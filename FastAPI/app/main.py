from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, files, upload, tiles, tiles_status, folders
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Gravel Road API",
    version="2.0.0",
    description="Gravel Road Iowa - TIFF Mapping with Static Tile Generation"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://172.29.50.232:3000",  # WSL2 IP for Windows browser access
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(upload.router)
app.include_router(tiles.router)
app.include_router(tiles_status.router)  # New: Tile generation status API


@app.on_event("startup")
async def startup_event():
    """Application startup"""
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
        "features": ["Static tile generation", "Dynamic tile fallback", "Async job processing"]
    }


@app.get("/health")
def health():
    return {"status": "healthy", "version": "2.0.0"}