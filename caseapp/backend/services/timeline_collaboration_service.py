"""
Timeline collaboration service for managing sharing and permissions
"""

import structlog
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, delete
from sqlalchemy.orm import selectinload
import uuid
import secrets

from core.database import AsyncSessionLocal
from models.timeline import (
    CaseTimeline, TimelineCollaboration, TimelineComment, 
    CollaborationSession
)
from models.user import User

logger = structlog.get_logger()

class TimelineCollaborationService:
    """Service for managing timeline collaboration and sharing"""
    
    async def share_timeline(
        self,
        timeline_id: str,
        user_id: str,
        permissions: Dict[str, bool],
        shared_by_id: str,
        message: Optional[str] = None
    ) -> TimelineCollaboration:
        """Share timeline with a user with granular permissions"""
        
        async with AsyncSessionLocal() as db:
            # Verify timeline exists
            timeline_result = await db.execute(
                select(CaseTimeline).where(CaseTimeline.id == timeline_id)
            )
            timeline = timeline_result.scalar_one_or_none()
            
            if not timeline:
                raise ValueError(f"Timeline {timeline_id} not found")
            
            # Verify user exists
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Check if collaboration already exists
            existing_result = await db.execute(
                select(TimelineCollaboration).where(
                    and_(
                        TimelineCollaboration.timeline_id == timeline_id,
                        TimelineCollaboration.user_id == user_id
                    )
                )
            )
            existing_collaboration = existing_result.scalar_one_or_none()
            
            if existing_collaboration:
                # Update existing collaboration
                existing_collaboration.can_view = permissions.get('can_view', True)
                existing_collaboration.can_edit = permissions.get('can_edit', False)
                existing_collaboration.can_add_events = permissions.get('can_add_events', False)
                existing_collaboration.can_pin_evidence = permissions.get('can_pin_evidence', False)
                existing_collaboration.can_share = permissions.get('can_share', False)
                existing_collaboration.can_comment = permissions.get('can_comment', True)
                existing_collaboration.shared_message = message
                existing_collaboration.updated_by_id = shared_by_id
                
                await db.commit()
                await db.refresh(existing_collaboration)
                return existing_collaboration
            
            # Create new collaboration
            collaboration = TimelineCollaboration(
                timeline_id=timeline_id,
                user_id=user_id,
                can_view=permissions.get('can_view', True),
                can_edit=permissions.get('can_edit', False),
                can_add_events=permissions.get('can_add_events', False),
                can_pin_evidence=permissions.get('can_pin_evidence', False),
                can_share=permissions.get('can_share', False),
                can_comment=permissions.get('can_comment', True),
                shared_message=message,
                created_by_id=shared_by_id
            )
            
            db.add(collaboration)
            await db.commit()
            await db.refresh(collaboration)
            
            logger.info("Timeline shared successfully", 
                       timeline_id=timeline_id, user_id=user_id, shared_by=shared_by_id)
            
            return collaboration
    
    async def get_timeline_collaborators(self, timeline_id: str) -> List[Dict[str, Any]]:
        """Get all collaborators for a timeline"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TimelineCollaboration, User)
                .join(User, TimelineCollaboration.user_id == User.id)
                .where(TimelineCollaboration.timeline_id == timeline_id)
                .options(selectinload(TimelineCollaboration.user))
            )
            
            collaborators = []
            for collaboration, user in result:
                collaborator_data = {
                    'collaboration_id': str(collaboration.id),
                    'user_id': str(user.id),
                    'user_name': user.full_name,
                    'user_email': user.email,
                    'permissions': {
                        'can_view': collaboration.can_view,
                        'can_edit': collaboration.can_edit,
                        'can_add_events': collaboration.can_add_events,
                        'can_pin_evidence': collaboration.can_pin_evidence,
                        'can_share': collaboration.can_share,
                        'can_comment': collaboration.can_comment
                    },
                    'shared_at': collaboration.created_at,
                    'updated_at': collaboration.updated_at,
                    'receive_notifications': collaboration.receive_notifications,
                    'access_level': collaboration.access_level
                }
                collaborators.append(collaborator_data)
            
            return collaborators
    
    async def update_collaboration_permissions(
        self,
        timeline_id: str,
        user_id: str,
        permissions: Dict[str, bool],
        updated_by_id: str
    ) -> TimelineCollaboration:
        """Update collaboration permissions for a user"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TimelineCollaboration).where(
                    and_(
                        TimelineCollaboration.timeline_id == timeline_id,
                        TimelineCollaboration.user_id == user_id
                    )
                )
            )
            collaboration = result.scalar_one_or_none()
            
            if not collaboration:
                raise ValueError("Collaboration not found")
            
            # Update permissions atomically
            collaboration.can_view = permissions.get('can_view', collaboration.can_view)
            collaboration.can_edit = permissions.get('can_edit', collaboration.can_edit)
            collaboration.can_add_events = permissions.get('can_add_events', collaboration.can_add_events)
            collaboration.can_pin_evidence = permissions.get('can_pin_evidence', collaboration.can_pin_evidence)
            collaboration.can_share = permissions.get('can_share', collaboration.can_share)
            collaboration.can_comment = permissions.get('can_comment', collaboration.can_comment)
            collaboration.updated_by_id = updated_by_id
            
            await db.commit()
            await db.refresh(collaboration)
            
            logger.info("Collaboration permissions updated", 
                       timeline_id=timeline_id, user_id=user_id, updated_by=updated_by_id)
            
            return collaboration
    
    async def remove_collaboration(self, timeline_id: str, user_id: str) -> bool:
        """Remove collaboration access for a user"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(TimelineCollaboration).where(
                    and_(
                        TimelineCollaboration.timeline_id == timeline_id,
                        TimelineCollaboration.user_id == user_id
                    )
                )
            )
            
            if result.rowcount > 0:
                await db.commit()
                logger.info("Collaboration removed", timeline_id=timeline_id, user_id=user_id)
                return True
            
            return False
    
    async def add_timeline_comment(
        self,
        timeline_id: str,
        event_id: str,
        user_id: str,
        comment_text: str,
        parent_comment_id: Optional[str] = None,
        is_internal: bool = True
    ) -> TimelineComment:
        """Add a comment to a timeline event"""
        
        async with AsyncSessionLocal() as db:
            # Calculate thread depth
            thread_depth = 0
            if parent_comment_id:
                parent_result = await db.execute(
                    select(TimelineComment).where(TimelineComment.id == parent_comment_id)
                )
                parent_comment = parent_result.scalar_one_or_none()
                
                if not parent_comment:
                    raise ValueError("Parent comment not found")
                
                thread_depth = parent_comment.thread_depth + 1
            
            # Create comment
            comment = TimelineComment(
                timeline_event_id=event_id,
                comment_text=comment_text,
                is_internal=is_internal,
                parent_comment_id=parent_comment_id,
                thread_depth=thread_depth,
                created_by=user_id
            )
            
            db.add(comment)
            await db.commit()
            await db.refresh(comment)
            
            logger.info("Timeline comment added", 
                       event_id=event_id, user_id=user_id, thread_depth=thread_depth)
            
            return comment
    
    async def get_timeline_comments(
        self,
        event_id: str,
        include_internal: bool = True
    ) -> List[Dict[str, Any]]:
        """Get comments for a timeline event"""
        
        async with AsyncSessionLocal() as db:
            query = select(TimelineComment, User).join(
                User, TimelineComment.created_by == User.id
            ).where(TimelineComment.timeline_event_id == event_id)
            
            if not include_internal:
                query = query.where(TimelineComment.is_internal == False)
            
            query = query.order_by(TimelineComment.created_at)
            
            result = await db.execute(query)
            
            comments = []
            for comment, user in result:
                comment_data = {
                    'id': str(comment.id),
                    'timeline_event_id': str(comment.timeline_event_id),
                    'comment_text': comment.comment_text,
                    'is_internal': comment.is_internal,
                    'parent_comment_id': str(comment.parent_comment_id) if comment.parent_comment_id else None,
                    'thread_depth': comment.thread_depth,
                    'created_at': comment.created_at,
                    'updated_at': comment.updated_at,
                    'created_by_id': str(comment.created_by),
                    'user_name': user.full_name,
                    'is_resolved': comment.is_resolved
                }
                comments.append(comment_data)
            
            return comments
    
    async def get_user_collaborations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all timeline collaborations for a user"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TimelineCollaboration, CaseTimeline)
                .join(CaseTimeline, TimelineCollaboration.timeline_id == CaseTimeline.id)
                .where(TimelineCollaboration.user_id == user_id)
                .options(selectinload(CaseTimeline.case))
            )
            
            collaborations = []
            for collaboration, timeline in result:
                collaboration_data = {
                    'collaboration_id': str(collaboration.id),
                    'timeline_id': str(timeline.id),
                    'timeline_title': timeline.title,
                    'case_id': str(timeline.case_id),
                    'case_title': timeline.case.title if timeline.case else None,
                    'permissions': {
                        'can_view': collaboration.can_view,
                        'can_edit': collaboration.can_edit,
                        'can_add_events': collaboration.can_add_events,
                        'can_pin_evidence': collaboration.can_pin_evidence,
                        'can_share': collaboration.can_share,
                        'can_comment': collaboration.can_comment
                    },
                    'shared_at': collaboration.created_at,
                    'access_level': collaboration.access_level
                }
                collaborations.append(collaboration_data)
            
            return collaborations
    
    async def create_external_share_link(
        self,
        timeline_id: str,
        created_by_id: str,
        expires_in_hours: int = 24,
        view_limit: Optional[int] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create external sharing link with expiration"""
        
        # Generate secure token
        share_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)
        
        # In a full implementation, this would be stored in a separate table
        # For now, return the share link data
        share_data = {
            'share_token': share_token,
            'timeline_id': timeline_id,
            'created_by_id': created_by_id,
            'expires_at': expires_at,
            'view_limit': view_limit,
            'password_protected': password is not None,
            'created_at': datetime.now(UTC)
        }
        
        logger.info("External share link created", 
                   timeline_id=timeline_id, expires_at=expires_at)
        
        return share_data