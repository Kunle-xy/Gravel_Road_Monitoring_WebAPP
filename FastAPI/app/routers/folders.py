from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
import boto3
from botocore.exceptions import ClientError
import logging

from app.database import get_db
from app.models import User, Folder, TiffFile, VideoFile
from app.schemas import FolderCreate, FolderUpdate, FolderResponse, FolderWithFilesResponse, TiffFileResponse, VideoFileResponse
from app.auth import get_current_user
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize S3 client
s3_client = boto3.client('s3', region_name=settings.AWS_REGION)

router = APIRouter(
    prefix="/folders",
    tags=["folders"]
)

@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    folder: FolderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new folder for the current user"""
    # Limit: 5 projects per user
    existing_count = db.query(Folder).filter(Folder.user_id == current_user.id).count()
    if existing_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have reached the maximum of 5 projects. Please delete an existing project before creating a new one."
        )

    new_folder = Folder(
        user_id=current_user.id,
        name=folder.name,
        description=folder.description,
        color=folder.color
    )

    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)

    return new_folder

@router.get("", response_model=List[FolderResponse])
@router.get("/", response_model=List[FolderResponse])
def list_folders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all folders for the current user"""
    folders = db.query(Folder).filter(
        Folder.user_id == current_user.id
    ).order_by(Folder.created_at.desc()).all()

    return folders

@router.get("/with-files", response_model=List[FolderWithFilesResponse])
def list_folders_with_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all folders with their files for the current user"""
    folders = db.query(Folder).filter(
        Folder.user_id == current_user.id
    ).order_by(Folder.created_at.desc()).all()

    # Build response with files and videos
    response = []
    for folder in folders:
        # Get videos for this folder
        folder_videos = db.query(VideoFile).filter(
            VideoFile.folder_id == folder.id,
            VideoFile.upload_status == "completed",
        ).all()

        folder_data = FolderWithFilesResponse(
            id=folder.id,
            user_id=folder.user_id,
            name=folder.name,
            description=folder.description,
            color=folder.color,
            is_expanded=folder.is_expanded,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
            files=[TiffFileResponse.from_orm(f) for f in folder.tiff_files],
            videos=[VideoFileResponse.from_orm(v) for v in folder_videos],
        )
        response.append(folder_data)

    return response

@router.get("/{folder_id}", response_model=FolderWithFilesResponse)
def get_folder(
    folder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific folder with its files"""
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    return FolderWithFilesResponse(
        id=folder.id,
        user_id=folder.user_id,
        name=folder.name,
        description=folder.description,
        color=folder.color,
        is_expanded=folder.is_expanded,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
        files=[TiffFileResponse.from_orm(f) for f in folder.tiff_files]
    )

@router.patch("/{folder_id}", response_model=FolderResponse)
def update_folder(
    folder_id: uuid.UUID,
    folder_update: FolderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a folder's properties"""
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    # Update only provided fields
    update_data = folder_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(folder, key, value)

    db.commit()
    db.refresh(folder)

    return folder

@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a folder and ALL files within it.

    This will permanently delete:
    - All files in the folder from the database
    - All original TIFF files from S3 RAW bucket
    - All COG files from S3 (both RAW and APP buckets)
    - All generated tiles from S3 APP bucket
    - The folder itself from the database

    This action is IRREVERSIBLE.
    """
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    # Get all files in the folder
    files_in_folder = db.query(TiffFile).filter(
        TiffFile.folder_id == folder_id
    ).all()

    logger.info(f"Deleting folder '{folder.name}' (ID: {folder_id}) with {len(files_in_folder)} files")

    # Delete each file's S3 objects before database cascade deletion
    for db_file in files_in_folder:
        try:
            logger.info(f"Deleting S3 objects for file: {db_file.filename} (ID: {db_file.id})")

            # 1. Delete original file from RAW bucket
            try:
                s3_client.delete_object(Bucket=db_file.s3_bucket, Key=db_file.s3_key)
                logger.info(f"Deleted original: s3://{db_file.s3_bucket}/{db_file.s3_key}")
            except ClientError as e:
                logger.warning(f"Failed to delete original file: {e}")

            # 2. Delete COG file from RAW bucket (if it exists)
            if db_file.cog_s3_key and db_file.cog_s3_key.startswith('uploads/'):
                try:
                    s3_client.delete_object(Bucket=db_file.s3_bucket, Key=db_file.cog_s3_key)
                    logger.info(f"Deleted COG from RAW: s3://{db_file.s3_bucket}/{db_file.cog_s3_key}")
                except ClientError as e:
                    logger.warning(f"Failed to delete COG from RAW bucket: {e}")

            # 3. Delete COG file from APP bucket (tiles bucket)
            cog_key_in_tiles_bucket = f"cogs/{db_file.user_id}/{db_file.id}.tif"
            try:
                s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=cog_key_in_tiles_bucket)
                logger.info(f"Deleted COG from APP: s3://{settings.S3_BUCKET_NAME}/{cog_key_in_tiles_bucket}")
            except ClientError as e:
                logger.warning(f"Failed to delete COG from APP bucket: {e}")

            # 4. Delete all generated tiles from APP bucket
            tile_prefix = f"tiles/{db_file.user_id}/{db_file.id}/"
            try:
                paginator = s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=tile_prefix)

                delete_count = 0
                for page in pages:
                    if 'Contents' in page:
                        objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                        if objects_to_delete:
                            s3_client.delete_objects(
                                Bucket=settings.S3_BUCKET_NAME,
                                Delete={'Objects': objects_to_delete}
                            )
                            delete_count += len(objects_to_delete)

                logger.info(f"Deleted {delete_count} tile files for {db_file.filename}")
            except ClientError as e:
                logger.warning(f"Failed to delete tiles: {e}")

        except Exception as e:
            # Log error but continue deleting other files
            logger.error(f"Error deleting S3 objects for file {db_file.id}: {e}")

    # Delete the folder (CASCADE will delete all file records from database)
    db.delete(folder)
    db.commit()

    logger.info(f"Successfully deleted folder '{folder.name}' and {len(files_in_folder)} files")
    return None

@router.post("/{folder_id}/files/{file_id}", response_model=TiffFileResponse)
def add_file_to_folder(
    folder_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a file to a folder"""
    # Verify folder exists and belongs to user
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    # Verify file exists and belongs to user
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Add file to folder
    file.folder_id = folder_id
    db.commit()
    db.refresh(file)

    return file

@router.delete("/{folder_id}/files/{file_id}", response_model=TiffFileResponse)
def remove_file_from_folder(
    folder_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a file from a folder (set folder_id to NULL)"""
    # Verify file exists, belongs to user, and is in the folder
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id,
        TiffFile.folder_id == folder_id
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in this folder"
        )

    # Remove from folder
    file.folder_id = None
    db.commit()
    db.refresh(file)

    return file
