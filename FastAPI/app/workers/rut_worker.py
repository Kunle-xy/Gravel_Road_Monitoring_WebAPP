"""
Celery Worker for Rut Analysis

This module handles asynchronous rut detection analysis using Celery.
Optimized to extract only polygon extents from cloud-stored GeoTIFFs.

--- ALL CODES ARE WRITTEN BY KUNLE OGUNTOYE, PhD Student at Iowa State University ---
--- CONTACT: oguntoye@IASTATE.EDU
"""

import os
import json
import logging
import tempfile
import base64
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

import boto3
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from rasterio.io import MemoryFile
from shapely.geometry import Polygon, LineString, shape
from shapely.ops import transform
from scipy.ndimage import gaussian_filter
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from weasyprint import HTML
from pyproj import Transformer

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import RutAnalysisJob, TiffFile
from app.config import settings

logger = logging.getLogger(__name__)

# Configure logging safely (create logs directory if needed)
def _configure_logging():
    """Configure detailed logging for rut analysis."""
    import os
    log_dir = '/home/oguntoye/GravelRoad_Iowa/FastAPI/logs'
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'rut_analysis.log')),
            logging.StreamHandler()
        ]
    )

# Configure logging when module is imported
_configure_logging()

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION
)


def _gaussian_filter_nan(arr: np.ndarray, sigma: float) -> np.ndarray:
    """
    Apply Gaussian smoothing to an array that may contain NaN.
    Normalizes by a binary mask so NaN regions remain NaN.
    """
    if sigma is None or sigma <= 0:
        return arr

    a = arr.astype(float).copy()
    nan_mask = np.isnan(a)
    a[nan_mask] = 0.0
    w = (~nan_mask).astype(float)

    a_blur = gaussian_filter(a, sigma=sigma, mode="nearest")
    w_blur = gaussian_filter(w, sigma=sigma, mode="nearest")

    with np.errstate(invalid="ignore", divide="ignore"):
        out = a_blur / w_blur
    out[w_blur == 0] = np.nan
    return out


