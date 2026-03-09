-- Add neighbor evaluation fields to rut_analysis_jobs table
-- Migration 004: Add neighbor_eval and neighbor_range columns

ALTER TABLE rut_analysis_jobs
ADD COLUMN IF NOT EXISTS neighbor_eval BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS neighbor_range INTEGER DEFAULT 2;

-- Add comments for clarity
COMMENT ON COLUMN rut_analysis_jobs.neighbor_eval IS 'Whether to try neighboring sampling frequencies';
COMMENT ON COLUMN rut_analysis_jobs.neighbor_range IS 'Plus or minus range for neighbor frequencies (default 2)';
