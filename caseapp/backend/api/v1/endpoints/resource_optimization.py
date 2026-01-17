"""
Resource Optimization API Endpoints
Provides endpoints for automated resource optimization and recommendations
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, List, Any, Optional
import structlog
from datetime import datetime, UTC

from services.resource_optimization_service import ResourceOptimizationService, OptimizationRecommendation

logger = structlog.get_logger()
router = APIRouter()

# Initialize service
optimization_service = ResourceOptimizationService()

@router.on_event("startup")
async def startup_event():
    """Initialize optimization service on startup"""
    try:
        await optimization_service.initialize()
        logger.info("Resource optimization service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize resource optimization service: {str(e)}")

@router.get("/analyze/{cluster_name}/{service_name}")
async def analyze_resource_usage(
    cluster_name: str,
    service_name: str,
    hours_back: int = Query(24, ge=1, le=168, description="Hours of historical data to analyze (1-168)")
) -> Dict[str, Any]:
    """
    Analyze resource usage patterns for an ECS service
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        hours_back: Hours of historical data to analyze
        
    Returns:
        Resource usage analysis results
    """
    try:
        logger.info(f"Analyzing resource usage for {service_name}", cluster=cluster_name, hours=hours_back)
        
        metrics = await optimization_service.analyze_resource_usage(
            cluster_name, service_name, hours_back
        )
        
        # Calculate summary statistics
        if metrics:
            cpu_values = [m.cpu_utilization for m in metrics if m.cpu_utilization > 0]
            memory_values = [m.memory_utilization for m in metrics if m.memory_utilization > 0]
            response_times = [m.response_time for m in metrics if m.response_time > 0]
            error_rates = [m.error_rate for m in metrics if m.error_rate >= 0]
            
            summary = {
                'cpu_utilization': {
                    'average': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    'maximum': max(cpu_values) if cpu_values else 0,
                    'minimum': min(cpu_values) if cpu_values else 0
                },
                'memory_utilization': {
                    'average': sum(memory_values) / len(memory_values) if memory_values else 0,
                    'maximum': max(memory_values) if memory_values else 0,
                    'minimum': min(memory_values) if memory_values else 0
                },
                'response_time': {
                    'average': sum(response_times) / len(response_times) if response_times else 0,
                    'maximum': max(response_times) if response_times else 0,
                    'p95': sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
                },
                'error_rate': {
                    'average': sum(error_rates) / len(error_rates) if error_rates else 0,
                    'maximum': max(error_rates) if error_rates else 0
                }
            }
        else:
            summary = {
                'cpu_utilization': {'average': 0, 'maximum': 0, 'minimum': 0},
                'memory_utilization': {'average': 0, 'maximum': 0, 'minimum': 0},
                'response_time': {'average': 0, 'maximum': 0, 'p95': 0},
                'error_rate': {'average': 0, 'maximum': 0}
            }
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'analysis_period_hours': hours_back,
            'data_points_analyzed': len(metrics),
            'analysis_timestamp': datetime.now(UTC).isoformat(),
            'summary_statistics': summary,
            'detailed_metrics': [
                {
                    'timestamp': m.timestamp.isoformat(),
                    'cpu_utilization': m.cpu_utilization,
                    'memory_utilization': m.memory_utilization,
                    'network_in_bytes': m.network_in,
                    'network_out_bytes': m.network_out,
                    'request_count': m.request_count,
                    'response_time_ms': m.response_time,
                    'error_rate_percent': m.error_rate
                }
                for m in metrics[-50:]  # Return last 50 data points for detailed view
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze resource usage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Resource analysis failed: {str(e)}")

@router.get("/recommendations/{cluster_name}/{service_name}")
async def get_optimization_recommendations(
    cluster_name: str,
    service_name: str,
    hours_back: int = Query(24, ge=1, le=168, description="Hours of historical data to analyze"),
    include_low_priority: bool = Query(False, description="Include low priority recommendations")
) -> Dict[str, Any]:
    """
    Get optimization recommendations for an ECS service
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        hours_back: Hours of historical data to analyze
        include_low_priority: Whether to include low priority recommendations
        
    Returns:
        Optimization recommendations
    """
    try:
        logger.info(f"Generating optimization recommendations for {service_name}", cluster=cluster_name)
        
        # Analyze resource usage
        metrics = await optimization_service.analyze_resource_usage(
            cluster_name, service_name, hours_back
        )
        
        # Generate recommendations
        recommendations = await optimization_service.generate_optimization_recommendations(
            cluster_name, service_name, metrics
        )
        
        # Filter recommendations if needed
        if not include_low_priority:
            recommendations = [r for r in recommendations if r.priority != 'low']
        
        # Calculate potential impact
        cost_savings = sum(r.expected_savings or 0 for r in recommendations)
        performance_improvements = len([r for r in recommendations if 'performance' in r.optimization_type.value])
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'analysis_period_hours': hours_back,
            'recommendation_timestamp': datetime.now(UTC).isoformat(),
            'total_recommendations': len(recommendations),
            'high_priority_count': len([r for r in recommendations if r.priority == 'high']),
            'medium_priority_count': len([r for r in recommendations if r.priority == 'medium']),
            'low_priority_count': len([r for r in recommendations if r.priority == 'low']),
            'estimated_cost_savings_percentage': cost_savings * 100,
            'performance_improvement_opportunities': performance_improvements,
            'recommendations': [
                {
                    'id': f"{r.resource_type}_{r.optimization_type.value}_{hash(r.reasoning) % 10000}",
                    'resource_type': r.resource_type,
                    'resource_name': r.resource_name,
                    'optimization_type': r.optimization_type.value,
                    'priority': r.priority,
                    'confidence_score': r.confidence_score,
                    'reasoning': r.reasoning,
                    'current_configuration': r.current_config,
                    'recommended_configuration': r.recommended_config,
                    'expected_cost_savings_percentage': (r.expected_savings or 0) * 100,
                    'expected_performance_impact': r.expected_performance_impact,
                    'implementation_complexity': self._get_implementation_complexity(r)
                }
                for r in recommendations
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to generate optimization recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}")

def _get_implementation_complexity(recommendation: OptimizationRecommendation) -> str:
    """Determine implementation complexity for a recommendation"""
    
    if recommendation.resource_type == 'ECS_TASK_COUNT':
        return 'low'  # Simple service update
    elif recommendation.resource_type in ['ECS_CPU', 'ECS_MEMORY']:
        return 'medium'  # Requires new task definition
    else:
        return 'high'  # May require code or architecture changes

@router.post("/apply/{cluster_name}/{service_name}")
async def apply_optimization_recommendation(
    cluster_name: str,
    service_name: str,
    recommendation_data: Dict[str, Any] = Body(...),
    dry_run: bool = Query(True, description="Perform dry run without making actual changes")
) -> Dict[str, Any]:
    """
    Apply an optimization recommendation
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        recommendation_data: Recommendation data to apply
        dry_run: Whether to perform a dry run
        
    Returns:
        Application result
    """
    try:
        logger.info(
            f"Applying optimization recommendation for {service_name}",
            cluster=cluster_name,
            dry_run=dry_run,
            resource_type=recommendation_data.get('resource_type')
        )
        
        # Reconstruct recommendation object
        from services.resource_optimization_service import OptimizationType
        
        recommendation = OptimizationRecommendation(
            resource_type=recommendation_data['resource_type'],
            resource_name=recommendation_data['resource_name'],
            optimization_type=OptimizationType(recommendation_data['optimization_type']),
            current_config=recommendation_data['current_configuration'],
            recommended_config=recommendation_data['recommended_configuration'],
            expected_savings=recommendation_data.get('expected_cost_savings_percentage', 0) / 100,
            expected_performance_impact=recommendation_data['expected_performance_impact'],
            confidence_score=recommendation_data['confidence_score'],
            reasoning=recommendation_data['reasoning'],
            priority=recommendation_data['priority']
        )
        
        # Apply the recommendation
        result = await optimization_service.apply_optimization_recommendation(
            cluster_name, service_name, recommendation, dry_run
        )
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'recommendation_id': recommendation_data.get('id'),
            'dry_run': dry_run,
            'application_timestamp': datetime.now(UTC).isoformat(),
            'result': result
        }
        
    except Exception as e:
        logger.error(f"Failed to apply optimization recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation application failed: {str(e)}")

@router.get("/summary/{cluster_name}/{service_name}")
async def get_optimization_summary(
    cluster_name: str,
    service_name: str
) -> Dict[str, Any]:
    """
    Get comprehensive optimization summary for an ECS service
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        
    Returns:
        Comprehensive optimization summary
    """
    try:
        logger.info(f"Getting optimization summary for {service_name}", cluster=cluster_name)
        
        summary = await optimization_service.get_optimization_summary(cluster_name, service_name)
        
        return {
            'summary_timestamp': datetime.now(UTC).isoformat(),
            **summary
        }
        
    except Exception as e:
        logger.error(f"Failed to get optimization summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Optimization summary failed: {str(e)}")

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for resource optimization service"""
    
    try:
        # Basic health check - verify AWS clients are available
        if optimization_service.cloudwatch is None:
            await optimization_service.initialize()
        
        return {
            'status': 'healthy',
            'service': 'resource_optimization',
            'timestamp': datetime.now(UTC).isoformat(),
            'aws_clients_initialized': all([
                optimization_service.cloudwatch is not None,
                optimization_service.ecs is not None,
                optimization_service.application_autoscaling is not None
            ])
        }
        
    except Exception as e:
        logger.error(f"Resource optimization service health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'service': 'resource_optimization',
            'timestamp': datetime.now(UTC).isoformat(),
            'error': str(e)
        }