def _extract_polygon_extent(
    s3_url: str,
    polygon_geojson: Dict[str, Any],
    apply_smoothing: bool = False,
    gaussian_sigma: float = 1.0
) -> Tuple[np.ndarray, dict, Polygon]:
    """
    Extract only the polygon extent from a cloud-stored GeoTIFF.

    Returns:
        - elevation_array: 2D numpy array of elevation values
        - metadata: dict with transform, crs, bounds, resolution
        - polygon: Shapely polygon in raster CRS
    """
    # Set AWS credentials as environment variables for GDAL
    os.environ['AWS_ACCESS_KEY_ID'] = settings.AWS_ACCESS_KEY_ID
    os.environ['AWS_SECRET_ACCESS_KEY'] = settings.AWS_SECRET_ACCESS_KEY
    os.environ['AWS_REGION'] = settings.AWS_REGION

    # Configure GDAL for S3 access (without AWS credentials)
    env_options = {
        'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR',
        'CPL_VSIL_CURL_ALLOWED_EXTENSIONS': '.tif,.tiff',
        'GDAL_HTTP_TIMEOUT': '300',
        'GDAL_HTTP_MAX_RETRY': '3',
    }

    # Parse polygon from GeoJSON (assumed to be in EPSG:4326)
    polygon_shape = shape(polygon_geojson)

    with rasterio.Env(**env_options):
        # Open remote file
        with rasterio.open(s3_url) as src:
            # Transform polygon from EPSG:4326 to DEM's CRS
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            polygon_transformed = transform(transformer.transform, polygon_shape)

            logger.info(f"Transformed polygon from EPSG:4326 to {src.crs}")
            logger.info(f"Original bounds (lat/lon): {polygon_shape.bounds}")
            logger.info(f"Transformed bounds ({src.crs}): {polygon_transformed.bounds}")

            # Get DEM bounds
            dem_bounds = src.bounds  # BoundingBox(left, bottom, right, top)

            # Get polygon bounds in DEM's CRS
            poly_bounds = polygon_transformed.bounds  # (minx, miny, maxx, maxy)

            # Validate polygon is within DEM bounds
            poly_minx, poly_miny, poly_maxx, poly_maxy = poly_bounds

            # Check if polygon is completely outside DEM
            if (poly_maxx < dem_bounds.left or poly_minx > dem_bounds.right or
                poly_maxy < dem_bounds.bottom or poly_miny > dem_bounds.top):
                raise ValueError(
                    f"Polygon is completely outside DEM bounds. "
                    f"Polygon: ({poly_minx:.6f}, {poly_miny:.6f}, {poly_maxx:.6f}, {poly_maxy:.6f}), "
                    f"DEM: ({dem_bounds.left:.6f}, {dem_bounds.bottom:.6f}, {dem_bounds.right:.6f}, {dem_bounds.top:.6f})"
                )

            # Check if polygon is partially outside DEM (warn but continue)
            if (poly_minx < dem_bounds.left or poly_maxx > dem_bounds.right or
                poly_miny < dem_bounds.bottom or poly_maxy > dem_bounds.top):
                logger.warning(
                    f"Polygon extends beyond DEM bounds. "
                    f"Polygon: ({poly_minx:.6f}, {poly_miny:.6f}, {poly_maxx:.6f}, {poly_maxy:.6f}), "
                    f"DEM: ({dem_bounds.left:.6f}, {dem_bounds.bottom:.6f}, {dem_bounds.right:.6f}, {dem_bounds.top:.6f}). "
                    f"Analysis will be limited to DEM coverage area."
                )

            # Create window from bounds
            window = from_bounds(*poly_bounds, transform=src.transform)

            # Read windowed data
            band1 = src.read(1, window=window).astype(float)

            # Get window transform
            window_transform = src.window_transform(window)

            # Respect raster nodata
            if src.nodata is not None:
                band1[band1 == float(src.nodata)] = np.nan

            # Apply Gaussian smoothing if requested
            if apply_smoothing:
                logger.info(f"Applying Gaussian smoothing with sigma={gaussian_sigma}")
                band1 = _gaussian_filter_nan(band1, gaussian_sigma)

            metadata = {
                'transform': window_transform,
                'crs': src.crs,
                'bounds': poly_bounds,
                'resolution': src.res,
                'width': window.width,
                'height': window.height,
                'nodata': src.nodata
            }

            # Return the transformed polygon (in DEM's CRS)
            return band1, metadata, polygon_transformed


