#!/bin/bash

# Start All Celery Workers in Background
# Workers run in background, terminal returns immediately

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate conda environment (support both system conda locations)
CONDA_SH="${CONDA_PREFIX:-$HOME/miniconda3}/etc/profile.d/conda.sh"
if [ ! -f "$CONDA_SH" ]; then
    CONDA_SH="$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh"
fi
source "$CONDA_SH"
conda activate gravelRD

CELERY_BIN="$(which celery)"
LOG_DIR="logs"

mkdir -p "$LOG_DIR"

echo "=========================================="
echo "  Starting Workers in Background"
echo "=========================================="

# Check Redis
+



















echo "[1/3] Checking Redis..."
if ! redis-cli ping &> /dev/null; then
    echo "  ❌ Redis is not running! Start with: sudo systemctl start redis"
    exit 1
fi
echo "  ✓ Redis is running"

# Clean up stale PID files
for pidfile in "$LOG_DIR"/celery_*.pid; do
    [ -f "$pidfile" ] || continue
    pid=$(cat "$pidfile")
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$pidfile"
    fi
done

# Start Tile Worker
echo "[2/3] Starting Tile Worker..."
nohup "$CELERY_BIN" \
    -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=10 \
    --queues=tiles \
    --hostname=tile_worker@%h \
    --logfile="$LOG_DIR/celery_tile_worker.log" \
    --pidfile="$LOG_DIR/celery_tile_worker.pid" \
    > "$LOG_DIR/tile_worker_startup.log" 2>&1 &

echo "  ✓ Tile worker started (PID: $!)"

# Start Rut Worker
echo "[3/3] Starting Rut Worker..."
nohup "$CELERY_BIN" \
    -A app.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=5 \
    --hostname=rut_worker@%h \
    --logfile="$LOG_DIR/celery_rut_worker.log" \
    --pidfile="$LOG_DIR/celery_rut_worker.pid" \
    > "$LOG_DIR/rut_worker_startup.log" 2>&1 &

echo "  ✓ Rut worker started (PID: $!)"

sleep 3

echo ""
echo "=========================================="
echo "  Worker Status"
echo "=========================================="
bash check_workers.sh

echo ""
echo "Monitor logs: tail -f $LOG_DIR/*.log"
echo "=========================================="
