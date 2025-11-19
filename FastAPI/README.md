# FastAPI Backend - GravelRoad Iowa

Backend API server for the GravelRoad Iowa pavement distress analysis system.

**Author**: Kunle Oguntoye, PhD Student at Iowa State University
**Contact**: oguntoye@iastate.edu

---

## Tech Stack

- **Framework**: FastAPI (async Python)
- **Database**: PostgreSQL + SQLAlchemy
- **Task Queue**: Celery + Redis
- **Storage**: AWS S3 + CloudFront
- **Geospatial**: GDAL, Rasterio, Shapely, PyProj
- **Visualization**: Plotly, WeasyPrint

---

## Setup

### Install Dependencies
```bash
# System dependencies
sudo apt-get install gdal-bin python3-gdal postgresql redis-server

# Python environment
conda create -n gravelRD python=3.10
conda activate gravelRD
pip install -r requirements.txt
```

### Configure
Create `.env`:
```bash
DATABASE_URL=postgresql://user:password@localhost/gravel_road_app
SECRET_KEY=your-secret-key
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=gravel-road-app
S3_BUCKET_RAW=gravel-road-raw
AWS_CLOUDFRONT_DOMAIN=xxxxx.cloudfront.net
CELERY_BROKER_URL=redis://localhost:6379/0
```

### Run
```bash
# Database
createdb gravel_road_app
alembic upgrade head

# Start services
sudo systemctl start redis
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start workers (separate terminal)
bash start_all_workers.sh
```

---

## Structure

```
app/
├── routers/              # API endpoints
│   ├── auth.py
│   ├── files.py
│   ├── folders.py
│   ├── upload.py
│   └── rut_analysis.py
├── workers/             # Celery tasks
│   ├── tile_worker.py   # COG conversion & tiles
│   └── rut_worker.py    # Rut analysis
├── models.py            # Database models
├── schemas.py           # Pydantic schemas
├── config.py            # Settings
└── celery_app.py        # Celery config
```

---

## API Endpoints

### Authentication
- `POST /auth/login` - Login (returns JWT)
- `POST /auth/register` - Register user
- `GET /auth/me` - Get current user

### Files
- `GET /files/` - List files
- `DELETE /files/{id}` - Delete file
- `GET /files/{id}/tiles` - Get tile config

### Folders
- `GET /folders/with-files` - List folders
- `POST /folders` - Create folder
- `DELETE /folders/{id}` - Delete folder

### Rut Analysis
- `POST /rut` - Create analysis job
- `GET /rut/{id}/status` - Poll status
- `GET /rut/completed` - List completed jobs

### Upload
- `POST /upload/init` - Init multipart upload
- `POST /upload/complete` - Complete upload

---

## Workers

### Tile Worker (queue: `tiles`)
- Converts TIFF to COG
- Generates map tiles
- Uploads to S3

### Rut Worker (queue: `celery`)
- Analyzes rut distress
- Generates plots & PDF reports
- Uploads results to S3

### Management
```bash
# Start with live logs
bash start_all_workers.sh

# Start in background
bash start_workers_background.sh

# Watch logs
bash watch_logs.sh

# Check status
bash check_workers.sh

# Stop all
bash stop_all_workers.sh
```

---

## Database Models

- **users**: User accounts
- **tiff_files**: Uploaded DEM files
- **folders**: Project folders
- **rut_analysis_jobs**: Analysis results
- **polygons**: Saved geometries

---

## Recent Fixes

1. ✅ Queue routing - tasks route to correct workers
2. ✅ AWS credentials - uses environment variables
3. ✅ S3 paths - prefers original DEM files
4. ✅ CRS transformation - auto-converts lat/lon
5. ✅ Settings - correct attribute names
6. ✅ Download URLs - added to status endpoint

---

**Last Updated**: November 18, 2025
