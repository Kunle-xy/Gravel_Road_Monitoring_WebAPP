"""
Celery task for corrugation distress analysis.

Orchestrates: extract polygon extent → detect corrugations along transects →
generate HTML report → upload to S3 → update database.
"""

import os
import tempfile
import logging
from datetime import datetime
from typing import Optional

import boto3

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import CorrugationAnalysisJob, TiffFile
from app.config import settings

from app.workers.rut.geo import extract_polygon_extent
from app.workers.corrugation.detection import analyze_corrugation_in_polygon
from app.workers.corrugation.report import generate_html_report

logger = logging.getLogger(__name__)

s3_client = boto3.client('s3', region_name=settings.AWS_REGION)


@celery_app.task(bind=True, name="app.workers.corrugation.task.analyze_corrugation_task")
def analyze_corrugation_task(self, job_id: str, screenshot_base64: Optional[str] = None):
    """
    Celery task to analyze corrugation distress in a polygon.

    Pipeline:
        1. Load job + TIFF metadata from DB
        2. Extract polygon extent from S3-hosted GeoTIFF
        3. Run corrugation detection along horizontal transect lines
        4. Generate interactive HTML report
        5. Upload report to S3
        6. Update job record in DB
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting corrugation analysis job {job_id}")

        job = db.query(CorrugationAnalysisJob).filter(CorrugationAnalysisJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = "processing"
        job.progress = 5
        db.commit()

        tiff_file = db.query(TiffFile).filter(TiffFile.id == job.tiff_file_id).first()
        if not tiff_file:
            raise ValueError(f"TIFF file {job.tiff_file_id} not found")

        s3_key = tiff_file.s3_key if tiff_file.file_type == "DEM" else (tiff_file.cog_s3_key or tiff_file.s3_key)
        s3_url = f"s3://{tiff_file.s3_bucket}/{s3_key}"
        logger.info(f"Job {job_id}: Reading from {s3_url}")

        # Step 1: Extract polygon extent
        job.progress = 10
        db.commit()

        elevation_data, metadata, polygon = extract_polygon_extent(
            s3_url, job.polygon_geojson, False, 1.0  # No smoothing at extraction level
        )
        logger.info(f"Job {job_id}: Extracted polygon, shape={elevation_data.shape}")

        # Step 2: Analyze corrugation
        job.progress = 25
        db.commit()

        results = analyze_corrugation_in_polygon(
            elevation_data, metadata, polygon,
            job.line_interval, job.dy_freq, job_id,
            job.sigma_samples, job.neighbor_eval, job.neighbor_range
        )

        # Step 3: Generate HTML report
        job.progress = 80
        db.commit()

        html_content = generate_html_report(results, job_id)

        # Step 4: Upload to S3
        job.progress = 90
        db.commit()

        html_s3_key = f"corrugation_analysis/{job.user_id}/{job_id}/report.html"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name

        try:
            s3_client.upload_file(tmp_path, settings.S3_BUCKET_RAW, html_s3_key,
                                  ExtraArgs={'ContentType': 'text/html'})
            html_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.S3_BUCKET_RAW, 'Key': html_s3_key},
                ExpiresIn=604800
            )
        finally:
            os.unlink(tmp_path)

        # Step 5: Update job
        totals = results["totals_ft2"]
        counts = results["counts"]

        job.results_json = results
        job.html_report_s3_key = html_s3_key
        job.html_report_url = html_url
        job.low_area_ft2 = totals.get("LOW", 0.0)
        job.medium_area_ft2 = totals.get("MEDIUM", 0.0)
        job.high_area_ft2 = totals.get("HIGH", 0.0)
        job.total_area_ft2 = results.get("total_area_ft2", 0.0)
        job.low_count = counts.get("LOW", 0)
        job.medium_count = counts.get("MEDIUM", 0)
        job.high_count = counts.get("HIGH", 0)
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Job {job_id} completed: Low={totals.get('LOW', 0):.1f}ft2, "
                    f"Med={totals.get('MEDIUM', 0):.1f}ft2, High={totals.get('HIGH', 0):.1f}ft2")

        return {'job_id': str(job_id), 'status': 'completed', 'totals_ft2': totals}

    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        raise

    finally:
        db.close()
