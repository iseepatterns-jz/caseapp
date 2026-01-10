"""
AI-powered timeline event detection and suggestion service using Amazon Bedrock
"""

import json
import re
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
import structlog
import boto3
from botocore.exceptions import ClientError

from models.document import Document
from models.timeline import EventType
from schemas.timeline import TimelineEventSuggestion
from core.exceptions import CaseManagementException
from core.config import settings

logger = structlog.get_logger()

class AITimelineService:
    """Service for AI-powered timeline event detection and suggestions"""
    
    def __init__(self):
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # Claude 3 Sonnet
    
    async def analyze_document_for_events(
        self, 
        document: Document,
        case_context: Optional[str] = None
    ) -> List[TimelineEventSuggestion]:
        """
        Analyze a document to detect potential timeline events
        
        Args:
            document: Document to analyze
            case_context: Optional context about the case for better suggestions
            
        Returns:
            List of suggested timeline events with confidence scores
        """
        try:
            if not document.extracted_text:
                logger.warning("Document has no extracted text", document_id=str(document.id))
                return []
            
            # Prepare the prompt for Claude
            prompt = self._build_event_detection_prompt(
                document.extracted_text, 
                document.filename,
                case_context
            )
            
            # Call Bedrock to analyze the document
            response = await self._call_bedrock(prompt)
            
            # Parse the response to extract timeline events
            suggestions = self._parse_event_suggestions(response, document.id)
            
            logger.info(
                "Document analyzed for timeline events",
                document_id=str(document.id),
                suggestions_count=len(suggestions)
            )
            
            return suggestions
            
        except Exception as e:
            logger.error(
                "Failed to analyze document for events",
                document_id=str(document.id),
                error=str(e)
            )
            raise CaseManagementException(f"Failed to analyze document for timeline events: {str(e)}")
    
    async def suggest_events_from_text(
        self,
        text_content: str,
        context: Optional[str] = None
    ) -> List[TimelineEventSuggestion]:
        """
        Generate timeline event suggestions from arbitrary text content
        
        Args:
            text_content: Text to analyze for events
            context: Optional context for better suggestions
            
        Returns:
            List of suggested timeline events
        """
        try:
            prompt = self._build_event_detection_prompt(text_content, "text_input", context)
            response = await self._call_bedrock(prompt)
            suggestions = self._parse_event_suggestions(response)
            
            logger.info("Text analyzed for timeline events", suggestions_count=len(suggestions))
            return suggestions
            
        except Exception as e:
            logger.error("Failed to analyze text for events", error=str(e))
            raise CaseManagementException(f"Failed to analyze text for timeline events: {str(e)}")
    
    async def enhance_event_description(
        self,
        event_title: str,
        event_description: str,
        event_type: EventType,
        case_context: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Use AI to enhance event descriptions and suggest improvements
        
        Args:
            event_title: Current event title
            event_description: Current event description
            event_type: Type of event
            case_context: Optional case context
            
        Returns:
            Dictionary with enhanced title and description
        """
        try:
            prompt = self._build_enhancement_prompt(
                event_title, event_description, event_type, case_context
            )
            
            response = await self._call_bedrock(prompt)
            enhanced = self._parse_enhancement_response(response)
            
            logger.info("Event description enhanced", event_title=event_title)
            return enhanced
            
        except Exception as e:
            logger.error("Failed to enhance event description", error=str(e))
            raise CaseManagementException(f"Failed to enhance event description: {str(e)}")
    
    def _build_event_detection_prompt(
        self, 
        text_content: str, 
        source_name: str,
        case_context: Optional[str] = None
    ) -> str:
        """Build prompt for timeline event detection"""
        
        context_section = ""
        if case_context:
            context_section = f"\n\nCase Context:\n{case_context}"
        
        prompt = f"""
You are a legal AI assistant analyzing documents to identify potential timeline events for a court case. 
Your task is to extract chronological events that could be relevant to building a case timeline.

Document Source: {source_name}
{context_section}

Document Content:
{text_content[:4000]}  # Limit content to avoid token limits

Instructions:
1. Identify specific events with dates, times, or temporal references
2. Focus on legally significant events (meetings, incidents, filings, communications, etc.)
3. Extract participant names and locations when available
4. Assign appropriate event types from: incident, meeting, filing, discovery, deposition, hearing, negotiation, correspondence, evidence_collection, witness_interview, expert_consultation, settlement, trial, verdict, appeal, other
5. Provide confidence scores (0.0-1.0) based on clarity and legal relevance
6. Include brief explanations for why each event is significant

Return your analysis as a JSON array with this structure:
[
  {{
    "title": "Brief descriptive title",
    "description": "Detailed description of the event",
    "event_type": "one of the valid event types",
    "suggested_date": "YYYY-MM-DD or YYYY-MM-DD HH:MM if time available",
    "location": "location if mentioned",
    "participants": ["list", "of", "participants"],
    "confidence_score": 0.85,
    "reasoning": "Why this event is legally significant",
    "source_reference": "Quote or reference from the document"
  }}
]

Only include events with confidence scores above 0.6. If no significant events are found, return an empty array.
"""
        return prompt
    
    def _build_enhancement_prompt(
        self,
        title: str,
        description: str,
        event_type: EventType,
        case_context: Optional[str] = None
    ) -> str:
        """Build prompt for event description enhancement"""
        
        context_section = ""
        if case_context:
            context_section = f"\n\nCase Context:\n{case_context}"
        
        prompt = f"""
You are a legal AI assistant helping to improve timeline event descriptions for court case presentation.

Current Event:
- Title: {title}
- Description: {description}
- Type: {event_type.value}
{context_section}

Instructions:
1. Enhance the title to be more descriptive and legally precise
2. Improve the description with better legal terminology and clarity
3. Maintain factual accuracy - do not add information not implied by the original
4. Make the language appropriate for legal professionals
5. Ensure the enhanced version is more compelling for case presentation

Return your enhancement as JSON:
{{
  "enhanced_title": "Improved title",
  "enhanced_description": "Improved description",
  "improvements_made": ["list", "of", "specific", "improvements"]
}}
"""
        return prompt
    
    async def _call_bedrock(self, prompt: str) -> str:
        """Make a call to Amazon Bedrock with the given prompt"""
        try:
            # Prepare the request body for Claude
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
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
            
        except ClientError as e:
            logger.error("Bedrock API error", error=str(e))
            raise CaseManagementException(f"AI service error: {str(e)}")
        except Exception as e:
            logger.error("Failed to call Bedrock", error=str(e))
            raise CaseManagementException(f"Failed to call AI service: {str(e)}")
    
    def _parse_event_suggestions(
        self, 
        ai_response: str, 
        source_document_id: Optional[UUID] = None
    ) -> List[TimelineEventSuggestion]:
        """Parse AI response into timeline event suggestions"""
        try:
            # Extract JSON from the response (AI might include extra text)
            json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON array found in AI response")
                return []
            
            events_data = json.loads(json_match.group())
            suggestions = []
            
            for event_data in events_data:
                try:
                    # Validate and parse the suggested date
                    suggested_date = None
                    if event_data.get('suggested_date'):
                        try:
                            # Try parsing with time first, then date only
                            date_str = event_data['suggested_date']
                            if ' ' in date_str or 'T' in date_str:
                                suggested_date = datetime.fromisoformat(date_str.replace('T', ' '))
                            else:
                                suggested_date = datetime.strptime(date_str, '%Y-%m-%d')
                        except ValueError:
                            logger.warning("Invalid date format", date_str=event_data['suggested_date'])
                    
                    # Validate event type
                    event_type = EventType.OTHER
                    if event_data.get('event_type'):
                        try:
                            event_type = EventType(event_data['event_type'])
                        except ValueError:
                            logger.warning("Invalid event type", event_type=event_data['event_type'])
                    
                    suggestion = TimelineEventSuggestion(
                        title=event_data.get('title', 'Untitled Event'),
                        description=event_data.get('description', ''),
                        event_type=event_type,
                        suggested_date=suggested_date,
                        location=event_data.get('location'),
                        participants=event_data.get('participants', []),
                        confidence_score=float(event_data.get('confidence_score', 0.5)),
                        reasoning=event_data.get('reasoning', ''),
                        source_reference=event_data.get('source_reference', ''),
                        source_document_id=source_document_id
                    )
                    
                    suggestions.append(suggestion)
                    
                except Exception as e:
                    logger.warning("Failed to parse event suggestion", error=str(e), event_data=event_data)
                    continue
            
            return suggestions
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON", error=str(e), response=ai_response[:500])
            return []
        except Exception as e:
            logger.error("Failed to parse event suggestions", error=str(e))
            return []
    
    def _parse_enhancement_response(self, ai_response: str) -> Dict[str, str]:
        """Parse AI response for event enhancement"""
        try:
            # Extract JSON from the response
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON object found in enhancement response")
                return {"enhanced_title": "", "enhanced_description": "", "improvements_made": []}
            
            enhancement_data = json.loads(json_match.group())
            
            return {
                "enhanced_title": enhancement_data.get('enhanced_title', ''),
                "enhanced_description": enhancement_data.get('enhanced_description', ''),
                "improvements_made": enhancement_data.get('improvements_made', [])
            }
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse enhancement response as JSON", error=str(e))
            return {"enhanced_title": "", "enhanced_description": "", "improvements_made": []}
        except Exception as e:
            logger.error("Failed to parse enhancement response", error=str(e))
            return {"enhanced_title": "", "enhanced_description": "", "improvements_made": []}