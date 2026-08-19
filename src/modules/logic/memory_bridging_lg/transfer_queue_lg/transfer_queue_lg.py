"""
Module: transfer_queue_lg
Description: Manages pending memory transfers with priority scheduling and bandwidth allocation
Phase: 2
Location: /src/modules/logic/memory_bridging_lg/transfer_queue_lg/
"""

# Standard library imports
import asyncio
import heapq
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
import uuid

# Local imports
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import MemoryTier
from src.modules.logic.memory_bridging_lg.bridge_controller_lg import (
    TransferRequest, TransferResult, TransferStatus, TransferPriority
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


class QueueStatus(Enum):
    """Status of the transfer queue."""
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    ERROR = "error"


@dataclass
class QueuedTransfer:
    """Represents a queued transfer with scheduling information."""
    transfer_request: TransferRequest
    queue_priority: int  # Lower number = higher priority
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: Optional[datetime] = None
    estimated_start_time: Optional[datetime] = None
    estimated_completion_time: Optional[datetime] = None
    bandwidth_allocation: float = 0.0  # MB/s
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """Enable priority queue ordering."""
        return self.queue_priority < other.queue_priority


@dataclass
class QueueConfiguration:
    """Configuration for the transfer queue."""
    max_queue_size: int = 1000
    max_concurrent_transfers: int = 4
    default_bandwidth_limit_mbps: float = 1000.0
    priority_bandwidth_boost: float = 1.5
    queue_timeout_seconds: float = 3600.0  # 1 hour
    enable_adaptive_scheduling: bool = True
    bandwidth_monitoring_interval: float = 1.0
    retry_delay_seconds: float = 2.0
    enable_bandwidth_throttling: bool = True


@dataclass
class QueueMetrics:
    """Metrics for queue performance."""
    total_queued: int = 0
    total_processed: int = 0
    total_failed: int = 0
    current_queue_size: int = 0
    average_queue_time_seconds: float = 0.0
    average_processing_time_seconds: float = 0.0
    bandwidth_utilization_percent: float = 0.0
    throughput_mbps: float = 0.0
    queue_efficiency: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ITransferQueue(ABC):
    """Interface for transfer queue managers."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the transfer queue."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the transfer queue."""
        pass
    
    @abstractmethod
    async def enqueue_transfer(self, request: TransferRequest) -> str:
        """Enqueue a transfer request."""
        pass
    
    @abstractmethod
    async def dequeue_transfer(self, queue_id: str) -> bool:
        """Remove a transfer from the queue."""
        pass
    
    @abstractmethod
    async def get_queue_status(self) -> QueueStatus:
        """Get current queue status."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> QueueMetrics:
        """Get queue metrics."""
        pass


class TransferScheduler:
    """Handles scheduling logic for transfer queue."""
    
    def __init__(self, config: QueueConfiguration):
        self._config = config
        self._bandwidth_allocations: Dict[str, float] = {}
        self._active_transfers: Dict[str, QueuedTransfer] = {}
    
    def calculate_priority(self, request: TransferRequest) -> int:
        """Calculate queue priority for a transfer request."""
        base_priority = request.priority.value * 1000
        
        # Adjust based on size (smaller transfers get slight priority)
        size_factor = min(100, request.size_bytes // (1024 * 1024))  # MB
        
        # Adjust based on deadline if present
        deadline_factor = 0
        if request.deadline:
            time_to_deadline = (request.deadline - datetime.now(timezone.utc)).total_seconds()
            if time_to_deadline < 300:  # Less than 5 minutes
                deadline_factor = -500  # Higher priority
        
        return base_priority + size_factor + deadline_factor
    
    def allocate_bandwidth(self, queued_transfer: QueuedTransfer, 
                          available_bandwidth: float) -> float:
        """Allocate bandwidth for a transfer."""
        base_allocation = available_bandwidth / max(1, len(self._active_transfers))
        
        # Boost for high priority transfers
        if queued_transfer.transfer_request.priority in [TransferPriority.CRITICAL, TransferPriority.HIGH]:
            base_allocation *= self._config.priority_bandwidth_boost
        
        return min(base_allocation, self._config.default_bandwidth_limit_mbps)
    
    def estimate_completion_time(self, queued_transfer: QueuedTransfer) -> datetime:
        """Estimate completion time for a transfer."""
        size_mb = queued_transfer.transfer_request.size_bytes / (1024 * 1024)
        bandwidth = max(queued_transfer.bandwidth_allocation, 1.0)
        
        estimated_duration = size_mb / bandwidth
        return datetime.now(timezone.utc) + timedelta(seconds=estimated_duration)


class BandwidthAllocator:
    """Manages bandwidth allocation across transfers."""
    
    def __init__(self, config: QueueConfiguration):
        self._config = config
        self._total_bandwidth = config.default_bandwidth_limit_mbps
        self._allocated_bandwidth: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def allocate(self, transfer_id: str, requested_bandwidth: float) -> float:
        """Allocate bandwidth for a transfer."""
        with self._lock:
            available = self._total_bandwidth - sum(self._allocated_bandwidth.values())
            allocated = min(requested_bandwidth, available)
            
            if allocated > 0:
                self._allocated_bandwidth[transfer_id] = allocated
            
            return allocated
    
    def deallocate(self, transfer_id: str) -> None:
        """Deallocate bandwidth for a transfer."""
        with self._lock:
            self._allocated_bandwidth.pop(transfer_id, None)
    
    def get_available_bandwidth(self) -> float:
        """Get currently available bandwidth."""
        with self._lock:
            return self._total_bandwidth - sum(self._allocated_bandwidth.values())
    
    def get_utilization(self) -> float:
        """Get bandwidth utilization percentage."""
        with self._lock:
            used = sum(self._allocated_bandwidth.values())
            return (used / self._total_bandwidth) * 100.0 if self._total_bandwidth > 0 else 0.0


class TransferQueue(ITransferQueue):
    """
    Manages pending memory transfers with priority scheduling and bandwidth allocation.
    
    This queue implements intelligent scheduling algorithms to optimize transfer throughput
    while respecting priority levels and bandwidth constraints.
    """
    
    def __init__(self, 
                 config: Optional[QueueConfiguration] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the transfer queue."""
        self._config = config or QueueConfiguration()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("transfer_queue")
        self._validation_engine = ValidationEngine()
        
        # Queue management
        self._lock = threading.RLock()
        self._queue: List[QueuedTransfer] = []  # Priority queue
        self._active_transfers: Dict[str, QueuedTransfer] = {}
        self._completed_transfers: List[Tuple[QueuedTransfer, TransferResult]] = []
        
        # Status and control
        self._status = QueueStatus.IDLE
        self._shutdown_event = asyncio.Event()
        self._processing_task: Optional[asyncio.Task] = None
        
        # Scheduling and bandwidth management
        self._scheduler = TransferScheduler(self._config)
        self._bandwidth_allocator = BandwidthAllocator(self._config)
        
        # Metrics
        self._metrics = QueueMetrics()
        
        self._logger.info("Transfer queue initialized")

    async def initialize(self) -> bool:
        """Initialize the transfer queue."""
        try:
            self._logger.info("Initializing transfer queue...")

            # Start processing task
            self._processing_task = asyncio.create_task(self._processing_loop())

            # Set status to active
            with self._lock:
                self._status = QueueStatus.ACTIVE

            self._logger.info("Transfer queue initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Error initializing transfer queue: {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown the transfer queue."""
        try:
            self._logger.info("Shutting down transfer queue...")

            # Set status to draining
            with self._lock:
                self._status = QueueStatus.DRAINING

            # Signal shutdown
            self._shutdown_event.set()

            # Cancel processing task
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass

            # Wait for active transfers to complete
            await self._wait_for_active_transfers()

            with self._lock:
                self._status = QueueStatus.IDLE

            self._logger.info("Transfer queue shutdown complete")

        except Exception as e:
            self._logger.error(f"Error during transfer queue shutdown: {e}")

    async def enqueue_transfer(self, request: TransferRequest) -> str:
        """Enqueue a transfer request."""
        try:
            # Validate request
            if not self._validate_transfer_request(request):
                raise ValueError("Invalid transfer request")

            with self._lock:
                # Check queue size limit
                if len(self._queue) >= self._config.max_queue_size:
                    raise RuntimeError("Transfer queue is full")

                # Calculate priority
                priority = self._scheduler.calculate_priority(request)

                # Create queued transfer
                queued_transfer = QueuedTransfer(
                    transfer_request=request,
                    queue_priority=priority
                )

                # Add to priority queue
                heapq.heappush(self._queue, queued_transfer)

                # Update metrics
                self._metrics.total_queued += 1
                self._metrics.current_queue_size = len(self._queue)

                self._logger.debug(f"Enqueued transfer {request.request_id} with priority {priority}")

                return request.request_id

        except Exception as e:
            self._logger.error(f"Error enqueuing transfer: {e}")
            raise

    async def dequeue_transfer(self, queue_id: str) -> bool:
        """Remove a transfer from the queue."""
        try:
            with self._lock:
                # Find and remove from queue
                for i, queued_transfer in enumerate(self._queue):
                    if queued_transfer.transfer_request.request_id == queue_id:
                        del self._queue[i]
                        heapq.heapify(self._queue)  # Restore heap property
                        self._metrics.current_queue_size = len(self._queue)
                        self._logger.debug(f"Dequeued transfer {queue_id}")
                        return True

                # Check active transfers
                if queue_id in self._active_transfers:
                    # Cannot remove active transfer
                    self._logger.warning(f"Cannot dequeue active transfer {queue_id}")
                    return False

                return False

        except Exception as e:
            self._logger.error(f"Error dequeuing transfer: {e}")
            return False

    async def get_queue_status(self) -> QueueStatus:
        """Get current queue status."""
        with self._lock:
            return self._status

    def get_metrics(self) -> QueueMetrics:
        """Get queue metrics."""
        with self._lock:
            # Calculate current metrics
            current_time = datetime.now(timezone.utc)

            # Calculate average queue time
            if self._completed_transfers:
                total_queue_time = sum(
                    (result.completed_at - queued.queued_at).total_seconds()
                    for queued, result in self._completed_transfers[-100:]  # Last 100
                )
                self._metrics.average_queue_time_seconds = total_queue_time / min(len(self._completed_transfers), 100)

            # Calculate bandwidth utilization
            self._metrics.bandwidth_utilization_percent = self._bandwidth_allocator.get_utilization()

            # Calculate throughput
            if self._completed_transfers:
                recent_transfers = [
                    (queued, result) for queued, result in self._completed_transfers
                    if (current_time - result.completed_at).total_seconds() < 300  # Last 5 minutes
                ]
                if recent_transfers:
                    total_bytes = sum(result.bytes_transferred for _, result in recent_transfers)
                    total_time = 300.0  # 5 minutes
                    self._metrics.throughput_mbps = (total_bytes / (1024 * 1024)) / total_time

            # Update current queue size
            self._metrics.current_queue_size = len(self._queue)
            self._metrics.last_updated = current_time

            return QueueMetrics(
                total_queued=self._metrics.total_queued,
                total_processed=self._metrics.total_processed,
                total_failed=self._metrics.total_failed,
                current_queue_size=self._metrics.current_queue_size,
                average_queue_time_seconds=self._metrics.average_queue_time_seconds,
                average_processing_time_seconds=self._metrics.average_processing_time_seconds,
                bandwidth_utilization_percent=self._metrics.bandwidth_utilization_percent,
                throughput_mbps=self._metrics.throughput_mbps,
                queue_efficiency=self._metrics.queue_efficiency,
                last_updated=self._metrics.last_updated
            )

    # Private helper methods

    async def _processing_loop(self) -> None:
        """Main processing loop for the transfer queue."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    await self._process_queue()
                    await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                except Exception as e:
                    self._logger.error(f"Error in processing loop: {e}")
                    await asyncio.sleep(1.0)  # Longer delay on error

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Fatal error in processing loop: {e}")
            with self._lock:
                self._status = QueueStatus.ERROR

    async def _process_queue(self) -> None:
        """Process pending transfers in the queue."""
        with self._lock:
            # Check if we can start new transfers
            if len(self._active_transfers) >= self._config.max_concurrent_transfers:
                return

            if not self._queue:
                return

            # Get next transfer
            queued_transfer = heapq.heappop(self._queue)
            self._metrics.current_queue_size = len(self._queue)

        # Start the transfer
        await self._start_transfer(queued_transfer)

    async def _start_transfer(self, queued_transfer: QueuedTransfer) -> None:
        """Start a queued transfer."""
        try:
            transfer_id = queued_transfer.transfer_request.request_id

            # Allocate bandwidth
            available_bandwidth = self._bandwidth_allocator.get_available_bandwidth()
            allocated_bandwidth = self._scheduler.allocate_bandwidth(queued_transfer, available_bandwidth)

            if allocated_bandwidth <= 0:
                # No bandwidth available, requeue
                with self._lock:
                    heapq.heappush(self._queue, queued_transfer)
                    self._metrics.current_queue_size = len(self._queue)
                return

            # Update queued transfer
            queued_transfer.bandwidth_allocation = allocated_bandwidth
            queued_transfer.scheduled_at = datetime.now(timezone.utc)
            queued_transfer.estimated_completion_time = self._scheduler.estimate_completion_time(queued_transfer)

            # Add to active transfers
            with self._lock:
                self._active_transfers[transfer_id] = queued_transfer

            # Allocate bandwidth
            self._bandwidth_allocator.allocate(transfer_id, allocated_bandwidth)

            # Start transfer task
            task = asyncio.create_task(self._execute_transfer(queued_transfer))

            self._logger.debug(f"Started transfer {transfer_id} with {allocated_bandwidth:.1f} MB/s")

        except Exception as e:
            self._logger.error(f"Error starting transfer: {e}")

    async def _execute_transfer(self, queued_transfer: QueuedTransfer) -> None:
        """Execute a transfer."""
        transfer_id = queued_transfer.transfer_request.request_id
        start_time = time.time()

        try:
            # Simulate transfer execution
            # In real implementation, this would call the bridge controller
            await self._simulate_transfer(queued_transfer)

            # Create successful result
            result = TransferResult(
                request_id=transfer_id,
                status=TransferStatus.COMPLETED,
                source_tier=queued_transfer.transfer_request.source_tier,
                target_tier=queued_transfer.transfer_request.target_tier,
                bytes_transferred=queued_transfer.transfer_request.size_bytes,
                transfer_time_seconds=time.time() - start_time,
                bandwidth_mbps=queued_transfer.bandwidth_allocation
            )

            # Update metrics
            self._update_transfer_metrics(queued_transfer, result, True)

        except Exception as e:
            self._logger.error(f"Transfer {transfer_id} failed: {e}")

            # Check if we should retry
            if queued_transfer.retry_count < queued_transfer.max_retries:
                queued_transfer.retry_count += 1
                await asyncio.sleep(self._config.retry_delay_seconds)

                # Requeue for retry
                with self._lock:
                    heapq.heappush(self._queue, queued_transfer)
                    self._metrics.current_queue_size = len(self._queue)
            else:
                # Create failed result
                result = TransferResult(
                    request_id=transfer_id,
                    status=TransferStatus.FAILED,
                    source_tier=queued_transfer.transfer_request.source_tier,
                    target_tier=queued_transfer.transfer_request.target_tier,
                    bytes_transferred=0,
                    transfer_time_seconds=time.time() - start_time,
                    bandwidth_mbps=0.0,
                    error_message=str(e)
                )

                # Update metrics
                self._update_transfer_metrics(queued_transfer, result, False)

        finally:
            # Clean up
            with self._lock:
                self._active_transfers.pop(transfer_id, None)

            # Deallocate bandwidth
            self._bandwidth_allocator.deallocate(transfer_id)

    async def _simulate_transfer(self, queued_transfer: QueuedTransfer) -> None:
        """Simulate transfer execution."""
        # Calculate transfer time based on size and bandwidth
        size_mb = queued_transfer.transfer_request.size_bytes / (1024 * 1024)
        bandwidth = max(queued_transfer.bandwidth_allocation, 1.0)
        transfer_time = size_mb / bandwidth

        # Simulate the transfer with progress updates
        steps = 10
        step_time = transfer_time / steps

        for i in range(steps):
            if self._shutdown_event.is_set():
                raise asyncio.CancelledError("Transfer cancelled due to shutdown")

            await asyncio.sleep(min(step_time, 0.1))  # Cap simulation time

    def _validate_transfer_request(self, request: TransferRequest) -> bool:
        """Validate a transfer request."""
        try:
            if not request.request_id:
                return False
            if request.size_bytes <= 0:
                return False
            if request.source_tier == request.target_tier:
                return False
            return True
        except Exception:
            return False

    async def _wait_for_active_transfers(self) -> None:
        """Wait for all active transfers to complete."""
        timeout = 30.0
        start_time = time.time()

        while self._active_transfers and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)

        if self._active_transfers:
            self._logger.warning(f"Timeout waiting for {len(self._active_transfers)} active transfers")

    def _update_transfer_metrics(self, queued_transfer: QueuedTransfer,
                               result: TransferResult, success: bool) -> None:
        """Update transfer metrics."""
        with self._lock:
            self._metrics.total_processed += 1

            if success:
                # Update processing time
                processing_time = (result.completed_at - queued_transfer.scheduled_at).total_seconds()
                total_processed = self._metrics.total_processed
                self._metrics.average_processing_time_seconds = (
                    (self._metrics.average_processing_time_seconds * (total_processed - 1) +
                     processing_time) / total_processed
                )
            else:
                self._metrics.total_failed += 1

            # Store completed transfer
            self._completed_transfers.append((queued_transfer, result))
            if len(self._completed_transfers) > 1000:
                self._completed_transfers.pop(0)

            # Calculate queue efficiency
            if self._metrics.total_queued > 0:
                self._metrics.queue_efficiency = (
                    (self._metrics.total_processed - self._metrics.total_failed) /
                    self._metrics.total_queued
                ) * 100.0
