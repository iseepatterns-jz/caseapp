"""
Collaboration API endpoints for real-time timeline sharing and presence
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from typing import List, Optional, Dict, Any
import structlog
from datetime import datetime

from core.database import get_db
from models.timeline import CaseTimeline, TimelineCollaboration, CollaborationSession, TimelineComment
from models.user import User
from services.timeline_collaboration_service import TimelineCollaborationService
from services.presence_service import PresenceService
from services.notification_service import NotificationService
from services.external_sharing_service import ExternalSharingService
from schemas.collaboration import (
    CollaborationShareRequest, CollaborationResponse, PresenceResponse,
    SessionStartRequest, SessionUpdateRequest, CommentCreateRequest, CommentResponse,
    ExternalShareRequest, ExternalShareResponse
)
from core.auth import get_current_user

logger = structlog.get_logger()
router = APIRouter()

collaboration_service = TimelineCollaborationService()
presence_service = PresenceService()
notification_service = NotificationService()
external_sharing_service = ExternalSharingService()

@router.post("/timelines/{timeline_id}/share", response_model=CollaborationResponse)
async def share_timeline(
    timeline_id: str,
    share_request: CollaborationShareRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Share timeline with a user with granular permissions (Requirements 6.1)"""
    
    try:
        collaboration = await collaboration_service.share_timeline(
            timeline_id=timeline_id,
            user_id=share_request.user_id,
            permissions=share_request.permissions.dict(),
            shared_by_id=current_user.id,
            message=share_request.message
        )
        
        return CollaborationResponse(
            id=str(collaboration.id),
            timeline_id=str(collaboration.timeline_id),
            user_id=str(collaboration.user_id),
            permissions=share_request.permissions,
            shared_at=collaboration.created_at,
            shared_by_id=str(collaboration.created_by_id),
            message=collaboration.shared_message
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to share timeline", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to share timeline")
    finally:
        # Send notification about timeline sharing
        try:
            await notification_service.notify_timeline_shared(
                timeline_id=timeline_id,
                shared_with_user_id=share_request.user_id,
                shared_by_user_id=str(current_user.id),
                permissions=share_request.permissions.dict(),
                message=share_request.message
            )
        except Exception as e:
            logger.warning("Failed to send sharing notification", error=str(e))

