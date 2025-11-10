from pydantic import BaseModel, EmailStr
from typing import Optional, List
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

class TiffFileResponse(BaseModel):
    id: uuid_lib.UUID
    user_id: uuid_lib.UUID
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
    created_at: datetime

    class Config:
        from_attributes = True

class TiffFileListResponse(BaseModel):
    total: int
    files: List[TiffFileResponse]