"""
Court Case Management System - Main FastAPI Application
"""

from datetime import datetime, UTC
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.exceptions import RequestValidationError
import structlog
from contextlib import asynccontextmanager

from core.config import settings
from core.database import engine, Base, get_db
from core.redis import redis_service
from core.audit_middleware import audit_middleware
from core.service_manager import ServiceManager
from core.exceptions import (
    CaseManagementException,
    case_management_exception_handler,
    validation_exception_handler,
    http_exception_handler
)
from api.v1.api import api_router
from core.aws_service import aws_service

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Court Case Management System")
    
    # Step 1: Validate database connection
    from core.database import validate_database_connection
    logger.info("Validating database connection...")
    
    db_valid = await validate_database_connection()
    if not db_valid:
        logger.error("Database connection validation failed during startup")
        # Continue startup but log the issue
    else:
        logger.info("Database connection validated successfully")
    
    # Step 2: Run database migrations
    from core.database_migration import run_startup_migrations
    logger.info("Running database migrations...")
    
    migration_success = await run_startup_migrations()
    if migration_success:
        logger.info("Database migrations completed successfully")
    else:
        logger.warning("Database migrations failed or were skipped")
    
    # Step 3: Initialize service manager
    service_manager = ServiceManager()
    app.state.service_manager = service_manager
    
    # Initialize all services
    initialization_result = await service_manager.initialize_all_services()
    
    if initialization_result["status"] == "success":
        logger.info("All services initialized successfully")
    else:
        logger.warning(
            "Some services failed to initialize",
            successful=initialization_result["successful_services"],
            total=initialization_result["total_services"]
        )
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Graceful service shutdown
    shutdown_result = await service_manager.shutdown_services()
    logger.info("Service shutdown completed", results=shutdown_result)

