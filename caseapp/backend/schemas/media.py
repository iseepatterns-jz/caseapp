"""
Pydantic schemas for media evidence management
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID
from enum import Enum

from models.media import MediaType, MediaFormat, ProcessingStatus

class MediaTypeEnum(str, Enum):
    """Media type enumeration for API"""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT_SCAN = "document_scan"
    SCREENSHOT = "screenshot"
    SURVEILLANCE = "surveillance"
    BODY_CAM = "body_cam"
    DASH_CAM = "dash_cam"
    PHONE_RECORDING = "phone_recording"
    CCTV = "cctv"
    OTHER = "other"

class MediaFormatEnum(str, Enum):
    """Media format enumeration for API"""
    # Image formats
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    BMP = "bmp"
    GIF = "gif"
    WEBP = "webp"
    RAW = "raw"
    
    # Video formats
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    WMV = "wmv"
    FLV = "flv"
    MKV = "mkv"
    WEBM = "webm"
    
    # Audio formats
    MP3 = "mp3"
    WAV = "wav"
    FLAC = "flac"
    AAC = "aac"
    OGG = "ogg"
    WMA = "wma"
    
    # Document formats
    PDF = "pdf"
    
    # Other
    UNKNOWN = "unknown"

class ProcessingStatusEnum(str, Enum):
    """Processing status enumeration for API"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class MediaUploadRequest(BaseModel):
    """Schema for media upload requests"""
    case_id: UUID = Field(..., description="Case ID to associate media with")
    media_type: MediaTypeEnum = Field(..., description="Type of media being uploaded")
    evidence_number: Optional[str] = Field(None, description="Official evidence number")
    captured_at: Optional[datetime] = Field(None, description="When the media was captured")
    captured_by: Optional[str] = Field(None, description="Who captured the media")
    capture_location: Optional[str] = Field(None, description="Where the media was captured")
    capture_device: Optional[str] = Field(None, description="Device used to capture media")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for categorization")
    categories: Optional[List[str]] = Field(default_factory=list, description="Categories for organization")
    is_privileged: bool = Field(False, description="Whether media is privileged")
    privilege_reason: Optional[str] = Field(None, description="Reason for privilege if applicable")
    
    @validator('tags', 'categories')
    def validate_lists(cls, v):
        if v is None:
            return []
        return [item.strip() for item in v if item.strip()]
    
    @validator('privilege_reason')
    def validate_privilege_reason(cls, v, values):
        if values.get('is_privileged') and not v:
            raise ValueError('Privilege reason is required when media is marked as privileged')
        return v

class MediaUpdateRequest(BaseModel):
    """Schema for updating media evidence"""
    evidence_number: Optional[str] = Field(None, description="Official evidence number")
    captured_at: Optional[datetime] = Field(None, description="When the media was captured")
    captured_by: Optional[str] = Field(None, description="Who captured the media")
    capture_location: Optional[str] = Field(None, description="Where the media was captured")
    capture_device: Optional[str] = Field(None, description="Device used to capture media")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    categories: Optional[List[str]] = Field(None, description="Categories for organization")
    is_privileged: Optional[bool] = Field(None, description="Whether media is privileged")
    privilege_reason: Optional[str] = Field(None, description="Reason for privilege if applicable")
    is_redacted: Optional[bool] = Field(None, description="Whether media is redacted")
    redaction_reason: Optional[str] = Field(None, description="Reason for redaction if applicable")
    admissibility_status: Optional[str] = Field(None, description="Admissibility status")
    admissibility_notes: Optional[str] = Field(None, description="Notes on admissibility")
    authenticity_verified: Optional[bool] = Field(None, description="Whether authenticity is verified")
    authenticity_method: Optional[str] = Field(None, description="Method used to verify authenticity")
    
    @validator('tags', 'categories')
    def validate_lists(cls, v):
        if v is None:
            return None
        return [item.strip() for item in v if item.strip()]
    
    @validator('admissibility_status')
    def validate_admissibility_status(cls, v):
        if v and v not in ['admissible', 'inadmissible', 'pending']:
            raise ValueError('Admissibility status must be admissible, inadmissible, or pending')
        return v

