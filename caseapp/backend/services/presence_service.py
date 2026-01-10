"""
Real-time presence service for collaboration sessions
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, delete
from sqlalchemy.orm import selectinload
import redis.asyncio as redis
import uuid

from core.database import AsyncSessionLocal
from models.timeline import CollaborationSession, CaseTimeline
from models.user import User

logger = structlog.get_logger()

class PresenceService:
    """Service for managing real-time user presence in collaboration sessions"""
    
    def __init__(self):
        # Redis connection for real-time data
        self.redis_client = None
        self._initialize_redis()
        
        # In-memory tracking for active sessions
        self.active_sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> session_data
        self.timeline_sessions: Dict[str, Set[str]] = {}  # timeline_id -> set of session_ids
        
    def _initialize_redis(self):
        """Initialize Redis connection for real-time features"""
        try:
            # Use Redis for real-time presence if available
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True,
                socket_connect_timeout=5
            )
        except Exception as e:
            logger.warning("Redis not available, using in-memory presence tracking", error=str(e))
            self.redis_client = None
    
    async def start_collaboration_session(
        self,
        timeline_id: str,
        user_id: str,
        session_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start a new collaboration session for a user on a timeline"""
        
        session_id = str(uuid.uuid4())
        
        async with AsyncSessionLocal() as db:
            # Verify timeline exists and user has access
            timeline_result = await db.execute(
                select(CaseTimeline).where(CaseTimeline.id == timeline_id)
            )
            timeline = timeline_result.scalar_one_or_none()
            
            if not timeline:
                raise ValueError(f"Timeline {timeline_id} not found")
            
            # Create collaboration session record
            session = CollaborationSession(
                session_id=session_id,
                timeline_id=timeline_id,
                user_id=user_id,
                is_active=True,
                last_activity=datetime.utcnow(),
                current_view=session_metadata or {},
                ip_address=session_metadata.get('ip_address') if session_metadata else None,
                user_agent=session_metadata.get('user_agent') if session_metadata else None
            )
            
            db.add(session)
            await db.commit()
            await db.refresh(session)
            
            # Track in memory and Redis
            session_data = {
                'session_id': session_id,
                'timeline_id': timeline_id,
                'user_id': user_id,
                'started_at': datetime.utcnow().isoformat(),
                'last_activity': datetime.utcnow().isoformat(),
                'current_view': session_metadata or {},
                'is_active': True
            }
            
            self.active_sessions[session_id] = session_data
            
            if timeline_id not in self.timeline_sessions:
                self.timeline_sessions[timeline_id] = set()
            self.timeline_sessions[timeline_id].add(session_id)
            
            # Store in Redis if available
            if self.redis_client:
                try:
                    await self.redis_client.hset(
                        f"session:{session_id}",
                        mapping=session_data
                    )
                    await self.redis_client.sadd(f"timeline:{timeline_id}:sessions", session_id)
                    await self.redis_client.expire(f"session:{session_id}", 3600)  # 1 hour TTL
                except Exception as e:
                    logger.warning("Failed to store session in Redis", error=str(e))
            
            logger.info("Collaboration session started", 
                       session_id=session_id, timeline_id=timeline_id, user_id=user_id)
            
            return session_id
    
    async def update_session_activity(
        self,
        session_id: str,
        activity_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update session activity and presence data"""
        
        if session_id not in self.active_sessions:
            return False
        
        current_time = datetime.utcnow()
        
        # Update in-memory data
        session_data = self.active_sessions[session_id]
        session_data['last_activity'] = current_time.isoformat()
        
        if activity_data:
            session_data.update(activity_data)
        
        # Update database
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CollaborationSession).where(CollaborationSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if session:
                session.last_activity = current_time
                if activity_data:
                    if 'current_view' in activity_data:
                        session.current_view = activity_data['current_view']
                    if 'cursor_position' in activity_data:
                        session.cursor_position = activity_data['cursor_position']
                    if 'selected_events' in activity_data:
                        session.selected_events = activity_data['selected_events']
                    if 'editing_event_id' in activity_data:
                        session.editing_event_id = activity_data['editing_event_id']
                
                await db.commit()
        
        # Update Redis if available
        if self.redis_client:
            try:
                mapping_data = {'last_activity': current_time.isoformat()}
                if activity_data:
                    mapping_data.update(activity_data)
                
                await self.redis_client.hset(
                    f"session:{session_id}",
                    mapping=mapping_data
                )
            except Exception as e:
                logger.warning("Failed to update session in Redis", error=str(e))
        
        return True
    
    async def end_collaboration_session(self, session_id: str) -> bool:
        """End a collaboration session"""
        
        if session_id not in self.active_sessions:
            return False
        
        session_data = self.active_sessions[session_id]
        timeline_id = session_data['timeline_id']
        
        # Remove from in-memory tracking
        del self.active_sessions[session_id]
        
        if timeline_id in self.timeline_sessions:
            self.timeline_sessions[timeline_id].discard(session_id)
            if not self.timeline_sessions[timeline_id]:
                del self.timeline_sessions[timeline_id]
        
        # Update database
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CollaborationSession).where(CollaborationSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if session:
                session.is_active = False
                session.last_activity = datetime.utcnow()
                await db.commit()
        
        # Remove from Redis if available
        if self.redis_client:
            try:
                await self.redis_client.delete(f"session:{session_id}")
                await self.redis_client.srem(f"timeline:{timeline_id}:sessions", session_id)
            except Exception as e:
                logger.warning("Failed to remove session from Redis", error=str(e))
        
        logger.info("Collaboration session ended", session_id=session_id, timeline_id=timeline_id)
        return True
    
    async def get_timeline_presence(self, timeline_id: str) -> List[Dict[str, Any]]:
        """Get current presence information for a timeline"""
        
        presence_data = []
        
        # Get active sessions for this timeline
        session_ids = self.timeline_sessions.get(timeline_id, set())
        
        if not session_ids:
            return presence_data
        
        async with AsyncSessionLocal() as db:
            # Get session data with user information
            result = await db.execute(
                select(CollaborationSession, User)
                .join(User, CollaborationSession.user_id == User.id)
                .where(
                    and_(
                        CollaborationSession.timeline_id == timeline_id,
                        CollaborationSession.is_active == True,
                        CollaborationSession.last_activity > datetime.utcnow() - timedelta(minutes=5)
                    )
                )
                .options(selectinload(CollaborationSession.user))
            )
            
            for session, user in result:
                presence_info = {
                    'session_id': session.session_id,
                    'user_id': str(user.id),
                    'user_name': user.full_name,
                    'user_email': user.email,
                    'last_activity': session.last_activity.isoformat(),
                    'current_view': session.current_view,
                    'cursor_position': session.cursor_position,
                    'selected_events': session.selected_events,
                    'editing_event_id': str(session.editing_event_id) if session.editing_event_id else None,
                    'is_active': session.is_active
                }
                presence_data.append(presence_info)
        
        return presence_data
    
    async def cleanup_inactive_sessions(self, inactive_threshold_minutes: int = 30):
        """Clean up inactive collaboration sessions"""
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=inactive_threshold_minutes)
        
        async with AsyncSessionLocal() as db:
            # Find inactive sessions
            result = await db.execute(
                select(CollaborationSession).where(
                    and_(
                        CollaborationSession.is_active == True,
                        CollaborationSession.last_activity < cutoff_time
                    )
                )
            )
            
            inactive_sessions = result.scalars().all()
            
            for session in inactive_sessions:
                # End the session
                await self.end_collaboration_session(session.session_id)
            
            logger.info(f"Cleaned up {len(inactive_sessions)} inactive collaboration sessions")
    
    async def get_user_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active collaboration sessions for a user"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CollaborationSession, CaseTimeline)
                .join(CaseTimeline, CollaborationSession.timeline_id == CaseTimeline.id)
                .where(
                    and_(
                        CollaborationSession.user_id == user_id,
                        CollaborationSession.is_active == True,
                        CollaborationSession.last_activity > datetime.utcnow() - timedelta(hours=1)
                    )
                )
                .options(selectinload(CaseTimeline.case))
            )
            
            sessions = []
            for session, timeline in result:
                session_info = {
                    'session_id': session.session_id,
                    'timeline_id': str(timeline.id),
                    'timeline_title': timeline.title,
                    'case_id': str(timeline.case_id),
                    'case_title': timeline.case.title if timeline.case else None,
                    'started_at': session.created_at.isoformat(),
                    'last_activity': session.last_activity.isoformat(),
                    'current_view': session.current_view
                }
                sessions.append(session_info)
            
            return sessions
    
    async def broadcast_presence_update(
        self,
        timeline_id: str,
        update_data: Dict[str, Any],
        exclude_session_id: Optional[str] = None
    ):
        """Broadcast presence update to all active sessions on a timeline"""
        
        # Get all active sessions for this timeline
        session_ids = self.timeline_sessions.get(timeline_id, set())
        
        if exclude_session_id:
            session_ids = session_ids - {exclude_session_id}
        
        # In a real implementation, this would use WebSocket connections
        # For now, we'll store the update in Redis for polling clients
        if self.redis_client and session_ids:
            try:
                update_message = {
                    'type': 'presence_update',
                    'timeline_id': timeline_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'data': update_data
                }
                
                # Store update for each active session
                for session_id in session_ids:
                    await self.redis_client.lpush(
                        f"session:{session_id}:updates",
                        json.dumps(update_message)
                    )
                    # Keep only last 50 updates
                    await self.redis_client.ltrim(f"session:{session_id}:updates", 0, 49)
                    await self.redis_client.expire(f"session:{session_id}:updates", 3600)
                
            except Exception as e:
                logger.warning("Failed to broadcast presence update", error=str(e))
    
    async def get_session_updates(self, session_id: str) -> List[Dict[str, Any]]:
        """Get pending updates for a collaboration session"""
        
        updates = []
        
        if self.redis_client:
            try:
                # Get all pending updates
                raw_updates = await self.redis_client.lrange(f"session:{session_id}:updates", 0, -1)
                
                for raw_update in raw_updates:
                    try:
                        update = json.loads(raw_update)
                        updates.append(update)
                    except json.JSONDecodeError:
                        continue
                
                # Clear the updates after retrieving
                await self.redis_client.delete(f"session:{session_id}:updates")
                
            except Exception as e:
                logger.warning("Failed to get session updates", error=str(e))
        
        return updates