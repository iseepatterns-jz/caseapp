"""
Pydantic schemas for integration API endpoints
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum

class IntegrationStatus(str, Enum):
    """Integration status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"

class SyncStatus(str, Enum):
    """Synchronization status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WebhookEvent(str, Enum):
    """Webhook event types"""
    CASE_CREATED = "case.created"
    CASE_UPDATED = "case.updated"
    CASE_CLOSED = "case.closed"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_ANALYZED = "document.analyzed"
    TIMELINE_EVENT_CREATED = "timeline.event.created"
    MEDIA_UPLOADED = "media.uploaded"
    FORENSIC_ANALYSIS_COMPLETED = "forensic.analysis.completed"

# Base Integration Response Models

class IntegrationResponse(BaseModel):
    """Base integration response model"""
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class IntegrationHealthResponse(BaseModel):
    """Integration API health status response"""
    status: IntegrationStatus
    version: str = "1.0.0"
    timestamp: datetime
    services: Dict[str, str] = Field(description="Status of dependent services")
    uptime_seconds: int = Field(description="API uptime in seconds")
    
    class Config:
        from_attributes = True

class IntegrationStatsResponse(BaseModel):
    """Integration usage statistics response"""
    period_days: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time_ms: float
    top_endpoints: List[Dict[str, Union[str, int]]]
    error_rate_percent: float
    
    class Config:
        from_attributes = True

# Case Integration Models

class CaseIntegrationResponse(IntegrationResponse):
    """Case data for external integration"""
    case_number: str
    title: str
    description: Optional[str] = None
    case_type: str
    status: str
    client_id: Optional[str] = None
    assigned_attorney: Optional[str] = None
    priority: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Optional related data
    documents: Optional[List[Dict[str, Any]]] = None
    timeline_events: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        from_attributes = True

class CaseCreateRequest(BaseModel):
    """Request model for creating case via integration"""
    case_number: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    case_type: str = Field(..., description="Case type from predefined list")
    client_id: Optional[str] = None
    assigned_attorney: Optional[str] = None
    priority: Optional[str] = Field("medium", description="Priority level")
    metadata: Optional[Dict[str, Any]] = None
    external_id: Optional[str] = Field(None, description="External system identifier")
    
    @field_validator('case_type')
    def validate_case_type(cls, v):
        allowed_types = [
            'civil', 'criminal', 'family', 'corporate', 'immigration',
            'personal_injury', 'real_estate', 'bankruptcy', 'intellectual_property'
        ]
        if v not in allowed_types:
            raise ValueError(f'Case type must be one of: {", ".join(allowed_types)}')
        return v
    
    @field_validator('priority')
    def validate_priority(cls, v):
        if v and v not in ['low', 'medium', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, medium, high, urgent')
        return v

class CaseUpdateRequest(BaseModel):
    """Request model for updating case via integration"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    status: Optional[str] = None
    assigned_attorney: Optional[str] = None
    priority: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('status')
    def validate_status(cls, v):
        if v and v not in ['active', 'closed', 'on_hold', 'archived']:
            raise ValueError('Status must be one of: active, closed, on_hold, archived')
        return v

# Document Integration Models

class DocumentIntegrationResponse(IntegrationResponse):
    """Document data for external integration"""
    filename: str
    file_size: int
    file_type: str
    case_id: str
    document_type: Optional[str] = None
    s3_key: Optional[str] = None
    analysis_status: Optional[str] = None
    extracted_text: Optional[str] = None
    entities: Optional[List[Dict[str, Any]]] = None
    summary: Optional[str] = None
    
    class Config:
        from_attributes = True

class DocumentUploadRequest(BaseModel):
    """Request model for document upload via integration"""
    filename: str = Field(..., min_length=1)
    file_content_base64: str = Field(..., description="Base64 encoded file content")
    document_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('file_content_base64')
    def validate_base64_content(cls, v):
        import base64
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError('Invalid base64 encoded content')
        return v

# Timeline Integration Models

