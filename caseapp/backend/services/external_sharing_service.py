"""
External sharing service for timeline collaboration
"""

import secrets
import hashlib
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from core.database import AsyncSessionLocal
from models.external_sharing import ExternalShareLink, ShareLinkAccessLog, ShareLinkStatus
from models.timeline import CaseTimeline
from models.user import User

logger = structlog.get_logger()

class ExternalSharingService:
    """Service for managing external timeline sharing"""
    
    async def create_share_link(
        self,
        timeline_id: str,
        created_by_id: str,
        expires_in_hours: int = 24,
        view_limit: Optional[int] = None,
        password: Optional[str] = None,
        allow_download: bool = False,
        allow_comments: bool = False,
        show_sensitive_data: bool = False
    ) -> ExternalShareLink:
        """Create a new external share link"""
        
        async with AsyncSessionLocal() as db:
            # Verify timeline exists
            timeline_result = await db.execute(
                select(CaseTimeline).where(CaseTimeline.id == timeline_id)
            )
            timeline = timeline_result.scalar_one_or_none()
            
            if not timeline:
                raise ValueError(f"Timeline {timeline_id} not found")
            
            # Generate secure token
            share_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)
            
            # Hash password if provided
            password_hash = None
            if password:
                password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Create share link
            share_link = ExternalShareLink(
                share_token=share_token,
                timeline_id=timeline_id,
                expires_at=expires_at,
                view_limit=view_limit,
                password_hash=password_hash,
                allow_download=allow_download,
                allow_comments=allow_comments,
                show_sensitive_data=show_sensitive_data,
                created_by_id=created_by_id
            )
            
            db.add(share_link)
            await db.commit()
            await db.refresh(share_link)
            
            logger.info("External share link created", 
                       share_link_id=str(share_link.id),
                       timeline_id=timeline_id,
                       expires_at=expires_at.isoformat())
            
            return share_link
    
    async def get_share_link(self, share_token: str) -> Optional[ExternalShareLink]:
        """Get share link by token"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExternalShareLink)
                .where(ExternalShareLink.share_token == share_token)
                .options(selectinload(ExternalShareLink.timeline))
            )
            return result.scalar_one_or_none()
    
    async def validate_share_link_access(
        self,
        share_token: str,
        password: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate access to a share link"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExternalShareLink)
                .where(ExternalShareLink.share_token == share_token)
                .options(selectinload(ExternalShareLink.timeline))
            )
            share_link = result.scalar_one_or_none()
            
            if not share_link:
                return {
                    'valid': False,
                    'reason': 'Share link not found',
                    'share_link': None
                }
            
            # Check if link is expired
            if share_link.expires_at < datetime.now(UTC):
                if share_link.status == ShareLinkStatus.ACTIVE.value:
                    share_link.status = ShareLinkStatus.EXPIRED.value
                    await db.commit()
                
                return {
                    'valid': False,
                    'reason': 'Share link has expired',
                    'share_link': share_link
                }
            
            # Check if link is revoked
            if share_link.status == ShareLinkStatus.REVOKED.value:
                return {
                    'valid': False,
                    'reason': 'Share link has been revoked',
                    'share_link': share_link
                }
            
            # Check view limit
            if share_link.view_limit and share_link.view_count >= share_link.view_limit:
                if share_link.status == ShareLinkStatus.ACTIVE.value:
                    share_link.status = ShareLinkStatus.VIEW_LIMIT_REACHED.value
                    await db.commit()
                
                return {
                    'valid': False,
                    'reason': 'View limit reached',
                    'share_link': share_link
                }
            
            # Check password if required
            if share_link.password_hash:
                if not password:
                    return {
                        'valid': False,
                        'reason': 'Password required',
                        'share_link': share_link,
                        'requires_password': True
                    }
                
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                if password_hash != share_link.password_hash:
                    return {
                        'valid': False,
                        'reason': 'Invalid password',
                        'share_link': share_link
                    }
            
            return {
                'valid': True,
                'share_link': share_link
            }
    
    async def log_share_link_access(
        self,
        share_link_id: str,
        action: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        success: bool = True,
        failure_reason: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ShareLinkAccessLog:
        """Log access to a share link"""
        
        async with AsyncSessionLocal() as db:
            access_log = ShareLinkAccessLog(
                share_link_id=share_link_id,
                action=action,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                failure_reason=failure_reason,
                session_id=session_id
            )
            
            db.add(access_log)
            
            # Update share link access tracking
            if success and action == 'view':
                result = await db.execute(
                    select(ExternalShareLink).where(ExternalShareLink.id == share_link_id)
                )
                share_link = result.scalar_one_or_none()
                
                if share_link:
                    share_link.view_count += 1
                    share_link.last_accessed_at = datetime.now(UTC)
                    share_link.last_accessed_ip = ip_address
            
            await db.commit()
            await db.refresh(access_log)
            
            return access_log
    
    async def revoke_share_link(
        self,
        share_token: str,
        revoked_by_id: str
    ) -> bool:
        """Revoke a share link"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExternalShareLink).where(ExternalShareLink.share_token == share_token)
            )
            share_link = result.scalar_one_or_none()
            
            if not share_link:
                return False
            
            share_link.status = ShareLinkStatus.REVOKED.value
            share_link.revoked_by_id = revoked_by_id
            share_link.revoked_at = datetime.now(UTC)
            
            await db.commit()
            
            logger.info("Share link revoked", 
                       share_link_id=str(share_link.id),
                       revoked_by=revoked_by_id)
            
            return True
    
    async def get_timeline_share_links(
        self,
        timeline_id: str,
        include_revoked: bool = False
    ) -> List[ExternalShareLink]:
        """Get all share links for a timeline"""
        
        async with AsyncSessionLocal() as db:
            query = select(ExternalShareLink).where(
                ExternalShareLink.timeline_id == timeline_id
            )
            
            if not include_revoked:
                query = query.where(
                    ExternalShareLink.status != ShareLinkStatus.REVOKED.value
                )
            
            query = query.order_by(desc(ExternalShareLink.created_at))
            
            result = await db.execute(query)
            return result.scalars().all()
    
    async def get_share_link_analytics(
        self,
        share_link_id: str
    ) -> Dict[str, Any]:
        """Get analytics for a share link"""
        
        async with AsyncSessionLocal() as db:
            # Get share link
            share_link_result = await db.execute(
                select(ExternalShareLink).where(ExternalShareLink.id == share_link_id)
            )
            share_link = share_link_result.scalar_one_or_none()
            
            if not share_link:
                return {}
            
            # Get access logs
            access_logs_result = await db.execute(
                select(ShareLinkAccessLog)
                .where(ShareLinkAccessLog.share_link_id == share_link_id)
                .order_by(desc(ShareLinkAccessLog.accessed_at))
            )
            access_logs = access_logs_result.scalars().all()
            
            # Calculate analytics
            total_accesses = len(access_logs)
            successful_accesses = len([log for log in access_logs if log.success])
            failed_accesses = total_accesses - successful_accesses
            
            unique_ips = len(set(log.ip_address for log in access_logs))
            unique_sessions = len(set(log.session_id for log in access_logs if log.session_id))
            
            # Access by action
            actions = {}
            for log in access_logs:
                actions[log.action] = actions.get(log.action, 0) + 1
            
            # Recent activity (last 24 hours)
            recent_cutoff = datetime.now(UTC) - timedelta(hours=24)
            recent_accesses = [
                log for log in access_logs 
                if log.accessed_at > recent_cutoff
            ]
            
            return {
                'share_link_id': str(share_link.id),
                'status': share_link.status,
                'created_at': share_link.created_at.isoformat(),
                'expires_at': share_link.expires_at.isoformat(),
                'view_limit': share_link.view_limit,
                'view_count': share_link.view_count,
                'last_accessed_at': share_link.last_accessed_at.isoformat() if share_link.last_accessed_at else None,
                'analytics': {
                    'total_accesses': total_accesses,
                    'successful_accesses': successful_accesses,
                    'failed_accesses': failed_accesses,
                    'unique_ips': unique_ips,
                    'unique_sessions': unique_sessions,
                    'actions': actions,
                    'recent_accesses_24h': len(recent_accesses)
                },
                'recent_activity': [
                    {
                        'action': log.action,
                        'ip_address': log.ip_address,
                        'accessed_at': log.accessed_at.isoformat(),
                        'success': log.success,
                        'failure_reason': log.failure_reason
                    }
                    for log in access_logs[:10]  # Last 10 accesses
                ]
            }
    
    async def cleanup_expired_links(self) -> int:
        """Clean up expired share links"""
        
        async with AsyncSessionLocal() as db:
            # Find expired links that are still active
            result = await db.execute(
                select(ExternalShareLink).where(
                    and_(
                        ExternalShareLink.expires_at < datetime.now(UTC),
                        ExternalShareLink.status == ShareLinkStatus.ACTIVE.value
                    )
                )
            )
            expired_links = result.scalars().all()
            
            # Mark as expired
            for link in expired_links:
                link.status = ShareLinkStatus.EXPIRED.value
            
            await db.commit()
            
            logger.info(f"Cleaned up {len(expired_links)} expired share links")
            
            return len(expired_links)
    
    async def extend_share_link(
        self,
        share_token: str,
        additional_hours: int,
        extended_by_id: str
    ) -> bool:
        """Extend the expiration of a share link"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExternalShareLink).where(ExternalShareLink.share_token == share_token)
            )
            share_link = result.scalar_one_or_none()
            
            if not share_link or share_link.status == ShareLinkStatus.REVOKED.value:
                return False
            
            # Extend expiration
            share_link.expires_at += timedelta(hours=additional_hours)
            
            # Reactivate if it was expired
            if share_link.status == ShareLinkStatus.EXPIRED.value:
                share_link.status = ShareLinkStatus.ACTIVE.value
            
            await db.commit()
            
            logger.info("Share link extended", 
                       share_link_id=str(share_link.id),
                       new_expiration=share_link.expires_at.isoformat(),
                       extended_by=extended_by_id)
            
            return True