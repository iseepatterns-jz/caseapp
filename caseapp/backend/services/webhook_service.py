"""
Webhook Notification Service
Handles webhook delivery and management
Validates Requirements 10.6
"""

import asyncio
import json
import uuid
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
import logging
from dataclasses import dataclass, asdict
import hashlib
import hmac

logger = logging.getLogger(__name__)

class WebhookEvent(str, Enum):
    """Webhook event types"""
    CASE_CREATED = "case.created"
    CASE_UPDATED = "case.updated"
    CASE_CLOSED = "case.closed"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_ANALYZED = "document.analyzed"
    TIMELINE_EVENT_CREATED = "timeline.event.created"
    TIMELINE_EVENT_UPDATED = "timeline.event.updated"
    MEDIA_PROCESSED = "media.processed"
    FORENSIC_ANALYSIS_COMPLETED = "forensic.analysis.completed"
    EXPORT_GENERATED = "export.generated"
    COLLABORATION_INVITED = "collaboration.invited"
    AI_INSIGHT_GENERATED = "ai.insight.generated"

class WebhookStatus(str, Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

@dataclass
class WebhookEndpoint:
    """Webhook endpoint configuration"""
    id: str
    name: str
    url: str
    events: List[WebhookEvent]
    secret: Optional[str] = None
    active: bool = True
    max_retries: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 30
    headers: Optional[Dict[str, str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class WebhookDelivery:
    """Webhook delivery record"""
    id: str
    endpoint_id: str
    event_type: WebhookEvent
    payload: Dict[str, Any]
    status: WebhookStatus
    created_at: datetime
    scheduled_at: datetime
    delivered_at: Optional[datetime] = None
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None

class WebhookService:
    """Service for webhook management and delivery"""
    
    def __init__(self, background_job_service=None):
        self.endpoints: Dict[str, WebhookEndpoint] = {}
        self.deliveries: Dict[str, WebhookDelivery] = {}
        self.background_job_service = background_job_service
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def create_endpoint(
        self,
        name: str,
        url: str,
        events: List[WebhookEvent],
        secret: Optional[str] = None,
        max_retries: int = 3,
        retry_delay_seconds: int = 60,
        timeout_seconds: int = 30,
        headers: Optional[Dict[str, str]] = None
    ) -> WebhookEndpoint:
        """
        Create a new webhook endpoint
        
        Args:
            name: Endpoint name
            url: Webhook URL
            events: List of events to subscribe to
            secret: Optional secret for signature verification
            max_retries: Maximum retry attempts
            retry_delay_seconds: Delay between retries
            timeout_seconds: Request timeout
            headers: Additional headers to send
        
        Returns:
            Created webhook endpoint
        """
        endpoint_id = str(uuid.uuid4())
        
        endpoint = WebhookEndpoint(
            id=endpoint_id,
            name=name,
            url=url,
            events=events,
            secret=secret,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            timeout_seconds=timeout_seconds,
            headers=headers or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.endpoints[endpoint_id] = endpoint
        
        logger.info(f"Created webhook endpoint {endpoint_id}: {name} -> {url}")
        return endpoint
    
    async def update_endpoint(
        self,
        endpoint_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        events: Optional[List[WebhookEvent]] = None,
        secret: Optional[str] = None,
        active: Optional[bool] = None,
        max_retries: Optional[int] = None,
        retry_delay_seconds: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[WebhookEndpoint]:
        """
        Update an existing webhook endpoint
        
        Args:
            endpoint_id: Endpoint identifier
            name: New name
            url: New URL
            events: New event list
            secret: New secret
            active: Active status
            max_retries: New max retries
            retry_delay_seconds: New retry delay
            timeout_seconds: New timeout
            headers: New headers
        
        Returns:
            Updated endpoint or None if not found
        """
        endpoint = self.endpoints.get(endpoint_id)
        if not endpoint:
            return None
        
        # Update fields if provided
        if name is not None:
            endpoint.name = name
        if url is not None:
            endpoint.url = url
        if events is not None:
            endpoint.events = events
        if secret is not None:
            endpoint.secret = secret
        if active is not None:
            endpoint.active = active
        if max_retries is not None:
            endpoint.max_retries = max_retries
        if retry_delay_seconds is not None:
            endpoint.retry_delay_seconds = retry_delay_seconds
        if timeout_seconds is not None:
            endpoint.timeout_seconds = timeout_seconds
        if headers is not None:
            endpoint.headers = headers
        
        endpoint.updated_at = datetime.utcnow()
        
        logger.info(f"Updated webhook endpoint {endpoint_id}")
        return endpoint
    
    async def delete_endpoint(self, endpoint_id: str) -> bool:
        """
        Delete a webhook endpoint
        
        Args:
            endpoint_id: Endpoint identifier
        
        Returns:
            True if deleted successfully
        """
        if endpoint_id in self.endpoints:
            del self.endpoints[endpoint_id]
            logger.info(f"Deleted webhook endpoint {endpoint_id}")
            return True
        return False
    
    async def get_endpoint(self, endpoint_id: str) -> Optional[WebhookEndpoint]:
        """
        Get webhook endpoint by ID
        
        Args:
            endpoint_id: Endpoint identifier
        
        Returns:
            Webhook endpoint or None if not found
        """
        return self.endpoints.get(endpoint_id)
    
    async def list_endpoints(self, active_only: bool = False) -> List[WebhookEndpoint]:
        """
        List all webhook endpoints
        
        Args:
            active_only: Only return active endpoints
        
        Returns:
            List of webhook endpoints
        """
        endpoints = list(self.endpoints.values())
        
        if active_only:
            endpoints = [ep for ep in endpoints if ep.active]
        
        return endpoints
    
    async def send_webhook(
        self,
        event_type: WebhookEvent,
        payload: Dict[str, Any],
        endpoint_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Send webhook notification for an event
        
        Args:
            event_type: Type of event
            payload: Event payload data
            endpoint_ids: Specific endpoints to send to (None for all subscribed)
        
        Returns:
            List of delivery IDs
        """
        # Find endpoints that should receive this event
        target_endpoints = []
        
        for endpoint in self.endpoints.values():
            if not endpoint.active:
                continue
            
            # Check if endpoint is subscribed to this event
            if event_type not in endpoint.events:
                continue
            
            # Check if endpoint is in the specific list (if provided)
            if endpoint_ids and endpoint.id not in endpoint_ids:
                continue
            
            target_endpoints.append(endpoint)
        
        # Create deliveries for each target endpoint
        delivery_ids = []
        
        for endpoint in target_endpoints:
            delivery_id = await self._create_delivery(endpoint, event_type, payload)
            delivery_ids.append(delivery_id)
        
        logger.info(f"Created {len(delivery_ids)} webhook deliveries for event {event_type}")
        return delivery_ids
    
    async def _create_delivery(
        self,
        endpoint: WebhookEndpoint,
        event_type: WebhookEvent,
        payload: Dict[str, Any]
    ) -> str:
        """
        Create a webhook delivery record
        
        Args:
            endpoint: Target endpoint
            event_type: Event type
            payload: Event payload
        
        Returns:
            Delivery ID
        """
        delivery_id = str(uuid.uuid4())
        
        # Add metadata to payload
        enhanced_payload = {
            "id": delivery_id,
            "event": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload
        }
        
        delivery = WebhookDelivery(
            id=delivery_id,
            endpoint_id=endpoint.id,
            event_type=event_type,
            payload=enhanced_payload,
            status=WebhookStatus.PENDING,
            created_at=datetime.utcnow(),
            scheduled_at=datetime.utcnow()
        )
        
        self.deliveries[delivery_id] = delivery
        
        # Schedule delivery using background job service
        if self.background_job_service:
            await self.background_job_service.submit_job(
                task_name="webhook_delivery",
                args=[delivery_id],
                priority="normal",
                max_retries=endpoint.max_retries,
                retry_delay_seconds=endpoint.retry_delay_seconds
            )
        else:
            # Deliver immediately if no background service
            asyncio.create_task(self._deliver_webhook(delivery_id))
        
        return delivery_id
    
    async def _deliver_webhook(self, delivery_id: str) -> bool:
        """
        Deliver a webhook
        
        Args:
            delivery_id: Delivery identifier
        
        Returns:
            True if delivered successfully
        """
        delivery = self.deliveries.get(delivery_id)
        if not delivery:
            logger.error(f"Delivery {delivery_id} not found")
            return False
        
        endpoint = self.endpoints.get(delivery.endpoint_id)
        if not endpoint:
            logger.error(f"Endpoint {delivery.endpoint_id} not found for delivery {delivery_id}")
            delivery.status = WebhookStatus.FAILED
            delivery.error_message = "Endpoint not found"
            return False
        
        if not endpoint.active:
            logger.info(f"Endpoint {endpoint.id} is inactive, cancelling delivery {delivery_id}")
            delivery.status = WebhookStatus.CANCELLED
            return False
        
        delivery.status = WebhookStatus.PENDING
        
        try:
            # Prepare request
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "CourtCaseManagement-Webhook/1.0",
                **endpoint.headers
            }
            
            # Add signature if secret is configured
            if endpoint.secret:
                payload_str = json.dumps(delivery.payload, sort_keys=True)
                signature = hmac.new(
                    endpoint.secret.encode(),
                    payload_str.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"
            
            # Create session if not exists
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Send webhook
            async with self.session.post(
                endpoint.url,
                json=delivery.payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=endpoint.timeout_seconds)
            ) as response:
                delivery.response_code = response.status
                delivery.response_body = await response.text()
                delivery.delivered_at = datetime.utcnow()
                
                if 200 <= response.status < 300:
                    delivery.status = WebhookStatus.DELIVERED
                    logger.info(f"Webhook delivered successfully: {delivery_id} -> {endpoint.url}")
                    return True
                else:
                    delivery.status = WebhookStatus.FAILED
                    delivery.error_message = f"HTTP {response.status}: {delivery.response_body}"
                    logger.error(f"Webhook delivery failed: {delivery_id} -> {endpoint.url} (HTTP {response.status})")
                    return False
        
        except asyncio.TimeoutError:
            delivery.status = WebhookStatus.FAILED
            delivery.error_message = f"Request timeout after {endpoint.timeout_seconds} seconds"
            logger.error(f"Webhook delivery timeout: {delivery_id} -> {endpoint.url}")
            return False
        
        except Exception as e:
            delivery.status = WebhookStatus.FAILED
            delivery.error_message = str(e)
            logger.error(f"Webhook delivery error: {delivery_id} -> {endpoint.url}: {str(e)}")
            return False
    
    async def retry_delivery(self, delivery_id: str) -> bool:
        """
        Retry a failed webhook delivery
        
        Args:
            delivery_id: Delivery identifier
        
        Returns:
            True if retry initiated
        """
        delivery = self.deliveries.get(delivery_id)
        if not delivery or delivery.status != WebhookStatus.FAILED:
            return False
        
        endpoint = self.endpoints.get(delivery.endpoint_id)
        if not endpoint:
            return False
        
        if delivery.retry_count >= endpoint.max_retries:
            logger.info(f"Max retries reached for delivery {delivery_id}")
            return False
        
        delivery.retry_count += 1
        delivery.status = WebhookStatus.RETRYING
        delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=endpoint.retry_delay_seconds)
        
        # Schedule retry
        if self.background_job_service:
            await self.background_job_service.submit_job(
                task_name="webhook_delivery",
                args=[delivery_id],
                priority="normal"
            )
        else:
            # Wait and retry
            await asyncio.sleep(endpoint.retry_delay_seconds)
            asyncio.create_task(self._deliver_webhook(delivery_id))
        
        logger.info(f"Scheduled retry {delivery.retry_count} for delivery {delivery_id}")
        return True
    
    async def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """
        Get webhook delivery by ID
        
        Args:
            delivery_id: Delivery identifier
        
        Returns:
            Webhook delivery or None if not found
        """
        return self.deliveries.get(delivery_id)
    
    async def list_deliveries(
        self,
        endpoint_id: Optional[str] = None,
        event_type: Optional[WebhookEvent] = None,
        status: Optional[WebhookStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[WebhookDelivery]:
        """
        List webhook deliveries with filtering
        
        Args:
            endpoint_id: Filter by endpoint
            event_type: Filter by event type
            status: Filter by status
            limit: Maximum results
            offset: Results offset
        
        Returns:
            List of webhook deliveries
        """
        deliveries = list(self.deliveries.values())
        
        # Apply filters
        if endpoint_id:
            deliveries = [d for d in deliveries if d.endpoint_id == endpoint_id]
        
        if event_type:
            deliveries = [d for d in deliveries if d.event_type == event_type]
        
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        # Sort by creation time (newest first)
        deliveries.sort(key=lambda d: d.created_at, reverse=True)
        
        # Apply pagination
        return deliveries[offset:offset + limit]
    
    async def get_delivery_statistics(
        self,
        endpoint_id: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get webhook delivery statistics
        
        Args:
            endpoint_id: Filter by endpoint
            hours: Time period for statistics
        
        Returns:
            Statistics dictionary
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Filter deliveries
        deliveries = [
            d for d in self.deliveries.values()
            if d.created_at >= cutoff_time and (not endpoint_id or d.endpoint_id == endpoint_id)
        ]
        
        total_deliveries = len(deliveries)
        status_counts = {}
        event_counts = {}
        endpoint_counts = {}
        
        successful_deliveries = 0
        total_retry_count = 0
        
        for delivery in deliveries:
            # Status counts
            status = delivery.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Event counts
            event = delivery.event_type.value
            event_counts[event] = event_counts.get(event, 0) + 1
            
            # Endpoint counts
            endpoint_counts[delivery.endpoint_id] = endpoint_counts.get(delivery.endpoint_id, 0) + 1
            
            # Success tracking
            if delivery.status == WebhookStatus.DELIVERED:
                successful_deliveries += 1
            
            total_retry_count += delivery.retry_count
        
        success_rate = 0
        if total_deliveries > 0:
            success_rate = (successful_deliveries / total_deliveries) * 100
        
        average_retries = 0
        if total_deliveries > 0:
            average_retries = total_retry_count / total_deliveries
        
        return {
            "period_hours": hours,
            "total_deliveries": total_deliveries,
            "success_rate_percent": round(success_rate, 2),
            "status_breakdown": status_counts,
            "event_breakdown": event_counts,
            "endpoint_breakdown": endpoint_counts,
            "average_retries": round(average_retries, 2),
            "total_endpoints": len(self.endpoints),
            "active_endpoints": len([ep for ep in self.endpoints.values() if ep.active])
        }
    
    async def test_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """
        Test a webhook endpoint with a ping event
        
        Args:
            endpoint_id: Endpoint identifier
        
        Returns:
            Test result
        """
        endpoint = self.endpoints.get(endpoint_id)
        if not endpoint:
            return {"success": False, "error": "Endpoint not found"}
        
        # Create test payload
        test_payload = {
            "test": True,
            "endpoint_id": endpoint_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "This is a test webhook from Court Case Management System"
        }
        
        # Create temporary delivery for testing
        delivery_id = str(uuid.uuid4())
        delivery = WebhookDelivery(
            id=delivery_id,
            endpoint_id=endpoint_id,
            event_type=WebhookEvent.CASE_CREATED,  # Use any event type for testing
            payload=test_payload,
            status=WebhookStatus.PENDING,
            created_at=datetime.utcnow(),
            scheduled_at=datetime.utcnow()
        )
        
        self.deliveries[delivery_id] = delivery
        
        # Attempt delivery
        success = await self._deliver_webhook(delivery_id)
        
        # Return test result
        result = {
            "success": success,
            "delivery_id": delivery_id,
            "response_code": delivery.response_code,
            "response_body": delivery.response_body,
            "error_message": delivery.error_message,
            "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None
        }
        
        return result