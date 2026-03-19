"""
Plotly figure generation for rut analysis.

Creates interactive charts for:
- Deduct value curves with actual severity markers
- Rut analysis dashboards (severity distribution, depth box plots, cross-sections)
- Neighbor frequency evaluation comparison plots
"""

import logging
from typing import Dict, Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.workers.rut.constants import DEDUCT_TABLE

logger = logging.getLogger(__name__)


def create_deduct_curve_plot(density_data: Dict[str, Any]) -> go.Figure:
    """
    Create a plot showing L, M, H deduct curves with actual values marked.
    """
    densities = sorted(DEDUCT_TABLE.keys())
    low_curve = [DEDUCT_TABLE[d]["Low"] for d in densities]
    medium_curve = [DEDUCT_TABLE[d]["Medium"] for d in densities]
    high_curve = [DEDUCT_TABLE[d]["High"] for d in densities]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=densities, y=low_curve, mode='lines',
        name='Low Severity', line=dict(color='green', width=3)
    ))
    fig.add_trace(go.Scatter(
        x=densities, y=medium_curve, mode='lines',
        name='Medium Severity', line=dict(color='orange', width=3)
    ))
    fig.add_trace(go.Scatter(
        x=densities, y=high_curve, mode='lines',
        name='High Severity', line=dict(color='red', width=3)
    ))

    colors_map = {'Low': 'green', 'Medium': 'orange', 'High': 'red'}
    for severity in ['Low', 'Medium', 'High']:
        if severity in density_data:
            actual_density = density_data[severity]['density_percent']
            actual_deduct = density_data[severity]['deduct_value']
            fig.add_trace(go.Scatter(
                x=[actual_density], y=[actual_deduct],
                mode='markers+text',
                name=f'{severity} (Actual)',
                marker=dict(size=15, color=colors_map[severity], symbol='star',
                            line=dict(color='black', width=2)),
                text=f'{actual_deduct}', textposition='top center',
                textfont=dict(size=12, color='black', family='Arial Black'),
                showlegend=False
            ))

    fig.update_layout(
        title='Deduct Value Curves with Actual Values',
        xaxis_title='Density (%)', yaxis_title='Deduct Value',
        template='plotly_white', height=400, width=700,
        showlegend=True,
        legend=dict(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.8)'),
        font=dict(size=11)
    )
    return fig


def create_plot_figure(results: Dict[str, Any]) -> go.Figure:
    """
    Create Plotly figure with rut analysis results:
    - Severity distribution bar chart
    - Depth box plot by severity
    - Deduct curve with actual markers
    - Density/deduct details table
    - Elevation cross-section profiles

    For neighbor_eval mode, shows frequency comparison charts instead.
    """
    ruts = results['ruts']
    cross_sections = results.get('cross_sections', [])
    density_data = results.get('density_data', {})
    neighbor_eval = results.get('neighbor_eval', False)
    frequency_results = results.get('frequency_results', {})

    if not ruts:
        fig = go.Figure()
        fig.add_annotation(
            text="No ruts detected in this area",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=20)
        )
        fig.update_layout(title="Rut Detection Results", template="simple_white", height=400)
        return fig

    severities = ['Low', 'Medium', 'High']
    colors = {'Low': 'green', 'Medium': 'orange', 'High': 'red'}
    colors_list = ['green', 'orange', 'red']

    if neighbor_eval:
        return _create_neighbor_eval_figure(results, frequency_results, density_data, severities, colors, ruts)
    else:
        return _create_standard_figure(results, density_data, cross_sections, severities, colors_list, ruts)


