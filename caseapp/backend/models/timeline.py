"""
Timeline and event model definitions for case timeline management
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
import uuid

from core.database import Base

class EventType(PyEnum):
    """Timeline event type enumeration"""
    INCIDENT = "incident"
    MEETING = "meeting"
    FILING = "filing"
    DISCOVERY = "discovery"
    DEPOSITION = "deposition"
    HEARING = "hearing"
    NEGOTIATION = "negotiation"
    CORRESPONDENCE = "correspondence"
    EVIDENCE_COLLECTION = "evidence_collection"
    WITNESS_INTERVIEW = "witness_interview"
    EXPERT_CONSULTATION = "expert_consultation"
    SETTLEMENT = "settlement"
    TRIAL = "trial"
    VERDICT = "verdict"
    APPEAL = "appeal"
    OTHER = "other"

class CaseTimeline(Base):
    """Case timeline model for organizing timeline events"""
    __tablename__ = "case_timelines"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Case association
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    
    # Timeline information
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Timeline settings
    is_primary = Column(Boolean, default=False)  # Primary timeline for the case
    is_public = Column(Boolean, default=False)  # Visible to clients
    timeline_settings = Column(JSON)  # Display preferences, filters, etc.
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    case = relationship("Case", back_populates="timelines")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    events = relationship("TimelineEvent", back_populates="timeline", cascade="all, delete-orphan")
    collaborations = relationship("TimelineCollaboration", back_populates="timeline", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CaseTimeline(id={self.id}, title='{self.title}', case_id={self.case_id})>"

class TimelineEvent(Base):
    """Timeline event model for chronological case events"""
    __tablename__ = "timeline_events"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Timeline association
    timeline_id = Column(UUID(as_uuid=True), ForeignKey("case_timelines.id"), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    
    # Event information
    title = Column(String(255), nullable=False)
    description = Column(Text)
    event_type = Column(String(50), default=EventType.OTHER.value)
    
    # Date and time information
    event_date = Column(DateTime(timezone=True), nullable=False, index=True)
    end_date = Column(DateTime(timezone=True))  # For events with duration
    all_day = Column(Boolean, default=False)
    
    # Location and participants
    location = Column(String(500))
    participants = Column(JSON)  # List of participant names/IDs
    
    # Event metadata
    event_metadata = Column(JSON)  # Additional flexible metadata
    importance_level = Column(Integer, default=3)  # 1-5 scale, 5 being most important
    is_milestone = Column(Boolean, default=False)  # Mark significant events
    
    # Display and ordering
    display_order = Column(Integer)  # Manual ordering within same date
    color = Column(String(7))  # Hex color code for visualization
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    timeline = relationship("CaseTimeline", back_populates="events")
    case = relationship("Case", back_populates="timeline_events")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    evidence_pins = relationship("EvidencePin", back_populates="timeline_event", cascade="all, delete-orphan")
    comments = relationship("TimelineComment", back_populates="timeline_event", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TimelineEvent(id={self.id}, title='{self.title}', event_date={self.event_date})>"

class TimelineCollaboration(Base):
    """Timeline collaboration model for sharing and permissions"""
    __tablename__ = "timeline_collaborations"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Timeline and user association
    timeline_id = Column(UUID(as_uuid=True), ForeignKey("case_timelines.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Granular permissions (Requirements 6.1)
    can_view = Column(Boolean, default=True)
    can_edit = Column(Boolean, default=False)
    can_add_events = Column(Boolean, default=False)
    can_pin_evidence = Column(Boolean, default=False)
    can_share = Column(Boolean, default=False)
    can_comment = Column(Boolean, default=True)
    
    # Collaboration settings
    receive_notifications = Column(Boolean, default=True)
    access_level = Column(String(20), default='viewer')  # viewer, editor, admin
    
    # Sharing metadata
    shared_message = Column(Text)  # Message from sharer
    access_expires_at = Column(DateTime(timezone=True))  # Optional expiration
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    timeline = relationship("CaseTimeline", back_populates="collaborations")
    user = relationship("User", foreign_keys=[user_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    
    # Unique constraint
    __table_args__ = (
        {'extend_existing': True}
    )
    
    def __repr__(self):
        return f"<TimelineCollaboration(id={self.id}, timeline_id={self.timeline_id}, user_id={self.user_id})>"

class CollaborationSession(Base):
    """Real-time collaboration session model for presence tracking"""
    __tablename__ = "collaboration_sessions"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Session information
    session_id = Column(String(255), nullable=False, unique=True, index=True)
    timeline_id = Column(UUID(as_uuid=True), ForeignKey("case_timelines.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Session state
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    current_view = Column(JSON)  # Current view state (filters, zoom level, etc.)
    
    # Real-time presence data
    cursor_position = Column(JSON)  # Current cursor/focus position
    selected_events = Column(JSON)  # Currently selected timeline events
    editing_event_id = Column(UUID(as_uuid=True))  # Event currently being edited
    
    # Connection metadata
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(Text)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    timeline = relationship("CaseTimeline")
    user = relationship("User")
    
    def __repr__(self):
        return f"<CollaborationSession(id={self.id}, session_id='{self.session_id}', user_id={self.user_id})>"

class EvidencePin(Base):
    """Evidence pinning model for associating evidence with timeline events"""
    __tablename__ = "evidence_pins"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Timeline event association
    timeline_event_id = Column(UUID(as_uuid=True), ForeignKey("timeline_events.id"), nullable=False, index=True)
    
    # Polymorphic evidence association
    evidence_type = Column(String(20), nullable=False)  # 'document', 'media', 'forensic'
    evidence_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Pin metadata
    relevance_score = Column(Float, default=1.0)  # 0.0-1.0 relevance to the event
    pin_description = Column(Text)  # Why this evidence is relevant
    pin_notes = Column(Text)  # Additional notes about the evidence
    
    # Display information
    display_order = Column(Integer, default=0)  # Order of evidence within event
    is_primary = Column(Boolean, default=False)  # Mark as primary evidence for event
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    timeline_event = relationship("TimelineEvent", back_populates="evidence_pins")
    creator = relationship("User")
    
    def __repr__(self):
        return f"<EvidencePin(id={self.id}, event_id={self.timeline_event_id}, evidence_type='{self.evidence_type}')>"

class TimelineComment(Base):
    """Comments on timeline events for collaboration"""
    __tablename__ = "timeline_comments"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Timeline event association
    timeline_event_id = Column(UUID(as_uuid=True), ForeignKey("timeline_events.id"), nullable=False, index=True)
    
    # Comment content
    comment_text = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=True)  # Internal team comment vs client-visible
    
    # Threading support (Requirements 6.3)
    parent_comment_id = Column(UUID(as_uuid=True), ForeignKey("timeline_comments.id"))
    thread_depth = Column(Integer, default=0)  # Depth in comment thread
    
    # Comment metadata
    is_resolved = Column(Boolean, default=False)  # For discussion resolution
    resolved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolved_at = Column(DateTime(timezone=True))
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    timeline_event = relationship("TimelineEvent", back_populates="comments")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    resolver = relationship("User", foreign_keys=[resolved_by_id])
    parent_comment = relationship("TimelineComment", remote_side=[id])
    child_comments = relationship("TimelineComment", back_populates="parent_comment")
    
    def __repr__(self):
        return f"<TimelineComment(id={self.id}, event_id={self.timeline_event_id}, created_by={self.created_by})>"

class TimelineTemplate(Base):
    """Template for common timeline structures"""
    __tablename__ = "timeline_templates"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Template information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    case_type = Column(String(50))  # Associated case type
    
    # Template structure
    template_events = Column(JSON)  # Predefined event structure
    is_public = Column(Boolean, default=False)  # Available to all users
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self):
        return f"<TimelineTemplate(id={self.id}, name='{self.name}', case_type='{self.case_type}')>"