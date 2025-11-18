# Folder-Level Project Organization - Implementation Guide

## Overview

This feature adds folder-level organization for DEM and Orthophoto files, allowing users to:
- Create folders/projects to organize files
- Upload files directly to folders
- Expand/collapse folders to show/hide files
- Rename and delete folders
- Move files between folders

---

## Backend Changes

### 1. Database Schema

**New Table: `folders`**
- `id` (UUID) - Primary key
- `user_id` (UUID) - Foreign key to users table
- `name` (VARCHAR) - Folder name
- `description` (TEXT) - Optional description
- `color` (VARCHAR) - Hex color for UI display
- `is_expanded` (BOOLEAN) - Expand/collapse state
- `created_at`, `updated_at` (TIMESTAMP)

**Modified Table: `tiff_files`**
- Added `folder_id` (UUID, nullable) - Foreign key to folders table

**Files:**
- `FastAPI/app/models.py` - Added Folder model, updated TiffFile model
- `FastAPI/app/schemas.py` - Added FolderCreate, FolderUpdate, FolderResponse, FolderWithFilesResponse
- `FastAPI/migrations/add_folders.sql` - SQL migration
- `FastAPI/apply_folder_migration.py` - Python migration script

### 2. API Endpoints

**New Router: `/folders`** (`FastAPI/app/routers/folders.py`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/folders/` | Create new folder |
| GET | `/folders/` | List all user folders |
| GET | `/folders/with-files` | List folders with their files |
| GET | `/folders/{folder_id}` | Get specific folder with files |
| PATCH | `/folders/{folder_id}` | Update folder (name, description, color, is_expanded) |
| DELETE | `/folders/{folder_id}` | Delete folder (files remain, folder_id set to NULL) |
| POST | `/folders/{folder_id}/files/{file_id}` | Add file to folder |
| DELETE | `/folders/{folder_id}/files/{file_id}` | Remove file from folder |

**Modified Endpoint:**
- `POST /upload/` - Added optional `folder_id` parameter

**Files Modified:**
- `FastAPI/app/routers/upload.py` - Added folder_id support
- `FastAPI/app/main.py` - Registered folders router

---

## Frontend Changes

### 1. API Configuration

**File: `webapp/app/lib/api.ts`**
- Added `FOLDERS` endpoints to `API_ENDPOINTS`

### 2. New Components

**File: `webapp/app/components/FolderTree/FolderTreeItem.tsx`**
- Displays folder with expand/collapse toggle
- Shows file count
- Inline folder renaming
- Delete folder action
- Renders nested files using TiffFileItem

**Features:**
- Click chevron to expand/collapse
- State persists to backend
- Hover to show edit/delete buttons
- Click name or edit icon to rename

---

## Setup Instructions

### Step 1: Apply Database Migration

```bash
cd FastAPI

# Option 1: Using Python script (recommended)
python3 apply_folder_migration.py

# Option 2: Using psql
psql -d gravel_road_app -U kunle_admin -f migrations/add_folders.sql
```

Verify migration:
```sql
-- Check folders table exists
SELECT table_name FROM information_schema.tables
WHERE table_name = 'folders';

-- Check folder_id column in tiff_files
SELECT column_name FROM information_schema.columns
WHERE table_name = 'tiff_files' AND column_name = 'folder_id';
```

### Step 2: Restart Backend

The FastAPI server must be restarted to load the new Folder model and router:

```bash
# Terminal 1: Stop (Ctrl+C) and restart
cd FastAPI
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Update Frontend (Integration Steps)

The FolderTreeItem component has been created. To integrate it into ProfileWidget:

1. Update `ProfileWidget.tsx` to fetch folders with files
2. Replace the DEM/ORTHOPHOTO sections with folder tree display
3. Show "Uncategorized Files" section for files without folder_id

**Example Integration:**
```typescript
// In ProfileWidget.tsx
const [foldersWithFiles, setFoldersWithFiles] = useState([]);
const [uncategorizedFiles, setUncategorizedFiles] = useState([]);

// Fetch folders
const response = await fetchWithAuth(API_ENDPOINTS.FOLDERS.LIST_WITH_FILES);
const folders = await response.json();
setFoldersWithFiles(folders);

// Render
{foldersWithFiles.map(folder => (
  <FolderTreeItem
    key={folder.id}
    folder={folder}
    onDelete={handleDelete}
    onRefresh={fetchAllFiles}
  />
))}
```

---

## Testing Guide

### 1. Test Database Migration

```bash
# Run migration
python3 FastAPI/apply_folder_migration.py

# Expected output:
# ✅ Migration applied successfully!
# ✅ Verified tables: folders, tiff_files
# ✅ folder_id column added to tiff_files table
```

### 2. Test Backend API

```bash
# Get auth token first
TOKEN="your_auth_token"

# 1. Create a folder
curl -X POST http://localhost:8000/folders/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Highway 20 Project", "description": "DEM and Ortho files for Highway 20", "color": "#10b981"}'

# 2. List folders
curl http://localhost:8000/folders/ \
  -H "Authorization: Bearer $TOKEN"

# 3. List folders with files
curl http://localhost:8000/folders/with-files \
  -H "Authorization: Bearer $TOKEN"

# 4. Upload file to folder
# Get folder_id from step 1, then upload:
curl -X POST http://localhost:8000/upload/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@your_file.tif" \
  -F "file_type=DEM" \
  -F "folder_id=<folder-id-here>"

# 5. Update folder (rename)
curl -X PATCH http://localhost:8000/folders/<folder-id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Highway 20 - Updated"}'

# 6. Toggle expand/collapse
curl -X PATCH http://localhost:8000/folders/<folder-id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_expanded": false}'

# 7. Move file to folder
curl -X POST http://localhost:8000/folders/<folder-id>/files/<file-id> \
  -H "Authorization: Bearer $TOKEN"

# 8. Remove file from folder
curl -X DELETE http://localhost:8000/folders/<folder-id>/files/<file-id> \
  -H "Authorization: Bearer $TOKEN"

# 9. Delete folder
curl -X DELETE http://localhost:8000/folders/<folder-id> \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Test Frontend UI

**Creating Folders:**
1. Add "Create Folder" button in ProfileWidget
2. Show modal/form to enter folder name, description, color
3. POST to `/folders/` endpoint
4. Refresh folder list

**Uploading to Folders:**
1. In upload page, add folder selection dropdown
2. Populate from `/folders/` endpoint
3. Include `folder_id` in FormData when uploading
4. File should appear in folder after upload completes

**Expand/Collapse:**
1. Click chevron icon next to folder name
2. Files should show/hide
3. State should persist (reload page and folder should remember state)

**Renaming Folders:**
1. Hover over folder name
2. Click edit icon
3. Type new name and press Enter
4. Name should update

**Deleting Folders:**
1. Hover over folder name
2. Click delete icon
3. Confirm deletion
4. Folder removed, files remain at root level

---

## Database Queries for Debugging

```sql
-- View all folders for a user
SELECT id, name, is_expanded, created_at FROM folders
WHERE user_id = '<user-uuid>' ORDER BY created_at DESC;

-- View files in a folder
SELECT f.id, f.filename, f.file_type, f.folder_id
FROM tiff_files f
WHERE f.folder_id = '<folder-uuid>';

-- View files without folder (uncategorized)
SELECT f.id, f.filename, f.file_type
FROM tiff_files f
WHERE f.folder_id IS NULL AND f.user_id = '<user-uuid>';

-- Count files per folder
SELECT fo.name, COUNT(f.id) as file_count
FROM folders fo
LEFT JOIN tiff_files f ON f.folder_id = fo.id
WHERE fo.user_id = '<user-uuid>'
GROUP BY fo.id, fo.name;
```

---

## Future Enhancements

1. **Drag & Drop**: Drag files between folders in UI
2. **Folder Colors**: Color-code folders for visual organization
3. **Folder Sharing**: Share folders with other users
4. **Nested Folders**: Support sub-folders/hierarchical structure
5. **Batch Operations**: Move multiple files to folder at once
6. **Folder Templates**: Create folders from templates (e.g., "Road Survey")
7. **Folder Export**: Export entire folder as ZIP
8. **Folder Statistics**: Show total size, file counts per type

---

## File Checklist

### Backend
- ✅ `FastAPI/app/models.py` - Folder model
- ✅ `FastAPI/app/schemas.py` - Folder schemas
- ✅ `FastAPI/app/routers/folders.py` - Folder CRUD endpoints
- ✅ `FastAPI/app/routers/upload.py` - folder_id support
- ✅ `FastAPI/app/main.py` - Router registration
- ✅ `FastAPI/migrations/add_folders.sql` - SQL migration
- ✅ `FastAPI/apply_folder_migration.py` - Python migration script

### Frontend
- ✅ `webapp/app/lib/api.ts` - Folder API endpoints
- ✅ `webapp/app/components/FolderTree/FolderTreeItem.tsx` - Folder tree component
- ⏳ `webapp/app/components/ProfileWidget.tsx` - Integration (needs manual update)
- ⏳ `webapp/app/dashboard/upload/page.tsx` - Folder selection (needs manual update)

---

## Support

For issues or questions:
1. Check backend logs: `FastAPI/logs/`
2. Check browser console for frontend errors
3. Verify database migration was successful
4. Test API endpoints with curl/Postman first
5. Ensure frontend is fetching from correct endpoints

---

**Implementation Complete!** 🎉

To activate the feature:
1. Run database migration
2. Restart FastAPI backend
3. Integrate FolderTreeItem into ProfileWidget
4. Add folder selection to upload page
5. Test end-to-end workflow
