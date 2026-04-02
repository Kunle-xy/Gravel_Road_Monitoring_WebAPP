"""
Celery task — Dust analysis: YOLO vehicle detection + ResNet-152 dust classification.
Processes video frame-by-frame, classifies dust severity, returns aggregated results.
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

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.dust.task.analyze_dust_task", bind=True)
def analyze_dust_task(self, job_id: str):
    """
    Process video: detect vehicles with YOLO, classify dust with ResNet-152.

    Logic:
    - For each frame, run YOLO detection.
    - If a vehicle is inside the polygon: crop around the vehicle bbox, classify dust.
    - If no vehicle detected but a vehicle previously encroached: crop the polygon
      region (road surface), classify dust on the lingering road.
    - Aggregate predictions into Non Dust / Low Dust / High Dust counts.
    """
    from app.workers.dust.detection import (
        get_yolo_model, classify_dust, center_square_from_frame,
        VEHICLE_CLASSES, DUST_CLASSES, TARGET,
    )

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

        logger.info(f"Downloading video from s3://{video.s3_bucket}/{video.s3_key}")
        s3.download_file(video.s3_bucket, video.s3_key, video_path)

        cap = cv.VideoCapture(video_path)
        if not cap.isOpened():
            job.status = "failed"
            job.error_message = "Could not open video file"
            db.commit()
            return

        total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        polygon = np.array(job.polygon_points, dtype=np.int32)

        frame_w = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Video: {frame_w}x{frame_h}, {total_frames} frames")
        logger.info(f"Polygon points: {job.polygon_points}")

        # Validate polygon is within video bounds
        poly_max_x = polygon[:, 0].max()
        poly_max_y = polygon[:, 1].max()
        if poly_max_x > frame_w or poly_max_y > frame_h:
            logger.warning(f"Polygon ({poly_max_x},{poly_max_y}) exceeds video dimensions ({frame_w},{frame_h})")

        # Load YOLO model
        yolo = get_yolo_model()
        class_names = yolo.names

        # Tracking state
        road_encroached = False
        counts = {"High Dust": 0, "Low Dust": 0, "No Dust": 0}
        truck_frames = 0
        no_truck_frames = 0
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_copy = frame.copy()
            results = yolo.predict(source=frame, conf=0.05, imgsz=960, verbose=False)

            vehicle_detected = False

            if results[0].boxes is not None and results[0].boxes.data is not None:
                boxes = results[0].boxes.xyxy
                class_indices = results[0].boxes.cls
                confidences = results[0].boxes.conf

                for box, cls_idx, conf in zip(boxes, class_indices, confidences):
                    label = class_names[int(cls_idx)]
                    if label not in VEHICLE_CLASSES:
                        continue

                    vehicle_detected = True
                    x1, y1, x2, y2 = map(int, box.tolist())
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                    inside = cv.pointPolygonTest(polygon, (cx, cy), False)
                    if inside >= 0:
                        road_encroached = True
                        truck_frames += 1

                        # Crop vehicle region
                        w, h = x2 - x1, y2 - y1
                        side = max(w, h) if (w >= TARGET or h >= TARGET) else TARGET
                        crop = center_square_from_frame(frame_copy, cx, cy, side)
                        crop_224 = cv.resize(crop, (TARGET, TARGET), interpolation=cv.INTER_AREA)

                        pred = classify_dust(crop_224)
                        counts[DUST_CLASSES[pred]] += 1

            # No vehicle detected but road was previously encroached
            if not vehicle_detected and road_encroached:
                no_truck_frames += 1

                # Crop the polygon bounding rect
                x_coords = polygon[:, 0]
                y_coords = polygon[:, 1]
                cx = int((x_coords.min() + x_coords.max()) / 2)
                cy = int((y_coords.min() + y_coords.max()) / 2)
                w = int(x_coords.max() - x_coords.min())
                h = int(y_coords.max() - y_coords.min())
                side = max(w, h) if (w >= TARGET or h >= TARGET) else TARGET

                crop = center_square_from_frame(frame_copy, cx, cy, side)
                crop_224 = cv.resize(crop, (TARGET, TARGET), interpolation=cv.INTER_AREA)

                pred = classify_dust(crop_224)
                counts[DUST_CLASSES[pred]] += 1

            # Update progress every 30 frames
            if frame_idx % 30 == 0:
                progress = int((frame_idx / max(total_frames, 1)) * 100)
                job.progress = min(progress, 99)
                db.commit()

            frame_idx += 1

        cap.release()

        logger.info(f"Job {job_id}: Processed {frame_idx} frames, truck_frames={truck_frames}, no_truck_frames={no_truck_frames}, road_encroached={road_encroached}")

        # Compute results
        total_classified = sum(counts.values())
        if total_classified > 0:
            percentages = {k: round(v / total_classified * 100, 1) for k, v in counts.items()}
        else:
            percentages = {"High Dust": 0, "Low Dust": 0, "No Dust": 0}

        job.status = "completed"
        job.progress = 100
        job.total_frames = frame_idx
        job.truck_frames = truck_frames
        job.no_truck_frames = no_truck_frames
        job.results_json = {
            "counts": counts,
            "percentages": percentages,
            "total_classified": total_classified,
        }
        from datetime import datetime, timezone
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Dust analysis complete for job {job_id}: {counts}")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)[:500]
        db.commit()
    finally:
        db.close()
        try:
            import shutil
            if "tmp_dir" in locals():
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
