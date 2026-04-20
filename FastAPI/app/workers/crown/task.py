"""
Celery task for crown distress analysis.

Orchestrates: extract polygon extent → analyze crown slopes/ruts →
generate HTML report → upload to S3 → update database.
"""

import json
import os
import tempfile
import logging
from datetime import datetime
from typing import Optional

import boto3

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import CrownAnalysisJob, TiffFile
from app.config import settings

from app.workers.rut.geo import extract_polygon_extent
from app.workers.crown.detection import analyze_crown_in_polygon
from app.workers.crown.report import generate_html_report

logger = logging.getLogger(__name__)

s3_client = boto3.client('s3', region_name=settings.AWS_REGION)


@celery_app.task(bind=True, name="app.workers.crown.task.analyze_crown_task")
def analyze_crown_task(self, job_id: str, screenshot_base64: Optional[str] = None):
    """
    Celery task to analyze crown distress in a polygon.

    Pipeline:
        1. Load job + TIFF metadata from DB
        2. Extract polygon extent from S3-hosted GeoTIFF
        3. Run crown slope analysis + rut detection along sampling lines
        4. Generate interactive HTML report
        5. Upload report to S3
        6. Update job record in DB
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting crown analysis job {job_id}")

        job = db.query(CrownAnalysisJob).filter(CrownAnalysisJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = "processing"
        job.progress = 5
        db.commit()

        tiff_file = db.query(TiffFile).filter(TiffFile.id == job.tiff_file_id).first()
        if not tiff_file:
            raise ValueError(f"TIFF file {job.tiff_file_id} not found")

        # Prefer original DEM for analysis
        s3_key = tiff_file.s3_key if tiff_file.file_type == "DEM" else (tiff_file.cog_s3_key or tiff_file.s3_key)
        s3_url = f"s3://{tiff_file.s3_bucket}/{s3_key}"
        logger.info(f"Job {job_id}: Reading from {s3_url}")

        # Step 1: Extract polygon extent
        job.progress = 10
        db.commit()

        elevation_data, metadata, polygon = extract_polygon_extent(
            s3_url, job.polygon_geojson, job.apply_smoothing, job.gaussian_sigma
        )
        logger.info(f"Job {job_id}: Extracted polygon, shape={elevation_data.shape}")

        # Step 2: Analyze crown distress
        job.progress = 25
        db.commit()

        results = analyze_crown_in_polygon(
            elevation_data, metadata, polygon,
            job.spacing_m, job.dy_freq, job_id,
            job.neighbor_eval, job.neighbor_range
        )

        # Step 3: Generate HTML report
        job.progress = 80
        db.commit()

        html_content = generate_html_report(results, job_id)

        # Step 4: Upload HTML to S3
        job.progress = 90
        db.commit()

        html_s3_key = f"crown_analysis/{job.user_id}/{job_id}/report.html"
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

        # Step 4b: GeoJSON overlay of classified crown strips (one feature per
        # sampling line with a non-None severity, clipped to the polygon).
        geojson_s3_key = None
        geojson_url = None
        try:
            features = []
            for seg in results.get("all_segments") or []:
                geom = seg.get("geometry")
                if not geom:
                    continue
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "severity": seg.get("severity"),
                        "rut_sev": seg.get("rut_sev"),
                        "rut_depth_in": seg.get("rut_depth_in"),
                        "avg_slope_pct": seg.get("avg_slope_pct"),
                        "line_x": seg.get("line_x"),
                    },
                })
            feature_collection = {"type": "FeatureCollection", "features": features}

            geojson_s3_key = f"crown_analysis/{job.user_id}/{job_id}/features.geojson"
            with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as tmp_gj:
                json.dump(feature_collection, tmp_gj)
                tmp_gj_path = tmp_gj.name
            try:
                s3_client.upload_file(tmp_gj_path, settings.S3_BUCKET_RAW, geojson_s3_key,
                                      ExtraArgs={"ContentType": "application/geo+json"})
                geojson_url = s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": settings.S3_BUCKET_RAW, "Key": geojson_s3_key},
                    ExpiresIn=604800,
                )
                logger.info(f"Job {job_id}: Crown GeoJSON uploaded ({len(features)} features)")
            finally:
                os.unlink(tmp_gj_path)
        except Exception as gj_err:
            logger.error(f"Job {job_id}: GeoJSON upload failed, continuing: {gj_err}")

        # Step 5: Update job with results
        totals = results['totals_ft']
        counts = results['counts']

        job.results_json = results
        job.html_report_s3_key = html_s3_key
        job.html_report_url = html_url
        job.features_geojson_s3_key = geojson_s3_key
        job.features_geojson_url = geojson_url
        job.low_severity_ft = totals.get('Low', 0.0)
        job.medium_severity_ft = totals.get('Medium', 0.0)
        job.high_severity_ft = totals.get('High', 0.0)
        job.total_linear_ft = results.get('total_linear_ft', 0.0)
        job.low_count = counts.get('Low', 0)
        job.medium_count = counts.get('Medium', 0)
        job.high_count = counts.get('High', 0)
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Job {job_id} completed: Low={totals['Low']:.1f}ft, "
                    f"Med={totals['Medium']:.1f}ft, High={totals['High']:.1f}ft")

        return {'job_id': str(job_id), 'status': 'completed', 'totals_ft': totals}

    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        raise

    finally:
        db.close()
