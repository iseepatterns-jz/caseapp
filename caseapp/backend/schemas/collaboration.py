"""
Collaboration schemas for API requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

class CollaborationPermissions(BaseModel):
    """Granular permissions for timeline collaboration"""
    can_view: bool = True
    can_edit: bool = False
    can_add_events: bool = False
    can_pin_evidence: bool = False
    can_share: bool = False
    can_comment: bool = True

class CollaborationShareRequest(BaseModel):
    """Request to share timeline with a user"""
    user_id: str = Field(..., description="ID of user to share with")
    permissions: CollaborationPermissions
    message: Optional[str] = Field(None, description="Optional message to include with share")
    expires_in_hours: Optional[int] = Field(None, description="Optional expiration in hours")

class CollaborationResponse(BaseModel):
    """Response for collaboration information"""
    id: Optional[str] = None
    timeline_id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    permissions: CollaborationPermissions
    shared_at: datetime
    updated_at: Optional[datetime] = None
    shared_by_id: Optional[str] = None
    message: Optional[str] = None
    receive_notifications: Optional[bool] = True
    access_expires_at: Optional[datetime] = None

class SessionStartRequest(BaseModel):
    """Request to start a collaboration session"""
    initial_view: Optional[Dict[str, Any]] = Field(None, description="Initial view state")

class SessionUpdateRequest(BaseModel):
    """Request to update session activity"""
    current_view: Optional[Dict[str, Any]] = Field(None, description="Current view state")
    cursor_position: Optional[Dict[str, Any]] = Field(None, description="Current cursor position")
    selected_events: Optional[List[str]] = Field(None, description="Currently selected event IDs")
    editing_event_id: Optional[str] = Field(None, description="Event currently being edited")

class PresenceResponse(BaseModel):
    """Response for user presence information"""
    session_id: str
    user_id: str
    user_name: str
    user_email: str
    last_activity: str
    current_view: Optional[Dict[str, Any]] = None
    cursor_position: Optional[Dict[str, Any]] = None
    editing_event_id: Optional[str] = None
    is_active: bool

class CommentCreateRequest(BaseModel):
    """Request to create a timeline comment"""
    comment_text: str = Field(..., min_length=1, max_length=2000)
    parent_comment_id: Optional[str] = Field(None, description="ID of parent comment for threading")
    is_internal: bool = Field(True, description="Whether comment is internal to team")

class CommentResponse(BaseModel):
    """Response for timeline comment"""
    id: str
    timeline_event_id: str
    comment_text: str
    is_internal: bool
    parent_comment_id: Optional[str] = None
    thread_depth: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_id: str
    user_name: str
    is_resolved: bool = False
    resolved_by_id: Optional[str] = None
    resolved_at: Optional[datetime] = None

class ExternalShareRequest(BaseModel):
    """Request to create external share link"""
    expires_in_hours: int = Field(24, ge=1, le=168, description="Expiration in hours (1-168)")
    view_limit: Optional[int] = Field(None, ge=1, description="Maximum number of views")
    password: Optional[str] = Field(None, min_length=4, description="Optional password protection")
    allow_download: bool = Field(False, description="Allow downloading timeline data")

class ExternalShareResponse(BaseModel):
    """Response for external share link"""
    share_token: str
    share_url: str
    expires_at: datetime
    view_limit: Optional[int] = None
    views_remaining: Optional[int] = None
    is_password_protected: bool = False

class NotificationPreferences(BaseModel):
    """User notification preferences for collaboration"""
    receive_notifications: bool = True
    email_notifications: bool = True
    in_app_notifications: bool = True
    notification_frequency: str = Field("immediate", pattern="^(immediate|hourly|daily)$")

class CollaborationAuditEntry(BaseModel):
    """Audit entry for collaboration activities"""
    id: str
    timeline_id: str
    user_id: str
    action: str  # shared, permissions_updated, comment_added, etc.
    details: Dict[str, Any]
    timestamp: datetime
    ip_address: Optional[str] = None

class CollaborationStats(BaseModel):
    """Statistics for timeline collaboration"""
    total_collaborators: int
    active_sessions: int
    total_comments: int
    recent_activity_count: int
    most_active_collaborator: Optional[str] = None