"""
Celery Worker for Tile Generation

This module handles asynchronous tile generation using Celery.
Tasks can be distributed across multiple workers for horizontal scaling.
"""

import os
import json
import tempfile
import subprocess
import logging
from datetime import datetime
from typing import Optional

import boto3
import rasterio
from rasterio.warp import transform_bounds
from celery import Task

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import TiffFile
from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """
    Custom Celery task that manages database sessions
    """
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Close database session after task completes"""
        if self._db is not None:
            self._db.close()
            self._db = None


# Initialize S3 client
s3_client = boto3.client('s3', region_name=settings.AWS_REGION)


def _s3_download(bucket: str, key: str, dst: str) -> dict:
    """
    Download file from S3 with validation
    Returns: dict with file_size and metadata
    """
    import time

    logger.info(f"Downloading s3://{bucket}/{key} to {dst}")

    # Get file metadata first
    metadata = s3_client.head_object(Bucket=bucket, Key=key)
    expected_size = metadata['ContentLength']
    logger.info(f"Expected file size: {expected_size} bytes")

    # Download file
    s3_client.download_file(bucket, key, dst)

    # Small delay to ensure file system has settled
    time.sleep(0.5)

    # Verify download
    actual_size = os.path.getsize(dst)
    if actual_size != expected_size:
        raise ValueError(
            f"Download incomplete: expected {expected_size} bytes, got {actual_size} bytes"
        )

    # Additional validation: ensure file is readable
    try:
        with open(dst, 'rb') as f:
            # Read first few bytes to ensure file handle works
            f.read(1024)
    except Exception as e:
        raise ValueError(f"Downloaded file is not readable: {e}")

    logger.info(f"Download verified: {actual_size} bytes")
    return {"file_size": actual_size, "metadata": metadata}


def _s3_upload_file(local_path: str, bucket: str, key: str, content_type: str = "image/tiff") -> None:
    """
    Upload single file to S3 with automatic multipart for large files
    Uses boto3's upload_file which handles multipart automatically for files > 8MB
    """
    file_size = os.path.getsize(local_path)
    logger.info(f"Uploading {local_path} ({file_size / (1024*1024):.2f} MB) to s3://{bucket}/{key}")

    # boto3's upload_file automatically uses multipart for files > 8MB
    # and handles retry logic
    s3_client.upload_file(
        local_path,
        bucket,
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=31536000"
        }
    )
    logger.info(f"Upload completed: s3://{bucket}/{key}")


def _s3_upload_dir(local_dir: str, bucket: str, prefix: str) -> int:
    """
    Upload directory to S3 recursively
    Returns: number of files uploaded
    """
    count = 0
    for root, _, files in os.walk(local_dir):
        for f in files:
            path = os.path.join(root, f)
            rel = os.path.relpath(path, local_dir).replace("\\", "/")
            s3_key = f"{prefix}/{rel}"

            # Determine content type
            content_type = "image/png"
            if f.endswith(".webp"):
                content_type = "image/webp"
            elif f.endswith(".json"):
                content_type = "application/json"

            s3_client.upload_file(
                path,
                bucket,
                s3_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "CacheControl": "public, max-age=31536000, immutable"
                }
            )
            count += 1

            if count % 100 == 0:
                logger.info(f"Uploaded {count} tiles...")

    return count


def _validate_tiff(path: str) -> dict:
    """
    Validate TIFF file can be opened and read basic metadata
    Returns: dict with validation info
    Raises: Exception if file is corrupted
    """
    logger.info(f"Validating TIFF file: {path}")

    try:
        with rasterio.open(path) as ds:
            info = {
                "width": ds.width,
                "height": ds.height,
                "count": ds.count,
                "dtype": str(ds.dtypes[0]) if ds.count > 0 else None,
                "crs": str(ds.crs) if ds.crs else None,
                "bounds": ds.bounds,
            }
            logger.info(f"TIFF validation passed: {info['width']}x{info['height']}, {info['count']} bands")
            return info
    except Exception as e:
        logger.error(f"TIFF validation failed: {e}")
        raise ValueError(f"Corrupted or invalid TIFF file: {e}")


def _to_cog(src_path: str, dst_path: str) -> None:
    """
    Convert TIFF to Cloud Optimized GeoTIFF using GDAL
    Uses DEFLATE compression for maximum compatibility
    """
    logger.info(f"Converting to COG: {src_path} -> {dst_path}")

    # Validate source file first
    _validate_tiff(src_path)

    cmd = [
        "gdal_translate",
        "-of", "GTiff",
        "-co", "TILED=YES",
        "-co", "COMPRESS=LZW",
        "-co", "BIGTIFF=YES",
        "-co", "BLOCKXSIZE=256",
        "-co", "BLOCKYSIZE=256",
        "-co", "COPY_SRC_OVERVIEWS=YES",
        "-co", "NUM_THREADS=ALL_CPUS",
        src_path,
        dst_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info("COG conversion completed")
    except subprocess.CalledProcessError as e:
        logger.error(f"gdal_translate failed: {e.stderr}")
        raise

    # Validate output COG
    try:
        _validate_tiff(dst_path)
    except Exception as e:
        raise ValueError(f"COG validation failed after conversion: {e}")

    # Build overviews
    logger.info("Building overviews...")
    cmd = [
        "gdaladdo",
        "-r", "average",
        "--config", "COMPRESS_OVERVIEW", "LZW",
        "--config", "BIGTIFF_OVERVIEW", "YES",
        "--config", "GDAL_NUM_THREADS", "ALL_CPUS",
        dst_path,
        "2", "4", "8", "16", "32", "64"
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info("Overviews built successfully")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to build overviews: {e.stderr}")
        # Non-fatal - continue without overviews


def _to_8bit_for_tiles(src_path: str, dst_path: str) -> None:
    """
    Convert raster to 8-bit for tile generation
    Uses auto-scaling to map the data range to 0-255

    gdal2tiles.py only works with 8-bit imagery, so we need to scale
    16-bit, 32-bit, or float data types to 8-bit for visualization.
    """
    logger.info(f"Scaling to 8-bit for tiles: {src_path} -> {dst_path}")

    # Check if already 8-bit
    with rasterio.open(src_path) as ds:
        dtype = str(ds.dtypes[0])
        logger.info(f"Source data type: {dtype}")

        if dtype in ['uint8', 'byte']:
            logger.info("Already 8-bit, copying file")
            import shutil
            shutil.copy2(src_path, dst_path)
            return

    # Scale to 8-bit
    cmd = [
        "gdal_translate",
        "-of", "GTiff",
        "-ot", "Byte",
        "-scale",  # Auto-scale to 0-255
        "-co", "TILED=YES",
        "-co", "COMPRESS=LZW",
        "-co", "BIGTIFF=YES",
        "-co", "NUM_THREADS=ALL_CPUS",
        src_path,
        dst_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info("8-bit scaling completed")
    except subprocess.CalledProcessError as e:
        logger.error(f"8-bit scaling failed: {e.stderr}")
        raise


def _xyz_with_gdal2tiles(cog_path: str, out_dir: str, min_zoom: int, max_zoom: int, file_type: str = "DEM") -> None:
    """
    Generate 256×256 XYZ tiles using gdal2tiles.py

    Note: gdal2tiles requires 8-bit imagery. The input cog_path should be
    an 8-bit file created by _to_8bit_for_tiles()
    """
    logger.info(f"Generating 256x256 tiles: zoom {min_zoom}-{max_zoom}, type={file_type}")

    # Use lanczos for imagery (sharper), average for DEMs (smoother)
    resampling = "lanczos" if file_type in ("ORTHOPHOTO", "HILLSHADE") else "average"

    cmd = [
        "gdal2tiles.py",
        "-z", f"{min_zoom}-{max_zoom}",
        "--tilesize=256",
        "--processes", "4",
        "--webviewer", "none",
        "--resampling", resampling,
        "--xyz",  # Use XYZ tile scheme
        cog_path,
        out_dir
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Tiles generated in {out_dir}")
    except subprocess.CalledProcessError as e:
        logger.error(f"gdal2tiles failed: {e.stderr}")
        if "8-bit" in e.stderr:
            raise ValueError("gdal2tiles requires 8-bit imagery. File needs to be scaled first.")
        raise


def _bounds_wgs84(path: str) -> tuple:
    """
    Calculate WGS84 bounds of raster
    Returns: (south, west, north, east)

    Handles complex/unknown CRS by attempting transformation
    and falling back to approximate bounds if transformation fails
    """
    # Validate file first
    try:
        _validate_tiff(path)
    except Exception as e:
        raise ValueError(f"Cannot calculate bounds - invalid TIFF file: {e}")

    with rasterio.open(path) as ds:
        b = ds.bounds

        # If already in WGS84, return as-is
        if ds.crs and ds.crs.to_epsg() == 4326:
            return b.bottom, b.left, b.top, b.right

        # Try to transform bounds to WGS84
        if ds.crs:
            try:
                # Try with the full CRS first
                w, s, e, n = transform_bounds(
                    ds.crs,
                    "EPSG:4326",
                    b.left, b.bottom, b.right, b.top,
                    densify_pts=21
                )
                logger.info(f"Successfully transformed bounds from {ds.crs} to EPSG:4326")
                return s, w, n, e
            except Exception as e:
                logger.warning(f"Failed to transform bounds with full CRS: {e}")

                # Try to extract just the horizontal CRS (ignore vertical datum)
                try:
                    # For compound CRS, try using just EPSG code if available
                    crs_string = str(ds.crs)
                    if "UTM zone 15N" in crs_string or "EPSG:26915" in crs_string:
                        # NAD83 UTM Zone 15N
                        from rasterio.crs import CRS
                        simple_crs = CRS.from_epsg(26915)
                        w, s, e, n = transform_bounds(
                            simple_crs,
                            "EPSG:4326",
                            b.left, b.bottom, b.right, b.top,
                            densify_pts=21
                        )
                        logger.info(f"Transformed bounds using simplified CRS (EPSG:26915)")
                        return s, w, n, e
                except Exception as e2:
                    logger.warning(f"Failed to transform with simplified CRS: {e2}")

        # Final fallback: Use native bounds (will be in native CRS, not WGS84)
        logger.warning(f"Could not transform bounds to WGS84. Using native bounds from {ds.crs}")
        return b.bottom, b.left, b.top, b.right


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.workers.tile_worker.generate_tiles_task",
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def generate_tiles_task(self, file_id: str, s3_bucket: str, s3_key: str, min_zoom: int = 12, max_zoom: int = 21):
    """
    Celery task for generating tiles from uploaded TIFF files

    Args:
        file_id: UUID of the TiffFile record
        s3_bucket: S3 bucket containing the source file
        s3_key: S3 key of the source TIFF file
        min_zoom: Minimum zoom level (default: 15)
        max_zoom: Maximum zoom level (default: 21)
    """
    db = self.db
    logger.info(f"Starting tile generation task for file {file_id}")

    # Update task status
    try:
        db_file = db.query(TiffFile).filter(TiffFile.id == file_id).first()
        if not db_file:
            logger.error(f"File {file_id} not found in database")
            return {"status": "error", "message": "File not found"}

        db_file.tile_status = "processing"
        db_file.tile_progress = 0
        db.commit()

        # Create temporary directory
        tmp = tempfile.mkdtemp(prefix=f"tiles_{file_id}_")
        logger.info(f"Working directory: {tmp}")

        try:
            local_src = os.path.join(tmp, "src.tif")
            local_cog = os.path.join(tmp, "cog.tif")
            local_8bit = os.path.join(tmp, "8bit.tif")
            tiles_dir = os.path.join(tmp, "tiles")

            # Step 1: Download from S3 (0-15%)
            logger.info(f"[1/6] Downloading from S3: {s3_bucket}/{s3_key}")
            db_file.tile_progress = 5
            db.commit()
            _s3_download(s3_bucket, s3_key, local_src)

            # Validate downloaded file immediately
            try:
                _validate_tiff(local_src)
                logger.info("Downloaded file validation passed")
            except Exception as e:
                raise ValueError(f"Downloaded file is corrupted or invalid: {e}")

            # Step 2: Convert to COG (15-30%)
            logger.info("[2/6] Converting to COG")
            db_file.tile_progress = 15
            db.commit()
            _to_cog(local_src, local_cog)

            # Step 3: Create 8-bit version for tiles (30-40%)
            logger.info("[3/6] Scaling to 8-bit for tile generation")
            db_file.tile_progress = 30
            db.commit()
            _to_8bit_for_tiles(local_cog, local_8bit)

            # Step 4: Calculate bounds (40-45%)
            logger.info("[4/6] Calculating bounds")
            db_file.tile_progress = 40
            db.commit()
            s, w, n, e = _bounds_wgs84(local_cog)
            logger.info(f"Bounds: S={s}, W={w}, N={n}, E={e}")

            # Step 5: Generate XYZ tiles (45-75%)
            logger.info("[5/6] Generating XYZ tiles")
            db_file.tile_progress = 45
            db.commit()
            os.makedirs(tiles_dir, exist_ok=True)
            _xyz_with_gdal2tiles(local_8bit, tiles_dir, min_zoom, max_zoom, db_file.file_type)

            # Step 6: Upload to S3 (75-100%)
            logger.info("[6/6] Uploading tiles to S3")
            db_file.tile_progress = 75
            db.commit()

            # Upload COG to tiles bucket
            user_id = str(db_file.user_id)
            cog_s3_key = f"cogs/{user_id}/{file_id}.tif"
            _s3_upload_file(local_cog, settings.S3_BUCKET_NAME, cog_s3_key, "image/tiff")
            logger.info(f"COG uploaded to s3://{settings.S3_BUCKET_NAME}/{cog_s3_key}")

            # Upload tiles
            tiles_prefix = f"tiles/{user_id}/{file_id}"
            tile_count = _s3_upload_dir(tiles_dir, settings.S3_BUCKET_NAME, tiles_prefix)
            logger.info(f"Uploaded {tile_count} tiles")

            # Build CloudFront tile URL template
            tile_url_template = f"https://{settings.AWS_CLOUDFRONT_DOMAIN}/{tiles_prefix}/{{z}}/{{x}}/{{y}}.png"

            # Update database with completion
            db_file.cog_s3_key = cog_s3_key
            db_file.tile_status = "completed"
            db_file.tile_progress = 100
            db_file.tile_min_zoom = min_zoom
            db_file.tile_max_zoom = max_zoom
            db_file.bounds_south = str(s)
            db_file.bounds_west = str(w)
            db_file.bounds_north = str(n)
            db_file.bounds_east = str(e)
            db_file.tile_url_template = tile_url_template
            db_file.tiles_generated_at = datetime.utcnow()
            db_file.tile_error = None
            db.commit()

            logger.info(f"Task completed successfully for file {file_id}")
            logger.info(f"Tile URL: {tile_url_template}")

            return {
                "status": "completed",
                "file_id": file_id,
                "tile_url_template": tile_url_template,
                "tile_count": tile_count,
                "bounds": {"south": s, "west": w, "north": n, "east": e}
            }

        except ValueError as e:
            # Validation errors (corrupted TIFF, etc.) - don't retry
            error_msg = f"File validation failed: {str(e)}"
            logger.error(error_msg)
            db_file.tile_status = "failed"
            db_file.tile_error = error_msg[:500]  # Limit error message length
            db_file.tile_progress = 0
            db.commit()
            # Don't retry - file is corrupted
            return {
                "status": "failed",
                "file_id": file_id,
                "error": error_msg
            }

        except subprocess.CalledProcessError as e:
            # GDAL command failed
            error_msg = f"Processing failed: {e.stderr[:500] if e.stderr else 'Unknown GDAL error'}"

            # Check if it's a corruption issue
            if any(keyword in error_msg.lower() for keyword in ['corrupt', 'invalid', 'sanity check', 'directory chaining']):
                logger.error(f"File corruption detected: {error_msg}")
                db_file.tile_status = "failed"
                db_file.tile_error = "File appears to be corrupted or invalid. Please re-upload."
                db_file.tile_progress = 0
                db.commit()
                # Don't retry corrupted files
                return {
                    "status": "failed",
                    "file_id": file_id,
                    "error": "File corrupted"
                }
            else:
                # Other GDAL errors - might be transient
                logger.error(error_msg)
                db_file.tile_status = "failed"
                db_file.tile_error = error_msg
                db.commit()
                raise  # Will retry

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)[:500]}"
            logger.error(error_msg)
            db_file.tile_status = "failed"
            db_file.tile_error = error_msg
            db.commit()
            raise  # Will retry

        finally:
            # Cleanup
            import shutil
            try:
                shutil.rmtree(tmp)
                logger.info(f"Cleaned up temp directory: {tmp}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup: {cleanup_error}")

    except Exception as e:
        logger.error(f"Task failed with exception: {e}")
        # Only retry if not already handled above
        if db_file and db_file.tile_status != "failed":
            raise self.retry(exc=e)
        # If already marked as failed, don't retry
        return {
            "status": "failed",
            "file_id": file_id,
            "error": str(e)
        }
