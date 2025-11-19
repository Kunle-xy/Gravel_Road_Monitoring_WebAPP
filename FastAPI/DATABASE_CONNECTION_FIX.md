# Database Connection Pool Exhaustion Fix

## Problem: Backend Connection Runout

Users experiencing "connection timeout" or "too many connections" errors when:
- Running multiple analyses simultaneously
- Workers processing tasks
- Long-running operations
- Database restarts

## Root Causes

### 1. **Insufficient Connection Pool Size**
```python
# BEFORE (app/database.py):
engine = create_engine(settings.DATABASE_URL)
# Uses default: pool_size=5, max_overflow=10
```

**Problem**:
- Default pool_size = 5 connections
- We have: 2 workers × 2 concurrency each = 4 processes per worker
- Total: Tile worker (4 processes) + Rut worker (4 processes) = **8 worker processes**
- Plus FastAPI server = **9+ total processes**
- **9 processes competing for 5 connections = exhaustion!**

### 2. **No Connection Recycling**
- Connections never recycled → stale connections after DB restart
- No pool_pre_ping → broken connections not detected
- Connections held indefinitely

### 3. **Worker Concurrency**
Each Celery worker runs with:
- `--concurrency=2` (2 parallel processes per worker)
- Each process can hold database connections
- Multiple workers multiply the problem

## The Fix

### Updated `app/database.py`:

```python
engine = create_engine(
    settings.DATABASE_URL,
    # Connection pool settings
    pool_size=20,           # Increased from 5 (supports more concurrent connections)
    max_overflow=10,        # Temporary connections beyond pool_size
    pool_recycle=3600,      # Recycle connections after 1 hour (prevents stale)
    pool_pre_ping=True,     # Test connections before use (catches broken)
    connect_args={
        "connect_timeout": 10,  # Fail fast on connection issues
    },
    echo_pool=False,        # Disable pool logging (set True for debugging)
)
```

### Why These Settings?

**pool_size=20**:
- Handles: 8 worker processes + FastAPI + some headroom
- Each process can get 2-3 connections if needed
- Much safer than default 5

**max_overflow=10**:
- Allows up to 30 total connections (20 + 10) during spikes
- Temporary connections are closed after use

**pool_recycle=3600** (1 hour):
- Connections older than 1 hour are recycled
- Prevents stale connections after DB maintenance
- PostgreSQL default timeout is often 8 hours, so 1 hour is safe

**pool_pre_ping=True**:
- Tests connection with "SELECT 1" before use
- Catches broken connections early
- Slightly slower but much more reliable

**connect_timeout=10**:
- Fail after 10 seconds if DB unreachable
- Prevents indefinite hangs

## Connection Math

### Current Setup:
```
Tile Worker:
  - Main process: 1
  - Child workers (--concurrency=2): 2
  - Total: 3 processes

Rut Worker:
  - Main process: 1
  - Child workers (--concurrency=2): 2
  - Total: 3 processes

FastAPI:
  - Server process: 1

Total Processes: 7

With pool_size=20:
  - Average per process: 20/7 ≈ 3 connections
  - Peak capacity: 30 connections (with overflow)
  - Comfortable headroom: ✅
```

### Before Fix (pool_size=5):
```
Total Processes: 7
Pool Size: 5
Average per process: 5/7 ≈ 0.7 connections
Result: Connection exhaustion! ❌
```

## Additional Considerations

### PostgreSQL max_connections
Check your PostgreSQL max_connections setting:
```sql
SHOW max_connections;
-- Default: 100
```

If you see "too many connections" at PostgreSQL level:
```sql
-- In postgresql.conf:
max_connections = 200

-- Then restart PostgreSQL:
sudo systemctl restart postgresql
```

### Monitoring Connections
```python
# Enable pool logging for debugging:
engine = create_engine(
    settings.DATABASE_URL,
    echo_pool=True,  # Shows connection checkout/checkin
    ...
)
```

Check active connections:
```sql
SELECT count(*) FROM pg_stat_activity;
SELECT * FROM pg_stat_activity WHERE datname='gravel_road_app';
```

## Best Practices Implemented

### 1. ✅ Proper Session Management
All workers use try/finally:
```python
db = SessionLocal()
try:
    # Do work
    db.commit()
finally:
    db.close()  # Always close
```

### 2. ✅ Connection Pooling
- pool_size matches concurrency needs
- max_overflow handles spikes
- pool_recycle prevents stale connections
- pool_pre_ping catches broken connections

### 3. ✅ Worker Configuration
```bash
--concurrency=2              # Reasonable parallelism
--max-tasks-per-child=10     # Restart after 10 tasks (prevents leaks)
worker_prefetch_multiplier=1  # Take 1 task at a time
```

## Testing

### 1. Verify Pool Settings
```python
# In Python shell:
from app.database import engine
print(f"Pool size: {engine.pool.size()}")
print(f"Pool class: {engine.pool.__class__.__name__}")
```

### 2. Load Test
```bash
# Run multiple analyses simultaneously
# Monitor connections:
watch -n 1 'psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='"'"'gravel_road_app'"'"';"'
```

### 3. Check Logs
```bash
# Look for connection errors:
grep -i "connection" logs/celery_*.log
```

## Symptoms of Connection Exhaustion

Before fix:
- ❌ "QueuePool limit of size 5 overflow 10 reached"
- ❌ "FATAL: sorry, too many clients already"
- ❌ "could not connect to server: Connection timed out"
- ❌ Workers hanging/stuck
- ❌ API requests timing out

After fix:
- ✅ Connections available
- ✅ Workers processing smoothly
- ✅ No timeout errors
- ✅ Reliable operation under load

## Rollback (if needed)

If issues occur, revert to defaults:
```python
engine = create_engine(settings.DATABASE_URL)
```

Then debug with:
```python
engine = create_engine(
    settings.DATABASE_URL,
    echo_pool=True,  # Enable logging
    pool_size=5,     # Small pool for debugging
)
```

## Status
- **Fixed**: November 18, 2025
- **Restart required**: Yes (API + workers)
- **Database changes**: None (connection pool is app-level)

---
**Author**: Claude Code
**Date**: November 18, 2025
**Issue**: Database connection pool exhaustion
**Solution**: Increased pool_size, added recycling and pre-ping
