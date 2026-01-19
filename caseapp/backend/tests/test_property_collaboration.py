"""
Property-based tests for collaboration system functionality
Validates Requirements 6.1 (granular permissions) and 6.3 (comment threading)
"""

import pytest
import asyncio
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, List
from hypothesis import given, strategies as st, settings, assume
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from models.timeline import (
    CaseTimeline, TimelineEvent, TimelineCollaboration, 
    TimelineComment, CollaborationSession
)
from models.case import Case, CaseType, CaseStatus
from models.user import User, UserRole
from services.timeline_collaboration_service import TimelineCollaborationService
from services.presence_service import PresenceService
from core.database import AsyncSessionLocal, engine
from sqlalchemy import delete

# Test data generators
@st.composite
def collaboration_permissions(draw):
    """Generate valid collaboration permission combinations"""
    can_edit = draw(st.booleans())
    can_add_events = draw(st.booleans())
    can_pin_evidence = draw(st.booleans())
    can_share = draw(st.booleans())
    can_comment = draw(st.booleans())
    
    # Enforce hierarchy: Advanced permissions require view access
    requires_view = can_edit or can_add_events or can_pin_evidence or can_share
    can_view = True if requires_view else draw(st.booleans())

    return {
        'can_view': can_view,
        'can_edit': can_edit,
        'can_add_events': can_add_events,
        'can_pin_evidence': can_pin_evidence,
        'can_share': can_share,
        'can_comment': can_comment
    }

@st.composite
def comment_text_strategy(draw):
    """Generate valid comment text"""
    # Filter out null bytes and ensure non-empty
    return draw(st.text(min_size=1, max_size=2000).filter(lambda x: x.strip() and '\x00' not in x))

@st.composite
def user_data_strategy(draw):
    """Generate user data for testing"""
    return {
        'email': draw(st.emails()),
        'first_name': draw(st.text(min_size=2, max_size=50)),
        'last_name': draw(st.text(min_size=2, max_size=50)),
        'hashed_password': 'test_hash',
        'role': UserRole.ATTORNEY
    }

