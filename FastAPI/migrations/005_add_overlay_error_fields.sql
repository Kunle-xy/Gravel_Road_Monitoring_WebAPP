-- 005: Persist the reason an overlay GeoJSON failed to be generated/uploaded.
-- The analysis itself can succeed (HTML report, severity totals) while the
-- map-overlay GeoJSON build raises (e.g., compound CRS not handled by
-- pyproj.Transformer). Previously this was logged on the worker only and
-- the UI silently hid the "Show on Map" button. Surface it instead.

ALTER TABLE rut_analysis_jobs ADD COLUMN IF NOT EXISTS overlay_error TEXT;
ALTER TABLE crown_analysis_jobs ADD COLUMN IF NOT EXISTS overlay_error TEXT;
ALTER TABLE corrugation_analysis_jobs ADD COLUMN IF NOT EXISTS overlay_error TEXT;

COMMENT ON COLUMN rut_analysis_jobs.overlay_error IS 'Why the rut overlay GeoJSON could not be produced; NULL on success';
COMMENT ON COLUMN crown_analysis_jobs.overlay_error IS 'Why the crown overlay GeoJSON could not be produced; NULL on success';
COMMENT ON COLUMN corrugation_analysis_jobs.overlay_error IS 'Why the corrugation overlay GeoJSON could not be produced; NULL on success';
