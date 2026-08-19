"""
Module: batch_processor_lg
Description: Manages batch processing of embeddings with configurable batch sizes for efficiency
Phase: 4
Location: /src/modules/logic/embedding_generation_lg/batch_processor_lg/batch_processor_lg.py
"""

# Standard library imports
import asyncio
import heapq
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Deque
import psutil

# Local imports
from src.modules.logic.embedding_generation_lg.base_interfaces import (
    IBatchProcessor,
    BatchProcessingResult,
    BatchConfig,
    BatchStatus,
    EmbeddingResult,
    EmbeddingStatus
)
from src.modules.logic.embedding_generation_lg.document_embedder_lg import DocumentEmbedder
from src.modules.logic.embedding_generation_lg.base_interfaces import EmbeddingConfig
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ValidationError


@dataclass
class BatchItem:
    """Individual item in the batch processing queue."""
    text: str
    chunk_id: str
    document_id: str
    priority: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    
    def __lt__(self, other):
        """Enable priority queue ordering (higher priority first)."""
        return self.priority > other.priority


@dataclass
class BatchJob:
    """Batch processing job container."""
    batch_id: str
    items: List[BatchItem]
    status: BatchStatus = BatchStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    memory_usage_mb: float = 0.0


class BatchQueue:
    """
    Thread-safe priority queue for batch processing items.
    
    Features:
    - Priority-based ordering
    - Size limits and overflow handling
    - Thread-safe operations
    - Queue statistics
    """
    
    def __init__(self, max_size: int = 1000):
        """Initialize batch queue."""
        self._max_size = max_size
        self._queue: List[BatchItem] = []
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._total_added = 0
        self._total_processed = 0
        
    def add_item(self, item: BatchItem) -> bool:
        """Add item to queue with priority ordering."""
        with self._condition:
            if len(self._queue) >= self._max_size:
                return False
            
            heapq.heappush(self._queue, item)
            self._total_added += 1
            self._condition.notify()
            return True
    
    def get_batch(self, batch_size: int) -> List[BatchItem]:
        """Get batch of items from queue."""
        with self._condition:
            batch = []
            for _ in range(min(batch_size, len(self._queue))):
                if self._queue:
                    batch.append(heapq.heappop(self._queue))
            
            self._total_processed += len(batch)
            return batch
    
    def get_size(self) -> int:
        """Get current queue size."""
        with self._lock:
            return len(self._queue)
    
    def clear(self) -> int:
        """Clear all items from queue."""
        with self._condition:
            cleared_count = len(self._queue)
            self._queue.clear()
            self._condition.notify_all()
            return cleared_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            return {
                "current_size": len(self._queue),
                "max_size": self._max_size,
                "total_added": self._total_added,
                "total_processed": self._total_processed,
                "utilization": len(self._queue) / self._max_size if self._max_size > 0 else 0
            }


class BatchOptimizer:
    """
    Optimizes batch sizes based on system resources and performance metrics.
    
    Features:
    - Adaptive batch sizing
    - Memory usage monitoring
    - Performance tracking
    - Resource-aware optimization
    """
    
    def __init__(self, config: BatchConfig):
        """Initialize batch optimizer."""
        self._config = config
        self._logger = get_logger(__name__)
        
        # Performance tracking
        self._processing_times: Deque[float] = deque(maxlen=100)
        self._memory_usage: Deque[float] = deque(maxlen=100)
        self._batch_sizes: Deque[int] = deque(maxlen=100)
        self._lock = threading.RLock()
        
        # Current optimal batch size
        self._current_batch_size = config.batch_size
    
    def get_optimal_batch_size(self, queue_size: int) -> int:
        """Calculate optimal batch size based on current conditions."""
        if not self._config.adaptive_batching:
            return self._config.batch_size
        
        with self._lock:
            # Check memory constraints
            memory_usage = self._get_memory_usage_mb()
            if memory_usage > self._config.memory_limit_mb * 0.8:
                # Reduce batch size if memory is high
                self._current_batch_size = max(
                    self._config.min_batch_size,
                    int(self._current_batch_size * 0.8)
                )
            elif memory_usage < self._config.memory_limit_mb * 0.5:
                # Increase batch size if memory is low
                self._current_batch_size = min(
                    self._config.max_batch_size,
                    int(self._current_batch_size * 1.2)
                )
            
            # Consider queue size
            if queue_size < self._current_batch_size:
                return queue_size
            
            # Apply performance-based adjustments
            if len(self._processing_times) >= 10:
                recent_avg_time = sum(list(self._processing_times)[-10:]) / 10
                if recent_avg_time > 5000:  # 5 seconds
                    self._current_batch_size = max(
                        self._config.min_batch_size,
                        int(self._current_batch_size * 0.9)
                    )
            
            return max(self._config.min_batch_size, 
                      min(self._config.max_batch_size, self._current_batch_size))
    
    def record_batch_performance(self, batch_size: int, processing_time_ms: float, 
                               memory_usage_mb: float) -> None:
        """Record batch processing performance metrics."""
        with self._lock:
            self._processing_times.append(processing_time_ms)
            self._memory_usage.append(memory_usage_mb)
            self._batch_sizes.append(batch_size)
    
    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        with self._lock:
            if not self._processing_times:
                return {"status": "no_data"}
            
            return {
                "current_batch_size": self._current_batch_size,
                "avg_processing_time_ms": sum(self._processing_times) / len(self._processing_times),
                "avg_memory_usage_mb": sum(self._memory_usage) / len(self._memory_usage),
                "total_batches_processed": len(self._processing_times),
                "memory_limit_mb": self._config.memory_limit_mb,
                "adaptive_batching_enabled": self._config.adaptive_batching
            }


