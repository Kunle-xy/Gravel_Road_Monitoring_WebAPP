# TIFF/COG/TiTiler Implementation Guide

## Overview

This implementation provides a complete workflow for handling geospatial TIFF files with Cloud Optimized GeoTIFF (COG) conversion and dynamic tile serving via TiTiler.

## Architecture

```
User uploads TIFF
    ↓
FastAPI processes upload
    ↓
├─→ Original TIFF saved to S3
└─→ Convert to COG (optional, enabled by default)
    ↓
    COG saved to S3
    ↓
Database records both files
    ↓
Frontend requests tiles
    ↓
Backend generates TiTiler URL with S3 presigned URL
    ↓
Leaflet displays tiles from TiTiler
```

## What Was Implemented

### Backend (FastAPI)

1. **COG Conversion Utility** (`FastAPI/app/cog_utils.py`)
   - `convert_to_cog()`: Converts TIFF to Cloud Optimized GeoTIFF
   - `is_cog()`: Checks if a file is already COG
   - `get_raster_metadata()`: Extracts raster metadata

2. **Database Model Updates** (`FastAPI/app/models.py`)
   - Added `cog_s3_key`: S3 key for COG file
   - Added `cog_size_bytes`: COG file size
   - Added `is_cog`: Flag if original was COG
   - Added `cog_created_at`: COG creation timestamp

3. **Upload Endpoint** (`FastAPI/app/routers/upload.py`)
   - Accepts `convert_cog` parameter (default: True)
   - Uploads original TIFF to S3
   - Converts to COG and uploads COG to S3
   - Stores both file references in database
   - Deletes both files when deleting

4. **TiTiler Integration** (`FastAPI/app/routers/files.py`)
   - New endpoint: `GET /files/{file_id}/tiles`
   - Returns:
     - `tile_url`: TiTiler tile URL template for Leaflet
     - `info_url`: Raster metadata endpoint
     - `bounds_url`: Geographic bounds endpoint
     - `statistics_url`: Band statistics endpoint