class MediaSearchRequest(BaseModel):
    """Schema for media search requests"""
    case_id: Optional[UUID] = Field(None, description="Filter by case ID")
    media_types: Optional[List[MediaTypeEnum]] = Field(None, description="Filter by media types")
    formats: Optional[List[MediaFormatEnum]] = Field(None, description="Filter by media formats")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    categories: Optional[List[str]] = Field(None, description="Filter by categories")
    captured_after: Optional[datetime] = Field(None, description="Filter by capture date (after)")
    captured_before: Optional[datetime] = Field(None, description="Filter by capture date (before)")
    min_file_size: Optional[int] = Field(None, description="Minimum file size in bytes")
    max_file_size: Optional[int] = Field(None, description="Maximum file size in bytes")
    has_ai_analysis: Optional[bool] = Field(None, description="Filter by AI analysis completion")
    is_privileged: Optional[bool] = Field(None, description="Filter by privilege status")
    is_redacted: Optional[bool] = Field(None, description="Filter by redaction status")
    authenticity_verified: Optional[bool] = Field(None, description="Filter by authenticity verification")
    admissibility_status: Optional[str] = Field(None, description="Filter by admissibility status")
    search_text: Optional[str] = Field(None, description="Search in extracted text and descriptions")
    
    @validator('admissibility_status')
    def validate_admissibility_status(cls, v):
        if v and v not in ['admissible', 'inadmissible', 'pending']:
            raise ValueError('Admissibility status must be admissible, inadmissible, or pending')
        return v

