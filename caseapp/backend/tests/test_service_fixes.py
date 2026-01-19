
# Validates fixes for service robustness

import pytest
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from services.case_insight_service import CaseInsightService
from services.forensic_analysis_service import ForensicAnalysisService
from models.forensic_analysis import AnalysisStatus

class TestServiceFixes(unittest.IsolatedAsyncioTestCase):
    
    @patch('services.case_insight_service.logger')
    async def test_case_insight_parsing_robustness(self, mock_logger):
        service = CaseInsightService()
        
        # Test Case 1: Valid JSON response
        response_json = '{"primary_category": {"category": "civil", "confidence": 0.9}}'
        result = service._parse_categorization_response(response_json)
        assert result['primary']['category'] == 'civil'
        
        # Test Case 2: Plain string response (Fallback)
        response_string = 'Family Law'
        result = service._parse_categorization_response(response_string)
        assert result['primary']['category'] == 'Family Law'
        assert result['primary']['confidence'] == 0.5
        assert "Extracted" in result['primary']['reasoning']
        
        # Test Case 3: Junk response (Too long to be a category)
        response_junk = "This is a very long response that doesn't look like a category name and definitely is not JSON." * 10
        result = service._parse_categorization_response(response_junk)
        assert result == {}
        mock_logger.warning.assert_any_call("No usable categorization found in AI response", response=response_junk)

    @patch('services.forensic_analysis_service.AsyncSessionLocal')
    @patch('services.forensic_analysis_service.logger')
    async def test_forensic_audit_logging(self, mock_logger, mock_session_local):
        # Mock audit service
        mock_audit = AsyncMock()
        service = ForensicAnalysisService(audit_service=mock_audit)
        
        # Mock DB session and source object
        mock_db = AsyncMock()
        # Ensure the mock returns the same session if called multiple times
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        mock_source = MagicMock()
        mock_source.id = 123
        mock_source.source_type = 'email_archive'
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_source
        mock_db.execute.return_value = mock_result
        
        # Mock internal analysis methods
        service._extract_messages = AsyncMock(return_value=[])
        service._analyze_communication_patterns = AsyncMock(return_value={})
        
        # Run background analysis
        await service._analyze_source_background(source_id=123, case_id=456, user_id=789)
        
        # Debugging: Print all calls to log_action
        print(f"\nAudit calls in success test: {mock_audit.log_action.mock_calls}")
        
        # Verify audit logs
        assert mock_audit.log_action.call_count == 2
        
        # Check START_ANALYSIS call
        mock_audit.log_action.assert_any_call(
            entity_type="forensic_source",
            entity_id=123,
            action="START_ANALYSIS",
            user_id=789,
            case_id=456
        )
        
        # Check COMPLETE_ANALYSIS call
        mock_audit.log_action.assert_any_call(
            entity_type="forensic_source",
            entity_id=123,
            action="COMPLETE_ANALYSIS",
            user_id=789,
            case_id=456
        )

    @patch('services.forensic_analysis_service.AsyncSessionLocal')
    @patch('services.forensic_analysis_service.logger')
    async def test_forensic_audit_failure_logging(self, mock_logger, mock_session_local):
        # Mock audit service
        mock_audit = AsyncMock()
        service = ForensicAnalysisService(audit_service=mock_audit)
        
        # Mock DB session - first call fails, second call succeeds (for the failure update)
        mock_db_fail = AsyncMock()
        mock_db_fail.execute.side_effect = Exception("DB Connection Error")
        
        mock_db_success = AsyncMock()
        mock_db_success.execute.return_value = MagicMock()
        
        # Set up side_effect to return failing session then successful session
        mock_session_local.return_value.__aenter__.side_effect = [mock_db_fail, mock_db_success]
        
        # Run background analysis (it should handle the exception)
        await service._analyze_source_background(source_id=123, case_id=456, user_id=789)
        
        # Debugging: Print all calls to log_action
        print(f"\nAudit calls in failure test: {mock_audit.log_action.mock_calls}")

        # Verify audit logs - should have START and then FAILED
        assert mock_audit.log_action.call_count == 2
        
        # Check FAILED_ANALYSIS call
        mock_audit.log_action.assert_any_call(
            entity_type="forensic_source",
            entity_id=123,
            action="FAILED_ANALYSIS",
            user_id=789,
            case_id=456,
            metadata={"error": "DB Connection Error"}
        )

if __name__ == '__main__':
    unittest.main()