@router.get("/timelines/{timeline_id}/collaborators", response_model=List[CollaborationResponse])
async def get_timeline_collaborators(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all collaborators for a timeline"""
    
    try:
        collaborators = await collaboration_service.get_timeline_collaborators(timeline_id)
        
        return [
            CollaborationResponse(
                id=str(collab['collaboration_id']) if 'collaboration_id' in collab else None,
                timeline_id=timeline_id,
                user_id=str(collab['user_id']),
                user_name=collab['user_name'],
                user_email=collab['user_email'],
                permissions=collab['permissions'],
                shared_at=collab['shared_at'],
                receive_notifications=collab['receive_notifications']
            )
            for collab in collaborators
        ]
        
    except Exception as e:
        logger.error("Failed to get timeline collaborators", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get collaborators")

@router.put("/timelines/{timeline_id}/collaborators/{user_id}", response_model=CollaborationResponse)
async def update_collaboration_permissions(
    timeline_id: str,
    user_id: str,
    permissions_update: CollaborationShareRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update collaboration permissions for a user"""
    
    try:
        collaboration = await collaboration_service.update_collaboration_permissions(
            timeline_id=timeline_id,
            user_id=user_id,
            permissions=permissions_update.permissions.dict(),
            updated_by_id=current_user.id
        )
        
        return CollaborationResponse(
            id=str(collaboration.id),
            timeline_id=str(collaboration.timeline_id),
            user_id=str(collaboration.user_id),
            permissions=permissions_update.permissions,
            shared_at=collaboration.created_at,
            updated_at=collaboration.updated_at
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to update collaboration permissions", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update permissions")

@router.delete("/timelines/{timeline_id}/collaborators/{user_id}")
async def remove_collaboration(
    timeline_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Remove collaboration access for a user"""
    
    try:
        success = await collaboration_service.remove_collaboration(
            timeline_id=timeline_id,
            user_id=user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Collaboration not found")
        
        return {"message": "Collaboration removed successfully"}
        
    except Exception as e:
        logger.error("Failed to remove collaboration", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to remove collaboration")

@router.post("/timelines/{timeline_id}/sessions/start")
async def start_collaboration_session(
    timeline_id: str,
    session_request: SessionStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Start a real-time collaboration session (Requirements 6.2)"""
    
    try:
        # Get client metadata
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        session_metadata = {
            'ip_address': client_ip,
            'user_agent': user_agent,
            'initial_view': session_request.initial_view
        }
        
        session_id = await presence_service.start_collaboration_session(
            timeline_id=timeline_id,
            user_id=str(current_user.id),
            session_metadata=session_metadata
        )
        
        # Broadcast presence update to other users
        await presence_service.broadcast_presence_update(
            timeline_id=timeline_id,
            update_data={
                'type': 'user_joined',
                'user_id': str(current_user.id),
                'user_name': current_user.full_name,
                'session_id': session_id
            }
        )
        
        return {
            "session_id": session_id,
            "message": "Collaboration session started successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to start collaboration session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to start session")

@router.post("/sessions/{session_id}/update")
async def update_session_activity(
    session_id: str,
    update_request: SessionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update session activity and presence data (Requirements 6.2)"""
    
    try:
        success = await presence_service.update_session_activity(
            session_id=session_id,
            activity_data=update_request.dict(exclude_unset=True)
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Broadcast presence update if there are significant changes
        if update_request.cursor_position or update_request.editing_event_id:
            # Get timeline_id from session
            session_data = presence_service.active_sessions.get(session_id)
            if session_data:
                await presence_service.broadcast_presence_update(
                    timeline_id=session_data['timeline_id'],
                    update_data={
                        'type': 'presence_update',
                        'user_id': str(current_user.id),
                        'session_id': session_id,
                        'cursor_position': update_request.cursor_position,
                        'editing_event_id': update_request.editing_event_id
                    },
                    exclude_session_id=session_id
                )
        
        return {"message": "Session updated successfully"}
        
    except Exception as e:
        logger.error("Failed to update session activity", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update session")

@router.post("/sessions/{session_id}/end")
async def end_collaboration_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """End a collaboration session"""
    
    try:
        # Get session data before ending
        session_data = presence_service.active_sessions.get(session_id)
        
        success = await presence_service.end_collaboration_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Broadcast user left update
        if session_data:
            await presence_service.broadcast_presence_update(
                timeline_id=session_data['timeline_id'],
                update_data={
                    'type': 'user_left',
                    'user_id': str(current_user.id),
                    'session_id': session_id
                }
            )
        
        return {"message": "Collaboration session ended successfully"}
        
    except Exception as e:
        logger.error("Failed to end collaboration session", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to end session")

@router.get("/timelines/{timeline_id}/presence", response_model=List[PresenceResponse])
async def get_timeline_presence(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get current presence information for a timeline (Requirements 6.2)"""
    
    try:
        presence_data = await presence_service.get_timeline_presence(timeline_id)
        
        return [
            PresenceResponse(
                session_id=presence['session_id'],
                user_id=presence['user_id'],
                user_name=presence['user_name'],
                user_email=presence['user_email'],
                last_activity=presence['last_activity'],
                current_view=presence['current_view'],
                cursor_position=presence['cursor_position'],
                editing_event_id=presence['editing_event_id'],
                is_active=presence['is_active']
            )
            for presence in presence_data
        ]
        
    except Exception as e:
        logger.error("Failed to get timeline presence", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get presence data")

@router.get("/sessions/{session_id}/updates")
async def get_session_updates(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get pending updates for a collaboration session"""
    
    try:
        updates = await presence_service.get_session_updates(session_id)
        return {"updates": updates}
        
    except Exception as e:
        logger.error("Failed to get session updates", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get updates")

@router.post("/timelines/{timeline_id}/events/{event_id}/comments", response_model=CommentResponse)
async def create_timeline_comment(
    timeline_id: str,
    event_id: str,
    comment_request: CommentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a comment on a timeline event (Requirements 6.3)"""
    
    try:
        comment = await collaboration_service.add_timeline_comment(
            timeline_id=timeline_id,
            event_id=event_id,
            user_id=str(current_user.id),
            comment_text=comment_request.comment_text,
            parent_comment_id=comment_request.parent_comment_id,
            is_internal=comment_request.is_internal
        )
        
        return CommentResponse(
            id=str(comment.id),
            timeline_event_id=str(comment.timeline_event_id),
            comment_text=comment.comment_text,
            is_internal=comment.is_internal,
            parent_comment_id=str(comment.parent_comment_id) if comment.parent_comment_id else None,
            thread_depth=comment.thread_depth,
            created_at=comment.created_at,
            created_by_id=str(comment.created_by),
            user_name=current_user.full_name
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create timeline comment", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create comment")
    finally:
        # Send notification about new comment
        try:
            await notification_service.notify_comment_added(
                comment_id=str(comment.id),
                timeline_id=timeline_id,
                event_id=event_id,
                commenter_user_id=str(current_user.id),
                comment_text=comment_request.comment_text
            )
        except Exception as e:
            logger.warning("Failed to send comment notification", error=str(e))

@router.get("/timelines/{timeline_id}/events/{event_id}/comments", response_model=List[CommentResponse])
async def get_timeline_comments(
    timeline_id: str,
    event_id: str,
    include_internal: bool = Query(True, description="Include internal comments"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get comments for a timeline event (Requirements 6.3)"""
    
    try:
        comments = await collaboration_service.get_timeline_comments(
            event_id=event_id,
            include_internal=include_internal
        )
        
        return [
            CommentResponse(
                id=str(comment['id']),
                timeline_event_id=str(comment['timeline_event_id']),
                comment_text=comment['comment_text'],
                is_internal=comment['is_internal'],
                parent_comment_id=str(comment['parent_comment_id']) if comment['parent_comment_id'] else None,
                thread_depth=comment['thread_depth'],
                created_at=comment['created_at'],
                updated_at=comment['updated_at'],
                created_by_id=str(comment['created_by_id']),
                user_name=comment['user_name'],
                is_resolved=comment.get('is_resolved', False)
            )
            for comment in comments
        ]
        
    except Exception as e:
        logger.error("Failed to get timeline comments", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get comments")

@router.post("/timelines/{timeline_id}/external-share", response_model=ExternalShareResponse)
async def create_external_share_link(
    timeline_id: str,
    share_request: ExternalShareRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create external sharing link with expiration (Requirements 6.4)"""
    
    try:
        share_link = await external_sharing_service.create_share_link(
            timeline_id=timeline_id,
            created_by_id=str(current_user.id),
            expires_in_hours=share_request.expires_in_hours,
            view_limit=share_request.view_limit,
            password=share_request.password,
            allow_download=share_request.allow_download
        )
        
        return ExternalShareResponse(
            share_token=share_link.share_token,
            share_url=f"/shared/timeline/{share_link.share_token}",
            expires_at=share_link.expires_at,
            view_limit=share_link.view_limit,
            views_remaining=share_link.view_limit - share_link.view_count if share_link.view_limit else None,
            is_password_protected=share_link.password_hash is not None
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create external share link", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create share link")

@router.get("/timelines/{timeline_id}/external-shares")
async def get_timeline_external_shares(
    timeline_id: str,
    include_revoked: bool = Query(False, description="Include revoked share links"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all external share links for a timeline"""
    
    try:
        share_links = await external_sharing_service.get_timeline_share_links(
            timeline_id=timeline_id,
            include_revoked=include_revoked
        )
        
        return {
            "share_links": [
                {
                    "id": str(link.id),
                    "share_token": link.share_token,
                    "share_url": f"/shared/timeline/{link.share_token}",
                    "status": link.status,
                    "expires_at": link.expires_at.isoformat(),
                    "view_limit": link.view_limit,
                    "view_count": link.view_count,
                    "allow_download": link.allow_download,
                    "is_password_protected": link.password_hash is not None,
                    "created_at": link.created_at.isoformat(),
                    "last_accessed_at": link.last_accessed_at.isoformat() if link.last_accessed_at else None
                }
                for link in share_links
            ]
        }
        
    except Exception as e:
        logger.error("Failed to get external share links", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get share links")

@router.delete("/external-shares/{share_token}")
async def revoke_external_share_link(
    share_token: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Revoke an external share link"""
    
    try:
        success = await external_sharing_service.revoke_share_link(
            share_token=share_token,
            revoked_by_id=str(current_user.id)
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Share link not found")
        
        return {"message": "Share link revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to revoke share link", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to revoke share link")

@router.get("/external-shares/{share_token}/analytics")
async def get_share_link_analytics(
    share_token: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get analytics for an external share link"""
    
    try:
        # Get share link to verify ownership/access
        share_link = await external_sharing_service.get_share_link(share_token)
        
        if not share_link:
            raise HTTPException(status_code=404, detail="Share link not found")
        
        analytics = await external_sharing_service.get_share_link_analytics(
            share_link_id=str(share_link.id)
        )
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get share link analytics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get analytics")

@router.get("/shared/timeline/{share_token}")
async def access_shared_timeline(
    share_token: str,
    password: Optional[str] = Query(None, description="Password for protected links"),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Access a shared timeline via external link (Requirements 6.4)"""
    
    try:
        # Get client information
        ip_address = request.client.host if request else "unknown"
        user_agent = request.headers.get("user-agent", "") if request else ""
        
        # Validate access
        validation_result = await external_sharing_service.validate_share_link_access(
            share_token=share_token,
            password=password,
            ip_address=ip_address
        )
        
        if not validation_result['valid']:
            # Log failed access
            if validation_result.get('share_link'):
                await external_sharing_service.log_share_link_access(
                    share_link_id=str(validation_result['share_link'].id),
                    action='view',
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    failure_reason=validation_result['reason']
                )
            
            if validation_result.get('requires_password'):
                raise HTTPException(status_code=401, detail="Password required")
            else:
                raise HTTPException(status_code=403, detail=validation_result['reason'])
        
        share_link = validation_result['share_link']
        
        # Log successful access
        await external_sharing_service.log_share_link_access(
            share_link_id=str(share_link.id),
            action='view',
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )
        
        # Get timeline data (simplified for external access)
        async with db:
            timeline_result = await db.execute(
                select(CaseTimeline).where(CaseTimeline.id == share_link.timeline_id)
            )
            timeline = timeline_result.scalar_one()
            
            return {
                "timeline": {
                    "id": str(timeline.id),
                    "title": timeline.title,
                    "description": timeline.description,
                    "created_at": timeline.created_at.isoformat()
                },
                "share_settings": {
                    "allow_download": share_link.allow_download,
                    "allow_comments": share_link.allow_comments,
                    "show_sensitive_data": share_link.show_sensitive_data
                },
                "access_info": {
                    "expires_at": share_link.expires_at.isoformat(),
                    "views_remaining": share_link.view_limit - share_link.view_count if share_link.view_limit else None
                }
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to access shared timeline", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to access timeline")

@router.get("/notifications")
async def get_user_notifications(
    limit: int = Query(50, ge=1, le=100, description="Number of notifications to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    unread_only: bool = Query(False, description="Return only unread notifications"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get notifications for the current user (Requirements 6.5)"""
    
    try:
        notifications = await notification_service.get_user_notifications(
            user_id=str(current_user.id),
            limit=limit,
            offset=offset,
            unread_only=unread_only
        )
        
        return {
            "notifications": notifications,
            "total": len(notifications),
            "has_more": len(notifications) == limit
        }
        
    except Exception as e:
        logger.error("Failed to get user notifications", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get notifications")

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Mark a notification as read (Requirements 6.5)"""
    
    try:
        success = await notification_service.mark_notification_read(
            notification_id=notification_id,
            user_id=str(current_user.id)
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {"message": "Notification marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to mark notification as read", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")

@router.post("/webhooks")
async def create_webhook_endpoint(
    webhook_config: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a webhook endpoint for collaboration events (Requirements 6.6)"""
    
    try:
        endpoint = await notification_service.create_webhook_endpoint(
            url=webhook_config['url'],
            event_types=webhook_config.get('event_types', []),
            secret_key=webhook_config.get('secret_key'),
            timeline_ids=webhook_config.get('timeline_ids'),
            created_by_id=str(current_user.id)
        )
        
        return {
            "id": str(endpoint.id),
            "url": endpoint.url,
            "event_types": endpoint.event_types,
            "is_active": endpoint.is_active,
            "created_at": endpoint.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to create webhook endpoint", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create webhook endpoint")

@router.get("/users/{user_id}/collaborations")
async def get_user_collaborations(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all timeline collaborations for a user"""
    
    # Users can only view their own collaborations unless they're admin
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        collaborations = await collaboration_service.get_user_collaborations(user_id)
        
        return {
            "collaborations": collaborations,
            "total": len(collaborations)
        }
        
    except Exception as e:
        logger.error("Failed to get user collaborations", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get collaborations")

@router.post("/cleanup/inactive-sessions")
async def cleanup_inactive_sessions(
    threshold_minutes: int = Query(30, description="Inactive threshold in minutes"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Clean up inactive collaboration sessions (admin only)"""
    
    # This would typically be restricted to admin users
    try:
        await presence_service.cleanup_inactive_sessions(threshold_minutes)
        return {"message": "Inactive sessions cleaned up successfully"}
        
    except Exception as e:
        logger.error("Failed to cleanup inactive sessions", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to cleanup sessions")