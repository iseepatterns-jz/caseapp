"""
External sharing models for timeline collaboration
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
import uuid

from core.database import Base

class ShareLinkStatus(PyEnum):
    """External share link status enumeration"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    VIEW_LIMIT_REACHED = "view_limit_reached"

class ExternalShareLink(Base):
    """External sharing link model for timeline access"""
    __tablename__ = "external_share_links"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Share token (unique identifier for the link)
    share_token = Column(String(255), nullable=False, unique=True, index=True)
    
    # Timeline association
    timeline_id = Column(UUID(as_uuid=True), ForeignKey("case_timelines.id"), nullable=False, index=True)
    
    # Share configuration
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    view_limit = Column(Integer)  # Optional view limit
    password_hash = Column(String(255))  # Optional password protection
    
    # Share settings
    allow_download = Column(Boolean, default=False)
    allow_comments = Column(Boolean, default=False)
    show_sensitive_data = Column(Boolean, default=False)
    
    # Status and usage tracking
    status = Column(String(50), default=ShareLinkStatus.ACTIVE.value)
    view_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True))
    last_accessed_ip = Column(String(45))  # IPv4 or IPv6
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    revoked_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    revoked_at = Column(DateTime(timezone=True))
    
    # Relationships
    timeline = relationship("CaseTimeline")
    creator = relationship("User", foreign_keys=[created_by_id])
    revoker = relationship("User", foreign_keys=[revoked_by_id])
    access_logs = relationship("ShareLinkAccessLog", back_populates="share_link", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ExternalShareLink(id={self.id}, token='{self.share_token[:8]}...', timeline_id={self.timeline_id})>"

class ShareLinkAccessLog(Base):
    """Access log for external share links"""
    __tablename__ = "share_link_access_logs"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Share link association
    share_link_id = Column(UUID(as_uuid=True), ForeignKey("external_share_links.id"), nullable=False, index=True)
    
    # Access information
    accessed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)  # IPv4 or IPv6
    user_agent = Column(Text)
    referer = Column(Text)
    
    # Access details
    action = Column(String(50), nullable=False)  # view, download, comment, etc.
    success = Column(Boolean, default=True)
    failure_reason = Column(String(255))  # If access failed
    
    # Geographic information (optional)
    country = Column(String(2))  # ISO country code
    city = Column(String(100))
    
    # Session tracking
    session_id = Column(String(255))  # Track unique sessions
    
    # Relationships
    share_link = relationship("ExternalShareLink", back_populates="access_logs")
    
    def __repr__(self):
        return f"<ShareLinkAccessLog(id={self.id}, share_link_id={self.share_link_id}, action='{self.action}')>"

class NotificationType(PyEnum):
    """Notification type enumeration"""
    TIMELINE_SHARED = "timeline_shared"
    TIMELINE_UPDATED = "timeline_updated"
    COMMENT_ADDED = "comment_added"
    COMMENT_REPLIED = "comment_replied"
    EVENT_ADDED = "event_added"
    EVIDENCE_PINNED = "evidence_pinned"
    EXTERNAL_ACCESS = "external_access"
    SHARE_LINK_EXPIRED = "share_link_expired"
    PERMISSION_CHANGED = "permission_changed"

class NotificationChannel(PyEnum):
    """Notification delivery channel enumeration"""
    EMAIL = "email"
    IN_APP = "in_app"
    WEBHOOK = "webhook"
    SMS = "sms"

class CollaborationNotification(Base):
    """Notification model for collaboration events"""
    __tablename__ = "collaboration_notifications"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Recipient information
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Notification content
    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    # Context information
    timeline_id = Column(UUID(as_uuid=True), ForeignKey("case_timelines.id"), index=True)
    event_id = Column(UUID(as_uuid=True))  # Timeline event if applicable
    comment_id = Column(UUID(as_uuid=True))  # Comment if applicable
    
    # Notification metadata
    data = Column(JSON)  # Additional structured data
    priority = Column(String(20), default='normal')  # low, normal, high, urgent
    
    # Delivery tracking
    channels = Column(JSON)  # List of delivery channels
    delivered_at = Column(JSON)  # Channel -> timestamp mapping
    read_at = Column(DateTime(timezone=True))
    clicked_at = Column(DateTime(timezone=True))
    
    # Status
    is_read = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # Who triggered the notification
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    timeline = relationship("CaseTimeline")
    creator = relationship("User", foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f"<CollaborationNotification(id={self.id}, type='{self.notification_type}', user_id={self.user_id})>"

class WebhookEndpoint(Base):
    """Webhook endpoint configuration for external integrations"""
    __tablename__ = "webhook_endpoints"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Endpoint configuration
    url = Column(String(2048), nullable=False)
    secret_key = Column(String(255))  # For webhook signature verification
    
    # Event filtering
    event_types = Column(JSON)  # List of event types to send
    timeline_ids = Column(JSON)  # Optional: specific timelines to monitor
    
    # Delivery settings
    is_active = Column(Boolean, default=True)
    retry_count = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=30)
    
    # Status tracking
    last_success_at = Column(DateTime(timezone=True))
    last_failure_at = Column(DateTime(timezone=True))
    failure_count = Column(Integer, default=0)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    creator = relationship("User")
    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WebhookEndpoint(id={self.id}, url='{self.url}', active={self.is_active})>"

class WebhookDelivery(Base):
    """Webhook delivery log"""
    __tablename__ = "webhook_deliveries"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Endpoint association
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id"), nullable=False, index=True)
    
    # Delivery information
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    
    # Delivery status
    status = Column(String(20), nullable=False)  # pending, success, failed, retrying
    http_status_code = Column(Integer)
    response_body = Column(Text)
    error_message = Column(Text)
    
    # Timing
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime(timezone=True))
    
    # Relationships
    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")
    
    def __repr__(self):
        return f"<WebhookDelivery(id={self.id}, endpoint_id={self.endpoint_id}, status='{self.status}')>"