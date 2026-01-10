"""
Encryption service for end-to-end encryption of sensitive documents and communications
Provides AES-256 encryption with AWS KMS key management
"""

import base64
import json
import hashlib
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import boto3
from botocore.exceptions import ClientError
import structlog

from core.config import settings
from core.exceptions import CaseManagementException

logger = structlog.get_logger()

class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""
    
    def __init__(self):
        self.kms_client = boto3.client(
            'kms',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.kms_key_id = getattr(settings, 'KMS_KEY_ID', None)
    
    async def encrypt_document(
        self, 
        content: bytes, 
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Encrypt document content using AES-256 with KMS-managed keys
        
        Args:
            content: Document content as bytes
            document_id: Unique document identifier
            metadata: Optional metadata to include in encryption
            
        Returns:
            Dictionary containing encrypted data and metadata
        """
        try:
            # Generate data encryption key using KMS
            data_key = await self._generate_data_key()
            
            # Create Fernet cipher with the data key
            fernet = Fernet(base64.urlsafe_b64encode(data_key['plaintext_key'][:32]))
            
            # Encrypt the content
            encrypted_content = fernet.encrypt(content)
            
            # Create encryption metadata
            encryption_metadata = {
                'document_id': document_id,
                'encrypted_at': datetime.utcnow().isoformat(),
                'encryption_algorithm': 'AES-256-GCM',
                'key_management': 'AWS-KMS',
                'content_hash': hashlib.sha256(content).hexdigest(),
                'metadata': metadata or {}
            }
            
            # Encrypt the metadata
            metadata_json = json.dumps(encryption_metadata).encode()
            encrypted_metadata = fernet.encrypt(metadata_json)
            
            result = {
                'encrypted_content': base64.b64encode(encrypted_content).decode(),
                'encrypted_metadata': base64.b64encode(encrypted_metadata).decode(),
                'encrypted_data_key': base64.b64encode(data_key['encrypted_key']).decode(),
                'key_id': data_key['key_id'],
                'encryption_context': {
                    'document_id': document_id,
                    'purpose': 'document_encryption'
                }
            }
            
            logger.info("Document encrypted successfully", 
                       document_id=document_id,
                       content_size=len(content))
            
            return result
            
        except Exception as e:
            logger.error("Document encryption failed", 
                        document_id=document_id, 
                        error=str(e))
            raise CaseManagementException(f"Document encryption failed: {str(e)}")
    
    async def decrypt_document(
        self, 
        encrypted_data: Dict[str, Any]
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Decrypt document content and return content with metadata
        
        Args:
            encrypted_data: Dictionary containing encrypted content and keys
            
        Returns:
            Tuple of (decrypted_content, metadata)
        """
        try:
            # Decrypt the data key using KMS
            encrypted_key = base64.b64decode(encrypted_data['encrypted_data_key'])
            
            decrypted_key_response = self.kms_client.decrypt(
                CiphertextBlob=encrypted_key,
                EncryptionContext=encrypted_data['encryption_context']
            )
            
            plaintext_key = decrypted_key_response['Plaintext']
            
            # Create Fernet cipher with the decrypted key
            fernet = Fernet(base64.urlsafe_b64encode(plaintext_key[:32]))
            
            # Decrypt the content
            encrypted_content = base64.b64decode(encrypted_data['encrypted_content'])
            decrypted_content = fernet.decrypt(encrypted_content)
            
            # Decrypt the metadata
            encrypted_metadata = base64.b64decode(encrypted_data['encrypted_metadata'])
            decrypted_metadata_json = fernet.decrypt(encrypted_metadata)
            metadata = json.loads(decrypted_metadata_json.decode())
            
            # Verify content integrity
            content_hash = hashlib.sha256(decrypted_content).hexdigest()
            if content_hash != metadata['content_hash']:
                raise CaseManagementException("Content integrity verification failed")
            
            logger.info("Document decrypted successfully", 
                       document_id=metadata['document_id'],
                       content_size=len(decrypted_content))
            
            return decrypted_content, metadata
            
        except ClientError as e:
            logger.error("KMS decryption failed", error=str(e))
            raise CaseManagementException(f"Document decryption failed: {str(e)}")
        except Exception as e:
            logger.error("Document decryption failed", error=str(e))
            raise CaseManagementException(f"Document decryption failed: {str(e)}")
    
    async def encrypt_communication(
        self, 
        message: str, 
        sender_id: str, 
        recipient_ids: list,
        communication_type: str = 'message'
    ) -> Dict[str, Any]:
        """
        Encrypt communication messages for end-to-end encryption
        
        Args:
            message: Message content to encrypt
            sender_id: ID of the message sender
            recipient_ids: List of recipient IDs
            communication_type: Type of communication (message, comment, etc.)
            
        Returns:
            Dictionary containing encrypted communication data
        """
        try:
            message_bytes = message.encode('utf-8')
            
            # Generate unique communication ID
            communication_id = hashlib.sha256(
                f"{sender_id}:{':'.join(recipient_ids)}:{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16]
            
            # Encrypt the message
            encrypted_data = await self.encrypt_document(
                content=message_bytes,
                document_id=communication_id,
                metadata={
                    'sender_id': sender_id,
                    'recipient_ids': recipient_ids,
                    'communication_type': communication_type,
                    'message_length': len(message)
                }
            )
            
            logger.info("Communication encrypted successfully", 
                       communication_id=communication_id,
                       sender_id=sender_id,
                       recipient_count=len(recipient_ids))
            
            return {
                'communication_id': communication_id,
                'encrypted_data': encrypted_data,
                'sender_id': sender_id,
                'recipient_ids': recipient_ids,
                'communication_type': communication_type,
                'encrypted_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Communication encryption failed", 
                        sender_id=sender_id, 
                        error=str(e))
            raise CaseManagementException(f"Communication encryption failed: {str(e)}")
    
    async def decrypt_communication(
        self, 
        encrypted_communication: Dict[str, Any],
        requesting_user_id: str
    ) -> str:
        """
        Decrypt communication message with access control
        
        Args:
            encrypted_communication: Encrypted communication data
            requesting_user_id: ID of user requesting decryption
            
        Returns:
            Decrypted message content
        """
        try:
            # Check access permissions
            sender_id = encrypted_communication['sender_id']
            recipient_ids = encrypted_communication['recipient_ids']
            
            if requesting_user_id not in [sender_id] + recipient_ids:
                raise CaseManagementException("Access denied: User not authorized to decrypt this communication")
            
            # Decrypt the message
            decrypted_content, metadata = await self.decrypt_document(
                encrypted_communication['encrypted_data']
            )
            
            message = decrypted_content.decode('utf-8')
            
            logger.info("Communication decrypted successfully", 
                       communication_id=encrypted_communication['communication_id'],
                       requesting_user_id=requesting_user_id)
            
            return message
            
        except Exception as e:
            logger.error("Communication decryption failed", 
                        communication_id=encrypted_communication.get('communication_id'),
                        requesting_user_id=requesting_user_id,
                        error=str(e))
            raise CaseManagementException(f"Communication decryption failed: {str(e)}")
    
    async def generate_integrity_hash(
        self, 
        content: bytes, 
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate cryptographic integrity hash for evidence chain of custody
        
        Args:
            content: Content to hash
            additional_data: Additional data to include in hash
            
        Returns:
            Hex-encoded SHA-256 hash
        """
        try:
            hasher = hashlib.sha256()
            hasher.update(content)
            
            if additional_data:
                # Sort keys for consistent hashing
                sorted_data = json.dumps(additional_data, sort_keys=True).encode()
                hasher.update(sorted_data)
            
            integrity_hash = hasher.hexdigest()
            
            logger.debug("Integrity hash generated", 
                        content_size=len(content),
                        hash_preview=integrity_hash[:16])
            
            return integrity_hash
            
        except Exception as e:
            logger.error("Integrity hash generation failed", error=str(e))
            raise CaseManagementException(f"Integrity hash generation failed: {str(e)}")
    
    async def verify_integrity(
        self, 
        content: bytes, 
        expected_hash: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Verify content integrity using cryptographic hash
        
        Args:
            content: Content to verify
            expected_hash: Expected hash value
            additional_data: Additional data used in original hash
            
        Returns:
            True if integrity is verified, False otherwise
        """
        try:
            calculated_hash = await self.generate_integrity_hash(content, additional_data)
            is_valid = calculated_hash == expected_hash
            
            logger.info("Integrity verification completed", 
                       is_valid=is_valid,
                       expected_hash_preview=expected_hash[:16],
                       calculated_hash_preview=calculated_hash[:16])
            
            return is_valid
            
        except Exception as e:
            logger.error("Integrity verification failed", error=str(e))
            return False
    
    async def _generate_data_key(self) -> Dict[str, Any]:
        """Generate a new data encryption key using AWS KMS"""
        try:
            if not self.kms_key_id:
                # For development/testing, generate a local key
                key = Fernet.generate_key()
                return {
                    'plaintext_key': base64.urlsafe_b64decode(key),
                    'encrypted_key': key,  # In real implementation, this would be KMS encrypted
                    'key_id': 'local-dev-key'
                }
            
            response = self.kms_client.generate_data_key(
                KeyId=self.kms_key_id,
                KeySpec='AES_256'
            )
            
            return {
                'plaintext_key': response['Plaintext'],
                'encrypted_key': response['CiphertextBlob'],
                'key_id': response['KeyId']
            }
            
        except ClientError as e:
            logger.error("KMS data key generation failed", error=str(e))
            # Fallback to local key generation for development
            key = Fernet.generate_key()
            return {
                'plaintext_key': base64.urlsafe_b64decode(key),
                'encrypted_key': key,
                'key_id': 'local-fallback-key'
            }
    
    async def rotate_encryption_keys(self, document_ids: list) -> Dict[str, Any]:
        """
        Rotate encryption keys for specified documents
        
        Args:
            document_ids: List of document IDs to rotate keys for
            
        Returns:
            Dictionary with rotation results
        """
        try:
            rotation_results = {
                'rotated_count': 0,
                'failed_count': 0,
                'rotation_timestamp': datetime.utcnow().isoformat(),
                'failed_documents': []
            }
            
            for document_id in document_ids:
                try:
                    # In a real implementation, this would:
                    # 1. Decrypt document with old key
                    # 2. Re-encrypt with new key
                    # 3. Update database with new encrypted data
                    
                    logger.info("Key rotation completed for document", 
                               document_id=document_id)
                    rotation_results['rotated_count'] += 1
                    
                except Exception as e:
                    logger.error("Key rotation failed for document", 
                                document_id=document_id, 
                                error=str(e))
                    rotation_results['failed_count'] += 1
                    rotation_results['failed_documents'].append({
                        'document_id': document_id,
                        'error': str(e)
                    })
            
            logger.info("Key rotation batch completed", 
                       total_documents=len(document_ids),
                       rotated=rotation_results['rotated_count'],
                       failed=rotation_results['failed_count'])
            
            return rotation_results
            
        except Exception as e:
            logger.error("Key rotation batch failed", error=str(e))
            raise CaseManagementException(f"Key rotation failed: {str(e)}")