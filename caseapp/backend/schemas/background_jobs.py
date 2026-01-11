"""
Background Jobs and Webhooks API schemas
Request and response models for background job processing and webhook management
Validates Requirements 10.4, 10.6
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

from services.background_job_service import JobPriority, JobStatus, JobResult
from services.webhook_service import WebhookEvent, WebhookStatus

class JobSubmissionRequest(BaseModel):
    """Request model for job submission"""
    task_name: str = Field(..., description="Name of the task to execute")
    args: List[Any] = Field(default=[], description="Positional arguments for the task")
    kwargs: Dict[str, Any] = Field(default={}, description="Keyword arguments for the task")
    priority: JobPriority = Field(default=JobPriority.NORMAL, description="Job priority level")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=60, ge=1, le=3600, description="Delay between retries in seconds")
    timeout_seconds: int = Field(default=300, ge=10, le=7200, description="Job timeout in seconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional job metadata")
    
    @validator('task_name')
    def validate_task_name(cls, v):
        allowed_tasks = [
            "document_analysis", "media_processing", "forensic_analysis",
            "export_generation", "webhook_delivery", "email_notification",
            "data_cleanup", "backup_creation"
        ]
        if v not in allowed_tasks:
            raise ValueError(f"Task name must be one of: {', '.join(allowed_tasks)}")
        return v

class JobSubmissionResponse(BaseModel):
    """Response model for job submission"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Submission status")
    message: str = Field(..., description="Submission message")

class JobResultResponse(BaseModel):
    """Response model for job result"""
    success: bool = Field(..., description="Whether the job succeeded")
    result: Optional[Any] = Field(None, description="Job result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time_seconds: Optional[float] = Field(None, description="Job execution time")
    retry_count: int = Field(..., description="Number of retry attempts")

class JobStatusResponse(BaseModel):
    """Response model for job status"""
    job_id: str = Field(..., description="Unique job identifier")
    task_name: str = Field(..., description="Task name")
    status: JobStatus = Field(..., description="Current job status")
    priority: JobPriority = Field(..., description="Job priority")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    result: Optional[JobResultResponse] = Field(None, description="Job result")
    max_retries: int = Field(..., description="Maximum retry attempts")
    metadata: Dict[str, Any] = Field(..., description="Job metadata")

class JobStatisticsResponse(BaseModel):
    """Response model for job statistics"""
    period_hours: int = Field(..., description="Statistics period in hours")
    total_jobs: int = Field(..., description="Total number of jobs")
    success_rate_percent: float = Field(..., description="Success rate percentage")
    status_breakdown: Dict[str, int] = Field(..., description="Breakdown by job status")
    task_breakdown: Dict[str, int] = Field(..., description="Breakdown by task type")
    priority_breakdown: Dict[str, int] = Field(..., description="Breakdown by priority")
    average_execution_time_seconds: float = Field(..., description="Average execution time")
    queue_length: int = Field(..., description="Current queue length")
    running_jobs: int = Field(..., description="Number of currently running jobs")

class WebhookEndpointRequest(BaseModel):
    """Request model for webhook endpoint creation/update"""
    name: str = Field(..., min_length=1, max_length=100, description="Endpoint name")
    url: str = Field(..., description="Webhook URL")
    events: List[WebhookEvent] = Field(..., min_items=1, description="List of events to subscribe to")
    secret: Optional[str] = Field(None, description="Secret for signature verification")
    active: bool = Field(default=True, description="Whether the endpoint is active")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=60, ge=1, le=3600, description="Delay between retries")
    timeout_seconds: int = Field(default=30, ge=5, le=300, description="Request timeout")
    headers: Dict[str, str] = Field(default={}, description="Additional headers to send")
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v
    
    @validator('events')
    def validate_events(cls, v):
        if not v:
            raise ValueError("At least one event must be specified")
        return v

class WebhookEndpointResponse(BaseModel):
    """Response model for webhook endpoint"""
    id: str = Field(..., description="Unique endpoint identifier")
    name: str = Field(..., description="Endpoint name")
    url: str = Field(..., description="Webhook URL")
    events: List[WebhookEvent] = Field(..., description="Subscribed events")
    active: bool = Field(..., description="Whether the endpoint is active")
    max_retries: int = Field(..., description="Maximum retry attempts")
    retry_delay_seconds: int = Field(..., description="Delay between retries")
    timeout_seconds: int = Field(..., description="Request timeout")
    headers: Dict[str, str] = Field(..., description="Additional headers")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

class WebhookDeliveryResponse(BaseModel):
    """Response model for webhook delivery"""
    id: str = Field(..., description="Unique delivery identifier")
    endpoint_id: str = Field(..., description="Target endpoint identifier")
    event_type: WebhookEvent = Field(..., description="Event type")
    status: WebhookStatus = Field(..., description="Delivery status")
    created_at: datetime = Field(..., description="Creation timestamp")
    delivered_at: Optional[datetime] = Field(None, description="Delivery timestamp")
    response_code: Optional[int] = Field(None, description="HTTP response code")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(..., description="Number of retry attempts")

class WebhookTestResponse(BaseModel):
    """Response model for webhook endpoint testing"""
    success: bool = Field(..., description="Whether the test succeeded")
    delivery_id: Optional[str] = Field(None, description="Test delivery identifier")
    response_code: Optional[int] = Field(None, description="HTTP response code")
    response_body: Optional[str] = Field(None, description="Response body")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    delivered_at: Optional[str] = Field(None, description="Delivery timestamp")

