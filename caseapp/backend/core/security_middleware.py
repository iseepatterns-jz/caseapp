"""
Security middleware for HIPAA and SOC 2 compliance
"""

import time
import json
from typing import Dict, Any, Optional
from datetime import datetime, UTC, timedelta
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import structlog
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

logger = structlog.get_logger()

class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for security headers and compliance controls"""
    
    def __init__(self, app):
        super().__init__(app)
        self.failed_attempts: Dict[str, Dict[str, Any]] = {}
        self.session_tracking: Dict[str, datetime] = {}
    
    async def dispatch(self, request: Request, call_next):
        """Process request with security controls"""
        start_time = time.time()
        
        # Add security headers
        response = await call_next(request)
        self._add_security_headers(response)
        
        # Log request for compliance
        await self._log_request_for_compliance(request, response, start_time)
        
        return response
    
    def _add_security_headers(self, response: Response):
        """Add security headers for compliance"""
        for header, value in settings.SECURITY_HEADERS.items():
            response.headers[header] = value
    
    async def _log_request_for_compliance(
        self, 
        request: Request, 
        response: Response, 
        start_time: float
    ):
        """Log requests for HIPAA and SOC 2 compliance"""
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        processing_time = time.time() - start_time
        
        # Extract user ID from authorization header if present
        user_id = None
        auth_header = request.headers.get("authorization")
        if auth_header:
            try:
                from core.auth import AuthService
                token = auth_header.replace("Bearer ", "")
                payload = AuthService.verify_token(token)
                user_id = payload.get("sub")
            except:
                pass  # Token validation will be handled by auth middleware
        
        compliance_log = {
            "event_type": "api_request",
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "processing_time_ms": round(processing_time * 1000, 2),
            "request_size": request.headers.get("content-length", 0),
            "response_size": response.headers.get("content-length", 0)
        }
        
        # Log sensitive data access
        if self._is_sensitive_endpoint(request.url.path):
            compliance_log["data_classification"] = "sensitive"
            compliance_log["compliance_flags"] = ["HIPAA", "SOC2"]
        
        logger.info("Compliance request log", **compliance_log)
    
    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint handles sensitive data"""
        sensitive_patterns = [
            "/api/v1/cases",
            "/api/v1/documents",
            "/api/v1/media",
            "/api/v1/forensic",
            "/api/v1/timeline",
            "/api/v1/collaboration"
        ]
        
        return any(pattern in path for pattern in sensitive_patterns)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for security"""
    
    def __init__(self, app):
        super().__init__(app)
        self.request_counts: Dict[str, Dict[str, Any]] = {}
        self.rate_limits = {
            "default": {"requests": 100, "window": 60},  # 100 requests per minute
            "auth": {"requests": 10, "window": 60},      # 10 auth attempts per minute
            "upload": {"requests": 20, "window": 60}     # 20 uploads per minute
        }
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting"""
        client_ip = request.client.host if request.client else "unknown"
        
        # Determine rate limit category
        limit_category = self._get_rate_limit_category(request.url.path)
        
        # Check rate limit
        if not self._check_rate_limit(client_ip, limit_category):
            logger.warning("Rate limit exceeded", 
                          client_ip=client_ip, 
                          category=limit_category,
                          path=request.url.path)
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )
        
        return await call_next(request)
    
    def _get_rate_limit_category(self, path: str) -> str:
        """Determine rate limit category based on path"""
        if "/auth" in path or "/login" in path:
            return "auth"
        elif "/upload" in path or "/media" in path:
            return "upload"
        else:
            return "default"
    
    def _check_rate_limit(self, client_ip: str, category: str) -> bool:
        """Check if request is within rate limit"""
        now = datetime.now(UTC)
        limit_config = self.rate_limits[category]
        window_start = now - timedelta(seconds=limit_config["window"])
        
        # Initialize tracking for new IPs
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = {}
        
        if category not in self.request_counts[client_ip]:
            self.request_counts[client_ip][category] = []
        
        # Clean old requests outside the window
        self.request_counts[client_ip][category] = [
            req_time for req_time in self.request_counts[client_ip][category]
            if req_time > window_start
        ]
        
        # Check if within limit
        current_count = len(self.request_counts[client_ip][category])
        if current_count >= limit_config["requests"]:
            return False
        
        # Add current request
        self.request_counts[client_ip][category].append(now)
        return True

