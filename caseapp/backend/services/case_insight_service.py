"""
AI-powered case insights service using Amazon Bedrock
Provides case categorization, evidence correlation, and risk assessment
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
import structlog
import boto3
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from core.database import AsyncSessionLocal
from models.case import Case, CaseStatus
from models.document import Document
from models.media import MediaEvidence
from models.forensic_analysis import ForensicSource, ForensicItem
from models.timeline import TimelineEvent, CaseTimeline
from schemas.timeline import TimelineEventSuggestion
from services.ai_timeline_service import AITimelineService
from core.exceptions import CaseManagementException
from core.config import settings

logger = structlog.get_logger()

class CaseInsightService:
    """Service for AI-powered case insights and analysis"""
    
    def __init__(self):
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # Claude 3 Sonnet
        self.ai_timeline_service = AITimelineService()
    
    async def generate_case_categorization(
        self, 
        case_id: str,
        confidence_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate AI-powered case categorization suggestions
        
        Args:
            case_id: UUID of the case to analyze
            confidence_threshold: Minimum confidence score for suggestions
            
        Returns:
            Dictionary with categorization suggestions and confidence scores
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get case with all related data
                case_result = await db.execute(
                    select(Case)
                    .where(Case.id == case_id)
                    .options(
                        selectinload(Case.documents),
                        selectinload(Case.timelines).selectinload(CaseTimeline.events),
                        selectinload(Case.media_evidence),
                        selectinload(Case.forensic_sources)
                    )
                )
                case = case_result.scalar_one_or_none()
                
                if not case:
                    raise CaseManagementException(f"Case {case_id} not found")
                
                # Prepare case data for analysis
                case_data = await self._prepare_case_data(case)
                
                # Generate categorization using AI
                prompt = self._build_categorization_prompt(case_data)
                response = await self._call_bedrock_model(prompt)
                
                # Parse and validate response
                categorization = self._parse_categorization_response(response)
                
                # Filter by confidence threshold
                filtered_suggestions = {
                    category: details for category, details in categorization.items()
                    if details.get('confidence', 0) >= confidence_threshold
                }
                
                logger.info("Generated case categorization", 
                           case_id=case_id, 
                           suggestions_count=len(filtered_suggestions))
                
                return {
                    'case_id': case_id,
                    'categorization': filtered_suggestions,
                    'generated_at': datetime.utcnow().isoformat(),
                    'confidence_threshold': confidence_threshold,
                    'model_used': self.model_id
                }
                
        except Exception as e:
            logger.error("Failed to generate case categorization", 
                        case_id=case_id, error=str(e))
            raise CaseManagementException(f"Case categorization failed: {str(e)}")
    
    async def correlate_evidence(
        self, 
        case_id: str,
        correlation_threshold: float = 0.6
    ) -> Dict[str, Any]:
        """
        Identify correlations between different evidence sources
        
        Args:
            case_id: UUID of the case to analyze
            correlation_threshold: Minimum correlation score for suggestions
            
        Returns:
            Dictionary with evidence correlations and relevance scores
        """
        try:
            async with AsyncSessionLocal() as db:
                case_result = await db.execute(
                    select(Case)
                    .where(Case.id == case_id)
                    .options(
                        selectinload(Case.documents),
                        selectinload(Case.media_evidence),
                        selectinload(Case.forensic_sources).selectinload(ForensicSource.forensic_items)
                    )
                )
                case = case_result.scalar_one_or_none()
                
                if not case:
                    raise CaseManagementException(f"Case {case_id} not found")
                
                # Prepare evidence data for correlation analysis
                evidence_data = await self._prepare_evidence_data(case)
                
                # Generate correlations using AI
                prompt = self._build_correlation_prompt(evidence_data)
                response = await self._call_bedrock_model(prompt)
                
                # Parse correlations
                correlations = self._parse_correlation_response(response)
                
                # Filter by correlation threshold
                filtered_correlations = [
                    corr for corr in correlations
                    if corr.get('correlation_score', 0) >= correlation_threshold
                ]
                
                logger.info("Generated evidence correlations", 
                           case_id=case_id, 
                           correlations_count=len(filtered_correlations))
                
                return {
                    'case_id': case_id,
                    'correlations': filtered_correlations,
                    'generated_at': datetime.utcnow().isoformat(),
                    'correlation_threshold': correlation_threshold,
                    'total_evidence_items': len(evidence_data),
                    'model_used': self.model_id
                }
                
        except Exception as e:
            logger.error("Failed to correlate evidence", 
                        case_id=case_id, error=str(e))
            raise CaseManagementException(f"Evidence correlation failed: {str(e)}")
    
    async def assess_case_risk(
        self, 
        case_id: str,
        include_historical_data: bool = True
    ) -> Dict[str, Any]:
        """
        Generate risk assessment for a case based on complexity and evidence quality
        
        Args:
            case_id: UUID of the case to analyze
            include_historical_data: Whether to include historical case outcomes
            
        Returns:
            Dictionary with risk assessment scores and factors
        """
        try:
            async with AsyncSessionLocal() as db:
                case_result = await db.execute(
                    select(Case)
                    .where(Case.id == case_id)
                    .options(
                        selectinload(Case.documents),
                        selectinload(Case.timelines).selectinload(CaseTimeline.events),
                        selectinload(Case.media_evidence),
                        selectinload(Case.forensic_sources)
                    )
                )
                case = case_result.scalar_one_or_none()
                
                if not case:
                    raise CaseManagementException(f"Case {case_id} not found")
                
                # Calculate case complexity metrics
                complexity_metrics = await self._calculate_complexity_metrics(case)
                
                # Assess evidence quality
                evidence_quality = await self._assess_evidence_quality(case)
                
                # Get historical data if requested
                historical_context = {}
                if include_historical_data:
                    historical_context = await self._get_historical_context(case, db)
                
                # Generate risk assessment using AI
                risk_data = {
                    'case_info': {
                        'case_type': case.case_type,
                        'status': case.status,
                        'created_at': case.created_at.isoformat(),
                        'description': case.description[:500] if case.description else ""
                    },
                    'complexity_metrics': complexity_metrics,
                    'evidence_quality': evidence_quality,
                    'historical_context': historical_context
                }
                
                prompt = self._build_risk_assessment_prompt(risk_data)
                response = await self._call_bedrock_model(prompt)
                
                # Parse risk assessment
                risk_assessment = self._parse_risk_assessment_response(response)
                
                logger.info("Generated risk assessment", 
                           case_id=case_id, 
                           overall_risk=risk_assessment.get('overall_risk_score'))
                
                return {
                    'case_id': case_id,
                    'risk_assessment': risk_assessment,
                    'complexity_metrics': complexity_metrics,
                    'evidence_quality': evidence_quality,
                    'generated_at': datetime.utcnow().isoformat(),
                    'model_used': self.model_id
                }
                
        except Exception as e:
            logger.error("Failed to assess case risk", 
                        case_id=case_id, error=str(e))
            raise CaseManagementException(f"Risk assessment failed: {str(e)}")
    
    async def detect_timeline_anomalies(
        self, 
        case_id: str,
        anomaly_threshold: float = 0.8
    ) -> Dict[str, Any]:
        """
        Detect anomalies in forensic data and timeline events
        
        Args:
            case_id: UUID of the case to analyze
            anomaly_threshold: Minimum anomaly score for flagging
            
        Returns:
            Dictionary with detected anomalies and patterns
        """
        try:
            async with AsyncSessionLocal() as db:
                case_result = await db.execute(
                    select(Case)
                    .where(Case.id == case_id)
                    .options(
                        selectinload(Case.forensic_sources),
                        selectinload(Case.timelines).selectinload(CaseTimeline.events)
                    )
                )
                case = case_result.scalar_one_or_none()
                
                if not case:
                    raise CaseManagementException(f"Case {case_id} not found")
                
                # Analyze forensic data for anomalies
                forensic_anomalies = await self._detect_forensic_anomalies(case)
                
                # Analyze timeline for suspicious patterns
                timeline_anomalies = await self._detect_timeline_anomalies(case)
                
                # Generate AI analysis of detected patterns
                anomaly_data = {
                    'forensic_anomalies': forensic_anomalies,
                    'timeline_anomalies': timeline_anomalies
                }
                
                prompt = self._build_anomaly_analysis_prompt(anomaly_data)
                response = await self._call_bedrock_model(prompt)
                
                # Parse anomaly analysis
                analysis = self._parse_anomaly_analysis_response(response)
                
                # Filter by threshold
                significant_anomalies = [
                    anomaly for anomaly in analysis.get('anomalies', [])
                    if anomaly.get('severity_score', 0) >= anomaly_threshold
                ]
                
                logger.info("Detected timeline anomalies", 
                           case_id=case_id, 
                           anomalies_count=len(significant_anomalies))
                
                return {
                    'case_id': case_id,
                    'anomalies': significant_anomalies,
                    'patterns': analysis.get('patterns', []),
                    'recommendations': analysis.get('recommendations', []),
                    'generated_at': datetime.utcnow().isoformat(),
                    'anomaly_threshold': anomaly_threshold,
                    'model_used': self.model_id
                }
                
        except Exception as e:
            logger.error("Failed to detect timeline anomalies", 
                        case_id=case_id, error=str(e))
            raise CaseManagementException(f"Anomaly detection failed: {str(e)}")
    
    async def suggest_timeline_events_from_documents(
        self, 
        case_id: str,
        confidence_threshold: float = 0.7,
        max_suggestions_per_document: int = 5
    ) -> Dict[str, Any]:
        """
        Analyze case documents to suggest timeline events
        
        Args:
            case_id: UUID of the case to analyze
            confidence_threshold: Minimum confidence score for suggestions
            max_suggestions_per_document: Maximum suggestions per document
            
        Returns:
            Dictionary with timeline event suggestions from documents
        """
        try:
            async with AsyncSessionLocal() as db:
                case_result = await db.execute(
                    select(Case)
                    .where(Case.id == case_id)
                    .options(selectinload(Case.documents))
                )
                case = case_result.scalar_one_or_none()
                
                if not case:
                    raise CaseManagementException(f"Case {case_id} not found")
                
                all_suggestions = []
                processed_documents = []
                
                # Analyze each document for timeline events
                for document in case.documents:
                    if not document.extracted_text:
                        continue
                    
                    try:
                        # Build case context for better suggestions
                        case_context = f"""
