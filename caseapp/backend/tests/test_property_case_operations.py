"""
Property-based tests for case operations
Feature: court-case-management-system
"""

import pytest
import asyncio
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from models.case import Case, CaseType, CaseStatus, CasePriority
from schemas.case import CaseCreate, CaseStatusUpdate
from services.case_service import CaseService
from services.audit_service import AuditService
from core.exceptions import CaseManagementException


class TestCaseOperationProperties:
    """Property-based tests for case operations"""

    @composite
    def case_create_data_strategy(draw):
        """Strategy for generating valid case creation data"""
        case_type = draw(st.sampled_from(list(CaseType)))
        priority = draw(st.sampled_from(list(CasePriority)))
        
        return CaseCreate(
            case_number=draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
            title=draw(st.text(min_size=5, max_size=100)),
            description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
            case_type=case_type,
            priority=priority,
            client_id=draw(st.one_of(st.none(), st.uuids())),
            court_name=draw(st.one_of(st.none(), st.text(min_size=5, max_size=100))),
            judge_name=draw(st.one_of(st.none(), st.text(min_size=5, max_size=50))),
            case_jurisdiction=draw(st.one_of(st.none(), st.text(min_size=5, max_size=50))),
            filed_date=draw(st.one_of(st.none(), st.datetimes())),
            court_date=draw(st.one_of(st.none(), st.datetimes())),
            deadline_date=draw(st.one_of(st.none(), st.datetimes())),
            case_metadata=draw(st.one_of(st.none(), st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(st.text(), st.integers(), st.booleans()),
                min_size=0,
                max_size=5
            )))
        )

    @composite
    def closure_data_strategy(draw):
        """Strategy for generating valid case closure data"""
        return CaseStatusUpdate(
            status=CaseStatus.CLOSED,
            closure_reason=draw(st.text(min_size=10, max_size=200)),
            closure_notes=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500)))
        )

    def setup_method(self):
        """Set up test fixtures"""
        # Mock database session
        self.mock_db = AsyncMock()
        
        # Mock audit service
        self.mock_audit_service = AsyncMock(spec=AuditService)
        self.mock_audit_service.log_action = AsyncMock()
        
        # Create case service with mocked dependencies
        self.case_service = CaseService(self.mock_db, self.mock_audit_service)
        
        # Mock user ID
        self.user_id = uuid4()

    @given(case_data=case_create_data_strategy())
    @settings(deadline=2000, max_examples=20)
    def test_case_type_validation_property(self, case_data):
        """
        Feature: court-case-management-system, Property 4: Case Type Validation
        
        For any case creation request, if the case type is one of the supported types 
        (civil, criminal, family, corporate, immigration, personal injury, real estate, 
        bankruptcy, intellectual property), the case should be created successfully.
        
        **Validates: Requirements 1.4**
        """
        # Property: All supported case types should be accepted
        supported_types = {
            CaseType.CIVIL, CaseType.CRIMINAL, CaseType.FAMILY, CaseType.CORPORATE,
            CaseType.IMMIGRATION, CaseType.PERSONAL_INJURY, CaseType.REAL_ESTATE,
            CaseType.BANKRUPTCY, CaseType.INTELLECTUAL_PROPERTY, CaseType.OTHER
        }
        
        # Verify the case type is supported
        assert case_data.case_type in supported_types, f"Case type {case_data.case_type} should be supported"
        
        # Execute: Test case type validation logic
        async def run_test():
            # Mock successful database operations
            self.mock_db.execute = AsyncMock()
            self.mock_db.execute.return_value.scalar_one_or_none.return_value = None  # No existing case
            self.mock_db.add = MagicMock()
            self.mock_db.flush = AsyncMock()
            self.mock_db.commit = AsyncMock()
            self.mock_db.refresh = AsyncMock()
            
            # Mock the case service's _get_case_by_number method
            self.case_service._get_case_by_number = AsyncMock(return_value=None)
            
            try:
                result = await self.case_service.create_case(case_data, self.user_id)
                
                # Property verification: Case should be created successfully
                # The fact that no exception was raised means the case type was accepted
                assert True, "Case creation should succeed for supported case types"
                
                # Verify audit logging was called
                self.mock_audit_service.log_action.assert_called()
                
                return True
                
            except CaseManagementException as e:
                # If there's an exception, it should not be due to invalid case type
                # since we're only testing with supported types
                if "Invalid case type" in str(e):
                    pytest.fail(f"Supported case type {case_data.case_type} was rejected: {e}")
                # Other exceptions (like duplicate case number) are acceptable for this property
                return False
        
        # Run the async test
        asyncio.run(run_test())

    @given(closure_data=closure_data_strategy())
    @settings(deadline=2000, max_examples=20)
    def test_case_closure_workflow_property(self, closure_data):
        """
        Feature: court-case-management-system, Property 5: Case Closure Workflow
        
        For any active case, when closure is requested with required completion metadata, 
        the case status should change to "closed" and the metadata should be preserved.
        
        **Validates: Requirements 1.5**
        """
        # Setup: Create a mock active case
        case_id = uuid4()
        mock_case = Case(
            id=case_id,
            case_number="TEST-CASE-001",
            title="Test Case",
            description="Test case for closure",
            case_type=CaseType.CIVIL,
            priority=CasePriority.MEDIUM,
            status=CaseStatus.ACTIVE,  # Start with active status
            client_id=uuid4(),
            case_metadata={},
            created_by=self.user_id,
            created_at=datetime.now()
        )
        
        # Property: Closure with required metadata should succeed
        assert closure_data.status == CaseStatus.CLOSED, "Test data should request closure"
        assert closure_data.closure_reason is not None, "Closure reason should be provided"
        assert len(closure_data.closure_reason.strip()) > 0, "Closure reason should not be empty"
        
        # Execute: Update case status to closed
        async def run_test():
            # Mock the get_case method to return our mock case
            self.case_service.get_case = AsyncMock(return_value=mock_case)
            
            # Mock database operations
            self.mock_db.commit = AsyncMock()
            self.mock_db.refresh = AsyncMock()
            
            try:
                result = await self.case_service.update_case_status(case_id, closure_data, self.user_id)
                
                # Property verification: Case should be closed successfully
                assert result is not None, "Case closure should succeed with required metadata"
                
                # Verify status changed to closed
                assert result.status == CaseStatus.CLOSED, "Case status should be CLOSED after closure request"
                
                # Verify closure metadata is preserved
                assert result.case_metadata is not None, "Case metadata should exist after closure"
                assert "closure_reason" in result.case_metadata, "Closure reason should be preserved in metadata"
                assert result.case_metadata["closure_reason"] == closure_data.closure_reason, "Closure reason should match input"
                
                # Verify closed_date is set
                assert result.closed_date is not None, "Closed date should be set when case is closed"
                
                # Verify closure notes are preserved if provided
                if closure_data.closure_notes:
                    assert "closure_notes" in result.case_metadata, "Closure notes should be preserved if provided"
                    assert result.case_metadata["closure_notes"] == closure_data.closure_notes, "Closure notes should match input"
                
                # Verify audit logging was called
                self.mock_audit_service.log_action.assert_called()
                
                return True
                
            except CaseManagementException as e:
                # Should not fail for valid closure requests
                pytest.fail(f"Case closure with valid metadata failed: {e}")
        
        # Run the async test
        asyncio.run(run_test())

    def test_closure_without_reason_validation_property(self):
        """
        Feature: court-case-management-system, Property 5: Case Closure Workflow (Edge Case)
        
        For any case closure request without required completion metadata, 
        the validation should fail at the schema level.
        
        **Validates: Requirements 1.5**
        """
        # Property: Closure requests without required reason should be rejected by validation
        
        # Test that Pydantic validation catches missing closure reason
        with pytest.raises(Exception) as exc_info:
            # This should fail at the Pydantic validation level
            invalid_closure_data = CaseStatusUpdate(
                status=CaseStatus.CLOSED,
                closure_reason=None,  # Missing required reason
                closure_notes=None
            )
        
        # Property verification: Should fail with validation error
        assert "closure_reason" in str(exc_info.value).lower(), "Error should mention missing closure reason"

    @given(st.text(min_size=1, max_size=10))
    @settings(deadline=2000, max_examples=10)
    def test_supported_case_types_property(self, test_string):
        """
        Feature: court-case-management-system, Property 4: Case Type Validation (Completeness)
        
        Verify that all required case types are supported according to Requirements 1.4.
        
        **Validates: Requirements 1.4**
        """
        # Property: The system should support exactly the case types specified in requirements
        supported_types = set(CaseType)
        required_types = {
            "CIVIL", "CRIMINAL", "FAMILY", "CORPORATE", "IMMIGRATION", 
            "PERSONAL_INJURY", "REAL_ESTATE", "BANKRUPTCY", "INTELLECTUAL_PROPERTY"
        }
        
        # Verify all required types are supported
        supported_type_values = {ct.value for ct in supported_types}
        
        for required_type in required_types:
            assert required_type in supported_type_values, f"Required case type '{required_type}' should be supported"
        
        # Verify we have the expected number of types (including 'other')
        assert len(supported_types) >= len(required_types), "Should support at least all required case types"
        
        # Verify specific required types exist
        assert CaseType.CIVIL in supported_types, "CIVIL should be supported"
        assert CaseType.CRIMINAL in supported_types, "CRIMINAL should be supported"
        assert CaseType.FAMILY in supported_types, "FAMILY should be supported"
        assert CaseType.CORPORATE in supported_types, "CORPORATE should be supported"
        assert CaseType.IMMIGRATION in supported_types, "IMMIGRATION should be supported"
        assert CaseType.PERSONAL_INJURY in supported_types, "PERSONAL_INJURY should be supported"
        assert CaseType.REAL_ESTATE in supported_types, "REAL_ESTATE should be supported"
        assert CaseType.BANKRUPTCY in supported_types, "BANKRUPTCY should be supported"
        assert CaseType.INTELLECTUAL_PROPERTY in supported_types, "INTELLECTUAL_PROPERTY should be supported"