class WebhookStatisticsResponse(BaseModel):
    """Response model for webhook statistics"""
    period_hours: int = Field(..., description="Statistics period in hours")
    total_deliveries: int = Field(..., description="Total number of deliveries")
    success_rate_percent: float = Field(..., description="Success rate percentage")
    status_breakdown: Dict[str, int] = Field(..., description="Breakdown by delivery status")
    event_breakdown: Dict[str, int] = Field(..., description="Breakdown by event type")
    endpoint_breakdown: Dict[str, int] = Field(..., description="Breakdown by endpoint")
    average_retries: float = Field(..., description="Average number of retries")
    total_endpoints: int = Field(..., description="Total number of endpoints")
    active_endpoints: int = Field(..., description="Number of active endpoints")

class WebhookPayload(BaseModel):
    """Base webhook payload structure"""
    id: str = Field(..., description="Unique event identifier")
    event: str = Field(..., description="Event type")
    timestamp: str = Field(..., description="Event timestamp")
    data: Dict[str, Any] = Field(..., description="Event data")

class CaseWebhookPayload(WebhookPayload):
    """Webhook payload for case events"""
    data: Dict[str, Any] = Field(..., description="Case event data")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "evt_123456789",
                "event": "case.created",
                "timestamp": "2024-01-15T10:30:00Z",
                "data": {
                    "case_id": "case_123",
                    "case_number": "CASE-2024-001",
                    "title": "Smith vs. Jones",
                    "case_type": "civil",
                    "status": "active",
                    "created_by": "attorney_1",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            }
        }

class DocumentWebhookPayload(WebhookPayload):
    """Webhook payload for document events"""
    data: Dict[str, Any] = Field(..., description="Document event data")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "evt_123456789",
                "event": "document.uploaded",
                "timestamp": "2024-01-15T10:30:00Z",
                "data": {
                    "document_id": "doc_123",
                    "case_id": "case_123",
                    "filename": "contract.pdf",
                    "file_type": "pdf",
                    "file_size": 2048576,
                    "uploaded_by": "attorney_1",
                    "uploaded_at": "2024-01-15T10:30:00Z"
                }
            }
        }

class TimelineWebhookPayload(WebhookPayload):
    """Webhook payload for timeline events"""
    data: Dict[str, Any] = Field(..., description="Timeline event data")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "evt_123456789",
                "event": "timeline.event.created",
                "timestamp": "2024-01-15T10:30:00Z",
                "data": {
                    "event_id": "timeline_evt_123",
                    "case_id": "case_123",
                    "title": "Contract Signing",
                    "event_type": "meeting",
                    "event_date": "2024-01-10T14:00:00Z",
                    "location": "Law Office",
                    "participants": ["John Smith", "Jane Jones"],
                    "created_by": "attorney_1",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            }
        }

class MediaWebhookPayload(WebhookPayload):
    """Webhook payload for media events"""
    data: Dict[str, Any] = Field(..., description="Media event data")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "evt_123456789",
                "event": "media.processed",
                "timestamp": "2024-01-15T10:30:00Z",
                "data": {
                    "media_id": "media_123",
                    "case_id": "case_123",
                    "filename": "deposition.mp4",
                    "media_type": "video",
                    "processing_status": "completed",
                    "thumbnail_url": "/api/v1/media/media_123/thumbnail",
                    "transcription_available": True,
                    "processed_at": "2024-01-15T10:30:00Z"
                }
            }
        }

class ExportWebhookPayload(WebhookPayload):
    """Webhook payload for export events"""
    data: Dict[str, Any] = Field(..., description="Export event data")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "evt_123456789",
                "event": "export.generated",
                "timestamp": "2024-01-15T10:30:00Z",
                "data": {
                    "export_id": "export_123",
                    "case_id": "case_123",
                    "export_type": "timeline_report",
                    "format": "pdf",
                    "file_size": 5242880,
                    "download_url": "/api/v1/exports/export_123/download",
                    "expires_at": "2024-01-22T10:30:00Z",
                    "generated_by": "attorney_1",
                    "generated_at": "2024-01-15T10:30:00Z"
                }
            }
        }

class WebhookEventTypes(BaseModel):
    """Available webhook event types"""
    events: List[Dict[str, str]] = Field(..., description="List of available events")
    
    class Config:
        schema_extra = {
            "example": {
                "events": [
                    {"type": "case.created", "description": "New case created"},
                    {"type": "case.updated", "description": "Case information updated"},
                    {"type": "case.closed", "description": "Case closed"},
                    {"type": "document.uploaded", "description": "Document uploaded to case"},
                    {"type": "document.analyzed", "description": "Document AI analysis completed"},
                    {"type": "timeline.event.created", "description": "Timeline event created"},
                    {"type": "timeline.event.updated", "description": "Timeline event updated"},
                    {"type": "media.processed", "description": "Media file processing completed"},
                    {"type": "forensic.analysis.completed", "description": "Forensic analysis completed"},
                    {"type": "export.generated", "description": "Case export generated"},
                    {"type": "collaboration.invited", "description": "User invited to collaborate"},
                    {"type": "ai.insight.generated", "description": "AI insight generated for case"}
                ]
            }
        }