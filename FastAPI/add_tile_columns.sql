-- Add tile-related columns to tiff_files table
-- Run this as postgres user or table owner

-- Add tile_status column
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_status VARCHAR(50) DEFAULT 'pending';

-- Add tile_progress column
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_progress INTEGER DEFAULT 0;

-- Add tile_url_template column
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_url_template TEXT;

-- Add tile_error column
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_error TEXT;

-- Add tile_min_zoom column
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_min_zoom INTEGER DEFAULT 15;

-- Add tile_max_zoom column
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_max_zoom INTEGER DEFAULT 21;

-- Add tiles_generated_at column
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tiles_generated_at TIMESTAMP WITH TIME ZONE;

-- Grant permissions to kunle_admin
GRANT ALL PRIVILEGES ON TABLE tiff_files TO kunle_admin;

-- Verify columns
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'tiff_files'
ORDER BY ordinal_position;