def _detect_ruts_along_line(
    depths: List[float],
    dy: float,
    dx: float,
    min_depth_diff: float = 0.0127,  # 0.5 inches in meters
    min_points_between: int = 10
) -> List[Dict[str, Any]]:
    """
    Detect ruts along a single sampling line.

    Returns list of detected ruts with:
        - idx_h1: left peak index
        - idx_low: valley index
        - idx_h2: right peak index
        - rut_depth_m: rut depth in meters
        - rut_depth_in: rut depth in inches
        - rut_area_sqft: rut area in square feet
        - severity: 'Low', 'Medium', or 'High'
    """
    inches_per_meter = 39.3701
    sqm_to_sqft = 10.7639

    if len(depths) < 2:
        return []

    df_input = pd.DataFrame({"section": list(range(len(depths))), "depth": depths})

    res = []
    direction_prev = None
    left_height = None
    peak_heights = [df_input["depth"].iloc[0]]
    peak_indices = [0]
    idx_h1 = 0
    h1 = df_input["depth"].iloc[0]
    low = h1
    idx_low = 0

    for idx in range(1, len(df_input)):
        current = df_input["depth"].iloc[idx]
        previous = df_input["depth"].iloc[idx - 1]
        direction = "UP" if current > previous else "DOWN"

        if direction == "UP":
            if current > peak_heights[-1]:
                peak_heights[-1] = current
                peak_indices[-1] = idx
            else:
                peak_heights.append(current)
                peak_indices.append(idx)

        # DOWN to UP transition: valley found
        if direction_prev == "DOWN" and direction == "UP":
            low = df_input["depth"].iloc[idx - 1]
            idx_low = idx - 1
            if peak_indices:
                valid_peaks = [i for i in peak_indices if i <= idx_low]
                if valid_peaks:
                    peak_heights_valid = [peak_heights[peak_indices.index(i)] for i in valid_peaks]
                    max_peak_idx = peak_heights_valid.index(max(peak_heights_valid))
                    idx_h1 = valid_peaks[max_peak_idx]
                    h1 = df_input["depth"].iloc[idx_h1]
                    left_height = h1 - low
                else:
                    left_height = None
            else:
                left_height = None

        # UP to DOWN transition: right peak found, check if rut
        elif direction_prev == "UP" and direction == "DOWN" and left_height is not None:
            if peak_indices:
                valid_peaks = [i for i in peak_indices if i > idx_low and i <= idx]
                if valid_peaks:
                    peak_heights_valid = [peak_heights[peak_indices.index(i)] for i in valid_peaks]
                    max_peak_idx = peak_heights_valid.index(max(peak_heights_valid))
                    idx_h2 = valid_peaks[max_peak_idx]
                    h2 = df_input["depth"].iloc[idx_h2]
                    right_height = h2 - low

                    avg_shoulder = 0.5 * (h1 + h2)
                    rut_depth_m = avg_shoulder - low
                    rut_depth_in = rut_depth_m * inches_per_meter

                    # Validate rut
                    if (idx_h2 > idx_low > idx_h1 and
                        (min(left_height, right_height) >= 0.1 * max(left_height, right_height)) and
                        rut_depth_m >= min_depth_diff and
                        (idx_h2 - idx_h1 - 1) > min_points_between):

                        width = (idx_h2 - idx_h1) * dy
                        rut_area = width * dx
                        rut_area_sqft = rut_area * sqm_to_sqft

                        # Determine severity
                        severity = None
                        if 0.5 < rut_depth_in < 1.0:
                            severity = "Low"
                        elif 1.0 <= rut_depth_in <= 3.0:
                            severity = "Medium"
                        elif rut_depth_in > 3.0:
                            severity = "High"

                        if severity:
                            res.append({
                                'idx_h1': int(idx_h1),
                                'idx_low': int(idx_low),
                                'idx_h2': int(idx_h2),
                                'rut_depth_m': float(rut_depth_m),
                                'rut_depth_in': float(rut_depth_in),
                                'rut_area_sqft': float(rut_area_sqft),
                                'severity': severity
                            })

                        peak_heights = [h2]
                        peak_indices = [idx_h2]

        direction_prev = direction

    return res


