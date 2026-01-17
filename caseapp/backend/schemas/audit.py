"""
Audit-related schemas for API requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from schemas.base import BaseEntity, BaseResponse, PaginatedResponse

class AuditLogBase(BaseModel):
    """Base audit log schema"""
    entity_type: str = Field(..., description="Type of entity (case, document, etc.)")
    entity_id: UUID = Field(..., description="ID of the entity")
    entity_name: Optional[str] = Field(None, description="Descriptive name for display")
    action: str = Field(..., description="Action performed")
    field_name: Optional[str] = Field(None, description="Specific field changed")
    old_value: Optional[str] = Field(None, description="Previous value")
    new_value: Optional[str] = Field(None, description="New value")
    user_id: UUID = Field(..., description="User who performed the action")
    ip_address: Optional[str] = Field(None, description="User's IP address")
    user_agent: Optional[str] = Field(None, description="User's browser/client")
    case_id: Optional[UUID] = Field(None, description="Associated case ID")

class AuditLogResponse(BaseModel):
    """Schema for audit log API responses"""
    id: UUID
    entity_type: str
    entity_id: UUID
    entity_name: Optional[str]
    action: str
    field_name: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    timestamp: datetime
    user_id: UUID
    ip_address: Optional[str]
    user_agent: Optional[str]
    case_id: Optional[UUID]
    
    class Config:
        from_attributes = True

class AuditTrailResponse(BaseResponse):
    """Schema for audit trail responses"""
    data: List[AuditLogResponse]

class AuditSearchRequest(BaseModel):
    """Schema for audit log search requests"""
    entity_type: Optional[str] = Field(None, description="Filter by entity type")
    action: Optional[str] = Field(None, description="Filter by action")
    user_id: Optional[UUID] = Field(None, description="Filter by user ID")
    case_id: Optional[UUID] = Field(None, description="Filter by case ID")
    start_date: Optional[datetime] = Field(None, description="Start date for filtering")
    end_date: Optional[datetime] = Field(None, description="End date for filtering")
    
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=200, description="Items per page")

class AuditSearchResponse(PaginatedResponse):
    """Schema for paginated audit search responses"""
    data: List[AuditLogResponse]

class AuditStatisticsResponse(BaseResponse):
    """Schema for audit statistics response"""
    data: Dict[str, Any]

class UserActivityRequest(BaseModel):
    """Schema for user activity requests"""
    user_id: UUID = Field(..., description="User ID to get activity for")
    start_date: Optional[datetime] = Field(None, description="Start date for filtering")
    end_date: Optional[datetime] = Field(None, description="End date for filtering")
    limit: int = Field(100, ge=1, le=500, description="Maximum number of entries")

class UserActivityResponse(BaseResponse):
    """Schema for user activity responses"""
    data: List[AuditLogResponse]

class SecurityEventRequest(BaseModel):
    """Schema for logging security events"""
    event_type: str = Field(..., description="Type of security event")
    description: str = Field(..., description="Description of the event")
    severity: str = Field("info", description="Event severity (info, warning, error, critical)")

class SecurityEventResponse(BaseResponse):
    """Schema for security event logging response"""
    data: AuditLogResponse