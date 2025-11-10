-- Migration: Add geographic bounds fields to tiff_files table
-- Date: 2025-11-10
-- Purpose: Store bounds in DB to avoid S3 fetches on map load

-- Add bounds columns
ALTER TABLE tiff_files
ADD COLUMN IF NOT EXISTS bounds_south VARCHAR(50),
ADD COLUMN IF NOT EXISTS bounds_west VARCHAR(50),
ADD COLUMN IF NOT EXISTS bounds_north VARCHAR(50),
ADD COLUMN IF NOT EXISTS bounds_east VARCHAR(50);

-- Add index for faster bounds queries
CREATE INDEX IF NOT EXISTS idx_tiff_files_bounds ON tiff_files(bounds_south, bounds_west, bounds_north, bounds_east);
