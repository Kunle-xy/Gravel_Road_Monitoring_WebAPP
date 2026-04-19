from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.models import User, RutAnalysisJob, TiffFile
from app.schemas import RutAnalysisCreate, RutAnalysisResponse, RutAnalysisStatusResponse
from app.auth import get_current_active_user
from app.config import settings
from app.workers.rut_worker import analyze_ruts_task

router = APIRouter(prefix="/rut", tags=["Rut Analysis"])


@router.post("", response_model=RutAnalysisResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RutAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_rut_analysis(
    analysis_request: RutAnalysisCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new rut analysis job.
    The analysis will run asynchronously in a Celery worker.
    """
    # Verify TIFF file exists and belongs to user
    tiff_file = db.query(TiffFile).filter(
        TiffFile.id == analysis_request.tiff_file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not tiff_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TIFF file not found or access denied"
        )

    # Check if TIFF has tiles generated (optional, but recommended)
    if tiff_file.tile_status != "completed":
        # You can either raise an error or allow it
        # For now, we'll allow it since we're reading from the original TIFF
        pass

    # Create analysis job
    job = RutAnalysisJob(
        user_id=current_user.id,
        tiff_file_id=analysis_request.tiff_file_id,
        polygon_geojson=analysis_request.polygon_geojson,
        dy_freq=analysis_request.dy_freq,
        dx=analysis_request.dx,
        apply_smoothing=analysis_request.apply_smoothing,
        gaussian_sigma=analysis_request.gaussian_sigma,
        neighbor_eval=analysis_request.neighbor_eval,
        neighbor_range=analysis_request.neighbor_range,
        status="pending",
        progress=0
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # Start Celery task with optional screenshot
    task = analyze_ruts_task.delay(str(job.id))

    # Update job with Celery task ID
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)

    return job


# Specific routes must come BEFORE parametrized routes to avoid conflicts
@router.get("/completed", response_model=List[RutAnalysisResponse])
async def get_completed_analyses(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all completed rut analysis jobs for the current user.
    """
    jobs = db.query(RutAnalysisJob).filter(
        RutAnalysisJob.user_id == current_user.id,
        RutAnalysisJob.status == "completed"
    ).order_by(RutAnalysisJob.completed_at.desc()).all()

    return jobs


@router.get("/file/{tiff_file_id}", response_model=List[RutAnalysisResponse])
async def get_analyses_for_file(
    tiff_file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all rut analysis jobs for a specific TIFF file.
    """
    # Verify file belongs to user
    tiff_file = db.query(TiffFile).filter(
        TiffFile.id == tiff_file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not tiff_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TIFF file not found or access denied"
        )

    jobs = db.query(RutAnalysisJob).filter(
        RutAnalysisJob.tiff_file_id == tiff_file_id,
        RutAnalysisJob.user_id == current_user.id
    ).order_by(RutAnalysisJob.created_at.desc()).all()

    return jobs


# Parametrized routes come after specific routes
@router.get("/{job_id}", response_model=RutAnalysisResponse)
async def get_rut_analysis(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get rut analysis job details and results.
    """
    job = db.query(RutAnalysisJob).filter(
        RutAnalysisJob.id == job_id,
        RutAnalysisJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rut analysis job not found"
        )

    return job


@router.get("/{job_id}/status", response_model=RutAnalysisStatusResponse)
async def get_rut_analysis_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get rut analysis job status (lighter response for polling).
    """
    job = db.query(RutAnalysisJob).filter(
        RutAnalysisJob.id == job_id,
        RutAnalysisJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rut analysis job not found"
        )

    return RutAnalysisStatusResponse(
        id=job.id,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        html_plot_url=job.html_plot_url,
        features_geojson_url=job.features_geojson_url,
        total_ruts_detected=job.total_ruts_detected,
        low_severity_count=job.low_severity_count,
        medium_severity_count=job.medium_severity_count,
        high_severity_count=job.high_severity_count,
        total_area_sqft=job.total_area_sqft
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rut_analysis(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a rut analysis job.
    """
    job = db.query(RutAnalysisJob).filter(
        RutAnalysisJob.id == job_id,
        RutAnalysisJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rut analysis job not found"
        )

    # Delete S3 artifacts
    import boto3, logging
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    for key in [job.html_plot_s3_key, job.features_geojson_s3_key]:
        if key:
            try:
                s3.delete_object(Bucket=settings.S3_BUCKET_RAW, Key=key)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to delete S3 object {key}: {e}")

    db.delete(job)
    db.commit()

    return None
