"""
Document model definitions for legal document management
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
import uuid

from core.database import Base

class DocumentStatus(PyEnum):
    """Document processing status enumeration"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"

class DocumentType(PyEnum):
    """Document type enumeration"""
    LEGAL_BRIEF = "legal_brief"
    CONTRACT = "contract"
    EVIDENCE = "evidence"
    CORRESPONDENCE = "correspondence"
    COURT_FILING = "court_filing"
    DISCOVERY = "discovery"
    DEPOSITION = "deposition"
    EXPERT_REPORT = "expert_report"
    OTHER = "other"

class Document(Base):
    """Document model with file metadata and AI analysis results"""
    __tablename__ = "documents"
    
    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)  # Store original name
    file_path = Column(String(500), nullable=False)  # S3 path or local path
    file_size = Column(Integer, nullable=False)  # Size in bytes
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64))  # SHA-256 hash for integrity
    
    # Document metadata
    document_type = Column(String(50), default=DocumentType.OTHER.value)
    status = Column(String(20), default=DocumentStatus.UPLOADED.value)
    version = Column(Integer, default=1)
    is_current_version = Column(Boolean, default=True)
    parent_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))  # For versioning
    
    # Case association
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    
    # AI analysis results
    extracted_text = Column(Text)  # Text extracted by Textract
    ai_summary = Column(Text)  # AI-generated summary
    entities = Column(JSON)  # Extracted entities (people, organizations, dates, etc.)
    keywords = Column(JSON)  # Key phrases and terms
    confidence_scores = Column(JSON)  # AI confidence scores
    
    # Processing metadata
    textract_job_id = Column(String(100))  # AWS Textract job ID
    comprehend_job_id = Column(String(100))  # AWS Comprehend job ID
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    processing_error = Column(Text)  # Error message if processing failed
    
    # Audit fields
    upload_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Search and indexing
    search_vector = Column(Text)  # Full-text search vector
    document_metadata = Column(JSON)  # Additional flexible metadata
    
    # Legal compliance
    retention_date = Column(DateTime(timezone=True))  # When document can be deleted
    is_privileged = Column(Boolean, default=False)  # Attorney-client privilege
    is_confidential = Column(Boolean, default=False)  # Confidential information
    access_level = Column(String(20), default="standard")  # Access control level
    
    # Relationships
    case = relationship("Case", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    updater = relationship("User", foreign_keys=[updated_by])
    parent_document = relationship("Document", remote_side=[id])
    child_documents = relationship("Document", back_populates="parent_document")
    audit_logs = relationship("AuditLog", 
                            primaryjoin="and_(AuditLog.entity_type=='document', AuditLog.entity_id==Document.id)",
                            foreign_keys="AuditLog.entity_id",
                            viewonly=True)
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', case_id={self.case_id})>"

class ExtractedEntity(Base):
    """Extracted entities from document analysis"""
    __tablename__ = "extracted_entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    
    # Entity information
    entity_type = Column(String(50), nullable=False)  # PERSON, ORGANIZATION, DATE, LOCATION, etc.
    entity_text = Column(String(500), nullable=False)  # The actual text
    confidence_score = Column(Integer)  # Confidence score (0-100)
    
    # Position in document
    start_offset = Column(Integer)  # Character offset in text
    end_offset = Column(Integer)  # End character offset
    page_number = Column(Integer)  # Page number if available
    
    # Additional metadata
    entity_metadata = Column(JSON)  # Additional entity-specific data
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    document = relationship("Document")
    
    def __repr__(self):
        return f"<ExtractedEntity(id={self.id}, type='{self.entity_type}', text='{self.entity_text[:50]}...')>"

class DocumentVersion(Base):
    """Document version history for change tracking"""
    __tablename__ = "document_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    
    # Version information
    version_number = Column(Integer, nullable=False)
    change_description = Column(Text)
    change_type = Column(String(50))  # 'content_update', 'metadata_update', 'reprocessing'
    
    # Snapshot of document state
    filename_snapshot = Column(String(255))
    file_path_snapshot = Column(String(500))
    file_size_snapshot = Column(Integer)
    extracted_text_snapshot = Column(Text)
    ai_summary_snapshot = Column(Text)
    entities_snapshot = Column(JSON)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    document = relationship("Document")
    creator = relationship("User")
    
    def __repr__(self):
        return f"<DocumentVersion(id={self.id}, document_id={self.document_id}, version={self.version_number})>"