def _analyze_ruts_in_polygon(
    elevation_data: np.ndarray,
    metadata: dict,
    polygon: Polygon,
    dy_freq: int,
    dx: float,
    job_id: str
) -> Dict[str, Any]:
    """
    Analyze ruts within polygon by sampling along vertical lines.

    Returns results dictionary with detected ruts and statistics.
    """
    # Calculate dy from frequency
    pix_m = float(np.mean(np.abs(metadata['resolution'])))
    dy = (100.0 / float(dy_freq)) * pix_m

    logger.info(f"Job {job_id}: dy={dy:.4f}m, dx={dx:.4f}m")

    # Get polygon bounds
    min_x, min_y, max_x, max_y = polygon.bounds
    x_steps = np.arange(min_x, max_x + dx, dx)

    logger.info(f"Job {job_id}: Analyzing {len(x_steps)} vertical lines")

    all_ruts = []
    cross_sections = []  # Store sample cross-sections for plotting
    max_cross_sections = 30  # Sample first 30 cross-sections

    # Sample along vertical lines
    for line_idx, x in enumerate(x_steps):
        if line_idx % 100 == 0:
            logger.info(f"Job {job_id}: Processing line {line_idx}/{len(x_steps)}")

        # Create vertical line
        line = LineString([(x, min_y), (x, max_y)])
        clipped_line = line.intersection(polygon)

        if clipped_line.is_empty or clipped_line.length <= 0:
            continue

        # Sample points along line
        length = clipped_line.length
        distances = np.arange(0, length, dy)

        if len(distances) < 2:
            continue

        sample_points = [clipped_line.interpolate(distance) for distance in distances]

        # Extract elevations at sample points
        depths = []
        for pt in sample_points:
            try:
                # Transform point to pixel coordinates
                from rasterio.transform import rowcol
                row, col = rowcol(metadata['transform'], pt.x, pt.y)

                # Check bounds
                if 0 <= row < elevation_data.shape[0] and 0 <= col < elevation_data.shape[1]:
                    depth = elevation_data[row, col]
                    if depth == -32767:  # Legacy safety
                        depth = np.nan
                else:
                    depth = np.nan
            except IndexError:
                depth = np.nan
            depths.append(depth)

        # Filter out NaN
        mask = [not np.isnan(d) for d in depths]
        if sum(mask) < 2:
            continue

        depths_filtered = [d for d, m in zip(depths, mask) if m]
        distances_filtered = [distances[i] for i, m in enumerate(mask) if m]

        # Save first N cross-sections for plotting
        if len(cross_sections) < max_cross_sections:
            cross_sections.append({
                'line_idx': line_idx,
                'x': float(x),
                'distances': [float(d) for d in distances_filtered],
                'elevations': [float(e) for e in depths_filtered]
            })

        # Detect ruts along this line
        ruts = _detect_ruts_along_line(depths_filtered, dy, dx)

        # Add line position to each rut
        for rut in ruts:
            rut['line_x'] = float(x)
            all_ruts.append(rut)

    # Calculate statistics
    total_ruts = len(all_ruts)
    low_count = sum(1 for r in all_ruts if r['severity'] == 'Low')
    medium_count = sum(1 for r in all_ruts if r['severity'] == 'Medium')
    high_count = sum(1 for r in all_ruts if r['severity'] == 'High')
    total_area = sum(r['rut_area_sqft'] for r in all_ruts)

    logger.info(f"Job {job_id}: Detected {total_ruts} ruts (Low={low_count}, Medium={medium_count}, High={high_count})")
    logger.info(f"Job {job_id}: Saved {len(cross_sections)} cross-sections for plotting")

    return {
        'ruts': all_ruts,
        'total_ruts_detected': total_ruts,
        'low_severity_count': low_count,
        'medium_severity_count': medium_count,
        'high_severity_count': high_count,
        'total_area_sqft': float(total_area),
        'cross_sections': cross_sections
    }


