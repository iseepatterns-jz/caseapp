"""
AI insights schemas for request/response models
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

class CaseCategorizationRequest(BaseModel):
    """Request model for case categorization"""
    case_id: str = Field(..., description="UUID of the case to analyze")
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum confidence score for suggestions")

class CategorySuggestion(BaseModel):
    """Individual category suggestion"""
    category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str

class CaseCategorizationResponse(BaseModel):
    """Response model for case categorization"""
    case_id: str
    categorization: Dict[str, Any]
    generated_at: str
    confidence_threshold: float
    model_used: str

class EvidenceCorrelationRequest(BaseModel):
    """Request model for evidence correlation"""
    case_id: str = Field(..., description="UUID of the case to analyze")
    correlation_threshold: float = Field(0.6, ge=0.0, le=1.0, description="Minimum correlation score for suggestions")

class EvidenceCorrelation(BaseModel):
    """Individual evidence correlation"""
    type: str
    evidence_ids: List[str]
    correlation_score: float = Field(..., ge=0.0, le=1.0)
    description: str
    legal_significance: str

class EvidenceCorrelationResponse(BaseModel):
    """Response model for evidence correlation"""
    case_id: str
    correlations: List[EvidenceCorrelation]
    generated_at: str
    correlation_threshold: float
    total_evidence_items: int
    model_used: str

class RiskAssessmentRequest(BaseModel):
    """Request model for risk assessment"""
    case_id: str = Field(..., description="UUID of the case to analyze")
    include_historical_data: bool = Field(True, description="Whether to include historical case outcomes")

class RiskFactor(BaseModel):
    """Individual risk factor"""
    factor: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    description: str
    mitigation: str

class SuccessFactor(BaseModel):
    """Success factor for case"""
    factor: str
    importance: float = Field(..., ge=0.0, le=1.0)
    description: str

class ResourceRecommendations(BaseModel):
    """Resource allocation recommendations"""
    estimated_hours: Optional[int] = None
    team_size: Optional[int] = None
    specialist_required: List[str] = []
    timeline_estimate: Optional[str] = None

class CriticalMilestone(BaseModel):
    """Critical milestone for case"""
    milestone: str
    target_date: str
    importance: str

class RiskAssessmentResponse(BaseModel):
    """Response model for risk assessment"""
    case_id: str
    risk_assessment: Dict[str, Any]
    complexity_metrics: Dict[str, Any]
    evidence_quality: Dict[str, Any]
    generated_at: str
    model_used: str

class AnomalyDetectionRequest(BaseModel):
    """Request model for anomaly detection"""
    case_id: str = Field(..., description="UUID of the case to analyze")
    anomaly_threshold: float = Field(0.8, ge=0.0, le=1.0, description="Minimum anomaly score for flagging")

class DetectedAnomaly(BaseModel):
    """Individual detected anomaly"""
    anomaly_id: str
    type: str
    severity_score: float = Field(..., ge=0.0, le=1.0)
    legal_significance: str
    investigation_priority: str
    recommended_actions: List[str]
    potential_impact: str

class DetectedPattern(BaseModel):
    """Detected pattern in case data"""
    pattern_name: str
    related_anomalies: List[str]
    pattern_significance: str
    confidence: float = Field(..., ge=0.0, le=1.0)

class InsightRecommendation(BaseModel):
    """AI-generated recommendation"""
    recommendation: str
    priority: str
    rationale: str
    timeline: str

class AnomalyDetectionResponse(BaseModel):
    """Response model for anomaly detection"""
    case_id: str
    anomalies: List[DetectedAnomaly]
    patterns: List[DetectedPattern]
    recommendations: List[InsightRecommendation]
    generated_at: str
    anomaly_threshold: float
    model_used: str

class AIInsightsSummaryResponse(BaseModel):
    """Summary response for all AI insights"""
    case_id: str
    categorization_available: bool
    correlation_available: bool
    risk_assessment_available: bool
    anomaly_detection_available: bool
    timeline_suggestions_available: bool
    last_updated: str
    insights_count: int

class TimelineSuggestionsRequest(BaseModel):
    """Request model for timeline event suggestions from documents"""
    case_id: str = Field(..., description="UUID of the case to analyze")
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum confidence score for suggestions")
    max_suggestions_per_document: int = Field(5, ge=1, le=20, description="Maximum suggestions per document")

class TimelineEventSuggestion(BaseModel):
    """Individual timeline event suggestion"""
    title: str
    description: str
    event_type: str
    suggested_date: Optional[str] = None
    location: Optional[str] = None
    participants: List[str] = []
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    source_reference: str
    source_document_id: Optional[str] = None

class ProcessedDocument(BaseModel):
    """Information about processed document"""
    document_id: str
    filename: str
    suggestions_count: int

class TimelineSuggestionsResponse(BaseModel):
    """Response model for timeline event suggestions"""
    case_id: str
    timeline_suggestions: List[TimelineEventSuggestion]
    processed_documents: List[ProcessedDocument]
    total_suggestions: int
    confidence_threshold: float
    generated_at: str
    model_used: str