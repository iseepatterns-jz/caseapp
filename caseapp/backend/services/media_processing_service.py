"""
Media processing service for background analysis tasks
"""

import os
import asyncio
from typing import List, Optional, Dict, Any
from uuid import UUID
from pathlib import Path
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from PIL import Image, ImageOps
import hashlib

from models.media import MediaEvidence, MediaProcessingJob, ProcessingStatus, MediaType
from core.database import get_db
from core.exceptions import CaseManagementException

logger = structlog.get_logger()

class MediaProcessingService:
    """Service for processing media evidence in background"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.thumbnail_size = (200, 200)
        self.preview_size = (800, 600)
    
    async def process_pending_jobs(self, limit: int = 10) -> int:
        """
        Process pending media processing jobs
        
        Args:
            limit: Maximum number of jobs to process
            
        Returns:
            Number of jobs processed
        """
        try:
            # Get pending jobs ordered by priority and creation time
            result = await self.db.execute(
                select(MediaProcessingJob)
                .where(MediaProcessingJob.status == ProcessingStatus.PENDING)
                .order_by(MediaProcessingJob.priority.desc(), MediaProcessingJob.created_at.asc())
                .limit(limit)
            )
            
            jobs = result.scalars().all()
            processed_count = 0
            
            for job in jobs:
                try:
                    await self._process_job(job)
                    processed_count += 1
                except Exception as e:
                    logger.error(
                        "Job processing failed",
                        job_id=str(job.id),
                        job_type=job.job_type,
                        error=str(e)
                    )
                    await self._mark_job_failed(job, str(e))
            
            logger.info(f"Processed {processed_count} media processing jobs")
            return processed_count
            
        except Exception as e:
            logger.error("Failed to process media jobs", error=str(e))
            return 0
    
    async def _process_job(self, job: MediaProcessingJob):
        """Process a single media processing job"""
        
        # Mark job as processing
        job.status = ProcessingStatus.PROCESSING
        job.started_at = asyncio.get_event_loop().time()
        await self.db.commit()
        
        try:
            # Get associated media
            media_result = await self.db.execute(
                select(MediaEvidence).where(MediaEvidence.id == job.media_id)
            )
            media = media_result.scalar_one_or_none()
            
            if not media:
                raise CaseManagementException(f"Media {job.media_id} not found")
            
            # Process based on job type
            if job.job_type == "thumbnail":
                await self._generate_thumbnail(media, job)
            elif job.job_type == "preview":
                await self._generate_preview(media, job)
            elif job.job_type == "ocr":
                await self._extract_text_ocr(media, job)
            elif job.job_type == "transcription":
                await self._transcribe_audio(media, job)
            elif job.job_type == "object_detection":
                await self._detect_objects(media, job)
            elif job.job_type == "face_detection":
                await self._detect_faces(media, job)
            else:
                raise CaseManagementException(f"Unknown job type: {job.job_type}")
            
            # Mark job as completed
            job.status = ProcessingStatus.COMPLETED
            job.completed_at = asyncio.get_event_loop().time()
            await self.db.commit()
            
            logger.info(
                "Job completed successfully",
                job_id=str(job.id),
                job_type=job.job_type,
                media_id=str(job.media_id)
            )
            
        except Exception as e:
            await self._mark_job_failed(job, str(e))
            raise
    
    async def _generate_thumbnail(self, media: MediaEvidence, job: MediaProcessingJob):
        """Generate thumbnail for image/video media"""
        
        if media.media_type not in [MediaType.IMAGE, MediaType.VIDEO, MediaType.DOCUMENT_SCAN]:
            job.status = ProcessingStatus.SKIPPED
            job.result_data = {"reason": "Media type not supported for thumbnails"}
            return
        
        try:
            # For images and PDFs, use PIL
            if media.media_type in [MediaType.IMAGE, MediaType.DOCUMENT_SCAN]:
                await self._generate_image_thumbnail(media, job)
            elif media.media_type == MediaType.VIDEO:
                # For videos, we'd use ffmpeg or similar - for now, skip
                job.status = ProcessingStatus.SKIPPED
                job.result_data = {"reason": "Video thumbnail generation not implemented"}
                
        except Exception as e:
            raise CaseManagementException(f"Thumbnail generation failed: {str(e)}")
    
    async def _generate_image_thumbnail(self, media: MediaEvidence, job: MediaProcessingJob):
        """Generate thumbnail for image files"""
        
        if not os.path.exists(media.file_path):
            raise CaseManagementException("Source file not found")
        
        try:
            # Open image
            with Image.open(media.file_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Generate thumbnail
                img.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
                
                # Create thumbnail path
                thumbnail_dir = Path(media.file_path).parent / "thumbnails"
                thumbnail_dir.mkdir(exist_ok=True)
                
                thumbnail_filename = f"thumb_{Path(media.filename).stem}.jpg"
                thumbnail_path = thumbnail_dir / thumbnail_filename
                
                # Save thumbnail
                img.save(thumbnail_path, "JPEG", quality=85, optimize=True)
                
                # Update media record
                media.thumbnail_path = str(thumbnail_path)
                
                # Store job results
                job.result_data = {
                    "thumbnail_path": str(thumbnail_path),
                    "thumbnail_size": img.size,
                    "original_size": Image.open(media.file_path).size
                }
                job.output_files = [str(thumbnail_path)]
                
                logger.info(
                    "Thumbnail generated",
                    media_id=str(media.id),
                    thumbnail_path=str(thumbnail_path),
                    size=img.size
                )
                
        except Exception as e:
            raise CaseManagementException(f"Image thumbnail generation failed: {str(e)}")
    
    async def _generate_preview(self, media: MediaEvidence, job: MediaProcessingJob):
        """Generate preview/compressed version for large media"""
        
        if media.media_type != MediaType.IMAGE:
            job.status = ProcessingStatus.SKIPPED
            job.result_data = {"reason": "Preview generation only supported for images"}
            return
        
        if not os.path.exists(media.file_path):
            raise CaseManagementException("Source file not found")
        
        try:
            with Image.open(media.file_path) as img:
                # Only generate preview if image is large enough
                if img.size[0] <= self.preview_size[0] and img.size[1] <= self.preview_size[1]:
                    job.status = ProcessingStatus.SKIPPED
                    job.result_data = {"reason": "Image too small for preview generation"}
                    return
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize for preview
                img.thumbnail(self.preview_size, Image.Resampling.LANCZOS)
                
                # Create preview path
                preview_dir = Path(media.file_path).parent / "previews"
                preview_dir.mkdir(exist_ok=True)
                
                preview_filename = f"preview_{Path(media.filename).stem}.jpg"
                preview_path = preview_dir / preview_filename
                
                # Save preview
                img.save(preview_path, "JPEG", quality=80, optimize=True)
                
                # Update media record
                media.preview_path = str(preview_path)
                
                # Store job results
                job.result_data = {
                    "preview_path": str(preview_path),
                    "preview_size": img.size,
                    "compression_ratio": os.path.getsize(preview_path) / media.file_size
                }
                job.output_files = [str(preview_path)]
                
        except Exception as e:
            raise CaseManagementException(f"Preview generation failed: {str(e)}")
    
    async def _extract_text_ocr(self, media: MediaEvidence, job: MediaProcessingJob):
        """Extract text from images using OCR (placeholder implementation)"""
        
        if media.media_type not in [MediaType.IMAGE, MediaType.DOCUMENT_SCAN]:
            job.status = ProcessingStatus.SKIPPED
            job.result_data = {"reason": "OCR only supported for images and document scans"}
            return
        
        # Placeholder OCR implementation
        # In a real system, you'd use libraries like pytesseract, AWS Textract, etc.
        
        job.status = ProcessingStatus.SKIPPED
        job.result_data = {
            "reason": "OCR not implemented - would use pytesseract or cloud OCR service",
            "extracted_text": ""
        }
        
        # Update media with extracted text (empty for now)
        media.extracted_text = ""
    
    async def _transcribe_audio(self, media: MediaEvidence, job: MediaProcessingJob):
        """Transcribe audio/video files (placeholder implementation)"""
        
        if media.media_type not in [MediaType.AUDIO, MediaType.VIDEO]:
            job.status = ProcessingStatus.SKIPPED
            job.result_data = {"reason": "Transcription only supported for audio and video"}
            return
        
        # Placeholder transcription implementation
        # In a real system, you'd use services like AWS Transcribe, Google Speech-to-Text, etc.
        
        job.status = ProcessingStatus.SKIPPED
        job.result_data = {
            "reason": "Transcription not implemented - would use cloud speech-to-text service",
            "transcript": ""
        }
        
        # Update media with transcript (empty for now)
        media.audio_transcript = ""
    
    async def _detect_objects(self, media: MediaEvidence, job: MediaProcessingJob):
        """Detect objects in images (placeholder implementation)"""
        
        if media.media_type != MediaType.IMAGE:
            job.status = ProcessingStatus.SKIPPED
            job.result_data = {"reason": "Object detection only supported for images"}
            return
        
        # Placeholder object detection implementation
        # In a real system, you'd use services like AWS Rekognition, Google Vision API, etc.
        
        job.status = ProcessingStatus.SKIPPED
        job.result_data = {
            "reason": "Object detection not implemented - would use cloud vision service",
            "detected_objects": []
        }
        
        # Update media with detected objects (empty for now)
        media.detected_objects = []
    
    async def _detect_faces(self, media: MediaEvidence, job: MediaProcessingJob):
        """Detect faces in images (placeholder implementation)"""
        
        if media.media_type != MediaType.IMAGE:
            job.status = ProcessingStatus.SKIPPED
            job.result_data = {"reason": "Face detection only supported for images"}
            return
        
        # Placeholder face detection implementation
        # In a real system, you'd use services like AWS Rekognition, OpenCV, etc.
        
        job.status = ProcessingStatus.SKIPPED
        job.result_data = {
            "reason": "Face detection not implemented - would use cloud vision service",
            "detected_faces": []
        }
        
        # Update media with detected faces (empty for now)
        media.detected_faces = []
    
    async def _mark_job_failed(self, job: MediaProcessingJob, error_message: str):
        """Mark job as failed and handle retry logic"""
        
        job.status = ProcessingStatus.FAILED
        job.error_message = error_message
        job.retry_count += 1
        job.completed_at = asyncio.get_event_loop().time()
        
        await self.db.commit()
        
        logger.error(
            "Job marked as failed",
            job_id=str(job.id),
            job_type=job.job_type,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            error=error_message
        )
    
    async def retry_failed_jobs(self, limit: int = 5) -> int:
        """
        Retry failed jobs that haven't exceeded max retries
        
        Args:
            limit: Maximum number of jobs to retry
            
        Returns:
            Number of jobs queued for retry
        """
        try:
            # Get failed jobs that can be retried
            result = await self.db.execute(
                select(MediaProcessingJob)
                .where(
                    and_(
                        MediaProcessingJob.status == ProcessingStatus.FAILED,
                        MediaProcessingJob.retry_count < MediaProcessingJob.max_retries
                    )
                )
                .order_by(MediaProcessingJob.priority.desc(), MediaProcessingJob.created_at.asc())
                .limit(limit)
            )
            
            jobs = result.scalars().all()
            retry_count = 0
            
            for job in jobs:
                # Reset job status for retry
                job.status = ProcessingStatus.PENDING
                job.error_message = None
                job.started_at = None
                job.completed_at = None
                retry_count += 1
            
            await self.db.commit()
            
            logger.info(f"Queued {retry_count} failed jobs for retry")
            return retry_count
            
        except Exception as e:
            logger.error("Failed to retry jobs", error=str(e))
            return 0

async def run_media_processor():
    """Background task to process media jobs"""
    
    logger.info("Media processor starting...")
    
    while True:
        async for db in get_db():
            try:
                processor = MediaProcessingService(db)
                
                # Process pending jobs
                processed = await processor.process_pending_jobs(limit=10)
                
                # Retry failed jobs occasionally
                if processed == 0:  # Only retry when no pending jobs
                    await processor.retry_failed_jobs(limit=3)
                    
            except Exception as e:
                logger.error("Media processor error", error=str(e))
            finally:
                await db.close()
            
            # Wait before next processing cycle
            await asyncio.sleep(30)  # Process every 30 seconds
            break  # Exit the async for loop after one iteration
        
        # Small delay between cycles
        await asyncio.sleep(1)

if __name__ == "__main__":
    """Entry point when run as a module"""
    logger.info("Starting media processing service...")
    asyncio.run(run_media_processor())