#!/bin/bash

# Stop All Celery Workers Script
# This script safely stops all running Celery workers

echo "=========================================="
echo "  Stopping All Celery Workers"
echo "=========================================="
echo ""

# Find all celery worker processes
CELERY_PIDS=$(ps aux | grep "[c]elery.*worker" | awk '{print $2}')

if [ -z "$CELERY_PIDS" ]; then
    echo "✓ No Celery workers are currently running"
    exit 0
fi

echo "Found the following Celery worker processes:"
ps aux | grep "[c]elery.*worker" | awk '{print "  PID: " $2 " - " $NF}'
echo ""

# Ask for confirmation
read -p "Do you want to stop all these workers? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled. No workers were stopped."
    exit 0
fi

echo ""
echo "Stopping workers..."
echo ""

# Stop tile worker
echo "1. Stopping tile worker..."
TILE_WORKER_PIDS=$(ps aux | grep "[c]elery.*tile_worker" | awk '{print $2}')
if [ -n "$TILE_WORKER_PIDS" ]; then
    pkill -f "celery.*tile_worker"
    sleep 2
    # Force kill if still running
    TILE_WORKER_PIDS=$(ps aux | grep "[c]elery.*tile_worker" | awk '{print $2}')
    if [ -n "$TILE_WORKER_PIDS" ]; then
        echo "   Force killing tile worker..."
        pkill -9 -f "celery.*tile_worker"
    fi
    echo "   ✓ Tile worker stopped"
else
    echo "   ✓ Tile worker was not running"
fi

# Stop rut worker
echo "2. Stopping rut worker..."
RUT_WORKER_PIDS=$(ps aux | grep "[c]elery.*rut_worker" | awk '{print $2}')
if [ -n "$RUT_WORKER_PIDS" ]; then
    pkill -f "celery.*rut_worker"
    sleep 2
    # Force kill if still running
    RUT_WORKER_PIDS=$(ps aux | grep "[c]elery.*rut_worker" | awk '{print $2}')
    if [ -n "$RUT_WORKER_PIDS" ]; then
        echo "   Force killing rut worker..."
        pkill -9 -f "celery.*rut_worker"
    fi
    echo "   ✓ Rut worker stopped"
else
    echo "   ✓ Rut worker was not running"
fi

# Stop any other celery workers
echo "3. Stopping any other celery workers..."
OTHER_PIDS=$(ps aux | grep "[c]elery.*worker" | awk '{print $2}')
if [ -n "$OTHER_PIDS" ]; then
    pkill -f "celery.*worker"
    sleep 2
    # Force kill if still running
    OTHER_PIDS=$(ps aux | grep "[c]elery.*worker" | awk '{print $2}')
    if [ -n "$OTHER_PIDS" ]; then
        echo "   Force killing remaining workers..."
        pkill -9 -f "celery.*worker"
    fi
    echo "   ✓ Other workers stopped"
else
    echo "   ✓ No other workers running"
fi

echo ""
echo "=========================================="
echo "  Verification"
echo "=========================================="

sleep 1

REMAINING=$(ps aux | grep "[c]elery.*worker" | wc -l)

if [ $REMAINING -eq 0 ]; then
    echo "✓ All Celery workers have been stopped successfully"
    echo ""
    echo "To start workers again, run:"
    echo "  bash start_all_workers.sh"
else
    echo "⚠ Warning: Some workers may still be running"
    echo "Run 'ps aux | grep celery' to check"
fi

echo "=========================================="
