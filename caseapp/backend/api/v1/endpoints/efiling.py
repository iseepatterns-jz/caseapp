"""
E-Filing API endpoints
Handles court e-filing integration requests
Validates Requirements 10.3
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime

from ....services.efiling_service import EFilingService, CourtSystem, FilingStatus
from ....schemas.efiling import (
    FilingSubmissionRequest, FilingSubmissionResponse,
    FilingStatusResponse, CourtRequirementsResponse,
    DocumentValidationRequest, DocumentValidationResponse,
    FilingStatisticsResponse, FilingListResponse
)
from ....core.auth import get_current_user
from ....models.user import User

router = APIRouter()
efiling_service = EFilingService()

@router.post("/submit", response_model=FilingSubmissionResponse)
async def submit_filing(
    request: FilingSubmissionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Submit documents for e-filing to court system
    
    Args:
        request: Filing submission request data
        current_user: Authenticated user
    
    Returns:
        Filing submission response with tracking information
    """
    try:
        submission = await efiling_service.submit_filing(
            case_id=request.case_id,
            court_system=request.court_system,
            document_ids=request.document_ids,
            filing_type=request.filing_type,
            metadata=request.metadata
        )
        
        return FilingSubmissionResponse(
            submission_id=submission.submission_id,
            status=submission.status,
            court_reference=submission.court_reference,
            submitted_at=submission.submitted_at,
            estimated_processing_time="24-48 hours",
            tracking_url=f"/api/v1/efiling/status/{submission.submission_id}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status/{submission_id}", response_model=FilingStatusResponse)
