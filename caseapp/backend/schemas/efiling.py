"""
E-Filing API schemas
Request and response models for court e-filing integration
Validates Requirements 10.3
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from ..services.efiling_service import CourtSystem, FilingStatus

class FilingSubmissionRequest(BaseModel):
    """Request model for filing submission"""
    case_id: str = Field(..., description="Internal case identifier")
    court_system: CourtSystem = Field(..., description="Target court system")
    document_ids: List[str] = Field(..., min_items=1, description="List of document IDs to file")
    filing_type: str = Field(..., description="Type of filing (motion, brief, exhibit, etc.)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional filing metadata")
    
    @validator('document_ids')
    def validate_document_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one document ID is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 documents per filing")
        return v
    
    @validator('filing_type')
    def validate_filing_type(cls, v):
        allowed_types = [
            "motion", "brief", "exhibit", "pleading", "discovery",
            "complaint", "answer", "counterclaim", "cross_claim",
            "third_party_complaint", "amended_pleading", "judgment"
        ]
        if v.lower() not in allowed_types:
            raise ValueError(f"Filing type must be one of: {', '.join(allowed_types)}")
        return v.lower()

class FilingSubmissionResponse(BaseModel):
    """Response model for filing submission"""
    submission_id: str = Field(..., description="Unique submission identifier")
    status: FilingStatus = Field(..., description="Current filing status")
    court_reference: Optional[str] = Field(None, description="Court system reference number")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    estimated_processing_time: str = Field(..., description="Estimated processing time")
    tracking_url: str = Field(..., description="URL to track filing status")

class FilingStatusResponse(BaseModel):
    """Response model for filing status"""
    submission_id: str = Field(..., description="Unique submission identifier")
    case_id: str = Field(..., description="Internal case identifier")
    court_system: CourtSystem = Field(..., description="Target court system")
    filing_type: str = Field(..., description="Type of filing")
    status: FilingStatus = Field(..., description="Current filing status")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    court_reference: Optional[str] = Field(None, description="Court system reference number")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection if applicable")
    document_count: int = Field(..., description="Number of documents in filing")

class FilingListResponse(BaseModel):
    """Response model for case filings list"""
    case_id: str = Field(..., description="Internal case identifier")
    total_filings: int = Field(..., description="Total number of filings")
    filings: List[FilingStatusResponse] = Field(..., description="List of filing submissions")

class CourtRequirementsResponse(BaseModel):
    """Response model for court filing requirements"""
    court_system: CourtSystem = Field(..., description="Court system")
    filing_type: str = Field(..., description="Type of filing")
    max_file_size_mb: int = Field(..., description="Maximum file size in MB")
    allowed_formats: List[str] = Field(..., description="Allowed file formats")
    required_metadata: List[str] = Field(..., description="Required metadata fields")
    filing_fees: Dict[str, float] = Field(..., description="Filing fees by type")
    processing_time_hours: int = Field(..., description="Estimated processing time in hours")
    court_rules: List[str] = Field(..., description="Court-specific rules and requirements")

class DocumentValidationRequest(BaseModel):
    """Request model for document validation"""
    document_ids: List[str] = Field(..., min_items=1, description="List of document IDs to validate")
    court_system: CourtSystem = Field(..., description="Target court system")
    filing_type: str = Field(..., description="Type of filing")
    
    @validator('document_ids')
    def validate_document_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one document ID is required")
        return v

class DocumentValidationResponse(BaseModel):
    """Response model for document validation"""
    valid: bool = Field(..., description="Whether all documents are valid")
    errors: List[str] = Field(..., description="List of validation errors")
    warnings: List[str] = Field(..., description="List of validation warnings")
    document_count: int = Field(..., description="Number of documents validated")
    estimated_fees: float = Field(..., description="Estimated filing fees")

class FilingStatisticsResponse(BaseModel):
    """Response model for filing statistics"""
    period_days: int = Field(..., description="Statistics period in days")
    total_filings: int = Field(..., description="Total number of filings")
    success_rate_percent: float = Field(..., description="Success rate percentage")
    status_breakdown: Dict[str, int] = Field(..., description="Breakdown by filing status")
    court_system_breakdown: Dict[str, int] = Field(..., description="Breakdown by court system")
    filing_type_breakdown: Dict[str, int] = Field(..., description="Breakdown by filing type")
    average_processing_time_hours: float = Field(..., description="Average processing time in hours")
    pending_filings: int = Field(..., description="Number of pending filings")

class FilingEventNotification(BaseModel):
    """Model for filing event notifications"""
    submission_id: str = Field(..., description="Unique submission identifier")
    case_id: str = Field(..., description="Internal case identifier")
    event_type: str = Field(..., description="Type of event (status_change, error, etc.)")
    old_status: Optional[FilingStatus] = Field(None, description="Previous status")
    new_status: FilingStatus = Field(..., description="New status")
    message: str = Field(..., description="Event message")
    timestamp: datetime = Field(..., description="Event timestamp")
    court_reference: Optional[str] = Field(None, description="Court system reference number")
    
    @validator('event_type')
    def validate_event_type(cls, v):
        allowed_events = [
            "status_change", "submission_error", "court_response",
            "processing_complete", "rejection", "acceptance", "filing_complete"
        ]
        if v not in allowed_events:
            raise ValueError(f"Event type must be one of: {', '.join(allowed_events)}")
        return v

class BulkFilingRequest(BaseModel):
    """Request model for bulk filing operations"""
    case_id: str = Field(..., description="Internal case identifier")
    court_system: CourtSystem = Field(..., description="Target court system")
    filings: List[Dict[str, Any]] = Field(..., min_items=1, max_items=20, description="List of filing requests")
    
    @validator('filings')
    def validate_filings(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one filing is required")
        if len(v) > 20:
            raise ValueError("Maximum 20 filings per bulk request")
        
        for filing in v:
            if 'document_ids' not in filing or 'filing_type' not in filing:
                raise ValueError("Each filing must have document_ids and filing_type")
        
        return v

class BulkFilingResponse(BaseModel):
    """Response model for bulk filing operations"""
    total_filings: int = Field(..., description="Total number of filings submitted")
    successful_submissions: List[str] = Field(..., description="List of successful submission IDs")
    failed_submissions: List[Dict[str, str]] = Field(..., description="List of failed submissions with errors")
    batch_id: str = Field(..., description="Unique batch identifier")
    submitted_at: datetime = Field(..., description="Batch submission timestamp")

class FilingSearchRequest(BaseModel):
    """Request model for filing search"""
    case_id: Optional[str] = Field(None, description="Filter by case ID")
    court_system: Optional[CourtSystem] = Field(None, description="Filter by court system")
    filing_type: Optional[str] = Field(None, description="Filter by filing type")
    status: Optional[FilingStatus] = Field(None, description="Filter by status")
    date_from: Optional[datetime] = Field(None, description="Filter by date range start")
    date_to: Optional[datetime] = Field(None, description="Filter by date range end")
    limit: int = Field(50, ge=1, le=500, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")

class FilingSearchResponse(BaseModel):
    """Response model for filing search"""
    total_count: int = Field(..., description="Total number of matching filings")
    filings: List[FilingStatusResponse] = Field(..., description="List of matching filings")
    has_more: bool = Field(..., description="Whether more results are available")
    next_offset: Optional[int] = Field(None, description="Offset for next page of results")

class CourtSystemStatus(BaseModel):
    """Model for court system status"""
    court_system: CourtSystem = Field(..., description="Court system")
    status: str = Field(..., description="System status (online, offline, maintenance)")
    last_checked: datetime = Field(..., description="Last status check timestamp")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if offline")
    maintenance_window: Optional[Dict[str, datetime]] = Field(None, description="Scheduled maintenance window")

class FilingTemplate(BaseModel):
    """Model for filing templates"""
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    court_system: CourtSystem = Field(..., description="Target court system")
    filing_type: str = Field(..., description="Type of filing")
    required_documents: List[str] = Field(..., description="Required document types")
    optional_documents: List[str] = Field(..., description="Optional document types")
    metadata_template: Dict[str, Any] = Field(..., description="Metadata template")
    created_at: datetime = Field(..., description="Template creation timestamp")
    updated_at: datetime = Field(..., description="Template last update timestamp")