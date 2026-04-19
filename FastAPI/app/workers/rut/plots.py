"""
Plotly figure generation for rut analysis.

Crown-style elevation profile plots with rut highlighting (peaks, valley,
straight-edge, and a colored band per detected rut), plus a compact
count/area summary chart.
"""

import logging
from typing import Dict, Any

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

SEV_COLOR = {"Low": "#2e7d32", "Medium": "#e65100", "High": "#c62828"}


def create_profile_plot(cross_section: Dict[str, Any]) -> go.Figure:
    """
    Build an elevation profile for one sampling line, highlighting every
    rut with a vertical band, the two shoulder peaks, the valley, and the
    straight-edge that defines the depth.
    """
    distances = cross_section.get('distances') or []
    elevations = cross_section.get('elevations') or []
    ruts = cross_section.get('ruts') or []
    line_x = cross_section.get('x', 0.0)

    y = np.array(elevations, dtype=float)
    x = np.array(distances, dtype=float)
    mask = np.isfinite(y)
    y = y[mask]
    x = x[mask]

    fig = go.Figure()

    if y.size < 3:
        fig.add_annotation(
            text="Insufficient data",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False
        )
        return fig

    # Filled elevation profile (crown-style)
    fig.add_trace(go.Scatter(
        x=x, y=np.full_like(x, np.nanmin(y)),
        mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=x, y=y, mode='lines', fill='tonexty',
        line=dict(color='#1976d2', width=2),
        fillcolor='rgba(25,118,210,0.15)',
        name='Elevation'
    ))

    n = len(x)
    severities_seen = []
    y_top = float(np.nanmax(y))
    y_bot = float(np.nanmin(y))
    y_range = max(y_top - y_bot, 1e-6)

    for rut in ruts:
        idx_h1 = max(0, min(int(rut.get('idx_h1', 0)), n - 1))
        idx_low = max(0, min(int(rut.get('idx_low', 0)), n - 1))
        idx_h2 = max(0, min(int(rut.get('idx_h2', 0)), n - 1))
        severity = rut.get('severity', 'Low')
        depth_in = float(rut.get('rut_depth_in', 0.0))
        color = SEV_COLOR.get(severity, '#888')

        # Translucent band marking the rut footprint
        fig.add_vrect(
            x0=x[idx_h1], x1=x[idx_h2],
            fillcolor=color, opacity=0.18, line_width=0,
            layer='below'
        )

        # Straight-edge line connecting the two peaks (the depth reference)
        fig.add_trace(go.Scatter(
            x=[x[idx_h1], x[idx_h2]],
            y=[y[idx_h1], y[idx_h2]],
            mode='lines',
            line=dict(color=color, width=2, dash='dash'),
            showlegend=False, hoverinfo='skip'
        ))

        # Peaks + valley markers (legend entry once per severity)
        show_in_legend = severity not in severities_seen
        if show_in_legend:
            severities_seen.append(severity)
        fig.add_trace(go.Scatter(
            x=[x[idx_h1], x[idx_low], x[idx_h2]],
            y=[y[idx_h1], y[idx_low], y[idx_h2]],
            mode='markers',
            marker=dict(size=9, color=color, line=dict(color='black', width=1)),
            name=severity,
            showlegend=show_in_legend,
            hovertemplate=(
                f"{severity} rut, depth {depth_in:.2f}\"<br>"
                "x=%{x:.2f} m<br>elev=%{y:.3f} m<extra></extra>"
            )
        ))

        # Per-rut depth label above the valley so every detection shows its depth
        fig.add_annotation(
            x=x[idx_low],
            y=y[idx_low],
            text=f"{depth_in:.2f}\"",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            arrowcolor=color,
            ax=0,
            ay=28,           # arrow points down toward the valley
            font=dict(size=10, color=color, family="Arial Black"),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor=color,
            borderwidth=1,
            borderpad=2,
        )

    summary_bits = []
    for sev in ('Low', 'Medium', 'High'):
        n_sev = sum(1 for r in ruts if r.get('severity') == sev)
        if n_sev:
            summary_bits.append(f"{n_sev} {sev}")
    title_suffix = f" — {', '.join(summary_bits)}" if summary_bits else ""

    fig.update_layout(
        title=dict(
            text=f"x = {line_x:.2f} m{title_suffix}",
            font=dict(size=12)
        ),
        xaxis_title="Distance along line (m)",
        yaxis_title="Elevation (m)",
        template="simple_white",
        showlegend=True,
        legend=dict(font=dict(size=9), orientation="h", y=-0.25),
        margin=dict(l=55, r=15, t=40, b=55),
    )
    return fig


