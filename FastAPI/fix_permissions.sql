-- Fix table ownership so kunle_admin can run migrations
-- Run this as the postgres user or a superuser

-- Transfer ownership of all tables to kunle_admin
ALTER TABLE users OWNER TO kunle_admin;
ALTER TABLE tiff_files OWNER TO kunle_admin;

-- Grant all privileges on the database
GRANT ALL PRIVILEGES ON DATABASE gravel_road_app TO kunle_admin;

-- Grant all privileges on all tables in the public schema
GRANT ALL PRIVILEGES ON ALL TABLES IN PUBLIC SCHEMA TO kunle_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN PUBLIC SCHEMA TO kunle_admin;

-- Make kunle_admin the default owner for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kunle_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO kunle_admin;

-- Verify
SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'public';