Case Type: {case.case_type.value}
Case Title: {case.title}
Case Description: {case.description[:500] if case.description else ""}
"""
                        
                        # Use AI timeline service to analyze document
                        doc_suggestions = await self.ai_timeline_service.analyze_document_for_events(
                            document, case_context
                        )
                        
                        # Filter by confidence threshold and limit suggestions
                        filtered_suggestions = [
                            suggestion for suggestion in doc_suggestions
                            if suggestion.confidence_score >= confidence_threshold
                        ][:max_suggestions_per_document]
                        
                        if filtered_suggestions:
                            all_suggestions.extend(filtered_suggestions)
                            processed_documents.append({
                                'document_id': str(document.id),
                                'filename': document.filename,
                                'suggestions_count': len(filtered_suggestions)
                            })
                        
                    except Exception as e:
                        logger.warning("Failed to analyze document for timeline events", 
                                     document_id=str(document.id), error=str(e))
                        continue
                
                # Sort suggestions by confidence score (highest first)
                all_suggestions.sort(key=lambda x: x.confidence_score, reverse=True)
                
                # Convert suggestions to dictionaries for JSON serialization
                suggestion_dicts = []
                for suggestion in all_suggestions:
                    suggestion_dict = {
                        'title': suggestion.title,
                        'description': suggestion.description,
                        'event_type': suggestion.event_type.value,
                        'suggested_date': suggestion.suggested_date.isoformat() if suggestion.suggested_date else None,
                        'location': suggestion.location,
                        'participants': suggestion.participants,
                        'confidence_score': suggestion.confidence_score,
                        'reasoning': suggestion.reasoning,
                        'source_reference': suggestion.source_reference,
                        'source_document_id': str(suggestion.source_document_id) if suggestion.source_document_id else None
                    }
                    suggestion_dicts.append(suggestion_dict)
                
                logger.info("Generated timeline event suggestions from documents", 
                           case_id=case_id, 
                           total_suggestions=len(suggestion_dicts),
                           documents_processed=len(processed_documents))
                
                return {
                    'case_id': case_id,
                    'timeline_suggestions': suggestion_dicts,
                    'processed_documents': processed_documents,
                    'total_suggestions': len(suggestion_dicts),
                    'confidence_threshold': confidence_threshold,
                    'generated_at': datetime.utcnow().isoformat(),
                    'model_used': self.model_id
                }
                
        except Exception as e:
            logger.error("Failed to suggest timeline events from documents", 
                        case_id=case_id, error=str(e))
            raise CaseManagementException(f"Timeline event suggestion failed: {str(e)}")
    
    
    # Helper methods for case data preparation
    async def _prepare_case_data(self, case: Case) -> Dict[str, Any]:
        """Prepare case data for AI analysis"""
        return {
            'case_info': {
                'case_number': case.case_number,
                'title': case.title,
                'description': case.description[:1000] if case.description else "",
                'case_type': case.case_type.value,
                'status': case.status.value,
                'priority': case.priority.value if hasattr(case, 'priority') else "medium",
                'created_at': case.created_at.isoformat(),
                'court_name': case.court_name,
                'judge_name': case.judge_name,
                'jurisdiction': case.case_jurisdiction
            },
            'documents': [
                {
                    'id': str(doc.id),
                    'filename': doc.filename,
                    'document_type': doc.document_type,
                    'ai_summary': doc.ai_summary[:500] if doc.ai_summary else "",
                    'keywords': doc.keywords[:10] if doc.keywords else [],
                    'entities': doc.entities[:20] if doc.entities else []
                }
                for doc in case.documents[:20]  # Limit to first 20 documents
            ],
            'timeline_events': [
                {
                    'id': str(event.id),
                    'title': event.title,
                    'description': event.description[:300] if event.description else "",
                    'event_type': event.event_type.value,
                    'event_date': event.event_date.isoformat() if event.event_date else None,
                    'location': event.location,
                    'participants': event.participants[:10] if event.participants else []
                }
                for timeline in case.timelines
                for event in timeline.events[:10]  # Limit events per timeline
            ],
            'media_evidence': [
                {
                    'id': str(media.id),
                    'filename': media.filename,
                    'media_type': media.media_type,
                    'file_size': media.file_size,
                    'duration': media.duration,
                    'transcription': media.transcription[:500] if media.transcription else ""
                }
                for media in case.media_evidence[:10]  # Limit to first 10 media files
            ],
            'forensic_sources': [
                {
                    'id': str(source.id),
                    'source_name': source.source_name,
                    'source_type': source.source_type,
                    'analysis_status': source.analysis_status.value,
                    'device_info': source.device_info,
                    'account_info': source.account_info
                }
                for source in case.forensic_sources[:5]  # Limit to first 5 sources
            ]
        }
    
    def _build_categorization_prompt(self, case_data: Dict[str, Any]) -> str:
        """Build prompt for case categorization"""
        return f"""
