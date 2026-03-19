"""
Report generation for rut analysis.

Generates HTML interactive plots and multi-page PDF reports
with summary statistics, deduct curve charts, and cross-section profiles.
"""

import base64
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import plotly.graph_objects as go
from weasyprint import HTML

from app.workers.rut.plots import create_plot_figure, create_deduct_curve_plot

logger = logging.getLogger(__name__)


def generate_html_plot(results: Dict[str, Any], job_id: str) -> str:
    """Generate interactive HTML plot of rut analysis results."""
    fig = create_plot_figure(results)
    return fig.to_html()


def _render_plot_image(fig: go.Figure, width: int, height: int) -> str:
    """Render a Plotly figure to a base64 PNG string."""
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    return base64.b64encode(img_bytes).decode('utf-8')


def _build_summary_table(results: Dict[str, Any], density_data: Dict[str, Any]) -> str:
    """Build compact HTML summary table with severity breakdown."""
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
            <td style="font-weight:bold;">{d.get('deduct_value', 0)}</td>
        </tr>"""

    return f"""
    <table style="width:100%; border-collapse:collapse; font-size:12px; margin-top:8px;">
        <tr style="background:#e0e0e0;">
            <th style="padding:6px; text-align:left; border:1px solid #999;">Severity</th>
            <th style="padding:6px; text-align:center; border:1px solid #999;">Count</th>
            <th style="padding:6px; text-align:center; border:1px solid #999;">Area (ft&sup2;)</th>
            <th style="padding:6px; text-align:center; border:1px solid #999;">Density</th>
            <th style="padding:6px; text-align:center; border:1px solid #999;">Deduct</th>
        </tr>
        {rows}
        <tr style="background:#f5f5f5; font-weight:bold;">
            <td style="padding:6px; border:1px solid #999;">Total</td>
            <td style="padding:6px; text-align:center; border:1px solid #999;">{results['total_ruts_detected']}</td>
            <td style="padding:6px; text-align:center; border:1px solid #999;">{results['total_area_sqft']:.1f}</td>
            <td style="padding:6px; text-align:center; border:1px solid #999;">-</td>
            <td style="padding:6px; text-align:center; border:1px solid #999;">-</td>
        </tr>
    </table>"""


def generate_pdf_from_results(
    results: Dict[str, Any],
    job_id: str,
    screenshot_base64: Optional[str] = None
) -> bytes:
    """
    Generate landscape PDF report maximizing plot space:
    - Page 1: Title, summary table, deduct curve (+ optional screenshot)
    - Pages 2+: Cross-section profiles, 6 per page in 3x2 grid
    """
    try:
        logger.info(f"Job {job_id}: Generating PDF report")

        cross_sections = results.get('cross_sections', [])
        density_data = results.get('density_data', {})

        # --- PAGE 1: Summary + Deduct Curve ---
        screenshot_block = ""
        if screenshot_base64:
            screenshot_block = (
                f'<div style="text-align:center; margin-bottom:10px;">'
                f'<img src="data:image/png;base64,{screenshot_base64}" '
                f'style="max-width:100%; max-height:200px; border:1px solid #ccc;" />'
                f'</div>'
            )

        # Deduct curve — render large to fill page
        deduct_plot_html = ""
        if density_data:
            try:
                deduct_fig = create_deduct_curve_plot(density_data)
                deduct_fig.update_layout(
                    margin=dict(l=60, r=30, t=50, b=50),
                    height=420, width=900
                )
                img_b64 = _render_plot_image(deduct_fig, 900, 420)
                deduct_plot_html = (
                    f'<div style="text-align:center;">'
                    f'<img src="data:image/png;base64,{img_b64}" '
                    f'style="width:100%; max-width:100%; height:auto;" />'
                    f'</div>'
                )
            except Exception as e:
                logger.warning(f"Job {job_id}: Deduct curve plot failed: {e}")

        summary_table = _build_summary_table(results, density_data)

        page1 = f"""
        <div class="page">
            <div class="title-bar">
                <h1>Rut Distress Analysis Report</h1>
                <span>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} &bull; Job {job_id[:8]}</span>
            </div>
            {screenshot_block}
            <div style="display:flex; gap:20px; align-items:flex-start;">
                <div style="flex:1; min-width:0;">
                    <h3 style="margin:0 0 4px 0; font-size:13px; color:#333;">Detection Summary</h3>
                    {summary_table}
                    <p style="font-size:11px; color:#666; margin-top:6px;">
                        Polygon Area: {results.get('polygon_area_sqft', 0):.1f} ft&sup2;
                    </p>
                </div>
            </div>
            <h3 style="margin:14px 0 4px 0; font-size:13px; color:#333; text-align:center;">Deduct Value Curves</h3>
            {deduct_plot_html}
        </div>"""

        # --- PAGES 2+: Cross-section plots, 6 per page (3 rows x 2 cols) ---
        plots_per_page = 6
        plot_pages = ""
        total_cs = len(cross_sections)

        for page_start in range(0, total_cs, plots_per_page):
            page_end = min(page_start + plots_per_page, total_cs)
            page_sections = cross_sections[page_start:page_end]

            plots_html = ""
            for idx, cs in enumerate(page_sections):
                global_idx = page_start + idx
                try:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=cs['distances'], y=cs['elevations'],
                        mode='lines', line=dict(color='#1565c0', width=2)
                    ))
                    fig.update_layout(
                        title=dict(text=f"Section {global_idx+1} (x={cs.get('x', 0):.1f}m)",
                                   font=dict(size=11)),
                        xaxis_title="Distance (m)", yaxis_title="Elevation (m)",
                        template="simple_white",
                        margin=dict(l=50, r=15, t=35, b=40),
                        showlegend=False,
                        xaxis=dict(tickfont=dict(size=9), title_font=dict(size=10)),
                        yaxis=dict(tickfont=dict(size=9), title_font=dict(size=10)),
                    )
                    img_b64 = _render_plot_image(fig, 520, 270)
                    plots_html += (
                        f'<div class="cs-plot">'
                        f'<img src="data:image/png;base64,{img_b64}" />'
                        f'</div>'
                    )
                except Exception as e:
                    logger.warning(f"Job {job_id}: Plot {global_idx+1} failed: {e}")
                    plots_html += f'<div class="cs-plot"><p>Section {global_idx+1} unavailable</p></div>'

            page_num = (page_start // plots_per_page) + 2
            plot_pages += f"""
            <div class="page">
                <div class="section-header">
                    Cross-Section Profiles &mdash; Page {page_num}
                    <span style="float:right; font-size:10px; color:#888;">
                        Sections {page_start+1}&ndash;{page_end} of {total_cs}
                    </span>
                </div>
                <div class="cs-grid">
                    {plots_html}
                </div>
            </div>"""

        # --- FULL HTML ---
        pdf_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4 landscape;
                    margin: 8mm;
                }}
                * {{ box-sizing: border-box; }}
                body {{
                    font-family: Arial, Helvetica, sans-serif;
                    margin: 0; padding: 0;
                    color: #222;
                }}
                .page {{
                    page-break-after: always;
                    padding: 6px 10px;
                    height: 100%;
                }}
                .page:last-child {{ page-break-after: auto; }}

                .title-bar {{
                    display: flex;
                    justify-content: space-between;
                    align-items: baseline;
                    border-bottom: 2px solid #333;
                    padding-bottom: 6px;
                    margin-bottom: 10px;
                }}
                .title-bar h1 {{
                    margin: 0; font-size: 18px; color: #111;
                }}
                .title-bar span {{
                    font-size: 10px; color: #666;
                }}

                .section-header {{
                    font-size: 13px;
                    font-weight: bold;
                    color: #333;
                    border-bottom: 1px solid #aaa;
                    padding-bottom: 4px;
                    margin-bottom: 8px;
                }}

                .cs-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    grid-template-rows: repeat(3, 1fr);
                    gap: 8px;
                    height: calc(100% - 30px);
                }}
                .cs-plot {{
                    text-align: center;
                    page-break-inside: avoid;
                }}
                .cs-plot img {{
                    width: 100%;
                    height: auto;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                }}

                @media print {{
                    .page {{ page-break-after: always; }}
                }}
            </style>
        </head>
        <body>
            {page1}
            {plot_pages}
        </body>
        </html>
        """

        pdf_bytes = HTML(string=pdf_html).write_pdf()
        logger.info(f"Job {job_id}: PDF generated, {len(pdf_bytes)} bytes, "
                    f"{1 + (total_cs + plots_per_page - 1) // plots_per_page} pages")
        return pdf_bytes

    except Exception as e:
        logger.error(f"Job {job_id}: Failed to generate PDF: {str(e)}", exc_info=True)
        raise
