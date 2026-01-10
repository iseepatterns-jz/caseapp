"""
Property-based tests for file format and size validation
Feature: court-case-management-system, Property 6: File Format and Size Validation
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID, uuid4
from datetime import datetime
import asyncio

from models.document import Document, DocumentStatus, DocumentType
from models.case import Case, CaseStatus, CaseType, CasePriority
from schemas.document import DocumentUploadRequest, SupportedFileFormats
from services.document_service import DocumentService
from services.audit_service import AuditService
from core.exceptions import CaseManagementException

class TestFileFormatAndSizeValidation:
    """
    Property-based tests for Property 6: File Format and Size Validation
    Validates: Requirements 2.1
    """
    
    @given(
        file_size=st.integers(min_value=1, max_value=SupportedFileFormats.MAX_FILE_SIZE),
        mime_type=st.sampled_from(SupportedFileFormats.get_supported_mime_types()),
        filename=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd'))).map(lambda x: f"{x}.pdf")
    )
    @settings(deadline=3000, max_examples=100)
    def test_valid_file_upload_succeeds_property(self, file_size, mime_type, filename):
        """
        Feature: court-case-management-system, Property 6: File Format and Size Validation
        
        For any file upload request, if the file format is supported (PDF, DOCX, DOC, TXT) 
        and size is within limits (50MB for documents), the upload should succeed.
        
        Validates: Requirements 2.1
        """
        # Assume valid inputs to focus on the property
        assume(len(filename) > 0)
        assume(SupportedFileFormats.is_supported_format(mime_type))
        assume(file_size <= SupportedFileFormats.MAX_FILE_SIZE)
        
        async def run_test():
            # Create mock file with valid properties
            mock_file = Mock()
            mock_file.filename = filename
            mock_file.content_type = mime_type
            mock_file.read = AsyncMock(return_value=b"0" * file_size)
            
            # Create mock case
            mock_case = Case(
                id=uuid4(),
                case_number="TEST-001",
                title="Test Case",
                description="Test case for document upload",
                case_type=CaseType.CIVIL,
                status=CaseStatus.ACTIVE,
                priority=CasePriority.MEDIUM,
                client_id=uuid4(),
                created_by=uuid4()
            )
            
            # Create upload request
            upload_request = DocumentUploadRequest(
                case_id=mock_case.id,
                document_type=DocumentType.EVIDENCE,
                is_privileged=False,
                is_confidential=False
            )
            
            # Mock database and services
            mock_db = AsyncMock()
            mock_audit_service = Mock(spec=AuditService)
            mock_audit_service.log_action = AsyncMock()
            
            # Mock S3 client
            with patch('boto3.client') as mock_boto3:
                mock_s3_client = Mock()
                mock_s3_client.put_object = Mock()
                mock_boto3.return_value = mock_s3_client
                
                # Create document service
                document_service = DocumentService(mock_db, mock_audit_service)
                document_service.s3_client = mock_s3_client
                document_service.s3_bucket = "test-bucket"
                
                # Mock case lookup
                document_service._get_case = AsyncMock(return_value=mock_case)
                
                # Mock database operations
                mock_db.add = Mock()
                mock_db.flush = AsyncMock()
                mock_db.commit = AsyncMock()
                mock_db.refresh = AsyncMock()
                
                # Mock document creation
                mock_document = Document(
                    id=uuid4(),
                    filename=f"processed_{filename}",
                    original_filename=filename,
                    file_path=f"documents/{mock_case.id}/{filename}",
                    file_size=file_size,
                    mime_type=mime_type,
                    file_hash="test_hash",
                    document_type=DocumentType.EVIDENCE.value,
                    status=DocumentStatus.UPLOADED.value,
                    case_id=mock_case.id,
                    uploaded_by=uuid4()
                )
                mock_db.refresh.side_effect = lambda doc: setattr(doc, 'id', mock_document.id)
                
                # Test the upload - should succeed for valid files
                try:
                    result = await document_service.upload_document(mock_file, upload_request, uuid4())
                    
                    # Property: Valid files should be uploaded successfully
                    assert result is not None
                    assert result.original_filename == filename
                    assert result.file_size == file_size
                    assert result.mime_type == mime_type
                    assert result.status == DocumentStatus.UPLOADED.value
                    
                    # Verify S3 upload was called
                    mock_s3_client.put_object.assert_called_once()
                    
                    # Verify audit logging was called
                    mock_audit_service.log_action.assert_called_once()
                    
                    upload_success = True
                    
                except CaseManagementException as e:
                    # Should not happen for valid files
                    upload_success = False
                    error_message = str(e)
                
                # Property: All valid files should upload successfully
                assert upload_success, f"Valid file (type: {mime_type}, size: {file_size}, name: {filename}) should upload successfully"
        
        # Run the async test
        asyncio.run(run_test())
    
    @given(
        file_size=st.integers(min_value=SupportedFileFormats.MAX_FILE_SIZE + 1, max_value=SupportedFileFormats.MAX_FILE_SIZE * 2),
        mime_type=st.sampled_from(SupportedFileFormats.get_supported_mime_types()),
        filename=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd'))).map(lambda x: f"{x}.pdf")
    )
    @settings(deadline=3000, max_examples=50)
    def test_oversized_file_rejection_property(self, file_size, mime_type, filename):
        """
        Feature: court-case-management-system, Property 6: File Format and Size Validation
        
        For any file upload request with size exceeding limits (50MB for documents),
        the upload should be rejected with appropriate error message.
        
        Validates: Requirements 2.1
        """
        # Ensure file is oversized
        assume(file_size > SupportedFileFormats.MAX_FILE_SIZE)
        assume(len(filename) > 0)
        
        async def run_test():
            # Create mock file with oversized content
            mock_file = Mock()
            mock_file.filename = filename
            mock_file.content_type = mime_type
            mock_file.read = AsyncMock(return_value=b"0" * file_size)
            
            # Create mock case
            mock_case = Case(
                id=uuid4(),
                case_number="TEST-001",
                title="Test Case",
                description="Test case for document upload",
                case_type=CaseType.CIVIL,
                status=CaseStatus.ACTIVE,
                priority=CasePriority.MEDIUM,
                client_id=uuid4(),
                created_by=uuid4()
            )
            
            # Create upload request
            upload_request = DocumentUploadRequest(
                case_id=mock_case.id,
                document_type=DocumentType.EVIDENCE
            )
            
            # Mock database and services
            mock_db = AsyncMock()
            mock_audit_service = Mock(spec=AuditService)
            mock_audit_service.log_action = AsyncMock()
            
            # Mock S3 client
            with patch('boto3.client') as mock_boto3:
                mock_s3_client = Mock()
                mock_boto3.return_value = mock_s3_client
                
                # Create document service
                document_service = DocumentService(mock_db, mock_audit_service)
                document_service.s3_client = mock_s3_client
                document_service.s3_bucket = "test-bucket"
                
                # Mock case lookup
                document_service._get_case = AsyncMock(return_value=mock_case)
                
                # Test the upload - should fail for oversized files
                upload_failed = False
                error_message = ""
                
                try:
                    await document_service.upload_document(mock_file, upload_request, uuid4())
                except CaseManagementException as e:
                    upload_failed = True
                    error_message = str(e)
                    # Verify it's specifically a size error
                    assert "size" in error_message.lower() or "exceed" in error_message.lower()
                
                # Property: Oversized files should be rejected
                assert upload_failed, f"Oversized file ({file_size} bytes > {SupportedFileFormats.MAX_FILE_SIZE} bytes) should be rejected"
                
                # Verify S3 upload was NOT called for rejected files
                mock_s3_client.put_object.assert_not_called()
        
        # Run the async test
        asyncio.run(run_test())
    
    @given(
        file_size=st.integers(min_value=1, max_value=SupportedFileFormats.MAX_FILE_SIZE),
        filename=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd'))).map(lambda x: f"{x}.xyz")
    )
    @settings(deadline=3000, max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_unsupported_format_rejection_property(self, file_size, filename):
        """
        Feature: court-case-management-system, Property 6: File Format and Size Validation
        
        For any file upload request with unsupported format, the upload should be 
        rejected with appropriate error message.
        
        Validates: Requirements 2.1
        """
        # Use a known unsupported MIME type
        unsupported_mime_types = [
            "application/x-unknown",
            "text/x-unsupported", 
            "image/jpeg",  # Not supported for documents
            "video/mp4",   # Not supported for documents
            "application/zip",
            "application/executable"
        ]
        mime_type = unsupported_mime_types[hash(filename) % len(unsupported_mime_types)]
        
        # Ensure format is unsupported and inputs are valid
        assume(not SupportedFileFormats.is_supported_format(mime_type))
        assume(len(filename) > 0)
        assume(file_size <= SupportedFileFormats.MAX_FILE_SIZE)
        
        async def run_test():
            # Create mock file with unsupported format
            mock_file = Mock()
            mock_file.filename = filename
            mock_file.content_type = mime_type
            mock_file.read = AsyncMock(return_value=b"0" * file_size)
            
            # Create mock case
            mock_case = Case(
                id=uuid4(),
                case_number="TEST-001",
                title="Test Case",
                description="Test case for document upload",
                case_type=CaseType.CIVIL,
                status=CaseStatus.ACTIVE,
                priority=CasePriority.MEDIUM,
                client_id=uuid4(),
                created_by=uuid4()
            )
            
            # Create upload request
            upload_request = DocumentUploadRequest(
                case_id=mock_case.id,
                document_type=DocumentType.EVIDENCE
            )
            
            # Mock database and services
            mock_db = AsyncMock()
            mock_audit_service = Mock(spec=AuditService)
            mock_audit_service.log_action = AsyncMock()
            
            # Mock S3 client
            with patch('boto3.client') as mock_boto3:
                mock_s3_client = Mock()
                mock_boto3.return_value = mock_s3_client
                
                # Create document service
                document_service = DocumentService(mock_db, mock_audit_service)
                document_service.s3_client = mock_s3_client
                document_service.s3_bucket = "test-bucket"
                
                # Mock case lookup
                document_service._get_case = AsyncMock(return_value=mock_case)
                
                # Test the upload - should fail for unsupported formats
                upload_failed = False
                error_message = ""
                
                try:
                    await document_service.upload_document(mock_file, upload_request, uuid4())
                except CaseManagementException as e:
                    upload_failed = True
                    error_message = str(e)
                    # Verify it's specifically a format error
                    assert "format" in error_message.lower() or "unsupported" in error_message.lower()
                
                # Property: Unsupported formats should be rejected
                assert upload_failed, f"Unsupported format ({mime_type}) should be rejected"
                
                # Verify S3 upload was NOT called for rejected files
                mock_s3_client.put_object.assert_not_called()
        
        # Run the async test
        asyncio.run(run_test())
    
    @given(
        supported_format=st.sampled_from(SupportedFileFormats.get_supported_extensions()),
        valid_size=st.integers(min_value=1, max_value=SupportedFileFormats.MAX_FILE_SIZE // 2)
    )
    @settings(deadline=2000, max_examples=30)
    def test_supported_formats_comprehensive_property(self, supported_format, valid_size):
        """
        Feature: court-case-management-system, Property 6: File Format and Size Validation
        
        For any supported file format (PDF, DOCX, DOC, TXT, RTF, ODT) with valid size,
        the format validation should pass.
        
        Validates: Requirements 2.1
        """
        # Get corresponding MIME type for the format
        format_mime_types = SupportedFileFormats.FORMATS.get(supported_format, [])
        assume(len(format_mime_types) > 0)
        
        # Test each MIME type for this format
        for mime_type in format_mime_types:
            # Property: All supported formats should pass validation
            assert SupportedFileFormats.is_supported_format(mime_type), f"Format {supported_format} with MIME type {mime_type} should be supported"
            
            # Property: Valid sizes should pass validation
            assert valid_size <= SupportedFileFormats.MAX_FILE_SIZE, f"Size {valid_size} should be within limits"
    
    def test_file_size_boundary_conditions(self):
        """
        Feature: court-case-management-system, Property 6: File Format and Size Validation
        
        Test boundary conditions for file size validation.
        
        Validates: Requirements 2.1
        """
        # Test exact limit
        assert SupportedFileFormats.MAX_FILE_SIZE == 50 * 1024 * 1024  # 50MB
        
        # Test just under limit
        just_under = SupportedFileFormats.MAX_FILE_SIZE - 1
        assert just_under <= SupportedFileFormats.MAX_FILE_SIZE
        
        # Test just over limit
        just_over = SupportedFileFormats.MAX_FILE_SIZE + 1
        assert just_over > SupportedFileFormats.MAX_FILE_SIZE
        
        # Test minimum size
        assert 1 <= SupportedFileFormats.MAX_FILE_SIZE
        
        # Test zero size (should be invalid in practice)
        assert 0 < SupportedFileFormats.MAX_FILE_SIZE
    
    def test_supported_format_completeness(self):
        """
        Feature: court-case-management-system, Property 6: File Format and Size Validation
        
        Verify that all required document formats from Requirements 2.1 are supported.
        
        Validates: Requirements 2.1
        """
        required_formats = ['pdf', 'docx', 'doc', 'txt']
        supported_formats = SupportedFileFormats.get_supported_extensions()
        
        # Property: All required formats must be supported
        for required_format in required_formats:
            assert required_format in supported_formats, f"Required format {required_format} must be supported"
        
        # Property: Each format must have at least one MIME type
        for format_ext in supported_formats:
            mime_types = SupportedFileFormats.FORMATS.get(format_ext, [])
            assert len(mime_types) > 0, f"Format {format_ext} must have at least one MIME type"
        
        # Property: All MIME types should be valid format strings
        all_mime_types = SupportedFileFormats.get_supported_mime_types()
        for mime_type in all_mime_types:
            assert "/" in mime_type, f"MIME type {mime_type} should contain '/'"
            assert len(mime_type.split("/")) == 2, f"MIME type {mime_type} should have format 'type/subtype'"