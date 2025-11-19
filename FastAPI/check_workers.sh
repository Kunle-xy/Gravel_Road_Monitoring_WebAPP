#!/bin/bash

# Quick Worker Status Check Script

echo "=========================================="
echo "  Celery Worker Status"
echo "=========================================="
echo ""

# Check Redis
echo "Redis Status:"
if redis-cli ping &> /dev/null; then
    echo "  ✓ Redis is running"
else
    echo "  ❌ Redis is NOT running"
fi
echo ""

# Check Celery workers
WORKER_COUNT=$(ps aux | grep "[c]elery.*worker" | wc -l)

echo "Celery Workers: $WORKER_COUNT main process(es) running"
echo ""

if [ $WORKER_COUNT -gt 0 ]; then
    ps aux | grep "[c]elery.*worker" | grep -v grep | while read line; do
        PID=$(echo $line | awk '{print $2}')
        CMD=$(echo $line | awk '{for(i=11;i<=NF;i++) printf $i" "}')

        if echo "$CMD" | grep -q "tile_worker"; then
            echo "  ✓ Tile Worker (PID: $PID)"
            echo "    Queue: tiles"
            echo "    Log: logs/celery_tile_worker.log"
        elif echo "$CMD" | grep -q "rut_worker"; then
            echo "  ✓ Rut Worker (PID: $PID)"
            echo "    Queue: celery (default)"
            echo "    Log: logs/celery_rut_worker.log"
        else
            echo "  ? Unknown Worker (PID: $PID)"
        fi
        echo ""
    done
else
    echo "  ⚠ No Celery workers are running!"
    echo ""
    echo "  Start workers with: bash start_all_workers.sh"
fi

echo "=========================================="
echo "  Queue Status (Redis)"
echo "=========================================="
echo ""

if redis-cli ping &> /dev/null; then
    CELERY_QUEUE=$(redis-cli -n 0 LLEN celery 2>/dev/null || echo "0")
    TILES_QUEUE=$(redis-cli -n 0 LLEN tiles 2>/dev/null || echo "0")

    echo "Pending tasks in queues:"
    echo "  • celery (rut analysis): $CELERY_QUEUE tasks"
    echo "  • tiles (tile generation): $TILES_QUEUE tasks"
else
    echo "  ⚠ Cannot check queues (Redis not running)"
fi

echo ""
echo "=========================================="
