"""
Integration service for external system connectivity
Provides comprehensive API integration capabilities
"""

import uuid
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
import structlog
import httpx
import hashlib
import hmac

from core.config import settings
from core.exceptions import CaseManagementException
from models.case import Case
from models.document import Document
from models.timeline import TimelineEvent
from models.media import MediaEvidence
from models.forensic import ForensicSource
from services.case_service import CaseService
from services.document_service import DocumentService
from services.timeline_service import TimelineService

logger = structlog.get_logger()

class IntegrationService:
    """Service for external system integration"""
    
    def __init__(self):
        self.case_service = CaseService()
        self.document_service = DocumentService()
        self.timeline_service = TimelineService()
        self.webhook_configs = {}
        self.sync_operations = {}
        self.api_keys = {}
        self.start_time = datetime.utcnow()
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get integration API health status
        
        Returns:
            Dictionary with health information
        """
        try:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            
            # Check dependent services
            services_status = {
                "database": "healthy",  # Would check actual DB connection
                "s3": "healthy",       # Would check S3 connectivity
                "redis": "healthy",    # Would check Redis connectivity
                "aws_services": "healthy"  # Would check AWS services
            }
            
            # Determine overall status
            overall_status = "active"
            if any(status != "healthy" for status in services_status.values()):
                overall_status = "error"
            
            health_data = {
                "status": overall_status,
                "version": "1.0.0",
                "timestamp": datetime.utcnow(),
                "services": services_status,
                "uptime_seconds": int(uptime)
            }
            
            logger.info("Health status checked", status=overall_status)
            return health_data
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {
                "status": "error",
                "version": "1.0.0",
                "timestamp": datetime.utcnow(),
                "services": {"error": str(e)},
                "uptime_seconds": 0
            }
    
    async def get_usage_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get integration usage statistics
        
        Args:
            days: Number of days for statistics
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            # In a real implementation, this would query actual usage data
            # For now, return mock statistics
            
            total_requests = days * 100  # Mock data
            successful_requests = int(total_requests * 0.95)
            failed_requests = total_requests - successful_requests
            
            stats = {
                "period_days": days,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "average_response_time_ms": 150.5,
                "top_endpoints": [
                    {"endpoint": "/api/v1/integrations/cases", "requests": 500},
                    {"endpoint": "/api/v1/integrations/documents", "requests": 300},
                    {"endpoint": "/api/v1/integrations/timeline", "requests": 200}
                ],
                "error_rate_percent": round((failed_requests / total_requests) * 100, 2)
            }
            
            logger.info("Usage statistics generated", days=days)
            return stats
            
        except Exception as e:
            logger.error("Usage statistics generation failed", error=str(e))
            raise CaseManagementException(f"Failed to generate statistics: {str(e)}")
    
    async def get_cases_for_integration(
        self,
        db: Session,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        case_type: Optional[str] = None,
        updated_since: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get cases formatted for external integration
        
        Args:
            db: Database session
            limit: Maximum number of cases to return
            offset: Number of cases to skip
            status: Filter by case status
            case_type: Filter by case type
            updated_since: ISO timestamp for incremental sync
            
        Returns:
            List of case dictionaries
        """
        try:
            query = db.query(Case)
            
            # Apply filters
            if status:
                query = query.filter(Case.status == status)
            
            if case_type:
                query = query.filter(Case.case_type == case_type)
            
            if updated_since:
                updated_date = datetime.fromisoformat(updated_since.replace('Z', '+00:00'))
                query = query.filter(Case.updated_at >= updated_date)
            
            # Apply pagination and ordering
            cases = query.order_by(desc(Case.updated_at)).offset(offset).limit(limit).all()
            
            # Format cases for integration
            formatted_cases = []
            for case in cases:
                case_data = {
                    "id": str(case.id),
                    "case_number": case.case_number,
                    "title": case.title,
                    "description": case.description,
                    "case_type": case.case_type,
                    "status": case.status,
                    "client_id": case.client_id,
                    "assigned_attorney": case.assigned_attorney,
                    "priority": getattr(case, 'priority', 'medium'),
                    "metadata": case.metadata or {},
                    "created_at": case.created_at,
                    "updated_at": case.updated_at
                }
                formatted_cases.append(case_data)
            
            logger.info("Cases retrieved for integration", 
                       count=len(formatted_cases),
                       limit=limit,
                       offset=offset)
            
            return formatted_cases
            
        except Exception as e:
            logger.error("Case integration retrieval failed", error=str(e))
            raise CaseManagementException(f"Failed to retrieve cases: {str(e)}")
    
    async def get_case_details_for_integration(
        self,
        db: Session,
        case_id: str,
        include_documents: bool = False,
        include_timeline: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed case information for integration
        
        Args:
            db: Database session
            case_id: Case ID
            include_documents: Include document metadata
            include_timeline: Include timeline events
            
        Returns:
            Case dictionary with optional related data
        """
        try:
            case = db.query(Case).filter(Case.id == case_id).first()
            
            if not case:
                return None
            
            case_data = {
                "id": str(case.id),
                "case_number": case.case_number,
                "title": case.title,
                "description": case.description,
                "case_type": case.case_type,
                "status": case.status,
                "client_id": case.client_id,
                "assigned_attorney": case.assigned_attorney,
                "priority": getattr(case, 'priority', 'medium'),
                "metadata": case.metadata or {},
                "created_at": case.created_at,
                "updated_at": case.updated_at
            }
            
            # Include documents if requested
            if include_documents:
                documents = db.query(Document).filter(Document.case_id == case_id).all()
                case_data["documents"] = [
                    {
                        "id": str(doc.id),
                        "filename": doc.filename,
                        "file_type": doc.file_type,
                        "file_size": doc.file_size,
                        "created_at": doc.created_at
                    }
                    for doc in documents
                ]
            
            # Include timeline if requested
            if include_timeline:
                timeline_events = db.query(TimelineEvent).filter(
                    TimelineEvent.case_id == case_id
                ).order_by(TimelineEvent.event_date).all()
                
                case_data["timeline_events"] = [
                    {
                        "id": str(event.id),
                        "title": event.title,
                        "event_type": event.event_type,
                        "event_date": event.event_date,
                        "created_at": event.created_at
                    }
                    for event in timeline_events
                ]
            
            logger.info("Case details retrieved for integration", 
                       case_id=case_id,
                       include_documents=include_documents,
                       include_timeline=include_timeline)
            
            return case_data
            
        except Exception as e:
            logger.error("Case detail retrieval failed", 
                        case_id=case_id, 
                        error=str(e))
            raise CaseManagementException(f"Failed to retrieve case details: {str(e)}")
    
    async def create_case_from_integration(
        self,
        db: Session,
        case_data: Dict[str, Any],
        created_by: str
    ) -> Dict[str, Any]:
        """
        Create case from external integration
        
        Args:
            db: Database session
            case_data: Case data from integration
            created_by: User ID creating the case
            
        Returns:
            Created case dictionary
        """
        try:
            # Use the case service to create the case
            created_case = await self.case_service.create_case(
                db=db,
                case_data=case_data,
                created_by=created_by
            )
            
            # Trigger webhook if configured
            await self._trigger_webhook("case.created", {
                "case_id": str(created_case.id),
                "case_number": created_case.case_number,
                "created_by": created_by
            })
            
            # Format response
            case_response = {
                "id": str(created_case.id),
                "case_number": created_case.case_number,
                "title": created_case.title,
                "description": created_case.description,
                "case_type": created_case.case_type,
                "status": created_case.status,
                "created_at": created_case.created_at,
                "updated_at": created_case.updated_at
            }
            
            logger.info("Case created from integration", 
                       case_id=str(created_case.id),
                       created_by=created_by)
            
            return case_response
            
        except Exception as e:
            logger.error("Case creation from integration failed", error=str(e))
            raise CaseManagementException(f"Failed to create case: {str(e)}")
    
    async def update_case_from_integration(
        self,
        db: Session,
        case_id: str,
        case_data: Dict[str, Any],
        updated_by: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update case from external integration
        
        Args:
            db: Database session
            case_id: Case ID to update
            case_data: Updated case data
            updated_by: User ID updating the case
            
        Returns:
            Updated case dictionary or None if not found
        """
        try:
            # Use the case service to update the case
            updated_case = await self.case_service.update_case(
                db=db,
                case_id=case_id,
                case_data=case_data,
                updated_by=updated_by
            )
            
            if not updated_case:
                return None
            
            # Trigger webhook if configured
            await self._trigger_webhook("case.updated", {
                "case_id": case_id,
                "updated_by": updated_by,
                "changes": list(case_data.keys())
            })
            
            # Format response
            case_response = {
                "id": str(updated_case.id),
                "case_number": updated_case.case_number,
                "title": updated_case.title,
                "description": updated_case.description,
                "case_type": updated_case.case_type,
                "status": updated_case.status,
                "created_at": updated_case.created_at,
                "updated_at": updated_case.updated_at
            }
            
            logger.info("Case updated from integration", 
                       case_id=case_id,
                       updated_by=updated_by)
            
            return case_response
            
        except Exception as e:
            logger.error("Case update from integration failed", 
                        case_id=case_id, 
                        error=str(e))
            raise CaseManagementException(f"Failed to update case: {str(e)}")
    
    async def get_case_documents_for_integration(
        self,
        db: Session,
        case_id: str,
        limit: int = 100,
        offset: int = 0,
        document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get case documents for integration
        
        Args:
            db: Database session
            case_id: Case ID
            limit: Maximum number of documents
            offset: Number of documents to skip
            document_type: Filter by document type
            
        Returns:
            List of document dictionaries
        """
        try:
            query = db.query(Document).filter(Document.case_id == case_id)
            
            if document_type:
                query = query.filter(Document.document_type == document_type)
            
            documents = query.order_by(desc(Document.created_at)).offset(offset).limit(limit).all()
            
            formatted_documents = []
            for doc in documents:
                doc_data = {
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "file_size": doc.file_size,
                    "file_type": doc.file_type,
                    "case_id": str(doc.case_id),
                    "document_type": doc.document_type,
                    "s3_key": doc.s3_key,
                    "analysis_status": getattr(doc, 'analysis_status', None),
                    "created_at": doc.created_at,
                    "updated_at": doc.updated_at
                }
                formatted_documents.append(doc_data)
            
            logger.info("Case documents retrieved for integration", 
                       case_id=case_id,
                       count=len(formatted_documents))
            
            return formatted_documents
            
        except Exception as e:
            logger.error("Document integration retrieval failed", 
                        case_id=case_id, 
                        error=str(e))
            raise CaseManagementException(f"Failed to retrieve documents: {str(e)}")
    
    async def get_case_timeline_for_integration(
        self,
        db: Session,
        case_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get case timeline for integration
        
        Args:
            db: Database session
            case_id: Case ID
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            event_type: Filter by event type
            
        Returns:
            List of timeline event dictionaries
        """
        try:
            query = db.query(TimelineEvent).filter(TimelineEvent.case_id == case_id)
            
            if start_date:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(TimelineEvent.event_date >= start_dt)
            
            if end_date:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(TimelineEvent.event_date <= end_dt)
            
            if event_type:
                query = query.filter(TimelineEvent.event_type == event_type)
            
            events = query.order_by(TimelineEvent.event_date).all()
            
            formatted_events = []
            for event in events:
                event_data = {
                    "id": str(event.id),
                    "case_id": str(event.case_id),
                    "title": event.title,
                    "description": event.description,
                    "event_type": event.event_type,
                    "event_date": event.event_date,
                    "location": event.location,
                    "participants": event.participants or [],
                    "metadata": event.metadata or {},
                    "created_at": event.created_at,
                    "updated_at": event.updated_at
                }
                formatted_events.append(event_data)
            
            logger.info("Case timeline retrieved for integration", 
                       case_id=case_id,
                       event_count=len(formatted_events))
            
            return formatted_events
            
        except Exception as e:
            logger.error("Timeline integration retrieval failed", 
                        case_id=case_id, 
                        error=str(e))
            raise CaseManagementException(f"Failed to retrieve timeline: {str(e)}")
    
    async def create_timeline_event_from_integration(
        self,
        db: Session,
        case_id: str,
        event_data: Dict[str, Any],
        created_by: str
    ) -> Dict[str, Any]:
        """
        Create timeline event from external integration
        
        Args:
            db: Database session
            case_id: Case ID
            event_data: Event data from integration
            created_by: User ID creating the event
            
        Returns:
            Created event dictionary
        """
        try:
            # Add case_id to event data
            event_data["case_id"] = case_id
            
            # Use the timeline service to create the event
            created_event = await self.timeline_service.create_timeline_event(
                db=db,
                event_data=event_data,
                created_by=created_by
            )
            
            # Trigger webhook if configured
            await self._trigger_webhook("timeline.event.created", {
                "case_id": case_id,
                "event_id": str(created_event.id),
                "created_by": created_by
            })
            
            # Format response
            event_response = {
                "id": str(created_event.id),
                "case_id": str(created_event.case_id),
                "title": created_event.title,
                "description": created_event.description,
                "event_type": created_event.event_type,
                "event_date": created_event.event_date,
                "created_at": created_event.created_at,
                "updated_at": created_event.updated_at
            }
            
            logger.info("Timeline event created from integration", 
                       case_id=case_id,
                       event_id=str(created_event.id),
                       created_by=created_by)
            
            return event_response
            
        except Exception as e:
            logger.error("Timeline event creation from integration failed", 
                        case_id=case_id, 
                        error=str(e))
            raise CaseManagementException(f"Failed to create timeline event: {str(e)}")
    
    async def get_webhook_configurations(self) -> List[Dict[str, Any]]:
        """
        Get all webhook configurations
        
        Returns:
            List of webhook configuration dictionaries
        """
        try:
            # In a real implementation, this would query from database
            # For now, return stored configurations
            webhooks = []
            for webhook_id, config in self.webhook_configs.items():
                webhook_data = {
                    "id": webhook_id,
                    "name": config["name"],
                    "url": config["url"],
                    "events": config["events"],
                    "active": config.get("active", True),
                    "created_at": config.get("created_at", datetime.utcnow()),
                    "updated_at": config.get("updated_at", datetime.utcnow())
                }
                webhooks.append(webhook_data)
            
            logger.info("Webhook configurations retrieved", count=len(webhooks))
            return webhooks
            
        except Exception as e:
            logger.error("Webhook configuration retrieval failed", error=str(e))
            raise CaseManagementException(f"Failed to retrieve webhooks: {str(e)}")
    
    async def create_webhook_configuration(
        self,
        webhook_data: Dict[str, Any],
        created_by: str
    ) -> Dict[str, Any]:
        """
        Create new webhook configuration
        
        Args:
            webhook_data: Webhook configuration data
            created_by: User ID creating the webhook
            
        Returns:
            Created webhook configuration dictionary
        """
        try:
            webhook_id = str(uuid.uuid4())
            
            config = {
                "id": webhook_id,
                "name": webhook_data["name"],
                "url": webhook_data["url"],
                "events": webhook_data["events"],
                "active": webhook_data.get("active", True),
                "secret": webhook_data.get("secret"),
                "headers": webhook_data.get("headers", {}),
                "retry_count": webhook_data.get("retry_count", 3),
                "timeout_seconds": webhook_data.get("timeout_seconds", 30),
                "created_by": created_by,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Store configuration
            self.webhook_configs[webhook_id] = config
            
            logger.info("Webhook configuration created", 
                       webhook_id=webhook_id,
                       created_by=created_by)
            
            return config
            
        except Exception as e:
            logger.error("Webhook configuration creation failed", error=str(e))
            raise CaseManagementException(f"Failed to create webhook: {str(e)}")
    
    async def delete_webhook_configuration(self, webhook_id: str) -> bool:
        """
        Delete webhook configuration
        
        Args:
            webhook_id: Webhook ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            if webhook_id in self.webhook_configs:
                del self.webhook_configs[webhook_id]
                logger.info("Webhook configuration deleted", webhook_id=webhook_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error("Webhook configuration deletion failed", 
                        webhook_id=webhook_id, 
                        error=str(e))
            raise CaseManagementException(f"Failed to delete webhook: {str(e)}")
    
    async def batch_create_cases(
        self,
        db: Session,
        cases_data: List[Dict[str, Any]],
        created_by: str
    ) -> List[Dict[str, Any]]:
        """
        Batch create multiple cases
        
        Args:
            db: Database session
            cases_data: List of case data dictionaries
            created_by: User ID creating the cases
            
        Returns:
            List of created case dictionaries
        """
        try:
            created_cases = []
            
            for case_data in cases_data:
                try:
                    created_case = await self.create_case_from_integration(
                        db=db,
                        case_data=case_data,
                        created_by=created_by
                    )
                    created_cases.append(created_case)
                    
                except Exception as e:
                    logger.error("Batch case creation failed for item", 
                                case_data=case_data, 
                                error=str(e))
                    # Continue with other cases
                    continue
            
            logger.info("Batch case creation completed", 
                       total_requested=len(cases_data),
                       successful=len(created_cases),
                       created_by=created_by)
            
            return created_cases
            
        except Exception as e:
            logger.error("Batch case creation failed", error=str(e))
            raise CaseManagementException(f"Batch case creation failed: {str(e)}")
    
    async def get_sync_status(self, sync_id: str) -> Optional[Dict[str, Any]]:
        """
        Get synchronization operation status
        
        Args:
            sync_id: Synchronization ID
            
        Returns:
            Sync status dictionary or None if not found
        """
        try:
            if sync_id in self.sync_operations:
                return self.sync_operations[sync_id]
            
            return None
            
        except Exception as e:
            logger.error("Sync status retrieval failed", 
                        sync_id=sync_id, 
                        error=str(e))
            raise CaseManagementException(f"Failed to get sync status: {str(e)}")
    
    async def _trigger_webhook(self, event_type: str, payload: Dict[str, Any]):
        """
        Trigger webhook notifications for configured events
        
        Args:
            event_type: Type of event that occurred
            payload: Event payload data
        """
        try:
            for webhook_id, config in self.webhook_configs.items():
                if not config.get("active", True):
                    continue
                
                if event_type not in config.get("events", []):
                    continue
                
                # Prepare webhook payload
                webhook_payload = {
                    "event": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": payload
                }
                
                # Send webhook asynchronously
                asyncio.create_task(self._send_webhook(config, webhook_payload))
                
        except Exception as e:
            logger.error("Webhook trigger failed", 
                        event_type=event_type, 
                        error=str(e))
    
    async def _send_webhook(self, config: Dict[str, Any], payload: Dict[str, Any]):
        """
        Send webhook HTTP request
        
        Args:
            config: Webhook configuration
            payload: Payload to send
        """
        try:
            headers = config.get("headers", {}).copy()
            headers["Content-Type"] = "application/json"
            
            # Add signature if secret is configured
            if config.get("secret"):
                signature = self._generate_webhook_signature(
                    config["secret"], 
                    json.dumps(payload)
                )
                headers["X-Webhook-Signature"] = signature
            
            timeout = config.get("timeout_seconds", 30)
            retry_count = config.get("retry_count", 3)
            
            async with httpx.AsyncClient() as client:
                for attempt in range(retry_count + 1):
                    try:
                        response = await client.post(
                            config["url"],
                            json=payload,
                            headers=headers,
                            timeout=timeout
                        )
                        
                        if response.status_code < 400:
                            logger.info("Webhook sent successfully", 
                                       webhook_id=config["id"],
                                       status_code=response.status_code)
                            break
                        else:
                            logger.warning("Webhook failed", 
                                          webhook_id=config["id"],
                                          status_code=response.status_code,
                                          attempt=attempt + 1)
                            
                    except Exception as e:
                        logger.error("Webhook request failed", 
                                    webhook_id=config["id"],
                                    attempt=attempt + 1,
                                    error=str(e))
                        
                        if attempt < retry_count:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        
        except Exception as e:
            logger.error("Webhook sending failed", 
                        webhook_id=config.get("id"),
                        error=str(e))
    
    def _generate_webhook_signature(self, secret: str, payload: str) -> str:
        """
        Generate webhook signature for payload verification
        
        Args:
            secret: Webhook secret
            payload: JSON payload string
            
        Returns:
            HMAC signature
        """
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"