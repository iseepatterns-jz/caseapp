"""
Health Check API Endpoints
Provides comprehensive system health monitoring
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any
from datetime import datetime
import structlog

from services.health_service import HealthService, HealthStatus
from services.comprehensive_health_service import ComprehensiveHealthService
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

# Comprehensive Health Monitoring Endpoints

@router.get("/comprehensive", response_model=Dict[str, Any])
async def comprehensive_health_check(
    current_user: User = Depends(get_current_user)
):
    """
    Comprehensive health check with performance monitoring and anomaly detection
    
    Returns:
        Detailed health status, performance metrics, resource utilization, and recommendations
    """
    try:
        comprehensive_service = ComprehensiveHealthService()
        result = await comprehensive_service.comprehensive_health_check()
        
        logger.info(
            "Comprehensive health check performed",
            user_id=current_user.id,
            health_score=result.get("health_score", 0),
            anomaly_count=len(result.get("anomalies", []))
        )
        
        return result
    except Exception as e:
        logger.error("Comprehensive health check failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Comprehensive health check failed: {str(e)}")

@router.get("/performance/trends", response_model=Dict[str, Any])
async def get_performance_trends(
    hours_back: int = Query(24, description="Hours of historical data", ge=1, le=168),
    current_user: User = Depends(get_current_user)
):
    """
    Get performance trends over specified time period
    
    Args:
        hours_back: Hours of historical data to analyze (1-168 hours)
        
    Returns:
        Performance trends and analysis
    """
    try:
        comprehensive_service = ComprehensiveHealthService()
        result = await comprehensive_service.get_performance_trends(hours_back)
        
        logger.info(
            "Performance trends retrieved",
            user_id=current_user.id,
            hours_back=hours_back
        )
        
        return result
    except Exception as e:
        logger.error("Failed to get performance trends", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get performance trends: {str(e)}")

@router.get("/metrics/resource", response_model=Dict[str, Any])
async def get_resource_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get current system resource utilization metrics
    
    Returns:
        CPU, memory, disk, and network utilization
    """
    try:
        comprehensive_service = ComprehensiveHealthService()
        resource_metrics = await comprehensive_service._check_resource_utilization()
        
        logger.info(
            "Resource metrics retrieved",
            user_id=current_user.id,
            cpu_usage=resource_metrics.get("cpu", {}).get("usage_percent", 0),
            memory_usage=resource_metrics.get("memory", {}).get("usage_percent", 0)
        )
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "resource_metrics": resource_metrics
        }
    except Exception as e:
        logger.error("Failed to get resource metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get resource metrics: {str(e)}")

@router.get("/metrics/performance", response_model=Dict[str, Any])
async def get_performance_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get current application performance metrics
    
    Returns:
        Database, Redis, and application response time metrics
    """
    try:
        comprehensive_service = ComprehensiveHealthService()
        performance_metrics = await comprehensive_service._collect_performance_metrics()
        
        logger.info(
            "Performance metrics retrieved",
            user_id=current_user.id
        )
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "performance_metrics": performance_metrics
        }
    except Exception as e:
        logger.error("Failed to get performance metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")

@router.get("/alerts", response_model=Dict[str, Any])
async def get_active_alerts(
    current_user: User = Depends(get_current_user)
):
    """
    Get current active alerts and anomalies
    
    Returns:
        Active alerts, anomalies, and alert status
    """
    try:
        comprehensive_service = ComprehensiveHealthService()
        
        # Get current metrics
        performance_metrics = await comprehensive_service._collect_performance_metrics()
        resource_metrics = await comprehensive_service._check_resource_utilization()
        
        # Detect anomalies
        anomalies = await comprehensive_service._detect_anomalies(performance_metrics, resource_metrics)
        
        # Check alert conditions
        alert_status = comprehensive_service._check_alert_conditions(performance_metrics, resource_metrics)
        
        logger.info(
            "Active alerts retrieved",
            user_id=current_user.id,
            total_alerts=len(alert_status["active_alerts"]),
            critical_count=alert_status["critical_count"]
        )
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "anomalies": anomalies,
            "alert_status": alert_status,
            "total_alerts": len(alert_status["active_alerts"]),
            "critical_count": alert_status["critical_count"],
            "warning_count": alert_status["warning_count"]
        }
    except Exception as e:
        logger.error("Failed to get active alerts", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get active alerts: {str(e)}")

@router.get("/recommendations", response_model=Dict[str, Any])
async def get_health_recommendations(
    current_user: User = Depends(get_current_user)
):
    """
    Get health recommendations based on current system status
    
    Returns:
        Actionable recommendations for improving system health
    """
    try:
        comprehensive_service = ComprehensiveHealthService()
        
        # Get comprehensive health data
        health_data = await comprehensive_service.comprehensive_health_check()
        
        logger.info(
            "Health recommendations retrieved",
            user_id=current_user.id,
            recommendation_count=len(health_data.get("recommendations", [])),
            health_score=health_data.get("health_score", 0)
        )
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "recommendations": health_data.get("recommendations", []),
            "health_score": health_data.get("health_score", 0),
            "overall_status": health_data.get("overall_status", "unknown")
        }
    except Exception as e:
        logger.error("Failed to get health recommendations", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get health recommendations: {str(e)}")

# Public endpoints for load balancer health checks (no authentication required)

@router.get("/ready", response_model=Dict[str, Any])
async def readiness_check_public():
    """
    Public readiness check for load balancer health checks
    
    Returns:
        Simple ready/not ready status
    """
    try:
        health_service = HealthService()
        result = await health_service.check_all_services()
        
        if result["overall_status"] == "healthy":
            return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
        else:
            raise HTTPException(
                status_code=503, 
                detail={
                    "status": "not_ready", 
                    "reason": result["overall_status"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail={"status": "not_ready", "error": str(e)})

@router.get("/live", response_model=Dict[str, Any])
async def liveness_check_public():
    """
    Public liveness check for container orchestration
    
    Returns:
        Simple alive status
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}