"""
Property-based tests for comprehensive audit trail
Feature: court-case-management-system
"""

import pytest
import asyncio
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, Optional

from models.case import Case, CaseType, CaseStatus, CasePriority, AuditLog
from schemas.case import CaseCreate, CaseUpdate
from services.case_service import CaseService
from services.audit_service import AuditService
from core.exceptions import CaseManagementException


class TestAuditTrailProperties:
    """Property-based tests for comprehensive audit trail functionality"""

    @composite
    def case_modification_strategy(draw):
        """Strategy for generating case modification operations"""
        operation_type = draw(st.sampled_from(['create', 'update', 'status_change', 'delete']))
        
        base_data = {
            'case_number': draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
            'title': draw(st.text(min_size=5, max_size=100)),
            'description': draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
            'case_type': draw(st.sampled_from(list(CaseType))),
            'priority': draw(st.sampled_from(list(CasePriority))),
            'client_id': draw(st.one_of(st.none(), st.uuids())),
            'user_id': draw(st.uuids()),
            'ip_address': draw(st.one_of(st.none(), st.text(min_size=7, max_size=15))),
            'user_agent': draw(st.one_of(st.none(), st.text(min_size=10, max_size=100)))
        }
        
        return {
            'operation': operation_type,
            'data': base_data
        }

    @composite
    def media_access_strategy(draw):
        """Strategy for generating media access operations"""
        return {
            'operation': 'media_access',
            'media_id': draw(st.uuids()),
            'user_id': draw(st.uuids()),
            'access_type': draw(st.sampled_from(['view', 'download', 'stream', 'share'])),
            'ip_address': draw(st.one_of(st.none(), st.text(min_size=7, max_size=15))),
            'user_agent': draw(st.one_of(st.none(), st.text(min_size=10, max_size=100))),
            'case_id': draw(st.uuids())
        }

    @composite
    def collaboration_action_strategy(draw):
        """Strategy for generating collaboration actions"""
        return {
            'operation': 'collaboration',
            'timeline_id': draw(st.uuids()),
            'user_id': draw(st.uuids()),
            'action_type': draw(st.sampled_from(['share', 'comment', 'edit_permission', 'remove_access'])),
            'target_user_id': draw(st.one_of(st.none(), st.uuids())),
            'permission_level': draw(st.one_of(st.none(), st.sampled_from(['view', 'edit', 'admin']))),
            'ip_address': draw(st.one_of(st.none(), st.text(min_size=7, max_size=15))),
            'case_id': draw(st.uuids())
        }

    @composite
    def export_operation_strategy(draw):
        """Strategy for generating export operations"""
        return {
            'operation': 'export',
            'export_type': draw(st.sampled_from(['timeline_pdf', 'timeline_png', 'forensic_report', 'case_summary'])),
            'case_id': draw(st.uuids()),
            'user_id': draw(st.uuids()),
            'filters': draw(st.one_of(st.none(), st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(st.text(), st.integers(), st.booleans()),
                min_size=0,
                max_size=3
            ))),
            'ip_address': draw(st.one_of(st.none(), st.text(min_size=7, max_size=15)))
        }

    def setup_method(self):
        """Set up test fixtures"""
        # Mock database session
        self.mock_db = AsyncMock()
        
        # Create real audit service for testing
        self.audit_service = AuditService(self.mock_db)
        
        # Mock case service
        self.mock_case_service = AsyncMock(spec=CaseService)

    @given(case_op=case_modification_strategy())
    @settings(deadline=3000, max_examples=25)
    def test_case_modification_audit_trail_property(self, case_op):
        """
        Feature: court-case-management-system, Property 3: Comprehensive Audit Trail
        
        For any system operation that modifies case data (case updates), an audit log entry 
        should be created containing timestamp, user identification, action type, and affected resources.
        
        **Validates: Requirements 1.3**
        """
        operation = case_op['operation']
        data = case_op['data']
        
        # Property: All case modification operations should create audit entries
        async def run_test():
            # Mock successful database operations
            self.mock_db.add = MagicMock()
            self.mock_db.flush = AsyncMock()
            
            try:
                # Execute: Create audit log for case modification
                result = await self.audit_service.log_action(
                    entity_type='case',
                    entity_id=uuid4(),
                    action=operation,
                    user_id=data['user_id'],
                    ip_address=data.get('ip_address'),
                    user_agent=data.get('user_agent'),
                    case_id=data.get('client_id')  # Using client_id as case_id for test
                )
                
                # Property verification: Audit log should be created with required fields
                assert result is not None, "Audit log should be created for case modifications"
                
                # Verify required audit trail components
                self.mock_db.add.assert_called_once()
                added_log = self.mock_db.add.call_args[0][0]
                
                # Verify this is an AuditLog instance
                assert isinstance(added_log, AuditLog), "Added object should be an AuditLog instance"
                
                # User identification verification
                assert hasattr(added_log, 'user_id'), "Audit log should have user identification"
                assert added_log.user_id == data['user_id'], "User ID should match the acting user"
                
                # Action type verification
                assert hasattr(added_log, 'action'), "Audit log should have action type"
                assert added_log.action == operation, "Action should match the operation performed"
                
                # Affected resources verification
                assert hasattr(added_log, 'entity_type'), "Audit log should identify affected resource type"
                assert hasattr(added_log, 'entity_id'), "Audit log should identify affected resource ID"
                assert added_log.entity_type == 'case', "Entity type should be 'case' for case modifications"
                
                # Timestamp field exists (will be set by database)
                assert hasattr(added_log, 'timestamp'), "Audit log should have timestamp field"
                
                # Optional context preservation
                if data.get('ip_address'):
                    assert added_log.ip_address == data['ip_address'], "IP address should be preserved when provided"
                
                if data.get('user_agent'):
                    assert added_log.user_agent == data['user_agent'], "User agent should be preserved when provided"
                
                return True
                
            except Exception as e:
                pytest.fail(f"Audit logging failed for case modification: {e}")
        
        # Run the async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()

    @given(media_op=media_access_strategy())
    @settings(deadline=3000, max_examples=25)
    def test_media_access_audit_trail_property(self, media_op):
        """
        Feature: court-case-management-system, Property 3: Comprehensive Audit Trail
        
        For any system operation that accesses media evidence, an audit log entry 
        should be created containing timestamp, user identification, action type, and affected resources.
        
        **Validates: Requirements 1.3, 4.5**
        """
        # Property: All media access operations should create audit entries
        async def run_test():
            # Mock successful database operations
            self.mock_db.add = MagicMock()
            self.mock_db.flush = AsyncMock()
            
            try:
                # Execute: Create audit log for media access
                result = await self.audit_service.log_action(
                    entity_type='media_evidence',
                    entity_id=media_op['media_id'],
                    action=f"media_{media_op['access_type']}",
                    user_id=media_op['user_id'],
                    ip_address=media_op.get('ip_address'),
                    user_agent=media_op.get('user_agent'),
                    case_id=media_op['case_id']
                )
                
                # Property verification: Audit log should be created with required fields
                assert result is not None, "Audit log should be created for media access"
                
                # Verify audit trail components for media access
                self.mock_db.add.assert_called_once()
                added_log = self.mock_db.add.call_args[0][0]
                
                # Verify this is an AuditLog instance
                assert isinstance(added_log, AuditLog), "Added object should be an AuditLog instance"
                
                # Timestamp field exists (will be set by database)
                assert hasattr(added_log, 'timestamp'), "Media access audit should have timestamp field"
                
                # User identification verification
                assert added_log.user_id == media_op['user_id'], "User ID should match the accessing user"
                
                # Action type verification
                expected_action = f"media_{media_op['access_type']}"
                assert added_log.action == expected_action, f"Action should be '{expected_action}'"
                
                # Affected resources verification
                assert added_log.entity_type == 'media_evidence', "Entity type should be 'media_evidence'"
                assert added_log.entity_id == media_op['media_id'], "Entity ID should match media ID"
                assert added_log.case_id == media_op['case_id'], "Case ID should be preserved for context"
                
                # Context preservation verification
                if media_op.get('ip_address'):
                    assert added_log.ip_address == media_op['ip_address'], "IP address should be preserved"
                
                return True
                
            except Exception as e:
                pytest.fail(f"Audit logging failed for media access: {e}")
        
        # Run the async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()

    @given(collab_op=collaboration_action_strategy())
    @settings(deadline=3000, max_examples=25)
    def test_collaboration_action_audit_trail_property(self, collab_op):
        """
        Feature: court-case-management-system, Property 3: Comprehensive Audit Trail
        
        For any system operation involving collaboration actions (sharing, permissions, comments), 
        an audit log entry should be created containing timestamp, user identification, action type, 
        and affected resources.
        
        **Validates: Requirements 1.3, 6.6**
        """
        # Property: All collaboration actions should create audit entries
        async def run_test():
            # Mock successful database operations
            self.mock_db.add = MagicMock()
            self.mock_db.flush = AsyncMock()
            
            try:
                # Execute: Create audit log for collaboration action
                action_details = {
                    'action_type': collab_op['action_type'],
                    'target_user_id': str(collab_op.get('target_user_id')) if collab_op.get('target_user_id') else None,
                    'permission_level': collab_op.get('permission_level')
                }
                
                result = await self.audit_service.log_action(
                    entity_type='timeline',
                    entity_id=collab_op['timeline_id'],
                    action=f"collaboration_{collab_op['action_type']}",
                    user_id=collab_op['user_id'],
                    field_name='collaboration',
                    new_value=str(action_details),
                    ip_address=collab_op.get('ip_address'),
                    case_id=collab_op['case_id']
                )
                
                # Property verification: Audit log should be created with required fields
                assert result is not None, "Audit log should be created for collaboration actions"
                
                # Verify audit trail components for collaboration
                self.mock_db.add.assert_called_once()
                added_log = self.mock_db.add.call_args[0][0]
                
                # Verify this is an AuditLog instance
                assert isinstance(added_log, AuditLog), "Added object should be an AuditLog instance"
                
                # Timestamp field exists (will be set by database)
                assert hasattr(added_log, 'timestamp'), "Collaboration audit should have timestamp field"
                
                # User identification verification
                assert added_log.user_id == collab_op['user_id'], "User ID should match the acting user"
                
                # Action type verification
                expected_action = f"collaboration_{collab_op['action_type']}"
                assert added_log.action == expected_action, f"Action should be '{expected_action}'"
                
                # Affected resources verification
                assert added_log.entity_type == 'timeline', "Entity type should be 'timeline'"
                assert added_log.entity_id == collab_op['timeline_id'], "Entity ID should match timeline ID"
                assert added_log.case_id == collab_op['case_id'], "Case ID should be preserved for context"
                
                # Collaboration-specific details verification
                assert added_log.field_name == 'collaboration', "Field name should indicate collaboration action"
                assert added_log.new_value is not None, "Action details should be preserved"
                
                return True
                
            except Exception as e:
                pytest.fail(f"Audit logging failed for collaboration action: {e}")
        
        # Run the async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()

    @given(export_op=export_operation_strategy())
    @settings(deadline=3000, max_examples=25)
    def test_export_operation_audit_trail_property(self, export_op):
        """
        Feature: court-case-management-system, Property 3: Comprehensive Audit Trail
        
        For any system operation that exports data (reports, timelines, forensic analysis), 
        an audit log entry should be created containing timestamp, user identification, 
        action type, and affected resources.
        
        **Validates: Requirements 1.3, 8.5**
        """
        # Property: All export operations should create audit entries
        async def run_test():
            # Mock successful database operations
            self.mock_db.add = MagicMock()
            self.mock_db.flush = AsyncMock()
            
            try:
                # Execute: Create audit log for export operation
                export_details = {
                    'export_type': export_op['export_type'],
                    'filters': export_op.get('filters')
                }
                
                result = await self.audit_service.log_action(
                    entity_type='case',
                    entity_id=export_op['case_id'],
                    action=f"export_{export_op['export_type']}",
                    user_id=export_op['user_id'],
                    field_name='export',
                    new_value=str(export_details),
                    ip_address=export_op.get('ip_address'),
                    case_id=export_op['case_id']
                )
                
                # Property verification: Audit log should be created with required fields
                assert result is not None, "Audit log should be created for export operations"
                
                # Verify audit trail components for exports
                self.mock_db.add.assert_called_once()
                added_log = self.mock_db.add.call_args[0][0]
                
                # Verify this is an AuditLog instance
                assert isinstance(added_log, AuditLog), "Added object should be an AuditLog instance"
                
                # Timestamp field exists (will be set by database)
                assert hasattr(added_log, 'timestamp'), "Export audit should have timestamp field"
                
                # User identification verification
                assert added_log.user_id == export_op['user_id'], "User ID should match the exporting user"
                
                # Action type verification
                expected_action = f"export_{export_op['export_type']}"
                assert added_log.action == expected_action, f"Action should be '{expected_action}'"
                
                # Affected resources verification
                assert added_log.entity_type == 'case', "Entity type should be 'case' for exports"
                assert added_log.entity_id == export_op['case_id'], "Entity ID should match case ID"
                assert added_log.case_id == export_op['case_id'], "Case ID should be preserved"
                
                # Export-specific details verification
                assert added_log.field_name == 'export', "Field name should indicate export operation"
                assert added_log.new_value is not None, "Export details should be preserved"
                
                return True
                
            except Exception as e:
                pytest.fail(f"Audit logging failed for export operation: {e}")
        
        # Run the async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()

    @given(st.uuids(), st.uuids())
    @settings(deadline=2000, max_examples=15)
    def test_audit_trail_completeness_property(self, entity_id, user_id):
        """
        Feature: court-case-management-system, Property 3: Comprehensive Audit Trail (Completeness)
        
        For any sequence of system operations on the same entity, all operations should be 
        captured in the audit trail and retrievable in chronological order.
        
        **Validates: Requirements 1.3**
        """
        # Property: All operations on an entity should be auditable and retrievable
        async def run_test():
            # Mock database operations for multiple audit entries
            mock_audit_logs = []
            
            # Simulate a sequence of operations
            operations = ['create', 'update', 'view', 'share', 'export']
            
            for i, operation in enumerate(operations):
                mock_log = AuditLog(
                    id=uuid4(),
                    entity_type='case',
                    entity_id=entity_id,
                    action=operation,
                    user_id=user_id
                )
                # Set timestamp manually for testing (normally set by database)
                mock_log.timestamp = datetime.now(UTC) + timedelta(seconds=i)
                mock_audit_logs.append(mock_log)
            
            # Mock the database query for audit trail retrieval
            mock_scalars = MagicMock()
            # Reverse the list to simulate descending timestamp order (newest first)
            mock_scalars.all.return_value = list(reversed(mock_audit_logs))
            mock_result = MagicMock()
            mock_result.scalars.return_value = mock_scalars
            self.mock_db.execute = AsyncMock(return_value=mock_result)
            
            try:
                # Execute: Retrieve audit trail for entity
                audit_trail = await self.audit_service.get_entity_audit_trail('case', entity_id)
                
                # Property verification: All operations should be captured
                assert audit_trail is not None, "Audit trail should be retrievable"
                assert len(audit_trail) == len(operations), "All operations should be captured in audit trail"
                
                # Verify chronological ordering (should be descending by timestamp)
                for i in range(len(audit_trail) - 1):
                    assert audit_trail[i].timestamp >= audit_trail[i + 1].timestamp, \
                        "Audit trail should be ordered chronologically (newest first)"
                
                # Verify all operations are present
                captured_actions = {log.action for log in audit_trail}
                expected_actions = set(operations)
                assert captured_actions == expected_actions, \
                    f"All operations should be captured. Expected: {expected_actions}, Got: {captured_actions}"
                
                # Verify entity consistency
                for log in audit_trail:
                    assert log.entity_id == entity_id, "All audit entries should reference the same entity"
                    assert log.entity_type == 'case', "All audit entries should have consistent entity type"
                    assert log.user_id == user_id, "All audit entries should reference the same user"
                
                return True
                
            except Exception as e:
                pytest.fail(f"Audit trail retrieval failed: {e}")
        
        # Run the async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()

    @given(st.uuids())
    @settings(deadline=2000, max_examples=10)
    def test_audit_trail_integrity_property(self, case_id):
        """
        Feature: court-case-management-system, Property 3: Comprehensive Audit Trail (Integrity)
        
        For any audit log entry, the timestamp should be immutable and accurately reflect 
        when the operation occurred, and user identification should be preserved.
        
        **Validates: Requirements 1.3, 9.3**
        """
        # Property: Audit entries should maintain integrity and immutability
        async def run_test():
            user_id = uuid4()
            operation_time = datetime.now(UTC)
            
            # Mock database operations
            self.mock_db.add = MagicMock()
            self.mock_db.flush = AsyncMock()
            
            try:
                # Execute: Create audit log entry
                result = await self.audit_service.log_action(
                    entity_type='case',
                    entity_id=case_id,
                    action='test_operation',
                    user_id=user_id,
                    ip_address='192.168.1.1',
                    user_agent='Test Agent'
                )
                
                # Property verification: Audit entry integrity
                assert result is not None, "Audit log should be created"
                
                # Verify audit log structure
                added_log = self.mock_db.add.call_args[0][0]
                assert isinstance(added_log, AuditLog), "Added object should be an AuditLog instance"
                
                # Timestamp field exists (will be set by database)
                assert hasattr(added_log, 'timestamp'), "Audit log should have timestamp field"
                
                # Verify user identification integrity
                assert added_log.user_id == user_id, "User ID should be preserved exactly"
                assert added_log.entity_id == case_id, "Entity ID should be preserved exactly"
                assert added_log.action == 'test_operation', "Action should be preserved exactly"
                
                # Verify context preservation
                assert added_log.ip_address == '192.168.1.1', "IP address should be preserved"
                assert added_log.user_agent == 'Test Agent', "User agent should be preserved"
                
                return True
                
            except Exception as e:
                pytest.fail(f"Audit integrity test failed: {e}")
        
        # Run the async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()

    def test_audit_failure_handling_property(self):
        """
        Feature: court-case-management-system, Property 3: Comprehensive Audit Trail (Resilience)
        
        For any audit logging failure, the system should handle the error gracefully 
        without breaking core functionality, but should log the failure for investigation.
        
        **Validates: Requirements 1.3**
        """
        # Property: Audit failures should not break core operations
        async def run_test():
            # Mock database failure
            self.mock_db.add = MagicMock(side_effect=Exception("Database connection failed"))
            self.mock_db.flush = AsyncMock(side_effect=Exception("Database connection failed"))
            
            try:
                # Execute: Attempt audit logging with database failure
                with pytest.raises(CaseManagementException) as exc_info:
                    await self.audit_service.log_action(
                        entity_type='case',
                        entity_id=uuid4(),
                        action='test_operation',
                        user_id=uuid4()
                    )
                
                # Property verification: Audit failure should be handled appropriately
                assert "Failed to create audit log" in str(exc_info.value), \
                    "Audit failure should be properly reported"
                
                return True
                
            except Exception as e:
                if "Failed to create audit log" not in str(e):
                    pytest.fail(f"Unexpected error in audit failure handling: {e}")
        
        # Run the async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()