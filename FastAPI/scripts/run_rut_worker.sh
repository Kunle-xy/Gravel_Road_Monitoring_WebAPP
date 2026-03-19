#!/bin/bash

# Rut Analysis Celery Worker Startup Script
# This worker handles rut distress analysis tasks

cd /home/oguntoye/GravelRoad_Iowa/FastAPI

# Activate conda environment
source /home/oguntoye/miniconda3/etc/profile.d/conda.sh
conda activate gravelRD

# Create logs directory if it doesn't exist
mkdir -p logs

# Start Celery worker for rut analysis
/home/oguntoye/miniconda3/envs/gravelRD/bin/celery -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=5 \
    --hostname=rut_worker@%h \
    --logfile=logs/celery_rut_worker.log \
    --pidfile=logs/celery_rut_worker.pid
