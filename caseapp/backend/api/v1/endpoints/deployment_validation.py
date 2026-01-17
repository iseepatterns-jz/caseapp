"""
Deployment Validation API Endpoints
Provides endpoints for deployment validation, testing, and health checks
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, List, Any, Optional
import structlog
from datetime import datetime, UTC

from services.deployment_validation_service import (
    DeploymentValidationService, 
    TestCategory, 
    ValidationStatus
)

logger = structlog.get_logger()
router = APIRouter()

# Initialize service
validation_service = DeploymentValidationService()

@router.on_event("startup")
async def startup_event():
    """Initialize deployment validation service on startup"""
    try:
        await validation_service.initialize()
        logger.info("Deployment validation service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize deployment validation service: {str(e)}")

@router.post("/validate/{cluster_name}/{service_name}")
async def validate_deployment(
    cluster_name: str,
    service_name: str,
    load_balancer_dns: Optional[str] = Query(None, description="Load balancer DNS (auto-detected if not provided)"),
    test_categories: Optional[List[str]] = Query(None, description="Test categories to run (smoke_test, api_validation, integration_test)")
) -> Dict[str, Any]:
    """
    Validate a deployment with comprehensive testing
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        load_balancer_dns: Load balancer DNS name
        test_categories: Categories of tests to run
        
    Returns:
        Comprehensive validation results
    """
    try:
        logger.info(f"Starting deployment validation for {service_name}", cluster=cluster_name)
        
        # Convert test categories from strings to enums
        categories = None
        if test_categories:
            try:
                categories = [TestCategory(cat) for cat in test_categories]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid test category: {str(e)}")
        
        # Run validation
        results = await validation_service.validate_deployment(
            cluster_name=cluster_name,
            service_name=service_name,
            load_balancer_dns=load_balancer_dns,
            test_categories=categories
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Deployment validation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deployment validation failed: {str(e)}")

@router.post("/smoke-test/{cluster_name}/{service_name}")
async def run_smoke_tests(
    cluster_name: str,
    service_name: str,
    load_balancer_dns: Optional[str] = Query(None, description="Load balancer DNS (auto-detected if not provided)")
) -> Dict[str, Any]:
    """
    Run smoke tests for basic functionality validation
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        load_balancer_dns: Load balancer DNS name
        
    Returns:
        Smoke test results
    """
    try:
        logger.info(f"Running smoke tests for {service_name}", cluster=cluster_name)
        
        results = await validation_service.validate_deployment(
            cluster_name=cluster_name,
            service_name=service_name,
            load_balancer_dns=load_balancer_dns,
            test_categories=[TestCategory.SMOKE_TEST]
        )
        
        return {
            'test_type': 'smoke_tests',
            'cluster_name': cluster_name,
            'service_name': service_name,
            'timestamp': datetime.now(UTC).isoformat(),
            **results
        }
        
    except Exception as e:
        logger.error(f"Smoke tests failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Smoke tests failed: {str(e)}")

@router.post("/api-validation/{cluster_name}/{service_name}")
async def validate_api_endpoints(
    cluster_name: str,
    service_name: str,
    load_balancer_dns: Optional[str] = Query(None, description="Load balancer DNS (auto-detected if not provided)")
) -> Dict[str, Any]:
    """
    Validate API endpoints functionality
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        load_balancer_dns: Load balancer DNS name
        
    Returns:
        API validation results
    """
    try:
        logger.info(f"Validating API endpoints for {service_name}", cluster=cluster_name)
        
        results = await validation_service.validate_deployment(
            cluster_name=cluster_name,
            service_name=service_name,
            load_balancer_dns=load_balancer_dns,
            test_categories=[TestCategory.API_VALIDATION]
        )
        
        return {
            'test_type': 'api_validation',
            'cluster_name': cluster_name,
            'service_name': service_name,
            'timestamp': datetime.now(UTC).isoformat(),
            **results
        }
        
    except Exception as e:
        logger.error(f"API validation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API validation failed: {str(e)}")

@router.post("/integration-test/{cluster_name}/{service_name}")
async def run_integration_tests(
    cluster_name: str,
    service_name: str,
    load_balancer_dns: Optional[str] = Query(None, description="Load balancer DNS (auto-detected if not provided)")
) -> Dict[str, Any]:
    """
    Run integration tests for external service connectivity
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        load_balancer_dns: Load balancer DNS name
        
    Returns:
        Integration test results
    """
    try:
        logger.info(f"Running integration tests for {service_name}", cluster=cluster_name)
        
        results = await validation_service.validate_deployment(
            cluster_name=cluster_name,
            service_name=service_name,
            load_balancer_dns=load_balancer_dns,
            test_categories=[TestCategory.INTEGRATION_TEST]
        )
        
        return {
            'test_type': 'integration_tests',
            'cluster_name': cluster_name,
            'service_name': service_name,
            'timestamp': datetime.now(UTC).isoformat(),
            **results
        }
        
    except Exception as e:
        logger.error(f"Integration tests failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Integration tests failed: {str(e)}")

@router.post("/performance-test")
async def run_performance_tests(
    test_config: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """
    Run performance tests against the deployed service
    
    Args:
        test_config: Performance test configuration
        
    Returns:
        Performance test results
    """
    try:
        base_url = test_config.get('base_url')
        if not base_url:
            raise HTTPException(status_code=400, detail="base_url is required")
        
        concurrent_requests = test_config.get('concurrent_requests', 10)
        duration_seconds = test_config.get('duration_seconds', 60)
        
        # Validate parameters
        if concurrent_requests < 1 or concurrent_requests > 100:
            raise HTTPException(status_code=400, detail="concurrent_requests must be between 1 and 100")
        
        if duration_seconds < 10 or duration_seconds > 600:
            raise HTTPException(status_code=400, detail="duration_seconds must be between 10 and 600")
        
        logger.info(f"Running performance tests", base_url=base_url, concurrent=concurrent_requests, duration=duration_seconds)
        
        results = await validation_service.run_performance_tests(
            base_url=base_url,
            concurrent_requests=concurrent_requests,
            duration_seconds=duration_seconds
        )
        
        return {
            'test_type': 'performance_test',
            'timestamp': datetime.now(UTC).isoformat(),
            **results
        }
        
    except Exception as e:
        logger.error(f"Performance tests failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Performance tests failed: {str(e)}")

@router.post("/wait-for-healthy/{cluster_name}/{service_name}")
async def wait_for_service_healthy(
    cluster_name: str,
    service_name: str,
    timeout_seconds: int = Query(300, ge=60, le=1800, description="Maximum wait time in seconds")
) -> Dict[str, Any]:
    """
    Wait for service to be healthy after deployment
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        timeout_seconds: Maximum wait time in seconds
        
    Returns:
        Service health validation results
    """
    try:
        logger.info(f"Waiting for service {service_name} to be healthy", cluster=cluster_name, timeout=timeout_seconds)
        
        results = await validation_service.validate_service_health_after_deployment(
            cluster_name=cluster_name,
            service_name=service_name,
            wait_timeout_seconds=timeout_seconds
        )
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'timeout_seconds': timeout_seconds,
            'timestamp': datetime.now(UTC).isoformat(),
            **results
        }
        
    except Exception as e:
        logger.error(f"Service health validation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Service health validation failed: {str(e)}")

@router.get("/test-definitions")
async def get_test_definitions() -> Dict[str, Any]:
    """
    Get available test definitions and categories
    
    Returns:
        Test definitions and configuration
    """
    try:
        return {
            'test_categories': [cat.value for cat in TestCategory],
            'validation_statuses': [status.value for status in ValidationStatus],
            'smoke_tests': [
                {
                    'name': test.name,
                    'description': test.description,
                    'endpoint': test.endpoint,
                    'method': test.method,
                    'expected_status': test.expected_status,
                    'critical': test.critical
                }
                for test in validation_service.smoke_tests
            ],
            'api_tests': [
                {
                    'name': test.name,
                    'description': test.description,
                    'endpoint': test.endpoint,
                    'method': test.method,
                    'expected_status': test.expected_status,
                    'critical': test.critical
                }
                for test in validation_service.api_tests
            ],
            'integration_tests': [
                {
                    'name': test.name,
                    'description': test.description,
                    'endpoint': test.endpoint,
                    'method': test.method,
                    'expected_status': test.expected_status,
                    'critical': test.critical
                }
                for test in validation_service.integration_tests
            ],
            'configuration': {
                'default_timeout_seconds': validation_service.default_timeout,
                'default_retry_count': validation_service.default_retry_count,
                'performance_threshold_ms': validation_service.performance_threshold_ms
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get test definitions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get test definitions: {str(e)}")

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for deployment validation service"""
    
    try:
        # Basic health check - verify AWS clients are available
        if validation_service.ecs is None:
            await validation_service.initialize()
        
        return {
            'status': 'healthy',
            'service': 'deployment_validation',
            'timestamp': datetime.now(UTC).isoformat(),
            'aws_clients_initialized': all([
                validation_service.ecs is not None,
                validation_service.elbv2 is not None,
                validation_service.cloudwatch is not None
            ]),
            'test_suites_available': {
                'smoke_tests': len(validation_service.smoke_tests),
                'api_tests': len(validation_service.api_tests),
                'integration_tests': len(validation_service.integration_tests)
            }
        }
        
    except Exception as e:
        logger.error(f"Deployment validation service health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'service': 'deployment_validation',
            'timestamp': datetime.now(UTC).isoformat(),
            'error': str(e)
        }

@router.get("/status/{cluster_name}/{service_name}")
async def get_service_status(
    cluster_name: str,
    service_name: str
) -> Dict[str, Any]:
    """
    Get current ECS service status
    
    Args:
        cluster_name: ECS cluster name
        service_name: ECS service name
        
    Returns:
        Current service status information
    """
    try:
        logger.info(f"Getting service status for {service_name}", cluster=cluster_name)
        
        # Get load balancer DNS first
        load_balancer_dns = await validation_service._get_service_load_balancer_dns(cluster_name, service_name)
        
        return {
            'cluster_name': cluster_name,
            'service_name': service_name,
            'load_balancer_dns': load_balancer_dns,
            'timestamp': datetime.now(UTC).isoformat(),
            'status': 'available' if load_balancer_dns else 'not_available'
        }
        
    except Exception as e:
        logger.error(f"Failed to get service status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get service status: {str(e)}")