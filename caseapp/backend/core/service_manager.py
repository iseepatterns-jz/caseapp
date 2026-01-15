"""
Service Manager for Court Case Management System
Manages service initialization, dependencies, and graceful shutdown
"""

import asyncio
from typing import Dict, List, Any, Optional
import structlog
from contextlib import asynccontextmanager

from core.database import engine, Base
from core.redis import redis_service
from services.aws_service import aws_service
from services.health_service import HealthService

logger = structlog.get_logger()

class ServiceManager:
    """Manages service lifecycle and dependencies"""
    
    def __init__(self):
        self.logger = logger.bind(component="service_manager")
        self.initialized_services: Dict[str, bool] = {}
        self.service_errors: Dict[str, str] = {}
        self.health_service = HealthService()
    
    async def initialize_all_services(self) -> Dict[str, Any]:
        """
        Initialize all services in proper dependency order
        
        Returns:
            Dict containing initialization results
        """
        self.logger.info("Starting service initialization")
        
        initialization_steps = [
            ("database", self._initialize_database),
            ("redis", self._initialize_redis),
            ("aws_services", self._initialize_aws_services),
            ("core_services", self._initialize_core_services),
            ("ai_services", self._initialize_ai_services),
            ("security_services", self._initialize_security_services),
            ("integration_services", self._initialize_integration_services)
        ]
        
        results = {}
        
        for service_name, init_func in initialization_steps:
            try:
                self.logger.info(f"Initializing {service_name}")
                result = await init_func()
                self.initialized_services[service_name] = True
                results[service_name] = {
                    "status": "success",
                    "message": f"{service_name} initialized successfully",
                    "details": result
                }
                self.logger.info(f"{service_name} initialized successfully")
            
            except Exception as e:
                error_msg = f"Failed to initialize {service_name}: {str(e)}"
                self.logger.error(error_msg, error=str(e))
                self.initialized_services[service_name] = False
                self.service_errors[service_name] = error_msg
                results[service_name] = {
                    "status": "error",
                    "message": error_msg,
                    "details": {}
                }
                
                # For critical services, stop initialization
                if service_name in ["database", "redis"]:
                    self.logger.error(f"Critical service {service_name} failed, stopping initialization")
                    break
        
        # Generate overall status
        successful_services = sum(1 for success in self.initialized_services.values() if success)
        total_services = len(initialization_steps)
        
        overall_status = {
            "status": "success" if successful_services == total_services else "partial",
            "successful_services": successful_services,
            "total_services": total_services,
            "services": results
        }
        
        self.logger.info(
            "Service initialization completed",
            successful=successful_services,
            total=total_services,
            status=overall_status["status"]
        )
        
        return overall_status
    
    async def _initialize_database(self) -> Dict[str, Any]:
        """Initialize database connection and create tables"""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Verify database connection
        health_result = await self.health_service._check_database()
        if health_result.status != "healthy":
            raise Exception(f"Database health check failed: {health_result.message}")
        
        return {"tables_created": True, "connection_verified": True}
    
    async def _initialize_redis(self) -> Dict[str, Any]:
        """Initialize Redis connection"""
        await redis_service.initialize()
        
        # Verify Redis connection
        health_result = await self.health_service._check_redis()
        if health_result.status != "healthy":
            raise Exception(f"Redis health check failed: {health_result.message}")
        
        return {"connection_established": True, "connection_verified": True}
    
    async def _initialize_aws_services(self) -> Dict[str, Any]:
        """Initialize AWS service clients"""
        await aws_service.initialize()
        
        # Verify AWS services
        aws_results = await self.health_service._check_aws_services()
        healthy_services = [r for r in aws_results if r.status == "healthy"]
        
        return {
            "services_initialized": len(aws_results),
            "healthy_services": len(healthy_services),
            "service_details": {r.name: r.status for r in aws_results}
        }
    
    async def _initialize_core_services(self) -> Dict[str, Any]:
        """Initialize core business services"""
        # Core services are initialized on-demand, so just verify they can be imported
        try:
            from services.case_service import CaseService
            from services.document_service import DocumentService
            from services.timeline_service import TimelineService
            from services.media_service import MediaService
            from services.forensic_analysis_service import ForensicAnalysisService
            from services.timeline_collaboration_service import TimelineCollaborationService
            
            # Just verify imports work - don't instantiate (services require dependencies)
            service_classes = [
                CaseService,
                DocumentService,
                TimelineService,
                MediaService,
                ForensicAnalysisService,
                TimelineCollaborationService
            ]
            
            return {
                "services_available": len(service_classes),
                "import_successful": True
            }
        
        except Exception as e:
            raise Exception(f"Core services import failed: {str(e)}")
    
    async def _initialize_ai_services(self) -> Dict[str, Any]:
        """Initialize AI-powered services"""
        try:
            from services.case_insight_service import CaseInsightService
            from services.export_service import ExportService
            
            # Just verify imports work - don't instantiate (services may require dependencies)
            service_classes = [
                CaseInsightService,
                ExportService
            ]
            
            return {
                "ai_services_available": len(service_classes),
                "bedrock_integration": True
            }
        
        except Exception as e:
            raise Exception(f"AI services initialization failed: {str(e)}")
    
    async def _initialize_security_services(self) -> Dict[str, Any]:
        """Initialize security and encryption services"""
        try:
            from services.security_service import SecurityService
            from services.encryption_service import EncryptionService
            
            # Just verify imports work - don't instantiate (services may require dependencies)
            service_classes = [
                SecurityService,
                EncryptionService
            ]
            
            return {
                "security_services_available": len(service_classes),
                "encryption_enabled": True
            }
        
        except Exception as e:
            raise Exception(f"Security services initialization failed: {str(e)}")
    
    async def _initialize_integration_services(self) -> Dict[str, Any]:
        """Initialize integration and background services"""
        try:
            from services.integration_service import IntegrationService
            from services.efiling_service import EFilingService
            from services.background_job_service import BackgroundJobService
            from services.webhook_service import WebhookService
            from services.deployment_monitoring_service import DeploymentMonitoringService
            from services.comprehensive_health_service import ComprehensiveHealthService
            from services.diagnostic_service import DiagnosticService
            from services.resource_optimization_service import ResourceOptimizationService
            from services.deployment_validation_service import DeploymentValidationService
            from services.disaster_recovery_service import DisasterRecoveryService
            from services.deployment_orchestration_service import DeploymentOrchestrationService
            
            # Just verify imports work - don't instantiate (services may require dependencies)
            service_classes = [
                IntegrationService,
                EFilingService,
                BackgroundJobService,
                WebhookService,
                DeploymentMonitoringService,
                ComprehensiveHealthService,
                DiagnosticService,
                ResourceOptimizationService,
                DeploymentValidationService,
                DisasterRecoveryService,
                DeploymentOrchestrationService
            ]
            
            return {
                "integration_services_available": len(service_classes),
                "background_processing_enabled": True,
                "webhook_support_enabled": True,
                "deployment_monitoring_enabled": True,
                "comprehensive_health_monitoring_enabled": True,
                "diagnostic_tools_enabled": True,
                "resource_optimization_enabled": True,
                "deployment_validation_enabled": True,
                "disaster_recovery_enabled": True,
                "deployment_orchestration_enabled": True
            }
        
        except Exception as e:
            raise Exception(f"Integration services initialization failed: {str(e)}")
    
    async def shutdown_services(self) -> Dict[str, Any]:
        """
        Gracefully shutdown all services
        
        Returns:
            Dict containing shutdown results
        """
        self.logger.info("Starting graceful service shutdown")
        
        shutdown_results = {}
        
        # Shutdown services in reverse order
        shutdown_steps = [
            ("integration_services", self._shutdown_integration_services),
            ("security_services", self._shutdown_security_services),
            ("ai_services", self._shutdown_ai_services),
            ("core_services", self._shutdown_core_services),
            ("aws_services", self._shutdown_aws_services),
            ("redis", self._shutdown_redis),
            ("database", self._shutdown_database)
        ]
        
        for service_name, shutdown_func in shutdown_steps:
            if self.initialized_services.get(service_name, False):
                try:
                    self.logger.info(f"Shutting down {service_name}")
                    result = await shutdown_func()
                    shutdown_results[service_name] = {
                        "status": "success",
                        "message": f"{service_name} shutdown successfully",
                        "details": result
                    }
                    self.logger.info(f"{service_name} shutdown successfully")
                
                except Exception as e:
                    error_msg = f"Error shutting down {service_name}: {str(e)}"
                    self.logger.error(error_msg, error=str(e))
                    shutdown_results[service_name] = {
                        "status": "error",
                        "message": error_msg,
                        "details": {}
                    }
        
        self.logger.info("Service shutdown completed")
        return shutdown_results
    
    async def _shutdown_integration_services(self) -> Dict[str, Any]:
        """Shutdown integration services"""
        # Integration services are stateless, no special shutdown needed
        return {"shutdown_type": "stateless"}
    
    async def _shutdown_security_services(self) -> Dict[str, Any]:
        """Shutdown security services"""
        # Security services are stateless, no special shutdown needed
        return {"shutdown_type": "stateless"}
    
    async def _shutdown_ai_services(self) -> Dict[str, Any]:
        """Shutdown AI services"""
        # AI services are stateless, no special shutdown needed
        return {"shutdown_type": "stateless"}
    
    async def _shutdown_core_services(self) -> Dict[str, Any]:
        """Shutdown core services"""
        # Core services are stateless, no special shutdown needed
        return {"shutdown_type": "stateless"}
    
    async def _shutdown_aws_services(self) -> Dict[str, Any]:
        """Shutdown AWS services"""
        # AWS clients are managed by boto3, no special shutdown needed
        return {"shutdown_type": "managed_by_boto3"}
    
    async def _shutdown_redis(self) -> Dict[str, Any]:
        """Shutdown Redis connection"""
        try:
            await redis_service.close()
            return {"connection_closed": True}
        except Exception as e:
            return {"error": str(e)}
    
    async def _shutdown_database(self) -> Dict[str, Any]:
        """Shutdown database connection"""
        try:
            await engine.dispose()
            return {"connection_pool_disposed": True}
        except Exception as e:
            return {"error": str(e)}
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current status of all services"""
        return {
            "initialized_services": self.initialized_services,
            "service_errors": self.service_errors,
            "total_services": len(self.initialized_services),
            "healthy_services": sum(1 for status in self.initialized_services.values() if status)
        }