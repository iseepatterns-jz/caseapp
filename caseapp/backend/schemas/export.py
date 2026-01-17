"""
Pydantic schemas for export and reporting functionality
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime, UTC
from enum import Enum

class ExportFormat(str, Enum):
    """Supported export formats"""
    PDF = "pdf"
    PNG = "png"
    JSON = "json"
    CSV = "csv"

class DateRange(BaseModel):
    """Date range for filtering exports"""
    start_date: datetime = Field(..., description="Start date for filtering")
    end_date: datetime = Field(..., description="End date for filtering")
    
    @model_validator(mode='after')
    def end_date_must_be_after_start_date(self) -> 'DateRange':
        if self.end_date <= self.start_date:
            raise ValueError('end_date must be after start_date')
        return self

class TimelineExportRequest(BaseModel):
    """Request schema for timeline export"""
    case_id: str = Field(..., description="UUID of the case to export")
    timeline_id: Optional[str] = Field(None, description="Optional specific timeline ID")
    date_range: Optional[DateRange] = Field(None, description="Optional date filtering")
    include_evidence: bool = Field(True, description="Whether to include evidence attachments")
    include_metadata: bool = Field(True, description="Whether to include event metadata")
    
    # PNG-specific options
    width: Optional[int] = Field(1920, ge=800, le=4000, description="Image width in pixels")
    height: Optional[int] = Field(1080, ge=600, le=3000, description="Image height in pixels")
    dpi: Optional[int] = Field(300, ge=72, le=600, description="Image resolution")
    
    @field_validator('case_id')
    def validate_case_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('case_id cannot be empty')
        return v.strip()

class ForensicReportRequest(BaseModel):
    """Request schema for forensic report export"""
    case_id: str = Field(..., description="UUID of the case to export")
    source_ids: Optional[List[str]] = Field(None, description="Optional list of specific forensic source IDs")
    include_statistics: bool = Field(True, description="Whether to include communication statistics")
    include_network_analysis: bool = Field(True, description="Whether to include network graphs")
    include_raw_data: bool = Field(False, description="Whether to include raw message data")
    
    @field_validator('case_id')
    def validate_case_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('case_id cannot be empty')
        return v.strip()
    
    @field_validator('source_ids')
    def validate_source_ids(cls, v):
        if v is not None:
            # Remove empty strings and duplicates
            v = list(set([s.strip() for s in v if s and s.strip()]))
            if not v:
                return None
        return v

class SelectiveExportRequest(BaseModel):
    """Request schema for selective export with filtering"""
    case_id: str = Field(..., description="UUID of the case to export")
    export_format: ExportFormat = Field(..., description="Export format")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Export filters")
    
    @field_validator('case_id')
    def validate_case_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('case_id cannot be empty')
        return v.strip()
    
    @field_validator('filters')
    def validate_filters(cls, v):
        # Validate common filter structures
        if 'date_range' in v and v['date_range']:
            date_range = v['date_range']
            if isinstance(date_range, dict):
                if 'start_date' in date_range and 'end_date' in date_range:
                    try:
                        start = datetime.fromisoformat(date_range['start_date'].replace('Z', '+00:00')) if isinstance(date_range['start_date'], str) else date_range['start_date']
                        end = datetime.fromisoformat(date_range['end_date'].replace('Z', '+00:00')) if isinstance(date_range['end_date'], str) else date_range['end_date']
                        if end <= start:
                            raise ValueError('end_date must be after start_date in filters')
                    except (ValueError, AttributeError) as e:
                        raise ValueError(f'Invalid date format in filters: {e}')
        
        # Validate event_types filter
        if 'event_types' in v and v['event_types']:
            if not isinstance(v['event_types'], list):
                raise ValueError('event_types filter must be a list')
            valid_types = ['meeting', 'incident', 'communication', 'legal_action', 'evidence_collection', 'other']
            for event_type in v['event_types']:
                if event_type not in valid_types:
                    raise ValueError(f'Invalid event_type: {event_type}. Must be one of {valid_types}')
        
        return v

class ExportResponse(BaseModel):
    """Response schema for export operations"""
    success: bool = Field(..., description="Whether the export was successful")
    message: str = Field(..., description="Status message")
    data: Optional[Dict[str, Any]] = Field(None, description="Export data (for JSON exports)")
    export_format: Optional[str] = Field(None, description="Format of the export")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Export timestamp")
    file_size: Optional[int] = Field(None, description="Size of exported file in bytes")
    download_url: Optional[str] = Field(None, description="URL for downloading the export")

class ExportHistoryItem(BaseModel):
    """Schema for export history items"""
    export_id: str = Field(..., description="Unique export identifier")
    case_id: str = Field(..., description="Case ID")
    export_type: str = Field(..., description="Type of export (timeline, forensic, selective)")
    export_format: str = Field(..., description="Export format")
    created_at: datetime = Field(..., description="Export creation timestamp")
    created_by: str = Field(..., description="User who created the export")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filters that were applied")
    status: str = Field(..., description="Export status (completed, failed, in_progress)")

class ExportHistoryResponse(BaseModel):
    """Response schema for export history"""
    case_id: str = Field(..., description="Case ID")
    exports: List[ExportHistoryItem] = Field(..., description="List of export history items")
    total_count: int = Field(..., description="Total number of exports")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Number of items per page")

class ExportCapabilities(BaseModel):
    """Schema for export format capabilities"""
    format: str = Field(..., description="Export format name")
    description: str = Field(..., description="Format description")
    supports_filtering: bool = Field(..., description="Whether format supports filtering")
    supports_evidence: Optional[bool] = Field(None, description="Whether format supports evidence inclusion")
    supports_metadata: Optional[bool] = Field(None, description="Whether format supports metadata inclusion")
    supports_statistics: Optional[bool] = Field(None, description="Whether format supports statistics")
    supports_network_analysis: Optional[bool] = Field(None, description="Whether format supports network analysis")
    supports_raw_data: Optional[bool] = Field(None, description="Whether format supports raw data inclusion")

class SupportedFormatsResponse(BaseModel):
    """Response schema for supported export formats"""
    timeline_formats: List[ExportCapabilities] = Field(..., description="Supported timeline export formats")
    forensic_formats: List[ExportCapabilities] = Field(..., description="Supported forensic export formats")
    selective_formats: List[ExportCapabilities] = Field(..., description="Supported selective export formats")
    available_filters: List[str] = Field(..., description="Available filter types")

# Additional schemas for specific export types

class TimelineVisualizationOptions(BaseModel):
    """Options for timeline visualization exports"""
    show_event_types: bool = Field(True, description="Whether to show event type indicators")
    show_participants: bool = Field(True, description="Whether to show participant information")
    color_by_type: bool = Field(True, description="Whether to color-code events by type")
    include_legend: bool = Field(True, description="Whether to include a legend")
    theme: str = Field("professional", description="Visualization theme")

class ForensicAnalysisOptions(BaseModel):
    """Options for forensic analysis exports"""
    include_sentiment_analysis: bool = Field(True, description="Whether to include sentiment analysis")
    include_temporal_patterns: bool = Field(True, description="Whether to include temporal pattern analysis")
    include_participant_networks: bool = Field(True, description="Whether to include participant network graphs")
    anonymize_participants: bool = Field(False, description="Whether to anonymize participant names")
    highlight_anomalies: bool = Field(True, description="Whether to highlight detected anomalies")

class ExportFilter(BaseModel):
    """Generic export filter"""
    filter_type: str = Field(..., description="Type of filter")
    filter_value: Union[str, List[str], Dict[str, Any]] = Field(..., description="Filter value")
    operator: str = Field("equals", description="Filter operator (equals, contains, between, etc.)")

class AdvancedExportRequest(BaseModel):
    """Advanced export request with detailed filtering options"""
    case_id: str = Field(..., description="UUID of the case to export")
    export_type: str = Field(..., description="Type of export (timeline, forensic, selective)")
    export_format: ExportFormat = Field(..., description="Export format")
    filters: List[ExportFilter] = Field(default_factory=list, description="List of filters to apply")
    options: Optional[Dict[str, Any]] = Field(None, description="Format-specific options")
    include_audit_trail: bool = Field(False, description="Whether to include audit trail information")
    
    @field_validator('case_id')
    def validate_case_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('case_id cannot be empty')
        return v.strip()
    
    @field_validator('export_type')
    def validate_export_type(cls, v):
        valid_types = ['timeline', 'forensic', 'selective', 'comprehensive']
        if v not in valid_types:
            raise ValueError(f'export_type must be one of {valid_types}')
        return v