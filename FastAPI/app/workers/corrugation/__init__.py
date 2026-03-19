"""
Corrugation Distress Analysis Worker Package

Detects corrugation severity along horizontal transect lines within a polygon.
All codes written by Kunle Oguntoye, PhD Student at Iowa State University.
Contact: oguntoye@IASTATE.EDU

Modules:
    detection   — Gaussian smoothing, peak/valley trend detection, severity classification
    plots       — Plotly interactive profile charts and summary plots
    report      — HTML report generation with embedded interactive plots
    task        — Celery task definition (analyze_corrugation_task)
"""

from app.workers.corrugation.task import analyze_corrugation_task

__all__ = ["analyze_corrugation_task"]
