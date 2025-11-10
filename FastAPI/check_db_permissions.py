#!/usr/bin/env python3
"""
Check database permissions and table ownership
"""
from sqlalchemy import create_engine, text
from app.config import settings

def check_permissions():
    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        print("=== Database Connection Info ===")
        result = conn.execute(text("SELECT current_user, current_database();"))
        row = result.fetchone()
        print(f"Current user: {row[0]}")
        print(f"Current database: {row[1]}")

        print("\n=== Table Owner ===")
        result = conn.execute(text("""
            SELECT tableowner
            FROM pg_tables
            WHERE tablename = 'tiff_files';
        """))
        row = result.fetchone()
        if row:
            print(f"tiff_files owner: {row[0]}")
        else:
            print("Table not found!")

        print("\n=== Current User Privileges ===")
        result = conn.execute(text("""
            SELECT privilege_type
            FROM information_schema.table_privileges
            WHERE table_name = 'tiff_files'
            AND grantee = current_user;
        """))
        privileges = [row[0] for row in result]
        print(f"Privileges: {', '.join(privileges) if privileges else 'None'}")

        print("\n=== Suggested Solution ===")
        if row:
            print(f"You need to either:")
            print(f"1. Connect as user '{row[0]}' (the table owner)")
            print(f"2. Run this command as the table owner or superuser:")
            print(f"   ALTER TABLE tiff_files OWNER TO {conn.execute(text('SELECT current_user')).scalar()};")
            print(f"3. Or grant ALTER permission:")
            print(f"   GRANT ALL ON TABLE tiff_files TO {conn.execute(text('SELECT current_user')).scalar()};")

if __name__ == "__main__":
    check_permissions()
