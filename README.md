# GravelRoad Iowa - Pavement Distress Analysis System

A full-stack web application for analyzing pavement conditions in Iowa gravel roads using high-resolution DEM (Digital Elevation Model) data. The system provides automated rut detection and interactive visualization of road distress patterns.

**Author**: Kunle Oguntoye, PhD Student at Iowa State University
**Contact**: oguntoye@iastate.edu

---

## System Overview

### Architecture
- **Backend**: FastAPI (Python) with PostgreSQL database
- **Frontend**: Next.js 15 (React) with TypeScript and Tailwind CSS
- **Task Queue**: Celery with Redis broker
- **Storage**: AWS S3 + CloudFront CDN
- **Map Engine**: Leaflet with custom tile layers

### Key Features
1. **DEM File Management**: Upload and organize large TIFF/GeoTIFF files in project folders
2. **Interactive Map Viewer**: Real-time visualization with custom tile layers served via CloudFront
3. **Automated Rut Detection**: Machine learning-based analysis of road surface depressions
4. **Polygon Drawing**: Define analysis regions directly on the map
5. **Distress Analysis**: Multiple distress types (Rut, Pothole, Crocodile Cracking, etc.)
6. **Report Generation**: Interactive HTML plots and downloadable PDF reports
7. **Job Management**: Track completed analyses with quick access to results

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- AWS Account (S3 + CloudFront)
- GDAL system libraries

### 1. Backend Setup (FastAPI)
```bash
cd FastAPI

# Create conda environment
conda create -n gravelRD python=3.10
conda activate gravelRD

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your AWS/database credentials

# Start Redis
sudo systemctl start redis

# Run database migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery workers (separate terminal)
bash start_all_workers.sh
```

### 2. Frontend Setup (Next.js)
```bash
cd webapp

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local with API URL

# Start development server
npm run dev
```

### 3. Access Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Project Structure

```
GravelRoad_Iowa/
├── FastAPI/                 # Backend application
│   ├── app/
│   │   ├── routers/        # API endpoints
│   │   ├── workers/        # Celery tasks
│   │   ├── models.py       # Database models
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── config.py       # Settings
│   ├── logs/               # Worker logs
│   ├── alembic/            # Database migrations
│   └── *.sh                # Worker management scripts
│
├── webapp/                  # Frontend application
│   ├── app/
│   │   ├── components/     # React components
│   │   ├── contexts/       # State management
│   │   ├── lib/            # Utilities & API client
│   │   └── dashboard/      # Main app pages
│   └── public/             # Static assets
│
└── README.md               # This file
```

---

## Core Workflows

### 1. Upload and Visualize DEM Files
1. Login to application
2. Navigate to "Upload Files"
3. Select DEM file (TIFF/GeoTIFF) and project folder
4. Upload → Backend converts to COG and generates map tiles
5. View file on interactive map with custom tile layer

### 2. Run Rut Analysis
1. Select DEM file from sidebar
2. Draw polygon on map to define analysis region
3. Open "Rut Automatic Detection" panel
4. Configure parameters (sampling frequency, width, smoothing)
5. Click "Run Analysis" → Celery worker processes in background
6. View progress bar (polling every 2 seconds)
7. Download results (interactive HTML plot + PDF report)
8. Access completed jobs from sidebar

### 3. Manage Projects
- Create folders to organize files by project/location
- Drag and drop files between folders
- Sort projects by name or file count
- Expand/collapse folder tree view

---

## Worker Management

### Start Workers (with live logs)
```bash
bash start_all_workers.sh
# Press Ctrl+C to stop watching logs (workers keep running)
```

### Start Workers (background, no logs)
```bash
bash start_workers_background.sh
```

### Watch Logs (workers already running)
```bash
bash watch_logs.sh
```

### Check Worker Status
```bash
bash check_workers.sh
```

### Stop All Workers
```bash
bash stop_all_workers.sh
```

### Worker Types
- **Tile Worker**: Handles TIFF→COG conversion and tile generation (queue: `tiles`)
- **Rut Worker**: Handles rut distress analysis (queue: `celery`)

---

## Configuration

### Backend (.env)
```bash
DATABASE_URL=postgresql://user:password@localhost/gravel_road_app
SECRET_KEY=your-secret-key-here
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=gravel-road-app        # Tiles bucket
S3_BUCKET_RAW=gravel-road-raw         # Uploads bucket
AWS_CLOUDFRONT_DOMAIN=xxxxx.cloudfront.net
CELERY_BROKER_URL=redis://localhost:6379/0
FRONTEND_URL=http://localhost:3000
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Common Issues & Solutions

### Tiles Not Loading
- Check CloudFront distribution is deployed
- Verify S3 bucket CORS configuration
- Ensure tile generation completed (check `tile_status` in database)

### Upload Failures
- Verify S3 bucket permissions
- Check multipart upload settings (max 10GB per file)
- Review upload logs in browser console

### Worker Issues
- Ensure Redis is running: `redis-cli ping`
- Check worker logs: `tail -f logs/celery_*.log`
- Verify conda environment: `conda activate gravelRD`
- Restart workers: `bash stop_all_workers.sh && bash start_all_workers.sh`

### Rut Analysis Errors
- All major issues have been fixed (CRS transformation, S3 paths, queue routing)
- Check logs if issues persist: `tail -f logs/celery_rut_worker.log`

---

## Recent Improvements (November 2025)
1. ✅ Fixed queue routing - tasks now route to correct workers
2. ✅ Fixed AWS credentials handling - uses environment variables
3. ✅ Fixed S3 file paths - prefers original DEM for analysis
4. ✅ Fixed CRS transformation - automatic lat/lon to projected coordinates
5. ✅ Fixed settings attributes - correct S3 bucket names
6. ✅ Fixed progress bar visibility - improved contrast
7. ✅ Added download URLs to status endpoint
8. ✅ Added "Completed Jobs" widget to sidebar

---

## Support

For issues or questions:
- **Email**: oguntoye@iastate.edu

---

**Last Updated**: November 18, 2025
