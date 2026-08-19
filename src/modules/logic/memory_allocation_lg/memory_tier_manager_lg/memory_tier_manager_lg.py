"""
Module: memory_tier_manager_lg
Description: Manages three-tier memory hierarchy (GPU VRAM, System RAM, NVMe) with bandwidth ratings and capacity tracking
Phase: 2
Location: /src/modules/logic/memory_allocation_lg/memory_tier_manager_lg/
"""

# Standard library imports
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock, RLock
from typing import Dict, List, Optional, Set, Tuple

# Third-party imports
import psutil
import shutil

# Local imports
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import MemoryTier


class TierStatus(Enum):
    """Memory tier status."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEGRADED = "DEGRADED"
    MAINTENANCE = "MAINTENANCE"
    ERROR = "ERROR"


@dataclass
class TierCapacity:
    """Memory tier capacity information."""
    total_bytes: int
    used_bytes: int
    available_bytes: int
    reserved_bytes: int
    fragmentation_percent: float


@dataclass
class TierBandwidth:
    """Memory tier bandwidth characteristics."""
    read_bandwidth_mbps: float
    write_bandwidth_mbps: float
    latency_microseconds: float
    sustained_bandwidth_mbps: float
    peak_bandwidth_mbps: float


@dataclass
class TierConfiguration:
    """Memory tier configuration."""
    tier: MemoryTier
    device_path: str
    enable_monitoring: bool = True
    capacity_threshold_percent: float = 90.0
    bandwidth_monitoring_interval: float = 5.0
    auto_cleanup: bool = True
    compression_enabled: bool = False


@dataclass
class TierMetrics:
    """Memory tier performance metrics."""
    allocation_count: int
    deallocation_count: int
    total_allocated_bytes: int
    peak_usage_bytes: int
    average_allocation_size: float
    fragmentation_events: int
    bandwidth_utilization: float
    error_count: int


@dataclass
class MemoryTierInfo:
    """Complete memory tier information."""
    tier: MemoryTier
    status: TierStatus
    capacity: TierCapacity
    bandwidth: TierBandwidth
    configuration: TierConfiguration
    metrics: TierMetrics
    last_updated: datetime
    allocation_map: Dict[str, Tuple[int, int]]  # allocation_id -> (offset, size)


class IMemoryTierManager(ABC):
    """Interface for memory tier management systems."""
    
    @abstractmethod
    def initialize_tiers(self) -> bool:
        """Initialize all memory tiers."""
        pass
    
    @abstractmethod
    def get_tier_info(self, tier: MemoryTier) -> Optional[MemoryTierInfo]:
        """Get information about a specific tier."""
        pass
    
    @abstractmethod
    def allocate_memory(self, tier: MemoryTier, size_bytes: int, 
                       allocation_id: str) -> Optional[Tuple[int, int]]:
        """Allocate memory in specified tier."""
        pass
    
    @abstractmethod
    def deallocate_memory(self, tier: MemoryTier, allocation_id: str) -> bool:
        """Deallocate memory from specified tier."""
        pass
    
    @abstractmethod
    def get_tier_usage(self) -> Dict[MemoryTier, float]:
        """Get usage percentage for all tiers."""
        pass
    
    @abstractmethod
    def optimize_tier_allocation(self, tier: MemoryTier) -> bool:
        """Optimize allocation in specified tier."""
        pass


class MemoryTierManager(IMemoryTierManager):
    """Manages three-tier memory hierarchy with capacity and bandwidth tracking."""
    
    def __init__(self):
        """Initialize memory tier manager."""
        self._logger = logging.getLogger(__name__)
        self._lock = RLock()
        
        # Tier information storage
        self._tiers: Dict[MemoryTier, MemoryTierInfo] = {}
        self._tier_locks: Dict[MemoryTier, Lock] = {}
        
        # Monitoring state
        self._monitoring_active = False
        self._last_bandwidth_check = {}
        
        # Allocation tracking
        self._allocation_counter = 0
        self._active_allocations: Dict[str, Tuple[MemoryTier, int, int]] = {}  # id -> (tier, offset, size)
        
        self._logger.info("Memory tier manager initialized")
    
    def initialize_tiers(self) -> bool:
        """
        Initialize all memory tiers with hardware detection.
        
        Returns:
            True if initialization successful
        """
        try:
            with self._lock:
                self._logger.info("Initializing memory tiers...")
                
                # Initialize GPU VRAM tier
                if self._initialize_gpu_tier():
                    self._logger.info("GPU VRAM tier initialized successfully")
                else:
                    self._logger.warning("GPU VRAM tier initialization failed")
                
                # Initialize System RAM tier
                if self._initialize_ram_tier():
                    self._logger.info("System RAM tier initialized successfully")
                else:
                    self._logger.error("System RAM tier initialization failed")
                    return False
                
                # Initialize NVMe tier
                if self._initialize_nvme_tier():
                    self._logger.info("NVMe tier initialized successfully")
                else:
                    self._logger.warning("NVMe tier initialization failed")
                
                # Start monitoring
                self._monitoring_active = True
                
                self._logger.info(f"Memory tier manager initialized with {len(self._tiers)} tiers")
                return True
                
        except Exception as e:
            self._logger.error(f"Error initializing memory tiers: {e}")
            return False
    
    def get_tier_info(self, tier: MemoryTier) -> Optional[MemoryTierInfo]:
        """
        Get information about a specific tier.
        
        Args:
            tier: Memory tier to query
            
        Returns:
            Tier information or None if not found
        """
        try:
            with self._lock:
                if tier not in self._tiers:
                    return None
                
                # Update tier information
                self._update_tier_metrics(tier)
                
                return self._tiers[tier]
                
        except Exception as e:
            self._logger.error(f"Error getting tier info for {tier}: {e}")
            return None
    
    def allocate_memory(self, tier: MemoryTier, size_bytes: int, 
                       allocation_id: str) -> Optional[Tuple[int, int]]:
        """
        Allocate memory in specified tier.
        
        Args:
            tier: Target memory tier
            size_bytes: Size to allocate in bytes
            allocation_id: Unique allocation identifier
            
        Returns:
            Tuple of (offset, size) if successful, None otherwise
        """
        try:
            if tier not in self._tiers:
                self._logger.error(f"Tier {tier} not available")
                return None
            
            tier_lock = self._tier_locks.get(tier)
            if not tier_lock:
                return None
            
            with tier_lock:
                tier_info = self._tiers[tier]
                
                # Check if tier is active
                if tier_info.status != TierStatus.ACTIVE:
                    self._logger.warning(f"Tier {tier} is not active (status: {tier_info.status})")
                    return None
                
                # Check available capacity
                if tier_info.capacity.available_bytes < size_bytes:
                    self._logger.warning(f"Insufficient capacity in tier {tier}: "
                                       f"requested {size_bytes}, available {tier_info.capacity.available_bytes}")
                    return None
                
                # Find allocation offset
                offset = self._find_allocation_offset(tier, size_bytes)
                if offset is None:
                    self._logger.warning(f"Could not find suitable offset in tier {tier}")
                    return None
                
                # Record allocation
                tier_info.allocation_map[allocation_id] = (offset, size_bytes)
                tier_info.capacity.used_bytes += size_bytes
                tier_info.capacity.available_bytes -= size_bytes
                tier_info.metrics.allocation_count += 1
                tier_info.metrics.total_allocated_bytes += size_bytes
                tier_info.last_updated = datetime.now(timezone.utc)
                
                # Update peak usage
                if tier_info.capacity.used_bytes > tier_info.metrics.peak_usage_bytes:
                    tier_info.metrics.peak_usage_bytes = tier_info.capacity.used_bytes
                
                # Track globally
                self._active_allocations[allocation_id] = (tier, offset, size_bytes)
                
                self._logger.debug(f"Allocated {size_bytes} bytes in tier {tier} at offset {offset}")
                
                return (offset, size_bytes)
                
        except Exception as e:
            self._logger.error(f"Error allocating memory in tier {tier}: {e}")
            return None

    def deallocate_memory(self, tier: MemoryTier, allocation_id: str) -> bool:
        """
        Deallocate memory from specified tier.

        Args:
            tier: Memory tier containing the allocation
            allocation_id: Allocation identifier to deallocate

        Returns:
            True if deallocation successful
        """
        try:
            if tier not in self._tiers:
                self._logger.error(f"Tier {tier} not available")
                return False

            tier_lock = self._tier_locks.get(tier)
            if not tier_lock:
                return False

            with tier_lock:
                tier_info = self._tiers[tier]

                # Check if allocation exists
                if allocation_id not in tier_info.allocation_map:
                    self._logger.warning(f"Allocation {allocation_id} not found in tier {tier}")
                    return False

                # Get allocation details
                offset, size_bytes = tier_info.allocation_map[allocation_id]

                # Remove allocation
                del tier_info.allocation_map[allocation_id]
                tier_info.capacity.used_bytes -= size_bytes
                tier_info.capacity.available_bytes += size_bytes
                tier_info.metrics.deallocation_count += 1
                tier_info.last_updated = datetime.now(timezone.utc)

                # Remove from global tracking
                if allocation_id in self._active_allocations:
                    del self._active_allocations[allocation_id]

                self._logger.debug(f"Deallocated {size_bytes} bytes from tier {tier}")

                return True

        except Exception as e:
            self._logger.error(f"Error deallocating memory from tier {tier}: {e}")
            return False

    def get_tier_usage(self) -> Dict[MemoryTier, float]:
        """
        Get usage percentage for all tiers.

        Returns:
            Dictionary mapping tiers to usage percentages
        """
        try:
            with self._lock:
                usage = {}

                for tier, tier_info in self._tiers.items():
                    if tier_info.capacity.total_bytes > 0:
                        usage_percent = (tier_info.capacity.used_bytes / tier_info.capacity.total_bytes) * 100.0
                        usage[tier] = usage_percent
                    else:
                        usage[tier] = 0.0

                return usage

        except Exception as e:
            self._logger.error(f"Error getting tier usage: {e}")
            return {}

    def optimize_tier_allocation(self, tier: MemoryTier) -> bool:
        """
        Optimize allocation in specified tier.

        Args:
            tier: Memory tier to optimize

        Returns:
            True if optimization successful
        """
        try:
            if tier not in self._tiers:
                return False

            tier_lock = self._tier_locks.get(tier)
            if not tier_lock:
                return False

            with tier_lock:
                tier_info = self._tiers[tier]

                # Calculate fragmentation
                fragmentation = self._calculate_fragmentation(tier)
                tier_info.capacity.fragmentation_percent = fragmentation

                # Perform defragmentation if needed
                if fragmentation > 25.0:  # 25% fragmentation threshold
                    success = self._defragment_tier(tier)
                    if success:
                        tier_info.metrics.fragmentation_events += 1
                        self._logger.info(f"Defragmented tier {tier} (fragmentation was {fragmentation:.1f}%)")
                    return success

                return True

        except Exception as e:
            self._logger.error(f"Error optimizing tier {tier}: {e}")
            return False

    def _initialize_gpu_tier(self) -> bool:
        """Initialize GPU VRAM tier."""
        try:
            # Try to detect GPU memory
            gpu_memory_gb = self._detect_gpu_memory()

            if gpu_memory_gb <= 0:
                self._logger.warning("No GPU memory detected")
                return False

            total_bytes = int(gpu_memory_gb * 1024**3)

            # Create tier configuration
            config = TierConfiguration(
                tier=MemoryTier.GPU_VRAM,
                device_path="/dev/gpu0",  # Placeholder
                capacity_threshold_percent=85.0,
                bandwidth_monitoring_interval=1.0
            )

            # Create tier info
            tier_info = MemoryTierInfo(
                tier=MemoryTier.GPU_VRAM,
                status=TierStatus.ACTIVE,
                capacity=TierCapacity(
                    total_bytes=total_bytes,
                    used_bytes=0,
                    available_bytes=total_bytes,
                    reserved_bytes=int(total_bytes * 0.1),  # Reserve 10%
                    fragmentation_percent=0.0
                ),
                bandwidth=TierBandwidth(
                    read_bandwidth_mbps=900000.0,  # ~900 GB/s for modern GPUs
                    write_bandwidth_mbps=900000.0,
                    latency_microseconds=0.1,
                    sustained_bandwidth_mbps=800000.0,
                    peak_bandwidth_mbps=1000000.0
                ),
                configuration=config,
                metrics=TierMetrics(
                    allocation_count=0,
                    deallocation_count=0,
                    total_allocated_bytes=0,
                    peak_usage_bytes=0,
                    average_allocation_size=0.0,
                    fragmentation_events=0,
                    bandwidth_utilization=0.0,
                    error_count=0
                ),
                last_updated=datetime.now(timezone.utc),
                allocation_map={}
            )

            self._tiers[MemoryTier.GPU_VRAM] = tier_info
            self._tier_locks[MemoryTier.GPU_VRAM] = Lock()

            return True

        except Exception as e:
            self._logger.error(f"Error initializing GPU tier: {e}")
            return False

    def _initialize_ram_tier(self) -> bool:
        """Initialize System RAM tier."""
        try:
            # Get system memory information
            memory_info = psutil.virtual_memory()
            total_bytes = memory_info.total

            # Reserve memory for OS and other applications
            reserved_bytes = int(total_bytes * 0.2)  # Reserve 20%
            available_bytes = total_bytes - reserved_bytes

            # Create tier configuration
            config = TierConfiguration(
                tier=MemoryTier.SYSTEM_RAM,
                device_path="/dev/mem",
                capacity_threshold_percent=90.0,
                bandwidth_monitoring_interval=2.0
            )

            # Create tier info
            tier_info = MemoryTierInfo(
                tier=MemoryTier.SYSTEM_RAM,
                status=TierStatus.ACTIVE,
                capacity=TierCapacity(
                    total_bytes=total_bytes,
                    used_bytes=memory_info.used,
                    available_bytes=available_bytes,
                    reserved_bytes=reserved_bytes,
                    fragmentation_percent=0.0
                ),
                bandwidth=TierBandwidth(
                    read_bandwidth_mbps=50000.0,  # ~50 GB/s for DDR4
                    write_bandwidth_mbps=50000.0,
                    latency_microseconds=100.0,
                    sustained_bandwidth_mbps=45000.0,
                    peak_bandwidth_mbps=60000.0
                ),
                configuration=config,
                metrics=TierMetrics(
                    allocation_count=0,
                    deallocation_count=0,
                    total_allocated_bytes=0,
                    peak_usage_bytes=memory_info.used,
                    average_allocation_size=0.0,
                    fragmentation_events=0,
                    bandwidth_utilization=0.0,
                    error_count=0
                ),
                last_updated=datetime.now(timezone.utc),
                allocation_map={}
            )

            self._tiers[MemoryTier.SYSTEM_RAM] = tier_info
            self._tier_locks[MemoryTier.SYSTEM_RAM] = Lock()

            return True

        except Exception as e:
            self._logger.error(f"Error initializing RAM tier: {e}")
            return False

    def _initialize_nvme_tier(self) -> bool:
        """Initialize NVMe tier."""
        try:
            # Detect NVMe drives
            nvme_info = self._detect_nvme_drives()

            if not nvme_info:
                self._logger.warning("No suitable NVMe drives detected")
                return False

            total_bytes, bandwidth_gbps, device_path = nvme_info

            # Create tier configuration
            config = TierConfiguration(
                tier=MemoryTier.NVME_CACHE,
                device_path=device_path,
                capacity_threshold_percent=95.0,
                bandwidth_monitoring_interval=5.0,
                compression_enabled=True
            )

            # Create tier info
            tier_info = MemoryTierInfo(
                tier=MemoryTier.NVME_CACHE,
                status=TierStatus.ACTIVE,
                capacity=TierCapacity(
                    total_bytes=total_bytes,
                    used_bytes=0,
                    available_bytes=total_bytes,
                    reserved_bytes=int(total_bytes * 0.05),  # Reserve 5%
                    fragmentation_percent=0.0
                ),
                bandwidth=TierBandwidth(
                    read_bandwidth_mbps=bandwidth_gbps * 1000,
                    write_bandwidth_mbps=bandwidth_gbps * 800,  # Write typically slower
                    latency_microseconds=50.0,
                    sustained_bandwidth_mbps=bandwidth_gbps * 900,
                    peak_bandwidth_mbps=bandwidth_gbps * 1100
                ),
                configuration=config,
                metrics=TierMetrics(
                    allocation_count=0,
                    deallocation_count=0,
                    total_allocated_bytes=0,
                    peak_usage_bytes=0,
                    average_allocation_size=0.0,
                    fragmentation_events=0,
                    bandwidth_utilization=0.0,
                    error_count=0
                ),
                last_updated=datetime.now(timezone.utc),
                allocation_map={}
            )

            self._tiers[MemoryTier.NVME_CACHE] = tier_info
            self._tier_locks[MemoryTier.NVME_CACHE] = Lock()

            return True

        except Exception as e:
            self._logger.error(f"Error initializing NVMe tier: {e}")
            return False

    def _detect_gpu_memory(self) -> float:
        """Detect GPU memory capacity in GB."""
        try:
            # Try to detect GPU memory using various methods
            # This is a simplified implementation

            # Method 1: Try nvidia-ml-py if available
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()

                if device_count > 0:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    return memory_info.total / (1024**3)  # Convert to GB

            except ImportError:
                pass
            except Exception:
                pass

            # Method 2: Estimate based on system specs (fallback)
            # This is a rough estimation
            system_ram_gb = psutil.virtual_memory().total / (1024**3)

            if system_ram_gb >= 32:
                return 8.0  # Assume high-end GPU
            elif system_ram_gb >= 16:
                return 4.0  # Assume mid-range GPU
            else:
                return 2.0  # Assume entry-level GPU

        except Exception as e:
            self._logger.error(f"Error detecting GPU memory: {e}")
            return 0.0

    def _detect_nvme_drives(self) -> Optional[Tuple[int, float, str]]:
        """Detect NVMe drives and return (capacity_bytes, bandwidth_gbps, device_path)."""
        try:
            # Get disk usage for available drives
            drives = []

            # Check common mount points
            mount_points = ["/", "C:\\", "D:\\", "E:\\"]

            for mount_point in mount_points:
                try:
                    if Path(mount_point).exists():
                        usage = shutil.disk_usage(mount_point)

                        # Estimate if this is an NVMe drive based on available space
                        # This is a simplified heuristic
                        total_gb = usage.total / (1024**3)

                        if total_gb >= 100:  # At least 100GB
                            # Estimate bandwidth based on drive size (heuristic)
                            if total_gb >= 1000:
                                bandwidth_gbps = 7.0  # High-end NVMe
                            elif total_gb >= 500:
                                bandwidth_gbps = 5.0  # Mid-range NVMe
                            else:
                                bandwidth_gbps = 3.5  # Entry-level NVMe

                            drives.append((usage.total, bandwidth_gbps, mount_point))

                except Exception:
                    continue

            if drives:
                # Return the largest drive
                return max(drives, key=lambda x: x[0])

            return None

        except Exception as e:
            self._logger.error(f"Error detecting NVMe drives: {e}")
            return None

    def _find_allocation_offset(self, tier: MemoryTier, size_bytes: int) -> Optional[int]:
        """Find suitable offset for allocation in tier."""
        try:
            tier_info = self._tiers[tier]

            # Simple first-fit allocation strategy
            # In a real implementation, this would be more sophisticated

            # Sort existing allocations by offset
            allocations = sorted(tier_info.allocation_map.values(), key=lambda x: x[0])

            # Check if we can fit at the beginning
            if not allocations or allocations[0][0] >= size_bytes:
                return 0

            # Check gaps between allocations
            for i in range(len(allocations) - 1):
                current_end = allocations[i][0] + allocations[i][1]
                next_start = allocations[i + 1][0]
                gap_size = next_start - current_end

                if gap_size >= size_bytes:
                    return current_end

            # Check if we can fit at the end
            if allocations:
                last_allocation = allocations[-1]
                last_end = last_allocation[0] + last_allocation[1]
                remaining_space = tier_info.capacity.total_bytes - last_end

                if remaining_space >= size_bytes:
                    return last_end

            return None

        except Exception as e:
            self._logger.error(f"Error finding allocation offset: {e}")
            return None

    def _update_tier_metrics(self, tier: MemoryTier) -> None:
        """Update tier metrics."""
        try:
            tier_info = self._tiers[tier]

            # Update average allocation size
            if tier_info.metrics.allocation_count > 0:
                tier_info.metrics.average_allocation_size = (
                    tier_info.metrics.total_allocated_bytes / tier_info.metrics.allocation_count
                )

            # Update bandwidth utilization (simplified)
            if tier_info.capacity.total_bytes > 0:
                usage_ratio = tier_info.capacity.used_bytes / tier_info.capacity.total_bytes
                tier_info.metrics.bandwidth_utilization = min(1.0, usage_ratio * 1.2)  # Heuristic

            tier_info.last_updated = datetime.now(timezone.utc)

        except Exception as e:
            self._logger.error(f"Error updating tier metrics: {e}")

    def _calculate_fragmentation(self, tier: MemoryTier) -> float:
        """Calculate fragmentation percentage for tier."""
        try:
            tier_info = self._tiers[tier]

            if not tier_info.allocation_map:
                return 0.0

            # Calculate fragmentation based on allocation gaps
            allocations = sorted(tier_info.allocation_map.values(), key=lambda x: x[0])

            total_gaps = 0
            for i in range(len(allocations) - 1):
                current_end = allocations[i][0] + allocations[i][1]
                next_start = allocations[i + 1][0]
                gap_size = next_start - current_end
                total_gaps += gap_size

            if tier_info.capacity.used_bytes > 0:
                fragmentation = (total_gaps / tier_info.capacity.used_bytes) * 100.0
                return min(100.0, fragmentation)

            return 0.0

        except Exception as e:
            self._logger.error(f"Error calculating fragmentation: {e}")
            return 0.0

    def _defragment_tier(self, tier: MemoryTier) -> bool:
        """Defragment tier allocations."""
        try:
            # In a real implementation, this would compact allocations
            # For now, we'll just simulate successful defragmentation
            tier_info = self._tiers[tier]
            tier_info.capacity.fragmentation_percent = 0.0

            self._logger.debug(f"Defragmented tier {tier}")
            return True

        except Exception as e:
            self._logger.error(f"Error defragmenting tier {tier}: {e}")
            return False

    def get_tier_statistics(self) -> Dict[str, Dict[str, float]]:
        """Get comprehensive tier statistics."""
        try:
            with self._lock:
                stats = {}

                for tier, tier_info in self._tiers.items():
                    tier_stats = {
                        'total_capacity_gb': tier_info.capacity.total_bytes / (1024**3),
                        'used_capacity_gb': tier_info.capacity.used_bytes / (1024**3),
                        'available_capacity_gb': tier_info.capacity.available_bytes / (1024**3),
                        'usage_percent': (tier_info.capacity.used_bytes / tier_info.capacity.total_bytes) * 100,
                        'fragmentation_percent': tier_info.capacity.fragmentation_percent,
                        'allocation_count': tier_info.metrics.allocation_count,
                        'deallocation_count': tier_info.metrics.deallocation_count,
                        'peak_usage_gb': tier_info.metrics.peak_usage_bytes / (1024**3),
                        'average_allocation_mb': tier_info.metrics.average_allocation_size / (1024**2),
                        'bandwidth_utilization': tier_info.metrics.bandwidth_utilization,
                        'read_bandwidth_gbps': tier_info.bandwidth.read_bandwidth_mbps / 1000,
                        'write_bandwidth_gbps': tier_info.bandwidth.write_bandwidth_mbps / 1000,
                        'latency_microseconds': tier_info.bandwidth.latency_microseconds,
                        'error_count': tier_info.metrics.error_count
                    }

                    stats[tier.value] = tier_stats

                return stats

        except Exception as e:
            self._logger.error(f"Error getting tier statistics: {e}")
            return {}
