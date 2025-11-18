#!/usr/bin/env python3
"""
Apply folder migration to the database
Creates folders table and adds folder_id to tiff_files
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

def apply_migration():
    """Apply the folder migration"""
    print("Connecting to database...")
    engine = create_engine(DATABASE_URL)

    migration_sql = """
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

    DROP TRIGGER IF EXISTS trigger_folders_updated_at ON folders;
    CREATE TRIGGER trigger_folders_updated_at
        BEFORE UPDATE ON folders
        FOR EACH ROW
        EXECUTE FUNCTION update_folders_updated_at();
    """

    try:
        with engine.connect() as conn:
            print("Applying migration...")

            # Execute migration in a transaction
            with conn.begin():
                conn.execute(text(migration_sql))

            print("✅ Migration applied successfully!")

            # Verify tables exist
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('folders', 'tiff_files')
            """))

            tables = [row[0] for row in result]
            print(f"\n✅ Verified tables: {', '.join(tables)}")

            # Check if folder_id column exists in tiff_files
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'tiff_files'
                AND column_name = 'folder_id'
            """))

            if result.rowcount > 0:
                print("✅ folder_id column added to tiff_files table")

    except Exception as e:
        print(f"❌ Error applying migration: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("=" * 60)
    print("Folder Migration Script")
    print("=" * 60)
    apply_migration()
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
