from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, Integer, ForeignKey, Text, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    organization = Column(String(255))
    is_active = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    tiff_files = relationship("TiffFile", back_populates="user")
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")

class Folder(Base):
    __tablename__ = "folders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7), default="#3b82f6")  # Hex color for folder display
    is_expanded = Column(Boolean, default=True)  # Track expand/collapse state
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="folders")
    tiff_files = relationship("TiffFile", back_populates="folder", cascade="all, delete-orphan")

class TiffFile(Base):
    __tablename__ = "tiff_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    folder_id = Column(UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    original_size_bytes = Column(BigInteger, nullable=False)
    s3_bucket = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False)
    s3_url = Column(Text)
    # COG (Cloud Optimized GeoTIFF) fields
    cog_s3_key = Column(String(500))  # S3 key for COG version
    cog_size_bytes = Column(BigInteger)
    is_cog = Column(Boolean, default=False)  # Whether original file is already COG
    cog_created_at = Column(DateTime(timezone=True))
    # Geographic bounds (stored as JSON for fast access)
    bounds_south = Column(String(50))  # South latitude
    bounds_west = Column(String(50))   # West longitude
    bounds_north = Column(String(50))  # North latitude
    bounds_east = Column(String(50))   # East longitude
    upload_status = Column(String(50), default="pending")
    upload_progress = Column(Integer, default=0)
    upload_completed_at = Column(DateTime(timezone=True))

    # Static tile generation fields
    tile_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    tile_progress = Column(Integer, default=0)  # 0-100
    tile_url_template = Column(Text)  # https://bucket/tiles/{file_id}/{z}/{x}/{y}.webp
    tile_error = Column(Text)  # Error message if tiling failed
    tile_min_zoom = Column(Integer, default=15)
    tile_max_zoom = Column(Integer, default=21)
    tiles_generated_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="tiff_files")
    folder = relationship("Folder", back_populates="tiff_files")
    rut_analyses = relationship("RutAnalysisJob", back_populates="tiff_file", cascade="all, delete-orphan")

class RutAnalysisJob(Base):
    __tablename__ = "rut_analysis_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tiff_file_id = Column(UUID(as_uuid=True), ForeignKey("tiff_files.id", ondelete="CASCADE"), nullable=False)

    # Analysis parameters
    polygon_geojson = Column(JSON, nullable=False)  # GeoJSON polygon for analysis area
    dy_freq = Column(Integer, default=3)  # Sampling frequency per 100 pixels
    dx = Column(Float, default=0.1)  # Rutting width in meters
    apply_smoothing = Column(Boolean, default=False)  # Apply Gaussian smoothing
    gaussian_sigma = Column(Float, default=1.0)  # Gaussian sigma in pixels
    neighbor_eval = Column(Boolean, default=False)  # Try neighboring sampling frequencies
    neighbor_range = Column(Integer, default=2)  # Plus or minus range for neighbor frequencies

    # Job status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text)
    celery_task_id = Column(String(255))  # Celery task ID for tracking

    # Results
    results_json = Column(JSON)  # Store detected ruts as JSON
    html_plot_s3_key = Column(String(500))  # S3 key for HTML plot
    html_plot_url = Column(Text)  # CloudFront URL for HTML plot
    pdf_plot_s3_key = Column(String(500))  # S3 key for PDF report
    pdf_plot_url = Column(Text)  # CloudFront URL for PDF report

    # Statistics
    total_ruts_detected = Column(Integer, default=0)
    low_severity_count = Column(Integer, default=0)
    medium_severity_count = Column(Integer, default=0)
    high_severity_count = Column(Integer, default=0)
    total_area_sqft = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))

    tiff_file = relationship("TiffFile", back_populates="rut_analyses")