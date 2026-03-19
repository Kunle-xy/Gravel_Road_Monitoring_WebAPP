from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AWS (credentials come from IAM role on EC2, optional for local dev)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-2"
    S3_BUCKET_NAME: str  # Main bucket for tiles (gravel-road-app)
    S3_BUCKET_RAW: str  # Raw uploads bucket (gravel-road-raw)

    # AWS CloudFront
    AWS_CLOUDFRONT_DOMAIN: str
    AWS_CLOUDFRONT_ARN: str = ""
    AWS_CLOUDFRONT_ORIGIN_ACCESS_ID: str = ""

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # TiTiler
    TITILER_URL: str = "https://titiler.xyz"  # Public TiTiler instance or your own

    # Email verification
    EMAIL_PROVIDER: str = "console"  # "console", "ses", or "resend"
    SES_FROM_EMAIL: str = ""  # Verified SES sender email
    RESEND_API_KEY: str = ""  # Resend API key (starts with re_)
    RESEND_FROM_EMAIL: str = "Gravel Road Iowa <onboarding@resend.dev>"
    EMAIL_VERIFY_EXPIRE_HOURS: int = 24

    # Redis
    REDIS_PASSWORD: str = ""

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        extra = "ignore"  # This fixes the validation error!

settings = Settings()