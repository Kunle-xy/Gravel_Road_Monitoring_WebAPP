# Operations

## Common Tasks

### Restart FastAPI (after code or .env changes)
```bash
sudo systemctl restart fastapi
sudo journalctl -u fastapi -f
```

### Check all services
```bash
sudo systemctl status fastapi redis postgresql@16-main
```

### Test Redis auth
```bash
redis-cli -a <password> ping
```

### Test PostgreSQL
```bash
psql -U kunle_admin -d gravel_road_app -c "SELECT 1"
```

### Check active DB connections
```sql
SELECT count(*) FROM pg_stat_activity WHERE datname='gravel_road_app';
```

### Check S3 access
```python
import boto3
s3 = boto3.client('s3', region_name='us-east-2')
print(s3.list_objects_v2(Bucket='gravel-road-raw-file', MaxKeys=1))
```

## Troubleshooting

### FastAPI won't start
```bash
sudo journalctl -u fastapi --no-pager -n 50
```
Common causes: .env syntax error, Redis down, PostgreSQL down.

### Tiles not loading
1. Check tile_status in DB: `SELECT tile_status, tile_error FROM tiff_files WHERE id='...';`
2. Verify CloudFront is serving: `curl https://d18o6mwudgwpmq.cloudfront.net/tiles/.../15/0/0.png`
3. Check Celery worker logs on ISU server

### Upload failures
1. Check S3 bucket CORS (must allow PUT from Vercel origin)
2. Check presigned URL expiry (1 hour)
3. Check FastAPI logs for /upload/presign errors

### Worker not processing
1. Verify Redis reachable from ISU: `redis-cli -h 52.15.33.164 -a <password> ping`
2. Verify PostgreSQL reachable: `psql -h 52.15.33.164 -U kunle_admin -d gravel_road_app`
3. Check Celery worker logs on ISU server

## DB Connection Pool
Pool is configured in `app/database.py`: pool_size=20, max_overflow=10, pool_recycle=3600, pool_pre_ping=True. Handles ~30 concurrent connections across FastAPI + workers.

## Rut Analysis Notes
- Severity: Low (0.5-1.0"), Medium (1.0-3.0"), High (>3.0")
- Iowa DOT deduct table lookup with density interpolation
- Neighbor frequency evaluation available (tests range around primary sampling freq)
- Results: presigned S3 URLs for HTML plots + PDF reports (7-day expiry)
