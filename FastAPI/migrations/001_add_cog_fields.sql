-- Migration: Add COG (Cloud Optimized GeoTIFF) fields to tiff_files table
-- Date: 2025-11-10

-- Add new columns for COG support
ALTER TABLE tiff_files
ADD COLUMN IF NOT EXISTS cog_s3_key VARCHAR(500),
ADD COLUMN IF NOT EXISTS cog_size_bytes BIGINT,
ADD COLUMN IF NOT EXISTS is_cog BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS cog_created_at TIMESTAMP WITH TIME ZONE;

-- Add index on cog_s3_key for faster lookups
CREATE INDEX IF NOT EXISTS idx_tiff_files_cog_s3_key ON tiff_files(cog_s3_key);

-- Add comment to document the fields
COMMENT ON COLUMN tiff_files.cog_s3_key IS 'S3 key for the Cloud Optimized GeoTIFF version of the file';
COMMENT ON COLUMN tiff_files.cog_size_bytes IS 'Size of the COG file in bytes';
COMMENT ON COLUMN tiff_files.is_cog IS 'Whether the original file was already a COG';
COMMENT ON COLUMN tiff_files.cog_created_at IS 'Timestamp when the COG was created';
