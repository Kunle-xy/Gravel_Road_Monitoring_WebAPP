from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import boto3
from botocore.exceptions import ClientError
import httpx

from app.database import get_db
from app.models import User, TiffFile
from app.schemas import TiffFileResponse, TiffFileListResponse
from app.auth import get_current_active_user
from app.config import settings

router = APIRouter(prefix="/files", tags=["Files"])

s3_client = boto3.client('s3', region_name=settings.AWS_REGION)

def check_s3_file_exists(bucket: str, key: str) -> bool:
    """Check if file exists in S3"""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False

@router.get("", response_model=TiffFileListResponse)
@router.get("/", response_model=TiffFileListResponse)
async def get_user_files(
    file_type: Optional[str] = Query(None, description="Filter by DEM or ORTHOPHOTO"),
    verify_s3: bool = Query(False, description="Verify files exist in S3"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(TiffFile).filter(TiffFile.user_id == current_user.id)

    if file_type:
        query = query.filter(TiffFile.file_type == file_type.upper())

    files = query.order_by(TiffFile.created_at.desc()).all()

    # Optionally verify S3 files exist and filter out missing ones
    if verify_s3:
        valid_files = []
        for file in files:
            if check_s3_file_exists(file.s3_bucket, file.s3_key):
                valid_files.append(file)
        files = valid_files

    return {
        "total": len(files),
        "files": files
    }

@router.post("/sync", status_code=status.HTTP_200_OK)
async def sync_files_with_s3(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Sync database with S3: Remove database records for files that no longer exist in S3
    """
    files = db.query(TiffFile).filter(TiffFile.user_id == current_user.id).all()

    removed_count = 0
    missing_files = []

    for file in files:
        if not check_s3_file_exists(file.s3_bucket, file.s3_key):
            missing_files.append({
                "id": str(file.id),
                "filename": file.filename,
                "s3_key": file.s3_key
            })
            db.delete(file)
            removed_count += 1

    if removed_count > 0:
        db.commit()

    return {
        "message": f"Sync completed. Removed {removed_count} orphaned records.",
        "removed_count": removed_count,
        "removed_files": missing_files
    }

@router.get("/{file_id}", response_model=TiffFileResponse)
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Verify file exists in S3
    if not check_s3_file_exists(file.s3_bucket, file.s3_key):
        # File was deleted from S3, remove from database
        db.delete(file)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in S3 storage"
        )

    return file

@router.get("/{file_id}/download-url")
async def get_file_download_url(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate a presigned URL for downloading a TIFF file
    """
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Verify file exists in S3
    if not check_s3_file_exists(file.s3_bucket, file.s3_key):
        db.delete(file)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in S3 storage"
        )

    try:
        # Generate presigned URL valid for 1 hour
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': file.s3_bucket,
                'Key': file.s3_key
            },
            ExpiresIn=3600  # 1 hour
        )

        return {
            "file_id": str(file.id),
            "filename": file.filename,
            "file_type": file.file_type,
            "download_url": presigned_url,
            "expires_in": 3600
        }
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        )


@router.get("/{file_id}/cog-file")
async def get_cog_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Stream the COG file from S3 - used as a proxy for TiTiler
    """
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Use COG if available, otherwise use original
    s3_key_to_use = file.cog_s3_key if file.cog_s3_key else file.s3_key

    # Verify file exists in S3
    if not check_s3_file_exists(file.s3_bucket, s3_key_to_use):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in S3 storage"
        )

    try:
        # Get object from S3
        response = s3_client.get_object(Bucket=file.s3_bucket, Key=s3_key_to_use)

        # Stream the file
        return StreamingResponse(
            response['Body'],
            media_type='image/tiff',
            headers={
                'Content-Disposition': f'inline; filename="{file.filename}"',
                'Access-Control-Allow-Origin': '*'
            }
        )
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch file from S3: {str(e)}"
        )


@router.get("/{file_id}/tiles")
async def get_file_tiles_info(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get tile URLs for displaying the file on a map

    Priority:
    1. Static pre-generated tiles (if completed) - FAST, cached
    2. Dynamic tiles via rio-tiler (fallback) - SLOW, realtime
    """
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Use static tiles if available
    if file.tile_status == "completed" and file.tile_url_template:
        # Parse bounds
        bounds = None
        if all([file.bounds_south, file.bounds_west, file.bounds_north, file.bounds_east]):
            bounds = [
                [float(file.bounds_south), float(file.bounds_west)],
                [float(file.bounds_north), float(file.bounds_east)]
            ]

        return {
            "file_id": str(file.id),
            "filename": file.filename,
            "file_type": file.file_type,
            "tile_url": file.tile_url_template,
            "tile_type": "static",
            "tile_status": file.tile_status,
            "bounds": bounds,
            "min_zoom": file.tile_min_zoom,
            "max_zoom": file.tile_max_zoom,
            "usage": {
                "leaflet": f"L.tileLayer('{file.tile_url_template}', {{minZoom: {file.tile_min_zoom}, maxZoom: {file.tile_max_zoom}}}).addTo(map);",
                "note": "Static pre-generated tiles served from S3 with CDN caching"
            }
        }

    # Fallback to dynamic tiles
    # Use COG if available, otherwise use original
    s3_key_to_use = file.cog_s3_key if file.cog_s3_key else file.s3_key

    # Verify file exists in S3
    if not check_s3_file_exists(file.s3_bucket, s3_key_to_use):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in S3 storage"
        )

    try:
        # Use our own backend tile server (dynamic)
        backend_url = settings.FRONTEND_URL.replace('3000', '8000')
        if not backend_url.startswith('http'):
            backend_url = "http://localhost:8000"

        # Dynamic tile endpoints
        tile_url = f"{backend_url}/tiles/{file_id}/{{z}}/{{x}}/{{y}}.png"
        info_url = f"{backend_url}/tiles/{file_id}/info"
        bounds_url = f"{backend_url}/tiles/{file_id}/bounds"

        # Parse bounds
        bounds = None
        if all([file.bounds_south, file.bounds_west, file.bounds_north, file.bounds_east]):
            bounds = [
                [float(file.bounds_south), float(file.bounds_west)],
                [float(file.bounds_north), float(file.bounds_east)]
            ]

        return {
            "file_id": str(file.id),
            "filename": file.filename,
            "file_type": file.file_type,
            "is_cog": bool(file.cog_s3_key),
            "tile_url": tile_url,
            "tile_type": "dynamic",
            "tile_status": file.tile_status if file.tile_status else "not_started",
            "info_url": info_url,
            "bounds_url": bounds_url,
            "bounds": bounds,
            "expires_in": 3600,
            "usage": {
                "leaflet": f"L.tileLayer('{tile_url}', {{maxZoom: 18}}).addTo(map);",
                "note": "Dynamic tiles served from FastAPI backend using rio-tiler (slower)"
            }
        }
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate tile URL: {str(e)}"
        )