class EmbeddingBatchManager:
    """
    Manages the lifecycle of embedding batch jobs.
    
    Features:
    - Job creation and tracking
    - Status management
    - Resource monitoring
    - Error handling and recovery
    """
    
    def __init__(self, config: BatchConfig):
        """Initialize batch manager."""
        self._config = config
        self._logger = get_logger(__name__)
        
        # Job tracking
        self._active_jobs: Dict[str, BatchJob] = {}
        self._completed_jobs: Deque[BatchJob] = deque(maxlen=100)
        self._lock = threading.RLock()
        
        # Statistics
        self._total_jobs_created = 0
        self._total_jobs_completed = 0
        self._total_items_processed = 0
    
    def create_batch_job(self, items: List[BatchItem]) -> str:
        """Create a new batch job."""
        batch_id = str(uuid.uuid4())
        
        job = BatchJob(
            batch_id=batch_id,
            items=items,
            status=BatchStatus.QUEUED
        )
        
        with self._lock:
            self._active_jobs[batch_id] = job
            self._total_jobs_created += 1
        
        self._logger.debug(f"Created batch job {batch_id} with {len(items)} items")
        return batch_id
    
    def start_job(self, batch_id: str) -> bool:
        """Mark job as started."""
        with self._lock:
            if batch_id in self._active_jobs:
                job = self._active_jobs[batch_id]
                job.status = BatchStatus.PROCESSING
                job.started_at = datetime.now()
                return True
            return False
    
    def complete_job(self, batch_id: str, results: List[EmbeddingResult], 
                    memory_usage_mb: float) -> bool:
        """Mark job as completed and store results."""
        with self._lock:
            if batch_id in self._active_jobs:
                job = self._active_jobs.pop(batch_id)
                job.status = BatchStatus.COMPLETED
                job.completed_at = datetime.now()
                job.memory_usage_mb = memory_usage_mb
                
                self._completed_jobs.append(job)
                self._total_jobs_completed += 1
                self._total_items_processed += len(job.items)
                
                return True
            return False
    
    def fail_job(self, batch_id: str, error_message: str) -> bool:
        """Mark job as failed."""
        with self._lock:
            if batch_id in self._active_jobs:
                job = self._active_jobs[batch_id]
                job.status = BatchStatus.FAILED
                job.completed_at = datetime.now()
                
                self._logger.error(f"Batch job {batch_id} failed: {error_message}")
                return True
            return False
    
    def get_job_status(self, batch_id: str) -> Optional[BatchStatus]:
        """Get status of a specific job."""
        with self._lock:
            if batch_id in self._active_jobs:
                return self._active_jobs[batch_id].status
            
            # Check completed jobs
            for job in self._completed_jobs:
                if job.batch_id == batch_id:
                    return job.status
            
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get batch manager statistics."""
        with self._lock:
            return {
                "total_jobs_created": self._total_jobs_created,
                "total_jobs_completed": self._total_jobs_completed,
                "total_items_processed": self._total_items_processed,
                "active_jobs": len(self._active_jobs),
                "completed_jobs_cached": len(self._completed_jobs),
                "success_rate": (self._total_jobs_completed / max(self._total_jobs_created, 1)) * 100
            }


class BatchProcessor(IBatchProcessor):
    """
    Main batch processor that manages batch processing of embeddings with configurable batch sizes.
    
    Features:
    - Priority-based queue management
    - Adaptive batch sizing (32-128 chunks)
    - Memory usage optimization
    - Concurrent batch processing
    - Performance monitoring
    - Error handling and recovery
    """
    
    def __init__(self, config: Optional[BatchConfig] = None, 
                 embedding_config: Optional[EmbeddingConfig] = None):
        """Initialize batch processor."""
        self._config = config or BatchConfig()
        self._embedding_config = embedding_config or EmbeddingConfig()
        self._logger = get_logger(__name__)
        
        # Core components
        self._queue = BatchQueue(self._config.queue_size_limit)
        self._optimizer = BatchOptimizer(self._config)
        self._job_manager = EmbeddingBatchManager(self._config)
        self._embedder = DocumentEmbedder(self._embedding_config)
        
        # Processing state
        self._processing_active = False
        self._processing_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        self._logger.info("BatchProcessor initialized successfully")
    
    def add_to_queue(self, text: str, chunk_id: str, document_id: str, priority: int = 0) -> bool:
        """
        Add a text chunk to the processing queue.
        
        Args:
            text: Text content to process
            chunk_id: Unique identifier for the chunk
            document_id: Source document identifier
            priority: Processing priority (higher = more urgent)
            
        Returns:
            True if successfully queued, False otherwise
        """
        try:
            item = BatchItem(
                text=text,
                chunk_id=chunk_id,
                document_id=document_id,
                priority=priority
            )
            
            success = self._queue.add_item(item)
            if success:
                self._logger.debug(f"Added chunk {chunk_id} to queue with priority {priority}")
            else:
                self._logger.warning(f"Failed to add chunk {chunk_id} to queue - queue full")
            
            return success
            
        except Exception as e:
            self._logger.error(f"Error adding item to queue: {e}")
            return False
    
    def process_batch(self, batch_size: Optional[int] = None) -> BatchProcessingResult:
        """
        Process a batch of queued items.
        
        Args:
            batch_size: Optional override for batch size
            
        Returns:
            BatchProcessingResult with processing details
        """
        start_time = time.time()
        batch_id = str(uuid.uuid4())
        
        try:
            # Determine optimal batch size
            queue_size = self._queue.get_size()
            if batch_size is None:
                batch_size = self._optimizer.get_optimal_batch_size(queue_size)
            
            if queue_size == 0:
                return BatchProcessingResult(
                    status=BatchStatus.COMPLETED,
                    batch_id=batch_id,
                    total_chunks=0,
                    processed_chunks=0,
                    successful_embeddings=0,
                    failed_embeddings=0
                )
            
            # Get batch items
            batch_items = self._queue.get_batch(batch_size)
            if not batch_items:
                return BatchProcessingResult(
                    status=BatchStatus.COMPLETED,
                    batch_id=batch_id,
                    total_chunks=0,
                    processed_chunks=0,
                    successful_embeddings=0,
                    failed_embeddings=0
                )
            
            # Create and start job
            job_id = self._job_manager.create_batch_job(batch_items)
            self._job_manager.start_job(job_id)
            
            # Prepare batch data
            texts = [item.text for item in batch_items]
            chunk_ids = [item.chunk_id for item in batch_items]
            document_ids = [item.document_id for item in batch_items]
            
            # Process embeddings
            self._logger.info(f"Processing batch {batch_id} with {len(batch_items)} items")
            embedding_results = self._embedder.generate_embeddings_batch(texts, chunk_ids, document_ids)
            
            # Calculate metrics
            processing_time = (time.time() - start_time) * 1000
            memory_usage = self._get_memory_usage_mb()
            
            successful_count = sum(1 for r in embedding_results if r.status == EmbeddingStatus.SUCCESS)
            failed_count = len(embedding_results) - successful_count
            
            # Record performance
            self._optimizer.record_batch_performance(len(batch_items), processing_time, memory_usage)
            
            # Complete job
            self._job_manager.complete_job(job_id, embedding_results, memory_usage)
            
            result = BatchProcessingResult(
                status=BatchStatus.COMPLETED,
                batch_id=batch_id,
                total_chunks=len(batch_items),
                processed_chunks=len(embedding_results),
                successful_embeddings=successful_count,
                failed_embeddings=failed_count,
                embeddings=embedding_results,
                processing_time_ms=processing_time,
                memory_usage_mb=memory_usage
            )
            
            self._logger.info(f"Batch {batch_id} completed: {successful_count} successful, {failed_count} failed")
            return result
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self._logger.error(f"Batch processing failed: {e}")
            
            return BatchProcessingResult(
                status=BatchStatus.FAILED,
                batch_id=batch_id,
                total_chunks=len(batch_items) if 'batch_items' in locals() else 0,
                processed_chunks=0,
                successful_embeddings=0,
                failed_embeddings=0,
                processing_time_ms=processing_time,
                errors=[str(e)]
            )
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current status of the processing queue.
        
        Returns:
            Dictionary with queue statistics
        """
        queue_stats = self._queue.get_statistics()
        optimizer_stats = self._optimizer.get_optimization_stats()
        manager_stats = self._job_manager.get_statistics()
        
        return {
            "queue": queue_stats,
            "optimization": optimizer_stats,
            "job_management": manager_stats,
            "processing_active": self._processing_active,
            "memory_usage_mb": self._get_memory_usage_mb()
        }
    
    def clear_queue(self) -> bool:
        """
        Clear all items from the processing queue.
        
        Returns:
            True if successfully cleared, False otherwise
        """
        try:
            cleared_count = self._queue.clear()
            self._logger.info(f"Cleared {cleared_count} items from queue")
            return True
        except Exception as e:
            self._logger.error(f"Failed to clear queue: {e}")
            return False
    
    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
