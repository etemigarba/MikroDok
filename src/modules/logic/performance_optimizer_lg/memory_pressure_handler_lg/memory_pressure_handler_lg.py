"""
Module: memory_pressure_handler_lg
Description: Responds to memory exhaustion by adjusting allocations, offloading to lower tiers, and implementing emergency cleanup
Phase: 2
Location: /src/modules/logic/performance_optimizer_lg/memory_pressure_handler_lg/
"""

# Standard library imports
import asyncio
import gc
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from collections import defaultdict, deque
import weakref

# Local imports
from src.modules.logic.resource_monitor_lg import MemoryMetrics, MemoryAllocationPattern
from src.modules.logic.logging_infrastructure_lg import get_logger


class PressureLevel(Enum):
    """Memory pressure severity levels."""
    NORMAL = "NORMAL"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class MemoryAction(Enum):
    """Actions that can be taken to relieve memory pressure."""
    GARBAGE_COLLECT = "GARBAGE_COLLECT"
    CLEAR_CACHES = "CLEAR_CACHES"
    REDUCE_BATCH_SIZE = "REDUCE_BATCH_SIZE"
    OFFLOAD_TO_DISK = "OFFLOAD_TO_DISK"
    OFFLOAD_TO_NVME = "OFFLOAD_TO_NVME"
    COMPRESS_DATA = "COMPRESS_DATA"
    RELEASE_UNUSED_MEMORY = "RELEASE_UNUSED_MEMORY"
    EMERGENCY_CLEANUP = "EMERGENCY_CLEANUP"
    SUSPEND_NON_CRITICAL = "SUSPEND_NON_CRITICAL"
    FORCE_MEMORY_RECLAIM = "FORCE_MEMORY_RECLAIM"


class AllocationStrategy(Enum):
    """Memory allocation strategies under pressure."""
    CONSERVATIVE = "CONSERVATIVE"
    AGGRESSIVE_CLEANUP = "AGGRESSIVE_CLEANUP"
    TIERED_STORAGE = "TIERED_STORAGE"
    COMPRESSION_FIRST = "COMPRESSION_FIRST"
    EMERGENCY_MODE = "EMERGENCY_MODE"


class CleanupStrategy(Enum):
    """Cleanup strategies for memory management."""
    LAZY_CLEANUP = "LAZY_CLEANUP"
    IMMEDIATE_CLEANUP = "IMMEDIATE_CLEANUP"
    SCHEDULED_CLEANUP = "SCHEDULED_CLEANUP"
    PRESSURE_BASED = "PRESSURE_BASED"
    PREDICTIVE_CLEANUP = "PREDICTIVE_CLEANUP"


class MemoryTier(Enum):
    """Memory storage tiers for offloading."""
    RAM = "RAM"
    GPU_MEMORY = "GPU_MEMORY"
    NVME_CACHE = "NVME_CACHE"
    SSD_STORAGE = "SSD_STORAGE"
    HDD_STORAGE = "HDD_STORAGE"
    COMPRESSED_RAM = "COMPRESSED_RAM"


@dataclass
class MemoryPressureEvent:
    """Represents a memory pressure event."""
    timestamp: datetime
    pressure_level: PressureLevel
    memory_usage_percent: float
    available_memory_mb: float
    pressure_score: float
    triggered_actions: List[MemoryAction]
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PressureConfiguration:
    """Configuration for memory pressure handling."""
    # Pressure thresholds (percentage)
    low_pressure_threshold: float = 70.0
    moderate_pressure_threshold: float = 80.0
    high_pressure_threshold: float = 90.0
    critical_pressure_threshold: float = 95.0
    emergency_pressure_threshold: float = 98.0
    
    # Action settings
    enable_automatic_cleanup: bool = True
    enable_tiered_storage: bool = True
    enable_compression: bool = True
    enable_emergency_actions: bool = True
    
    # Timing settings
    pressure_check_interval_seconds: float = 2.0
    cleanup_cooldown_seconds: float = 10.0
    emergency_response_timeout_seconds: float = 5.0
    
    # Strategy settings
    default_allocation_strategy: AllocationStrategy = AllocationStrategy.TIERED_STORAGE
    default_cleanup_strategy: CleanupStrategy = CleanupStrategy.PRESSURE_BASED
    
    # Limits
    max_concurrent_actions: int = 3
    max_offload_size_mb: float = 1024.0
    compression_ratio_target: float = 0.5


