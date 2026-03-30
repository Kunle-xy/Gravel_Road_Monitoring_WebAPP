from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid as uuid_lib
import re

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization: Optional[str] = None

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[^A-Za-z0-9]', v):
            raise ValueError('Password must contain at least one special character')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class EmailOnly(BaseModel):
    email: EmailStr

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
    user_id: Optional[str] = None

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

class VideoFileResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    folder_id: Optional[uuid_lib.UUID] = None
    filename: str
    original_size_bytes: int
    upload_status: str
    total_frames: Optional[int] = None
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True

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
    videos: List[VideoFileResponse] = []

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


# Presigned Upload Schemas
class PresignRequest(BaseModel):
    filename: str
    file_size: int
    file_type: str  # DEM, ORTHOPHOTO, HILLSHADE
    folder_id: Optional[uuid_lib.UUID] = None
    content_type: str = "image/tiff"

class PresignResponse(BaseModel):
    presigned_url: str
    s3_key: str
    upload_id: uuid_lib.UUID

class UploadCompleteRequest(BaseModel):
    upload_id: uuid_lib.UUID
    s3_key: str

class UploadCompleteResponse(BaseModel):
    job_id: str
    status: str


# Multipart Presigned Upload Schemas
class MultipartInitRequest(BaseModel):
    filename: str
    file_size: int
    file_type: str  # DEM, ORTHOPHOTO, HILLSHADE
    folder_id: Optional[uuid_lib.UUID] = None
    content_type: str = "image/tiff"

class MultipartInitResponse(BaseModel):
    upload_id: uuid_lib.UUID       # DB record ID
    s3_key: str
    s3_upload_id: str              # S3 multipart UploadId

class MultipartPresignPartRequest(BaseModel):
    s3_key: str
    s3_upload_id: str
    part_number: int = Field(..., ge=1, le=10000)

class MultipartPresignPartResponse(BaseModel):
    presigned_url: str
    part_number: int

class MultipartCompletePart(BaseModel):
    part_number: int = Field(..., ge=1, le=10000)
    etag: str

class MultipartCompleteRequest(BaseModel):
    upload_id: uuid_lib.UUID
    s3_key: str
    s3_upload_id: str
    parts: List[MultipartCompletePart]

class MultipartCompleteResponse(BaseModel):
    job_id: str
    status: str

class MultipartAbortRequest(BaseModel):
    s3_key: str
    s3_upload_id: str
    upload_id: uuid_lib.UUID


# Crown Analysis Schemas
class CrownAnalysisCreate(BaseModel):
    tiff_file_id: uuid_lib.UUID
    polygon_geojson: Dict[str, Any]
    spacing_m: Optional[float] = 0.2
    dy_freq: Optional[int] = 10
    apply_smoothing: Optional[bool] = False
    gaussian_sigma: Optional[float] = 1.0
    neighbor_eval: Optional[bool] = False
    neighbor_range: Optional[int] = 2
    screenshot_base64: Optional[str] = None

class CrownAnalysisResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    tiff_file_id: uuid_lib.UUID
    polygon_geojson: Dict[str, Any]
    spacing_m: float
    dy_freq: int
    apply_smoothing: bool
    gaussian_sigma: float
    neighbor_eval: bool
    neighbor_range: int
    status: str
    progress: int
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    results_json: Optional[Dict[str, Any]] = None
    html_report_url: Optional[str] = None
    low_severity_ft: float
    medium_severity_ft: float
    high_severity_ft: float
    total_linear_ft: float
    low_count: int
    medium_count: int
    high_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CrownAnalysisStatusResponse(BaseModel):
    id: uuid_lib.UUID
    status: str
    progress: int
    error_message: Optional[str] = None
    html_report_url: Optional[str] = None
    low_severity_ft: float
    medium_severity_ft: float
    high_severity_ft: float
    total_linear_ft: float
    low_count: int
    medium_count: int
    high_count: int

    class Config:
        from_attributes = True


# Corrugation Analysis Schemas
class CorrugationAnalysisCreate(BaseModel):
    tiff_file_id: uuid_lib.UUID
    polygon_geojson: Dict[str, Any]
    line_interval: Optional[float] = 0.1
    dy_freq: Optional[int] = 10
    sigma_samples: Optional[float] = 2.0
    neighbor_eval: Optional[bool] = False
    neighbor_range: Optional[int] = 2
    screenshot_base64: Optional[str] = None

class CorrugationAnalysisResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    tiff_file_id: uuid_lib.UUID
    polygon_geojson: Dict[str, Any]
    line_interval: float
    dy_freq: int
    sigma_samples: float
    neighbor_eval: bool
    neighbor_range: int
    status: str
    progress: int
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    results_json: Optional[Dict[str, Any]] = None
    html_report_url: Optional[str] = None
    low_area_ft2: float
    medium_area_ft2: float
    high_area_ft2: float
    total_area_ft2: float
    low_count: int
    medium_count: int
    high_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CorrugationAnalysisStatusResponse(BaseModel):
    id: uuid_lib.UUID
    status: str
    progress: int
    error_message: Optional[str] = None
    html_report_url: Optional[str] = None
    low_area_ft2: float
    medium_area_ft2: float
    high_area_ft2: float
    total_area_ft2: float
    low_count: int
    medium_count: int
    high_count: int

    class Config:
        from_attributes = True


# Pothole Analysis Schemas
class PotholeAnalysisCreate(BaseModel):
    tiff_file_id: uuid_lib.UUID
    polygon_geojson: Dict[str, Any]

class PotholeAnalysisResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    tiff_file_id: uuid_lib.UUID
    polygon_geojson: Dict[str, Any]
    status: str
    progress: int
    error_message: Optional[str] = None
    html_report_url: Optional[str] = None
    depth_inches: float
    width_inches: float
    width_feet: float
    severity: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PotholeAnalysisStatusResponse(BaseModel):
    id: uuid_lib.UUID
    status: str
    progress: int
    error_message: Optional[str] = None
    html_report_url: Optional[str] = None
    depth_inches: float
    width_inches: float
    width_feet: float
    severity: Optional[str] = None

    class Config:
        from_attributes = True


# Video Upload Schemas
class VideoPresignRequest(BaseModel):
    filename: str
    file_size: int
    folder_id: Optional[uuid_lib.UUID] = None
    content_type: str = "video/mp4"

class VideoPresignResponse(BaseModel):
    presigned_url: str
    s3_key: str
    video_id: uuid_lib.UUID

# Dust Analysis Schemas
class DustAnalysisCreate(BaseModel):
    video_file_id: uuid_lib.UUID
    polygon_points: List[List[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]

class DustAnalysisResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
    video_file_id: uuid_lib.UUID
    polygon_points: List[List[float]]
    status: str
    progress: int
    error_message: Optional[str] = None
    total_frames: int
    truck_frames: int
    no_truck_frames: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DustAnalysisStatusResponse(BaseModel):
    id: uuid_lib.UUID
    status: str
    progress: int
    error_message: Optional[str] = None
    total_frames: int
    truck_frames: int
    no_truck_frames: int

    class Config:
        from_attributes = True
