"""
AWS Services Integration
"""

import boto3
import structlog
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError

from core.config import settings

logger = structlog.get_logger()

class AWSService:
    """Central AWS service manager"""
    
    def __init__(self):
        self.textract_client: Optional[boto3.client] = None
        self.comprehend_client: Optional[boto3.client] = None
        self.bedrock_client: Optional[boto3.client] = None
        self.transcribe_client: Optional[boto3.client] = None
        self.s3_client: Optional[boto3.client] = None
        self.kms_client: Optional[boto3.client] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all AWS service clients"""
        try:
            # Configure AWS session
            session_kwargs = {
                'region_name': settings.AWS_REGION
            }
            
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                session_kwargs.update({
                    'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY
                })
            
            session = boto3.Session(**session_kwargs)
            
            # Initialize service clients
            self.textract_client = session.client('textract')
            self.comprehend_client = session.client('comprehend')
            self.bedrock_client = session.client('bedrock-runtime')
            self.transcribe_client = session.client('transcribe')
            self.s3_client = session.client('s3')
            self.kms_client = session.client('kms')
            
            # Test connectivity
            await self._test_connectivity()
            
            self._initialized = True
            logger.info("AWS services initialized successfully")
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except Exception as e:
            logger.error("Failed to initialize AWS services", error=str(e))
            raise
    
    async def _test_connectivity(self) -> None:
        """Test connectivity to AWS services"""
        try:
            # Test S3 connectivity
            if self.s3_client:
                self.s3_client.list_buckets()
            
            # Test other services with simple calls
            if self.textract_client:
                self.textract_client.describe_document_text_detection(JobId="test")
            
        except ClientError as e:
            # Expected for test calls, just checking connectivity
            if e.response['Error']['Code'] not in ['InvalidJobIdException', 'AccessDenied']:
                raise
        except Exception as e:
            logger.warning("AWS service connectivity test failed", error=str(e))
    
    def get_textract_client(self) -> boto3.client:
        """Get Textract client"""
        if not self._initialized or not self.textract_client:
            raise RuntimeError("AWS services not initialized")
        return self.textract_client
    
    def get_comprehend_client(self) -> boto3.client:
        """Get Comprehend client"""
        if not self._initialized or not self.comprehend_client:
            raise RuntimeError("AWS services not initialized")
        return self.comprehend_client
    
    def get_bedrock_client(self) -> boto3.client:
        """Get Bedrock client"""
        if not self._initialized or not self.bedrock_client:
            raise RuntimeError("AWS services not initialized")
        return self.bedrock_client
    
    def get_transcribe_client(self) -> boto3.client:
        """Get Transcribe client"""
        if not self._initialized or not self.transcribe_client:
            raise RuntimeError("AWS services not initialized")
        return self.transcribe_client
    
    def get_s3_client(self) -> boto3.client:
        """Get S3 client"""
        if not self._initialized or not self.s3_client:
            raise RuntimeError("AWS services not initialized")
        return self.s3_client
    
    def get_kms_client(self) -> boto3.client:
        """Get KMS client"""
        if not self._initialized or not self.kms_client:
            raise RuntimeError("AWS services not initialized")
        return self.kms_client

# Global AWS service instance
aws_service = AWSService()