"""
Module: memory_pool_allocator_lg
Description: Provides pre-allocated memory pools to reduce allocation overhead and improve performance
Phase: 2
Location: /src/modules/logic/performance_optimization_lg/memory_pool_allocator_lg/
"""

# Standard library imports
import asyncio
import logging
import math
import threading
import time
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable, Set, Union
from collections import deque, defaultdict

# Local imports
from src.modules.logic.resource_monitor_lg import ResourceMetrics, MemoryMetrics
from src.modules.logic.logging_infrastructure_lg import get_logger


class PoolType(Enum):
    """Memory pool types."""
    SMALL_OBJECTS = "SMALL_OBJECTS"      # < 1KB
    MEDIUM_OBJECTS = "MEDIUM_OBJECTS"    # 1KB - 1MB
    LARGE_OBJECTS = "LARGE_OBJECTS"      # 1MB - 100MB
    HUGE_OBJECTS = "HUGE_OBJECTS"        # > 100MB
    TENSOR_BUFFERS = "TENSOR_BUFFERS"    # ML tensor storage
    TEMPORARY_BUFFERS = "TEMPORARY_BUFFERS"  # Short-lived allocations


class AllocationStrategy(Enum):
    """Memory allocation strategies."""
    FIRST_FIT = "FIRST_FIT"
    BEST_FIT = "BEST_FIT"
    WORST_FIT = "WORST_FIT"
    BUDDY_SYSTEM = "BUDDY_SYSTEM"
    SLAB_ALLOCATION = "SLAB_ALLOCATION"


class PoolStatus(Enum):
    """Memory pool status."""
    ACTIVE = "ACTIVE"
    FULL = "FULL"
    EXPANDING = "EXPANDING"
    SHRINKING = "SHRINKING"
    DISABLED = "DISABLED"


@dataclass
class PoolConfiguration:
    """Memory pool configuration."""
    pool_type: PoolType
    initial_size_mb: float
    max_size_mb: float
    block_size_bytes: int
    growth_factor: float = 1.5
    shrink_threshold: float = 0.3
    max_free_blocks: int = 1000
    enable_auto_expansion: bool = True
    enable_auto_shrinking: bool = True
    allocation_strategy: AllocationStrategy = AllocationStrategy.FIRST_FIT


@dataclass
class MemoryBlock:
    """Memory block representation."""
    block_id: str
    size_bytes: int
    offset: int
    is_free: bool
    allocated_at: Optional[datetime] = None
    freed_at: Optional[datetime] = None
    owner_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PoolStatistics:
    """Memory pool statistics."""
    pool_type: PoolType
    total_size_mb: float
    allocated_mb: float
    free_mb: float
    utilization_percent: float
    total_blocks: int
    allocated_blocks: int
    free_blocks: int
    allocation_count: int
    deallocation_count: int
    fragmentation_percent: float
    average_allocation_time_ms: float


@dataclass
class AllocationRequest:
    """Memory allocation request."""
    size_bytes: int
    alignment: int = 8
    pool_type: Optional[PoolType] = None
    owner_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IMemoryPoolAllocator(ABC):
    """Interface for memory pool allocation systems."""
    
    @abstractmethod
    def allocate(self, request: AllocationRequest) -> Optional[str]:
        """Allocate memory from appropriate pool."""
        pass
    
    @abstractmethod
    def deallocate(self, block_id: str) -> bool:
        """Deallocate memory block."""
        pass
    
    @abstractmethod
    def get_pool_statistics(self, pool_type: PoolType) -> PoolStatistics:
        """Get statistics for a specific pool."""
        pass
    
    @abstractmethod
    def defragment_pool(self, pool_type: PoolType) -> bool:
        """Defragment a memory pool."""
        pass


