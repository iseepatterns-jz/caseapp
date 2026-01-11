"""
Media evidence management API endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.auth import get_current_user
from models.user import User
from services.media_service import MediaService
from services.audit_service import AuditService
from schemas.media import (
    MediaUploadRequest, MediaUpdateRequest, MediaSearchRequest,
    MediaAnnotationCreateRequest, MediaAnnotationUpdateRequest,
    MediaEvidenceResponse, MediaEvidenceSummaryResponse, MediaListResponse,
    MediaAnnotationResponse, MediaStatisticsResponse, MediaAnalysisRequest,
    MediaProcessingJobResponse, MediaTypeEnum, MediaFormatEnum
)
from core.exceptions import CaseManagementException
import structlog

logger = structlog.get_logger()

router = APIRouter()

def get_media_service(
    db: AsyncSession = Depends(get_db)
) -> MediaService:
    """Get media service instance"""
    audit_service = AuditService(db)
    return MediaService(db, audit_service)

@router.post("/upload", response_model=MediaEvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    case_id: UUID = Form(...),
    media_type: MediaTypeEnum = Form(...),
    evidence_number: Optional[str] = Form(None),
    captured_by: Optional[str] = Form(None),
    capture_location: Optional[str] = Form(None),
    capture_device: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma-separated tags
    categories: Optional[str] = Form(None),  # Comma-separated categories
    is_privileged: bool = Form(False),
    privilege_reason: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Upload media evidence file
    
    - **file**: Media file to upload
    - **case_id**: Case ID to associate media with
    - **media_type**: Type of media (image, video, audio, etc.)
    - **evidence_number**: Optional official evidence number
    - **captured_by**: Who captured the media
    - **capture_location**: Where the media was captured
    - **capture_device**: Device used to capture media
    - **tags**: Comma-separated tags for categorization
    - **categories**: Comma-separated categories for organization
    - **is_privileged**: Whether media is privileged
    - **privilege_reason**: Reason for privilege if applicable
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Parse tags and categories
        parsed_tags = [tag.strip() for tag in tags.split(",")] if tags else []
        parsed_categories = [cat.strip() for cat in categories.split(",")] if categories else []
        
        # Create upload request
        upload_request = MediaUploadRequest(
            case_id=case_id,
            media_type=media_type,
            evidence_number=evidence_number,
            captured_by=captured_by,
            capture_location=capture_location,
            capture_device=capture_device,
            tags=parsed_tags,
            categories=parsed_categories,
            is_privileged=is_privileged,
            privilege_reason=privilege_reason
        )
        
        # Upload media
        media_evidence = await media_service.upload_media(
            file=file,
            upload_request=upload_request,
            user_id=current_user.id
        )
        
        return MediaEvidenceResponse.from_orm(media_evidence)
        
    except CaseManagementException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Media upload failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload media"
        )

@router.get("/{media_id}", response_model=MediaEvidenceResponse)
async def get_media(
    media_id: UUID,
    include_annotations: bool = Query(True, description="Include annotations in response"),
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Get media evidence by ID
    
    - **media_id**: Media evidence ID
    - **include_annotations**: Whether to include annotations
    """
    try:
        media = await media_service.get_media(media_id, include_annotations)
        if not media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media {media_id} not found"
            )
        
        return MediaEvidenceResponse.from_orm(media)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get media", media_id=str(media_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get media"
        )

