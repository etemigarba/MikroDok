"""
Module: page_manager_lg
Description: Handles 4KB page-level operations for efficient disk-based memory extension
Phase: 2
Location: /src/modules/logic/nvme_virtual_memory_lg/page_manager_lg/
"""

# Standard library imports
import asyncio
import logging
import mmap
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock, RLock
from typing import Dict, List, Optional, Set, Tuple, Union

# Third-party imports
import psutil

# Local imports
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import MemoryTier
from src.modules.logic.memory_allocation_lg.memory_tier_manager_lg import (
    MemoryTierManager, IMemoryTierManager
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


class PageStatus(Enum):
    """Status of memory pages."""
    FREE = "free"
    ALLOCATED = "allocated"
    MAPPED = "mapped"
    DIRTY = "dirty"
    SWAPPED = "swapped"
    LOCKED = "locked"


@dataclass
class PageInfo:
    """Information about a memory page."""
    page_id: int
    virtual_address: int
    physical_address: Optional[int]
    size_bytes: int = 4096
    status: PageStatus = PageStatus.FREE
    reference_count: int = 0
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dirty: bool = False
    locked: bool = False
    metadata: Dict = field(default_factory=dict)


@dataclass
class PageAllocation:
    """Page allocation request and result."""
    allocation_id: str
    requested_pages: int
    allocated_pages: List[PageInfo] = field(default_factory=list)
    total_size_bytes: int = 0
    allocation_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    owner_id: Optional[str] = None


@dataclass
class PageMapping:
    """Virtual to physical page mapping."""
    virtual_page_id: int
    physical_page_id: int
    virtual_address: int
    physical_address: int
    mapping_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_permissions: str = "rw"  # read-write, read-only, etc.


@dataclass
class PageConfiguration:
    """Configuration for page manager."""
    page_size_bytes: int = 4096
    total_pages: int = 1048576  # 4GB worth of 4KB pages
    max_dirty_pages: int = 65536  # 256MB worth of dirty pages
    sync_interval_seconds: float = 30.0
    compression_enabled: bool = True
    prefault_enabled: bool = True
    huge_pages_enabled: bool = False


@dataclass
class PageMetrics:
    """Metrics for page manager performance."""
    total_pages: int = 0
    allocated_pages: int = 0
    free_pages: int = 0
    dirty_pages: int = 0
    swapped_pages: int = 0
    page_faults: int = 0
    page_allocations: int = 0
    page_deallocations: int = 0
    memory_utilization_percent: float = 0.0
    fragmentation_ratio: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PagePool:
    """Pool of pages for efficient allocation."""
    pool_id: str
    page_size_bytes: int
    total_pages: int
    free_pages: Set[int] = field(default_factory=set)
    allocated_pages: Dict[int, PageInfo] = field(default_factory=dict)
    pool_lock: Lock = field(default_factory=Lock)


class IPageManager(ABC):
    """Interface for page managers."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the page manager."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the page manager."""
        pass
    
    @abstractmethod
    async def allocate_pages(self, count: int, owner_id: Optional[str] = None) -> Optional[PageAllocation]:
        """Allocate a number of pages."""
        pass
    
    @abstractmethod
    async def deallocate_pages(self, allocation_id: str) -> bool:
        """Deallocate pages by allocation ID."""
        pass
    
    @abstractmethod
    async def map_page(self, virtual_address: int, physical_address: int) -> Optional[PageMapping]:
        """Map virtual address to physical address."""
        pass
    
    @abstractmethod
    async def unmap_page(self, virtual_address: int) -> bool:
        """Unmap virtual address."""
        pass
    
    @abstractmethod
    def get_page_info(self, page_id: int) -> Optional[PageInfo]:
        """Get information about a specific page."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> PageMetrics:
        """Get page manager metrics."""
        pass


class PageManager(IPageManager):
    """
    Handles 4KB page-level operations for efficient disk-based memory extension.
    
    Provides:
    - Page allocation and deallocation
    - Virtual to physical address mapping
    - Page status tracking and management
    - Memory pool management
    - Page fault handling
    - Dirty page synchronization
    - Memory fragmentation management
    """
    
    def __init__(self, config: PageConfiguration):
        """Initialize page manager with configuration."""
        self._config = config
        self._logger = get_log_manager().get_logger(__name__)
        self._lock = RLock()
        
        # State management
        self._initialized = False
        self._shutdown_requested = False
        
        # Page tracking
        self._pages: Dict[int, PageInfo] = {}
        self._page_mappings: Dict[int, PageMapping] = {}  # virtual_address -> mapping
        self._allocations: Dict[str, PageAllocation] = {}
        
        # Free page management
        self._free_pages: Set[int] = set()
        self._dirty_pages: Set[int] = set()
        
        # Page pools for different sizes
        self._page_pools: Dict[int, PagePool] = {}
        
        # Metrics
        self._metrics = PageMetrics()
        self._allocation_counter = 0
        
        # Background tasks
        self._sync_task: Optional[asyncio.Task] = None
        
        # Memory tier integration
        self._tier_manager: Optional[IMemoryTierManager] = None
        
        self._logger.info(f"Page manager initialized with config: {config}")
    
    async def initialize(self) -> bool:
        """
        Initialize the page manager with page pools and tracking structures.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            with self._lock:
                if self._initialized:
                    return True
                
                # Initialize page pools
                if not self._initialize_page_pools():
                    return False
                
                # Initialize page tracking
                if not self._initialize_page_tracking():
                    return False
                
                # Start background sync task
                self._sync_task = asyncio.create_task(self._sync_dirty_pages())
                
                # Initialize memory tier integration
                self._tier_manager = MemoryTierManager()
                
                self._initialized = True
                self._logger.info("Page manager initialized successfully")
                return True
                
        except Exception as e:
            self._logger.error(f"Error initializing page manager: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown the page manager and cleanup resources."""
        try:
            with self._lock:
                self._shutdown_requested = True
                
                # Cancel background tasks
                if self._sync_task:
                    self._sync_task.cancel()
                    try:
                        await self._sync_task
                    except asyncio.CancelledError:
                        pass
                
                # Sync any remaining dirty pages
                await self._flush_dirty_pages()
                
                # Clear all data structures
                self._pages.clear()
                self._page_mappings.clear()
                self._allocations.clear()
                self._free_pages.clear()
                self._dirty_pages.clear()
                
                self._initialized = False
                self._logger.info("Page manager shutdown completed")
                
        except Exception as e:
            self._logger.error(f"Error during page manager shutdown: {e}")
    
    async def allocate_pages(self, count: int, owner_id: Optional[str] = None) -> Optional[PageAllocation]:
        """
        Allocate a number of pages.
        
        Args:
            count: Number of pages to allocate
            owner_id: Optional owner identifier
            
        Returns:
            PageAllocation: Allocation result or None if failed
        """
        try:
            with self._lock:
                if self._shutdown_requested:
                    return None
                
                # Check if enough free pages available
                if len(self._free_pages) < count:
                    self._logger.warning(f"Insufficient free pages: requested={count}, available={len(self._free_pages)}")
                    return None
                
                # Generate allocation ID
                self._allocation_counter += 1
                allocation_id = f"alloc_{self._allocation_counter}_{int(datetime.now(timezone.utc).timestamp())}"
                
                # Allocate pages
                allocated_pages = []
                allocated_page_ids = []
                
                for _ in range(count):
                    if not self._free_pages:
                        break
                    
                    page_id = self._free_pages.pop()
                    page_info = self._pages[page_id]
                    
                    # Update page status
                    page_info.status = PageStatus.ALLOCATED
                    page_info.last_accessed = datetime.now(timezone.utc)
                    page_info.reference_count = 1
                    
                    allocated_pages.append(page_info)
                    allocated_page_ids.append(page_id)
                
                # Create allocation record
                allocation = PageAllocation(
                    allocation_id=allocation_id,
                    requested_pages=count,
                    allocated_pages=allocated_pages,
                    total_size_bytes=len(allocated_pages) * self._config.page_size_bytes,
                    owner_id=owner_id
                )
                
                self._allocations[allocation_id] = allocation
                
                # Update metrics
                self._metrics.page_allocations += 1
                self._metrics.allocated_pages += len(allocated_pages)
                self._metrics.free_pages -= len(allocated_pages)
                self._update_utilization_metrics()
                
                self._logger.debug(f"Allocated {len(allocated_pages)} pages: {allocation_id}")
                return allocation
                
        except Exception as e:
            self._logger.error(f"Error allocating pages: {e}")
            return None

    async def deallocate_pages(self, allocation_id: str) -> bool:
        """
        Deallocate pages by allocation ID.

        Args:
            allocation_id: ID of the allocation to deallocate

        Returns:
            bool: True if deallocation successful
        """
        try:
            with self._lock:
                if allocation_id not in self._allocations:
                    self._logger.warning(f"Allocation not found: {allocation_id}")
                    return False

                allocation = self._allocations[allocation_id]

                # Deallocate each page
                for page_info in allocation.allocated_pages:
                    # Update page status
                    page_info.status = PageStatus.FREE
                    page_info.reference_count = 0
                    page_info.dirty = False
                    page_info.locked = False

                    # Add back to free pages
                    self._free_pages.add(page_info.page_id)

                    # Remove from dirty pages if present
                    self._dirty_pages.discard(page_info.page_id)

                # Remove allocation record
                del self._allocations[allocation_id]

                # Update metrics
                self._metrics.page_deallocations += 1
                self._metrics.allocated_pages -= len(allocation.allocated_pages)
                self._metrics.free_pages += len(allocation.allocated_pages)
                self._update_utilization_metrics()

                self._logger.debug(f"Deallocated {len(allocation.allocated_pages)} pages: {allocation_id}")
                return True

        except Exception as e:
            self._logger.error(f"Error deallocating pages: {e}")
            return False

    async def map_page(self, virtual_address: int, physical_address: int) -> Optional[PageMapping]:
        """
        Map virtual address to physical address.

        Args:
            virtual_address: Virtual memory address
            physical_address: Physical memory address

        Returns:
            PageMapping: Mapping result or None if failed
        """
        try:
            with self._lock:
                # Validate addresses are page-aligned
                if virtual_address % self._config.page_size_bytes != 0:
                    self._logger.error(f"Virtual address not page-aligned: {virtual_address}")
                    return None

                if physical_address % self._config.page_size_bytes != 0:
                    self._logger.error(f"Physical address not page-aligned: {physical_address}")
                    return None

                # Check if virtual address is already mapped
                if virtual_address in self._page_mappings:
                    self._logger.warning(f"Virtual address already mapped: {virtual_address}")
                    return None

                # Calculate page IDs
                virtual_page_id = virtual_address // self._config.page_size_bytes
                physical_page_id = physical_address // self._config.page_size_bytes

                # Create mapping
                mapping = PageMapping(
                    virtual_page_id=virtual_page_id,
                    physical_page_id=physical_page_id,
                    virtual_address=virtual_address,
                    physical_address=physical_address
                )

                self._page_mappings[virtual_address] = mapping

                # Update page status if it exists
                if virtual_page_id in self._pages:
                    self._pages[virtual_page_id].status = PageStatus.MAPPED
                    self._pages[virtual_page_id].physical_address = physical_address

                self._logger.debug(f"Mapped page: virtual={virtual_address:x} -> physical={physical_address:x}")
                return mapping

        except Exception as e:
            self._logger.error(f"Error mapping page: {e}")
            return None

    async def unmap_page(self, virtual_address: int) -> bool:
        """
        Unmap virtual address.

        Args:
            virtual_address: Virtual memory address to unmap

        Returns:
            bool: True if unmapping successful
        """
        try:
            with self._lock:
                if virtual_address not in self._page_mappings:
                    self._logger.warning(f"Virtual address not mapped: {virtual_address}")
                    return False

                mapping = self._page_mappings[virtual_address]

                # Remove mapping
                del self._page_mappings[virtual_address]

                # Update page status if it exists
                virtual_page_id = virtual_address // self._config.page_size_bytes
                if virtual_page_id in self._pages:
                    page_info = self._pages[virtual_page_id]
                    page_info.status = PageStatus.ALLOCATED if page_info.reference_count > 0 else PageStatus.FREE
                    page_info.physical_address = None

                self._logger.debug(f"Unmapped page: virtual={virtual_address:x}")
                return True

        except Exception as e:
            self._logger.error(f"Error unmapping page: {e}")
            return False

    def get_page_info(self, page_id: int) -> Optional[PageInfo]:
        """
        Get information about a specific page.

        Args:
            page_id: ID of the page

        Returns:
            PageInfo: Page information or None if not found
        """
        try:
            with self._lock:
                return self._pages.get(page_id)

        except Exception as e:
            self._logger.error(f"Error getting page info: {e}")
            return None

    def get_metrics(self) -> PageMetrics:
        """Get current page manager metrics."""
        with self._lock:
            self._update_utilization_metrics()
            return PageMetrics(
                total_pages=self._metrics.total_pages,
                allocated_pages=self._metrics.allocated_pages,
                free_pages=self._metrics.free_pages,
                dirty_pages=len(self._dirty_pages),
                swapped_pages=self._metrics.swapped_pages,
                page_faults=self._metrics.page_faults,
                page_allocations=self._metrics.page_allocations,
                page_deallocations=self._metrics.page_deallocations,
                memory_utilization_percent=self._metrics.memory_utilization_percent,
                fragmentation_ratio=self._calculate_fragmentation_ratio(),
                last_updated=datetime.now(timezone.utc)
            )

    # Private helper methods

    def _initialize_page_pools(self) -> bool:
        """Initialize page pools for different page sizes."""
        try:
            # Create main page pool for standard 4KB pages
            main_pool = PagePool(
                pool_id="main_4kb",
                page_size_bytes=self._config.page_size_bytes,
                total_pages=self._config.total_pages
            )

            self._page_pools[self._config.page_size_bytes] = main_pool

            # Initialize free pages in the pool
            for page_id in range(self._config.total_pages):
                main_pool.free_pages.add(page_id)

            self._logger.info(f"Initialized page pool with {self._config.total_pages} pages")
            return True

        except Exception as e:
            self._logger.error(f"Error initializing page pools: {e}")
            return False

    def _initialize_page_tracking(self) -> bool:
        """Initialize page tracking structures."""
        try:
            # Initialize all pages as free
            for page_id in range(self._config.total_pages):
                virtual_address = page_id * self._config.page_size_bytes

                page_info = PageInfo(
                    page_id=page_id,
                    virtual_address=virtual_address,
                    physical_address=None,
                    size_bytes=self._config.page_size_bytes,
                    status=PageStatus.FREE
                )

                self._pages[page_id] = page_info
                self._free_pages.add(page_id)

            # Initialize metrics
            self._metrics.total_pages = self._config.total_pages
            self._metrics.free_pages = self._config.total_pages
            self._metrics.allocated_pages = 0

            self._logger.info(f"Initialized tracking for {self._config.total_pages} pages")
            return True

        except Exception as e:
            self._logger.error(f"Error initializing page tracking: {e}")
            return False

    async def _sync_dirty_pages(self) -> None:
        """Background task to sync dirty pages to storage."""
        try:
            while not self._shutdown_requested:
                await asyncio.sleep(self._config.sync_interval_seconds)

                if self._dirty_pages:
                    await self._flush_dirty_pages()

        except asyncio.CancelledError:
            self._logger.debug("Dirty page sync task cancelled")
        except Exception as e:
            self._logger.error(f"Error in dirty page sync task: {e}")

    async def _flush_dirty_pages(self) -> None:
        """Flush dirty pages to storage."""
        try:
            with self._lock:
                dirty_page_ids = list(self._dirty_pages)

            if not dirty_page_ids:
                return

            # Flush pages in batches
            batch_size = 64
            for i in range(0, len(dirty_page_ids), batch_size):
                batch = dirty_page_ids[i:i + batch_size]
                await self._flush_page_batch(batch)

            # Clear dirty pages set
            with self._lock:
                for page_id in dirty_page_ids:
                    self._dirty_pages.discard(page_id)
                    if page_id in self._pages:
                        self._pages[page_id].dirty = False

            self._logger.debug(f"Flushed {len(dirty_page_ids)} dirty pages")

        except Exception as e:
            self._logger.error(f"Error flushing dirty pages: {e}")

    async def _flush_page_batch(self, page_ids: List[int]) -> None:
        """Flush a batch of pages to storage."""
        try:
            # In a real implementation, this would write pages to NVMe storage
            # For now, we'll simulate the operation
            await asyncio.sleep(0.001)  # Simulate I/O delay

        except Exception as e:
            self._logger.error(f"Error flushing page batch: {e}")

    def _update_utilization_metrics(self) -> None:
        """Update memory utilization metrics."""
        try:
            if self._metrics.total_pages > 0:
                self._metrics.memory_utilization_percent = (
                    self._metrics.allocated_pages / self._metrics.total_pages
                ) * 100.0
            else:
                self._metrics.memory_utilization_percent = 0.0

        except Exception as e:
            self._logger.error(f"Error updating utilization metrics: {e}")

    def _calculate_fragmentation_ratio(self) -> float:
        """Calculate memory fragmentation ratio."""
        try:
            if not self._free_pages:
                return 0.0

            # Simple fragmentation calculation based on free page distribution
            # In a real implementation, would analyze contiguous free blocks
            total_free = len(self._free_pages)
            if total_free == 0:
                return 0.0

            # Calculate largest contiguous block (simplified)
            sorted_free = sorted(self._free_pages)
            largest_block = 1
            current_block = 1

            for i in range(1, len(sorted_free)):
                if sorted_free[i] == sorted_free[i-1] + 1:
                    current_block += 1
                else:
                    largest_block = max(largest_block, current_block)
                    current_block = 1

            largest_block = max(largest_block, current_block)

            # Fragmentation ratio: 1 - (largest_block / total_free)
            return 1.0 - (largest_block / total_free)

        except Exception as e:
            self._logger.error(f"Error calculating fragmentation ratio: {e}")
            return 0.0

    def mark_page_dirty(self, page_id: int) -> bool:
        """Mark a page as dirty."""
        try:
            with self._lock:
                if page_id in self._pages:
                    self._pages[page_id].dirty = True
                    self._dirty_pages.add(page_id)

                    # Check if we need to flush dirty pages
                    if len(self._dirty_pages) >= self._config.max_dirty_pages:
                        # Schedule immediate flush
                        asyncio.create_task(self._flush_dirty_pages())

                    return True
                return False

        except Exception as e:
            self._logger.error(f"Error marking page dirty: {e}")
            return False

    def lock_page(self, page_id: int) -> bool:
        """Lock a page in memory."""
        try:
            with self._lock:
                if page_id in self._pages:
                    self._pages[page_id].locked = True
                    return True
                return False

        except Exception as e:
            self._logger.error(f"Error locking page: {e}")
            return False

    def unlock_page(self, page_id: int) -> bool:
        """Unlock a page."""
        try:
            with self._lock:
                if page_id in self._pages:
                    self._pages[page_id].locked = False
                    return True
                return False

        except Exception as e:
            self._logger.error(f"Error unlocking page: {e}")
            return False
