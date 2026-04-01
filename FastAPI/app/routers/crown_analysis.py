from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.models import User, CrownAnalysisJob, TiffFile
from app.schemas import CrownAnalysisCreate, CrownAnalysisResponse, CrownAnalysisStatusResponse
from app.auth import get_current_active_user
from app.workers.crown import analyze_crown_task
from app.config import settings

router = APIRouter(prefix="/crown", tags=["Crown Analysis"])


@router.post("", response_model=CrownAnalysisResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CrownAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_crown_analysis(
    analysis_request: CrownAnalysisCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new crown distress analysis job."""
    tiff_file = db.query(TiffFile).filter(
        TiffFile.id == analysis_request.tiff_file_id,
        TiffFile.user_id == current_user.id
    ).first()

    if not tiff_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TIFF file not found or access denied"
        )

    job = CrownAnalysisJob(
        user_id=current_user.id,
        tiff_file_id=analysis_request.tiff_file_id,
        polygon_geojson=analysis_request.polygon_geojson,
        spacing_m=analysis_request.spacing_m,
        dy_freq=analysis_request.dy_freq,
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

    task = analyze_crown_task.delay(str(job.id), analysis_request.screenshot_base64)
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)

    return job


@router.get("/completed", response_model=List[CrownAnalysisResponse])
async def get_completed_analyses(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all completed crown analysis jobs for the current user."""
    jobs = db.query(CrownAnalysisJob).filter(
        CrownAnalysisJob.user_id == current_user.id,
        CrownAnalysisJob.status == "completed"
    ).order_by(CrownAnalysisJob.completed_at.desc()).all()
    return jobs


@router.get("/file/{tiff_file_id}", response_model=List[CrownAnalysisResponse])
async def get_analyses_for_file(
    tiff_file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all crown analysis jobs for a specific TIFF file."""
    tiff_file = db.query(TiffFile).filter(
        TiffFile.id == tiff_file_id,
        TiffFile.user_id == current_user.id
    ).first()
    if not tiff_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TIFF file not found")

    jobs = db.query(CrownAnalysisJob).filter(
        CrownAnalysisJob.tiff_file_id == tiff_file_id,
        CrownAnalysisJob.user_id == current_user.id
    ).order_by(CrownAnalysisJob.created_at.desc()).all()
    return jobs


@router.get("/{job_id}", response_model=CrownAnalysisResponse)
async def get_crown_analysis(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get crown analysis job details and results."""
    job = db.query(CrownAnalysisJob).filter(
        CrownAnalysisJob.id == job_id,
        CrownAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crown analysis job not found")
    return job


@router.get("/{job_id}/status", response_model=CrownAnalysisStatusResponse)
async def get_crown_analysis_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get crown analysis job status (lightweight response for polling)."""
    job = db.query(CrownAnalysisJob).filter(
        CrownAnalysisJob.id == job_id,
        CrownAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crown analysis job not found")

    return CrownAnalysisStatusResponse(
        id=job.id,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        html_report_url=job.html_report_url,
        low_severity_ft=job.low_severity_ft,
        medium_severity_ft=job.medium_severity_ft,
        high_severity_ft=job.high_severity_ft,
        total_linear_ft=job.total_linear_ft,
        low_count=job.low_count,
        medium_count=job.medium_count,
        high_count=job.high_count
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_crown_analysis(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a crown analysis job."""
    job = db.query(CrownAnalysisJob).filter(
        CrownAnalysisJob.id == job_id,
        CrownAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crown analysis job not found")
    import boto3, logging
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    for key in [job.html_report_s3_key]:
        if key:
            try:
                s3.delete_object(Bucket=settings.S3_BUCKET_RAW, Key=key)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to delete S3 object {key}: {e}")
    db.delete(job)
    db.commit()
    return None
