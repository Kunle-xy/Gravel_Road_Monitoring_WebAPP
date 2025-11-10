from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # AWS S3
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # TiTiler
    TITILER_URL: str = "https://titiler.xyz"  # Public TiTiler instance or your own

    class Config:
        env_file = ".env"
        extra = "ignore"  # This fixes the validation error!

settings = Settings()