"""
Health Check API Endpoints
Provides comprehensive system health monitoring
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import structlog

from services.health_service import HealthService, HealthStatus
from core.auth import get_current_user
from models.user import User

logger = structlog.get_logger()
router = APIRouter()

@router.get("/", response_model=Dict[str, Any])
async def basic_health_check():
    """
    Basic health check endpoint
    
    Returns:
        Basic system status
    """
    return {
        "status": "healthy",
        "message": "Court Case Management System is operational",
        "version": "1.0.0"
    }

@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(
    current_user: User = Depends(get_current_user)
):
    """
    Detailed health check of all system components
    
    Requires authentication to access detailed system information.
    
    Returns:
        Comprehensive health status of all services and dependencies
    """
    try:
        health_service = HealthService()
        health_status = await health_service.check_all_services()
        
        logger.info(
            "Detailed health check performed",
            user_id=current_user.id,
            overall_status=health_status["overall_status"]
        )
        
        return health_status
    
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )

@router.get("/dependencies", response_model=Dict[str, Any])
async def check_dependencies(
    current_user: User = Depends(get_current_user)
):
    """
    Check service dependencies and initialization status
    
    Returns:
        Dependency status and recommendations for system optimization
    """
    try:
        health_service = HealthService()
        dependency_status = await health_service.check_service_dependencies()
        
        logger.info(
            "Dependency check performed",
            user_id=current_user.id
        )
        
        return dependency_status
    
    except Exception as e:
        logger.error("Dependency check failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Dependency check failed: {str(e)}"
        )

@router.get("/services/{service_name}", response_model=Dict[str, Any])
async def check_specific_service(
    service_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Check health of a specific service
    
    Args:
        service_name: Name of the service to check
        
    Returns:
        Health status of the specified service
    """
    try:
        health_service = HealthService()
        full_status = await health_service.check_all_services()
        
        if service_name not in full_status["services"]:
            raise HTTPException(
                status_code=404,
                detail=f"Service '{service_name}' not found"
            )
        
        service_status = full_status["services"][service_name]
        
        logger.info(
            "Specific service health check performed",
            user_id=current_user.id,
            service_name=service_name,
            status=service_status["status"]
        )
        
        return {
            "service_name": service_name,
            "status": service_status["status"],
            "message": service_status["message"],
            "details": service_status["details"],
            "timestamp": service_status["timestamp"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Service health check failed", service_name=service_name, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Service health check failed: {str(e)}"
        )

@router.get("/readiness", response_model=Dict[str, Any])
async def readiness_check():
    """
    Kubernetes/Docker readiness probe endpoint
    
    Returns:
        Simple readiness status for container orchestration
    """
    try:
        health_service = HealthService()
        
        # Check critical dependencies only
        db_result = await health_service._check_database()
        redis_result = await health_service._check_redis()
        
        if (db_result.status == HealthStatus.HEALTHY and 
            redis_result.status == HealthStatus.HEALTHY):
            return {
                "status": "ready",
                "message": "System is ready to accept requests"
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="System is not ready - critical dependencies unavailable"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Readiness check failed: {str(e)}"
        )

@router.get("/liveness", response_model=Dict[str, Any])
async def liveness_check():
    """
    Kubernetes/Docker liveness probe endpoint
    
    Returns:
        Simple liveness status for container orchestration
    """
    return {
        "status": "alive",
        "message": "System is alive and responding"
    }