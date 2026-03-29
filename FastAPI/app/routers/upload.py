from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.orm import Session
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import uuid
import tempfile
import os
import logging
import aiofiles

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models import User, TiffFile, Folder
from app.schemas import (
    TiffFileResponse, PresignRequest, PresignResponse,
    UploadCompleteRequest, UploadCompleteResponse,
    MultipartInitRequest, MultipartInitResponse,
    MultipartPresignPartRequest, MultipartPresignPartResponse,
    MultipartCompleteRequest, MultipartCompleteResponse,
    MultipartAbortRequest,
)
from app.auth import get_current_active_user
from app.config import settings
from app.cog_utils import convert_to_cog, is_cog as check_is_cog
from app.workers.tile_worker import generate_tiles_task
from rio_tiler.io import Reader

router = APIRouter(prefix="/upload", tags=["Upload"])

# Per-user file limits
MAX_DEM_PER_USER = 1
MAX_IMAGERY_PER_USER = 1  # Covers both ORTHOPHOTO and HILLSHADE


def _check_file_limit(db: Session, user_id, file_type: str):
    """Enforce per-user file type limits: 1 DEM, 1 Hillshade/Orthophoto."""
    ft = file_type.upper()
    if ft == "DEM":
        count = db.query(TiffFile).filter(TiffFile.user_id == user_id, TiffFile.file_type == "DEM").count()
        if count >= MAX_DEM_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You have reached the maximum of {MAX_DEM_PER_USER} DEM file(s). Delete your existing DEM before uploading a new one."
            )
    elif ft in ("ORTHOPHOTO", "HILLSHADE"):
        # Count both ORTHOPHOTO and HILLSHADE together — user gets 1 imagery file total
        count = db.query(TiffFile).filter(
            TiffFile.user_id == user_id,
            TiffFile.file_type.in_(["ORTHOPHOTO", "HILLSHADE"])
        ).count()
        if count >= MAX_IMAGERY_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You have reached the maximum of {MAX_IMAGERY_PER_USER} Hillshade/Orthophoto file(s). Delete your existing file before uploading a new one."
            )

s3_client = boto3.client('s3', region_name=settings.AWS_REGION)