@router.get("/{media_id}/download")
async def download_media(
    media_id: UUID,
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Download media evidence file
    
    - **media_id**: Media evidence ID
    """
    try:
        media = await media_service.get_media(media_id, include_annotations=False)
        if not media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media {media_id} not found"
            )
        
        # Check if file exists
        import os
        if not os.path.exists(media.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media file not found on disk"
            )
        
        return FileResponse(
            path=media.file_path,
            filename=media.original_filename,
            media_type=media.mime_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download media", media_id=str(media_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download media"
        )

@router.get("/{media_id}/thumbnail")
async def get_media_thumbnail(
    media_id: UUID,
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Get media thumbnail
    
    - **media_id**: Media evidence ID
    """
    try:
        media = await media_service.get_media(media_id, include_annotations=False)
        if not media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media {media_id} not found"
            )
        
        if not media.thumbnail_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thumbnail not available"
            )
        
        # Check if thumbnail exists
        import os
        if not os.path.exists(media.thumbnail_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thumbnail file not found on disk"
            )
        
        return FileResponse(
            path=media.thumbnail_path,
            media_type="image/jpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get thumbnail", media_id=str(media_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get thumbnail"
        )

@router.post("/search", response_model=MediaListResponse)
async def search_media(
    search_request: MediaSearchRequest,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Search media evidence with filters
    
    - **search_request**: Search criteria and filters
    - **page**: Page number (1-based)
    - **per_page**: Items per page (max 100)
    """
    try:
        media_list, total_count = await media_service.search_media(
            search_request=search_request,
            page=page,
            per_page=per_page
        )
        
        # Convert to summary responses
        items = [MediaEvidenceSummaryResponse.from_orm(media) for media in media_list]
        
        # Calculate pagination info
        pages = (total_count + per_page - 1) // per_page
        has_next = page < pages
        has_prev = page > 1
        
        return MediaListResponse(
            items=items,
            total=total_count,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except Exception as e:
        logger.error("Media search failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search media"
        )

@router.get("/case/{case_id}", response_model=MediaListResponse)
async def get_case_media(
    case_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    media_type: Optional[MediaTypeEnum] = Query(None, description="Filter by media type"),
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Get media evidence for a specific case
    
    - **case_id**: Case ID
    - **page**: Page number (1-based)
    - **per_page**: Items per page (max 100)
    - **media_type**: Optional media type filter
    """
    try:
        # Create search request for case
        search_request = MediaSearchRequest(
            case_id=case_id,
            media_types=[media_type] if media_type else None
        )
        
        media_list, total_count = await media_service.search_media(
            search_request=search_request,
            page=page,
            per_page=per_page
        )
        
        # Convert to summary responses
        items = [MediaEvidenceSummaryResponse.from_orm(media) for media in media_list]
        
        # Calculate pagination info
        pages = (total_count + per_page - 1) // per_page
        has_next = page < pages
        has_prev = page > 1
        
        return MediaListResponse(
            items=items,
            total=total_count,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except Exception as e:
        logger.error("Failed to get case media", case_id=str(case_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get case media"
        )

@router.get("/{media_id}/stream")
async def stream_media(
    media_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Stream media evidence file with HTTP range request support
    
    - **media_id**: Media evidence ID
    """
    try:
        media = await media_service.get_media(media_id, include_annotations=False)
        if not media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media {media_id} not found"
            )
        
        # Check if file exists
        import os
        if not os.path.exists(media.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media file not found on disk"
            )
        
        # Log media access for audit
        await media_service.log_media_access(
            media_id=media_id,
            user_id=current_user.id,
            access_type="stream",
            ip_address=request.client.host if request.client else "unknown"
        )
        
        # Handle range requests for streaming
        range_header = request.headers.get('range')
        
        if range_header:
            return await _handle_range_request(media.file_path, range_header, media.mime_type)
        else:
            # Return full file
            return FileResponse(
                path=media.file_path,
                media_type=media.mime_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(media.file_size)
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to stream media", media_id=str(media_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stream media"
        )

@router.post("/{media_id}/share", response_model=dict)
async def create_secure_share_link(
    media_id: UUID,
    expiration_hours: int = Form(24, description="Link expiration in hours"),
    view_limit: Optional[int] = Form(None, description="Maximum number of views"),
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Create secure sharing link for media evidence
    
    - **media_id**: Media evidence ID
    - **expiration_hours**: Link expiration time in hours (default 24)
    - **view_limit**: Optional maximum number of views
    """
    try:
        media = await media_service.get_media(media_id, include_annotations=False)
        if not media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media {media_id} not found"
            )
        
        # Create secure share link
        share_link = await media_service.create_secure_share_link(
            media_id=media_id,
            user_id=current_user.id,
            expiration_hours=expiration_hours,
            view_limit=view_limit
        )
        
        return {
            "share_token": share_link["token"],
            "share_url": f"/api/v1/media/shared/{share_link['token']}",
            "expires_at": share_link["expires_at"],
            "view_limit": share_link["view_limit"],
            "views_remaining": share_link["view_limit"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create share link", media_id=str(media_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create share link"
        )

@router.get("/shared/{share_token}")
async def access_shared_media(
    share_token: str,
    request: Request,
    media_service: MediaService = Depends(get_media_service)
):
    """
    Access media through secure sharing link
    
    - **share_token**: Secure sharing token
    """
    try:
        # Validate and consume share link
        media_info = await media_service.access_shared_media(
            share_token=share_token,
            ip_address=request.client.host if request.client else "unknown"
        )
        
        if not media_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired share link"
            )
        
        media = media_info["media"]
        
        # Check if file exists
        import os
        if not os.path.exists(media.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media file not found on disk"
            )
        
        # Handle range requests for streaming
        range_header = request.headers.get('range')
        
        if range_header:
            return await _handle_range_request(media.file_path, range_header, media.mime_type)
        else:
            # Return full file
            return FileResponse(
                path=media.file_path,
                media_type=media.mime_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(media.file_size)
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to access shared media", share_token=share_token, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to access shared media"
        )

async def _handle_range_request(file_path: str, range_header: str, mime_type: str):
    """Handle HTTP range requests for media streaming"""
    import os
    from fastapi.responses import Response
    
    file_size = os.path.getsize(file_path)
    
    # Parse range header (e.g., "bytes=0-1023")
    try:
        range_match = range_header.replace('bytes=', '').split('-')
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if range_match[1] else file_size - 1
        
        # Validate range
        if start >= file_size or end >= file_size or start > end:
            return Response(
                status_code=416,  # Range Not Satisfiable
                headers={
                    "Content-Range": f"bytes */{file_size}"
                }
            )
        
        # Read requested range
        with open(file_path, 'rb') as f:
            f.seek(start)
            chunk_size = end - start + 1
            data = f.read(chunk_size)
        
        return Response(
            content=data,
            status_code=206,  # Partial Content
            media_type=mime_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(chunk_size)
            }
        )
        
    except (ValueError, IndexError):
        # Invalid range header
        return Response(
            status_code=400,
            content="Invalid range header"
        )

@router.get("/statistics", response_model=MediaStatisticsResponse)
async def get_media_statistics(
    case_id: Optional[UUID] = Query(None, description="Filter by case ID"),
    current_user: User = Depends(get_current_user),
    media_service: MediaService = Depends(get_media_service)
):
    """
    Get media evidence statistics
    
    - **case_id**: Optional case ID to filter by
    """
    try:
        stats = await media_service.get_media_statistics(case_id)
        return MediaStatisticsResponse(**stats)
        
    except Exception as e:
        logger.error("Failed to get media statistics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get media statistics"
        )