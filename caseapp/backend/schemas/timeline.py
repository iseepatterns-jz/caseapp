"""
Timeline schemas for API requests and responses
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class EventTypeEnum(str, Enum):
    """Event type enumeration for API"""
    INCIDENT = "incident"
    MEETING = "meeting"
    FILING = "filing"
    DISCOVERY = "discovery"
    DEPOSITION = "deposition"
    HEARING = "hearing"
    NEGOTIATION = "negotiation"
    CORRESPONDENCE = "correspondence"
    EVIDENCE_COLLECTION = "evidence_collection"
    WITNESS_INTERVIEW = "witness_interview"
    EXPERT_CONSULTATION = "expert_consultation"
    SETTLEMENT = "settlement"
    TRIAL = "trial"
    VERDICT = "verdict"
    APPEAL = "appeal"
    OTHER = "other"

class EvidenceTypeEnum(str, Enum):
    """Evidence type enumeration for pinning"""
    DOCUMENT = "document"
    MEDIA = "media"
    FORENSIC = "forensic"

# Request schemas
class TimelineEventCreateRequest(BaseModel):
    """Schema for creating timeline events"""
    case_id: UUID = Field(..., description="ID of the case this event belongs to")
    title: str = Field(..., min_length=1, max_length=255, description="Event title")
    description: Optional[str] = Field(None, description="Detailed event description")
    event_type: EventTypeEnum = Field(EventTypeEnum.OTHER, description="Type of event")
    event_date: datetime = Field(..., description="Date and time of the event")
    end_date: Optional[datetime] = Field(None, description="End date for events with duration")
    all_day: Optional[bool] = Field(False, description="Whether this is an all-day event")
    location: Optional[str] = Field(None, max_length=500, description="Event location")
    participants: Optional[List[str]] = Field(None, description="List of participants")
    importance_level: Optional[int] = Field(3, ge=1, le=5, description="Importance level (1-5)")
    is_milestone: Optional[bool] = Field(False, description="Mark as milestone event")
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="Hex color code")
    event_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional event metadata")

    @model_validator(mode='after')
    def validate_end_date(self) -> 'TimelineEventCreateRequest':
        if self.end_date and self.event_date and self.end_date < self.event_date:
            raise ValueError('End date must be after event date')
        return self

class TimelineEventUpdateRequest(BaseModel):
    """Schema for updating timeline events"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Event title")
    description: Optional[str] = Field(None, description="Detailed event description")
    event_type: Optional[EventTypeEnum] = Field(None, description="Type of event")
    event_date: Optional[datetime] = Field(None, description="Date and time of the event")
    end_date: Optional[datetime] = Field(None, description="End date for events with duration")
    all_day: Optional[bool] = Field(None, description="Whether this is an all-day event")
    location: Optional[str] = Field(None, max_length=500, description="Event location")
    participants: Optional[List[str]] = Field(None, description="List of participants")
    importance_level: Optional[int] = Field(None, ge=1, le=5, description="Importance level (1-5)")
    is_milestone: Optional[bool] = Field(None, description="Mark as milestone event")
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="Hex color code")
    event_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional event metadata")

class EvidencePinCreateRequest(BaseModel):
    """Schema for pinning evidence to timeline events"""
    timeline_event_id: UUID = Field(..., description="ID of the timeline event")
    evidence_type: EvidenceTypeEnum = Field(..., description="Type of evidence")
    evidence_id: UUID = Field(..., description="ID of the evidence item")
    relevance_score: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Relevance score (0.0-1.0)")
    pin_description: Optional[str] = Field(None, description="Why this evidence is relevant")
    pin_notes: Optional[str] = Field(None, description="Additional notes")
    is_primary: Optional[bool] = Field(False, description="Mark as primary evidence")

class EvidencePinUpdateRequest(BaseModel):
    """Schema for updating evidence pins"""
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevance score (0.0-1.0)")
    pin_description: Optional[str] = Field(None, description="Why this evidence is relevant")
    pin_notes: Optional[str] = Field(None, description="Additional notes")
    is_primary: Optional[bool] = Field(None, description="Mark as primary evidence")

class TimelineCommentCreateRequest(BaseModel):
    """Schema for creating timeline comments"""
    timeline_event_id: UUID = Field(..., description="ID of the timeline event")
    comment_text: str = Field(..., min_length=1, description="Comment text")
    is_internal: Optional[bool] = Field(True, description="Internal team comment")
    parent_comment_id: Optional[UUID] = Field(None, description="Parent comment for threading")

class TimelineCommentUpdateRequest(BaseModel):
    """Schema for updating timeline comments"""
    comment_text: str = Field(..., min_length=1, description="Comment text")
    is_internal: Optional[bool] = Field(None, description="Internal team comment")

