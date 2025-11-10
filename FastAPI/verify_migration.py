#!/usr/bin/env python3
"""
Verify that COG fields exist in the database
"""
from sqlalchemy import create_engine, text
from app.config import settings

def verify():
    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        print("=== Checking tiff_files table structure ===\n")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'tiff_files'
            ORDER BY ordinal_position;
        """))

        columns = []
        cog_fields = ['cog_s3_key', 'cog_size_bytes', 'is_cog', 'cog_created_at']
        found_cog_fields = []

        for row in result:
            columns.append(row[0])
            marker = "✓ [NEW]" if row[0] in cog_fields else "      "
            print(f"{marker} {row[0]}: {row[1]} (nullable: {row[2]})")
            if row[0] in cog_fields:
                found_cog_fields.append(row[0])

        print("\n=== Migration Status ===")
        if len(found_cog_fields) == len(cog_fields):
            print("✓ SUCCESS! All COG fields are present:")
            for field in found_cog_fields:
                print(f"  ✓ {field}")
            print("\n✓ Database is ready to use COG features!")
        else:
            missing = set(cog_fields) - set(found_cog_fields)
            print(f"⚠ INCOMPLETE: Missing {len(missing)} field(s):")
            for field in missing:
                print(f"  ✗ {field}")
            print("\nThe migration needs to be completed.")

if __name__ == "__main__":
    verify()
