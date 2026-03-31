"""
Dust analysis API — video upload, first frame extraction,
live MJPEG streaming with YOLOv8 detection.
"""

import uuid
import tempfile
import os
import logging
import time
from io import BytesIO
from typing import Generator

import boto3
import cv2 as cv
import numpy as np

from fastapi import APIRouter, Depends, HTTPException, status, Query
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


# --- Video List / Upload ---

@router.get("/videos", response_model=list[VideoFileResponse])
def list_videos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(VideoFile).filter(
        VideoFile.user_id == current_user.id,
        VideoFile.upload_status == "completed",
    ).order_by(VideoFile.created_at.desc()).all()


@router.delete("/video/{video_id}", status_code=204)
def delete_video(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    video = db.query(VideoFile).filter(
        VideoFile.id == video_id, VideoFile.user_id == current_user.id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    try:
        s3_client.delete_object(Bucket=video.s3_bucket, Key=video.s3_key)
    except Exception as e:
        logger.warning(f"Failed to delete S3 object: {e}")
    db.delete(video)
    db.commit()


@router.post("/video/presign", response_model=VideoPresignResponse)
def presign_video_upload(
    body: VideoPresignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.filename.lower().endswith((".mp4", ".avi", ".mov")):
        raise HTTPException(status_code=400, detail="Only .mp4, .avi, .mov allowed")

    unique_id = uuid.uuid4().hex[:8]
    s3_key = f"videos/{current_user.id}/{unique_id}/{body.filename}"

    presigned_url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.S3_BUCKET_RAW, "Key": s3_key, "ContentType": body.content_type},
        ExpiresIn=3600,
    )

    db_video = VideoFile(
        user_id=current_user.id, folder_id=body.folder_id,
        filename=body.filename, original_size_bytes=body.file_size,
        s3_bucket=settings.S3_BUCKET_RAW, s3_key=s3_key, upload_status="pending",
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)

    return VideoPresignResponse(presigned_url=presigned_url, s3_key=s3_key, video_id=db_video.id)


@router.post("/video/{video_id}/complete", response_model=VideoFileResponse)
def complete_video_upload(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    video = db.query(VideoFile).filter(
        VideoFile.id == video_id, VideoFile.user_id == current_user.id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

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
    video = db.query(VideoFile).filter(
        VideoFile.id == video_id, VideoFile.user_id == current_user.id,
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
        return StreamingResponse(BytesIO(buffer.tobytes()), media_type="image/jpeg")
    finally:
        os.unlink(tmp.name)


# --- Model List ---

@router.get("/models")
def list_models():
    """Return the YOLO model used for detection."""
    from app.workers.dust.detection import MODEL_LABEL
    return [{"id": "yolo26", "label": MODEL_LABEL, "description": "Latest, edge-optimized"}]


# --- Live MJPEG Stream ---

def _generate_mjpeg(video_path: str, polygon_points: list, speed: float = 1.0) -> Generator[bytes, None, None]:
    """
    Generator that reads video frame-by-frame, runs YOLO detection,
    and yields MJPEG frames for streaming.
    """
    from app.workers.dust.detection import detect_and_annotate

    cap = cv.VideoCapture(video_path)
    if not cap.isOpened():
        return

    video_fps = cap.get(cv.CAP_PROP_FPS) or 30.0
    frame_delay = 1.0 / (video_fps * max(speed, 0.1))
    polygon = np.array(polygon_points, dtype=np.int32)

    try:
        while cap.isOpened():
            t_start = time.time()

            ret, frame = cap.read()
            if not ret:
                break

            annotated = detect_and_annotate(frame, polygon)

            _, buffer = cv.imencode(".jpg", annotated, [cv.IMWRITE_JPEG_QUALITY, 80])
            frame_bytes = buffer.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n"
                b"\r\n" + frame_bytes + b"\r\n"
            )

            elapsed = time.time() - t_start
            if elapsed < frame_delay:
                time.sleep(frame_delay - elapsed)
    finally:
        cap.release()


@router.get("/stream/{video_id}")
def stream_detection(
    video_id: uuid.UUID,
    polygon: str = Query(..., description="Polygon points as JSON"),
    speed: float = Query(1.0, ge=0.25, le=4.0, description="Playback speed multiplier"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Live MJPEG stream with YOLO detection. Speed: 0.25x to 4x."""
    import json

    video = db.query(VideoFile).filter(
        VideoFile.id == video_id, VideoFile.user_id == current_user.id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        polygon_points = json.loads(polygon)
        if len(polygon_points) != 4:
            raise ValueError("Need 4 points")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid polygon: {e}")

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    s3_client.download_file(video.s3_bucket, video.s3_key, tmp.name)

    def stream_and_cleanup():
        try:
            yield from _generate_mjpeg(tmp.name, polygon_points, speed)
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    return StreamingResponse(
        stream_and_cleanup(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
