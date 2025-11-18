from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.models import User, Folder, TiffFile
from app.schemas import FolderCreate, FolderUpdate, FolderResponse, FolderWithFilesResponse, TiffFileResponse
from app.auth import get_current_user

router = APIRouter(
    prefix="/folders",
    tags=["folders"]
)

@router.post("/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    folder: FolderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new folder for the current user"""
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

    # Build response with files
    response = []
    for folder in folders:
        folder_data = FolderWithFilesResponse(
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
    """Delete a folder (files will have folder_id set to NULL)"""
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    db.delete(folder)
    db.commit()

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
