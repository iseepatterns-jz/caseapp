"""
Custom exceptions and error handling
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import structlog
from typing import Any, Dict

logger = structlog.get_logger()

class CaseManagementException(Exception):
    """Base exception for case management system"""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(CaseManagementException):
    """Validation error"""
    pass

class NotFoundError(CaseManagementException):
    """Resource not found error"""
    pass

class PermissionError(CaseManagementException):
    """Permission denied error"""
    pass

class ProcessingError(CaseManagementException):
    """Processing error (AI, media, etc.)"""
    pass

class IntegrationError(CaseManagementException):
    """External service integration error"""
    pass

async def case_management_exception_handler(request: Request, exc: CaseManagementException):
    """Handle custom case management exceptions"""
    logger.error(
        "Case management exception",
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        path=request.url.path
    )
    
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    if isinstance(exc, ValidationError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, NotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, PermissionError):
        status_code = status.HTTP_403_FORBIDDEN
    
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.error("Validation error", errors=exc.errors(), path=request.url.path)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error",
            "error_code": "VALIDATION_ERROR",
            "details": {"validation_errors": exc.errors()}
        }
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.error("HTTP exception", status_code=exc.status_code, detail=exc.detail, path=request.url.path)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": f"HTTP_{exc.status_code}"
        }
    )