# Operations

## Common Tasks

### Restart a service

```bash
sudo systemctl restart fastapi
sudo systemctl restart celery-tiles
sudo systemctl restart celery-analysis
sudo systemctl restart cloudflared
```

### Check all services

```bash
sudo systemctl status fastapi celery-tiles celery-analysis cloudflared postgresql redis-server --no-pager
```

### Tail logs

```bash
sudo journalctl -u fastapi -f
sudo journalctl -u celery-tiles -f
sudo journalctl -u celery-analysis -f
sudo journalctl -u cloudflared -f
```

### Test Redis

```bash
redis-cli -a <password> ping
```

### Test PostgreSQL

```bash
PGPASSWORD=<password> psql -h localhost -U kunle_admin -d gravel_road_app -c "SELECT 1"
```

### Check active DB connections

```sql
SELECT count(*) FROM pg_stat_activity WHERE datname='gravel_road_app';
```

### Test Cloudflare Tunnel

```bash
curl https://api.prosper-gravelroad.com/docs
```

### Check S3 access

```python
import boto3
s3 = boto3.client('s3', region_name='us-east-2')
print(s3.list_objects_v2(Bucket='gravel-road-raw-file', MaxKeys=1))
```

### Deploy code changes

```bash
cd ~/GravelRoad_Iowa
git pull
sudo systemctl restart fastapi celery-tiles celery-analysis
```

## Troubleshooting

### FastAPI won't start

```bash
sudo journalctl -u fastapi --no-pager -n 50
```

Common causes:
- `.env` syntax error
- Redis not running (`sudo systemctl start redis-server`)
- PostgreSQL not running (`sudo systemctl start postgresql`)
- Port 8000 already in use (kill stale process: `lsof -i :8000`)

### Tunnel not working

```bash
sudo systemctl status cloudflared --no-pager
sudo journalctl -u cloudflared --no-pager -n 20
```

Common causes:
- Config file missing or malformed (`cat /etc/cloudflared/config.yml`)
- Credentials file missing
- ISU network blocking outbound QUIC (rare)

### Tiles not loading

1. Check tile_status in DB: `SELECT tile_status, tile_error FROM tiff_files WHERE id='...';`
2. Verify CloudFront is serving: `curl https://d18o6mwudgwpmq.cloudfront.net/tiles/.../15/0/0.png`
3. Check Celery tile worker: `sudo journalctl -u celery-tiles -f`

### Upload failures

1. Check S3 bucket CORS (must allow PUT from Vercel origin)
2. Check presigned URL expiry (1 hour)
3. Check FastAPI logs for /upload/presign errors

### Analysis job stuck

1. Check Celery analysis worker: `sudo journalctl -u celery-analysis -f`
2. Check job status in DB: `SELECT status, error_message FROM rut_analysis_jobs WHERE id='...';`
3. Restart worker: `sudo systemctl restart celery-analysis`

## DB Connection Pool

Pool is configured in `app/database.py`: pool_size=20, max_overflow=10, pool_recycle=3600, pool_pre_ping=True. Handles ~30 concurrent connections across FastAPI + workers.

## Distress Analysis Notes

### Rut
- Severity: Low (0.5-1.0"), Medium (1.0-3.0"), High (>3.0")
- Iowa DOT deduct table lookup with density interpolation
- Output: HTML plot + PDF report (presigned S3 URLs, 7-day expiry)

### Crown
- Severity: Low (<1"), Medium (1-3"), High (>3")
- Measures camber distress in linear feet
- Output: HTML report

### Corrugation
- Severity: Low (<1"), Medium (1-3"), High (>3")
- Detects washboarding patterns via peak/valley analysis
- Output: HTML report

All analyses support neighbor frequency evaluation (tests range around primary sampling frequency).
