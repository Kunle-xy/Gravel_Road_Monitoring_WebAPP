from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.orm import Session
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import uuid
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models import User, TiffFile
from app.schemas import TiffFileResponse
from app.auth import get_current_active_user
from app.config import settings
from app.cog_utils import convert_to_cog, is_cog as check_is_cog
from app.job_manager import submit_tile_generation_job
from rio_tiler.io import Reader

router = APIRouter(prefix="/upload", tags=["Upload"])

s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION
)

def generate_s3_key(user_id: str, filename: str, file_type: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    unique_id = str(uuid.uuid4())[:8]
    ext = filename.rsplit('.', 1)[1] if '.' in filename else 'tif'
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    return f"uploads/{user_id}/{timestamp}/{file_type.lower()}/{name}-{unique_id}.{ext}"

@router.post("/", response_model=TiffFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Form(...),
    convert_cog: bool = Form(True),  # Convert to COG by default
    generate_tiles: bool = Form(True),  # Generate static tiles by default
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if file_type.upper() not in ['DEM', 'ORTHOPHOTO']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be 'DEM' or 'ORTHOPHOTO'"
        )

    if not file.filename.lower().endswith(('.tif', '.tiff')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only TIFF files allowed"
        )

    s3_key = generate_s3_key(str(current_user.id), file.filename, file_type)

    try:
        file_content = await file.read()
        file_size = len(file_content)

        # Upload original TIFF to S3
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType='image/tiff'
        )

        s3_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=604800
        )

        # Initialize database record
        db_file = TiffFile(
            user_id=current_user.id,
            filename=file.filename,
            file_type=file_type.upper(),
            original_size_bytes=file_size,
            s3_bucket=settings.S3_BUCKET_NAME,
            s3_key=s3_key,
            s3_url=s3_url,
            upload_status='completed',
            upload_progress=100,
            upload_completed_at=datetime.utcnow()
        )

        # Convert to COG if requested
        if convert_cog:
            try:
                cog_data, cog_size = convert_to_cog(file_content)

                # Generate COG S3 key
                cog_s3_key = s3_key.replace('.tif', '_cog.tif').replace('.tiff', '_cog.tif')

                # Upload COG to S3
                s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=cog_s3_key,
                    Body=cog_data,
                    ContentType='image/tiff',
                    Metadata={
                        'cog': 'true',
                        'original_key': s3_key
                    }
                )

                # Update database record with COG info
                db_file.cog_s3_key = cog_s3_key
                db_file.cog_size_bytes = cog_size
                db_file.is_cog = False  # Original was not COG
                db_file.cog_created_at = datetime.utcnow()

                # Calculate bounds from COG
                try:
                    print(f"Calculating bounds for {file.filename}...")
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp_file:
                        tmp_file.write(cog_data)
                        tmp_path = tmp_file.name

                    try:
                        with Reader(tmp_path) as src:
                            bounds = src.get_geographic_bounds(crs="EPSG:4326")
                            # bounds returns: [west, south, east, north]
                            db_file.bounds_west = str(bounds[0])
                            db_file.bounds_south = str(bounds[1])
                            db_file.bounds_east = str(bounds[2])
                            db_file.bounds_north = str(bounds[3])
                            print(f"Bounds calculated: {bounds}")
                    finally:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)

                except Exception as bounds_error:
                    print(f"Failed to calculate bounds: {bounds_error}")
                    # Continue without bounds

            except Exception as cog_error:
                # Log error but don't fail the upload
                print(f"COG conversion failed: {cog_error}")
                # Original file is still uploaded successfully

        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        # Trigger async tile generation job if requested
        if generate_tiles and db_file.cog_s3_key:
            try:
                logger.info(f"Submitting tile generation job for file {db_file.id}")
                submit_tile_generation_job(
                    file_id=str(db_file.id),
                    s3_key=db_file.cog_s3_key
                )
                db_file.tile_status = "queued"
                db.commit()
                logger.info(f"Tile generation job queued for {db_file.id}")
            except Exception as tile_error:
                logger.error(f"Failed to submit tile generation job: {tile_error}")
                db_file.tile_status = "failed"
                db_file.tile_error = f"Failed to queue job: {str(tile_error)}"
                db.commit()

        return db_file

    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 upload failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    try:
        # Delete original file from S3
        s3_client.delete_object(Bucket=db_file.s3_bucket, Key=db_file.s3_key)

        # Delete COG file if it exists
        if db_file.cog_s3_key:
            try:
                s3_client.delete_object(Bucket=db_file.s3_bucket, Key=db_file.cog_s3_key)
            except ClientError as cog_delete_error:
                logger.warning(f"Failed to delete COG file: {cog_delete_error}")

        # Delete all generated tiles if they exist
        if db_file.tile_status == "completed":
            try:
                # List all tiles under tiles/{file_id}/
                tile_prefix = f"tiles/{db_file.id}/"
                logger.info(f"Deleting tiles with prefix: {tile_prefix}")

                paginator = s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=db_file.s3_bucket, Prefix=tile_prefix)

                delete_count = 0
                for page in pages:
                    if 'Contents' in page:
                        # Delete in batches of up to 1000 objects
                        objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                        if objects_to_delete:
                            s3_client.delete_objects(
                                Bucket=db_file.s3_bucket,
                                Delete={'Objects': objects_to_delete}
                            )
                            delete_count += len(objects_to_delete)

                logger.info(f"Deleted {delete_count} tile files")

            except ClientError as tile_delete_error:
                logger.warning(f"Failed to delete tiles: {tile_delete_error}")

        db.delete(db_file)
        db.commit()
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 delete failed: {str(e)}"
        )