class DataClassificationMiddleware(BaseHTTPMiddleware):
    """Middleware for data classification and handling"""
    
    def __init__(self, app):
        super().__init__(app)
        self.data_classifications = {
            "public": ["health", "status"],
            "internal": ["cases", "users", "audit"],
            "confidential": ["documents", "timeline", "collaboration"],
            "restricted": ["forensic", "media", "ai-insights"]
        }
    
    async def dispatch(self, request: Request, call_next):
        """Apply data classification controls"""
        # Classify the data being accessed
        classification = self._classify_request(request.url.path)
        
        # Add classification header to response
        response = await call_next(request)
        response.headers["X-Data-Classification"] = classification
        
        # Log data access with classification
        if classification in ["confidential", "restricted"]:
            await self._log_sensitive_data_access(request, classification)
        
        return response
    
    def _classify_request(self, path: str) -> str:
        """Classify request based on endpoint"""
        for classification, patterns in self.data_classifications.items():
            if any(pattern in path for pattern in patterns):
                return classification
        return "internal"
    
    async def _log_sensitive_data_access(self, request: Request, classification: str):
        """Log access to sensitive data for compliance"""
        client_ip = request.client.host if request.client else "unknown"
        
        sensitive_access_log = {
            "event_type": "sensitive_data_access",
            "timestamp": datetime.now(UTC).isoformat(),
            "client_ip": client_ip,
            "path": request.url.path,
            "method": request.method,
            "data_classification": classification,
            "compliance_requirement": "HIPAA_SOC2"
        }
        
        logger.warning("Sensitive data access", **sensitive_access_log)

class ComplianceAuditMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive compliance auditing"""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Audit requests for compliance requirements"""
        # Process request
        response = await call_next(request)
        
        # Audit based on compliance requirements
        await self._audit_for_hipaa(request, response)
        await self._audit_for_soc2(request, response)
        
        return response
    
    async def _audit_for_hipaa(self, request: Request, response: Response):
        """HIPAA compliance auditing"""
        if not settings.HIPAA_COMPLIANCE:
            return
        
        # Check for PHI access patterns
        phi_indicators = ["patient", "medical", "health", "diagnosis", "treatment"]
        request_body = await self._get_request_body(request)
        
        contains_phi = any(
            indicator in str(request.url).lower() or 
            indicator in str(request_body).lower()
            for indicator in phi_indicators
        )
        
        if contains_phi:
            hipaa_audit = {
                "event_type": "hipaa_phi_access",
                "timestamp": datetime.now(UTC).isoformat(),
                "url": str(request.url),
                "method": request.method,
                "status_code": response.status_code,
                "compliance_standard": "HIPAA",
                "phi_detected": True
            }
            
            logger.info("HIPAA PHI access audit", **hipaa_audit)
    
    async def _audit_for_soc2(self, request: Request, response: Response):
        """SOC 2 compliance auditing"""
        if not settings.SOC2_COMPLIANCE:
            return
        
        # Audit system access and data processing
        soc2_audit = {
            "event_type": "soc2_system_access",
            "timestamp": datetime.now(UTC).isoformat(),
            "url": str(request.url),
            "method": request.method,
            "status_code": response.status_code,
            "compliance_standard": "SOC2",
            "trust_service_criteria": self._get_soc2_criteria(request.url.path)
        }
        
        logger.info("SOC 2 compliance audit", **soc2_audit)
    
    def _get_soc2_criteria(self, path: str) -> list:
        """Determine applicable SOC 2 trust service criteria"""
        criteria = []
        
        if "/auth" in path or "/login" in path:
            criteria.extend(["Security", "Confidentiality"])
        
        if "/documents" in path or "/media" in path:
            criteria.extend(["Confidentiality", "Privacy"])
        
        if "/audit" in path:
            criteria.append("Availability")
        
        if "/export" in path:
            criteria.extend(["Processing Integrity", "Confidentiality"])
        
        return criteria or ["Security"]
    
    async def _get_request_body(self, request: Request) -> str:
        """Safely get request body for auditing"""
        try:
            if hasattr(request, '_body'):
                return request._body.decode('utf-8')
            return ""
        except:
            return ""