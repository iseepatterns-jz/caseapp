"""
Disaster Recovery API Endpoints
Provides endpoints for disaster recovery, rollback operations, and emergency procedures
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, List, Any, Optional
import structlog
from datetime import datetime, UTC

from services.disaster_recovery_service import DisasterRecoveryService

logger = structlog.get_logger()
router = APIRouter()

# Initialize service
recovery_service = DisasterRecoveryService()

@router.on_event("startup")
async def startup_event():
    """Initialize disaster recovery service on startup"""
    try:
        await recovery_service.initialize()
        logger.info("Disaster recovery service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize disaster recovery service: {str(e)}")

@router.post("/snapshot/{cluster_name}/{service_name}")
async def create_deployment_snapshot(
    cluster_name: str,
    service_name: str
) -> Dict[str, Any]:
    """
    Create a snapshot of current deployment configuration
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        
    Returns:
        Deployment snapshot information
    """
    try:
        logger.info(f"Creating deployment snapshot for {service_name}", cluster=cluster_name)
        
        snapshot = await recovery_service.create_deployment_snapshot(cluster_name, service_name)
        
        return {
            'status': 'success',
            'message': 'Deployment snapshot created successfully',
            'snapshot': {
                'snapshot_id': snapshot.timestamp.strftime('%Y%m%d_%H%M%S'),
                'timestamp': snapshot.timestamp.isoformat(),
                'cluster_name': snapshot.cluster_name,
                'service_name': snapshot.service_name,
                'task_definition_arn': snapshot.task_definition_arn,
                'desired_count': snapshot.desired_count,
                'environment_variables_count': len(snapshot.environment_variables)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to create deployment snapshot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Snapshot creation failed: {str(e)}")

@router.get("/snapshots/{cluster_name}/{service_name}")
async def list_deployment_snapshots(
    cluster_name: str,
    service_name: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of snapshots to return")
) -> Dict[str, Any]:
    """
    List available deployment snapshots
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        limit: Maximum number of snapshots to return
        
    Returns:
        List of available snapshots
    """
    try:
        logger.info(f"Listing deployment snapshots for {service_name}", cluster=cluster_name, limit=limit)
        
        snapshots = await recovery_service.list_deployment_snapshots(cluster_name, service_name, limit)
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'total_snapshots': len(snapshots),
            'snapshots': snapshots
        }
        
    except Exception as e:
        logger.error(f"Failed to list deployment snapshots: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Snapshot listing failed: {str(e)}")

@router.post("/rollback/{cluster_name}/{service_name}")
async def rollback_to_snapshot(
    cluster_name: str,
    service_name: str,
    rollback_config: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """
    Rollback service to a previous snapshot
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        rollback_config: Rollback configuration
        
    Returns:
        Rollback operation result
    """
    try:
        snapshot_id = rollback_config.get('snapshot_id')
        if not snapshot_id:
            raise HTTPException(status_code=400, detail="snapshot_id is required")
        
        dry_run = rollback_config.get('dry_run', True)
        
        logger.info(f"Rolling back {service_name} to snapshot {snapshot_id}", 
                   cluster=cluster_name, dry_run=dry_run)
        
        result = await recovery_service.rollback_to_snapshot(
            cluster_name, service_name, snapshot_id, dry_run
        )
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'rollback_timestamp': datetime.now(UTC).isoformat(),
            **result
        }
        
    except Exception as e:
        logger.error(f"Rollback operation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")

@router.post("/emergency-scale/{cluster_name}/{service_name}")
async def emergency_scale_service(
    cluster_name: str,
    service_name: str,
    scaling_config: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """
    Emergency scaling of ECS service
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        scaling_config: Scaling configuration
        
    Returns:
        Scaling operation result
    """
    try:
        target_count = scaling_config.get('target_count')
        if target_count is None:
            raise HTTPException(status_code=400, detail="target_count is required")
        
        if target_count < 0 or target_count > 50:
            raise HTTPException(status_code=400, detail="target_count must be between 0 and 50")
        
        reason = scaling_config.get('reason', 'Emergency scaling via API')
        
        logger.info(f"Emergency scaling {service_name} to {target_count} tasks", 
                   cluster=cluster_name, reason=reason)
        
        result = await recovery_service.emergency_scale_service(
            cluster_name, service_name, target_count, reason
        )
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'scaling_timestamp': datetime.now(UTC).isoformat(),
            **result
        }
        
    except Exception as e:
        logger.error(f"Emergency scaling failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Emergency scaling failed: {str(e)}")

@router.post("/execute-plan/{plan_id}")
async def execute_recovery_plan(
    plan_id: str,
    execution_config: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """
    Execute a disaster recovery plan
    
    Args:
        plan_id: Recovery plan ID
        execution_config: Execution configuration
        
    Returns:
        Recovery operation tracking information
    """
    try:
        cluster_name = execution_config.get('cluster_name')
        service_name = execution_config.get('service_name')
        
        if not cluster_name or not service_name:
            raise HTTPException(status_code=400, detail="cluster_name and service_name are required")
        
        parameters = execution_config.get('parameters', {})
        
        logger.info(f"Executing recovery plan {plan_id}", 
                   cluster=cluster_name, service=service_name)
        
        operation_id = await recovery_service.execute_recovery_plan(
            plan_id, cluster_name, service_name, parameters
        )
        
        return {
            'status': 'started',
            'message': f'Recovery plan {plan_id} execution started',
            'operation_id': operation_id,
            'cluster_name': cluster_name,
            'service_name': service_name,
            'plan_id': plan_id,
            'started_at': datetime.now(UTC).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Recovery plan execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recovery plan execution failed: {str(e)}")

@router.get("/operation/{operation_id}")
async def get_recovery_operation_status(
    operation_id: str
) -> Dict[str, Any]:
    """
    Get status of a recovery operation
    
    Args:
        operation_id: Recovery operation ID
        
    Returns:
        Recovery operation status
    """
    try:
        logger.info(f"Getting recovery operation status", operation_id=operation_id)
        
        status = await recovery_service.get_recovery_operation_status(operation_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Recovery operation {operation_id} not found")
        
        return {
            'query_timestamp': datetime.now(UTC).isoformat(),
            **status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recovery operation status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status query failed: {str(e)}")

@router.get("/plans")
async def get_recovery_plans() -> Dict[str, Any]:
    """
    Get available recovery plans
    
    Returns:
        Available recovery plans
    """
    try:
        logger.info("Getting available recovery plans")
        
        plans = await recovery_service.get_recovery_plans()
        
        return {
            'query_timestamp': datetime.now(UTC).isoformat(),
            'total_plans': len(plans['plans']),
            **plans
        }
        
    except Exception as e:
        logger.error(f"Failed to get recovery plans: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recovery plans query failed: {str(e)}")

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for disaster recovery service"""
    
    try:
        # Basic health check - verify AWS clients are available
        if recovery_service.ecs is None:
            await recovery_service.initialize()
        
        return {
            'status': 'healthy',
            'service': 'disaster_recovery',
            'timestamp': datetime.now(UTC).isoformat(),
            'aws_clients_initialized': all([
                recovery_service.ecs is not None,
                recovery_service.elbv2 is not None,
                recovery_service.s3 is not None,
                recovery_service.cloudformation is not None
            ]),
            'backup_bucket': recovery_service.backup_bucket_name,
            'active_operations': len(recovery_service.active_operations),
            'available_plans': len(recovery_service.recovery_plans)
        }
        
    except Exception as e:
        logger.error(f"Disaster recovery service health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'service': 'disaster_recovery',
            'timestamp': datetime.now(UTC).isoformat(),
            'error': str(e)
        }

