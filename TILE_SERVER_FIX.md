# Tile Server Fix - Direct Backend Serving

## Problem

The original implementation used the public TiTiler instance (titiler.xyz) which couldn't access your private S3 buckets, even with presigned URLs. This caused 404 errors when trying to load tiles.

## Solution

**Created a self-hosted tile server directly in your FastAPI backend** using `rio-tiler`. No external dependencies needed!

## What Changed

### New Tile Endpoints (`FastAPI/app/routers/tiles.py`)

Your backend now serves tiles directly:

1. **`GET /tiles/{file_id}/{z}/{x}/{y}.png`** - Serve individual map tiles
2. **`GET /tiles/{file_id}/info`** - Get raster metadata
3. **`GET /tiles/{file_id}/bounds`** - Get geographic bounds

### Updated Files

1. **`FastAPI/app/routers/tiles.py`** (NEW)
   - Tile server using rio-tiler
   - Fetches from S3 and generates tiles on-the-fly
   - Returns PNG tiles for Leaflet

2. **`FastAPI/app/routers/files.py`**
   - Updated `/files/{file_id}/tiles` endpoint
   - Now returns URLs to your own backend instead of TiTiler

3. **`FastAPI/app/main.py`**
   - Added tiles router

4. **`FastAPI/requirements.txt`**
   - Added `rio-tiler==7.9.2`

## How It Works

```
User checks file box in UI
    ↓
Frontend calls: GET /files/{file_id}/tiles
    ↓
Backend returns: http://localhost:8000/tiles/{file_id}/{z}/{x}/{y}.png
    ↓
Leaflet requests tiles: /tiles/{file_id}/10/250/400.png
    ↓
Backend:
  1. Fetches COG from S3
  2. Generates tile for zoom/x/y
  3. Returns PNG
    ↓
Leaflet displays tile on map
```

## Advantages Over External TiTiler

✅ **No external dependencies** - Everything runs in your backend
✅ **Works with private S3** - Your backend has S3 credentials
✅ **Authentication built-in** - Uses your existing auth system
✅ **No CORS issues** - Same origin as your API
✅ **Full control** - Can customize rendering, caching, etc.

## Testing

1. **Restart your backend:**
   ```bash
   cd FastAPI
   uvicorn app.main:app --reload
   ```

2. **Upload a TIFF file** (it will convert to COG automatically)

3. **Check the box** next to the file in the sidebar

4. **Tiles should load!** 🎉

## API Examples

### Get Tile URLs
```bash
curl "http://localhost:8000/files/{file_id}/tiles" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "file_id": "abc-123",
  "filename": "elevation.tif",
  "tile_url": "http://localhost:8000/tiles/abc-123/{z}/{x}/{y}.png",
  "bounds_url": "http://localhost:8000/tiles/abc-123/bounds",
  "info_url": "http://localhost:8000/tiles/abc-123/info",
  "is_cog": true
}
```

### Get a Specific Tile
```bash
curl "http://localhost:8000/tiles/abc-123/10/250/400.png" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output tile.png
```

### Get Bounds
```bash
curl "http://localhost:8000/tiles/abc-123/bounds" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "bounds": [
    [41.0, -94.0],  // [south, west]
    [42.0, -93.0]   // [north, east]
  ]
}
```

## Performance Notes

- Tiles are generated on-demand (no pre-processing)
- COG format enables efficient streaming from S3
- Consider adding caching for production (Redis, CDN, etc.)
- First tile load may be slower (downloads file from S3)
- Subsequent tiles from same file are faster

## Production Considerations

1. **Add Caching:**
   ```python
   # Cache tiles in Redis or filesystem
   # Cache bounds/info to avoid repeated S3 fetches
   ```

2. **Set Backend URL in `.env`:**
   ```bash
   BACKEND_URL=https://api.yourdomain.com
   ```
   Then use `settings.BACKEND_URL` instead of auto-detecting

3. **Add Rate Limiting:**
   ```python
   # Limit tile requests per user to prevent abuse
   ```

4. **Consider CDN:**
   - Put CloudFront in front of tile endpoints
   - Configure aggressive caching

5. **Monitor S3 Costs:**
   - Each tile request downloads from S3
   - Consider caching frequently accessed files locally

## Troubleshooting

### Tiles not loading?

1. Check backend logs for errors
2. Verify file exists in S3
3. Check authentication token is valid
4. Try fetching a single tile directly

### Slow performance?

1. Ensure files are converted to COG
2. Add caching layer
3. Use smaller COG blocksize (256 instead of 512)
4. Consider pre-generating tiles for frequently viewed areas

### Memory issues?

1. Large TIFFs can use lots of memory
2. Adjust uvicorn workers: `--workers 2`
3. Add memory limits to tile generation
4. Use smaller COG overviews

## Next Steps

- ✅ Tiles now work from your own backend!
- Consider adding color ramps for DEMs
- Add hillshade rendering for elevation data
- Implement tile caching for better performance
- Add analytics to track which files are viewed most

## Files Modified

- `FastAPI/app/routers/tiles.py` - New tile server
- `FastAPI/app/routers/files.py` - Updated tile URL generation
- `FastAPI/app/main.py` - Registered tiles router
- `FastAPI/requirements.txt` - Added rio-tiler

No frontend changes needed - it automatically uses the new URLs!
