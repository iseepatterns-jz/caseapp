"""
Case management service with CRUD operations
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta, UTC
import structlog

from models.case import Case, CaseStatus, CaseType, CasePriority, AuditLog
from models.user import User
from schemas.case import CaseCreate, CaseUpdate, CaseStatusUpdate, CaseSearchRequest
from core.exceptions import CaseManagementException
from services.audit_service import AuditService

logger = structlog.get_logger()

class CaseService:
    """Service for case management operations"""
    
    def __init__(self, db: AsyncSession, audit_service: AuditService):
        self.db = db
        self.audit_service = audit_service
    
    async def create_case(self, case_data: CaseCreate, created_by: UUID) -> Case:
        """
        Create a new case with validation and audit logging
        
        Args:
            case_data: Case creation data
            created_by: UUID of the user creating the case
            
        Returns:
            Created case instance
            
        Raises:
            CaseManagementException: If case number already exists or validation fails
        """
        try:
            # Check if case number already exists
            existing_case = await self._get_case_by_number(case_data.case_number)
            if existing_case:
                raise CaseManagementException(
                    f"Case number '{case_data.case_number}' already exists",
                    error_code="DUPLICATE_CASE_NUMBER"
                )
            
            # Validate case type
            if case_data.case_type not in CaseType:
                raise CaseManagementException(
                    f"Invalid case type: {case_data.case_type}",
                    error_code="INVALID_CASE_TYPE"
                )
            
            # Create case instance
            case = Case(
                case_number=case_data.case_number,
                title=case_data.title,
                description=case_data.description,
                case_type=case_data.case_type,
                priority=case_data.priority,
                status=CaseStatus.ACTIVE,  # Always start as active
                client_id=case_data.client_id,
                court_name=case_data.court_name,
                judge_name=case_data.judge_name,
                case_jurisdiction=case_data.case_jurisdiction,
                filed_date=case_data.filed_date,
                court_date=case_data.court_date,
                deadline_date=case_data.deadline_date,
                case_metadata=case_data.case_metadata or {},
                created_by=created_by
            )
            
            self.db.add(case)
            await self.db.flush()  # Get the ID without committing
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="case",
                entity_id=case.id,
                action="create",
                user_id=created_by,
                case_id=case.id,
                entity_name=case.title,
                new_value=case_data.model_dump_json()
            )
            
            await self.db.commit()
            await self.db.refresh(case)
            
            logger.info("Case created successfully", case_id=str(case.id), case_number=case.case_number)
            return case
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to create case", error=str(e))
            raise CaseManagementException(f"Failed to create case: {str(e)}")
    
    async def get_case(self, case_id: UUID) -> Optional[Case]:
        """
        Get a case by ID with related data
        
        Args:
            case_id: Case UUID
            
        Returns:
            Case instance or None if not found
        """
        try:
            result = await self.db.execute(
                select(Case)
                .options(
                    selectinload(Case.client),
                    selectinload(Case.creator),
                    selectinload(Case.updater)
                )
                .where(Case.id == case_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get case", case_id=str(case_id), error=str(e))
            raise CaseManagementException(f"Failed to retrieve case: {str(e)}")
    
    async def update_case(self, case_id: UUID, case_data: CaseUpdate, updated_by: UUID) -> Case:
        """
        Update an existing case with audit logging
        
        Args:
            case_id: Case UUID
            case_data: Update data
            updated_by: UUID of the user updating the case
            
        Returns:
            Updated case instance
            
        Raises:
            CaseManagementException: If case not found or validation fails
        """
        try:
            case = await self.get_case(case_id)
            if not case:
                raise CaseManagementException(
                    f"Case with ID {case_id} not found",
                    error_code="CASE_NOT_FOUND"
                )
            
            # Store original values for audit
            original_values = {}
            
            # Update fields that are provided
            update_data = case_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(case, field):
                    original_values[field] = getattr(case, field)
                    setattr(case, field, value)
            
            case.updated_by = updated_by
            case.updated_at = datetime.now(UTC)
            
            # Create audit logs for each changed field
            for field, new_value in update_data.items():
                if field in original_values:
                    await self.audit_service.log_action(
                        entity_type="case",
                        entity_id=case.id,
                        action="update",
                        field_name=field,
                        old_value=str(original_values[field]) if original_values[field] is not None else None,
                        new_value=str(new_value) if new_value is not None else None,
                        user_id=updated_by,
                        case_id=case.id,
                        entity_name=case.title
                    )
            
            await self.db.commit()
            await self.db.refresh(case)
            
            logger.info("Case updated successfully", case_id=str(case.id))
            return case
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to update case", case_id=str(case_id), error=str(e))
            raise CaseManagementException(f"Failed to update case: {str(e)}")
    
    async def update_case_status(self, case_id: UUID, status_data: CaseStatusUpdate, updated_by: UUID) -> Case:
        """
        Update case status with closure workflow validation
        
        Args:
            case_id: Case UUID
            status_data: Status update data
            updated_by: UUID of the user updating the status
            
        Returns:
            Updated case instance
            
        Raises:
            CaseManagementException: If case not found or closure validation fails
        """
        try:
            case = await self.get_case(case_id)
            if not case:
                raise CaseManagementException(
                    f"Case with ID {case_id} not found",
                    error_code="CASE_NOT_FOUND"
                )
            
            old_status = case.status
            
            # Handle closure workflow
            if status_data.status == CaseStatus.CLOSED:
                if not status_data.closure_reason:
                    raise CaseManagementException(
                        "Closure reason is required when closing a case",
                        error_code="CLOSURE_REASON_REQUIRED"
                    )
                
                case.closed_date = datetime.now(UTC)
                
                # Add closure metadata
                closure_metadata = {
                    "closure_reason": status_data.closure_reason,
                    "closure_notes": status_data.closure_notes,
                    "closed_by": str(updated_by),
                    "closed_at": case.closed_date.isoformat()
                }
                
                if case.case_metadata:
                    case.case_metadata.update(closure_metadata)
                else:
                    case.case_metadata = closure_metadata
            
            case.status = status_data.status
            case.updated_by = updated_by
            case.updated_at = datetime.now(UTC)
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="case",
                entity_id=case.id,
                action="status_change",
                field_name="status",
                old_value=old_status.value,
                new_value=status_data.status.value,
                user_id=updated_by,
                case_id=case.id,
                entity_name=case.title
            )
            
            await self.db.commit()
            await self.db.refresh(case)
            
            logger.info("Case status updated", case_id=str(case.id), old_status=old_status.value, new_status=status_data.status.value)
            return case
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to update case status", case_id=str(case_id), error=str(e))
            raise CaseManagementException(f"Failed to update case status: {str(e)}")
    
    async def delete_case(self, case_id: UUID, deleted_by: UUID) -> bool:
        """
        Soft delete a case (mark as archived)
        
        Args:
            case_id: Case UUID
            deleted_by: UUID of the user deleting the case
            
        Returns:
            True if successful
            
        Raises:
            CaseManagementException: If case not found
        """
        try:
            case = await self.get_case(case_id)
            if not case:
                raise CaseManagementException(
                    f"Case with ID {case_id} not found",
                    error_code="CASE_NOT_FOUND"
                )
            
            old_status = case.status
            case.status = CaseStatus.ARCHIVED
            case.updated_by = deleted_by
            case.updated_at = datetime.now(UTC)
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="case",
                entity_id=case.id,
                action="delete",
                field_name="status",
                old_value=old_status.value,
                new_value=CaseStatus.ARCHIVED.value,
                user_id=deleted_by,
                case_id=case.id,
                entity_name=case.title
            )
            
            await self.db.commit()
            
            logger.info("Case deleted (archived)", case_id=str(case.id))
            return True
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to delete case", case_id=str(case_id), error=str(e))
            raise CaseManagementException(f"Failed to delete case: {str(e)}")
    
    async def search_cases(self, search_params: CaseSearchRequest) -> Tuple[List[Case], int]:
        """
        Search cases with filtering, pagination, and sorting
        
        Args:
            search_params: Search parameters
            
        Returns:
            Tuple of (cases list, total count)
        """
        try:
            # Build base query
            query = select(Case).options(
                selectinload(Case.client),
                selectinload(Case.creator)
            )
            
            # Apply filters
            filters = []
            
            if search_params.query:
                # Full-text search across title, description, and case_number
                search_term = f"%{search_params.query}%"
                filters.append(
                    or_(
                        Case.title.ilike(search_term),
                        Case.description.ilike(search_term),
                        Case.case_number.ilike(search_term)
                    )
                )
            
            if search_params.case_type:
                filters.append(Case.case_type == search_params.case_type)
            
            if search_params.status:
                filters.append(Case.status == search_params.status)
            
            if search_params.priority:
                filters.append(Case.priority == search_params.priority)
            
            if search_params.client_id:
                filters.append(Case.client_id == search_params.client_id)
            
            if search_params.date_from:
                filters.append(Case.created_at >= search_params.date_from)
            
            if search_params.date_to:
                filters.append(Case.created_at <= search_params.date_to)
            
            if filters:
                query = query.where(and_(*filters))
            
            # Get total count
            count_query = select(func.count(Case.id))
            if filters:
                count_query = count_query.where(and_(*filters))
            
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()
            
            # Apply sorting
            sort_field = getattr(Case, search_params.sort_by, Case.created_at)
            if search_params.sort_order == "desc":
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
            
            # Apply pagination
            offset = (search_params.page - 1) * search_params.page_size
            query = query.offset(offset).limit(search_params.page_size)
            
            # Execute query
            result = await self.db.execute(query)
            cases = result.scalars().all()
            
            return list(cases), total
            
        except Exception as e:
            logger.error("Failed to search cases", error=str(e))
            raise CaseManagementException(f"Failed to search cases: {str(e)}")
    
    async def get_case_statistics(self) -> Dict[str, Any]:
        """
        Get case statistics for dashboard
        
        Returns:
            Dictionary with case statistics
        """
        try:
            # Total cases
            total_result = await self.db.execute(select(func.count(Case.id)))
            total_cases = total_result.scalar()
            
            # Cases by status
            status_result = await self.db.execute(
                select(Case.status, func.count(Case.id))
                .group_by(Case.status)
            )
            status_counts = {status.value: count for status, count in status_result.all()}
            
            # Cases by type
            type_result = await self.db.execute(
                select(Case.case_type, func.count(Case.id))
                .group_by(Case.case_type)
            )
            type_counts = {case_type.value: count for case_type, count in type_result.all()}
            
            # Cases by priority
            priority_result = await self.db.execute(
                select(Case.priority, func.count(Case.id))
                .group_by(Case.priority)
            )
            priority_counts = {priority.value: count for priority, count in priority_result.all()}
            
            return {
                "total_cases": total_cases,
                "by_status": status_counts,
                "by_type": type_counts,
                "by_priority": priority_counts,
                "generated_at": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get case statistics", error=str(e))
            raise CaseManagementException(f"Failed to get case statistics: {str(e)}")
    
    async def _get_case_by_number(self, case_number: str) -> Optional[Case]:
        """Get case by case number"""
        result = await self.db.execute(
            select(Case).where(Case.case_number == case_number)
        )
        return result.scalar_one_or_none()