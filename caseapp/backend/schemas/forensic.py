"""
Pydantic schemas for forensic analysis API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from models.forensic_analysis import ForensicDataType, AnalysisStatus

class ForensicSourceCreate(BaseModel):
    """Schema for creating forensic source"""
    case_id: int
    source_name: str = Field(..., min_length=1, max_length=200)
    source_type: str = Field(..., min_length=1, max_length=50)

class ForensicSourceResponse(BaseModel):
    """Schema for forensic source response"""
    id: int
    case_id: int
    source_name: str
    source_type: str
    file_path: str
    file_size: Optional[int]
    file_hash: Optional[str]
    device_info: Optional[Dict[str, Any]]
    account_info: Optional[Dict[str, Any]]
    analysis_status: AnalysisStatus
    analysis_progress: float
    analysis_started_at: Optional[datetime]
    analysis_completed_at: Optional[datetime]
    analysis_errors: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ForensicItemResponse(BaseModel):
    """Schema for forensic item response"""
    id: int
    source_id: int
    item_type: ForensicDataType
    external_id: Optional[str]
    thread_id: Optional[str]
    timestamp: datetime
    timezone_offset: Optional[int]
    sender: Optional[str]
    recipients: Optional[List[str]]
    participants: Optional[List[str]]
    subject: Optional[str]
    content: Optional[str]
    content_type: Optional[str]
    attachments: Optional[List[Dict[str, Any]]]
    message_id: Optional[str]
    in_reply_to: Optional[str]
    headers: Optional[Dict[str, Any]]
    latitude: Optional[float]
    longitude: Optional[float]
    location_accuracy: Optional[float]
    location_name: Optional[str]
    sentiment_score: Optional[float]
    language: Optional[str]
    keywords: Optional[List[str]]
    entities: Optional[List[Dict[str, Any]]]
    topics: Optional[List[str]]
    is_deleted: bool
    is_draft: bool
    is_encrypted: bool
    is_suspicious: bool
    relevance_score: Optional[float]
    is_flagged: bool
    flag_reason: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ForensicAnalysisReportResponse(BaseModel):
    """Schema for forensic analysis report response"""
    id: int
    source_id: int
    report_type: str
    title: str
    description: Optional[str]
    total_items: int
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    statistics: Optional[Dict[str, Any]]
    insights: Optional[List[Dict[str, Any]]]
    patterns: Optional[Dict[str, Any]]
    anomalies: Optional[Dict[str, Any]]
    charts_data: Optional[Dict[str, Any]]
    network_data: Optional[Dict[str, Any]]
    timeline_data: Optional[List[Dict[str, Any]]]
    report_file_path: Optional[str]
    export_data: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ForensicSearchRequest(BaseModel):
    """Schema for forensic search request"""
    case_id: int
    query: Optional[str] = None
    item_types: Optional[List[ForensicDataType]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sender: Optional[str] = None
    min_relevance: Optional[float] = Field(None, ge=0.0, le=1.0)
    has_attachments: Optional[bool] = None
    sentiment_range: Optional[str] = Field(None, pattern="^(positive|negative|neutral)$")
    limit: int = Field(100, le=1000)
    offset: int = Field(0, ge=0)

class ForensicSearchResponse(BaseModel):
    """Schema for forensic search response"""
    items: List[ForensicItemResponse]
    total: int
    offset: int
    limit: int
    
    class Config:
        from_attributes = True

class ForensicItemFlag(BaseModel):
    """Schema for flagging forensic items"""
    is_flagged: bool = True
    reason: Optional[str] = None
    is_suspicious: bool = False

class ForensicTimelinePinCreate(BaseModel):
    """Schema for pinning forensic item to timeline"""
    timeline_event_id: int
    relevance_score: float = Field(5.0, ge=1.0, le=10.0)
    context_note: Optional[str] = None
    is_key_evidence: bool = False

class ForensicAlertResponse(BaseModel):
    """Schema for forensic alert response"""
    id: int
    source_id: int
    alert_type: str
    severity: str
    title: str
    description: Optional[str]
    trigger_criteria: Optional[Dict[str, Any]]
    affected_items: Optional[List[int]]
    is_acknowledged: bool
    acknowledged_by_id: Optional[int]
    acknowledged_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class CommunicationNetworkResponse(BaseModel):
    """Schema for communication network response"""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    clusters: Optional[List[Dict[str, Any]]]
    centrality_scores: Optional[Dict[str, float]]
    community_detection: Optional[Dict[str, Any]]
    temporal_analysis: Optional[Dict[str, Any]]
    metrics: Optional[Dict[str, Any]]

class ForensicTimelineResponse(BaseModel):
    """Schema for forensic timeline response"""
    timeline: List[Dict[str, Any]]
    total_items: int
    date_range: Dict[str, Optional[str]]

class ForensicStatistics(BaseModel):
    """Schema for forensic statistics"""
    total_items: int
    by_type: Dict[str, int]
    by_hour: List[int]
    by_day_of_week: List[int]
    by_month: Dict[str, int]
    top_contacts: Dict[str, int]
    conversation_threads: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    flagged_items: int
    suspicious_items: int
    deleted_items: int

class ForensicInsight(BaseModel):
    """Schema for forensic insights"""
    type: str
    title: str
    description: str
    severity: str
    confidence: Optional[float] = None
    affected_items: Optional[List[int]] = None
    recommendations: Optional[List[str]] = None