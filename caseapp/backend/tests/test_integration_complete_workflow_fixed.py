"""
Complete workflow integration tests for Court Case Management System
Tests end-to-end workflows across multiple services
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Import services for integration testing
from services.background_job_service import BackgroundJobService, JobPriority
from services.webhook_service import WebhookService, WebhookEvent
from services.security_service import SecurityService

class TestCompleteWorkflowIntegration:
    """Test complete system workflows"""
    
    def test_case_creation_workflow(self):
        """Test complete case creation workflow with notifications"""
        async def run_test():
            # Initialize services
            job_service = BackgroundJobService()
            webhook_service = WebhookService()
            security_service = SecurityService()
            
            # Step 1: Validate user permissions
            has_permission = await security_service.validate_data_access_permissions(
                user_id="user123",
                user_roles=["attorney"],
                resource_type="case",
                resource_id="new_case",
                action="write"
            )
            assert has_permission is True
            
            # Step 2: Create webhook endpoint for case notifications
            endpoint = await webhook_service.create_endpoint(
                name="case_notifications",
                url="https://example.com/case-webhook",
                events=[WebhookEvent.CASE_CREATED, WebhookEvent.CASE_UPDATED]
            )
            assert endpoint is not None
            
            # Step 3: Submit background job for case processing
            job_id = await job_service.submit_job(
                task_name="document_analysis",
                args=["case_doc_123", "full"],
                priority=JobPriority.HIGH,
                metadata={"case_id": "case123", "user_id": "user123"}
            )
            assert job_id is not None
            
            # Step 4: Send webhook notification for case creation
            delivery_ids = await webhook_service.send_webhook(
                event_type=WebhookEvent.CASE_CREATED,
                payload={
                    "case_id": "case123",
                    "user_id": "user123",
                    "job_id": job_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            assert len(delivery_ids) > 0
            
            # Step 5: Verify job status
            job = await job_service.get_job_status(job_id)
            assert job is not None
            assert job.metadata["case_id"] == "case123"
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_security_workflow(self):
        """Test security workflow with MFA and session management"""
        async def run_test():
            security_service = SecurityService()
            
            # Step 1: Validate password strength
            password_result = await security_service.validate_password_strength("SecurePass123!")
            assert password_result["is_valid"] is True
            assert password_result["strength_score"] > 80
            
            # Step 2: Check account lockout status
            is_locked = await security_service.check_account_lockout("user123")
            assert is_locked is False
            
            # Step 3: Set up MFA for user
            mfa_setup = await security_service.setup_mfa_for_user("user123", "user@example.com")
            assert "mfa_secret" in mfa_setup
            assert "backup_codes" in mfa_setup
            
            # Step 4: Create secure session
            session = await security_service.create_secure_session(
                user_id="user123",
                user_roles=["attorney"],
                mfa_verified=True
            )
            assert "access_token" in session
            assert session["mfa_verified"] is True
            
            # Step 5: Generate security report
            report = await security_service.generate_security_report(days=7)
            assert "authentication_metrics" in report
            assert "compliance_status" in report
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_background_job_workflow(self):
        """Test background job processing workflow"""
        async def run_test():
            job_service = BackgroundJobService()
            
            # Step 1: Submit multiple jobs with different priorities
            job_ids = []
            
            # High priority job
            high_job = await job_service.submit_job(
                task_name="forensic_analysis",
                args=["source123", "deep"],
                priority=JobPriority.HIGH
            )
            job_ids.append(high_job)
            
            # Normal priority job
            normal_job = await job_service.submit_job(
                task_name="media_processing",
                args=["media456", ["thumbnail", "waveform"]],
                priority=JobPriority.NORMAL
            )
            job_ids.append(normal_job)
            
            # Low priority job
            low_job = await job_service.submit_job(
                task_name="export_generation",
                args=["timeline", ["doc1", "doc2"], "pdf"],
                priority=JobPriority.LOW
            )
            job_ids.append(low_job)
            
            # Step 2: Verify all jobs were created
            for job_id in job_ids:
                job = await job_service.get_job_status(job_id)
                assert job is not None
                assert job.status.value in ["pending", "running"]
            
            # Step 3: Test job cancellation
            cancelled = await job_service.cancel_job(low_job)
            assert cancelled is True
            
            # Step 4: Get job statistics
            stats = await job_service.get_job_statistics(hours=1)
            assert stats["total_jobs"] >= 3
            assert "priority_breakdown" in stats
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_webhook_delivery_workflow(self):
        """Test webhook delivery and management workflow"""
        async def run_test():
            webhook_service = WebhookService()
            
            # Step 1: Create multiple webhook endpoints
            endpoints = []
            
            # Case management endpoint
            case_endpoint = await webhook_service.create_endpoint(
                name="case_management",
                url="https://example.com/case-webhook",
                events=[WebhookEvent.CASE_CREATED, WebhookEvent.CASE_UPDATED],
                secret="secret123"
            )
            endpoints.append(case_endpoint)
            
            # Document processing endpoint
            doc_endpoint = await webhook_service.create_endpoint(
                name="document_processing",
                url="https://example.com/doc-webhook",
                events=[WebhookEvent.DOCUMENT_UPLOADED, WebhookEvent.DOCUMENT_ANALYZED]
            )
            endpoints.append(doc_endpoint)
            
            # Step 2: Send webhooks for different events
            delivery_ids = []
            
            # Case created event
            case_deliveries = await webhook_service.send_webhook(
                event_type=WebhookEvent.CASE_CREATED,
                payload={"case_id": "case123", "title": "Test Case"}
            )
            delivery_ids.extend(case_deliveries)
            
            # Document uploaded event
            doc_deliveries = await webhook_service.send_webhook(
                event_type=WebhookEvent.DOCUMENT_UPLOADED,
                payload={"document_id": "doc456", "filename": "evidence.pdf"}
            )
            delivery_ids.extend(doc_deliveries)
            
            # Step 3: Verify deliveries were created
            assert len(delivery_ids) >= 2
            
            for delivery_id in delivery_ids:
                delivery = await webhook_service.get_delivery(delivery_id)
                assert delivery is not None
                assert delivery.status.value in ["pending", "delivered", "failed"]
            
            # Step 4: Get delivery statistics
            stats = await webhook_service.get_delivery_statistics(hours=1)
            assert stats["total_deliveries"] >= 2
            assert "event_breakdown" in stats
            
            # Step 5: Test endpoint management
            updated_endpoint = await webhook_service.update_endpoint(
                endpoint_id=case_endpoint.id,
                name="updated_case_management",
                active=False
            )
            assert updated_endpoint.name == "updated_case_management"
            assert updated_endpoint.active is False
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_cross_service_integration(self):
        """Test integration between multiple services"""
        async def run_test():
            job_service = BackgroundJobService()
            webhook_service = WebhookService()
            security_service = SecurityService()
            
            # Step 1: Security validation
            has_permission = await security_service.validate_data_access_permissions(
                user_id="user123",
                user_roles=["attorney"],
                resource_type="forensic",
                resource_id="source123",
                action="read"
            )
            assert has_permission is True
            
            # Step 2: Create webhook for job completion notifications
            endpoint = await webhook_service.create_endpoint(
                name="job_completion",
                url="https://example.com/job-complete",
                events=[WebhookEvent.FORENSIC_ANALYSIS_COMPLETED]
            )
            
            # Step 3: Submit forensic analysis job
            job_id = await job_service.submit_job(
                task_name="forensic_analysis",
                args=["source123", "standard"],
                metadata={
                    "user_id": "user123",
                    "webhook_endpoint": endpoint.id
                }
            )
            
            # Step 4: Simulate job completion notification
            delivery_ids = await webhook_service.send_webhook(
                event_type=WebhookEvent.FORENSIC_ANALYSIS_COMPLETED,
                payload={
                    "job_id": job_id,
                    "user_id": "user123",
                    "source_id": "source123",
                    "results": {
                        "messages_analyzed": 1250,
                        "patterns_detected": 8,
                        "anomalies_found": 3
                    }
                }
            )
            
            # Step 5: Verify cross-service data flow
            job = await job_service.get_job_status(job_id)
            assert job.metadata["webhook_endpoint"] == endpoint.id
            
            assert len(delivery_ids) > 0
            delivery = await webhook_service.get_delivery(delivery_ids[0])
            assert delivery.payload["data"]["job_id"] == job_id
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True
    
    def test_error_handling_workflow(self):
        """Test error handling and recovery mechanisms"""
        async def run_test():
            job_service = BackgroundJobService()
            webhook_service = WebhookService()
            security_service = SecurityService()
            
            # Step 1: Test permission denial
            has_permission = await security_service.validate_data_access_permissions(
                user_id="user123",
                user_roles=["staff"],  # Staff can't delete forensic data
                resource_type="forensic",
                resource_id="source123",
                action="delete"
            )
            assert has_permission is False
            
            # Step 2: Test account lockout simulation
            # Simulate multiple failed login attempts (need 5 attempts based on config)
            for _ in range(5):
                is_locked = await security_service.record_failed_login("user456")
            
            # Should be locked after max attempts
            assert is_locked is True
            
            # Verify lockout status
            is_locked = await security_service.check_account_lockout("user456")
            assert is_locked is True
            
            # Step 3: Test job cancellation
            job_id = await job_service.submit_job(
                task_name="backup_creation",
                args=["full", ["database", "files"]],
                priority=JobPriority.LOW
            )
            
            cancelled = await job_service.cancel_job(job_id)
            assert cancelled is True
            
            job = await job_service.get_job_status(job_id)
            assert job.status.value == "cancelled"
            
            # Step 4: Test webhook endpoint deactivation
            endpoint = await webhook_service.create_endpoint(
                name="test_endpoint",
                url="https://example.com/test",
                events=[WebhookEvent.CASE_CREATED]
            )
            
            # Deactivate endpoint
            updated = await webhook_service.update_endpoint(
                endpoint_id=endpoint.id,
                active=False
            )
            assert updated.active is False
            
            # Webhook should not be delivered to inactive endpoint
            delivery_ids = await webhook_service.send_webhook(
                event_type=WebhookEvent.CASE_CREATED,
                payload={"test": "data"}
            )
            assert len(delivery_ids) == 0  # No deliveries to inactive endpoints
            
            return True
        
        result = asyncio.run(run_test())
        assert result is True