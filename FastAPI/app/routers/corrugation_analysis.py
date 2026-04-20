from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
import logging
import os
import uuid

import numpy as np
import rasterio

from app.database import get_db
from app.models import User, CorrugationAnalysisJob, TiffFile
from app.schemas import CorrugationAnalysisCreate, CorrugationAnalysisResponse, CorrugationAnalysisStatusResponse
from app.auth import get_current_active_user
from app.workers.corrugation import analyze_corrugation_task
from app.config import settings

router = APIRouter(prefix="/corrugation", tags=["Corrugation Analysis"])
logger = logging.getLogger(__name__)


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
        min_drop_in=req.min_drop_in,
        min_wavelength_m=req.min_wavelength_m,
        max_wavelength_m=req.max_wavelength_m,
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


@router.get("/auto-defaults")
async def auto_defaults(
    tiff_file_id: uuid.UUID,
    dy_freq: int = Query(20, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Compute sensible wavelength bounds for a given DEM + sampling frequency.

    min_wavelength_m = max(0.15, 10 * dx)   where dx = 100 * pix_m / dy_freq
    max_wavelength_m = 0.6                  (physical gravel-road washboard ceiling)
    """
    tiff = db.query(TiffFile).filter(
        TiffFile.id == tiff_file_id, TiffFile.user_id == current_user.id
    ).first()
    if not tiff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TIFF file not found")

    os.environ['AWS_ACCESS_KEY_ID'] = settings.AWS_ACCESS_KEY_ID
    os.environ['AWS_SECRET_ACCESS_KEY'] = settings.AWS_SECRET_ACCESS_KEY
    os.environ['AWS_REGION'] = settings.AWS_REGION

    s3_key = tiff.s3_key if tiff.file_type == "DEM" else (tiff.cog_s3_key or tiff.s3_key)
    s3_url = f"s3://{tiff.s3_bucket}/{s3_key}"

    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
                          CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif,.tiff'):
            with rasterio.open(s3_url) as src:
                pix_m = float(np.mean(np.abs(src.res)))
    except Exception as e:
        logger.warning(f"auto-defaults: failed to read {s3_url}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Unable to read DEM metadata")

    dx = (100.0 * pix_m) / float(dy_freq)
    min_wavelength_m = max(0.15, 10.0 * dx)
    max_wavelength_m = 0.6
    return {
        "pix_m": pix_m,
        "dx": dx,
        "min_wavelength_m": round(min_wavelength_m, 4),
        "max_wavelength_m": round(max_wavelength_m, 4),
    }


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
        features_geojson_url=job.features_geojson_url,
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
    import boto3, logging
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    for key in [job.html_report_s3_key, job.features_geojson_s3_key]:
        if key:
            try:
                s3.delete_object(Bucket=settings.S3_BUCKET_RAW, Key=key)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to delete S3 object {key}: {e}")
    db.delete(job)
    db.commit()
