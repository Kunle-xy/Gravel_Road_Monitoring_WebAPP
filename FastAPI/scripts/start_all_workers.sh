#!/bin/bash

# Start All Celery Workers Script
# This script starts all required Celery workers for the GravelRoad application

cd /home/oguntoye/GravelRoad_Iowa/FastAPI

echo "=========================================="
echo "  Starting All Celery Workers"
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

# Check if any workers are already running
echo "2. Checking for existing workers..."
EXISTING_WORKERS=$(ps aux | grep "[c]elery.*worker" | wc -l)
if [ $EXISTING_WORKERS -gt 0 ]; then
    echo "   ⚠ Warning: Found $EXISTING_WORKERS existing worker(s):"
    ps aux | grep "[c]elery.*worker" | awk '{print "     PID: " $2 " - " $NF}'
    echo ""
    read -p "   Stop existing workers and restart? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   Stopping existing workers..."
        bash stop_all_workers.sh
        sleep 2
    else
        echo "   Cancelled. Keeping existing workers running."
        exit 0
    fi
fi
echo "   ✓ No existing workers found"
echo ""

echo "=========================================="
echo "  Starting Workers"
echo "=========================================="
echo ""

# Start Tile Worker
echo "3. Starting Tile Worker..."
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

TILE_WORKER_PID=$!
echo "   Started with PID: $TILE_WORKER_PID"
sleep 3

# Verify tile worker started
if ps -p $TILE_WORKER_PID > /dev/null; then
    echo "   ✓ Tile worker started successfully"
else
    echo "   ❌ Tile worker failed to start. Check logs/tile_worker_startup.log"
fi
echo ""

# Start Rut Worker
echo "4. Starting Rut Worker..."
nohup /home/oguntoye/miniconda3/envs/gravelRD/bin/celery \
    -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=5 \
    --hostname=rut_worker@%h \
    --logfile=logs/celery_rut_worker.log \
    --pidfile=logs/celery_rut_worker.pid \
    > logs/rut_worker_startup.log 2>&1 &

RUT_WORKER_PID=$!
echo "   Started with PID: $RUT_WORKER_PID"
sleep 3

# Verify rut worker started
if ps -p $RUT_WORKER_PID > /dev/null; then
    echo "   ✓ Rut worker started successfully"
else
    echo "   ❌ Rut worker failed to start. Check logs/rut_worker_startup.log"
fi
echo ""

echo "=========================================="
echo "  Worker Status Summary"
echo "=========================================="
echo ""

sleep 2

# Show all running celery workers
WORKER_COUNT=$(ps aux | grep "[c]elery.*worker" | wc -l)

if [ $WORKER_COUNT -eq 0 ]; then
    echo "❌ No workers are running!"
    echo ""
    echo "Check startup logs:"
    echo "  cat logs/tile_worker_startup.log"
    echo "  cat logs/rut_worker_startup.log"
else
    echo "✓ Running workers ($WORKER_COUNT main processes):"
    echo ""
    ps aux | grep "[c]elery.*worker" | grep -v grep | awk '{print "  • " $11 " " $12 " " $13 " " $14 " (PID: " $2 ")"}'
    echo ""
    echo "Worker Details:"
    echo "  • Tile Worker:"
    echo "    - Queue: tiles"
    echo "    - Handles: TIFF → COG conversion, tile generation"
    echo "    - Log: logs/celery_tile_worker.log"
    echo ""
    echo "  • Rut Worker:"
    echo "    - Queue: celery (default)"
    echo "    - Handles: Rut distress analysis"
    echo "    - Log: logs/celery_rut_worker.log"
fi

echo ""
echo "=========================================="
echo "  Monitoring Logs"
echo "=========================================="
echo ""
echo "Starting live log monitoring..."
echo "Press CTRL+C to stop watching logs (workers will continue running)"
echo ""
sleep 2

# Tail all worker logs
tail -f logs/celery_tile_worker.log logs/celery_rut_worker.log
