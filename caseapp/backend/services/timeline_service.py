"""
Timeline management service with event creation, evidence pinning, and chronological validation
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta, UTC
import structlog

from models.timeline import TimelineEvent, EvidencePin, TimelineComment, EventType
from models.case import Case
from models.document import Document
from schemas.timeline import (
    TimelineEventCreateRequest, TimelineEventUpdateRequest,
    EvidencePinCreateRequest, EvidencePinUpdateRequest,
    TimelineCommentCreateRequest, TimelineCommentUpdateRequest,
    TimelineEventResponse, EvidencePinResponse, TimelineCommentResponse
)
from core.exceptions import CaseManagementException
from services.audit_service import AuditService

logger = structlog.get_logger()

class TimelineService:
    """Service for timeline and event management"""
    
    def __init__(self, db: AsyncSession, audit_service: AuditService):
        self.db = db
        self.audit_service = audit_service
    
    async def create_timeline_event(
        self, 
        event_request: TimelineEventCreateRequest, 
        created_by: UUID
    ) -> TimelineEvent:
        """
        Create a new timeline event with validation
        
        Args:
            event_request: Event creation data
            created_by: UUID of the user creating the event
            
        Returns:
            Created timeline event instance
            
        Raises:
            CaseManagementException: If validation fails or case not found
        """
        try:
            # Validate case exists
            case = await self._get_case(event_request.case_id)
            if not case:
                raise CaseManagementException(
                    f"Case with ID {event_request.case_id} not found",
                    error_code="CASE_NOT_FOUND"
                )
            
            # Validate date constraints
            if event_request.end_date and event_request.end_date < event_request.event_date:
                raise CaseManagementException(
                    "End date must be after event date",
                    error_code="INVALID_DATE_RANGE"
                )
            
            # Get display order for events on the same date
            display_order = await self._get_next_display_order(
                event_request.case_id, 
                event_request.event_date
            )
            
            # Create timeline event
            timeline_event = TimelineEvent(
                case_id=event_request.case_id,
                title=event_request.title,
                description=event_request.description,
                event_type=event_request.event_type.value,
                event_date=event_request.event_date,
                end_date=event_request.end_date,
                all_day=event_request.all_day,
                location=event_request.location,
                participants=event_request.participants or [],
                importance_level=event_request.importance_level,
                is_milestone=event_request.is_milestone,
                display_order=display_order,
                color=event_request.color,
                event_metadata=event_request.event_metadata or {},
                created_by=created_by
            )
            
            self.db.add(timeline_event)
            await self.db.flush()  # Get the ID without committing
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="timeline_event",
                entity_id=timeline_event.id,
                action="create",
                user_id=created_by,
                case_id=event_request.case_id,
                new_value=f"Created event: {event_request.title} on {event_request.event_date}"
            )
            
            await self.db.commit()
            await self.db.refresh(timeline_event)
            
            logger.info(
                "Timeline event created",
                event_id=str(timeline_event.id),
                title=event_request.title,
                case_id=str(event_request.case_id)
            )
            
            return timeline_event
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to create timeline event", error=str(e))
            raise CaseManagementException(f"Failed to create timeline event: {str(e)}")
    
    async def get_timeline_event(self, event_id: UUID) -> Optional[TimelineEvent]:
        """
        Get a timeline event by ID with related data
        
        Args:
            event_id: Timeline event UUID
            
        Returns:
            Timeline event instance or None if not found
        """
        try:
            result = await self.db.execute(
                select(TimelineEvent)
                .options(
                    selectinload(TimelineEvent.case),
                    selectinload(TimelineEvent.creator),
                    selectinload(TimelineEvent.evidence_pins),
                    selectinload(TimelineEvent.comments)
                )
                .where(TimelineEvent.id == event_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get timeline event", event_id=str(event_id), error=str(e))
            raise CaseManagementException(f"Failed to retrieve timeline event: {str(e)}")
    
    async def update_timeline_event(
        self, 
        event_id: UUID, 
        update_request: TimelineEventUpdateRequest, 
        updated_by: UUID
    ) -> TimelineEvent:
        """
        Update timeline event with date validation
        
        Args:
            event_id: Timeline event UUID
            update_request: Update data
            updated_by: UUID of the user updating the event
            
        Returns:
            Updated timeline event instance
        """
        try:
            event = await self.get_timeline_event(event_id)
            if not event:
                raise CaseManagementException(
                    f"Timeline event with ID {event_id} not found",
                    error_code="EVENT_NOT_FOUND"
                )
            
            # Store original values for audit
            original_values = {}
            
            # Update fields that are provided
            update_data = update_request.model_dump(exclude_unset=True)
            
            # Validate date constraints if dates are being updated
            new_event_date = update_data.get('event_date', event.event_date)
            new_end_date = update_data.get('end_date', event.end_date)
            
            if new_end_date and new_end_date < new_event_date:
                raise CaseManagementException(
                    "End date must be after event date",
                    error_code="INVALID_DATE_RANGE"
                )
            
            for field, value in update_data.items():
                if hasattr(event, field):
                    original_values[field] = getattr(event, field)
                    if field == 'event_type':
                        setattr(event, field, value.value if hasattr(value, 'value') else value)
                    else:
                        setattr(event, field, value)
            
            event.updated_by = updated_by
            event.updated_at = datetime.now(UTC)
            
            # Create audit logs for each changed field
            for field, new_value in update_data.items():
                if field in original_values:
                    await self.audit_service.log_action(
                        entity_type="timeline_event",
                        entity_id=event.id,
                        action="update",
                        field_name=field,
                        old_value=str(original_values[field]) if original_values[field] is not None else None,
                        new_value=str(new_value) if new_value is not None else None,
                        user_id=updated_by,
                        case_id=event.case_id
                    )
            
            await self.db.commit()
            await self.db.refresh(event)
            
            logger.info("Timeline event updated", event_id=str(event.id))
            return event
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to update timeline event", event_id=str(event_id), error=str(e))
            raise CaseManagementException(f"Failed to update timeline event: {str(e)}")
    
    async def delete_timeline_event(self, event_id: UUID, deleted_by: UUID) -> bool:
        """
        Delete a timeline event
        
        Args:
            event_id: Timeline event UUID
            deleted_by: UUID of the user deleting the event
            
        Returns:
            True if successful
        """
        try:
            event = await self.get_timeline_event(event_id)
            if not event:
                raise CaseManagementException(
                    f"Timeline event with ID {event_id} not found",
                    error_code="EVENT_NOT_FOUND"
                )
            
            # Create audit log before deletion
            await self.audit_service.log_action(
                entity_type="timeline_event",
                entity_id=event.id,
                action="delete",
                user_id=deleted_by,
                case_id=event.case_id,
                old_value=f"Deleted event: {event.title}"
            )
            
            await self.db.delete(event)
            await self.db.commit()
            
            logger.info("Timeline event deleted", event_id=str(event_id))
            return True
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to delete timeline event", event_id=str(event_id), error=str(e))
            raise CaseManagementException(f"Failed to delete timeline event: {str(e)}")
    
    async def get_case_timeline(
        self, 
        case_id: UUID, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[TimelineEvent], int]:
        """
        Get timeline events for a case with filtering and pagination
        
        Args:
            case_id: Case UUID
            start_date: Filter events from this date
            end_date: Filter events until this date
            event_types: Filter by event types
            limit: Maximum number of events to return
            offset: Number of events to skip
            
        Returns:
            Tuple of (events list, total count)
        """
        try:
            # Build base query
            query = select(TimelineEvent).options(
                selectinload(TimelineEvent.creator),
                selectinload(TimelineEvent.evidence_pins),
                selectinload(TimelineEvent.comments)
            )
            
            # Apply filters
            filters = [TimelineEvent.case_id == case_id]
            
            if start_date:
                filters.append(TimelineEvent.event_date >= start_date)
            
            if end_date:
                filters.append(TimelineEvent.event_date <= end_date)
            
            if event_types:
                filters.append(TimelineEvent.event_type.in_(event_types))
            
            query = query.where(and_(*filters))
            
            # Get total count
            count_query = select(func.count(TimelineEvent.id)).where(and_(*filters))
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()
            
            # Apply ordering and pagination
            query = query.order_by(
                TimelineEvent.event_date.asc(),
                TimelineEvent.display_order.asc()
            ).offset(offset).limit(limit)
            
            # Execute query
            result = await self.db.execute(query)
            events = result.scalars().all()
            
            return list(events), total
            
        except Exception as e:
            logger.error("Failed to get case timeline", case_id=str(case_id), error=str(e))
            raise CaseManagementException(f"Failed to get case timeline: {str(e)}")
    
    async def pin_evidence_to_event(
        self, 
        pin_request: EvidencePinCreateRequest, 
        created_by: UUID
    ) -> EvidencePin:
        """
        Pin evidence to a timeline event
        
        Args:
            pin_request: Evidence pin creation data
            created_by: UUID of the user creating the pin
            
        Returns:
            Created evidence pin instance
        """
        try:
            # Validate timeline event exists
            event = await self.get_timeline_event(pin_request.timeline_event_id)
            if not event:
                raise CaseManagementException(
                    f"Timeline event with ID {pin_request.timeline_event_id} not found",
                    error_code="EVENT_NOT_FOUND"
                )
            
            # Validate evidence exists based on type
            await self._validate_evidence_exists(pin_request.evidence_type, pin_request.evidence_id)
            
            # Get display order for evidence pins
            display_order = await self._get_next_pin_display_order(pin_request.timeline_event_id)
            
            # Create evidence pin
            evidence_pin = EvidencePin(
                timeline_event_id=pin_request.timeline_event_id,
                evidence_type=pin_request.evidence_type.value,
                evidence_id=pin_request.evidence_id,
                relevance_score=pin_request.relevance_score,
                pin_description=pin_request.pin_description,
                pin_notes=pin_request.pin_notes,
                display_order=display_order,
                is_primary=pin_request.is_primary,
                created_by=created_by
            )
            
            self.db.add(evidence_pin)
            await self.db.flush()
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="evidence_pin",
                entity_id=evidence_pin.id,
                action="create",
                user_id=created_by,
                case_id=event.case_id,
                new_value=f"Pinned {pin_request.evidence_type.value} evidence to event: {event.title}"
            )
            
            await self.db.commit()
            await self.db.refresh(evidence_pin)
            
            logger.info(
                "Evidence pinned to timeline event",
                pin_id=str(evidence_pin.id),
                event_id=str(pin_request.timeline_event_id),
                evidence_type=pin_request.evidence_type.value
            )
            
            return evidence_pin
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to pin evidence to event", error=str(e))
            raise CaseManagementException(f"Failed to pin evidence to event: {str(e)}")
    
    async def update_evidence_pin(
        self, 
        pin_id: UUID, 
        update_request: EvidencePinUpdateRequest, 
        updated_by: UUID
    ) -> EvidencePin:
        """
        Update an evidence pin
        
        Args:
            pin_id: Evidence pin UUID
            update_request: Update data
            updated_by: UUID of the user updating the pin
            
        Returns:
            Updated evidence pin instance
        """
        try:
            pin = await self._get_evidence_pin(pin_id)
            if not pin:
                raise CaseManagementException(
                    f"Evidence pin with ID {pin_id} not found",
                    error_code="PIN_NOT_FOUND"
                )
            
            # Update fields that are provided
            update_data = update_request.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(pin, field):
                    setattr(pin, field, value)
            
            # Get the timeline event for audit logging
            event = await self.get_timeline_event(pin.timeline_event_id)
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="evidence_pin",
                entity_id=pin.id,
                action="update",
                user_id=updated_by,
                case_id=event.case_id if event else None,
                new_value=f"Updated evidence pin"
            )
            
            await self.db.commit()
            await self.db.refresh(pin)
            
            logger.info("Evidence pin updated", pin_id=str(pin_id))
            return pin
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to update evidence pin", pin_id=str(pin_id), error=str(e))
            raise CaseManagementException(f"Failed to update evidence pin: {str(e)}")
    
    async def remove_evidence_pin(self, pin_id: UUID, removed_by: UUID) -> bool:
        """
        Remove an evidence pin from a timeline event
        
        Args:
            pin_id: Evidence pin UUID
            removed_by: UUID of the user removing the pin
            
        Returns:
            True if successful
        """
        try:
            pin = await self._get_evidence_pin(pin_id)
            if not pin:
                raise CaseManagementException(
                    f"Evidence pin with ID {pin_id} not found",
                    error_code="PIN_NOT_FOUND"
                )
            
            # Get the timeline event for audit logging
            event = await self.get_timeline_event(pin.timeline_event_id)
            
            # Create audit log before deletion
            await self.audit_service.log_action(
                entity_type="evidence_pin",
                entity_id=pin.id,
                action="delete",
                user_id=removed_by,
                case_id=event.case_id if event else None,
                old_value=f"Removed evidence pin"
            )
            
            await self.db.delete(pin)
            await self.db.commit()
            
            logger.info("Evidence pin removed", pin_id=str(pin_id))
            return True
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to remove evidence pin", pin_id=str(pin_id), error=str(e))
            raise CaseManagementException(f"Failed to remove evidence pin: {str(e)}")
    
    async def reorder_timeline_events(
        self, 
        case_id: UUID, 
        event_orders: List[Dict[str, Any]], 
        reordered_by: UUID
    ) -> List[TimelineEvent]:
        """
        Reorder timeline events with date validation
        
        Args:
            case_id: Case UUID
            event_orders: List of {event_id, new_date, display_order}
            reordered_by: UUID of the user reordering events
            
        Returns:
            List of updated timeline events
        """
        try:
            updated_events = []
            
            for order_data in event_orders:
                event_id = order_data.get('event_id')
                new_date = order_data.get('new_date')
                display_order = order_data.get('display_order', 0)
                
                if not event_id:
                    continue
                
                event = await self.get_timeline_event(UUID(event_id))
                if not event or event.case_id != case_id:
                    continue
                
                # Update event date and order if provided
                if new_date:
                    # Validate chronological constraints
                    if isinstance(new_date, str):
                        new_date = datetime.fromisoformat(new_date.replace('Z', '+00:00'))
                    
                    # Check if this violates any chronological constraints
                    # (This is where you'd implement business rules for date validation)
                    
                    event.event_date = new_date
                
                event.display_order = display_order
                event.updated_by = reordered_by
                event.updated_at = datetime.now(UTC)
                
                updated_events.append(event)
            
            # Create audit log for reordering
            await self.audit_service.log_action(
                entity_type="timeline",
                entity_id=case_id,
                action="reorder",
                user_id=reordered_by,
                case_id=case_id,
                new_value=f"Reordered {len(updated_events)} timeline events"
            )
            
            await self.db.commit()
            
            logger.info(
                "Timeline events reordered",
                case_id=str(case_id),
                event_count=len(updated_events)
            )
            
            return updated_events
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to reorder timeline events", case_id=str(case_id), error=str(e))
            raise CaseManagementException(f"Failed to reorder timeline events: {str(e)}")
    
    # Helper methods
    async def _get_case(self, case_id: UUID) -> Optional[Case]:
        """Get case by ID for validation"""
        result = await self.db.execute(
            select(Case).where(Case.id == case_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_evidence_pin(self, pin_id: UUID) -> Optional[EvidencePin]:
        """Get evidence pin by ID"""
        result = await self.db.execute(
            select(EvidencePin).where(EvidencePin.id == pin_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_next_display_order(self, case_id: UUID, event_date: datetime) -> int:
        """Get the next display order for events on the same date"""
        result = await self.db.execute(
            select(func.coalesce(func.max(TimelineEvent.display_order), 0))
            .where(TimelineEvent.case_id == case_id)
            .where(func.date(TimelineEvent.event_date) == event_date.date())
        )
        max_order = result.scalar() or 0
        return max_order + 1
    
    async def _get_next_pin_display_order(self, event_id: UUID) -> int:
        """Get the next display order for evidence pins on an event"""
        result = await self.db.execute(
            select(func.coalesce(func.max(EvidencePin.display_order), 0))
            .where(EvidencePin.timeline_event_id == event_id)
        )
        max_order = result.scalar() or 0
        return max_order + 1
    
    async def _validate_evidence_exists(self, evidence_type: str, evidence_id: UUID) -> bool:
        """Validate that evidence exists based on type"""
        if evidence_type == "document":
            result = await self.db.execute(
                select(Document).where(Document.id == evidence_id)
            )
            if not result.scalar_one_or_none():
                raise CaseManagementException(
                    f"Document with ID {evidence_id} not found",
                    error_code="EVIDENCE_NOT_FOUND"
                )
        # TODO: Add validation for media and forensic evidence when those models are implemented
        return True