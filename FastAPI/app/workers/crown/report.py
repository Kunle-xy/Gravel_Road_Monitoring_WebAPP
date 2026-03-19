"""
Report generation for crown distress analysis.

Generates HTML interactive reports with:
- Summary table of linear feet by severity
- Elevation profile plots with slope annotations
- Optional neighbor frequency summary
"""

import base64
import logging
from typing import Dict, Any

from app.workers.crown.plots import create_profile_plot, create_summary_figure, create_neighbor_summary_figure

logger = logging.getLogger(__name__)


def _render_plot_b64(fig, width: int, height: int) -> str:
    """Render Plotly figure to base64 PNG."""
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    return base64.b64encode(img_bytes).decode('utf-8')


def generate_html_report(results: Dict[str, Any], job_id: str) -> str:
    """
    Generate interactive HTML report for crown distress analysis.
    Returns HTML string with embedded Plotly plots.
    """
    totals = results['totals_ft']
    counts = results['counts']
    profiles = results.get('profiles', [])
    neighbor_eval = results.get('neighbor_eval', False)

    # Summary figure
    if neighbor_eval:
        summary_fig = create_neighbor_summary_figure(results)
    else:
        summary_fig = create_summary_figure(results)
    summary_html = summary_fig.to_html(full_html=False, include_plotlyjs='cdn')

    # Profile plots (up to 20)
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

    # Summary table
    total_ft = sum(totals.values())
    table_rows = ""
    for sev, color in [("Low", "#2e7d32"), ("Medium", "#e65100"), ("High", "#c62828")]:
        table_rows += f"""
        <tr>
            <td style="color:{color}; font-weight:bold;">{sev}</td>
            <td>{totals.get(sev, 0):.2f}</td>
            <td>{counts.get(sev, 0)}</td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Crown Distress Report - Job {job_id[:8]}</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #fafafa; }}
            h1 {{ color: #333; margin-bottom: 4px; }}
            .meta {{ color: #666; font-size: 12px; margin-bottom: 20px; }}
            table {{ border-collapse: collapse; margin: 10px 0; }}
            th, td {{ border: 1px solid #ccc; padding: 8px 14px; text-align: left; }}
            th {{ background: #e0e0e0; }}
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

        <h2>Summary</h2>
        <table>
            <thead><tr><th>Severity</th><th>Linear Feet</th><th>Line Count</th></tr></thead>
            <tbody>
                {table_rows}
                <tr style="font-weight:bold; background:#f5f5f5;">
                    <td>Total</td><td>{total_ft:.2f}</td><td>{sum(counts.values())}</td>
                </tr>
            </tbody>
        </table>

        <h2>{'Frequency Neighbor Summary' if neighbor_eval else 'Summary Chart'}</h2>
        {summary_html}

        <h2>Elevation Profiles (Top {min(len(profiles), 20)} by severity)</h2>
        <div class="profiles-grid">
            {profile_plots_html if profile_plots_html else '<p>No profiles available</p>'}
        </div>
    </body>
    </html>
    """
    return html