def generate_s3_key(user_id: str, filename: str, file_type: str, bucket_type: str = "raw") -> str:
    """
    Generate S3 key for uploaded files

    Args:
        user_id: User's UUID
        filename: Original filename
        file_type: DEM or ORTHOPHOTO
        bucket_type: 'raw' for raw uploads, 'tiles' for processed tiles
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    unique_id = str(uuid.uuid4())[:8]
    ext = filename.rsplit('.', 1)[1] if '.' in filename else 'tif'
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    return f"uploads/{user_id}/{timestamp}/{file_type.lower()}/{name}-{unique_id}.{ext}"

def upload_to_s3(bucket: str, key: str, data: bytes, content_type: str = 'image/tiff') -> None:
    """
    Upload data to S3 with automatic multipart upload for large files

    Handles files of any size:
    - < 100MB: Simple upload (PutObject)
    - >= 100MB: Multipart upload (up to 5TB)

    Works for all file types: DEM, ORTHOPHOTO, COG

    Args:
        bucket: S3 bucket name
        key: S3 object key
        data: File content as bytes
        content_type: MIME type
    """
    file_size = len(data)
    # Use multipart for files >= 100MB (AWS recommends this threshold)
    multipart_threshold = 100 * 1024 * 1024  # 100MB

    if file_size < multipart_threshold:
        # Simple upload for files < 100MB
        logger.info(f"Simple upload: {file_size / (1024*1024):.2f} MB to s3://{bucket}/{key}")
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type
        )
    else:
        # Multipart upload for large files (100MB - 5TB)
        logger.info(f"Multipart upload: {file_size / (1024*1024):.2f} MB to s3://{bucket}/{key}")

        # Use 10MB chunks (minimum is 5MB except for last part)
        chunk_size = 10 * 1024 * 1024

        # Initiate multipart upload
        multipart = s3_client.create_multipart_upload(
            Bucket=bucket,
            Key=key,
            ContentType=content_type
        )
        upload_id = multipart['UploadId']

        try:
            parts = []
            part_number = 1
            offset = 0

            while offset < file_size:
                # Calculate chunk boundaries
                chunk_end = min(offset + chunk_size, file_size)
                chunk = data[offset:chunk_end]

                # Upload part
                progress_pct = (offset / file_size) * 100
                logger.info(f"Uploading part {part_number}: {progress_pct:.1f}% complete")

                response = s3_client.upload_part(
                    Bucket=bucket,
                    Key=key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk
                )

                parts.append({
                    'PartNumber': part_number,
                    'ETag': response['ETag']
                })

                part_number += 1
                offset = chunk_end

            # Complete multipart upload
            s3_client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            logger.info(f"Multipart upload completed: {part_number - 1} parts uploaded")

        except Exception as e:
            # Abort multipart upload on error
            logger.error(f"Multipart upload failed: {e}")
            try:
                s3_client.abort_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id
                )
                logger.info("Multipart upload aborted")
            except Exception as abort_error:
                logger.warning(f"Failed to abort multipart upload: {abort_error}")
            raise

@router.post("", response_model=TiffFileResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TiffFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Form(...),
    folder_id: str = Form(None),  # Optional folder ID
    convert_cog: bool = Form(True),  # Convert to COG by default
    generate_tiles: bool = Form(True),  # Generate static tiles by default
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if file_type.upper() not in ['DEM', 'ORTHOPHOTO', 'HILLSHADE']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be 'DEM', 'ORTHOPHOTO', or 'HILLSHADE'"
        )

    # Enforce per-user file limits
    _check_file_limit(db, current_user.id, file_type)

    # Check for duplicate filename for this user in the same folder
    existing_file = db.query(TiffFile).filter(
        TiffFile.user_id == current_user.id,
        TiffFile.filename == file.filename,
        TiffFile.folder_id == (uuid.UUID(folder_id) if folder_id else None),
    ).first()
    if existing_file:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'A file named "{file.filename}" already exists in this project. Please rename the file or delete the existing one first.'
        )

    if not file.filename.lower().endswith(('.tif', '.tiff')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only TIFF files allowed"
        )

    # Validate folder_id if provided
    folder_uuid = None
    if folder_id:
        try:
            folder_uuid = uuid.UUID(folder_id)
            # Verify folder exists and belongs to user
            folder = db.query(Folder).filter(
                Folder.id == folder_uuid,
                Folder.user_id == current_user.id
            ).first()
            if not folder:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Folder not found"
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid folder_id format"
            )

    s3_key = generate_s3_key(str(current_user.id), file.filename, file_type)

    # Temp file for streaming (avoid loading entire file into RAM)
    tmp_upload_path = None

    try:
        # Stream uploaded file to disk in chunks (memory efficient)
        tmp_fd, tmp_upload_path = tempfile.mkstemp(suffix='.tif')
        os.close(tmp_fd)  # Close file descriptor, we'll use aiofiles

        logger.info(f"Streaming {file.filename} to disk for user {current_user.id}")
        file_size = 0
        chunk_size = 10 * 1024 * 1024  # 10MB chunks

        async with aiofiles.open(tmp_upload_path, 'wb') as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                await f.write(chunk)
                file_size += len(chunk)

        logger.info(f"File written to disk: {file_size / (1024*1024):.2f} MB at {tmp_upload_path}")

        # Upload original TIFF to S3 RAW bucket using boto3's upload_file (handles multipart automatically)
        logger.info(f"Uploading {file.filename} ({file_size / (1024*1024):.2f} MB) to S3")
        s3_client.upload_file(
            tmp_upload_path,
            settings.S3_BUCKET_RAW,
            s3_key,
            ExtraArgs={'ContentType': 'image/tiff'}
        )

        s3_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.S3_BUCKET_RAW, 'Key': s3_key},
            ExpiresIn=604800
        )

        # Initialize database record
        db_file = TiffFile(
            user_id=current_user.id,
            folder_id=folder_uuid,  # Associate with folder if provided
            filename=file.filename,
            file_type=file_type.upper(),
            original_size_bytes=file_size,
            s3_bucket=settings.S3_BUCKET_RAW,
            s3_key=s3_key,
            s3_url=s3_url,
            upload_status='completed',
            upload_progress=100,
            upload_completed_at=datetime.utcnow()
        )

        # Convert to COG if requested
        if convert_cog:
            tmp_cog_path = None
            try:
                # Convert to COG from disk (memory efficient)
                tmp_cog_path = tmp_upload_path.replace('.tif', '_cog.tif')
                logger.info(f"Converting to COG: {tmp_upload_path} -> {tmp_cog_path}")

                # Use GDAL to convert to COG (operates on disk, not in memory)
                from osgeo import gdal
                gdal.Translate(
                    tmp_cog_path,
                    tmp_upload_path,
                    format='COG',
                    creationOptions=[
                        'COMPRESS=DEFLATE',
                        'TILED=YES',
                        'BLOCKXSIZE=512',
                        'BLOCKYSIZE=512',
                        'NUM_THREADS=ALL_CPUS'
                    ]
                )

                # Get COG file size
                cog_size = os.path.getsize(tmp_cog_path)
                logger.info(f"COG created: {cog_size / (1024*1024):.2f} MB")

                # Generate COG S3 key
                cog_s3_key = s3_key.replace('.tif', '_cog.tif').replace('.tiff', '_cog.tif')

                # Upload COG to S3 RAW bucket (boto3 handles multipart automatically)
                logger.info(f"Uploading COG ({cog_size / (1024*1024):.2f} MB) to S3")
                s3_client.upload_file(
                    tmp_cog_path,
                    settings.S3_BUCKET_RAW,
                    cog_s3_key,
                    ExtraArgs={'ContentType': 'image/tiff'}
                )

                # Set COG metadata separately
                s3_client.copy_object(
                    Bucket=settings.S3_BUCKET_RAW,
                    CopySource={'Bucket': settings.S3_BUCKET_RAW, 'Key': cog_s3_key},
                    Key=cog_s3_key,
                    Metadata={
                        'cog': 'true',
                        'original_key': s3_key
                    },
                    MetadataDirective='REPLACE'
                )

                # Update database record with COG info
                db_file.cog_s3_key = cog_s3_key
                db_file.cog_size_bytes = cog_size
                db_file.is_cog = False  # Original was not COG
                db_file.cog_created_at = datetime.utcnow()

                # Calculate bounds from COG (already on disk)
                try:
                    logger.info(f"Calculating bounds for {file.filename}...")
                    with Reader(tmp_cog_path) as src:
                        bounds = src.get_geographic_bounds(crs="EPSG:4326")
                        # bounds returns: [west, south, east, north]
                        db_file.bounds_west = str(bounds[0])
                        db_file.bounds_south = str(bounds[1])
                        db_file.bounds_east = str(bounds[2])
                        db_file.bounds_north = str(bounds[3])
                        logger.info(f"Bounds calculated: {bounds}")

                except Exception as bounds_error:
                    logger.warning(f"Failed to calculate bounds: {bounds_error}")
                    # Continue without bounds

                # Clean up COG temp file
                if tmp_cog_path and os.path.exists(tmp_cog_path):
                    os.unlink(tmp_cog_path)

            except Exception as cog_error:
                # Log error but don't fail the upload
                logger.error(f"COG conversion failed: {cog_error}")
                # Clean up on error
                if tmp_cog_path and os.path.exists(tmp_cog_path):
                    os.unlink(tmp_cog_path)
                # Original file is still uploaded successfully

        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        # Trigger async tile generation job with Celery if requested
        if generate_tiles and db_file.cog_s3_key:
            try:
                logger.info(f"Submitting Celery tile generation task for file {db_file.id}")

                # Submit Celery task
                task = generate_tiles_task.apply_async(
                    args=[
                        str(db_file.id),
                        db_file.s3_bucket,
                        db_file.cog_s3_key,
                        12,  # min_zoom - visible when zoomed out
                        21   # max_zoom - road-level detail
                    ],
                    task_id=f"tile_{db_file.id}"
                )

                db_file.tile_status = "queued"
                db.commit()
                logger.info(f"Celery task {task.id} queued for file {db_file.id}")

            except Exception as tile_error:
                logger.error(f"Failed to submit Celery task: {tile_error}")
                db_file.tile_status = "failed"
                db_file.tile_error = f"Failed to queue task: {str(tile_error)}"
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
    finally:
        # Clean up temp upload file
        if tmp_upload_path and os.path.exists(tmp_upload_path):
            try:
                os.unlink(tmp_upload_path)
                logger.info(f"Cleaned up temp file: {tmp_upload_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp file: {cleanup_error}")

@router.post("/presign", response_model=PresignResponse, status_code=status.HTTP_200_OK)
async def presign_upload(
    body: PresignRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate a presigned S3 PUT URL for direct browser-to-S3 upload.
    Bypasses the Vercel 4.5MB limit and 30s timeout for large TIFF files.
    """
    # Validate file_type
    if body.file_type.upper() not in ['DEM', 'ORTHOPHOTO', 'HILLSHADE']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be 'DEM', 'ORTHOPHOTO', or 'HILLSHADE'"
        )

    # Enforce per-user file limits
    _check_file_limit(db, current_user.id, body.file_type)

    # Validate filename
    if not body.filename.lower().endswith(('.tif', '.tiff')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only TIFF files allowed"
        )

    # Validate folder if provided
    folder_uuid = None
    if body.folder_id:
        folder = db.query(Folder).filter(
            Folder.id == body.folder_id,
            Folder.user_id == current_user.id
        ).first()
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Folder not found"
            )
        folder_uuid = body.folder_id

    # Check for duplicate filename
    existing_file = db.query(TiffFile).filter(
        TiffFile.user_id == current_user.id,
        TiffFile.filename == body.filename,
        TiffFile.folder_id == folder_uuid,
    ).first()
    if existing_file:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'A file named "{body.filename}" already exists in this project.'
        )

    # Generate S3 key
    s3_key = generate_s3_key(str(current_user.id), body.filename, body.file_type)

    # Generate presigned PUT URL (1 hour expiry)
    presigned_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': settings.S3_BUCKET_RAW,
            'Key': s3_key,
            'ContentType': body.content_type,
        },
        ExpiresIn=3600
    )

    # Create pending database record
    db_file = TiffFile(
        user_id=current_user.id,
        folder_id=folder_uuid,
        filename=body.filename,
        file_type=body.file_type.upper(),
        original_size_bytes=body.file_size,
        s3_bucket=settings.S3_BUCKET_RAW,
        s3_key=s3_key,
        upload_status='pending',
        upload_progress=0,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    logger.info(f"Presigned URL generated for {body.filename} (user={current_user.id}, upload_id={db_file.id})")

    return PresignResponse(
        presigned_url=presigned_url,
        s3_key=s3_key,
        upload_id=db_file.id,
    )


@router.post("/complete", response_model=UploadCompleteResponse, status_code=status.HTTP_200_OK)
async def complete_upload(
    body: UploadCompleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Confirm a presigned upload completed and queue processing.
    Validates the file exists in S3, updates the DB record, and queues
    COG conversion + tile generation via Celery.
    """
    # Find the pending upload record
    db_file = db.query(TiffFile).filter(
        TiffFile.id == body.upload_id,
        TiffFile.user_id == current_user.id,
    ).first()
    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload record not found"
        )

    if db_file.upload_status == 'completed':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload already completed"
        )

    # Verify file actually exists in S3
    try:
        head = s3_client.head_object(
            Bucket=settings.S3_BUCKET_RAW,
            Key=body.s3_key,
        )
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code in ('404', 'NoSuchKey'):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in S3. Upload may not have completed."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify S3 upload: {str(e)}"
        )

    # Update record with confirmed upload info
    file_size = head['ContentLength']
    db_file.original_size_bytes = file_size
    db_file.upload_status = 'completed'
    db_file.upload_progress = 100
    db_file.upload_completed_at = datetime.utcnow()
    db_file.s3_key = body.s3_key

    # Generate a presigned GET URL for the raw file
    db_file.s3_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.S3_BUCKET_RAW, 'Key': body.s3_key},
        ExpiresIn=604800
    )

    db.commit()

    # Queue Celery task for COG conversion + tile generation
    try:
        task = generate_tiles_task.apply_async(
            args=[
                str(db_file.id),
                settings.S3_BUCKET_RAW,
                body.s3_key,
                12,   # min_zoom - visible when zoomed out
                21,   # max_zoom - road-level detail
            ],
            task_id=f"tile_{db_file.id}"
        )
        db_file.tile_status = "queued"
        db.commit()
        logger.info(f"Upload complete: file={db_file.id}, size={file_size}, celery_task={task.id}")

    except Exception as e:
        logger.error(f"Failed to queue Celery task for {db_file.id}: {e}")
        db_file.tile_status = "failed"
        db_file.tile_error = f"Failed to queue processing: {str(e)}"
        db.commit()
        return UploadCompleteResponse(job_id=str(db_file.id), status="queue_failed")

    return UploadCompleteResponse(job_id=task.id, status="processing")


# ── Multipart presigned upload (for files > 5GB) ──────────────────────

@router.post("/multipart/init", response_model=MultipartInitResponse, status_code=status.HTTP_200_OK)
async def multipart_init(
    body: MultipartInitRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Initiate an S3 multipart upload for large files (>5GB).
    Returns an s3_upload_id that the browser uses to upload parts directly.
    """
    if body.file_type.upper() not in ['DEM', 'ORTHOPHOTO', 'HILLSHADE']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be 'DEM', 'ORTHOPHOTO', or 'HILLSHADE'"
        )

    # Enforce per-user file limits
    _check_file_limit(db, current_user.id, body.file_type)

    if not body.filename.lower().endswith(('.tif', '.tiff')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only TIFF files allowed"
        )

    folder_uuid = None
    if body.folder_id:
        folder = db.query(Folder).filter(
            Folder.id == body.folder_id,
            Folder.user_id == current_user.id
        ).first()
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Folder not found"
            )
        folder_uuid = body.folder_id

    existing_file = db.query(TiffFile).filter(
        TiffFile.user_id == current_user.id,
        TiffFile.filename == body.filename,
        TiffFile.folder_id == folder_uuid,
    ).first()
    if existing_file:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'A file named "{body.filename}" already exists in this project.'
        )

    s3_key = generate_s3_key(str(current_user.id), body.filename, body.file_type)

    # Create S3 multipart upload
    multipart = s3_client.create_multipart_upload(
        Bucket=settings.S3_BUCKET_RAW,
        Key=s3_key,
        ContentType=body.content_type,
    )
    s3_upload_id = multipart['UploadId']

    # Create pending DB record
    db_file = TiffFile(
        user_id=current_user.id,
        folder_id=folder_uuid,
        filename=body.filename,
        file_type=body.file_type.upper(),
        original_size_bytes=body.file_size,
        s3_bucket=settings.S3_BUCKET_RAW,
        s3_key=s3_key,
        upload_status='pending',
        upload_progress=0,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    logger.info(f"Multipart upload initiated for {body.filename} (upload_id={db_file.id}, s3_upload_id={s3_upload_id})")

    return MultipartInitResponse(
        upload_id=db_file.id,
        s3_key=s3_key,
        s3_upload_id=s3_upload_id,
    )


@router.post("/multipart/presign-part", response_model=MultipartPresignPartResponse, status_code=status.HTTP_200_OK)
async def multipart_presign_part(
    body: MultipartPresignPartRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate a presigned URL for uploading a single part of a multipart upload.
    The browser calls this once per chunk (e.g., every 100MB).
    """
    presigned_url = s3_client.generate_presigned_url(
        'upload_part',
        Params={
            'Bucket': settings.S3_BUCKET_RAW,
            'Key': body.s3_key,
            'PartNumber': body.part_number,
            'UploadId': body.s3_upload_id,
        },
        ExpiresIn=3600,
    )

    return MultipartPresignPartResponse(
        presigned_url=presigned_url,
        part_number=body.part_number,
    )


@router.post("/multipart/complete", response_model=MultipartCompleteResponse, status_code=status.HTTP_200_OK)
async def multipart_complete(
    body: MultipartCompleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Finalize a multipart upload after all parts are uploaded.
    Completes the S3 multipart upload and queues the Celery processing job.
    """
    db_file = db.query(TiffFile).filter(
        TiffFile.id == body.upload_id,
        TiffFile.user_id == current_user.id,
    ).first()
    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload record not found"
        )

    if db_file.upload_status == 'completed':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload already completed"
        )

    # Complete the S3 multipart upload
    s3_parts = [
        {'PartNumber': p.part_number, 'ETag': p.etag}
        for p in sorted(body.parts, key=lambda p: p.part_number)
    ]

    try:
        s3_client.complete_multipart_upload(
            Bucket=settings.S3_BUCKET_RAW,
            Key=body.s3_key,
            UploadId=body.s3_upload_id,
            MultipartUpload={'Parts': s3_parts},
        )
    except ClientError as e:
        logger.error(f"Failed to complete multipart upload: {e}")
        try:
            s3_client.abort_multipart_upload(
                Bucket=settings.S3_BUCKET_RAW,
                Key=body.s3_key,
                UploadId=body.s3_upload_id,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete S3 upload: {str(e)}"
        )

    # Verify file in S3
    try:
        head = s3_client.head_object(Bucket=settings.S3_BUCKET_RAW, Key=body.s3_key)
    except ClientError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File not found in S3 after completing multipart upload"
        )

    file_size = head['ContentLength']
    db_file.original_size_bytes = file_size
    db_file.upload_status = 'completed'
    db_file.upload_progress = 100
    db_file.upload_completed_at = datetime.utcnow()
    db_file.s3_key = body.s3_key
    db_file.s3_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.S3_BUCKET_RAW, 'Key': body.s3_key},
        ExpiresIn=604800,
    )
    db.commit()

    # Queue Celery task
    try:
        task = generate_tiles_task.apply_async(
            args=[str(db_file.id), settings.S3_BUCKET_RAW, body.s3_key, 12, 21],
            task_id=f"tile_{db_file.id}",
        )
        db_file.tile_status = "queued"
        db.commit()
        logger.info(f"Multipart upload complete: file={db_file.id}, size={file_size}, celery_task={task.id}")
    except Exception as e:
        logger.error(f"Failed to queue Celery task for {db_file.id}: {e}")
        db_file.tile_status = "failed"
        db_file.tile_error = f"Failed to queue processing: {str(e)}"
        db.commit()
        return MultipartCompleteResponse(job_id=str(db_file.id), status="queue_failed")

    return MultipartCompleteResponse(job_id=task.id, status="processing")


