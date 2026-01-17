"""
Notification service for collaboration events and external integrations
"""

import asyncio
import json
import hmac
import hashlib
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload
import aiohttp
import uuid

from core.database import AsyncSessionLocal
from models.external_sharing import (
    CollaborationNotification, NotificationType, NotificationChannel,
    WebhookEndpoint, WebhookDelivery
)
from models.timeline import CaseTimeline, TimelineEvent, TimelineComment
from models.user import User

logger = structlog.get_logger()

class NotificationService:
    """Service for managing collaboration notifications and webhooks"""
    
    def __init__(self):
        self.webhook_session = None
        self._initialize_webhook_client()
    
    def _initialize_webhook_client(self):
        """Initialize HTTP client for webhook deliveries"""
        timeout = aiohttp.ClientTimeout(total=30)
        self.webhook_session = aiohttp.ClientSession(timeout=timeout)
    
    async def create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        timeline_id: Optional[str] = None,
        event_id: Optional[str] = None,
        comment_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        priority: str = 'normal',
        channels: Optional[List[NotificationChannel]] = None,
        created_by_id: Optional[str] = None
    ) -> CollaborationNotification:
        """Create a new collaboration notification"""
        
        if channels is None:
            channels = [NotificationChannel.IN_APP, NotificationChannel.EMAIL]
        
        async with AsyncSessionLocal() as db:
            notification = CollaborationNotification(
                user_id=user_id,
                notification_type=notification_type.value,
                title=title,
                message=message,
                timeline_id=timeline_id,
                event_id=event_id,
                comment_id=comment_id,
                data=data or {},
                priority=priority,
                channels=[channel.value for channel in channels],
                delivered_at={},
                created_by_id=created_by_id
            )
            
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
            
            logger.info("Notification created", 
                       notification_id=str(notification.id), 
                       type=notification_type.value,
                       user_id=user_id)
            
            # Trigger delivery
            await self._deliver_notification(notification)
            
            return notification
    
    async def _deliver_notification(self, notification: CollaborationNotification):
        """Deliver notification through configured channels"""
        
        delivery_results = {}
        
        for channel in notification.channels:
            try:
                if channel == NotificationChannel.EMAIL.value:
                    success = await self._deliver_email(notification)
                elif channel == NotificationChannel.IN_APP.value:
                    success = await self._deliver_in_app(notification)
                elif channel == NotificationChannel.WEBHOOK.value:
                    success = await self._deliver_webhook(notification)
                else:
                    success = False
                
                if success:
                    delivery_results[channel] = datetime.now(UTC).isoformat()
                
            except Exception as e:
                logger.error("Failed to deliver notification", 
                           notification_id=str(notification.id),
                           channel=channel, error=str(e))
        
        # Update delivery status
        if delivery_results:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(CollaborationNotification).where(
                        CollaborationNotification.id == notification.id
                    )
                )
                stored_notification = result.scalar_one_or_none()
                
                if stored_notification:
                    stored_notification.delivered_at = delivery_results
                    await db.commit()
    
    async def _deliver_email(self, notification: CollaborationNotification) -> bool:
        """Deliver notification via email"""
        # In a real implementation, this would integrate with an email service
        # like AWS SES, SendGrid, or similar
        logger.info("Email notification delivered", 
                   notification_id=str(notification.id))
        return True
    
    async def _deliver_in_app(self, notification: CollaborationNotification) -> bool:
        """Deliver in-app notification (already stored in database)"""
        # In-app notifications are delivered by storing in the database
        # The frontend polls or uses WebSocket to get new notifications
        return True
    
    async def _deliver_webhook(self, notification: CollaborationNotification) -> bool:
        """Deliver notification via webhook"""
        
        async with AsyncSessionLocal() as db:
            # Get active webhook endpoints for this event type
            result = await db.execute(
                select(WebhookEndpoint).where(
                    and_(
                        WebhookEndpoint.is_active == True,
                        WebhookEndpoint.event_types.contains([notification.notification_type])
                    )
                )
            )
            endpoints = result.scalars().all()
            
            success = True
            for endpoint in endpoints:
                try:
                    await self._send_webhook(endpoint, notification)
                except Exception as e:
                    logger.error("Webhook delivery failed", 
                               endpoint_id=str(endpoint.id), error=str(e))
                    success = False
            
            return success
    
    async def _send_webhook(self, endpoint: WebhookEndpoint, notification: CollaborationNotification):
        """Send webhook to a specific endpoint"""
        
        # Prepare webhook payload
        payload = {
            'event_type': notification.notification_type,
            'notification_id': str(notification.id),
            'timestamp': notification.created_at.isoformat(),
            'data': {
                'title': notification.title,
                'message': notification.message,
                'timeline_id': str(notification.timeline_id) if notification.timeline_id else None,
                'event_id': str(notification.event_id) if notification.event_id else None,
                'comment_id': str(notification.comment_id) if notification.comment_id else None,
                'priority': notification.priority,
                'user_id': str(notification.user_id),
                'created_by_id': str(notification.created_by_id) if notification.created_by_id else None,
                **notification.data
            }
        }
        
        # Create delivery record
        async with AsyncSessionLocal() as db:
            delivery = WebhookDelivery(
                endpoint_id=endpoint.id,
                event_type=notification.notification_type,
                payload=payload,
                status='pending'
            )
            db.add(delivery)
            await db.commit()
            await db.refresh(delivery)
        
        try:
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'CaseApp-Webhook/1.0'
            }
            
            # Add signature if secret key is configured
            if endpoint.secret_key:
                payload_str = json.dumps(payload, sort_keys=True)
                signature = hmac.new(
                    endpoint.secret_key.encode(),
                    payload_str.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers['X-CaseApp-Signature'] = f'sha256={signature}'
            
            # Send webhook
            async with self.webhook_session.post(
                endpoint.url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=endpoint.timeout_seconds)
            ) as response:
                
                response_body = await response.text()
                
                # Update delivery record
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(WebhookDelivery).where(WebhookDelivery.id == delivery.id)
                    )
                    stored_delivery = result.scalar_one()
                    
                    stored_delivery.http_status_code = response.status
                    stored_delivery.response_body = response_body[:1000]  # Limit size
                    stored_delivery.completed_at = datetime.now(UTC)
                    
                    if 200 <= response.status < 300:
                        stored_delivery.status = 'success'
                        # Update endpoint success tracking
                        endpoint.last_success_at = datetime.now(UTC)
                        endpoint.failure_count = 0
                    else:
                        stored_delivery.status = 'failed'
                        stored_delivery.error_message = f"HTTP {response.status}: {response_body[:200]}"
                        # Update endpoint failure tracking
                        endpoint.last_failure_at = datetime.now(UTC)
                        endpoint.failure_count += 1
                    
                    await db.commit()
                    
                    if stored_delivery.status == 'failed' and stored_delivery.retry_count < endpoint.retry_count:
                        # Schedule retry
                        await self._schedule_webhook_retry(stored_delivery, endpoint)
        
        except Exception as e:
            # Update delivery record with error
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(WebhookDelivery).where(WebhookDelivery.id == delivery.id)
                )
                stored_delivery = result.scalar_one()
                
                stored_delivery.status = 'failed'
                stored_delivery.error_message = str(e)[:500]
                stored_delivery.completed_at = datetime.now(UTC)
                
                # Update endpoint failure tracking
                endpoint.last_failure_at = datetime.now(UTC)
                endpoint.failure_count += 1
                
                await db.commit()
                
                if stored_delivery.retry_count < endpoint.retry_count:
                    await self._schedule_webhook_retry(stored_delivery, endpoint)
            
            raise
    
    async def _schedule_webhook_retry(self, delivery: WebhookDelivery, endpoint: WebhookEndpoint):
        """Schedule webhook retry with exponential backoff"""
        
        retry_delay = min(300, 30 * (2 ** delivery.retry_count))  # Max 5 minutes
        next_retry = datetime.now(UTC) + timedelta(seconds=retry_delay)
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == delivery.id)
            )
            stored_delivery = result.scalar_one()
            
            stored_delivery.status = 'retrying'
            stored_delivery.retry_count += 1
            stored_delivery.next_retry_at = next_retry
            
            await db.commit()
        
        logger.info("Webhook retry scheduled", 
                   delivery_id=str(delivery.id), 
                   retry_count=delivery.retry_count,
                   next_retry=next_retry.isoformat())
    
    async def notify_timeline_shared(
        self,
        timeline_id: str,
        shared_with_user_id: str,
        shared_by_user_id: str,
        permissions: Dict[str, bool],
        message: Optional[str] = None
    ):
        """Send notification when timeline is shared"""
        
        async with AsyncSessionLocal() as db:
            # Get timeline and user information
            timeline_result = await db.execute(
                select(CaseTimeline).where(CaseTimeline.id == timeline_id)
                .options(selectinload(CaseTimeline.case))
            )
            timeline = timeline_result.scalar_one()
            
            sharer_result = await db.execute(
                select(User).where(User.id == shared_by_user_id)
            )
            sharer = sharer_result.scalar_one()
        
        title = f"Timeline Shared: {timeline.title}"
        notification_message = f"{sharer.full_name} shared the timeline '{timeline.title}' with you."
        
        if message:
            notification_message += f"\n\nMessage: {message}"
        
        await self.create_notification(
            user_id=shared_with_user_id,
            notification_type=NotificationType.TIMELINE_SHARED,
            title=title,
            message=notification_message,
            timeline_id=timeline_id,
            data={
                'permissions': permissions,
                'sharer_name': sharer.full_name,
                'case_title': timeline.case.title if timeline.case else None
            },
            created_by_id=shared_by_user_id
        )
    
    async def notify_comment_added(
        self,
        comment_id: str,
        timeline_id: str,
        event_id: str,
        commenter_user_id: str,
        comment_text: str
    ):
        """Send notification when comment is added to timeline event"""
        
        async with AsyncSessionLocal() as db:
            # Get timeline collaborators who should be notified
            from models.timeline import TimelineCollaboration
            
            result = await db.execute(
                select(TimelineCollaboration, User, CaseTimeline)
                .join(User, TimelineCollaboration.user_id == User.id)
                .join(CaseTimeline, TimelineCollaboration.timeline_id == CaseTimeline.id)
                .where(
                    and_(
                        TimelineCollaboration.timeline_id == timeline_id,
                        TimelineCollaboration.receive_notifications == True,
                        TimelineCollaboration.user_id != commenter_user_id  # Don't notify the commenter
                    )
                )
            )
            
            commenter_result = await db.execute(
                select(User).where(User.id == commenter_user_id)
            )
            commenter = commenter_result.scalar_one()
            
            for collaboration, user, timeline in result:
                title = f"New Comment: {timeline.title}"
                message = f"{commenter.full_name} added a comment: \"{comment_text[:100]}{'...' if len(comment_text) > 100 else ''}\""
                
                await self.create_notification(
                    user_id=str(user.id),
                    notification_type=NotificationType.COMMENT_ADDED,
                    title=title,
                    message=message,
                    timeline_id=timeline_id,
                    event_id=event_id,
                    comment_id=comment_id,
                    data={
                        'commenter_name': commenter.full_name,
                        'comment_preview': comment_text[:200]
                    },
                    created_by_id=commenter_user_id
                )
    
    async def notify_timeline_updated(
        self,
        timeline_id: str,
        updated_by_user_id: str,
        update_type: str,
        update_details: Dict[str, Any]
    ):
        """Send notification when timeline is updated"""
        
        async with AsyncSessionLocal() as db:
            # Get timeline collaborators
            from models.timeline import TimelineCollaboration
            
            result = await db.execute(
                select(TimelineCollaboration, User, CaseTimeline)
                .join(User, TimelineCollaboration.user_id == User.id)
                .join(CaseTimeline, TimelineCollaboration.timeline_id == CaseTimeline.id)
                .where(
                    and_(
                        TimelineCollaboration.timeline_id == timeline_id,
                        TimelineCollaboration.receive_notifications == True,
                        TimelineCollaboration.user_id != updated_by_user_id
                    )
                )
            )
            
            updater_result = await db.execute(
                select(User).where(User.id == updated_by_user_id)
            )
            updater = updater_result.scalar_one()
            
            for collaboration, user, timeline in result:
                title = f"Timeline Updated: {timeline.title}"
                message = f"{updater.full_name} made changes to the timeline."
                
                await self.create_notification(
                    user_id=str(user.id),
                    notification_type=NotificationType.TIMELINE_UPDATED,
                    title=title,
                    message=message,
                    timeline_id=timeline_id,
                    data={
                        'updater_name': updater.full_name,
                        'update_type': update_type,
                        'update_details': update_details
                    },
                    created_by_id=updated_by_user_id
                )
    
    async def get_user_notifications(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user"""
        
        async with AsyncSessionLocal() as db:
            query = select(CollaborationNotification).where(
                CollaborationNotification.user_id == user_id
            )
            
            if unread_only:
                query = query.where(CollaborationNotification.is_read == False)
            
            query = query.order_by(desc(CollaborationNotification.created_at))
            query = query.limit(limit).offset(offset)
            
            result = await db.execute(query)
            notifications = result.scalars().all()
            
            return [
                {
                    'id': str(notification.id),
                    'type': notification.notification_type,
                    'title': notification.title,
                    'message': notification.message,
                    'timeline_id': str(notification.timeline_id) if notification.timeline_id else None,
                    'event_id': str(notification.event_id) if notification.event_id else None,
                    'comment_id': str(notification.comment_id) if notification.comment_id else None,
                    'data': notification.data,
                    'priority': notification.priority,
                    'is_read': notification.is_read,
                    'created_at': notification.created_at.isoformat(),
                    'read_at': notification.read_at.isoformat() if notification.read_at else None
                }
                for notification in notifications
            ]
    
    async def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CollaborationNotification).where(
                    and_(
                        CollaborationNotification.id == notification_id,
                        CollaborationNotification.user_id == user_id
                    )
                )
            )
            notification = result.scalar_one_or_none()
            
            if notification and not notification.is_read:
                notification.is_read = True
                notification.read_at = datetime.now(UTC)
                await db.commit()
                return True
            
            return False
    
    async def create_webhook_endpoint(
        self,
        url: str,
        event_types: List[str],
        secret_key: Optional[str] = None,
        timeline_ids: Optional[List[str]] = None,
        created_by_id: str = None
    ) -> WebhookEndpoint:
        """Create a new webhook endpoint"""
        
        async with AsyncSessionLocal() as db:
            endpoint = WebhookEndpoint(
                url=url,
                secret_key=secret_key,
                event_types=event_types,
                timeline_ids=timeline_ids,
                created_by_id=created_by_id
            )
            
            db.add(endpoint)
            await db.commit()
            await db.refresh(endpoint)
            
            logger.info("Webhook endpoint created", 
                       endpoint_id=str(endpoint.id), url=url)
            
            return endpoint
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.webhook_session:
            await self.webhook_session.close()