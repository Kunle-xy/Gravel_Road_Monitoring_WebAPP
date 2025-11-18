-- Migration: Change folder_id foreign key to CASCADE delete
-- This ensures when a folder is deleted, all files in it are also deleted

-- Step 1: Drop the existing foreign key constraint
-- First, find the constraint name
DO $$
DECLARE
    constraint_name text;
BEGIN
    -- Get the constraint name dynamically
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'tiff_files'::regclass
    AND confrelid = 'folders'::regclass;

    -- Drop the constraint if it exists
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE tiff_files DROP CONSTRAINT %I', constraint_name);
        RAISE NOTICE 'Dropped constraint: %', constraint_name;
    END IF;
END $$;

-- Step 2: Add the new foreign key constraint with CASCADE
ALTER TABLE tiff_files
ADD CONSTRAINT tiff_files_folder_id_fkey
FOREIGN KEY (folder_id)
REFERENCES folders(id)
ON DELETE CASCADE;

-- Verify the change
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_name = 'tiff_files'
AND kcu.column_name = 'folder_id';
