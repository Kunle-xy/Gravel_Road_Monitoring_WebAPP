-- Migration: Add tile generation fields for static XYZ tile support
-- Date: 2025-11-10
-- Description: Adds fields to track static tile generation status, URLs, and metadata

-- Add tile generation tracking fields to tiff_files table
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_progress INTEGER DEFAULT 0;
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_url_template TEXT;
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_error TEXT;
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_min_zoom INTEGER DEFAULT 15;
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tile_max_zoom INTEGER DEFAULT 21;
ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS tiles_generated_at TIMESTAMP WITH TIME ZONE;

-- Add comments for documentation
COMMENT ON COLUMN tiff_files.tile_status IS 'Tile generation status: pending, queued, processing, completed, failed';
COMMENT ON COLUMN tiff_files.tile_progress IS 'Tile generation progress: 0-100';
COMMENT ON COLUMN tiff_files.tile_url_template IS 'Static tile URL template: https://bucket/tiles/{file_id}/{z}/{x}/{y}.png';
COMMENT ON COLUMN tiff_files.tile_error IS 'Error message if tile generation failed';
COMMENT ON COLUMN tiff_files.tile_min_zoom IS 'Minimum zoom level for generated tiles';
COMMENT ON COLUMN tiff_files.tile_max_zoom IS 'Maximum zoom level for generated tiles';
COMMENT ON COLUMN tiff_files.tiles_generated_at IS 'Timestamp when tiles were successfully generated';

-- Create index on tile_status for efficient queries
CREATE INDEX IF NOT EXISTS idx_tiff_files_tile_status ON tiff_files(tile_status);

-- Create index on user_id and tile_status for user-specific status queries
CREATE INDEX IF NOT EXISTS idx_tiff_files_user_tile_status ON tiff_files(user_id, tile_status);
