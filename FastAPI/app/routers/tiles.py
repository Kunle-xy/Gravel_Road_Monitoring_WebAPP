"""
Tile serving endpoints using rio-tiler
Serves map tiles directly from S3 COG files
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response
from sqlalchemy.orm import Session
import boto3
from botocore.exceptions import ClientError
from io import BytesIO
import tempfile
import os

from rio_tiler.io import Reader
from rio_tiler.models import ImageData

from app.database import get_db
from app.models import User, TiffFile
from app.auth import get_current_active_user
from app.config import settings

router = APIRouter(prefix="/tiles", tags=["Tiles"])

s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION
)


def get_s3_file_path(bucket: str, key: str) -> str:
    """Generate S3 path compatible with rasterio"""
    return f"s3://{bucket}/{key}"


@router.get("/{file_id}/{z}/{x}/{y}.png")
async def get_tile(
    file_id: str,
    z: int = Path(..., ge=0, le=26),
    x: int = Path(..., ge=0),
    y: int = Path(..., ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Serve a map tile for the given file at specified zoom/x/y coordinates
    Returns PNG image tile or transparent tile if outside bounds
    Supports zoom levels 0-26 for high-resolution overlay display
    """
    # Get file from database
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Use COG if available
    s3_key = file.cog_s3_key if file.cog_s3_key else file.s3_key

    try:
        # Download file from S3 to temp file
        # (rio-tiler needs a file path, not just bytes)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp_file:
            s3_client.download_fileobj(
                Bucket=file.s3_bucket,
                Key=s3_key,
                Fileobj=tmp_file
            )
            tmp_path = tmp_file.name

        try:
            # Read and generate tile
            with Reader(tmp_path) as src:
                try:
                    # Generate tile at original quality
                    img: ImageData = src.tile(x, y, z, tilesize=256)

                    # Render to PNG with maximum quality (no compression)
                    png_data = img.render(
                        img_format="PNG",
                        # PNG options for best quality
                        **{"compress_level": 0}  # No compression for best quality
                    )

                    return Response(
                        content=png_data,
                        media_type="image/png",
                        headers={
                            "Cache-Control": "public, max-age=3600",
                            "Access-Control-Allow-Origin": "*"
                        }
                    )
                except Exception as tile_error:
                    # If tile is outside bounds, return transparent 256x256 PNG
                    if "outside bounds" in str(tile_error).lower():
                        # 1x1 transparent PNG (smallest possible)
                        transparent_png = bytes([
                            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
                            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
                            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
                            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
                            0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
                            0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
                            0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
                            0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
                            0x42, 0x60, 0x82
                        ])
                        return Response(
                            content=transparent_png,
                            media_type="image/png",
                            headers={
                                "Cache-Control": "public, max-age=86400",
                                "Access-Control-Allow-Origin": "*"
                            }
                        )
                    else:
                        # Other errors, re-raise
                        raise tile_error

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating tile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate tile: {str(e)}"
        )


@router.get("/{file_id}/info")
async def get_info(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get raster metadata (bounds, size, etc.)"""
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    s3_key = file.cog_s3_key if file.cog_s3_key else file.s3_key

    try:
        # Download file from S3 to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp_file:
            s3_client.download_fileobj(
                Bucket=file.s3_bucket,
                Key=s3_key,
                Fileobj=tmp_file
            )
            tmp_path = tmp_file.name

        try:
            with Reader(tmp_path) as src:
                info = src.info()
                return {
                    "bounds": info.bounds,
                    "minzoom": info.minzoom,
                    "maxzoom": info.maxzoom,
                    "band_descriptions": info.band_descriptions,
                    "dtype": info.dtype,
                    "colorinterp": info.colorinterp,
                    "nodata_type": info.nodata_type
                }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get info: {str(e)}"
        )


@router.get("/{file_id}/bounds")
async def get_bounds(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get geographic bounds of the raster"""
    file = db.query(TiffFile).filter(
        TiffFile.id == file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    s3_key = file.cog_s3_key if file.cog_s3_key else file.s3_key

    print(f"Getting bounds for file {file_id}")
    print(f"S3 bucket: {file.s3_bucket}, key: {s3_key}")

    tmp_path = None
    try:
        # Download file from S3 to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp_file:
            print(f"Downloading from S3...")
            s3_client.download_fileobj(
                Bucket=file.s3_bucket,
                Key=s3_key,
                Fileobj=tmp_file
            )
            tmp_path = tmp_file.name
            print(f"Downloaded to temp file: {tmp_path}")

        try:
            print(f"Opening raster with rio-tiler...")
            with Reader(tmp_path) as src:
                # Get bounds in WGS84 (EPSG:4326) for Leaflet
                bounds = src.get_geographic_bounds(crs="EPSG:4326")
                print(f"Geographic bounds (WSEN): {bounds}")

                # get_geographic_bounds returns: BoundingBox(west, south, east, north)
                result = {
                    "bounds": [
                        [bounds[1], bounds[0]],  # [south, west] = [lat, lon]
                        [bounds[3], bounds[2]]   # [north, east] = [lat, lon]
                    ]
                }
                print(f"Returning formatted bounds: {result}")

                return result
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                print(f"Cleaned up temp file")

    except ClientError as e:
        print(f"S3 ClientError: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file from S3: {str(e)}"
        )
    except Exception as e:
        print(f"Error getting bounds: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get bounds: {str(e)}"
        )
