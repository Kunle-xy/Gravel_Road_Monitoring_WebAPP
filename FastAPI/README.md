# FastAPI Backend

API server for GravelRoad Iowa. Runs on EC2 as a systemd service.

## Stack

FastAPI, PostgreSQL 16, Redis 7, Celery, boto3, GDAL, Rasterio

## Running

```bash
# Managed by systemd
sudo systemctl start fastapi
sudo systemctl status fastapi
sudo journalctl -u fastapi -f   # tail logs
```

## Environment

Config via `FastAPI/.env`. Key vars:

| Variable | Purpose |
|----------|---------|
| DATABASE_URL | PostgreSQL (localhost) |
| CELERY_BROKER_URL | Redis with password |
| CELERY_RESULT_BACKEND | Redis with password |
| S3_BUCKET_RAW | Raw TIFF uploads (gravel-road-raw-file) |
| S3_BUCKET_NAME | Tiles + COGs (gravel-road-app-file) |
| AWS_CLOUDFRONT_DOMAIN | CDN for tile serving |
| FRONTEND_URL | Vercel app URL (CORS) |

AWS credentials come from the EC2 IAM role, not env vars.

## API Endpoints

### Auth
- `POST /auth/register` — register
- `POST /auth/login` — login (returns JWT)
- `GET /auth/me` — current user

### Upload (presigned flow)
- `POST /upload/presign` — get presigned S3 PUT URL
- `POST /upload/complete` — confirm upload, queue processing
- `POST /upload` — legacy direct upload (kept for compatibility)
- `DELETE /upload/{id}` — delete file + S3 objects + tiles

### Files & Folders
- `GET /files/` — list user files
- `GET /files/{id}/tiles` — tile config for map
- `GET /folders/with-files` — folders with files
- `POST /folders` — create folder

### Rut Analysis
- `POST /rut` — submit analysis job
- `GET /rut/{id}/status` — poll job status
- `GET /rut/completed` — list completed jobs

### Tiles
- `GET /tiles/{id}/{z}/{x}/{y}.png` — dynamic tile fallback
- `GET /tiles/{id}/info` — tile metadata

## Database Tables

- `users` — accounts + auth
- `tiff_files` — uploaded files, S3 keys, tile status, bounds
- `folders` — project organization
- `rut_analysis_jobs` — analysis params, status, results
- `refresh_tokens` — JWT refresh tokens

## Workers (run on ISU server, not EC2)

- **Tile worker** (queue: `tiles`) — COG conversion, tile generation, S3 upload
- **Rut worker** (queue: `celery`) — rut detection, plot generation, PDF reports
