"""
Deployment Orchestration Service
Unified orchestration of monitoring, alerting, recovery, and validation systems
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import structlog
from dataclasses import dataclass
from enum import Enum

from services.deployment_monitoring_service import DeploymentMonitoringService
from services.comprehensive_health_service import ComprehensiveHealthService
from services.diagnostic_service import DiagnosticService
from services.resource_optimization_service import ResourceOptimizationService
from services.deployment_validation_service import DeploymentValidationService, TestCategory
from services.disaster_recovery_service import DisasterRecoveryService

logger = structlog.get_logger()

class OrchestrationPhase(Enum):
    """Deployment orchestration phases"""
    PRE_DEPLOYMENT = "pre_deployment"
    DEPLOYMENT = "deployment"
    POST_DEPLOYMENT = "post_deployment"
    MONITORING = "monitoring"
    OPTIMIZATION = "optimization"

class OrchestrationStatus(Enum):
    """Orchestration status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    WARNING = "warning"

@dataclass
class OrchestrationResult:
    """Result of orchestration phase"""
    phase: OrchestrationPhase
    status: OrchestrationStatus
    duration_seconds: float
    details: Dict[str, Any]
    error_message: Optional[str] = None

class DeploymentOrchestrationService:
    """Unified deployment orchestration service"""
    
    def __init__(self):
        self.logger = logger.bind(component="deployment_orchestration")
        
        # Initialize component services
        self.monitoring_service = DeploymentMonitoringService()
        self.health_service = ComprehensiveHealthService()
        self.diagnostic_service = DiagnosticService()
        self.optimization_service = ResourceOptimizationService()
        self.validation_service = DeploymentValidationService()
        self.recovery_service = DisasterRecoveryService()
        
        # Configuration
        self.auto_optimization_enabled = True
        self.auto_recovery_enabled = True
        self.validation_timeout_minutes = 10
        self.monitoring_interval_minutes = 5
    
    async def initialize(self):
        """Initialize all component services"""
        try:
            self.logger.info("Initializing deployment orchestration service")
            
            # Initialize all services in parallel
            await asyncio.gather(
                self.monitoring_service.initialize(),
                self.health_service.initialize(),
                self.diagnostic_service.initialize(),
                self.optimization_service.initialize(),
                self.validation_service.initialize(),
                self.recovery_service.initialize(),
                return_exceptions=True
            )
            
            self.logger.info("Deployment orchestration service initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize deployment orchestration service: {str(e)}")
            raise
    
    async def orchestrate_full_deployment(self,
                                        cluster_name: str,
                                        service_name: str,
                                        deployment_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
            self.logger.info(f"Starting full deployment orchestration for {service_name}", cluster=cluster_name)
            
            orchestration_start = datetime.utcnow()
            results = []
            overall_status = OrchestrationStatus.COMPLETED
            
            # Phase 1: Pre-deployment validation and preparation
            pre_deployment_result = await self._execute_pre_deployment_phase(
                cluster_name, service_name, deployment_config
            )
            results.append(pre_deployment_result)
            
            if pre_deployment_result.status == OrchestrationStatus.FAILED:
                overall_status = OrchestrationStatus.FAILED
                return self._create_orchestration_summary(orchestration_start, results, overall_status)
            
            # Phase 2: Deployment monitoring and validation
            deployment_result = await self._execute_deployment_phase(
                cluster_name, service_name, deployment_config
            )
            results.append(deployment_result)
            
            if deployment_result.status == OrchestrationStatus.FAILED:
                overall_status = OrchestrationStatus.FAILED
                # Attempt automatic recovery
                if self.auto_recovery_enabled:
                    recovery_result = await self._execute_emergency_recovery(cluster_name, service_name)
                    results.append(recovery_result)
                
                return self._create_orchestration_summary(orchestration_start, results, overall_status)
            
            # Phase 3: Post-deployment validation and setup
            post_deployment_result = await self._execute_post_deployment_phase(
                cluster_name, service_name, deployment_config
            )
            results.append(post_deployment_result)
            
            if post_deployment_result.status == OrchestrationStatus.WARNING:
                overall_status = OrchestrationStatus.WARNING
            
            # Phase 4: Continuous monitoring setup
            monitoring_result = await self._execute_monitoring_setup_phase(
                cluster_name, service_name, deployment_config
            )
            results.append(monitoring_result)
            
            # Phase 5: Optimization analysis (if enabled)
            if self.auto_optimization_enabled:
                optimization_result = await self._execute_optimization_phase(
                    cluster_name, service_name, deployment_config
                )
                results.append(optimization_result)
            
            return self._create_orchestration_summary(orchestration_start, results, overall_status)
            
        except Exception as e:
            self.logger.error(f"Deployment orchestration failed: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _execute_pre_deployment_phase(self,
                                          cluster_name: str,
                                          service_name: str,
                                          deployment_config: Optional[Dict[str, Any]]) -> OrchestrationResult:
        """Execute pre-deployment validation and preparation"""
        
        phase_start = datetime.utcnow()
        
        try:
            self.logger.info("Executing pre-deployment phase", service=service_name)
            
            phase_details = {}
            
            # Create deployment snapshot before changes
            try:
                snapshot = await self.recovery_service.create_deployment_snapshot(cluster_name, service_name)
                phase_details['snapshot_created'] = {
                    'snapshot_id': snapshot.timestamp.strftime('%Y%m%d_%H%M%S'),
                    'timestamp': snapshot.timestamp.isoformat()
                }
            except Exception as e:
                self.logger.warning(f"Could not create pre-deployment snapshot: {str(e)}")
                phase_details['snapshot_created'] = {'error': str(e)}
            
            # Run diagnostic checks
            try:
                diagnostic_report = await self.diagnostic_service.run_comprehensive_diagnostics()
                phase_details['diagnostic_report'] = {
                    'issues_found': len(diagnostic_report.get('issues', [])),
                    'critical_issues': len([i for i in diagnostic_report.get('issues', []) if i.get('severity') == 'critical']),
                    'system_health_score': diagnostic_report.get('system_health_score', 0)
                }
                
                # Check for critical issues that should block deployment
                critical_issues = [i for i in diagnostic_report.get('issues', []) if i.get('severity') == 'critical']
                if critical_issues:
                    return OrchestrationResult(
                        phase=OrchestrationPhase.PRE_DEPLOYMENT,
                        status=OrchestrationStatus.FAILED,
                        duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                        details=phase_details,
                        error_message=f"Critical issues found: {len(critical_issues)} issues must be resolved before deployment"
                    )
                    
            except Exception as e:
                self.logger.warning(f"Diagnostic check failed: {str(e)}")
                phase_details['diagnostic_report'] = {'error': str(e)}
            
            # Validate current service health
            try:
                health_status = await self.health_service.get_comprehensive_health_status()
                phase_details['current_health'] = {
                    'overall_score': health_status.get('overall_health_score', 0),
                    'critical_components': health_status.get('critical_component_failures', 0)
                }
                
                # Check if service is healthy enough for deployment
                if health_status.get('overall_health_score', 0) < 70:
                    return OrchestrationResult(
                        phase=OrchestrationPhase.PRE_DEPLOYMENT,
                        status=OrchestrationStatus.WARNING,
                        duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                        details=phase_details,
                        error_message="Service health score below recommended threshold for deployment"
                    )
                    
            except Exception as e:
                self.logger.warning(f"Health check failed: {str(e)}")
                phase_details['current_health'] = {'error': str(e)}
            
            return OrchestrationResult(
                phase=OrchestrationPhase.PRE_DEPLOYMENT,
                status=OrchestrationStatus.COMPLETED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details=phase_details
            )
            
        except Exception as e:
            return OrchestrationResult(
                phase=OrchestrationPhase.PRE_DEPLOYMENT,
                status=OrchestrationStatus.FAILED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details={},
                error_message=str(e)
            )
    
    async def _execute_deployment_phase(self,
                                      cluster_name: str,
                                      service_name: str,
                                      deployment_config: Optional[Dict[str, Any]]) -> OrchestrationResult:
        """Execute deployment monitoring and validation"""
        
        phase_start = datetime.utcnow()
        
        try:
            self.logger.info("Executing deployment phase", service=service_name)
            
            phase_details = {}
            
            # Wait for service to be healthy after deployment
            try:
                health_validation = await self.validation_service.validate_service_health_after_deployment(
                    cluster_name, service_name, wait_timeout_seconds=self.validation_timeout_minutes * 60
                )
                phase_details['health_validation'] = health_validation
                
                if health_validation.get('status') != 'healthy':
                    return OrchestrationResult(
                        phase=OrchestrationPhase.DEPLOYMENT,
                        status=OrchestrationStatus.FAILED,
                        duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                        details=phase_details,
                        error_message="Service did not become healthy after deployment"
                    )
                    
            except Exception as e:
                self.logger.error(f"Health validation failed: {str(e)}")
                phase_details['health_validation'] = {'error': str(e)}
                return OrchestrationResult(
                    phase=OrchestrationPhase.DEPLOYMENT,
                    status=OrchestrationStatus.FAILED,
                    duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                    details=phase_details,
                    error_message=f"Health validation failed: {str(e)}"
                )
            
            return OrchestrationResult(
                phase=OrchestrationPhase.DEPLOYMENT,
                status=OrchestrationStatus.COMPLETED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details=phase_details
            )
            
        except Exception as e:
            return OrchestrationResult(
                phase=OrchestrationPhase.DEPLOYMENT,
                status=OrchestrationStatus.FAILED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details={},
                error_message=str(e)
            )
    
    async def _execute_post_deployment_phase(self,
                                           cluster_name: str,
                                           service_name: str,
                                           deployment_config: Optional[Dict[str, Any]]) -> OrchestrationResult:
        """Execute post-deployment validation and setup"""
        
        phase_start = datetime.utcnow()
        
        try:
            self.logger.info("Executing post-deployment phase", service=service_name)
            
            phase_details = {}
            
            # Run comprehensive validation tests
            try:
                validation_results = await self.validation_service.validate_deployment(
                    cluster_name, service_name,
                    test_categories=[TestCategory.SMOKE_TEST, TestCategory.API_VALIDATION, TestCategory.INTEGRATION_TEST]
                )
                phase_details['validation_results'] = {
                    'overall_status': validation_results.get('overall_status'),
                    'success_rate': validation_results.get('summary', {}).get('success_rate_percentage', 0),
                    'total_tests': validation_results.get('summary', {}).get('total_tests', 0),
                    'failed_tests': validation_results.get('summary', {}).get('failed_tests', 0)
                }
                
                # Determine if validation passed acceptably
                success_rate = validation_results.get('summary', {}).get('success_rate_percentage', 0)
                if success_rate < 90:
                    return OrchestrationResult(
                        phase=OrchestrationPhase.POST_DEPLOYMENT,
                        status=OrchestrationStatus.WARNING,
                        duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                        details=phase_details,
                        error_message=f"Validation success rate {success_rate}% below 90% threshold"
                    )
                    
            except Exception as e:
                self.logger.warning(f"Validation tests failed: {str(e)}")
                phase_details['validation_results'] = {'error': str(e)}
            
            # Create post-deployment snapshot
            try:
                snapshot = await self.recovery_service.create_deployment_snapshot(cluster_name, service_name)
                phase_details['post_deployment_snapshot'] = {
                    'snapshot_id': snapshot.timestamp.strftime('%Y%m%d_%H%M%S'),
                    'timestamp': snapshot.timestamp.isoformat()
                }
            except Exception as e:
                self.logger.warning(f"Could not create post-deployment snapshot: {str(e)}")
                phase_details['post_deployment_snapshot'] = {'error': str(e)}
            
            return OrchestrationResult(
                phase=OrchestrationPhase.POST_DEPLOYMENT,
                status=OrchestrationStatus.COMPLETED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details=phase_details
            )
            
        except Exception as e:
            return OrchestrationResult(
                phase=OrchestrationPhase.POST_DEPLOYMENT,
                status=OrchestrationStatus.FAILED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details={},
                error_message=str(e)
            )
    
    async def _execute_monitoring_setup_phase(self,
                                            cluster_name: str,
                                            service_name: str,
                                            deployment_config: Optional[Dict[str, Any]]) -> OrchestrationResult:
        """Execute monitoring and alerting setup"""
        
        phase_start = datetime.utcnow()
        
        try:
            self.logger.info("Executing monitoring setup phase", service=service_name)
            
            phase_details = {}
            
            # Setup deployment monitoring
            try:
                monitoring_setup = await self.monitoring_service.setup_deployment_monitoring(
                    cluster_name, service_name
                )
                phase_details['monitoring_setup'] = monitoring_setup
            except Exception as e:
                self.logger.warning(f"Monitoring setup failed: {str(e)}")
                phase_details['monitoring_setup'] = {'error': str(e)}
            
            # Setup health monitoring
            try:
                health_monitoring = await self.health_service.setup_continuous_monitoring(
                    interval_minutes=self.monitoring_interval_minutes
                )
                phase_details['health_monitoring'] = health_monitoring
            except Exception as e:
                self.logger.warning(f"Health monitoring setup failed: {str(e)}")
                phase_details['health_monitoring'] = {'error': str(e)}
            
            return OrchestrationResult(
                phase=OrchestrationPhase.MONITORING,
                status=OrchestrationStatus.COMPLETED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details=phase_details
            )
            
        except Exception as e:
            return OrchestrationResult(
                phase=OrchestrationPhase.MONITORING,
                status=OrchestrationStatus.FAILED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details={},
                error_message=str(e)
            )
    
    async def _execute_optimization_phase(self,
                                        cluster_name: str,
                                        service_name: str,
                                        deployment_config: Optional[Dict[str, Any]]) -> OrchestrationResult:
        """Execute resource optimization analysis"""
        
        phase_start = datetime.utcnow()
        
        try:
            self.logger.info("Executing optimization phase", service=service_name)
            
            phase_details = {}
            
            # Get optimization summary
            try:
                optimization_summary = await self.optimization_service.get_optimization_summary(
                    cluster_name, service_name
                )
                phase_details['optimization_summary'] = {
                    'total_recommendations': optimization_summary.get('total_recommendations', 0),
                    'high_priority_recommendations': optimization_summary.get('high_priority_recommendations', 0),
                    'estimated_cost_savings': optimization_summary.get('estimated_cost_savings_percentage', 0)
                }
            except Exception as e:
                self.logger.warning(f"Optimization analysis failed: {str(e)}")
                phase_details['optimization_summary'] = {'error': str(e)}
            
            return OrchestrationResult(
                phase=OrchestrationPhase.OPTIMIZATION,
                status=OrchestrationStatus.COMPLETED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details=phase_details
            )
            
        except Exception as e:
            return OrchestrationResult(
                phase=OrchestrationPhase.OPTIMIZATION,
                status=OrchestrationStatus.FAILED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details={},
                error_message=str(e)
            )
    
    async def _execute_emergency_recovery(self,
                                        cluster_name: str,
                                        service_name: str) -> OrchestrationResult:
        """Execute emergency recovery procedures"""
        
        phase_start = datetime.utcnow()
        
        try:
            self.logger.info("Executing emergency recovery", service=service_name)
            
            # Execute service rollback recovery plan
            operation_id = await self.recovery_service.execute_recovery_plan(
                'service_rollback', cluster_name, service_name
            )
            
            # Wait for recovery to complete (with timeout)
            timeout_end = datetime.utcnow() + timedelta(minutes=10)
            
            while datetime.utcnow() < timeout_end:
                status = await self.recovery_service.get_recovery_operation_status(operation_id)
                if status and status['status'] in ['completed', 'failed']:
                    break
                await asyncio.sleep(10)
            
            final_status = await self.recovery_service.get_recovery_operation_status(operation_id)
            
            return OrchestrationResult(
                phase=OrchestrationPhase.PRE_DEPLOYMENT,  # Recovery is part of deployment phase
                status=OrchestrationStatus.COMPLETED if final_status.get('status') == 'completed' else OrchestrationStatus.FAILED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details={'recovery_operation': final_status}
            )
            
        except Exception as e:
            return OrchestrationResult(
                phase=OrchestrationPhase.PRE_DEPLOYMENT,
                status=OrchestrationStatus.FAILED,
                duration_seconds=(datetime.utcnow() - phase_start).total_seconds(),
                details={},
                error_message=f"Emergency recovery failed: {str(e)}"
            )
    
    def _create_orchestration_summary(self,
                                    start_time: datetime,
                                    results: List[OrchestrationResult],
                                    overall_status: OrchestrationStatus) -> Dict[str, Any]:
        """Create comprehensive orchestration summary"""
        
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            'orchestration_id': f"orch_{start_time.strftime('%Y%m%d_%H%M%S')}",
            'status': overall_status.value,
            'started_at': start_time.isoformat(),
            'completed_at': datetime.utcnow().isoformat(),
            'total_duration_seconds': total_duration,
            'phases_executed': len(results),
            'phases_successful': len([r for r in results if r.status == OrchestrationStatus.COMPLETED]),
            'phases_failed': len([r for r in results if r.status == OrchestrationStatus.FAILED]),
            'phases_warning': len([r for r in results if r.status == OrchestrationStatus.WARNING]),
            'phase_results': [
                {
                    'phase': result.phase.value,
                    'status': result.status.value,
                    'duration_seconds': result.duration_seconds,
                    'error_message': result.error_message,
                    'details': result.details
                }
                for result in results
            ]
        }
    
    async def get_orchestration_status(self, cluster_name: str, service_name: str) -> Dict[str, Any]:
        """Get current orchestration status for a service"""
        
        try:
            # Get status from all component services
            monitoring_status = await self.monitoring_service.get_deployment_status(cluster_name, service_name)
            health_status = await self.health_service.get_comprehensive_health_status()
            optimization_summary = await self.optimization_service.get_optimization_summary(cluster_name, service_name)
            
            return {
                'cluster_name': cluster_name,
                'service_name': service_name,
                'timestamp': datetime.utcnow().isoformat(),
                'monitoring': {
                    'status': monitoring_status.get('status', 'unknown'),
                    'metrics_available': len(monitoring_status.get('metrics', {}))
                },
                'health': {
                    'overall_score': health_status.get('overall_health_score', 0),
                    'critical_issues': health_status.get('critical_component_failures', 0)
                },
                'optimization': {
                    'recommendations_available': optimization_summary.get('total_recommendations', 0),
                    'high_priority_recommendations': optimization_summary.get('high_priority_recommendations', 0)
                },
                'services_initialized': {
                    'monitoring': self.monitoring_service is not None,
                    'health': self.health_service is not None,
                    'diagnostics': self.diagnostic_service is not None,
                    'optimization': self.optimization_service is not None,
                    'validation': self.validation_service is not None,
                    'recovery': self.recovery_service is not None
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get orchestration status: {str(e)}")
            return {
                'status': 'error',
                'error_message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }