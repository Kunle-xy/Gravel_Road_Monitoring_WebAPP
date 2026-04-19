"""
HTML report generation for rut analysis.

Crown-style interactive HTML:
- Density table (severity / count / area / density %)
- Summary bar chart (count + area)
- Grid of profile plots that show where the ruts are on each sampling line
"""

import base64
import logging
import os
from functools import lru_cache
from typing import Dict, Any

from app.workers.rut.plots import (
    create_profile_plot,
    create_summary_figure,
    create_neighbor_summary_figure,
)

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
    suitable for inserting into a flex/grid row.
    """
    try:
        deduct_b64 = _load_asset_b64("rut_deduct_curve.png")
        severity_b64 = _load_asset_b64("rut_severity_classes.png")
    except Exception as e:
        logger.warning(f"Could not load reference images: {e}")
        return ""

    return f"""
    <figure style="margin:0; min-width:0;">
        <img src="data:image/png;base64,{deduct_b64}"
             alt="Rut deduct value curves"
             style="width:100%; height:auto; border:1px solid #ccc; border-radius:4px;" />
        <figcaption style="font-size:11px; color:#555; text-align:center; margin-top:4px;">
            Deduct value curves for ruts (PCI reference)
        </figcaption>
    </figure>
    <figure style="margin:0; min-width:0;">
        <img src="data:image/png;base64,{severity_b64}"
             alt="Rut severity classification"
             style="width:100%; height:auto; border:1px solid #ccc; border-radius:4px;" />
        <figcaption style="font-size:11px; color:#555; text-align:center; margin-top:4px;">
            Severity classes by depth (Low &lt; 1″, Medium 1–3″, High &gt; 3″)
        </figcaption>
    </figure>"""


def _build_density_table_rows(results: Dict[str, Any]) -> str:
    """Density table rows: severity / count / area / density %. No deduct."""
    density_data = results.get('density_data') or {}
    rows = ""
    for sev, color in [("Low", "#2e7d32"), ("Medium", "#e65100"), ("High", "#c62828")]:
        d = density_data.get(sev, {})
        count_key = f"{sev.lower()}_severity_count"
        rows += f"""
        <tr>
            <td style="color:{color}; font-weight:bold;">{sev}</td>
            <td>{results.get(count_key, 0)}</td>
            <td>{d.get('area_sqft', 0):.1f}</td>
            <td>{d.get('density_percent', 0):.2f}%</td>
        </tr>"""
    return rows


def generate_html_plot(results: Dict[str, Any], job_id: str) -> str:
    """
    Build the interactive HTML report.

    Layout:
        1. Title + meta
        2. Density table (severity / count / area / density %)
        3. Summary chart (count + area bars)
        4. Grid of profile plots highlighting where each rut sits
    """
    cross_sections = results.get('cross_sections', []) or []
    polygon_area_sqft = results.get('polygon_area_sqft', 0.0)
    total_ruts = results.get('total_ruts_detected', 0)
    total_area = results.get('total_area_sqft', 0.0)
    neighbor_eval = bool(results.get('neighbor_eval'))

    # Summary chart — swap in the per-frequency view when neighbor eval is on
    summary_fig = (
        create_neighbor_summary_figure(results) if neighbor_eval
        else create_summary_figure(results)
    )
    summary_fig.update_layout(autosize=True, width=None)
    summary_html = summary_fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True},
        default_width='100%',
    )
    summary_heading = "Frequency Neighbor Summary" if neighbor_eval else "Summary Chart"

    # Profile plots
    profile_blocks = ""
    for i, cs in enumerate(cross_sections):
        try:
            fig = create_profile_plot(cs)
            plot_html = fig.to_html(full_html=False, include_plotlyjs=False)
            n_ruts = len(cs.get('ruts') or [])
            header = f"Line {i + 1} &nbsp;|&nbsp; x = {cs.get('x', 0):.2f} m &nbsp;|&nbsp; {n_ruts} rut{'s' if n_ruts != 1 else ''}"
            profile_blocks += f"""
            <div class="profile-card">
                <div class="profile-header">{header}</div>
                {plot_html}
            </div>
            """
        except Exception as e:
            logger.warning(f"Job {job_id}: profile plot {i} failed: {e}")

    table_rows = _build_density_table_rows(results)
    reference_figures = _reference_image_figures()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Rut Distress Report &mdash; Job {job_id[:8]}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #fafafa; color: #222; }}
            h1 {{ color: #333; margin-bottom: 4px; }}
            h2 {{ color: #333; margin-top: 28px; }}
            .meta {{ color: #666; font-size: 12px; margin-bottom: 18px; }}
            table {{ border-collapse: collapse; margin: 10px 0; }}
            th, td {{ border: 1px solid #ccc; padding: 8px 14px; text-align: left; }}
            th {{ background: #e0e0e0; }}
            .totals-row {{ font-weight: bold; background: #f5f5f5; }}
            /* Density table + reference images, side by side */
            .summary-band {{
                display: grid;
                grid-template-columns: minmax(340px, 1fr) minmax(240px, 1fr) minmax(240px, 1fr);
                gap: 16px;
                align-items: start;
                margin-top: 12px;
            }}
            .summary-band > * {{ min-width: 0; }}
            .summary-band table {{ width: 100%; margin: 0; }}
            @media (max-width: 1000px) {{
                .summary-band {{ grid-template-columns: 1fr; }}
            }}
            /* The chart gets the full width of the page */
            .chart-wrap {{
                width: 100%;
                margin-top: 8px;
            }}
            .chart-wrap .plotly-graph-div,
            .chart-wrap .js-plotly-plot {{
                width: 100% !important;
            }}
            .profiles-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(520px, 1fr));
                gap: 16px;
                margin-top: 12px;
            }}
            .profile-card {{
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
                background: white;
            }}
            .profile-header {{
                font-weight: bold;
                font-size: 13px;
                margin-bottom: 6px;
                color: #333;
            }}
        </style>
    </head>
    <body>
        <h1>Rut Distress Report</h1>
        <div class="meta">Job ID: {job_id} &middot; Polygon Area: {polygon_area_sqft:.1f} ft&sup2;</div>

        <h2>Summary</h2>
        <div class="summary-band">
            <table>
                <thead>
                    <tr>
                        <th>Severity</th>
                        <th>Count</th>
                        <th>Area (ft&sup2;)</th>
                        <th>Density</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                    <tr class="totals-row">
                        <td>Total</td>
                        <td>{total_ruts}</td>
                        <td>{total_area:.1f}</td>
                        <td>&mdash;</td>
                    </tr>
                </tbody>
            </table>
            {reference_figures}
        </div>

        <h2>{summary_heading}</h2>
        <div class="chart-wrap">{summary_html}</div>

        <h2>Rut Locations &mdash; Sampled Profiles</h2>
        <div class="profiles-grid">
            {profile_blocks if profile_blocks else '<p>No rut profiles available</p>'}
        </div>
    </body>
    </html>
    """
    return html
