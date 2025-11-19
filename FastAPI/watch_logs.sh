#!/bin/bash

# Watch Worker Logs in Real-Time

cd /home/oguntoye/GravelRoad_Iowa/FastAPI

echo "=========================================="
echo "  Live Worker Logs"
echo "=========================================="
echo ""
echo "Watching both tile and rut worker logs..."
echo "Press CTRL+C to stop"
echo ""
echo "=========================================="
echo ""

# Check if log files exist
if [ ! -f logs/celery_tile_worker.log ] && [ ! -f logs/celery_rut_worker.log ]; then
    echo "⚠ No log files found!"
    echo ""
    echo "Make sure workers are running:"
    echo "  bash start_all_workers.sh"
    exit 1
fi

# Tail both logs with labels
tail -f logs/celery_tile_worker.log logs/celery_rut_worker.log
