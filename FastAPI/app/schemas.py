from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid as uuid_lib

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: uuid_lib.UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    organization: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class FolderCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#3b82f6"

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    is_expanded: Optional[bool] = None

class FolderResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    name: str
    description: Optional[str]
    color: str
    is_expanded: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class TiffFileResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    folder_id: Optional[uuid_lib.UUID] = None
    filename: str
    file_type: str
    original_size_bytes: int
    s3_bucket: str
    s3_key: str
    s3_url: Optional[str]
    cog_s3_key: Optional[str] = None
    cog_size_bytes: Optional[int] = None
    is_cog: Optional[bool] = False
    # Geographic bounds for instant map positioning
    bounds_south: Optional[str] = None
    bounds_west: Optional[str] = None
    bounds_north: Optional[str] = None
    bounds_east: Optional[str] = None
    upload_status: str
    upload_progress: int
    upload_completed_at: Optional[datetime]
    # Tile generation fields
    tile_status: Optional[str] = "pending"
    tile_progress: Optional[int] = 0
    tile_url_template: Optional[str] = None
    tile_error: Optional[str] = None
    tile_min_zoom: Optional[int] = 15
    tile_max_zoom: Optional[int] = 21
    tiles_generated_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TiffFileListResponse(BaseModel):
    total: int
    files: List[TiffFileResponse]

class FolderWithFilesResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    name: str
    description: Optional[str]
    color: str
    is_expanded: bool
    created_at: datetime
    updated_at: Optional[datetime]
    files: List[TiffFileResponse]

    class Config:
        from_attributes = True

# Rut Analysis Schemas
class RutAnalysisCreate(BaseModel):
    tiff_file_id: uuid_lib.UUID
    polygon_geojson: Dict[str, Any]  # GeoJSON polygon
    dy_freq: Optional[int] = 3  # Sampling frequency per 100 pixels (whole integers only)
    dx: Optional[float] = 0.1  # Rutting width in meters
    apply_smoothing: Optional[bool] = False
    gaussian_sigma: Optional[float] = 1.0
    neighbor_eval: Optional[bool] = False  # Try neighboring sampling frequencies
    neighbor_range: Optional[int] = 2  # Plus or minus range for neighbor frequencies
    screenshot_base64: Optional[str] = None  # Base64 encoded screenshot

class RutAnalysisResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    tiff_file_id: uuid_lib.UUID
    polygon_geojson: Dict[str, Any]
    dy_freq: int
    dx: float
    apply_smoothing: bool
    gaussian_sigma: float
    neighbor_eval: bool
    neighbor_range: int
    status: str
    progress: int
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    results_json: Optional[Dict[str, Any]] = None
    html_plot_url: Optional[str] = None
    pdf_plot_url: Optional[str] = None
    total_ruts_detected: int
    low_severity_count: int
    medium_severity_count: int
    high_severity_count: int
    total_area_sqft: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RutAnalysisStatusResponse(BaseModel):
    id: uuid_lib.UUID
    status: str
    progress: int
    error_message: Optional[str] = None
    html_plot_url: Optional[str] = None
    pdf_plot_url: Optional[str] = None
    total_ruts_detected: int
    low_severity_count: int
    medium_severity_count: int
    high_severity_count: int
    total_area_sqft: float

    class Config:
        from_attributes = True