class MediaAnnotationCreateRequest(BaseModel):
    """Schema for creating media annotations"""
    annotation_type: str = Field(..., description="Type of annotation (rectangle, circle, arrow, text, highlight)")
    annotation_data: Dict[str, Any] = Field(..., description="Annotation coordinates and properties")
    title: Optional[str] = Field(None, description="Annotation title")
    description: Optional[str] = Field(None, description="Annotation description")
    start_time: Optional[int] = Field(None, description="Start time for video/audio annotations (seconds)")
    end_time: Optional[int] = Field(None, description="End time for video/audio annotations (seconds)")
    color: Optional[str] = Field("#FF0000", description="Annotation color (hex)")
    opacity: Optional[int] = Field(80, description="Annotation opacity (0-100)")
    is_key_evidence: bool = Field(False, description="Whether this annotation marks key evidence")
    relevance_score: Optional[int] = Field(None, description="Relevance score (1-10)")
    
    @validator('annotation_type')
    def validate_annotation_type(cls, v):
        valid_types = ['rectangle', 'circle', 'arrow', 'text', 'highlight', 'polygon', 'line']
        if v not in valid_types:
            raise ValueError(f'Annotation type must be one of: {", ".join(valid_types)}')
        return v
    
    @validator('color')
    def validate_color(cls, v):
        if v and not v.startswith('#') or len(v) != 7:
            raise ValueError('Color must be a valid hex color (e.g., #FF0000)')
        return v
    
    @validator('opacity')
    def validate_opacity(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Opacity must be between 0 and 100')
        return v
    
    @validator('relevance_score')
    def validate_relevance_score(cls, v):
        if v is not None and (v < 1 or v > 10):
            raise ValueError('Relevance score must be between 1 and 10')
        return v
    
    @validator('end_time')
    def validate_time_range(cls, v, values):
        start_time = values.get('start_time')
        if start_time is not None and v is not None and v <= start_time:
            raise ValueError('End time must be greater than start time')
        return v

class MediaAnnotationUpdateRequest(BaseModel):
    """Schema for updating media annotations"""
    annotation_data: Optional[Dict[str, Any]] = Field(None, description="Annotation coordinates and properties")
    title: Optional[str] = Field(None, description="Annotation title")
    description: Optional[str] = Field(None, description="Annotation description")
    start_time: Optional[int] = Field(None, description="Start time for video/audio annotations (seconds)")
    end_time: Optional[int] = Field(None, description="End time for video/audio annotations (seconds)")
    color: Optional[str] = Field(None, description="Annotation color (hex)")
    opacity: Optional[int] = Field(None, description="Annotation opacity (0-100)")
    is_key_evidence: Optional[bool] = Field(None, description="Whether this annotation marks key evidence")
    relevance_score: Optional[int] = Field(None, description="Relevance score (1-10)")
    
    @validator('color')
    def validate_color(cls, v):
        if v and (not v.startswith('#') or len(v) != 7):
            raise ValueError('Color must be a valid hex color (e.g., #FF0000)')
        return v
    
    @validator('opacity')
    def validate_opacity(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Opacity must be between 0 and 100')
        return v
    
    @validator('relevance_score')
    def validate_relevance_score(cls, v):
        if v is not None and (v < 1 or v > 10):
            raise ValueError('Relevance score must be between 1 and 10')
        return v

class MediaAnnotationResponse(BaseModel):
    """Schema for media annotation responses"""
    id: UUID
    media_id: UUID
    annotation_type: str
    annotation_data: Dict[str, Any]
    title: Optional[str]
    description: Optional[str]
    start_time: Optional[int]
    end_time: Optional[int]
    color: Optional[str]
    opacity: Optional[int]
    is_key_evidence: bool
    relevance_score: Optional[int]
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: Optional[UUID]
    
    class Config:
        from_attributes = True

class MediaEvidenceResponse(BaseModel):
    """Schema for media evidence responses"""
    id: UUID
    case_id: UUID
    filename: str
    original_filename: str
    file_size: int
    file_size_mb: float
    file_hash: str
    mime_type: str
    media_type: MediaTypeEnum
    media_format: MediaFormatEnum
    
    # Technical metadata
    duration: Optional[int]
    duration_formatted: Optional[str]
    width: Optional[int]
    height: Optional[int]
    resolution: Optional[str]
    frame_rate: Optional[int]
    bit_rate: Optional[int]
    sample_rate: Optional[int]
    color_depth: Optional[int]
    
    # Capture information
    captured_at: Optional[datetime]
    captured_by: Optional[str]
    capture_location: Optional[str]
    capture_device: Optional[str]
    
    # Evidence metadata
    evidence_number: Optional[str]
    authenticity_verified: bool
    authenticity_method: Optional[str]
    
    # Content analysis
    ai_analysis_status: ProcessingStatusEnum
    has_ai_analysis: bool
    extracted_text: Optional[str]
    
    # Legal and administrative
    is_privileged: bool
    privilege_reason: Optional[str]
    is_redacted: bool
    redaction_reason: Optional[str]
    admissibility_status: Optional[str]
    admissibility_notes: Optional[str]
    
    # Tags and categorization
    tags: List[str]
    categories: List[str]
    
    # Thumbnails and previews
    thumbnail_path: Optional[str]
    preview_path: Optional[str]
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: Optional[UUID]
    
    # Annotations
    annotations: List[MediaAnnotationResponse] = []
    
    class Config:
        from_attributes = True

class MediaEvidenceSummaryResponse(BaseModel):
    """Schema for media evidence summary responses (for lists)"""
    id: UUID
    case_id: UUID
    filename: str
    file_size_mb: float
    media_type: MediaTypeEnum
    media_format: MediaFormatEnum
    duration_formatted: Optional[str]
    resolution: Optional[str]
    captured_at: Optional[datetime]
    evidence_number: Optional[str]
    ai_analysis_status: ProcessingStatusEnum
    is_privileged: bool
    is_redacted: bool
    admissibility_status: Optional[str]
    tags: List[str]
    thumbnail_path: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class MediaListResponse(BaseModel):
    """Schema for paginated media evidence list responses"""
    items: List[MediaEvidenceSummaryResponse]
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool

class MediaProcessingJobResponse(BaseModel):
    """Schema for media processing job responses"""
    id: UUID
    media_id: UUID
    job_type: str
    status: ProcessingStatusEnum
    priority: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    result_data: Optional[Dict[str, Any]]
    output_files: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class MediaAnalysisRequest(BaseModel):
    """Schema for requesting media analysis"""
    analysis_types: List[str] = Field(..., description="Types of analysis to perform")
    priority: int = Field(5, description="Processing priority (1-10)")
    
    @validator('analysis_types')
    def validate_analysis_types(cls, v):
        valid_types = ['thumbnail', 'ocr', 'object_detection', 'face_detection', 'transcription', 'content_moderation']
        for analysis_type in v:
            if analysis_type not in valid_types:
                raise ValueError(f'Invalid analysis type: {analysis_type}. Valid types: {", ".join(valid_types)}')
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        if v < 1 or v > 10:
            raise ValueError('Priority must be between 1 and 10')
        return v

class MediaStatisticsResponse(BaseModel):
    """Schema for media evidence statistics"""
    total_media: int
    total_size_mb: float
    media_by_type: Dict[str, int]
    media_by_format: Dict[str, int]
    processing_status_counts: Dict[str, int]
    privileged_count: int
    redacted_count: int
    verified_count: int
    with_annotations: int
    average_file_size_mb: float
    largest_file_mb: float
    oldest_capture: Optional[datetime]
    newest_capture: Optional[datetime]