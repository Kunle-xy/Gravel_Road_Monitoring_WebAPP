# CloudFront and S3 Permissions Configuration

## Current Setup (Working Configuration)

### 1. S3 Bucket: `gravel-road-app`

**Region:** us-east-2

#### Bucket Policy
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
    },
    {
      "Sid": "AllowCloudFrontServicePrincipal",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudfront.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::gravel-road-app/*",
      "Condition": {
        "ArnLike": {
          "AWS:SourceArn": "arn:aws:cloudfront::708034343404:distribution/E1IAIBTRGRQKSH"
        }
      }
    }
  ]
}
```

**What this does:**
- Statement 1: Allows **public read access** to all objects (tiles can be accessed by anyone)
- Statement 2: Explicitly allows CloudFront distribution to access objects

#### CORS Configuration
```json
{
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedOrigins": ["*"],
  "AllowedHeaders": ["*"],
  "ExposeHeaders": ["ETag"],
  "MaxAgeSeconds": 3000
}
```

**What this does:**
- Allows GET/HEAD requests from any origin (browsers can load tiles from different domains)
- Caches CORS preflight for 3000 seconds

#### Public Access Block Settings
```
Block Public ACLs: False
Ignore Public ACLs: False
Block Public Policy: False
Restrict Public Buckets: False
```

**What this does:**
- **All blocks disabled** - allows public access via bucket policy

---

### 2. CloudFront Distribution

**Domain:** `d2ewj0q6gtwtvq.cloudfront.net`
**Distribution ID:** `E1IAIBTRGRQKSH`
**Status:** Enabled

#### Origin Configuration
```
Origin Domain: gravel-road-app.s3.us-east-2.amazonaws.com
Origin Access Identity: None (using public bucket policy)
```

#### Cache Behavior
```
Viewer Protocol Policy: redirect-to-https
Allowed Methods: GET, HEAD
Cached Methods: GET, HEAD
```

**What this does:**
- All HTTP requests redirected to HTTPS
- Only GET/HEAD methods allowed (read-only access)
- Tiles are cached at CloudFront edge locations

---

## How Tiles Are Served

1. **User requests tile:** `https://d2ewj0q6gtwtvq.cloudfront.net/tiles/{user_id}/{file_id}/{z}/{x}/{y}.png`

2. **CloudFront checks cache:**
   - **Cache hit** → Returns tile immediately (< 100ms)
   - **Cache miss** → Fetches from S3 origin

3. **S3 returns tile:**
   - Bucket policy allows CloudFront service principal
   - Public policy also allows direct access (backup)

4. **CloudFront caches tile:**
   - Cache-Control: `public, max-age=31536000, immutable`
   - Tiles cached for 1 year at edge locations

---

## Security Notes

### Current Setup (Public Bucket)
✅ **Pros:**
- Simple to configure
- Works immediately without OAI setup
- Tiles accessible from any client

⚠️ **Cons:**
- Tiles are publicly accessible (anyone with URL can view)
- S3 bucket policy allows `Principal: "*"`

### Recommended Production Setup (Private Bucket with OAI)

For better security, consider using CloudFront Origin Access Identity (OAI):

1. **Create OAI in CloudFront**
2. **Update S3 bucket policy** to only allow CloudFront OAI:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontOAI",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity <OAI_ID>"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::gravel-road-app/*"
    }
  ]
}
```

3. **Remove public access** (set `Principal: "*"` statement to OAI only)

This ensures tiles are **only accessible via CloudFront**, not directly from S3.

---

## Troubleshooting

### If tiles return 403 Forbidden:

1. **Check S3 bucket policy** includes public access or CloudFront service principal
2. **Verify public access block** is disabled
3. **Check CloudFront distribution** is deployed and enabled
4. **Verify object exists** in S3 at the expected path
5. **Check CORS** if loading from browser

### If tiles are slow:

1. **First load is always slower** (CloudFront cache miss)
2. **Check CloudFront cache hit ratio** in metrics
3. **Verify Cache-Control headers** are set on S3 objects
4. **Consider increasing cache TTL** if needed

---

## Environment Variables

Current configuration from `.env`:

```bash
AWS_CLOUDFRONT_DOMAIN=d2ewj0q6gtwtvq.cloudfront.net
S3_BUCKET_NAME=gravel-road-app
AWS_REGION=us-east-2
```

---

## Testing Permissions

Test if a tile is accessible:

```bash
# Via CloudFront (recommended)
curl -I "https://d2ewj0q6gtwtvq.cloudfront.net/tiles/{user_id}/{file_id}/15/8000/12000.png"

# Direct S3 access (should also work with current policy)
curl -I "https://gravel-road-app.s3.us-east-2.amazonaws.com/tiles/{user_id}/{file_id}/15/8000/12000.png"
```

Expected response: `HTTP/2 200 OK`

---

Generated: 2025-11-11
