"""
Celery task for dust analysis — processes video frame-by-frame,
detects vehicles with YOLOv8, creates annotated output video with bounding boxes.
"""

import cv2 as cv
import numpy as np
import json
import tempfile
import os
import logging

import boto3

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import DustAnalysisJob, VideoFile
from app.workers.dust.detection import detect_vehicles_in_frame

logger = logging.getLogger(__name__)

FRAME_SKIP = 1  # Process every frame


@celery_app.task(name="app.workers.dust.task.analyze_dust_task", bind=True)
def analyze_dust_task(self, job_id: str):
    """
    Process video frame-by-frame:
    1. Download video from S3
    2. For each frame, run YOLOv8 vehicle detection
    3. Draw bounding boxes + polygon overlay on each frame
    4. Write annotated video
    5. Upload annotated video to S3
    6. Update DB with results + video URL
    """
    db = SessionLocal()

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

        # Setup output video writer (H.264 in mp4)
        fourcc = cv.VideoWriter_fourcc(*"mp4v")
        out = cv.VideoWriter(output_path, fourcc, video_fps, (frame_w, frame_h))

        # Parse road polygon
        polygon = np.array(job.polygon_points, dtype=np.int32)

        truck_count = 0
        no_truck_count = 0
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Run detection
            detection = detect_vehicles_in_frame(frame, polygon)

            # Draw polygon overlay (cyan)
            overlay = frame.copy()
            cv.fillPoly(overlay, [polygon], (255, 255, 0))  # BGR cyan fill
            cv.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            cv.polylines(frame, [polygon], True, (255, 255, 0), 2)

            # Draw polygon vertices
            for pt in polygon:
                cv.circle(frame, tuple(pt), 6, (0, 255, 0), -1)
                cv.circle(frame, tuple(pt), 6, (255, 255, 255), 2)

            # Draw bounding boxes on vehicles inside polygon
            for v in detection["vehicles"]:
                if v["inside_polygon"]:
                    x1, y1, x2, y2 = v["bbox"]
                    color = (0, 255, 0)  # Green for detected
                    cv.rectangle(frame, (x1, y1), (x2, y2), color, 3)
                    label = f"{v['label']} {v['confidence']:.2f}"
                    cv.putText(frame, label, (x1, y1 - 10),
                               cv.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # Track counts
            if detection["truck_detected"]:
                truck_count += 1
            else:
                no_truck_count += 1

            # Write annotated frame
            out.write(frame)

            # Update progress every 30 frames
            if frame_idx % 30 == 0:
                progress = int((frame_idx / max(total_frames, 1)) * 100)
                job.progress = min(progress, 99)
                job.truck_frames = truck_count
                job.no_truck_frames = no_truck_count
                db.commit()

            frame_idx += 1

        cap.release()
        out.release()

        # Upload annotated video to S3
        s3_key = f"dust-results/{job_id}/annotated.mp4"
        logger.info(f"Uploading annotated video to s3://{settings.S3_BUCKET_NAME}/{s3_key}")
        s3.upload_file(
            output_path,
            settings.S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )

        # Generate presigned URL (7-day expiry)
        annotated_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=604800,
        )

        # Final update
        job.status = "completed"
        job.progress = 100
        job.total_frames = frame_idx
        job.truck_frames = truck_count
        job.no_truck_frames = no_truck_count
        job.results_json = {"annotated_video_url": annotated_url, "s3_key": s3_key}
        from datetime import datetime, timezone
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"Dust analysis {job_id} complete: {frame_idx} frames, "
            f"{truck_count} with trucks"
        )

    except Exception as e:
        logger.error(f"Dust analysis {job_id} failed: {e}", exc_info=True)
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
