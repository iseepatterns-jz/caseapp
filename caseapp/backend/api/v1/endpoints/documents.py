"""
Document management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import json
import structlog

from core.database import get_db
from core.auth import get_current_user
from models.user import User
from schemas.document import (
    DocumentUploadRequest, DocumentUpdateRequest, DocumentSearchRequest,
    DocumentResponse, DocumentListResponse, DocumentAnalysisResponse,
    FileUploadResponse, DocumentSummaryResponse, DocumentSearchResponse,
    SupportedFileFormats
)
from services.document_service import DocumentService
from services.audit_service import AuditService
from core.exceptions import CaseManagementException

logger = structlog.get_logger()
router = APIRouter()

def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    """Dependency to get document service"""
    audit_service = AuditService(db)
    return DocumentService(db, audit_service)

@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    case_id: str = Form(...),
    document_type: Optional[str] = Form(None),
    is_privileged: Optional[bool] = Form(False),
    is_confidential: Optional[bool] = Form(False),
    access_level: Optional[str] = Form("standard"),
    retention_date: Optional[str] = Form(None),
    document_metadata: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Upload a new document to a case
    
    - **file**: Document file to upload (PDF, DOCX, DOC, TXT up to 50MB)
    - **case_id**: UUID of the case this document belongs to
    - **document_type**: Type of document (optional)
    - **is_privileged**: Whether document is attorney-client privileged
    - **is_confidential**: Whether document contains confidential information
    - **access_level**: Access control level (public, standard, confidential, restricted)
    - **retention_date**: Date when document can be deleted (ISO format)
    - **document_metadata**: Additional metadata as JSON string
    """
    try:
        # Parse optional fields
        parsed_metadata = None
        if document_metadata:
            try:
                parsed_metadata = json.loads(document_metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format for document_metadata"
                )
        
        parsed_retention_date = None
        if retention_date:
            from datetime import datetime
            try:
                parsed_retention_date = datetime.fromisoformat(retention_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format for retention_date. Use ISO format."
                )
        
        # Create upload request
        upload_request = DocumentUploadRequest(
            case_id=UUID(case_id),
            document_type=document_type,
            is_privileged=is_privileged,
            is_confidential=is_confidential,
            access_level=access_level,
            retention_date=parsed_retention_date,
            document_metadata=parsed_metadata
        )
        
        # Upload document
        document = await document_service.upload_document(file, upload_request, current_user.id)
        
        return FileUploadResponse(
            document_id=document.id,
            filename=document.original_filename,
            file_size=document.file_size,
            mime_type=document.mime_type,
            status=document.status,
            message="Document uploaded successfully"
        )
        
    except CaseManagementException as e:
        logger.error("Document upload failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error during document upload", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get document details by ID
    
    - **document_id**: UUID of the document to retrieve
    """
    try:
        document = await document_service.get_document(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found"
            )
        
        return DocumentResponse.model_validate(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get document", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    update_request: DocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Update document metadata
    
    - **document_id**: UUID of the document to update
    - **update_request**: Document update data
    """
    try:
        document = await document_service.update_document(document_id, update_request, current_user.id)
        return DocumentResponse.model_validate(document)
        
    except CaseManagementException as e:
        logger.error("Document update failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to update document", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Delete (archive) a document
    
    - **document_id**: UUID of the document to delete
    """
    try:
        await document_service.delete_document(document_id, current_user.id)
        
    except CaseManagementException as e:
        logger.error("Document deletion failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete document", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    expires_in: int = Query(3600, ge=300, le=86400, description="URL expiration time in seconds"),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get a pre-signed download URL for a document
    
    - **document_id**: UUID of the document to download
    - **expires_in**: URL expiration time in seconds (5 minutes to 24 hours)
    """
    try:
        download_url = await document_service.get_document_download_url(
            document_id, current_user.id, expires_in
        )
        
        # Redirect to the pre-signed URL
        return RedirectResponse(url=download_url, status_code=status.HTTP_302_FOUND)
        
    except CaseManagementException as e:
        logger.error("Document download failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to generate download URL", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    search_request: DocumentSearchRequest,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Search documents with filtering and pagination
    
    - **search_request**: Search parameters including query, filters, and pagination
    """
    try:
        start_time = datetime.now(UTC)
        documents, total_count = await document_service.search_documents(search_request)
        end_time = datetime.now(UTC)
        
        search_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        document_summaries = [
            DocumentSummaryResponse.model_validate(doc) for doc in documents
        ]
        
        return DocumentSearchResponse(
            documents=document_summaries,
            total_count=total_count,
            query=search_request.query,
            search_time_ms=search_time_ms
        )
        
    except Exception as e:
        logger.error("Document search failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/case/{case_id}", response_model=DocumentListResponse)
async def get_case_documents(
    case_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of documents per page"),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get all documents for a specific case with pagination
    
    - **case_id**: UUID of the case
    - **page**: Page number (starts from 1)
    - **page_size**: Number of documents per page (1-100)
    """
    try:
        offset = (page - 1) * page_size
        documents, total_count = await document_service.get_case_documents(case_id, page_size, offset)
        
        document_responses = [
            DocumentResponse.model_validate(doc) for doc in documents
        ]
        
        has_next = (offset + page_size) < total_count
        has_previous = page > 1
        
        return DocumentListResponse(
            documents=document_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=has_next,
            has_previous=has_previous
        )
        
    except Exception as e:
        logger.error("Failed to get case documents", case_id=str(case_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/statistics", response_model=dict)
async def get_document_statistics(
    case_id: Optional[UUID] = Query(None, description="Optional case ID to filter statistics"),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get document statistics for dashboard
    
    - **case_id**: Optional case ID to filter statistics to a specific case
    """
    try:
        statistics = await document_service.get_document_statistics(case_id)
        return statistics
        
    except Exception as e:
        logger.error("Failed to get document statistics", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/formats/supported", response_model=dict)
async def get_supported_formats():
    """
    Get information about supported file formats and size limits
    """
    return {
        "supported_formats": SupportedFileFormats.FORMATS,
        "supported_extensions": SupportedFileFormats.get_supported_extensions(),
        "supported_mime_types": SupportedFileFormats.get_supported_mime_types(),
        "max_file_size_bytes": SupportedFileFormats.MAX_FILE_SIZE,
        "max_file_size_mb": SupportedFileFormats.MAX_FILE_SIZE / (1024 * 1024)
    }

@router.post("/{document_id}/analyze", response_model=DocumentAnalysisResponse)
async def analyze_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Trigger AI analysis for a document
    
    - **document_id**: UUID of the document to analyze
    
    This endpoint initiates text extraction using AWS Textract, entity recognition 
    using AWS Comprehend, and generates AI summaries for documents longer than 1000 words.
    """
    try:
        analysis_result = await document_service.analyze_document(document_id, current_user.id)
        return analysis_result
        
    except CaseManagementException as e:
        logger.error("Document analysis failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to analyze document", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/{document_id}/analysis/status", response_model=dict)
async def get_analysis_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get the current analysis status of a document
    
    - **document_id**: UUID of the document to check
    
    Returns information about the document's processing status, including:
    - Current processing status (uploaded, processing, processed, failed)
    - Processing timestamps
    - Error messages if processing failed
    - Analysis results summary
    """
    try:
        status_info = await document_service.get_analysis_status(document_id)
        return status_info
        
    except CaseManagementException as e:
        logger.error("Failed to get analysis status", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to get analysis status", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/{document_id}/versions", response_model=List[dict])
async def get_document_versions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get all versions of a document for version control
    
    - **document_id**: UUID of the document
    
    Returns a list of all document versions with change history, timestamps,
    and metadata for each version.
    """
    try:
        versions = await document_service.get_document_versions(document_id)
        
        # Convert to response format
        version_responses = []
        for version in versions:
            version_responses.append({
                "id": str(version.id),
                "version_number": version.version_number,
                "change_description": version.change_description,
                "change_type": version.change_type,
                "created_at": version.created_at.isoformat(),
                "created_by": str(version.created_by),
                "filename_snapshot": version.filename_snapshot,
                "file_size_snapshot": version.file_size_snapshot
            })
        
        return version_responses
        
    except CaseManagementException as e:
        logger.error("Failed to get document versions", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to get document versions", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/{document_id}/versions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_document_version(
    document_id: UUID,
    change_description: str = Form(...),
    change_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Create a new version of a document for change tracking
    
    - **document_id**: UUID of the document
    - **change_description**: Description of the changes made
    - **change_type**: Type of change (content_update, metadata_update, reprocessing)
    
    This creates a snapshot of the current document state for version control.
    """
    try:
        # Validate change_type
        valid_change_types = ["content_update", "metadata_update", "reprocessing", "manual_version"]
        if change_type not in valid_change_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid change_type. Must be one of: {', '.join(valid_change_types)}"
            )
        
        version = await document_service.create_document_version(
            document_id, change_description, change_type, current_user.id
        )
        
        return {
            "id": str(version.id),
            "document_id": str(version.document_id),
            "version_number": version.version_number,
            "change_description": version.change_description,
            "change_type": version.change_type,
            "created_at": version.created_at.isoformat(),
            "created_by": str(version.created_by),
            "message": f"Version {version.version_number} created successfully"
        }
        
    except CaseManagementException as e:
        logger.error("Failed to create document version", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to create document version", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/{document_id}/rollback/{target_version}", response_model=DocumentResponse)
async def rollback_document_to_version(
    document_id: UUID,
    target_version: int,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Rollback a document to a previous version
    
    - **document_id**: UUID of the document
    - **target_version**: Version number to rollback to
    
    This restores the document to the exact state it was in at the target version,
    creating a new version entry to track the rollback operation.
    """
    try:
        if target_version < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target version must be 1 or greater"
            )
        
        document = await document_service.rollback_document_to_version(
            document_id, target_version, current_user.id
        )
        
        return DocumentResponse.model_validate(document)
        
    except CaseManagementException as e:
        logger.error("Failed to rollback document", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to rollback document", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/{document_id}/versions/compare/{version1}/{version2}", response_model=dict)
async def compare_document_versions(
    document_id: UUID,
    version1: int,
    version2: int,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Compare two versions of a document
    
    - **document_id**: UUID of the document
    - **version1**: First version number to compare
    - **version2**: Second version number to compare
    
    Returns a detailed comparison showing what changed between the two versions,
    including field-by-field differences and a summary of changes.
    """
    try:
        if version1 < 1 or version2 < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Version numbers must be 1 or greater"
            )
        
        comparison = await document_service.compare_document_versions(
            document_id, version1, version2
        )
        
        return comparison
        
    except CaseManagementException as e:
        logger.error("Failed to compare document versions", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to compare document versions", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")