class TimelineEventSuggestion(BaseModel):
    """Schema for AI-generated timeline event suggestions"""
    title: str = Field(..., description="Suggested event title")
    description: str = Field(..., description="Suggested event description")
    event_type: EventTypeEnum = Field(EventTypeEnum.OTHER, description="Suggested event type")
    suggested_date: Optional[datetime] = Field(None, description="Suggested event date")
    location: Optional[str] = Field(None, description="Suggested location")
    participants: List[str] = Field(default_factory=list, description="Suggested participants")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="AI confidence score")
    reasoning: str = Field(..., description="AI reasoning for the suggestion")
    source_reference: Optional[str] = Field(None, description="Reference to source text")
    source_document_id: Optional[UUID] = Field(None, description="Source document ID if applicable")

class EventSuggestionRequest(BaseModel):
    """Schema for requesting event suggestions"""
    document_id: Optional[UUID] = Field(None, description="Document ID to analyze")
    text_content: Optional[str] = Field(None, description="Text content to analyze")
    case_context: Optional[str] = Field(None, description="Additional case context")

class EventEnhancementRequest(BaseModel):
    """Schema for requesting event description enhancement"""
    event_title: str = Field(..., description="Current event title")
    event_description: str = Field(..., description="Current event description")
    event_type: EventTypeEnum = Field(..., description="Event type")
    case_context: Optional[str] = Field(None, description="Additional case context")

class EventEnhancementResponse(BaseModel):
    """Schema for event enhancement response"""
    enhanced_title: str = Field(..., description="Enhanced event title")
    enhanced_description: str = Field(..., description="Enhanced event description")
    improvements_made: List[str] = Field(default_factory=list, description="List of improvements made")

# Response schemas
class EvidencePinResponse(BaseModel):
    """Schema for evidence pin responses"""
    id: UUID
    timeline_event_id: UUID
    evidence_type: str
    evidence_id: UUID
    relevance_score: float
    pin_description: Optional[str]
    pin_notes: Optional[str]
    display_order: int
    is_primary: bool
    created_at: datetime
    created_by: UUID

    class Config:
        from_attributes = True

class TimelineCommentResponse(BaseModel):
    """Schema for timeline comment responses"""
    id: UUID
    timeline_event_id: UUID
    comment_text: str
    is_internal: bool
    parent_comment_id: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: UUID
    updated_by: Optional[UUID]

    class Config:
        from_attributes = True

class TimelineEventResponse(BaseModel):
    """Schema for timeline event responses"""
    id: UUID
    case_id: UUID
    title: str
    description: Optional[str]
    event_type: str
    event_date: datetime
    end_date: Optional[datetime]
    all_day: bool
    location: Optional[str]
    participants: Optional[List[str]]
    importance_level: int
    is_milestone: bool
    display_order: Optional[int]
    color: Optional[str]
    event_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: UUID
    updated_by: Optional[UUID]
    
    # Related data
    evidence_pins: List[EvidencePinResponse] = Field(default_factory=list)
    comments: List[TimelineCommentResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True

class TimelineEventSummaryResponse(BaseModel):
    """Schema for timeline event summary (minimal information)"""
    id: UUID
    case_id: UUID
    title: str
    event_type: str
    event_date: datetime
    end_date: Optional[datetime]
    all_day: bool
    location: Optional[str]
    importance_level: int
    is_milestone: bool
    evidence_count: int = 0
    comment_count: int = 0

    class Config:
        from_attributes = True

class TimelineListResponse(BaseModel):
    """Schema for paginated timeline list responses"""
    events: List[TimelineEventResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool

class TimelineExportRequest(BaseModel):
    """Schema for timeline export requests"""
    case_id: UUID = Field(..., description="Case ID to export timeline for")
    format: str = Field(..., pattern=r'^(pdf|png|json)$', description="Export format")
    start_date: Optional[datetime] = Field(None, description="Filter events from this date")
    end_date: Optional[datetime] = Field(None, description="Filter events until this date")
    event_types: Optional[List[EventTypeEnum]] = Field(None, description="Filter by event types")
    include_evidence: Optional[bool] = Field(True, description="Include evidence attachments")
    include_comments: Optional[bool] = Field(False, description="Include comments")
    title: Optional[str] = Field(None, description="Custom title for export")

class TimelineExportResponse(BaseModel):
    """Schema for timeline export responses"""
    export_id: UUID
    format: str
    status: str
    download_url: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    file_size: Optional[int]
    error_message: Optional[str]

class TimelineTemplateResponse(BaseModel):
    """Schema for timeline template responses"""
    id: UUID
    name: str
    description: Optional[str]
    case_type: Optional[str]
    template_events: List[Dict[str, Any]]
    is_public: bool
    usage_count: int
    created_at: datetime
    created_by: UUID

    class Config:
        from_attributes = True

class TimelineStatsResponse(BaseModel):
    """Schema for timeline statistics"""
    case_id: UUID
    total_events: int
    events_by_type: Dict[str, int]
    events_by_month: Dict[str, int]
    milestone_count: int
    evidence_pins_count: int
    comments_count: int
    date_range: Dict[str, Optional[datetime]]
    generated_at: datetime