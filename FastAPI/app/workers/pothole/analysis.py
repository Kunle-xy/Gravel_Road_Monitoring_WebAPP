"""
Pothole analysis — extract elevation from DEM polygon,
calculate depth/width, classify severity, generate 3D plot.
"""

import numpy as np
import logging
from scipy.spatial import ConvexHull

logger = logging.getLogger(__name__)

# Severity matrix: severity[depth_idx][width_idx]
# Depth: 0 = 0.5-2in, 1 = 2-4in, 2 = 4+in
# Width: 0 = <1ft, 1 = 1-2ft, 2 = 2-3ft, 3 = >3ft
SEVERITY_MATRIX = [
    ["Low", "Low", "Medium", "Medium"],    # 0.5-2 in depth
    ["Low", "Medium", "Medium", "High"],    # 2-4 in depth
    ["Medium", "High", "High", "High"],     # 4+ in depth
]


def classify_severity(depth_inches: float, width_feet: float) -> str:
    """Classify pothole severity based on depth and width."""
    if depth_inches < 0.5:
        return "None"

    # Depth index
    if depth_inches < 2:
        di = 0
    elif depth_inches < 4:
        di = 1
    else:
        di = 2

    # Width index
    if width_feet < 1:
        wi = 0
    elif width_feet < 2:
        wi = 1
    elif width_feet < 3:
        wi = 2
    else:
        wi = 3

    return SEVERITY_MATRIX[di][wi]


def analyze_pothole(elevation_data: np.ndarray, pixel_resolution: float) -> dict:
    """
    Analyze pothole from extracted elevation data.

    Args:
        elevation_data: 2D numpy array of elevation values (meters)
        pixel_resolution: meters per pixel

    Returns:
        dict with depth_inches, width_inches, width_feet, severity, stats
    """
    valid = elevation_data[~np.isnan(elevation_data)]
    if len(valid) == 0:
        raise ValueError("No valid elevation data in polygon")

    max_val = float(np.nanmax(elevation_data))
    min_val = float(np.nanmin(elevation_data))
    depth_m = max_val - min_val
    depth_inches = depth_m * 39.3701

    # Width via convex hull of valid pixels
    valid_pixels = np.where(~np.isnan(elevation_data))
    points = np.vstack((valid_pixels[1], valid_pixels[0])).T

    if len(points) < 3:
        raise ValueError("Pothole region too small — need at least 3 valid pixels")

    hull = ConvexHull(points)
    hull_points = points[hull.vertices]

    max_width_pixels = 0.0
    for i in range(len(hull_points)):
        for j in range(i + 1, len(hull_points)):
            dist = float(np.sqrt(np.sum((hull_points[i] - hull_points[j]) ** 2)))
            max_width_pixels = max(max_width_pixels, dist)

    width_m = max_width_pixels * pixel_resolution
    width_inches = width_m * 39.3701
    width_feet = width_m * 3.28084

    severity = classify_severity(depth_inches, width_feet)

    return {
        "depth_m": round(depth_m, 4),
        "depth_inches": round(depth_inches, 2),
        "width_m": round(width_m, 4),
        "width_inches": round(width_inches, 2),
        "width_feet": round(width_feet, 2),
        "severity": severity,
        "min_elevation": round(min_val, 4),
        "max_elevation": round(max_val, 4),
        "pixel_resolution": round(pixel_resolution, 6),
    }


