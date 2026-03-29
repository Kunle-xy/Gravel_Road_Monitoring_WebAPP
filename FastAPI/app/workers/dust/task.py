"""
Celery task — YOLOv8 object detection on video within bounded region.
Creates annotated output video with bounding boxes.
"""

import cv2 as cv
import numpy as np
import tempfile
import os
import logging

import boto3

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import DustAnalysisJob, VideoFile
from app.workers.dust.detection import detect_and_annotate

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.dust.task.analyze_dust_task", bind=True)
def analyze_dust_task(self, job_id: str):
    """
    Process video frame-by-frame with YOLOv8, annotate detections,
    write output video, upload to S3.
    """
    db = SessionLocal()

    try:
        job = db.query(DustAnalysisJob).filter(DustAnalysisJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
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

        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        tmp_dir = tempfile.mkdtemp(prefix=f"dust_{job_id}_")
        video_path = os.path.join(tmp_dir, "input.mp4")
        output_path = os.path.join(tmp_dir, "annotated.mp4")

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
        frame_w = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv.VideoWriter_fourcc(*"mp4v")
        out = cv.VideoWriter(output_path, fourcc, video_fps, (frame_w, frame_h))

        polygon = np.array(job.polygon_points, dtype=np.int32)
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            annotated = detect_and_annotate(frame, polygon)
            out.write(annotated)

            if frame_idx % 30 == 0:
                progress = int((frame_idx / max(total_frames, 1)) * 100)
                job.progress = min(progress, 99)
                db.commit()

            frame_idx += 1

        cap.release()
        out.release()

        # Upload to S3
        s3_key = f"dust-results/{job_id}/annotated.mp4"
        s3.upload_file(
            output_path, settings.S3_BUCKET_NAME, s3_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )

        annotated_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=604800,
        )

        job.status = "completed"
        job.progress = 100
        job.total_frames = frame_idx
        job.results_json = {"annotated_video_url": annotated_url, "s3_key": s3_key}
        from datetime import datetime, timezone
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Detection complete: {frame_idx} frames processed for job {job_id}")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
    finally:
        db.close()
        try:
            import shutil
            if "tmp_dir" in locals():
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
