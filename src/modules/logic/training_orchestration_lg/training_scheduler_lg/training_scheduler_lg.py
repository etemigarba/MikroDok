"""
Module: training_scheduler_lg
Description: Schedules and queues training jobs with priority management
Phase: 4
Location: /src/modules/logic/training_orchestration_lg/training_scheduler_lg/
"""

# Standard library imports
import asyncio
import heapq
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import sqlite3

# Local imports
from ..base_interfaces import (
    ITrainingScheduler, TrainingJob, TrainingPriority, SchedulerStatus,
    TrainingConfig
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier
from src.modules.logic.resource_monitor_lg import HardwareMonitor


class JobQueue:
    """Priority queue for training jobs."""
    
    def __init__(self):
        """Initialize job queue."""
        self._heap: List[Tuple[int, datetime, TrainingJob]] = []
        self._job_map: Dict[str, TrainingJob] = {}
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
    
    def add_job(self, job: TrainingJob) -> None:
        """
        Add job to queue.
        
        Args:
            job: Training job to add
        """
        with self._lock:
            # Use negative priority for max-heap behavior (higher priority first)
            priority_value = -job.priority.value
            created_time = job.created_at
            
            heapq.heappush(self._heap, (priority_value, created_time, job))
            self._job_map[job.job_id] = job
            
            self._logger.debug(f"Added job {job.job_id} to queue with priority {job.priority.value}")
    
    def get_next_job(self) -> Optional[TrainingJob]:
        """
        Get next job from queue.
        
        Returns:
            Next job or None if queue is empty
        """
        with self._lock:
            while self._heap:
                priority_value, created_time, job = heapq.heappop(self._heap)
                
                # Check if job is still valid (not cancelled)
                if job.job_id in self._job_map:
                    del self._job_map[job.job_id]
                    return job
            
            return None
    
    def remove_job(self, job_id: str) -> bool:
        """
        Remove job from queue.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was removed
        """
        with self._lock:
            if job_id in self._job_map:
                del self._job_map[job_id]
                self._logger.debug(f"Removed job {job_id} from queue")
                return True
            return False
    
    def get_job(self, job_id: str) -> Optional[TrainingJob]:
        """
        Get job by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            TrainingJob or None if not found
        """
        with self._lock:
            return self._job_map.get(job_id)
    
    def list_jobs(self) -> List[TrainingJob]:
        """
        List all jobs in queue.
        
        Returns:
            List of jobs sorted by priority
        """
        with self._lock:
            return list(self._job_map.values())
    
    def size(self) -> int:
        """Get queue size."""
        with self._lock:
            return len(self._job_map)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        with self._lock:
            return len(self._job_map) == 0


class ResourceEstimator:
    """Estimates resource requirements and execution time for jobs."""
    
    def __init__(self):
        """Initialize resource estimator."""
        self._logger = get_logger(__name__)
        self._historical_data: Dict[str, List[Dict[str, Any]]] = {}
    
    def estimate_duration(self, job: TrainingJob) -> timedelta:
        """
        Estimate job execution duration.
        
        Args:
            job: Training job to estimate
            
        Returns:
            Estimated duration
        """
        try:
            # Base estimation factors
            base_time_per_epoch = 60  # seconds
            
            # Get configuration parameters
            epochs = job.config.max_epochs
            batch_size = job.config.hyperparameters.get('batch_size', {}).value or 32
            
            # Estimate based on model complexity and data size
            # This is a simplified estimation - in practice, you'd use historical data
            estimated_seconds = epochs * base_time_per_epoch
            
            # Adjust for batch size (smaller batches take longer)
            batch_factor = 32 / batch_size if batch_size > 0 else 1.0
            estimated_seconds *= batch_factor
            
            # Add some buffer
            estimated_seconds *= 1.2
            
            duration = timedelta(seconds=estimated_seconds)
            self._logger.debug(f"Estimated duration for job {job.job_id}: {duration}")
            
            return duration
            
        except Exception as e:
            self._logger.error(f"Failed to estimate duration for job {job.job_id}: {e}")
            return timedelta(hours=2)  # Default fallback
    
    def estimate_resources(self, job: TrainingJob) -> Dict[str, Any]:
        """
        Estimate resource requirements for job.
        
        Args:
            job: Training job to estimate
            
        Returns:
            Dictionary of resource requirements
        """
        try:
            # Base resource requirements
            requirements = {
                'cpu_cores': 4,
                'memory_gb': 8,
                'gpu_memory_gb': 4,
                'disk_space_gb': 10
            }
            
            # Adjust based on batch size
            batch_size = job.config.hyperparameters.get('batch_size', {}).value or 32
            if batch_size > 64:
                requirements['memory_gb'] *= 1.5
                requirements['gpu_memory_gb'] *= 1.5
            
            # Adjust based on model complexity (simplified)
            if 'transformer' in job.config.model_name.lower():
                requirements['memory_gb'] *= 2
                requirements['gpu_memory_gb'] *= 2
            
            job.resource_requirements = requirements
            return requirements
            
        except Exception as e:
            self._logger.error(f"Failed to estimate resources for job {job.job_id}: {e}")
            return {'cpu_cores': 4, 'memory_gb': 8, 'gpu_memory_gb': 4, 'disk_space_gb': 10}
    
    def update_historical_data(self, job: TrainingJob, actual_duration: timedelta, 
                             actual_resources: Dict[str, Any]) -> None:
        """
        Update historical data with actual job performance.
        
        Args:
            job: Completed training job
            actual_duration: Actual execution duration
            actual_resources: Actual resource usage
        """
        try:
            model_type = job.config.model_name
            
            if model_type not in self._historical_data:
                self._historical_data[model_type] = []
            
            data_point = {
                'job_id': job.job_id,
                'duration_seconds': actual_duration.total_seconds(),
                'epochs': job.config.max_epochs,
                'batch_size': job.config.hyperparameters.get('batch_size', {}).value or 32,
                'actual_resources': actual_resources,
                'timestamp': datetime.now().isoformat()
            }
            
            self._historical_data[model_type].append(data_point)
            
            # Keep only recent data (last 100 jobs per model type)
            if len(self._historical_data[model_type]) > 100:
                self._historical_data[model_type] = self._historical_data[model_type][-100:]
            
            self._logger.debug(f"Updated historical data for model type {model_type}")
            
        except Exception as e:
            self._logger.error(f"Failed to update historical data: {e}")


class TrainingScheduler(ITrainingScheduler):
    """
    Schedules and queues training jobs with priority management.
    
    This class provides comprehensive job scheduling with resource management,
    priority queuing, and execution coordination for training workflows.
    """
    
    def __init__(self, db_path: Optional[Path] = None, max_concurrent_jobs: int = 2):
        """
        Initialize training scheduler.
        
        Args:
            db_path: Path to scheduler database
            max_concurrent_jobs: Maximum number of concurrent jobs
        """
        self.db_path = db_path or Path("data/scheduler.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_concurrent_jobs = max_concurrent_jobs
        
        self._job_queue = JobQueue()
        self._resource_estimator = ResourceEstimator()
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()
        
        # Job tracking
        self._active_jobs: Dict[str, TrainingJob] = {}
        self._completed_jobs: Dict[str, TrainingJob] = {}
        self._failed_jobs: Dict[str, TrainingJob] = {}
        
        # Scheduling state
        self._is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            'total_jobs_scheduled': 0,
            'total_jobs_completed': 0,
            'total_jobs_failed': 0,
            'average_queue_time': timedelta(0),
            'average_execution_time': timedelta(0)
        }
        
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize scheduler database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_jobs (
                        job_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        config_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        scheduled_at TEXT,
                        started_at TEXT,
                        completed_at TEXT,
                        status TEXT NOT NULL,
                        estimated_duration_seconds REAL,
                        actual_duration_seconds REAL,
                        resource_requirements_json TEXT,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        error_message TEXT,
                        metadata_json TEXT
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_jobs_status 
                    ON scheduled_jobs (status, priority, created_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_jobs_session 
                    ON scheduled_jobs (session_id)
                """)
                
                conn.commit()
                self._logger.info("Scheduler database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize scheduler database: {e}")
                raise
            finally:
                conn.close()

    async def schedule_job(self, job: TrainingJob) -> str:
        """
        Schedule a training job.

        Args:
            job: Training job to schedule

        Returns:
            Job ID
        """
        try:
            # Generate job ID if not provided
            if not job.job_id:
                job.job_id = str(uuid.uuid4())

            # Estimate resources and duration
            job.resource_requirements = self._resource_estimator.estimate_resources(job)
            job.estimated_duration = self._resource_estimator.estimate_duration(job)

            # Add to queue
            self._job_queue.add_job(job)

            # Save to database
            await self._save_job(job, "queued")

            # Update statistics
            with self._lock:
                self._stats['total_jobs_scheduled'] += 1

            self._logger.info(f"Scheduled job {job.job_id} with priority {job.priority.value}")

            # Start scheduler if not running
            if not self._is_running:
                await self.start_scheduler()

            return job.job_id

        except Exception as e:
            self._logger.error(f"Failed to schedule job: {e}")
            raise

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a scheduled job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled successfully
        """
        try:
            # Remove from queue
            if self._job_queue.remove_job(job_id):
                await self._update_job_status(job_id, "cancelled")
                self._logger.info(f"Cancelled queued job {job_id}")
                return True

            # Check if job is active
            with self._lock:
                if job_id in self._active_jobs:
                    # Mark for cancellation (actual cancellation handled by executor)
                    job = self._active_jobs[job_id]
                    job.metadata['cancelled'] = True
                    await self._update_job_status(job_id, "cancelled")
                    self._logger.info(f"Marked active job {job_id} for cancellation")
                    return True

            self._logger.warning(f"Job {job_id} not found for cancellation")
            return False

        except Exception as e:
            self._logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    async def get_job_status(self, job_id: str) -> Optional[TrainingJob]:
        """
        Get job status and information.

        Args:
            job_id: Job identifier

        Returns:
            TrainingJob object or None if not found
        """
        try:
            # Check active jobs first
            with self._lock:
                if job_id in self._active_jobs:
                    return self._active_jobs[job_id]
                if job_id in self._completed_jobs:
                    return self._completed_jobs[job_id]
                if job_id in self._failed_jobs:
                    return self._failed_jobs[job_id]

            # Check queue
            job = self._job_queue.get_job(job_id)
            if job:
                return job

            # Load from database
            return await self._load_job(job_id)

        except Exception as e:
            self._logger.error(f"Failed to get job status for {job_id}: {e}")
            return None

    async def list_jobs(self, status_filter: Optional[str] = None) -> List[TrainingJob]:
        """
        List scheduled jobs with optional status filter.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of TrainingJob objects
        """
        try:
            jobs = []

            # Get jobs from different sources
            with self._lock:
                if not status_filter or status_filter == "active":
                    jobs.extend(self._active_jobs.values())
                if not status_filter or status_filter == "completed":
                    jobs.extend(self._completed_jobs.values())
                if not status_filter or status_filter == "failed":
                    jobs.extend(self._failed_jobs.values())

            if not status_filter or status_filter == "queued":
                jobs.extend(self._job_queue.list_jobs())

            # Sort by creation time
            jobs.sort(key=lambda x: x.created_at, reverse=True)

            return jobs

        except Exception as e:
            self._logger.error(f"Failed to list jobs: {e}")
            return []

    async def get_scheduler_status(self) -> SchedulerStatus:
        """
        Get scheduler status and statistics.

        Returns:
            SchedulerStatus object
        """
        try:
            with self._lock:
                active_jobs = len(self._active_jobs)
                queued_jobs = self._job_queue.size()
                completed_jobs = len(self._completed_jobs)
                failed_jobs = len(self._failed_jobs)

                return SchedulerStatus(
                    active_jobs=active_jobs,
                    queued_jobs=queued_jobs,
                    completed_jobs=completed_jobs,
                    failed_jobs=failed_jobs,
                    total_capacity=self.max_concurrent_jobs,
                    available_capacity=max(0, self.max_concurrent_jobs - active_jobs),
                    average_queue_time=self._stats['average_queue_time'],
                    average_execution_time=self._stats['average_execution_time'],
                    last_updated=datetime.now()
                )

        except Exception as e:
            self._logger.error(f"Failed to get scheduler status: {e}")
            return SchedulerStatus(
                active_jobs=0, queued_jobs=0, completed_jobs=0, failed_jobs=0,
                total_capacity=self.max_concurrent_jobs, available_capacity=0,
                average_queue_time=timedelta(0), average_execution_time=timedelta(0)
            )

    async def set_job_priority(self, job_id: str, priority: TrainingPriority) -> bool:
        """
        Update job priority.

        Args:
            job_id: Job identifier
            priority: New priority level

        Returns:
            True if updated successfully
        """
        try:
            # Check if job is in queue
            job = self._job_queue.get_job(job_id)
            if job:
                # Remove and re-add with new priority
                self._job_queue.remove_job(job_id)
                job.priority = priority
                self._job_queue.add_job(job)

                await self._update_job_priority(job_id, priority)
                self._logger.info(f"Updated priority for job {job_id} to {priority.value}")
                return True

            # Check if job is active (can't change priority of running jobs)
            with self._lock:
                if job_id in self._active_jobs:
                    self._logger.warning(f"Cannot change priority of active job {job_id}")
                    return False

            self._logger.warning(f"Job {job_id} not found for priority update")
            return False

        except Exception as e:
            self._logger.error(f"Failed to update job priority for {job_id}: {e}")
            return False

    async def estimate_queue_time(self, job: TrainingJob) -> timedelta:
        """
        Estimate queue time for a job.

        Args:
            job: Training job to estimate for

        Returns:
            Estimated queue time
        """
        try:
            # Get jobs ahead in queue with higher or equal priority
            queue_jobs = self._job_queue.list_jobs()
            jobs_ahead = [j for j in queue_jobs if j.priority.value >= job.priority.value and j.created_at < job.created_at]

            # Estimate total time for jobs ahead
            total_time = timedelta(0)
            for ahead_job in jobs_ahead:
                if ahead_job.estimated_duration:
                    total_time += ahead_job.estimated_duration
                else:
                    total_time += self._resource_estimator.estimate_duration(ahead_job)

            # Divide by available capacity
            available_capacity = max(1, self.max_concurrent_jobs - len(self._active_jobs))
            estimated_queue_time = total_time / available_capacity

            self._logger.debug(f"Estimated queue time for job {job.job_id}: {estimated_queue_time}")
            return estimated_queue_time

        except Exception as e:
            self._logger.error(f"Failed to estimate queue time: {e}")
            return timedelta(hours=1)  # Default fallback

    async def start_scheduler(self) -> None:
        """Start the job scheduler."""
        if self._is_running:
            return

        self._is_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._logger.info("Training scheduler started")

    async def stop_scheduler(self) -> None:
        """Stop the job scheduler."""
        self._is_running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        self._logger.info("Training scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._is_running:
            try:
                # Check if we can start new jobs
                with self._lock:
                    available_slots = self.max_concurrent_jobs - len(self._active_jobs)

                if available_slots > 0 and not self._job_queue.is_empty():
                    # Get next job from queue
                    next_job = self._job_queue.get_next_job()
                    if next_job:
                        await self._start_job(next_job)

                # Check for completed jobs
                await self._check_completed_jobs()

                # Sleep before next iteration
                await asyncio.sleep(1)

            except Exception as e:
                self._logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error

    async def _start_job(self, job: TrainingJob) -> None:
        """
        Start execution of a job.

        Args:
            job: Training job to start
        """
        try:
            job.scheduled_at = datetime.now()

            with self._lock:
                self._active_jobs[job.job_id] = job

            await self._update_job_status(job.job_id, "running")

            # In practice, you would start the actual training execution here
            # For now, we'll simulate job execution
            self._logger.info(f"Started job {job.job_id}")

            # Simulate job execution (replace with actual training executor call)
            asyncio.create_task(self._simulate_job_execution(job))

        except Exception as e:
            self._logger.error(f"Failed to start job {job.job_id}: {e}")
            await self._handle_job_failure(job, str(e))

    async def _simulate_job_execution(self, job: TrainingJob) -> None:
        """
        Simulate job execution (replace with actual training executor).

        Args:
            job: Training job to execute
        """
        try:
            # Simulate execution time
            execution_time = job.estimated_duration or timedelta(minutes=30)
            await asyncio.sleep(min(execution_time.total_seconds(), 10))  # Cap at 10 seconds for demo

            # Check if job was cancelled
            if job.metadata.get('cancelled', False):
                await self._handle_job_cancellation(job)
                return

            # Simulate success/failure
            import random
            if random.random() < 0.9:  # 90% success rate
                await self._handle_job_completion(job)
            else:
                await self._handle_job_failure(job, "Simulated training failure")

        except Exception as e:
            await self._handle_job_failure(job, str(e))

    async def _handle_job_completion(self, job: TrainingJob) -> None:
        """
        Handle successful job completion.

        Args:
            job: Completed training job
        """
        try:
            job.metadata['completed_at'] = datetime.now().isoformat()

            with self._lock:
                self._active_jobs.pop(job.job_id, None)
                self._completed_jobs[job.job_id] = job
                self._stats['total_jobs_completed'] += 1

            await self._update_job_status(job.job_id, "completed")

            # Update resource estimator with actual data
            actual_duration = datetime.now() - (job.scheduled_at or job.created_at)
            self._resource_estimator.update_historical_data(job, actual_duration, {})

            self._logger.info(f"Job {job.job_id} completed successfully")

        except Exception as e:
            self._logger.error(f"Error handling job completion for {job.job_id}: {e}")

    async def _handle_job_failure(self, job: TrainingJob, error_message: str) -> None:
        """
        Handle job failure.

        Args:
            job: Failed training job
            error_message: Error description
        """
        try:
            job.retry_count += 1
            job.metadata['error_message'] = error_message
            job.metadata['failed_at'] = datetime.now().isoformat()

            # Check if we should retry
            if job.retry_count < job.max_retries:
                # Re-queue for retry
                self._job_queue.add_job(job)
                await self._update_job_status(job.job_id, "queued")
                self._logger.info(f"Re-queued job {job.job_id} for retry ({job.retry_count}/{job.max_retries})")
            else:
                # Mark as permanently failed
                with self._lock:
                    self._active_jobs.pop(job.job_id, None)
                    self._failed_jobs[job.job_id] = job
                    self._stats['total_jobs_failed'] += 1

                await self._update_job_status(job.job_id, "failed")
                self._logger.error(f"Job {job.job_id} failed permanently: {error_message}")

        except Exception as e:
            self._logger.error(f"Error handling job failure for {job.job_id}: {e}")

    async def _handle_job_cancellation(self, job: TrainingJob) -> None:
        """
        Handle job cancellation.

        Args:
            job: Cancelled training job
        """
        try:
            job.metadata['cancelled_at'] = datetime.now().isoformat()

            with self._lock:
                self._active_jobs.pop(job.job_id, None)

            await self._update_job_status(job.job_id, "cancelled")
            self._logger.info(f"Job {job.job_id} was cancelled")

        except Exception as e:
            self._logger.error(f"Error handling job cancellation for {job.job_id}: {e}")

    async def _check_completed_jobs(self) -> None:
        """Check for completed jobs and update statistics."""
        # This method would check with the actual training executor
        # for job completion status in a real implementation
        pass

    async def _save_job(self, job: TrainingJob, status: str) -> None:
        """Save job to database."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO scheduled_jobs (
                            job_id, session_id, priority, config_json, created_at,
                            scheduled_at, status, estimated_duration_seconds,
                            resource_requirements_json, retry_count, max_retries,
                            metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job.job_id,
                        job.session_id,
                        job.priority.value,
                        json.dumps(job.config.__dict__, default=str),
                        job.created_at.isoformat(),
                        job.scheduled_at.isoformat() if job.scheduled_at else None,
                        status,
                        job.estimated_duration.total_seconds() if job.estimated_duration else None,
                        json.dumps(job.resource_requirements),
                        job.retry_count,
                        job.max_retries,
                        json.dumps(job.metadata)
                    ))

                    conn.commit()

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to save job {job.job_id}: {e}")
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Failed to save job {job.job_id}: {e}")

    async def _load_job(self, job_id: str) -> Optional[TrainingJob]:
        """Load job from database."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM scheduled_jobs WHERE job_id = ?
                    """, (job_id,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Reconstruct job object (simplified)
                    # In practice, you'd need proper deserialization
                    return None  # Placeholder

                except Exception as e:
                    self._logger.error(f"Failed to load job {job_id}: {e}")
                    return None
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Failed to load job {job_id}: {e}")
            return None

    async def _update_job_status(self, job_id: str, status: str) -> None:
        """Update job status in database."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE scheduled_jobs SET status = ? WHERE job_id = ?
                    """, (status, job_id))

                    conn.commit()

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to update job status for {job_id}: {e}")
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Failed to update job status for {job_id}: {e}")

    async def _update_job_priority(self, job_id: str, priority: TrainingPriority) -> None:
        """Update job priority in database."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE scheduled_jobs SET priority = ? WHERE job_id = ?
                    """, (priority.value, job_id))

                    conn.commit()

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to update job priority for {job_id}: {e}")
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Failed to update job priority for {job_id}: {e}")
