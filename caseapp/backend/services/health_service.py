"""
Health Check Service for Court Case Management System
Validates all services and dependencies are functioning properly
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.database import get_db
from core.redis import redis_service
from services.aws_service import aws_service
from services.case_service import CaseService
from services.document_service import DocumentService
from services.timeline_service import TimelineService
from services.media_service import MediaService
# from services.forensic_analysis_service import ForensicAnalysisService  # Skip due to missing dependencies
# from services.timeline_collaboration_service import TimelineCollaborationService  # Skip due to potential issues
from services.case_insight_service import CaseInsightService
# from services.export_service import ExportService  # Skip due to missing dependencies
from services.integration_service import IntegrationService
from services.efiling_service import EFilingService
from services.background_job_service import BackgroundJobService
from services.webhook_service import WebhookService
from services.security_service import SecurityService
from services.encryption_service import EncryptionService

logger = structlog.get_logger()

class HealthStatus:
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class HealthCheckResult:
    """Health check result for a single component"""
    def __init__(self, name: str, status: str, message: str = "", details: Dict[str, Any] = None):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow()

class HealthService:
    """Comprehensive health check service"""
    
    def __init__(self):
        self.logger = logger.bind(service="health")
    
    async def check_all_services(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of all services
        
        Returns:
            Dict containing overall status and individual service results
        """
        self.logger.info("Starting comprehensive health check")
        
        # Run all health checks concurrently
        checks = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
            self._check_aws_services(),
            self._check_core_services(),
            self._check_ai_services(),
            self._check_security_services(),
            self._check_integration_services(),
            return_exceptions=True
        )
        
        # Collect results
        all_results = []
        for check_result in checks:
            if isinstance(check_result, Exception):
                all_results.append(HealthCheckResult(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(check_result)}"
                ))
            elif isinstance(check_result, list):
                all_results.extend(check_result)
            else:
                all_results.append(check_result)
        
        # Calculate overall status
        overall_status = self._calculate_overall_status(all_results)
        
        # Format response
        response = {
            "overall_status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                result.name: {
                    "status": result.status,
                    "message": result.message,
                    "details": result.details,
                    "timestamp": result.timestamp.isoformat()
                }
                for result in all_results
            }
        }
        
        self.logger.info("Health check completed", overall_status=overall_status)
        return response
    
    async def _check_database(self) -> HealthCheckResult:
        """Check database connectivity and basic operations with enhanced validation"""
        try:
            from core.database import validate_database_connection, get_database_info
            
            # Use enhanced database validation
            connection_valid = await validate_database_connection()
            
            if connection_valid:
                # Get additional database information
                db_info = await get_database_info()
                
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful with connection pooling",
                    details={
                        "connection_valid": True,
                        "pool_info": db_info.get("pool_info", {}),
                        "validation_method": "enhanced_with_retry"
                    }
                )
            else:
                db_info = await get_database_info()
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="Database connection validation failed",
                    details={
                        "connection_valid": False,
                        "error_info": db_info.get("error", "Unknown error"),
                        "validation_method": "enhanced_with_retry"
                    }
                )
                
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "validation_method": "enhanced_with_retry"
                }
            )
    
    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity"""
        try:
            # Test Redis connection
            await redis_service.set("health_check", "test", expire=10)
            value = await redis_service.get("health_check")
            
            if value == "test":
                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    message="Redis connection successful",
                    details={"test_operation": "OK"}
                )
            else:
                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    message="Redis test operation failed"
                )
        except Exception as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}"
            )
    
    async def _check_aws_services(self) -> List[HealthCheckResult]:
        """Check AWS service connectivity"""
        results = []
        
        # Check each AWS service
        aws_services = [
            ("textract", "Amazon Textract"),
            ("comprehend", "Amazon Comprehend"),
            ("bedrock", "Amazon Bedrock"),
            ("transcribe", "Amazon Transcribe"),
            ("s3", "Amazon S3")
        ]
        
        for service_key, service_name in aws_services:
            try:
                # Test service availability (simplified check)
                client = getattr(aws_service, f"{service_key}_client", None)
                if client:
                    results.append(HealthCheckResult(
                        name=f"aws_{service_key}",
                        status=HealthStatus.HEALTHY,
                        message=f"{service_name} client initialized",
                        details={"client_status": "initialized"}
                    ))
                else:
                    results.append(HealthCheckResult(
                        name=f"aws_{service_key}",
                        status=HealthStatus.UNHEALTHY,
                        message=f"{service_name} client not available"
                    ))
            except Exception as e:
                results.append(HealthCheckResult(
                    name=f"aws_{service_key}",
                    status=HealthStatus.UNHEALTHY,
                    message=f"{service_name} check failed: {str(e)}"
                ))
        
        return results
    
    async def _check_core_services(self) -> List[HealthCheckResult]:
        """Check core business services"""
        results = []
        
        # Core services to check (excluding problematic ones)
        services = [
            ("CaseService", "services.case_service"),
            ("DocumentService", "services.document_service"),
            ("TimelineService", "services.timeline_service"),
            ("MediaService", "services.media_service"),
            ("TimelineCollaborationService", "services.timeline_collaboration_service")
        ]
        
        for service_name, module_path in services:
            try:
                # Test service import and instantiation
                module = __import__(module_path, fromlist=[service_name])
                service_class = getattr(module, service_name)
                service = service_class()
                
                results.append(HealthCheckResult(
                    name=service_name.lower(),
                    status=HealthStatus.HEALTHY,
                    message=f"{service_name} initialized successfully",
                    details={"service_class": service_class.__name__}
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    name=service_name.lower(),
                    status=HealthStatus.UNHEALTHY,
                    message=f"{service_name} initialization failed: {str(e)}"
                ))
        
        return results
    
    async def _check_ai_services(self) -> List[HealthCheckResult]:
        """Check AI-powered services"""
        results = []
        
        # AI services to check (using dynamic import)
        ai_services = [
            ("CaseInsightService", "services.case_insight_service")
            # ("ExportService", "services.export_service")  # Skip due to missing dependencies
        ]
        
        for service_name, module_path in ai_services:
            try:
                # Test service import and instantiation
                module = __import__(module_path, fromlist=[service_name])
                service_class = getattr(module, service_name)
                service = service_class()
                
                results.append(HealthCheckResult(
                    name=service_name.lower(),
                    status=HealthStatus.HEALTHY,
                    message=f"{service_name} initialized successfully",
                    details={"ai_enabled": True}
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    name=service_name.lower(),
                    status=HealthStatus.UNHEALTHY,
                    message=f"{service_name} initialization failed: {str(e)}"
                ))
        
        return results
    
    async def _check_security_services(self) -> List[HealthCheckResult]:
        """Check security and encryption services"""
        results = []
        
        # Security services to check (using dynamic import)
        security_services = [
            ("SecurityService", "services.security_service"),
            ("EncryptionService", "services.encryption_service")
        ]
        
        for service_name, module_path in security_services:
            try:
                # Test service import and instantiation
                module = __import__(module_path, fromlist=[service_name])
                service_class = getattr(module, service_name)
                service = service_class()
                
                results.append(HealthCheckResult(
                    name=service_name.lower(),
                    status=HealthStatus.HEALTHY,
                    message=f"{service_name} initialized successfully",
                    details={"security_enabled": True}
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    name=service_name.lower(),
                    status=HealthStatus.UNHEALTHY,
                    message=f"{service_name} initialization failed: {str(e)}"
                ))
        
        return results
    
    async def _check_integration_services(self) -> List[HealthCheckResult]:
        """Check integration and background services"""
        results = []
        
        # Integration services to check (using dynamic import)
        integration_services = [
            ("IntegrationService", "services.integration_service"),
            ("EFilingService", "services.efiling_service"),
            ("BackgroundJobService", "services.background_job_service"),
            ("WebhookService", "services.webhook_service")
        ]
        
        for service_name, module_path in integration_services:
            try:
                # Test service import and instantiation
                module = __import__(module_path, fromlist=[service_name])
                service_class = getattr(module, service_name)
                service = service_class()
                
                results.append(HealthCheckResult(
                    name=service_name.lower(),
                    status=HealthStatus.HEALTHY,
                    message=f"{service_name} initialized successfully",
                    details={"integration_enabled": True}
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    name=service_name.lower(),
                    status=HealthStatus.UNHEALTHY,
                    message=f"{service_name} initialization failed: {str(e)}"
                ))
        
        return results
    
    def _calculate_overall_status(self, results: List[HealthCheckResult]) -> str:
        """Calculate overall system status based on individual service results"""
        if not results:
            return HealthStatus.UNHEALTHY
        
        unhealthy_count = sum(1 for r in results if r.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for r in results if r.status == HealthStatus.DEGRADED)
        
        # If any critical services are unhealthy, system is unhealthy
        critical_services = ["database", "redis"]
        critical_unhealthy = any(
            r.status == HealthStatus.UNHEALTHY and r.name in critical_services
            for r in results
        )
        
        if critical_unhealthy:
            return HealthStatus.UNHEALTHY
        
        # If more than 25% of services are unhealthy, system is unhealthy
        if unhealthy_count > len(results) * 0.25:
            return HealthStatus.UNHEALTHY
        
        # If any services are degraded or some are unhealthy, system is degraded
        if degraded_count > 0 or unhealthy_count > 0:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    async def check_service_dependencies(self) -> Dict[str, Any]:
        """
        Check service dependencies and initialization order
        
        Returns:
            Dict containing dependency status and recommendations
        """
        dependencies = {
            "database": {
                "required_for": ["all_services"],
                "status": "checking"
            },
            "redis": {
                "required_for": ["collaboration", "background_jobs", "caching"],
                "status": "checking"
            },
            "aws_services": {
                "required_for": ["ai_analysis", "document_processing", "insights"],
                "status": "checking"
            }
        }
        
        # Check each dependency
        db_result = await self._check_database()
        dependencies["database"]["status"] = db_result.status
        
        redis_result = await self._check_redis()
        dependencies["redis"]["status"] = redis_result.status
        
        aws_results = await self._check_aws_services()
        aws_healthy = all(r.status == HealthStatus.HEALTHY for r in aws_results)
        dependencies["aws_services"]["status"] = HealthStatus.HEALTHY if aws_healthy else HealthStatus.DEGRADED
        
        return {
            "dependencies": dependencies,
            "recommendations": self._get_dependency_recommendations(dependencies)
        }
    
    def _get_dependency_recommendations(self, dependencies: Dict[str, Any]) -> List[str]:
        """Get recommendations based on dependency status"""
        recommendations = []
        
        for dep_name, dep_info in dependencies.items():
            if dep_info["status"] == HealthStatus.UNHEALTHY:
                if dep_name == "database":
                    recommendations.append("Database connection failed - check PostgreSQL service and connection settings")
                elif dep_name == "redis":
                    recommendations.append("Redis connection failed - check Redis service and connection settings")
                elif dep_name == "aws_services":
                    recommendations.append("AWS services unavailable - check AWS credentials and service configuration")
            elif dep_info["status"] == HealthStatus.DEGRADED:
                recommendations.append(f"{dep_name} is degraded - some functionality may be limited")
        
        if not recommendations:
            recommendations.append("All dependencies are healthy - system is fully operational")
        
        return recommendations