@router.get("/config")
async def get_optimization_config() -> Dict[str, Any]:
    """Get current optimization configuration and thresholds"""
    
    return {
        'thresholds': {
            'cpu_high_threshold': optimization_service.cpu_high_threshold,
            'cpu_low_threshold': optimization_service.cpu_low_threshold,
            'memory_high_threshold': optimization_service.memory_high_threshold,
            'memory_low_threshold': optimization_service.memory_low_threshold,
            'response_time_threshold': optimization_service.response_time_threshold,
            'error_rate_threshold': optimization_service.error_rate_threshold
        },
        'features': {
            'cost_optimization_enabled': optimization_service.cost_optimization_enabled,
            'performance_optimization_enabled': optimization_service.performance_optimization_enabled
        },
        'service_info': {
            'name': 'Resource Optimization Service',
            'version': '1.0.0',
            'description': 'Automated resource optimization based on usage patterns and performance metrics'
        }
    }

@router.put("/config")
async def update_optimization_config(
    config_update: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Update optimization configuration and thresholds"""
    
    try:
        updated_fields = []
        
        # Update thresholds if provided
        thresholds = config_update.get('thresholds', {})
        for threshold_name, value in thresholds.items():
            if hasattr(optimization_service, threshold_name):
                setattr(optimization_service, threshold_name, value)
                updated_fields.append(threshold_name)
        
        # Update feature flags if provided
        features = config_update.get('features', {})
        for feature_name, value in features.items():
            if hasattr(optimization_service, feature_name):
                setattr(optimization_service, feature_name, value)
                updated_fields.append(feature_name)
        
        logger.info(f"Updated optimization configuration", updated_fields=updated_fields)
        
        return {
            'status': 'updated',
            'updated_fields': updated_fields,
            'timestamp': datetime.now(UTC).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to update optimization configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Configuration update failed: {str(e)}")