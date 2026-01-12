"""
Monitoring API endpoints for deployment and infrastructure monitoring
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
import structlog

from services.deployment_monitoring_service import DeploymentMonitoringService
from core.config import settings

logger = structlog.get_logger()
router = APIRouter()

# Pydantic models for request/response
class DeploymentStatusResponse(BaseModel):
    """Response model for deployment status"""
    status: str
    service_name: str
    cluster_name: str
    health: str
    running_count: int
    desired_count: int
    deployments: list
    recent_events: list

class MetricsResponse(BaseModel):
    """Response model for metrics data"""
    status: str
    metrics: Dict[str, Any]
    timestamp: str

class DashboardRequest(BaseModel):
    """Request model for dashboard creation"""
    dashboard_name: str
    cluster_name: str
    service_name: str
    load_balancer_arn: str
    db_instance_identifier: str

class AlarmRequest(BaseModel):
    """Request model for alarm creation"""
    cluster_name: str
    service_name: str
    load_balancer_arn: str
    db_instance_identifier: str
    sns_topic_arn: Optional[str] = None

def get_monitoring_service() -> DeploymentMonitoringService:
    """Dependency to get monitoring service instance"""
    return DeploymentMonitoringService()

@router.get("/deployment/status", response_model=Dict[str, Any])
async def get_deployment_status(
    cluster_name: str = Query(..., description="ECS cluster name"),
    service_name: str = Query(..., description="ECS service name"),
    monitoring_service: DeploymentMonitoringService = Depends(get_monitoring_service)
):
    """
    Get comprehensive deployment status for ECS service
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        
    Returns:
        Deployment status and health information
    """
    try:
        logger.info("Getting deployment status", cluster=cluster_name, service=service_name)
        
        result = await monitoring_service.get_deployment_status(cluster_name, service_name)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return result
        
    except Exception as e:
        logger.error("Failed to get deployment status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get deployment status: {str(e)}")

@router.get("/metrics/ecs", response_model=Dict[str, Any])
async def get_ecs_metrics(
    cluster_name: str = Query(..., description="ECS cluster name"),
    service_name: str = Query(..., description="ECS service name"),
    hours_back: int = Query(1, description="Hours of historical data", ge=1, le=24),
    monitoring_service: DeploymentMonitoringService = Depends(get_monitoring_service)
):
    """
    Get ECS service metrics from CloudWatch
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        hours_back: Hours of historical data to retrieve (1-24)
        
    Returns:
        ECS metrics data
    """
    try:
        logger.info("Getting ECS metrics", cluster=cluster_name, service=service_name, hours=hours_back)
        
        result = await monitoring_service.get_ecs_metrics(cluster_name, service_name, hours_back)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return result
        
    except Exception as e:
        logger.error("Failed to get ECS metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get ECS metrics: {str(e)}")

@router.get("/metrics/alb", response_model=Dict[str, Any])
async def get_alb_metrics(
    load_balancer_arn: str = Query(..., description="Application Load Balancer ARN"),
    hours_back: int = Query(1, description="Hours of historical data", ge=1, le=24),
    monitoring_service: DeploymentMonitoringService = Depends(get_monitoring_service)
):
    """
    Get Application Load Balancer metrics from CloudWatch
    
    Args:
        load_balancer_arn: ALB ARN
        hours_back: Hours of historical data to retrieve (1-24)
        
    Returns:
        ALB metrics data
    """
    try:
        logger.info("Getting ALB metrics", alb_arn=load_balancer_arn, hours=hours_back)
        
        result = await monitoring_service.get_alb_metrics(load_balancer_arn, hours_back)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return result
        
    except Exception as e:
        logger.error("Failed to get ALB metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get ALB metrics: {str(e)}")

@router.get("/metrics/rds", response_model=Dict[str, Any])
async def get_rds_metrics(
    db_instance_identifier: str = Query(..., description="RDS instance identifier"),
    hours_back: int = Query(1, description="Hours of historical data", ge=1, le=24),
    monitoring_service: DeploymentMonitoringService = Depends(get_monitoring_service)
):
    """
    Get RDS database metrics from CloudWatch
    
    Args:
        db_instance_identifier: RDS instance identifier
        hours_back: Hours of historical data to retrieve (1-24)
        
    Returns:
        RDS metrics data
    """
    try:
        logger.info("Getting RDS metrics", db_instance=db_instance_identifier, hours=hours_back)
        
        result = await monitoring_service.get_rds_metrics(db_instance_identifier, hours_back)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return result
        
    except Exception as e:
        logger.error("Failed to get RDS metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get RDS metrics: {str(e)}")

@router.post("/dashboard/create", response_model=Dict[str, Any])
async def create_deployment_dashboard(
    request: DashboardRequest,
    monitoring_service: DeploymentMonitoringService = Depends(get_monitoring_service)
):
    """
    Create CloudWatch dashboard for deployment monitoring
    
    Args:
        request: Dashboard creation request with resource identifiers
        
    Returns:
        Dashboard creation result
    """
    try:
        logger.info("Creating deployment dashboard", dashboard_name=request.dashboard_name)
        
        result = await monitoring_service.create_deployment_dashboard(
            dashboard_name=request.dashboard_name,
            cluster_name=request.cluster_name,
            service_name=request.service_name,
            load_balancer_arn=request.load_balancer_arn,
            db_instance_identifier=request.db_instance_identifier
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return result
        
    except Exception as e:
        logger.error("Failed to create dashboard", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create dashboard: {str(e)}")

@router.post("/alarms/create", response_model=Dict[str, Any])
async def create_deployment_alarms(
    request: AlarmRequest,
    monitoring_service: DeploymentMonitoringService = Depends(get_monitoring_service)
):
    """
    Create CloudWatch alarms for deployment monitoring
    
    Args:
        request: Alarm creation request with resource identifiers
        
    Returns:
        Alarm creation result
    """
    try:
        logger.info("Creating deployment alarms", service=request.service_name)
        
        result = await monitoring_service.create_deployment_alarms(
            cluster_name=request.cluster_name,
            service_name=request.service_name,
            load_balancer_arn=request.load_balancer_arn,
            db_instance_identifier=request.db_instance_identifier,
            sns_topic_arn=request.sns_topic_arn
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return result
        
    except Exception as e:
        logger.error("Failed to create alarms", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create alarms: {str(e)}")

@router.get("/health/summary", response_model=Dict[str, Any])
async def get_deployment_health_summary(
    cluster_name: str = Query(..., description="ECS cluster name"),
    service_name: str = Query(..., description="ECS service name"),
    monitoring_service: DeploymentMonitoringService = Depends(get_monitoring_service)
):
    """
    Get comprehensive deployment health summary
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        
    Returns:
        Health summary with score and recommendations
    """
    try:
        logger.info("Getting deployment health summary", cluster=cluster_name, service=service_name)
        
        result = await monitoring_service.get_deployment_health_summary(cluster_name, service_name)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return result
        
    except Exception as e:
        logger.error("Failed to get health summary", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get health summary: {str(e)}")

@router.get("/dashboard/url")
async def get_dashboard_url(
    dashboard_name: str = Query(..., description="CloudWatch dashboard name"),
    region: str = Query(None, description="AWS region (defaults to configured region)")
):
    """
    Get CloudWatch dashboard URL for easy access
    
    Args:
        dashboard_name: Name of the CloudWatch dashboard
        region: AWS region (optional, uses configured region if not provided)
        
    Returns:
        Dashboard URL and access information
    """
    try:
        aws_region = region or settings.AWS_REGION
        dashboard_url = f"https://{aws_region}.console.aws.amazon.com/cloudwatch/home?region={aws_region}#dashboards:name={dashboard_name}"
        
        return {
            "status": "success",
            "dashboard_name": dashboard_name,
            "dashboard_url": dashboard_url,
            "region": aws_region,
            "message": "Dashboard URL generated successfully"
        }
        
    except Exception as e:
        logger.error("Failed to generate dashboard URL", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate dashboard URL: {str(e)}")

@router.get("/metrics/custom")
async def get_custom_metrics(
    metric_queries: str = Query(..., description="JSON string of CloudWatch metric queries"),
    start_time: datetime = Query(..., description="Start time for metrics (ISO format)"),
    end_time: datetime = Query(..., description="End time for metrics (ISO format)"),
    monitoring_service: DeploymentMonitoringService = Depends(get_monitoring_service)
):
    """
    Get custom CloudWatch metrics with flexible query support
    
    Args:
        metric_queries: JSON string containing CloudWatch metric queries
        start_time: Start time for metrics in ISO format
        end_time: End time for metrics in ISO format
        
    Returns:
        Custom metrics data
    """
    try:
        import json
        
        logger.info("Getting custom metrics", start_time=start_time, end_time=end_time)
        
        # Parse metric queries
        try:
            queries = json.loads(metric_queries)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in metric_queries: {str(e)}")
        
        result = await monitoring_service.get_cloudwatch_metrics(queries, start_time, end_time)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get custom metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get custom metrics: {str(e)}")