# FastAPI Backend - Quick Reference Guide

## File Locations

| Component | File Path |
|-----------|-----------|
| **Main Application** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/main.py` |
| **Configuration** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/config.py` |
| **Database Setup** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/database.py` |
| **Database Models** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/models.py` |
| **Response Schemas** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/schemas.py` |
| **Authentication** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/auth.py` |
| **COG Utilities** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/cog_utils.py` |
| **Auth Router** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/routers/auth.py` |
| **Upload Router** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/routers/upload.py` |
| **Files Router** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/routers/files.py` |
| **Tiles Router** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/routers/tiles.py` |
| **Dependencies** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/requirements.txt` |
| **Environment** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/.env` |
| **Migrations** | `/home/oguntoye/GravelRoad_Iowa/FastAPI/migrations/` |

---

## Key Classes & Models

### User Model
```python
class User:
    id: UUID (PK)
    email: str (UNIQUE)
    password_hash: str
    first_name: str
    last_name: str
    organization: str
    is_active: bool
    created_at: DateTime
    updated_at: DateTime
    last_login: DateTime
    
    # Relationship
    tiff_files: List[TiffFile]
```

### TiffFile Model
```python
class TiffFile:
    id: UUID (PK)
    user_id: UUID (FK -> users.id)
    filename: str
    file_type: str ('DEM' or 'ORTHOPHOTO')
    original_size_bytes: int
    
    # S3 Original
    s3_bucket: str
    s3_key: str
    s3_url: str (presigned)
    
    # COG Version
    cog_s3_key: str
    cog_size_bytes: int
    is_cog: bool
    cog_created_at: DateTime
    
    # Geographic Bounds (PRE-CALCULATED)
    bounds_south: str
    bounds_west: str
    bounds_north: str
    bounds_east: str
    
    # Upload Status
    upload_status: str ('pending' or 'completed')
    upload_progress: int (0-100)
    upload_completed_at: DateTime
    
    created_at: DateTime
    updated_at: DateTime
```

---

## Critical Configuration

### Database
```
Type: PostgreSQL
Connection: postgresql://kunle_admin:prosper@localhost:5432/gravel_road_app
```

### AWS S3
```
Bucket: gravel-road-app
Region: us-east-2
Access Key: AKIA2JWRCWHWDVNZRMFL
```

### JWT
```
Algorithm: HS256
Expiration: 30 minutes
Secret: [Strong secret key in .env]
```

### CORS
```
Allowed Origin: http://localhost:3000
```

---

## API Endpoint Categories

### Authentication (3 endpoints)
```
POST   /auth/register        - Create account
POST   /auth/login          - Get JWT token
GET    /auth/me             - Get current user
```

### File Management (6 endpoints)
```
GET    /files/              - List user's files
GET    /files/{file_id}     - Get file details
GET    /files/{file_id}/download-url - Presigned download
GET    /files/{file_id}/cog-file     - Stream COG
GET    /files/{file_id}/tiles        - Get tile URLs
POST   /files/sync          - Clean up S3 orphans
```

### Upload/Delete (2 endpoints)
```
POST   /upload              - Upload TIFF (auto-COG)
DELETE /upload/{file_id}    - Delete file
```

### Tile Serving (3 endpoints)
```
GET    /tiles/{file_id}/{z}/{x}/{y}.png - Get map tile
GET    /tiles/{file_id}/info             - Raster metadata
GET    /tiles/{file_id}/bounds           - Geographic bounds
```

### System (2 endpoints)
```
GET    /                    - API info
GET    /health              - Health check
```

---

## Data Flow

### Upload Flow
```
1. POST /upload (multipart form)
   ├─ Validate file format (.tif/.tiff)
   ├─ Generate S3 key: uploads/{user_id}/{date}/{type}/{name}-{uuid}.tif
   ├─ Upload original to S3
   ├─ Create DB record
   ├─ If convert_cog=True:
   │  ├─ Convert using rio-cogeo
   │  ├─ Upload COG to S3 with _cog.tif suffix
   │  ├─ Extract bounds (EPSG:4326)
   │  └─ Store bounds in DB (south, west, north, east)
   └─ Return TiffFileResponse

2. Bounds stored in DB = instant map zoom
3. COG uploaded = efficient tile generation
```

### Tile Generation Flow
```
1. GET /tiles/{file_id}/{z}/{x}/{y}.png
   ├─ Verify user owns file
   ├─ Download COG from S3 to temp file
   ├─ Use rio-tiler to generate tile
   ├─ Render to PNG
   ├─ Return with Cache-Control headers
   └─ Clean up temp file

2. Out-of-bounds = transparent 1x1 PNG (not error)
3. Browser caches for 1 hour
```

---

## Dependencies Overview

### Web Framework
- **fastapi** (0.121.0) - Async web framework
- **uvicorn** (0.38.0) - ASGI server

### Database
- **sqlalchemy** (2.0.32) - ORM
- **psycopg2-binary** (2.9.11) - PostgreSQL driver
- **alembic** (1.17.1) - Migrations

### Security
- **passlib** (1.7.4) - Password hashing (Argon2)
- **python-jose** (3.5.0) - JWT tokens
- **pydantic** (2.12.4) - Data validation

### Cloud & Geospatial
- **boto3** (1.40.68) - AWS SDK for S3
- **rasterio** (1.4.3) - Read/write rasters
- **rio-cogeo** (5.3.3) - COG creation
- **rio-tiler** (7.9.2) - Tile generation from rasters

### Utilities
- **python-dotenv** (1.2.2) - Load .env files
- **python-multipart** (0.0.20) - Multipart form parsing

---

## Common Tasks

### Start Development Server
```bash
cd /home/oguntoye/GravelRoad_Iowa/FastAPI
uvicorn app.main:app --reload --port 8000
```

### Run Database Migrations
```bash
cd /home/oguntoye/GravelRoad_Iowa/FastAPI
python run_migration.py
```

### Test Authentication
```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "secure_pass",
    "first_name": "Test"
  }'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "secure_pass"
  }'
