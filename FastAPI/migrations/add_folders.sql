-- Migration: Add folder support for organizing files
-- Date: 2025-11-17
-- Description: Creates folders table and adds folder_id to tiff_files

-- Create folders table
CREATE TABLE IF NOT EXISTS folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(7) DEFAULT '#3b82f6',
    is_expanded BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders(user_id);
CREATE INDEX IF NOT EXISTS idx_folders_created_at ON folders(created_at);

-- Add folder_id column to tiff_files table
ALTER TABLE tiff_files
ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES folders(id) ON DELETE SET NULL;

-- Add index for folder_id
CREATE INDEX IF NOT EXISTS idx_tiff_files_folder_id ON tiff_files(folder_id);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_folders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_folders_updated_at
    BEFORE UPDATE ON folders
    FOR EACH ROW
    EXECUTE FUNCTION update_folders_updated_at();

-- Optional: Create a default folder for existing users (commented out)
-- INSERT INTO folders (user_id, name, description)
-- SELECT id, 'My Files', 'Default folder for organizing files'
-- FROM users
-- WHERE NOT EXISTS (SELECT 1 FROM folders WHERE folders.user_id = users.id);

COMMIT;
