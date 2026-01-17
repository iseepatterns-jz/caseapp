"""
Resource Optimization Service
Provides automated resource optimization based on usage patterns and performance metrics
"""

import asyncio
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional, Tuple
import structlog
import boto3
from dataclasses import dataclass
from enum import Enum

from core.aws_service import aws_service

logger = structlog.get_logger()

class OptimizationType(Enum):
    """Types of optimization recommendations"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    COST_OPTIMIZATION = "cost_optimization"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"

@dataclass
class ResourceMetrics:
    """Resource usage metrics"""
    cpu_utilization: float
    memory_utilization: float
    network_in: float
    network_out: float
    request_count: int
    response_time: float
    error_rate: float
    timestamp: datetime

@dataclass
class OptimizationRecommendation:
    """Resource optimization recommendation"""
    resource_type: str
    resource_name: str
    optimization_type: OptimizationType
    current_config: Dict[str, Any]
    recommended_config: Dict[str, Any]
    expected_savings: Optional[float]
    expected_performance_impact: str
    confidence_score: float
    reasoning: str
    priority: str  # high, medium, low

class ResourceOptimizationService:
    """Service for automated resource optimization"""
    
    def __init__(self):
        self.logger = logger.bind(component="resource_optimization")
        self.cloudwatch = None
        self.ecs = None
        self.application_autoscaling = None
        
        # Optimization thresholds
        self.cpu_high_threshold = 80.0
        self.cpu_low_threshold = 20.0
        self.memory_high_threshold = 85.0
        self.memory_low_threshold = 30.0
        self.response_time_threshold = 2000.0  # 2 seconds
        self.error_rate_threshold = 5.0  # 5%
        
        # Cost optimization settings
        self.cost_optimization_enabled = True
        self.performance_optimization_enabled = True
    
    async def initialize(self):
        """Initialize AWS clients"""
        try:
            await aws_service.initialize()
            self.cloudwatch = aws_service.get_client('cloudwatch')
            self.ecs = aws_service.get_client('ecs')
            self.application_autoscaling = aws_service.get_client('application-autoscaling')
            self.logger.info("Resource optimization service initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize resource optimization service: {str(e)}")
            raise
    
    async def analyze_resource_usage(self, 
                                   cluster_name: str,
                                   service_name: str,
                                   hours_back: int = 24) -> List[ResourceMetrics]:
        """
        Analyze resource usage patterns over specified time period
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            hours_back: Hours of historical data to analyze
            
        Returns:
            List of resource metrics
        """
        try:
            end_time = datetime.now(UTC)
            start_time = end_time - timedelta(hours=hours_back)
            
            # Get ECS service metrics
            ecs_metrics = await self._get_ecs_metrics(
                cluster_name, service_name, start_time, end_time
            )
            
            # Get ALB metrics
            alb_metrics = await self._get_alb_metrics(
                service_name, start_time, end_time
            )
            
            # Combine metrics
            combined_metrics = self._combine_metrics(ecs_metrics, alb_metrics)
            
            self.logger.info(
                f"Analyzed resource usage for {service_name}",
                metrics_count=len(combined_metrics),
                time_range_hours=hours_back
            )
            
            return combined_metrics
            
        except Exception as e:
            self.logger.error(f"Failed to analyze resource usage: {str(e)}")
            raise
    
    async def _get_ecs_metrics(self, 
                              cluster_name: str,
                              service_name: str,
                              start_time: datetime,
                              end_time: datetime) -> Dict[str, List]:
        """Get ECS service metrics from CloudWatch"""
        
        metrics_to_fetch = [
            ('CPUUtilization', 'AWS/ECS'),
            ('MemoryUtilization', 'AWS/ECS'),
            ('NetworkRxBytes', 'AWS/ECS'),
            ('NetworkTxBytes', 'AWS/ECS')
        ]
        
        metrics_data = {}
        
        for metric_name, namespace in metrics_to_fetch:
            try:
                response = await asyncio.to_thread(
                    self.cloudwatch.get_metric_statistics,
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=[
                        {'Name': 'ServiceName', 'Value': service_name},
                        {'Name': 'ClusterName', 'Value': cluster_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,  # 5-minute intervals
                    Statistics=['Average', 'Maximum']
                )
                
                metrics_data[metric_name] = response.get('Datapoints', [])
                
            except Exception as e:
                self.logger.warning(f"Failed to get {metric_name} metrics: {str(e)}")
                metrics_data[metric_name] = []
        
        return metrics_data
    
    async def _get_alb_metrics(self,
                              service_name: str,
                              start_time: datetime,
                              end_time: datetime) -> Dict[str, List]:
        """Get ALB metrics from CloudWatch"""
        
        # Try to find ALB target group for this service
        alb_metrics = {}
        
        try:
            # Get ALB metrics (assuming standard naming convention)
            alb_metric_names = [
                'RequestCount',
                'TargetResponseTime',
                'HTTPCode_Target_4XX_Count',
                'HTTPCode_Target_5XX_Count'
            ]
            
            for metric_name in alb_metric_names:
                try:
                    response = await asyncio.to_thread(
                        self.cloudwatch.get_metric_statistics,
                        Namespace='AWS/ApplicationELB',
                        MetricName=metric_name,
                        Dimensions=[
                            {'Name': 'LoadBalancer', 'Value': f'app/{service_name}-alb/*'}
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300,
                        Statistics=['Sum', 'Average']
                    )
                    
                    alb_metrics[metric_name] = response.get('Datapoints', [])
                    
                except Exception as e:
                    self.logger.warning(f"Failed to get ALB {metric_name} metrics: {str(e)}")
                    alb_metrics[metric_name] = []
        
        except Exception as e:
            self.logger.warning(f"Failed to get ALB metrics: {str(e)}")
        
        return alb_metrics
    
    def _combine_metrics(self, 
                        ecs_metrics: Dict[str, List],
                        alb_metrics: Dict[str, List]) -> List[ResourceMetrics]:
        """Combine ECS and ALB metrics into ResourceMetrics objects"""
        
        combined_metrics = []
        
        # Get all timestamps from ECS CPU metrics as baseline
        cpu_data = ecs_metrics.get('CPUUtilization', [])
        
        for cpu_point in cpu_data:
            timestamp = cpu_point['Timestamp']
            
            # Find corresponding data points for other metrics
            memory_util = self._find_metric_value(
                ecs_metrics.get('MemoryUtilization', []), timestamp
            )
            network_in = self._find_metric_value(
                ecs_metrics.get('NetworkRxBytes', []), timestamp
            )
            network_out = self._find_metric_value(
                ecs_metrics.get('NetworkTxBytes', []), timestamp
            )
            request_count = self._find_metric_value(
                alb_metrics.get('RequestCount', []), timestamp, 'Sum'
            )
            response_time = self._find_metric_value(
                alb_metrics.get('TargetResponseTime', []), timestamp
            )
            
            # Calculate error rate
            error_4xx = self._find_metric_value(
                alb_metrics.get('HTTPCode_Target_4XX_Count', []), timestamp, 'Sum'
            )
            error_5xx = self._find_metric_value(
                alb_metrics.get('HTTPCode_Target_5XX_Count', []), timestamp, 'Sum'
            )
            
            total_errors = (error_4xx or 0) + (error_5xx or 0)
            error_rate = (total_errors / max(request_count or 1, 1)) * 100
            
            metrics = ResourceMetrics(
                cpu_utilization=cpu_point.get('Average', 0),
                memory_utilization=memory_util or 0,
                network_in=network_in or 0,
                network_out=network_out or 0,
                request_count=int(request_count or 0),
                response_time=(response_time or 0) * 1000,  # Convert to milliseconds
                error_rate=error_rate,
                timestamp=timestamp
            )
            
            combined_metrics.append(metrics)
        
        return sorted(combined_metrics, key=lambda x: x.timestamp)
    
    def _find_metric_value(self, 
                          datapoints: List[Dict],
                          target_timestamp: datetime,
                          statistic: str = 'Average') -> Optional[float]:
        """Find metric value closest to target timestamp"""
        
        if not datapoints:
            return None
        
        # Find closest timestamp (within 5 minutes)
        closest_point = None
        min_diff = timedelta(minutes=5)
        
        for point in datapoints:
            diff = abs(point['Timestamp'] - target_timestamp)
            if diff < min_diff:
                min_diff = diff
                closest_point = point
        
        return closest_point.get(statistic) if closest_point else None
    
    async def generate_optimization_recommendations(self,
                                                  cluster_name: str,
                                                  service_name: str,
                                                  metrics: List[ResourceMetrics]) -> List[OptimizationRecommendation]:
        """
        Generate optimization recommendations based on metrics analysis
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            metrics: Historical resource metrics
            
        Returns:
            List of optimization recommendations
        """
        try:
            recommendations = []
            
            if not metrics:
                self.logger.warning("No metrics available for optimization analysis")
                return recommendations
            
            # Get current service configuration
            current_config = await self._get_current_service_config(cluster_name, service_name)
            
            # Analyze CPU utilization patterns
            cpu_recommendations = self._analyze_cpu_utilization(metrics, current_config)
            recommendations.extend(cpu_recommendations)
            
            # Analyze memory utilization patterns
            memory_recommendations = self._analyze_memory_utilization(metrics, current_config)
            recommendations.extend(memory_recommendations)
            
            # Analyze performance patterns
            performance_recommendations = self._analyze_performance_patterns(metrics, current_config)
            recommendations.extend(performance_recommendations)
            
            # Analyze cost optimization opportunities
            cost_recommendations = self._analyze_cost_optimization(metrics, current_config)
            recommendations.extend(cost_recommendations)
            
            # Sort by priority and confidence
            recommendations.sort(key=lambda x: (
                {'high': 3, 'medium': 2, 'low': 1}[x.priority],
                x.confidence_score
            ), reverse=True)
            
            self.logger.info(
                f"Generated {len(recommendations)} optimization recommendations",
                service=service_name,
                high_priority=len([r for r in recommendations if r.priority == 'high'])
            )
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Failed to generate optimization recommendations: {str(e)}")
            raise
    
    async def _get_current_service_config(self, cluster_name: str, service_name: str) -> Dict[str, Any]:
        """Get current ECS service configuration"""
        
        try:
            response = await asyncio.to_thread(
                self.ecs.describe_services,
                cluster=cluster_name,
                services=[service_name]
            )
            
            if not response['services']:
                raise ValueError(f"Service {service_name} not found in cluster {cluster_name}")
            
            service = response['services'][0]
            task_definition_arn = service['taskDefinition']
            
            # Get task definition details
            task_def_response = await asyncio.to_thread(
                self.ecs.describe_task_definition,
                taskDefinition=task_definition_arn
            )
            
            task_def = task_def_response['taskDefinition']
            container_def = task_def['containerDefinitions'][0]  # Assume single container
            
            return {
                'desired_count': service['desiredCount'],
                'cpu': int(task_def.get('cpu', 0)),
                'memory': int(task_def.get('memory', 0)),
                'container_cpu': container_def.get('cpu', 0),
                'container_memory': container_def.get('memory', 0),
                'task_definition_arn': task_definition_arn
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get service configuration: {str(e)}")
            return {}
    
    def _analyze_cpu_utilization(self, 
                               metrics: List[ResourceMetrics],
                               current_config: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Analyze CPU utilization and generate recommendations"""
        
        recommendations = []
        
        if not metrics:
            return recommendations
        
        # Calculate average and peak CPU utilization
        cpu_values = [m.cpu_utilization for m in metrics if m.cpu_utilization > 0]
        
        if not cpu_values:
            return recommendations
        
        avg_cpu = sum(cpu_values) / len(cpu_values)
        max_cpu = max(cpu_values)
        
        current_cpu = current_config.get('cpu', 1024)
        
        # High CPU utilization - recommend scale up
        if avg_cpu > self.cpu_high_threshold or max_cpu > 95:
            new_cpu = min(current_cpu * 2, 4096)  # Cap at 4 vCPU
            
            recommendations.append(OptimizationRecommendation(
                resource_type="ECS_CPU",
                resource_name=f"Task CPU allocation",
                optimization_type=OptimizationType.PERFORMANCE_OPTIMIZATION,
                current_config={'cpu': current_cpu},
                recommended_config={'cpu': new_cpu},
                expected_savings=None,
                expected_performance_impact="Improved response times and reduced CPU bottlenecks",
                confidence_score=0.9 if avg_cpu > 90 else 0.7,
                reasoning=f"Average CPU utilization is {avg_cpu:.1f}% (peak: {max_cpu:.1f}%), exceeding threshold of {self.cpu_high_threshold}%",
                priority="high" if avg_cpu > 90 else "medium"
            ))
        
        # Low CPU utilization - recommend scale down
        elif avg_cpu < self.cpu_low_threshold and max_cpu < 40:
            new_cpu = max(current_cpu // 2, 256)  # Minimum 0.25 vCPU
            
            # Calculate potential cost savings
            cost_reduction = ((current_cpu - new_cpu) / current_cpu) * 0.3  # Rough estimate
            
            recommendations.append(OptimizationRecommendation(
                resource_type="ECS_CPU",
                resource_name=f"Task CPU allocation",
                optimization_type=OptimizationType.COST_OPTIMIZATION,
                current_config={'cpu': current_cpu},
                recommended_config={'cpu': new_cpu},
                expected_savings=cost_reduction,
                expected_performance_impact="Minimal impact on performance",
                confidence_score=0.8,
                reasoning=f"Average CPU utilization is {avg_cpu:.1f}% (peak: {max_cpu:.1f}%), below threshold of {self.cpu_low_threshold}%",
                priority="medium"
            ))
        
        return recommendations
    
    def _analyze_memory_utilization(self,
                                  metrics: List[ResourceMetrics],
                                  current_config: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Analyze memory utilization and generate recommendations"""
        
        recommendations = []
        
        if not metrics:
            return recommendations
        
        # Calculate average and peak memory utilization
        memory_values = [m.memory_utilization for m in metrics if m.memory_utilization > 0]
        
        if not memory_values:
            return recommendations
        
        avg_memory = sum(memory_values) / len(memory_values)
        max_memory = max(memory_values)
        
        current_memory = current_config.get('memory', 2048)
        
        # High memory utilization - recommend scale up
        if avg_memory > self.memory_high_threshold or max_memory > 95:
            new_memory = min(current_memory * 2, 8192)  # Cap at 8GB
            
            recommendations.append(OptimizationRecommendation(
                resource_type="ECS_MEMORY",
                resource_name=f"Task memory allocation",
                optimization_type=OptimizationType.PERFORMANCE_OPTIMIZATION,
                current_config={'memory': current_memory},
                recommended_config={'memory': new_memory},
                expected_savings=None,
                expected_performance_impact="Reduced memory pressure and improved stability",
                confidence_score=0.9 if avg_memory > 90 else 0.7,
                reasoning=f"Average memory utilization is {avg_memory:.1f}% (peak: {max_memory:.1f}%), exceeding threshold of {self.memory_high_threshold}%",
                priority="high" if avg_memory > 90 else "medium"
            ))
        
        # Low memory utilization - recommend scale down
        elif avg_memory < self.memory_low_threshold and max_memory < 50:
            new_memory = max(current_memory // 2, 512)  # Minimum 512MB
            
            # Calculate potential cost savings
            cost_reduction = ((current_memory - new_memory) / current_memory) * 0.4  # Memory is more expensive
            
            recommendations.append(OptimizationRecommendation(
                resource_type="ECS_MEMORY",
                resource_name=f"Task memory allocation",
                optimization_type=OptimizationType.COST_OPTIMIZATION,
                current_config={'memory': current_memory},
                recommended_config={'memory': new_memory},
                expected_savings=cost_reduction,
                expected_performance_impact="Minimal impact on performance",
                confidence_score=0.8,
                reasoning=f"Average memory utilization is {avg_memory:.1f}% (peak: {max_memory:.1f}%), below threshold of {self.memory_low_threshold}%",
                priority="medium"
            ))
        
        return recommendations
    
    def _analyze_performance_patterns(self,
                                    metrics: List[ResourceMetrics],
                                    current_config: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Analyze performance patterns and generate recommendations"""
        
        recommendations = []
        
        if not metrics:
            return recommendations
        
        # Analyze response times
        response_times = [m.response_time for m in metrics if m.response_time > 0]
        error_rates = [m.error_rate for m in metrics if m.error_rate >= 0]
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            if avg_response_time > self.response_time_threshold:
                recommendations.append(OptimizationRecommendation(
                    resource_type="PERFORMANCE",
                    resource_name="Application response time",
                    optimization_type=OptimizationType.PERFORMANCE_OPTIMIZATION,
                    current_config={'avg_response_time': avg_response_time},
                    recommended_config={'target_response_time': self.response_time_threshold},
                    expected_savings=None,
                    expected_performance_impact="Improved user experience and application responsiveness",
                    confidence_score=0.8,
                    reasoning=f"Average response time is {avg_response_time:.0f}ms, exceeding target of {self.response_time_threshold:.0f}ms",
                    priority="high" if avg_response_time > self.response_time_threshold * 2 else "medium"
                ))
        
        if error_rates:
            avg_error_rate = sum(error_rates) / len(error_rates)
            
            if avg_error_rate > self.error_rate_threshold:
                recommendations.append(OptimizationRecommendation(
                    resource_type="RELIABILITY",
                    resource_name="Application error rate",
                    optimization_type=OptimizationType.PERFORMANCE_OPTIMIZATION,
                    current_config={'error_rate': avg_error_rate},
                    recommended_config={'target_error_rate': self.error_rate_threshold},
                    expected_savings=None,
                    expected_performance_impact="Improved application reliability and user satisfaction",
                    confidence_score=0.9,
                    reasoning=f"Average error rate is {avg_error_rate:.1f}%, exceeding target of {self.error_rate_threshold}%",
                    priority="high"
                ))
        
        return recommendations
    
    def _analyze_cost_optimization(self,
                                 metrics: List[ResourceMetrics],
                                 current_config: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Analyze cost optimization opportunities"""
        
        recommendations = []
        
        if not self.cost_optimization_enabled:
            return recommendations
        
        # Analyze task count optimization
        desired_count = current_config.get('desired_count', 1)
        
        if desired_count > 1:
            # Check if we can reduce task count based on load patterns
            request_counts = [m.request_count for m in metrics if m.request_count > 0]
            
            if request_counts:
                avg_requests = sum(request_counts) / len(request_counts)
                max_requests = max(request_counts)
                
                # If load is consistently low, suggest reducing task count
                if max_requests < avg_requests * 2 and avg_requests < 100:  # Low and stable load
                    new_count = max(1, desired_count - 1)
                    
                    cost_reduction = ((desired_count - new_count) / desired_count) * 1.0
                    
                    recommendations.append(OptimizationRecommendation(
                        resource_type="ECS_TASK_COUNT",
                        resource_name="Service task count",
                        optimization_type=OptimizationType.COST_OPTIMIZATION,
                        current_config={'desired_count': desired_count},
                        recommended_config={'desired_count': new_count},
                        expected_savings=cost_reduction,
                        expected_performance_impact="Reduced redundancy but maintained availability",
                        confidence_score=0.6,
                        reasoning=f"Load is consistently low (avg: {avg_requests:.0f} req/5min, max: {max_requests:.0f})",
                        priority="low"
                    ))
        
        return recommendations
    
    async def apply_optimization_recommendation(self,
                                             cluster_name: str,
                                             service_name: str,
                                             recommendation: OptimizationRecommendation,
                                             dry_run: bool = True) -> Dict[str, Any]:
        """
        Apply an optimization recommendation
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            recommendation: Optimization recommendation to apply
            dry_run: If True, only simulate the change
            
        Returns:
            Result of the optimization application
        """
        try:
            self.logger.info(
                f"Applying optimization recommendation",
                resource_type=recommendation.resource_type,
                optimization_type=recommendation.optimization_type.value,
                dry_run=dry_run
            )
            
            if dry_run:
                return {
                    'status': 'simulated',
                    'message': 'Optimization would be applied successfully',
                    'recommendation': recommendation.__dict__
                }
            
            # Apply the actual optimization based on type
            if recommendation.resource_type in ['ECS_CPU', 'ECS_MEMORY']:
                return await self._apply_ecs_resource_optimization(
                    cluster_name, service_name, recommendation
                )
            elif recommendation.resource_type == 'ECS_TASK_COUNT':
                return await self._apply_ecs_scaling_optimization(
                    cluster_name, service_name, recommendation
                )
            else:
                return {
                    'status': 'skipped',
                    'message': f'Optimization type {recommendation.resource_type} not implemented for automatic application'
                }
                
        except Exception as e:
            self.logger.error(f"Failed to apply optimization recommendation: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _apply_ecs_resource_optimization(self,
                                             cluster_name: str,
                                             service_name: str,
                                             recommendation: OptimizationRecommendation) -> Dict[str, Any]:
        """Apply ECS resource optimization (CPU/Memory)"""
        
        # This would require creating a new task definition with updated resources
        # For now, return a message indicating manual intervention is needed
        
        return {
            'status': 'manual_intervention_required',
            'message': 'ECS resource optimization requires creating a new task definition',
            'instructions': [
                '1. Create new task definition with recommended CPU/memory settings',
                '2. Update ECS service to use new task definition',
                '3. Monitor deployment and performance after change'
            ],
            'recommended_config': recommendation.recommended_config
        }
    
    async def _apply_ecs_scaling_optimization(self,
                                            cluster_name: str,
                                            service_name: str,
                                            recommendation: OptimizationRecommendation) -> Dict[str, Any]:
        """Apply ECS scaling optimization"""
        
        try:
            new_count = recommendation.recommended_config['desired_count']
            
            response = await asyncio.to_thread(
                self.ecs.update_service,
                cluster=cluster_name,
                service=service_name,
                desiredCount=new_count
            )
            
            return {
                'status': 'applied',
                'message': f'Updated service desired count to {new_count}',
                'service_arn': response['service']['serviceArn']
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to update service scaling: {str(e)}'
            }
    
    async def get_optimization_summary(self,
                                     cluster_name: str,
                                     service_name: str) -> Dict[str, Any]:
        """Get comprehensive optimization summary"""
        
        try:
            # Analyze recent resource usage
            metrics = await self.analyze_resource_usage(cluster_name, service_name, hours_back=24)
            
            # Generate recommendations
            recommendations = await self.generate_optimization_recommendations(
                cluster_name, service_name, metrics
            )
            
            # Calculate potential savings
            total_cost_savings = sum(
                r.expected_savings or 0 
                for r in recommendations 
                if r.optimization_type == OptimizationType.COST_OPTIMIZATION
            )
            
            # Categorize recommendations
            high_priority = [r for r in recommendations if r.priority == 'high']
            performance_recs = [r for r in recommendations if r.optimization_type == OptimizationType.PERFORMANCE_OPTIMIZATION]
            cost_recs = [r for r in recommendations if r.optimization_type == OptimizationType.COST_OPTIMIZATION]
            
            return {
                'service_name': service_name,
                'cluster_name': cluster_name,
                'analysis_period_hours': 24,
                'metrics_analyzed': len(metrics),
                'total_recommendations': len(recommendations),
                'high_priority_recommendations': len(high_priority),
                'performance_recommendations': len(performance_recs),
                'cost_recommendations': len(cost_recs),
                'estimated_cost_savings_percentage': total_cost_savings * 100,
                'recommendations': [
                    {
                        'resource_type': r.resource_type,
                        'optimization_type': r.optimization_type.value,
                        'priority': r.priority,
                        'confidence_score': r.confidence_score,
                        'reasoning': r.reasoning,
                        'expected_savings': r.expected_savings,
                        'current_config': r.current_config,
                        'recommended_config': r.recommended_config
                    }
                    for r in recommendations
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get optimization summary: {str(e)}")
            raise