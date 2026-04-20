"""
Report generation for crown distress analysis.

Generates HTML interactive reports with:
- Density table + Iowa DOT crown severity matrix + reference images, in a
  side-by-side summary band.
- Elevation profile plots with slope annotations.
- Optional neighbor frequency summary.
"""

import base64
import logging
import os
from functools import lru_cache
from typing import Dict, Any

from app.workers.crown.plots import create_profile_plot, create_summary_figure, create_neighbor_summary_figure

logger = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def _render_plot_b64(fig, width: int, height: int) -> str:
    """Render Plotly figure to base64 PNG."""
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    return base64.b64encode(img_bytes).decode('utf-8')


@lru_cache(maxsize=8)
def _load_asset_b64(filename: str) -> str:
    """Load a static reference image and return base64-encoded contents."""
    path = os.path.join(ASSETS_DIR, filename)
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("utf-8")


def _reference_image_blocks() -> list[str]:
    """
    Pick up any *.png / *.jpg / *.jpeg in the crown assets folder and render
    each as a standalone <figure>. Returns a list so the caller can place
    each figure into its own grid cell (keeping summary+matrix+images on a
    single row instead of stacking images vertically in one cell).
    """
    if not os.path.isdir(ASSETS_DIR):
        return []
    try:
        names = sorted(
            f for f in os.listdir(ASSETS_DIR)
            if f.lower().endswith((".png", ".jpg", ".jpeg"))
        )
    except Exception as e:
        logger.warning(f"Could not list crown assets: {e}")
        return []

    blocks: list[str] = []
    for name in names:
        try:
            b64 = _load_asset_b64(name)
        except Exception as e:
            logger.warning(f"Could not load crown asset {name}: {e}")
            continue
        caption = os.path.splitext(name)[0].replace("_", " ").replace("-", " ").strip().title()
        mime = "image/jpeg" if name.lower().endswith((".jpg", ".jpeg")) else "image/png"
        blocks.append(
            f"""
            <figure style="margin:0; min-width:0;">
                <img src="data:{mime};base64,{b64}"
                     alt="{caption}"
                     style="width:100%; height:auto; max-height:220px; object-fit:contain; border:1px solid #ccc; border-radius:4px;" />
                <figcaption style="font-size:11px; color:#555; text-align:center; margin-top:4px;">
                    {caption}
                </figcaption>
            </figure>"""
        )
    return blocks


def _crown_matrix_html() -> str:
    """
    Iowa DOT crown severity matrix: slope band × rut severity.
    Identical layout to the ArcPy reference script.
    """
    def cell(value):
        if value is None:
            return "<td>&mdash;</td>"
        cls = {"Low": "low", "Medium": "med", "High": "high"}[value]
        return f"<td class='{cls}'>{value}</td>"

    rows = [
        ("Inverted (&#8722;/+)", ["High", "High", "High", "High"]),
        ("&gt; 6%",              [None,   None,   "Low",    "Medium"]),
        ("4 &lt; x &le; 6%",     [None,   "Low",  "Medium", "High"]),
        ("2 &lt; x &le; 4%",     ["Low",  "Medium", "High", "High"]),
        ("0 &le; x &le; 2%",     ["Medium", "High", "High", "High"]),
    ]
    rows_html = "\n".join(
        f"<tr><td class='label'>{label}</td>{''.join(cell(v) for v in cells)}</tr>"
        for label, cells in rows
    )
    return f"""
    <table class="matrix">
        <thead>
            <tr>
                <th rowspan='2'>Slope (abs avg %)</th>
                <th colspan='4'>Rut severity</th>
            </tr>
            <tr>
                <th>None</th><th>Low</th><th>Medium</th><th>High</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>"""


