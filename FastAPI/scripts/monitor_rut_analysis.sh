#!/bin/bash

# Real-time Rut Analysis Monitoring Script
# Shows live logs from rut worker and analysis progress

echo "==================================================="
echo "   Rut Analysis Monitoring Dashboard"
echo "==================================================="
echo ""

# Check if rut worker is running
echo "1. Checking Rut Worker Status..."
RUT_WORKER_PID=$(ps aux | grep "celery.*rut_worker@" | grep -v grep | awk '{print $2}' | head -1)

if [ -z "$RUT_WORKER_PID" ]; then
    echo "   ❌ RUT WORKER IS NOT RUNNING!"
    echo "   Start it with: bash run_rut_worker.sh"
    exit 1
else
    echo "   ✅ Rut worker is running (PID: $RUT_WORKER_PID)"
fi

echo ""
echo "2. Recent Rut Analysis Jobs (last 5):"
echo "---------------------------------------------------"
PGPASSWORD=prosper psql -h localhost -U kunle_admin -d gravel_road_app -c "
    SELECT
        id,
        status,
        progress || '%' as progress,
        total_ruts_detected as ruts,
        to_char(created_at, 'HH24:MI:SS') as created
    FROM rut_analysis_jobs
    ORDER BY created_at DESC
    LIMIT 5;
" -t

echo ""
echo "3. Active/Pending Jobs:"
echo "---------------------------------------------------"
PGPASSWORD=prosper psql -h localhost -U kunle_admin -d gravel_road_app -c "
    SELECT
        id,
        status,
        progress || '%' as progress,
        CASE
            WHEN error_message IS NOT NULL THEN LEFT(error_message, 50)
            ELSE 'No errors'
        END as error
    FROM rut_analysis_jobs
    WHERE status IN ('pending', 'processing')
    ORDER BY created_at DESC;
" -t

echo ""
echo "4. Recent Worker Logs (last 20 lines):"
echo "---------------------------------------------------"
tail -20 /home/oguntoye/GravelRoad_Iowa/FastAPI/logs/celery_rut_worker.log

echo ""
echo "5. Detailed Analysis Logs (if any):"
echo "---------------------------------------------------"
if [ -f /home/oguntoye/GravelRoad_Iowa/FastAPI/logs/rut_analysis.log ]; then
    tail -20 /home/oguntoye/GravelRoad_Iowa/FastAPI/logs/rut_analysis.log
else
    echo "   No analysis logs yet"
fi

echo ""
echo "==================================================="
echo "To watch logs in real-time, run:"
echo "  tail -f /home/oguntoye/GravelRoad_Iowa/FastAPI/logs/celery_rut_worker.log"
echo "==================================================="
