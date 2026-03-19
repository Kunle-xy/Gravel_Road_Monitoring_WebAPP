"""
Rut Analysis Worker Package

Modular rut detection and analysis pipeline.
All codes written by Kunle Oguntoye, PhD Student at Iowa State University.
Contact: oguntoye@IASTATE.EDU

Modules:
    constants   — Deduct value lookup table and interpolation
    geo         — GeoTIFF polygon extraction and spatial utilities
    detection   — Rut detection along sampling lines and polygon analysis
    plots       — Plotly figure generation (cross-sections, deduct curves)
    report      — HTML and PDF report generation
    task        — Celery task definition (analyze_ruts_task)
"""

from app.workers.rut.task import analyze_ruts_task

__all__ = ["analyze_ruts_task"]
