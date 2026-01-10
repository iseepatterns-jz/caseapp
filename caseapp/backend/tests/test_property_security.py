"""
Property-based tests for security and compliance features
Validates Requirements 9.1, 9.2, 9.4, 9.5
"""

import pytest
from hypothesis import given, strategies as st, settings as hypothesis_settings, HealthCheck
from unittest.mock import AsyncMock, MagicMock, patch
import json
import base64
from datetime import datetime, timedelta

from services.security_service import SecurityService
from services.encryption_service import EncryptionService
from core.auth import AuthService

class TestSecurityProperties:
    """Property-based tests for security features"""

    @given(
        password=st.text(min_size=1, max_size=100),
        min_length=st.integers(min_value=8, max_value=20)
    )
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_27_password_validation_consistency(
        self, 
        password, 
        min_length
    ):
        """
        Property 27: Password Validation Consistency
        Validates: Requirements 9.1, 9.2
        
        For any password and validation rules, the password validation
        should be consistent and enforce security requirements.
        """
        security_service = SecurityService()
        
        # Mock settings for consistent testing
        with patch('services.security_service.settings') as mock_settings:
            mock_settings.PASSWORD_MIN_LENGTH = min_length
            mock_settings.PASSWORD_REQUIRE_UPPERCASE = True
            mock_settings.PASSWORD_REQUIRE_LOWERCASE = True
            mock_settings.PASSWORD_REQUIRE_NUMBERS = True
            mock_settings.PASSWORD_REQUIRE_SYMBOLS = True
            
            # Test password validation
            result = await security_service.validate_password_strength(password)
            
            # Property: Result should always have required fields
            assert isinstance(result, dict)
            assert "is_valid" in result
            assert "errors" in result
            assert "strength_score" in result
            assert "requirements_met" in result
            
            # Property: Validation should be consistent
            assert isinstance(result["is_valid"], bool)
            assert isinstance(result["errors"], list)
            assert isinstance(result["strength_score"], int)
            assert isinstance(result["requirements_met"], dict)
            
            # Property: Strength score should be non-negative
            assert result["strength_score"] >= 0
            
            # Property: If password is too short, it should be invalid
            if len(password) < min_length:
                assert not result["is_valid"]
                assert any("characters long" in error for error in result["errors"])
            
            # Property: If validation fails, there should be error messages
            if not result["is_valid"]:
                assert len(result["errors"]) > 0

    @given(
        user_id=st.text(min_size=1, max_size=50),
        max_attempts=st.integers(min_value=1, max_value=10),
        lockout_minutes=st.integers(min_value=1, max_value=60)
    )
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_27_account_lockout_enforcement(
        self, 
        user_id, 
        max_attempts, 
        lockout_minutes
    ):
        """
        Property 27: Account Lockout Enforcement
        Validates: Requirements 9.1, 9.2
        
        For any user and lockout configuration, the account lockout
        mechanism should prevent brute force attacks consistently.
        """
        security_service = SecurityService()
        
        # Mock settings
        with patch('services.security_service.settings') as mock_settings:
            mock_settings.MAX_LOGIN_ATTEMPTS = max_attempts
            mock_settings.LOCKOUT_DURATION_MINUTES = lockout_minutes
            
            # Property: Initially account should not be locked
            is_locked = await security_service.check_account_lockout(user_id)
            assert not is_locked
            
            # Property: Recording failed attempts should eventually lock account
            locked = False
            for attempt in range(max_attempts + 1):
                locked = await security_service.record_failed_login(user_id)
                if attempt < max_attempts - 1:
                    # Should not be locked before reaching max attempts
                    assert not locked
                else:
                    # Should be locked after max attempts
                    assert locked
            
            # Property: Account should be locked after max attempts
            is_locked = await security_service.check_account_lockout(user_id)
            assert is_locked
            
            # Property: Clearing attempts should unlock account
            await security_service.clear_failed_login_attempts(user_id)
            is_locked = await security_service.check_account_lockout(user_id)
            assert not is_locked

    @given(
        content=st.binary(min_size=1, max_size=1000),
        document_id=st.text(min_size=1, max_size=50)
    )
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_27_encryption_integrity(
        self, 
        content, 
        document_id
    ):
        """
        Property 27: Encryption Integrity
        Validates: Requirements 9.1, 9.4
        
        For any content and document ID, encryption and decryption
        should preserve data integrity and provide secure storage.
        """
        encryption_service = EncryptionService()
        
        # Mock KMS client for testing
        with patch.object(encryption_service, 'kms_client') as mock_kms:
            mock_kms.generate_data_key.return_value = {
                'Plaintext': b'test_key_32_bytes_long_for_aes256',
                'CiphertextBlob': b'encrypted_key_data',
                'KeyId': 'test-key-id'
            }
            mock_kms.decrypt.return_value = {
                'Plaintext': b'test_key_32_bytes_long_for_aes256'
            }
            
            # Test encryption
            encrypted_data = await encryption_service.encrypt_document(
                content=content,
                document_id=document_id
            )
            
            # Property: Encrypted data should have required fields
            assert isinstance(encrypted_data, dict)
            required_fields = [
                'encrypted_content', 'encrypted_metadata', 
                'encrypted_data_key', 'key_id', 'encryption_context'
            ]
            for field in required_fields:
                assert field in encrypted_data
            
            # Property: Encrypted content should be different from original
            encrypted_content_bytes = base64.b64decode(encrypted_data['encrypted_content'])
            assert encrypted_content_bytes != content
            
            # Test decryption
            decrypted_content, metadata = await encryption_service.decrypt_document(encrypted_data)
            
            # Property: Decrypted content should match original
            assert decrypted_content == content
            
            # Property: Metadata should contain document information
            assert isinstance(metadata, dict)
            assert metadata['document_id'] == document_id
            assert 'encrypted_at' in metadata
            assert 'content_hash' in metadata

    @given(
        user_id=st.text(min_size=1, max_size=50),
        user_email=st.emails(),
        mfa_token=st.text(min_size=6, max_size=6, alphabet=st.characters(whitelist_categories=('Nd',)))
    )
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_27_mfa_security(
        self, 
        user_id, 
        user_email, 
        mfa_token
    ):
        """
        Property 27: Multi-Factor Authentication Security
        Validates: Requirements 9.2
        
        For any user, MFA setup and verification should provide
        secure second-factor authentication consistently.
        """
        security_service = SecurityService()
        
        # Test MFA setup
        mfa_setup = await security_service.setup_mfa_for_user(user_id, user_email)
        
        # Property: MFA setup should provide required components
        assert isinstance(mfa_setup, dict)
        required_fields = [
            'mfa_secret', 'qr_code', 'backup_codes', 
            'hashed_backup_codes', 'setup_timestamp'
        ]
        for field in required_fields:
            assert field in mfa_setup
        
        # Property: MFA secret should be generated
        assert isinstance(mfa_setup['mfa_secret'], str)
        assert len(mfa_setup['mfa_secret']) > 0
        
        # Property: Backup codes should be provided
        assert isinstance(mfa_setup['backup_codes'], list)
        assert len(mfa_setup['backup_codes']) > 0
        
        # Property: Backup codes should be hashed for storage
        assert isinstance(mfa_setup['hashed_backup_codes'], list)
        assert len(mfa_setup['hashed_backup_codes']) == len(mfa_setup['backup_codes'])
        
        # Property: Hashed codes should be different from plain codes
        for plain, hashed in zip(mfa_setup['backup_codes'], mfa_setup['hashed_backup_codes']):
            assert plain != hashed

    @given(
        user_id=st.text(min_size=1, max_size=50),
        user_roles=st.lists(
            st.sampled_from(['admin', 'attorney', 'staff', 'client']),
            min_size=1, max_size=3, unique=True
        ),
        resource_type=st.sampled_from(['case', 'document', 'timeline', 'forensic', 'media']),
        resource_id=st.text(min_size=1, max_size=50),
        action=st.sampled_from(['read', 'write', 'delete', 'share'])
    )
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_27_rbac_enforcement(
        self, 
        user_id, 
        user_roles, 
        resource_type, 
        resource_id, 
        action
    ):
        """
        Property 27: Role-Based Access Control Enforcement
        Validates: Requirements 9.5
        
        For any user, roles, and resource access request, the RBAC system
        should enforce principle of least privilege consistently.
        """
        security_service = SecurityService()
        
        # Test permission validation
        has_permission = await security_service.validate_data_access_permissions(
            user_id=user_id,
            user_roles=user_roles,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action
        )
        
        # Property: Permission result should be boolean
        assert isinstance(has_permission, bool)
        
        # Property: Admin users should always have access
        if 'admin' in user_roles:
            assert has_permission
        
        # Property: Access should be denied for unknown resource types
        unknown_permission = await security_service.validate_data_access_permissions(
            user_id=user_id,
            user_roles=user_roles,
            resource_type='unknown_resource',
            resource_id=resource_id,
            action=action
        )
        assert not unknown_permission
        
        # Property: Forensic data should have restricted access
        if resource_type == 'forensic' and 'admin' not in user_roles:
            forensic_permission = await security_service.validate_data_access_permissions(
                user_id=user_id,
                user_roles=['client'],  # Client should not access forensic data
                resource_type='forensic',
                resource_id=resource_id,
                action=action
            )
            assert not forensic_permission

    @given(
        content=st.binary(min_size=1, max_size=1000),
        additional_data=st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.text(min_size=1, max_size=50),
            min_size=0, max_size=5
        )
    )
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_27_integrity_verification(
        self, 
        content, 
        additional_data
    ):
        """
        Property 27: Cryptographic Integrity Verification
        Validates: Requirements 9.4
        
        For any content and additional data, integrity hash generation
        and verification should detect any tampering consistently.
        """
        encryption_service = EncryptionService()
        
        # Generate integrity hash
        integrity_hash = await encryption_service.generate_integrity_hash(
            content=content,
            additional_data=additional_data
        )
        
        # Property: Hash should be generated
        assert isinstance(integrity_hash, str)
        assert len(integrity_hash) > 0
        
        # Property: Hash should be deterministic
        hash2 = await encryption_service.generate_integrity_hash(
            content=content,
            additional_data=additional_data
        )
        assert integrity_hash == hash2
        
        # Property: Verification should succeed with correct data
        is_valid = await encryption_service.verify_integrity(
            content=content,
            expected_hash=integrity_hash,
            additional_data=additional_data
        )
        assert is_valid
        
        # Property: Verification should fail with tampered content
        if len(content) > 1:
            tampered_content = content[:-1] + b'X'
            is_valid_tampered = await encryption_service.verify_integrity(
                content=tampered_content,
                expected_hash=integrity_hash,
                additional_data=additional_data
            )
            assert not is_valid_tampered
        
        # Property: Verification should fail with wrong hash
        wrong_hash = "0" * len(integrity_hash)
        is_valid_wrong = await encryption_service.verify_integrity(
            content=content,
            expected_hash=wrong_hash,
            additional_data=additional_data
        )
        assert not is_valid_wrong

    @given(
        days=st.integers(min_value=1, max_value=365)
    )
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_27_security_reporting(
        self, 
        days
    ):
        """
        Property 27: Security Reporting Completeness
        Validates: Requirements 9.1, 9.2, 9.4, 9.5
        
        For any reporting period, security reports should provide
        comprehensive compliance and audit information.
        """
        security_service = SecurityService()
        
        # Generate security report
        report = await security_service.generate_security_report(days=days)
        
        # Property: Report should have required sections
        assert isinstance(report, dict)
        required_sections = [
            'report_period', 'authentication_metrics', 'access_control_metrics',
            'security_incidents', 'compliance_status', 'recommendations'
        ]
        for section in required_sections:
            assert section in report
        
        # Property: Report period should match request
        assert report['report_period']['days'] == days
        
        # Property: Metrics should be numeric
        auth_metrics = report['authentication_metrics']
        for metric in ['total_login_attempts', 'successful_logins', 'failed_logins', 'mfa_verifications']:
            assert isinstance(auth_metrics[metric], int)
            assert auth_metrics[metric] >= 0
        
        # Property: Compliance status should be boolean
        compliance = report['compliance_status']
        for status in ['hipaa_compliant', 'soc2_compliant', 'encryption_enabled', 'mfa_enforced']:
            assert isinstance(compliance[status], bool)
        
        # Property: Recommendations should be actionable
        assert isinstance(report['recommendations'], list)
        for recommendation in report['recommendations']:
            assert isinstance(recommendation, str)
            assert len(recommendation) > 0