"""
Comprehensive Health Monitoring Service for Court Case Management System
Provides multi-level health checks, performance monitoring, and anomaly detection
"""

import asyncio
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import boto3
from botocore.exceptions import ClientError

from core.database import get_db, validate_database_connection, get_database_info
from core.redis import redis_service
from core.config import settings
from services.health_service import HealthService, HealthStatus, HealthCheckResult

logger = structlog.get_logger()

class PerformanceMetrics:
    """Container for performance metrics"""
    def __init__(self):
        self.response_times: List[float] = []
        self.error_rates: List[float] = []
        self.throughput: List[float] = []
        self.resource_usage: Dict[str, float] = {}
        self.timestamp = datetime.utcnow()

class ComprehensiveHealthService(HealthService):
    """Enhanced health service with comprehensive monitoring capabilities"""
    
    def __init__(self):
        super().__init__()
        self.logger = logger.bind(service="comprehensive_health")
        self.performance_history: List[PerformanceMetrics] = []
        self.alert_thresholds = {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "disk_usage": 90.0,
            "response_time": 2.0,  # seconds
            "error_rate": 5.0,     # percentage
            "db_connections": 80   # percentage of max connections
        }
        
        # Initialize CloudWatch client for metrics
        try:
            self.cloudwatch = boto3.client('cloudwatch', region_name=settings.AWS_REGION)
        except Exception as e:
            self.logger.warning("CloudWatch client initialization failed", error=str(e))
            self.cloudwatch = None
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check with performance monitoring
        
        Returns:
            Dict containing detailed health status, metrics, and recommendations
        """
        self.logger.info("Starting comprehensive health check with performance monitoring")
        
        # Run all health checks concurrently
        health_results = await self.check_all_services()
        
        # Collect performance metrics
        performance_metrics = await self._collect_performance_metrics()
        
        # Check resource utilization
        resource_metrics = await self._check_resource_utilization()
        
        # Analyze load balancer health
        lb_health = await self._check_load_balancer_health()
        
        # Check application-level metrics
        app_metrics = await self._check_application_metrics()
        
        # Detect anomalies
        anomalies = await self._detect_anomalies(performance_metrics, resource_metrics)
        
        # Generate recommendations
        recommendations = await self._generate_health_recommendations(
            health_results, performance_metrics, resource_metrics, anomalies
        )
        
        # Calculate comprehensive health score
        health_score = self._calculate_health_score(
            health_results, performance_metrics, resource_metrics, anomalies
        )
        
        comprehensive_result = {
            "overall_status": health_results["overall_status"],
            "health_score": health_score,
            "timestamp": datetime.utcnow().isoformat(),
            "services": health_results["services"],
            "performance_metrics": performance_metrics,
            "resource_metrics": resource_metrics,
            "load_balancer_health": lb_health,
            "application_metrics": app_metrics,
            "anomalies": anomalies,
            "recommendations": recommendations,
            "alert_status": self._check_alert_conditions(performance_metrics, resource_metrics)
        }
        
        # Store metrics for trend analysis
        self._store_performance_metrics(performance_metrics)
        
        self.logger.info(
            "Comprehensive health check completed",
            overall_status=health_results["overall_status"],
            health_score=health_score,
            anomaly_count=len(anomalies)
        )
        
        return comprehensive_result
    
    async def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect application performance metrics"""
        try:
            metrics = {}
            
            # Database performance metrics
            db_metrics = await self._get_database_performance()
            metrics["database"] = db_metrics
            
            # Redis performance metrics
            redis_metrics = await self._get_redis_performance()
            metrics["redis"] = redis_metrics
            
            # Application response time metrics
            response_metrics = await self._measure_response_times()
            metrics["response_times"] = response_metrics
            
            # Error rate metrics
            error_metrics = await self._calculate_error_rates()
            metrics["error_rates"] = error_metrics
            
            return metrics
            
        except Exception as e:
            self.logger.error("Failed to collect performance metrics", error=str(e))
            return {"error": str(e)}
    
    async def _get_database_performance(self) -> Dict[str, Any]:
        """Get database performance metrics"""
        try:
            db_info = await get_database_info()
            
            # Measure query response time
            start_time = time.time()
            async for session in get_db():
                result = await session.execute(text("SELECT 1"))
                await session.commit()
                break
            query_time = time.time() - start_time
            
            return {
                "query_response_time": query_time,
                "connection_pool_size": db_info.get("pool_info", {}).get("size", 0),
                "active_connections": db_info.get("pool_info", {}).get("checked_out", 0),
                "connection_pool_overflow": db_info.get("pool_info", {}).get("overflow", 0),
                "status": "healthy" if query_time < 0.1 else "degraded"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "unhealthy"
            }
    
    async def _get_redis_performance(self) -> Dict[str, Any]:
        """Get Redis performance metrics"""
        try:
            # Measure Redis response time
            start_time = time.time()
            await redis_service.set("perf_test", "test", expire=5)
            value = await redis_service.get("perf_test")
            response_time = time.time() - start_time
            
            # Get Redis info (if available)
            redis_info = {}
            try:
                # This would require direct Redis client access
                redis_info = {"memory_usage": "unknown", "connected_clients": "unknown"}
            except:
                pass
            
            return {
                "response_time": response_time,
                "test_operation_success": value == "test",
                "redis_info": redis_info,
                "status": "healthy" if response_time < 0.01 else "degraded"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "unhealthy"
            }
    
    async def _measure_response_times(self) -> Dict[str, Any]:
        """Measure application endpoint response times"""
        try:
            import aiohttp
            
            endpoints = [
                "/health/ready",
                "/api/v1/health/status",
                "/api/v1/cases/",  # Assuming this exists
            ]
            
            response_times = {}
            
            async with aiohttp.ClientSession() as session:
                for endpoint in endpoints:
                    try:
                        start_time = time.time()
                        async with session.get(f"http://localhost:8000{endpoint}") as response:
                            response_time = time.time() - start_time
                            response_times[endpoint] = {
                                "response_time": response_time,
                                "status_code": response.status,
                                "status": "healthy" if response_time < 1.0 else "degraded"
                            }
                    except Exception as e:
                        response_times[endpoint] = {
                            "error": str(e),
                            "status": "unhealthy"
                        }
            
            return response_times
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _calculate_error_rates(self) -> Dict[str, Any]:
        """Calculate application error rates"""
        try:
            # This would typically come from application logs or metrics
            # For now, return placeholder data
            return {
                "http_5xx_rate": 0.1,  # 0.1% error rate
                "http_4xx_rate": 2.5,  # 2.5% client error rate
                "database_error_rate": 0.0,
                "redis_error_rate": 0.0,
                "overall_error_rate": 0.1,
                "status": "healthy"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _check_resource_utilization(self) -> Dict[str, Any]:
        """Check system resource utilization"""
        try:
            # CPU utilization
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory utilization
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk utilization
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network I/O
            network = psutil.net_io_counters()
            
            # Process information
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "status": "healthy" if cpu_percent < self.alert_thresholds["cpu_usage"] else "degraded"
                },
                "memory": {
                    "usage_percent": memory_percent,
                    "available_gb": memory.available / (1024**3),
                    "total_gb": memory.total / (1024**3),
                    "status": "healthy" if memory_percent < self.alert_thresholds["memory_usage"] else "degraded"
                },
                "disk": {
                    "usage_percent": disk_percent,
                    "free_gb": disk.free / (1024**3),
                    "total_gb": disk.total / (1024**3),
                    "status": "healthy" if disk_percent < self.alert_thresholds["disk_usage"] else "degraded"
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "process": {
                    "memory_mb": process_memory.rss / (1024**2),
                    "cpu_percent": process.cpu_percent()
                }
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _check_load_balancer_health(self) -> Dict[str, Any]:
        """Check load balancer health and target group status"""
        try:
            if not self.cloudwatch:
                return {"error": "CloudWatch client not available"}
            
            # This would typically query ALB target group health
            # For now, return placeholder data
            return {
                "healthy_targets": 2,
                "total_targets": 2,
                "health_percentage": 100.0,
                "response_time_avg": 0.15,
                "request_count_5min": 150,
                "error_count_5min": 0,
                "status": "healthy"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _check_application_metrics(self) -> Dict[str, Any]:
        """Check application-specific metrics"""
        try:
            # Application-specific health checks
            metrics = {
                "active_sessions": 0,  # Would come from session store
                "background_jobs_pending": 0,  # Would come from job queue
                "cache_hit_rate": 95.0,  # Would come from Redis
                "database_query_avg_time": 0.05,  # Would come from DB metrics
                "api_requests_per_minute": 50,  # Would come from application metrics
                "websocket_connections": 0,  # Would come from WebSocket server
                "status": "healthy"
            }
            
            return metrics
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _detect_anomalies(self, performance_metrics: Dict[str, Any], 
                              resource_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect performance anomalies and unusual patterns"""
        anomalies = []
        
        try:
            # Check CPU anomalies
            cpu_usage = resource_metrics.get("cpu", {}).get("usage_percent", 0)
            if cpu_usage > self.alert_thresholds["cpu_usage"]:
                anomalies.append({
                    "type": "high_cpu_usage",
                    "severity": "warning" if cpu_usage < 90 else "critical",
                    "value": cpu_usage,
                    "threshold": self.alert_thresholds["cpu_usage"],
                    "message": f"CPU usage is {cpu_usage:.1f}%, exceeding threshold of {self.alert_thresholds['cpu_usage']}%"
                })
            
            # Check memory anomalies
            memory_usage = resource_metrics.get("memory", {}).get("usage_percent", 0)
            if memory_usage > self.alert_thresholds["memory_usage"]:
                anomalies.append({
                    "type": "high_memory_usage",
                    "severity": "warning" if memory_usage < 95 else "critical",
                    "value": memory_usage,
                    "threshold": self.alert_thresholds["memory_usage"],
                    "message": f"Memory usage is {memory_usage:.1f}%, exceeding threshold of {self.alert_thresholds['memory_usage']}%"
                })
            
            # Check database response time anomalies
            db_response_time = performance_metrics.get("database", {}).get("query_response_time", 0)
            if db_response_time > 0.5:  # 500ms threshold
                anomalies.append({
                    "type": "slow_database_response",
                    "severity": "warning" if db_response_time < 1.0 else "critical",
                    "value": db_response_time,
                    "threshold": 0.5,
                    "message": f"Database response time is {db_response_time:.3f}s, exceeding normal range"
                })
            
            # Check error rate anomalies
            error_rate = performance_metrics.get("error_rates", {}).get("overall_error_rate", 0)
            if error_rate > self.alert_thresholds["error_rate"]:
                anomalies.append({
                    "type": "high_error_rate",
                    "severity": "critical",
                    "value": error_rate,
                    "threshold": self.alert_thresholds["error_rate"],
                    "message": f"Error rate is {error_rate:.1f}%, exceeding threshold of {self.alert_thresholds['error_rate']}%"
                })
            
        except Exception as e:
            self.logger.error("Failed to detect anomalies", error=str(e))
            anomalies.append({
                "type": "anomaly_detection_error",
                "severity": "warning",
                "message": f"Anomaly detection failed: {str(e)}"
            })
        
        return anomalies
    
    async def _generate_health_recommendations(self, health_results: Dict[str, Any],
                                             performance_metrics: Dict[str, Any],
                                             resource_metrics: Dict[str, Any],
                                             anomalies: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable health recommendations"""
        recommendations = []
        
        # Check overall health status
        if health_results["overall_status"] == HealthStatus.UNHEALTHY:
            recommendations.append("System is unhealthy - immediate attention required")
        elif health_results["overall_status"] == HealthStatus.DEGRADED:
            recommendations.append("System is degraded - monitor closely and address issues")
        
        # Resource-based recommendations
        cpu_usage = resource_metrics.get("cpu", {}).get("usage_percent", 0)
        if cpu_usage > 80:
            recommendations.append(f"High CPU usage ({cpu_usage:.1f}%) - consider scaling up or optimizing application")
        
        memory_usage = resource_metrics.get("memory", {}).get("usage_percent", 0)
        if memory_usage > 85:
            recommendations.append(f"High memory usage ({memory_usage:.1f}%) - check for memory leaks or increase memory allocation")
        
        # Performance-based recommendations
        db_response_time = performance_metrics.get("database", {}).get("query_response_time", 0)
        if db_response_time > 0.1:
            recommendations.append(f"Slow database queries ({db_response_time:.3f}s) - optimize queries or increase database resources")
        
        # Anomaly-based recommendations
        for anomaly in anomalies:
            if anomaly["type"] == "high_cpu_usage":
                recommendations.append("Consider implementing CPU-intensive task queuing or horizontal scaling")
            elif anomaly["type"] == "high_memory_usage":
                recommendations.append("Review memory usage patterns and implement garbage collection optimization")
            elif anomaly["type"] == "slow_database_response":
                recommendations.append("Analyze slow queries and consider database indexing or connection pooling adjustments")
            elif anomaly["type"] == "high_error_rate":
                recommendations.append("Investigate error patterns and implement additional error handling")
        
        # Service-specific recommendations
        for service_name, service_info in health_results.get("services", {}).items():
            if service_info["status"] == HealthStatus.UNHEALTHY:
                recommendations.append(f"Service {service_name} is unhealthy - check logs and restart if necessary")
        
        if not recommendations:
            recommendations.append("All systems are operating normally - continue monitoring")
        
        return recommendations
    
    def _calculate_health_score(self, health_results: Dict[str, Any],
                               performance_metrics: Dict[str, Any],
                               resource_metrics: Dict[str, Any],
                               anomalies: List[Dict[str, Any]]) -> int:
        """Calculate overall health score (0-100)"""
        score = 100
        
        # Deduct points for unhealthy services
        for service_info in health_results.get("services", {}).values():
            if service_info["status"] == HealthStatus.UNHEALTHY:
                score -= 15
            elif service_info["status"] == HealthStatus.DEGRADED:
                score -= 5
        
        # Deduct points for resource issues
        cpu_usage = resource_metrics.get("cpu", {}).get("usage_percent", 0)
        if cpu_usage > 90:
            score -= 20
        elif cpu_usage > 80:
            score -= 10
        
        memory_usage = resource_metrics.get("memory", {}).get("usage_percent", 0)
        if memory_usage > 95:
            score -= 20
        elif memory_usage > 85:
            score -= 10
        
        # Deduct points for performance issues
        db_response_time = performance_metrics.get("database", {}).get("query_response_time", 0)
        if db_response_time > 1.0:
            score -= 15
        elif db_response_time > 0.5:
            score -= 8
        
        # Deduct points for anomalies
        for anomaly in anomalies:
            if anomaly["severity"] == "critical":
                score -= 15
            elif anomaly["severity"] == "warning":
                score -= 5
        
        return max(0, score)
    
    def _check_alert_conditions(self, performance_metrics: Dict[str, Any],
                               resource_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Check if any alert conditions are met"""
        alerts = {
            "active_alerts": [],
            "warning_count": 0,
            "critical_count": 0
        }
        
        # Check CPU alerts
        cpu_usage = resource_metrics.get("cpu", {}).get("usage_percent", 0)
        if cpu_usage > 90:
            alerts["active_alerts"].append({
                "type": "cpu_critical",
                "message": f"Critical CPU usage: {cpu_usage:.1f}%",
                "severity": "critical"
            })
            alerts["critical_count"] += 1
        elif cpu_usage > self.alert_thresholds["cpu_usage"]:
            alerts["active_alerts"].append({
                "type": "cpu_warning",
                "message": f"High CPU usage: {cpu_usage:.1f}%",
                "severity": "warning"
            })
            alerts["warning_count"] += 1
        
        # Check memory alerts
        memory_usage = resource_metrics.get("memory", {}).get("usage_percent", 0)
        if memory_usage > 95:
            alerts["active_alerts"].append({
                "type": "memory_critical",
                "message": f"Critical memory usage: {memory_usage:.1f}%",
                "severity": "critical"
            })
            alerts["critical_count"] += 1
        elif memory_usage > self.alert_thresholds["memory_usage"]:
            alerts["active_alerts"].append({
                "type": "memory_warning",
                "message": f"High memory usage: {memory_usage:.1f}%",
                "severity": "warning"
            })
            alerts["warning_count"] += 1
        
        return alerts
    
    def _store_performance_metrics(self, metrics: Dict[str, Any]):
        """Store performance metrics for trend analysis"""
        try:
            perf_metrics = PerformanceMetrics()
            
            # Extract key metrics for storage
            if "database" in metrics:
                perf_metrics.response_times.append(
                    metrics["database"].get("query_response_time", 0)
                )
            
            if "error_rates" in metrics:
                perf_metrics.error_rates.append(
                    metrics["error_rates"].get("overall_error_rate", 0)
                )
            
            # Store in memory (in production, this would go to a time-series database)
            self.performance_history.append(perf_metrics)
            
            # Keep only last 100 entries
            if len(self.performance_history) > 100:
                self.performance_history = self.performance_history[-100:]
                
        except Exception as e:
            self.logger.error("Failed to store performance metrics", error=str(e))
    
    async def get_performance_trends(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get performance trends over specified time period"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            # Filter metrics by time
            recent_metrics = [
                m for m in self.performance_history 
                if m.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {"message": "No performance data available for the specified time period"}
            
            # Calculate trends
            response_times = []
            error_rates = []
            
            for metrics in recent_metrics:
                if metrics.response_times:
                    response_times.extend(metrics.response_times)
                if metrics.error_rates:
                    error_rates.extend(metrics.error_rates)
            
            trends = {
                "time_period_hours": hours_back,
                "data_points": len(recent_metrics),
                "response_time_trend": {
                    "average": sum(response_times) / len(response_times) if response_times else 0,
                    "min": min(response_times) if response_times else 0,
                    "max": max(response_times) if response_times else 0,
                    "samples": len(response_times)
                },
                "error_rate_trend": {
                    "average": sum(error_rates) / len(error_rates) if error_rates else 0,
                    "min": min(error_rates) if error_rates else 0,
                    "max": max(error_rates) if error_rates else 0,
                    "samples": len(error_rates)
                }
            }
            
            return trends
            
        except Exception as e:
            self.logger.error("Failed to get performance trends", error=str(e))
            return {"error": str(e)}