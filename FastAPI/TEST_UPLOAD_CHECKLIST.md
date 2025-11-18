# Test Upload Checklist - After CloudFront Deployment

## Pre-Test Checklist

### 1. CloudFront Deployment Status
Check in AWS Console → CloudFront → Distribution `E35OIHHH02JZNT`:
- [ ] Status shows: **Deployed** (not "Deploying")
- [ ] Last Modified: Within last 15 minutes
- [ ] Default behavior uses: `gravel-road-app.s3.us-east-2.amazonaws.com`

### 2. Services Running
- [ ] **Terminal 1**: FastAPI running on port 8000
- [ ] **Terminal 2**: Celery worker running and connected to Redis
- [ ] **Terminal 3**: Frontend running on port 3000 (optional)

### 3. Redis Status
```bash
redis-cli ping
# Should return: PONG
```

## Testing Steps

### Step 1: Restart Celery Worker
**Important**: Restart to load the latest bounds fix

Terminal 2:
```bash
# Press Ctrl+C to stop current worker
cd /home/oguntoye/GravelRoad_Iowa/FastAPI
./run_celery_worker.sh
```

Expected output:
```
[INFO] Connected to redis://localhost:6379/0
[INFO] tile_worker@hostname ready.
```

### Step 2: Upload Test File
Upload your TIFF file through the UI (http://localhost:3000)

### Step 3: Monitor Celery Logs (Terminal 2)
Watch for this sequence:

```
[INFO] Task app.workers.tile_worker.generate_tiles_task[tile_xxx] received
[INFO] Starting tile generation task for file xxx
[INFO] Working directory: /tmp/tiles_xxx
[INFO] [1/5] Downloading from S3: gravel-road-raw/...
[INFO] Downloading s3://gravel-road-raw/... to /tmp/...
[INFO] [2/5] Converting to COG
[INFO] Converting to COG: /tmp/.../src.tif -> /tmp/.../cog.tif
[INFO] COG conversion completed
[INFO] Building overviews...
[INFO] Overviews built successfully
[INFO] [3/5] Calculating bounds
[INFO] Transformed bounds using simplified CRS (EPSG:26915)  ← NEW FIX
[INFO] [4/5] Generating XYZ tiles
[INFO] Generating tiles: zoom 15-21
[INFO] Tiles generated in /tmp/.../tiles
[INFO] [5/5] Uploading tiles to S3
[INFO] Uploaded 100 tiles...
[INFO] Uploaded 200 tiles...
...
[INFO] Uploaded XXX tiles
[INFO] COG uploaded to s3://gravel-road-app/cogs/...
[INFO] Task completed successfully for file xxx
[INFO] Tile URL: https://d27qedu9pry7hv.cloudfront.net/tiles/.../{z}/{x}/{y}.png
```

### Step 4: Verify Tiles in S3
```bash
aws s3 ls s3://gravel-road-app/tiles/ --recursive | head -20
```

Should show:
```
2025-11-10 20:xx:xx  12345 tiles/USER_ID/FILE_ID/15/xxxxx/yyyyy.png
2025-11-10 20:xx:xx  12345 tiles/USER_ID/FILE_ID/15/xxxxx/yyyyy.png
...
```

### Step 5: Test CloudFront URL
Get the tile URL from database or Celery logs, then test:

```bash
# Replace with actual URL from your upload
curl -I "https://d27qedu9pry7hv.cloudfront.net/tiles/USER_ID/FILE_ID/15/10000/12000.png"
```

Expected response:
```
HTTP/2 200
content-type: image/png
content-length: XXXX
cache-control: public, max-age=31536000, immutable
x-cache: Miss from cloudfront  ← First request
```

Second request should show:
```
x-cache: Hit from cloudfront  ← Cached!
```

### Step 6: Check Database
```bash
psql -U kunle_admin -d gravel_road_app -c "
  SELECT
    id,
    filename,
    tile_status,
    tile_progress,
    LEFT(tile_url_template, 80) as tile_url
  FROM tiff_files
  ORDER BY created_at DESC
  LIMIT 3;
"
```

Should show:
```
tile_status: completed
tile_progress: 100
tile_url: https://d27qedu9pry7hv.cloudfront.net/tiles/.../...
```

### Step 7: Verify in UI
- Go to http://localhost:3000
- Check that the uploaded file appears in the list
- Click to view on map
- Tiles should load from CloudFront

## Success Criteria

✓ Celery completes all 5 steps without errors
✓ Tiles uploaded to s3://gravel-road-app/tiles/
✓ Database shows tile_status = "completed"
✓ CloudFront URL returns 200 with PNG image
✓ UI displays tiles on map

## Troubleshooting

### Issue: Bounds calculation fails
**Error**: "Cannot find coordinate operations"
**Status**: FIXED - Code now handles complex CRS
**Action**: Restart Celery worker to load fix

### Issue: 403 Forbidden on CloudFront URL
**Cause**: Bucket policy or CloudFront permissions
**Fix**:
1. Check bucket policy allows public read
2. Verify CloudFront origin is correct
3. Wait for CloudFront deployment

### Issue: 404 Not Found on CloudFront URL
**Cause**: Tiles not uploaded or wrong path
**Fix**:
1. Check tiles exist: `aws s3 ls s3://gravel-road-app/tiles/`
2. Verify path in URL matches S3 path
3. Check Celery logs for upload errors

### Issue: Task keeps retrying
**Cause**: GDAL errors or S3 upload failures
**Fix**:
1. Check Celery logs for specific error
2. Verify GDAL is installed: `which gdal_translate`
3. Check AWS credentials have S3 write permissions

## After Successful Test

1. Check tile count and file sizes in S3
2. Test multiple zoom levels in UI
3. Verify CloudFront caching is working (x-cache header)
4. Monitor CloudFront metrics in AWS Console
5. Consider adding more test uploads with different file types

## Performance Notes

**Typical tile generation times** (for 170MB TIFF):
- Download from S3: 3-5 seconds
- COG conversion: 5-10 seconds
- Tile generation (zoom 15-21): 2-5 minutes
- Upload to S3: 1-3 minutes (depends on tile count)

**Total**: ~5-10 minutes for a 170MB file

**Tile counts by zoom range**:
- Zoom 15-18: ~1,000-5,000 tiles
- Zoom 15-21: ~10,000-50,000 tiles
- Zoom 15-24: ~100,000+ tiles (not recommended)

**Optimization tips**:
- Reduce max_zoom for faster processing
- Use smaller geographic extents
- Pre-process files to COG format
- Scale Celery workers horizontally for multiple uploads
