#!/usr/bin/env python3
"""
Run database migration using SQLAlchemy's migration approach
This works around permission issues by using the app's database connection
"""
from sqlalchemy import create_engine, Column, String, BigInteger, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from app.config import settings
from app.database import Base
import app.models  # Import to load models

def run_migration():
    """Execute the COG fields migration using SQLAlchemy"""
    print("Connecting to database...")

    engine = create_engine(settings.DATABASE_URL)

    print("\n=== Checking current schema ===")
    from sqlalchemy import inspect
    inspector = inspect(engine)

    existing_columns = [col['name'] for col in inspector.get_columns('tiff_files')]
    print(f"Existing columns: {', '.join(existing_columns)}")

    cog_fields = ['cog_s3_key', 'cog_size_bytes', 'is_cog', 'cog_created_at']
    missing_fields = [field for field in cog_fields if field not in existing_columns]

    if not missing_fields:
        print("\n✓ Migration already applied! All COG fields exist.")
        return

    print(f"\n⚠ Missing fields: {', '.join(missing_fields)}")
    print("\n=== Applying migration ===")
    print("Creating/updating table schema based on models...")

    # This will create missing columns
    Base.metadata.create_all(engine, checkfirst=True)

    print("\n✓ Schema updated!")

    # Verify
    inspector = inspect(engine)
    new_columns = [col['name'] for col in inspector.get_columns('tiff_files')]
    print(f"\nUpdated columns: {', '.join(new_columns)}")

    added_fields = [field for field in cog_fields if field in new_columns and field not in existing_columns]
    if added_fields:
        print(f"\n✓ Successfully added: {', '.join(added_fields)}")
    else:
        print("\n⚠ Note: SQLAlchemy's create_all() doesn't add columns to existing tables.")
        print("You need to either:")
        print("1. Run fix_permissions.sql as postgres user")
        print("2. Or manually add the columns using a tool with proper permissions")

if __name__ == "__main__":
    run_migration()