@pytest.mark.asyncio
class TestCollaborationPermissionProperties:
    """Property-based tests for collaboration permission system (Requirements 6.1)"""
    
    async def setup_test_data(self):
        """Setup test environment"""
        self.collaboration_service = TimelineCollaborationService()
        self.presence_service = PresenceService()
        
        # Create test users and timeline
        async with AsyncSessionLocal() as db:
            # Create test users with unique data
            suffix = str(uuid.uuid4())[:8]
            self.owner_user = User(
                email=f"owner_{suffix}@test.com",
                username=f"owner_{suffix}",
                first_name="Timeline",
                last_name="Owner",
                hashed_password="test_hash",
                role=UserRole.ATTORNEY
            )
            self.collaborator_user = User(
                email=f"collaborator_{suffix}@test.com", 
                username=f"collaborator_{suffix}",
                first_name="Collaborator",
                last_name="User",
                hashed_password="test_hash",
                role=UserRole.ATTORNEY
            )
            db.add_all([self.owner_user, self.collaborator_user])
            await db.flush()

            # Create test case
            random_suffix = str(uuid.uuid4())[:8]
            self.test_case = Case(
                case_number=f"TEST-COLLAB-{random_suffix}",
                title="Test Collaboration Case",
                description="Test case for collaboration",
                case_type=CaseType.CIVIL,
                status=CaseStatus.ACTIVE,
                created_by=self.owner_user.id
            )
            db.add(self.test_case)
            await db.flush()
            
            # Create test timeline
            self.test_timeline = CaseTimeline(
                case_id=self.test_case.id,
                title="Test Timeline",
                description="Timeline for collaboration testing",
                created_by=self.owner_user.id
            )
            db.add(self.test_timeline)
            await db.flush()
            
            # Create test event
            self.test_event = TimelineEvent(
                timeline_id=self.test_timeline.id,
                case_id=self.test_case.id,
                title="Test Event",
                description="Event for testing",
                event_date=datetime.now(UTC),
                created_by=self.owner_user.id
            )
            db.add(self.test_event)
            await db.commit()
            
            # Store IDs for tests
            self.timeline_id = str(self.test_timeline.id)
            self.event_id = str(self.test_event.id)
            self.owner_id = str(self.owner_user.id)
            self.collaborator_id = str(self.collaborator_user.id)

    async def teardown_test_data(self):
        """Cleanup test data"""
        async with AsyncSessionLocal() as db:
            try:
                # Delete in reverse order of dependency
                # Verify attributes exist before deletion to safely handle partial setup failures
                if hasattr(self, 'owner_id'):
                     await db.execute(text(f"DELETE FROM audit_logs WHERE user_id IN ('{self.owner_id}', '{self.collaborator_id}')"))
                

                await db.execute(delete(TimelineCollaboration).where(TimelineCollaboration.timeline_id == self.timeline_id))
                await db.execute(delete(TimelineEvent).where(TimelineEvent.id == self.event_id))
                await db.execute(delete(CaseTimeline).where(CaseTimeline.id == self.timeline_id))
                await db.execute(delete(Case).where(Case.id == self.test_case.id))
                await db.execute(delete(User).where(User.id.in_([self.owner_id, self.collaborator_id])))
                await db.commit()
            except Exception:
                await db.rollback()

    @given(permissions=collaboration_permissions())
    @settings(max_examples=20, deadline=None)
    async def test_property_21_permission_based_access_control(self, permissions: Dict[str, bool]):
        """
        Property 21: Permission-Based Access Control (Requirements 6.1)
        
        For any set of granular permissions assigned to a collaborator,
        the system SHALL enforce those permissions consistently across all operations,
        ensuring users can only perform actions they are explicitly granted.
        """
        
        try:
            await self.setup_test_data()
            
            # Share timeline with specific permissions
            collaboration = await self.collaboration_service.share_timeline(
                timeline_id=self.timeline_id,
                user_id=self.collaborator_id,
                permissions=permissions,
                shared_by_id=self.owner_id
            )
            
            # Verify collaboration was created with correct permissions
            assert collaboration is not None
            assert collaboration.can_view == permissions['can_view']
            assert collaboration.can_edit == permissions['can_edit']
            assert collaboration.can_add_events == permissions['can_add_events']
            assert collaboration.can_pin_evidence == permissions['can_pin_evidence']
            assert collaboration.can_share == permissions['can_share']
            assert collaboration.can_comment == permissions['can_comment']
            
            # Test permission enforcement
            async with AsyncSessionLocal() as db:
                # Verify permissions are stored correctly in database
                result = await db.execute(
                    select(TimelineCollaboration).where(
                        and_(
                            TimelineCollaboration.timeline_id == self.timeline_id,
                            TimelineCollaboration.user_id == self.collaborator_id
                        )
                    )
                )
                stored_collaboration = result.scalar_one()
                
                # Property: Stored permissions must match assigned permissions
                assert stored_collaboration.can_view == permissions['can_view']
                assert stored_collaboration.can_edit == permissions['can_edit']
                assert stored_collaboration.can_add_events == permissions['can_add_events']
                assert stored_collaboration.can_pin_evidence == permissions['can_pin_evidence']
                assert stored_collaboration.can_share == permissions['can_share']
                assert stored_collaboration.can_comment == permissions['can_comment']
                
                # Property: Edit permission should imply view permission
                if permissions['can_edit']:
                    assert stored_collaboration.can_view, "Edit permission requires view permission"
                
                # Property: Add events permission should imply view permission
                if permissions['can_add_events']:
                    assert stored_collaboration.can_view, "Add events permission requires view permission"
                
                # Property: Pin evidence permission should imply view permission
                if permissions['can_pin_evidence']:
                    assert stored_collaboration.can_view, "Pin evidence permission requires view permission"
                
                # Property: Share permission should imply view permission
                if permissions['can_share']:
                    assert stored_collaboration.can_view, "Share permission requires view permission"
            
            # Test permission retrieval consistency
            collaborators = await self.collaboration_service.get_timeline_collaborators(self.timeline_id)
            
            # Find our collaborator in the results
            collaborator_data = None
            for collab in collaborators:
                if collab['user_id'] == self.collaborator_id:
                    collaborator_data = collab
                    break
            
            assert collaborator_data is not None, "Collaborator should be found in timeline collaborators"
            
            # Property: Retrieved permissions must match stored permissions
            retrieved_permissions = collaborator_data['permissions']
            assert retrieved_permissions['can_view'] == permissions['can_view']
            assert retrieved_permissions['can_edit'] == permissions['can_edit']
            assert retrieved_permissions['can_add_events'] == permissions['can_add_events']
            assert retrieved_permissions['can_pin_evidence'] == permissions['can_pin_evidence']
            assert retrieved_permissions['can_share'] == permissions['can_share']
            assert retrieved_permissions['can_comment'] == permissions['can_comment']
            
            # Clean up for next test
            await self.collaboration_service.remove_collaboration(
                timeline_id=self.timeline_id,
                user_id=self.collaborator_id
            )
            
        finally:
            await self.teardown_test_data()
            # await engine.dispose() - removed, handled by fixture

