"""
HTML report generation for corrugation analysis.

Produces a self-contained HTML file with:
- Summary totals by severity
- Interactive Plotly elevation profiles with peak/valley annotations
- Neighbor frequency summary table and chart (when enabled)
"""

import base64
import logging
import os
from functools import lru_cache
from typing import Dict, Any

from app.workers.corrugation.plots import create_profile_plot, create_summary_figure

logger = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


@lru_cache(maxsize=4)
def _load_asset_b64(filename: str) -> str:
    """Load a static reference image and return base64-encoded contents."""
    path = os.path.join(ASSETS_DIR, filename)
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("utf-8")


def _reference_image_figures() -> str:
    """
    Return two `<figure>` blocks (deduct curves + severity classification)
    suitable for dropping next to the summary table.
    """
    try:
        deduct_b64 = _load_asset_b64("deduct plat.png")
        severity_b64 = _load_asset_b64("refernce.png")
    except Exception as e:
        logger.warning(f"Could not load corrugation reference images: {e}")
        return ""

    return f"""
    <figure style="margin:0; min-width:0;">
        <img src="data:image/png;base64,{deduct_b64}"
             alt="Corrugation deduct plot"
             style="width:100%; height:auto; border:1px solid #ccc; border-radius:4px;" />
        <figcaption style="font-size:11px; color:#555; text-align:center; margin-top:4px;">
            Deduct value plot for corrugation (PCI reference)
        </figcaption>
    </figure>
    <figure style="margin:0; min-width:0;">
        <img src="data:image/png;base64,{severity_b64}"
             alt="Corrugation severity reference"
             style="width:100%; height:auto; border:1px solid #ccc; border-radius:4px;" />
        <figcaption style="font-size:11px; color:#555; text-align:center; margin-top:4px;">
            Severity reference for corrugation
        </figcaption>
    </figure>"""


def generate_html_report(results: Dict[str, Any], job_id: str) -> str:
    """Generate interactive HTML report for corrugation analysis."""
    totals = results["totals_ft2"]
    counts = results["counts"]
    profiles = results.get("profiles", [])
    polygon_area_sqft = float(results.get("polygon_area_sqft", 0.0) or 0.0)

    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append("<title>Corrugation Severity Report</title>")
    parts.append("<script src='https://cdn.plot.ly/plotly-2.27.0.min.js'></script>")
    parts.append("""<style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #fafafa; color: #222; }
        h1, h2, h3 { color: #333; }
        .meta { color: #666; font-size: 12px; margin-bottom: 18px; }
        table { border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ccc; padding: 8px 14px; text-align: left; }
        th { background: #e0e0e0; }
        .totals-row { font-weight: bold; background: #f5f5f5; }
        .summary-band {
            display: grid;
            grid-template-columns: minmax(340px, 1fr) minmax(240px, 1fr) minmax(240px, 1fr);
            gap: 16px;
            align-items: start;
            margin-top: 12px;
        }
        .summary-band > * { min-width: 0; }
        .summary-band table { width: 100%; margin: 0; }
        @media (max-width: 1000px) {
            .summary-band { grid-template-columns: 1fr; }
        }
        .chart-wrap { width: 100%; margin-top: 8px; }
        .chart-wrap .plotly-graph-div,
        .chart-wrap .js-plotly-plot { width: 100% !important; }
        .profile-card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin: 12px 0; background: white; }
    </style>""")
    parts.append("</head><body>")
    parts.append(f"<h1>Corrugation Severity Report</h1>")
    parts.append(
        f"<div class='meta'>Job ID: {job_id} &middot; "
        f"Polygon Area: {polygon_area_sqft:.1f} ft&sup2;</div>"
    )

    # Summary — density table side-by-side with the manual reference images
    total_area = sum(totals.values())
    total_count = sum(counts.values())
    parts.append("<h2>Summary</h2>")
    parts.append("<div class='summary-band'>")
    parts.append("<table>")
    parts.append(
        "<thead><tr>"
        "<th>Severity</th><th>Count</th><th>Area (ft&sup2;)</th><th>Density</th>"
        "</tr></thead><tbody>"
    )
    for sev_key, label, color in [
        ("LOW", "Low", "#2e7d32"),
        ("MEDIUM", "Medium", "#e65100"),
        ("HIGH", "High", "#c62828"),
    ]:
        cnt = counts.get(sev_key, 0)
        area = float(totals.get(sev_key, 0.0) or 0.0)
        density = (area / polygon_area_sqft * 100.0) if polygon_area_sqft > 0 else 0.0
        parts.append(
            f"<tr><td style='color:{color}; font-weight:bold;'>{label}</td>"
            f"<td>{cnt}</td><td>{area:.1f}</td><td>{density:.2f}%</td></tr>"
        )
    parts.append(
        f"<tr class='totals-row'><td>Total</td><td>{total_count}</td>"
        f"<td>{total_area:.1f}</td><td>&mdash;</td></tr>"
    )
    parts.append("</tbody></table>")
    parts.append(_reference_image_figures())
    parts.append("</div>")

    # Summary chart — full width below the summary band
    summary_html = create_summary_figure(results)
    parts.append(f"<h2>Summary Chart</h2>")
    parts.append(f"<div class='chart-wrap'>{summary_html}</div>")

    # Transect profile plots
    if profiles:
        parts.append(f"<h2>Transect Profiles ({len(profiles)} shown)</h2>")
        for profile in profiles:
            plot_html = create_profile_plot(profile)
            parts.append(f"<div class='profile-card'>{plot_html}</div>")

    parts.append("</body></html>")
    return "\n".join(parts)
