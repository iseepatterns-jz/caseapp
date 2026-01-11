"""
REST API endpoints for external integrations
Provides comprehensive API for case management system integration
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from core.database import get_db
from core.auth import get_current_user, require_admin, require_attorney
from services.audit_service import AuditService
from schemas.integrations import (
    IntegrationResponse, CaseIntegrationResponse, DocumentIntegrationResponse,
    TimelineIntegrationResponse, MediaIntegrationResponse, ForensicIntegrationResponse,
    IntegrationStatsResponse, IntegrationHealthResponse, WebhookConfigResponse,
    CaseCreateRequest, CaseUpdateRequest, DocumentUploadRequest, TimelineEventRequest
)
from services.integration_service import IntegrationService
from services.case_service import CaseService
from services.document_service import DocumentService
from services.timeline_service import TimelineService
from services.media_service import MediaService

logger = structlog.get_logger()

router = APIRouter()

# Dependency functions
async def get_integration_service(db: AsyncSession = Depends(get_db)) -> IntegrationService:
    """Dependency to get integration service instance"""
    audit_service = AuditService(db)
    return IntegrationService(db, audit_service)

async def get_case_service_for_integration(db: AsyncSession = Depends(get_db)) -> CaseService:
    """Dependency to get case service instance for integrations"""
    audit_service = AuditService(db)
    return CaseService(db, audit_service)

@router.get("/health", response_model=IntegrationHealthResponse)
async def get_integration_health(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get integration API health status
    """
    try:
        health_status = await integration_service.get_health_status()
        
        logger.info("Integration health check requested", 
                   user_id=current_user.get("sub"),
                   status=health_status["status"])
        
        return IntegrationHealthResponse(**health_status)
        
    except Exception as e:
        logger.error("Integration health check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )

@router.get("/stats", response_model=IntegrationStatsResponse)
async def get_integration_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days for statistics"),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    Get integration usage statistics
    """
    try:
        stats = await integration_service.get_usage_statistics(days=days)
        
        logger.info("Integration statistics requested", 
                   user_id=current_user.get("sub"),
                   days=days)
        
        return IntegrationStatsResponse(**stats)
        
    except Exception as e:
        logger.error("Integration statistics failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )

# Case Management Integration Endpoints

@router.get("/cases", response_model=List[CaseIntegrationResponse])
async def list_cases_for_integration(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of cases to return"),
    offset: int = Query(0, ge=0, description="Number of cases to skip"),
    status: Optional[str] = Query(None, description="Filter by case status"),
    case_type: Optional[str] = Query(None, description="Filter by case type"),
    updated_since: Optional[str] = Query(None, description="ISO timestamp for incremental sync"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    List cases for external system integration
    Supports pagination and filtering for efficient synchronization
    """
    try:
        cases = await integration_service.get_cases_for_integration(
            db=db,
            limit=limit,
            offset=offset,
            status=status,
            case_type=case_type,
            updated_since=updated_since
        )
        
        logger.info("Cases listed for integration", 
                   user_id=current_user.get("sub"),
                   count=len(cases),
                   limit=limit,
                   offset=offset)
        
        return [CaseIntegrationResponse(**case) for case in cases]
        
    except Exception as e:
        logger.error("Case integration listing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cases"
        )

@router.get("/cases/{case_id}", response_model=CaseIntegrationResponse)
async def get_case_for_integration(
    case_id: str = Path(..., description="Case ID"),
    include_documents: bool = Query(False, description="Include document metadata"),
    include_timeline: bool = Query(False, description="Include timeline events"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    Get detailed case information for integration
    """
    try:
        case_data = await integration_service.get_case_details_for_integration(
            db=db,
            case_id=case_id,
            include_documents=include_documents,
            include_timeline=include_timeline
        )
        
        if not case_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found"
            )
        
        logger.info("Case details retrieved for integration", 
                   user_id=current_user.get("sub"),
                   case_id=case_id)
        
        return CaseIntegrationResponse(**case_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Case integration retrieval failed", 
                    case_id=case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve case"
        )

@router.post("/cases", response_model=CaseIntegrationResponse)
async def create_case_via_integration(
    case_data: CaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    Create new case via external integration
    """
    try:
        created_case = await integration_service.create_case_from_integration(
            db=db,
            case_data=case_data.dict(),
            created_by=current_user.get("sub")
        )
        
        logger.info("Case created via integration", 
                   user_id=current_user.get("sub"),
                   case_id=created_case["id"])
        
        return CaseIntegrationResponse(**created_case)
        
    except Exception as e:
        logger.error("Case creation via integration failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create case"
        )

@router.put("/cases/{case_id}", response_model=CaseIntegrationResponse)
async def update_case_via_integration(
    case_id: str = Path(..., description="Case ID"),
    case_data: CaseUpdateRequest = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    Update case via external integration
    """
    try:
        updated_case = await integration_service.update_case_from_integration(
            db=db,
            case_id=case_id,
            case_data=case_data.dict(exclude_unset=True),
            updated_by=current_user.get("sub")
        )
        
        if not updated_case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found"
            )
        
        logger.info("Case updated via integration", 
                   user_id=current_user.get("sub"),
                   case_id=case_id)
        
        return CaseIntegrationResponse(**updated_case)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Case update via integration failed", 
                    case_id=case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update case"
        )

# Document Integration Endpoints

@router.get("/cases/{case_id}/documents", response_model=List[DocumentIntegrationResponse])
async def list_case_documents_for_integration(
    case_id: str = Path(..., description="Case ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    List case documents for integration
    """
    try:
        documents = await integration_service.get_case_documents_for_integration(
            db=db,
            case_id=case_id,
            limit=limit,
            offset=offset,
            document_type=document_type
        )
        
        logger.info("Case documents listed for integration", 
                   user_id=current_user.get("sub"),
                   case_id=case_id,
                   count=len(documents))
        
        return [DocumentIntegrationResponse(**doc) for doc in documents]
        
    except Exception as e:
        logger.error("Document integration listing failed", 
                    case_id=case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )

# Timeline Integration Endpoints

@router.get("/cases/{case_id}/timeline", response_model=List[TimelineIntegrationResponse])
async def get_case_timeline_for_integration(
    case_id: str = Path(..., description="Case ID"),
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    Get case timeline for integration
    """
    try:
        timeline_events = await integration_service.get_case_timeline_for_integration(
            db=db,
            case_id=case_id,
            start_date=start_date,
            end_date=end_date,
            event_type=event_type
        )
        
        logger.info("Case timeline retrieved for integration", 
                   user_id=current_user.get("sub"),
                   case_id=case_id,
                   event_count=len(timeline_events))
        
        return [TimelineIntegrationResponse(**event) for event in timeline_events]
        
    except Exception as e:
        logger.error("Timeline integration retrieval failed", 
                    case_id=case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timeline"
        )

@router.post("/cases/{case_id}/timeline", response_model=TimelineIntegrationResponse)
async def create_timeline_event_via_integration(
    case_id: str = Path(..., description="Case ID"),
    event_data: TimelineEventRequest = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    Create timeline event via integration
    """
    try:
        created_event = await integration_service.create_timeline_event_from_integration(
            db=db,
            case_id=case_id,
            event_data=event_data.dict(),
            created_by=current_user.get("sub")
        )
        
        logger.info("Timeline event created via integration", 
                   user_id=current_user.get("sub"),
                   case_id=case_id,
                   event_id=created_event["id"])
        
        return TimelineIntegrationResponse(**created_event)
        
    except Exception as e:
        logger.error("Timeline event creation via integration failed", 
                    case_id=case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create timeline event"
        )

# Webhook Configuration Endpoints

@router.get("/webhooks", response_model=List[WebhookConfigResponse])
async def list_webhook_configurations(
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    List webhook configurations for external integrations
    """
    try:
        webhooks = await integration_service.get_webhook_configurations()
        
        logger.info("Webhook configurations listed", 
                   user_id=current_user.get("sub"),
                   count=len(webhooks))
        
        return [WebhookConfigResponse(**webhook) for webhook in webhooks]
        
    except Exception as e:
        logger.error("Webhook configuration listing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve webhook configurations"
        )

@router.post("/webhooks", response_model=WebhookConfigResponse)
async def create_webhook_configuration(
    webhook_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Create new webhook configuration
    """
    try:
        created_webhook = await integration_service.create_webhook_configuration(
            webhook_data=webhook_data,
            created_by=current_user.get("sub")
        )
        
        logger.info("Webhook configuration created", 
                   user_id=current_user.get("sub"),
                   webhook_id=created_webhook["id"])
        
        return WebhookConfigResponse(**created_webhook)
        
    except Exception as e:
        logger.error("Webhook configuration creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create webhook configuration"
        )

@router.delete("/webhooks/{webhook_id}")
async def delete_webhook_configuration(
    webhook_id: str = Path(..., description="Webhook ID"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Delete webhook configuration
    """
    try:
        success = await integration_service.delete_webhook_configuration(webhook_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook configuration not found"
            )
        
        logger.info("Webhook configuration deleted", 
                   user_id=current_user.get("sub"),
                   webhook_id=webhook_id)
        
        return {"message": "Webhook configuration deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Webhook configuration deletion failed", 
                    webhook_id=webhook_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete webhook configuration"
        )

# Batch Operations for Efficient Integration

@router.post("/batch/cases", response_model=List[CaseIntegrationResponse])
async def batch_create_cases(
    cases_data: List[CaseCreateRequest],
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Batch create multiple cases for efficient integration
    """
    try:
        if len(cases_data) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch size cannot exceed 100 cases"
            )
        
        created_cases = await integration_service.batch_create_cases(
            db=db,
            cases_data=[case.dict() for case in cases_data],
            created_by=current_user.get("sub")
        )
        
        logger.info("Batch case creation completed", 
                   user_id=current_user.get("sub"),
                   count=len(created_cases))
        
        return [CaseIntegrationResponse(**case) for case in created_cases]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Batch case creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create cases in batch"
        )

@router.get("/sync/status/{sync_id}")
async def get_sync_status(
    sync_id: str = Path(..., description="Synchronization ID"),
    current_user: Dict[str, Any] = Depends(require_attorney)
):
    """
    Get status of ongoing synchronization operation
    """
    try:
        sync_status = await integration_service.get_sync_status(sync_id)
        
        if not sync_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Synchronization not found"
            )
        
        logger.info("Sync status retrieved", 
                   user_id=current_user.get("sub"),
                   sync_id=sync_id,
                   status=sync_status["status"])
        
        return sync_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sync status retrieval failed", 
                    sync_id=sync_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sync status"
        )