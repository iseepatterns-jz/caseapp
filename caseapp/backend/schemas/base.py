"""
Base schemas and response models
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from uuid import UUID

class BaseResponse(BaseModel):
    """Base API response model"""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorResponse(BaseResponse):
    """Error response model"""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class PaginatedResponse(BaseResponse):
    """Paginated response model"""
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

class AuditInfo(BaseModel):
    """Audit information for entities"""
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: UUID
    updated_by: Optional[UUID] = None

class BaseEntity(BaseModel):
    """Base entity model with audit fields"""
    id: UUID
    audit: AuditInfo
    
    class Config:
        from_attributes = True

class HealthCheck(BaseModel):
    """Health check response"""
    status: str = "healthy"
    database: str = "connected"
    aws_services: str = "initialized"
    redis: str = "connected"
    timestamp: datetime = Field(default_factory=datetime.utcnow)