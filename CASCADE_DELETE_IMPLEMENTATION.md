# CASCADE DELETE Implementation for Folders

## Overview

Changed folder deletion behavior from **"SET NULL"** (keep files, remove folder reference) to **"CASCADE"** (permanently delete all files in the folder).

## What Changed

### Before
- Deleting a folder would:
  - Remove the folder from the database
  - Set `folder_id = NULL` for all files in that folder
  - Keep all files in database and S3 storage
  - Files became "uncategorized"

### After
- Deleting a folder will:
  - Permanently delete ALL files in the folder from the database
  - Delete ALL S3 objects for each file:
    - Original TIFF files (RAW bucket)
    - COG files (RAW bucket)
    - COG files (APP bucket)
    - All generated tiles (APP bucket)
  - Delete the folder from the database
  - **This action is IRREVERSIBLE**

---

## Files Modified

### Backend

1. **`FastAPI/app/models.py`**
   - Changed `folder_id` foreign key from `ondelete="SET NULL"` to `ondelete="CASCADE"` (line 45)
   - Added cascade relationship to Folder model (line 38)

2. **`FastAPI/app/routers/folders.py`**
   - Added S3 client imports and initialization
   - Completely rewrote `delete_folder` endpoint to:
     - Fetch all files in the folder
     - Delete S3 objects for each file (original, COG, tiles)
     - Delete folder (which cascades to delete database records)
   - Added comprehensive logging

### Database Migration

3. **`FastAPI/migrations/alter_folder_cascade.sql`** (NEW)
   - SQL migration to alter foreign key constraint
   - Drops existing constraint
   - Re-adds with `ON DELETE CASCADE`

4. **`FastAPI/apply_cascade_migration.py`** (NEW)
   - Python script to apply migration safely
   - Includes verification step
   - Requires explicit confirmation

### Frontend

5. **`webapp/app/components/FolderTree/FolderTreeItem.tsx`**
   - Updated deletion confirmation message (line 118)
   - Now warns: "This will PERMANENTLY delete all X files from database and S3 storage"
   - Shows file count in warning
   - Emphasizes action cannot be undone

---

## How to Apply Changes

### Step 1: Apply Database Migration

**IMPORTANT:** This will change the database constraint. After this, deleting a folder will permanently delete all files.

```bash
cd /home/oguntoye/GravelRoad_Iowa/FastAPI

# Run the migration script
python3 apply_cascade_migration.py
```

The script will:
1. Ask for confirmation
2. Drop the existing `folder_id` foreign key constraint
3. Re-add it with `ON DELETE CASCADE`
4. Verify the change was successful

**Expected output:**
```
==============================================================
CASCADE DELETE MIGRATION FOR FOLDERS
==============================================================

This migration changes the folder_id foreign key constraint
from 'SET NULL' to 'CASCADE'.

⚠️  IMPORTANT: After this migration, deleting a folder will
permanently delete ALL files within that folder from both
the database and S3 storage.

==============================================================

Do you want to proceed? (yes/no): yes

🔄 Applying CASCADE delete migration...
📄 Reading migration file: /home/oguntoye/GravelRoad_Iowa/FastAPI/migrations/alter_folder_cascade.sql
✅ Migration applied successfully!

📊 Verifying CASCADE constraint...
✅ Verified: tiff_files_folder_id_fkey is now CASCADE

⚠️  WARNING: Deleting a folder will now permanently delete all files in it!
```

### Step 2: Restart Backend Server

The backend must be restarted to load the updated models:

```bash
# In the terminal running FastAPI, press Ctrl+C to stop

# Restart
cd /home/oguntoye/GravelRoad_Iowa/FastAPI
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Restart Frontend (Optional)

The frontend changes are already in the code, but restart to ensure they're loaded:

```bash
# In the terminal running Next.js, press Ctrl+C to stop

# Restart
cd /home/oguntoye/GravelRoad_Iowa/webapp
npm run dev
```

---

## Testing

### 1. Test Database Constraint

```sql
-- Check the CASCADE constraint is in place
SELECT
    tc.constraint_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_name = 'tiff_files'
AND tc.constraint_name LIKE '%folder_id%';