def _create_neighbor_eval_figure(results, frequency_results, density_data, severities, colors, ruts):
    """Create figure for neighbor frequency evaluation mode."""
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=[
            "Mean Depth by Severity (Across Frequencies)",
            "Total Area by Severity (Across Frequencies)",
            "Density & Deduct Values",
            "Frequency Analysis Details", "", ""
        ],
        specs=[
            [{'type': 'scatter'}, {'type': 'scatter'}, {'type': 'bar'}],
            [{'type': 'table', 'colspan': 3}, None, None]
        ],
        row_heights=[0.6, 0.4], vertical_spacing=0.1
    )

    freq_list = sorted(frequency_results.keys())

    # Plot 1: Mean depth across frequencies
    for sev in severities:
        depths_by_freq = []
        for freq in freq_list:
            freq_ruts = [r for r in frequency_results[freq]['ruts'] if r['severity'] == sev]
            depths_by_freq.append(np.mean([r['rut_depth_in'] for r in freq_ruts]) if freq_ruts else 0)
        fig.add_trace(go.Scatter(
            x=freq_list, y=depths_by_freq, mode='lines+markers',
            name=sev, line=dict(color=colors[sev], width=2), marker=dict(size=8)
        ), row=1, col=1)

    # Plot 2: Total area across frequencies
    for sev in severities:
        areas_by_freq = [frequency_results[freq][f'{sev.lower()}_area_sqft'] for freq in freq_list]
        fig.add_trace(go.Scatter(
            x=freq_list, y=areas_by_freq, mode='lines+markers',
            name=sev, line=dict(color=colors[sev], width=2), marker=dict(size=8), showlegend=False
        ), row=1, col=2)

    # Plot 3: Density & Deduct bar chart
    deduct_vals = [density_data[sev]['deduct_value'] for sev in severities]
    fig.add_trace(go.Bar(
        x=severities, y=deduct_vals,
        marker_color=[colors[sev] for sev in severities],
        text=[f"<b>Density: {density_data[sev]['density_percent']:.1f}%</b><br>Deduct: {density_data[sev]['deduct_value']}"
              for sev in severities],
        textposition='auto', name='Deduct Value', showlegend=False
    ), row=1, col=3)

    # Frequency analysis table
    table_data = []
    for freq in freq_list:
        for sev in severities:
            freq_res = frequency_results[freq]
            count = sum(1 for r in freq_res['ruts'] if r['severity'] == sev)
            area = freq_res[f'{sev.lower()}_area_sqft']
            table_data.append({'Frequency': freq, 'Severity': sev, 'Count': count, 'Area (ft2)': round(area, 2)})

    table_df = pd.DataFrame(table_data)
    fig.add_trace(go.Table(
        header=dict(values=list(table_df.columns), fill_color='paleturquoise', align='left', font=dict(size=12)),
        cells=dict(values=[table_df[col] for col in table_df.columns], fill_color='lavender', align='left', font=dict(size=11))
    ), row=2, col=1)

    fig.update_xaxes(title_text="Sampling Frequency", row=1, col=1)
    fig.update_yaxes(title_text="Mean Depth (inches)", row=1, col=1)
    fig.update_xaxes(title_text="Sampling Frequency", row=1, col=2)
    fig.update_yaxes(title_text="Total Area (ft2)", row=1, col=2)
    fig.update_xaxes(title_text="Severity", row=1, col=3)
    fig.update_yaxes(title_text="Deduct Value", row=1, col=3)

    fig.update_layout(
        title=f"Rut Analysis - Neighbor Frequency Evaluation<br><sub>Primary Frequency: {list(frequency_results.keys())[len(frequency_results)//2]}, Total Area: {results['total_area_sqft']:.2f} ft2</sub>",
        template="simple_white", height=800, showlegend=True, legend=dict(x=0.01, y=0.99)
    )
    return fig


