# FastAPI Backend

API server for GravelRoad Iowa. Runs on the ISU server as a systemd service, accessible via Cloudflare Tunnel at https://api.prosper-gravelroad.com.

## Stack

FastAPI, PostgreSQL 16, Redis 7, Celery, boto3, GDAL, Rasterio, UV

## Running

```bash
# Managed by systemd
sudo systemctl start fastapi
sudo systemctl status fastapi
sudo journalctl -u fastapi -f   # tail logs

# Celery workers
sudo systemctl start celery-tiles celery-analysis
```

## Environment

Config via `FastAPI/.env`. Key vars:

| Variable | Purpose |
|----------|---------|
| DATABASE_URL | PostgreSQL (localhost) |
| CELERY_BROKER_URL | Redis with password (localhost) |
| CELERY_RESULT_BACKEND | Redis with password (localhost) |
| S3_BUCKET_RAW | Raw TIFF uploads (gravel-road-raw-file) |
| S3_BUCKET_NAME | Tiles + COGs (gravel-road-app-file) |
| AWS_CLOUDFRONT_DOMAIN | CDN for tile serving |
| FRONTEND_URL | Vercel app URL (CORS) |
| AWS_ACCESS_KEY_ID | S3/CloudFront/SES access |
| AWS_SECRET_ACCESS_KEY | S3/CloudFront/SES access |

## Dependencies

Managed with UV:

```bash
uv add <package>     # add dependency
uv remove <package>  # remove
uv run <command>     # run within venv
```

## API Endpoints

### Auth
- `POST /auth/register` — register
- `POST /auth/login` — login (returns JWT in HttpOnly cookie)
- `POST /auth/refresh` — refresh access token
- `GET /auth/me` — current user
- `POST /auth/logout` — revoke tokens

### Upload (presigned flow)
- `POST /upload/presign` — get presigned S3 PUT URL
- `POST /upload/complete` — confirm upload, queue processing
- `POST /upload/multipart/init` — start multipart upload (>100MB)
- `POST /upload/multipart/presign-part` — presign a chunk
- `POST /upload/multipart/complete` — finish multipart upload
- `DELETE /upload/{id}` — delete file + S3 objects + tiles

### Files & Folders
- `GET /files/` — list user files
- `GET /files/{id}/tiles` — tile config for map
- `GET /folders/with-files` — folders with files
- `POST /folders` — create folder
- `PATCH /folders/{id}` — update folder
- `DELETE /folders/{id}` — delete folder + files

### Distress Analysis
- `POST /rut` — submit rut analysis job
- `POST /crown` — submit crown analysis job
- `POST /corrugation` — submit corrugation analysis job
- `GET /rut/{id}/status` — poll job status (same pattern for crown, corrugation)
- `GET /rut/completed` — list completed jobs

### Tiles
- `GET /tiles/{id}/{z}/{x}/{y}.png` — dynamic tile fallback
- `GET /tiles/{id}/info` — tile metadata
- `GET /tiles/{id}/status` — tile generation progress

## Database Tables

- `users` — accounts, auth, lockout tracking
- `tiff_files` — uploaded files, S3 keys, tile status, bounds
- `folders` — project organization
- `refresh_tokens` — JWT refresh tokens with family rotation
- `rut_analysis_jobs` — rut analysis params, status, results
- `crown_analysis_jobs` — crown analysis params, status, results
- `corrugation_analysis_jobs` — corrugation analysis params, status, results

## Workers

Both run on the ISU server via systemd:

- **Tile worker** (queue: `tiles`, concurrency: 4) — COG conversion, tile generation, S3 upload
- **Analysis worker** (queue: `celery`, concurrency: 3) — rut/crown/corrugation detection, plot generation, reports
