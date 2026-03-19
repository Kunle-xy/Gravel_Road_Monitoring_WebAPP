"""
Celery task for rut analysis.

Orchestrates the full pipeline: extract polygon extent from GeoTIFF,
detect ruts, generate plots/reports, upload to S3, and update the database.
"""

import os
import tempfile
import logging
from datetime import datetime
from typing import Optional

import boto3

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import RutAnalysisJob, TiffFile
from app.config import settings

from app.workers.rut.geo import extract_polygon_extent
from app.workers.rut.detection import analyze_ruts_in_polygon
from app.workers.rut.report import generate_html_plot, generate_pdf_from_results

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
def analyze_ruts_task(self, job_id: str, screenshot_base64: Optional[str] = None):
    """
    Celery task to analyze ruts in a polygon.
    Extracts only the polygon extent from the cloud-stored GeoTIFF.

    Pipeline:
        1. Load job + TIFF metadata from DB
        2. Extract polygon extent from S3-hosted GeoTIFF
        3. Run rut detection along sampling lines
        4. Generate interactive HTML plot
        5. Generate multi-page PDF report
        6. Upload results to S3
        7. Update job record in DB
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

        # Step 5: Generate and upload PDF
        job.progress = 92
        db.commit()

        pdf_s3_key = None
        pdf_url = None
        try:
            pdf_bytes = generate_pdf_from_results(results, job_id, screenshot_base64)
            pdf_s3_key = f"rut_analysis/{job.user_id}/{job_id}/report.pdf"

            with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_pdf:
                tmp_pdf.write(pdf_bytes)
                tmp_pdf_path = tmp_pdf.name

            try:
                s3_client.upload_file(tmp_pdf_path, settings.S3_BUCKET_RAW, pdf_s3_key,
                                      ExtraArgs={'ContentType': 'application/pdf'})
                pdf_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': settings.S3_BUCKET_RAW, 'Key': pdf_s3_key},
                    ExpiresIn=604800
                )
                logger.info(f"Job {job_id}: PDF uploaded to S3: {pdf_s3_key}")
            finally:
                os.unlink(tmp_pdf_path)
        except Exception as pdf_error:
            logger.error(f"Job {job_id}: PDF generation failed, but continuing: {str(pdf_error)}")

        # Step 6: Update job with results
        job.results_json = results
        job.html_plot_s3_key = html_s3_key
        job.html_plot_url = html_url
        job.pdf_plot_s3_key = pdf_s3_key
        job.pdf_plot_url = pdf_url
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
