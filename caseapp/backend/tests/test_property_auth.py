"""
Property-based tests for authentication system
Feature: court-case-management-system, Property 28: Multi-Factor Authentication
"""


import pytest
from hypothesis import given, strategies as st, settings
import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.auth import AuthService

# Test data strategies
@st.composite
def user_credentials(draw):
    """Generate user credentials for testing"""
    username = draw(st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    roles = draw(st.lists(st.sampled_from(['admin', 'attorney', 'staff', 'client']), min_size=1, max_size=3))
    return {
        'username': username,
        'roles': roles
    }

@st.composite
def valid_passwords(draw):
    """Generate valid passwords (no null bytes)"""
    return draw(st.text(min_size=8, max_size=16, alphabet=st.characters(blacklist_characters='\x00', blacklist_categories=('Cs',))))

class TestMultiFactorAuthentication:
    """Property tests for multi-factor authentication"""
    
    @given(credentials=user_credentials())
    @settings(deadline=1000, max_examples=20)  # Increase deadline for slower operations
    def test_mfa_token_structure_property(self, credentials):
        """
        Property 28: Multi-Factor Authentication
        For any system access attempt, the authentication token should contain
        MFA-related fields that can be used to enforce MFA policies.
        Validates: Requirements 9.2
        """
        # Create token with MFA fields
        token_data = {
            'sub': credentials['username'],
            'roles': credentials['roles'],
            'mfa_completed': False,
            'mfa_required': True
        }
        
        token = AuthService.create_access_token(token_data)
        token = AuthService.create_access_token(token_data)
        decoded = asyncio.run(AuthService.verify_token(token))
        
        # Verify MFA fields are preserved in token
        assert decoded['sub'] == credentials['username']
        assert decoded['roles'] == credentials['roles']
        assert 'mfa_completed' in decoded or 'mfa_required' in decoded
        
        # Test MFA completion token
        mfa_completed_data = token_data.copy()
        mfa_completed_data['mfa_completed'] = True
        mfa_token = AuthService.create_access_token(mfa_completed_data)
        
        mfa_token = AuthService.create_access_token(mfa_completed_data)
        
        decoded_mfa = asyncio.run(AuthService.verify_token(mfa_token))
        assert decoded_mfa['sub'] == credentials['username']
    
    @given(credentials=user_credentials())
    @settings(deadline=1000)
    def test_token_creation_property(self, credentials):
        """
        Property: Token creation preserves user data
        For any valid user credentials, creating a token should preserve 
        the user identity and roles in the token payload.
        """
        token_data = {
            'sub': credentials['username'],
            'roles': credentials['roles']
        }
        
        token = AuthService.create_access_token(token_data)
        token = AuthService.create_access_token(token_data)
        decoded = asyncio.run(AuthService.verify_token(token))
        
        # Verify data preservation
        assert decoded['sub'] == credentials['username']
        assert decoded['roles'] == credentials['roles']
        assert 'exp' in decoded  # Expiration should be set
    
    @given(password=valid_passwords())
    @settings(deadline=2000, max_examples=10)  # Password hashing can be slow
    def test_password_hashing_property(self, password):
        """
        Property: Password hashing round-trip
        For any password, hashing then verifying should return True,
        and the hash should be different from the original password.
        """
        hashed = AuthService.get_password_hash(password)
        
        # Hash should be different from original
        assert hashed != password
        
        # Verification should succeed
        assert AuthService.verify_password(password, hashed) == True
        
        # Wrong password should fail (if we can create a different one)
        if len(password) > 1:
            wrong_password = password[:-1] + ('x' if password[-1] != 'x' else 'y')
            assert AuthService.verify_password(wrong_password, hashed) == False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])