"""
Timeline management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import structlog

from core.database import get_db
from core.auth import get_current_user
from models.user import User
from schemas.timeline import (
    TimelineEventCreateRequest, TimelineEventUpdateRequest,
    EvidencePinCreateRequest, EvidencePinUpdateRequest,
    TimelineCommentCreateRequest, TimelineCommentUpdateRequest,
    TimelineEventResponse, TimelineEventSummaryResponse, TimelineListResponse,
    EvidencePinResponse, TimelineCommentResponse, EventTypeEnum,
    TimelineEventSuggestion, EventSuggestionRequest, 
    EventEnhancementRequest, EventEnhancementResponse
)
from services.timeline_service import TimelineService
from services.ai_timeline_service import AITimelineService
from services.audit_service import AuditService
from core.exceptions import CaseManagementException

logger = structlog.get_logger()
router = APIRouter()

def get_timeline_service(db: AsyncSession = Depends(get_db)) -> TimelineService:
    """Dependency to get timeline service"""
    audit_service = AuditService(db)
    return TimelineService(db, audit_service)

@router.post("/events", response_model=TimelineEventResponse, status_code=status.HTTP_201_CREATED)
async def create_timeline_event(
    event_request: TimelineEventCreateRequest,
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Create a new timeline event
    
    - **event_request**: Timeline event data including title, date, type, and metadata
    
    Creates a chronological event for a case with proper date validation and ordering.
    """
    try:
        event = await timeline_service.create_timeline_event(event_request, current_user.id)
        return TimelineEventResponse.model_validate(event)
        
    except CaseManagementException as e:
        logger.error("Timeline event creation failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to create timeline event", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/events/{event_id}", response_model=TimelineEventResponse)
async def get_timeline_event(
    event_id: UUID,
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Get timeline event details by ID
    
    - **event_id**: UUID of the timeline event to retrieve
    
    Returns complete event information including evidence pins and comments.
    """
    try:
        event = await timeline_service.get_timeline_event(event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timeline event with ID {event_id} not found"
            )
        
        return TimelineEventResponse.model_validate(event)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get timeline event", event_id=str(event_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.put("/events/{event_id}", response_model=TimelineEventResponse)
async def update_timeline_event(
    event_id: UUID,
    update_request: TimelineEventUpdateRequest,
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Update timeline event details
    
    - **event_id**: UUID of the timeline event to update
    - **update_request**: Updated event data
    
    Updates event information with proper date validation and audit logging.
    """
    try:
        event = await timeline_service.update_timeline_event(event_id, update_request, current_user.id)
        return TimelineEventResponse.model_validate(event)
        
    except CaseManagementException as e:
        logger.error("Timeline event update failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to update timeline event", event_id=str(event_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline_event(
    event_id: UUID,
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Delete a timeline event
    
    - **event_id**: UUID of the timeline event to delete
    
    Permanently removes the event and all associated evidence pins and comments.
    """
    try:
        await timeline_service.delete_timeline_event(event_id, current_user.id)
        
    except CaseManagementException as e:
        logger.error("Timeline event deletion failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete timeline event", event_id=str(event_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/cases/{case_id}/timeline", response_model=TimelineListResponse)
async def get_case_timeline(
    case_id: UUID,
    start_date: Optional[datetime] = Query(None, description="Filter events from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter events until this date"),
    event_types: Optional[List[EventTypeEnum]] = Query(None, description="Filter by event types"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Number of events per page"),
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Get timeline events for a specific case
    
    - **case_id**: UUID of the case
    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter
    - **event_types**: Optional list of event types to filter by
    - **page**: Page number (starts from 1)
    - **page_size**: Number of events per page (1-200)
    
    Returns chronologically ordered timeline events with pagination.
    """
    try:
        offset = (page - 1) * page_size
        event_type_values = [et.value for et in event_types] if event_types else None
        
        events, total_count = await timeline_service.get_case_timeline(
            case_id, start_date, end_date, event_type_values, page_size, offset
        )
        
        event_responses = [
            TimelineEventResponse.model_validate(event) for event in events
        ]
        
        has_next = (offset + page_size) < total_count
        has_previous = page > 1
        
        return TimelineListResponse(
            events=event_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=has_next,
            has_previous=has_previous
        )
        
    except Exception as e:
        logger.error("Failed to get case timeline", case_id=str(case_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/evidence-pins", response_model=EvidencePinResponse, status_code=status.HTTP_201_CREATED)
async def pin_evidence_to_event(
    pin_request: EvidencePinCreateRequest,
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Pin evidence to a timeline event
    
    - **pin_request**: Evidence pin data including event ID, evidence type and ID, relevance score
    
    Associates evidence (documents, media, forensic data) with timeline events for case building.
    """
    try:
        pin = await timeline_service.pin_evidence_to_event(pin_request, current_user.id)
        return EvidencePinResponse.model_validate(pin)
        
    except CaseManagementException as e:
        logger.error("Evidence pinning failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to pin evidence to event", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.put("/evidence-pins/{pin_id}", response_model=EvidencePinResponse)
async def update_evidence_pin(
    pin_id: UUID,
    update_request: EvidencePinUpdateRequest,
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Update evidence pin details
    
    - **pin_id**: UUID of the evidence pin to update
    - **update_request**: Updated pin data including relevance score and notes
    
    Modifies evidence association details like relevance score and descriptive notes.
    """
    try:
        pin = await timeline_service.update_evidence_pin(pin_id, update_request, current_user.id)
        return EvidencePinResponse.model_validate(pin)
        
    except CaseManagementException as e:
        logger.error("Evidence pin update failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to update evidence pin", pin_id=str(pin_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.delete("/evidence-pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_evidence_pin(
    pin_id: UUID,
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Remove evidence pin from timeline event
    
    - **pin_id**: UUID of the evidence pin to remove
    
    Removes the association between evidence and timeline event.
    """
    try:
        await timeline_service.remove_evidence_pin(pin_id, current_user.id)
        
    except CaseManagementException as e:
        logger.error("Evidence pin removal failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to remove evidence pin", pin_id=str(pin_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/cases/{case_id}/timeline/reorder", response_model=List[TimelineEventResponse])
async def reorder_timeline_events(
    case_id: UUID,
    event_orders: List[dict],
    current_user: User = Depends(get_current_user),
    timeline_service: TimelineService = Depends(get_timeline_service)
):
    """
    Reorder timeline events with date validation
    
    - **case_id**: UUID of the case
    - **event_orders**: List of event reordering data with event_id, new_date, display_order
    
    Reorders timeline events while maintaining chronological constraints and proper validation.
    Each item in event_orders should have: {"event_id": "uuid", "new_date": "iso_date", "display_order": int}
    """
    try:
        updated_events = await timeline_service.reorder_timeline_events(
            case_id, event_orders, current_user.id
        )
        
        return [TimelineEventResponse.model_validate(event) for event in updated_events]
        
    except CaseManagementException as e:
        logger.error("Timeline reordering failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to reorder timeline events", case_id=str(case_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/events/types", response_model=List[dict])
async def get_event_types():
    """
    Get available timeline event types
    
    Returns a list of all supported event types with descriptions.
    """
    event_types = [
        {"value": "incident", "label": "Incident", "description": "Key incident or occurrence"},
        {"value": "meeting", "label": "Meeting", "description": "Client or team meeting"},
        {"value": "filing", "label": "Court Filing", "description": "Document filed with court"},
        {"value": "discovery", "label": "Discovery", "description": "Discovery process event"},
        {"value": "deposition", "label": "Deposition", "description": "Witness deposition"},
        {"value": "hearing", "label": "Hearing", "description": "Court hearing or proceeding"},
        {"value": "negotiation", "label": "Negotiation", "description": "Settlement negotiation"},
        {"value": "correspondence", "label": "Correspondence", "description": "Important communication"},
        {"value": "evidence_collection", "label": "Evidence Collection", "description": "Evidence gathering activity"},
        {"value": "witness_interview", "label": "Witness Interview", "description": "Interview with witness"},
        {"value": "expert_consultation", "label": "Expert Consultation", "description": "Consultation with expert"},
        {"value": "settlement", "label": "Settlement", "description": "Settlement agreement"},
        {"value": "trial", "label": "Trial", "description": "Trial proceeding"},
        {"value": "verdict", "label": "Verdict", "description": "Court verdict or decision"},
        {"value": "appeal", "label": "Appeal", "description": "Appeal process"},
        {"value": "other", "label": "Other", "description": "Other event type"}
    ]
    
    return event_types

@router.post("/ai/suggest-events", response_model=List[TimelineEventSuggestion])
async def suggest_timeline_events(
    suggestion_request: EventSuggestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered timeline event suggestions
    
    - **suggestion_request**: Request containing document ID or text content to analyze
    
    Uses Amazon Bedrock to analyze documents or text and suggest potential timeline events
    with confidence scores and reasoning.
    """
    try:
        ai_service = AITimelineService()
        
        if suggestion_request.document_id:
            # Get document from database
            from services.document_service import DocumentService
            document_service = DocumentService(db)
            document = await document_service.get_document(suggestion_request.document_id)
            
            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document with ID {suggestion_request.document_id} not found"
                )
            
            suggestions = await ai_service.analyze_document_for_events(
                document, suggestion_request.case_context
            )
        
        elif suggestion_request.text_content:
            suggestions = await ai_service.suggest_events_from_text(
                suggestion_request.text_content, suggestion_request.case_context
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either document_id or text_content must be provided"
            )
        
        logger.info(
            "AI event suggestions generated",
            user_id=str(current_user.id),
            suggestions_count=len(suggestions)
        )
        
        return suggestions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate event suggestions", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/ai/enhance-event", response_model=EventEnhancementResponse)
async def enhance_event_description(
    enhancement_request: EventEnhancementRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Enhance event descriptions using AI
    
    - **enhancement_request**: Event details to enhance
    
    Uses Amazon Bedrock to improve event titles and descriptions with better
    legal terminology and clarity.
    """
    try:
        ai_service = AITimelineService()
        
        enhanced = await ai_service.enhance_event_description(
            enhancement_request.event_title,
            enhancement_request.event_description,
            enhancement_request.event_type,
            enhancement_request.case_context
        )
        
        logger.info(
            "Event description enhanced",
            user_id=str(current_user.id),
            event_title=enhancement_request.event_title
        )
        
        return EventEnhancementResponse(
            enhanced_title=enhanced["enhanced_title"],
            enhanced_description=enhanced["enhanced_description"],
            improvements_made=enhanced["improvements_made"]
        )
        
    except Exception as e:
        logger.error("Failed to enhance event description", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/documents/{document_id}/suggest-events", response_model=List[TimelineEventSuggestion])
async def suggest_events_from_document(
    document_id: UUID,
    case_context: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate timeline event suggestions from a specific document
    
    - **document_id**: UUID of the document to analyze
    - **case_context**: Optional context about the case for better suggestions
    
    Analyzes the specified document using AI to identify potential timeline events.
    """
    try:
        ai_service = AITimelineService()
        
        # Get document from database
        from services.document_service import DocumentService
        document_service = DocumentService(db)
        document = await document_service.get_document(document_id)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found"
            )
        
        suggestions = await ai_service.analyze_document_for_events(document, case_context)
        
        logger.info(
            "Document analyzed for timeline events",
            document_id=str(document_id),
            user_id=str(current_user.id),
            suggestions_count=len(suggestions)
        )
        
        return suggestions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to analyze document for events", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")