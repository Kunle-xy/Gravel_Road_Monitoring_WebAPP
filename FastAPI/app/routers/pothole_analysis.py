"""Pothole analysis API — 3D surface plot, depth/width measurement, severity classification."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.config import settings
from app.models import User, TiffFile, PotholeAnalysisJob
from app.schemas import PotholeAnalysisCreate, PotholeAnalysisResponse, PotholeAnalysisStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pothole", tags=["Pothole Analysis"])


@router.get("/completed", response_model=list[PotholeAnalysisResponse])
def get_completed_pothole_analyses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all completed pothole analysis jobs for the current user."""
    return db.query(PotholeAnalysisJob).filter(
        PotholeAnalysisJob.user_id == current_user.id,
        PotholeAnalysisJob.status == "completed",
    ).order_by(PotholeAnalysisJob.completed_at.desc()).all()


@router.post("", response_model=PotholeAnalysisResponse, status_code=201)
@router.post("/", response_model=PotholeAnalysisResponse, status_code=201)
def create_pothole_analysis(
    body: PotholeAnalysisCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tiff = db.query(TiffFile).filter(
        TiffFile.id == body.tiff_file_id, TiffFile.user_id == current_user.id
    ).first()
    if not tiff:
        raise HTTPException(status_code=404, detail="DEM file not found")

    job = PotholeAnalysisJob(
        user_id=current_user.id,
        tiff_file_id=body.tiff_file_id,
        polygon_geojson=body.polygon_geojson,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.workers.pothole.task import analyze_pothole_task
    task = analyze_pothole_task.apply_async(args=[str(job.id)], task_id=f"pothole_{job.id}")
    job.celery_task_id = task.id
    job.status = "queued"
    db.commit()

    return job


@router.get("/{job_id}/status", response_model=PotholeAnalysisStatusResponse)
def get_pothole_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(PotholeAnalysisJob).filter(
        PotholeAnalysisJob.id == job_id, PotholeAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}", response_model=PotholeAnalysisResponse)
def get_pothole_result(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(PotholeAnalysisJob).filter(
        PotholeAnalysisJob.id == job_id, PotholeAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
def delete_pothole_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(PotholeAnalysisJob).filter(
        PotholeAnalysisJob.id == job_id, PotholeAnalysisJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
