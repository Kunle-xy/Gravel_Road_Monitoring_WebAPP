"""
Celery Application Configuration

This module initializes the Celery app for distributed task processing.
Workers can be scaled horizontally to handle multiple tile generation jobs.
"""

from celery import Celery
from app.config import settings

# Initialize Celery app
celery_app = Celery(
    "gravel_road_tiles",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tile_worker", "app.workers.rut.task", "app.workers.crown.task", "app.workers.corrugation.task", "app.workers.dust.task"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_track_started=True,  # Track when task starts
    task_time_limit=None,  # No hard time limit - allow tasks to run indefinitely
    task_soft_time_limit=None,  # No soft time limit - allow tasks to run indefinitely

    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store additional task metadata

    # Worker settings
    worker_prefetch_multiplier=1,  # Worker takes 1 task at a time (important for long-running tasks)
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (prevents memory leaks)

    # Retry settings
    task_acks_late=True,  # Task is acked after completion (enables retry on failure)
    task_reject_on_worker_lost=True,  # Requeue task if worker dies

    # Task routing (optional - for multiple queues)
    task_default_queue="celery",  # Default Celery queue
    task_routes={
        "app.workers.tile_worker.generate_tiles_task": {"queue": "tiles"},
        "app.workers.rut_worker.analyze_ruts_task": {"queue": "celery"},
        "app.workers.crown.task.analyze_crown_task": {"queue": "celery"},
        "app.workers.corrugation.task.analyze_corrugation_task": {"queue": "celery"},
        "app.workers.dust.task.analyze_dust_task": {"queue": "celery"},
    },
)

# Optional: Task result backend cleanup
# celery_app.conf.beat_schedule = {
#     "cleanup-old-results": {
#         "task": "celery.backend_cleanup",
#         "schedule": 43200.0,  # Every 12 hours
#     },
# }
