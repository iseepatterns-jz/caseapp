"""
Audit logging service for tracking all system changes
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import json
import structlog

from models.case import AuditLog
from core.exceptions import CaseManagementException

logger = structlog.get_logger()

class AuditService:
    """Service for comprehensive audit logging"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_action(
        self,
        entity_type: str,
        entity_id: UUID,
        action: str,
        user_id: UUID,
        field_name: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        case_id: Optional[UUID] = None
    ) -> AuditLog:
        """
        Create an audit log entry for entity changes
        
        Args:
            entity_type: Type of entity being modified (e.g., 'case', 'document')
            entity_id: ID of the entity being modified
            action: Action performed ('create', 'update', 'delete', etc.)
            user_id: ID of the user performing the action
            field_name: Specific field that was changed (optional)
            old_value: Previous value (optional)
            new_value: New value (optional)
            ip_address: User's IP address (optional)
            user_agent: User's browser/client info (optional)
            case_id: Associated case ID (optional)
            
        Returns:
            Created audit log entry
            
        Raises:
            CaseManagementException: If audit logging fails
        """
        try:
            audit_log = AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                case_id=case_id
            )
            
            self.db.add(audit_log)
            await self.db.flush()  # Get the ID without committing
            
            logger.info(
                "Audit log created",
                audit_id=str(audit_log.id),
                entity_type=entity_type,
                entity_id=str(entity_id),
                action=action,
                user_id=str(user_id)
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(
                "Failed to create audit log",
                entity_type=entity_type,
                entity_id=str(entity_id),
                action=action,
                error=str(e)
            )
            raise CaseManagementException(f"Failed to create audit log: {str(e)}")
    
    async def log_api_request(
        self,
        method: str,
        path: str,
        user_id: UUID,
        response_status: int,
        duration_ms: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        query_params: Optional[str] = None,
        request_data: Optional[str] = None,
        response_data: Optional[str] = None
    ) -> AuditLog:
        """
        Create an audit log entry for API requests
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            user_id: ID of the user making the request
            response_status: HTTP response status code
            duration_ms: Request duration in milliseconds
            ip_address: User's IP address (optional)
            user_agent: User's browser/client info (optional)
            query_params: Query parameters (optional)
            request_data: Request body data (optional)
            response_data: Response data (optional)
            
        Returns:
            Created audit log entry
        """
        try:
            # Create a special audit log entry for API requests
            audit_log = AuditLog(
                entity_type="api_request",
                entity_id=user_id,  # Use user_id as entity_id for API requests
                action=f"{method} {path}",
                field_name="api_call",
                old_value=request_data,
                new_value=json.dumps({
                    "status": response_status,
                    "duration_ms": duration_ms,
                    "query_params": query_params,
                    "response_data": response_data
                }),
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            self.db.add(audit_log)
            await self.db.flush()
            
            logger.debug(
                "API request logged",
                audit_id=str(audit_log.id),
                method=method,
                path=path,
                status=response_status,
                duration_ms=duration_ms,
                user_id=str(user_id)
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(
                "Failed to log API request",
                method=method,
                path=path,
                user_id=str(user_id),
                error=str(e)
            )
            # Don't raise exception for API logging failures
            return None
    
    async def log_security_event(
        self,
        event_type: str,
        description: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "info"
    ) -> AuditLog:
        """
        Log security-related events
        
        Args:
            event_type: Type of security event (login, logout, failed_auth, etc.)
            description: Description of the event
            user_id: ID of the user (optional for failed auth attempts)
            ip_address: User's IP address (optional)
            user_agent: User's browser/client info (optional)
            severity: Event severity (info, warning, error, critical)
            
        Returns:
            Created audit log entry
        """
        try:
            audit_log = AuditLog(
                entity_type="security_event",
                entity_id=user_id or UUID("00000000-0000-0000-0000-000000000000"),
                action=event_type,
                field_name="security",
                new_value=json.dumps({
                    "description": description,
                    "severity": severity
                }),
                user_id=user_id or UUID("00000000-0000-0000-0000-000000000000"),
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            self.db.add(audit_log)
            await self.db.flush()
            
            logger.info(
                "Security event logged",
                audit_id=str(audit_log.id),
                event_type=event_type,
                severity=severity,
                user_id=str(user_id) if user_id else None
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(
                "Failed to log security event",
                event_type=event_type,
                error=str(e)
            )
            raise CaseManagementException(f"Failed to log security event: {str(e)}")
    
    async def get_entity_audit_trail(self, entity_type: str, entity_id: UUID) -> List[AuditLog]:
        """
        Get complete audit trail for an entity
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            
        Returns:
            List of audit log entries ordered by timestamp
        """
        try:
            result = await self.db.execute(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == entity_type,
                    AuditLog.entity_id == entity_id
                )
                .order_by(AuditLog.timestamp.desc())
            )
            
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(
                "Failed to get audit trail",
                entity_type=entity_type,
                entity_id=str(entity_id),
                error=str(e)
            )
            raise CaseManagementException(f"Failed to get audit trail: {str(e)}")
    
    async def get_case_audit_trail(self, case_id: UUID) -> List[AuditLog]:
        """
        Get complete audit trail for a case and all related entities
        
        Args:
            case_id: Case ID
            
        Returns:
            List of audit log entries for the case and related entities
        """
        try:
            result = await self.db.execute(
                select(AuditLog)
                .where(AuditLog.case_id == case_id)
                .order_by(AuditLog.timestamp.desc())
            )
            
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(
                "Failed to get case audit trail",
                case_id=str(case_id),
                error=str(e)
            )
            raise CaseManagementException(f"Failed to get case audit trail: {str(e)}")
    
    async def get_user_activity(
        self, 
        user_id: UUID, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Get user activity audit trail
        
        Args:
            user_id: User ID
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries for the user
        """
        try:
            query = select(AuditLog).where(AuditLog.user_id == user_id)
            
            if start_date:
                query = query.where(AuditLog.timestamp >= start_date)
            
            if end_date:
                query = query.where(AuditLog.timestamp <= end_date)
            
            query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(
                "Failed to get user activity",
                user_id=str(user_id),
                error=str(e)
            )
            raise CaseManagementException(f"Failed to get user activity: {str(e)}")
    
    async def get_audit_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get audit statistics for the specified number of days
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with audit statistics
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Total audit entries
            total_result = await self.db.execute(
                select(func.count(AuditLog.id))
                .where(AuditLog.timestamp >= start_date)
            )
            total_entries = total_result.scalar()
            
            # Entries by action type
            action_result = await self.db.execute(
                select(AuditLog.action, func.count(AuditLog.id))
                .where(AuditLog.timestamp >= start_date)
                .group_by(AuditLog.action)
            )
            actions = {action: count for action, count in action_result.all()}
            
            # Entries by entity type
            entity_result = await self.db.execute(
                select(AuditLog.entity_type, func.count(AuditLog.id))
                .where(AuditLog.timestamp >= start_date)
                .group_by(AuditLog.entity_type)
            )
            entities = {entity_type: count for entity_type, count in entity_result.all()}
            
            # Most active users
            user_result = await self.db.execute(
                select(AuditLog.user_id, func.count(AuditLog.id))
                .where(AuditLog.timestamp >= start_date)
                .group_by(AuditLog.user_id)
                .order_by(func.count(AuditLog.id).desc())
                .limit(10)
            )
            active_users = [
                {"user_id": str(user_id), "activity_count": count}
                for user_id, count in user_result.all()
            ]
            
            return {
                "period_days": days,
                "total_entries": total_entries,
                "by_action": actions,
                "by_entity_type": entities,
                "most_active_users": active_users,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get audit statistics", error=str(e))
            raise CaseManagementException(f"Failed to get audit statistics: {str(e)}")
    
    async def search_audit_logs(
        self,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        user_id: Optional[UUID] = None,
        case_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[AuditLog], int]:
        """
        Search audit logs with various filters
        
        Args:
            entity_type: Filter by entity type (optional)
            action: Filter by action (optional)
            user_id: Filter by user ID (optional)
            case_id: Filter by case ID (optional)
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Maximum number of entries to return
            offset: Number of entries to skip
            
        Returns:
            Tuple of (audit log entries, total count)
        """
        try:
            # Build base query
            query = select(AuditLog)
            count_query = select(func.count(AuditLog.id))
            
            # Apply filters
            filters = []
            
            if entity_type:
                filters.append(AuditLog.entity_type == entity_type)
            
            if action:
                filters.append(AuditLog.action == action)
            
            if user_id:
                filters.append(AuditLog.user_id == user_id)
            
            if case_id:
                filters.append(AuditLog.case_id == case_id)
            
            if start_date:
                filters.append(AuditLog.timestamp >= start_date)
            
            if end_date:
                filters.append(AuditLog.timestamp <= end_date)
            
            if filters:
                query = query.where(and_(*filters))
                count_query = count_query.where(and_(*filters))
            
            # Get total count
            count_result = await self.db.execute(count_query)
            total_count = count_result.scalar()
            
            # Apply ordering, limit, and offset
            query = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
            
            # Execute query
            result = await self.db.execute(query)
            audit_logs = list(result.scalars().all())
            
            return audit_logs, total_count
            
        except Exception as e:
            logger.error("Failed to search audit logs", error=str(e))
            raise CaseManagementException(f"Failed to search audit logs: {str(e)}")