"""
Dust analysis API — video upload, first frame extraction,
analysis submission, WebSocket for real-time results.
"""

import uuid
import json
import tempfile
import os
import logging
import asyncio
from io import BytesIO

import boto3
import cv2 as cv
import redis

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.config import settings
from app.models import User, VideoFile, DustAnalysisJob
from app.schemas import (
    VideoPresignRequest, VideoPresignResponse, VideoFileResponse,
    DustAnalysisCreate, DustAnalysisResponse, DustAnalysisStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dust", tags=["Dust Analysis"])

s3_client = boto3.client("s3", region_name=settings.AWS_REGION)


# --- Video Upload ---

@router.post("/video/presign", response_model=VideoPresignResponse)
def presign_video_upload(
    body: VideoPresignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a presigned URL to upload a video to S3."""
    if not body.filename.lower().endswith((".mp4", ".avi", ".mov")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only video files (.mp4, .avi, .mov) are allowed",
        )

    unique_id = uuid.uuid4().hex[:8]
    s3_key = f"videos/{current_user.id}/{unique_id}/{body.filename}"

    presigned_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_RAW,
            "Key": s3_key,
            "ContentType": body.content_type,
        },
        ExpiresIn=3600,
    )

    db_video = VideoFile(
        user_id=current_user.id,
        filename=body.filename,
        original_size_bytes=body.file_size,
        s3_bucket=settings.S3_BUCKET_RAW,
        s3_key=s3_key,
        upload_status="pending",
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)

    return VideoPresignResponse(
        presigned_url=presigned_url,
        s3_key=s3_key,
        video_id=db_video.id,
    )


@router.post("/video/{video_id}/complete", response_model=VideoFileResponse)
def complete_video_upload(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark video upload as complete and extract metadata."""
    video = db.query(VideoFile).filter(
        VideoFile.id == video_id,
        VideoFile.user_id == current_user.id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Download just enough to get metadata
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        s3_client.download_file(video.s3_bucket, video.s3_key, tmp.name)
        cap = cv.VideoCapture(tmp.name)
        if cap.isOpened():
            video.total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
            video.fps = cap.get(cv.CAP_PROP_FPS)
            video.width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
            video.height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
            if video.fps and video.fps > 0:
                video.duration_seconds = video.total_frames / video.fps
            cap.release()
    finally:
        os.unlink(tmp.name)

    video.upload_status = "completed"
    db.commit()
    db.refresh(video)
    return video


@router.get("/video/{video_id}/first-frame")
def get_first_frame(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract and return the first frame of the video as JPEG."""
    video = db.query(VideoFile).filter(
        VideoFile.id == video_id,
        VideoFile.user_id == current_user.id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        s3_client.download_file(video.s3_bucket, video.s3_key, tmp.name)
        cap = cv.VideoCapture(tmp.name)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=500, detail="Could not read first frame")

        _, buffer = cv.imencode(".jpg", frame, [cv.IMWRITE_JPEG_QUALITY, 90])
        return StreamingResponse(
            BytesIO(buffer.tobytes()),
            media_type="image/jpeg",
            headers={"Content-Disposition": f"inline; filename=first_frame.jpg"},
        )
    finally:
        os.unlink(tmp.name)


# --- Analysis ---

@router.post("", response_model=DustAnalysisResponse, status_code=201)
@router.post("/", response_model=DustAnalysisResponse, status_code=201)
def create_dust_analysis(
    body: DustAnalysisCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a dust analysis job."""
    video = db.query(VideoFile).filter(
        VideoFile.id == body.video_file_id,
        VideoFile.user_id == current_user.id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if len(body.polygon_points) != 4:
        raise HTTPException(
            status_code=400,
            detail="Exactly 4 polygon points required",
        )

    job = DustAnalysisJob(
        user_id=current_user.id,
        video_file_id=body.video_file_id,
        polygon_points=body.polygon_points,
        total_frames=video.total_frames or 0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue Celery task
    from app.workers.dust.task import analyze_dust_task
    task = analyze_dust_task.apply_async(
        args=[str(job.id)],
        task_id=f"dust_{job.id}",
    )
    job.celery_task_id = task.id
    job.status = "queued"
    db.commit()

    return job


@router.get("/{job_id}/status", response_model=DustAnalysisStatusResponse)
def get_dust_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analysis job status."""
    job = db.query(DustAnalysisJob).filter(
        DustAnalysisJob.id == job_id,
        DustAnalysisJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}", response_model=DustAnalysisResponse)
def get_dust_result(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full analysis result."""
    job = db.query(DustAnalysisJob).filter(
        DustAnalysisJob.id == job_id,
        DustAnalysisJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# --- WebSocket for real-time results ---

@router.websocket("/{job_id}/ws")
async def dust_websocket(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint that streams per-frame detection results.
    Subscribes to Redis pub/sub channel 'dust:{job_id}'.
    """
    await websocket.accept()

    r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    pubsub = r.pubsub()
    channel = f"dust:{job_id}"
    pubsub.subscribe(channel)

    try:
        while True:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)

                # Check if done
                parsed = json.loads(data)
                if parsed.get("done") or parsed.get("error"):
                    break
            else:
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for dust job {job_id}")
    finally:
        pubsub.unsubscribe(channel)
        pubsub.close()