async def get_filing_status(
    submission_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get current status of a filing submission
    
    Args:
        submission_id: Unique submission identifier
        current_user: Authenticated user
    
    Returns:
        Current filing status and details
    """
    submission = await efiling_service.get_filing_status(submission_id)
    
    if not submission:
        raise HTTPException(status_code=404, detail="Filing submission not found")
    
    return FilingStatusResponse(
        submission_id=submission.submission_id,
        case_id=submission.case_id,
        court_system=submission.court_system,
        filing_type=submission.filing_type,
        status=submission.status,
        submitted_at=submission.submitted_at,
        updated_at=submission.updated_at,
        court_reference=submission.court_reference,
        rejection_reason=submission.rejection_reason,
        document_count=len(submission.document_ids)
    )

@router.get("/case/{case_id}/filings", response_model=FilingListResponse)
async def get_case_filings(
    case_id: str,
    status: Optional[FilingStatus] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Get all filings for a specific case
    
    Args:
        case_id: Internal case identifier
        status: Optional status filter
        current_user: Authenticated user
    
    Returns:
        List of filing submissions for the case
    """
    filings = await efiling_service.get_case_filings(case_id)
    
    # Apply status filter if provided
    if status:
        filings = [f for f in filings if f.status == status]
    
    filing_responses = [
        FilingStatusResponse(
            submission_id=f.submission_id,
            case_id=f.case_id,
            court_system=f.court_system,
            filing_type=f.filing_type,
            status=f.status,
            submitted_at=f.submitted_at,
            updated_at=f.updated_at,
            court_reference=f.court_reference,
            rejection_reason=f.rejection_reason,
            document_count=len(f.document_ids)
        )
        for f in filings
    ]
    
    return FilingListResponse(
        case_id=case_id,
        total_filings=len(filing_responses),
        filings=filing_responses
    )

@router.post("/cancel/{submission_id}")
async def cancel_filing(
    submission_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a pending filing submission
    
    Args:
        submission_id: Unique submission identifier
        current_user: Authenticated user
    
    Returns:
        Success confirmation
    """
    success = await efiling_service.cancel_filing(submission_id)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Cannot cancel filing - submission not found or already processed"
        )
    
    return {"message": "Filing cancelled successfully", "submission_id": submission_id}

@router.post("/retry/{submission_id}")
async def retry_filing(
    submission_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Retry a failed filing submission
    
    Args:
        submission_id: Unique submission identifier
        current_user: Authenticated user
    
    Returns:
        Success confirmation
    """
    success = await efiling_service.retry_failed_filing(submission_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot retry filing - submission not found or not in failed state"
        )
    
    return {"message": "Filing retry initiated", "submission_id": submission_id}

@router.get("/requirements/{court_system}/{filing_type}", response_model=CourtRequirementsResponse)
async def get_court_requirements(
    court_system: CourtSystem,
    filing_type: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get filing requirements for specific court system and filing type
    
    Args:
        court_system: Target court system
        filing_type: Type of filing
        current_user: Authenticated user
    
    Returns:
        Court filing requirements and rules
    """
    requirements = await efiling_service.get_court_requirements(court_system, filing_type)
    
    if not requirements:
        raise HTTPException(
            status_code=404,
            detail=f"Requirements not found for {court_system} - {filing_type}"
        )
    
    return CourtRequirementsResponse(
        court_system=court_system,
        filing_type=filing_type,
        max_file_size_mb=requirements.get("max_file_size_mb", 25),
        allowed_formats=requirements.get("allowed_formats", ["pdf"]),
        required_metadata=requirements.get("required_metadata", []),
        filing_fees=requirements.get("filing_fees", {}),
        processing_time_hours=requirements.get("processing_time_hours", 24),
        court_rules=requirements.get("court_rules", [])
    )

@router.post("/validate", response_model=DocumentValidationResponse)
async def validate_filing_documents(
    request: DocumentValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Validate documents against court requirements
    
    Args:
        request: Document validation request
        current_user: Authenticated user
    
    Returns:
        Validation results with errors and warnings
    """
    validation_result = await efiling_service.validate_filing_documents(
        document_ids=request.document_ids,
        court_system=request.court_system,
        filing_type=request.filing_type
    )
    
    return DocumentValidationResponse(
        valid=validation_result["valid"],
        errors=validation_result["errors"],
        warnings=validation_result["warnings"],
        document_count=validation_result["document_count"],
        estimated_fees=validation_result["estimated_fees"]
    )

@router.get("/statistics", response_model=FilingStatisticsResponse)
async def get_filing_statistics(
    case_id: Optional[str] = None,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Get filing statistics for reporting
    
    Args:
        case_id: Optional case ID to filter by
        days: Number of days to include in statistics
        current_user: Authenticated user
    
    Returns:
        Filing statistics and metrics
    """
    stats = await efiling_service.get_filing_statistics(case_id=case_id, days=days)
    
    return FilingStatisticsResponse(
        period_days=stats["period_days"],
        total_filings=stats["total_filings"],
        success_rate_percent=stats["success_rate_percent"],
        status_breakdown=stats["status_breakdown"],
        court_system_breakdown=stats["court_system_breakdown"],
        filing_type_breakdown=stats["filing_type_breakdown"],
        average_processing_time_hours=stats["average_processing_time_hours"],
        pending_filings=stats["pending_filings"]
    )

@router.get("/courts", response_model=List[Dict[str, Any]])
async def get_supported_courts(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of supported court systems
    
    Args:
        current_user: Authenticated user
    
    Returns:
        List of supported court systems with details
    """
    courts = [
        {
            "system": CourtSystem.FEDERAL_PACER,
            "name": "Federal PACER System",
            "description": "Federal court electronic filing system",
            "supported_filing_types": ["motion", "brief", "exhibit", "pleading"],
            "max_file_size_mb": 25,
            "processing_time_hours": 24
        },
        {
            "system": CourtSystem.STATE_ECOURTS,
            "name": "State E-Courts System",
            "description": "State court electronic filing system",
            "supported_filing_types": ["motion", "brief", "exhibit", "pleading", "discovery"],
            "max_file_size_mb": 50,
            "processing_time_hours": 48
        },
        {
            "system": CourtSystem.LOCAL_EFILING,
            "name": "Local E-Filing System",
            "description": "Local court electronic filing system",
            "supported_filing_types": ["motion", "brief", "exhibit"],
            "max_file_size_mb": 10,
            "processing_time_hours": 72
        },
        {
            "system": CourtSystem.MOCK_COURT,
            "name": "Mock Court System",
            "description": "Testing and development court system",
            "supported_filing_types": ["motion", "brief", "exhibit", "pleading", "discovery"],
            "max_file_size_mb": 100,
            "processing_time_hours": 1
        }
    ]
    
    return courts

@router.get("/filing-types", response_model=List[Dict[str, Any]])
async def get_filing_types(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of supported filing types
    
    Args:
        current_user: Authenticated user
    
    Returns:
        List of supported filing types with descriptions
    """
    filing_types = [
        {
            "type": "motion",
            "name": "Motion",
            "description": "Request for court action or ruling",
            "typical_fee": 50.00,
            "required_documents": ["motion_document"]
        },
        {
            "type": "brief",
            "name": "Legal Brief",
            "description": "Written legal argument supporting a position",
            "typical_fee": 100.00,
            "required_documents": ["brief_document", "table_of_contents"]
        },
        {
            "type": "exhibit",
            "name": "Exhibit",
            "description": "Evidence or supporting documentation",
            "typical_fee": 25.00,
            "required_documents": ["exhibit_document"]
        },
        {
            "type": "pleading",
            "name": "Pleading",
            "description": "Formal written statement of claims or defenses",
            "typical_fee": 75.00,
            "required_documents": ["pleading_document", "certificate_of_service"]
        },
        {
            "type": "discovery",
            "name": "Discovery Request",
            "description": "Request for information or evidence from opposing party",
            "typical_fee": 30.00,
            "required_documents": ["discovery_document"]
        }
    ]
    
    return filing_types