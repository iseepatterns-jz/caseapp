"""
Document management service with S3 integration and AI analysis
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, String
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any, Tuple, BinaryIO
from uuid import UUID
from datetime import datetime
import hashlib
import os
import uuid
import structlog
from fastapi import UploadFile
import boto3
from botocore.exceptions import ClientError

from models.document import Document, DocumentStatus, DocumentType, ExtractedEntity, DocumentVersion
from models.case import Case
from schemas.document import (
    DocumentUploadRequest, DocumentUpdateRequest, DocumentSearchRequest,
    DocumentResponse, DocumentListResponse, DocumentAnalysisResponse,
    FileUploadResponse, SupportedFileFormats
)
from core.exceptions import CaseManagementException
from core.config import get_settings
from services.audit_service import AuditService

logger = structlog.get_logger()
settings = get_settings()

class DocumentService:
    """Service for document management with S3 storage and AI analysis"""
    
    def __init__(self, db: AsyncSession, audit_service: AuditService):
        self.db = db
        self.audit_service = audit_service
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.s3_bucket = settings.S3_BUCKET_NAME
    
    async def upload_document(
        self, 
        file: UploadFile, 
        upload_request: DocumentUploadRequest, 
        uploaded_by: UUID
    ) -> Document:
        """
        Upload a document with validation, S3 storage, and audit logging
        
        Args:
            file: Uploaded file object
            upload_request: Document upload metadata
            uploaded_by: UUID of the user uploading the document
            
        Returns:
            Created document instance
            
        Raises:
            CaseManagementException: If validation fails or upload errors occur
        """
        try:
            # Validate file format
            if not SupportedFileFormats.is_supported_format(file.content_type):
                raise CaseManagementException(
                    f"Unsupported file format: {file.content_type}. "
                    f"Supported formats: {', '.join(SupportedFileFormats.get_supported_extensions())}",
                    error_code="UNSUPPORTED_FILE_FORMAT"
                )
            
            # Validate file size
            file_content = await file.read()
            file_size = len(file_content)
            
            if file_size > SupportedFileFormats.MAX_FILE_SIZE:
                raise CaseManagementException(
                    f"File size ({file_size} bytes) exceeds maximum allowed size "
                    f"({SupportedFileFormats.MAX_FILE_SIZE} bytes)",
                    error_code="FILE_SIZE_EXCEEDED"
                )
            
            # Validate case exists
            case = await self._get_case(upload_request.case_id)
            if not case:
                raise CaseManagementException(
                    f"Case with ID {upload_request.case_id} not found",
                    error_code="CASE_NOT_FOUND"
                )
            
            # Generate file hash for integrity
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # Generate unique filename for S3
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}/{file_hash[:8]}{file_extension}"
            s3_key = f"documents/{upload_request.case_id}/{unique_filename}"
            
            # Upload to S3
            try:
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=file_content,
                    ContentType=file.content_type,
                    Metadata={
                        'original_filename': file.filename,
                        'uploaded_by': str(uploaded_by),
                        'case_id': str(upload_request.case_id),
                        'upload_timestamp': datetime.utcnow().isoformat()
                    }
                )
                logger.info("File uploaded to S3", s3_key=s3_key, file_size=file_size)
            except ClientError as e:
                logger.error("Failed to upload file to S3", error=str(e), s3_key=s3_key)
                raise CaseManagementException(f"Failed to upload file to storage: {str(e)}")
            
            # Create document record
            document = Document(
                filename=unique_filename,
                original_filename=file.filename,
                file_path=s3_key,
                file_size=file_size,
                mime_type=file.content_type,
                file_hash=file_hash,
                document_type=upload_request.document_type.value if upload_request.document_type else DocumentType.OTHER.value,
                status=DocumentStatus.UPLOADED.value,
                case_id=upload_request.case_id,
                is_privileged=upload_request.is_privileged or False,
                is_confidential=upload_request.is_confidential or False,
                access_level=upload_request.access_level.value if upload_request.access_level else "standard",
                retention_date=upload_request.retention_date,
                document_metadata=upload_request.document_metadata or {},
                uploaded_by=uploaded_by
            )
            
            self.db.add(document)
            await self.db.flush()  # Get the ID without committing
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="document",
                entity_id=document.id,
                action="upload",
                user_id=uploaded_by,
                case_id=upload_request.case_id,
                new_value=f"Uploaded file: {file.filename} ({file_size} bytes)"
            )
            
            await self.db.commit()
            await self.db.refresh(document)
            
            # Automatically trigger AI analysis for supported formats
            if settings.ENABLE_AI_FEATURES and SupportedFileFormats.is_supported_format(file.content_type):
                try:
                    # Import here to avoid circular imports
                    from services.document_analysis_service import DocumentAnalysisService
                    analysis_service = DocumentAnalysisService(self.db, self.audit_service)
                    
                    # Start analysis in background (don't wait for completion)
                    await analysis_service.analyze_document(document.id, uploaded_by)
                except Exception as analysis_error:
                    # Log analysis error but don't fail the upload
                    logger.warning(
                        "Failed to start automatic document analysis",
                        document_id=str(document.id),
                        error=str(analysis_error)
                    )
            
            logger.info(
                "Document uploaded successfully",
                document_id=str(document.id),
                filename=file.filename,
                case_id=str(upload_request.case_id)
            )
            
            return document
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to upload document", error=str(e))
            raise CaseManagementException(f"Failed to upload document: {str(e)}")
    
    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """
        Get a document by ID with related data
        
        Args:
            document_id: Document UUID
            
        Returns:
            Document instance or None if not found
        """
        try:
            result = await self.db.execute(
                select(Document)
                .options(
                    selectinload(Document.case),
                    selectinload(Document.uploader),
                    selectinload(Document.updater)
                )
                .where(Document.id == document_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get document", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to retrieve document: {str(e)}")
    
    async def update_document(
        self, 
        document_id: UUID, 
        update_request: DocumentUpdateRequest, 
        updated_by: UUID
    ) -> Document:
        """
        Update document metadata with audit logging
        
        Args:
            document_id: Document UUID
            update_request: Update data
            updated_by: UUID of the user updating the document
            
        Returns:
            Updated document instance
            
        Raises:
            CaseManagementException: If document not found or validation fails
        """
        try:
            document = await self.get_document(document_id)
            if not document:
                raise CaseManagementException(
                    f"Document with ID {document_id} not found",
                    error_code="DOCUMENT_NOT_FOUND"
                )
            
            # Store original values for audit
            original_values = {}
            
            # Update fields that are provided
            update_data = update_request.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(document, field):
                    original_values[field] = getattr(document, field)
                    if field.endswith('_level') or field.endswith('_type'):
                        # Handle enum fields
                        setattr(document, field, value.value if hasattr(value, 'value') else value)
                    else:
                        setattr(document, field, value)
            
            document.updated_by = updated_by
            document.updated_at = datetime.utcnow()
            
            # Create audit logs for each changed field
            for field, new_value in update_data.items():
                if field in original_values:
                    await self.audit_service.log_action(
                        entity_type="document",
                        entity_id=document.id,
                        action="update",
                        field_name=field,
                        old_value=str(original_values[field]) if original_values[field] is not None else None,
                        new_value=str(new_value) if new_value is not None else None,
                        user_id=updated_by,
                        case_id=document.case_id
                    )
            
            await self.db.commit()
            await self.db.refresh(document)
            
            logger.info("Document updated successfully", document_id=str(document.id))
            return document
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to update document", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to update document: {str(e)}")
    
    async def delete_document(self, document_id: UUID, deleted_by: UUID) -> bool:
        """
        Soft delete a document (mark as archived)
        
        Args:
            document_id: Document UUID
            deleted_by: UUID of the user deleting the document
            
        Returns:
            True if successful
            
        Raises:
            CaseManagementException: If document not found
        """
        try:
            document = await self.get_document(document_id)
            if not document:
                raise CaseManagementException(
                    f"Document with ID {document_id} not found",
                    error_code="DOCUMENT_NOT_FOUND"
                )
            
            old_status = document.status
            document.status = DocumentStatus.ARCHIVED.value
            document.updated_by = deleted_by
            document.updated_at = datetime.utcnow()
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="document",
                entity_id=document.id,
                action="delete",
                field_name="status",
                old_value=old_status,
                new_value=DocumentStatus.ARCHIVED.value,
                user_id=deleted_by,
                case_id=document.case_id
            )
            
            await self.db.commit()
            
            logger.info("Document deleted (archived)", document_id=str(document.id))
            return True
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to delete document", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to delete document: {str(e)}")
    
    async def get_document_download_url(self, document_id: UUID, user_id: UUID, expires_in: int = 3600) -> str:
        """
        Generate a pre-signed URL for document download
        
        Args:
            document_id: Document UUID
            user_id: UUID of the user requesting download
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Pre-signed download URL
            
        Raises:
            CaseManagementException: If document not found or access denied
        """
        try:
            document = await self.get_document(document_id)
            if not document:
                raise CaseManagementException(
                    f"Document with ID {document_id} not found",
                    error_code="DOCUMENT_NOT_FOUND"
                )
            
            # Generate pre-signed URL
            try:
                download_url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.s3_bucket, 'Key': document.file_path},
                    ExpiresIn=expires_in
                )
                
                # Log document access
                await self.audit_service.log_action(
                    entity_type="document",
                    entity_id=document.id,
                    action="download_requested",
                    user_id=user_id,
                    case_id=document.case_id,
                    new_value=f"Download URL generated (expires in {expires_in}s)"
                )
                
                logger.info(
                    "Download URL generated",
                    document_id=str(document.id),
                    user_id=str(user_id),
                    expires_in=expires_in
                )
                
                return download_url
                
            except ClientError as e:
                logger.error("Failed to generate download URL", error=str(e))
                raise CaseManagementException(f"Failed to generate download URL: {str(e)}")
            
        except Exception as e:
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to get download URL", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to get download URL: {str(e)}")
    
    async def search_documents(self, search_request: DocumentSearchRequest) -> Tuple[List[Document], int]:
        """
        Search documents with filtering, pagination, and full-text search using PostgreSQL
        
        Args:
            search_request: Search parameters
            
        Returns:
            Tuple of (documents list, total count)
        """
        try:
            # Build base query
            query = select(Document).options(
                selectinload(Document.case),
                selectinload(Document.uploader)
            )
            
            # Apply filters
            filters = []
            
            if search_request.query:
                # Enhanced full-text search using PostgreSQL features
                search_term = search_request.query.strip()
                
                # Create search filters for different fields
                search_filters = []
                
                # Basic ILIKE search for filenames (always included)
                filename_search = f"%{search_term}%"
                search_filters.extend([
                    Document.original_filename.ilike(filename_search),
                    Document.filename.ilike(filename_search)
                ])
                
                # Full-text search on extracted content if requested
                if search_request.include_content and search_term:
                    # Use PostgreSQL's full-text search capabilities
                    content_filters = []
                    if len(search_term) > 2:  # Only for meaningful search terms
                        content_filters.append(Document.extracted_text.ilike(f"%{search_term}%"))
                        
                        # Search in entities JSON field
                        content_filters.append(
                            func.cast(Document.entities, String).ilike(f"%{search_term}%")
                        )
                        
                        # Search in keywords JSON field
                        content_filters.append(
                            func.cast(Document.keywords, String).ilike(f"%{search_term}%")
                        )
                    
                    if content_filters:
                        search_filters.extend(content_filters)
                
                # Search in AI-generated metadata if requested
                if search_request.include_metadata and search_term:
                    metadata_filters = []
                    if len(search_term) > 2:
                        metadata_filters.append(Document.ai_summary.ilike(f"%{search_term}%"))
                        
                        # Search in document metadata JSON field
                        metadata_filters.append(
                            func.cast(Document.document_metadata, String).ilike(f"%{search_term}%")
                        )
                    
                    if metadata_filters:
                        search_filters.extend(metadata_filters)
                
                if search_filters:
                    filters.append(or_(*search_filters))
            
            # Apply additional filters
            if search_request.case_id:
                filters.append(Document.case_id == search_request.case_id)
            
            if search_request.document_type:
                filters.append(Document.document_type == search_request.document_type.value)
            
            if search_request.status:
                filters.append(Document.status == search_request.status.value)
            
            if search_request.start_date:
                filters.append(Document.upload_date >= search_request.start_date)
            
            if search_request.end_date:
                filters.append(Document.upload_date <= search_request.end_date)
            
            # Only show current versions by default (not archived)
            filters.append(Document.status != DocumentStatus.ARCHIVED.value)
            
            if filters:
                query = query.where(and_(*filters))
            
            # Get total count
            count_query = select(func.count(Document.id))
            if filters:
                count_query = count_query.where(and_(*filters))
            
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()
            
            # Apply relevance-based sorting if there's a search query, otherwise sort by date
            if search_request.query and search_request.query.strip():
                # For text search, we could implement relevance scoring
                # For now, we'll sort by a combination of factors
                query = query.order_by(
                    Document.updated_at.desc().nullslast(),
                    Document.upload_date.desc()
                )
            else:
                query = query.order_by(Document.upload_date.desc())
            
            # Apply pagination
            query = query.offset(search_request.offset).limit(search_request.limit)
            
            # Execute query
            result = await self.db.execute(query)
            documents = result.scalars().all()
            
            logger.info(
                "Document search completed",
                query=search_request.query,
                total_results=total,
                returned_results=len(documents)
            )
            
            return list(documents), total
            
        except Exception as e:
            logger.error("Failed to search documents", error=str(e))
            raise CaseManagementException(f"Failed to search documents: {str(e)}")
    
    async def get_case_documents(self, case_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Document], int]:
        """
        Get all documents for a specific case
        
        Args:
            case_id: Case UUID
            limit: Maximum number of documents to return
            offset: Number of documents to skip
            
        Returns:
            Tuple of (documents list, total count)
        """
        try:
            # Get total count
            count_result = await self.db.execute(
                select(func.count(Document.id))
                .where(Document.case_id == case_id)
                .where(Document.status != DocumentStatus.ARCHIVED.value)
            )
            total = count_result.scalar()
            
            # Get documents
            result = await self.db.execute(
                select(Document)
                .options(selectinload(Document.uploader))
                .where(Document.case_id == case_id)
                .where(Document.status != DocumentStatus.ARCHIVED.value)
                .order_by(Document.upload_date.desc())
                .offset(offset)
                .limit(limit)
            )
            documents = result.scalars().all()
            
            return list(documents), total
            
        except Exception as e:
            logger.error("Failed to get case documents", case_id=str(case_id), error=str(e))
            raise CaseManagementException(f"Failed to get case documents: {str(e)}")
    
    async def get_document_statistics(self, case_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Get document statistics for dashboard
        
        Args:
            case_id: Optional case ID to filter statistics
            
        Returns:
            Dictionary with document statistics
        """
        try:
            base_query = select(func.count(Document.id))
            if case_id:
                base_query = base_query.where(Document.case_id == case_id)
            
            # Total documents
            total_result = await self.db.execute(base_query)
            total_documents = total_result.scalar()
            
            # Documents by status
            status_query = select(Document.status, func.count(Document.id)).group_by(Document.status)
            if case_id:
                status_query = status_query.where(Document.case_id == case_id)
            
            status_result = await self.db.execute(status_query)
            status_counts = {status: count for status, count in status_result.all()}
            
            # Documents by type
            type_query = select(Document.document_type, func.count(Document.id)).group_by(Document.document_type)
            if case_id:
                type_query = type_query.where(Document.case_id == case_id)
            
            type_result = await self.db.execute(type_query)
            type_counts = {doc_type: count for doc_type, count in type_result.all()}
            
            # Total file size
            size_query = select(func.sum(Document.file_size))
            if case_id:
                size_query = size_query.where(Document.case_id == case_id)
            
            size_result = await self.db.execute(size_query)
            total_size = size_result.scalar() or 0
            
            return {
                "total_documents": total_documents,
                "by_status": status_counts,
                "by_type": type_counts,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "case_id": str(case_id) if case_id else None,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get document statistics", error=str(e))
            raise CaseManagementException(f"Failed to get document statistics: {str(e)}")
    
    async def analyze_document(self, document_id: UUID, user_id: UUID) -> DocumentAnalysisResponse:
        """
        Trigger AI analysis for a document
        
        Args:
            document_id: Document UUID to analyze
            user_id: UUID of the user requesting analysis
            
        Returns:
            DocumentAnalysisResponse with analysis results
        """
        # Import here to avoid circular imports
        from services.document_analysis_service import DocumentAnalysisService
        analysis_service = DocumentAnalysisService(self.db, self.audit_service)
        return await analysis_service.analyze_document(document_id, user_id)
    
    async def get_analysis_status(self, document_id: UUID) -> Dict[str, Any]:
        """
        Get the current analysis status of a document
        
        Args:
            document_id: Document UUID
            
        Returns:
            Analysis status information
        """
        # Import here to avoid circular imports
        from services.document_analysis_service import DocumentAnalysisService
        analysis_service = DocumentAnalysisService(self.db, self.audit_service)
        return await analysis_service.get_analysis_status(document_id)
    
    async def create_document_version(
        self, 
        document_id: UUID, 
        change_description: str, 
        change_type: str, 
        created_by: UUID
    ) -> DocumentVersion:
        """
        Create a new version of a document for change tracking
        
        Args:
            document_id: Document UUID
            change_description: Description of the changes made
            change_type: Type of change (content_update, metadata_update, reprocessing)
            created_by: UUID of the user creating the version
            
        Returns:
            Created DocumentVersion instance
            
        Raises:
            CaseManagementException: If document not found
        """
        try:
            document = await self.get_document(document_id)
            if not document:
                raise CaseManagementException(
                    f"Document with ID {document_id} not found",
                    error_code="DOCUMENT_NOT_FOUND"
                )
            
            # Get the next version number
            version_count_result = await self.db.execute(
                select(func.count(DocumentVersion.id))
                .where(DocumentVersion.document_id == document_id)
            )
            next_version = version_count_result.scalar() + 1
            
            # Create version snapshot
            document_version = DocumentVersion(
                document_id=document_id,
                version_number=next_version,
                change_description=change_description,
                change_type=change_type,
                filename_snapshot=document.filename,
                file_path_snapshot=document.file_path,
                file_size_snapshot=document.file_size,
                extracted_text_snapshot=document.extracted_text,
                ai_summary_snapshot=document.ai_summary,
                entities_snapshot=document.entities,
                created_by=created_by
            )
            
            self.db.add(document_version)
            
            # Update document version number
            document.version = next_version
            document.updated_by = created_by
            document.updated_at = datetime.utcnow()
            
            # Create audit log
            await self.audit_service.log_action(
                entity_type="document",
                entity_id=document.id,
                action="version_created",
                field_name="version",
                old_value=str(next_version - 1),
                new_value=str(next_version),
                user_id=created_by,
                case_id=document.case_id,
                additional_data={
                    "change_description": change_description,
                    "change_type": change_type
                }
            )
            
            await self.db.commit()
            await self.db.refresh(document_version)
            
            logger.info(
                "Document version created",
                document_id=str(document_id),
                version_number=next_version,
                change_type=change_type
            )
            
            return document_version
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to create document version", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to create document version: {str(e)}")
    
    async def get_document_versions(self, document_id: UUID) -> List[DocumentVersion]:
        """
        Get all versions of a document
        
        Args:
            document_id: Document UUID
            
        Returns:
            List of DocumentVersion instances ordered by version number
        """
        try:
            result = await self.db.execute(
                select(DocumentVersion)
                .options(selectinload(DocumentVersion.creator))
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.version_number.desc())
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to get document versions", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to get document versions: {str(e)}")
    
    async def rollback_document_to_version(
        self, 
        document_id: UUID, 
        target_version: int, 
        rolled_back_by: UUID
    ) -> Document:
        """
        Rollback a document to a previous version
        
        Args:
            document_id: Document UUID
            target_version: Version number to rollback to
            rolled_back_by: UUID of the user performing the rollback
            
        Returns:
            Updated document instance
            
        Raises:
            CaseManagementException: If document or version not found
        """
        try:
            document = await self.get_document(document_id)
            if not document:
                raise CaseManagementException(
                    f"Document with ID {document_id} not found",
                    error_code="DOCUMENT_NOT_FOUND"
                )
            
            # Get the target version
            version_result = await self.db.execute(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .where(DocumentVersion.version_number == target_version)
            )
            target_version_obj = version_result.scalar_one_or_none()
            
            if not target_version_obj:
                raise CaseManagementException(
                    f"Version {target_version} not found for document {document_id}",
                    error_code="VERSION_NOT_FOUND"
                )
            
            # Store current state before rollback
            current_version = document.version
            
            # Create a new version entry for the rollback
            await self.create_document_version(
                document_id=document_id,
                change_description=f"Rollback to version {target_version}",
                change_type="rollback",
                created_by=rolled_back_by
            )
            
            # Restore document state from target version
            document.filename = target_version_obj.filename_snapshot
            document.file_path = target_version_obj.file_path_snapshot
            document.file_size = target_version_obj.file_size_snapshot
            document.extracted_text = target_version_obj.extracted_text_snapshot
            document.ai_summary = target_version_obj.ai_summary_snapshot
            document.entities = target_version_obj.entities_snapshot
            document.updated_by = rolled_back_by
            document.updated_at = datetime.utcnow()
            
            # Create audit log for rollback
            await self.audit_service.log_action(
                entity_type="document",
                entity_id=document.id,
                action="rollback",
                field_name="version",
                old_value=str(current_version),
                new_value=str(document.version),
                user_id=rolled_back_by,
                case_id=document.case_id,
                additional_data={
                    "target_version": target_version,
                    "rollback_description": f"Rolled back from version {current_version} to version {target_version}"
                }
            )
            
            await self.db.commit()
            await self.db.refresh(document)
            
            logger.info(
                "Document rolled back to previous version",
                document_id=str(document_id),
                from_version=current_version,
                to_version=target_version
            )
            
            return document
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to rollback document", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to rollback document: {str(e)}")
    
    async def compare_document_versions(
        self, 
        document_id: UUID, 
        version1: int, 
        version2: int
    ) -> Dict[str, Any]:
        """
        Compare two versions of a document
        
        Args:
            document_id: Document UUID
            version1: First version number
            version2: Second version number
            
        Returns:
            Dictionary with comparison results
        """
        try:
            # Get both versions
            versions_result = await self.db.execute(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .where(DocumentVersion.version_number.in_([version1, version2]))
            )
            versions = {v.version_number: v for v in versions_result.scalars().all()}
            
            if version1 not in versions:
                raise CaseManagementException(f"Version {version1} not found")
            if version2 not in versions:
                raise CaseManagementException(f"Version {version2} not found")
            
            v1 = versions[version1]
            v2 = versions[version2]
            
            # Compare fields
            comparison = {
                "document_id": str(document_id),
                "version1": version1,
                "version2": version2,
                "differences": {},
                "summary": {
                    "total_changes": 0,
                    "field_changes": []
                }
            }
            
            # Compare each field
            fields_to_compare = [
                ("filename", "filename_snapshot"),
                ("file_path", "file_path_snapshot"),
                ("file_size", "file_size_snapshot"),
                ("extracted_text", "extracted_text_snapshot"),
                ("ai_summary", "ai_summary_snapshot"),
                ("entities", "entities_snapshot")
            ]
            
            for field_name, snapshot_field in fields_to_compare:
                val1 = getattr(v1, snapshot_field)
                val2 = getattr(v2, snapshot_field)
                
                if val1 != val2:
                    comparison["differences"][field_name] = {
                        f"version_{version1}": val1,
                        f"version_{version2}": val2,
                        "changed": True
                    }
                    comparison["summary"]["field_changes"].append(field_name)
                    comparison["summary"]["total_changes"] += 1
                else:
                    comparison["differences"][field_name] = {
                        "value": val1,
                        "changed": False
                    }
            
            return comparison
            
        except Exception as e:
            logger.error("Failed to compare document versions", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to compare document versions: {str(e)}")
    
    async def _get_case(self, case_id: UUID) -> Optional[Case]:
        """Get case by ID for validation"""
        result = await self.db.execute(
            select(Case).where(Case.id == case_id)
        )
        return result.scalar_one_or_none()