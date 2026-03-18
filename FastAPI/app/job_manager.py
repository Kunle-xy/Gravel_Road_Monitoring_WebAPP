"""
Background Job Manager for Tile Generation

Uses ThreadPoolExecutor for asynchronous tile generation.
Can be upgraded to Celery for distributed processing later.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import TiffFile
from app.tile_generator import TileGenerator, TileGenerationError
import boto3
from app.config import settings

logger = logging.getLogger(__name__)

# Global thread pool executor
# max_workers=2 means 2 concurrent tile generation jobs
# Adjust based on server CPU/memory capacity
_executor: Optional[ThreadPoolExecutor] = None


def get_executor() -> ThreadPoolExecutor:
    """Get or create the global thread pool executor"""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="tile_worker"
        )
        logger.info("ThreadPoolExecutor created with 2 workers")
    return _executor


def shutdown_executor():
    """Shutdown the executor gracefully"""
    global _executor
    if _executor:
        _executor.shutdown(wait=True)
        _executor = None
        logger.info("ThreadPoolExecutor shutdown")


class TileGenerationJob:
    """Represents a tile generation job"""

    def __init__(self, file_id: str, s3_key: str):
        self.file_id = file_id
        self.s3_key = s3_key
        self.db: Optional[Session] = None

    def update_progress(self, progress: int, status: str = "processing"):
        """Update job progress in database"""
        if self.db:
            try:
                db_file = self.db.query(TiffFile).filter(
                    TiffFile.id == self.file_id
                ).first()

                if db_file:
                    db_file.tile_progress = progress
                    db_file.tile_status = status
                    self.db.commit()
                    logger.info(f"Job {self.file_id}: {status} - {progress}%")

            except Exception as e:
                logger.error(f"Failed to update progress: {e}")
                self.db.rollback()

    def run(self):
        """
        Execute the tile generation job

        This runs in a background thread
        """
        self.db = SessionLocal()

        try:
            logger.info(f"Starting tile generation job for file {self.file_id}")

            # Update status to processing
            self.update_progress(0, "processing")

            # Initialize S3 client
            s3_client = boto3.client('s3', region_name=settings.AWS_REGION)

            # Initialize tile generator
            tile_generator = TileGenerator(
                s3_client=s3_client,
                bucket_name=settings.S3_BUCKET_NAME,
                base_tile_path="tiles"
            )

            # Generate and upload tiles
            tile_url_template, metadata = tile_generator.generate_and_upload(
                s3_key=self.s3_key,
                file_id=self.file_id,
                min_zoom=15,
                max_zoom=21,
                progress_callback=lambda p: self.update_progress(p, "processing")
            )

            # Update database with completion
            db_file = self.db.query(TiffFile).filter(
                TiffFile.id == self.file_id
            ).first()

            if db_file:
                db_file.tile_status = "completed"
                db_file.tile_progress = 100
                db_file.tile_url_template = tile_url_template
                db_file.tile_min_zoom = metadata["min_zoom"]
                db_file.tile_max_zoom = metadata["max_zoom"]
                db_file.tiles_generated_at = datetime.utcnow()
                db_file.tile_error = None
                self.db.commit()

                logger.info(f"Job {self.file_id} completed successfully")
                logger.info(f"Tile URL: {tile_url_template}")
                logger.info(f"Tile count: {metadata['tile_count']}")

        except TileGenerationError as e:
            logger.error(f"Job {self.file_id} failed: {e}")
            self.update_progress(0, "failed")

            # Store error in database
            try:
                db_file = self.db.query(TiffFile).filter(
                    TiffFile.id == self.file_id
                ).first()

                if db_file:
                    db_file.tile_error = str(e)
                    self.db.commit()

            except Exception as db_error:
                logger.error(f"Failed to store error: {db_error}")

        except Exception as e:
            logger.error(f"Job {self.file_id} failed with unexpected error: {e}")
            self.update_progress(0, "failed")

            # Store error in database
            try:
                db_file = self.db.query(TiffFile).filter(
                    TiffFile.id == self.file_id
                ).first()

                if db_file:
                    db_file.tile_error = f"Unexpected error: {str(e)}"
                    self.db.commit()

            except Exception as db_error:
                logger.error(f"Failed to store error: {db_error}")

        finally:
            if self.db:
                self.db.close()


def submit_tile_generation_job(file_id: str, s3_key: str) -> None:
    """
    Submit a tile generation job to the thread pool

    Args:
        file_id: UUID of the file record
        s3_key: S3 key of the source TIFF file
    """
    executor = get_executor()
    job = TileGenerationJob(file_id, s3_key)

    # Submit to thread pool
    future = executor.submit(job.run)

    logger.info(f"Tile generation job submitted for file {file_id}")

    # Optional: Add callback for completion
    def on_complete(future):
        try:
            future.result()  # This will raise exception if job failed
        except Exception as e:
            logger.error(f"Job failed with exception: {e}")

    future.add_done_callback(on_complete)
