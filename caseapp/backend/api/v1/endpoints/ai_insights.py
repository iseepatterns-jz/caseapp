"""
AI insights API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from datetime import datetime
import structlog

from schemas.ai_insights import (
    CaseCategorizationRequest, CaseCategorizationResponse,
    EvidenceCorrelationRequest, EvidenceCorrelationResponse,
    RiskAssessmentRequest, RiskAssessmentResponse,
    AnomalyDetectionRequest, AnomalyDetectionResponse,
    TimelineSuggestionsRequest, TimelineSuggestionsResponse,
    AIInsightsSummaryResponse
)
from services.case_insight_service import CaseInsightService
from core.exceptions import CaseManagementException
from core.auth import get_current_user
from models.user import User

logger = structlog.get_logger()
router = APIRouter()

@router.post("/categorization", response_model=CaseCategorizationResponse)
async def generate_case_categorization(
    request: CaseCategorizationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate AI-powered case categorization suggestions
    
    Analyzes case data to suggest appropriate legal categorizations,
    practice areas, and complexity assessments.
    """
    try:
        service = CaseInsightService()
        result = await service.generate_case_categorization(
            case_id=request.case_id,
            confidence_threshold=request.confidence_threshold
        )
        
        logger.info("Case categorization generated", 
                   case_id=request.case_id, 
                   user_id=str(current_user.id))
        
        return CaseCategorizationResponse(**result)
        
    except CaseManagementException as e:
        logger.error("Case categorization failed", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error in case categorization", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate case categorization"
        )

@router.post("/evidence-correlation", response_model=EvidenceCorrelationResponse)
async def correlate_evidence(
    request: EvidenceCorrelationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Identify correlations between different evidence sources
    
    Analyzes documents, media, and forensic data to find connections,
    patterns, and potential contradictions across evidence types.
    """
    try:
        service = CaseInsightService()
        result = await service.correlate_evidence(
            case_id=request.case_id,
            correlation_threshold=request.correlation_threshold
        )
        
        logger.info("Evidence correlation generated", 
                   case_id=request.case_id, 
                   user_id=str(current_user.id))
        
        return EvidenceCorrelationResponse(**result)
        
    except CaseManagementException as e:
        logger.error("Evidence correlation failed", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error in evidence correlation", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to correlate evidence"
        )

@router.post("/risk-assessment", response_model=RiskAssessmentResponse)
async def assess_case_risk(
    request: RiskAssessmentRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate comprehensive risk assessment for a case
    
    Analyzes case complexity, evidence quality, and historical data
    to provide risk scores, resource recommendations, and strategic insights.
    """
    try:
        service = CaseInsightService()
        result = await service.assess_case_risk(
            case_id=request.case_id,
            include_historical_data=request.include_historical_data
        )
        
        logger.info("Risk assessment generated", 
                   case_id=request.case_id, 
                   user_id=str(current_user.id))
        
        return RiskAssessmentResponse(**result)
        
    except CaseManagementException as e:
        logger.error("Risk assessment failed", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error in risk assessment", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assess case risk"
        )

@router.post("/anomaly-detection", response_model=AnomalyDetectionResponse)
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Detect anomalies and suspicious patterns in case data
    
    Analyzes forensic data and timeline events to identify unusual patterns,
    timing anomalies, and potentially significant irregularities.
    """
    try:
        service = CaseInsightService()
        result = await service.detect_timeline_anomalies(
            case_id=request.case_id,
            anomaly_threshold=request.anomaly_threshold
        )
        
        logger.info("Anomaly detection completed", 
                   case_id=request.case_id, 
                   user_id=str(current_user.id))
        
        return AnomalyDetectionResponse(**result)
        
    except CaseManagementException as e:
        logger.error("Anomaly detection failed", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error in anomaly detection", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to detect anomalies"
        )

@router.post("/timeline-suggestions", response_model=TimelineSuggestionsResponse)
async def suggest_timeline_events_from_documents(
    request: TimelineSuggestionsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate timeline event suggestions from case documents
    
    Analyzes all documents in a case to identify potential timeline events
    using AI analysis. Provides confidence scores and reasoning for each suggestion.
    """
    try:
        service = CaseInsightService()
        result = await service.suggest_timeline_events_from_documents(
            case_id=request.case_id,
            confidence_threshold=request.confidence_threshold,
            max_suggestions_per_document=request.max_suggestions_per_document
        )
        
        logger.info("Timeline event suggestions generated", 
                   case_id=request.case_id, 
                   user_id=str(current_user.id))
        
        return TimelineSuggestionsResponse(**result)
        
    except CaseManagementException as e:
        logger.error("Timeline suggestions failed", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error in timeline suggestions", 
                    case_id=request.case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate timeline suggestions"
        )

@router.get("/{case_id}/summary", response_model=AIInsightsSummaryResponse)
async def get_insights_summary(
    case_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get summary of available AI insights for a case
    
    Returns overview of which AI insights are available and when
    they were last generated for the specified case.
    """
    try:
        # This would typically check the database for existing insights
        # For now, return a basic summary indicating all insights are available
        
        logger.info("AI insights summary requested", 
                   case_id=case_id, 
                   user_id=str(current_user.id))
        
        return AIInsightsSummaryResponse(
            case_id=case_id,
            categorization_available=True,
            correlation_available=True,
            risk_assessment_available=True,
            anomaly_detection_available=True,
            timeline_suggestions_available=True,
            last_updated="2024-01-01T00:00:00Z",  # Placeholder
            insights_count=5
        )
        
    except Exception as e:
        logger.error("Failed to get insights summary", 
                    case_id=case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get insights summary"
        )

@router.post("/{case_id}/generate-all")
async def generate_all_insights(
    case_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Generate all available AI insights for a case
    
    Runs categorization, evidence correlation, risk assessment,
    and anomaly detection in sequence for comprehensive analysis.
    """
    try:
        service = CaseInsightService()
        results = {}
        
        # Generate categorization
        try:
            categorization = await service.generate_case_categorization(case_id)
            results['categorization'] = categorization
        except Exception as e:
            results['categorization'] = {'error': str(e)}
        
        # Generate evidence correlation
        try:
            correlation = await service.correlate_evidence(case_id)
            results['correlation'] = correlation
        except Exception as e:
            results['correlation'] = {'error': str(e)}
        
        # Generate risk assessment
        try:
            risk_assessment = await service.assess_case_risk(case_id)
            results['risk_assessment'] = risk_assessment
        except Exception as e:
            results['risk_assessment'] = {'error': str(e)}
        
        # Generate anomaly detection
        try:
            anomalies = await service.detect_timeline_anomalies(case_id)
            results['anomalies'] = anomalies
        except Exception as e:
            results['anomalies'] = {'error': str(e)}
        
        # Generate timeline suggestions
        try:
            timeline_suggestions = await service.suggest_timeline_events_from_documents(case_id)
            results['timeline_suggestions'] = timeline_suggestions
        except Exception as e:
            results['timeline_suggestions'] = {'error': str(e)}
        
        logger.info("All AI insights generated", 
                   case_id=case_id, 
                   user_id=str(current_user.id))
        
        return {
            'case_id': case_id,
            'insights': results,
            'generated_at': str(datetime.utcnow()),
            'success_count': len([r for r in results.values() if 'error' not in r])
        }
        
    except Exception as e:
        logger.error("Failed to generate all insights", 
                    case_id=case_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate all insights"
        )