from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, Integer, ForeignKey, Text
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
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    tiff_files = relationship("TiffFile", back_populates="user")
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")

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