from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.models import User, CorrugationAnalysisJob, TiffFile
from app.schemas import CorrugationAnalysisCreate, CorrugationAnalysisResponse, CorrugationAnalysisStatusResponse
from app.auth import get_current_active_user
from app.workers.corrugation import analyze_corrugation_task

router = APIRouter(prefix="/corrugation", tags=["Corrugation Analysis"])


@router.post("", response_model=CorrugationAnalysisResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CorrugationAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_corrugation_analysis(
    req: CorrugationAnalysisCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new corrugation analysis job."""
    tiff_file = db.query(TiffFile).filter(
        TiffFile.id == req.tiff_file_id, TiffFile.user_id == current_user.id
    ).first()
    if not tiff_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TIFF file not found")

    job = CorrugationAnalysisJob(
        user_id=current_user.id,
        tiff_file_id=req.tiff_file_id,
        polygon_geojson=req.polygon_geojson,
        line_interval=req.line_interval,
        dy_freq=req.dy_freq,
        sigma_samples=req.sigma_samples,
        neighbor_eval=req.neighbor_eval,
        neighbor_range=req.neighbor_range,
        status="pending", progress=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task = analyze_corrugation_task.delay(str(job.id), req.screenshot_base64)
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)
    return job


@router.get("/completed", response_model=List[CorrugationAnalysisResponse])
async def get_completed(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return db.query(CorrugationAnalysisJob).filter(
        CorrugationAnalysisJob.user_id == current_user.id,
        CorrugationAnalysisJob.status == "completed"
    ).order_by(CorrugationAnalysisJob.completed_at.desc()).all()


@router.get("/file/{tiff_file_id}", response_model=List[CorrugationAnalysisResponse])
async def get_for_file(tiff_file_id: uuid.UUID, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    tiff = db.query(TiffFile).filter(TiffFile.id == tiff_file_id, TiffFile.user_id == current_user.id).first()
    if not tiff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TIFF file not found")
    return db.query(CorrugationAnalysisJob).filter(
        CorrugationAnalysisJob.tiff_file_id == tiff_file_id,
        CorrugationAnalysisJob.user_id == current_user.id
    ).order_by(CorrugationAnalysisJob.created_at.desc()).all()


@router.get("/{job_id}", response_model=CorrugationAnalysisResponse)
async def get_job(job_id: uuid.UUID, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    job = db.query(CorrugationAnalysisJob).filter(
        CorrugationAnalysisJob.id == job_id, CorrugationAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/{job_id}/status", response_model=CorrugationAnalysisStatusResponse)
async def get_status(job_id: uuid.UUID, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    job = db.query(CorrugationAnalysisJob).filter(
        CorrugationAnalysisJob.id == job_id, CorrugationAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return CorrugationAnalysisStatusResponse(
        id=job.id, status=job.status, progress=job.progress,
        error_message=job.error_message, html_report_url=job.html_report_url,
        low_area_ft2=job.low_area_ft2, medium_area_ft2=job.medium_area_ft2,
        high_area_ft2=job.high_area_ft2, total_area_ft2=job.total_area_ft2,
        low_count=job.low_count, medium_count=job.medium_count, high_count=job.high_count
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: uuid.UUID, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    job = db.query(CorrugationAnalysisJob).filter(
        CorrugationAnalysisJob.id == job_id, CorrugationAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    db.delete(job)
    db.commit()
