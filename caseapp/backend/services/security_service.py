"""
Comprehensive security service for authentication, authorization, and compliance
"""

import re
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from fastapi import HTTPException, status
import structlog

from core.config import settings
from core.auth import AuthService
from services.encryption_service import EncryptionService

logger = structlog.get_logger()

class SecurityService:
    """Comprehensive security service"""
    
    def __init__(self):
        self.auth_service = AuthService()
        self.encryption_service = EncryptionService()
        self.failed_login_attempts: Dict[str, List[datetime]] = {}
        self.locked_accounts: Dict[str, datetime] = {}
    
    async def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """
        Validate password against security requirements
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "is_valid": True,
            "errors": [],
            "strength_score": 0,
            "requirements_met": {}
        }
        
        # Check minimum length
        if len(password) < settings.PASSWORD_MIN_LENGTH:
            validation_result["errors"].append(
                f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
            )
            validation_result["is_valid"] = False
        else:
            validation_result["requirements_met"]["min_length"] = True
            validation_result["strength_score"] += 20
        
        # Check uppercase requirement
        if settings.PASSWORD_REQUIRE_UPPERCASE:
            if not re.search(r'[A-Z]', password):
                validation_result["errors"].append("Password must contain at least one uppercase letter")
                validation_result["is_valid"] = False
            else:
                validation_result["requirements_met"]["uppercase"] = True
                validation_result["strength_score"] += 20
        
        # Check lowercase requirement
        if settings.PASSWORD_REQUIRE_LOWERCASE:
            if not re.search(r'[a-z]', password):
                validation_result["errors"].append("Password must contain at least one lowercase letter")
                validation_result["is_valid"] = False
            else:
                validation_result["requirements_met"]["lowercase"] = True
                validation_result["strength_score"] += 20
        
        # Check numbers requirement
        if settings.PASSWORD_REQUIRE_NUMBERS:
            if not re.search(r'\d', password):
                validation_result["errors"].append("Password must contain at least one number")
                validation_result["is_valid"] = False
            else:
                validation_result["requirements_met"]["numbers"] = True
                validation_result["strength_score"] += 20
        
        # Check symbols requirement
        if settings.PASSWORD_REQUIRE_SYMBOLS:
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                validation_result["errors"].append("Password must contain at least one special character")
                validation_result["is_valid"] = False
            else:
                validation_result["requirements_met"]["symbols"] = True
                validation_result["strength_score"] += 20
        
        # Check for common patterns
        common_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'admin',
            r'letmein'
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, password.lower()):
                validation_result["errors"].append("Password contains common patterns")
                validation_result["is_valid"] = False
                validation_result["strength_score"] -= 30
                break
        
        # Ensure minimum score
        validation_result["strength_score"] = max(0, validation_result["strength_score"])
        
        logger.info("Password validation completed", 
                   is_valid=validation_result["is_valid"],
                   strength_score=validation_result["strength_score"])
        
        return validation_result
    
    async def check_account_lockout(self, user_id: str) -> bool:
        """
        Check if account is locked due to failed login attempts
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if account is locked, False otherwise
        """
        # Check if account is currently locked
        if user_id in self.locked_accounts:
            lockout_time = self.locked_accounts[user_id]
            lockout_duration = timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
            
            if datetime.utcnow() < lockout_time + lockout_duration:
                logger.warning("Account access attempted while locked", user_id=user_id)
                return True
            else:
                # Lockout period expired, remove from locked accounts
                del self.locked_accounts[user_id]
                if user_id in self.failed_login_attempts:
                    del self.failed_login_attempts[user_id]
        
        return False
    
    async def record_failed_login(self, user_id: str) -> bool:
        """
        Record failed login attempt and check if account should be locked
        
        Args:
            user_id: User ID for failed login
            
        Returns:
            True if account is now locked, False otherwise
        """
        now = datetime.utcnow()
        
        # Initialize failed attempts list if not exists
        if user_id not in self.failed_login_attempts:
            self.failed_login_attempts[user_id] = []
        
        # Add current failed attempt
        self.failed_login_attempts[user_id].append(now)
        
        # Clean old attempts (older than lockout window)
        window_start = now - timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
        self.failed_login_attempts[user_id] = [
            attempt for attempt in self.failed_login_attempts[user_id]
            if attempt > window_start
        ]
        
        # Check if max attempts exceeded
        if len(self.failed_login_attempts[user_id]) >= settings.MAX_LOGIN_ATTEMPTS:
            self.locked_accounts[user_id] = now
            logger.warning("Account locked due to failed login attempts", 
                          user_id=user_id,
                          attempt_count=len(self.failed_login_attempts[user_id]))
            return True
        
        logger.info("Failed login recorded", 
                   user_id=user_id,
                   attempt_count=len(self.failed_login_attempts[user_id]))
        return False
    
    async def clear_failed_login_attempts(self, user_id: str):
        """Clear failed login attempts after successful login"""
        if user_id in self.failed_login_attempts:
            del self.failed_login_attempts[user_id]
        
        if user_id in self.locked_accounts:
            del self.locked_accounts[user_id]
        
        logger.info("Failed login attempts cleared", user_id=user_id)
    
    async def setup_mfa_for_user(self, user_id: str, user_email: str) -> Dict[str, Any]:
        """
        Set up multi-factor authentication for a user
        
        Args:
            user_id: User ID
            user_email: User email for QR code generation
            
        Returns:
            Dictionary with MFA setup data
        """
        try:
            # Generate MFA secret
            mfa_secret = self.auth_service.generate_mfa_secret()
            
            # Generate QR code
            qr_code = self.auth_service.generate_qr_code(user_email, mfa_secret)
            
            # Generate backup codes
            backup_codes = self.auth_service.generate_backup_codes()
            hashed_backup_codes = self.auth_service.hash_backup_codes(backup_codes)
            
            setup_data = {
                "mfa_secret": mfa_secret,
                "qr_code": qr_code,
                "backup_codes": backup_codes,
                "hashed_backup_codes": hashed_backup_codes,
                "setup_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info("MFA setup completed", user_id=user_id, user_email=user_email)
            return setup_data
            
        except Exception as e:
            logger.error("MFA setup failed", user_id=user_id, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MFA setup failed"
            )
    
    async def verify_mfa_login(
        self, 
        user_id: str, 
        mfa_secret: str, 
        mfa_token: str,
        backup_codes: Optional[List[str]] = None
    ) -> bool:
        """
        Verify MFA token or backup code during login
        
        Args:
            user_id: User ID
            mfa_secret: User's MFA secret
            mfa_token: TOTP token or backup code
            backup_codes: List of hashed backup codes
            
        Returns:
            True if verification successful, False otherwise
        """
        try:
            # First try TOTP verification
            if self.auth_service.verify_mfa_token(mfa_secret, mfa_token):
                logger.info("MFA TOTP verification successful", user_id=user_id)
                return True
            
            # If TOTP fails, try backup codes
            if backup_codes and self.auth_service.verify_backup_code(mfa_token, backup_codes):
                logger.info("MFA backup code verification successful", user_id=user_id)
                # In a real implementation, you would mark this backup code as used
                return True
            
            logger.warning("MFA verification failed", user_id=user_id)
            return False
            
        except Exception as e:
            logger.error("MFA verification error", user_id=user_id, error=str(e))
            return False
    
    async def create_secure_session(
        self, 
        user_id: str, 
        user_roles: List[str],
        mfa_verified: bool = False
    ) -> Dict[str, Any]:
        """
        Create secure session with proper token and metadata
        
        Args:
            user_id: User ID
            user_roles: User roles
            mfa_verified: Whether MFA was verified
            
        Returns:
            Dictionary with session data
        """
        try:
            # Create token data
            token_data = {
                "sub": user_id,
                "roles": user_roles,
                "mfa_verified": mfa_verified,
                "mfa_required": settings.MFA_REQUIRED,
                "session_id": secrets.token_hex(16),
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Create access token
            access_token = self.auth_service.create_access_token(
                data=token_data,
                expires_delta=timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
            )
            
            session_data = {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.SESSION_TIMEOUT_MINUTES * 60,
                "session_id": token_data["session_id"],
                "mfa_verified": mfa_verified,
                "created_at": token_data["created_at"]
            }
            
            logger.info("Secure session created", 
                       user_id=user_id,
                       session_id=token_data["session_id"],
                       mfa_verified=mfa_verified)
            
            return session_data
            
        except Exception as e:
            logger.error("Session creation failed", user_id=user_id, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Session creation failed"
            )
    
    async def validate_data_access_permissions(
        self, 
        user_id: str, 
        user_roles: List[str],
        resource_type: str,
        resource_id: str,
        action: str
    ) -> bool:
        """
        Validate user permissions for data access with principle of least privilege
        
        Args:
            user_id: User ID
            user_roles: User roles
            resource_type: Type of resource (case, document, etc.)
            resource_id: ID of specific resource
            action: Action being performed (read, write, delete, share)
            
        Returns:
            True if access is allowed, False otherwise
        """
        try:
            # Admin users have full access
            if "admin" in user_roles:
                logger.info("Admin access granted", 
                           user_id=user_id, 
                           resource_type=resource_type,
                           resource_id=resource_id,
                           action=action)
                return True
            
            # Define permission matrix
            permission_matrix = {
                "case": {
                    "read": ["attorney", "staff"],
                    "write": ["attorney"],
                    "delete": [],
                    "share": ["attorney"]
                },
                "document": {
                    "read": ["attorney", "staff"],
                    "write": ["attorney", "staff"],
                    "delete": ["attorney"],
                    "share": ["attorney"]
                },
                "timeline": {
                    "read": ["attorney", "staff"],
                    "write": ["attorney", "staff"],
                    "delete": ["attorney"],
                    "share": ["attorney"]
                },
                "forensic": {
                    "read": ["attorney"],
                    "write": ["attorney"],
                    "delete": [],
                    "share": []
                },
                "media": {
                    "read": ["attorney", "staff"],
                    "write": ["attorney", "staff"],
                    "delete": ["attorney"],
                    "share": ["attorney"]
                }
            }
            
            # Check if resource type and action are defined
            if resource_type not in permission_matrix:
                logger.warning("Unknown resource type", 
                              resource_type=resource_type,
                              user_id=user_id)
                return False
            
            if action not in permission_matrix[resource_type]:
                logger.warning("Unknown action", 
                              action=action,
                              resource_type=resource_type,
                              user_id=user_id)
                return False
            
            # Check if user has required role
            required_roles = permission_matrix[resource_type][action]
            has_permission = any(role in user_roles for role in required_roles)
            
            if has_permission:
                logger.info("Data access granted", 
                           user_id=user_id,
                           resource_type=resource_type,
                           resource_id=resource_id,
                           action=action,
                           user_roles=user_roles)
            else:
                logger.warning("Data access denied", 
                              user_id=user_id,
                              resource_type=resource_type,
                              resource_id=resource_id,
                              action=action,
                              user_roles=user_roles,
                              required_roles=required_roles)
            
            return has_permission
            
        except Exception as e:
            logger.error("Permission validation error", 
                        user_id=user_id,
                        resource_type=resource_type,
                        error=str(e))
            return False
    
    async def generate_security_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate security report for compliance auditing
        
        Args:
            days: Number of days to include in report
            
        Returns:
            Dictionary with security metrics
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # In a real implementation, this would query audit logs from database
            security_report = {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days
                },
                "authentication_metrics": {
                    "total_login_attempts": 0,  # Would be queried from audit logs
                    "successful_logins": 0,
                    "failed_logins": 0,
                    "mfa_verifications": 0,
                    "account_lockouts": len(self.locked_accounts)
                },
                "access_control_metrics": {
                    "permission_denials": 0,  # Would be queried from audit logs
                    "privilege_escalation_attempts": 0,
                    "data_access_events": 0
                },
                "security_incidents": {
                    "suspicious_activities": 0,  # Would be analyzed from logs
                    "rate_limit_violations": 0,
                    "integrity_violations": 0
                },
                "compliance_status": {
                    "hipaa_compliant": settings.HIPAA_COMPLIANCE,
                    "soc2_compliant": settings.SOC2_COMPLIANCE,
                    "encryption_enabled": True,
                    "mfa_enforced": settings.MFA_REQUIRED
                },
                "recommendations": []
            }
            
            # Add recommendations based on metrics
            if security_report["authentication_metrics"]["account_lockouts"] > 10:
                security_report["recommendations"].append(
                    "High number of account lockouts detected. Consider reviewing password policies."
                )
            
            if not settings.MFA_REQUIRED:
                security_report["recommendations"].append(
                    "Multi-factor authentication is not enforced. Enable MFA for enhanced security."
                )
            
            logger.info("Security report generated", 
                       report_period_days=days,
                       lockouts=security_report["authentication_metrics"]["account_lockouts"])
            
            return security_report
            
        except Exception as e:
            logger.error("Security report generation failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Security report generation failed"
            )