@router.post("/multipart/abort", status_code=status.HTTP_200_OK)
async def multipart_abort(
    body: MultipartAbortRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Abort a multipart upload. Cleans up S3 and removes the pending DB record.
    Call this if the user cancels an in-progress upload.
    """
    try:
        s3_client.abort_multipart_upload(
            Bucket=settings.S3_BUCKET_RAW,
            Key=body.s3_key,
            UploadId=body.s3_upload_id,
        )
    except Exception as e:
        logger.warning(f"Failed to abort S3 multipart upload: {e}")

    db_file = db.query(TiffFile).filter(
        TiffFile.id == body.upload_id,
        TiffFile.user_id == current_user.id,
        TiffFile.upload_status == 'pending',
    ).first()
    if db_file:
        db.delete(db_file)
        db.commit()

    logger.info(f"Multipart upload aborted: upload_id={body.upload_id}")
    return {"status": "aborted"}


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
        # 1. Delete original file from RAW bucket
        logger.info(f"Deleting original file: s3://{db_file.s3_bucket}/{db_file.s3_key}")
        try:
            s3_client.delete_object(Bucket=db_file.s3_bucket, Key=db_file.s3_key)
        except ClientError as e:
            logger.warning(f"Failed to delete original file from raw bucket: {e}")

        # 2. Delete COG file from RAW bucket (if it exists there)
        if db_file.cog_s3_key and db_file.cog_s3_key.startswith('uploads/'):
            logger.info(f"Deleting COG from raw bucket: s3://{db_file.s3_bucket}/{db_file.cog_s3_key}")
            try:
                s3_client.delete_object(Bucket=db_file.s3_bucket, Key=db_file.cog_s3_key)
            except ClientError as e:
                logger.warning(f"Failed to delete COG from raw bucket: {e}")

        # 3. Delete COG file from APP bucket (tiles bucket)
        # COG is stored at: cogs/{user_id}/{file_id}.tif
        cog_key_in_tiles_bucket = f"cogs/{db_file.user_id}/{db_file.id}.tif"
        logger.info(f"Deleting COG from app bucket: s3://{settings.S3_BUCKET_NAME}/{cog_key_in_tiles_bucket}")
        try:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=cog_key_in_tiles_bucket)
        except ClientError as e:
            logger.warning(f"Failed to delete COG from app bucket: {e}")

        # 4. Delete all generated tiles from APP bucket
        # Tiles are stored at: tiles/{user_id}/{file_id}/{z}/{x}/{y}.png
        tile_prefix = f"tiles/{db_file.user_id}/{db_file.id}/"
        logger.info(f"Deleting tiles with prefix: s3://{settings.S3_BUCKET_NAME}/{tile_prefix}")

        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=tile_prefix)

            delete_count = 0
            for page in pages:
                if 'Contents' in page:
                    # Delete in batches of up to 1000 objects
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                    if objects_to_delete:
                        s3_client.delete_objects(
                            Bucket=settings.S3_BUCKET_NAME,
                            Delete={'Objects': objects_to_delete}
                        )
                        delete_count += len(objects_to_delete)

            logger.info(f"Deleted {delete_count} tile files from app bucket")

        except ClientError as e:
            logger.warning(f"Failed to delete tiles from app bucket: {e}")

        # 5. Delete database record
        db.delete(db_file)
        db.commit()
        logger.info(f"Successfully deleted file {db_file.filename} (ID: {db_file.id})")
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 delete failed: {str(e)}"
        )