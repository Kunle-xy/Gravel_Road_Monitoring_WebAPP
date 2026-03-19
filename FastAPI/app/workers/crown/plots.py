"""
Plot generation for crown distress analysis.

Uses Plotly to generate:
- Elevation profile plots with slope fits and rut highlighting
- Neighbor frequency summary (mean ± std by severity)
"""

import logging
from typing import Dict, Any, List, Optional

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

SEV_COLOR = {"Low": "blue", "Medium": "orange", "High": "red"}


def create_profile_plot(profile: Dict[str, Any]) -> go.Figure:
    """Create an elevation profile plot with slope fits and rut shading."""
    depths = profile['depths']
    distances = profile['distances']
    dy_m = profile['dy_m']
    ref_idx = profile['ref_idx']
    rut_idxs = profile.get('rut_idxs')
    rut_sev = profile.get('rut_sev')
    m_left = profile.get('m_left', 0)
    m_right = profile.get('m_right', 0)
    crown = profile.get('crown')

    # Filter NaN
    y = np.array([d if d is not None else np.nan for d in depths], dtype=float)
    mask = np.isfinite(y)
    y_clean = y[mask]
    x_clean = np.array(distances, dtype=float)[mask]

    if y_clean.size < 3:
        fig = go.Figure()
        fig.add_annotation(text="Insufficient data", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
        return fig

    fig = go.Figure()

    # Fill + line
    fig.add_trace(go.Scatter(
        x=x_clean, y=np.full_like(x_clean, np.nanmin(y_clean)),
        mode='lines', line=dict(width=0), showlegend=False
    ))
    fig.add_trace(go.Scatter(
        x=x_clean, y=y_clean, mode='lines', fill='tonexty',
        line=dict(color='#1976d2', width=2), fillcolor='rgba(25,118,210,0.15)',
        name='Elevation'
    ))

    # Slope fit lines
    ref_idx_clamped = min(ref_idx, len(y_clean) - 1)
    if ref_idx_clamped > 1:
        left_y = y_clean[:ref_idx_clamped]
        left_x = x_clean[:ref_idx_clamped]
        if len(left_x) >= 2:
            m, b = np.polyfit(left_x, left_y, 1)
            fig.add_trace(go.Scatter(
                x=left_x, y=m * left_x + b, mode='lines',
                line=dict(color='green', width=2, dash='dash'),
                name=f'Left fit {m_left:.2f}%'
            ))

    if ref_idx_clamped + 1 < len(y_clean):
        right_y = y_clean[ref_idx_clamped + 1:]
        right_x = x_clean[ref_idx_clamped + 1:]
        if len(right_x) >= 2:
            m, b = np.polyfit(right_x, right_y, 1)
            fig.add_trace(go.Scatter(
                x=right_x, y=m * right_x + b, mode='lines',
                line=dict(color='#e65100', width=2, dash='dash'),
                name=f'Right fit {m_right:.2f}%'
            ))

    # Reference line
    if ref_idx_clamped < len(x_clean):
        fig.add_vline(x=x_clean[ref_idx_clamped], line_dash="dot", line_color="gray", opacity=0.5)

    # Rut shading
    if rut_idxs and rut_sev:
        h1, low, h2 = rut_idxs
        h1 = max(0, min(h1, len(x_clean) - 1))
        low = max(0, min(low, len(x_clean) - 1))
        h2 = max(0, min(h2, len(x_clean) - 1))
        color = SEV_COLOR.get(rut_sev, 'gray')
        fig.add_vrect(x0=x_clean[h1], x1=x_clean[h2], fillcolor=color, opacity=0.2, line_width=0)
        fig.add_trace(go.Scatter(
            x=[x_clean[h1], x_clean[low], x_clean[h2]],
            y=[y_clean[h1], y_clean[low], y_clean[h2]],
            mode='markers', marker=dict(size=8, color=color),
            name=f'Rut ({rut_sev})', showlegend=True
        ))

    title = f"x={profile['x']:.2f}m"
    if crown:
        title += f" | Crown: {crown}"
    if rut_sev:
        title += f" | Rut: {rut_sev}"

    fig.update_layout(
        title=dict(text=title, font=dict(size=11)),
        xaxis_title="Distance (m)", yaxis_title="Elevation (m)",
        template="simple_white", showlegend=True,
        legend=dict(font=dict(size=8), orientation="h", y=-0.25),
        margin=dict(l=50, r=15, t=35, b=55),
    )
    return fig


def create_summary_figure(results: Dict[str, Any]) -> go.Figure:
    """Create summary bar chart of linear feet by severity."""
    totals = results['totals_ft']
    counts = results['counts']
    sevs = ['Low', 'Medium', 'High']
    colors = ['#2e7d32', '#e65100', '#c62828']

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Linear Feet by Severity", "Line Count by Severity"])

    fig.add_trace(go.Bar(
        x=sevs, y=[totals.get(s, 0) for s in sevs],
        marker_color=colors,
        text=[f"{totals.get(s, 0):.1f} ft" for s in sevs],
        textposition='auto', showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=sevs, y=[counts.get(s, 0) for s in sevs],
        marker_color=colors,
        text=[str(counts.get(s, 0)) for s in sevs],
        textposition='auto', showlegend=False
    ), row=1, col=2)

    fig.update_layout(template="simple_white", height=350, margin=dict(t=40, b=30))
    return fig


def create_neighbor_summary_figure(results: Dict[str, Any]) -> go.Figure:
    """Create neighbor frequency summary showing mean ± std linear feet by severity."""
    means = results['means_ft']
    stds = results['stds_ft']
    sevs = ['Low', 'Medium', 'High']
    colors = ['#2e7d32', '#e65100', '#c62828']

    fig = go.Figure()
    x_idx = list(range(len(sevs)))

    for i, (sev, color) in enumerate(zip(sevs, colors)):
        mu = means.get(sev, 0)
        sd = stds.get(sev, 0)
        fig.add_trace(go.Bar(
            x=[sev], y=[mu], error_y=dict(type='data', array=[sd], visible=True),
            marker_color=color, name=sev,
            text=[f"{mu:.1f} ± {sd:.1f} ft"], textposition='auto'
        ))

    fig.update_layout(
        title=f"Linear Feet by Severity (Mean ± Std, freqs {results.get('freq_list', [])})",
        yaxis_title="Linear Feet", template="simple_white",
        height=350, showlegend=False, margin=dict(t=50, b=30)
    )
    return fig