# Create FastAPI application with comprehensive API documentation
app = FastAPI(
    title="Court Case Management API",
    description="""
    ## AI-Powered Legal Case Management System

    A comprehensive legal case management platform with advanced AI capabilities, 
    forensic analysis, and real-time collaboration features.

    ### Key Features

    * **Case Management**: Complete case lifecycle management with metadata tracking
    * **Document Analysis**: AI-powered document processing with entity recognition
    * **Timeline Building**: Visual timeline creation with evidence pinning
    * **Media Evidence**: Secure media handling with chain of custody
    * **Forensic Analysis**: Digital communication analysis and pattern detection
    * **Real-time Collaboration**: Multi-user collaboration with granular permissions
    * **AI Insights**: Machine learning-powered case insights and recommendations
    * **Export & Reporting**: Professional court-ready reports and presentations
    * **Security & Compliance**: HIPAA and SOC 2 compliant with end-to-end encryption
    * **External Integrations**: Comprehensive REST API for system integration

    ### Authentication

    All API endpoints require authentication using Bearer tokens. Include your token in the Authorization header:

    ```
    Authorization: Bearer <your-token>
    ```

    ### Rate Limiting

    API requests are rate-limited to prevent abuse:
    - General endpoints: 100 requests per minute
    - Authentication endpoints: 10 requests per minute
    - Upload endpoints: 20 requests per minute

    ### Webhooks

    The system supports webhook notifications for real-time integration with external systems.
    Configure webhooks through the `/integrations/webhooks` endpoints.

    ### Error Handling

    The API uses standard HTTP status codes and returns detailed error information:
    - `400` - Bad Request (validation errors)
    - `401` - Unauthorized (authentication required)
    - `403` - Forbidden (insufficient permissions)
    - `404` - Not Found (resource not found)
    - `429` - Too Many Requests (rate limit exceeded)
    - `500` - Internal Server Error (system error)

    ### Support

    For API support and documentation, contact the development team.
    """,
    version="1.0.0",
    contact={
        "name": "Court Case Management API Support",
        "email": "api-support@courtcase.com",
    },
    license_info={
        "name": "Proprietary License",
        "url": "https://courtcase.com/license",
    },
    terms_of_service="https://courtcase.com/terms",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=[
        {
            "name": "authentication",
            "description": "User authentication and authorization endpoints"
        },
        {
            "name": "cases",
            "description": "Case management operations - create, read, update, and manage legal cases"
        },
        {
            "name": "documents",
            "description": "Document management with AI analysis - upload, process, and search documents"
        },
        {
            "name": "timeline",
            "description": "Timeline building and evidence pinning - create chronological case narratives"
        },
        {
            "name": "media",
            "description": "Media evidence management - handle audio/video evidence with forensic integrity"
        },
        {
            "name": "forensic",
            "description": "Digital forensic analysis - analyze communication data and detect patterns"
        },
        {
            "name": "collaboration",
            "description": "Real-time collaboration - share timelines and collaborate with team members"
        },
        {
            "name": "insights",
            "description": "AI-powered insights - get machine learning recommendations and analysis"
        },
        {
            "name": "exports",
            "description": "Export and reporting - generate court-ready reports and presentations"
        },
        {
            "name": "audit",
            "description": "Audit logging - track all system activities for compliance"
        },
        {
            "name": "integrations",
            "description": "External integrations - comprehensive REST API for system connectivity"
        },
        {
            "name": "health",
            "description": "System health monitoring - check service status and dependencies"
        }
    ],
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add audit logging middleware
app.middleware("http")(audit_middleware)

# Add exception handlers
app.add_exception_handler(CaseManagementException, case_management_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# Security
security = HTTPBearer()

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Court Case Management System API",
        "version": "1.0.0",
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    """
    Simple health check endpoint for container health checks
    Returns HTTP 200 immediately without database dependency
    Use /health/ready for comprehensive checks including database
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "backend",
        "version": "1.0.0"
    }

@app.get("/health/ready")
async def readiness_check():
    """
    Comprehensive readiness check for ALB health checks
    Includes database connectivity validation
    """
    try:
        from core.database import validate_database_connection
        from services.health_service import HealthService
        
        # Database connectivity check
        db_valid = await validate_database_connection()
        
        if not db_valid:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "message": "Database connection validation failed",
                    "database": "disconnected"
                }
            )
        
        # Quick Redis check
        health_service = HealthService()
        redis_result = await health_service._check_redis()
        redis_status = "connected" if redis_result.status == "healthy" else "error"
        
        # Check migration status
        from core.database_migration import get_migration_status
        migration_status = await get_migration_status()
        
        return {
            "status": "ready",
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "Service ready for traffic",
            "database": "connected",
            "redis": redis_status,
            "migrations": {
                "current_version": migration_status.get("current_version"),
                "pending_count": migration_status.get("pending_count", 0),
                "schema_status": migration_status.get("schema_status", "unknown")
            },
            "version": "1.0.0"
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "timestamp": datetime.now(UTC).isoformat(),
                "error": str(e),
                "message": "Service not ready for traffic"
            }
        )

@app.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check endpoint for monitoring and debugging
    Returns comprehensive status of all services and dependencies
    """
    from services.health_service import HealthService
    
    try:
        health_service = HealthService()
        
        # Comprehensive health check
        db_result = await health_service._check_database()
        redis_result = await health_service._check_redis()
        
        database_status = "connected" if db_result.status == "healthy" else "error"
        redis_status = "connected" if redis_result.status == "healthy" else "error"
        
        # Check migration status
        from core.database_migration import get_migration_status
        migration_status = await get_migration_status()
        
        # Determine overall health
        is_healthy = database_status == "connected" and redis_status == "connected"
        overall_status = "healthy" if is_healthy else "degraded"
        
        response = {
            "status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
            "database": database_status,
            "redis": redis_status,
            "aws_services": "initialized",
            "migrations": {
                "current_version": migration_status.get("current_version"),
                "pending_count": migration_status.get("pending_count", 0),
                "schema_status": migration_status.get("schema_status", "unknown")
            },
            "version": "1.0.0"
        }
        
        # Return HTTP 200 only if core services are healthy
        if is_healthy:
            return response
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    **response,
                    "error": "Core services unavailable"
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "database": "error",
                "redis": "error",
                "aws_services": "unknown",
                "migrations": {"status": "unknown"},
                "error": str(e)
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None  # Use structlog instead
    )