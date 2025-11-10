#!/usr/bin/env python3
"""
Run database migration to add COG fields to tiff_files table
"""
import sys
from sqlalchemy import create_engine, text
from app.config import settings

def run_migration():
    """Execute the COG fields migration"""
    print("Connecting to database...")
    print(f"Database URL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")

    try:
        engine = create_engine(settings.DATABASE_URL)

        with engine.connect() as conn:
            print("\n=== Current tiff_files table structure ===")
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'tiff_files'
                ORDER BY ordinal_position;
            """))

            existing_columns = []
            for row in result:
                existing_columns.append(row[0])
                print(f"  {row[0]}: {row[1]} (nullable: {row[2]})")

            # Check if migration already applied
            cog_fields = ['cog_s3_key', 'cog_size_bytes', 'is_cog', 'cog_created_at']
            already_exists = all(field in existing_columns for field in cog_fields)

            if already_exists:
                print("\n✓ Migration already applied! COG fields exist.")
                return

            print("\n=== Applying migration ===")

            # Read migration SQL (simplified version without COMMENT statements)
            with open('migrations/001_add_cog_fields_simple.sql', 'r') as f:
                migration_sql = f.read()

            # Execute migration
            conn.execute(text(migration_sql))
            conn.commit()

            print("✓ Migration executed successfully!")

            # Verify migration
            print("\n=== Updated table structure ===")
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'tiff_files'
                ORDER BY ordinal_position;
            """))

            for row in result:
                marker = "NEW" if row[0] in cog_fields else "   "
                print(f"  {marker} {row[0]}: {row[1]} (nullable: {row[2]})")

            print("\n✓ Database migration completed successfully!")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
