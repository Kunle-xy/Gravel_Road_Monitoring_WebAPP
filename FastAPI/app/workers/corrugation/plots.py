"""
Plotly chart generation for corrugation analysis.

Creates interactive plots with:
- Elevation profiles with smoothed line, severity overlay, peak/valley annotations
- Neighbor frequency summary (total area mean ± std by severity)
- Summary bar charts
"""

import logging
from typing import Dict, List, Any

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

logger = logging.getLogger(__name__)


def create_profile_plot(profile: Dict[str, Any]) -> str:
    """
    Create interactive Plotly elevation profile with peak/valley annotations.
    Returns HTML div string (not full HTML page).
    """
    sections = profile["sections"]
    depths = profile["depths"]
    smoothed = profile["smoothed"]
    severity_labels = profile["severity_labels"]
    peaks = profile.get("peaks", [])
    valleys = profile.get("valleys", [])

    sev_order = ["NO CORRUGATION", "LOW", "MEDIUM", "HIGH"]
    sev_to_num = {s: i for i, s in enumerate(sev_order)}
    sev_num = [sev_to_num.get(s, 0) for s in severity_labels]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=sections, y=depths, mode="lines", name="Original", opacity=0.35,
        hovertemplate="Section %{x}<br>Elevation: %{y:.6f} m<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=sections, y=smoothed, mode="lines", name="Smoothed", line=dict(width=2),
        hovertemplate="Section %{x}<br>Smoothed: %{y:.6f} m<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=sections, y=sev_num, mode="lines", name="Severity",
        line=dict(width=2, dash="dash"), yaxis="y2",
        hovertemplate="Section %{x}<br>Severity: %{text}<extra></extra>",
        text=severity_labels
    ))

    for peak_idx, peak_val in peaks:
        if peak_idx < len(sections):
            fig.add_annotation(
                x=sections[peak_idx], y=peak_val, showarrow=True,
                arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor="red",
                ax=0, ay=-25, text="Peak", font=dict(size=9, color="red"), standoff=8
            )

    for valley_idx, valley_val in valleys:
        if valley_idx < len(sections):
            fig.add_annotation(
                x=sections[valley_idx], y=valley_val, showarrow=True,
                arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor="blue",
                ax=0, ay=25, text="Valley", font=dict(size=9, color="blue"), standoff=8
            )

    fig.update_layout(
        title=f"Y = {profile['transect_y']:.2f} m",
        template="plotly_white",
        margin=dict(l=60, r=60, t=50, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
        xaxis=dict(title="Section index"),
        yaxis=dict(title="Elevation (m)"),
        yaxis2=dict(title="Severity", overlaying="y", side="right",
                    range=[-0.5, 3.5], tickmode="array",
                    tickvals=[0, 1, 2, 3], ticktext=["None", "Low", "Med", "High"])
    )
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def create_summary_figure(results: Dict[str, Any]) -> str:
    """Create summary bar chart of area by severity. Returns HTML div."""
    totals = results["totals_ft2"]
    counts = results["counts"]
    sevs = ["LOW", "MEDIUM", "HIGH"]
    colors = ["#2e7d32", "#e65100", "#c62828"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sevs, y=[totals.get(s, 0) for s in sevs],
        marker_color=colors,
        text=[f"{totals.get(s, 0):.1f} ft2 ({counts.get(s, 0)} seg)" for s in sevs],
        textposition="auto"
    ))
    fig.update_layout(
        title="Total Area by Severity", yaxis_title="Area (ft2)",
        template="plotly_white", height=350, margin=dict(t=50, b=40)
    )
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def create_neighbor_summary_plot(neighbor_summary: List[Dict[str, Any]]) -> str:
    """Create mean ± std total area plot across neighbor frequencies. Returns HTML div."""
    sev_order = ["LOW", "MEDIUM", "HIGH"]
    colors = ["#2e7d32", "#e65100", "#c62828"]

    vals = {s: [] for s in sev_order}
    for r in neighbor_summary:
        s = r.get("severity")
        a = r.get("total_area_ft2", 0)
        if s in vals and np.isfinite(a):
            vals[s].append(float(a))

    means = [float(np.mean(vals[s])) if vals[s] else 0.0 for s in sev_order]
    stds = [float(np.std(vals[s])) if len(vals[s]) > 1 else 0.0 for s in sev_order]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sev_order, y=means,
        error_y=dict(type="data", array=stds, visible=True),
        marker_color=colors,
        text=[f"{m:.1f} +/- {s:.1f}" for m, s in zip(means, stds)],
        textposition="auto"
    ))
    fig.update_layout(
        title="Total Area (Mean +/- Std) Across Frequencies",
        yaxis_title="Area (ft2)", template="plotly_white",
        height=350, margin=dict(t=50, b=40)
    )
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)
