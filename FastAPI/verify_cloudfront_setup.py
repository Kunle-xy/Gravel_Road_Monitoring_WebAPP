#!/usr/bin/env python3
"""
Verify CloudFront and S3 Configuration for Tile Serving
"""
import boto3
from app.config import settings

def verify_setup():
    """Verify CloudFront and S3 configuration"""
    print("=" * 60)
    print("CloudFront & S3 Configuration Verification")
    print("=" * 60)

    # Configuration
    print("\n[1] Configuration")
    print(f"  ✓ Tiles Bucket: {settings.S3_BUCKET_NAME}")
    print(f"  ✓ Raw Bucket: {settings.S3_BUCKET_RAW}")
    print(f"  ✓ CloudFront Domain: {settings.AWS_CLOUDFRONT_DOMAIN}")
    print(f"  ✓ Region: {settings.AWS_REGION}")

    # S3 Client
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )

    # Check S3 buckets exist
    print("\n[2] S3 Bucket Access")
    for bucket_name in [settings.S3_BUCKET_NAME, settings.S3_BUCKET_RAW]:
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"  ✓ Can access bucket: {bucket_name}")
        except Exception as e:
            print(f"  ✗ Cannot access bucket {bucket_name}: {e}")

    # Check for existing tiles
    print("\n[3] Existing Tiles in S3")
    try:
        response = s3.list_objects_v2(
            Bucket=settings.S3_BUCKET_NAME,
            Prefix='tiles/',
            MaxKeys=10
        )

        if 'Contents' in response and len(response['Contents']) > 0:
            print(f"  ✓ Found {response['KeyCount']} tiles (showing first 10):")
            for obj in response['Contents'][:5]:
                print(f"    - {obj['Key']} ({obj['Size']} bytes)")
            if response['KeyCount'] > 5:
                print(f"    ... and {response['KeyCount'] - 5} more")
        else:
            print(f"  ⚠ No tiles found in s3://{settings.S3_BUCKET_NAME}/tiles/")
            print(f"    This is normal if you haven't uploaded files yet.")
    except Exception as e:
        print(f"  ✗ Error listing tiles: {e}")

    # Check bucket CORS
    print("\n[4] CORS Configuration")
    try:
        cors = s3.get_bucket_cors(Bucket=settings.S3_BUCKET_NAME)
        print(f"  ✓ CORS is configured on {settings.S3_BUCKET_NAME}")
        for rule in cors.get('CORSRules', []):
            print(f"    - Allowed Methods: {', '.join(rule.get('AllowedMethods', []))}")
            print(f"    - Allowed Origins: {', '.join(rule.get('AllowedOrigins', []))}")
    except s3.exceptions.NoSuchCORSConfiguration:
        print(f"  ⚠ No CORS configuration found on {settings.S3_BUCKET_NAME}")
        print(f"    Add CORS to allow CloudFront and browser access")
    except Exception as e:
        print(f"  ⚠ Could not check CORS: {e}")

    # Check bucket policy
    print("\n[5] Bucket Policy")
    try:
        policy = s3.get_bucket_policy(Bucket=settings.S3_BUCKET_NAME)
        print(f"  ✓ Bucket policy is configured on {settings.S3_BUCKET_NAME}")
    except s3.exceptions.NoSuchBucketPolicy:
        print(f"  ⚠ No bucket policy found on {settings.S3_BUCKET_NAME}")
        print(f"    You may need to add a policy for CloudFront or public access")
    except Exception as e:
        print(f"  ⚠ Could not check bucket policy: {e}")

    # Check CloudFront
    print("\n[6] CloudFront Distribution")
    try:
        cloudfront = boto3.client(
            'cloudfront',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

        # Extract distribution ID from ARN
        dist_id = settings.AWS_CLOUDFRONT_ARN.split('/')[-1] if settings.AWS_CLOUDFRONT_ARN else None

        if dist_id:
            dist = cloudfront.get_distribution(Id=dist_id)
            config = dist['Distribution']['DistributionConfig']

            print(f"  ✓ Distribution: {dist_id}")
            print(f"  ✓ Domain: {dist['Distribution']['DomainName']}")
            print(f"  ✓ Status: {dist['Distribution']['Status']}")

            # Check origins
            print(f"\n  Origins:")
            for origin in config['Origins']['Items']:
                origin_domain = origin['DomainName']
                print(f"    - {origin_domain}")
                if settings.S3_BUCKET_NAME in origin_domain:
                    print(f"      ✓ Matches tiles bucket!")
                elif settings.S3_BUCKET_RAW in origin_domain:
                    print(f"      ⚠ Points to RAW bucket (should use tiles bucket)")
        else:
            print(f"  ⚠ Could not extract distribution ID from ARN")

    except Exception as e:
        print(f"  ⚠ Could not check CloudFront distribution: {e}")

    # Recommendations
    print("\n" + "=" * 60)
    print("Recommendations")
    print("=" * 60)
    print("\n1. Ensure CloudFront origin points to: gravel-road-app.s3.us-east-2.amazonaws.com")
    print("2. Add CORS configuration to gravel-road-app bucket (see CLOUDFRONT_SETUP_CHECKLIST.md)")
    print("3. Add bucket policy for public access or OAC (see CLOUDFRONT_SETUP_CHECKLIST.md)")
    print("4. Wait 5-10 minutes after CloudFront changes before testing")
    print("5. Upload a test file and check Celery logs for tile generation")
    print("\nFor detailed instructions, see: CLOUDFRONT_SETUP_CHECKLIST.md")
    print("=" * 60)

if __name__ == "__main__":
    verify_setup()
