#!/bin/bash

# Rut Analysis Celery Worker Startup Script
# Handles rut distress analysis tasks. Uses uv to manage the env.

cd /home/oguntoye/GravelRoad_Iowa/FastAPI

mkdir -p logs

uv run celery -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=5 \
    --hostname=rut_worker@%h \
    --logfile=logs/celery_rut_worker.log \
    --pidfile=logs/celery_rut_worker.pid
