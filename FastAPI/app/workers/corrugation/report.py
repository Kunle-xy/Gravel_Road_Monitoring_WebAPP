"""
HTML report generation for corrugation analysis.

Produces a self-contained HTML file with:
- Summary totals by severity
- Interactive Plotly elevation profiles with peak/valley annotations
- Neighbor frequency summary table and chart (when enabled)
"""

import logging
from typing import Dict, Any

from app.workers.corrugation.plots import create_profile_plot, create_summary_figure, create_neighbor_summary_plot

logger = logging.getLogger(__name__)


def generate_html_report(results: Dict[str, Any], job_id: str) -> str:
    """Generate interactive HTML report for corrugation analysis."""
    totals = results["totals_ft2"]
    counts = results["counts"]
    profiles = results.get("profiles", [])
    neighbor_eval = results.get("neighbor_eval", False)
    neighbor_summary = results.get("neighbor_summary", [])

    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append("<title>Corrugation Severity Report</title>")
    parts.append("<script src='https://cdn.plot.ly/plotly-2.27.0.min.js'></script>")
    parts.append("""<style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #fafafa; }
        h1, h2, h3 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin-top: 12px; }
        th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
        th { background: #f0f8ff; }
        .box { padding: 12px; border: 1px solid #ddd; border-radius: 6px; background: #fcfcff; margin: 12px 0; }
        .pill { display: inline-block; margin-right: 10px; padding: 6px 10px; border-radius: 999px; background: #eef2ff; border: 1px solid #d0d7ff; }
        .profile-card { border: 1px solid #ddd; border-radius: 6px; padding: 8px; margin: 12px 0; background: white; }
    </style>""")
    parts.append("</head><body>")
    parts.append(f"<h1>Corrugation Severity Report</h1>")
    parts.append(f"<p style='color:#666; font-size:12px;'>Job ID: {job_id}</p>")

    # Summary
    total_area = sum(totals.values())
    parts.append("<div class='box'><b>Totals across all transects</b><br>")
    for sev, color in [("LOW", "#2e7d32"), ("MEDIUM", "#e65100"), ("HIGH", "#c62828")]:
        cnt = counts.get(sev, 0)
        area = totals.get(sev, 0)
        parts.append(f"<span class='pill' style='border-color:{color};'>"
                     f"<b style='color:{color};'>{sev}</b>: {cnt} segments, {area:.2f} ft&sup2;</span>")
    parts.append(f"<br><br><b>Total area: {total_area:.2f} ft&sup2;</b></div>")

    # Summary chart
    summary_html = create_summary_figure(results)
    parts.append(f"<div>{summary_html}</div>")

    # Neighbor summary
    if neighbor_eval and neighbor_summary:
        parts.append("<h2>Neighbor Frequency Summary</h2>")
        cols = ["frequency", "severity", "count", "mean_depth_in", "std_depth_in", "total_area_ft2"]
        headers = ["Frequency", "Severity", "Count", "Mean Depth (in)", "Std Depth (in)", "Total Area (ft2)"]
        parts.append("<table><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")
        for r in neighbor_summary:
            parts.append("<tr>" + "".join(
                f"<td>{r.get(c, ''):.2f}</td>" if isinstance(r.get(c), float)
                else f"<td>{r.get(c, '')}</td>" for c in cols
            ) + "</tr>")
        parts.append("</table>")

        neighbor_plot = create_neighbor_summary_plot(neighbor_summary)
        parts.append(f"<h2>Area by Severity (Mean +/- Std)</h2><div>{neighbor_plot}</div>")

    # Profiles (only when neighbor eval is off)
    if not neighbor_eval and profiles:
        parts.append(f"<h2>Transect Profiles ({len(profiles)} shown)</h2>")
        for profile in profiles:
            plot_html = create_profile_plot(profile)
            parts.append(f"<div class='profile-card'>{plot_html}</div>")

    parts.append("</body></html>")
    return "\n".join(parts)