class MemoryPool:
    """Individual memory pool implementation."""
    
    def __init__(self, config: PoolConfiguration):
        """Initialize memory pool."""
        self._config = config
        self._logger = get_logger(f"{__name__}.{config.pool_type.value}")
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Pool state
        self._status = PoolStatus.ACTIVE
        self._total_size = int(config.initial_size_mb * 1024 * 1024)
        self._memory_buffer = bytearray(self._total_size)
        
        # Block management
        self._blocks: Dict[str, MemoryBlock] = {}
        self._free_blocks: List[MemoryBlock] = []
        self._allocated_blocks: Dict[str, MemoryBlock] = {}
        
        # Statistics
        self._allocation_count = 0
        self._deallocation_count = 0
        self._allocation_times: deque = deque(maxlen=1000)
        
        # Initialize with one large free block
        initial_block = MemoryBlock(
            block_id=f"free_0",
            size_bytes=self._total_size,
            offset=0,
            is_free=True
        )
        self._blocks[initial_block.block_id] = initial_block
        self._free_blocks.append(initial_block)
        
        self._logger.info(f"Memory pool initialized: {config.pool_type} ({config.initial_size_mb}MB)")
    
    def allocate(self, request: AllocationRequest) -> Optional[str]:
        """Allocate memory from this pool."""
        start_time = time.time()
        
        try:
            with self._lock:
                if self._status != PoolStatus.ACTIVE:
                    return None
                
                # Find suitable free block
                block = self._find_free_block(request.size_bytes, request.alignment)
                
                if not block:
                    # Try to expand pool if enabled
                    if self._config.enable_auto_expansion:
                        if self._expand_pool(request.size_bytes):
                            block = self._find_free_block(request.size_bytes, request.alignment)
                    
                    if not block:
                        return None
                
                # Split block if necessary
                allocated_block = self._split_block(block, request.size_bytes, request.alignment)
                
                # Update block state
                allocated_block.is_free = False
                allocated_block.allocated_at = datetime.now(timezone.utc)
                allocated_block.owner_id = request.owner_id
                allocated_block.metadata = request.metadata.copy()
                
                # Update tracking
                self._allocated_blocks[allocated_block.block_id] = allocated_block
                if block in self._free_blocks:
                    self._free_blocks.remove(block)
                
                self._allocation_count += 1
                
                # Record timing
                allocation_time = (time.time() - start_time) * 1000
                self._allocation_times.append(allocation_time)
                
                self._logger.debug(f"Allocated {request.size_bytes} bytes (block: {allocated_block.block_id})")
                
                return allocated_block.block_id
                
        except Exception as e:
            self._logger.error(f"Error allocating memory: {e}")
            return None
    
    def deallocate(self, block_id: str) -> bool:
        """Deallocate memory block."""
        try:
            with self._lock:
                if block_id not in self._allocated_blocks:
                    self._logger.warning(f"Block {block_id} not found in allocated blocks")
                    return False
                
                block = self._allocated_blocks[block_id]
                
                # Update block state
                block.is_free = True
                block.freed_at = datetime.now(timezone.utc)
                block.owner_id = None
                block.metadata.clear()
                
                # Update tracking
                del self._allocated_blocks[block_id]
                self._free_blocks.append(block)
                self._deallocation_count += 1
                
                # Try to coalesce with adjacent free blocks
                self._coalesce_free_blocks(block)
                
                self._logger.debug(f"Deallocated block {block_id}")
                
                return True
                
        except Exception as e:
            self._logger.error(f"Error deallocating memory: {e}")
            return False

    def _find_free_block(self, size_bytes: int, alignment: int) -> Optional[MemoryBlock]:
        """Find a suitable free block."""
        try:
            suitable_blocks = [
                block for block in self._free_blocks
                if block.size_bytes >= size_bytes and block.offset % alignment == 0
            ]

            if not suitable_blocks:
                return None

            # Apply allocation strategy
            if self._config.allocation_strategy == AllocationStrategy.FIRST_FIT:
                return suitable_blocks[0]
            elif self._config.allocation_strategy == AllocationStrategy.BEST_FIT:
                return min(suitable_blocks, key=lambda b: b.size_bytes)
            elif self._config.allocation_strategy == AllocationStrategy.WORST_FIT:
                return max(suitable_blocks, key=lambda b: b.size_bytes)
            else:
                return suitable_blocks[0]

        except Exception as e:
            self._logger.error(f"Error finding free block: {e}")
            return None

    def _split_block(self, block: MemoryBlock, size_bytes: int, alignment: int) -> MemoryBlock:
        """Split a block for allocation."""
        try:
            # Calculate aligned size
            aligned_size = ((size_bytes + alignment - 1) // alignment) * alignment

            if block.size_bytes == aligned_size:
                # No split needed
                return block

            # Create new allocated block
            allocated_block = MemoryBlock(
                block_id=f"alloc_{self._allocation_count}",
                size_bytes=aligned_size,
                offset=block.offset,
                is_free=False
            )

            # Update original block (remaining free space)
            block.offset += aligned_size
            block.size_bytes -= aligned_size
            block.block_id = f"free_{len(self._blocks)}"

            # Add blocks to tracking
            self._blocks[allocated_block.block_id] = allocated_block
            self._blocks[block.block_id] = block

            return allocated_block

        except Exception as e:
            self._logger.error(f"Error splitting block: {e}")
            return block

    def _expand_pool(self, required_size: int) -> bool:
        """Expand the memory pool."""
        try:
            current_size_mb = self._total_size / (1024 * 1024)
            if current_size_mb >= self._config.max_size_mb:
                return False

            # Calculate expansion size
            expansion_size = max(
                required_size,
                int(self._total_size * (self._config.growth_factor - 1))
            )

            new_total_size = self._total_size + expansion_size
            max_size_bytes = int(self._config.max_size_mb * 1024 * 1024)

            if new_total_size > max_size_bytes:
                expansion_size = max_size_bytes - self._total_size
                new_total_size = max_size_bytes

            if expansion_size <= 0:
                return False

            # Expand buffer
            self._memory_buffer.extend(bytearray(expansion_size))

            # Create new free block for expanded space
            new_block = MemoryBlock(
                block_id=f"free_expanded_{int(time.time())}",
                size_bytes=expansion_size,
                offset=self._total_size,
                is_free=True
            )

            self._blocks[new_block.block_id] = new_block
            self._free_blocks.append(new_block)
            self._total_size = new_total_size

            self._logger.info(f"Pool expanded by {expansion_size / (1024 * 1024):.2f}MB")
            return True

        except Exception as e:
            self._logger.error(f"Error expanding pool: {e}")
            return False

    def _coalesce_free_blocks(self, block: MemoryBlock) -> None:
        """Coalesce adjacent free blocks."""
        try:
            # Find adjacent blocks
            adjacent_blocks = [
                b for b in self._free_blocks
                if b != block and (
                    b.offset + b.size_bytes == block.offset or
                    block.offset + block.size_bytes == b.offset
                )
            ]

            for adjacent in adjacent_blocks:
                # Merge blocks
                if adjacent.offset < block.offset:
                    # Adjacent block comes before
                    adjacent.size_bytes += block.size_bytes
                    self._free_blocks.remove(block)
                    del self._blocks[block.block_id]
                    block = adjacent
                else:
                    # Adjacent block comes after
                    block.size_bytes += adjacent.size_bytes
                    self._free_blocks.remove(adjacent)
                    del self._blocks[adjacent.block_id]

        except Exception as e:
            self._logger.error(f"Error coalescing free blocks: {e}")

    def get_statistics(self) -> PoolStatistics:
        """Get pool statistics."""
        try:
            with self._lock:
                allocated_size = sum(block.size_bytes for block in self._allocated_blocks.values())
                free_size = sum(block.size_bytes for block in self._free_blocks)

                # Calculate fragmentation
                largest_free_block = max(
                    (block.size_bytes for block in self._free_blocks),
                    default=0
                )
                fragmentation = 0.0
                if free_size > 0:
                    fragmentation = (1 - largest_free_block / free_size) * 100

                # Calculate average allocation time
                avg_allocation_time = 0.0
                if self._allocation_times:
                    avg_allocation_time = sum(self._allocation_times) / len(self._allocation_times)

                return PoolStatistics(
                    pool_type=self._config.pool_type,
                    total_size_mb=self._total_size / (1024 * 1024),
                    allocated_mb=allocated_size / (1024 * 1024),
                    free_mb=free_size / (1024 * 1024),
                    utilization_percent=(allocated_size / self._total_size) * 100,
                    total_blocks=len(self._blocks),
                    allocated_blocks=len(self._allocated_blocks),
                    free_blocks=len(self._free_blocks),
                    allocation_count=self._allocation_count,
                    deallocation_count=self._deallocation_count,
                    fragmentation_percent=fragmentation,
                    average_allocation_time_ms=avg_allocation_time
                )

        except Exception as e:
            self._logger.error(f"Error getting pool statistics: {e}")
            return PoolStatistics(
                pool_type=self._config.pool_type,
                total_size_mb=0.0,
                allocated_mb=0.0,
                free_mb=0.0,
                utilization_percent=0.0,
                total_blocks=0,
                allocated_blocks=0,
                free_blocks=0,
                allocation_count=0,
                deallocation_count=0,
                fragmentation_percent=0.0,
                average_allocation_time_ms=0.0
            )


class MemoryPoolAllocator(IMemoryPoolAllocator):
    """Main memory pool allocator with multiple pool management."""

    def __init__(self, pool_configs: List[PoolConfiguration]):
        """Initialize memory pool allocator."""
        self._logger = get_logger(__name__)

        # Thread safety
        self._lock = threading.RLock()

        # Pool management
        self._pools: Dict[PoolType, MemoryPool] = {}
        self._pool_configs = {config.pool_type: config for config in pool_configs}

        # Initialize pools
        for config in pool_configs:
            self._pools[config.pool_type] = MemoryPool(config)

        # Global statistics
        self._total_allocations = 0
        self._total_deallocations = 0
        self._allocation_history: deque = deque(maxlen=10000)

        # Monitoring
        self._monitoring_enabled = False
        self._monitoring_task: Optional[asyncio.Task] = None

        # Callbacks
        self._allocation_callbacks: List[Callable[[str, AllocationRequest], None]] = []
        self._deallocation_callbacks: List[Callable[[str], None]] = []

        self._logger.info(f"Memory pool allocator initialized with {len(pool_configs)} pools")

    async def start_monitoring(self) -> None:
        """Start pool monitoring."""
        if self._monitoring_enabled:
            self._logger.warning("Pool monitoring already running")
            return

        self._monitoring_enabled = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._logger.info("Pool monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop pool monitoring."""
        if not self._monitoring_enabled:
            return

        self._monitoring_enabled = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self._logger.info("Pool monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main pool monitoring loop."""
        try:
            while self._monitoring_enabled:
                start_time = time.time()

                # Check pool health and perform maintenance
                await self._perform_maintenance()

                # Calculate sleep time (30-second intervals)
                elapsed = time.time() - start_time
                sleep_time = max(0, 30.0 - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._logger.error(f"Error in pool monitoring loop: {e}")

    async def _perform_maintenance(self) -> None:
        """Perform pool maintenance tasks."""
        try:
            for pool_type, pool in self._pools.items():
                stats = pool.get_statistics()

                # Check for high fragmentation
                if stats.fragmentation_percent > 50:
                    self._logger.info(f"High fragmentation in {pool_type}: {stats.fragmentation_percent:.1f}%")
                    # Could trigger defragmentation here

                # Check utilization
                if stats.utilization_percent > 90:
                    self._logger.warning(f"High utilization in {pool_type}: {stats.utilization_percent:.1f}%")

        except Exception as e:
            self._logger.error(f"Error in pool maintenance: {e}")

    def allocate(self, request: AllocationRequest) -> Optional[str]:
        """Allocate memory from appropriate pool."""
        try:
            with self._lock:
                # Determine pool type if not specified
                pool_type = request.pool_type or self._determine_pool_type(request.size_bytes)

                if pool_type not in self._pools:
                    self._logger.error(f"Pool type {pool_type} not available")
                    return None

                # Attempt allocation
                block_id = self._pools[pool_type].allocate(request)

                if block_id:
                    self._total_allocations += 1

                    # Record allocation
                    allocation_record = {
                        'timestamp': datetime.now(timezone.utc),
                        'block_id': block_id,
                        'pool_type': pool_type,
                        'size_bytes': request.size_bytes,
                        'owner_id': request.owner_id
                    }
                    self._allocation_history.append(allocation_record)

                    # Notify callbacks
                    for callback in self._allocation_callbacks:
                        try:
                            callback(block_id, request)
                        except Exception as e:
                            self._logger.error(f"Error in allocation callback: {e}")

                    self._logger.debug(f"Allocated {request.size_bytes} bytes from {pool_type}")

                return block_id

        except Exception as e:
            self._logger.error(f"Error allocating memory: {e}")
            return None

    def deallocate(self, block_id: str) -> bool:
        """Deallocate memory block."""
        try:
            with self._lock:
                # Find which pool contains this block
                for pool_type, pool in self._pools.items():
                    if block_id in pool._allocated_blocks:
                        success = pool.deallocate(block_id)

                        if success:
                            self._total_deallocations += 1

                            # Notify callbacks
                            for callback in self._deallocation_callbacks:
                                try:
                                    callback(block_id)
                                except Exception as e:
                                    self._logger.error(f"Error in deallocation callback: {e}")

                            self._logger.debug(f"Deallocated block {block_id} from {pool_type}")

                        return success

                self._logger.warning(f"Block {block_id} not found in any pool")
                return False

        except Exception as e:
            self._logger.error(f"Error deallocating memory: {e}")
            return False

    def get_pool_statistics(self, pool_type: PoolType) -> PoolStatistics:
        """Get statistics for a specific pool."""
        try:
            if pool_type not in self._pools:
                raise ValueError(f"Pool type {pool_type} not available")

            return self._pools[pool_type].get_statistics()

        except Exception as e:
            self._logger.error(f"Error getting pool statistics: {e}")
            return PoolStatistics(
                pool_type=pool_type,
                total_size_mb=0.0,
                allocated_mb=0.0,
                free_mb=0.0,
                utilization_percent=0.0,
                total_blocks=0,
                allocated_blocks=0,
                free_blocks=0,
                allocation_count=0,
                deallocation_count=0,
                fragmentation_percent=0.0,
                average_allocation_time_ms=0.0
            )

    def defragment_pool(self, pool_type: PoolType) -> bool:
        """Defragment a memory pool."""
        try:
            if pool_type not in self._pools:
                return False

            # This is a simplified defragmentation
            # In a real implementation, this would involve moving allocated blocks
            pool = self._pools[pool_type]

            with pool._lock:
                # Coalesce all adjacent free blocks
                free_blocks = sorted(pool._free_blocks, key=lambda b: b.offset)

                i = 0
                while i < len(free_blocks) - 1:
                    current = free_blocks[i]
                    next_block = free_blocks[i + 1]

                    if current.offset + current.size_bytes == next_block.offset:
                        # Merge blocks
                        current.size_bytes += next_block.size_bytes
                        pool._free_blocks.remove(next_block)
                        del pool._blocks[next_block.block_id]
                        free_blocks.remove(next_block)
                    else:
                        i += 1

                self._logger.info(f"Defragmented pool {pool_type}")
                return True

        except Exception as e:
            self._logger.error(f"Error defragmenting pool: {e}")
            return False

    def _determine_pool_type(self, size_bytes: int) -> PoolType:
        """Determine appropriate pool type for allocation size."""
        if size_bytes < 1024:  # < 1KB
            return PoolType.SMALL_OBJECTS
        elif size_bytes < 1024 * 1024:  # < 1MB
            return PoolType.MEDIUM_OBJECTS
        elif size_bytes < 100 * 1024 * 1024:  # < 100MB
            return PoolType.LARGE_OBJECTS
        else:
            return PoolType.HUGE_OBJECTS

    def get_all_statistics(self) -> Dict[PoolType, PoolStatistics]:
        """Get statistics for all pools."""
        try:
            return {
                pool_type: pool.get_statistics()
                for pool_type, pool in self._pools.items()
            }
        except Exception as e:
            self._logger.error(f"Error getting all statistics: {e}")
            return {}

    def get_global_statistics(self) -> Dict[str, Any]:
        """Get global allocator statistics."""
        try:
            with self._lock:
                total_allocated_mb = sum(
                    stats.allocated_mb
                    for stats in self.get_all_statistics().values()
                )

                total_free_mb = sum(
                    stats.free_mb
                    for stats in self.get_all_statistics().values()
                )

                return {
                    'total_allocations': self._total_allocations,
                    'total_deallocations': self._total_deallocations,
                    'active_allocations': self._total_allocations - self._total_deallocations,
                    'total_allocated_mb': total_allocated_mb,
                    'total_free_mb': total_free_mb,
                    'pool_count': len(self._pools),
                    'allocation_history_size': len(self._allocation_history)
                }

        except Exception as e:
            self._logger.error(f"Error getting global statistics: {e}")
            return {}

    def add_allocation_callback(self, callback: Callable[[str, AllocationRequest], None]) -> None:
        """Add allocation callback."""
        self._allocation_callbacks.append(callback)

    def add_deallocation_callback(self, callback: Callable[[str], None]) -> None:
        """Add deallocation callback."""
        self._deallocation_callbacks.append(callback)

    def create_pool(self, config: PoolConfiguration) -> bool:
        """Create a new memory pool."""
        try:
            with self._lock:
                if config.pool_type in self._pools:
                    self._logger.warning(f"Pool {config.pool_type} already exists")
                    return False

                self._pools[config.pool_type] = MemoryPool(config)
                self._pool_configs[config.pool_type] = config

                self._logger.info(f"Created new pool: {config.pool_type}")
                return True

        except Exception as e:
            self._logger.error(f"Error creating pool: {e}")
            return False

    def remove_pool(self, pool_type: PoolType) -> bool:
        """Remove a memory pool."""
        try:
            with self._lock:
                if pool_type not in self._pools:
                    return False

                pool = self._pools[pool_type]

                # Check if pool has active allocations
                if pool._allocated_blocks:
                    self._logger.warning(f"Cannot remove pool {pool_type} with active allocations")
                    return False

                del self._pools[pool_type]
                del self._pool_configs[pool_type]

                self._logger.info(f"Removed pool: {pool_type}")
                return True

        except Exception as e:
            self._logger.error(f"Error removing pool: {e}")
            return False
