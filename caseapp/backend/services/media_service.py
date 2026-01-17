"""
Media evidence management service
"""

import os
import hashlib
import mimetypes
import asyncio
from functools import partial
from typing import List, Optional, Dict, Any, Tuple

from uuid import UUID
from datetime import datetime
from pathlib import Path
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
from fastapi import UploadFile

from models.media import MediaEvidence, MediaAnnotation, MediaProcessingJob, MediaType, MediaFormat, ProcessingStatus
from models.case import Case
from schemas.media import (
    MediaUploadRequest, MediaUpdateRequest, MediaSearchRequest,
    MediaAnnotationCreateRequest, MediaAnnotationUpdateRequest,
    MediaAnalysisRequest
)
from services.audit_service import AuditService
from core.config import settings
from core.exceptions import CaseManagementException

logger = structlog.get_logger()

class MediaService:
    """Service for managing media evidence"""
    
    def __init__(self, db: AsyncSession, audit_service: AuditService):
        self.db = db
        self.audit_service = audit_service
        self.upload_path = Path(getattr(settings, 'MEDIA_UPLOAD_PATH', './uploads/media'))
        self.upload_path.mkdir(parents=True, exist_ok=True)
    
    async def upload_media(
        self,
        file: UploadFile,
        upload_request: MediaUploadRequest,
        user_id: UUID
    ) -> MediaEvidence:
        """
        Upload and process media evidence file
        
        Args:
            file: Uploaded file
            upload_request: Upload metadata
            user_id: User performing the upload
            
        Returns:
            Created MediaEvidence instance
        """
        try:
            # Validate case exists
            case_result = await self.db.execute(
                select(Case).where(Case.id == upload_request.case_id)
            )
            case = case_result.scalar_one_or_none()
            if not case:
                raise CaseManagementException(f"Case {upload_request.case_id} not found")
            
            # Read file content and calculate hash
            file_content = await file.read()
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # Check for duplicate files
            existing_result = await self.db.execute(
                select(MediaEvidence).where(MediaEvidence.file_hash == file_hash)
            )
            existing_media = existing_result.scalar_one_or_none()
            if existing_media:
                raise CaseManagementException(f"File already exists with ID {existing_media.id}")
            
            # Determine media type and format
            mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
            media_type, media_format = self._determine_media_type_and_format(mime_type, file.filename)
            
            # Generate unique filename
            file_extension = Path(file.filename).suffix.lower()
            unique_filename = f"{file_hash}{file_extension}"
            file_path = self.upload_path / str(upload_request.case_id) / unique_filename
            
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Extract basic metadata
            metadata = await self._extract_basic_metadata(file_path, media_type)
            
            # Create media evidence record
            media_evidence = MediaEvidence(
                case_id=upload_request.case_id,
                filename=unique_filename,
                original_filename=file.filename,
                file_path=str(file_path),
                file_size=len(file_content),
                file_hash=file_hash,
                mime_type=mime_type,
                media_type=media_type,
                media_format=media_format,
                evidence_number=upload_request.evidence_number,
                captured_at=upload_request.captured_at,
                captured_by=upload_request.captured_by,
                capture_location=upload_request.capture_location,
                capture_device=upload_request.capture_device,
                tags=upload_request.tags or [],
                categories=upload_request.categories or [],
                is_privileged=upload_request.is_privileged,
                privilege_reason=upload_request.privilege_reason,
                created_by=user_id,
                **metadata
            )
            
            self.db.add(media_evidence)
            await self.db.commit()
            await self.db.refresh(media_evidence)
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="media_evidence",
                entity_id=media_evidence.id,
                action="create",
                user_id=user_id,
                case_id=upload_request.case_id,
                entity_name=file.filename,
                new_value=f"Uploaded media: {file.filename}"
            )
            
            # Queue processing jobs
            await self._queue_processing_jobs(media_evidence, user_id)
            
            logger.info(
                "Media evidence uploaded",
                media_id=str(media_evidence.id),
                filename=file.filename,
                case_id=str(upload_request.case_id),
                user_id=str(user_id)
            )
            
            return media_evidence
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Media upload failed", filename=file.filename, error=str(e))
            raise CaseManagementException(f"Failed to upload media: {str(e)}")
    
    async def get_media(self, media_id: UUID, include_annotations: bool = True) -> Optional[MediaEvidence]:
        """
        Get media evidence by ID
        
        Args:
            media_id: Media evidence ID
            include_annotations: Whether to include annotations
            
        Returns:
            MediaEvidence instance or None
        """
        try:
            query = select(MediaEvidence).where(MediaEvidence.id == media_id)
            
            if include_annotations:
                query = query.options(selectinload(MediaEvidence.annotations))
            
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get media", media_id=str(media_id), error=str(e))
            raise CaseManagementException(f"Failed to get media: {str(e)}")
    
    async def search_media(
        self,
        search_request: MediaSearchRequest,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[MediaEvidence], int]:
        """
        Search media evidence with filters
        
        Args:
            search_request: Search criteria
            page: Page number (1-based)
            per_page: Items per page
            
        Returns:
            Tuple of (media_list, total_count)
        """
        try:
            # Build base query
            query = select(MediaEvidence)
            count_query = select(func.count(MediaEvidence.id))
            
            # Apply filters
            conditions = []
            
            if search_request.case_id:
                conditions.append(MediaEvidence.case_id == search_request.case_id)
            
            if search_request.media_types:
                conditions.append(MediaEvidence.media_type.in_([mt.value for mt in search_request.media_types]))
            
            if search_request.search_text:
                text_conditions = [
                    MediaEvidence.original_filename.ilike(f"%{search_request.search_text}%"),
                    MediaEvidence.extracted_text.ilike(f"%{search_request.search_text}%"),
                    MediaEvidence.evidence_number.ilike(f"%{search_request.search_text}%")
                ]
                conditions.append(or_(*text_conditions))
            
            # Apply conditions to queries
            if conditions:
                query = query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))
            
            # Get total count
            count_result = await self.db.execute(count_query)
            total_count = count_result.scalar()
            
            # Apply pagination and ordering
            query = query.order_by(desc(MediaEvidence.created_at))
            query = query.offset((page - 1) * per_page).limit(per_page)
            
            # Execute query
            result = await self.db.execute(query)
            media_list = result.scalars().all()
            
            return list(media_list), total_count
            
        except Exception as e:
            logger.error("Media search failed", error=str(e))
            raise CaseManagementException(f"Failed to search media: {str(e)}")
    
    def _determine_media_type_and_format(self, mime_type: str, filename: str) -> Tuple[MediaType, MediaFormat]:
        """Determine media type and format from MIME type and filename"""
        
        mime_lower = mime_type.lower()
        filename_lower = filename.lower()
        
        # Image types
        if mime_lower.startswith('image/'):
            if 'jpeg' in mime_lower or filename_lower.endswith(('.jpg', '.jpeg')):
                return MediaType.IMAGE, MediaFormat.JPEG
            elif 'png' in mime_lower or filename_lower.endswith('.png'):
                return MediaType.IMAGE, MediaFormat.PNG
            elif 'tiff' in mime_lower or filename_lower.endswith(('.tif', '.tiff')):
                return MediaType.IMAGE, MediaFormat.TIFF
            elif 'gif' in mime_lower or filename_lower.endswith('.gif'):
                return MediaType.IMAGE, MediaFormat.GIF
            elif 'webp' in mime_lower or filename_lower.endswith('.webp'):
                return MediaType.IMAGE, MediaFormat.WEBP
            elif 'bmp' in mime_lower or filename_lower.endswith('.bmp'):
                return MediaType.IMAGE, MediaFormat.BMP
            else:
                return MediaType.IMAGE, MediaFormat.UNKNOWN
        
        # Video types - Requirements 4.1: MP4, AVI, MOV, MKV
        elif mime_lower.startswith('video/'):
            if 'mp4' in mime_lower or filename_lower.endswith('.mp4'):
                return MediaType.VIDEO, MediaFormat.MP4
            elif 'avi' in mime_lower or filename_lower.endswith('.avi'):
                return MediaType.VIDEO, MediaFormat.AVI
            elif 'quicktime' in mime_lower or filename_lower.endswith('.mov'):
                return MediaType.VIDEO, MediaFormat.MOV
            elif 'mkv' in mime_lower or filename_lower.endswith('.mkv'):
                return MediaType.VIDEO, MediaFormat.MKV
            elif 'webm' in mime_lower or filename_lower.endswith('.webm'):
                return MediaType.VIDEO, MediaFormat.WEBM
            elif 'wmv' in mime_lower or filename_lower.endswith('.wmv'):
                return MediaType.VIDEO, MediaFormat.WMV
            elif 'flv' in mime_lower or filename_lower.endswith('.flv'):
                return MediaType.VIDEO, MediaFormat.FLV
            else:
                return MediaType.VIDEO, MediaFormat.UNKNOWN
        
        # Audio types - Requirements 4.1: MP3, WAV, M4A, FLAC
        elif mime_lower.startswith('audio/'):
            if 'mp3' in mime_lower or filename_lower.endswith('.mp3'):
                return MediaType.AUDIO, MediaFormat.MP3
            elif 'wav' in mime_lower or filename_lower.endswith('.wav'):
                return MediaType.AUDIO, MediaFormat.WAV
            elif 'flac' in mime_lower or filename_lower.endswith('.flac'):
                return MediaType.AUDIO, MediaFormat.FLAC
            elif 'aac' in mime_lower or 'm4a' in mime_lower or filename_lower.endswith(('.m4a', '.aac')):
                return MediaType.AUDIO, MediaFormat.AAC  # M4A is AAC in MP4 container
            elif 'ogg' in mime_lower or filename_lower.endswith('.ogg'):
                return MediaType.AUDIO, MediaFormat.OGG
            elif 'wma' in mime_lower or filename_lower.endswith('.wma'):
                return MediaType.AUDIO, MediaFormat.WMA
            else:
                return MediaType.AUDIO, MediaFormat.UNKNOWN
        
        # PDF documents
        elif mime_lower == 'application/pdf' or filename_lower.endswith('.pdf'):
            return MediaType.DOCUMENT_SCAN, MediaFormat.PDF
        
        # Default to other
        else:
            return MediaType.OTHER, MediaFormat.UNKNOWN
    
    async def _extract_basic_metadata(self, file_path: Path, media_type: MediaType) -> Dict[str, Any]:
        """Extract basic metadata from media file using appropriate libraries"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            partial(self._sync_extract_metadata, file_path, media_type)
        )

    def _sync_extract_metadata(self, file_path: Path, media_type: MediaType) -> Dict[str, Any]:
        """Synchronous part of metadata extraction to be run in thread pool"""
        metadata = {}
        
        try:
            if media_type == MediaType.IMAGE:
                from PIL import Image
                with Image.open(file_path) as img:
                    metadata['width'] = img.width
                    metadata['height'] = img.height
                    
            elif media_type in [MediaType.VIDEO, MediaType.AUDIO]:
                import ffmpeg
                try:
                    probe = ffmpeg.probe(str(file_path))
                    
                    # Extract stream info
                    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                    audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
                    format_info = probe.get('format', {})
                    
                    # Duration from format info
                    if 'duration' in format_info:
                        metadata['duration'] = int(float(format_info['duration']))
                    
                    # Bitrate from format info
                    if 'bit_rate' in format_info:
                        metadata['bit_rate'] = int(format_info['bit_rate'])
                    
                    if video_stream:
                        # Video dimensions
                        if 'width' in video_stream:
                            metadata['width'] = int(video_stream['width'])
                        if 'height' in video_stream:
                            metadata['height'] = int(video_stream['height'])
                            
                        # Frame rate parsing (e.g., "30000/1001" or "25/1")
                        if 'avg_frame_rate' in video_stream:
                            try:
                                num, den = video_stream['avg_frame_rate'].split('/')
                                if int(den) > 0:
                                    metadata['frame_rate'] = int(int(num) / int(den))
                            except (ValueError, ZeroDivisionError):
                                pass
                                
                    if audio_stream:
                        # Audio specific metadata
                        if 'sample_rate' in audio_stream:
                            metadata['sample_rate'] = int(audio_stream['sample_rate'])
                        if not metadata.get('bit_rate') and 'bit_rate' in audio_stream:
                            metadata['bit_rate'] = int(audio_stream['bit_rate'])
                            
                except ffmpeg.Error as e:
                    logger.error("FFmpeg probe failed", file_path=str(file_path), error=e.stderr.decode() if e.stderr else str(e))
                except Exception as e:
                    logger.error("Internal error during FFmpeg probe", file_path=str(file_path), error=str(e))
                        
        except ImportError as e:
            logger.error("Required library for metadata extraction not installed", error=str(e))
        except Exception as e:
            logger.error("Unexpected error extracting metadata", file_path=str(file_path), error=str(e))
            
        return metadata
    
    async def _queue_processing_jobs(self, media_evidence: MediaEvidence, user_id: UUID):
        """Queue background processing jobs for media analysis"""
        
        # Create thumbnail generation job
        thumbnail_job = MediaProcessingJob(
            media_id=media_evidence.id,
            job_type="thumbnail",
            priority=8,  # High priority for thumbnails
            created_by=user_id
        )
        self.db.add(thumbnail_job)
        
        # Create OCR job for images and PDFs
        if media_evidence.media_type in [MediaType.IMAGE, MediaType.DOCUMENT_SCAN]:
            ocr_job = MediaProcessingJob(
                media_id=media_evidence.id,
                job_type="ocr",
                priority=5,
                created_by=user_id
            )
            self.db.add(ocr_job)
        
        # Create transcription job for audio/video
        if media_evidence.media_type in [MediaType.AUDIO, MediaType.VIDEO]:
            transcription_job = MediaProcessingJob(
                media_id=media_evidence.id,
                job_type="transcription",
                priority=6,
                created_by=user_id
            )
            self.db.add(transcription_job)
        
        await self.db.commit()
    async def create_secure_share_link(
        self,
        media_id: UUID,
        user_id: UUID,
        expiration_hours: int = 24,
        view_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create secure sharing link for media evidence
        
        Args:
            media_id: Media evidence ID
            user_id: User creating the share link
            expiration_hours: Link expiration in hours
            view_limit: Optional maximum number of views
            
        Returns:
            Dictionary with share link details
        """
        try:
            # Verify media exists
            media = await self.get_media(media_id, include_annotations=False)
            if not media:
                raise CaseManagementException(f"Media {media_id} not found")
            
            # Generate secure token
            import secrets
            share_token = secrets.token_urlsafe(48)
            
            # Calculate expiration time
            from datetime import datetime, timezone, timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)
            
            # Create share link record
            from models.media import MediaShareLink
            share_link = MediaShareLink(
                media_id=media_id,
                share_token=share_token,
                expires_at=expires_at,
                view_limit=view_limit,
                created_by=user_id
            )
            
            self.db.add(share_link)
            await self.db.commit()
            await self.db.refresh(share_link)
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="media_share_link",
                entity_id=share_link.id,
                action="create",
                user_id=user_id,
                case_id=media.case_id,
                entity_name=media.original_filename,
                new_value=f"Created share link for media: {media.original_filename}"
            )
            
            logger.info(
                "Secure share link created",
                media_id=str(media_id),
                share_token=share_token[:8] + "...",
                expires_at=expires_at,
                view_limit=view_limit,
                user_id=str(user_id)
            )
            
            return {
                "token": share_token,
                "expires_at": expires_at,
                "view_limit": view_limit,
                "media_id": media_id
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create share link", media_id=str(media_id), error=str(e))
            raise CaseManagementException(f"Failed to create share link: {str(e)}")
    
    async def access_shared_media(
        self,
        share_token: str,
        ip_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Access media through secure sharing link
        
        Args:
            share_token: Secure sharing token
            ip_address: Client IP address
            
        Returns:
            Dictionary with media info or None if invalid
        """
        try:
            from models.media import MediaShareLink
            from datetime import datetime, timezone
            
            # Get share link
            result = await self.db.execute(
                select(MediaShareLink)
                .where(MediaShareLink.share_token == share_token)
                .options(selectinload(MediaShareLink.media))
            )
            share_link = result.scalar_one_or_none()
            
            if not share_link:
                return None
            
            # Check if link is valid
            if not share_link.is_valid:
                logger.warning(
                    "Invalid share link access attempt",
                    share_token=share_token[:8] + "...",
                    ip_address=ip_address,
                    expired=share_link.is_expired,
                    view_limit_exceeded=share_link.is_view_limit_exceeded,
                    active=share_link.is_active
                )
                return None
            
            # Update access tracking
            share_link.view_count += 1
            share_link.last_accessed_at = datetime.now(timezone.utc)
            share_link.last_accessed_ip = ip_address
            
            # Log access
            await self.log_media_access(
                media_id=share_link.media_id,
                user_id=None,  # Anonymous access via share link
                access_type="shared_view",
                ip_address=ip_address,
                share_token=share_token
            )
            
            await self.db.commit()
            
            logger.info(
                "Shared media accessed",
                media_id=str(share_link.media_id),
                share_token=share_token[:8] + "...",
                view_count=share_link.view_count,
                ip_address=ip_address
            )
            
            return {
                "media": share_link.media,
                "share_link": share_link,
                "views_remaining": share_link.views_remaining
            }
            
        except Exception as e:
            logger.error("Failed to access shared media", share_token=share_token[:8] + "...", error=str(e))
            return None
    
    async def log_media_access(
        self,
        media_id: UUID,
        access_type: str,
        ip_address: str,
        user_id: Optional[UUID] = None,
        share_token: Optional[str] = None,
        bytes_served: Optional[int] = None,
        response_status: Optional[int] = None,
        duration_ms: Optional[int] = None
    ):
        """
        Log media access for audit purposes
        
        Args:
            media_id: Media evidence ID
            access_type: Type of access (view, download, stream, share)
            ip_address: Client IP address
            user_id: Optional user ID (for authenticated access)
            share_token: Optional share token (for shared access)
            bytes_served: Optional bytes served (for streaming/download)
            response_status: Optional HTTP response status
            duration_ms: Optional request duration in milliseconds
        """
        try:
            from models.media import MediaAccessLog
            
            access_log = MediaAccessLog(
                media_id=media_id,
                access_type=access_type,
                user_id=user_id,
                share_token=share_token,
                ip_address=ip_address,
                bytes_served=bytes_served,
                response_status=response_status,
                duration_ms=duration_ms
            )
            
            self.db.add(access_log)
            await self.db.commit()
            
            logger.info(
                "Media access logged",
                media_id=str(media_id),
                access_type=access_type,
                user_id=str(user_id) if user_id else None,
                ip_address=ip_address
            )
            
        except Exception as e:
            logger.error("Failed to log media access", media_id=str(media_id), error=str(e))
            # Don't raise exception for logging failures