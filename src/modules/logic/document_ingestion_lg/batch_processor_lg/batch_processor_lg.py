"""
Module: batch_processor_lg
Description: Manages parallel processing of multiple documents with priority queuing and resource allocation
Phase: 3
Location: /src/modules/logic/document_ingestion_lg/batch_processor_lg/
"""

# Standard library imports
import asyncio
import threading
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from queue import PriorityQueue, Queue
from typing import Any, Callable, Dict, List, Optional, Set, Union

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_ingestion_lg.format_detector_lg import FormatDetector, DocumentFormat
from src.modules.logic.document_ingestion_lg.file_validator_lg import FileValidator, FileValidationResult


class BatchPriority(Enum):
    """Batch processing priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class BatchStatus(Enum):
    """Batch processing status."""
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class ProcessingMode(Enum):
    """Batch processing modes."""
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    ADAPTIVE = "ADAPTIVE"


@dataclass
class BatchItem:
    """Individual item in a batch processing job."""
    item_id: str
    file_path: Path
    priority: BatchPriority = BatchPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation_result: Optional[FileValidationResult] = None
    processing_start_time: Optional[datetime] = None
    processing_end_time: Optional[datetime] = None
    processing_duration: Optional[float] = None
    error_message: Optional[str] = None
    status: BatchStatus = BatchStatus.PENDING
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.item_id:
            self.item_id = str(uuid.uuid4())
    
    def __lt__(self, other):
        """Comparison for priority queue ordering."""
        if not isinstance(other, BatchItem):
            return NotImplemented
        # Higher priority values come first (reverse order)
        return self.priority.value > other.priority.value


@dataclass
class BatchJob:
    """Batch processing job containing multiple items."""
    job_id: str
    name: str
    items: List[BatchItem] = field(default_factory=list)
    priority: BatchPriority = BatchPriority.NORMAL
    processing_mode: ProcessingMode = ProcessingMode.ADAPTIVE
    max_concurrent_items: int = 4
    timeout_seconds: float = 300.0
    retry_attempts: int = 3
    created_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    status: BatchStatus = BatchStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.job_id:
            self.job_id = str(uuid.uuid4())
    
    @property
    def total_items(self) -> int:
        """Get total number of items in the batch."""
        return len(self.items)
    
    @property
    def completed_items(self) -> int:
        """Get number of completed items."""
        return len([item for item in self.items if item.status == BatchStatus.COMPLETED])
    
    @property
    def failed_items(self) -> int:
        """Get number of failed items."""
        return len([item for item in self.items if item.status == BatchStatus.FAILED])
    
    @property
    def processing_items(self) -> int:
        """Get number of items currently being processed."""
        return len([item for item in self.items if item.status == BatchStatus.PROCESSING])
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_items == 0:
            return 0.0
        return self.completed_items / self.total_items
    
    def update_progress(self) -> None:
        """Update job progress based on item completion."""
        if self.total_items == 0:
            self.progress = 1.0
        else:
            completed = self.completed_items + self.failed_items
            self.progress = completed / self.total_items


@dataclass
class BatchProcessingMetrics:
    """Metrics for batch processing performance."""
    job_id: str
    timestamp: datetime
    total_items: int
    completed_items: int
    failed_items: int
    processing_items: int
    average_processing_time: float
    throughput_items_per_second: float
    memory_usage_mb: float
    cpu_utilization_percent: float
    success_rate: float
    error_rate: float


class IBatchProcessor(ABC):
    """Interface for batch processors."""
    
    @abstractmethod
    async def submit_batch(self, batch_job: BatchJob) -> str:
        """
        Submit a batch job for processing.
        
        Args:
            batch_job: Batch job to process
            
        Returns:
            Job ID for tracking
        """
        pass
    
    @abstractmethod
    async def process_batch(self, batch_job: BatchJob) -> BatchJob:
        """
        Process a batch job.
        
        Args:
            batch_job: Batch job to process
            
        Returns:
            Updated batch job with results
        """
        pass
    
    @abstractmethod
    def get_job_status(self, job_id: str) -> Optional[BatchStatus]:
        """
        Get status of a batch job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status or None if not found
        """
        pass
    
    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a batch job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_processing_metrics(self, job_id: str) -> Optional[BatchProcessingMetrics]:
        """
        Get processing metrics for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Processing metrics or None if not found
        """
        pass


class BatchProcessor(IBatchProcessor):
    """
    Document batch processor with parallel processing and resource management.
    
    Features:
    - Priority-based job queuing
    - Parallel processing with configurable concurrency
    - Resource-aware processing
    - Progress tracking and metrics
    - Error handling and retry logic
    - Cancellation support
    """
    
    def __init__(self, max_concurrent_jobs: int = 2, max_concurrent_items: int = 4):
        """
        Initialize batch processor.
        
        Args:
            max_concurrent_jobs: Maximum number of concurrent batch jobs
            max_concurrent_items: Maximum number of concurrent items per job
        """
        self._logger = get_logger(__name__)
        self._max_concurrent_jobs = max_concurrent_jobs
        self._max_concurrent_items = max_concurrent_items
        
        # Processing components
        self._format_detector = FormatDetector()
        self._file_validator = FileValidator()
        
        # Job management
        self._job_queue: PriorityQueue = PriorityQueue()
        self._active_jobs: Dict[str, BatchJob] = {}
        self._completed_jobs: Dict[str, BatchJob] = {}
        self._cancelled_jobs: Set[str] = set()
        
        # Threading and synchronization
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent_jobs)
        self._job_lock = threading.RLock()
        self._shutdown_event = threading.Event()
        
        # Metrics tracking
        self._metrics: Dict[str, BatchProcessingMetrics] = {}
        
        # Start background processing
        self._processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._processing_thread.start()
        
        self._logger.info(
            f"BatchProcessor initialized: max_jobs={max_concurrent_jobs}, "
            f"max_items={max_concurrent_items}"
        )

    async def submit_batch(self, batch_job: BatchJob) -> str:
        """
        Submit a batch job for processing.

        Args:
            batch_job: Batch job to process

        Returns:
            Job ID for tracking
        """
        try:
            # Validate batch job
            if not batch_job.items:
                raise ValueError("Batch job must contain at least one item")

            # Set job status
            batch_job.status = BatchStatus.QUEUED

            # Add to queue with priority
            priority_item = (-batch_job.priority.value, time.time(), batch_job)
            self._job_queue.put(priority_item)

            with self._job_lock:
                self._active_jobs[batch_job.job_id] = batch_job

            self._logger.info(f"Batch job submitted: {batch_job.job_id} with {len(batch_job.items)} items")
            return batch_job.job_id

        except Exception as e:
            self._logger.error(f"Failed to submit batch job: {e}")
            batch_job.status = BatchStatus.FAILED
            raise

    async def process_batch(self, batch_job: BatchJob) -> BatchJob:
        """
        Process a batch job with parallel item processing.

        Args:
            batch_job: Batch job to process

        Returns:
            Updated batch job with results
        """
        try:
            batch_job.status = BatchStatus.PROCESSING
            batch_job.started_time = datetime.now(timezone.utc)

            self._logger.info(f"Starting batch processing: {batch_job.job_id}")

            # Determine processing mode
            if batch_job.processing_mode == ProcessingMode.SEQUENTIAL:
                await self._process_sequential(batch_job)
            elif batch_job.processing_mode == ProcessingMode.PARALLEL:
                await self._process_parallel(batch_job)
            else:  # ADAPTIVE
                await self._process_adaptive(batch_job)

            # Update final status
            batch_job.completed_time = datetime.now(timezone.utc)
            if batch_job.failed_items == 0:
                batch_job.status = BatchStatus.COMPLETED
            elif batch_job.completed_items > 0:
                batch_job.status = BatchStatus.COMPLETED  # Partial success
            else:
                batch_job.status = BatchStatus.FAILED

            batch_job.update_progress()

            # Generate metrics
            self._generate_metrics(batch_job)

            # Move to completed jobs
            with self._job_lock:
                if batch_job.job_id in self._active_jobs:
                    del self._active_jobs[batch_job.job_id]
                self._completed_jobs[batch_job.job_id] = batch_job

            self._logger.info(
                f"Batch processing completed: {batch_job.job_id}, "
                f"success_rate={batch_job.success_rate:.2f}"
            )

            return batch_job

        except Exception as e:
            self._logger.error(f"Batch processing failed: {batch_job.job_id}: {e}")
            batch_job.status = BatchStatus.FAILED
            batch_job.completed_time = datetime.now(timezone.utc)
            return batch_job

    def get_job_status(self, job_id: str) -> Optional[BatchStatus]:
        """Get status of a batch job."""
        with self._job_lock:
            if job_id in self._active_jobs:
                return self._active_jobs[job_id].status
            elif job_id in self._completed_jobs:
                return self._completed_jobs[job_id].status
            elif job_id in self._cancelled_jobs:
                return BatchStatus.CANCELLED
        return None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a batch job."""
        try:
            with self._job_lock:
                if job_id in self._active_jobs:
                    job = self._active_jobs[job_id]
                    job.status = BatchStatus.CANCELLED
                    self._cancelled_jobs.add(job_id)
                    self._logger.info(f"Batch job cancelled: {job_id}")
                    return True
            return False
        except Exception as e:
            self._logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    def get_processing_metrics(self, job_id: str) -> Optional[BatchProcessingMetrics]:
        """Get processing metrics for a job."""
        return self._metrics.get(job_id)

    async def _process_sequential(self, batch_job: BatchJob) -> None:
        """Process batch items sequentially."""
        for item in batch_job.items:
            if batch_job.job_id in self._cancelled_jobs:
                break

            await self._process_item(item, batch_job)
            batch_job.update_progress()

    async def _process_parallel(self, batch_job: BatchJob) -> None:
        """Process batch items in parallel."""
        max_workers = min(batch_job.max_concurrent_items, self._max_concurrent_items)

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_workers)

        async def process_with_semaphore(item):
            async with semaphore:
                if batch_job.job_id not in self._cancelled_jobs:
                    await self._process_item(item, batch_job)
                    batch_job.update_progress()

        # Process all items concurrently
        tasks = [process_with_semaphore(item) for item in batch_job.items]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_adaptive(self, batch_job: BatchJob) -> None:
        """Process batch items using adaptive strategy."""
        # Start with parallel processing for small batches
        if len(batch_job.items) <= 10:
            await self._process_parallel(batch_job)
        else:
            # Use chunked parallel processing for large batches
            chunk_size = max(1, len(batch_job.items) // 4)
            for i in range(0, len(batch_job.items), chunk_size):
                if batch_job.job_id in self._cancelled_jobs:
                    break

                chunk = batch_job.items[i:i + chunk_size]
                chunk_job = BatchJob(
                    job_id=f"{batch_job.job_id}_chunk_{i}",
                    name=f"{batch_job.name}_chunk_{i}",
                    items=chunk,
                    max_concurrent_items=batch_job.max_concurrent_items
                )
                await self._process_parallel(chunk_job)
                batch_job.update_progress()

    async def _process_item(self, item: BatchItem, batch_job: BatchJob) -> None:
        """Process a single batch item."""
        try:
            item.status = BatchStatus.PROCESSING
            item.processing_start_time = datetime.now(timezone.utc)

            # Validate file
            validation_result = self._file_validator.validate_file(item.file_path)
            item.validation_result = validation_result

            if not validation_result.is_valid:
                raise ValueError(f"File validation failed: {validation_result.get_error_summary()}")

            # Detect format
            format_result = self._format_detector.detect_format(item.file_path)
            if not format_result.is_supported:
                raise ValueError(f"Unsupported file format: {format_result.format_type.value}")

            # Simulate processing (in real implementation, this would call actual processors)
            await asyncio.sleep(0.1)  # Simulate processing time

            # Mark as completed
            item.status = BatchStatus.COMPLETED
            item.processing_end_time = datetime.now(timezone.utc)

            if item.processing_start_time and item.processing_end_time:
                item.processing_duration = (
                    item.processing_end_time - item.processing_start_time
                ).total_seconds()

            self._logger.debug(f"Item processed successfully: {item.item_id}")

        except Exception as e:
            item.status = BatchStatus.FAILED
            item.error_message = str(e)
            item.processing_end_time = datetime.now(timezone.utc)

            if item.processing_start_time and item.processing_end_time:
                item.processing_duration = (
                    item.processing_end_time - item.processing_start_time
                ).total_seconds()

            self._logger.error(f"Item processing failed: {item.item_id}: {e}")

    def _process_queue(self) -> None:
        """Background thread to process job queue."""
        while not self._shutdown_event.is_set():
            try:
                # Get job from queue with timeout
                try:
                    priority, timestamp, batch_job = self._job_queue.get(timeout=1.0)
                except:
                    continue

                # Check if job was cancelled
                if batch_job.job_id in self._cancelled_jobs:
                    self._job_queue.task_done()
                    continue

                # Process job in executor
                future = self._executor.submit(self._run_async_batch, batch_job)

                # Wait for completion or cancellation
                while not future.done():
                    if batch_job.job_id in self._cancelled_jobs:
                        future.cancel()
                        break
                    time.sleep(0.1)

                self._job_queue.task_done()

            except Exception as e:
                self._logger.error(f"Queue processing error: {e}")

    def _run_async_batch(self, batch_job: BatchJob) -> None:
        """Run async batch processing in thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.process_batch(batch_job))
        except Exception as e:
            self._logger.error(f"Async batch processing error: {e}")
        finally:
            loop.close()

    def _generate_metrics(self, batch_job: BatchJob) -> None:
        """Generate processing metrics for a batch job."""
        try:
            processing_times = [
                item.processing_duration for item in batch_job.items
                if item.processing_duration is not None
            ]

            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0

            total_duration = 0.0
            if batch_job.started_time and batch_job.completed_time:
                total_duration = (batch_job.completed_time - batch_job.started_time).total_seconds()

            throughput = batch_job.total_items / total_duration if total_duration > 0 else 0.0

            metrics = BatchProcessingMetrics(
                job_id=batch_job.job_id,
                timestamp=datetime.now(timezone.utc),
                total_items=batch_job.total_items,
                completed_items=batch_job.completed_items,
                failed_items=batch_job.failed_items,
                processing_items=batch_job.processing_items,
                average_processing_time=avg_processing_time,
                throughput_items_per_second=throughput,
                memory_usage_mb=0.0,  # Would be implemented with actual memory monitoring
                cpu_utilization_percent=0.0,  # Would be implemented with actual CPU monitoring
                success_rate=batch_job.success_rate,
                error_rate=1.0 - batch_job.success_rate
            )

            self._metrics[batch_job.job_id] = metrics

        except Exception as e:
            self._logger.error(f"Failed to generate metrics for {batch_job.job_id}: {e}")

    def shutdown(self) -> None:
        """Shutdown the batch processor."""
        self._logger.info("Shutting down batch processor")
        self._shutdown_event.set()

        # Cancel all active jobs
        with self._job_lock:
            for job_id in list(self._active_jobs.keys()):
                self.cancel_job(job_id)

        # Shutdown executor
        self._executor.shutdown(wait=True)

        # Wait for processing thread
        if self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5.0)

    def get_active_jobs(self) -> Dict[str, BatchJob]:
        """Get all active jobs."""
        with self._job_lock:
            return self._active_jobs.copy()

    def get_completed_jobs(self) -> Dict[str, BatchJob]:
        """Get all completed jobs."""
        with self._job_lock:
            return self._completed_jobs.copy()

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self._job_queue.qsize()
