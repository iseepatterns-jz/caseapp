"""
Background Job Processing Service
Handles asynchronous task processing and job management
Validates Requirements 10.4
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import logging
from dataclasses import dataclass, asdict
import traceback

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class JobPriority(str, Enum):
    """Job priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class JobResult:
    """Job execution result"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    retry_count: int = 0

@dataclass
class BackgroundJob:
    """Background job data structure"""
    job_id: str
    task_name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    status: JobStatus
    priority: JobPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[JobResult] = None
    max_retries: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 300
    metadata: Optional[Dict[str, Any]] = None

class BackgroundJobService:
    """Service for background job processing"""
    
    def __init__(self):
        self.jobs: Dict[str, BackgroundJob] = {}
        self.task_registry: Dict[str, Callable] = {}
        self.workers_running = False
        self.max_concurrent_jobs = 5
        self.running_jobs: Dict[str, asyncio.Task] = {}
        self.job_queue: List[str] = []  # Job IDs in priority order
        
        # Register built-in tasks
        self._register_builtin_tasks()
    
    def _register_builtin_tasks(self):
        """Register built-in background tasks"""
        self.register_task("document_analysis", self._process_document_analysis)
        self.register_task("media_processing", self._process_media_processing)
        self.register_task("forensic_analysis", self._process_forensic_analysis)
        self.register_task("export_generation", self._process_export_generation)
        self.register_task("webhook_delivery", self._process_webhook_delivery)
        self.register_task("email_notification", self._process_email_notification)
        self.register_task("data_cleanup", self._process_data_cleanup)
        self.register_task("backup_creation", self._process_backup_creation)
    
    def register_task(self, task_name: str, task_function: Callable):
        """
        Register a background task function
        
        Args:
            task_name: Unique task identifier
            task_function: Async function to execute
        """
        self.task_registry[task_name] = task_function
        logger.info(f"Registered background task: {task_name}")
    
    async def submit_job(
        self,
        task_name: str,
        args: List[Any] = None,
        kwargs: Dict[str, Any] = None,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        retry_delay_seconds: int = 60,
        timeout_seconds: int = 300,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Submit a background job for processing
        
        Args:
            task_name: Name of registered task
            args: Positional arguments for task
            kwargs: Keyword arguments for task
            priority: Job priority level
            max_retries: Maximum retry attempts
            retry_delay_seconds: Delay between retries
            timeout_seconds: Job timeout
            metadata: Additional job metadata
        
        Returns:
            Job ID for tracking
        """
        if task_name not in self.task_registry:
            raise ValueError(f"Unknown task: {task_name}")
        
        job_id = str(uuid.uuid4())
        
        job = BackgroundJob(
            job_id=job_id,
            task_name=task_name,
            args=args or [],
            kwargs=kwargs or {},
            status=JobStatus.PENDING,
            priority=priority,
            created_at=datetime.utcnow(),
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {}
        )
        
        self.jobs[job_id] = job
        self._add_to_queue(job_id)
        
        logger.info(f"Submitted job {job_id}: {task_name}")
        
        # Start workers if not running
        if not self.workers_running:
            asyncio.create_task(self._start_workers())
        
        return job_id
    
    def _add_to_queue(self, job_id: str):
        """Add job to priority queue"""
        job = self.jobs[job_id]
        
        # Insert based on priority
        priority_order = {
            JobPriority.CRITICAL: 0,
            JobPriority.HIGH: 1,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 3
        }
        
        job_priority = priority_order[job.priority]
        
        # Find insertion point
        insert_index = len(self.job_queue)
        for i, queued_job_id in enumerate(self.job_queue):
            queued_job = self.jobs[queued_job_id]
            queued_priority = priority_order[queued_job.priority]
            
            if job_priority < queued_priority:
                insert_index = i
                break
        
        self.job_queue.insert(insert_index, job_id)
    
    async def get_job_status(self, job_id: str) -> Optional[BackgroundJob]:
        """
        Get current status of a job
        
        Args:
            job_id: Job identifier
        
        Returns:
            Job object or None if not found
        """
        return self.jobs.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or running job
        
        Args:
            job_id: Job identifier
        
        Returns:
            True if cancelled successfully
        """
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status == JobStatus.PENDING:
            # Remove from queue
            if job_id in self.job_queue:
                self.job_queue.remove(job_id)
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            return True
        
        elif job.status == JobStatus.RUNNING:
            # Cancel running task
            if job_id in self.running_jobs:
                self.running_jobs[job_id].cancel()
                del self.running_jobs[job_id]
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            return True
        
        return False
    
    async def retry_job(self, job_id: str) -> bool:
        """
        Retry a failed job
        
        Args:
            job_id: Job identifier
        
        Returns:
            True if retry initiated
        """
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.FAILED:
            return False
        
        if job.result and job.result.retry_count >= job.max_retries:
            return False
        
        # Reset job status
        job.status = JobStatus.PENDING
        job.started_at = None
        job.completed_at = None
        
        # Increment retry count
        if job.result:
            job.result.retry_count += 1
        else:
            job.result = JobResult(success=False, retry_count=1)
        
        # Add back to queue
        self._add_to_queue(job_id)
        
        logger.info(f"Retrying job {job_id} (attempt {job.result.retry_count + 1})")
        return True
    
    async def get_job_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get job processing statistics
        
        Args:
            hours: Time period for statistics
        
        Returns:
            Statistics dictionary
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_jobs = [
            job for job in self.jobs.values()
            if job.created_at >= cutoff_time
        ]
        
        total_jobs = len(recent_jobs)
        status_counts = {}
        task_counts = {}
        priority_counts = {}
        
        total_execution_time = 0
        completed_jobs = 0
        
        for job in recent_jobs:
            # Status counts
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Task counts
            task = job.task_name
            task_counts[task] = task_counts.get(task, 0) + 1
            
            # Priority counts
            priority = job.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # Execution time
            if job.result and job.result.execution_time_seconds:
                total_execution_time += job.result.execution_time_seconds
                completed_jobs += 1
        
        success_rate = 0
        if total_jobs > 0:
            successful_jobs = status_counts.get("completed", 0)
            success_rate = (successful_jobs / total_jobs) * 100
        
        average_execution_time = 0
        if completed_jobs > 0:
            average_execution_time = total_execution_time / completed_jobs
        
        return {
            "period_hours": hours,
            "total_jobs": total_jobs,
            "success_rate_percent": round(success_rate, 2),
            "status_breakdown": status_counts,
            "task_breakdown": task_counts,
            "priority_breakdown": priority_counts,
            "average_execution_time_seconds": round(average_execution_time, 2),
            "queue_length": len(self.job_queue),
            "running_jobs": len(self.running_jobs)
        }
    
    async def _start_workers(self):
        """Start background job workers"""
        if self.workers_running:
            return
        
        self.workers_running = True
        logger.info("Starting background job workers")
        
        # Start worker tasks
        worker_tasks = []
        for i in range(self.max_concurrent_jobs):
            task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            worker_tasks.append(task)
        
        try:
            await asyncio.gather(*worker_tasks)
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
        finally:
            self.workers_running = False
    
    async def _worker_loop(self, worker_name: str):
        """Main worker loop"""
        logger.info(f"Started worker: {worker_name}")
        
        while self.workers_running:
            try:
                # Get next job from queue
                job_id = await self._get_next_job()
                
                if job_id:
                    await self._execute_job(job_id, worker_name)
                else:
                    # No jobs available, wait a bit
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _get_next_job(self) -> Optional[str]:
        """Get next job from queue"""
        if not self.job_queue:
            return None
        
        # Find first pending job
        for i, job_id in enumerate(self.job_queue):
            job = self.jobs.get(job_id)
            if job and job.status == JobStatus.PENDING:
                # Remove from queue
                self.job_queue.pop(i)
                return job_id
        
        return None
    
    async def _execute_job(self, job_id: str, worker_name: str):
        """Execute a single job"""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        logger.info(f"Worker {worker_name} executing job {job_id}: {job.task_name}")
        
        # Update job status
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        
        start_time = datetime.utcnow()
        
        try:
            # Get task function
            task_function = self.task_registry[job.task_name]
            
            # Create execution task with timeout
            execution_task = asyncio.create_task(
                task_function(*job.args, **job.kwargs)
            )
            self.running_jobs[job_id] = execution_task
            
            # Wait for completion with timeout
            result = await asyncio.wait_for(
                execution_task, 
                timeout=job.timeout_seconds
            )
            
            # Job completed successfully
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = JobResult(
                success=True,
                result=result,
                execution_time_seconds=execution_time,
                retry_count=job.result.retry_count if job.result else 0
            )
            
            logger.info(f"Job {job_id} completed successfully in {execution_time:.2f}s")
            
        except asyncio.TimeoutError:
            # Job timed out
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.result = JobResult(
                success=False,
                error=f"Job timed out after {job.timeout_seconds} seconds",
                retry_count=job.result.retry_count if job.result else 0
            )
            
            logger.error(f"Job {job_id} timed out")
            
        except asyncio.CancelledError:
            # Job was cancelled
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            
            logger.info(f"Job {job_id} was cancelled")
            
        except Exception as e:
            # Job failed with error
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_message = f"{str(e)}\n{traceback.format_exc()}"
            
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.result = JobResult(
                success=False,
                error=error_message,
                execution_time_seconds=execution_time,
                retry_count=job.result.retry_count if job.result else 0
            )
            
            logger.error(f"Job {job_id} failed: {str(e)}")
            
            # Schedule retry if applicable
            if job.result.retry_count < job.max_retries:
                await asyncio.sleep(job.retry_delay_seconds)
                await self.retry_job(job_id)
        
        finally:
            # Clean up running job reference
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]
    
    # Built-in task implementations
    async def _process_document_analysis(self, document_id: str, analysis_type: str = "full"):
        """Process document analysis task"""
        logger.info(f"Processing document analysis: {document_id} ({analysis_type})")
        
        # Simulate document analysis processing
        await asyncio.sleep(2)  # Simulate processing time
        
        return {
            "document_id": document_id,
            "analysis_type": analysis_type,
            "status": "completed",
            "extracted_text_length": 1500,
            "entities_found": 25,
            "processing_time_ms": 2000
        }
    
    async def _process_media_processing(self, media_id: str, operations: List[str]):
        """Process media processing task"""
        logger.info(f"Processing media: {media_id} with operations: {operations}")
        
        # Simulate media processing
        processing_time = len(operations) * 1.5
        await asyncio.sleep(processing_time)
        
        return {
            "media_id": media_id,
            "operations_completed": operations,
            "status": "completed",
            "output_files": [f"{media_id}_{op}.processed" for op in operations],
            "processing_time_ms": int(processing_time * 1000)
        }
    
    async def _process_forensic_analysis(self, source_id: str, analysis_depth: str = "standard"):
        """Process forensic analysis task"""
        logger.info(f"Processing forensic analysis: {source_id} ({analysis_depth})")
        
        # Simulate forensic analysis
        processing_time = 5 if analysis_depth == "deep" else 3
        await asyncio.sleep(processing_time)
        
        return {
            "source_id": source_id,
            "analysis_depth": analysis_depth,
            "status": "completed",
            "messages_analyzed": 1250,
            "patterns_detected": 8,
            "anomalies_found": 3,
            "processing_time_ms": int(processing_time * 1000)
        }
    
    async def _process_export_generation(self, export_type: str, data_ids: List[str], format: str = "pdf"):
        """Process export generation task"""
        logger.info(f"Generating {format} export of type {export_type} for {len(data_ids)} items")
        
        # Simulate export generation
        processing_time = len(data_ids) * 0.5
        await asyncio.sleep(processing_time)
        
        export_id = str(uuid.uuid4())
        
        return {
            "export_id": export_id,
            "export_type": export_type,
            "format": format,
            "items_exported": len(data_ids),
            "file_size_mb": len(data_ids) * 2.5,
            "download_url": f"/api/v1/exports/{export_id}/download",
            "status": "completed",
            "processing_time_ms": int(processing_time * 1000)
        }
    
    async def _process_webhook_delivery(self, webhook_url: str, payload: Dict[str, Any], retry_count: int = 0):
        """Process webhook delivery task"""
        logger.info(f"Delivering webhook to {webhook_url}")
        
        # Simulate webhook delivery
        await asyncio.sleep(0.5)
        
        # Simulate occasional failures for testing
        if "fail" in webhook_url and retry_count == 0:
            raise Exception("Webhook delivery failed - network error")
        
        return {
            "webhook_url": webhook_url,
            "status": "delivered",
            "response_code": 200,
            "payload_size": len(json.dumps(payload)),
            "delivery_time_ms": 500,
            "retry_count": retry_count
        }
    
    async def _process_email_notification(self, recipient: str, subject: str, template: str, data: Dict[str, Any]):
        """Process email notification task"""
        logger.info(f"Sending email to {recipient}: {subject}")
        
        # Simulate email sending
        await asyncio.sleep(1)
        
        return {
            "recipient": recipient,
            "subject": subject,
            "template": template,
            "status": "sent",
            "message_id": str(uuid.uuid4()),
            "delivery_time_ms": 1000
        }
    
    async def _process_data_cleanup(self, cleanup_type: str, older_than_days: int):
        """Process data cleanup task"""
        logger.info(f"Running {cleanup_type} cleanup for data older than {older_than_days} days")
        
        # Simulate cleanup processing
        await asyncio.sleep(3)
        
        return {
            "cleanup_type": cleanup_type,
            "older_than_days": older_than_days,
            "status": "completed",
            "items_cleaned": 150,
            "space_freed_mb": 2500,
            "processing_time_ms": 3000
        }
    
    async def _process_backup_creation(self, backup_type: str, data_sources: List[str]):
        """Process backup creation task"""
        logger.info(f"Creating {backup_type} backup for {len(data_sources)} data sources")
        
        # Simulate backup creation
        processing_time = len(data_sources) * 2
        await asyncio.sleep(processing_time)
        
        backup_id = str(uuid.uuid4())
        
        return {
            "backup_id": backup_id,
            "backup_type": backup_type,
            "data_sources": data_sources,
            "status": "completed",
            "backup_size_gb": len(data_sources) * 5.2,
            "backup_location": f"/backups/{backup_id}.tar.gz",
            "processing_time_ms": int(processing_time * 1000)
        }