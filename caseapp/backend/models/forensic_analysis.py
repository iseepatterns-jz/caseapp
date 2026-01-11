"""
Forensic analysis models for email and text message analysis
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, JSON, Float, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
import uuid

from core.database import Base

class ForensicDataType(PyEnum):
    """Types of forensic data"""
    EMAIL = "email"
    SMS = "sms"
    IMESSAGE = "imessage"
    WHATSAPP = "whatsapp"
    CALL_LOG = "call_log"
    CONTACT = "contact"
    LOCATION = "location"
    BROWSER_HISTORY = "browser_history"
    APP_DATA = "app_data"

class AnalysisStatus(PyEnum):
    """Analysis processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

class ForensicSource(Base):
    """Forensic data source (e.g., iPhone backup, email archive)"""
    __tablename__ = "forensic_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    
    # Source information
    source_name = Column(String(200), nullable=False)
    source_type = Column(String(50))  # iphone_backup, android_backup, email_archive, etc.
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    file_hash = Column(String(64))  # SHA-256 hash for integrity
    
    # Device/account information
    device_info = Column(JSON)  # Device model, OS version, etc.
    account_info = Column(JSON)  # Email accounts, phone numbers, etc.
    
    # Processing status
    analysis_status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    analysis_progress = Column(Float, default=0.0)
    analysis_started_at = Column(DateTime(timezone=True))
    analysis_completed_at = Column(DateTime(timezone=True))
    analysis_errors = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    case = relationship("Case")
    uploaded_by = relationship("User")
    forensic_items = relationship("ForensicItem", back_populates="source", cascade="all, delete-orphan")
    analysis_reports = relationship("ForensicAnalysisReport", back_populates="source", cascade="all, delete-orphan")

class ForensicItem(Base):
    """Individual forensic data item (email, text message, etc.)"""
    __tablename__ = "forensic_items"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("forensic_sources.id"), nullable=False)
    
    # Item identification
    item_type = Column(Enum(ForensicDataType), nullable=False)
    external_id = Column(String(200))  # Original ID from source system
    thread_id = Column(String(200))  # For grouping related messages
    
    # Temporal information
    timestamp = Column(DateTime(timezone=True), nullable=False)
    timezone_offset = Column(Integer)  # Minutes from UTC
    
    # Participants
    sender = Column(String(200))
    recipients = Column(JSON)  # List of recipients
    participants = Column(JSON)  # All participants in conversation
    
    # Content
    subject = Column(String(500))  # Email subject or message preview
    content = Column(Text)  # Full message content
    content_type = Column(String(50))  # text/plain, text/html, etc.
    attachments = Column(JSON)  # List of attachment info
    
    # Technical metadata
    message_id = Column(String(200))  # Unique message identifier
    in_reply_to = Column(String(200))  # Reference to replied message
    headers = Column(JSON)  # Email headers or message metadata
    
    # Location data (if available)
    latitude = Column(Float)
    longitude = Column(Float)
    location_accuracy = Column(Float)
    location_name = Column(String(200))
    
    # Analysis results
    sentiment_score = Column(Float)  # -1 to 1 (negative to positive)
    language = Column(String(10))  # ISO language code
    keywords = Column(JSON)  # Extracted keywords
    entities = Column(JSON)  # Named entities (people, places, organizations)
    topics = Column(JSON)  # Topic classification
    
    # Forensic flags
    is_deleted = Column(Boolean, default=False)
    is_draft = Column(Boolean, default=False)
    is_encrypted = Column(Boolean, default=False)
    is_suspicious = Column(Boolean, default=False)
    
    # Evidence relevance
    relevance_score = Column(Float)  # AI-calculated relevance to case
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String(200))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    source = relationship("ForensicSource", back_populates="forensic_items")
    timeline_pins = relationship("ForensicTimelinePin", back_populates="forensic_item", cascade="all, delete-orphan")

class ForensicAnalysisReport(Base):
    """Analysis report for forensic source"""
    __tablename__ = "forensic_analysis_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("forensic_sources.id"), nullable=False)
    
    # Report metadata
    report_type = Column(String(50))  # summary, timeline, network, etc.
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Analysis results
    total_items = Column(Integer, default=0)
    date_range_start = Column(DateTime(timezone=True))
    date_range_end = Column(DateTime(timezone=True))
    
    # Statistics
    statistics = Column(JSON)  # Detailed statistics
    insights = Column(JSON)  # AI-generated insights
    patterns = Column(JSON)  # Detected patterns
    anomalies = Column(JSON)  # Suspicious activities
    
    # Visualizations
    charts_data = Column(JSON)  # Data for charts and graphs
    network_data = Column(JSON)  # Communication network analysis
    timeline_data = Column(JSON)  # Timeline visualization data
    
    # Generated files
    report_file_path = Column(String(500))  # Path to generated report
    export_data = Column(JSON)  # Exportable data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    generated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    source = relationship("ForensicSource", back_populates="analysis_reports")
    generated_by = relationship("User")

class ForensicTimelinePin(Base):
    """Pin forensic items to timeline events"""
    __tablename__ = "forensic_timeline_pins"
    
    id = Column(Integer, primary_key=True, index=True)
    timeline_event_id = Column(UUID(as_uuid=True), ForeignKey("timeline_events.id"), nullable=False)
    forensic_item_id = Column(Integer, ForeignKey("forensic_items.id"), nullable=False)
    
    # Pin details
    relevance_score = Column(Float, default=5.0)
    context_note = Column(Text)
    is_key_evidence = Column(Boolean, default=False)
    
    pinned_at = Column(DateTime(timezone=True), server_default=func.now())
    pinned_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    timeline_event = relationship("TimelineEvent")
    forensic_item = relationship("ForensicItem", back_populates="timeline_pins")
    pinned_by = relationship("User")

class ForensicSearch(Base):
    """Saved forensic searches and filters"""
    __tablename__ = "forensic_searches"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    
    # Search details
    name = Column(String(200), nullable=False)
    description = Column(Text)
    search_criteria = Column(JSON, nullable=False)  # Search parameters
    
    # Results
    result_count = Column(Integer, default=0)
    last_executed = Column(DateTime(timezone=True))
    
    # Sharing
    is_shared = Column(Boolean, default=False)
    shared_with = Column(JSON)  # List of user IDs
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    case = relationship("Case")
    created_by = relationship("User")

class ForensicAlert(Base):
    """Automated alerts for suspicious patterns"""
    __tablename__ = "forensic_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("forensic_sources.id"), nullable=False)
    
    # Alert details
    alert_type = Column(String(50))  # pattern, keyword, anomaly, etc.
    severity = Column(String(20))  # low, medium, high, critical
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Trigger information
    trigger_criteria = Column(JSON)  # What triggered the alert
    affected_items = Column(JSON)  # List of forensic item IDs
    
    # Status
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    acknowledged_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    source = relationship("ForensicSource")
    acknowledged_by = relationship("User")

class CommunicationNetwork(Base):
    """Communication network analysis"""
    __tablename__ = "communication_networks"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("forensic_sources.id"), nullable=False)
    
    # Network data
    nodes = Column(JSON)  # People/entities in network
    edges = Column(JSON)  # Connections between nodes
    clusters = Column(JSON)  # Identified groups/clusters
    
    # Analysis metrics
    centrality_scores = Column(JSON)  # Importance of each node
    community_detection = Column(JSON)  # Community structure
    temporal_analysis = Column(JSON)  # How network changes over time
    
    # Metadata
    analysis_date = Column(DateTime(timezone=True), server_default=func.now())
    parameters = Column(JSON)  # Analysis parameters used
    
    # Relationships
    source = relationship("ForensicSource")