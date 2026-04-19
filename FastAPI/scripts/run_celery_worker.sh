#!/bin/bash

# Celery Worker Startup Script
# Starts a Celery worker for tile generation tasks. Uses uv to manage the env.

# Move to the FastAPI project root (parent of scripts/)
cd "$(dirname "$0")/.."

# Load environment variables from .env file
export $(grep -v '^#' .env | xargs)

echo "Starting Celery worker for tile generation..."
echo "Broker: $CELERY_BROKER_URL"
echo "Backend: $CELERY_RESULT_BACKEND"

# Start Celery worker via uv
# -A app.celery_app: Application instance
# --loglevel=info: Logging level
# --concurrency=2: Number of concurrent worker processes (adjust based on CPU cores)
# --max-tasks-per-child=10: Restart worker after 10 tasks to prevent memory leaks
# --queues=tiles: Listen to the 'tiles' queue

uv run celery -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=10 \
    --queues=tiles \
    --hostname=tile_worker@%h
