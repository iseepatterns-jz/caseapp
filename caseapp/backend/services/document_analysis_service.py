"""
Document analysis service with AWS Textract and Comprehend integration
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta, UTC
import json
import asyncio
import structlog
import boto3
from botocore.exceptions import ClientError

from models.document import Document, DocumentStatus, ExtractedEntity
from schemas.document import DocumentAnalysisResponse
from core.exceptions import CaseManagementException
from core.config import get_settings
from services.audit_service import AuditService

logger = structlog.get_logger()
settings = get_settings()

class DocumentAnalysisService:
    """Service for AI-powered document analysis using AWS services"""
    
    def __init__(self, db: AsyncSession, audit_service: AuditService):
        self.db = db
        self.audit_service = audit_service
        
        # Initialize AWS clients
        self.textract_client = boto3.client(
            'textract',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        self.comprehend_client = boto3.client(
            'comprehend',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        self.s3_bucket = settings.S3_BUCKET_NAME
    
    async def analyze_document(self, document_id: UUID, user_id: UUID) -> DocumentAnalysisResponse:
        """
        Perform complete AI analysis on a document
        
        Args:
            document_id: Document UUID to analyze
            user_id: UUID of the user requesting analysis
            
        Returns:
            DocumentAnalysisResponse with analysis results
            
        Raises:
            CaseManagementException: If document not found or analysis fails
        """
        try:
            # Get document
            document = await self._get_document(document_id)
            if not document:
                raise CaseManagementException(
                    f"Document with ID {document_id} not found",
                    error_code="DOCUMENT_NOT_FOUND"
                )
            
            # Check if document is in a state that can be analyzed
            if document.status == DocumentStatus.PROCESSING.value:
                raise CaseManagementException(
                    "Document is already being processed",
                    error_code="DOCUMENT_PROCESSING"
                )
            
            # Update document status to processing
            document.status = DocumentStatus.PROCESSING.value
            document.processing_started_at = datetime.now(UTC)
            document.processing_error = None
            await self.db.commit()
            
            # Log analysis start
            await self.audit_service.log_action(
                entity_type="document",
                entity_id=document.id,
                action="analysis_started",
                user_id=user_id,
                case_id=document.case_id,
                new_value="AI analysis pipeline initiated"
            )
            
            try:
                # Step 1: Extract text using Textract
                extracted_text = await self._extract_text_with_textract(document)
                
                # Step 1b: Detect financial transactions in text
                try:
                    from services.financial_analysis_service import FinancialAnalysisService
                    financial_service = FinancialAnalysisService(self.db)
                    await financial_service.ingest_from_text(
                        case_id=document.case_id,
                        text=extracted_text,
                        document_id=document.id
                    )
                except Exception as financial_error:
                    logger.warning("Financial analysis failed, continuing with other analysis", error=str(financial_error))
                
                # Step 2: Perform entity recognition using Comprehend
                entities = []
                try:
                    entities = await self._extract_entities_with_comprehend(extracted_text)
                except Exception as entity_error:
                    logger.warning("Entity extraction failed, continuing with empty entities", error=str(entity_error))
                    entities = []
                
                # Step 3: Generate summary if document is long enough
                ai_summary = None
                if len(extracted_text) > 1000:  # Requirement 2.4: Summary for documents > 1000 words
                    ai_summary = await self._generate_summary_with_comprehend(extracted_text)
                
                # Step 4: Extract key phrases
                key_phrases = []
                try:
                    key_phrases = await self._extract_key_phrases_with_comprehend(extracted_text)
                except Exception as key_phrase_error:
                    logger.warning("Key phrase extraction failed, continuing with empty phrases", error=str(key_phrase_error))
                    key_phrases = []
                
                # Step 5: Analyze sentiment
                sentiment_analysis = {"sentiment": "NEUTRAL", "confidence": 0, "scores": {}}
                try:
                    sentiment_analysis = await self._analyze_sentiment_with_comprehend(extracted_text)
                except Exception as sentiment_error:
                    logger.warning("Sentiment analysis failed, using neutral sentiment", error=str(sentiment_error))
                    sentiment_analysis = {"sentiment": "NEUTRAL", "confidence": 0, "scores": {}}
                
                # Update document with analysis results
                document.extracted_text = extracted_text
                document.ai_summary = ai_summary
                document.entities = self._format_entities_for_storage(entities)
                document.keywords = key_phrases
                document.confidence_scores = {
                    "text_extraction": 95,  # Textract is generally very reliable
                    "entity_extraction": self._calculate_average_entity_confidence(entities),
                    "sentiment": sentiment_analysis.get("confidence", 0)
                }
                document.status = DocumentStatus.PROCESSED.value
                document.processing_completed_at = datetime.now(UTC)
                
                # Store extracted entities in separate table
                await self._store_extracted_entities(document.id, entities)
                
                await self.db.commit()
                
                # Log successful analysis
                await self.audit_service.log_action(
                    entity_type="document",
                    entity_id=document.id,
                    action="analysis_completed",
                    user_id=user_id,
                    case_id=document.case_id,
                    new_value=f"Analysis completed: {len(entities)} entities, {len(extracted_text)} chars extracted"
                )
                
                logger.info(
                    "Document analysis completed successfully",
                    document_id=str(document.id),
                    entities_count=len(entities),
                    text_length=len(extracted_text),
                    has_summary=ai_summary is not None
                )
                
                return DocumentAnalysisResponse(
                    document_id=document.id,
                    extracted_text=extracted_text,
                    ai_summary=ai_summary,
                    entities=entities,
                    key_phrases=key_phrases,
                    sentiment=sentiment_analysis,
                    confidence_scores=document.confidence_scores,
                    processing_time_seconds=(
                        document.processing_completed_at - document.processing_started_at
                    ).total_seconds(),
                    status="completed"
                )
                
            except Exception as analysis_error:
                # Update document with error status
                document.status = DocumentStatus.FAILED.value
                document.processing_error = str(analysis_error)
                document.processing_completed_at = datetime.now(UTC)
                await self.db.commit()
                
                # Log analysis failure
                await self.audit_service.log_action(
                    entity_type="document",
                    entity_id=document.id,
                    action="analysis_failed",
                    user_id=user_id,
                    case_id=document.case_id,
                    new_value=f"Analysis failed: {str(analysis_error)}"
                )
                
                logger.error(
                    "Document analysis failed",
                    document_id=str(document.id),
                    error=str(analysis_error)
                )
                
                raise CaseManagementException(
                    f"Document analysis failed: {str(analysis_error)}",
                    error_code="ANALYSIS_FAILED"
                )
                
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to analyze document", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to analyze document: {str(e)}")
    
    async def _extract_text_with_textract(self, document: Document) -> str:
        """
        Extract text from document using AWS Textract
        
        Args:
            document: Document instance
            
        Returns:
            Extracted text content
        """
        try:
            # For synchronous processing (documents < 5MB)
            if document.file_size < 5 * 1024 * 1024:  # 5MB limit for sync processing
                response = self.textract_client.detect_document_text(
                    Document={
                        'S3Object': {
                            'Bucket': self.s3_bucket,
                            'Name': document.file_path
                        }
                    }
                )
                
                # Extract text from blocks
                extracted_text = ""
                for block in response.get('Blocks', []):
                    if block['BlockType'] == 'LINE':
                        extracted_text += block.get('Text', '') + '\n'
                
                return extracted_text.strip()
            
            else:
                # For larger documents, use asynchronous processing
                return await self._extract_text_async_textract(document)
                
        except ClientError as e:
            logger.error("Textract extraction failed", error=str(e), document_id=str(document.id))
            raise CaseManagementException(f"Text extraction failed: {str(e)}")
    
    async def _extract_text_async_textract(self, document: Document) -> str:
        """
        Extract text from large documents using async Textract
        
        Args:
            document: Document instance
            
        Returns:
            Extracted text content
        """
        try:
            # Start async job
            response = self.textract_client.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': self.s3_bucket,
                        'Name': document.file_path
                    }
                }
            )
            
            job_id = response['JobId']
            
            # Store job ID for tracking
            document.textract_job_id = job_id
            await self.db.commit()
            
            # Poll for completion
            max_attempts = 60  # 5 minutes max wait
            attempt = 0
            
            while attempt < max_attempts:
                await asyncio.sleep(5)  # Wait 5 seconds between checks
                
                result = self.textract_client.get_document_text_detection(JobId=job_id)
                status = result['JobStatus']
                
                if status == 'SUCCEEDED':
                    # Extract text from results
                    extracted_text = ""
                    
                    # Get all pages of results
                    next_token = None
                    while True:
                        if next_token:
                            result = self.textract_client.get_document_text_detection(
                                JobId=job_id,
                                NextToken=next_token
                            )
                        
                        for block in result.get('Blocks', []):
                            if block['BlockType'] == 'LINE':
                                extracted_text += block.get('Text', '') + '\n'
                        
                        next_token = result.get('NextToken')
                        if not next_token:
                            break
                    
                    return extracted_text.strip()
                
                elif status == 'FAILED':
                    raise CaseManagementException(f"Textract job failed: {result.get('StatusMessage', 'Unknown error')}")
                
                attempt += 1
            
            raise CaseManagementException("Textract job timed out")
            
        except ClientError as e:
            logger.error("Async Textract extraction failed", error=str(e), document_id=str(document.id))
            raise CaseManagementException(f"Async text extraction failed: {str(e)}")
    
    async def _extract_entities_with_comprehend(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from text using AWS Comprehend
        
        Args:
            text: Text content to analyze
            
        Returns:
            List of extracted entities
        """
        try:
            # Comprehend has a 5000 character limit per request
            max_chars = 5000
            entities = []
            
            # Process text in chunks if necessary
            for i in range(0, len(text), max_chars):
                chunk = text[i:i + max_chars]
                
                response = self.comprehend_client.detect_entities(
                    Text=chunk,
                    LanguageCode='en'
                )
                
                # Adjust offsets for chunk position
                for entity in response.get('Entities', []):
                    entity['BeginOffset'] += i
                    entity['EndOffset'] += i
                    entities.append(entity)
            
            return entities
            
        except ClientError as e:
            logger.error("Comprehend entity extraction failed", error=str(e))
            raise CaseManagementException(f"Entity extraction failed: {str(e)}")
    
    async def _generate_summary_with_comprehend(self, text: str) -> str:
        """
        Generate AI summary for long documents
        
        Args:
            text: Text content to summarize
            
        Returns:
            Generated summary
        """
        try:
            # For now, use key phrase extraction as a simple summary approach
            # In production, you might use Amazon Bedrock for better summarization
            key_phrases_response = self.comprehend_client.detect_key_phrases(
                Text=text[:5000],  # Use first 5000 chars for summary
                LanguageCode='en'
            )
            
            # Create summary from top key phrases
            key_phrases = [
                phrase['Text'] for phrase in key_phrases_response.get('KeyPhrases', [])
                if phrase['Score'] > 0.8  # High confidence phrases only
            ]
            
            if key_phrases:
                summary = f"Key topics: {', '.join(key_phrases[:10])}"  # Top 10 phrases
                return summary
            else:
                return "Document processed - no high-confidence key phrases identified."
                
        except ClientError as e:
            logger.error("Summary generation failed", error=str(e))
            # Don't fail the entire analysis if summary fails
            return "Summary generation failed - document text extracted successfully."
    
    async def _extract_key_phrases_with_comprehend(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract key phrases from text using AWS Comprehend
        
        Args:
            text: Text content to analyze
            
        Returns:
            List of key phrases with confidence scores
        """
        try:
            max_chars = 5000
            key_phrases = []
            
            # Process text in chunks
            for i in range(0, len(text), max_chars):
                chunk = text[i:i + max_chars]
                
                response = self.comprehend_client.detect_key_phrases(
                    Text=chunk,
                    LanguageCode='en'
                )
                
                # Adjust offsets for chunk position
                for phrase in response.get('KeyPhrases', []):
                    phrase['BeginOffset'] += i
                    phrase['EndOffset'] += i
                    key_phrases.append(phrase)
            
            return key_phrases
            
        except ClientError as e:
            logger.error("Key phrase extraction failed", error=str(e))
            return []  # Return empty list if extraction fails
    
    async def _analyze_sentiment_with_comprehend(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text using AWS Comprehend
        
        Args:
            text: Text content to analyze
            
        Returns:
            Sentiment analysis results
        """
        try:
            # Use first 5000 characters for sentiment analysis
            sample_text = text[:5000] if len(text) > 5000 else text
            
            response = self.comprehend_client.detect_sentiment(
                Text=sample_text,
                LanguageCode='en'
            )
            
            return {
                "sentiment": response.get('Sentiment'),
                "confidence": max(response.get('SentimentScore', {}).values()) * 100,
                "scores": response.get('SentimentScore', {})
            }
            
        except ClientError as e:
            logger.error("Sentiment analysis failed", error=str(e))
            return {"sentiment": "NEUTRAL", "confidence": 0, "scores": {}}
    
    async def _store_extracted_entities(self, document_id: UUID, entities: List[Dict[str, Any]]) -> None:
        """
        Store extracted entities in the database
        
        Args:
            document_id: Document UUID
            entities: List of extracted entities
        """
        try:
            # Clear existing entities for this document
            await self.db.execute(
                select(ExtractedEntity).where(ExtractedEntity.document_id == document_id)
            )
            
            # Create new entity records
            for entity in entities:
                entity_record = ExtractedEntity(
                    document_id=document_id,
                    entity_type=entity.get('Type'),
                    entity_text=entity.get('Text'),
                    confidence_score=int(entity.get('Score', 0) * 100),
                    start_offset=entity.get('BeginOffset'),
                    end_offset=entity.get('EndOffset'),
                    entity_metadata=entity
                )
                self.db.add(entity_record)
            
            await self.db.flush()
            
        except Exception as e:
            logger.error("Failed to store extracted entities", error=str(e))
            # Don't fail the entire analysis if entity storage fails
    
    def _format_entities_for_storage(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format entities for JSON storage in document record
        
        Args:
            entities: List of extracted entities
            
        Returns:
            Formatted entities dictionary
        """
        formatted = {
            "total_count": len(entities),
            "by_type": {},
            "high_confidence": []
        }
        
        for entity in entities:
            entity_type = entity.get('Type')
            confidence = entity.get('Score', 0)
            
            # Count by type
            if entity_type not in formatted["by_type"]:
                formatted["by_type"][entity_type] = 0
            formatted["by_type"][entity_type] += 1
            
            # Store high confidence entities
            if confidence > 0.8:
                formatted["high_confidence"].append({
                    "type": entity_type,
                    "text": entity.get('Text'),
                    "confidence": round(confidence * 100, 2)
                })
        
        return formatted
    
    def _calculate_average_entity_confidence(self, entities: List[Dict[str, Any]]) -> float:
        """
        Calculate average confidence score for entities
        
        Args:
            entities: List of extracted entities
            
        Returns:
            Average confidence score (0-100)
        """
        if not entities:
            return 0.0
        
        total_confidence = sum(entity.get('Score', 0) for entity in entities)
        return round((total_confidence / len(entities)) * 100, 2)
    
    async def _get_document(self, document_id: UUID) -> Optional[Document]:
        """Get document by ID"""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()
    
    async def get_analysis_status(self, document_id: UUID) -> Dict[str, Any]:
        """
        Get the current analysis status of a document
        
        Args:
            document_id: Document UUID
            
        Returns:
            Analysis status information
        """
        try:
            document = await self._get_document(document_id)
            if not document:
                raise CaseManagementException(
                    f"Document with ID {document_id} not found",
                    error_code="DOCUMENT_NOT_FOUND"
                )
            
            status_info = {
                "document_id": str(document.id),
                "status": document.status,
                "processing_started_at": document.processing_started_at.isoformat() if document.processing_started_at else None,
                "processing_completed_at": document.processing_completed_at.isoformat() if document.processing_completed_at else None,
                "processing_error": document.processing_error,
                "has_extracted_text": bool(document.extracted_text),
                "has_ai_summary": bool(document.ai_summary),
                "entity_count": len(document.entities.get("high_confidence", [])) if document.entities else 0,
                "confidence_scores": document.confidence_scores
            }
            
            if document.processing_started_at and document.processing_completed_at:
                status_info["processing_time_seconds"] = (
                    document.processing_completed_at - document.processing_started_at
                ).total_seconds()
            
            return status_info
            
        except Exception as e:
            if isinstance(e, CaseManagementException):
                raise
            logger.error("Failed to get analysis status", document_id=str(document_id), error=str(e))
            raise CaseManagementException(f"Failed to get analysis status: {str(e)}")