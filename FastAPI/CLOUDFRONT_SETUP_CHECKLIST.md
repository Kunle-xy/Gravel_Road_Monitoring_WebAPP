# CloudFront Setup Checklist

## Current Configuration
- **Tiles Bucket**: `gravel-road-app` (S3_BUCKET_NAME)
- **Raw Files Bucket**: `gravel-road-raw` (S3_BUCKET_RAW)
- **CloudFront Domain**: `d27qedu9pry7hv.cloudfront.net`
- **CloudFront Distribution**: `E35OIHHH02JZNT`

## Required CloudFront Settings

### 1. Origin Configuration
- [x] Created new origin: `gravel-road-app.s3.us-east-2.amazonaws.com`
- [ ] Set as default behavior origin
- [ ] Origin Access: Choose one:
  - **Option A (Recommended)**: Public S3 bucket access
  - **Option B**: Origin Access Control (OAC) with bucket policy

### 2. Default Behavior Settings
- [ ] Viewer Protocol Policy: **Redirect HTTP to HTTPS** or **HTTPS only**
- [ ] Allowed HTTP Methods: **GET, HEAD**
- [ ] Cache Policy: **CachingOptimized** or custom with:
  - Min TTL: 0
  - Max TTL: 31536000 (1 year)
  - Default TTL: 86400 (1 day)
- [ ] Compress Objects Automatically: **Yes** (optional but recommended)

### 3. S3 Bucket Permissions (gravel-road-app)

If using public access, add this bucket policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::gravel-road-app/*"
    }
  ]
}
```

If using Origin Access Control (OAC), CloudFront will provide the policy to add.

### 4. CORS Configuration (gravel-road-app)

Add this CORS policy to the bucket:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

## Testing Steps

### 1. Wait for CloudFront Deployment
- After making changes, wait 5-10 minutes for CloudFront to deploy
- Status should change from "Deploying" to "Deployed"

### 2. Test Tile Upload
Upload a test file and check Celery logs for:
```
[INFO] COG uploaded to s3://gravel-road-app/cogs/...
[INFO] Uploaded XXX tiles
[INFO] Tile URL: https://d27qedu9pry7hv.cloudfront.net/tiles/...
```

### 3. Verify Tiles in S3
Check that tiles were uploaded to the correct bucket:
```bash
aws s3 ls s3://gravel-road-app/tiles/ --recursive | head -20
```

### 4. Test CloudFront URL
After tile generation completes, test a tile URL directly:
```
https://d27qedu9pry7hv.cloudfront.net/tiles/{user_id}/{file_id}/{z}/{x}/{y}.png
```

Example:
```
https://d27qedu9pry7hv.cloudfront.net/tiles/038e51a9-7f0e-4e80-a34d-d3629997f8c9/c32024e5-f00b-4b5f-a91a-7b15bbd5c822/15/10000/12000.png
```

Should return:
- **200 OK** with PNG image ✓
- **403 Forbidden** = Permission issue ✗
- **404 Not Found** = Tile doesn't exist or wrong path ✗

## Common Issues & Solutions

### 403 Forbidden Error
**Problem**: CloudFront can't access S3 bucket
**Solution**:
1. Check S3 bucket policy allows CloudFront or public access
2. Ensure OAC is properly configured if using it
3. Verify bucket is not blocking public access

### 404 Not Found Error
**Problem**: Tiles not in expected location
**Solution**:
1. Check tiles were uploaded: `aws s3 ls s3://gravel-road-app/tiles/`
2. Verify path format matches CloudFront URL
3. Check Celery logs for upload errors

### Tiles Not Loading in UI
**Problem**: Frontend can't fetch tiles
**Solution**:
1. Check browser console for CORS errors
2. Verify CORS policy on S3 bucket
3. Check tile_url_template in database matches CloudFront domain

## Verification Commands

```bash
# Check if tiles exist in S3
aws s3 ls s3://gravel-road-app/tiles/ --recursive | head -20

# Test a specific tile URL (replace with actual URL from database)
curl -I "https://d27qedu9pry7hv.cloudfront.net/tiles/USER_ID/FILE_ID/15/10000/12000.png"

# Check database for tile URL
psql -U kunle_admin -d gravel_road_app -c "SELECT id, filename, tile_status, tile_url_template FROM tiff_files ORDER BY created_at DESC LIMIT 5;"
```

## Next Steps After Configuration

1. **Restart Celery Worker** (to pick up any code changes)
2. **Upload a test TIFF file**
3. **Monitor Celery logs** for tile generation progress
4. **Check S3 bucket** for uploaded tiles
5. **Test CloudFront URL** in browser
6. **Verify UI displays tiles** correctly
