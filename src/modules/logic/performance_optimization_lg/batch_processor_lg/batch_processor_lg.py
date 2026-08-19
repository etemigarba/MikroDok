"""
Module: batch_processor_lg
Description: Handles efficient batch processing operations with dynamic optimization and resource-aware scheduling
Phase: 2
Location: /src/modules/logic/performance_optimization_lg/batch_processor_lg/
"""

# Standard library imports
import asyncio
import logging
import math
import statistics
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable, Set, Union, Iterator
from collections import deque, defaultdict
import queue

# Local imports
from src.modules.logic.resource_monitor_lg import ResourceMetrics, MemoryMetrics, GPUMetrics
from src.modules.logic.performance_optimizer_lg.batch_size_optimizer_lg import (
    BatchSizeOptimizer, 
    ResourceConstraints,
    BatchConfiguration
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class BatchType(Enum):
    """Types of batch processing."""
    TRAINING_BATCH = "TRAINING_BATCH"
    INFERENCE_BATCH = "INFERENCE_BATCH"
    PREPROCESSING_BATCH = "PREPROCESSING_BATCH"
    VALIDATION_BATCH = "VALIDATION_BATCH"
    DATA_LOADING_BATCH = "DATA_LOADING_BATCH"


class ProcessingMode(Enum):
    """Batch processing modes."""
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    PIPELINE = "PIPELINE"
    ADAPTIVE = "ADAPTIVE"


class BatchPriority(Enum):
    """Batch processing priorities."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


class BatchStatus(Enum):
    """Batch processing status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


@dataclass
class BatchItem:
    """Individual item in a batch."""
    item_id: str
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time: Optional[float] = None
    error: Optional[str] = None


@dataclass
class BatchJob:
    """Batch processing job."""
    job_id: str
    batch_type: BatchType
    items: List[BatchItem]
    priority: BatchPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: BatchStatus = BatchStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingConfiguration:
    """Batch processing configuration."""
    max_batch_size: int = 32
    min_batch_size: int = 1
    max_concurrent_batches: int = 4
    processing_timeout_seconds: float = 300.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    enable_dynamic_sizing: bool = True
    enable_load_balancing: bool = True
    memory_limit_mb: float = 8192.0
    processing_mode: ProcessingMode = ProcessingMode.ADAPTIVE


@dataclass
class ProcessingMetrics:
    """Batch processing metrics."""
    timestamp: datetime
    batch_id: str
    batch_size: int
    processing_time_seconds: float
    throughput_items_per_second: float
    memory_usage_mb: float
    cpu_utilization_percent: float
    gpu_utilization_percent: float
    error_count: int
    success_rate: float


class IBatchProcessor(ABC):
    """Interface for batch processing systems."""
    
    @abstractmethod
    async def submit_batch(self, job: BatchJob) -> str:
        """Submit a batch job for processing."""
        pass
    
    @abstractmethod
    async def process_batch(self, job: BatchJob) -> BatchJob:
        """Process a batch job."""
        pass
    
    @abstractmethod
    def get_batch_status(self, job_id: str) -> Optional[BatchStatus]:
        """Get status of a batch job."""
        pass
    
    @abstractmethod
    def cancel_batch(self, job_id: str) -> bool:
        """Cancel a batch job."""
        pass


class BatchProcessor(IBatchProcessor):
    """Efficient batch processor with dynamic optimization and resource awareness."""
    
    def __init__(self, config: ProcessingConfiguration, 
                 batch_optimizer: Optional[BatchSizeOptimizer] = None):
        """Initialize the batch processor."""
        self._config = config
        self._batch_optimizer = batch_optimizer
        self._logger = get_logger(__name__)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Job management
        self._pending_jobs: queue.PriorityQueue = queue.PriorityQueue()
        self._active_jobs: Dict[str, BatchJob] = {}
        self._completed_jobs: Dict[str, BatchJob] = {}
        self._job_history: deque = deque(maxlen=1000)
        
        # Processing state
        self._processing_enabled = False
        self._worker_tasks: List[asyncio.Task] = []
        self._current_batch_size = config.max_batch_size
        
        # Performance tracking
        self._processing_metrics: deque = deque(maxlen=1000)
        self._throughput_history: deque = deque(maxlen=100)
        
        # Resource monitoring
        self._resource_metrics: Optional[ResourceMetrics] = None
        self._last_optimization = datetime.now(timezone.utc)
        
        # Callbacks
        self._job_callbacks: Dict[str, List[Callable[[BatchJob], None]]] = defaultdict(list)
        self._metrics_callbacks: List[Callable[[ProcessingMetrics], None]] = []
        
        self._logger.info("Batch processor initialized")
    
    async def start_processing(self) -> None:
        """Start batch processing workers."""
        if self._processing_enabled:
            self._logger.warning("Batch processing already running")
            return
        
        self._processing_enabled = True
        
        # Start worker tasks
        for i in range(self._config.max_concurrent_batches):
            task = asyncio.create_task(self._worker_loop(f"worker_{i}"))
            self._worker_tasks.append(task)
        
        self._logger.info(f"Started {len(self._worker_tasks)} batch processing workers")
    
    async def stop_processing(self) -> None:
        """Stop batch processing workers."""
        if not self._processing_enabled:
            return
        
        self._processing_enabled = False
        
        # Cancel worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        self._worker_tasks.clear()
        self._logger.info("Batch processing workers stopped")
    
    async def _worker_loop(self, worker_id: str) -> None:
        """Main worker loop for processing batches."""
        try:
            while self._processing_enabled:
                try:
                    # Get next job (with timeout)
                    try:
                        priority, job = self._pending_jobs.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    
                    # Process the job
                    await self._process_job(job, worker_id)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._logger.error(f"Error in worker {worker_id}: {e}")
                    await asyncio.sleep(1.0)  # Brief pause on error
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Fatal error in worker {worker_id}: {e}")
    
    async def submit_batch(self, job: BatchJob) -> str:
        """Submit a batch job for processing."""
        try:
            with self._lock:
                # Validate job
                if not job.items:
                    raise ValueError("Batch job must contain at least one item")
                
                # Set job metadata
                job.created_at = datetime.now(timezone.utc)
                job.status = BatchStatus.PENDING
                
                # Calculate priority value (lower number = higher priority)
                priority_value = {
                    BatchPriority.CRITICAL: 0,
                    BatchPriority.HIGH: 1,
                    BatchPriority.NORMAL: 2,
                    BatchPriority.LOW: 3,
                    BatchPriority.BACKGROUND: 4
                }.get(job.priority, 2)
                
                # Add to pending queue
                self._pending_jobs.put((priority_value, job))
                
                # Notify callbacks
                self._notify_job_callbacks(job, 'submitted')
                
                self._logger.info(f"Submitted batch job {job.job_id} with {len(job.items)} items")
                return job.job_id
                
        except Exception as e:
            self._logger.error(f"Error submitting batch job: {e}")
            raise

    async def _process_job(self, job: BatchJob, worker_id: str) -> None:
        """Process a batch job."""
        start_time = time.time()

        try:
            with self._lock:
                job.status = BatchStatus.PROCESSING
                job.started_at = datetime.now(timezone.utc)
                self._active_jobs[job.job_id] = job

            self._logger.info(f"Worker {worker_id} processing job {job.job_id}")

            # Optimize batch size if enabled
            if self._config.enable_dynamic_sizing and self._batch_optimizer:
                await self._optimize_batch_size(job)

            # Process items in batches
            processed_items = 0
            total_items = len(job.items)

            for batch_start in range(0, total_items, self._current_batch_size):
                batch_end = min(batch_start + self._current_batch_size, total_items)
                batch_items = job.items[batch_start:batch_end]

                # Process batch
                await self._process_batch_items(batch_items, job)

                # Update progress
                processed_items += len(batch_items)
                job.progress = (processed_items / total_items) * 100

                # Check for cancellation
                if job.status == BatchStatus.CANCELLED:
                    break

            # Complete job
            if job.status != BatchStatus.CANCELLED:
                job.status = BatchStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)

            # Record metrics
            processing_time = time.time() - start_time
            await self._record_processing_metrics(job, processing_time, worker_id)

            # Move to completed jobs
            with self._lock:
                if job.job_id in self._active_jobs:
                    del self._active_jobs[job.job_id]
                self._completed_jobs[job.job_id] = job
                self._job_history.append(job)

            # Notify callbacks
            self._notify_job_callbacks(job, 'completed')

            self._logger.info(f"Worker {worker_id} completed job {job.job_id} in {processing_time:.2f}s")

        except Exception as e:
            self._logger.error(f"Error processing job {job.job_id}: {e}")

            # Mark job as failed
            job.status = BatchStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)

            with self._lock:
                if job.job_id in self._active_jobs:
                    del self._active_jobs[job.job_id]
                self._completed_jobs[job.job_id] = job

            # Notify callbacks
            self._notify_job_callbacks(job, 'failed')

    async def _process_batch_items(self, items: List[BatchItem], job: BatchJob) -> None:
        """Process a batch of items."""
        try:
            # This is where actual processing would happen
            # For now, we'll simulate processing

            for item in items:
                item_start_time = time.time()

                try:
                    # Simulate processing based on batch type
                    if job.batch_type == BatchType.TRAINING_BATCH:
                        await asyncio.sleep(0.1)  # Simulate training
                    elif job.batch_type == BatchType.INFERENCE_BATCH:
                        await asyncio.sleep(0.05)  # Simulate inference
                    elif job.batch_type == BatchType.PREPROCESSING_BATCH:
                        await asyncio.sleep(0.02)  # Simulate preprocessing
                    else:
                        await asyncio.sleep(0.01)  # Default processing

                    item.processing_time = time.time() - item_start_time

                except Exception as e:
                    item.error = str(e)
                    self._logger.error(f"Error processing item {item.item_id}: {e}")

        except Exception as e:
            self._logger.error(f"Error processing batch items: {e}")
            raise

    async def _optimize_batch_size(self, job: BatchJob) -> None:
        """Optimize batch size for the job."""
        try:
            if not self._batch_optimizer or not self._resource_metrics:
                return

            # Get optimization recommendation
            recommendation = await self._batch_optimizer.optimize_batch_size(
                self._resource_metrics,
                self._current_batch_size
            )

            if recommendation.recommended_size != self._current_batch_size:
                old_size = self._current_batch_size
                self._current_batch_size = recommendation.recommended_size

                self._logger.info(
                    f"Optimized batch size: {old_size} -> {self._current_batch_size} "
                    f"(confidence: {recommendation.confidence:.2f})"
                )

        except Exception as e:
            self._logger.error(f"Error optimizing batch size: {e}")

    async def _record_processing_metrics(self, job: BatchJob, processing_time: float,
                                       worker_id: str) -> None:
        """Record processing metrics."""
        try:
            # Calculate metrics
            total_items = len(job.items)
            throughput = total_items / processing_time if processing_time > 0 else 0

            # Count errors
            error_count = sum(1 for item in job.items if item.error)
            success_rate = ((total_items - error_count) / total_items) * 100 if total_items > 0 else 0

            # Create metrics record
            metrics = ProcessingMetrics(
                timestamp=datetime.now(timezone.utc),
                batch_id=job.job_id,
                batch_size=len(job.items),
                processing_time_seconds=processing_time,
                throughput_items_per_second=throughput,
                memory_usage_mb=0.0,  # Would be measured in real implementation
                cpu_utilization_percent=0.0,  # Would be measured in real implementation
                gpu_utilization_percent=0.0,  # Would be measured in real implementation
                error_count=error_count,
                success_rate=success_rate
            )

            # Store metrics
            self._processing_metrics.append(metrics)
            self._throughput_history.append(throughput)

            # Notify callbacks
            for callback in self._metrics_callbacks:
                try:
                    callback(metrics)
                except Exception as e:
                    self._logger.error(f"Error in metrics callback: {e}")

        except Exception as e:
            self._logger.error(f"Error recording processing metrics: {e}")

    def _notify_job_callbacks(self, job: BatchJob, event_type: str) -> None:
        """Notify job event callbacks."""
        try:
            callbacks = self._job_callbacks.get(event_type, [])
            for callback in callbacks:
                try:
                    callback(job)
                except Exception as e:
                    self._logger.error(f"Error in job callback: {e}")
        except Exception as e:
            self._logger.error(f"Error notifying job callbacks: {e}")

    async def process_batch(self, job: BatchJob) -> BatchJob:
        """Process a batch job synchronously."""
        try:
            # Submit and wait for completion
            job_id = await self.submit_batch(job)

            # Wait for completion
            while True:
                status = self.get_batch_status(job_id)
                if status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]:
                    break
                await asyncio.sleep(0.1)

            # Return completed job
            return self._completed_jobs.get(job_id, job)

        except Exception as e:
            self._logger.error(f"Error processing batch synchronously: {e}")
            job.status = BatchStatus.FAILED
            job.error_message = str(e)
            return job

    def get_batch_status(self, job_id: str) -> Optional[BatchStatus]:
        """Get status of a batch job."""
        try:
            with self._lock:
                # Check active jobs
                if job_id in self._active_jobs:
                    return self._active_jobs[job_id].status

                # Check completed jobs
                if job_id in self._completed_jobs:
                    return self._completed_jobs[job_id].status

                # Check pending queue
                temp_queue = queue.Queue()
                found_status = None

                while not self._pending_jobs.empty():
                    try:
                        priority, job = self._pending_jobs.get_nowait()
                        temp_queue.put((priority, job))

                        if job.job_id == job_id:
                            found_status = job.status
                    except queue.Empty:
                        break

                # Restore queue
                while not temp_queue.empty():
                    self._pending_jobs.put(temp_queue.get())

                return found_status

        except Exception as e:
            self._logger.error(f"Error getting batch status: {e}")
            return None

    def cancel_batch(self, job_id: str) -> bool:
        """Cancel a batch job."""
        try:
            with self._lock:
                # Check active jobs
                if job_id in self._active_jobs:
                    job = self._active_jobs[job_id]
                    job.status = BatchStatus.CANCELLED
                    job.completed_at = datetime.now(timezone.utc)

                    self._logger.info(f"Cancelled active job {job_id}")
                    return True

                # Check pending queue
                temp_queue = queue.Queue()
                cancelled = False

                while not self._pending_jobs.empty():
                    try:
                        priority, job = self._pending_jobs.get_nowait()

                        if job.job_id == job_id:
                            job.status = BatchStatus.CANCELLED
                            job.completed_at = datetime.now(timezone.utc)
                            self._completed_jobs[job_id] = job
                            cancelled = True
                            self._logger.info(f"Cancelled pending job {job_id}")
                        else:
                            temp_queue.put((priority, job))
                    except queue.Empty:
                        break

                # Restore queue
                while not temp_queue.empty():
                    self._pending_jobs.put(temp_queue.get())

                return cancelled

        except Exception as e:
            self._logger.error(f"Error cancelling batch: {e}")
            return False

    def get_job_details(self, job_id: str) -> Optional[BatchJob]:
        """Get detailed information about a job."""
        try:
            with self._lock:
                if job_id in self._active_jobs:
                    return self._active_jobs[job_id]
                if job_id in self._completed_jobs:
                    return self._completed_jobs[job_id]
                return None
        except Exception as e:
            self._logger.error(f"Error getting job details: {e}")
            return None

    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        try:
            with self._lock:
                if not self._processing_metrics:
                    return {}

                recent_metrics = list(self._processing_metrics)[-100:]  # Last 100 metrics

                avg_throughput = statistics.mean(
                    m.throughput_items_per_second for m in recent_metrics
                ) if recent_metrics else 0.0

                avg_processing_time = statistics.mean(
                    m.processing_time_seconds for m in recent_metrics
                ) if recent_metrics else 0.0

                total_errors = sum(m.error_count for m in recent_metrics)
                total_items = sum(m.batch_size for m in recent_metrics)

                return {
                    'total_jobs_processed': len(self._job_history),
                    'active_jobs': len(self._active_jobs),
                    'pending_jobs': self._pending_jobs.qsize(),
                    'completed_jobs': len(self._completed_jobs),
                    'average_throughput': avg_throughput,
                    'average_processing_time': avg_processing_time,
                    'total_errors': total_errors,
                    'total_items_processed': total_items,
                    'error_rate': (total_errors / total_items * 100) if total_items > 0 else 0.0,
                    'current_batch_size': self._current_batch_size
                }

        except Exception as e:
            self._logger.error(f"Error getting processing statistics: {e}")
            return {}

    def add_job_callback(self, event_type: str, callback: Callable[[BatchJob], None]) -> None:
        """Add job event callback."""
        self._job_callbacks[event_type].append(callback)

    def add_metrics_callback(self, callback: Callable[[ProcessingMetrics], None]) -> None:
        """Add metrics callback."""
        self._metrics_callbacks.append(callback)

    def update_resource_metrics(self, metrics: ResourceMetrics) -> None:
        """Update resource metrics for optimization."""
        self._resource_metrics = metrics

    def configure_processing(self, config: ProcessingConfiguration) -> None:
        """Update processing configuration."""
        with self._lock:
            self._config = config
            self._current_batch_size = min(self._current_batch_size, config.max_batch_size)
            self._logger.info("Processing configuration updated")

    def pause_processing(self) -> bool:
        """Pause batch processing."""
        try:
            self._processing_enabled = False
            self._logger.info("Batch processing paused")
            return True
        except Exception as e:
            self._logger.error(f"Error pausing processing: {e}")
            return False

    def resume_processing(self) -> bool:
        """Resume batch processing."""
        try:
            if not self._processing_enabled:
                asyncio.create_task(self.start_processing())
                self._logger.info("Batch processing resumed")
            return True
        except Exception as e:
            self._logger.error(f"Error resuming processing: {e}")
            return False