```

### Upload TIFF
```bash
TOKEN="your_jwt_token_here"

curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/file.tif" \
  -F "file_type=DEM" \
  -F "convert_cog=true"
```

### Get Tile URLs
```bash
TOKEN="your_jwt_token_here"
FILE_ID="uuid-of-file"

curl "http://localhost:8000/files/$FILE_ID/tiles" \
  -H "Authorization: Bearer $TOKEN"
```

### Request a Tile
```bash
TOKEN="your_jwt_token_here"

curl "http://localhost:8000/tiles/FILE_ID/10/250/400.png" \
  -H "Authorization: Bearer $TOKEN" \
  --output tile.png
```

---

## Key Design Decisions

### Self-Hosted Tile Server
✅ Uses rio-tiler directly instead of external TiTiler
✅ Solves private S3 access issue
✅ Full authentication control
✅ No CORS problems

### Pre-Calculated Bounds
✅ Stored in DB during upload
✅ Zero-latency map zoom
✅ Reduces S3 requests

### COG Conversion
✅ Automatic on upload
✅ Enables efficient streaming
✅ Fallback to original if fails

### No Async Workers
❌ Currently synchronous processing
❌ Simple but blocks on large uploads
➡️ Future: Add Celery for background COG conversion

---

## Performance Notes

### Tile Generation
- **First tile**: Slow (downloads COG from S3)
- **Subsequent tiles**: Faster (file cached in temp)
- **Caching**: Browser caches 1 hour
- **Out-of-bounds**: Returns transparent PNG (not error)

### Bounds Calculation
- **When**: During upload (one-time cost)
- **Storage**: VARCHAR(50) in each tiff_files row
- **Retrieval**: Instant with file list query

### S3 Structure
```
s3://gravel-road-app/uploads/
  {user_id}/
    {YYYY-MM-DD}/
      dem/
        {name}-{uuid}.tif
        {name}-{uuid}_cog.tif
      orthophoto/
        {name}-{uuid}.tif
        {name}-{uuid}_cog.tif
```

---

## Security Best Practices

### Current Implementation
- JWT tokens (HS256, 30 min expiry)
- Argon2 password hashing
- CORS limited to frontend
- Presigned URLs for S3 access
- No exposed credentials in code

### Production Recommendations
1. Use AWS Secrets Manager for sensitive data
2. Enable HTTPS everywhere
3. Implement refresh tokens
4. Add rate limiting
5. Enable audit logging
6. Restrict S3 bucket with IAM policy
7. Monitor and alert on errors
8. Use VPC endpoints for S3

---

## Troubleshooting

### Issue: Tiles not loading
```
Solution:
1. Check file exists in S3
2. Verify COG was created (check logs)
3. Test bounds endpoint: GET /tiles/{file_id}/bounds
4. Check browser console for auth errors
5. Verify JWT token is valid
```

### Issue: Upload timeout
```
Solution:
1. Large file + slow COG conversion
2. In production, move COG to background job
3. For now, increase request timeout
4. Consider multi-part upload
```

### Issue: Slow map interaction
```
Solution:
1. Ensure files are in COG format
2. Check browser network tab (tile size)
3. Add Redis cache for frequently accessed tiles
4. Use CloudFront CDN for tiles
```

### Issue: Database connection errors
```
Solution:
1. Verify PostgreSQL is running
2. Check DATABASE_URL in .env
3. Ensure permissions with check_db_permissions.py
4. Run migrations: python run_migration.py
```

---

## Important Notes

### Critical Fields
- **bounds_south, bounds_west, bounds_north, bounds_east**: MUST be pre-calculated during upload
- **s3_key**: Original TIFF location
- **cog_s3_key**: COG location (if converted)
- **is_cog**: Boolean flag (False if original was converted)

### Database Indexes
- `users.email` - UNIQUE for login
- `tiff_files.user_id` - For filtering user's files

### S3 Credentials
- ⚠️ Never commit .env file
- ⚠️ Use IAM user (not root account)
- ⚠️ Restrict S3 permissions to minimum needed

### Presigned URLs
- **Upload metadata**: 7 days (generous for viewing)
- **Download**: 1 hour (limited exposure)
- **Consider**: Shorter duration in production

---

## Version Information

- **FastAPI**: 0.121.0
- **SQLAlchemy**: 2.0.32
- **rio-tiler**: 7.9.2
- **rio-cogeo**: 5.3.3
- **rasterio**: 1.4.3
- **boto3**: 1.40.68
- **Python**: 3.8+ (recommended 3.10+)

---

## Next Steps for Production

1. [ ] Enable HTTPS
2. [ ] Move secrets to AWS Secrets Manager
3. [ ] Add Celery for background COG processing
4. [ ] Implement Redis caching for tiles
5. [ ] Set up CloudFront CDN
6. [ ] Add comprehensive logging (ELK/CloudWatch)
7. [ ] Set up monitoring (Sentry, Prometheus)
8. [ ] Implement rate limiting
9. [ ] Add database backup strategy
10. [ ] Document API with OpenAPI (auto-generated by FastAPI)

