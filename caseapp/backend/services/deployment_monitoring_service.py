"""
Deployment Monitoring Service for Court Case Management System
Provides real-time deployment status tracking and CloudWatch metrics
"""

import asyncio
import json
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional
import structlog
import boto3
from botocore.exceptions import ClientError

from core.config import settings

logger = structlog.get_logger()

class DeploymentMonitoringService:
    """Service for monitoring deployment status and health metrics"""
    
    def __init__(self):
        self.logger = logger.bind(service="deployment_monitoring")
        self.cloudwatch = boto3.client('cloudwatch', region_name=settings.AWS_REGION)
        self.ecs = boto3.client('ecs', region_name=settings.AWS_REGION)
        self.elbv2 = boto3.client('elbv2', region_name=settings.AWS_REGION)
        self.rds = boto3.client('rds', region_name=settings.AWS_REGION)
        self.elasticache = boto3.client('elasticache', region_name=settings.AWS_REGION)
        
    async def get_deployment_status(self, cluster_name: str, service_name: str) -> Dict[str, Any]:
        """
        Get comprehensive deployment status for ECS service
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            
        Returns:
            Dict containing deployment status and metrics
        """
        try:
            # Get ECS service details
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.ecs.describe_services(
                    cluster=cluster_name,
                    services=[service_name]
                )
            )
            
            if not response['services']:
                return {
                    "status": "not_found",
                    "message": f"Service {service_name} not found in cluster {cluster_name}"
                }
            
            service = response['services'][0]
            
            # Extract deployment information
            deployment_status = {
                "service_name": service_name,
                "cluster_name": cluster_name,
                "status": service['status'],
                "running_count": service['runningCount'],
                "pending_count": service['pendingCount'],
                "desired_count": service['desiredCount'],
                "task_definition": service['taskDefinition'],
                "platform_version": service.get('platformVersion', 'LATEST'),
                "created_at": service['createdAt'].isoformat() if 'createdAt' in service else None,
                "deployments": []
            }
            
            # Process deployments
            for deployment in service.get('deployments', []):
                deployment_info = {
                    "id": deployment.get('id'),
                    "status": deployment.get('status'),
                    "task_definition": deployment.get('taskDefinition'),
                    "desired_count": deployment.get('desiredCount'),
                    "pending_count": deployment.get('pendingCount'),
                    "running_count": deployment.get('runningCount'),
                    "created_at": deployment.get('createdAt').isoformat() if deployment.get('createdAt') else None,
                    "updated_at": deployment.get('updatedAt').isoformat() if deployment.get('updatedAt') else None,
                    "rollout_state": deployment.get('rolloutState'),
                    "rollout_state_reason": deployment.get('rolloutStateReason')
                }
                deployment_status["deployments"].append(deployment_info)
            
            # Get service events (recent issues)
            events_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.ecs.describe_services(
                    cluster=cluster_name,
                    services=[service_name],
                    include=['EVENTS']
                )
            )
            
            if events_response['services']:
                service_events = events_response['services'][0].get('events', [])
                deployment_status["recent_events"] = [
                    {
                        "id": event.get('id'),
                        "created_at": event.get('createdAt').isoformat() if event.get('createdAt') else None,
                        "message": event.get('message')
                    }
                    for event in service_events[:10]  # Last 10 events
                ]
            
            # Calculate overall health
            total_desired = deployment_status["desired_count"]
            total_running = deployment_status["running_count"]
            
            if total_running == total_desired and total_desired > 0:
                deployment_status["health"] = "healthy"
            elif total_running > 0:
                deployment_status["health"] = "degraded"
            else:
                deployment_status["health"] = "unhealthy"
            
            return deployment_status
            
        except Exception as e:
            self.logger.error("Failed to get deployment status", error=str(e))
            return {
                "status": "error",
                "message": f"Failed to get deployment status: {str(e)}"
            }
    
    async def get_cloudwatch_metrics(self, 
                                   metric_queries: List[Dict[str, Any]], 
                                   start_time: datetime, 
                                   end_time: datetime) -> Dict[str, Any]:
        """
        Get CloudWatch metrics for deployment monitoring
        
        Args:
            metric_queries: List of CloudWatch metric queries
            start_time: Start time for metrics
            end_time: End time for metrics
            
        Returns:
            Dict containing metric data
        """
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.get_metric_data(
                    MetricDataQueries=metric_queries,
                    StartTime=start_time,
                    EndTime=end_time
                )
            )
            
            metrics_data = {}
            for result in response.get('MetricDataResults', []):
                metrics_data[result['Id']] = {
                    "label": result.get('Label'),
                    "timestamps": [ts.isoformat() for ts in result.get('Timestamps', [])],
                    "values": result.get('Values', []),
                    "status_code": result.get('StatusCode')
                }
            
            return {
                "status": "success",
                "metrics": metrics_data,
                "messages": response.get('Messages', [])
            }
            
        except Exception as e:
            self.logger.error("Failed to get CloudWatch metrics", error=str(e))
            return {
                "status": "error",
                "message": f"Failed to get metrics: {str(e)}"
            }
    
    async def get_ecs_metrics(self, cluster_name: str, service_name: str, 
                            hours_back: int = 1) -> Dict[str, Any]:
        """
        Get ECS-specific metrics for deployment monitoring
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            hours_back: Hours of historical data to retrieve
            
        Returns:
            Dict containing ECS metrics
        """
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours_back)
        
        metric_queries = [
            {
                'Id': 'cpu_utilization',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/ECS',
                        'MetricName': 'CPUUtilization',
                        'Dimensions': [
                            {'Name': 'ServiceName', 'Value': service_name},
                            {'Name': 'ClusterName', 'Value': cluster_name}
                        ]
                    },
                    'Period': 300,  # 5 minutes
                    'Stat': 'Average'
                },
                'ReturnData': True
            },
            {
                'Id': 'memory_utilization',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/ECS',
                        'MetricName': 'MemoryUtilization',
                        'Dimensions': [
                            {'Name': 'ServiceName', 'Value': service_name},
                            {'Name': 'ClusterName', 'Value': cluster_name}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Average'
                },
                'ReturnData': True
            },
            {
                'Id': 'running_task_count',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/ECS',
                        'MetricName': 'RunningTaskCount',
                        'Dimensions': [
                            {'Name': 'ServiceName', 'Value': service_name},
                            {'Name': 'ClusterName', 'Value': cluster_name}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Average'
                },
                'ReturnData': True
            }
        ]
        
        return await self.get_cloudwatch_metrics(metric_queries, start_time, end_time)
    
    async def get_alb_metrics(self, load_balancer_arn: str, hours_back: int = 1) -> Dict[str, Any]:
        """
        Get Application Load Balancer metrics
        
        Args:
            load_balancer_arn: ALB ARN
            hours_back: Hours of historical data to retrieve
            
        Returns:
            Dict containing ALB metrics
        """
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours_back)
        
        # Extract load balancer name from ARN
        lb_name = load_balancer_arn.split('/')[-3] + '/' + load_balancer_arn.split('/')[-2] + '/' + load_balancer_arn.split('/')[-1]
        
        metric_queries = [
            {
                'Id': 'request_count',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/ApplicationELB',
                        'MetricName': 'RequestCount',
                        'Dimensions': [
                            {'Name': 'LoadBalancer', 'Value': lb_name}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Sum'
                },
                'ReturnData': True
            },
            {
                'Id': 'response_time',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/ApplicationELB',
                        'MetricName': 'TargetResponseTime',
                        'Dimensions': [
                            {'Name': 'LoadBalancer', 'Value': lb_name}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Average'
                },
                'ReturnData': True
            },
            {
                'Id': 'http_5xx_count',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/ApplicationELB',
                        'MetricName': 'HTTPCode_ELB_5XX_Count',
                        'Dimensions': [
                            {'Name': 'LoadBalancer', 'Value': lb_name}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Sum'
                },
                'ReturnData': True
            },
            {
                'Id': 'healthy_host_count',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/ApplicationELB',
                        'MetricName': 'HealthyHostCount',
                        'Dimensions': [
                            {'Name': 'LoadBalancer', 'Value': lb_name}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Average'
                },
                'ReturnData': True
            }
        ]
        
        return await self.get_cloudwatch_metrics(metric_queries, start_time, end_time)
    
    async def get_rds_metrics(self, db_instance_identifier: str, hours_back: int = 1) -> Dict[str, Any]:
        """
        Get RDS database metrics
        
        Args:
            db_instance_identifier: RDS instance identifier
            hours_back: Hours of historical data to retrieve
            
        Returns:
            Dict containing RDS metrics
        """
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours_back)
        
        metric_queries = [
            {
                'Id': 'cpu_utilization',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/RDS',
                        'MetricName': 'CPUUtilization',
                        'Dimensions': [
                            {'Name': 'DBInstanceIdentifier', 'Value': db_instance_identifier}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Average'
                },
                'ReturnData': True
            },
            {
                'Id': 'database_connections',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/RDS',
                        'MetricName': 'DatabaseConnections',
                        'Dimensions': [
                            {'Name': 'DBInstanceIdentifier', 'Value': db_instance_identifier}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Average'
                },
                'ReturnData': True
            },
            {
                'Id': 'read_latency',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/RDS',
                        'MetricName': 'ReadLatency',
                        'Dimensions': [
                            {'Name': 'DBInstanceIdentifier', 'Value': db_instance_identifier}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Average'
                },
                'ReturnData': True
            },
            {
                'Id': 'write_latency',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/RDS',
                        'MetricName': 'WriteLatency',
                        'Dimensions': [
                            {'Name': 'DBInstanceIdentifier', 'Value': db_instance_identifier}
                        ]
                    },
                    'Period': 300,
                    'Stat': 'Average'
                },
                'ReturnData': True
            }
        ]
        
        return await self.get_cloudwatch_metrics(metric_queries, start_time, end_time)
    
    async def create_deployment_dashboard(self, dashboard_name: str, 
                                        cluster_name: str, 
                                        service_name: str,
                                        load_balancer_arn: str,
                                        db_instance_identifier: str) -> Dict[str, Any]:
        """
        Create CloudWatch dashboard for deployment monitoring
        
        Args:
            dashboard_name: Name for the dashboard
            cluster_name: ECS cluster name
            service_name: ECS service name
            load_balancer_arn: ALB ARN
            db_instance_identifier: RDS instance identifier
            
        Returns:
            Dict containing dashboard creation result
        """
        try:
            # Extract load balancer name from ARN
            lb_name = load_balancer_arn.split('/')[-3] + '/' + load_balancer_arn.split('/')[-2] + '/' + load_balancer_arn.split('/')[-1]
            
            dashboard_body = {
                "widgets": [
                    {
                        "type": "metric",
                        "x": 0,
                        "y": 0,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/ECS", "CPUUtilization", "ServiceName", service_name, "ClusterName", cluster_name],
                                [".", "MemoryUtilization", ".", ".", ".", "."],
                                [".", "RunningTaskCount", ".", ".", ".", "."]
                            ],
                            "view": "timeSeries",
                            "stacked": False,
                            "region": settings.AWS_REGION,
                            "title": "ECS Service Metrics",
                            "period": 300
                        }
                    },
                    {
                        "type": "metric",
                        "x": 12,
                        "y": 0,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", lb_name],
                                [".", "TargetResponseTime", ".", "."],
                                [".", "HTTPCode_ELB_5XX_Count", ".", "."],
                                [".", "HealthyHostCount", ".", "."]
                            ],
                            "view": "timeSeries",
                            "stacked": False,
                            "region": settings.AWS_REGION,
                            "title": "Load Balancer Metrics",
                            "period": 300
                        }
                    },
                    {
                        "type": "metric",
                        "x": 0,
                        "y": 6,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "metrics": [
                                ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", db_instance_identifier],
                                [".", "DatabaseConnections", ".", "."],
                                [".", "ReadLatency", ".", "."],
                                [".", "WriteLatency", ".", "."]
                            ],
                            "view": "timeSeries",
                            "stacked": False,
                            "region": settings.AWS_REGION,
                            "title": "Database Metrics",
                            "period": 300
                        }
                    },
                    {
                        "type": "log",
                        "x": 12,
                        "y": 6,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "query": f"SOURCE '/ecs/{service_name}'\n| fields @timestamp, @message\n| filter @message like /ERROR/\n| sort @timestamp desc\n| limit 100",
                            "region": settings.AWS_REGION,
                            "title": "Recent Errors",
                            "view": "table"
                        }
                    }
                ]
            }
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.put_dashboard(
                    DashboardName=dashboard_name,
                    DashboardBody=json.dumps(dashboard_body)
                )
            )
            
            return {
                "status": "success",
                "dashboard_name": dashboard_name,
                "dashboard_arn": response.get('DashboardArn'),
                "message": "Dashboard created successfully"
            }
            
        except Exception as e:
            self.logger.error("Failed to create dashboard", error=str(e))
            return {
                "status": "error",
                "message": f"Failed to create dashboard: {str(e)}"
            }
    
    async def create_deployment_alarms(self, cluster_name: str, service_name: str,
                                     load_balancer_arn: str, db_instance_identifier: str,
                                     sns_topic_arn: Optional[str] = None) -> Dict[str, Any]:
        """
        Create CloudWatch alarms for deployment monitoring
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            load_balancer_arn: ALB ARN
            db_instance_identifier: RDS instance identifier
            sns_topic_arn: SNS topic for alarm notifications
            
        Returns:
            Dict containing alarm creation results
        """
        try:
            alarms_created = []
            
            # Extract load balancer name from ARN
            lb_name = load_balancer_arn.split('/')[-3] + '/' + load_balancer_arn.split('/')[-2] + '/' + load_balancer_arn.split('/')[-1]
            
            # ECS Service CPU Alarm
            cpu_alarm = {
                'AlarmName': f'{service_name}-HighCPU',
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 2,
                'MetricName': 'CPUUtilization',
                'Namespace': 'AWS/ECS',
                'Period': 300,
                'Statistic': 'Average',
                'Threshold': 80.0,
                'ActionsEnabled': True,
                'AlarmDescription': f'High CPU utilization for {service_name}',
                'Dimensions': [
                    {'Name': 'ServiceName', 'Value': service_name},
                    {'Name': 'ClusterName', 'Value': cluster_name}
                ],
                'Unit': 'Percent'
            }
            
            if sns_topic_arn:
                cpu_alarm['AlarmActions'] = [sns_topic_arn]
                cpu_alarm['OKActions'] = [sns_topic_arn]
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.put_metric_alarm(**cpu_alarm)
            )
            alarms_created.append(cpu_alarm['AlarmName'])
            
            # ECS Service Memory Alarm
            memory_alarm = {
                'AlarmName': f'{service_name}-HighMemory',
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 2,
                'MetricName': 'MemoryUtilization',
                'Namespace': 'AWS/ECS',
                'Period': 300,
                'Statistic': 'Average',
                'Threshold': 85.0,
                'ActionsEnabled': True,
                'AlarmDescription': f'High memory utilization for {service_name}',
                'Dimensions': [
                    {'Name': 'ServiceName', 'Value': service_name},
                    {'Name': 'ClusterName', 'Value': cluster_name}
                ],
                'Unit': 'Percent'
            }
            
            if sns_topic_arn:
                memory_alarm['AlarmActions'] = [sns_topic_arn]
                memory_alarm['OKActions'] = [sns_topic_arn]
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.put_metric_alarm(**memory_alarm)
            )
            alarms_created.append(memory_alarm['AlarmName'])
            
            # ALB 5XX Error Alarm
            alb_5xx_alarm = {
                'AlarmName': f'{service_name}-ALB-High5XX',
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 2,
                'MetricName': 'HTTPCode_ELB_5XX_Count',
                'Namespace': 'AWS/ApplicationELB',
                'Period': 300,
                'Statistic': 'Sum',
                'Threshold': 10.0,
                'ActionsEnabled': True,
                'AlarmDescription': f'High 5XX error rate for {service_name}',
                'Dimensions': [
                    {'Name': 'LoadBalancer', 'Value': lb_name}
                ],
                'TreatMissingData': 'notBreaching'
            }
            
            if sns_topic_arn:
                alb_5xx_alarm['AlarmActions'] = [sns_topic_arn]
                alb_5xx_alarm['OKActions'] = [sns_topic_arn]
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.put_metric_alarm(**alb_5xx_alarm)
            )
            alarms_created.append(alb_5xx_alarm['AlarmName'])
            
            # RDS CPU Alarm
            rds_cpu_alarm = {
                'AlarmName': f'{db_instance_identifier}-HighCPU',
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 2,
                'MetricName': 'CPUUtilization',
                'Namespace': 'AWS/RDS',
                'Period': 300,
                'Statistic': 'Average',
                'Threshold': 75.0,
                'ActionsEnabled': True,
                'AlarmDescription': f'High CPU utilization for database {db_instance_identifier}',
                'Dimensions': [
                    {'Name': 'DBInstanceIdentifier', 'Value': db_instance_identifier}
                ],
                'Unit': 'Percent'
            }
            
            if sns_topic_arn:
                rds_cpu_alarm['AlarmActions'] = [sns_topic_arn]
                rds_cpu_alarm['OKActions'] = [sns_topic_arn]
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.put_metric_alarm(**rds_cpu_alarm)
            )
            alarms_created.append(rds_cpu_alarm['AlarmName'])
            
            return {
                "status": "success",
                "alarms_created": alarms_created,
                "message": f"Created {len(alarms_created)} alarms successfully"
            }
            
        except Exception as e:
            self.logger.error("Failed to create alarms", error=str(e))
            return {
                "status": "error",
                "message": f"Failed to create alarms: {str(e)}"
            }
    
    async def get_deployment_health_summary(self, cluster_name: str, service_name: str) -> Dict[str, Any]:
        """
        Get comprehensive deployment health summary
        
        Args:
            cluster_name: ECS cluster name
            service_name: ECS service name
            
        Returns:
            Dict containing health summary
        """
        try:
            # Get deployment status
            deployment_status = await self.get_deployment_status(cluster_name, service_name)
            
            # Get recent metrics
            ecs_metrics = await self.get_ecs_metrics(cluster_name, service_name, hours_back=1)
            
            # Calculate health score
            health_score = 100
            health_issues = []
            
            # Check deployment status
            if deployment_status.get("health") == "unhealthy":
                health_score -= 50
                health_issues.append("Service has no running tasks")
            elif deployment_status.get("health") == "degraded":
                health_score -= 25
                health_issues.append("Service is running below desired capacity")
            
            # Check CPU utilization
            if ecs_metrics.get("status") == "success":
                cpu_metrics = ecs_metrics["metrics"].get("cpu_utilization", {})
                if cpu_metrics.get("values"):
                    avg_cpu = sum(cpu_metrics["values"]) / len(cpu_metrics["values"])
                    if avg_cpu > 80:
                        health_score -= 15
                        health_issues.append(f"High CPU utilization: {avg_cpu:.1f}%")
                    elif avg_cpu > 60:
                        health_score -= 5
                        health_issues.append(f"Elevated CPU utilization: {avg_cpu:.1f}%")
                
                # Check memory utilization
                memory_metrics = ecs_metrics["metrics"].get("memory_utilization", {})
                if memory_metrics.get("values"):
                    avg_memory = sum(memory_metrics["values"]) / len(memory_metrics["values"])
                    if avg_memory > 85:
                        health_score -= 15
                        health_issues.append(f"High memory utilization: {avg_memory:.1f}%")
                    elif avg_memory > 70:
                        health_score -= 5
                        health_issues.append(f"Elevated memory utilization: {avg_memory:.1f}%")
            
            # Determine overall health status
            if health_score >= 90:
                overall_health = "excellent"
            elif health_score >= 75:
                overall_health = "good"
            elif health_score >= 50:
                overall_health = "fair"
            else:
                overall_health = "poor"
            
            return {
                "status": "success",
                "health_summary": {
                    "overall_health": overall_health,
                    "health_score": health_score,
                    "health_issues": health_issues,
                    "deployment_status": deployment_status,
                    "metrics_summary": {
                        "cpu_utilization": ecs_metrics["metrics"].get("cpu_utilization", {}),
                        "memory_utilization": ecs_metrics["metrics"].get("memory_utilization", {}),
                        "running_task_count": ecs_metrics["metrics"].get("running_task_count", {})
                    },
                    "timestamp": datetime.now(UTC).isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error("Failed to get health summary", error=str(e))
            return {
                "status": "error",
                "message": f"Failed to get health summary: {str(e)}"
            }