def generate_html_report(results: Dict[str, Any], job_id: str) -> str:
    """
    Generate interactive HTML report for crown distress analysis.
    Returns HTML string with embedded Plotly plots.
    """
    totals = results['totals_ft']
    counts = results['counts']
    profiles = results.get('profiles', [])
    neighbor_eval = results.get('neighbor_eval', False)
    polygon_length_ft = float(results.get('polygon_length_ft', 0.0) or 0.0)

    if neighbor_eval:
        summary_fig = create_neighbor_summary_figure(results)
    else:
        summary_fig = create_summary_figure(results)
    summary_fig.update_layout(autosize=True, width=None)
    summary_html = summary_fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True},
        default_width='100%',
    )

    profile_plots_html = ""
    for i, profile in enumerate(profiles[:20]):
        fig = create_profile_plot(profile)
        plot_html = fig.to_html(full_html=False, include_plotlyjs=False)
        crown = profile.get('crown', 'None')
        rut = profile.get('rut_sev', 'None')
        header = f"Line {profile['line_idx']} | x={profile['x']:.2f}m | Crown: {crown} | Rut: {rut}"
        profile_plots_html += f"""
        <div class="profile-card">
            <div class="profile-header">{header}</div>
            <div class="profile-meta">
                Left slope: {profile.get('m_left', 0):.2f}% ({profile.get('s_left', '?')}) |
                Right slope: {profile.get('m_right', 0):.2f}% ({profile.get('s_right', '?')}) |
                Avg: {profile.get('m_avg', 0):.2f}%
            </div>
            {plot_html}
        </div>
        """

    total_ft = sum(totals.values())

    def _density(sev_ft: float) -> str:
        if polygon_length_ft > 0:
            return f"{(sev_ft / polygon_length_ft * 100.0):.2f}%"
        return "&mdash;"

    table_rows = ""
    for sev, color in [("Low", "#2e7d32"), ("Medium", "#e65100"), ("High", "#c62828")]:
        ft_val = totals.get(sev, 0.0)
        table_rows += f"""
        <tr>
            <td style="color:{color}; font-weight:bold;">{sev}</td>
            <td>{ft_val:.2f}</td>
            <td>{counts.get(sev, 0)}</td>
            <td>{_density(ft_val)}</td>
        </tr>"""

    matrix_html = _crown_matrix_html()
    image_blocks = _reference_image_blocks()
    # One grid column per item so summary + matrix + each image land on a
    # single horizontal row.
    image_cells = "".join(f"<div class='ref'>{b}</div>" for b in image_blocks)
    n_cells = 2 + len(image_blocks)  # table + matrix + N images
    grid_cols = " ".join(["minmax(240px, 1fr)"] * n_cells)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Crown Distress Report - Job {job_id[:8]}</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #fafafa; color: #222; }}
            h1 {{ color: #333; margin-bottom: 4px; }}
            h2 {{ color: #333; margin-top: 28px; }}
            .meta {{ color: #666; font-size: 12px; margin-bottom: 20px; }}
            table {{ border-collapse: collapse; margin: 10px 0; }}
            th, td {{ border: 1px solid #ccc; padding: 8px 14px; text-align: left; }}
            th {{ background: #e0e0e0; }}
            /* Summary band: density table | matrix | each reference image.
               One horizontal row, one column per item. */
            .summary-band {{
                display: grid;
                grid-template-columns: {grid_cols};
                gap: 12px;
                align-items: start;
                margin-top: 12px;
            }}
            .summary-band > * {{ min-width: 0; }}
            .summary-band table {{ width: 100%; margin: 0; font-size: 12px; }}
            .summary-band table th, .summary-band table td {{ padding: 6px 8px; }}
            .ref figure img {{ max-height: 220px; }}
            /* Iowa DOT crown-severity matrix */
            table.matrix td, table.matrix th {{ text-align: center; padding: 6px 10px; font-size: 12px; }}
            table.matrix td.label {{ text-align: left; font-weight: 600; background: #f7f7f7; }}
            table.matrix td.low {{ background: #d0e8ff; }}
            table.matrix td.med {{ background: #ffe0b0; }}
            table.matrix td.high {{ background: #ffd0d0; font-weight: bold; }}
            .chart-wrap {{ width: 100%; margin-top: 8px; }}
            .chart-wrap .plotly-graph-div,
            .chart-wrap .js-plotly-plot {{ width: 100% !important; }}
            .profiles-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
                gap: 16px; margin-top: 20px;
            }}
            .profile-card {{
                border: 1px solid #ddd; border-radius: 8px;
                padding: 12px; background: white;
            }}
            .profile-header {{ font-weight: bold; font-size: 13px; margin-bottom: 4px; }}
            .profile-meta {{ font-size: 11px; color: #555; font-family: monospace; margin-bottom: 8px; }}
        </style>
    </head>
    <body>
        <h1>Crown Distress Report</h1>
        <div class="meta">Job ID: {job_id}</div>

        <h2>Summary <span style="font-size:12px; color:#666; font-weight:normal;">
            (polygon length {polygon_length_ft:.2f} ft)
        </span></h2>
        <div class="summary-band">
            <table>
                <thead>
                    <tr>
                        <th>Severity</th><th>Linear Feet</th><th>Line Count</th><th>Density</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                    <tr style="font-weight:bold; background:#f5f5f5;">
                        <td>Total</td>
                        <td>{total_ft:.2f}</td>
                        <td>{sum(counts.values())}</td>
                        <td>{_density(total_ft)}</td>
                    </tr>
                </tbody>
            </table>
            <div>
                <div style="font-size:12px; color:#555; margin-bottom:6px;">
                    Iowa DOT crown severity matrix
                </div>
                {matrix_html}
            </div>
            {image_cells}
        </div>

        <h2>{'Frequency Neighbor Summary' if neighbor_eval else 'Summary Chart'}</h2>
        <div class="chart-wrap">{summary_html}</div>

        <h2>Elevation Profiles (Top {min(len(profiles), 20)} by severity)</h2>
        <div class="profiles-grid">
            {profile_plots_html if profile_plots_html else '<p>No profiles available</p>'}
        </div>
    </body>
    </html>
    """
    return html
