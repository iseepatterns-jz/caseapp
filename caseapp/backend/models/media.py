"""
Media evidence models for court case management system
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, JSON, BigInteger
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List

from core.database import Base

class MediaType(str, Enum):
    """Enumeration of supported media types"""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT_SCAN = "document_scan"
    SCREENSHOT = "screenshot"
    SURVEILLANCE = "surveillance"
    BODY_CAM = "body_cam"
    DASH_CAM = "dash_cam"
    PHONE_RECORDING = "phone_recording"
    CCTV = "cctv"
    OTHER = "other"

class MediaFormat(str, Enum):
    """Enumeration of supported media formats"""
    # Image formats
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    BMP = "bmp"
    GIF = "gif"
    WEBP = "webp"
    RAW = "raw"
    
    # Video formats
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    WMV = "wmv"
    FLV = "flv"
    MKV = "mkv"
    WEBM = "webm"
    
    # Audio formats
    MP3 = "mp3"
    WAV = "wav"
    FLAC = "flac"
    AAC = "aac"
    OGG = "ogg"
    WMA = "wma"
    
    # Document formats
    PDF = "pdf"
    
    # Other
    UNKNOWN = "unknown"

class ProcessingStatus(str, Enum):
    """Media processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class MediaEvidence(Base):
    """Media evidence model for storing multimedia evidence files"""
    
    __tablename__ = "media_evidence"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)  # Size in bytes
    file_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash
    mime_type = Column(String(100), nullable=False)
    
    # Media classification
    media_type = Column(SQLEnum(MediaType), nullable=False, index=True)
    media_format = Column(SQLEnum(MediaFormat), nullable=False)
    
    # Technical metadata
    duration = Column(Integer, nullable=True)  # Duration in seconds for video/audio
    width = Column(Integer, nullable=True)  # Width in pixels for images/video
    height = Column(Integer, nullable=True)  # Height in pixels for images/video
    frame_rate = Column(Integer, nullable=True)  # FPS for video
    bit_rate = Column(Integer, nullable=True)  # Bit rate for audio/video
    sample_rate = Column(Integer, nullable=True)  # Sample rate for audio
    color_depth = Column(Integer, nullable=True)  # Color depth for images
    
    # Capture information
    captured_at = Column(DateTime(timezone=True), nullable=True)  # When media was captured
    captured_by = Column(String(255), nullable=True)  # Device or person who captured
    capture_location = Column(String(500), nullable=True)  # GPS or location description
    capture_device = Column(String(255), nullable=True)  # Camera model, phone, etc.
    
    # Evidence metadata
    evidence_number = Column(String(100), nullable=True, index=True)  # Official evidence number
    chain_of_custody = Column(JSON, nullable=True)  # Chain of custody log
    authenticity_verified = Column(Boolean, default=False, nullable=False)
    authenticity_method = Column(String(255), nullable=True)  # How authenticity was verified
    
    # Content analysis
    ai_analysis_status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False)
    ai_analysis_results = Column(JSON, nullable=True)  # AI analysis results
    extracted_text = Column(Text, nullable=True)  # OCR extracted text
    detected_objects = Column(JSON, nullable=True)  # Object detection results
    detected_faces = Column(JSON, nullable=True)  # Face detection results
    audio_transcript = Column(Text, nullable=True)  # Audio transcription
    
    # Thumbnails and previews
    thumbnail_path = Column(String(500), nullable=True)  # Thumbnail image path
    preview_path = Column(String(500), nullable=True)  # Preview/compressed version path
    
    # Legal and administrative
    is_privileged = Column(Boolean, default=False, nullable=False)
    privilege_reason = Column(String(500), nullable=True)
    is_redacted = Column(Boolean, default=False, nullable=False)
    redaction_reason = Column(String(500), nullable=True)
    admissibility_status = Column(String(50), nullable=True)  # admissible, inadmissible, pending
    admissibility_notes = Column(Text, nullable=True)
    
    # Tags and categorization
    tags = Column(ARRAY(String), nullable=True, default=list)
    categories = Column(ARRAY(String), nullable=True, default=list)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    case = relationship("Case", back_populates="media_evidence")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    annotations = relationship("MediaAnnotation", back_populates="media", cascade="all, delete-orphan")
    timeline_pins = relationship("EvidencePin", 
                               primaryjoin="and_(MediaEvidence.id==foreign(EvidencePin.evidence_id), "
                                          "EvidencePin.evidence_type=='media')",
                               cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MediaEvidence(id={self.id}, filename='{self.filename}', type={self.media_type})>"
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes"""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def is_image(self) -> bool:
        """Check if media is an image"""
        return self.media_type == MediaType.IMAGE
    
    @property
    def is_video(self) -> bool:
        """Check if media is a video"""
        return self.media_type == MediaType.VIDEO
    
    @property
    def is_audio(self) -> bool:
        """Check if media is audio"""
        return self.media_type == MediaType.AUDIO
    
    @property
    def has_ai_analysis(self) -> bool:
        """Check if AI analysis has been completed"""
        return self.ai_analysis_status == ProcessingStatus.COMPLETED and self.ai_analysis_results is not None
    
    @property
    def duration_formatted(self) -> Optional[str]:
        """Get formatted duration string (HH:MM:SS)"""
        if not self.duration:
            return None
        
        hours = self.duration // 3600
        minutes = (self.duration % 3600) // 60
        seconds = self.duration % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def resolution(self) -> Optional[str]:
        """Get resolution string (WxH)"""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None

class MediaAnnotation(Base):
    """Annotations and markups on media evidence"""
    
    __tablename__ = "media_annotations"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    media_id = Column(UUID(as_uuid=True), ForeignKey("media_evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Annotation details
    annotation_type = Column(String(50), nullable=False)  # rectangle, circle, arrow, text, highlight
    annotation_data = Column(JSON, nullable=False)  # Coordinates, text, styling
    
    # Content
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # Timing (for video/audio annotations)
    start_time = Column(Integer, nullable=True)  # Start time in seconds
    end_time = Column(Integer, nullable=True)  # End time in seconds
    
    # Visual properties
    color = Column(String(7), nullable=True, default="#FF0000")  # Hex color
    opacity = Column(Integer, nullable=True, default=80)  # 0-100
    
    # Legal significance
    is_key_evidence = Column(Boolean, default=False, nullable=False)
    relevance_score = Column(Integer, nullable=True)  # 1-10 scale
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    media = relationship("MediaEvidence", back_populates="annotations")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self):
        return f"<MediaAnnotation(id={self.id}, type='{self.annotation_type}', media_id={self.media_id})>"

class MediaProcessingJob(Base):
    """Background processing jobs for media analysis"""
    
    __tablename__ = "media_processing_jobs"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    media_id = Column(UUID(as_uuid=True), ForeignKey("media_evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Job details
    job_type = Column(String(50), nullable=False)  # thumbnail, ocr, object_detection, transcription, etc.
    status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False)
    priority = Column(Integer, default=5, nullable=False)  # 1-10, higher is more urgent
    
    # Processing details
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    
    # Results
    result_data = Column(JSON, nullable=True)
    output_files = Column(ARRAY(String), nullable=True, default=list)  # Generated file paths
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    media = relationship("MediaEvidence")
    creator = relationship("User")
    
    def __repr__(self):
        return f"<MediaProcessingJob(id={self.id}, type='{self.job_type}', status={self.status})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if job is completed successfully"""
        return self.status == ProcessingStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if job has failed"""
        return self.status == ProcessingStatus.FAILED
    
    @property
    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.is_failed and self.retry_count < self.max_retries
    
    @property
    def processing_duration(self) -> Optional[int]:
        """Get processing duration in seconds"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None

class MediaShareLink(Base):
    """Secure sharing links for media evidence"""
    
    __tablename__ = "media_share_links"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    media_id = Column(UUID(as_uuid=True), ForeignKey("media_evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Share token and security
    share_token = Column(String(64), nullable=False, unique=True, index=True)  # Secure random token
    
    # Access controls
    expires_at = Column(DateTime(timezone=True), nullable=False)
    view_limit = Column(Integer, nullable=True)  # Maximum number of views
    view_count = Column(Integer, default=0, nullable=False)  # Current view count
    
    # Access tracking
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    last_accessed_ip = Column(String(45), nullable=True)  # IPv6 compatible
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    media = relationship("MediaEvidence")
    creator = relationship("User")
    
    def __repr__(self):
        return f"<MediaShareLink(id={self.id}, token='{self.share_token[:8]}...', media_id={self.media_id})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if share link is expired"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_view_limit_exceeded(self) -> bool:
        """Check if view limit is exceeded"""
        return self.view_limit is not None and self.view_count >= self.view_limit
    
    @property
    def is_valid(self) -> bool:
        """Check if share link is valid for access"""
        return self.is_active and not self.is_expired and not self.is_view_limit_exceeded
    
    @property
    def views_remaining(self) -> Optional[int]:
        """Get remaining views if view limit is set"""
        if self.view_limit is None:
            return None
        return max(0, self.view_limit - self.view_count)

class MediaAccessLog(Base):
    """Log of media access for audit purposes"""
    
    __tablename__ = "media_access_logs"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    media_id = Column(UUID(as_uuid=True), ForeignKey("media_evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Access details
    access_type = Column(String(50), nullable=False)  # view, download, stream, share
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Null for shared access
    share_token = Column(String(64), nullable=True)  # If accessed via share link
    
    # Request details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    referer = Column(String(500), nullable=True)
    
    # Response details
    bytes_served = Column(BigInteger, nullable=True)  # For streaming/download
    response_status = Column(Integer, nullable=True)  # HTTP status code
    
    # Timing
    accessed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    duration_ms = Column(Integer, nullable=True)  # Request duration in milliseconds
    
    # Relationships
    media = relationship("MediaEvidence")
    user = relationship("User")
    
    def __repr__(self):
        return f"<MediaAccessLog(id={self.id}, media_id={self.media_id}, access_type='{self.access_type}')>"