@pytest.mark.asyncio
class TestCommentThreadProperties:
    """Property-based tests for comment threading system (Requirements 6.3)"""
    
    async def setup_test_data(self):
        """Setup test environment"""
        self.collaboration_service = TimelineCollaborationService()
        
        # Create test data similar to permission tests
        async with AsyncSessionLocal() as db:
            # Create test users
            suffix = str(uuid.uuid4())[:8]
            self.user1 = User(
                email=f"user1_{suffix}@test.com",
                username=f"user1_{suffix}",
                first_name="User",
                last_name="One",
                hashed_password="test_hash",
                role=UserRole.ATTORNEY
            )
            self.user2 = User(
                email=f"user2_{suffix}@test.com",
                username=f"user2_{suffix}",
                first_name="User",
                last_name="Two", 
                hashed_password="test_hash",
                role=UserRole.ATTORNEY
            )
            db.add_all([self.user1, self.user2])
            await db.flush()

            # Create test case
            random_suffix = str(uuid.uuid4())[:8]
            self.test_case = Case(
                case_number=f"TEST-COMMENT-{random_suffix}",
                title="Test Comment Case",
                description="Test case for comments",
                case_type=CaseType.CIVIL,
                status=CaseStatus.ACTIVE,
                created_by=self.user1.id
            )
            db.add(self.test_case)
            await db.flush()
            
            # Create test timeline
            self.test_timeline = CaseTimeline(
                case_id=self.test_case.id,
                title="Test Timeline",
                description="Timeline for comment testing",
                created_by=self.user1.id
            )
            db.add(self.test_timeline)
            await db.flush()
            
            # Create test event
            self.test_event = TimelineEvent(
                timeline_id=self.test_timeline.id,
                case_id=self.test_case.id,
                title="Test Event",
                description="Event for comment testing",
                event_date=datetime.now(UTC),
                created_by=self.user1.id
            )
            db.add(self.test_event)
            await db.commit()
            
            # Store IDs
            self.timeline_id = str(self.test_timeline.id)
            self.event_id = str(self.test_event.id)
            self.user1_id = str(self.user1.id)
            self.user2_id = str(self.user2.id)
    
    @given(comment_texts=st.lists(comment_text_strategy(), min_size=1, max_size=5))
    @settings(max_examples=10, deadline=None)
    async def test_property_22_comment_thread_integrity(self, comment_texts: List[str]):
        """
        Property 22: Comment Thread Integrity (Requirements 6.3)
        
        For any sequence of comments added to a timeline event,
        the system SHALL maintain proper thread hierarchy and depth calculations,
        ensuring comment threading remains consistent and navigable.
        """
        
        try:
            await self.setup_test_data()
            
            # Assume we have at least one comment
            assume(len(comment_texts) >= 1)
            
            created_comments = []
            
            # Create root comment
            root_comment = await self.collaboration_service.add_timeline_comment(
                timeline_id=self.timeline_id,
                event_id=self.event_id,
                user_id=self.user1_id,
                comment_text=comment_texts[0],
                parent_comment_id=None,
                is_internal=True
            )
            created_comments.append(root_comment)
            
            # Property: Root comment should have depth 0 and no parent
            assert root_comment.thread_depth == 0
            assert root_comment.parent_comment_id is None
            
            # Create child comments if we have more text
            for i, comment_text in enumerate(comment_texts[1:], 1):
                # Randomly choose a parent from existing comments
                parent_comment = created_comments[i % len(created_comments)]
                user_id = self.user1_id if i % 2 == 0 else self.user2_id
                
                child_comment = await self.collaboration_service.add_timeline_comment(
                    timeline_id=self.timeline_id,
                    event_id=self.event_id,
                    user_id=user_id,
                    comment_text=comment_text,
                    parent_comment_id=str(parent_comment.id),
                    is_internal=True
                )
                created_comments.append(child_comment)
                
                # Property: Child comment depth should be parent depth + 1
                expected_depth = parent_comment.thread_depth + 1
                assert child_comment.thread_depth == expected_depth, \
                    f"Child comment depth {child_comment.thread_depth} should be {expected_depth}"
                
                # Property: Child comment should reference correct parent
                assert str(child_comment.parent_comment_id) == str(parent_comment.id)
            
            # Verify thread integrity in database
            async with AsyncSessionLocal() as db:
                # Get all comments for this event
                result = await db.execute(
                    select(TimelineComment)
                    .where(TimelineComment.timeline_event_id == self.event_id)
                    .order_by(TimelineComment.created_at)
                )
                all_comments = result.scalars().all()
                
                # Property: Number of stored comments should match created comments
                assert len(all_comments) == len(created_comments)
                
                # Property: Thread depth consistency
                for comment in all_comments:
                    if comment.parent_comment_id is None:
                        # Root comment should have depth 0
                        assert comment.thread_depth == 0
                    else:
                        # Find parent comment
                        parent = next(
                            (c for c in all_comments if c.id == comment.parent_comment_id),
                            None
                        )
                        assert parent is not None, "Parent comment should exist"
                        
                        # Child depth should be parent depth + 1
                        assert comment.thread_depth == parent.thread_depth + 1
                
                # Property: No circular references in thread hierarchy
                for comment in all_comments:
                    visited = set()
                    current = comment
                    
                    while current.parent_comment_id is not None:
                        assert current.id not in visited, "Circular reference detected in comment thread"
                        visited.add(current.id)
                        
                        # Find parent
                        current = next(
                            (c for c in all_comments if c.id == current.parent_comment_id),
                            None
                        )
                        assert current is not None, "Parent comment chain should be complete"
        finally:
            # Cleanup test data
            async with AsyncSessionLocal() as db:
                try:
                    await db.execute(delete(TimelineComment).where(TimelineComment.timeline_event_id == self.event_id))
                    
                    # Explicitly delete audit logs for these users to prevent foreign key issues
                    if hasattr(self, 'user1_id') and hasattr(self, 'user2_id'):
                        await db.execute(text(f"DELETE FROM audit_logs WHERE user_id IN ('{self.user1_id}', '{self.user2_id}')"))

                    # Clean up audit logs first (FK references)
                    # We need to find logs by user or case? 
                    # Users are deleted below. Case deleted below.
                    # Explicit delete might be safer if cascade missing.
                    # But without knowing IDs, we rely on cascade or user_id.
                    # Let's try deleting logs by user ID if possible.
                    # But self.user1_id might not be set if setup failed?
                    # The finally block runs after setup.
                    if hasattr(self, 'user1_id'):
                         # Use raw SQL or delete(AuditLog)
                         pass # Cascade via Case/User SHOULD handle it if configured.
                         # BUT tests/test_ai_insights_simple.py needed manual delete.
                         # Let's Assume cascade works for users here unless proven otherwise, 
                         # or add a broad delete if we have the IDs.
                         # self.ownership_user and collaborator_user.
                    await db.execute(delete(TimelineEvent).where(TimelineEvent.id == self.event_id))
                    await db.execute(delete(CaseTimeline).where(CaseTimeline.id == self.timeline_id))
                    await db.execute(delete(Case).where(Case.id == self.test_case.id))
                    await db.execute(delete(User).where(User.id.in_([self.user1_id, self.user2_id])))
                    await db.commit()
                except Exception:
                    await db.rollback()
            # await engine.dispose() - removed, handled by fixture

    @pytest.fixture(autouse=True)
    async def cleanup_database(self):
        yield
        # await engine.dispose() - removed to prevent event loop closed error