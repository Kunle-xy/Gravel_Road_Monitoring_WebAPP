#!/bin/bash

# Start All Celery Workers in Background (No Log Monitoring)
# Workers run in background, terminal returns immediately

cd /home/oguntoye/GravelRoad_Iowa/FastAPI

echo "=========================================="
echo "  Starting Workers in Background"
echo "=========================================="
echo ""

# Activate conda environment
source /home/oguntoye/miniconda3/etc/profile.d/conda.sh
conda activate gravelRD

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if Redis is running
echo "1. Checking Redis..."
if ! redis-cli ping &> /dev/null; then
    echo "   ❌ Error: Redis is not running!"
    echo "   Start Redis with: sudo systemctl start redis"
    exit 1
fi
echo "   ✓ Redis is running"
echo ""

# Start Tile Worker
echo "2. Starting Tile Worker..."
nohup /home/oguntoye/miniconda3/envs/gravelRD/bin/celery \
    -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=10 \
    --queues=tiles \
    --hostname=tile_worker@%h \
    --logfile=logs/celery_tile_worker.log \
    --pidfile=logs/celery_tile_worker.pid \
    > logs/tile_worker_startup.log 2>&1 &

echo "   ✓ Tile worker started"
echo ""

# Start Rut Worker
echo "3. Starting Rut Worker..."
nohup /home/oguntoye/miniconda3/envs/gravelRD/bin/celery \
    -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=5 \
    --hostname=rut_worker@%h \
    --logfile=logs/celery_rut_worker.log \
    --pidfile=logs/celery_rut_worker.pid \
    > logs/rut_worker_startup.log 2>&1 &

echo "   ✓ Rut worker started"
echo ""

sleep 3

echo "=========================================="
echo "  Worker Status"
echo "=========================================="
echo ""

# Show running workers
bash check_workers.sh

echo ""
echo "Workers are running in background."
echo ""
echo "Monitor logs with:"
echo "  tail -f logs/celery_tile_worker.log"
echo "  tail -f logs/celery_rut_worker.log"
echo "  tail -f logs/*.log"
echo ""
echo "=========================================="