def create_summary_figure(results: Dict[str, Any]) -> go.Figure:
    """
    Side-by-side bar charts: rut count by severity and total area by severity.
    Mirrors the crown summary chart layout.
    """
    sevs = ['Low', 'Medium', 'High']
    colors = [SEV_COLOR[s] for s in sevs]

    counts = [
        results.get('low_severity_count', 0),
        results.get('medium_severity_count', 0),
        results.get('high_severity_count', 0),
    ]

    density_data = results.get('density_data') or {}
    areas = [float(density_data.get(s, {}).get('area_sqft', 0.0)) for s in sevs]

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["Count by Severity", "Area by Severity (ft²)"]
    )

    fig.add_trace(go.Bar(
        x=sevs, y=counts,
        marker_color=colors,
        text=[str(c) for c in counts],
        textposition='auto', showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=sevs, y=areas,
        marker_color=colors,
        text=[f"{a:.1f} ft²" for a in areas],
        textposition='auto', showlegend=False
    ), row=1, col=2)

    fig.update_layout(
        template="simple_white",
        height=320,
        margin=dict(t=45, b=30, l=40, r=20),
    )
    return fig


def create_neighbor_summary_figure(results: Dict[str, Any]) -> go.Figure:
    """
    Pooled neighbor-frequency study.

    Mirrors the ArcGIS RUT-IOWADOT.pyt layout: two top charts (depth and total
    area, both mean ± std by severity, with shaded bands) and a full per-
    frequency per-severity table underneath.
    """
    freq_results = results.get('frequency_results') or {}
    sev_order = ['Low', 'Medium', 'High']
    color_map = {"Low": "green", "Medium": "orange", "High": "red"}
    x_idx = [0, 1, 2]

    # Flatten all ruts across frequencies
    neighbor_rows = []
    for freq, fr in freq_results.items():
        for rut in fr.get('ruts') or []:
            sev = rut.get('severity')
            if not sev:
                continue
            neighbor_rows.append({
                "Frequency": int(freq),
                "Severity": sev,
                "Depth": float(rut.get('rut_depth_in', 0.0)),
                "Area": float(rut.get('rut_area_sqft', 0.0)),
            })

    freq_list = sorted({r["Frequency"] for r in neighbor_rows}) or sorted(int(f) for f in freq_results.keys())

    # Per (frequency, severity) stats for the table
    freq_sev_rows = []
    for f in freq_list:
        for sev in sev_order:
            rows = [r for r in neighbor_rows if r["Frequency"] == f and r["Severity"] == sev]
            depths = np.array([r["Depth"] for r in rows], dtype=float)
            areas = np.array([r["Area"] for r in rows], dtype=float)
            freq_sev_rows.append({
                "Frequency": f,
                "Severity": sev,
                "Count": int(depths.size),
                "Mean Depth (in)": float(np.nanmean(depths)) if depths.size else np.nan,
                "Std Depth (in)": float(np.nanstd(depths)) if depths.size else np.nan,
                "Mean Area (ft²)": float(np.nanmean(areas)) if areas.size else np.nan,
                "Std Area (ft²)": float(np.nanstd(areas)) if areas.size else np.nan,
                "Total Area (ft²)": float(np.nansum(areas)) if areas.size else 0.0,
            })

    # Pooled depth stats per severity (across every rut, every frequency)
    pooled_depth = {}
    for sev in sev_order:
        d = np.array([r["Depth"] for r in neighbor_rows if r["Severity"] == sev], dtype=float)
        pooled_depth[sev] = {
            "mean": float(np.nanmean(d)) if d.size else np.nan,
            "std": float(np.nanstd(d)) if d.size else np.nan,
            "n": int(d.size),
        }

    # Per-severity total-area stats across frequencies (mean ± std of per-freq totals)
    sev_total_by_freq = {sev: [] for sev in sev_order}
    for sev in sev_order:
        for f in freq_list:
            tot = next(
                (row["Total Area (ft²)"] for row in freq_sev_rows
                 if row["Frequency"] == f and row["Severity"] == sev),
                0.0,
            )
            if tot > 0.0:
                sev_total_by_freq[sev].append(tot)

    sev_total_mean = {
        sev: (float(np.nanmean(v)) if v else np.nan) for sev, v in sev_total_by_freq.items()
    }
    sev_total_std = {
        sev: (float(np.nanstd(v)) if v else np.nan) for sev, v in sev_total_by_freq.items()
    }
    sev_total_n = {sev: len(v) for sev, v in sev_total_by_freq.items()}

    for row in freq_sev_rows:
        sd = sev_total_std[row["Severity"]]
        row["Total Area Std by Severity (ft²)"] = None if np.isnan(sd) else float(round(sd, 4))

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Mean depth with standard deviation, by severity",
            "Total area with standard deviation, by severity",
            "Details per frequency and severity", "",
        ],
        specs=[
            [{'type': 'xy'}, {'type': 'xy'}],
            [{'type': 'table', 'colspan': 2}, None],
        ],
        row_heights=[0.55, 0.45],
        vertical_spacing=0.08,
    )

    def _add_band(row, col, x_center, y_mean, y_std, clamp_zero, color_hex, width=0.35):
        if np.isnan(y_mean) or np.isnan(y_std):
            return
        y0, y1 = y_mean - y_std, y_mean + y_std
        if clamp_zero:
            y0 = max(0.0, y0)
        fig.add_shape(
            type="rect",
            x0=x_center - width, x1=x_center + width,
            y0=y0, y1=y1,
            fillcolor=color_hex, opacity=0.20, line=dict(width=0),
            row=row, col=col,
        )

    # (1,1) Depth
    depth_means = [pooled_depth[s]["mean"] for s in sev_order]
    for i, sev in enumerate(sev_order):
        _add_band(row=1, col=1, x_center=x_idx[i],
                  y_mean=pooled_depth[sev]["mean"], y_std=pooled_depth[sev]["std"],
                  clamp_zero=False, color_hex=color_map[sev])
    fig.add_trace(go.Scatter(
        x=x_idx, y=depth_means, mode="lines+markers",
        name="Mean depth", marker=dict(size=8), line=dict(width=2),
    ), row=1, col=1)
    for i, sev in enumerate(sev_order):
        mu, sd, n = pooled_depth[sev]["mean"], pooled_depth[sev]["std"], pooled_depth[sev]["n"]
        if np.isnan(mu) or np.isnan(sd) or n == 0:
            continue
        fig.add_annotation(
            x=x_idx[i], y=mu + sd,
            text=f"{sev}<br>mean {mu:.2f} in, std {sd:.2f}, n {n}",
            showarrow=False, yshift=8, font=dict(size=11), row=1, col=1,
        )
    fig.update_xaxes(row=1, col=1, tickmode="array", tickvals=x_idx, ticktext=sev_order, title_text="Severity")
    fig.update_yaxes(row=1, col=1, title_text="Depth, inches")

    # (1,2) Total area
    area_means = [sev_total_mean[s] for s in sev_order]
    for i, sev in enumerate(sev_order):
        _add_band(row=1, col=2, x_center=x_idx[i],
                  y_mean=sev_total_mean[sev], y_std=sev_total_std[sev],
                  clamp_zero=True, color_hex=color_map[sev])
    fig.add_trace(go.Scatter(
        x=x_idx, y=area_means, mode="lines+markers",
        name="Total area", marker=dict(size=8), line=dict(width=2),
    ), row=1, col=2)
    for i, sev in enumerate(sev_order):
        mu, sd, n = sev_total_mean[sev], sev_total_std[sev], sev_total_n[sev]
        if np.isnan(mu) or np.isnan(sd) or n == 0:
            continue
        fig.add_annotation(
            x=x_idx[i], y=mu + sd,
            text=f"{sev}<br>mean {mu:.2f} ft², std {sd:.2f}, n {n}",
            showarrow=False, yshift=8, font=dict(size=11), row=1, col=2,
        )
    fig.update_xaxes(row=1, col=2, tickmode="array", tickvals=x_idx, ticktext=sev_order, title_text="Severity")
    fig.update_yaxes(row=1, col=2, title_text="Total area, square feet")

    # (2,1) Full details table
    freq_sev_rows.sort(key=lambda r: (r["Frequency"], sev_order.index(r["Severity"])))

    def _fmt(val):
        return None if (val is None or (isinstance(val, float) and np.isnan(val))) else round(val, 4)

    fig.add_trace(go.Table(
        header=dict(
            values=[
                "Frequency", "Severity", "Count",
                "Mean Depth, in", "Std Depth, in",
                "Mean Area, ft²", "Std Area, ft²",
                "Total Area, ft²", "Total Area Std by Severity, ft²",
            ],
            fill_color='paleturquoise', align='left', font=dict(size=12),
        ),
        cells=dict(
            values=[
                [r["Frequency"] for r in freq_sev_rows],
                [r["Severity"] for r in freq_sev_rows],
                [r["Count"] for r in freq_sev_rows],
                [_fmt(r["Mean Depth (in)"]) for r in freq_sev_rows],
                [_fmt(r["Std Depth (in)"]) for r in freq_sev_rows],
                [_fmt(r["Mean Area (ft²)"]) for r in freq_sev_rows],
                [_fmt(r["Std Area (ft²)"]) for r in freq_sev_rows],
                [round(r["Total Area (ft²)"], 4) for r in freq_sev_rows],
                [r["Total Area Std by Severity (ft²)"] for r in freq_sev_rows],
            ],
            fill_color='lavender', align='left', font=dict(size=11),
        ),
    ), row=2, col=1)

    fig.update_layout(
        title="Rutting severity, neighbor frequency study, pooled results",
        height=900,
        showlegend=False,
        template="simple_white",
        margin=dict(l=60, r=60, t=80, b=60),
    )
    return fig