def _create_standard_figure(results, density_data, cross_sections, severities, colors_list, ruts):
    """Create standard analysis figure with summary, deduct curves, and cross-sections."""
    n_cross_sections = len(cross_sections)
    n_cols_cs = min(5, n_cross_sections)
    n_rows_cs = (n_cross_sections + n_cols_cs - 1) // n_cols_cs if n_cross_sections > 0 else 0
    total_rows = 2 + n_rows_cs

    specs = [
        [{'type': 'bar'}, {'type': 'box'}, None, None, None],
        [{'type': 'scatter', 'colspan': 3}, None, None, {'type': 'table', 'colspan': 2}, None]
    ]
    for _ in range(n_rows_cs):
        specs.append([{'type': 'scatter'}] * n_cols_cs)

    subplot_titles = ["Rut Severity Distribution", "Depth Distribution by Severity",
                      "Deduct Value Curves with Actual Values", "Density/Deduct Details"]
    if n_cross_sections > 0:
        subplot_titles.extend([f"Section {i+1}" for i in range(n_cross_sections)])

    fig = make_subplots(
        rows=total_rows, cols=n_cols_cs, subplot_titles=subplot_titles, specs=specs,
        vertical_spacing=0.08, horizontal_spacing=0.05,
        row_heights=[0.2, 0.2] + [0.6/n_rows_cs]*n_rows_cs if n_rows_cs > 0 else [0.4, 0.6]
    )

    # Row 1: Summary
    counts = [results['low_severity_count'], results['medium_severity_count'], results['high_severity_count']]
    fig.add_trace(go.Bar(
        x=severities, y=counts, marker_color=colors_list, text=counts,
        textposition='auto', name='Count', showlegend=False
    ), row=1, col=1)

    for sev, color in zip(severities, colors_list):
        sev_ruts = [r for r in ruts if r['severity'] == sev]
        if sev_ruts:
            fig.add_trace(go.Box(
                y=[r['rut_depth_in'] for r in sev_ruts], name=sev,
                marker_color=color, showlegend=False
            ), row=1, col=2)

    # Row 2: Deduct curves + table
    if density_data:
        densities_curve = sorted(DEDUCT_TABLE.keys())
        for curve_name, curve_color in [("Low", "green"), ("Medium", "orange"), ("High", "red")]:
            curve_data = [DEDUCT_TABLE[d][curve_name] for d in densities_curve]
            fig.add_trace(go.Scatter(
                x=densities_curve, y=curve_data, mode='lines',
                name=f'{curve_name} Curve', line=dict(color=curve_color, width=2), showlegend=True
            ), row=2, col=1)

        for sev, color in zip(severities, colors_list):
            if sev in density_data:
                fig.add_trace(go.Scatter(
                    x=[density_data[sev]['density_percent']], y=[density_data[sev]['deduct_value']],
                    mode='markers+text', name=f'{sev} (Actual)',
                    marker=dict(size=12, color=color, symbol='star', line=dict(color='black', width=1.5)),
                    text=f'{density_data[sev]["deduct_value"]}', textposition='top center',
                    textfont=dict(size=10, color='black'), showlegend=False
                ), row=2, col=1)

        table_data = {
            'Severity': severities,
            'Area (ft2)': [round(density_data[sev]['area_sqft'], 2) for sev in severities],
            'Density (%)': [round(density_data[sev]['density_percent'], 2) for sev in severities],
            'Deduct Value': [density_data[sev]['deduct_value'] for sev in severities]
        }
        fig.add_trace(go.Table(
            header=dict(values=list(table_data.keys()), fill_color='paleturquoise', align='left',
                        font=dict(size=12, color='black'), line=dict(color='darkslategray', width=2)),
            cells=dict(values=[table_data[k] for k in table_data.keys()],
                       fill_color=[['lightgreen', 'lightyellow', 'lightcoral']], align='left',
                       font=dict(size=11, color='black'), line=dict(color='darkslategray', width=1), height=30)
        ), row=2, col=4)

    # Cross-section plots
    for idx, cs in enumerate(cross_sections):
        row = 3 + (idx // n_cols_cs)
        col = (idx % n_cols_cs) + 1
        fig.add_trace(go.Scatter(
            x=cs['distances'], y=cs['elevations'], mode='lines',
            line=dict(color='blue', width=1), name=f"CS {idx+1}", showlegend=False
        ), row=row, col=col)
        fig.update_xaxes(title_text="Distance (m)", row=row, col=col, title_font=dict(size=8))
        fig.update_yaxes(title_text="Elevation (m)", row=row, col=col, title_font=dict(size=8))

    fig.update_xaxes(title_text="Severity", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_xaxes(title_text="Severity", row=1, col=2)
    fig.update_yaxes(title_text="Depth (inches)", row=1, col=2)
    fig.update_xaxes(title_text="Density (%)", row=2, col=1)
    fig.update_yaxes(title_text="Deduct Value", row=2, col=1)

    plot_height = 400 + 200 + (n_rows_cs * 200)
    fig.update_layout(
        title=f"Rut Analysis Results<br><sub>Total: {results['total_ruts_detected']} ruts, Area: {results['total_area_sqft']:.2f} ft2, Polygon Area: {results.get('polygon_area_sqft', 0):.2f} ft2</sub>",
        template="simple_white", height=plot_height, showlegend=False
    )
    return fig
