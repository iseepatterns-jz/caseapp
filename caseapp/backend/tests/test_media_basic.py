"""
Basic tests for media evidence functionality
"""

import pytest
from io import BytesIO
from uuid import uuid4
from fastapi import UploadFile

from models.media import MediaEvidence, MediaType, MediaFormat, ProcessingStatus
from services.media_service import MediaService

@pytest.mark.asyncio
async def test_media_type_detection():
    """Test media type and format detection"""
    from services.media_service import MediaService
    from services.audit_service import AuditService
    
    # Create a mock database session
    class MockDB:
        pass
    
    db = MockDB()
    audit_service = AuditService(db)
    media_service = MediaService(db, audit_service)
    
    # Test image detection
    media_type, media_format = media_service._determine_media_type_and_format("image/jpeg", "test.jpg")
    assert media_type == MediaType.IMAGE
    assert media_format == MediaFormat.JPEG
    
    # Test video detection
    media_type, media_format = media_service._determine_media_type_and_format("video/mp4", "test.mp4")
    assert media_type == MediaType.VIDEO
    assert media_format == MediaFormat.MP4
    
    # Test audio detection
    media_type, media_format = media_service._determine_media_type_and_format("audio/mp3", "test.mp3")
    assert media_type == MediaType.AUDIO
    assert media_format == MediaFormat.MP3
    
    # Test PDF detection
    media_type, media_format = media_service._determine_media_type_and_format("application/pdf", "test.pdf")
    assert media_type == MediaType.DOCUMENT_SCAN
    assert media_format == MediaFormat.PDF

def test_media_evidence_properties():
    """Test MediaEvidence model properties"""
    
    # Create a media evidence instance
    media = MediaEvidence(
        case_id=uuid4(),
        filename="test.jpg",
        original_filename="original_test.jpg",
        file_path="/path/to/test.jpg",
        file_size=1024 * 1024,  # 1MB
        file_hash="abc123",
        mime_type="image/jpeg",
        media_type=MediaType.IMAGE,
        media_format=MediaFormat.JPEG,
        duration=120,  # 2 minutes
        width=1920,
        height=1080,
        created_by=uuid4()
    )
    
    # Test properties
    assert media.file_size_mb == 1.0
    assert media.is_image is True
    assert media.is_video is False
    assert media.is_audio is False
    assert media.duration_formatted == "02:00"
    assert media.resolution == "1920x1080"
    assert media.has_ai_analysis is False

def test_media_processing_job_properties():
    """Test MediaProcessingJob model properties"""
    from models.media import MediaProcessingJob
    from datetime import datetime, timezone, timedelta
    
    # Create a processing job
    job = MediaProcessingJob(
        media_id=uuid4(),
        job_type="thumbnail",
        status=ProcessingStatus.COMPLETED,
        retry_count=1,
        max_retries=3,
        created_by=uuid4()
    )
    
    # Set timing
    start_time = datetime.now(timezone.utc)
    job.started_at = start_time
    job.completed_at = start_time + timedelta(seconds=30)  # 30 seconds later
    
    # Test properties
    assert job.is_completed is True
    assert job.is_failed is False
    assert job.can_retry is False  # Not failed, so can't retry
    assert job.processing_duration == 30

def test_media_share_link_properties():
    """Test MediaShareLink model properties"""
    from models.media import MediaShareLink
    from datetime import datetime, timezone, timedelta
    
    # Create a share link
    share_link = MediaShareLink(
        media_id=uuid4(),
        share_token="test_token_123",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        view_limit=5,
        view_count=2,
        is_active=True,  # Explicitly set is_active
        created_by=uuid4()
    )
    
    # Test properties
    assert share_link.is_expired is False
    assert share_link.is_view_limit_exceeded is False
    assert share_link.is_valid is True
    assert share_link.views_remaining == 3
    
    # Test expired link
    share_link.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    assert share_link.is_expired is True
    assert share_link.is_valid is False
    
    # Test view limit exceeded
    share_link.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    share_link.view_count = 5
    assert share_link.is_view_limit_exceeded is True
    assert share_link.is_valid is False

if __name__ == "__main__":
    pytest.main([__file__])