5. **Configuration** (`FastAPI/app/config.py`)
   - Added `TITILER_URL` setting (default: https://titiler.xyz)

### Frontend (Next.js/React)

1. **TiffMapViewer Component** (`webapp/app/components/TiffMapViewer.tsx`)
   - Standalone component to display any TIFF file on a map
   - Fetches tile URL from backend
   - Automatically fits map to raster bounds
   - Usage:
     ```tsx
     <TiffMapViewer fileId="abc-123" className="h-96 w-full" />
     ```

2. **Updated TiffFileItem** (`webapp/app/components/TiffFiles/TiffFileItem.tsx`)
   - Now uses TiTiler tiles instead of downloading entire file
   - Much faster and more efficient for large files
   - Streams tiles on-demand

3. **API Endpoints** (`webapp/app/lib/api.ts`)
   - Added `TILES` endpoint function

## Setup Instructions

### 1. Install Python Dependencies

```bash
cd FastAPI
pip install -r requirements.txt
```

New dependencies added:
- `rio-cogeo==5.3.3`: COG conversion library
- `rasterio==1.4.3`: Raster I/O
- `numpy==1.26.4`: Numerical operations

### 2. Run Database Migration

```bash
cd FastAPI
psql $DATABASE_URL -f migrations/001_add_cog_fields.sql
```

Or manually execute the SQL in `FastAPI/migrations/001_add_cog_fields.sql`

### 3. Configure TiTiler URL (Optional)

Add to your `.env` file:

```bash
# Use public TiTiler instance (default)
TITILER_URL=https://titiler.xyz

# OR deploy your own TiTiler instance
# TITILER_URL=https://your-titiler-instance.com
```

### 4. Restart Backend

```bash
cd FastAPI
uvicorn app.main:app --reload
```

### 5. Frontend is Ready

No additional setup needed - the frontend dependencies are already installed.

## Usage

### Upload a TIFF File with COG Conversion

**API Request:**
```bash
curl -X POST "http://localhost:8000/upload/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/your/file.tif" \
  -F "file_type=DEM" \
  -F "convert_cog=true"
```

**Response:**
```json
{
  "id": "abc-123",
  "filename": "elevation.tif",
  "file_type": "DEM",
  "s3_key": "uploads/user-id/2025-11-10/dem/elevation-abc123.tif",
  "cog_s3_key": "uploads/user-id/2025-11-10/dem/elevation-abc123_cog.tif",
  "original_size_bytes": 50000000,
  "cog_size_bytes": 45000000,
  "is_cog": false
}
```

### Get Tile URL for Display

**API Request:**
```bash
curl "http://localhost:8000/files/abc-123/tiles" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "file_id": "abc-123",
  "filename": "elevation.tif",
  "file_type": "DEM",
  "is_cog": true,
  "tile_url": "https://titiler.xyz/cog/tiles/{z}/{x}/{y}?url=...",
  "info_url": "https://titiler.xyz/cog/info?url=...",
  "bounds_url": "https://titiler.xyz/cog/bounds?url=...",
  "statistics_url": "https://titiler.xyz/cog/statistics?url=...",
  "expires_in": 3600
}
```

### Display on Map (Frontend)

**Option 1: Use TiffMapViewer Component**
```tsx
import TiffMapViewer from '@/app/components/TiffMapViewer';

function MyPage() {
  return (
    <TiffMapViewer
      fileId="abc-123"
      className="h-screen w-full"
    />
  );
}
```

**Option 2: Checkbox in ProfileWidget**
Just check the box next to the file in the sidebar - it will automatically load using TiTiler!

## Benefits

### Performance
- **Before**: Downloaded entire TIFF file (can be GBs) to browser
- **After**: Streams only visible tiles (KBs per tile)

### Efficiency
- **COG Format**: Optimized for cloud storage and range requests
- **TiTiler**: Generates tiles on-the-fly from COG
- **Leaflet**: Loads only tiles in viewport

### Scalability
- Can handle very large raster files (10+ GB)
- Multiple users can view the same file simultaneously
- No server-side tile pre-generation needed

## Architecture Decisions

### Why COG?
Cloud Optimized GeoTIFF is designed for cloud storage:
- Internal tiling for efficient random access
- Overviews for multi-resolution display
- HTTP range request support

### Why TiTiler?
- Dynamic tile generation (no pre-processing)
- Supports COG and regular GeoTIFFs
- Built on modern geospatial stack (rio-tiler, GDAL)
- Can apply color maps, rescaling, algorithms on-the-fly

### Why Store Both Original and COG?
- **Original**: Preserve exact uploaded file
- **COG**: Optimized for fast tile serving
- User can download original if needed
- COG is used for map display

## Advanced Usage

### Customize COG Conversion

```python
# In upload endpoint, customize COG parameters
cog_data, cog_size = convert_to_cog(
    file_content,
    compression="lzw",  # or "deflate", "jpeg", "zstd"
    blocksize=512       # tile size (256 or 512)
)
```

### Use TiTiler Advanced Features

Add query parameters to tile URL:
- Color map: `&colormap_name=viridis`
- Rescale: `&rescale=0,1000`
- Resampling: `&resampling_method=bilinear`

Example:
```
https://titiler.xyz/cog/tiles/{z}/{x}/{y}?url={s3_url}&colormap_name=terrain&rescale=0,3000
```

### Deploy Your Own TiTiler

For production, consider deploying your own TiTiler instance:

```bash
# Using Docker
docker run -p 8000:8000 ghcr.io/developmentseed/titiler:latest

# Or with AWS Lambda
# See: https://github.com/developmentseed/titiler
```

## Troubleshooting

### TIFF Not Displaying
1. Check S3 file exists: `GET /files/{id}/download-url`
2. Verify COG was created: Check `cog_s3_key` in database
3. Test TiTiler manually: Open `tile_url` in browser (replace {z}/{x}/{y} with 0/0/0)

### COG Conversion Fails
- Ensure TIFF has valid georeferencing
- Check file is not corrupted
- Verify sufficient memory for large files

### CORS Issues with TiTiler
- Use your own TiTiler instance
- Or proxy TiTiler requests through your backend

## Next Steps

1. **Add Color Ramps**: Implement color ramp selection for DEMs
2. **Band Selection**: Allow selecting specific bands from multi-band TIFFs
3. **Tile Caching**: Cache frequently accessed tiles
4. **Background Processing**: Process COG conversion in background job queue
5. **Analytics**: Track which files are viewed most

## File References

**Backend:**
- `FastAPI/app/cog_utils.py` - COG conversion utilities
- `FastAPI/app/models.py` - Database models
- `FastAPI/app/routers/upload.py` - Upload endpoint
- `FastAPI/app/routers/files.py` - Files and tiles endpoints
- `FastAPI/app/config.py` - Configuration
- `FastAPI/requirements.txt` - Python dependencies
- `FastAPI/migrations/001_add_cog_fields.sql` - Database migration

**Frontend:**
- `webapp/app/components/TiffMapViewer.tsx` - Standalone map viewer
- `webapp/app/components/TiffFiles/TiffFileItem.tsx` - Updated to use TiTiler
- `webapp/app/lib/api.ts` - API endpoints

## Resources

- [TiTiler Documentation](https://developmentseed.org/titiler/)
- [COG Specification](https://www.cogeo.org/)
- [rio-cogeo Documentation](https://cogeotiff.github.io/rio-cogeo/)
- [Leaflet Documentation](https://leafletjs.com/)
