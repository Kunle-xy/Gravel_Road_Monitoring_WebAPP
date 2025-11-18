# Tile Zoom Level Configuration

## Current Settings

**Location:** `/home/oguntoye/GravelRoad_Iowa/FastAPI/app/routers/upload.py:172-173`

```python
min_zoom = 15
max_zoom = 21  # Current default
```

## Zoom Level Reference

| Zoom | Ground Resolution | Use Case |
|------|------------------|----------|
| 15 | ~4.77m/pixel | Overview of large areas |
| 16 | ~2.39m/pixel | Regional view |
| 17 | ~1.19m/pixel | Local area detail |
| 18 | ~0.60m/pixel | Street-level detail |
| 19 | ~0.30m/pixel | Building-level detail |
| 20 | ~0.15m/pixel | Fine detail |
| **21** | **~0.07m/pixel** | **Current max - Very fine detail** |
| 22 | ~0.04m/pixel | Ultra-fine detail |
| 23 | ~0.02m/pixel | Maximum detail |
| 24 | ~0.01m/pixel | Extreme close-up |

## To See More Detail When Zooming In

### Option 1: Increase Max Zoom Level (Recommended)

Edit `/app/routers/upload.py` line 173:

```python
# For more detail when zooming in
max_zoom = 23  # Increase from 21 to 23
```

**Pros:**
- ✅ More detail at close zoom
- ✅ Smoother zoom experience
- ✅ Better for high-resolution source images

**Cons:**
- ⚠️ **Significantly more tiles generated** (4x more tiles per zoom level!)
- ⚠️ **Longer processing time** (2-3x longer)
- ⚠️ **More S3 storage used** (higher costs)

### Option 2: Add Configuration Variable

Add to `/app/config.py`:

```python
class Settings(BaseSettings):
    # ... existing config ...

    # Tile generation settings
    TILE_MIN_ZOOM: int = 15
    TILE_MAX_ZOOM: int = 21  # Increase to 23 for more detail
```

Add to `.env`:
```bash
TILE_MIN_ZOOM=15
TILE_MAX_ZOOM=23
```

Update `/app/routers/upload.py`:
```python
task = generate_tiles_task.apply_async(
    args=[
        str(db_file.id),
        db_file.s3_bucket,
        db_file.cog_s3_key,
        settings.TILE_MIN_ZOOM,  # From config
        settings.TILE_MAX_ZOOM   # From config
    ],
    task_id=f"tile_{db_file.id}"
)
```

### Option 3: File-Type Specific Zoom Levels

Different zoom levels for DEM vs ORTHOPHOTO:

```python
# In upload.py
if file_type == "ORTHOPHOTO":
    min_zoom = 15
    max_zoom = 23  # More detail for orthophotos
else:  # DEM
    min_zoom = 15
    max_zoom = 21  # Standard detail for DEMs

task = generate_tiles_task.apply_async(
    args=[
        str(db_file.id),
        db_file.s3_bucket,
        db_file.cog_s3_key,
        min_zoom,
        max_zoom
    ],
    task_id=f"tile_{db_file.id}"
)
```

## Tile Count Estimation

Number of tiles increases exponentially:

| Max Zoom | Approximate Tiles | Storage (typical) | Processing Time |
|----------|------------------|-------------------|-----------------|
| 21 | ~10,000 tiles | 50-100 MB | 2-5 minutes |
| 22 | ~40,000 tiles | 200-400 MB | 8-15 minutes |
| 23 | ~160,000 tiles | 800 MB - 1.6 GB | 30-60 minutes |
| 24 | ~640,000 tiles | 3-6 GB | 2-4 hours |

**Formula:** Each zoom level increase = 4x more tiles

## Leaflet Map Configuration

When tiles are ready, Leaflet will automatically use the max zoom:

```javascript
// Current (auto-configured from backend)
L.tileLayer(tileUrl, {
    maxZoom: 21,  // From database
    minZoom: 15
})

// After increasing to 23, this will update automatically
L.tileLayer(tileUrl, {
    maxZoom: 23,  // From database
    minZoom: 15
})
```

## Recommended Settings

### For Orthophotos (Aerial Images)
```
min_zoom = 15
max_zoom = 23  ← High detail needed
```

### For DEMs (Elevation Models)
```
min_zoom = 15
max_zoom = 21  ← Current default is fine
```

### For Large Areas (> 10 km²)
```
min_zoom = 13
max_zoom = 21  ← Start zoomed out
```

### For Small Sites (< 1 km²)
```
min_zoom = 16
max_zoom = 24  ← Maximum detail
```

## Quick Implementation

### Simple: Edit One Line

1. Open `/app/routers/upload.py`
2. Change line 173:
   ```python
   21   # max_zoom
   ```
   To:
   ```python
   23   # max_zoom - increased for more detail
   ```

3. Restart Celery worker:
   ```bash
   cd /home/oguntoye/GravelRoad_Iowa/FastAPI
   # Stop current worker (Ctrl+C)
   ./run_celery_worker.sh
   ```

4. **All new uploads** will use zoom level 23

### Advanced: Per-File Control

If you want to choose zoom level per file, you can:

1. Add form field in frontend upload page
2. Pass zoom level to backend API
3. Use it in tile generation task

## Storage Cost Impact

Assuming $0.023/GB/month for S3:

| Max Zoom | Storage/File | Monthly Cost (10 files) |
|----------|--------------|-------------------------|
| 21 | 75 MB | $0.02 |
| 22 | 300 MB | $0.07 |
| 23 | 1.2 GB | $0.28 |
| 24 | 4.8 GB | $1.10 |

## Current Tiles

Check current zoom levels:
```bash
python3 << EOF
from app.database import SessionLocal
from app.models import TiffFile

db = SessionLocal()
files = db.query(TiffFile).all()

for f in files:
    print(f"{f.filename}: zoom {f.tile_min_zoom}-{f.tile_max_zoom}")
db.close()
EOF
```

---

Generated: 2025-11-11
