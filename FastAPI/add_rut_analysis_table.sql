-- Migration: Add rut_analysis_jobs table
-- Date: 2025-11-18
-- Description: Create table for storing rut analysis jobs and results

-- Create rut_analysis_jobs table
CREATE TABLE IF NOT EXISTS rut_analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tiff_file_id UUID NOT NULL REFERENCES tiff_files(id) ON DELETE CASCADE,

    -- Analysis parameters
    polygon_geojson JSONB NOT NULL,
    dy_freq INTEGER DEFAULT 3,
    dx DOUBLE PRECISION DEFAULT 0.1,
    apply_smoothing BOOLEAN DEFAULT FALSE,
    gaussian_sigma DOUBLE PRECISION DEFAULT 1.0,

    -- Job status
    status VARCHAR(50) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    error_message TEXT,
    celery_task_id VARCHAR(255),

    -- Results
    results_json JSONB,
    html_plot_s3_key VARCHAR(500),
    html_plot_url TEXT,
    pdf_plot_s3_key VARCHAR(500),
    pdf_plot_url TEXT,

    -- Statistics
    total_ruts_detected INTEGER DEFAULT 0,
    low_severity_count INTEGER DEFAULT 0,
    medium_severity_count INTEGER DEFAULT 0,
    high_severity_count INTEGER DEFAULT 0,
    total_area_sqft DOUBLE PRECISION DEFAULT 0.0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_rut_analysis_user_id ON rut_analysis_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_rut_analysis_tiff_file_id ON rut_analysis_jobs(tiff_file_id);
CREATE INDEX IF NOT EXISTS idx_rut_analysis_status ON rut_analysis_jobs(status);
CREATE INDEX IF NOT EXISTS idx_rut_analysis_created_at ON rut_analysis_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rut_analysis_pdf_s3_key ON rut_analysis_jobs(pdf_plot_s3_key);

-- Add comment to table
COMMENT ON TABLE rut_analysis_jobs IS 'Stores rut distress analysis jobs and results for TIFF/DEM files';
