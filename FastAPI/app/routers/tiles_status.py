"""
Tile Generation Status and Management Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db
from app.models import User, TiffFile
from app.auth import get_current_active_user
from app.workers.tile_worker import generate_tiles_task
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tiles-status", tags=["Tile Status"])


@router.get("/{file_id}")
async def get_tile_generation_status(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the tile generation status for a specific file

    Status values:
    - pending: Not started
    - queued: Job submitted but not started
    - processing: Currently generating tiles
    - completed: Tiles generated successfully
    - failed: Tile generation failed
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

    # Check Celery task status if available
    celery_task_status: Optional[dict] = None
    try:
        task_id = f"tile_{file_id}"
        task_result = celery_app.AsyncResult(task_id)
        if task_result:
            celery_task_status = {
                "task_id": task_id,
                "state": task_result.state,
                "info": task_result.info if task_result.info else None
            }
    except Exception as e:
        logger.warning(f"Failed to get Celery task status: {e}")

    return {
        "file_id": str(file.id),
        "filename": file.filename,
        "tile_status": file.tile_status or "pending",
        "tile_progress": file.tile_progress or 0,
        "tile_url_template": file.tile_url_template,
        "tile_error": file.tile_error,
        "tiles_generated_at": file.tiles_generated_at,
        "min_zoom": file.tile_min_zoom,
        "max_zoom": file.tile_max_zoom,
        "celery_task": celery_task_status
    }


@router.post("/{file_id}/retry")
async def retry_tile_generation(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retry tile generation for a failed or pending file
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

    # Check if COG exists
    if not file.cog_s3_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="COG file not available. Cannot generate tiles."
        )

    # Check current status
    if file.tile_status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tile generation is already in progress"
        )

    if file.tile_status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tiles already generated. Delete and re-upload to regenerate."
        )

    try:
        # Submit Celery tile generation task
        task = generate_tiles_task.apply_async(
            args=[
                str(file.id),
                file.s3_bucket,
                file.cog_s3_key,
                15,  # min_zoom
                21   # max_zoom
            ],
            task_id=f"tile_{file.id}"
        )

        # Update status
        file.tile_status = "queued"
        file.tile_progress = 0
        file.tile_error = None
        db.commit()

        logger.info(f"Celery task {task.id} submitted for retry on file {file.id}")

        return {
            "message": "Tile generation task submitted",
            "file_id": str(file.id),
            "task_id": task.id,
            "tile_status": "queued"
        }

    except Exception as e:
        logger.error(f"Failed to submit Celery task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}"
        )


@router.get("/")
async def get_all_tile_statuses(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get tile generation status for all user's files
    """
    files = db.query(TiffFile).filter(
        TiffFile.user_id == current_user.id
    ).order_by(TiffFile.created_at.desc()).all()

    return {
        "total": len(files),
        "statuses": [
            {
                "file_id": str(f.id),
                "filename": f.filename,
                "file_type": f.file_type,
                "tile_status": f.tile_status or "pending",
                "tile_progress": f.tile_progress or 0,
                "tile_error": f.tile_error,
                "tiles_generated_at": f.tiles_generated_at
            }
            for f in files
        ],
        "summary": {
            "pending": sum(1 for f in files if (f.tile_status or "pending") == "pending"),
            "queued": sum(1 for f in files if f.tile_status == "queued"),
            "processing": sum(1 for f in files if f.tile_status == "processing"),
            "completed": sum(1 for f in files if f.tile_status == "completed"),
            "failed": sum(1 for f in files if f.tile_status == "failed")
        }
    }
