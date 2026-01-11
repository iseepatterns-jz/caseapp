"""
Background Jobs API endpoints
Handles background job management and monitoring
Validates Requirements 10.4, 10.6
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime

from services.background_job_service import BackgroundJobService, JobPriority
from services.webhook_service import WebhookService, WebhookEvent
from schemas.background_jobs import (
    JobSubmissionRequest, JobSubmissionResponse,
    JobStatusResponse, JobStatisticsResponse,
    WebhookEndpointRequest, WebhookEndpointResponse,
    WebhookDeliveryResponse, WebhookTestResponse,
    WebhookStatisticsResponse
)
from core.auth import get_current_user
from models.user import User

router = APIRouter()

# Global service instances (in production, these would be dependency injected)
background_job_service = BackgroundJobService()
webhook_service = WebhookService(background_job_service)

@router.post("/submit", response_model=JobSubmissionResponse)
async def submit_background_job(
    request: JobSubmissionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Submit a background job for processing
    
    Args:
        request: Job submission request
        current_user: Authenticated user
    
    Returns:
        Job submission response with job ID
    """
    try:
        job_id = await background_job_service.submit_job(
            task_name=request.task_name,
            args=request.args,
            kwargs=request.kwargs,
            priority=request.priority,
            max_retries=request.max_retries,
            retry_delay_seconds=request.retry_delay_seconds,
            timeout_seconds=request.timeout_seconds,
            metadata=request.metadata
        )
        
        return JobSubmissionResponse(
            job_id=job_id,
            status="submitted",
            message=f"Job {job_id} submitted successfully"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {str(e)}")

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get current status of a background job
    
    Args:
        job_id: Job identifier
        current_user: Authenticated user
    
    Returns:
        Current job status and details
    """
    job = await background_job_service.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        task_name=job.task_name,
        status=job.status,
        priority=job.priority,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        result=job.result,
        max_retries=job.max_retries,
        metadata=job.metadata
    )

@router.post("/cancel/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a pending or running job
    
    Args:
        job_id: Job identifier
        current_user: Authenticated user
    
    Returns:
        Cancellation confirmation
    """
    success = await background_job_service.cancel_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel job - job not found or not in cancellable state"
        )
    
    return {"message": f"Job {job_id} cancelled successfully", "job_id": job_id}

@router.post("/retry/{job_id}")
async def retry_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Retry a failed job
    
    Args:
        job_id: Job identifier
        current_user: Authenticated user
    
    Returns:
        Retry confirmation
    """
    success = await background_job_service.retry_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot retry job - job not found, not failed, or max retries exceeded"
        )
    
    return {"message": f"Job {job_id} retry initiated", "job_id": job_id}

@router.get("/statistics", response_model=JobStatisticsResponse)
async def get_job_statistics(
    hours: int = 24,
    current_user: User = Depends(get_current_user)
):
    """
    Get background job processing statistics
    
    Args:
        hours: Time period for statistics
        current_user: Authenticated user
    
    Returns:
        Job processing statistics
    """
    stats = await background_job_service.get_job_statistics(hours=hours)
    
    return JobStatisticsResponse(
        period_hours=stats["period_hours"],
        total_jobs=stats["total_jobs"],
        success_rate_percent=stats["success_rate_percent"],
        status_breakdown=stats["status_breakdown"],
        task_breakdown=stats["task_breakdown"],
        priority_breakdown=stats["priority_breakdown"],
        average_execution_time_seconds=stats["average_execution_time_seconds"],
        queue_length=stats["queue_length"],
        running_jobs=stats["running_jobs"]
    )

@router.get("/tasks")
async def get_available_tasks(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of available background tasks
    
    Args:
        current_user: Authenticated user
    
    Returns:
        List of available tasks with descriptions
    """
    tasks = [
        {
            "name": "document_analysis",
            "description": "Analyze uploaded documents with AI",
            "parameters": ["document_id", "analysis_type"]
        },
        {
            "name": "media_processing",
            "description": "Process media files (thumbnails, transcription)",
            "parameters": ["media_id", "operations"]
        },
        {
            "name": "forensic_analysis",
            "description": "Analyze forensic communication data",
            "parameters": ["source_id", "analysis_depth"]
        },
        {
            "name": "export_generation",
            "description": "Generate case exports and reports",
            "parameters": ["export_type", "data_ids", "format"]
        },
        {
            "name": "webhook_delivery",
            "description": "Deliver webhook notifications",
            "parameters": ["webhook_url", "payload", "retry_count"]
        },
        {
            "name": "email_notification",
            "description": "Send email notifications",
            "parameters": ["recipient", "subject", "template", "data"]
        },
        {
            "name": "data_cleanup",
            "description": "Clean up old data and temporary files",
            "parameters": ["cleanup_type", "older_than_days"]
        },
        {
            "name": "backup_creation",
            "description": "Create system backups",
            "parameters": ["backup_type", "data_sources"]
        }
    ]
    
    return {"tasks": tasks}