def _create_plot_figure(results: Dict[str, Any]) -> go.Figure:
    """
    Create Plotly figure with rut analysis results and elevation cross-sections.
    Returns Plotly Figure object.
    """
    ruts = results['ruts']
    cross_sections = results.get('cross_sections', [])

    if not ruts:
        # Empty plot
        fig = go.Figure()
        fig.add_annotation(
            text="No ruts detected in this area",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20)
        )
        fig.update_layout(
            title="Rut Detection Results",
            template="simple_white",
            height=400
        )
        return fig

    # Calculate number of rows for cross-section plots
    n_cross_sections = len(cross_sections)
    n_cols_cs = min(5, n_cross_sections)  # Max 5 columns
    n_rows_cs = (n_cross_sections + n_cols_cs - 1) // n_cols_cs if n_cross_sections > 0 else 0

    # Total rows: 1 for summary + n_rows_cs for cross-sections
    total_rows = 1 + n_rows_cs

    # Create subplot specs
    specs = [[{'type': 'bar'}, {'type': 'box'}, None, None, None]]  # First row for summary
    for _ in range(n_rows_cs):
        specs.append([{'type': 'scatter'}] * n_cols_cs)

    # Create titles
    subplot_titles = ["Rut Severity Distribution", "Depth Distribution by Severity"]
    if n_cross_sections > 0:
        subplot_titles.extend([f"Section {i+1}" for i in range(n_cross_sections)])

    # Create figure with subplots
    fig = make_subplots(
        rows=total_rows,
        cols=n_cols_cs,
        subplot_titles=subplot_titles,
        specs=specs,
        vertical_spacing=0.08,
        horizontal_spacing=0.05,
        row_heights=[0.3] + [0.7/n_rows_cs]*n_rows_cs if n_rows_cs > 0 else [1.0]
    )

    # Summary plots in first row
    severities = ['Low', 'Medium', 'High']
    counts = [
        results['low_severity_count'],
        results['medium_severity_count'],
        results['high_severity_count']
    ]
    colors = ['green', 'orange', 'red']

    # Bar chart
    fig.add_trace(
        go.Bar(
            x=severities,
            y=counts,
            marker_color=colors,
            text=counts,
            textposition='auto',
            name='Count',
            showlegend=False
        ),
        row=1, col=1
    )

    # Box plot
    for sev, color in zip(severities, colors):
        sev_ruts = [r for r in ruts if r['severity'] == sev]
        if sev_ruts:
            depths = [r['rut_depth_in'] for r in sev_ruts]
            fig.add_trace(
                go.Box(
                    y=depths,
                    name=sev,
                    marker_color=color,
                    showlegend=False
                ),
                row=1, col=2
            )

    # Add elevation cross-section plots
    for idx, cs in enumerate(cross_sections):
        row = 2 + (idx // n_cols_cs)
        col = (idx % n_cols_cs) + 1

        fig.add_trace(
            go.Scatter(
                x=cs['distances'],
                y=cs['elevations'],
                mode='lines',
                line=dict(color='blue', width=1),
                name=f"CS {idx+1}",
                showlegend=False
            ),
            row=row, col=col
        )

        # Update axes for cross-section plots
        fig.update_xaxes(title_text="Distance (m)", row=row, col=col, title_font=dict(size=8))
        fig.update_yaxes(title_text="Elevation (m)", row=row, col=col, title_font=dict(size=8))

    # Update summary plot axes
    fig.update_xaxes(title_text="Severity", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_xaxes(title_text="Severity", row=1, col=2)
    fig.update_yaxes(title_text="Depth (inches)", row=1, col=2)

    # Calculate appropriate height
    plot_height = 400 + (n_rows_cs * 200)

    fig.update_layout(
        title=f"Rut Analysis Results (Total: {results['total_ruts_detected']} ruts, Area: {results['total_area_sqft']:.2f} ft²)<br><sub>Showing {n_cross_sections} cross-section elevation profiles</sub>",
        template="simple_white",
        height=plot_height,
        showlegend=False
    )

    return fig


def _generate_html_plot(results: Dict[str, Any], job_id: str) -> str:
    """
    Generate HTML plot of rut analysis results with elevation cross-sections.
    Returns HTML string.
    """
    fig = _create_plot_figure(results)
    return fig.to_html()


def _generate_pdf_from_results(results: Dict[str, Any], job_id: str, screenshot_base64: Optional[str] = None) -> bytes:
    """
    Generate PDF report from analysis results with 4 pages:
    - Page 1: Screenshot + summary statistics
    - Pages 2-4: Cross-section plots (10 per page)

    Args:
        results: Analysis results dictionary
        job_id: Job ID for logging
        screenshot_base64: Optional base64 encoded screenshot

    Returns:
        PDF content as bytes
    """
    try:
        logger.info(f"Job {job_id}: Generating multi-page PDF report")

        cross_sections = results.get('cross_sections', [])

        # Page 1: Screenshot + Summary
        screenshot_html = ""
        if screenshot_base64:
            screenshot_html = f'<img src="data:image/png;base64,{screenshot_base64}" style="width:100%; max-width:100%; height:auto; margin-bottom: 20px; border: 1px solid #ddd;" />'

        summary_html = f"""
        <div style="background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin-top: 20px;">
            <h2 style="margin-top: 0; color: #333;">Analysis Summary</h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 14px;">
                <div><strong>Total Ruts Detected:</strong> {results['total_ruts_detected']}</div>
                <div><strong>Total Area:</strong> {results['total_area_sqft']:.2f} ft²</div>
                <div style="color: green;"><strong>Low Severity:</strong> {results['low_severity_count']}</div>
                <div style="color: orange;"><strong>Medium Severity:</strong> {results['medium_severity_count']}</div>
                <div style="color: red;"><strong>High Severity:</strong> {results['high_severity_count']}</div>
            </div>
        </div>
        """

        page1_html = f"""
        <div class="page">
            <div class="header">
                <h1>Rut Distress Analysis Report</h1>
                <p>Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p>Job ID: {job_id}</p>
            </div>
            <div class="content">
                {screenshot_html}
                {summary_html}
            </div>
        </div>
        """

        # Pages 2-4: Cross-section plots (10 per page)
        plot_pages_html = ""
        plots_per_page = 10

        for page_idx in range(3):  # 3 pages for plots
            start_idx = page_idx * plots_per_page
            end_idx = min(start_idx + plots_per_page, len(cross_sections))
            page_sections = cross_sections[start_idx:end_idx]

            if not page_sections:
                break

            # Create individual plot figures for this page
            plots_html = ""
            for idx, cs in enumerate(page_sections):
                global_idx = start_idx + idx

                # Create a simple plot using plotly
                try:
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=cs['distances'],
                            y=cs['elevations'],
                            mode='lines',
                            line=dict(color='blue', width=2),
                            name=f"Section {global_idx+1}"
                        )
                    )
                    fig.update_layout(
                        title=f"Cross-Section {global_idx+1}",
                        xaxis_title="Distance (m)",
                        yaxis_title="Elevation (m)",
                        template="simple_white",
                        height=250,
                        width=400,
                        margin=dict(l=50, r=20, t=40, b=40),
                        showlegend=False
                    )

                    # Convert to image
                    img_bytes = fig.to_image(format="png", width=400, height=250)
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                    plots_html += f'<div class="plot-item"><img src="data:image/png;base64,{img_base64}" /></div>'
                except Exception as plot_error:
                    logger.warning(f"Job {job_id}: Failed to create plot {global_idx+1}: {plot_error}")
                    plots_html += f'<div class="plot-item"><p>Plot {global_idx+1} unavailable</p></div>'

            plot_pages_html += f"""
            <div class="page">
                <div class="header">
                    <h2>Cross-Section Elevation Profiles - Page {page_idx + 2}</h2>
                    <p>Showing sections {start_idx+1} to {end_idx}</p>
                </div>
                <div class="plots-grid">
                    {plots_html}
                </div>
            </div>
            """

        # Complete HTML document
        pdf_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4 landscape;
                    margin: 1cm;
                }}
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                }}
                .page {{
                    page-break-after: always;
                    padding: 20px;
                }}
                .page:last-child {{
                    page-break-after: auto;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 20px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #333;
                }}
                .header h1 {{
                    margin: 0 0 10px 0;
                    font-size: 24px;
                }}
                .header h2 {{
                    margin: 0 0 10px 0;
                    font-size: 18px;
                }}
                .header p {{
                    margin: 5px 0;
                    font-size: 12px;
                    color: #666;
                }}
                .content {{
                    margin: 20px 0;
                }}
                .plots-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 15px;
                    margin-top: 20px;
                }}
                .plot-item {{
                    text-align: center;
                    page-break-inside: avoid;
                }}
                .plot-item img {{
                    width: 100%;
                    height: auto;
                    border: 1px solid #ddd;
                }}
                .footer {{
                    position: fixed;
                    bottom: 10px;
                    width: 100%;
                    text-align: center;
                    font-size: 10px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            {page1_html}
            {plot_pages_html}
            <div class="footer">
                <p>Generated by GravelRoad Iowa - Rut Analysis System | Contact: oguntoye@iastate.edu</p>
            </div>
        </body>
        </html>
        """

        # Convert HTML to PDF
        pdf_bytes = HTML(string=pdf_html).write_pdf()

        logger.info(f"Job {job_id}: Multi-page PDF generated successfully, size={len(pdf_bytes)} bytes")
        return pdf_bytes

    except Exception as e:
        logger.error(f"Job {job_id}: Failed to generate PDF: {str(e)}", exc_info=True)
        raise


@celery_app.task(bind=True)
def analyze_ruts_task(self, job_id: str, screenshot_base64: Optional[str] = None):
    """
    Celery task to analyze ruts in a polygon.
    Extracts only the polygon extent from the cloud-stored GeoTIFF.

    Args:
        job_id: Job ID to process
        screenshot_base64: Optional base64 encoded screenshot for PDF report
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting rut analysis job {job_id}")

        # Get job from database
        job = db.query(RutAnalysisJob).filter(RutAnalysisJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Update status
        job.status = "processing"
        job.progress = 5
        db.commit()

        # Get TIFF file info
        tiff_file = db.query(TiffFile).filter(TiffFile.id == job.tiff_file_id).first()
        if not tiff_file:
            raise ValueError(f"TIFF file {job.tiff_file_id} not found")

        # For DEM files, prefer original over COG (better for analysis)
        # COG is optimized for tiling/display, not necessarily for analysis
        if tiff_file.file_type == "DEM":
            s3_key = tiff_file.s3_key
            logger.info(f"Job {job_id}: Using original DEM file for analysis")
        else:
            # For other files, try COG first, fallback to original
            if tiff_file.cog_s3_key:
                s3_key = tiff_file.cog_s3_key
            else:
                s3_key = tiff_file.s3_key

        s3_url = f"s3://{tiff_file.s3_bucket}/{s3_key}"
        logger.info(f"Job {job_id}: Reading from {s3_url}")

        # Extract polygon extent
        job.progress = 10
        db.commit()

        elevation_data, metadata, polygon = _extract_polygon_extent(
            s3_url,
            job.polygon_geojson,
            job.apply_smoothing,
            job.gaussian_sigma
        )

        logger.info(f"Job {job_id}: Extracted polygon extent, shape={elevation_data.shape}")

        # Analyze ruts
        job.progress = 30
        db.commit()

        results = _analyze_ruts_in_polygon(
            elevation_data,
            metadata,
            polygon,
            job.dy_freq,
            job.dx,
            job_id
        )

        # Generate HTML plot
        job.progress = 80
        db.commit()

        html_content = _generate_html_plot(results, job_id)

        # Upload HTML to S3
        job.progress = 90
        db.commit()

        html_s3_key = f"rut_analysis/{job.user_id}/{job_id}/plot.html"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name

        try:
            s3_client.upload_file(
                tmp_path,
                settings.S3_BUCKET_RAW,
                html_s3_key,
                ExtraArgs={'ContentType': 'text/html'}
            )
            # Generate presigned URL (valid for 7 days)
            html_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.S3_BUCKET_RAW,
                    'Key': html_s3_key
                },
                ExpiresIn=604800  # 7 days
            )
        finally:
            os.unlink(tmp_path)

        # Generate and upload PDF
        job.progress = 92
        db.commit()

        try:
            pdf_bytes = _generate_pdf_from_results(results, job_id, screenshot_base64)
            pdf_s3_key = f"rut_analysis/{job.user_id}/{job_id}/report.pdf"

            # Upload PDF to S3
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_pdf:
                tmp_pdf.write(pdf_bytes)
                tmp_pdf_path = tmp_pdf.name

            try:
                s3_client.upload_file(
                    tmp_pdf_path,
                    settings.S3_BUCKET_RAW,
                    pdf_s3_key,
                    ExtraArgs={'ContentType': 'application/pdf'}
                )
                # Generate presigned URL (valid for 7 days)
                pdf_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': settings.S3_BUCKET_RAW,
                        'Key': pdf_s3_key
                    },
                    ExpiresIn=604800  # 7 days
                )
                logger.info(f"Job {job_id}: PDF uploaded to S3: {pdf_s3_key}")
            finally:
                os.unlink(tmp_pdf_path)

        except Exception as pdf_error:
            # Don't fail the entire job if PDF generation fails
            logger.error(f"Job {job_id}: PDF generation failed, but continuing: {str(pdf_error)}")
            pdf_s3_key = None
            pdf_url = None

        # Update job with results
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

        return {
            'job_id': str(job_id),
            'status': 'completed',
            'total_ruts': results['total_ruts_detected']
        }

    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)

        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()

        raise

    finally:
        db.close()
