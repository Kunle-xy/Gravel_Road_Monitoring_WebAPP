#!/usr/bin/env python3
"""
Test Database and S3 Connections
Run this from your FastAPI directory: python test_connections.py
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("🧪 Testing Gravel Road Iowa Backend Connections")
print("=" * 60)
print()

# ============================================
# TEST 1: Environment Variables
# ============================================
print("📋 TEST 1: Checking Environment Variables")
print("-" * 60)

required_vars = [
    'DATABASE_URL',
    'SECRET_KEY',
    'AWS_ACCESS_KEY_ID',
    'AWS_SECRET_ACCESS_KEY',
    'AWS_REGION',
    'S3_BUCKET_NAME'
]

missing_vars = []
for var in required_vars:
    value = os.getenv(var)
    if value:
        # Mask sensitive values
        if 'SECRET' in var or 'PASSWORD' in var:
            display_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
        elif 'DATABASE_URL' in var:
            display_value = value.split('@')[0].split('//')[0] + "//***@" + value.split('@')[1] if '@' in value else "***"
        else:
            display_value = value
        print(f"✅ {var}: {display_value}")
    else:
        print(f"❌ {var}: NOT SET")
        missing_vars.append(var)

if missing_vars:
    print(f"\n⚠️  Missing variables: {', '.join(missing_vars)}")
    print("Please update your .env file!")
    exit(1)

print("✅ All environment variables are set")
print()

# ============================================
# TEST 2: Database Connection
# ============================================
print("🗄️  TEST 2: Testing PostgreSQL Database Connection")
print("-" * 60)

try:
    from sqlalchemy import create_engine, text
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Test basic connection
        result = conn.execute(text("SELECT version()"))
        version = result.scalar()
        print(f"✅ Connected to PostgreSQL")
        print(f"   Version: {version.split(',')[0]}")
        
        # Check if tables exist
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        tables = [row[0] for row in result]
        
        if 'users' in tables and 'tiff_files' in tables:
            print(f"✅ Required tables exist: users, tiff_files")
        else:
            print(f"⚠️  Tables found: {', '.join(tables)}")
            if 'users' not in tables or 'tiff_files' not in tables:
                print("   Missing required tables! Run the database schema SQL.")
        
        # Count records
        result = conn.execute(text("SELECT COUNT(*) FROM users"))
        user_count = result.scalar()
        print(f"   Users in database: {user_count}")
        
        result = conn.execute(text("SELECT COUNT(*) FROM tiff_files"))
        file_count = result.scalar()
        print(f"   Files in database: {file_count}")
        
        print("✅ Database connection successful!")
        
except Exception as e:
    print(f"❌ Database connection failed!")
    print(f"   Error: {str(e)}")
    print()
    print("Troubleshooting:")
    print("1. Is PostgreSQL running? Run: sudo systemctl status postgresql")
    print("2. Check DATABASE_URL in .env")
    print("3. Verify database exists: psql -U gravel_admin -d gravel_road_app")
    exit(1)

print()

# ============================================
# TEST 3: AWS S3 Connection
# ============================================
print("☁️  TEST 3: Testing AWS S3 Connection")
print("-" * 60)

try:
    import boto3
    from botocore.exceptions import ClientError
    
    # Create S3 client
    s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-2'))
    
    bucket_name = os.getenv('S3_BUCKET_NAME')
    
    # Test bucket access
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Connected to S3")
        print(f"   Bucket: {bucket_name}")
        print(f"   Region: {os.getenv('AWS_REGION')}")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"⚠️  Bucket '{bucket_name}' does not exist!")
            print(f"   Create it with: aws s3 mb s3://{bucket_name}")
        elif error_code == '403':
            print(f"❌ Access denied to bucket '{bucket_name}'")
            print(f"   Check your AWS credentials")
        else:
            raise
        exit(1)
    
    # Test bucket permissions
    try:
        # Try to list objects
        response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        object_count = response.get('KeyCount', 0)
        print(f"   Objects in bucket: {object_count}")
        print("✅ Bucket permissions verified (can list objects)")
    except ClientError as e:
        print(f"⚠️  Cannot list objects: {e}")
    
    # Test write permission with a test file
    try:
        test_key = "test/connection-test.txt"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=b"Connection test",
            ContentType='text/plain'
        )
        print("✅ Write permission verified (can upload)")
        
        # Clean up test file
        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        print("✅ Delete permission verified (can delete)")
        
    except ClientError as e:
        print(f"⚠️  Write/Delete test failed: {e}")
    
    print("✅ S3 connection successful!")
    
except Exception as e:
    print(f"❌ S3 connection failed!")
    print(f"   Error: {str(e)}")
    print()
    print("Troubleshooting:")
    print("1. Check AWS credentials: aws sts get-caller-identity")
    print("2. Verify bucket exists: aws s3 ls")
    print("3. Check .env has correct AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
    exit(1)

print()

# ============================================
# TEST 4: Import All Modules
# ============================================
print("📦 TEST 4: Testing Module Imports")
print("-" * 60)

try:
    from app.config import settings
    print("✅ app.config")
    
    from app.database import engine, get_db
    print("✅ app.database")
    
    from app.models import User, TiffFile
    print("✅ app.models")
    
    from app.schemas import UserCreate, TiffFileResponse
    print("✅ app.schemas")
    
    from app.auth import get_password_hash, create_access_token
    print("✅ app.auth")
    
    from app.routers import auth, files, upload
    print("✅ app.routers")
    
    from app.main import app
    print("✅ app.main (FastAPI app)")
    
    print("✅ All modules imported successfully!")
    
except Exception as e:
    print(f"❌ Module import failed!")
    print(f"   Error: {str(e)}")
    print()
    print("Make sure all files are created in the correct structure")
    exit(1)

print()

# ============================================
# SUMMARY
# ============================================
print("=" * 60)
print("✨ ALL TESTS PASSED!")
print("=" * 60)
print()
print("🚀 Your backend is ready to run!")
print()
print("Start the server with:")
print("   uvicorn app.main:app --reload")
print()
print("Then open:")
print("   http://localhost:8000/docs")
print()
print("=" * 60)