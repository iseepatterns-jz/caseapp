"""
Audit trail endpoints for comprehensive audit logging access
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
import math

from core.auth import get_current_user
from core.database import get_db
from schemas.base import BaseResponse
from schemas.audit import (
    AuditTrailResponse, AuditSearchRequest, AuditSearchResponse,
    AuditStatisticsResponse, UserActivityRequest, UserActivityResponse,
    SecurityEventRequest, SecurityEventResponse, AuditLogResponse
)
from services.audit_service import AuditService
from core.exceptions import CaseManagementException

router = APIRouter()

async def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    """Dependency to get audit service instance"""
    return AuditService(db)

@router.get("/entity/{entity_type}/{entity_id}", response_model=AuditTrailResponse)
async def get_entity_audit_trail(
    entity_type: str,
    entity_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Get complete audit trail for a specific entity
    
    - **entity_type**: Type of entity (case, document, media, etc.)
    - **entity_id**: UUID of the entity
    """
    try:
        audit_logs = await audit_service.get_entity_audit_trail(entity_type, entity_id)
        
        # Convert to response models
        audit_responses = []
        for log in audit_logs:
            audit_response = AuditLogResponse(
                id=log.id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                action=log.action,
                field_name=log.field_name,
                old_value=log.old_value,
                new_value=log.new_value,
                timestamp=log.timestamp,
                user_id=log.user_id,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                case_id=log.case_id
            )
            audit_responses.append(audit_response)
        
        return AuditTrailResponse(
            message=f"Audit trail retrieved for {entity_type} {entity_id}",
            data=audit_responses
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/case/{case_id}", response_model=AuditTrailResponse)
async def get_case_audit_trail(
    case_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Get complete audit trail for a case and all related entities
    
    - **case_id**: UUID of the case
    """
    try:
        audit_logs = await audit_service.get_case_audit_trail(case_id)
        
        # Convert to response models
        audit_responses = []
        for log in audit_logs:
            audit_response = AuditLogResponse(
                id=log.id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                action=log.action,
                field_name=log.field_name,
                old_value=log.old_value,
                new_value=log.new_value,
                timestamp=log.timestamp,
                user_id=log.user_id,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                case_id=log.case_id
            )
            audit_responses.append(audit_response)
        
        return AuditTrailResponse(
            message=f"Case audit trail retrieved for case {case_id}",
            data=audit_responses
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/search", response_model=AuditSearchResponse)
async def search_audit_logs(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    case_id: Optional[UUID] = Query(None, description="Filter by case ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    page: int = Query(1, description="Page number"),
    page_size: int = Query(50, description="Items per page"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Search audit logs with various filters
    
    - **entity_type**: Filter by entity type (optional)
    - **action**: Filter by action (optional)
    - **user_id**: Filter by user ID (optional)
    - **case_id**: Filter by case ID (optional)
    - **start_date**: Start date for filtering (optional)
    - **end_date**: End date for filtering (optional)
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page
    """
    try:
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Search audit logs
        audit_logs, total_count = await audit_service.search_audit_logs(
            entity_type=entity_type,
            action=action,
            user_id=user_id,
            case_id=case_id,
            start_date=start_date,
            end_date=end_date,
            limit=page_size,
            offset=offset
        )
        
        # Convert to response models
        audit_responses = []
        for log in audit_logs:
            audit_response = AuditLogResponse(
                id=log.id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                action=log.action,
                field_name=log.field_name,
                old_value=log.old_value,
                new_value=log.new_value,
                timestamp=log.timestamp,
                user_id=log.user_id,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                case_id=log.case_id
            )
            audit_responses.append(audit_response)
        
        # Calculate pagination info
        total_pages = math.ceil(total_count / page_size)
        has_next = page < total_pages
        has_previous = page > 1
        
        return AuditSearchResponse(
            message="Audit logs retrieved successfully",
            data=audit_responses,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )
        
    except CaseManagementException as e:
        print(f"AUDIT SEARCH ERROR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/user/{user_id}/activity", response_model=UserActivityResponse)
async def get_user_activity(
    user_id: UUID,
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of entries"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Get user activity audit trail
    
    - **user_id**: UUID of the user
    - **start_date**: Start date for filtering (optional)
    - **end_date**: End date for filtering (optional)
    - **limit**: Maximum number of entries (max 500)
    """
    try:
        # Check if current user can access this user's activity
        # (In a real system, you'd implement proper authorization here)
        if current_user["id"] != user_id and not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this user's activity"
            )
        
        audit_logs = await audit_service.get_user_activity(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        # Convert to response models
        audit_responses = []
        for log in audit_logs:
            audit_response = AuditLogResponse(
                id=log.id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                action=log.action,
                field_name=log.field_name,
                old_value=log.old_value,
                new_value=log.new_value,
                timestamp=log.timestamp,
                user_id=log.user_id,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                case_id=log.case_id
            )
            audit_responses.append(audit_response)
        
        return UserActivityResponse(
            message=f"User activity retrieved for user {user_id}",
            data=audit_responses
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/statistics", response_model=AuditStatisticsResponse)
async def get_audit_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Get audit statistics for the specified number of days
    
    - **days**: Number of days to analyze (max 365)
    """
    try:
        # Check if user has admin privileges for statistics
        if not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required to view audit statistics"
            )
        
        statistics = await audit_service.get_audit_statistics(days=days)
        
        return AuditStatisticsResponse(
            message=f"Audit statistics retrieved for {days} days",
            data=statistics
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/security-event", response_model=SecurityEventResponse)
async def log_security_event(
    event_data: SecurityEventRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Log a security event
    
    - **event_type**: Type of security event
    - **description**: Description of the event
    - **severity**: Event severity (info, warning, error, critical)
    """
    try:
        # Extract request metadata
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        audit_log = await audit_service.log_security_event(
            event_type=event_data.event_type,
            description=event_data.description,
            user_id=current_user["id"],
            ip_address=ip_address,
            user_agent=user_agent,
            severity=event_data.severity
        )
        
        audit_response = AuditLogResponse(
            id=audit_log.id,
            entity_type=audit_log.entity_type,
            entity_id=audit_log.entity_id,
            action=audit_log.action,
            field_name=audit_log.field_name,
            old_value=audit_log.old_value,
            new_value=audit_log.new_value,
            timestamp=audit_log.timestamp,
            user_id=audit_log.user_id,
            ip_address=audit_log.ip_address,
            user_agent=audit_log.user_agent,
            case_id=audit_log.case_id
        )
        
        return SecurityEventResponse(
            message="Security event logged successfully",
            data=audit_response
        )
        
    except CaseManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )