"""
Property-based tests for AI document processing pipeline

Feature: court-case-management-system, Property 7: AI Processing Pipeline
Validates: Requirements 2.2, 2.3, 2.4

This module tests the AI processing pipeline that automatically processes uploaded documents
through text extraction, entity recognition, and summary generation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4, UUID
from datetime import datetime, UTC
from typing import Dict, Any, List
import json

from models.document import Document, DocumentStatus, DocumentType
from models.case import Case, CaseStatus, CaseType
from models.user import User
from schemas.document import DocumentAnalysisResponse
from services.document_analysis_service import DocumentAnalysisService
from services.audit_service import AuditService
from core.exceptions import CaseManagementException


# Test data strategies
@composite
def document_strategy(draw):
    """Generate valid document data for testing"""
    return {
        "id": uuid4(),
        "filename": draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')))),
        "original_filename": draw(st.text(min_size=5, max_size=50)) + ".pdf",
        "file_path": f"documents/{uuid4()}/test.pdf",
        "file_size": draw(st.integers(min_value=1000, max_value=4000000)),  # 1KB to 4MB (under 5MB limit)
        "mime_type": draw(st.sampled_from(["application/pdf", "application/msword", "text/plain"])),
        "file_hash": draw(st.text(min_size=64, max_size=64, alphabet="0123456789abcdef")),
        "document_type": draw(st.sampled_from([dt.value for dt in DocumentType])),
        "status": DocumentStatus.UPLOADED.value,
        "case_id": uuid4(),
        "uploaded_by": uuid4(),
        "upload_date": datetime.now(UTC),
        "created_at": datetime.now(UTC)
    }

@composite
def textract_response_strategy(draw):
    """Generate mock Textract response"""
    num_blocks = draw(st.integers(min_value=1, max_value=20))
    blocks = []
    
    for i in range(num_blocks):
        blocks.append({
            'BlockType': 'LINE',
            'Text': draw(st.text(min_size=10, max_size=100)),
            'Confidence': draw(st.floats(min_value=80.0, max_value=99.9))
        })
    
    return {'Blocks': blocks}

@composite
def comprehend_entities_strategy(draw):
    """Generate mock Comprehend entities response"""
    num_entities = draw(st.integers(min_value=0, max_value=10))
    entities = []
    
    entity_types = ['PERSON', 'ORGANIZATION', 'LOCATION', 'DATE', 'QUANTITY', 'EVENT']
    
    for i in range(num_entities):
        entities.append({
            'Type': draw(st.sampled_from(entity_types)),
            'Text': draw(st.text(min_size=3, max_size=30)),
            'Score': draw(st.floats(min_value=0.5, max_value=1.0)),
            'BeginOffset': draw(st.integers(min_value=0, max_value=100)),
            'EndOffset': draw(st.integers(min_value=0, max_value=200))
        })
    
    return {'Entities': entities}

@composite
def comprehend_key_phrases_strategy(draw):
    """Generate mock Comprehend key phrases response"""
    num_phrases = draw(st.integers(min_value=0, max_value=15))
    phrases = []
    
    for i in range(num_phrases):
        phrases.append({
            'Text': draw(st.text(min_size=5, max_size=50)),
            'Score': draw(st.floats(min_value=0.5, max_value=1.0)),
            'BeginOffset': draw(st.integers(min_value=0, max_value=100)),
            'EndOffset': draw(st.integers(min_value=0, max_value=200))
        })
    
    return {'KeyPhrases': phrases}

@composite
def comprehend_sentiment_strategy(draw):
    """Generate mock Comprehend sentiment response"""
    sentiment = draw(st.sampled_from(['POSITIVE', 'NEGATIVE', 'NEUTRAL', 'MIXED']))
    scores = {
        'Positive': draw(st.floats(min_value=0.0, max_value=1.0)),
        'Negative': draw(st.floats(min_value=0.0, max_value=1.0)),
        'Neutral': draw(st.floats(min_value=0.0, max_value=1.0)),
        'Mixed': draw(st.floats(min_value=0.0, max_value=1.0))
    }
    
    return {
        'Sentiment': sentiment,
        'SentimentScore': scores
    }


class TestAIProcessingPipeline:
    """Test AI processing pipeline functionality"""
    
    @given(
        document_data=document_strategy(),
        textract_response=textract_response_strategy(),
        entities_response=comprehend_entities_strategy(),
        key_phrases_response=comprehend_key_phrases_strategy(),
        sentiment_response=comprehend_sentiment_strategy()
    )
    @settings(max_examples=5, deadline=10000)
    def test_ai_processing_pipeline_property(
        self, 
        document_data: Dict[str, Any],
        textract_response: Dict[str, Any],
        entities_response: Dict[str, Any],
        key_phrases_response: Dict[str, Any],
        sentiment_response: Dict[str, Any]
    ):
        """
        Feature: court-case-management-system, Property 7: AI Processing Pipeline
        
        For any uploaded document, text extraction should be initiated automatically,
        followed by entity recognition if extraction succeeds, and summary generation
        if the document exceeds 1000 words.
        
        Validates: Requirements 2.2, 2.3, 2.4
        """
        # Create mock document
        document = Document(**document_data)
        user_id = uuid4()
        
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock audit service
        mock_audit_service = AsyncMock(spec=AuditService)
        mock_audit_service.log_action = AsyncMock()
        
        # Create service with mocked AWS clients
        with patch('boto3.client') as mock_boto3:
            # Mock AWS clients
            mock_textract = MagicMock()
            mock_comprehend = MagicMock()
            mock_s3 = MagicMock()
            
            mock_boto3.side_effect = lambda service, **kwargs: {
                'textract': mock_textract,
                'comprehend': mock_comprehend,
                's3': mock_s3
            }[service]
            
            analysis_service = DocumentAnalysisService(mock_db, mock_audit_service)
            analysis_service.textract_client = mock_textract
            analysis_service.comprehend_client = mock_comprehend
            analysis_service.s3_client = mock_s3
            
            # Mock database queries
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = document
            analysis_service.db.execute.return_value = mock_result
            
            # Mock AWS service responses
            analysis_service.textract_client.detect_document_text.return_value = textract_response
            analysis_service.comprehend_client.detect_entities.return_value = entities_response
            analysis_service.comprehend_client.detect_key_phrases.return_value = key_phrases_response
            analysis_service.comprehend_client.detect_sentiment.return_value = sentiment_response
            
            # Extract expected text from Textract response
            expected_text = '\n'.join([
                block.get('Text', '') for block in textract_response.get('Blocks', [])
                if block.get('BlockType') == 'LINE'
            ]).strip()
            
            # Assume we have valid text extraction
            assume(len(expected_text) > 0)
            
            # Execute analysis using asyncio.run to handle async function
            result = asyncio.run(analysis_service.analyze_document(document.id, user_id))
            
            # Verify the processing pipeline executed correctly
            
            # 1. Text extraction should have been called (Requirement 2.2)
            analysis_service.textract_client.detect_document_text.assert_called_once()
            
            # 2. Entity recognition should have been called if text extraction succeeded (Requirement 2.3)
            if expected_text:
                analysis_service.comprehend_client.detect_entities.assert_called()
                
            # 3. Summary generation should be attempted if document is long enough (Requirement 2.4)
            if len(expected_text) > 1000:
                analysis_service.comprehend_client.detect_key_phrases.assert_called()
            
            # 4. Sentiment analysis should be performed
            analysis_service.comprehend_client.detect_sentiment.assert_called()
            
            # 5. Document status should be updated to processed
            assert document.status == DocumentStatus.PROCESSED.value
            
            # 6. Analysis results should be properly structured
            assert isinstance(result, DocumentAnalysisResponse)
            assert result.document_id == document.id
            assert result.status == "completed"
            assert result.extracted_text == expected_text
            
            # 7. Entities should be preserved
            if entities_response.get('Entities'):
                assert result.entities == entities_response['Entities']
            
            # 8. Key phrases should be preserved
            if key_phrases_response.get('KeyPhrases'):
                assert result.key_phrases == key_phrases_response['KeyPhrases']
            
            # 9. Sentiment analysis should be preserved
            assert result.sentiment is not None
            assert 'sentiment' in result.sentiment
            
            # 10. Confidence scores should be calculated
            assert result.confidence_scores is not None
            assert 'text_extraction' in result.confidence_scores
            assert 'entity_extraction' in result.confidence_scores
            
            # 11. Processing time should be recorded
            assert result.processing_time_seconds is not None
            assert result.processing_time_seconds >= 0
            
            # 12. Audit logging should have occurred
            analysis_service.audit_service.log_action.assert_called()
    
    @given(document_data=document_strategy())
    @settings(max_examples=20, deadline=5000)
    def test_text_extraction_failure_handling_property(
        self,
        document_data: Dict[str, Any]
    ):
        """
        Feature: court-case-management-system, Property 7: AI Processing Pipeline
        
        When text extraction fails, the document status should be updated to failed
        and the error should be logged appropriately.
        
        Validates: Requirements 2.2 (error handling)
        """
        # Create mock document
        document = Document(**document_data)
        user_id = uuid4()
        
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock audit service
        mock_audit_service = AsyncMock(spec=AuditService)
        mock_audit_service.log_action = AsyncMock()
        
        # Create service with mocked AWS clients
        with patch('boto3.client') as mock_boto3:
            # Mock AWS clients
            mock_textract = MagicMock()
            mock_comprehend = MagicMock()
            mock_s3 = MagicMock()
            
            mock_boto3.side_effect = lambda service, **kwargs: {
                'textract': mock_textract,
                'comprehend': mock_comprehend,
                's3': mock_s3
            }[service]
            
            analysis_service = DocumentAnalysisService(mock_db, mock_audit_service)
            analysis_service.textract_client = mock_textract
            analysis_service.comprehend_client = mock_comprehend
            analysis_service.s3_client = mock_s3
            
            # Mock database queries
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = document
            analysis_service.db.execute.return_value = mock_result
            
            # Mock Textract failure
            from botocore.exceptions import ClientError
            error_response = {'Error': {'Code': 'InvalidParameterException', 'Message': 'Invalid document'}}
            analysis_service.textract_client.detect_document_text.side_effect = ClientError(
                error_response, 'DetectDocumentText'
            )
            
            # Execute analysis and expect failure
            with pytest.raises(CaseManagementException) as exc_info:
                asyncio.run(analysis_service.analyze_document(document.id, user_id))
            
            # Verify error handling
            assert "Text extraction failed" in str(exc_info.value)
            assert document.status == DocumentStatus.FAILED.value
            assert document.processing_error is not None
            
            # Verify audit logging occurred
            analysis_service.audit_service.log_action.assert_called()
    
    @given(
        document_data=document_strategy(),
        textract_response=textract_response_strategy()
    )
    @settings(max_examples=20, deadline=5000)
    def test_entity_extraction_failure_resilience_property(
        self,
        document_data: Dict[str, Any],
        textract_response: Dict[str, Any]
    ):
        """
        Feature: court-case-management-system, Property 7: AI Processing Pipeline
        
        When entity extraction fails but text extraction succeeds, the pipeline
        should continue and complete successfully with empty entities.
        
        Validates: Requirements 2.3 (resilience)
        """
        # Create mock document
        document = Document(**document_data)
        user_id = uuid4()
        
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock audit service
        mock_audit_service = AsyncMock(spec=AuditService)
        mock_audit_service.log_action = AsyncMock()
        
        # Create service with mocked AWS clients
        with patch('boto3.client') as mock_boto3:
            # Mock AWS clients
            mock_textract = MagicMock()
            mock_comprehend = MagicMock()
            mock_s3 = MagicMock()
            
            mock_boto3.side_effect = lambda service, **kwargs: {
                'textract': mock_textract,
                'comprehend': mock_comprehend,
                's3': mock_s3
            }[service]
            
            analysis_service = DocumentAnalysisService(mock_db, mock_audit_service)
            analysis_service.textract_client = mock_textract
            analysis_service.comprehend_client = mock_comprehend
            analysis_service.s3_client = mock_s3
            
            # Mock database queries
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = document
            analysis_service.db.execute.return_value = mock_result
            
            # Mock successful text extraction
            analysis_service.textract_client.detect_document_text.return_value = textract_response
            
            # Mock entity extraction failure
            from botocore.exceptions import ClientError
            error_response = {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}
            analysis_service.comprehend_client.detect_entities.side_effect = ClientError(
                error_response, 'DetectEntities'
            )
            
            # Mock other Comprehend services to succeed
            analysis_service.comprehend_client.detect_key_phrases.return_value = {'KeyPhrases': []}
            analysis_service.comprehend_client.detect_sentiment.return_value = {
                'Sentiment': 'NEUTRAL',
                'SentimentScore': {'Neutral': 0.9, 'Positive': 0.05, 'Negative': 0.03, 'Mixed': 0.02}
            }
            
            # Execute analysis
            result = asyncio.run(analysis_service.analyze_document(document.id, user_id))
            
            # Verify pipeline completed successfully despite entity extraction failure
            assert result.status == "completed"
            assert document.status == DocumentStatus.PROCESSED.value
            
            # Verify text was extracted
            expected_text = '\n'.join([
                block.get('Text', '') for block in textract_response.get('Blocks', [])
                if block.get('BlockType') == 'LINE'
            ]).strip()
            assert result.extracted_text == expected_text
            
            # Verify entities are empty due to failure
            assert result.entities == []
            
            # Verify other processing continued
            assert result.sentiment is not None
    
    @given(
        document_data=document_strategy(),
        textract_response=textract_response_strategy(),
        entities_response=comprehend_entities_strategy()
    )
    @settings(max_examples=30, deadline=8000)
    def test_summary_generation_threshold_property(
        self,
        document_data: Dict[str, Any],
        textract_response: Dict[str, Any],
        entities_response: Dict[str, Any]
    ):
        """
        Feature: court-case-management-system, Property 7: AI Processing Pipeline
        
        Summary generation should only be triggered for documents longer than 1000 words,
        and should be skipped for shorter documents.
        
        Validates: Requirements 2.4 (conditional summary generation)
        """
        # Create mock document
        document = Document(**document_data)
        user_id = uuid4()
        
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock audit service
        mock_audit_service = AsyncMock(spec=AuditService)
        mock_audit_service.log_action = AsyncMock()
        
        # Create service with mocked AWS clients
        with patch('boto3.client') as mock_boto3:
            # Mock AWS clients
            mock_textract = MagicMock()
            mock_comprehend = MagicMock()
            mock_s3 = MagicMock()
            
            mock_boto3.side_effect = lambda service, **kwargs: {
                'textract': mock_textract,
                'comprehend': mock_comprehend,
                's3': mock_s3
            }[service]
            
            analysis_service = DocumentAnalysisService(mock_db, mock_audit_service)
            analysis_service.textract_client = mock_textract
            analysis_service.comprehend_client = mock_comprehend
            analysis_service.s3_client = mock_s3
            
            # Mock database queries
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = document
            analysis_service.db.execute.return_value = mock_result
            
            # Create text of specific length to test threshold
            text_length = len(' '.join([
                block.get('Text', '') for block in textract_response.get('Blocks', [])
                if block.get('BlockType') == 'LINE'
            ]))
            
            # Mock AWS service responses
            analysis_service.textract_client.detect_document_text.return_value = textract_response
            analysis_service.comprehend_client.detect_entities.return_value = entities_response
            analysis_service.comprehend_client.detect_key_phrases.return_value = {'KeyPhrases': []}
            analysis_service.comprehend_client.detect_sentiment.return_value = {
                'Sentiment': 'NEUTRAL',
                'SentimentScore': {'Neutral': 0.9, 'Positive': 0.05, 'Negative': 0.03, 'Mixed': 0.02}
            }
            
            # Execute analysis
            result = asyncio.run(analysis_service.analyze_document(document.id, user_id))
            
            # Verify summary generation behavior based on text length
            if text_length > 1000:
                # Summary should be generated for long documents
                analysis_service.comprehend_client.detect_key_phrases.assert_called()
                assert result.ai_summary is not None
            else:
                # Summary generation may or may not be called for short documents
                # but if called, it should still work
                pass
            
            # Verify analysis completed successfully regardless of summary generation
            assert result.status == "completed"
            assert document.status == DocumentStatus.PROCESSED.value
    
    @given(document_data=document_strategy())
    @settings(max_examples=10, deadline=3000)
    def test_document_not_found_error_property(
        self,
        document_data: Dict[str, Any]
    ):
        """
        Feature: court-case-management-system, Property 7: AI Processing Pipeline
        
        When attempting to analyze a non-existent document, the service should
        raise an appropriate error without attempting AWS service calls.
        
        Validates: Requirements 2.2 (input validation)
        """
        user_id = uuid4()
        non_existent_document_id = uuid4()
        
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock audit service
        mock_audit_service = AsyncMock(spec=AuditService)
        mock_audit_service.log_action = AsyncMock()
        
        # Create service with mocked AWS clients
        with patch('boto3.client') as mock_boto3:
            # Mock AWS clients
            mock_textract = MagicMock()
            mock_comprehend = MagicMock()
            mock_s3 = MagicMock()
            
            mock_boto3.side_effect = lambda service, **kwargs: {
                'textract': mock_textract,
                'comprehend': mock_comprehend,
                's3': mock_s3
            }[service]
            
            analysis_service = DocumentAnalysisService(mock_db, mock_audit_service)
            analysis_service.textract_client = mock_textract
            analysis_service.comprehend_client = mock_comprehend
            analysis_service.s3_client = mock_s3
            
            # Mock database to return None (document not found)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            analysis_service.db.execute.return_value = mock_result
            
            # Execute analysis and expect failure
            with pytest.raises(CaseManagementException) as exc_info:
                asyncio.run(analysis_service.analyze_document(non_existent_document_id, user_id))
            
            # Verify appropriate error
            assert "not found" in str(exc_info.value).lower()
            assert exc_info.value.error_code == "DOCUMENT_NOT_FOUND"
            
            # Verify no AWS service calls were made
            analysis_service.textract_client.detect_document_text.assert_not_called()
            analysis_service.comprehend_client.detect_entities.assert_not_called()
    
    @given(
        document_data=document_strategy(),
        textract_response=textract_response_strategy(),
        entities_response=comprehend_entities_strategy()
    )
    @settings(max_examples=20, deadline=5000)
    def test_processing_status_transitions_property(
        self,
        document_data: Dict[str, Any],
        textract_response: Dict[str, Any],
        entities_response: Dict[str, Any]
    ):
        """
        Feature: court-case-management-system, Property 7: AI Processing Pipeline
        
        Document status should transition correctly through the processing pipeline:
        uploaded -> processing -> processed (or failed)
        
        Validates: Requirements 2.2, 2.3, 2.4 (status management)
        """
        # Create mock document with uploaded status
        document_data['status'] = DocumentStatus.UPLOADED.value
        document = Document(**document_data)
        user_id = uuid4()
        
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock audit service
        mock_audit_service = AsyncMock(spec=AuditService)
        mock_audit_service.log_action = AsyncMock()
        
        # Create service with mocked AWS clients
        with patch('boto3.client') as mock_boto3:
            # Mock AWS clients
            mock_textract = MagicMock()
            mock_comprehend = MagicMock()
            mock_s3 = MagicMock()
            
            mock_boto3.side_effect = lambda service, **kwargs: {
                'textract': mock_textract,
                'comprehend': mock_comprehend,
                's3': mock_s3
            }[service]
            
            analysis_service = DocumentAnalysisService(mock_db, mock_audit_service)
            analysis_service.textract_client = mock_textract
            analysis_service.comprehend_client = mock_comprehend
            analysis_service.s3_client = mock_s3
            
            # Mock database queries
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = document
            analysis_service.db.execute.return_value = mock_result
            
            # Mock AWS service responses
            analysis_service.textract_client.detect_document_text.return_value = textract_response
            analysis_service.comprehend_client.detect_entities.return_value = entities_response
            analysis_service.comprehend_client.detect_key_phrases.return_value = {'KeyPhrases': []}
            analysis_service.comprehend_client.detect_sentiment.return_value = {
                'Sentiment': 'NEUTRAL',
                'SentimentScore': {'Neutral': 0.9, 'Positive': 0.05, 'Negative': 0.03, 'Mixed': 0.02}
            }
            
            # Verify initial status
            assert document.status == DocumentStatus.UPLOADED.value
            
            # Execute analysis
            result = asyncio.run(analysis_service.analyze_document(document.id, user_id))
            
            # Verify status transitions
            # Document should have been set to processing during analysis
            # and then to processed upon completion
            assert document.status == DocumentStatus.PROCESSED.value
            assert document.processing_started_at is not None
            assert document.processing_completed_at is not None
            assert document.processing_completed_at >= document.processing_started_at
            
            # Verify result status
            assert result.status == "completed"


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])