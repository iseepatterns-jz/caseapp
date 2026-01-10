"""
Export endpoints for timeline and case data
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from uuid import UUID
import structlog

from core.database import get_db
from core.auth import get_current_user
from models.user import User
from schemas.timeline import TimelineExportRequest, TimelineExportResponse
from schemas.base import BaseResponse
from services.timeline_export_service import TimelineExportService
from services.audit_service import AuditService
from core.exceptions import CaseManagementException

logger = structlog.get_logger()
router = APIRouter()

@router.post("/timeline/{case_id}", response_model=Dict[str, str])
async def export_case_timeline(
    case_id: UUID,
    export_request: TimelineExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export case timeline in various formats
    
    - **case_id**: UUID of the case to export timeline for
    - **export_request**: Export configuration including format, filters, and options
    
    Exports the case timeline in PDF, PNG, or JSON format with optional filtering
    by date range and event types.
    """
    try:
        # Validate case_id matches request
        if export_request.case_id != case_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Case ID in URL must match case ID in request body"
            )
        
        # Create export service
        export_service = TimelineExportService(db)
        
        # Export timeline
        filepath = await export_service.export_case_timeline(
            case_id=case_id,
            export_request=export_request,
            user_id=current_user.id
        )
        
        # Create audit log
        audit_service = AuditService(db)
        await audit_service.log_action(
            entity_type="timeline_export",
            entity_id=case_id,
            action="export",
            user_id=current_user.id,
            case_id=case_id,
            new_value=f"Exported timeline as {export_request.format}"
        )
        
        logger.info(
            "Timeline export completed",
            case_id=str(case_id),
            format=export_request.format,
            user_id=str(current_user.id),
            filepath=filepath
        )
        
        return {
            "message": "Timeline exported successfully",
            "format": export_request.format,
            "filepath": filepath,
            "case_id": str(case_id)
        }
        
    except CaseManagementException as e:
        logger.error("Timeline export failed", case_id=str(case_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        logger.error("Timeline export validation failed", case_id=str(case_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Timeline export failed", case_id=str(case_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/formats")
async def get_export_formats():
    """
    Get available export formats and their descriptions
    
    Returns a list of supported export formats with descriptions and capabilities.
    """
    formats = [
        {
            "format": "pdf",
            "name": "PDF Report",
            "description": "Professional PDF document with detailed event information and evidence",
            "supports_evidence": True,
            "supports_comments": True,
            "file_extension": ".pdf"
        },
        {
            "format": "png",
            "name": "Timeline Visualization",
            "description": "Visual timeline chart showing events chronologically with importance levels",
            "supports_evidence": False,
            "supports_comments": False,
            "file_extension": ".png"
        },
        {
            "format": "json",
            "name": "Structured Data",
            "description": "Complete timeline data in JSON format for integration or analysis",
            "supports_evidence": True,
            "supports_comments": True,
            "file_extension": ".json"
        }
    ]
    
    return {
        "formats": formats,
        "default_format": "pdf"
    }