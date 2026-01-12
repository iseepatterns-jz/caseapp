"""
Diagnostic and Troubleshooting Service for Court Case Management System
Provides automated diagnostics, log analysis, and guided troubleshooting workflows
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import structlog
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

from core.config import settings
from services.comprehensive_health_service import ComprehensiveHealthService
from services.deployment_monitoring_service import DeploymentMonitoringService

logger = structlog.get_logger()

class DiagnosticIssue:
    """Represents a diagnostic issue with severity and recommendations"""
    def __init__(self, category: str, severity: str, title: str, description: str, 
                 recommendations: List[str], details: Dict[str, Any] = None):
        self.category = category
        self.severity = severity  # critical, warning, info
        self.title = title
        self.description = description
        self.recommendations = recommendations
        self.details = details or {}
        self.timestamp = datetime.utcnow()

class DiagnosticService:
    """Comprehensive diagnostic and troubleshooting service"""
    
    def __init__(self):
        self.logger = logger.bind(service="diagnostic")
        self.health_service = ComprehensiveHealthService()
        self.monitoring_service = DeploymentMonitoringService()
        
        # Initialize AWS clients for log analysis
        try:
            self.logs_client = boto3.client('logs', region_name=settings.AWS_REGION)
            self.ecs_client = boto3.client('ecs', region_name=settings.AWS_REGION)
        except Exception as e:
            self.logger.warning("AWS clients initialization failed", error=str(e))
            self.logs_client = None
            self.ecs_client = None
    
    async def generate_diagnostic_report(self, include_logs: bool = True, 
                                       hours_back: int = 24) -> Dict[str, Any]:
        """
        Generate comprehensive diagnostic report
        
        Args:
            include_logs: Whether to include log analysis
            hours_back: Hours of historical data to analyze
            
        Returns:
            Comprehensive diagnostic report with issues and recommendations
        """
        self.logger.info("Generating comprehensive diagnostic report", hours_back=hours_back)
        
        try:
            # Collect all diagnostic data
            health_data = await self.health_service.comprehensive_health_check()
            system_info = await self._collect_system_information()
            deployment_status = await self._analyze_deployment_status()
            
            # Analyze logs if requested
            log_analysis = {}
            if include_logs and self.logs_client:
                log_analysis = await self._analyze_application_logs(hours_back)
            
            # Detect issues and generate recommendations
            issues = await self._detect_diagnostic_issues(health_data, system_info, deployment_status, log_analysis)
            
            # Generate troubleshooting workflows
            workflows = self._generate_troubleshooting_workflows(issues)
            
            # Create diagnostic summary
            summary = self._create_diagnostic_summary(health_data, issues)
            
            report = {
                "report_id": f"diag_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.utcnow().isoformat(),
                "summary": summary,
                "health_data": health_data,
                "system_info": system_info,
                "deployment_status": deployment_status,
                "log_analysis": log_analysis,
                "issues": [self._issue_to_dict(issue) for issue in issues],
                "troubleshooting_workflows": workflows,
                "recommendations": self._prioritize_recommendations(issues)
            }
            
            self.logger.info(
                "Diagnostic report generated",
                issue_count=len(issues),
                critical_issues=len([i for i in issues if i.severity == "critical"]),
                health_score=health_data.get("health_score", 0)
            )
            
            return report
            
        except Exception as e:
            self.logger.error("Failed to generate diagnostic report", error=str(e))
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "status": "failed"
            }
    
    async def _collect_system_information(self) -> Dict[str, Any]:
        """Collect comprehensive system information"""
        try:
            import platform
            import psutil
            
            system_info = {
                "platform": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor()
                },
                "python": {
                    "version": platform.python_version(),
                    "implementation": platform.python_implementation()
                },
                "resources": {
                    "cpu_count": psutil.cpu_count(),
                    "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                    "disk_total_gb": psutil.disk_usage('/').total / (1024**3)
                },
                "network": {
                    "hostname": platform.node()
                },
                "environment": {
                    "aws_region": settings.AWS_REGION,
                    "debug_mode": settings.DEBUG if hasattr(settings, 'DEBUG') else False
                }
            }
            
            return system_info
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _analyze_deployment_status(self) -> Dict[str, Any]:
        """Analyze current deployment status"""
        try:
            if not self.ecs_client:
                return {"error": "ECS client not available"}
            
            # This would typically use actual cluster and service names from configuration
            cluster_name = "CourtCaseCluster"  # Would come from settings
            service_name = "BackendService"    # Would come from settings
            
            deployment_status = await self.monitoring_service.get_deployment_status(
                cluster_name, service_name
            )
            
            return deployment_status
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _analyze_application_logs(self, hours_back: int) -> Dict[str, Any]:
        """Analyze application logs for errors and patterns"""
        try:
            if not self.logs_client:
                return {"error": "CloudWatch Logs client not available"}
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours_back)
            
            # Convert to milliseconds since epoch
            start_time_ms = int(start_time.timestamp() * 1000)
            end_time_ms = int(end_time.timestamp() * 1000)
            
            log_group_name = "/ecs/BackendService"  # Would come from settings
            
            # Query for errors
            error_query = """
            fields @timestamp, @message
            | filter @message like /ERROR/
            | sort @timestamp desc
            | limit 100
            """
            
            # Query for warnings
            warning_query = """
            fields @timestamp, @message
            | filter @message like /WARNING/ or @message like /WARN/
            | sort @timestamp desc
            | limit 50
            """
            
            # Execute queries
            error_results = await self._execute_log_query(
                log_group_name, error_query, start_time_ms, end_time_ms
            )
            
            warning_results = await self._execute_log_query(
                log_group_name, warning_query, start_time_ms, end_time_ms
            )
            
            # Analyze patterns
            error_patterns = self._analyze_log_patterns(error_results.get("results", []))
            warning_patterns = self._analyze_log_patterns(warning_results.get("results", []))
            
            return {
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "hours_back": hours_back
                },
                "errors": {
                    "count": len(error_results.get("results", [])),
                    "patterns": error_patterns,
                    "recent_errors": error_results.get("results", [])[:10]
                },
                "warnings": {
                    "count": len(warning_results.get("results", [])),
                    "patterns": warning_patterns,
                    "recent_warnings": warning_results.get("results", [])[:10]
                }
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _execute_log_query(self, log_group_name: str, query: str, 
                                start_time: int, end_time: int) -> Dict[str, Any]:
        """Execute CloudWatch Logs Insights query"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.logs_client.start_query(
                    logGroupName=log_group_name,
                    startTime=start_time,
                    endTime=end_time,
                    queryString=query
                )
            )
            
            query_id = response['queryId']
            
            # Wait for query to complete
            max_attempts = 30
            for _ in range(max_attempts):
                await asyncio.sleep(1)
                
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.logs_client.get_query_results(queryId=query_id)
                )
                
                if result['status'] == 'Complete':
                    return {"results": result.get('results', [])}
                elif result['status'] == 'Failed':
                    return {"error": "Query failed"}
            
            return {"error": "Query timeout"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_log_patterns(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze log entries for common patterns and issues"""
        patterns = {
            "database_errors": 0,
            "connection_errors": 0,
            "timeout_errors": 0,
            "authentication_errors": 0,
            "validation_errors": 0,
            "unknown_errors": 0
        }
        
        pattern_regexes = {
            "database_errors": [
                r"database.*error",
                r"connection.*database.*failed",
                r"postgresql.*error",
                r"sqlalchemy.*error"
            ],
            "connection_errors": [
                r"connection.*refused",
                r"connection.*timeout",
                r"network.*unreachable",
                r"redis.*connection.*error"
            ],
            "timeout_errors": [
                r"timeout",
                r"request.*timed.*out",
                r"operation.*timeout"
            ],
            "authentication_errors": [
                r"authentication.*failed",
                r"unauthorized",
                r"invalid.*credentials",
                r"token.*expired"
            ],
            "validation_errors": [
                r"validation.*error",
                r"invalid.*input",
                r"schema.*validation.*failed"
            ]
        }
        
        for entry in log_entries:
            message = entry.get("message", "").lower()
            categorized = False
            
            for pattern_name, regexes in pattern_regexes.items():
                for regex in regexes:
                    if re.search(regex, message):
                        patterns[pattern_name] += 1
                        categorized = True
                        break
                if categorized:
                    break
            
            if not categorized:
                patterns["unknown_errors"] += 1
        
        return patterns
    
    async def _detect_diagnostic_issues(self, health_data: Dict[str, Any],
                                      system_info: Dict[str, Any],
                                      deployment_status: Dict[str, Any],
                                      log_analysis: Dict[str, Any]) -> List[DiagnosticIssue]:
        """Detect and categorize diagnostic issues"""
        issues = []
        
        # Health-based issues
        health_score = health_data.get("health_score", 100)
        if health_score < 50:
            issues.append(DiagnosticIssue(
                category="health",
                severity="critical",
                title="Poor System Health",
                description=f"System health score is {health_score}/100, indicating serious issues",
                recommendations=[
                    "Review all unhealthy services immediately",
                    "Check resource utilization and scale if necessary",
                    "Investigate recent deployments or configuration changes"
                ],
                details={"health_score": health_score}
            ))
        elif health_score < 80:
            issues.append(DiagnosticIssue(
                category="health",
                severity="warning",
                title="Degraded System Health",
                description=f"System health score is {health_score}/100, indicating some issues",
                recommendations=[
                    "Review degraded services and address issues",
                    "Monitor resource usage trends",
                    "Consider preventive maintenance"
                ],
                details={"health_score": health_score}
            ))
        
        # Resource utilization issues
        resource_metrics = health_data.get("resource_metrics", {})
        cpu_usage = resource_metrics.get("cpu", {}).get("usage_percent", 0)
        memory_usage = resource_metrics.get("memory", {}).get("usage_percent", 0)
        
        if cpu_usage > 90:
            issues.append(DiagnosticIssue(
                category="performance",
                severity="critical",
                title="Critical CPU Usage",
                description=f"CPU usage is {cpu_usage:.1f}%, system may be unresponsive",
                recommendations=[
                    "Scale up CPU resources immediately",
                    "Identify CPU-intensive processes",
                    "Consider horizontal scaling",
                    "Review recent code changes for performance issues"
                ],
                details={"cpu_usage": cpu_usage}
            ))
        elif cpu_usage > 80:
            issues.append(DiagnosticIssue(
                category="performance",
                severity="warning",
                title="High CPU Usage",
                description=f"CPU usage is {cpu_usage:.1f}%, approaching critical levels",
                recommendations=[
                    "Monitor CPU usage closely",
                    "Plan for resource scaling",
                    "Optimize CPU-intensive operations"
                ],
                details={"cpu_usage": cpu_usage}
            ))
        
        if memory_usage > 95:
            issues.append(DiagnosticIssue(
                category="performance",
                severity="critical",
                title="Critical Memory Usage",
                description=f"Memory usage is {memory_usage:.1f}%, risk of out-of-memory errors",
                recommendations=[
                    "Increase memory allocation immediately",
                    "Check for memory leaks",
                    "Restart services if necessary",
                    "Review memory-intensive operations"
                ],
                details={"memory_usage": memory_usage}
            ))
        elif memory_usage > 85:
            issues.append(DiagnosticIssue(
                category="performance",
                severity="warning",
                title="High Memory Usage",
                description=f"Memory usage is {memory_usage:.1f}%, monitor closely",
                recommendations=[
                    "Plan for memory scaling",
                    "Monitor for memory leaks",
                    "Optimize memory usage patterns"
                ],
                details={"memory_usage": memory_usage}
            ))
        
        # Deployment issues
        if deployment_status.get("health") == "unhealthy":
            issues.append(DiagnosticIssue(
                category="deployment",
                severity="critical",
                title="Unhealthy Deployment",
                description="ECS service deployment is unhealthy with no running tasks",
                recommendations=[
                    "Check ECS service logs for startup errors",
                    "Verify container image availability",
                    "Check resource allocation and limits",
                    "Review health check configuration"
                ],
                details=deployment_status
            ))
        elif deployment_status.get("health") == "degraded":
            issues.append(DiagnosticIssue(
                category="deployment",
                severity="warning",
                title="Degraded Deployment",
                description="ECS service is running below desired capacity",
                recommendations=[
                    "Check for failing health checks",
                    "Review resource constraints",
                    "Monitor for intermittent failures"
                ],
                details=deployment_status
            ))
        
        # Log-based issues
        if log_analysis and "errors" in log_analysis:
            error_count = log_analysis["errors"].get("count", 0)
            if error_count > 100:
                issues.append(DiagnosticIssue(
                    category="application",
                    severity="critical",
                    title="High Error Rate",
                    description=f"Found {error_count} errors in recent logs",
                    recommendations=[
                        "Review error patterns and fix critical issues",
                        "Check for cascading failures",
                        "Implement additional error handling"
                    ],
                    details={"error_count": error_count, "patterns": log_analysis["errors"].get("patterns", {})}
                ))
            elif error_count > 20:
                issues.append(DiagnosticIssue(
                    category="application",
                    severity="warning",
                    title="Elevated Error Rate",
                    description=f"Found {error_count} errors in recent logs",
                    recommendations=[
                        "Investigate error patterns",
                        "Monitor error trends",
                        "Consider preventive fixes"
                    ],
                    details={"error_count": error_count, "patterns": log_analysis["errors"].get("patterns", {})}
                ))
        
        return issues
    
    def _generate_troubleshooting_workflows(self, issues: List[DiagnosticIssue]) -> Dict[str, Any]:
        """Generate guided troubleshooting workflows based on detected issues"""
        workflows = {}
        
        # Group issues by category
        issues_by_category = {}
        for issue in issues:
            if issue.category not in issues_by_category:
                issues_by_category[issue.category] = []
            issues_by_category[issue.category].append(issue)
        
        # Generate workflows for each category
        for category, category_issues in issues_by_category.items():
            workflows[category] = self._create_category_workflow(category, category_issues)
        
        # Add general troubleshooting workflow
        workflows["general"] = self._create_general_workflow()
        
        return workflows
    
    def _create_category_workflow(self, category: str, issues: List[DiagnosticIssue]) -> Dict[str, Any]:
        """Create troubleshooting workflow for a specific category"""
        critical_issues = [i for i in issues if i.severity == "critical"]
        warning_issues = [i for i in issues if i.severity == "warning"]
        
        workflow = {
            "category": category,
            "priority": "high" if critical_issues else "medium" if warning_issues else "low",
            "steps": []
        }
        
        if category == "health":
            workflow["steps"] = [
                {
                    "step": 1,
                    "action": "Check service status",
                    "command": "GET /api/v1/health/comprehensive",
                    "description": "Get detailed health status of all services"
                },
                {
                    "step": 2,
                    "action": "Review unhealthy services",
                    "description": "Identify and prioritize unhealthy services for investigation"
                },
                {
                    "step": 3,
                    "action": "Check dependencies",
                    "command": "GET /api/v1/health/dependencies",
                    "description": "Verify all service dependencies are available"
                }
            ]
        elif category == "performance":
            workflow["steps"] = [
                {
                    "step": 1,
                    "action": "Check resource metrics",
                    "command": "GET /api/v1/health/metrics/resource",
                    "description": "Review CPU, memory, and disk utilization"
                },
                {
                    "step": 2,
                    "action": "Analyze performance trends",
                    "command": "GET /api/v1/health/performance/trends",
                    "description": "Check performance trends over time"
                },
                {
                    "step": 3,
                    "action": "Scale resources if needed",
                    "description": "Increase CPU/memory allocation or scale horizontally"
                }
            ]
        elif category == "deployment":
            workflow["steps"] = [
                {
                    "step": 1,
                    "action": "Check deployment status",
                    "command": "GET /api/v1/monitoring/deployment/status",
                    "description": "Review ECS service deployment status"
                },
                {
                    "step": 2,
                    "action": "Review container logs",
                    "description": "Check ECS task logs for startup errors"
                },
                {
                    "step": 3,
                    "action": "Verify health checks",
                    "description": "Ensure health check endpoints are responding correctly"
                }
            ]
        elif category == "application":
            workflow["steps"] = [
                {
                    "step": 1,
                    "action": "Analyze error patterns",
                    "description": "Review application logs for error patterns and root causes"
                },
                {
                    "step": 2,
                    "action": "Check database connectivity",
                    "command": "GET /api/v1/health/metrics/performance",
                    "description": "Verify database and Redis connectivity"
                },
                {
                    "step": 3,
                    "action": "Review recent deployments",
                    "description": "Check if errors correlate with recent code deployments"
                }
            ]
        
        return workflow
    
    def _create_general_workflow(self) -> Dict[str, Any]:
        """Create general troubleshooting workflow"""
        return {
            "category": "general",
            "priority": "medium",
            "description": "General troubleshooting steps for system issues",
            "steps": [
                {
                    "step": 1,
                    "action": "Generate diagnostic report",
                    "command": "POST /api/v1/diagnostics/report",
                    "description": "Generate comprehensive diagnostic report"
                },
                {
                    "step": 2,
                    "action": "Check system health",
                    "command": "GET /api/v1/health/comprehensive",
                    "description": "Review overall system health and identify issues"
                },
                {
                    "step": 3,
                    "action": "Review active alerts",
                    "command": "GET /api/v1/health/alerts",
                    "description": "Check for active alerts and anomalies"
                },
                {
                    "step": 4,
                    "action": "Follow category-specific workflows",
                    "description": "Use specific workflows based on identified issue categories"
                },
                {
                    "step": 5,
                    "action": "Implement recommendations",
                    "command": "GET /api/v1/health/recommendations",
                    "description": "Follow system-generated recommendations"
                }
            ]
        }
    
    def _create_diagnostic_summary(self, health_data: Dict[str, Any], 
                                 issues: List[DiagnosticIssue]) -> Dict[str, Any]:
        """Create diagnostic summary"""
        critical_issues = [i for i in issues if i.severity == "critical"]
        warning_issues = [i for i in issues if i.severity == "warning"]
        info_issues = [i for i in issues if i.severity == "info"]
        
        return {
            "overall_status": health_data.get("overall_status", "unknown"),
            "health_score": health_data.get("health_score", 0),
            "total_issues": len(issues),
            "critical_issues": len(critical_issues),
            "warning_issues": len(warning_issues),
            "info_issues": len(info_issues),
            "requires_immediate_attention": len(critical_issues) > 0,
            "top_recommendations": self._get_top_recommendations(issues)[:5]
        }
    
    def _prioritize_recommendations(self, issues: List[DiagnosticIssue]) -> List[Dict[str, Any]]:
        """Prioritize recommendations based on issue severity and impact"""
        all_recommendations = []
        
        # Sort issues by severity (critical first)
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        sorted_issues = sorted(issues, key=lambda x: severity_order.get(x.severity, 3))
        
        for issue in sorted_issues:
            for i, recommendation in enumerate(issue.recommendations):
                all_recommendations.append({
                    "priority": severity_order.get(issue.severity, 3),
                    "category": issue.category,
                    "issue_title": issue.title,
                    "recommendation": recommendation,
                    "severity": issue.severity,
                    "order": i
                })
        
        return all_recommendations[:20]  # Return top 20 recommendations
    
    def _get_top_recommendations(self, issues: List[DiagnosticIssue]) -> List[str]:
        """Get top recommendations from all issues"""
        recommendations = []
        for issue in issues:
            if issue.severity == "critical":
                recommendations.extend(issue.recommendations)
        
        # If no critical issues, add warning recommendations
        if not recommendations:
            for issue in issues:
                if issue.severity == "warning":
                    recommendations.extend(issue.recommendations[:2])  # Top 2 per warning
        
        return recommendations
    
    def _issue_to_dict(self, issue: DiagnosticIssue) -> Dict[str, Any]:
        """Convert DiagnosticIssue to dictionary"""
        return {
            "category": issue.category,
            "severity": issue.severity,
            "title": issue.title,
            "description": issue.description,
            "recommendations": issue.recommendations,
            "details": issue.details,
            "timestamp": issue.timestamp.isoformat()
        }
    
    async def get_guided_troubleshooting(self, issue_category: str) -> Dict[str, Any]:
        """Get guided troubleshooting steps for a specific issue category"""
        try:
            # Generate current diagnostic data
            health_data = await self.health_service.comprehensive_health_check()
            
            # Filter issues by category
            all_issues = await self._detect_diagnostic_issues(health_data, {}, {}, {})
            category_issues = [i for i in all_issues if i.category == issue_category]
            
            if not category_issues:
                return {
                    "category": issue_category,
                    "status": "no_issues",
                    "message": f"No issues detected in category '{issue_category}'",
                    "general_workflow": self._create_general_workflow()
                }
            
            # Generate workflow for this category
            workflow = self._create_category_workflow(issue_category, category_issues)
            
            return {
                "category": issue_category,
                "status": "issues_detected",
                "issues": [self._issue_to_dict(issue) for issue in category_issues],
                "workflow": workflow,
                "estimated_resolution_time": self._estimate_resolution_time(category_issues)
            }
            
        except Exception as e:
            self.logger.error("Failed to get guided troubleshooting", error=str(e))
            return {"error": str(e)}
    
    def _estimate_resolution_time(self, issues: List[DiagnosticIssue]) -> Dict[str, Any]:
        """Estimate resolution time based on issue complexity"""
        critical_count = len([i for i in issues if i.severity == "critical"])
        warning_count = len([i for i in issues if i.severity == "warning"])
        
        # Base time estimates in minutes
        base_times = {
            "critical": 30,  # 30 minutes per critical issue
            "warning": 15,   # 15 minutes per warning issue
            "info": 5        # 5 minutes per info issue
        }
        
        total_minutes = (critical_count * base_times["critical"] + 
                        warning_count * base_times["warning"])
        
        return {
            "estimated_minutes": total_minutes,
            "estimated_hours": round(total_minutes / 60, 1),
            "complexity": "high" if critical_count > 2 else "medium" if critical_count > 0 else "low",
            "requires_expert": critical_count > 3 or warning_count > 10
        }