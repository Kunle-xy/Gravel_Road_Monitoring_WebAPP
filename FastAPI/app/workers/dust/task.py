"""
Celery task for dust analysis — processes every Nth frame,
detects vehicles with YOLOv8, publishes results via Redis pub/sub.
"""

import cv2 as cv
import numpy as np
import json
import tempfile
import os
import logging

import boto3
import redis

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import DustAnalysisJob, VideoFile
from app.workers.dust.detection import detect_vehicles_in_frame

logger = logging.getLogger(__name__)

FRAME_SKIP = 1  # Process every frame (RTX 5000 handles ~30fps)


def get_redis_client():
    return redis.Redis.from_url(settings.CELERY_BROKER_URL)


@celery_app.task(name="app.workers.dust.task.analyze_dust_task", bind=True)
def analyze_dust_task(self, job_id: str):
    """
    Process video frame-by-frame (every Nth frame):
    1. Download video from S3
    2. For each sampled frame, run YOLOv8 vehicle detection
    3. Check if vehicle center is inside the road polygon
    4. Publish per-frame results to Redis pub/sub channel
    5. Update DB with final results
    """
    db = SessionLocal()
    redis_client = get_redis_client()
    channel = f"dust:{job_id}"

    try:
        job = db.query(DustAnalysisJob).filter(DustAnalysisJob.id == job_id).first()
        if not job:
            logger.error(f"Dust job {job_id} not found")
            return

        video = db.query(VideoFile).filter(VideoFile.id == job.video_file_id).first()
        if not video:
            job.status = "failed"
            job.error_message = "Video file not found"
            db.commit()
            return

        job.status = "processing"
        job.progress = 0
        db.commit()

        # Download video from S3
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        tmp_dir = tempfile.mkdtemp(prefix=f"dust_{job_id}_")
        video_path = os.path.join(tmp_dir, "video.mp4")

        logger.info(f"Downloading video from s3://{video.s3_bucket}/{video.s3_key}")
        s3.download_file(video.s3_bucket, video.s3_key, video_path)

        cap = cv.VideoCapture(video_path)
        if not cap.isOpened():
            job.status = "failed"
            job.error_message = "Could not open video file"
            db.commit()
            return

        total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv.CAP_PROP_FPS) or 30.0

        # Parse road polygon
        polygon = np.array(job.polygon_points, dtype=np.int32)

        results = []
        truck_count = 0
        no_truck_count = 0
        sample_count = 0

        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            detection = detect_vehicles_in_frame(frame, polygon)
            truck_detected = detection["truck_detected"]

            if truck_detected:
                truck_count += 1
            else:
                no_truck_count += 1

            time_seconds = round(frame_idx / video_fps, 2)

            frame_result = {
                "frame": frame_idx,
                "time": time_seconds,
                "truck": truck_detected,
                "vehicle_count": len([v for v in detection["vehicles"] if v["inside_polygon"]]),
            }
            results.append(frame_result)
            sample_count += 1

            # Publish to Redis for WebSocket consumers
            redis_client.publish(channel, json.dumps(frame_result))

            # Update DB progress every 30 frames (avoid DB overhead per frame)
            if frame_idx % 30 == 0:
                progress = int((frame_idx / max(total_frames, 1)) * 100)
                job.progress = min(progress, 99)
                job.truck_frames = truck_count
                job.no_truck_frames = no_truck_count
                db.commit()

            frame_idx += 1

        cap.release()

        # Final update
        job.status = "completed"
        job.progress = 100
        job.total_frames = sample_count
        job.truck_frames = truck_count
        job.no_truck_frames = no_truck_count
        job.results_json = results
        from datetime import datetime, timezone
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Publish completion
        redis_client.publish(channel, json.dumps({
            "done": True,
            "total_frames": sample_count,
        }))

        logger.info(
            f"Dust analysis {job_id} complete: {sample_count} samples from {frame_idx} frames, "
            f"{truck_count} with trucks (skip={FRAME_SKIP})"
        )

    except Exception as e:
        logger.error(f"Dust analysis {job_id} failed: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
        redis_client.publish(channel, json.dumps({"error": str(e)}))
    finally:
        db.close()
        try:
            import shutil
            if "tmp_dir" in locals():
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
