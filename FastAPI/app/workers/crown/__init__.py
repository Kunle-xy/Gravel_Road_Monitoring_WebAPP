"""
Crown Distress Analysis Worker Package

Modular crown distress detection and analysis pipeline.
All codes written by Kunle Oguntoye, PhD Student at Iowa State University.
Contact: oguntoye@IASTATE.EDU

Modules:
    detection   — Crown slope analysis and rut detection along profiles
    plots       — Matplotlib figure generation for elevation profiles and summaries
    report      — HTML report generation
    task        — Celery task definition (analyze_crown_task)
"""

from app.workers.crown.task import analyze_crown_task

__all__ = ["analyze_crown_task"]
