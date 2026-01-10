"""
Audit logging middleware for comprehensive request tracking
"""

import time
import json
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
import structlog
from uuid import UUID

from services.audit_service import AuditService
from core.database import get_db

logger = structlog.get_logger()

class AuditMiddleware:
    """Middleware for comprehensive audit logging of API requests"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        
        # Skip audit logging for certain paths
        if self._should_skip_audit(request):
            await self.app(scope, receive, send)
            return
        
        # Capture request details
        start_time = time.time()
        request_body = await self._get_request_body(request)
        
        # Create a new receive callable that replays the body
        async def receive_wrapper():
            return {"type": "http.request", "body": request_body}
        
        # Capture response
        response_body = b""
        response_status = 200
        
        async def send_wrapper(message):
            nonlocal response_body, response_status
            
            if message["type"] == "http.response.start":
                response_status = message["status"]
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")
            
            await send(message)
        
        # Process the request
        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except Exception as e:
            # Log the exception but don't interfere with error handling
            logger.error("Request processing failed", error=str(e), path=request.url.path)
            raise
        finally:
            # Log the request after processing
            end_time = time.time()
            await self._log_request(
                request, 
                request_body, 
                response_status, 
                response_body, 
                end_time - start_time
            )
    
    def _should_skip_audit(self, request: Request) -> bool:
        """Determine if this request should be skipped for audit logging"""
        skip_paths = {
            "/", 
            "/health", 
            "/api/docs", 
            "/api/redoc", 
            "/openapi.json",
            "/favicon.ico"
        }
        
        # Skip static files and health checks
        if request.url.path in skip_paths:
            return True
        
        # Skip GET requests to certain endpoints (too noisy)
        if request.method == "GET" and any(path in request.url.path for path in ["/api/v1/cases/statistics"]):
            return True
        
        return False
    
    async def _get_request_body(self, request: Request) -> bytes:
        """Safely extract request body"""
        try:
            body = await request.body()
            return body
        except Exception:
            return b""
    
    async def _log_request(
        self, 
        request: Request, 
        request_body: bytes, 
        response_status: int, 
        response_body: bytes, 
        duration: float
    ):
        """Log the API request for audit purposes"""
        try:
            # Extract user information from request
            user_id = await self._extract_user_id(request)
            ip_address = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            
            # Parse request body safely
            request_data = self._safe_parse_json(request_body)
            
            # Parse response body safely (only for small responses)
            response_data = None
            if len(response_body) < 10000:  # Only log small responses
                response_data = self._safe_parse_json(response_body)
            
            # Create audit log entry for API request
            if user_id:
                async for db in get_db():
                    audit_service = AuditService(db)
                    
                    await audit_service.log_api_request(
                        method=request.method,
                        path=request.url.path,
                        query_params=str(request.query_params) if request.query_params else None,
                        request_data=json.dumps(request_data) if request_data else None,
                        response_status=response_status,
                        response_data=json.dumps(response_data) if response_data else None,
                        duration_ms=int(duration * 1000),
                        user_id=user_id,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                    
                    await db.commit()
                    break
            
            # Log to structured logger as well
            logger.info(
                "API request completed",
                method=request.method,
                path=request.url.path,
                status=response_status,
                duration_ms=int(duration * 1000),
                user_id=str(user_id) if user_id else None,
                ip_address=ip_address
            )
            
        except Exception as e:
            # Don't let audit logging failures break the application
            logger.error("Failed to log API request", error=str(e))
    
    async def _extract_user_id(self, request: Request) -> Optional[UUID]:
        """Extract user ID from request (from auth token)"""
        try:
            # This would typically extract from JWT token or session
            # For now, we'll check if there's a user in the request state
            if hasattr(request.state, "user") and request.state.user:
                return request.state.user.get("id")
            
            # Alternative: extract from Authorization header
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # In a real implementation, you'd decode the JWT here
                # For now, return None if we can't extract user ID
                pass
            
            return None
        except Exception:
            return None
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first (for load balancers/proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _safe_parse_json(self, data: bytes) -> Optional[dict]:
        """Safely parse JSON data"""
        try:
            if not data:
                return None
            
            text = data.decode("utf-8")
            return json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None


async def audit_middleware(request: Request, call_next):
    """Simple function-based audit middleware"""
    start_time = time.time()
    
    # Skip certain paths
    skip_paths = {"/", "/health", "/api/docs", "/api/redoc", "/openapi.json", "/favicon.ico"}
    if request.url.path in skip_paths:
        response = await call_next(request)
        return response
    
    # Process request
    response = await call_next(request)
    
    # Log the request
    process_time = time.time() - start_time
    
    logger.info(
        "API request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        process_time=process_time
    )
    
    return response