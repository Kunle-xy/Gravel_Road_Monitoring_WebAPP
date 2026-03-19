#!/bin/bash

# Celery Worker Startup Script
# This script starts a Celery worker for processing tile generation tasks

# Set the working directory to the FastAPI app directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# Load environment variables from .env file
export $(grep -v '^#' .env | xargs)

# Set GDAL/PROJ environment variables for conda environment
export CONDA_PREFIX="/home/oguntoye/miniconda3/envs/gravelRD"
export PROJ_LIB="$CONDA_PREFIX/share/proj"
export GDAL_DATA="$CONDA_PREFIX/share/gdal"

echo "Starting Celery worker for tile generation..."
echo "Broker: $CELERY_BROKER_URL"
echo "Backend: $CELERY_RESULT_BACKEND"
echo "PROJ_LIB: $PROJ_LIB"
echo "GDAL_DATA: $GDAL_DATA"

# Start Celery worker
# -A app.celery_app: Application instance
# --loglevel=info: Logging level
# --concurrency=2: Number of concurrent worker processes (adjust based on CPU cores)
# --max-tasks-per-child=10: Restart worker after 10 tasks to prevent memory leaks
# --queues=tiles: Listen to the 'tiles' queue

celery -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=10 \
    --queues=tiles \
    --hostname=tile_worker@%h

# Alternative for development with auto-reload:
# celery -A app.celery_app worker --loglevel=info --concurrency=2 --pool=solo --autoreload
