"""
Celery task for pothole analysis — extract elevation, calculate depth/width,
generate 3D plot, upload HTML report to S3.
"""

import logging
import boto3

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import PotholeAnalysisJob, TiffFile
from app.workers.rut.geo import extract_polygon_extent
from app.workers.pothole.analysis import analyze_pothole, generate_pothole_html

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.pothole.task.analyze_pothole_task", bind=True)
def analyze_pothole_task(self, job_id: str):
    db = SessionLocal()
    try:
        job = db.query(PotholeAnalysisJob).filter(PotholeAnalysisJob.id == job_id).first()
        if not job:
            logger.error(f"Pothole job {job_id} not found")
            return

        tiff_file = db.query(TiffFile).filter(TiffFile.id == job.tiff_file_id).first()
        if not tiff_file:
            job.status = "failed"
            job.error_message = "DEM file not found"
            db.commit()
            return

        job.status = "processing"
        job.progress = 10
        db.commit()

        # Extract elevation data from polygon
        s3_key = tiff_file.s3_key
        s3_url = f"s3://{tiff_file.s3_bucket}/{s3_key}"
        logger.info(f"Pothole job {job_id}: Reading from {s3_url}")

        elevation_data, metadata, polygon = extract_polygon_extent(
            s3_url, job.polygon_geojson
        )
        logger.info(f"Pothole job {job_id}: Extracted elevation, shape={elevation_data.shape}")

        job.progress = 40
        db.commit()

        # Calculate depth, width, severity
        res = metadata.get("resolution", (0.01, 0.01))
        pixel_resolution = float(res[0]) if isinstance(res, (tuple, list)) else float(res)
        results = analyze_pothole(elevation_data, pixel_resolution)
        logger.info(f"Pothole job {job_id}: depth={results['depth_inches']:.2f}in, width={results['width_feet']:.2f}ft, severity={results['severity']}")

        job.progress = 70
        db.commit()

        # Generate HTML report
        html = generate_pothole_html(elevation_data, results, job_id)

        # Upload to S3
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        html_key = f"pothole-results/{job_id}/report.html"
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=html_key,
            Body=html.encode("utf-8"),
            ContentType="text/html",
        )

        html_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": html_key},
            ExpiresIn=604800,
        )

        # Update job
        job.status = "completed"
        job.progress = 100
        job.results_json = results
        job.html_report_s3_key = html_key
        job.html_report_url = html_url
        job.depth_inches = results["depth_inches"]
        job.width_inches = results["width_inches"]
        job.width_feet = results["width_feet"]
        job.severity = results["severity"]
        from datetime import datetime, timezone
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Pothole job {job_id} complete")

    except Exception as e:
        logger.error(f"Pothole job {job_id} failed: {e}", exc_info=True)
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
    finally:
        db.close()
