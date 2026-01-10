"""
Minimal integration tests for Court Case Management System
Tests only core services without complex dependencies
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Import only core services that work
from services.background_job_service import BackgroundJobService, JobPriority
from services.webhook_service import WebhookService, WebhookEvent
from services.security_service import SecurityService

class TestMinimalIntegration:
    """Test minimal system integration"""
    
    def test_background_job_service_basic(self):
        """Test background job service basic functionality"""
        async def run_test():
            job_service = BackgroundJobService()
            
            # Test job submission with correct parameters
            job_id = await job_service.submit_job(
                task_name="document_analysis",  # Use registered task
                args=["doc123", "full"],
                kwargs={"analysis_type": "full"}
            )
            
            # Verify job creation
            assert job_id is not None
            assert isinstance(job_id, str)
            
            # Test job status retrieval
            job = await job_service.get_job_status(job_id)
            assert job is not None
            assert job.task_name == "document_analysis"
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_webhook_service_basic(self):
        """Test webhook service basic functionality"""
        async def run_test():
            webhook_service = WebhookService()
            
            # Test endpoint creation with correct parameters
            endpoint = await webhook_service.create_endpoint(
                name="test_endpoint",
                url="https://example.com/webhook",
                events=[WebhookEvent.CASE_CREATED]
            )
            
            # Verify endpoint creation
            assert endpoint is not None
            assert endpoint.name == "test_endpoint"
            assert endpoint.url == "https://example.com/webhook"
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_security_service_basic(self):
        """Test security service basic functionality"""
        async def run_test():
            security_service = SecurityService()
            
            # Test password validation - it's an async method
            result = await security_service.validate_password_strength("TestPassword123!")
            
            # Verify password validation
            assert result is not None
            assert "is_valid" in result
            assert "strength_score" in result
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_service_instantiation(self):
        """Test that core services can be instantiated"""
        services = [
            BackgroundJobService,
            WebhookService,
            SecurityService
        ]
        
        for service_class in services:
            try:
                service = service_class()
                assert service is not None
            except Exception as e:
                pytest.fail(f"Failed to instantiate {service_class.__name__}: {str(e)}")
    
    def test_background_job_and_webhook_integration(self):
        """Test background job and webhook services work together"""
        async def run_test():
            job_service = BackgroundJobService()
            webhook_service = WebhookService()
            
            # Create webhook endpoint - use correct event name
            endpoint = await webhook_service.create_endpoint(
                name="job_notifications",
                url="https://example.com/job-webhook",
                events=[WebhookEvent.CASE_CREATED]  # Use available event
            )
            
            # Submit job with registered task
            job_id = await job_service.submit_job(
                task_name="document_analysis",
                args=["test_doc", "full"]
            )
            
            # Send webhook notification - use available event
            delivery_ids = await webhook_service.send_webhook(
                event_type=WebhookEvent.CASE_CREATED,  # Use available event
                payload={"job_id": job_id, "status": "completed"}
            )
            
            # Verify integration
            assert endpoint is not None
            assert job_id is not None
            assert len(delivery_ids) > 0
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_job_statistics(self):
        """Test job statistics functionality"""
        async def run_test():
            job_service = BackgroundJobService()
            
            # Submit multiple jobs with registered tasks
            job_ids = []
            for i in range(3):
                job_id = await job_service.submit_job(
                    task_name="document_analysis",
                    args=[f"doc_{i}", "full"]
                )
                job_ids.append(job_id)
            
            # Get statistics
            stats = await job_service.get_job_statistics(hours=24)
            
            # Verify statistics
            assert stats is not None
            assert "total_jobs" in stats
            assert stats["total_jobs"] >= 3
            assert "status_breakdown" in stats
            assert "task_breakdown" in stats
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_webhook_delivery_statistics(self):
        """Test webhook delivery statistics"""
        async def run_test():
            webhook_service = WebhookService()
            
            # Create endpoint
            endpoint = await webhook_service.create_endpoint(
                name="stats_test",
                url="https://example.com/stats-webhook",
                events=[WebhookEvent.CASE_CREATED]
            )
            
            # Send multiple webhooks
            for i in range(2):
                await webhook_service.send_webhook(
                    event_type=WebhookEvent.CASE_CREATED,
                    payload={"test": f"payload_{i}"}
                )
            
            # Get statistics
            stats = await webhook_service.get_delivery_statistics(hours=24)
            
            # Verify statistics
            assert stats is not None
            assert "total_deliveries" in stats
            assert stats["total_deliveries"] >= 2
            assert "status_breakdown" in stats
            assert "event_breakdown" in stats
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True