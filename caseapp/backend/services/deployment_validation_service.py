"""
Deployment Validation and Testing Service
Provides automated smoke tests, API validation, and integration testing for deployed services
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional, Tuple
import structlog
import json
from dataclasses import dataclass
from enum import Enum
import boto3
from urllib.parse import urljoin

from core.aws_service import aws_service

logger = structlog.get_logger()

class ValidationStatus(Enum):
    """Validation test status"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"

class TestCategory(Enum):
    """Test category types"""
    SMOKE_TEST = "smoke_test"
    API_VALIDATION = "api_validation"
    INTEGRATION_TEST = "integration_test"
    PERFORMANCE_TEST = "performance_test"
    SECURITY_TEST = "security_test"

@dataclass
class ValidationTest:
    """Individual validation test"""
    name: str
    category: TestCategory
    description: str
    endpoint: Optional[str]
    method: str
    expected_status: int
    timeout_seconds: int
    retry_count: int
    critical: bool

@dataclass
class ValidationResult:
    """Validation test result"""
    test_name: str
    category: TestCategory
    status: ValidationStatus
    response_time_ms: float
    status_code: Optional[int]
    error_message: Optional[str]
    details: Dict[str, Any]
    timestamp: datetime

class DeploymentValidationService:
    """Service for deployment validation and testing"""
    
    def __init__(self):
        self.logger = logger.bind(component="deployment_validation")
        self.ecs = None
        self.elbv2 = None
        self.cloudwatch = None
        
        # Default test configuration
        self.default_timeout = 30
        self.default_retry_count = 3
        self.performance_threshold_ms = 2000
        
        # Test suites
        self.smoke_tests = self._define_smoke_tests()
        self.api_tests = self._define_api_tests()
        self.integration_tests = self._define_integration_tests()
    
    async def initialize(self):
        """Initialize AWS clients"""
        try:
            await aws_service.initialize()
            self.ecs = aws_service.get_client('ecs')
            self.elbv2 = aws_service.get_client('elbv2')
            self.cloudwatch = aws_service.get_client('cloudwatch')
            self.logger.info("Deployment validation service initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize deployment validation service: {str(e)}")
            raise
    
    def _define_smoke_tests(self) -> List[ValidationTest]:
        """Define smoke tests for basic functionality"""
        return [
            ValidationTest(
                name="health_check",
                category=TestCategory.SMOKE_TEST,
                description="Basic health check endpoint",
                endpoint="/health",
                method="GET",
                expected_status=200,
                timeout_seconds=10,
                retry_count=3,
                critical=True
            ),
            ValidationTest(
                name="readiness_check",
                category=TestCategory.SMOKE_TEST,
                description="Application readiness check",
                endpoint="/health/ready",
                method="GET",
                expected_status=200,
                timeout_seconds=15,
                retry_count=3,
                critical=True
            ),
            ValidationTest(
                name="liveness_check",
                category=TestCategory.SMOKE_TEST,
                description="Application liveness check",
                endpoint="/health/live",
                method="GET",
                expected_status=200,
                timeout_seconds=10,
                retry_count=2,
                critical=True
            ),
            ValidationTest(
                name="api_docs_access",
                category=TestCategory.SMOKE_TEST,
                description="API documentation accessibility",
                endpoint="/docs",
                method="GET",
                expected_status=200,
                timeout_seconds=10,
                retry_count=1,
                critical=False
            )
        ]
    
    def _define_api_tests(self) -> List[ValidationTest]:
        """Define API validation tests"""
        return [
            ValidationTest(
                name="api_v1_root",
                category=TestCategory.API_VALIDATION,
                description="API v1 root endpoint",
                endpoint="/api/v1/",
                method="GET",
                expected_status=200,
                timeout_seconds=10,
                retry_count=2,
                critical=True
            ),
            ValidationTest(
                name="cases_endpoint",
                category=TestCategory.API_VALIDATION,
                description="Cases API endpoint availability",
                endpoint="/api/v1/cases/",
                method="GET",
                expected_status=200,
                timeout_seconds=15,
                retry_count=2,
                critical=True
            ),
            ValidationTest(
                name="documents_endpoint",
                category=TestCategory.API_VALIDATION,
                description="Documents API endpoint availability",
                endpoint="/api/v1/documents/",
                method="GET",
                expected_status=200,
                timeout_seconds=15,
                retry_count=2,
                critical=True
            ),
            ValidationTest(
                name="monitoring_endpoint",
                category=TestCategory.API_VALIDATION,
                description="Monitoring API endpoint availability",
                endpoint="/api/v1/monitoring/health",
                method="GET",
                expected_status=200,
                timeout_seconds=10,
                retry_count=2,
                critical=False
            ),
            ValidationTest(
                name="diagnostics_endpoint",
                category=TestCategory.API_VALIDATION,
                description="Diagnostics API endpoint availability",
                endpoint="/api/v1/diagnostics/health",
                method="GET",
                expected_status=200,
                timeout_seconds=10,
                retry_count=2,
                critical=False
            )
        ]
    
    def _define_integration_tests(self) -> List[ValidationTest]:
        """Define integration tests for external services"""
        return [
            ValidationTest(
                name="database_connectivity",
                category=TestCategory.INTEGRATION_TEST,
                description="Database connection test",
                endpoint="/health/database",
                method="GET",
                expected_status=200,
                timeout_seconds=20,
                retry_count=3,
                critical=True
            ),
            ValidationTest(
                name="redis_connectivity",
                category=TestCategory.INTEGRATION_TEST,
                description="Redis connection test",
                endpoint="/health/redis",
                method="GET",
                expected_status=200,
                timeout_seconds=15,
                retry_count=3,
                critical=True
            ),
            ValidationTest(
                name="aws_services_connectivity",
                category=TestCategory.INTEGRATION_TEST,
                description="AWS services connectivity test",
                endpoint="/health/aws",
                method="GET",
                expected_status=200,
                timeout_seconds=30,
                retry_count=2,
                critical=True
            ),
            ValidationTest(
                name="s3_access",
                category=TestCategory.INTEGRATION_TEST,
                description="S3 bucket access test",
                endpoint="/api/v1/diagnostics/s3-test",
                method="GET",
                expected_status=200,
                timeout_seconds=20,
                retry_count=2,
                critical=False
            )
        ]
    
    async def validate_deployment(self,
                                cluster_name: str,
                                service_name: str,
                                load_balancer_dns: Optional[str] = None,
                                test_categories: Optional[List[TestCategory]] = None) -> Dict[str, Any]:
        """
        Validate a deployment with comprehensive testing
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            load_balancer_dns: Load balancer DNS name (auto-detected if not provided)
            test_categories: Categories of tests to run (all if not specified)
            
        Returns:
            Comprehensive validation results
        """
        try:
            self.logger.info(f"Starting deployment validation for {service_name}", cluster=cluster_name)
            
            # Get service information and load balancer DNS
            if not load_balancer_dns:
                load_balancer_dns = await self._get_service_load_balancer_dns(cluster_name, service_name)
            
            if not load_balancer_dns:
                raise ValueError(f"Could not determine load balancer DNS for service {service_name}")
            
            base_url = f"http://{load_balancer_dns}"
            
            # Determine which test categories to run
            if test_categories is None:
                test_categories = list(TestCategory)
            
            # Collect all tests to run
            all_tests = []
            for category in test_categories:
                if category == TestCategory.SMOKE_TEST:
                    all_tests.extend(self.smoke_tests)
                elif category == TestCategory.API_VALIDATION:
                    all_tests.extend(self.api_tests)
                elif category == TestCategory.INTEGRATION_TEST:
                    all_tests.extend(self.integration_tests)
            
            # Run tests
            results = []
            critical_failures = 0
            
            for test in all_tests:
                try:
                    result = await self._run_validation_test(base_url, test)
                    results.append(result)
                    
                    if result.status == ValidationStatus.FAILED and test.critical:
                        critical_failures += 1
                        
                except Exception as e:
                    self.logger.error(f"Test {test.name} failed with exception: {str(e)}")
                    results.append(ValidationResult(
                        test_name=test.name,
                        category=test.category,
                        status=ValidationStatus.FAILED,
                        response_time_ms=0,
                        status_code=None,
                        error_message=str(e),
                        details={},
                        timestamp=datetime.now(UTC)
                    ))
                    
                    if test.critical:
                        critical_failures += 1
            
            # Calculate summary statistics
            total_tests = len(results)
            passed_tests = len([r for r in results if r.status == ValidationStatus.PASSED])
            failed_tests = len([r for r in results if r.status == ValidationStatus.FAILED])
            warning_tests = len([r for r in results if r.status == ValidationStatus.WARNING])
            
            # Determine overall status
            if critical_failures > 0:
                overall_status = "critical_failure"
            elif failed_tests > 0:
                overall_status = "failure"
            elif warning_tests > 0:
                overall_status = "warning"
            else:
                overall_status = "success"
            
            # Calculate performance metrics
            response_times = [r.response_time_ms for r in results if r.response_time_ms > 0]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            validation_summary = {
                'cluster_name': cluster_name,
                'service_name': service_name,
                'load_balancer_dns': load_balancer_dns,
                'validation_timestamp': datetime.now(UTC).isoformat(),
                'overall_status': overall_status,
                'summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'failed_tests': failed_tests,
                    'warning_tests': warning_tests,
                    'critical_failures': critical_failures,
                    'success_rate_percentage': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                    'average_response_time_ms': avg_response_time
                },
                'test_categories_run': [cat.value for cat in test_categories],
                'results': [
                    {
                        'test_name': r.test_name,
                        'category': r.category.value,
                        'status': r.status.value,
                        'response_time_ms': r.response_time_ms,
                        'status_code': r.status_code,
                        'error_message': r.error_message,
                        'details': r.details,
                        'timestamp': r.timestamp.isoformat()
                    }
                    for r in results
                ]
            }
            
            self.logger.info(
                f"Deployment validation completed for {service_name}",
                overall_status=overall_status,
                success_rate=validation_summary['summary']['success_rate_percentage']
            )
            
            return validation_summary
            
        except Exception as e:
            self.logger.error(f"Deployment validation failed: {str(e)}")
            raise
    
    async def _get_service_load_balancer_dns(self, cluster_name: str, service_name: str) -> Optional[str]:
        """Get load balancer DNS name for ECS service"""
        
        try:
            # Get service details
            response = await asyncio.to_thread(
                self.ecs.describe_services,
                cluster=cluster_name,
                services=[service_name]
            )
            
            if not response['services']:
                return None
            
            service = response['services'][0]
            
            # Look for load balancer configuration
            load_balancers = service.get('loadBalancers', [])
            if not load_balancers:
                return None
            
            # Get target group ARN
            target_group_arn = load_balancers[0].get('targetGroupArn')
            if not target_group_arn:
                return None
            
            # Get load balancer ARN from target group
            tg_response = await asyncio.to_thread(
                self.elbv2.describe_target_groups,
                TargetGroupArns=[target_group_arn]
            )
            
            if not tg_response['TargetGroups']:
                return None
            
            lb_arns = tg_response['TargetGroups'][0].get('LoadBalancerArns', [])
            if not lb_arns:
                return None
            
            # Get load balancer DNS name
            lb_response = await asyncio.to_thread(
                self.elbv2.describe_load_balancers,
                LoadBalancerArns=[lb_arns[0]]
            )
            
            if not lb_response['LoadBalancers']:
                return None
            
            return lb_response['LoadBalancers'][0]['DNSName']
            
        except Exception as e:
            self.logger.error(f"Failed to get load balancer DNS: {str(e)}")
            return None
    
    async def _run_validation_test(self, base_url: str, test: ValidationTest) -> ValidationResult:
        """Run a single validation test"""
        
        start_time = datetime.now(UTC)
        
        for attempt in range(test.retry_count + 1):
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=test.timeout_seconds)
                ) as session:
                    
                    url = urljoin(base_url, test.endpoint) if test.endpoint else base_url
                    
                    async with session.request(test.method, url) as response:
                        end_time = datetime.now(UTC)
                        response_time_ms = (end_time - start_time).total_seconds() * 1000
                        
                        # Read response content for analysis
                        try:
                            response_text = await response.text()
                            response_json = json.loads(response_text) if response_text.strip().startswith('{') else None
                        except:
                            response_text = ""
                            response_json = None
                        
                        # Determine test status
                        if response.status == test.expected_status:
                            status = ValidationStatus.PASSED
                            error_message = None
                        else:
                            status = ValidationStatus.FAILED
                            error_message = f"Expected status {test.expected_status}, got {response.status}"
                        
                        # Check for performance warnings
                        if status == ValidationStatus.PASSED and response_time_ms > self.performance_threshold_ms:
                            status = ValidationStatus.WARNING
                            error_message = f"Response time {response_time_ms:.0f}ms exceeds threshold {self.performance_threshold_ms}ms"
                        
                        return ValidationResult(
                            test_name=test.name,
                            category=test.category,
                            status=status,
                            response_time_ms=response_time_ms,
                            status_code=response.status,
                            error_message=error_message,
                            details={
                                'url': url,
                                'method': test.method,
                                'attempt': attempt + 1,
                                'response_size_bytes': len(response_text),
                                'has_json_response': response_json is not None
                            },
                            timestamp=end_time
                        )
                        
            except asyncio.TimeoutError:
                if attempt < test.retry_count:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                
                return ValidationResult(
                    test_name=test.name,
                    category=test.category,
                    status=ValidationStatus.FAILED,
                    response_time_ms=test.timeout_seconds * 1000,
                    status_code=None,
                    error_message=f"Request timed out after {test.timeout_seconds} seconds",
                    details={'url': urljoin(base_url, test.endpoint), 'timeout_seconds': test.timeout_seconds},
                    timestamp=datetime.now(UTC)
                )
                
            except Exception as e:
                if attempt < test.retry_count:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                
                return ValidationResult(
                    test_name=test.name,
                    category=test.category,
                    status=ValidationStatus.FAILED,
                    response_time_ms=0,
                    status_code=None,
                    error_message=str(e),
                    details={'url': urljoin(base_url, test.endpoint), 'exception_type': type(e).__name__},
                    timestamp=datetime.now(UTC)
                )
        
        # Should not reach here, but return failure as fallback
        return ValidationResult(
            test_name=test.name,
            category=test.category,
            status=ValidationStatus.FAILED,
            response_time_ms=0,
            status_code=None,
            error_message="Unexpected test execution path",
            details={},
            timestamp=datetime.now(UTC)
        )
    
    async def run_performance_tests(self,
                                  base_url: str,
                                  concurrent_requests: int = 10,
                                  duration_seconds: int = 60) -> Dict[str, Any]:
        """
        Run performance tests against the deployed service
        
        Args:
            base_url: Base URL of the service
            concurrent_requests: Number of concurrent requests
            duration_seconds: Duration of the test
            
        Returns:
            Performance test results
        """
        try:
            self.logger.info(f"Starting performance tests", concurrent_requests=concurrent_requests, duration=duration_seconds)
            
            start_time = datetime.now(UTC)
            end_time = start_time + timedelta(seconds=duration_seconds)
            
            # Performance test endpoints
            test_endpoints = [
                '/health',
                '/health/ready',
                '/api/v1/',
                '/api/v1/cases/'
            ]
            
            # Track results
            total_requests = 0
            successful_requests = 0
            failed_requests = 0
            response_times = []
            error_counts = {}
            
            # Run concurrent requests
            async def make_request(session, endpoint):
                nonlocal total_requests, successful_requests, failed_requests
                
                try:
                    request_start = datetime.now(UTC)
                    async with session.get(urljoin(base_url, endpoint)) as response:
                        request_end = datetime.now(UTC)
                        response_time = (request_end - request_start).total_seconds() * 1000
                        
                        total_requests += 1
                        response_times.append(response_time)
                        
                        if 200 <= response.status < 400:
                            successful_requests += 1
                        else:
                            failed_requests += 1
                            error_key = f"HTTP_{response.status}"
                            error_counts[error_key] = error_counts.get(error_key, 0) + 1
                            
                except Exception as e:
                    total_requests += 1
                    failed_requests += 1
                    error_key = type(e).__name__
                    error_counts[error_key] = error_counts.get(error_key, 0) + 1
            
            # Create session and run tests
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                
                tasks = []
                
                while datetime.now(UTC) < end_time:
                    # Create batch of concurrent requests
                    for _ in range(concurrent_requests):
                        endpoint = test_endpoints[total_requests % len(test_endpoints)]
                        task = asyncio.create_task(make_request(session, endpoint))
                        tasks.append(task)
                    
                    # Wait for batch to complete
                    await asyncio.gather(*tasks, return_exceptions=True)
                    tasks.clear()
                    
                    # Small delay between batches
                    await asyncio.sleep(0.1)
            
            # Calculate statistics
            actual_duration = (datetime.now(UTC) - start_time).total_seconds()
            requests_per_second = total_requests / actual_duration if actual_duration > 0 else 0
            
            if response_times:
                response_times.sort()
                avg_response_time = sum(response_times) / len(response_times)
                p50_response_time = response_times[len(response_times) // 2]
                p95_response_time = response_times[int(len(response_times) * 0.95)]
                p99_response_time = response_times[int(len(response_times) * 0.99)]
                min_response_time = min(response_times)
                max_response_time = max(response_times)
            else:
                avg_response_time = p50_response_time = p95_response_time = p99_response_time = 0
                min_response_time = max_response_time = 0
            
            success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'test_configuration': {
                    'base_url': base_url,
                    'concurrent_requests': concurrent_requests,
                    'planned_duration_seconds': duration_seconds,
                    'actual_duration_seconds': actual_duration
                },
                'results': {
                    'total_requests': total_requests,
                    'successful_requests': successful_requests,
                    'failed_requests': failed_requests,
                    'success_rate_percentage': success_rate,
                    'requests_per_second': requests_per_second
                },
                'response_times': {
                    'average_ms': avg_response_time,
                    'min_ms': min_response_time,
                    'max_ms': max_response_time,
                    'p50_ms': p50_response_time,
                    'p95_ms': p95_response_time,
                    'p99_ms': p99_response_time
                },
                'errors': error_counts,
                'timestamp': datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Performance test failed: {str(e)}")
            raise
    
    async def validate_service_health_after_deployment(self,
                                                     cluster_name: str,
                                                     service_name: str,
                                                     wait_timeout_seconds: int = 300) -> Dict[str, Any]:
        """
        Wait for service to be healthy after deployment and validate
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            wait_timeout_seconds: Maximum time to wait for service to be healthy
            
        Returns:
            Service health validation results
        """
        try:
            self.logger.info(f"Waiting for service {service_name} to be healthy after deployment")
            
            start_time = datetime.now(UTC)
            end_time = start_time + timedelta(seconds=wait_timeout_seconds)
            
            while datetime.now(UTC) < end_time:
                # Check service status
                response = await asyncio.to_thread(
                    self.ecs.describe_services,
                    cluster=cluster_name,
                    services=[service_name]
                )
                
                if not response['services']:
                    raise ValueError(f"Service {service_name} not found")
                
                service = response['services'][0]
                
                # Check if service is stable and running
                if (service['status'] == 'ACTIVE' and 
                    service['runningCount'] >= service['desiredCount'] and
                    service['deploymentStatus'] == 'PRIMARY'):
                    
                    # Service appears healthy, run validation tests
                    validation_results = await self.validate_deployment(
                        cluster_name, 
                        service_name,
                        test_categories=[TestCategory.SMOKE_TEST, TestCategory.API_VALIDATION]
                    )
                    
                    if validation_results['overall_status'] in ['success', 'warning']:
                        return {
                            'status': 'healthy',
                            'wait_time_seconds': (datetime.now(UTC) - start_time).total_seconds(),
                            'service_status': service['status'],
                            'running_count': service['runningCount'],
                            'desired_count': service['desiredCount'],
                            'validation_results': validation_results
                        }
                
                # Wait before next check
                await asyncio.sleep(10)
            
            # Timeout reached
            return {
                'status': 'timeout',
                'wait_time_seconds': wait_timeout_seconds,
                'message': f'Service did not become healthy within {wait_timeout_seconds} seconds'
            }
            
        except Exception as e:
            self.logger.error(f"Service health validation failed: {str(e)}")
            return {
                'status': 'error',
                'error_message': str(e)
            }