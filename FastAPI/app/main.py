from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.database import engine, Base
from app.routers import auth, files, upload, tiles_status, folders, rut_analysis, crown_analysis, corrugation_analysis, dust_analysis
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.CELERY_BROKER_URL,  # Reuse existing Redis instance
)

app = FastAPI(
    title="Gravel Road API",
    version="2.0.0",
    description="Gravel Road Iowa - TIFF Mapping with Static Tile Generation",
)

app.state.limiter = limiter

def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Too many requests. You are limited to {exc.detail}. Please wait and try again later."
        },
    )

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(upload.router)
app.include_router(tiles_status.router)  # Tile generation status API
app.include_router(rut_analysis.router)  # New: Rut distress analysis
app.include_router(crown_analysis.router)  # Crown distress analysis
app.include_router(corrugation_analysis.router)  # Corrugation distress analysis
app.include_router(dust_analysis.router)  # Dust distress analysis (video + YOLOv8)


@app.on_event("startup")
async def startup_event():
    """Application startup"""
    import app.models  # noqa: ensure all models are registered
    from app.models import RefreshToken
    from app.database import SessionLocal
    from datetime import datetime, timezone

    Base.metadata.create_all(bind=engine)

    # Cleanup expired/revoked refresh tokens
    db = SessionLocal()
    try:
        deleted = db.query(RefreshToken).filter(
            (RefreshToken.revoked == True) | (RefreshToken.expires_at < datetime.now(timezone.utc))
        ).delete(synchronize_session=False)
        db.commit()
        if deleted:
            logger.info(f"Cleaned up {deleted} expired/revoked refresh tokens")
    finally:
        db.close()

    logger.info("Starting Gravel Road API v2.0.0")
    logger.info("Static tile generation enabled")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown - cleanup resources"""
    logger.info("Shutting down Gravel Road API")
    logger.info("Celery workers will continue processing tasks")


@app.get("/")
def root():
    return {
        "message": "Gravel Road API",
        "version": "2.0.0",
        "features": ["Static tile generation", "Async job processing"]
    }


@app.get("/health")
def health():
    return {"status": "healthy", "version": "2.0.0"}