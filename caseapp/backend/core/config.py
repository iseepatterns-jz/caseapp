"""
Application configuration settings
"""

from pydantic_settings import BaseSettings
from typing import List, Optional, Dict
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Court Case Management System"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    
    # API
    API_V1_STR: str = "/api/v1"
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Database - Individual components for RDS secret compatibility
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_USER: str = "user"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "courtcase_db"
    
    # Constructed DATABASE_URL from individual components
    @property
    def DATABASE_URL(self) -> str:
        """Construct PostgreSQL connection URL from individual components"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    
    # S3 Configuration
    S3_BUCKET_NAME: str = "court-case-documents"
    S3_BUCKET_REGION: str = "us-east-1"
    
    # Textract Configuration
    TEXTRACT_ROLE_ARN: Optional[str] = None
    
    # Comprehend Configuration
    COMPREHEND_ENDPOINT: Optional[str] = None
    
    # OpenSearch Configuration
    OPENSEARCH_ENDPOINT: Optional[str] = None
    OPENSEARCH_USERNAME: Optional[str] = None
    OPENSEARCH_PASSWORD: Optional[str] = None
    
    # Cognito Configuration
    COGNITO_USER_POOL_ID: Optional[str] = None
    COGNITO_CLIENT_ID: Optional[str] = None
    COGNITO_CLIENT_SECRET: Optional[str] = None
    
    # JWT Configuration
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Security Configuration
    MFA_REQUIRED: bool = True
    MFA_ISSUER_NAME: str = "iseepatterns"
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SYMBOLS: bool = True
    SESSION_TIMEOUT_MINUTES: int = 60
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30
    
    # Encryption Configuration
    KMS_KEY_ID: Optional[str] = None
    ENCRYPTION_ALGORITHM: str = "AES-256-GCM"
    KEY_ROTATION_DAYS: int = 90
    
    # Compliance Configuration
    AUDIT_LOG_RETENTION_DAYS: int = 2555  # 7 years for legal compliance
    DATA_RETENTION_YEARS: int = 7
    HIPAA_COMPLIANCE: bool = True
    SOC2_COMPLIANCE: bool = True
    
    # Security Headers
    SECURITY_HEADERS: Dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
    
    # Document Processing
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_FILE_TYPES: List[str] = [".pdf", ".docx", ".doc", ".txt"]
    
    # AI Configuration
    ENABLE_AI_FEATURES: bool = True
    CASE_CATEGORIZATION_MODEL: str = "amazon.titan-text-express-v1"
    
    # Court Integration
    COURT_EFILING_API_URL: Optional[str] = None
    COURT_EFILING_API_KEY: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get application settings"""
    return settings