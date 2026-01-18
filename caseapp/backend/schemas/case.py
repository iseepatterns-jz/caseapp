"""
Case-related schemas for API requests and responses
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from enum import Enum

from models.case import CaseStatus, CasePriority, CaseType
from schemas.base import BaseEntity, AuditInfo, BaseResponse, PaginatedResponse

class CaseBase(BaseModel):
    """Base case schema with common fields"""
    case_number: str = Field(..., min_length=1, max_length=50, description="Unique case number")
    title: str = Field(..., min_length=1, max_length=200, description="Case title")
    description: Optional[str] = Field(None, description="Case description")
    case_type: CaseType = Field(..., description="Type of case")
    priority: CasePriority = Field(CasePriority.MEDIUM, description="Case priority")
    client_id: Optional[UUID] = Field(None, description="Associated client ID")
    
    # Court information
    court_name: Optional[str] = Field(None, max_length=200, description="Court name")
    judge_name: Optional[str] = Field(None, max_length=100, description="Judge name")
    case_jurisdiction: Optional[str] = Field(None, max_length=100, description="Case jurisdiction")
    
    # Important dates
    filed_date: Optional[datetime] = Field(None, description="Date case was filed")
    court_date: Optional[datetime] = Field(None, description="Next court date")
    deadline_date: Optional[datetime] = Field(None, description="Important deadline")
    
    # Flexible metadata
    case_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional case metadata")
    
    @model_validator(mode='before')
    @classmethod
    def validate_enums_case_insensitive(cls, data: Any) -> Any:
        """Allow case-insensitive enum values"""
        if isinstance(data, dict):
            # Handle case_type
            if 'case_type' in data and isinstance(data['case_type'], str):
                data['case_type'] = data['case_type'].upper()
            
            # Handle priority
            if 'priority' in data and isinstance(data['priority'], str):
                data['priority'] = data['priority'].upper()
                
        return data

class CaseCreate(CaseBase):
    """Schema for creating a new case"""
    pass

class CaseUpdate(BaseModel):
    """Schema for updating an existing case"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    case_type: Optional[CaseType] = None
    priority: Optional[CasePriority] = None
    status: Optional[CaseStatus] = None
    client_id: Optional[UUID] = None
    
    # Court information
    court_name: Optional[str] = Field(None, max_length=200)
    judge_name: Optional[str] = Field(None, max_length=100)
    case_jurisdiction: Optional[str] = Field(None, max_length=100)
    
    # Important dates
    filed_date: Optional[datetime] = None
    court_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    closed_date: Optional[datetime] = None
    
    # Flexible metadata
    case_metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    @classmethod
    def validate_enums_case_insensitive(cls, data: Any) -> Any:
        """Allow case-insensitive enum values"""
        if isinstance(data, dict):
            # Handle case_type
            if 'case_type' in data and isinstance(data['case_type'], str):
                data['case_type'] = data['case_type'].upper()
            
            # Handle priority
            if 'priority' in data and isinstance(data['priority'], str):
                data['priority'] = data['priority'].upper()
                
            # Handle status
            if 'status' in data and isinstance(data['status'], str):
                data['status'] = data['status'].upper()
                
        return data

class CaseStatusUpdate(BaseModel):
    """Schema for updating case status with closure workflow"""
    status: CaseStatus = Field(..., description="New case status")
    closure_reason: Optional[str] = Field(None, description="Reason for closure (required when closing)")
    closure_notes: Optional[str] = Field(None, description="Additional closure notes")
    
    @model_validator(mode='after')
    def validate_closure_reason(self) -> 'CaseStatusUpdate':
        """Require closure reason when status is closed"""
        if self.status == CaseStatus.CLOSED and not self.closure_reason:
            raise ValueError('closure_reason is required when closing a case')
        return self

class CaseResponse(BaseEntity):
    """Schema for case API responses"""
    case_number: str
    title: str
    description: Optional[str]
    case_type: CaseType
    status: CaseStatus
    priority: CasePriority
    client_id: Optional[UUID]
    
    # Court information
    court_name: Optional[str]
    judge_name: Optional[str]
    case_jurisdiction: Optional[str]
    
    # Important dates
    filed_date: Optional[datetime]
    court_date: Optional[datetime]
    deadline_date: Optional[datetime]
    closed_date: Optional[datetime]
    
    # AI-generated fields
    ai_category: Optional[str]
    ai_summary: Optional[str]
    ai_keywords: Optional[List[str]]
    ai_risk_assessment: Optional[Dict[str, Any]]
    
    # Flexible metadata
    case_metadata: Optional[Dict[str, Any]]

class CaseListResponse(PaginatedResponse):
    """Schema for paginated case list responses"""
    data: List[CaseResponse]

class CaseCreateResponse(BaseResponse):
    """Schema for case creation response"""
    data: CaseResponse

class CaseUpdateResponse(BaseResponse):
    """Schema for case update response"""
    data: CaseResponse

class CaseSearchRequest(BaseModel):
    """Schema for case search requests"""
    query: Optional[str] = Field(None, description="Search query")
    case_type: Optional[CaseType] = Field(None, description="Filter by case type")
    status: Optional[CaseStatus] = Field(None, description="Filter by status")
    priority: Optional[CasePriority] = Field(None, description="Filter by priority")
    client_id: Optional[UUID] = Field(None, description="Filter by client")
    date_from: Optional[datetime] = Field(None, description="Filter cases created after this date")
    date_to: Optional[datetime] = Field(None, description="Filter cases created before this date")
    
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    
    # Sorting
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")

    @model_validator(mode='before')
    @classmethod
    def validate_enums_case_insensitive(cls, data: Any) -> Any:
        """Allow case-insensitive enum values"""
        if isinstance(data, dict):
            # Handle case_type
            if 'case_type' in data and isinstance(data['case_type'], str):
                data['case_type'] = data['case_type'].upper()
            
            # Handle priority
            if 'priority' in data and isinstance(data['priority'], str):
                data['priority'] = data['priority'].upper()
                
            # Handle status
            if 'status' in data and isinstance(data['status'], str):
                data['status'] = data['status'].upper()
                
        return data

class CaseStatsResponse(BaseResponse):
    """Schema for case statistics response"""
    data: Dict[str, Any]