You are a legal AI assistant analyzing a court case to suggest appropriate categorizations and classifications.

Case Information:
{json.dumps(case_data['case_info'], indent=2)}

Documents Summary:
- Total documents: {len(case_data['documents'])}
- Document types: {list(set(doc['document_type'] for doc in case_data['documents']))}
- Key entities: {list(set(entity for doc in case_data['documents'] for entity in doc.get('entities', [])[:5]))}

Timeline Events:
- Total events: {len(case_data['timeline_events'])}
- Event types: {list(set(event['event_type'] for event in case_data['timeline_events']))}

Evidence:
- Media files: {len(case_data['media_evidence'])}
- Forensic sources: {len(case_data['forensic_sources'])}

Instructions:
1. Analyze the case data to suggest appropriate legal categorizations
2. Consider case complexity, evidence types, and legal domain
3. Provide confidence scores (0.0-1.0) for each suggestion
4. Include reasoning for each categorization
5. Suggest relevant legal practice areas and specializations

Return your analysis as JSON:
{{
  "primary_category": {{
    "category": "category_name",
    "confidence": 0.85,
    "reasoning": "explanation"
  }},
  "secondary_categories": [
    {{
      "category": "category_name",
      "confidence": 0.75,
      "reasoning": "explanation"
    }}
  ],
  "practice_areas": ["area1", "area2"],
  "complexity_level": "low|medium|high|complex",
  "estimated_duration": "short|medium|long|extended",
  "resource_requirements": ["requirement1", "requirement2"],
  "key_legal_issues": ["issue1", "issue2"]
}}
"""
    
    async def _call_bedrock_model(self, prompt: str) -> str:
        """Make a call to Amazon Bedrock with the given prompt"""
        try:
            # Prepare the request body for Claude
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 3000,
                "temperature": 0.1,  # Low temperature for consistent, factual responses
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            # Call Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except Exception as e:
            logger.error("Failed to call Bedrock", error=str(e))
            raise CaseManagementException(f"Failed to call AI service: {str(e)}")
    
    def _parse_categorization_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for case categorization"""
        try:
            # Extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in categorization response")
                return {}
            
            categorization = json.loads(json_match.group())
            
            # Validate and structure the response
            result = {}
            
            if 'primary_category' in categorization:
                result['primary'] = categorization['primary_category']
            
            if 'secondary_categories' in categorization:
                result['secondary'] = categorization['secondary_categories']
            
            if 'practice_areas' in categorization:
                result['practice_areas'] = categorization['practice_areas']
            
            if 'complexity_level' in categorization:
                result['complexity'] = categorization['complexity_level']
            
            if 'estimated_duration' in categorization:
                result['duration'] = categorization['estimated_duration']
            
            if 'resource_requirements' in categorization:
                result['resources'] = categorization['resource_requirements']
            
            if 'key_legal_issues' in categorization:
                result['legal_issues'] = categorization['key_legal_issues']
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse categorization response as JSON", error=str(e))
            return {}
        except Exception as e:
            logger.error("Failed to parse categorization response", error=str(e))
            return {}
    
    async def _prepare_evidence_data(self, case: Case) -> List[Dict[str, Any]]:
        """Prepare evidence data for correlation analysis"""
        evidence_items = []
        
        # Add documents
        for doc in case.documents:
            evidence_items.append({
                'id': str(doc.id),
                'type': 'document',
                'title': doc.filename,
                'content': doc.extracted_text[:1000] if doc.extracted_text else "",
                'summary': doc.ai_summary[:300] if doc.ai_summary else "",
                'entities': doc.entities[:10] if doc.entities else [],
                'keywords': doc.keywords[:10] if doc.keywords else [],
                'created_at': doc.created_at.isoformat(),
                'metadata': {
                    'document_type': doc.document_type,
                    'file_size': doc.file_size,
                    'mime_type': doc.mime_type
                }
            })
        
        # Add media evidence
        for media in case.media_evidence:
            evidence_items.append({
                'id': str(media.id),
                'type': 'media',
                'title': media.filename,
                'content': media.transcription[:1000] if media.transcription else "",
                'summary': f"{media.media_type} file, duration: {media.duration}s" if media.duration else "",
                'entities': [],
                'keywords': [],
                'created_at': media.created_at.isoformat(),
                'metadata': {
                    'media_type': media.media_type,
                    'file_size': media.file_size,
                    'duration': media.duration
                }
            })
        
        # Add forensic messages (sample)
        for source in case.forensic_sources:
            if hasattr(source, 'forensic_items'):
                for item in source.forensic_items[:20]:  # Limit to first 20 items per source
                    evidence_items.append({
                        'id': str(item.id),
                        'type': 'forensic_message',
                        'title': item.subject or f"{item.sender} -> {item.recipients}",
                        'content': item.content[:500] if item.content else "",
                        'summary': f"Message from {item.sender} at {item.timestamp}",
                        'entities': item.entities[:5] if item.entities else [],
                        'keywords': item.keywords[:5] if item.keywords else [],
                        'created_at': item.timestamp.isoformat() if item.timestamp else "",
                        'metadata': {
                            'sender': item.sender,
                            'recipients': item.recipients,
                            'message_type': item.item_type.value if hasattr(item, 'item_type') else 'unknown',
                            'sentiment_score': item.sentiment_score
                        }
                    })
        
        return evidence_items
    
    def _build_correlation_prompt(self, evidence_data: List[Dict[str, Any]]) -> str:
        """Build prompt for evidence correlation analysis"""
        return f"""
You are a legal AI assistant analyzing evidence to identify correlations and connections across different sources.

Evidence Summary:
- Total evidence items: {len(evidence_data)}
- Document count: {len([e for e in evidence_data if e['type'] == 'document'])}
- Media count: {len([e for e in evidence_data if e['type'] == 'media'])}
- Forensic messages: {len([e for e in evidence_data if e['type'] == 'forensic_message'])}

Evidence Items (first 10):
{json.dumps(evidence_data[:10], indent=2)}

Instructions:
1. Identify correlations between different evidence items
2. Look for common entities, keywords, dates, and themes
3. Suggest evidence clusters that support similar legal arguments
4. Identify potential contradictions or inconsistencies
5. Provide correlation scores (0.0-1.0) and explanations

Return your analysis as JSON:
{{
  "correlations": [
    {{
      "evidence_ids": ["id1", "id2", "id3"],
      "correlation_type": "entity_overlap|temporal|thematic|contradictory",
      "correlation_score": 0.85,
      "description": "explanation of correlation",
      "legal_significance": "why this correlation matters",
      "supporting_elements": ["element1", "element2"]
    }}
  ],
  "evidence_clusters": [
    {{
      "cluster_name": "cluster_description",
      "evidence_ids": ["id1", "id2"],
      "cluster_strength": 0.75,
      "legal_theme": "theme_description"
    }}
  ],
  "inconsistencies": [
    {{
      "evidence_ids": ["id1", "id2"],
      "inconsistency_type": "temporal|factual|testimonial",
      "description": "explanation of inconsistency",
      "impact_assessment": "potential impact on case"
    }}
  ]
}}
"""
    
    def _parse_correlation_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI response for evidence correlations"""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in correlation response")
                return []
            
            correlation_data = json.loads(json_match.group())
            
            # Extract correlations and add metadata
            correlations = []
            
            for corr in correlation_data.get('correlations', []):
                correlations.append({
                    'type': 'correlation',
                    'evidence_ids': corr.get('evidence_ids', []),
                    'correlation_type': corr.get('correlation_type', 'unknown'),
                    'correlation_score': float(corr.get('correlation_score', 0.5)),
                    'description': corr.get('description', ''),
                    'legal_significance': corr.get('legal_significance', ''),
                    'supporting_elements': corr.get('supporting_elements', [])
                })
            
            for cluster in correlation_data.get('evidence_clusters', []):
                correlations.append({
                    'type': 'cluster',
                    'evidence_ids': cluster.get('evidence_ids', []),
                    'correlation_score': float(cluster.get('cluster_strength', 0.5)),
                    'description': cluster.get('cluster_name', ''),
                    'legal_significance': cluster.get('legal_theme', ''),
                    'cluster_name': cluster.get('cluster_name', '')
                })
            
            for inconsistency in correlation_data.get('inconsistencies', []):
                correlations.append({
                    'type': 'inconsistency',
                    'evidence_ids': inconsistency.get('evidence_ids', []),
                    'correlation_score': 0.9,  # High score for inconsistencies (important to flag)
                    'description': inconsistency.get('description', ''),
                    'legal_significance': inconsistency.get('impact_assessment', ''),
                    'inconsistency_type': inconsistency.get('inconsistency_type', 'unknown')
                })
            
            return correlations
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse correlation response as JSON", error=str(e))
            return []
        except Exception as e:
            logger.error("Failed to parse correlation response", error=str(e))
            return []
    
    async def _calculate_complexity_metrics(self, case: Case) -> Dict[str, Any]:
        """Calculate case complexity metrics"""
        metrics = {
            'document_count': len(case.documents),
            'media_count': len(case.media_evidence),
            'forensic_sources_count': len(case.forensic_sources),
            'timeline_events_count': sum(len(timeline.events) for timeline in case.timelines),
            'case_age_days': (datetime.utcnow() - case.created_at).days,
            'has_court_date': case.court_date is not None,
            'has_deadline': case.deadline_date is not None,
            'document_types': list(set(doc.document_type for doc in case.documents)),
            'total_file_size': sum(doc.file_size for doc in case.documents if doc.file_size),
            'ai_processed_documents': len([doc for doc in case.documents if doc.ai_summary]),
            'privileged_documents': len([doc for doc in case.documents if doc.is_privileged]),
            'confidential_documents': len([doc for doc in case.documents if doc.is_confidential])
        }
        
        # Calculate complexity score
        complexity_score = 0
        
        # Document complexity
        if metrics['document_count'] > 100:
            complexity_score += 3
        elif metrics['document_count'] > 50:
            complexity_score += 2
        elif metrics['document_count'] > 10:
            complexity_score += 1
        
        # Media complexity
        if metrics['media_count'] > 20:
            complexity_score += 2
        elif metrics['media_count'] > 5:
            complexity_score += 1
        
        # Forensic complexity
        if metrics['forensic_sources_count'] > 3:
            complexity_score += 3
        elif metrics['forensic_sources_count'] > 1:
            complexity_score += 2
        elif metrics['forensic_sources_count'] > 0:
            complexity_score += 1
        
        # Timeline complexity
        if metrics['timeline_events_count'] > 50:
            complexity_score += 2
        elif metrics['timeline_events_count'] > 20:
            complexity_score += 1
        
        # Case age complexity
        if metrics['case_age_days'] > 365:
            complexity_score += 2
        elif metrics['case_age_days'] > 180:
            complexity_score += 1
        
        # Document type diversity
        if len(metrics['document_types']) > 5:
            complexity_score += 1
        
        metrics['complexity_score'] = min(complexity_score, 10)  # Cap at 10
        metrics['complexity_level'] = (
            'low' if complexity_score <= 3 else
            'medium' if complexity_score <= 6 else
            'high' if complexity_score <= 8 else
            'very_high'
        )
        
        return metrics
    
    async def _assess_evidence_quality(self, case: Case) -> Dict[str, Any]:
        """Assess the quality of evidence in the case"""
        quality_metrics = {
            'total_evidence_items': len(case.documents) + len(case.media_evidence) + len(case.forensic_sources),
            'processed_documents_ratio': 0,
            'ai_analysis_coverage': 0,
            'chain_of_custody_compliance': 0,
            'evidence_diversity_score': 0,
            'temporal_coverage_score': 0
        }
        
        if case.documents:
            processed_docs = len([doc for doc in case.documents if doc.ai_summary])
            quality_metrics['processed_documents_ratio'] = processed_docs / len(case.documents)
            quality_metrics['ai_analysis_coverage'] = processed_docs / len(case.documents)
        
        # Evidence diversity (different types of evidence)
        evidence_types = set()
        if case.documents:
            evidence_types.add('documents')
        if case.media_evidence:
            evidence_types.add('media')
        if case.forensic_sources:
            evidence_types.add('forensic')
        
        quality_metrics['evidence_diversity_score'] = len(evidence_types) / 3.0
        
        # Chain of custody (simplified assessment)
        custody_compliant = 0
        total_items = 0
        
        for doc in case.documents:
            total_items += 1
            if doc.file_hash and doc.uploaded_by:
                custody_compliant += 1
        
        for media in case.media_evidence:
            total_items += 1
            if hasattr(media, 'file_hash') and media.file_hash and hasattr(media, 'uploaded_by') and media.uploaded_by:
                custody_compliant += 1
        
        if total_items > 0:
            quality_metrics['chain_of_custody_compliance'] = custody_compliant / total_items
        
        # Temporal coverage (how well evidence covers the case timeline)
        if case.timelines:
            all_dates = []
            for timeline in case.timelines:
                for event in timeline.events:
                    if event.event_date:
                        all_dates.append(event.event_date)
            
            if all_dates:
                date_range = (max(all_dates) - min(all_dates)).days
                quality_metrics['temporal_coverage_days'] = date_range
                quality_metrics['temporal_coverage_score'] = min(date_range / 365.0, 1.0)  # Normalize to 1 year
        
        # Overall quality score
        quality_score = (
            quality_metrics['processed_documents_ratio'] * 0.3 +
            quality_metrics['evidence_diversity_score'] * 0.3 +
            quality_metrics['chain_of_custody_compliance'] * 0.2 +
            quality_metrics['temporal_coverage_score'] * 0.2
        )
        
        quality_metrics['overall_quality_score'] = quality_score
        quality_metrics['quality_level'] = (
            'poor' if quality_score < 0.3 else
            'fair' if quality_score < 0.6 else
            'good' if quality_score < 0.8 else
            'excellent'
        )
        
        return quality_metrics
    
    async def _get_historical_context(self, case: Case, db: AsyncSession) -> Dict[str, Any]:
        """Get historical context from similar cases"""
        try:
            # Find similar cases by type and characteristics
            similar_cases_result = await db.execute(
                select(Case)
                .where(
                    and_(
                        Case.case_type == case.case_type,
                        Case.status == CaseStatus.CLOSED,
                        Case.id != case.id
                    )
                )
                .limit(10)
            )
            similar_cases = similar_cases_result.scalars().all()
            
            if not similar_cases:
                return {'message': 'No historical data available for similar cases'}
            
            # Calculate historical metrics
            case_durations = []
            outcomes = []
            
            for similar_case in similar_cases:
                if similar_case.created_at and similar_case.closed_date:
                    duration = (similar_case.closed_date - similar_case.created_at).days
                    case_durations.append(duration)
                
                # Extract outcome from case metadata if available
                if similar_case.case_metadata and 'outcome' in similar_case.case_metadata:
                    outcomes.append(similar_case.case_metadata['outcome'])
            
            historical_context = {
                'similar_cases_count': len(similar_cases),
                'average_duration_days': sum(case_durations) / len(case_durations) if case_durations else None,
                'median_duration_days': sorted(case_durations)[len(case_durations)//2] if case_durations else None,
                'common_outcomes': list(set(outcomes)) if outcomes else [],
                'case_type': case.case_type.value,
                'success_indicators': []
            }
            
            # Add success indicators based on historical data
            if case_durations:
                if len(case_durations) >= 5:
                    historical_context['success_indicators'].append(
                        f"Similar {case.case_type.value} cases typically resolve in {historical_context['average_duration_days']:.0f} days"
                    )
                
                if outcomes:
                    outcome_counts = {}
                    for outcome in outcomes:
                        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
                    
                    most_common_outcome = max(outcome_counts, key=outcome_counts.get)
                    historical_context['success_indicators'].append(
                        f"Most common outcome for similar cases: {most_common_outcome}"
                    )
            
            return historical_context
            
        except Exception as e:
            logger.warning("Failed to get historical context", error=str(e))
            return {'message': 'Historical context unavailable', 'error': str(e)}
    
    def _build_risk_assessment_prompt(self, risk_data: Dict[str, Any]) -> str:
        """Build prompt for risk assessment"""
        return f"""
