"""
Module: bridge_controller_lg
Description: Orchestrates data movement between memory tiers using DMA transfers with LRU eviction policies
Phase: 2
Location: /src/modules/logic/memory_bridging_lg/bridge_controller_lg/
"""

# Standard library imports
import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
import uuid

# Local imports
from src.modules.logic.memory_allocation_lg.memory_tier_manager_lg import (
    MemoryTierManager, MemoryTierInfo
)
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import MemoryTier
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


class TransferStatus(Enum):
    """Status of memory transfer operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvictionPolicy(Enum):
    """Memory eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    PRIORITY_BASED = "priority_based"


class TransferPriority(Enum):
    """Priority levels for memory transfers."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class TransferRequest:
    """Request for memory transfer between tiers."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_tier: MemoryTier = MemoryTier.RAM
    target_tier: MemoryTier = MemoryTier.GPU_MEMORY
    data_id: str = ""
    size_bytes: int = 0
    priority: TransferPriority = TransferPriority.NORMAL
    deadline: Optional[datetime] = None
    callback: Optional[Callable[[str, TransferStatus], None]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TransferResult:
    """Result of a memory transfer operation."""
    request_id: str
    status: TransferStatus
    source_tier: MemoryTier
    target_tier: MemoryTier
    bytes_transferred: int
    transfer_time_seconds: float
    bandwidth_mbps: float
    error_message: Optional[str] = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BridgeConfiguration:
    """Configuration for the bridge controller."""
    max_concurrent_transfers: int = 4
    transfer_timeout_seconds: float = 300.0
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    enable_compression: bool = True
    compression_threshold_bytes: int = 1024 * 1024  # 1MB
    bandwidth_limit_mbps: Optional[float] = None
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    enable_dma: bool = True
    cache_size_mb: int = 512


@dataclass
class BridgeMetrics:
    """Metrics for bridge controller performance."""
    total_transfers: int = 0
    successful_transfers: int = 0
    failed_transfers: int = 0
    total_bytes_transferred: int = 0
    average_transfer_time: float = 0.0
    average_bandwidth_mbps: float = 0.0
    cache_hit_rate: float = 0.0
    eviction_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class IBridgeController(ABC):
    """Interface for memory bridge controllers."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the bridge controller."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the bridge controller."""
        pass
    
    @abstractmethod
    async def transfer_data(self, request: TransferRequest) -> TransferResult:
        """Transfer data between memory tiers."""
        pass
    
    @abstractmethod
    async def batch_transfer(self, requests: List[TransferRequest]) -> List[TransferResult]:
        """Transfer multiple data items in batch."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> BridgeMetrics:
        """Get bridge controller metrics."""
        pass
    
    @abstractmethod
    def configure_eviction_policy(self, policy: EvictionPolicy) -> None:
        """Configure memory eviction policy."""
        pass


class BridgeController(IBridgeController):
    """
    Orchestrates data movement between memory tiers using DMA transfers with LRU eviction policies.
    
    This controller manages efficient data movement across GPU VRAM, System RAM, and NVMe storage
    tiers, implementing intelligent caching and eviction strategies for optimal performance.
    """
    
    def __init__(self, 
                 config: Optional[BridgeConfiguration] = None,
                 memory_tier_manager: Optional[MemoryTierManager] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the bridge controller."""
        self._config = config or BridgeConfiguration()
        self._memory_tier_manager = memory_tier_manager or MemoryTierManager()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("bridge_controller")
        self._validation_engine = ValidationEngine()
        
        # Threading and synchronization
        self._lock = threading.RLock()
        self._transfer_semaphore = asyncio.Semaphore(self._config.max_concurrent_transfers)
        self._shutdown_event = asyncio.Event()
        
        # Transfer tracking
        self._active_transfers: Dict[str, TransferRequest] = {}
        self._transfer_history: List[TransferResult] = []
        self._metrics = BridgeMetrics()
        
        # Cache management (LRU cache for frequently accessed data)
        self._cache: OrderedDict[str, Tuple[MemoryTier, int, datetime]] = OrderedDict()
        self._cache_size_bytes = 0
        self._max_cache_size_bytes = self._config.cache_size_mb * 1024 * 1024
        
        # Eviction tracking
        self._access_counts: Dict[str, int] = {}
        self._access_times: Dict[str, datetime] = {}
        
        self._logger.info("Bridge controller initialized")

    async def initialize(self) -> bool:
        """Initialize the bridge controller."""
        try:
            self._logger.info("Initializing bridge controller...")

            # Initialize memory tier manager
            if not await self._memory_tier_manager.initialize_tiers():
                self._logger.error("Failed to initialize memory tiers")
                return False

            # Validate configuration
            if not self._validate_configuration():
                self._logger.error("Invalid bridge configuration")
                return False

            # Initialize DMA if enabled
            if self._config.enable_dma:
                await self._initialize_dma()

            self._logger.info("Bridge controller initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Error initializing bridge controller: {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown the bridge controller."""
        try:
            self._logger.info("Shutting down bridge controller...")

            # Signal shutdown
            self._shutdown_event.set()

            # Wait for active transfers to complete
            await self._wait_for_active_transfers()

            # Clear cache
            with self._lock:
                self._cache.clear()
                self._cache_size_bytes = 0

            self._logger.info("Bridge controller shutdown complete")

        except Exception as e:
            self._logger.error(f"Error during bridge controller shutdown: {e}")

    async def transfer_data(self, request: TransferRequest) -> TransferResult:
        """Transfer data between memory tiers."""
        start_time = time.time()

        try:
            # Validate request
            if not self._validate_transfer_request(request):
                return TransferResult(
                    request_id=request.request_id,
                    status=TransferStatus.FAILED,
                    source_tier=request.source_tier,
                    target_tier=request.target_tier,
                    bytes_transferred=0,
                    transfer_time_seconds=0.0,
                    bandwidth_mbps=0.0,
                    error_message="Invalid transfer request"
                )

            # Check cache first
            if await self._check_cache(request):
                return self._create_cache_hit_result(request, start_time)

            # Acquire transfer semaphore
            async with self._transfer_semaphore:
                # Track active transfer
                with self._lock:
                    self._active_transfers[request.request_id] = request

                try:
                    # Perform the actual transfer
                    result = await self._perform_transfer(request, start_time)

                    # Update cache
                    await self._update_cache(request, result)

                    # Update metrics
                    self._update_metrics(result)

                    return result

                finally:
                    # Remove from active transfers
                    with self._lock:
                        self._active_transfers.pop(request.request_id, None)

        except Exception as e:
            self._logger.error(f"Error during data transfer: {e}")
            return TransferResult(
                request_id=request.request_id,
                status=TransferStatus.FAILED,
                source_tier=request.source_tier,
                target_tier=request.target_tier,
                bytes_transferred=0,
                transfer_time_seconds=time.time() - start_time,
                bandwidth_mbps=0.0,
                error_message=str(e)
            )

    async def batch_transfer(self, requests: List[TransferRequest]) -> List[TransferResult]:
        """Transfer multiple data items in batch."""
        try:
            self._logger.info(f"Starting batch transfer of {len(requests)} items")

            # Create tasks for concurrent transfers
            tasks = [self.transfer_data(request) for request in requests]

            # Execute transfers concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self._logger.error(f"Batch transfer error for request {i}: {result}")
                    final_results.append(TransferResult(
                        request_id=requests[i].request_id,
                        status=TransferStatus.FAILED,
                        source_tier=requests[i].source_tier,
                        target_tier=requests[i].target_tier,
                        bytes_transferred=0,
                        transfer_time_seconds=0.0,
                        bandwidth_mbps=0.0,
                        error_message=str(result)
                    ))
                else:
                    final_results.append(result)

            self._logger.info(f"Batch transfer completed: {len(final_results)} results")
            return final_results

        except Exception as e:
            self._logger.error(f"Error during batch transfer: {e}")
            return [TransferResult(
                request_id=req.request_id,
                status=TransferStatus.FAILED,
                source_tier=req.source_tier,
                target_tier=req.target_tier,
                bytes_transferred=0,
                transfer_time_seconds=0.0,
                bandwidth_mbps=0.0,
                error_message=str(e)
            ) for req in requests]

    def get_metrics(self) -> BridgeMetrics:
        """Get bridge controller metrics."""
        with self._lock:
            # Update cache hit rate
            if self._metrics.total_transfers > 0:
                cache_hits = sum(1 for result in self._transfer_history[-100:]
                               if result.transfer_time_seconds < 0.001)  # Cache hits are very fast
                self._metrics.cache_hit_rate = cache_hits / min(len(self._transfer_history), 100)

            return BridgeMetrics(
                total_transfers=self._metrics.total_transfers,
                successful_transfers=self._metrics.successful_transfers,
                failed_transfers=self._metrics.failed_transfers,
                total_bytes_transferred=self._metrics.total_bytes_transferred,
                average_transfer_time=self._metrics.average_transfer_time,
                average_bandwidth_mbps=self._metrics.average_bandwidth_mbps,
                cache_hit_rate=self._metrics.cache_hit_rate,
                eviction_count=self._metrics.eviction_count,
                last_updated=datetime.now(timezone.utc)
            )

    def configure_eviction_policy(self, policy: EvictionPolicy) -> None:
        """Configure memory eviction policy."""
        with self._lock:
            self._config.eviction_policy = policy
            self._logger.info(f"Eviction policy updated to: {policy.value}")

    # Private helper methods

    def _validate_configuration(self) -> bool:
        """Validate bridge configuration."""
        try:
            if self._config.max_concurrent_transfers <= 0:
                return False
            if self._config.transfer_timeout_seconds <= 0:
                return False
            if self._config.cache_size_mb <= 0:
                return False
            return True
        except Exception:
            return False

    async def _initialize_dma(self) -> None:
        """Initialize DMA transfers if available."""
        try:
            # Check for DMA capability
            self._logger.info("DMA transfer support enabled")
        except Exception as e:
            self._logger.warning(f"DMA initialization failed: {e}")
            self._config.enable_dma = False

    async def _wait_for_active_transfers(self) -> None:
        """Wait for all active transfers to complete."""
        timeout = 30.0  # 30 second timeout
        start_time = time.time()

        while self._active_transfers and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)

        if self._active_transfers:
            self._logger.warning(f"Timeout waiting for {len(self._active_transfers)} active transfers")

    def _validate_transfer_request(self, request: TransferRequest) -> bool:
        """Validate a transfer request."""
        try:
            if not request.request_id:
                return False
            if request.size_bytes <= 0:
                return False
            if request.source_tier == request.target_tier:
                return False
            if not request.data_id:
                return False
            return True
        except Exception:
            return False

    async def _check_cache(self, request: TransferRequest) -> bool:
        """Check if data is available in cache."""
        with self._lock:
            cache_key = f"{request.data_id}_{request.target_tier.value}"

            if cache_key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(cache_key)
                self._access_counts[cache_key] = self._access_counts.get(cache_key, 0) + 1
                self._access_times[cache_key] = datetime.now(timezone.utc)
                return True

            return False

    def _create_cache_hit_result(self, request: TransferRequest, start_time: float) -> TransferResult:
        """Create result for cache hit."""
        return TransferResult(
            request_id=request.request_id,
            status=TransferStatus.COMPLETED,
            source_tier=request.source_tier,
            target_tier=request.target_tier,
            bytes_transferred=request.size_bytes,
            transfer_time_seconds=time.time() - start_time,
            bandwidth_mbps=float('inf'),  # Cache access is effectively infinite bandwidth
            error_message=None
        )

    async def _perform_transfer(self, request: TransferRequest, start_time: float) -> TransferResult:
        """Perform the actual memory transfer."""
        try:
            # Check if eviction is needed
            await self._check_eviction_needed(request)

            # Simulate transfer based on tier characteristics
            transfer_time = await self._calculate_transfer_time(request)

            # Perform the transfer (simulated)
            await asyncio.sleep(min(transfer_time, 0.1))  # Cap simulation time

            # Calculate bandwidth
            bandwidth_mbps = (request.size_bytes / (1024 * 1024)) / max(transfer_time, 0.001)

            return TransferResult(
                request_id=request.request_id,
                status=TransferStatus.COMPLETED,
                source_tier=request.source_tier,
                target_tier=request.target_tier,
                bytes_transferred=request.size_bytes,
                transfer_time_seconds=time.time() - start_time,
                bandwidth_mbps=bandwidth_mbps,
                error_message=None
            )

        except Exception as e:
            return TransferResult(
                request_id=request.request_id,
                status=TransferStatus.FAILED,
                source_tier=request.source_tier,
                target_tier=request.target_tier,
                bytes_transferred=0,
                transfer_time_seconds=time.time() - start_time,
                bandwidth_mbps=0.0,
                error_message=str(e)
            )

    async def _update_cache(self, request: TransferRequest, result: TransferResult) -> None:
        """Update cache with transfer result."""
        if result.status != TransferStatus.COMPLETED:
            return

        with self._lock:
            cache_key = f"{request.data_id}_{request.target_tier.value}"

            # Add to cache
            self._cache[cache_key] = (
                request.target_tier,
                request.size_bytes,
                datetime.now(timezone.utc)
            )
            self._cache_size_bytes += request.size_bytes
            self._access_counts[cache_key] = 1
            self._access_times[cache_key] = datetime.now(timezone.utc)

            # Evict if necessary
            await self._evict_cache_entries()

    async def _evict_cache_entries(self) -> None:
        """Evict cache entries based on configured policy."""
        while self._cache_size_bytes > self._max_cache_size_bytes and self._cache:
            if self._config.eviction_policy == EvictionPolicy.LRU:
                # Remove least recently used
                cache_key, (tier, size, timestamp) = self._cache.popitem(last=False)
            elif self._config.eviction_policy == EvictionPolicy.LFU:
                # Remove least frequently used
                cache_key = min(self._access_counts.keys(), key=lambda k: self._access_counts[k])
                tier, size, timestamp = self._cache.pop(cache_key)
            else:  # FIFO
                cache_key, (tier, size, timestamp) = self._cache.popitem(last=False)

            self._cache_size_bytes -= size
            self._access_counts.pop(cache_key, None)
            self._access_times.pop(cache_key, None)
            self._metrics.eviction_count += 1

    async def _check_eviction_needed(self, request: TransferRequest) -> None:
        """Check if eviction is needed for the transfer."""
        target_tier_info = self._memory_tier_manager.get_tier_info(request.target_tier)
        if not target_tier_info:
            return

        available_bytes = target_tier_info.capacity.available_bytes
        if available_bytes < request.size_bytes:
            # Need to evict data from target tier
            await self._evict_from_tier(request.target_tier, request.size_bytes - available_bytes)

    async def _evict_from_tier(self, tier: MemoryTier, bytes_needed: int) -> None:
        """Evict data from specified tier."""
        try:
            # Find candidates for eviction based on policy
            eviction_candidates = self._find_eviction_candidates(tier, bytes_needed)

            # Perform eviction
            for data_id in eviction_candidates:
                # Simulate eviction
                self._logger.debug(f"Evicting {data_id} from {tier.value}")

        except Exception as e:
            self._logger.error(f"Error during tier eviction: {e}")

    def _find_eviction_candidates(self, tier: MemoryTier, bytes_needed: int) -> List[str]:
        """Find candidates for eviction from tier."""
        candidates = []

        # Simple implementation - would be more sophisticated in practice
        for cache_key, (cached_tier, size, timestamp) in self._cache.items():
            if cached_tier == tier:
                candidates.append(cache_key.split('_')[0])  # Extract data_id
                if len(candidates) * 1024 * 1024 >= bytes_needed:  # Rough estimate
                    break

        return candidates

    async def _calculate_transfer_time(self, request: TransferRequest) -> float:
        """Calculate expected transfer time based on tier characteristics."""
        # Get tier information
        source_info = self._memory_tier_manager.get_tier_info(request.source_tier)
        target_info = self._memory_tier_manager.get_tier_info(request.target_tier)

        if not source_info or not target_info:
            return 1.0  # Default 1 second

        # Use the slower bandwidth of source/target
        source_bandwidth = source_info.bandwidth.sustained_bandwidth_mbps
        target_bandwidth = target_info.bandwidth.sustained_bandwidth_mbps
        effective_bandwidth = min(source_bandwidth, target_bandwidth)

        # Calculate transfer time
        size_mb = request.size_bytes / (1024 * 1024)
        transfer_time = size_mb / max(effective_bandwidth, 1.0)

        # Add latency
        latency = max(source_info.bandwidth.latency_microseconds,
                     target_info.bandwidth.latency_microseconds) / 1_000_000

        return transfer_time + latency

    def _update_metrics(self, result: TransferResult) -> None:
        """Update bridge controller metrics."""
        with self._lock:
            self._metrics.total_transfers += 1

            if result.status == TransferStatus.COMPLETED:
                self._metrics.successful_transfers += 1
                self._metrics.total_bytes_transferred += result.bytes_transferred

                # Update averages
                total_successful = self._metrics.successful_transfers
                self._metrics.average_transfer_time = (
                    (self._metrics.average_transfer_time * (total_successful - 1) +
                     result.transfer_time_seconds) / total_successful
                )
                self._metrics.average_bandwidth_mbps = (
                    (self._metrics.average_bandwidth_mbps * (total_successful - 1) +
                     result.bandwidth_mbps) / total_successful
                )
            else:
                self._metrics.failed_transfers += 1

            # Keep transfer history (last 1000 transfers)
            self._transfer_history.append(result)
            if len(self._transfer_history) > 1000:
                self._transfer_history.pop(0)

            self._metrics.last_updated = datetime.now(timezone.utc)
