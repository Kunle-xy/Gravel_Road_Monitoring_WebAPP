#!/usr/bin/env python3
"""
Apply CASCADE delete migration for folder_id foreign key.
This script updates the database constraint so that deleting a folder
also deletes all files within that folder.
"""

import os
import sys
from pathlib import Path

# Add the FastAPI directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.database import engine


def apply_migration():
    """Apply the CASCADE delete migration."""
    migration_file = Path(__file__).parent / "migrations" / "alter_folder_cascade.sql"

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print("🔄 Applying CASCADE delete migration...")
    print(f"📄 Reading migration file: {migration_file}")

    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    try:
        with engine.connect() as conn:
            # Execute the migration
            conn.execute(text(migration_sql))
            conn.commit()

            print("✅ Migration applied successfully!")
            print("\n📊 Verifying CASCADE constraint...")

            # Verify the constraint
            verify_sql = """
                SELECT
                    tc.constraint_name,
                    rc.delete_rule
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.referential_constraints AS rc
                    ON tc.constraint_name = rc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'tiff_files'
                AND tc.constraint_name LIKE '%folder_id%';
            """

            result = conn.execute(text(verify_sql))
            row = result.fetchone()

            if row and row[1] == 'CASCADE':
                print(f"✅ Verified: {row[0]} is now CASCADE")
                print("\n⚠️  WARNING: Deleting a folder will now permanently delete all files in it!")
                return True
            else:
                print("⚠️  Could not verify CASCADE constraint")
                return False

    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("CASCADE DELETE MIGRATION FOR FOLDERS")
    print("=" * 60)
    print("\nThis migration changes the folder_id foreign key constraint")
    print("from 'SET NULL' to 'CASCADE'.")
    print("\n⚠️  IMPORTANT: After this migration, deleting a folder will")
    print("permanently delete ALL files within that folder from both")
    print("the database and S3 storage.")
    print("\n" + "=" * 60)

    response = input("\nDo you want to proceed? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        success = apply_migration()
        sys.exit(0 if success else 1)
    else:
        print("\n❌ Migration cancelled by user")
        sys.exit(1)