# Webhook endpoints
@router.post("/webhooks", response_model=WebhookEndpointResponse)
async def create_webhook_endpoint(
    request: WebhookEndpointRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new webhook endpoint
    
    Args:
        request: Webhook endpoint configuration
        current_user: Authenticated user
    
    Returns:
        Created webhook endpoint
    """
    try:
        endpoint = await webhook_service.create_endpoint(
            name=request.name,
            url=request.url,
            events=request.events,
            secret=request.secret,
            max_retries=request.max_retries,
            retry_delay_seconds=request.retry_delay_seconds,
            timeout_seconds=request.timeout_seconds,
            headers=request.headers
        )
        
        return WebhookEndpointResponse(
            id=endpoint.id,
            name=endpoint.name,
            url=endpoint.url,
            events=endpoint.events,
            active=endpoint.active,
            max_retries=endpoint.max_retries,
            retry_delay_seconds=endpoint.retry_delay_seconds,
            timeout_seconds=endpoint.timeout_seconds,
            headers=endpoint.headers,
            created_at=endpoint.created_at,
            updated_at=endpoint.updated_at
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/webhooks", response_model=List[WebhookEndpointResponse])
async def list_webhook_endpoints(
    active_only: bool = False,
    current_user: User = Depends(get_current_user)
):
    """
    List webhook endpoints
    
    Args:
        active_only: Only return active endpoints
        current_user: Authenticated user
    
    Returns:
        List of webhook endpoints
    """
    endpoints = await webhook_service.list_endpoints(active_only=active_only)
    
    return [
        WebhookEndpointResponse(
            id=ep.id,
            name=ep.name,
            url=ep.url,
            events=ep.events,
            active=ep.active,
            max_retries=ep.max_retries,
            retry_delay_seconds=ep.retry_delay_seconds,
            timeout_seconds=ep.timeout_seconds,
            headers=ep.headers,
            created_at=ep.created_at,
            updated_at=ep.updated_at
        )
        for ep in endpoints
    ]

@router.get("/webhooks/{endpoint_id}", response_model=WebhookEndpointResponse)
async def get_webhook_endpoint(
    endpoint_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get webhook endpoint by ID
    
    Args:
        endpoint_id: Endpoint identifier
        current_user: Authenticated user
    
    Returns:
        Webhook endpoint details
    """
    endpoint = await webhook_service.get_endpoint(endpoint_id)
    
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    
    return WebhookEndpointResponse(
        id=endpoint.id,
        name=endpoint.name,
        url=endpoint.url,
        events=endpoint.events,
        active=endpoint.active,
        max_retries=endpoint.max_retries,
        retry_delay_seconds=endpoint.retry_delay_seconds,
        timeout_seconds=endpoint.timeout_seconds,
        headers=endpoint.headers,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at
    )

@router.put("/webhooks/{endpoint_id}", response_model=WebhookEndpointResponse)
async def update_webhook_endpoint(
    endpoint_id: str,
    request: WebhookEndpointRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update webhook endpoint
    
    Args:
        endpoint_id: Endpoint identifier
        request: Updated endpoint configuration
        current_user: Authenticated user
    
    Returns:
        Updated webhook endpoint
    """
    endpoint = await webhook_service.update_endpoint(
        endpoint_id=endpoint_id,
        name=request.name,
        url=request.url,
        events=request.events,
        secret=request.secret,
        active=request.active,
        max_retries=request.max_retries,
        retry_delay_seconds=request.retry_delay_seconds,
        timeout_seconds=request.timeout_seconds,
        headers=request.headers
    )
    
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    
    return WebhookEndpointResponse(
        id=endpoint.id,
        name=endpoint.name,
        url=endpoint.url,
        events=endpoint.events,
        active=endpoint.active,
        max_retries=endpoint.max_retries,
        retry_delay_seconds=endpoint.retry_delay_seconds,
        timeout_seconds=endpoint.timeout_seconds,
        headers=endpoint.headers,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at
    )

@router.delete("/webhooks/{endpoint_id}")
async def delete_webhook_endpoint(
    endpoint_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete webhook endpoint
    
    Args:
        endpoint_id: Endpoint identifier
        current_user: Authenticated user
    
    Returns:
        Deletion confirmation
    """
    success = await webhook_service.delete_endpoint(endpoint_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    
    return {"message": f"Webhook endpoint {endpoint_id} deleted successfully"}

@router.post("/webhooks/{endpoint_id}/test", response_model=WebhookTestResponse)
async def test_webhook_endpoint(
    endpoint_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Test webhook endpoint with a ping
    
    Args:
        endpoint_id: Endpoint identifier
        current_user: Authenticated user
    
    Returns:
        Test result
    """
    result = await webhook_service.test_endpoint(endpoint_id)
    
    return WebhookTestResponse(
        success=result["success"],
        delivery_id=result.get("delivery_id"),
        response_code=result.get("response_code"),
        response_body=result.get("response_body"),
        error_message=result.get("error_message"),
        delivered_at=result.get("delivered_at")
    )

@router.get("/webhooks/{endpoint_id}/deliveries", response_model=List[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    endpoint_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """
    List webhook deliveries for an endpoint
    
    Args:
        endpoint_id: Endpoint identifier
        limit: Maximum results
        offset: Results offset
        current_user: Authenticated user
    
    Returns:
        List of webhook deliveries
    """
    deliveries = await webhook_service.list_deliveries(
        endpoint_id=endpoint_id,
        limit=limit,
        offset=offset
    )
    
    return [
        WebhookDeliveryResponse(
            id=d.id,
            endpoint_id=d.endpoint_id,
            event_type=d.event_type,
            status=d.status,
            created_at=d.created_at,
            delivered_at=d.delivered_at,
            response_code=d.response_code,
            error_message=d.error_message,
            retry_count=d.retry_count
        )
        for d in deliveries
    ]

@router.post("/webhooks/send")
async def send_webhook_notification(
    event_type: WebhookEvent,
    payload: Dict[str, Any],
    endpoint_ids: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Send webhook notification manually
    
    Args:
        event_type: Type of event
        payload: Event payload
        endpoint_ids: Specific endpoints (None for all subscribed)
        current_user: Authenticated user
    
    Returns:
        Delivery confirmation
    """
    delivery_ids = await webhook_service.send_webhook(
        event_type=event_type,
        payload=payload,
        endpoint_ids=endpoint_ids
    )
    
    return {
        "message": f"Webhook notifications sent",
        "event_type": event_type.value,
        "delivery_ids": delivery_ids,
        "delivery_count": len(delivery_ids)
    }

@router.get("/webhooks/statistics", response_model=WebhookStatisticsResponse)
async def get_webhook_statistics(
    endpoint_id: Optional[str] = None,
    hours: int = 24,
    current_user: User = Depends(get_current_user)
):
    """
    Get webhook delivery statistics
    
    Args:
        endpoint_id: Filter by endpoint
        hours: Time period for statistics
        current_user: Authenticated user
    
    Returns:
        Webhook delivery statistics
    """
    stats = await webhook_service.get_delivery_statistics(
        endpoint_id=endpoint_id,
        hours=hours
    )
    
    return WebhookStatisticsResponse(
        period_hours=stats["period_hours"],
        total_deliveries=stats["total_deliveries"],
        success_rate_percent=stats["success_rate_percent"],
        status_breakdown=stats["status_breakdown"],
        event_breakdown=stats["event_breakdown"],
        endpoint_breakdown=stats["endpoint_breakdown"],
        average_retries=stats["average_retries"],
        total_endpoints=stats["total_endpoints"],
        active_endpoints=stats["active_endpoints"]
    )