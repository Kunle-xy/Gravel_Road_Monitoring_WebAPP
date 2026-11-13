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

### Road direction and polygon rotation

Rut, crown, and corrugation forms share a **Road direction** selection for
each drawn polygon. **Horizontal** is the default. The direction describes
the road before rotating the rectangle:

| Road direction | Rut / crown profiles | Corrugation profiles |
|---|---|---|
| Horizontal | Across the road (local vertical) | Along the road (local horizontal) |
| Vertical | Across the road (local horizontal) | Along the road (local vertical) |

All profiles and map overlays follow polygon rotation, including square
polygons. The original horizontal edge is tracked through rotation and
resizing; the longest side is not used to guess road direction. Spacing
and sampling distances retain their existing meter units. The DEM is not
rotated or resampled.

The map and the three analysis forms use the same selected polygon. Each
polygon retains its own Horizontal/Vertical choice when switching forms or
selecting another polygon. Clicking an empty map area hides editing handles
without resetting the analysis selection. A newly drawn polygon starts with
Horizontal selected. Drawn polygons/settings currently live in the dashboard
session; a full page reload clears them.

The selected polygon displays a live, illustrative direction preview: dashed
amber lines show rut/crown sampling and dashed cyan lines show corrugation
sampling. These are direction guides, not the actual sampling density or
detected-distress results. Rotation/resize commits on release, cancellation,
window blur, or editing-handle cleanup. Analyses are blocked during an active
drag so partially edited geometry is not submitted.

Changing the polygon, DEM, or road direction removes old overlays and marks
previous results as requiring a rerun. An already submitted job remains a
snapshot of its original settings; changing controls does not recalculate it.
Late overlay/status responses must not replace a newer selection or job.

Frontend interaction regression checks, from `webapp/`:

```bash
npm run test:polygons
```

Each job saves its road direction and edge index in `polygon_geojson`.
No database migration is required. Existing results are unchanged; rerun
analysis to generate results with the new sampling behavior.

After deploying, restart `fastapi` and `celery-analysis`, and deploy the
updated frontend. Run the sampling regression checks from `FastAPI/` with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

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