class TimelineIntegrationResponse(IntegrationResponse):
    """Timeline event data for external integration"""
    case_id: str
    title: str
    description: Optional[str] = None
    event_type: str
    event_date: datetime
    location: Optional[str] = None
    participants: Optional[List[str]] = None
    evidence_pins: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class TimelineEventRequest(BaseModel):
    """Request model for creating timeline event via integration"""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    event_type: str = Field(..., description="Event type")
    event_date: datetime
    location: Optional[str] = Field(None, max_length=500)
    participants: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    external_id: Optional[str] = Field(None, description="External system identifier")

# Media Integration Models

class MediaIntegrationResponse(IntegrationResponse):
    """Media evidence data for external integration"""
    case_id: str
    filename: str
    file_size: int
    media_type: str
    duration_seconds: Optional[float] = None
    resolution: Optional[str] = None
    s3_key: Optional[str] = None
    thumbnail_s3_key: Optional[str] = None
    transcription: Optional[str] = None
    chain_of_custody: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        from_attributes = True

# Forensic Integration Models

class ForensicIntegrationResponse(IntegrationResponse):
    """Forensic analysis data for external integration"""
    case_id: str
    source_type: str
    source_description: str
    analysis_status: str
    message_count: Optional[int] = None
    participant_count: Optional[int] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    network_analysis: Optional[Dict[str, Any]] = None
    sentiment_analysis: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

# Webhook Configuration Models

class WebhookConfigResponse(IntegrationResponse):
    """Webhook configuration response"""
    name: str
    url: str
    events: List[WebhookEvent]
    active: bool = True
    secret: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    retry_count: int = 3
    timeout_seconds: int = 30
    
    class Config:
        from_attributes = True

class WebhookConfigRequest(BaseModel):
    """Request model for webhook configuration"""
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., description="Webhook endpoint URL")
    events: List[WebhookEvent] = Field(..., min_items=1)
    active: bool = True
    secret: Optional[str] = Field(None, description="Webhook secret for signature verification")
    headers: Optional[Dict[str, str]] = None
    retry_count: int = Field(3, ge=0, le=10)
    timeout_seconds: int = Field(30, ge=5, le=300)
    
    @field_validator('url')
    def validate_url(cls, v):
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if not url_pattern.match(v):
            raise ValueError('Invalid URL format')
        return v

# Synchronization Models

class SyncOperationResponse(BaseModel):
    """Synchronization operation response"""
    sync_id: str
    operation_type: str
    status: SyncStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_items: Optional[int] = None
    processed_items: Optional[int] = None
    failed_items: Optional[int] = None
    error_message: Optional[str] = None
    progress_percent: Optional[float] = None
    
    class Config:
        from_attributes = True

# Batch Operation Models

class BatchOperationRequest(BaseModel):
    """Base batch operation request"""
    operation_id: Optional[str] = None
    batch_size: int = Field(50, ge=1, le=100)
    
class BatchCaseCreateRequest(BatchOperationRequest):
    """Batch case creation request"""
    cases: List[CaseCreateRequest] = Field(..., min_items=1, max_items=100)

class BatchOperationResponse(BaseModel):
    """Batch operation response"""
    operation_id: str
    total_items: int
    successful_items: int
    failed_items: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    created_items: List[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True

# API Key Management Models

class APIKeyResponse(BaseModel):
    """API key response model"""
    key_id: str
    name: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    permissions: List[str]
    active: bool = True
    
    class Config:
        from_attributes = True

class APIKeyCreateRequest(BaseModel):
    """API key creation request"""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: List[str] = Field(..., min_items=1)
    expires_days: Optional[int] = Field(None, ge=1, le=365)
    
    @field_validator('permissions')
    def validate_permissions(cls, v):
        allowed_permissions = [
            'cases:read', 'cases:write', 'cases:delete',
            'documents:read', 'documents:write', 'documents:delete',
            'timeline:read', 'timeline:write', 'timeline:delete',
            'media:read', 'media:write', 'media:delete',
            'forensic:read', 'forensic:write',
            'webhooks:manage', 'admin:all'
        ]
        for permission in v:
            if permission not in allowed_permissions:
                raise ValueError(f'Invalid permission: {permission}')
        return v