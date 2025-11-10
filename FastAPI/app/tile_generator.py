"""
Tile Generation Pipeline for Static XYZ Tiles

This module handles the complete pipeline:
1. Download TIFF from S3 to /tmp
2. Convert to COG (Cloud Optimized GeoTIFF)
3. Generate XYZ tile pyramid using gdal2tiles
4. Upload tiles to S3 with caching headers
"""

import os
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Tuple, Optional
import boto3
from botocore.exceptions import ClientError
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TileGenerationError(Exception):
    """Custom exception for tile generation errors"""
    pass


class TileGenerator:
    """Handles the complete tile generation pipeline"""

    def __init__(self,
                 s3_client,
                 bucket_name: str,
                 base_tile_path: str = "tiles"):
        """
        Initialize the tile generator

        Args:
            s3_client: Boto3 S3 client instance
            bucket_name: S3 bucket name
            base_tile_path: Base path for tiles in S3 (default: "tiles")
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.base_tile_path = base_tile_path

    def download_from_s3(self, s3_key: str, local_path: str) -> None:
        """Download file from S3 to local path"""
        try:
            logger.info(f"Downloading {s3_key} from S3...")
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"Downloaded to {local_path}")
        except ClientError as e:
            raise TileGenerationError(f"Failed to download from S3: {e}")

    def convert_to_cog(self, input_path: str, output_path: str) -> None:
        """
        Convert TIFF to Cloud Optimized GeoTIFF using GDAL

        Uses gdal_translate with optimal settings:
        - TILED=YES: Enable tiling
        - COMPRESS=WEBP: Use WebP compression (smaller than JPEG, better quality)
        - BLOCKSIZE=512: 512x512 pixel tiles
        - QUALITY=85: WebP quality
        - COPY_SRC_OVERVIEWS=YES: Preserve existing overviews
        """
        try:
            logger.info(f"Converting to COG: {input_path} -> {output_path}")

            cmd = [
                "gdal_translate",
                "-of", "GTiff",
                "-co", "TILED=YES",
                "-co", "COMPRESS=WEBP",
                "-co", "BLOCKXSIZE=512",
                "-co", "BLOCKYSIZE=512",
                "-co", "QUALITY=85",
                "-co", "COPY_SRC_OVERVIEWS=YES",
                input_path,
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("COG conversion completed")

            # Build overviews (pyramids) for faster rendering at lower zoom levels
            self.build_overviews(output_path)

        except subprocess.CalledProcessError as e:
            raise TileGenerationError(f"COG conversion failed: {e.stderr}")
        except FileNotFoundError:
            raise TileGenerationError(
                "gdal_translate not found. Please install GDAL: "
                "apt-get install gdal-bin python3-gdal"
            )

    def build_overviews(self, cog_path: str) -> None:
        """
        Build internal overviews using gdaladdo

        Creates pyramid levels: 2, 4, 8, 16, 32, 64
        """
        try:
            logger.info(f"Building overviews for {cog_path}")

            cmd = [
                "gdaladdo",
                "-r", "average",  # Resampling method
                "--config", "COMPRESS_OVERVIEW", "WEBP",
                "--config", "QUALITY_OVERVIEW", "85",
                cog_path,
                "2", "4", "8", "16", "32", "64"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Overviews built successfully")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to build overviews: {e.stderr}")
            # Non-fatal - continue without overviews

    def generate_tiles(self,
                      cog_path: str,
                      output_dir: str,
                      min_zoom: int = 15,
                      max_zoom: int = 21) -> None:
        """
        Generate XYZ tile pyramid using gdal2tiles.py

        Args:
            cog_path: Path to input COG file
            output_dir: Directory to output tiles
            min_zoom: Minimum zoom level (default: 15)
            max_zoom: Maximum zoom level (default: 21)
        """
        try:
            logger.info(f"Generating tiles from {cog_path}")
            logger.info(f"Zoom range: {min_zoom}-{max_zoom}")

            cmd = [
                "gdal2tiles.py",
                "--zoom", f"{min_zoom}-{max_zoom}",
                "--processes", "4",  # Parallel processing
                "--webviewer", "none",  # Don't generate HTML viewer
                "--resampling", "average",
                "--xyz",  # Use XYZ tile scheme (not TMS)
                cog_path,
                output_dir
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Tile generation completed")
            logger.info(f"Tiles saved to {output_dir}")

        except subprocess.CalledProcessError as e:
            raise TileGenerationError(f"Tile generation failed: {e.stderr}")
        except FileNotFoundError:
            raise TileGenerationError(
                "gdal2tiles.py not found. Please install GDAL: "
                "apt-get install gdal-bin python3-gdal"
            )

    def upload_tiles_to_s3(self,
                          tiles_dir: str,
                          file_id: str,
                          progress_callback: Optional[callable] = None) -> str:
        """
        Upload all generated tiles to S3 with optimal caching headers

        Args:
            tiles_dir: Local directory containing tiles
            file_id: Unique file identifier (UUID)
            progress_callback: Optional callback function for progress updates

        Returns:
            Tile URL template string
        """
        try:
            logger.info(f"Uploading tiles to S3 for file {file_id}")

            # Find all tile files (PNG by default from gdal2tiles)
            tile_files = list(Path(tiles_dir).rglob("*.png"))
            total_files = len(tile_files)

            if total_files == 0:
                raise TileGenerationError("No tiles found to upload")

            logger.info(f"Found {total_files} tiles to upload")

            uploaded = 0
            for tile_path in tile_files:
                # Calculate S3 key: tiles/{file_id}/{z}/{x}/{y}.png
                rel_path = tile_path.relative_to(tiles_dir)
                s3_key = f"{self.base_tile_path}/{file_id}/{rel_path}"

                # Upload with caching headers
                self.s3_client.upload_file(
                    str(tile_path),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        'ContentType': 'image/png',
                        'CacheControl': 'public, max-age=31536000, immutable',
                        'ACL': 'public-read'  # Make tiles publicly accessible
                    }
                )

                uploaded += 1

                # Update progress
                if progress_callback:
                    progress = int((uploaded / total_files) * 100)
                    progress_callback(progress)

                # Log progress every 100 tiles
                if uploaded % 100 == 0:
                    logger.info(f"Uploaded {uploaded}/{total_files} tiles")

            logger.info(f"Successfully uploaded {uploaded} tiles")

            # Return tile URL template
            # Note: Replace with your actual S3/CDN URL
            tile_url_template = (
                f"https://{self.bucket_name}.s3.amazonaws.com/"
                f"{self.base_tile_path}/{file_id}/{{z}}/{{x}}/{{y}}.png"
            )

            return tile_url_template

        except ClientError as e:
            raise TileGenerationError(f"S3 upload failed: {e}")

    def generate_and_upload(self,
                           s3_key: str,
                           file_id: str,
                           min_zoom: int = 15,
                           max_zoom: int = 21,
                           progress_callback: Optional[callable] = None) -> Tuple[str, dict]:
        """
        Complete pipeline: download -> COG -> tiles -> upload

        Args:
            s3_key: S3 key of the source TIFF file
            file_id: Unique file identifier
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            progress_callback: Optional progress callback

        Returns:
            Tuple of (tile_url_template, metadata)
        """
        # Create temporary directories
        temp_dir = tempfile.mkdtemp(prefix=f"tiles_{file_id}_")

        try:
            # Paths
            input_tiff = os.path.join(temp_dir, "input.tif")
            cog_tiff = os.path.join(temp_dir, "cog.tif")
            tiles_dir = os.path.join(temp_dir, "tiles")

            # Step 1: Download from S3
            logger.info("[1/4] Downloading from S3...")
            if progress_callback:
                progress_callback(10)
            self.download_from_s3(s3_key, input_tiff)

            # Step 2: Convert to COG
            logger.info("[2/4] Converting to COG...")
            if progress_callback:
                progress_callback(25)
            self.convert_to_cog(input_tiff, cog_tiff)

            # Step 3: Generate tiles
            logger.info("[3/4] Generating tile pyramid...")
            if progress_callback:
                progress_callback(40)
            self.generate_tiles(cog_tiff, tiles_dir, min_zoom, max_zoom)

            # Step 4: Upload to S3
            logger.info("[4/4] Uploading tiles to S3...")
            if progress_callback:
                progress_callback(50)

            def upload_progress(progress):
                # Map 0-100 to 50-100
                adjusted = 50 + (progress // 2)
                if progress_callback:
                    progress_callback(adjusted)

            tile_url_template = self.upload_tiles_to_s3(
                tiles_dir,
                file_id,
                progress_callback=upload_progress
            )

            # Metadata
            metadata = {
                "min_zoom": min_zoom,
                "max_zoom": max_zoom,
                "tile_count": len(list(Path(tiles_dir).rglob("*.png"))),
                "generated_at": datetime.utcnow().isoformat()
            }

            if progress_callback:
                progress_callback(100)

            logger.info("Tile generation pipeline completed successfully")
            return tile_url_template, metadata

        except Exception as e:
            logger.error(f"Tile generation failed: {e}")
            raise TileGenerationError(f"Pipeline failed: {e}")

        finally:
            # Cleanup temporary files
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
