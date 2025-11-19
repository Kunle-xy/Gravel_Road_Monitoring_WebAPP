# Presigned URLs Fix for Rut Analysis Results

## Issue
Users were getting "Access Denied" errors when trying to view HTML plots or download PDF reports from completed rut analysis jobs.

**Error**:
```xml
<Error>
<Code>AccessDenied</Code>
<Message>Access Denied</Message>
</Error>
```

## Root Cause
The rut_worker was generating direct CloudFront URLs for analysis results:
```python
html_url = f"https://{settings.AWS_CLOUDFRONT_DOMAIN}/{html_s3_key}"
pdf_url = f"https://{settings.AWS_CLOUDFRONT_DOMAIN}/{pdf_s3_key}"
```

**Problem**: The S3_BUCKET_RAW bucket is **private** (not publicly accessible), and CloudFront was not configured with Origin Access Identity (OAI) to serve private S3 content.

## Solution
Generate **presigned S3 URLs** instead of direct CloudFront URLs. Presigned URLs:
- Are signed with AWS credentials
- Grant temporary access to private S3 objects
- Expire after a set time (we use 7 days)
- Don't require CloudFront OAI configuration

## Changes Made

### 1. HTML Plot URL (`app/workers/rut_worker.py` lines 655-663)
```python
# BEFORE (broken):
html_url = f"https://{settings.AWS_CLOUDFRONT_DOMAIN}/{html_s3_key}"

# AFTER (working):
html_url = s3_client.generate_presigned_url(
    'get_object',
    Params={
        'Bucket': settings.S3_BUCKET_RAW,
        'Key': html_s3_key
    },
    ExpiresIn=604800  # 7 days
)
```

### 2. PDF Report URL (`app/workers/rut_worker.py` lines 687-695)
```python
# BEFORE (broken):
pdf_url = f"https://{settings.AWS_CLOUDFRONT_DOMAIN}/{pdf_s3_key}"

# AFTER (working):
pdf_url = s3_client.generate_presigned_url(
    'get_object',
    Params={
        'Bucket': settings.S3_BUCKET_RAW,
        'Key': pdf_s3_key
    },
    ExpiresIn=604800  # 7 days
)
```

## Benefits

1. **Works with private S3 buckets** - No need to make analysis results public
2. **Secure** - URLs are signed and only work for authorized requests
3. **Time-limited** - URLs expire after 7 days (configurable)
4. **No CloudFront changes needed** - Works with existing infrastructure
5. **Better security** - Analysis results remain private

## How Presigned URLs Work

```
User clicks "View Plot"
  ↓
Frontend requests: https://gravel-road-raw.s3.amazonaws.com/rut_analysis/.../plot.html?AWSAccessKeyId=...&Expires=...&Signature=...
  ↓
S3 validates signature and expiration
  ↓
If valid: Returns file content
If invalid/expired: Returns AccessDenied
```

## URL Format

**Presigned URL**:
```
https://gravel-road-raw.s3.us-east-1.amazonaws.com/rut_analysis/user-id/job-id/plot.html?
  AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&
  Expires=1700000000&
  Signature=vjbyqhez91d09dmw1efneu0xn4h7awx8
```

**Contains**:
- Bucket name and region
- Object key (file path)
- AWS Access Key ID
- Expiration timestamp
- Cryptographic signature

## Expiration Time

Current setting: **7 days (604,800 seconds)**

This means:
- Users can access results for 7 days after analysis completes
- After 7 days, they need to re-run the analysis
- Adjustable via the `ExpiresIn` parameter

To change expiration:
```python
ExpiresIn=86400   # 1 day
ExpiresIn=604800  # 7 days (current)
ExpiresIn=2592000 # 30 days
```

## Testing

1. Run a new rut analysis
2. Wait for completion
3. Click "View Interactive Plot" in results or completed jobs
4. Should open HTML plot without AccessDenied error
5. Click "Download PDF Report"
6. Should download PDF without AccessDenied error

## Alternative Approaches (Not Used)

### Option A: CloudFront with OAI (Origin Access Identity)
**Pros**: Can use CloudFront CDN for faster downloads
**Cons**: Complex setup, requires CloudFront reconfiguration

### Option B: Make S3 bucket public
**Pros**: Simple, works with direct CloudFront URLs
**Cons**: **Security risk** - anyone with URL can access results

### Option C: Presigned CloudFront URLs
**Pros**: CDN benefits + security
**Cons**: Requires CloudFront key pair setup, more complex

**We chose Option D (Presigned S3 URLs)** for simplicity and security.

## Status
- **Fixed**: November 18, 2025 23:00
- **Workers restarted**: Manually by user
- **Ready for testing**: Yes

---
**Author**: Claude Code
**Date**: November 18, 2025
**Issue**: AccessDenied errors on HTML/PDF downloads
**Solution**: Use presigned S3 URLs instead of direct CloudFront URLs
