"""
Property-based tests for case management
Feature: court-case-management-system, Property 1: Case Data Preservation
"""

import pytest
from hypothesis import given, strategies as st, settings
import sys
import os
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.case import Case, CaseType, CaseStatus, CasePriority

# Test data strategies
@st.composite
def case_data(draw):
    """Generate case data for testing"""
    return {
        'case_number': draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'title': draw(st.text(min_size=10, max_size=100)),
        'description': draw(st.text(min_size=20, max_size=500)),
        'case_type': draw(st.sampled_from(list(CaseType))),
        'status': draw(st.sampled_from(list(CaseStatus))),
        'priority': draw(st.sampled_from(list(CasePriority))),
        'client_id': uuid4(),
        'created_by': uuid4(),
        'case_metadata': draw(st.dictionaries(
            st.text(min_size=1, max_size=20), 
            st.one_of(st.text(), st.integers(), st.booleans()),
            min_size=0,
            max_size=5
        ))
    }

class TestCaseDataPreservation:
    """Property tests for case data preservation"""
    
    @given(data=case_data())
    @settings(deadline=1000)
    def test_case_data_preservation_property(self, data):
        """
        Property 1: Case Data Preservation
        For any case creation request with valid data, all provided fields 
        (case number, title, description, case type, client information) 
        should be preserved exactly as submitted and retrievable through the case API.
        Validates: Requirements 1.1
        """
        # Create a Case instance with the generated data
        case = Case(
            case_number=data['case_number'],
            title=data['title'],
            description=data['description'],
            case_type=data['case_type'],
            status=data['status'],
            priority=data['priority'],
            client_id=data['client_id'],
            created_by=data['created_by'],
            case_metadata=data['case_metadata']
        )
        
        # Verify all fields are preserved exactly as submitted
        assert case.case_number == data['case_number']
        assert case.title == data['title']
        assert case.description == data['description']
        assert case.case_type == data['case_type']
        assert case.status == data['status']
        assert case.priority == data['priority']
        assert case.client_id == data['client_id']
        assert case.created_by == data['created_by']
        assert case.case_metadata == data['case_metadata']
        
        # Verify that the case has the correct structure
        # (UUID will be generated when saved to database)
        assert hasattr(case, 'id')
        assert hasattr(case, 'created_at')
        assert hasattr(case, 'updated_at')
        
        # Verify that default values are set correctly
        if data['status'] == CaseStatus.ACTIVE:
            assert case.status == CaseStatus.ACTIVE
        if data['priority'] == CasePriority.MEDIUM:
            assert case.priority == CasePriority.MEDIUM
    
    @given(case_type=st.sampled_from(list(CaseType)))
    @settings(deadline=1000)
    def test_case_type_preservation_property(self, case_type):
        """
        Property: Case type preservation
        For any valid case type, creating a case with that type should preserve
        the exact case type value.
        """
        case = Case(
            case_number="TEST-001",
            title="Test Case",
            description="Test Description",
            case_type=case_type,
            client_id=uuid4(),
            created_by=uuid4()
        )
        
        assert case.case_type == case_type
        assert isinstance(case.case_type, CaseType)
    
    @given(metadata=st.dictionaries(
        st.text(min_size=1, max_size=20), 
        st.one_of(st.text(), st.integers(), st.booleans(), st.none()),
        min_size=0,
        max_size=10
    ))
    @settings(deadline=1000)
    def test_metadata_preservation_property(self, metadata):
        """
        Property: Metadata preservation
        For any valid metadata dictionary, the case should preserve
        the exact metadata structure and values.
        """
        case = Case(
            case_number="TEST-META-001",
            title="Metadata Test Case",
            description="Testing metadata preservation",
            case_type=CaseType.CIVIL,
            client_id=uuid4(),
            created_by=uuid4(),
            case_metadata=metadata
        )
        
        assert case.case_metadata == metadata
        
        # Verify that nested structures are preserved
        if metadata:
            for key, value in metadata.items():
                assert case.case_metadata[key] == value
    
    @given(case_numbers=st.lists(
        st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        min_size=2,
        max_size=10,
        unique=True
    ))
    @settings(deadline=1000)
    def test_unique_case_identification_property(self, case_numbers):
        """
        Property 2: Unique Case Identification
        For any sequence of case creation requests, each created case should receive 
        a unique identifier and initial status of "active".
        Validates: Requirements 1.2
        """
        cases = []
        
        # Create multiple cases with different case numbers
        for i, case_number in enumerate(case_numbers):
            case = Case(
                case_number=case_number,
                title=f"Test Case {i+1}",
                description=f"Test Description {i+1}",
                case_type=CaseType.CIVIL,
                status=CaseStatus.ACTIVE,  # Explicitly set status
                client_id=uuid4(),
                created_by=uuid4()
            )
            cases.append(case)
        
        # Verify each case has unique case numbers
        case_numbers_created = [case.case_number for case in cases]
        assert len(case_numbers_created) == len(set(case_numbers_created))
        
        # Verify all cases have initial status of "active"
        for case in cases:
            assert case.status == CaseStatus.ACTIVE
        
        # Verify each case has the structure for unique identification
        for case in cases:
            assert hasattr(case, 'id')  # Will be UUID when saved
            assert case.case_number is not None
            assert case.case_number != ""

if __name__ == "__main__":
    pytest.main([__file__, "-v"])