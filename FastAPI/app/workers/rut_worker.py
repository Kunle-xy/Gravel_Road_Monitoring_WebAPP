"""
Backward-compatible re-export.

The rut worker has been refactored into the app.workers.rut package:
    rut/constants.py  — Deduct value lookup table
    rut/geo.py        — GeoTIFF polygon extraction
    rut/detection.py  — Rut detection algorithms
    rut/plots.py      — Plotly figure generation
    rut/report.py     — HTML and PDF report generation
    rut/task.py       — Celery task definition

All codes written by Kunle Oguntoye, PhD Student at Iowa State University.
Contact: oguntoye@IASTATE.EDU
"""

from app.workers.rut.task import analyze_ruts_task

__all__ = ["analyze_ruts_task"]