-- Expected result: delete_rule = 'CASCADE'
```

### 2. Test Folder Deletion

**⚠️ WARNING: Use a test folder with test files only!**

1. Create a test folder in the UI
2. Upload a test TIFF file to that folder
3. Verify file appears in the folder
4. Click delete on the folder
5. Confirm you see the warning: "This will PERMANENTLY delete all X files..."
6. Type "I confirm" and delete
7. Verify:
   - Folder is gone from UI
   - File is gone from database
   - All S3 objects are deleted (check S3 console or logs)

### 3. Check Backend Logs

After deleting a folder, check the logs for confirmation:

```bash
tail -f /home/oguntoye/GravelRoad_Iowa/FastAPI/logs/app.log
```

Expected log entries:
```
INFO - Deleting folder 'Test Folder' (ID: xxx) with 2 files
INFO - Deleting S3 objects for file: test.tif (ID: yyy)
INFO - Deleted original: s3://bucket/path/to/file.tif
INFO - Deleted COG from RAW: s3://bucket/path/to/file_cog.tif
INFO - Deleted COG from APP: s3://bucket/cogs/user_id/file_id.tif
INFO - Deleted 150 tile files for test.tif
INFO - Successfully deleted folder 'Test Folder' and 2 files
```

---

## Rollback (If Needed)

If you need to rollback to the old behavior (SET NULL):

### 1. Rollback Database Migration

```sql
-- Drop CASCADE constraint
ALTER TABLE tiff_files DROP CONSTRAINT IF EXISTS tiff_files_folder_id_fkey;

-- Re-add with SET NULL
ALTER TABLE tiff_files
ADD CONSTRAINT tiff_files_folder_id_fkey
FOREIGN KEY (folder_id)
REFERENCES folders(id)
ON DELETE SET NULL;
```

### 2. Rollback Code Changes

```bash
cd /home/oguntoye/GravelRoad_Iowa

# Use git to revert the changes
git checkout HEAD -- FastAPI/app/models.py
git checkout HEAD -- FastAPI/app/routers/folders.py
git checkout HEAD -- webapp/app/components/FolderTree/FolderTreeItem.tsx
```

### 3. Restart Backend

Restart FastAPI server after rollback.

---

## Safety Features

1. **Confirmation Required**: User must type "I confirm" exactly
2. **File Count Shown**: Warning displays number of files that will be deleted
3. **Clear Warning**: UI emphasizes permanent deletion and irreversibility
4. **Comprehensive Logging**: All deletions are logged for audit trail
5. **Error Handling**: S3 deletion errors are logged but don't block folder deletion
6. **User Verification**: Only folder owner can delete (auth check)

---

## S3 Objects Deleted

For each file in the deleted folder, the following S3 objects are removed:

1. **Original TIFF** (RAW bucket)
   - Path: `uploads/{user_id}/{date}/{file_type}/{filename}.tif`

2. **COG in RAW bucket** (if exists)
   - Path: `uploads/{user_id}/{date}/{file_type}/{filename}_cog.tif`

3. **COG in APP bucket**
   - Path: `cogs/{user_id}/{file_id}.tif`

4. **All Tiles** (APP bucket)
   - Path: `tiles/{user_id}/{file_id}/{z}/{x}/{y}.png`
   - Can be hundreds or thousands of files

---

## Important Notes

- **This change is permanent once migration is applied**
- **Test thoroughly before using in production**
- **Consider backing up database before migration**
- **Existing folders/files are not affected until deletion occurs**
- **S3 deletion is best-effort** (logs warnings if objects not found)
- **Database CASCADE happens automatically** after migration

---

## Migration Checklist

- [ ] Backup database
- [ ] Run `apply_cascade_migration.py`
- [ ] Verify CASCADE constraint is active
- [ ] Restart FastAPI backend
- [ ] Restart Next.js frontend (optional)
- [ ] Test with a test folder and test files
- [ ] Verify S3 objects are deleted
- [ ] Check backend logs for errors
- [ ] Document the change for other developers

---

## Support

If issues occur:
1. Check backend logs: `tail -f FastAPI/logs/app.log`
2. Check database constraint: Run verification SQL above
3. Check S3 permissions: Ensure delete permissions are granted
4. Verify AWS credentials are correct in `.env`

---

**Implementation Complete!** ✅

Folder deletion now performs true CASCADE delete, removing all files and S3 objects permanently.