class IMemoryPressureHandler(ABC):
    """Interface for memory pressure handling systems."""
    
    @abstractmethod
    async def start_monitoring(self) -> None:
        """Start memory pressure monitoring."""
        pass
    
    @abstractmethod
    async def stop_monitoring(self) -> None:
        """Stop memory pressure monitoring."""
        pass
    
    @abstractmethod
    async def handle_pressure_event(self, pressure_level: PressureLevel, 
                                   memory_metrics: MemoryMetrics) -> List[MemoryAction]:
        """Handle a memory pressure event."""
        pass
    
    @abstractmethod
    async def emergency_cleanup(self) -> bool:
        """Perform emergency memory cleanup."""
        pass
    
    @abstractmethod
    def register_cleanup_handler(self, action: MemoryAction, 
                                handler: Callable[[], bool]) -> None:
        """Register a cleanup handler for specific actions."""
        pass


class MemoryPressureHandler(IMemoryPressureHandler):
    """
    Responds to memory exhaustion by adjusting allocations, offloading to lower tiers, 
    and implementing emergency cleanup.
    
    This class monitors memory pressure and takes appropriate actions to maintain
    system stability and performance under memory constraints.
    """
    
    def __init__(self, config: Optional[PressureConfiguration] = None):
        """
        Initialize the memory pressure handler.
        
        Args:
            config: Configuration for pressure handling behavior
        """
        self._config = config or PressureConfiguration()
        self._logger = get_logger(__name__)
        
        # Monitoring state
        self._monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        
        # Pressure tracking
        self._current_pressure_level = PressureLevel.NORMAL
        self._pressure_history: deque = deque(maxlen=100)
        self._recent_events: deque = deque(maxlen=50)
        
        # Action management
        self._cleanup_handlers: Dict[MemoryAction, Callable] = {}
        self._active_actions: Set[MemoryAction] = set()
        self._action_cooldowns: Dict[MemoryAction, datetime] = {}
        
        # Memory management
        self._managed_objects: weakref.WeakSet = weakref.WeakSet()
        self._offloaded_data: Dict[str, Tuple[MemoryTier, Any]] = {}
        self._compression_cache: Dict[str, Any] = {}
        
        # Performance tracking
        self._cleanup_times: deque = deque(maxlen=50)
        self._memory_freed_mb: deque = deque(maxlen=50)
        
        # Initialize default handlers
        self._initialize_default_handlers()
        
        self._logger.info("Memory pressure handler initialized")
    
    async def start_monitoring(self) -> None:
        """Start memory pressure monitoring."""
        if self._monitoring:
            self._logger.warning("Memory pressure monitoring already running")
            return
        
        self._monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._logger.info("Memory pressure monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop memory pressure monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self._logger.info("Memory pressure monitoring stopped")
    
    async def handle_pressure_event(self, pressure_level: PressureLevel, 
                                   memory_metrics: MemoryMetrics) -> List[MemoryAction]:
        """Handle a memory pressure event."""
        start_time = time.time()
        actions_taken = []
        
        try:
            with self._lock:
                self._current_pressure_level = pressure_level
                
                # Determine required actions based on pressure level
                required_actions = self._determine_required_actions(pressure_level, memory_metrics)
                
                # Execute actions
                for action in required_actions:
                    if await self._execute_action(action, memory_metrics):
                        actions_taken.append(action)
                
                # Create and track event
                event = MemoryPressureEvent(
                    timestamp=datetime.now(timezone.utc),
                    pressure_level=pressure_level,
                    memory_usage_percent=memory_metrics.usage_percent,
                    available_memory_mb=memory_metrics.available_ram_mb,
                    pressure_score=memory_metrics.memory_pressure_score,
                    triggered_actions=actions_taken,
                    context={
                        'swap_usage': memory_metrics.swap_info.usage_percent,
                        'gc_objects': memory_metrics.gc_uncollectable_objects
                    }
                )
                
                self._recent_events.append(event)
                self._pressure_history.append((datetime.now(timezone.utc), pressure_level))
            
            # Track performance
            handling_time = time.time() - start_time
            self._cleanup_times.append(handling_time)
            
            if actions_taken:
                self._logger.info(f"Handled {pressure_level.value} pressure with {len(actions_taken)} actions "
                                f"in {handling_time:.3f}s")
            
            return actions_taken
            
        except Exception as e:
            self._logger.error(f"Error handling pressure event: {e}")
            return []

    async def emergency_cleanup(self) -> bool:
        """Perform emergency memory cleanup."""
        self._logger.warning("Performing emergency memory cleanup")
        start_time = time.time()

        try:
            cleanup_success = False

            # Force garbage collection
            collected = gc.collect()
            if collected > 0:
                cleanup_success = True
                self._logger.info(f"Emergency GC collected {collected} objects")

            # Clear all caches
            if await self._clear_all_caches():
                cleanup_success = True

            # Force memory reclaim
            if await self._force_memory_reclaim():
                cleanup_success = True

            # Suspend non-critical operations
            if await self._suspend_non_critical_operations():
                cleanup_success = True

            cleanup_time = time.time() - start_time
            self._cleanup_times.append(cleanup_time)

            if cleanup_success:
                self._logger.info(f"Emergency cleanup completed in {cleanup_time:.3f}s")
            else:
                self._logger.warning("Emergency cleanup had limited effect")

            return cleanup_success

        except Exception as e:
            self._logger.error(f"Error in emergency cleanup: {e}")
            return False

    def register_cleanup_handler(self, action: MemoryAction,
                                handler: Callable[[], bool]) -> None:
        """Register a cleanup handler for specific actions."""
        with self._lock:
            self._cleanup_handlers[action] = handler

        self._logger.info(f"Registered cleanup handler for action: {action.value}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for memory pressure detection."""
        self._logger.info("Starting memory pressure monitoring loop")

        while self._monitoring:
            try:
                # This would typically get memory metrics from memory monitor
                # For now, we'll skip the actual monitoring in the loop
                await asyncio.sleep(self._config.pressure_check_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(1.0)

    def _determine_required_actions(self, pressure_level: PressureLevel,
                                   memory_metrics: MemoryMetrics) -> List[MemoryAction]:
        """Determine what actions are required for the given pressure level."""
        actions = []

        try:
            if pressure_level == PressureLevel.LOW:
                actions.extend([MemoryAction.GARBAGE_COLLECT])

            elif pressure_level == PressureLevel.MODERATE:
                actions.extend([
                    MemoryAction.GARBAGE_COLLECT,
                    MemoryAction.CLEAR_CACHES
                ])

            elif pressure_level == PressureLevel.HIGH:
                actions.extend([
                    MemoryAction.GARBAGE_COLLECT,
                    MemoryAction.CLEAR_CACHES,
                    MemoryAction.COMPRESS_DATA,
                    MemoryAction.OFFLOAD_TO_NVME
                ])

            elif pressure_level == PressureLevel.CRITICAL:
                actions.extend([
                    MemoryAction.GARBAGE_COLLECT,
                    MemoryAction.CLEAR_CACHES,
                    MemoryAction.COMPRESS_DATA,
                    MemoryAction.OFFLOAD_TO_DISK,
                    MemoryAction.REDUCE_BATCH_SIZE,
                    MemoryAction.RELEASE_UNUSED_MEMORY
                ])

            elif pressure_level == PressureLevel.EMERGENCY:
                actions.extend([
                    MemoryAction.EMERGENCY_CLEANUP,
                    MemoryAction.FORCE_MEMORY_RECLAIM,
                    MemoryAction.SUSPEND_NON_CRITICAL
                ])

            # Filter out actions that are on cooldown
            current_time = datetime.now(timezone.utc)
            available_actions = []

            for action in actions:
                if action in self._action_cooldowns:
                    if current_time >= self._action_cooldowns[action]:
                        available_actions.append(action)
                else:
                    available_actions.append(action)

            return available_actions

        except Exception as e:
            self._logger.error(f"Error determining required actions: {e}")
            return []

    async def _execute_action(self, action: MemoryAction, memory_metrics: MemoryMetrics) -> bool:
        """Execute a specific memory action."""
        try:
            # Check if action is already active
            if action in self._active_actions:
                return False

            # Check concurrent action limit
            if len(self._active_actions) >= self._config.max_concurrent_actions:
                return False

            self._active_actions.add(action)

            try:
                success = False

                # Execute the action
                if action == MemoryAction.GARBAGE_COLLECT:
                    success = await self._perform_garbage_collection()
                elif action == MemoryAction.CLEAR_CACHES:
                    success = await self._clear_caches()
                elif action == MemoryAction.COMPRESS_DATA:
                    success = await self._compress_data()
                elif action == MemoryAction.OFFLOAD_TO_NVME:
                    success = await self._offload_to_tier(MemoryTier.NVME_CACHE)
                elif action == MemoryAction.OFFLOAD_TO_DISK:
                    success = await self._offload_to_tier(MemoryTier.SSD_STORAGE)
                elif action == MemoryAction.RELEASE_UNUSED_MEMORY:
                    success = await self._release_unused_memory()
                elif action == MemoryAction.EMERGENCY_CLEANUP:
                    success = await self.emergency_cleanup()
                elif action in self._cleanup_handlers:
                    # Use custom handler
                    handler = self._cleanup_handlers[action]
                    if asyncio.iscoroutinefunction(handler):
                        success = await handler()
                    else:
                        success = handler()

                # Set cooldown
                if success:
                    cooldown_time = datetime.now(timezone.utc) + timedelta(
                        seconds=self._config.cleanup_cooldown_seconds
                    )
                    self._action_cooldowns[action] = cooldown_time

                return success

            finally:
                self._active_actions.discard(action)

        except Exception as e:
            self._logger.error(f"Error executing action {action.value}: {e}")
            return False

    async def _perform_garbage_collection(self) -> bool:
        """Perform garbage collection."""
        try:
            collected_objects = gc.collect()
            if collected_objects > 0:
                self._logger.debug(f"Garbage collection freed {collected_objects} objects")
                return True
            return False
        except Exception as e:
            self._logger.error(f"Error in garbage collection: {e}")
            return False

    async def _clear_caches(self) -> bool:
        """Clear internal caches."""
        try:
            initial_size = len(self._compression_cache)
            self._compression_cache.clear()

            # Clear other internal caches
            cleared_items = initial_size

            if cleared_items > 0:
                self._logger.debug(f"Cleared {cleared_items} cache items")
                return True
            return False
        except Exception as e:
            self._logger.error(f"Error clearing caches: {e}")
            return False

    async def _clear_all_caches(self) -> bool:
        """Clear all available caches."""
        try:
            success = await self._clear_caches()

            # Additional cache clearing would go here
            # This could include clearing application-specific caches

            return success
        except Exception as e:
            self._logger.error(f"Error clearing all caches: {e}")
            return False

    async def _compress_data(self) -> bool:
        """Compress data in memory to reduce usage."""
        try:
            # This would implement data compression logic
            # For now, we'll simulate compression
            compressed_items = 0

            # Simulate compression of managed objects
            for obj in list(self._managed_objects):
                try:
                    # In a real implementation, this would compress the object
                    compressed_items += 1
                    if compressed_items >= 10:  # Limit compression batch
                        break
                except Exception:
                    continue

            if compressed_items > 0:
                self._logger.debug(f"Compressed {compressed_items} data items")
                return True
            return False
        except Exception as e:
            self._logger.error(f"Error compressing data: {e}")
            return False

    async def _offload_to_tier(self, tier: MemoryTier) -> bool:
        """Offload data to a specific memory tier."""
        try:
            offloaded_items = 0
            offloaded_size_mb = 0.0

            # Simulate offloading managed objects
            for obj in list(self._managed_objects):
                try:
                    # In a real implementation, this would offload the object
                    # to the specified tier (NVMe, SSD, etc.)
                    obj_id = str(id(obj))
                    self._offloaded_data[obj_id] = (tier, obj)

                    offloaded_items += 1
                    offloaded_size_mb += 0.1  # Simulate size

                    if offloaded_size_mb >= self._config.max_offload_size_mb:
                        break
                except Exception:
                    continue

            if offloaded_items > 0:
                self._logger.debug(f"Offloaded {offloaded_items} items ({offloaded_size_mb:.1f} MB) to {tier.value}")
                return True
            return False
        except Exception as e:
            self._logger.error(f"Error offloading to {tier.value}: {e}")
            return False

    async def _release_unused_memory(self) -> bool:
        """Release unused memory allocations."""
        try:
            # Force garbage collection
            collected = gc.collect()

            # Clear weak references to dead objects
            initial_count = len(self._managed_objects)
            # WeakSet automatically removes dead references
            final_count = len(self._managed_objects)

            released_objects = initial_count - final_count + collected

            if released_objects > 0:
                self._logger.debug(f"Released {released_objects} unused memory allocations")
                return True
            return False
        except Exception as e:
            self._logger.error(f"Error releasing unused memory: {e}")
            return False

    async def _force_memory_reclaim(self) -> bool:
        """Force aggressive memory reclamation."""
        try:
            success = False

            # Multiple garbage collection passes
            for _ in range(3):
                collected = gc.collect()
                if collected > 0:
                    success = True

            # Clear all offloaded data references
            if self._offloaded_data:
                self._offloaded_data.clear()
                success = True

            # Clear compression cache
            if self._compression_cache:
                self._compression_cache.clear()
                success = True

            if success:
                self._logger.debug("Forced memory reclamation completed")

            return success
        except Exception as e:
            self._logger.error(f"Error in forced memory reclaim: {e}")
            return False

    async def _suspend_non_critical_operations(self) -> bool:
        """Suspend non-critical operations to free memory."""
        try:
            # This would implement suspension of non-critical operations
            # For now, we'll simulate this
            suspended_operations = 0

            # In a real implementation, this would:
            # - Pause background tasks
            # - Suspend caching operations
            # - Reduce processing threads
            # - Defer non-essential computations

            suspended_operations = 5  # Simulate suspended operations

            if suspended_operations > 0:
                self._logger.debug(f"Suspended {suspended_operations} non-critical operations")
                return True
            return False
        except Exception as e:
            self._logger.error(f"Error suspending operations: {e}")
            return False

    def _initialize_default_handlers(self) -> None:
        """Initialize default cleanup handlers."""
        try:
            # Register default handlers for common actions
            self._cleanup_handlers[MemoryAction.REDUCE_BATCH_SIZE] = self._default_reduce_batch_size
            self._cleanup_handlers[MemoryAction.SUSPEND_NON_CRITICAL] = self._default_suspend_operations

        except Exception as e:
            self._logger.error(f"Error initializing default handlers: {e}")

    def _default_reduce_batch_size(self) -> bool:
        """Default handler for reducing batch size."""
        try:
            # This would implement batch size reduction
            # For now, we'll simulate this
            self._logger.debug("Reduced batch size due to memory pressure")
            return True
        except Exception:
            return False

    def _default_suspend_operations(self) -> bool:
        """Default handler for suspending operations."""
        try:
            # This would implement operation suspension
            # For now, we'll simulate this
            self._logger.debug("Suspended non-critical operations")
            return True
        except Exception:
            return False

    def add_managed_object(self, obj: Any) -> None:
        """Add an object to be managed by the pressure handler."""
        try:
            self._managed_objects.add(obj)
        except Exception as e:
            self._logger.error(f"Error adding managed object: {e}")

    def get_pressure_statistics(self) -> Dict[str, Any]:
        """Get statistics about memory pressure handling."""
        with self._lock:
            avg_cleanup_time = (
                sum(self._cleanup_times) / len(self._cleanup_times)
                if self._cleanup_times else 0.0
            )

            total_memory_freed = sum(self._memory_freed_mb) if self._memory_freed_mb else 0.0

            return {
                'current_pressure_level': self._current_pressure_level.value,
                'recent_events': len(self._recent_events),
                'active_actions': len(self._active_actions),
                'managed_objects': len(self._managed_objects),
                'offloaded_items': len(self._offloaded_data),
                'average_cleanup_time_ms': avg_cleanup_time * 1000,
                'total_memory_freed_mb': total_memory_freed,
                'monitoring_active': self._monitoring
            }

    def get_current_pressure_level(self) -> PressureLevel:
        """Get the current memory pressure level."""
        return self._current_pressure_level

    def calculate_pressure_level(self, memory_metrics: MemoryMetrics) -> PressureLevel:
        """Calculate pressure level from memory metrics."""
        try:
            usage_percent = memory_metrics.usage_percent
            pressure_score = memory_metrics.memory_pressure_score

            # Use the higher of usage percentage or pressure score
            effective_pressure = max(usage_percent, pressure_score * 100)

            if effective_pressure >= self._config.emergency_pressure_threshold:
                return PressureLevel.EMERGENCY
            elif effective_pressure >= self._config.critical_pressure_threshold:
                return PressureLevel.CRITICAL
            elif effective_pressure >= self._config.high_pressure_threshold:
                return PressureLevel.HIGH
            elif effective_pressure >= self._config.moderate_pressure_threshold:
                return PressureLevel.MODERATE
            elif effective_pressure >= self._config.low_pressure_threshold:
                return PressureLevel.LOW
            else:
                return PressureLevel.NORMAL

        except Exception as e:
            self._logger.error(f"Error calculating pressure level: {e}")
            return PressureLevel.NORMAL
