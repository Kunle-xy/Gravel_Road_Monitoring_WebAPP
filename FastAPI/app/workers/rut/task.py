"""
Celery task for rut analysis.

Orchestrates the full pipeline: extract polygon extent from GeoTIFF,
detect ruts, generate plots/reports, upload to S3, and update the database.
"""

import json
import os
import tempfile
import logging
from datetime import datetime

import boto3

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import RutAnalysisJob, TiffFile
from app.config import settings

from app.workers.rut.geo import extract_polygon_extent
from app.workers.rut.detection import analyze_ruts_in_polygon
from app.workers.rut.report import generate_html_plot

logger = logging.getLogger(__name__)

# Configure logging
def _configure_logging():
    """Configure detailed logging for rut analysis."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'rut_analysis.log')),
            logging.StreamHandler()
        ]
    )

_configure_logging()

s3_client = boto3.client('s3', region_name=settings.AWS_REGION)


@celery_app.task(bind=True, name="app.workers.rut_worker.analyze_ruts_task")
def analyze_ruts_task(self, job_id: str):
    """
    Celery task to analyze ruts in a polygon.
    Extracts only the polygon extent from the cloud-stored GeoTIFF.

    Pipeline:
        1. Load job + TIFF metadata from DB
        2. Extract polygon extent from S3-hosted GeoTIFF
        3. Run rut detection along sampling lines
        4. Generate interactive HTML plot and upload to S3
        5. Update job record in DB
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting rut analysis job {job_id}")

        job = db.query(RutAnalysisJob).filter(RutAnalysisJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = "processing"
        job.progress = 5
        db.commit()

        tiff_file = db.query(TiffFile).filter(TiffFile.id == job.tiff_file_id).first()
        if not tiff_file:
            raise ValueError(f"TIFF file {job.tiff_file_id} not found")

        # For DEM files, prefer original over COG (better for analysis)
        if tiff_file.file_type == "DEM":
            s3_key = tiff_file.s3_key
            logger.info(f"Job {job_id}: Using original DEM file for analysis")
        else:
            s3_key = tiff_file.cog_s3_key if tiff_file.cog_s3_key else tiff_file.s3_key

        s3_url = f"s3://{tiff_file.s3_bucket}/{s3_key}"
        logger.info(f"Job {job_id}: Reading from {s3_url}")

        # Step 1: Extract polygon extent
        job.progress = 10
        db.commit()

        elevation_data, metadata, polygon = extract_polygon_extent(
            s3_url, job.polygon_geojson, job.apply_smoothing, job.gaussian_sigma
        )
        logger.info(f"Job {job_id}: Extracted polygon extent, shape={elevation_data.shape}")

        # Step 2: Analyze ruts
        job.progress = 30
        db.commit()

        results = analyze_ruts_in_polygon(
            elevation_data, metadata, polygon,
            job.dy_freq, job.dx, job_id,
            job.neighbor_eval, job.neighbor_range
        )

        # Step 3: Generate HTML plot
        job.progress = 80
        db.commit()

        html_content = generate_html_plot(results, job_id)

        # Step 4: Upload HTML to S3
        job.progress = 90
        db.commit()

        html_s3_key = f"rut_analysis/{job.user_id}/{job_id}/plot.html"
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

        # Step 4b: Build a GeoJSON FeatureCollection of the detected ruts and
        # upload it to S3. The frontend toggles this as a Leaflet layer.
        geojson_s3_key = None
        geojson_url = None
        try:
            features = []
            for rut in results.get('ruts') or []:
                ring = rut.get('rect_coords')
                if not ring or len(ring) < 4:
                    continue
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Polygon',
                        'coordinates': [ring],
                    },
                    'properties': {
                        'severity': rut.get('severity'),
                        'depth_in': rut.get('rut_depth_in'),
                        'area_sqft': rut.get('rut_area_sqft'),
                        'line_x': rut.get('line_x'),
                        'frequency': rut.get('frequency'),
                    },
                })
            feature_collection = {'type': 'FeatureCollection', 'features': features}

            geojson_s3_key = f"rut_analysis/{job.user_id}/{job_id}/features.geojson"
            with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp_gj:
                json.dump(feature_collection, tmp_gj)
                tmp_gj_path = tmp_gj.name
            try:
                s3_client.upload_file(tmp_gj_path, settings.S3_BUCKET_RAW, geojson_s3_key,
                                      ExtraArgs={'ContentType': 'application/geo+json'})
                geojson_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': settings.S3_BUCKET_RAW, 'Key': geojson_s3_key},
                    ExpiresIn=604800,
                )
                logger.info(f"Job {job_id}: Features GeoJSON uploaded ({len(features)} features)")
            finally:
                os.unlink(tmp_gj_path)
        except Exception as gj_err:
            logger.error(f"Job {job_id}: Features GeoJSON upload failed, continuing: {gj_err}")

        # Step 5: Update job with results
        job.results_json = results
        job.html_plot_s3_key = html_s3_key
        job.html_plot_url = html_url
        job.features_geojson_s3_key = geojson_s3_key
        job.features_geojson_url = geojson_url
        job.total_ruts_detected = results['total_ruts_detected']
        job.low_severity_count = results['low_severity_count']
        job.medium_severity_count = results['medium_severity_count']
        job.high_severity_count = results['high_severity_count']
        job.total_area_sqft = results['total_area_sqft']
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Job {job_id} completed successfully")
        return {'job_id': str(job_id), 'status': 'completed', 'total_ruts': results['total_ruts_detected']}

    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        raise

    finally:
        db.close()
