-- Add PDF columns to rut_analysis_jobs table
-- Run this migration to add PDF generation support

ALTER TABLE rut_analysis_jobs
ADD COLUMN IF NOT EXISTS pdf_plot_s3_key VARCHAR(500),
ADD COLUMN IF NOT EXISTS pdf_plot_url TEXT;

-- Create index for faster PDF URL lookups
CREATE INDEX IF NOT EXISTS idx_rut_analysis_pdf_s3_key ON rut_analysis_jobs(pdf_plot_s3_key);

-- Verify columns were added
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'rut_analysis_jobs'
AND column_name IN ('pdf_plot_s3_key', 'pdf_plot_url');
