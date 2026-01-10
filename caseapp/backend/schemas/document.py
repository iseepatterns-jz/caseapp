"""
Document schemas for API requests and responses
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class DocumentTypeEnum(str, Enum):
    """Document type enumeration for API"""
    LEGAL_BRIEF = "legal_brief"
    CONTRACT = "contract"
    EVIDENCE = "evidence"
    CORRESPONDENCE = "correspondence"
    COURT_FILING = "court_filing"
    DISCOVERY = "discovery"
    DEPOSITION = "deposition"
    EXPERT_REPORT = "expert_report"
    OTHER = "other"

class DocumentStatusEnum(str, Enum):
    """Document status enumeration for API"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"

class AccessLevelEnum(str, Enum):
    """Document access level enumeration"""
    PUBLIC = "public"
    STANDARD = "standard"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

# Request schemas
class DocumentUploadRequest(BaseModel):
    """Schema for document upload metadata"""
    case_id: UUID = Field(..., description="ID of the case this document belongs to")
    document_type: Optional[DocumentTypeEnum] = Field(DocumentTypeEnum.OTHER, description="Type of document")
    is_privileged: Optional[bool] = Field(False, description="Whether document is attorney-client privileged")
    is_confidential: Optional[bool] = Field(False, description="Whether document contains confidential information")
    access_level: Optional[AccessLevelEnum] = Field(AccessLevelEnum.STANDARD, description="Access control level")
    retention_date: Optional[datetime] = Field(None, description="Date when document can be deleted")
    document_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional document metadata")

class DocumentUpdateRequest(BaseModel):
    """Schema for updating document metadata"""
    document_type: Optional[DocumentTypeEnum] = Field(None, description="Type of document")
    is_privileged: Optional[bool] = Field(None, description="Whether document is attorney-client privileged")
    is_confidential: Optional[bool] = Field(None, description="Whether document contains confidential information")
    access_level: Optional[AccessLevelEnum] = Field(None, description="Access control level")
    retention_date: Optional[datetime] = Field(None, description="Date when document can be deleted")
    document_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional document metadata")

class DocumentSearchRequest(BaseModel):
    """Schema for document search requests"""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    case_id: Optional[UUID] = Field(None, description="Filter by case ID")
    document_type: Optional[DocumentTypeEnum] = Field(None, description="Filter by document type")
    status: Optional[DocumentStatusEnum] = Field(None, description="Filter by processing status")
    start_date: Optional[datetime] = Field(None, description="Filter documents uploaded after this date")
    end_date: Optional[datetime] = Field(None, description="Filter documents uploaded before this date")
    include_content: Optional[bool] = Field(True, description="Whether to search document content")
    include_metadata: Optional[bool] = Field(True, description="Whether to search document metadata")
    limit: Optional[int] = Field(20, ge=1, le=100, description="Maximum number of results")
    offset: Optional[int] = Field(0, ge=0, description="Number of results to skip")

# Response schemas
class ExtractedEntityResponse(BaseModel):
    """Schema for extracted entity information"""
    id: UUID
    entity_type: str
    entity_text: str
    confidence_score: Optional[int]
    start_offset: Optional[int]
    end_offset: Optional[int]
    page_number: Optional[int]
    entity_metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

class DocumentVersionResponse(BaseModel):
    """Schema for document version information"""
    id: UUID
    version_number: int
    change_description: Optional[str]
    change_type: Optional[str]
    created_at: datetime
    created_by: UUID

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    """Schema for document API responses"""
    id: UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    document_type: str
    status: str
    version: int
    is_current_version: bool
    case_id: UUID
    
    # AI analysis results
    extracted_text: Optional[str]
    ai_summary: Optional[str]
    entities: Optional[List[ExtractedEntityResponse]]
    keywords: Optional[List[str]]
    confidence_scores: Optional[Dict[str, Any]]
    
    # Processing information
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    processing_error: Optional[str]
    
    # Metadata
    upload_date: datetime
    uploaded_by: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    updated_by: Optional[UUID]
    
    # Legal compliance
    retention_date: Optional[datetime]
    is_privileged: bool
    is_confidential: bool
    access_level: str
    document_metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    """Schema for paginated document list responses"""
    documents: List[DocumentResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool

class DocumentSummaryResponse(BaseModel):
    """Schema for document summary (minimal information)"""
    id: UUID
    filename: str
    file_size: int
    mime_type: str
    document_type: str
    status: str
    upload_date: datetime
    uploaded_by: UUID
    case_id: UUID
    is_privileged: bool
    is_confidential: bool

    class Config:
        from_attributes = True

class DocumentAnalysisResponse(BaseModel):
    """Schema for document analysis results"""
    document_id: UUID
    status: str
    extracted_text: Optional[str] = None
    ai_summary: Optional[str] = None
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    key_phrases: List[Dict[str, Any]] = Field(default_factory=list)
    sentiment: Optional[Dict[str, Any]] = None
    confidence_scores: Optional[Dict[str, Any]] = None
    processing_time_seconds: Optional[float] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None

class FileUploadResponse(BaseModel):
    """Schema for file upload response"""
    document_id: UUID
    filename: str
    file_size: int
    mime_type: str
    status: str
    message: str
    upload_url: Optional[str]  # Pre-signed URL for direct S3 upload if applicable

class DocumentSearchResponse(BaseModel):
    """Schema for document search results"""
    documents: List[DocumentSummaryResponse]
    total_count: int
    query: str
    search_time_ms: int
    facets: Optional[Dict[str, Any]]  # Search facets for filtering

# Validation schemas
class SupportedFileFormats:
    """Supported file formats and their MIME types"""
    FORMATS = {
        'pdf': ['application/pdf'],
        'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        'doc': ['application/msword'],
        'txt': ['text/plain'],
        'rtf': ['application/rtf', 'text/rtf'],
        'odt': ['application/vnd.oasis.opendocument.text']
    }
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes
    
    @classmethod
    def is_supported_format(cls, mime_type: str) -> bool:
        """Check if MIME type is supported"""
        for format_mimes in cls.FORMATS.values():
            if mime_type in format_mimes:
                return True
        return False
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get list of supported file extensions"""
        return list(cls.FORMATS.keys())
    
    @classmethod
    def get_supported_mime_types(cls) -> List[str]:
        """Get list of supported MIME types"""
        mime_types = []
        for format_mimes in cls.FORMATS.values():
            mime_types.extend(format_mimes)
        return mime_types