You are a legal AI assistant performing risk assessment for a court case based on complexity metrics, evidence quality, and historical data.

Case Information:
{json.dumps(risk_data['case_info'], indent=2)}

Complexity Metrics:
{json.dumps(risk_data['complexity_metrics'], indent=2)}

Evidence Quality Assessment:
{json.dumps(risk_data['evidence_quality'], indent=2)}

Historical Context:
{json.dumps(risk_data['historical_context'], indent=2)}

Instructions:
1. Assess overall case risk based on complexity, evidence quality, and historical patterns
2. Identify specific risk factors and mitigation strategies
3. Provide risk scores (0.0-1.0) for different aspects
4. Suggest resource allocation and timeline recommendations
5. Highlight critical success factors and potential pitfalls

Return your assessment as JSON:
{{
  "overall_risk_score": 0.65,
  "risk_level": "low|medium|high|critical",
  "risk_factors": [
    {{
      "factor": "factor_name",
      "risk_score": 0.7,
      "description": "explanation",
      "mitigation": "suggested mitigation strategy"
    }}
  ],
  "success_factors": [
    {{
      "factor": "factor_name",
      "importance": 0.8,
      "description": "explanation"
    }}
  ],
  "resource_recommendations": {{
    "estimated_hours": 150,
    "team_size": 3,
    "specialist_required": ["expert1", "expert2"],
    "timeline_estimate": "3-6 months"
  }},
  "critical_milestones": [
    {{
      "milestone": "milestone_name",
      "target_date": "relative_timeframe",
      "importance": "high|medium|low"
    }}
  ],
  "confidence_score": 0.85
}}
"""
    
    def _parse_risk_assessment_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for risk assessment"""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in risk assessment response")
                return {'overall_risk_score': 0.5, 'risk_level': 'medium'}
            
            risk_data = json.loads(json_match.group())
            
            # Validate and structure the response
            result = {
                'overall_risk_score': float(risk_data.get('overall_risk_score', 0.5)),
                'risk_level': risk_data.get('risk_level', 'medium'),
                'risk_factors': risk_data.get('risk_factors', []),
                'success_factors': risk_data.get('success_factors', []),
                'resource_recommendations': risk_data.get('resource_recommendations', {}),
                'critical_milestones': risk_data.get('critical_milestones', []),
                'confidence_score': float(risk_data.get('confidence_score', 0.5))
            }
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse risk assessment response as JSON", error=str(e))
            return {'overall_risk_score': 0.5, 'risk_level': 'medium', 'error': 'parsing_failed'}
        except Exception as e:
            logger.error("Failed to parse risk assessment response", error=str(e))
            return {'overall_risk_score': 0.5, 'risk_level': 'medium', 'error': str(e)}
    
    async def _detect_forensic_anomalies(self, case: Case) -> List[Dict[str, Any]]:
        """Detect anomalies in forensic data"""
        anomalies = []
        
        for source in case.forensic_sources:
            if hasattr(source, 'forensic_items'):
                items = source.forensic_items if hasattr(source, 'forensic_items') else []
                
                # Check for timing anomalies (messages sent at unusual hours)
                unusual_times = []
                for item in items:
                    if item.timestamp:
                        hour = item.timestamp.hour
                        if hour < 6 or hour > 22:  # Messages between 10 PM and 6 AM
                            unusual_times.append(item.timestamp)
                
                if len(unusual_times) > len(items) * 0.2:  # More than 20% unusual timing
                    anomalies.append({
                        'type': 'timing_anomaly',
                        'source_id': str(source.id),
                        'description': f'High frequency of messages sent during unusual hours',
                        'severity': 0.7,
                        'count': len(unusual_times),
                        'total_messages': len(items)
                    })
                
                # Check for deleted message patterns
                deleted_items = [item for item in items if item.is_deleted]
                if len(deleted_items) > len(items) * 0.1:  # More than 10% deleted
                    anomalies.append({
                        'type': 'deletion_pattern',
                        'source_id': str(source.id),
                        'description': f'High rate of deleted messages detected',
                        'severity': 0.8,
                        'deleted_count': len(deleted_items),
                        'total_messages': len(items)
                    })
                
                # Check for sentiment anomalies
                negative_items = [item for item in items if item.sentiment_score and item.sentiment_score < -0.5]
                if len(negative_items) > len(items) * 0.3:  # More than 30% very negative
                    anomalies.append({
                        'type': 'sentiment_anomaly',
                        'source_id': str(source.id),
                        'description': f'High concentration of negative sentiment messages',
                        'severity': 0.6,
                        'negative_count': len(negative_items),
                        'total_messages': len(items)
                    })
        
        return anomalies
    
    async def _detect_timeline_anomalies(self, case: Case) -> List[Dict[str, Any]]:
        """Detect anomalies in timeline events"""
        anomalies = []
        
        for timeline in case.timelines:
            events = timeline.events
            
            if len(events) < 2:
                continue
            
            # Sort events by date
            dated_events = [event for event in events if event.event_date]
            dated_events.sort(key=lambda x: x.event_date)
            
            # Check for temporal gaps
            for i in range(1, len(dated_events)):
                gap = (dated_events[i].event_date - dated_events[i-1].event_date).days
                if gap > 90:  # More than 3 months gap
                    anomalies.append({
                        'type': 'temporal_gap',
                        'timeline_id': str(timeline.id),
                        'description': f'Large temporal gap between events: {gap} days',
                        'severity': 0.5,
                        'gap_days': gap,
                        'event_before': dated_events[i-1].title,
                        'event_after': dated_events[i].title
                    })
            
            # Check for event clustering (too many events in short time)
            event_dates = [event.event_date.date() for event in dated_events]
            date_counts = {}
            for date in event_dates:
                date_counts[date] = date_counts.get(date, 0) + 1
            
            for date, count in date_counts.items():
                if count > 5:  # More than 5 events on same day
                    anomalies.append({
                        'type': 'event_clustering',
                        'timeline_id': str(timeline.id),
                        'description': f'High concentration of events on single day: {date}',
                        'severity': 0.4,
                        'event_count': count,
                        'date': date.isoformat()
                    })
        
        return anomalies
    
    def _build_anomaly_analysis_prompt(self, anomaly_data: Dict[str, Any]) -> str:
        """Build prompt for anomaly analysis"""
        return f"""
You are a legal AI assistant analyzing detected anomalies and patterns in case data to assess their significance and provide recommendations.

Detected Forensic Anomalies:
{json.dumps(anomaly_data['forensic_anomalies'], indent=2)}

Detected Timeline Anomalies:
{json.dumps(anomaly_data['timeline_anomalies'], indent=2)}

Instructions:
1. Analyze the significance of each detected anomaly
2. Identify patterns that might indicate important legal issues
3. Assess the severity and potential impact of anomalies
4. Provide recommendations for investigation or follow-up
5. Suggest how anomalies might affect case strategy

Return your analysis as JSON:
{{
  "anomalies": [
    {{
      "anomaly_id": "unique_id",
      "type": "anomaly_type",
      "severity_score": 0.8,
      "legal_significance": "explanation of legal importance",
      "investigation_priority": "high|medium|low",
      "recommended_actions": ["action1", "action2"],
      "potential_impact": "description of potential case impact"
    }}
  ],
  "patterns": [
    {{
      "pattern_name": "pattern_description",
      "related_anomalies": ["anomaly_id1", "anomaly_id2"],
      "pattern_significance": "explanation",
      "confidence": 0.75
    }}
  ],
  "recommendations": [
    {{
      "recommendation": "specific_recommendation",
      "priority": "high|medium|low",
      "rationale": "explanation",
      "timeline": "suggested_timeframe"
    }}
  ],
  "overall_assessment": {{
    "risk_level": "low|medium|high|critical",
    "key_concerns": ["concern1", "concern2"],
    "strategic_implications": "overall strategic impact"
  }}
}}
"""
    
    def _parse_anomaly_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for anomaly analysis"""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in anomaly analysis response")
                return {'anomalies': [], 'patterns': [], 'recommendations': []}
            
            analysis_data = json.loads(json_match.group())
            
            return {
                'anomalies': analysis_data.get('anomalies', []),
                'patterns': analysis_data.get('patterns', []),
                'recommendations': analysis_data.get('recommendations', []),
                'overall_assessment': analysis_data.get('overall_assessment', {})
            }
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse anomaly analysis response as JSON", error=str(e))
            return {'anomalies': [], 'patterns': [], 'recommendations': []}
        except Exception as e:
            logger.error("Failed to parse anomaly analysis response", error=str(e))
            return {'anomalies': [], 'patterns': [], 'recommendations': []}