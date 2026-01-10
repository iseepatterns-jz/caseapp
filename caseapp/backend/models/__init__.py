"""
Models package - imports all models for SQLAlchemy
"""

from .user import User, UserRole
from .client import Client
from .case import Case, CaseStatus, CaseType, CasePriority, AuditLog
from .document import Document, DocumentStatus, DocumentType, ExtractedEntity, DocumentVersion
from .timeline import TimelineEvent, EvidencePin
from .media import MediaEvidence, MediaAnnotation, MediaProcessingJob, MediaShareLink, MediaAccessLog, MediaType, MediaFormat, ProcessingStatus

# Import other models as they are created
# from .forensic_analysis import ForensicSource

__all__ = [
    "User", "UserRole",
    "Client", 
    "Case", "CaseStatus", "CaseType", "CasePriority",
    "AuditLog",
    "Document", "DocumentStatus", "DocumentType", "ExtractedEntity", "DocumentVersion",
    "TimelineEvent", "EvidencePin",
    "MediaEvidence", "MediaAnnotation", "MediaProcessingJob", "MediaShareLink", "MediaAccessLog", "MediaType", "MediaFormat", "ProcessingStatus"
]