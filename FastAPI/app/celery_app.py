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
    include=["app.workers.tile_worker"]  # Auto-discover tasks
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
    task_time_limit=3600,  # 1 hour hard time limit
    task_soft_time_limit=3300,  # 55 minutes soft time limit

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
    task_default_queue="tiles",
    task_routes={
        "app.workers.tile_worker.generate_tiles_task": {"queue": "tiles"},
    },
)

# Optional: Task result backend cleanup
# celery_app.conf.beat_schedule = {
#     "cleanup-old-results": {
#         "task": "celery.backend_cleanup",
#         "schedule": 43200.0,  # Every 12 hours
#     },
# }
