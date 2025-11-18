#!/usr/bin/env python3
"""
Add tile-related columns to tiff_files table
"""
from sqlalchemy import create_engine, text, inspect
from app.config import settings

def add_tile_columns():
    """Add tile generation columns to tiff_files table"""
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)

    print("\n=== Checking current schema ===")
    inspector = inspect(engine)
    existing_columns = [col['name'] for col in inspector.get_columns('tiff_files')]
    print(f"Existing columns: {', '.join(existing_columns)}")

    # Define tile columns to add
    tile_columns = {
        'tile_status': "VARCHAR(50) DEFAULT 'pending'",
        'tile_progress': "INTEGER DEFAULT 0",
        'tile_url_template': "TEXT",
        'tile_error': "TEXT",
        'tile_min_zoom': "INTEGER DEFAULT 15",
        'tile_max_zoom': "INTEGER DEFAULT 21",
        'tiles_generated_at': "TIMESTAMP WITH TIME ZONE"
    }

    missing_columns = [col for col in tile_columns.keys() if col not in existing_columns]

    if not missing_columns:
        print("\n✓ All tile columns already exist!")
        return

    print(f"\n⚠ Missing columns: {', '.join(missing_columns)}")
    print("\n=== Adding missing columns ===")

    with engine.connect() as conn:
        for column_name in missing_columns:
            column_def = tile_columns[column_name]
            sql = f"ALTER TABLE tiff_files ADD COLUMN IF NOT EXISTS {column_name} {column_def};"

            try:
                print(f"Adding column: {column_name}")
                conn.execute(text(sql))
                conn.commit()
                print(f"  ✓ Added {column_name}")
            except Exception as e:
                print(f"  ✗ Error adding {column_name}: {e}")
                conn.rollback()

    print("\n=== Verifying changes ===")
    inspector = inspect(engine)
    new_columns = [col['name'] for col in inspector.get_columns('tiff_files')]

    added = [col for col in missing_columns if col in new_columns]
    if added:
        print(f"✓ Successfully added: {', '.join(added)}")

    still_missing = [col for col in missing_columns if col not in new_columns]
    if still_missing:
        print(f"✗ Still missing: {', '.join(still_missing)}")
    else:
        print("\n✓ All tile columns added successfully!")

if __name__ == "__main__":
    add_tile_columns()