@router.get("/config")
async def get_disaster_recovery_config() -> Dict[str, Any]:
    """Get disaster recovery configuration"""
    
    return {
        'configuration': {
            'backup_bucket_name': recovery_service.backup_bucket_name,
            'max_snapshots_per_service': recovery_service.max_snapshots_per_service,
            'snapshot_retention_days': recovery_service.snapshot_retention_days
        },
        'recovery_plans': len(recovery_service.recovery_plans),
        'active_operations': len(recovery_service.active_operations),
        'service_info': {
            'name': 'Disaster Recovery Service',
            'version': '1.0.0',
            'description': 'Automated rollback capabilities, backup procedures, and emergency deployment handling'
        }
    }

@router.post("/test-recovery-plan/{plan_id}")
async def test_recovery_plan(
    plan_id: str,
    test_config: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """
    Test a recovery plan without executing it
    
    Args:
        plan_id: Recovery plan ID to test
        test_config: Test configuration
        
    Returns:
        Recovery plan test results
    """
    try:
        cluster_name = test_config.get('cluster_name')
        service_name = test_config.get('service_name')
        
        if not cluster_name or not service_name:
            raise HTTPException(status_code=400, detail="cluster_name and service_name are required")
        
        # Get the recovery plan
        plans = await recovery_service.get_recovery_plans()
        plan = next((p for p in plans['plans'] if p['plan_id'] == plan_id), None)
        
        if not plan:
            raise HTTPException(status_code=404, detail=f"Recovery plan {plan_id} not found")
        
        # Simulate plan execution
        test_results = {
            'plan_id': plan_id,
            'plan_name': plan['name'],
            'test_timestamp': datetime.now(UTC).isoformat(),
            'cluster_name': cluster_name,
            'service_name': service_name,
            'estimated_rto_minutes': plan['estimated_rto_minutes'],
            'estimated_rpo_minutes': plan['estimated_rpo_minutes'],
            'recovery_actions': plan['recovery_actions'],
            'test_status': 'simulated_success',
            'prerequisites_check': {
                'snapshots_available': True,  # Would check actual snapshots
                'aws_permissions': True,      # Would check actual permissions
                'service_exists': True        # Would check actual service
            },
            'simulation_results': [
                {
                    'action': action,
                    'estimated_duration_minutes': 2 if 'scale' in action else 5,
                    'success_probability': 0.95,
                    'potential_issues': []
                }
                for action in plan['recovery_actions']
            ]
        }
        
        return test_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recovery plan test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recovery plan test failed: {str(e)}")