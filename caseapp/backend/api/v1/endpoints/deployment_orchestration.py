"""
Deployment Orchestration API Endpoints
Provides unified endpoints for complete deployment orchestration with all reliability features
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, List, Any, Optional
import structlog
from datetime import datetime

from services.deployment_orchestration_service import DeploymentOrchestrationService

logger = structlog.get_logger()
router = APIRouter()

# Initialize service
orchestration_service = DeploymentOrchestrationService()

@router.on_event("startup")
async def startup_event():
    """Initialize deployment orchestration service on startup"""
    try:
        await orchestration_service.initialize()
        logger.info("Deployment orchestration service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize deployment orchestration service: {str(e)}")

@router.post("/orchestrate/{cluster_name}/{service_name}")
async def orchestrate_full_deployment(
    cluster_name: str,
    service_name: str,
    deployment_config: Optional[Dict[str, Any]] = Body(None)
) -> Dict[str, Any]:
    """
    Orchestrate complete deployment with all reliability features
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        deployment_config: Optional deployment configuration
        
    Returns:
        Complete orchestration results
    """
    try:
        logger.info(f"Starting full deployment orchestration for {service_name}", cluster=cluster_name)
        
        results = await orchestration_service.orchestrate_full_deployment(
            cluster_name=cluster_name,
            service_name=service_name,
            deployment_config=deployment_config
        )
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'orchestration_timestamp': datetime.utcnow().isoformat(),
            **results
        }
        
    except Exception as e:
        logger.error(f"Deployment orchestration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deployment orchestration failed: {str(e)}")

@router.get("/status/{cluster_name}/{service_name}")
async def get_orchestration_status(
    cluster_name: str,
    service_name: str
) -> Dict[str, Any]:
    """
    Get current orchestration status for a service
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        
    Returns:
        Current orchestration status
    """
    try:
        logger.info(f"Getting orchestration status for {service_name}", cluster=cluster_name)
        
        status = await orchestration_service.get_orchestration_status(cluster_name, service_name)
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get orchestration status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status query failed: {str(e)}")

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for deployment orchestration service"""
    
    try:
        # Check if all component services are initialized
        services_status = {
            'monitoring_service': orchestration_service.monitoring_service is not None,
            'health_service': orchestration_service.health_service is not None,
            'diagnostic_service': orchestration_service.diagnostic_service is not None,
            'optimization_service': orchestration_service.optimization_service is not None,
            'validation_service': orchestration_service.validation_service is not None,
            'recovery_service': orchestration_service.recovery_service is not None
        }
        
        all_services_ready = all(services_status.values())
        
        return {
            'status': 'healthy' if all_services_ready else 'partial',
            'service': 'deployment_orchestration',
            'timestamp': datetime.utcnow().isoformat(),
            'component_services': services_status,
            'configuration': {
                'auto_optimization_enabled': orchestration_service.auto_optimization_enabled,
                'auto_recovery_enabled': orchestration_service.auto_recovery_enabled,
                'validation_timeout_minutes': orchestration_service.validation_timeout_minutes,
                'monitoring_interval_minutes': orchestration_service.monitoring_interval_minutes
            }
        }
        
    except Exception as e:
        logger.error(f"Deployment orchestration service health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'service': 'deployment_orchestration',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }

@router.get("/config")
async def get_orchestration_config() -> Dict[str, Any]:
    """Get deployment orchestration configuration"""
    
    return {
        'configuration': {
            'auto_optimization_enabled': orchestration_service.auto_optimization_enabled,
            'auto_recovery_enabled': orchestration_service.auto_recovery_enabled,
            'validation_timeout_minutes': orchestration_service.validation_timeout_minutes,
            'monitoring_interval_minutes': orchestration_service.monitoring_interval_minutes
        },
        'component_services': {
            'monitoring_service': 'DeploymentMonitoringService',
            'health_service': 'ComprehensiveHealthService',
            'diagnostic_service': 'DiagnosticService',
            'optimization_service': 'ResourceOptimizationService',
            'validation_service': 'DeploymentValidationService',
            'recovery_service': 'DisasterRecoveryService'
        },
        'orchestration_phases': [
            'pre_deployment',
            'deployment',
            'post_deployment',
            'monitoring',
            'optimization'
        ],
        'service_info': {
            'name': 'Deployment Orchestration Service',
            'version': '1.0.0',
            'description': 'Unified orchestration of monitoring, alerting, recovery, and validation systems'
        }
    }

@router.put("/config")
async def update_orchestration_config(
    config_update: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Update deployment orchestration configuration"""
    
    try:
        updated_fields = []
        
        # Update configuration fields if provided
        if 'auto_optimization_enabled' in config_update:
            orchestration_service.auto_optimization_enabled = config_update['auto_optimization_enabled']
            updated_fields.append('auto_optimization_enabled')
        
        if 'auto_recovery_enabled' in config_update:
            orchestration_service.auto_recovery_enabled = config_update['auto_recovery_enabled']
            updated_fields.append('auto_recovery_enabled')
        
        if 'validation_timeout_minutes' in config_update:
            timeout = config_update['validation_timeout_minutes']
            if 1 <= timeout <= 60:
                orchestration_service.validation_timeout_minutes = timeout
                updated_fields.append('validation_timeout_minutes')
            else:
                raise HTTPException(status_code=400, detail="validation_timeout_minutes must be between 1 and 60")
        
        if 'monitoring_interval_minutes' in config_update:
            interval = config_update['monitoring_interval_minutes']
            if 1 <= interval <= 60:
                orchestration_service.monitoring_interval_minutes = interval
                updated_fields.append('monitoring_interval_minutes')
            else:
                raise HTTPException(status_code=400, detail="monitoring_interval_minutes must be between 1 and 60")
        
        logger.info(f"Updated orchestration configuration", updated_fields=updated_fields)
        
        return {
            'status': 'updated',
            'updated_fields': updated_fields,
            'timestamp': datetime.utcnow().isoformat(),
            'current_config': {
                'auto_optimization_enabled': orchestration_service.auto_optimization_enabled,
                'auto_recovery_enabled': orchestration_service.auto_recovery_enabled,
                'validation_timeout_minutes': orchestration_service.validation_timeout_minutes,
                'monitoring_interval_minutes': orchestration_service.monitoring_interval_minutes
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update orchestration configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Configuration update failed: {str(e)}")

@router.get("/capabilities")
async def get_orchestration_capabilities() -> Dict[str, Any]:
    """Get deployment orchestration capabilities and features"""
    
    return {
        'orchestration_capabilities': {
            'pre_deployment_validation': {
                'description': 'Validates system health and creates snapshots before deployment',
                'features': [
                    'Deployment snapshot creation',
                    'Diagnostic checks for critical issues',
                    'Service health validation',
                    'Deployment readiness assessment'
                ]
            },
            'deployment_monitoring': {
                'description': 'Monitors deployment progress and validates service health',
                'features': [
                    'Service health validation with timeout',
                    'Deployment progress tracking',
                    'Automatic failure detection',
                    'Emergency recovery triggering'
                ]
            },
            'post_deployment_validation': {
                'description': 'Comprehensive testing and validation after deployment',
                'features': [
                    'Smoke tests for basic functionality',
                    'API endpoint validation',
                    'Integration testing with external services',
                    'Post-deployment snapshot creation'
                ]
            },
            'continuous_monitoring': {
                'description': 'Setup ongoing monitoring and alerting',
                'features': [
                    'CloudWatch dashboard creation',
                    'Automated alerting configuration',
                    'Health monitoring setup',
                    'Performance metrics collection'
                ]
            },
            'resource_optimization': {
                'description': 'Automated resource optimization analysis',
                'features': [
                    'CPU and memory utilization analysis',
                    'Cost optimization recommendations',
                    'Performance improvement suggestions',
                    'Automated scaling recommendations'
                ]
            },
            'disaster_recovery': {
                'description': 'Automated recovery and rollback capabilities',
                'features': [
                    'Automatic rollback on deployment failure',
                    'Emergency scaling procedures',
                    'Recovery plan execution',
                    'Backup and restore operations'
                ]
            }
        },
        'integration_features': {
            'unified_orchestration': 'Single API for complete deployment lifecycle',
            'automatic_recovery': 'Automated failure detection and recovery',
            'comprehensive_validation': 'Multi-level testing and validation',
            'continuous_optimization': 'Ongoing resource and performance optimization',
            'centralized_monitoring': 'Unified monitoring and alerting setup'
        },
        'supported_phases': [
            {
                'phase': 'pre_deployment',
                'description': 'Validation and preparation before deployment',
                'duration_estimate': '2-5 minutes'
            },
            {
                'phase': 'deployment',
                'description': 'Deployment monitoring and health validation',
                'duration_estimate': '5-15 minutes'
            },
            {
                'phase': 'post_deployment',
                'description': 'Comprehensive testing and validation',
                'duration_estimate': '3-10 minutes'
            },
            {
                'phase': 'monitoring',
                'description': 'Monitoring and alerting setup',
                'duration_estimate': '1-3 minutes'
            },
            {
                'phase': 'optimization',
                'description': 'Resource optimization analysis',
                'duration_estimate': '2-5 minutes'
            }
        ]
    }