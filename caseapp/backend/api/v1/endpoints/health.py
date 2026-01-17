"""
Health Check API Endpoints
Provides comprehensive system health monitoring
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any
from datetime import datetime, UTC
import structlog

from services.health_service import HealthService, HealthStatus
from services.comprehensive_health_service import ComprehensiveHealthService
from core.auth import get_current_user
from models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.audit_service import AuditService

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform a detailed health check of all system components"""
    audit_service = AuditService(db)
    health_service = HealthService()
    return await health_service.check_all_services(db, audit_service)

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

@router.get("/service/{service_name}", response_model=Dict[str, Any])
async def check_specific_service(
    service_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check the health of a specific service"""
    audit_service = AuditService(db)
    health_service = HealthService()
    results = await health_service.check_all_services(db, audit_service)
    
    try:
        full_status = results # Use results from the new call
        
        if service_name not in full_status["services"]:
            raise HTTPException(
                status_code=404,
                detail=f"Service '{service_name}' not found"
            )
        
        service_status = full_status["services"][service_name]
        
        logger.info(
            "Specific service health check performed",
            service_name=service_name, # Removed user_id as current_user is removed
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform a comprehensive health check with performance metrics"""
    audit_service = AuditService(db)
    comp_health_service = ComprehensiveHealthService()
    return await comp_health_service.comprehensive_health_check(db, audit_service)

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
            "timestamp": datetime.now(UTC).isoformat(),
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
            "timestamp": datetime.now(UTC).isoformat(),
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
            "timestamp": datetime.now(UTC).isoformat(),
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
            "timestamp": datetime.now(UTC).isoformat(),
            "recommendations": health_data.get("recommendations", []),
            "health_score": health_data.get("health_score", 0),
            "overall_status": health_data.get("overall_status", "unknown")
        }
    except Exception as e:
        logger.error("Failed to get health recommendations", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get health recommendations: {str(e)}")

@router.get("/readiness/public", response_model=Dict[str, Any])
async def readiness_check_public(
    db: AsyncSession = Depends(get_db)
):
    """Public readiness check (returns 200/503)"""
    try:
        audit_service = AuditService(db)
        health_service = HealthService()
        result = await health_service.check_all_services(db, audit_service)
        
        if result["overall_status"] == "healthy":
            return {"status": "ready", "timestamp": datetime.now(UTC).isoformat()}
        else:
            raise HTTPException(
                status_code=503, 
                detail={
                    "status": "not_ready", 
                    "reason": result["overall_status"],
                    "timestamp": datetime.now(UTC).isoformat()
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
    return {"status": "alive", "timestamp": datetime.now(UTC).isoformat()}