def generate_pothole_html(elevation_data: np.ndarray, results: dict, job_id: str) -> str:
    """Generate an interactive HTML report with 3D Plotly plot and results table."""
    import plotly.graph_objects as go
    import plotly.io as pio

    # rasterio returns the window as [row, col] (row 0 = North, col 0 = West).
    # Plotting that directly leaves the footprint rotated ~90° vs. the map;
    # transposing the grid (swap X<->Y) aligns the surface with the drawn
    # polygon. Validated against real potholes on the map.
    z = elevation_data.T
    nrows, ncols = z.shape
    X, Y = np.meshgrid(np.arange(0, ncols), np.arange(0, nrows))

    fig = go.Figure(data=[
        go.Surface(
            z=z,
            x=X, y=Y,
            colorscale="Viridis",
            opacity=0.9,
            colorbar=dict(title="Elevation (m)"),
        )
    ])

    fig.update_layout(
        scene=dict(
            xaxis_title="X (pixels)",
            yaxis_title="Y (pixels)",
            zaxis_title="Elevation (m)",
            zaxis=dict(showspikes=False),
        ),
        width=800,
        height=550,
        margin=dict(l=0, r=0, t=0, b=0),
    )

    plot_html = pio.to_html(fig, full_html=False, include_plotlyjs="cdn")

    sev = results["severity"]
    sev_color = {"Low": "#22c55e", "Medium": "#f97316", "High": "#ef4444", "None": "#94a3b8"}[sev]

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pothole Analysis</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 16px; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 18px; text-align: center; margin-bottom: 16px; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px; border: 1px solid #334155; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ color: #94a3b8; font-weight: 600; }}
  td {{ color: #e2e8f0; }}
  .severity {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 12px; color: white; background: {sev_color}; }}
  .matrix {{ font-size: 11px; margin-top: 12px; }}
  .matrix th, .matrix td {{ padding: 4px 8px; text-align: center; }}
  .matrix .active {{ background: {sev_color}33; font-weight: bold; }}
  .L {{ color: #22c55e; }} .M {{ color: #f97316; }} .H {{ color: #ef4444; }}
</style></head><body>
<div class="container">
  <h1>Pothole Analysis Report</h1>

  <div class="card">{plot_html}</div>

  <div class="card">
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Depth</td><td><strong>{results['depth_inches']:.2f} inches</strong> ({results['depth_m']:.4f} m)</td></tr>
      <tr><td>Width (max diameter)</td><td><strong>{results['width_inches']:.2f} inches</strong> ({results['width_feet']:.2f} ft / {results['width_m']:.4f} m)</td></tr>
      <tr><td>Min Elevation</td><td>{results['min_elevation']:.4f} m</td></tr>
      <tr><td>Max Elevation</td><td>{results['max_elevation']:.4f} m</td></tr>
      <tr><td>Pixel Resolution</td><td>{results['pixel_resolution']:.6f} m/px</td></tr>
      <tr><td>Severity</td><td><span class="severity">{sev}</span></td></tr>
    </table>
  </div>

  <div class="card">
    <h3 style="font-size:13px;margin:0 0 8px 0;color:#94a3b8;">Severity Classification Matrix</h3>
    <table class="matrix">
      <tr><th>Depth \\ Width</th><th>&lt;1 ft</th><th>1-2 ft</th><th>2-3 ft</th><th>&gt;3 ft</th></tr>
      <tr><td>0.5-2 in</td>{''.join(f'<td class="{"active" if _match_cell(results, 0, ci) else ""} {SEVERITY_MATRIX[0][ci][0]}">{SEVERITY_MATRIX[0][ci]}</td>' for ci in range(4))}</tr>
      <tr><td>2-4 in</td>{''.join(f'<td class="{"active" if _match_cell(results, 1, ci) else ""} {SEVERITY_MATRIX[1][ci][0]}">{SEVERITY_MATRIX[1][ci]}</td>' for ci in range(4))}</tr>
      <tr><td>4+ in</td>{''.join(f'<td class="{"active" if _match_cell(results, 2, ci) else ""} {SEVERITY_MATRIX[2][ci][0]}">{SEVERITY_MATRIX[2][ci]}</td>' for ci in range(4))}</tr>
    </table>
  </div>
</div></body></html>"""

    return html


def _match_cell(results: dict, depth_idx: int, width_idx: int) -> bool:
    """Check if the current result matches a cell in the severity matrix."""
    d = results["depth_inches"]
    w = results["width_feet"]

    if d < 0.5:
        return False
    di = 0 if d < 2 else (1 if d < 4 else 2)
    wi = 0 if w < 1 else (1 if w < 2 else (2 if w < 3 else 3))

    return di == depth_idx and wi == width_idx
