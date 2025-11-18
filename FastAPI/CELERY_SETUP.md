# Celery + CloudFront Tile Generation Setup

This guide explains how to set up and run the Celery-based tile generation system with CloudFront CDN delivery.

## Architecture Overview

- **FastAPI**: Main application server
- **Celery**: Distributed task queue for tile generation
- **Redis**: Message broker and result backend for Celery
- **S3 Buckets**:
  - `gravel-road-raw`: Raw uploaded TIFF files and COGs
  - `gravel-road-app`: Generated tiles and processed files
- **CloudFront**: CDN for fast tile delivery to frontend

## Prerequisites

1. Python 3.9+
2. Redis server
3. GDAL system libraries
4. AWS credentials with S3 and CloudFront access

## Installation Steps

### 1. Install Redis

#### Ubuntu/Debian (WSL2):
```bash
sudo apt-get update
sudo apt-get install -y redis-server

# Start Redis
sudo service redis-server start

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

#### macOS:
```bash
brew install redis

# Start Redis
brew services start redis

# Verify
redis-cli ping
```

#### Docker (Alternative):
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

### 2. Install GDAL (if not already installed)

#### Ubuntu/Debian:
```bash
sudo apt-get install -y gdal-bin python3-gdal
```

#### macOS:
```bash
brew install gdal
```

Verify GDAL installation:
```bash
gdal_translate --version
gdal2tiles.py --version
```

### 3. Install Python Dependencies

```bash
cd FastAPI
pip install -r requirements.txt
```

This will install:
- `celery==5.4.0` - Task queue framework
- `redis==5.2.1` - Redis Python client
- All existing dependencies

### 4. Environment Configuration

Your `.env` file should already have these variables (verify):

```bash
# AWS S3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-2
S3_BUCKET_NAME=gravel-road-app  # For tiles
S3_BUCKET_RAW=gravel-road-raw   # For raw uploads

# AWS CloudFront
AWS_CLOUDFRONT_DOMAIN=d27qedu9pry7hv.cloudfront.net
AWS_CLOUDFRONT_ARN=arn:aws:cloudfront::708034343404:distribution/E35OIHHH02JZNT
AWS_CLOUDFRONT_ORIGIN_ACCESS_ID=E374S2F4VV16RB

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Database
DATABASE_URL=postgresql://kunle_admin:prosper@localhost:5432/gravel_road_app
```

## Running the System

You need to run **three** processes:

### Terminal 1: FastAPI Server
```bash
cd FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2: Celery Worker
```bash
cd FastAPI
./run_celery_worker.sh
```

Or manually:
```bash
cd FastAPI
celery -A app.celery_app worker --loglevel=info --concurrency=2 --queues=tiles
```

### Terminal 3: Frontend (if applicable)
```bash
cd webapp
npm run dev
```

## Monitoring

### Check Redis Connection
```bash
redis-cli
> PING
PONG
> KEYS *
> EXIT
```

### Check Celery Tasks
```bash
# List all task keys in Redis
redis-cli KEYS "celery*"

# Monitor Celery worker logs
# Check Terminal 2 for real-time logs
```

### Check Task Status via API
```bash
# Get status for a specific file
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/tiles-status/{file_id}

# Response includes:
# - tile_status: pending/queued/processing/completed/failed
# - tile_progress: 0-100
# - celery_task: {task_id, state, info}
```

## How It Works

### 1. File Upload
```
User uploads TIFF → FastAPI → S3 Raw Bucket (gravel-road-raw)
                  ↓
              Convert to COG
                  ↓
           Submit Celery Task
```

### 2. Celery Task Processing
```
Celery Worker receives task
    ↓
Download COG from S3
    ↓
Generate XYZ tiles (gdal2tiles)
    ↓
Upload tiles to S3 (gravel-road-app)
    ↓
Update database with CloudFront URL
```

### 3. Frontend Display
```
Frontend fetches tile_url_template
    ↓
https://d27qedu9pry7hv.cloudfront.net/tiles/{user_id}/{file_id}/{z}/{x}/{y}.png
    ↓
Display on map (Leaflet/Mapbox)
```

## Tile URL Format

Generated tiles are served via CloudFront:
```
https://d27qedu9pry7hv.cloudfront.net/tiles/{user_id}/{file_id}/{z}/{x}/{y}.png
```

Example:
```
https://d27qedu9pry7hv.cloudfront.net/tiles/abc-123-def/xyz-789-ghi/18/12345/67890.png
```

## Troubleshooting

### Redis Connection Failed
```bash
# Check if Redis is running
sudo service redis-server status

# Restart Redis
sudo service redis-server restart
```

### Celery Worker Not Picking Up Tasks
```bash
# Check Celery logs in Terminal 2
# Ensure worker is listening to 'tiles' queue

# Manually test task
python3 -c "
from app.workers.tile_worker import generate_tiles_task
task = generate_tiles_task.apply_async(args=['test-id', 'bucket', 'key', 15, 21])
print(f'Task ID: {task.id}')
"
```

### GDAL Commands Not Found
```bash
# Add GDAL to PATH (Ubuntu/Debian)
export PATH="/usr/bin:$PATH"

# Verify
which gdal2tiles.py
```

### S3 Upload Failed
- Verify AWS credentials in `.env`
- Check bucket permissions
- Ensure buckets exist: `gravel-road-raw` and `gravel-road-app`

### CloudFront Not Serving Tiles
- Verify CloudFront distribution is deployed
- Check origin is set to `gravel-road-app` S3 bucket
- Wait 5-10 minutes for CloudFront cache invalidation
- Test direct S3 URL first

## Performance Tuning

### Adjust Worker Concurrency
Edit `run_celery_worker.sh`:
```bash
# For 4 CPU cores
celery -A app.celery_app worker --concurrency=4 ...

# For single-core debugging
celery -A app.celery_app worker --concurrency=1 --pool=solo
```

### Scale Horizontally
Run multiple workers on different machines:
```bash
# Machine 1
celery -A app.celery_app worker --hostname=worker1@%h

# Machine 2
celery -A app.celery_app worker --hostname=worker2@%h
```

All workers connect to the same Redis broker.

## Production Deployment

### Systemd Service (Linux)

Create `/etc/systemd/system/celery-tiles.service`:
```ini
[Unit]
Description=Celery Worker for Tile Generation
After=network.target redis.service

[Service]
Type=forking
User=your_user
Group=your_group
WorkingDirectory=/path/to/FastAPI
Environment="PATH=/path/to/venv/bin:/usr/bin"
ExecStart=/path/to/FastAPI/run_celery_worker.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable celery-tiles
sudo systemctl start celery-tiles
sudo systemctl status celery-tiles
```

### Docker Compose

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  celery-worker:
    build: ./FastAPI
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    volumes:
      - ./FastAPI:/app
```

## Next Steps

1. **Install Redis** (see instructions above)
2. **Install Python dependencies**: `pip install -r requirements.txt`
3. **Start Redis server**: `sudo service redis-server start`
4. **Start FastAPI**: `uvicorn app.main:app --reload`
5. **Start Celery worker**: `./run_celery_worker.sh`
6. **Upload a TIFF file** and monitor progress in Celery logs

## Questions?

- Check Celery logs in Terminal 2
- Check FastAPI logs in Terminal 1
- Check Redis status: `redis-cli PING`
- Test tile URL in browser after completion
