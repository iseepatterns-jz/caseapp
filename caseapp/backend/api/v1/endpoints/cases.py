"""
Case management endpoints with full CRUD operations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from uuid import UUID
import math

from core.auth import get_current_user
from core.database import get_db
from schemas.base import BaseResponse
from schemas.case import (
    CaseCreate, CaseUpdate, CaseStatusUpdate, CaseResponse, 
    CaseListResponse, CaseCreateResponse, CaseUpdateResponse,
    CaseSearchRequest, CaseStatsResponse
)
from services.case_service import CaseService
from services.audit_service import AuditService
from core.exceptions import CaseManagementException

router = APIRouter()

async def get_case_service(db: AsyncSession = Depends(get_db)) -> CaseService:
    """Dependency to get case service instance"""
    audit_service = AuditService(db)
    return CaseService(db, audit_service)

@router.post("/", response_model=CaseCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_data: CaseCreate,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service)
):
    """
    Create a new case
    
    - **case_number**: Unique case identifier
    - **title**: Case title
    - **description**: Optional case description
    - **case_type**: Type of case (civil, criminal, family, etc.)
    - **priority**: Case priority (low, medium, high, urgent)
    - **client_id**: Optional associated client ID
    """
    try:
        case = await case_service.create_case(case_data, current_user["id"])
        
        # Convert to response model
        case_response = CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            case_type=case.case_type,
            status=case.status,
            priority=case.priority,
            client_id=case.client_id,
            court_name=case.court_name,
            judge_name=case.judge_name,
            case_jurisdiction=case.case_jurisdiction,
            filed_date=case.filed_date,
            court_date=case.court_date,
            deadline_date=case.deadline_date,
            closed_date=case.closed_date,
            ai_category=case.ai_category,
            ai_summary=case.ai_summary,
            ai_keywords=case.ai_keywords,
            ai_risk_assessment=case.ai_risk_assessment,
            case_metadata=case.case_metadata,
            audit={
                "created_at": case.created_at,
                "updated_at": case.updated_at,
                "created_by": case.created_by,
                "updated_by": case.updated_by
            }
        )
        
        return CaseCreateResponse(
            message="Case created successfully",
            data=case_response
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "error_code": e.error_code}
        )

@router.get("/{case_id}", response_model=CaseUpdateResponse)
async def get_case(
    case_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service)
):
    """Get a specific case by ID"""
    try:
        case = await case_service.get_case(case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found"
            )
        
        case_response = CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            case_type=case.case_type,
            status=case.status,
            priority=case.priority,
            client_id=case.client_id,
            court_name=case.court_name,
            judge_name=case.judge_name,
            case_jurisdiction=case.case_jurisdiction,
            filed_date=case.filed_date,
            court_date=case.court_date,
            deadline_date=case.deadline_date,
            closed_date=case.closed_date,
            ai_category=case.ai_category,
            ai_summary=case.ai_summary,
            ai_keywords=case.ai_keywords,
            ai_risk_assessment=case.ai_risk_assessment,
            case_metadata=case.case_metadata,
            audit={
                "created_at": case.created_at,
                "updated_at": case.updated_at,
                "created_by": case.created_by,
                "updated_by": case.updated_by
            }
        )
        
        return CaseUpdateResponse(
            message="Case retrieved successfully",
            data=case_response
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/{case_id}", response_model=CaseUpdateResponse)
async def update_case(
    case_id: UUID,
    case_data: CaseUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service)
):
    """Update an existing case"""
    try:
        case = await case_service.update_case(case_id, case_data, current_user["id"])
        
        case_response = CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            case_type=case.case_type,
            status=case.status,
            priority=case.priority,
            client_id=case.client_id,
            court_name=case.court_name,
            judge_name=case.judge_name,
            case_jurisdiction=case.case_jurisdiction,
            filed_date=case.filed_date,
            court_date=case.court_date,
            deadline_date=case.deadline_date,
            closed_date=case.closed_date,
            ai_category=case.ai_category,
            ai_summary=case.ai_summary,
            ai_keywords=case.ai_keywords,
            ai_risk_assessment=case.ai_risk_assessment,
            case_metadata=case.case_metadata,
            audit={
                "created_at": case.created_at,
                "updated_at": case.updated_at,
                "created_by": case.created_by,
                "updated_by": case.updated_by
            }
        )
        
        return CaseUpdateResponse(
            message="Case updated successfully",
            data=case_response
        )
        
    except CaseManagementException as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.patch("/{case_id}/status", response_model=CaseUpdateResponse)
async def update_case_status(
    case_id: UUID,
    status_data: CaseStatusUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service)
):
    """Update case status with closure workflow validation"""
    try:
        case = await case_service.update_case_status(case_id, status_data, current_user["id"])
        
        case_response = CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            case_type=case.case_type,
            status=case.status,
            priority=case.priority,
            client_id=case.client_id,
            court_name=case.court_name,
            judge_name=case.judge_name,
            case_jurisdiction=case.case_jurisdiction,
            filed_date=case.filed_date,
            court_date=case.court_date,
            deadline_date=case.deadline_date,
            closed_date=case.closed_date,
            ai_category=case.ai_category,
            ai_summary=case.ai_summary,
            ai_keywords=case.ai_keywords,
            ai_risk_assessment=case.ai_risk_assessment,
            case_metadata=case.case_metadata,
            audit={
                "created_at": case.created_at,
                "updated_at": case.updated_at,
                "created_by": case.created_by,
                "updated_by": case.updated_by
            }
        )
        
        return CaseUpdateResponse(
            message="Case status updated successfully",
            data=case_response
        )
        
    except CaseManagementException as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{case_id}", response_model=BaseResponse)
async def delete_case(
    case_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service)
):
    """Soft delete a case (mark as archived)"""
    try:
        await case_service.delete_case(case_id, current_user["id"])
        
        return BaseResponse(message="Case deleted successfully")
        
    except CaseManagementException as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=CaseListResponse)
async def search_cases(
    query: Optional[str] = Query(None, description="Search query"),
    case_type: Optional[str] = Query(None, description="Filter by case type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    client_id: Optional[UUID] = Query(None, description="Filter by client"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service)
):
    """
    Search and list cases with filtering, pagination, and sorting
    
    - **query**: Search across case number, title, and description
    - **case_type**: Filter by case type
    - **status**: Filter by case status
    - **priority**: Filter by case priority
    - **client_id**: Filter by associated client
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 100)
    - **sort_by**: Field to sort by (default: created_at)
    - **sort_order**: Sort order (asc/desc, default: desc)
    """
    try:
        # Create search request
        search_request = CaseSearchRequest(
            query=query,
            case_type=case_type,
            status=status,
            priority=priority,
            client_id=client_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        cases, total = await case_service.search_cases(search_request)
        
        # Convert to response models
        case_responses = []
        for case in cases:
            case_response = CaseResponse(
                id=case.id,
                case_number=case.case_number,
                title=case.title,
                description=case.description,
                case_type=case.case_type,
                status=case.status,
                priority=case.priority,
                client_id=case.client_id,
                court_name=case.court_name,
                judge_name=case.judge_name,
                case_jurisdiction=case.case_jurisdiction,
                filed_date=case.filed_date,
                court_date=case.court_date,
                deadline_date=case.deadline_date,
                closed_date=case.closed_date,
                ai_category=case.ai_category,
                ai_summary=case.ai_summary,
                ai_keywords=case.ai_keywords,
                ai_risk_assessment=case.ai_risk_assessment,
                case_metadata=case.case_metadata,
                audit={
                    "created_at": case.created_at,
                    "updated_at": case.updated_at,
                    "created_by": case.created_by,
                    "updated_by": case.updated_by
                }
            )
            case_responses.append(case_response)
        
        # Calculate pagination info
        total_pages = math.ceil(total / page_size)
        has_next = page < total_pages
        has_previous = page > 1
        
        return CaseListResponse(
            message="Cases retrieved successfully",
            data=case_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/statistics/dashboard", response_model=CaseStatsResponse)
async def get_case_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service)
):
    """Get case statistics for dashboard"""
    try:
        stats = await case_service.get_case_statistics()
        
        return CaseStatsResponse(
            message="Case statistics retrieved successfully",
            data=stats
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )