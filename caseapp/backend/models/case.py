"""
Case model definitions
"""

from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
import uuid

from core.database import Base

class CaseStatus(PyEnum):
    """Case status enumeration"""
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"
    ON_HOLD = "ON_HOLD"

class CasePriority(PyEnum):
    """Case priority enumeration"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"

class CaseType(PyEnum):
    """Case type enumeration"""
    CIVIL = "CIVIL"
    CRIMINAL = "CRIMINAL"
    FAMILY = "FAMILY"
    CORPORATE = "CORPORATE"
    IMMIGRATION = "IMMIGRATION"
    PERSONAL_INJURY = "PERSONAL_INJURY"
    REAL_ESTATE = "REAL_ESTATE"
    BANKRUPTCY = "BANKRUPTCY"
    INTELLECTUAL_PROPERTY = "INTELLECTUAL_PROPERTY"
    OTHER = "OTHER"

class Case(Base):
    """Case model with UUID primary key and audit fields"""
    __tablename__ = "cases"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    case_number = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Case details
    case_type = Column(Enum(CaseType), nullable=False)
    status = Column(Enum(CaseStatus), default=CaseStatus.ACTIVE)
    priority = Column(Enum(CasePriority), default=CasePriority.MEDIUM)
    
    # Client information
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Additional dates
    filed_date = Column(DateTime(timezone=True))
    court_date = Column(DateTime(timezone=True))
    deadline_date = Column(DateTime(timezone=True))
    closed_date = Column(DateTime(timezone=True))
    
    # Court information
    court_name = Column(String(200))
    judge_name = Column(String(100))
    case_jurisdiction = Column(String(100))
    
    # JSONB metadata field for flexible data storage
    case_metadata = Column(JSON)
    
    # AI-generated fields
    ai_category = Column(String(100))
    ai_summary = Column(Text)
    ai_keywords = Column(JSON)
    ai_risk_assessment = Column(JSON)
    
    # Relationships (will be added as models are created)
    client = relationship("Client", back_populates="cases")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    audit_logs = relationship("AuditLog", back_populates="case", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    media_evidence = relationship("MediaEvidence", back_populates="case", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="case", cascade="all, delete-orphan")
    timelines = relationship("CaseTimeline", back_populates="case", cascade="all, delete-orphan")
    forensic_sources = relationship("ForensicSource", back_populates="case", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Case(id={self.id}, case_number='{self.case_number}', title='{self.title}')>"

class AuditLog(Base):
    """Audit log for tracking all system changes"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # What was changed
    entity_type = Column(String(50), nullable=False)  # 'case', 'document', etc.
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    entity_name = Column(String(200))  # Descriptive name for display
    action = Column(String(20), nullable=False)  # 'create', 'update', 'delete'
    
    # Change details
    field_name = Column(String(100))  # specific field that changed
    old_value = Column(Text)  # previous value (JSON serialized)
    new_value = Column(Text)  # new value (JSON serialized)
    
    # Audit metadata
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(Text)
    
    # Optional case association for case-related changes
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"))
    
    # Relationships
    user = relationship("User")
    case = relationship("Case", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, entity_type='{self.entity_type}', action='{self.action}')>"