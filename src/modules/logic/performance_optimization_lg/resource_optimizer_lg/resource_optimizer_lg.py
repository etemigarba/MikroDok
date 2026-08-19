"""
Module: resource_optimizer_lg
Description: Dynamically optimizes resource allocation based on load, implementing intelligent resource distribution across GPU, CPU, and memory tiers
Phase: 2
Location: /src/modules/logic/performance_optimization_lg/resource_optimizer_lg/
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
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
from collections import deque, defaultdict

# Local imports
from src.modules.logic.resource_monitor_lg import (
    ResourceMetrics, 
    MemoryMetrics, 
    GPUMetrics,
    ThermalMetrics,
    DiskMetrics
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class OptimizationStrategy(Enum):
    """Resource optimization strategies."""
    BALANCED = "BALANCED"
    PERFORMANCE_FIRST = "PERFORMANCE_FIRST"
    EFFICIENCY_FIRST = "EFFICIENCY_FIRST"
    THERMAL_AWARE = "THERMAL_AWARE"
    MEMORY_CONSERVATIVE = "MEMORY_CONSERVATIVE"
    POWER_EFFICIENT = "POWER_EFFICIENT"
    ADAPTIVE = "ADAPTIVE"


class ResourceTier(Enum):
    """Resource allocation tiers."""
    GPU_VRAM = "GPU_VRAM"
    SYSTEM_RAM = "SYSTEM_RAM"
    NVME_CACHE = "NVME_CACHE"
    SSD_STORAGE = "SSD_STORAGE"
    HDD_STORAGE = "HDD_STORAGE"


class AllocationPriority(Enum):
    """Resource allocation priorities."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


@dataclass
class ResourceAllocation:
    """Resource allocation configuration."""
    tier: ResourceTier
    allocated_bytes: int
    max_bytes: int
    priority: AllocationPriority
    timestamp: datetime
    consumer_id: str
    allocation_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationTarget:
    """Optimization target configuration."""
    target_gpu_utilization: float = 85.0
    target_memory_utilization: float = 80.0
    target_thermal_limit: float = 80.0
    max_power_consumption: Optional[float] = None
    min_performance_threshold: float = 0.7
    efficiency_weight: float = 0.5
    performance_weight: float = 0.5


@dataclass
class ResourceConstraints:
    """Resource allocation constraints."""
    max_gpu_memory_percent: float = 90.0
    max_system_memory_percent: float = 85.0
    thermal_limit_celsius: float = 85.0
    power_limit_watts: Optional[float] = None
    min_free_memory_mb: float = 2048.0
    max_allocation_time_ms: float = 100.0
    enable_cross_tier_migration: bool = True
    enable_predictive_allocation: bool = True


@dataclass
class OptimizationResult:
    """Result of resource optimization."""
    timestamp: datetime
    strategy_used: OptimizationStrategy
    allocations_changed: int
    memory_freed_mb: float
    performance_improvement: float
    efficiency_gain: float
    thermal_reduction: float
    success: bool
    error_message: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)


class IResourceOptimizer(ABC):
    """Interface for resource optimization systems."""
    
    @abstractmethod
    async def optimize_allocation(self, current_metrics: ResourceMetrics,
                                 strategy: OptimizationStrategy) -> OptimizationResult:
        """Optimize resource allocation based on current metrics."""
        pass
    
    @abstractmethod
    def allocate_resource(self, consumer_id: str, tier: ResourceTier,
                         size_bytes: int, priority: AllocationPriority) -> Optional[str]:
        """Allocate resources for a consumer."""
        pass
    
    @abstractmethod
    def deallocate_resource(self, allocation_id: str) -> bool:
        """Deallocate resources."""
        pass
    
    @abstractmethod
    def get_allocation_recommendations(self, workload_type: str,
                                     constraints: ResourceConstraints) -> List[ResourceAllocation]:
        """Get allocation recommendations for a workload."""
        pass


class ResourceOptimizer(IResourceOptimizer):
    """Dynamic resource allocation optimizer with intelligent tier management."""
    
    def __init__(self, targets: OptimizationTarget, constraints: ResourceConstraints):
        """Initialize the resource optimizer."""
        self._targets = targets
        self._constraints = constraints
        self._logger = get_logger(__name__)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Resource tracking
        self._allocations: Dict[str, ResourceAllocation] = {}
        self._tier_usage: Dict[ResourceTier, int] = defaultdict(int)
        self._tier_limits: Dict[ResourceTier, int] = {}
        
        # Performance tracking
        self._optimization_history: deque = deque(maxlen=100)
        self._allocation_patterns: Dict[str, List[ResourceAllocation]] = defaultdict(list)
        
        # Monitoring
        self._monitoring_enabled = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_optimization = datetime.now(timezone.utc)
        
        # Callbacks
        self._allocation_callbacks: List[Callable[[ResourceAllocation], None]] = []
        self._optimization_callbacks: List[Callable[[OptimizationResult], None]] = []
        
        self._logger.info("Resource optimizer initialized")
    
    async def start_monitoring(self) -> None:
        """Start resource optimization monitoring."""
        if self._monitoring_enabled:
            self._logger.warning("Resource optimization monitoring already running")
            return
        
        self._monitoring_enabled = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._logger.info("Resource optimization monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop resource optimization monitoring."""
        if not self._monitoring_enabled:
            return
        
        self._monitoring_enabled = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self._logger.info("Resource optimization monitoring stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main optimization monitoring loop."""
        try:
            while self._monitoring_enabled:
                start_time = time.time()
                
                # Perform periodic optimization checks
                await self._periodic_optimization_check()
                
                # Calculate sleep time (5-second intervals)
                elapsed = time.time() - start_time
                sleep_time = max(0, 5.0 - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._logger.error(f"Error in optimization monitoring loop: {e}")
    
    async def _periodic_optimization_check(self) -> None:
        """Perform periodic optimization checks."""
        try:
            # Check if optimization is needed
            time_since_last = datetime.now(timezone.utc) - self._last_optimization
            if time_since_last.total_seconds() < 30:  # Minimum 30 seconds between optimizations
                return

            # Get current metrics (would be injected in real implementation)
            # For now, we'll skip automatic optimization without metrics

        except Exception as e:
            self._logger.error(f"Error in periodic optimization check: {e}")

    async def optimize_allocation(self, current_metrics: ResourceMetrics,
                                 strategy: OptimizationStrategy) -> OptimizationResult:
        """Optimize resource allocation based on current metrics."""
        start_time = time.time()

        try:
            with self._lock:
                self._logger.debug(f"Starting resource optimization with strategy: {strategy}")

                # Analyze current resource state
                analysis = self._analyze_resource_state(current_metrics)

                # Determine optimization actions
                actions = self._determine_optimization_actions(analysis, strategy)

                # Execute optimization actions
                result = await self._execute_optimization_actions(actions, current_metrics)

                # Update optimization history
                self._optimization_history.append(result)
                self._last_optimization = datetime.now(timezone.utc)

                # Notify callbacks
                for callback in self._optimization_callbacks:
                    try:
                        callback(result)
                    except Exception as e:
                        self._logger.error(f"Error in optimization callback: {e}")

                optimization_time = (time.time() - start_time) * 1000
                self._logger.info(f"Resource optimization completed in {optimization_time:.2f}ms")

                return result

        except Exception as e:
            self._logger.error(f"Error in resource optimization: {e}")
            return OptimizationResult(
                timestamp=datetime.now(timezone.utc),
                strategy_used=strategy,
                allocations_changed=0,
                memory_freed_mb=0.0,
                performance_improvement=0.0,
                efficiency_gain=0.0,
                thermal_reduction=0.0,
                success=False,
                error_message=str(e)
            )

    def allocate_resource(self, consumer_id: str, tier: ResourceTier,
                         size_bytes: int, priority: AllocationPriority) -> Optional[str]:
        """Allocate resources for a consumer."""
        try:
            with self._lock:
                # Check if allocation is possible
                if not self._can_allocate(tier, size_bytes):
                    self._logger.warning(f"Cannot allocate {size_bytes} bytes in tier {tier}")
                    return None

                # Generate allocation ID
                allocation_id = f"{consumer_id}_{tier.value}_{int(time.time() * 1000)}"

                # Create allocation
                allocation = ResourceAllocation(
                    tier=tier,
                    allocated_bytes=size_bytes,
                    max_bytes=size_bytes,
                    priority=priority,
                    timestamp=datetime.now(timezone.utc),
                    consumer_id=consumer_id,
                    allocation_id=allocation_id
                )

                # Update tracking
                self._allocations[allocation_id] = allocation
                self._tier_usage[tier] += size_bytes
                self._allocation_patterns[consumer_id].append(allocation)

                # Notify callbacks
                for callback in self._allocation_callbacks:
                    try:
                        callback(allocation)
                    except Exception as e:
                        self._logger.error(f"Error in allocation callback: {e}")

                self._logger.debug(f"Allocated {size_bytes} bytes in {tier} for {consumer_id}")
                return allocation_id

        except Exception as e:
            self._logger.error(f"Error allocating resource: {e}")
            return None

    def deallocate_resource(self, allocation_id: str) -> bool:
        """Deallocate resources."""
        try:
            with self._lock:
                if allocation_id not in self._allocations:
                    self._logger.warning(f"Allocation {allocation_id} not found")
                    return False

                allocation = self._allocations[allocation_id]

                # Update tracking
                self._tier_usage[allocation.tier] -= allocation.allocated_bytes
                del self._allocations[allocation_id]

                # Remove from patterns
                if allocation.consumer_id in self._allocation_patterns:
                    patterns = self._allocation_patterns[allocation.consumer_id]
                    self._allocation_patterns[allocation.consumer_id] = [
                        a for a in patterns if a.allocation_id != allocation_id
                    ]

                self._logger.debug(f"Deallocated {allocation.allocated_bytes} bytes from {allocation.tier}")
                return True

        except Exception as e:
            self._logger.error(f"Error deallocating resource: {e}")
            return False

    def get_allocation_recommendations(self, workload_type: str,
                                     constraints: ResourceConstraints) -> List[ResourceAllocation]:
        """Get allocation recommendations for a workload."""
        try:
            with self._lock:
                recommendations = []

                # Analyze workload requirements
                requirements = self._analyze_workload_requirements(workload_type)

                # Generate tier recommendations
                for tier, size_bytes in requirements.items():
                    if self._can_allocate(tier, size_bytes, constraints):
                        recommendation = ResourceAllocation(
                            tier=tier,
                            allocated_bytes=size_bytes,
                            max_bytes=size_bytes,
                            priority=AllocationPriority.NORMAL,
                            timestamp=datetime.now(timezone.utc),
                            consumer_id=workload_type,
                            allocation_id=f"recommendation_{tier.value}_{int(time.time())}"
                        )
                        recommendations.append(recommendation)

                return recommendations

        except Exception as e:
            self._logger.error(f"Error generating allocation recommendations: {e}")
            return []

    def _analyze_resource_state(self, metrics: ResourceMetrics) -> Dict[str, Any]:
        """Analyze current resource state."""
        analysis = {
            'memory_pressure': 0.0,
            'gpu_pressure': 0.0,
            'thermal_pressure': 0.0,
            'disk_pressure': 0.0,
            'overall_pressure': 0.0,
            'bottlenecks': [],
            'recommendations': []
        }

        try:
            # Analyze memory pressure
            if metrics.memory:
                memory_usage = metrics.memory.usage_percent
                analysis['memory_pressure'] = min(memory_usage / 100.0, 1.0)
                if memory_usage > 85:
                    analysis['bottlenecks'].append('memory')

            # Analyze GPU pressure
            if metrics.gpu:
                gpu_memory_usage = metrics.gpu.memory_usage_percent
                analysis['gpu_pressure'] = min(gpu_memory_usage / 100.0, 1.0)
                if gpu_memory_usage > 90:
                    analysis['bottlenecks'].append('gpu_memory')

            # Analyze thermal pressure
            if metrics.thermal:
                max_temp = max(metrics.thermal.cpu_temperature, metrics.thermal.gpu_temperature)
                analysis['thermal_pressure'] = min(max_temp / self._constraints.thermal_limit_celsius, 1.0)
                if max_temp > self._constraints.thermal_limit_celsius:
                    analysis['bottlenecks'].append('thermal')

            # Calculate overall pressure
            pressures = [
                analysis['memory_pressure'],
                analysis['gpu_pressure'],
                analysis['thermal_pressure']
            ]
            analysis['overall_pressure'] = statistics.mean(pressures)

        except Exception as e:
            self._logger.error(f"Error analyzing resource state: {e}")

        return analysis

    def _determine_optimization_actions(self, analysis: Dict[str, Any],
                                      strategy: OptimizationStrategy) -> List[str]:
        """Determine optimization actions based on analysis and strategy."""
        actions = []

        try:
            overall_pressure = analysis.get('overall_pressure', 0.0)
            bottlenecks = analysis.get('bottlenecks', [])

            # High pressure situations
            if overall_pressure > 0.8:
                actions.append('emergency_cleanup')
                actions.append('migrate_to_lower_tiers')

            # Memory pressure
            if 'memory' in bottlenecks:
                actions.append('compress_allocations')
                actions.append('offload_to_nvme')

            # GPU memory pressure
            if 'gpu_memory' in bottlenecks:
                actions.append('migrate_gpu_to_system')
                actions.append('reduce_gpu_allocations')

            # Thermal pressure
            if 'thermal' in bottlenecks:
                actions.append('reduce_performance_allocations')
                actions.append('throttle_high_priority')

            # Strategy-specific actions
            if strategy == OptimizationStrategy.PERFORMANCE_FIRST:
                actions.append('prioritize_gpu_allocations')
            elif strategy == OptimizationStrategy.EFFICIENCY_FIRST:
                actions.append('consolidate_allocations')
            elif strategy == OptimizationStrategy.THERMAL_AWARE:
                actions.append('thermal_optimization')

        except Exception as e:
            self._logger.error(f"Error determining optimization actions: {e}")

        return actions

    async def _execute_optimization_actions(self, actions: List[str],
                                          metrics: ResourceMetrics) -> OptimizationResult:
        """Execute optimization actions."""
        result = OptimizationResult(
            timestamp=datetime.now(timezone.utc),
            strategy_used=OptimizationStrategy.BALANCED,
            allocations_changed=0,
            memory_freed_mb=0.0,
            performance_improvement=0.0,
            efficiency_gain=0.0,
            thermal_reduction=0.0,
            success=True
        )

        try:
            for action in actions:
                if action == 'emergency_cleanup':
                    freed = await self._emergency_cleanup()
                    result.memory_freed_mb += freed
                    result.allocations_changed += 1

                elif action == 'migrate_to_lower_tiers':
                    migrated = await self._migrate_to_lower_tiers()
                    result.allocations_changed += migrated

                elif action == 'compress_allocations':
                    compressed = await self._compress_allocations()
                    result.memory_freed_mb += compressed

                elif action == 'offload_to_nvme':
                    offloaded = await self._offload_to_nvme()
                    result.memory_freed_mb += offloaded

                # Add more action implementations as needed

        except Exception as e:
            self._logger.error(f"Error executing optimization actions: {e}")
            result.success = False
            result.error_message = str(e)

        return result

    def _can_allocate(self, tier: ResourceTier, size_bytes: int,
                     constraints: Optional[ResourceConstraints] = None) -> bool:
        """Check if allocation is possible in the specified tier."""
        try:
            constraints = constraints or self._constraints
            current_usage = self._tier_usage.get(tier, 0)
            tier_limit = self._tier_limits.get(tier, float('inf'))

            # Check tier-specific limits
            if current_usage + size_bytes > tier_limit:
                return False

            # Check constraint-specific limits
            if tier == ResourceTier.GPU_VRAM:
                # Would need actual GPU memory info
                return True
            elif tier == ResourceTier.SYSTEM_RAM:
                # Would need actual system memory info
                return True

            return True

        except Exception as e:
            self._logger.error(f"Error checking allocation possibility: {e}")
            return False

    def _analyze_workload_requirements(self, workload_type: str) -> Dict[ResourceTier, int]:
        """Analyze workload requirements and suggest tier allocations."""
        requirements = {}

        try:
            # Default requirements based on workload type
            if workload_type == 'training':
                requirements[ResourceTier.GPU_VRAM] = 8 * 1024 * 1024 * 1024  # 8GB
                requirements[ResourceTier.SYSTEM_RAM] = 16 * 1024 * 1024 * 1024  # 16GB
                requirements[ResourceTier.NVME_CACHE] = 32 * 1024 * 1024 * 1024  # 32GB

            elif workload_type == 'inference':
                requirements[ResourceTier.GPU_VRAM] = 4 * 1024 * 1024 * 1024  # 4GB
                requirements[ResourceTier.SYSTEM_RAM] = 8 * 1024 * 1024 * 1024  # 8GB
                requirements[ResourceTier.NVME_CACHE] = 16 * 1024 * 1024 * 1024  # 16GB

            elif workload_type == 'preprocessing':
                requirements[ResourceTier.SYSTEM_RAM] = 4 * 1024 * 1024 * 1024  # 4GB
                requirements[ResourceTier.NVME_CACHE] = 8 * 1024 * 1024 * 1024  # 8GB

            else:
                # Default allocation
                requirements[ResourceTier.SYSTEM_RAM] = 2 * 1024 * 1024 * 1024  # 2GB

        except Exception as e:
            self._logger.error(f"Error analyzing workload requirements: {e}")

        return requirements

    async def _emergency_cleanup(self) -> float:
        """Perform emergency cleanup to free memory."""
        freed_mb = 0.0

        try:
            # Find low-priority allocations to remove
            low_priority_allocations = [
                alloc for alloc in self._allocations.values()
                if alloc.priority in [AllocationPriority.LOW, AllocationPriority.BACKGROUND]
            ]

            for allocation in low_priority_allocations[:5]:  # Limit to 5 allocations
                if self.deallocate_resource(allocation.allocation_id):
                    freed_mb += allocation.allocated_bytes / (1024 * 1024)

            self._logger.info(f"Emergency cleanup freed {freed_mb:.2f} MB")

        except Exception as e:
            self._logger.error(f"Error in emergency cleanup: {e}")

        return freed_mb

    async def _migrate_to_lower_tiers(self) -> int:
        """Migrate allocations to lower tiers."""
        migrated_count = 0

        try:
            # Find GPU allocations that can be migrated
            gpu_allocations = [
                alloc for alloc in self._allocations.values()
                if alloc.tier == ResourceTier.GPU_VRAM and alloc.priority != AllocationPriority.CRITICAL
            ]

            for allocation in gpu_allocations[:3]:  # Limit migrations
                # Try to migrate to system RAM
                if self._can_allocate(ResourceTier.SYSTEM_RAM, allocation.allocated_bytes):
                    # Create new allocation in system RAM
                    new_id = self.allocate_resource(
                        allocation.consumer_id,
                        ResourceTier.SYSTEM_RAM,
                        allocation.allocated_bytes,
                        allocation.priority
                    )

                    if new_id:
                        # Remove old allocation
                        self.deallocate_resource(allocation.allocation_id)
                        migrated_count += 1

            self._logger.info(f"Migrated {migrated_count} allocations to lower tiers")

        except Exception as e:
            self._logger.error(f"Error migrating to lower tiers: {e}")

        return migrated_count

    async def _compress_allocations(self) -> float:
        """Compress allocations to free memory."""
        freed_mb = 0.0

        try:
            # Simulate compression by reducing allocation sizes
            compressible_allocations = [
                alloc for alloc in self._allocations.values()
                if alloc.tier in [ResourceTier.SYSTEM_RAM, ResourceTier.NVME_CACHE]
                and alloc.priority != AllocationPriority.CRITICAL
            ]

            for allocation in compressible_allocations[:5]:
                # Reduce allocation by 20%
                reduction = int(allocation.allocated_bytes * 0.2)
                allocation.allocated_bytes -= reduction
                self._tier_usage[allocation.tier] -= reduction
                freed_mb += reduction / (1024 * 1024)

            self._logger.info(f"Compression freed {freed_mb:.2f} MB")

        except Exception as e:
            self._logger.error(f"Error compressing allocations: {e}")

        return freed_mb

    async def _offload_to_nvme(self) -> float:
        """Offload data to NVMe storage."""
        freed_mb = 0.0

        try:
            # Find system RAM allocations to offload
            ram_allocations = [
                alloc for alloc in self._allocations.values()
                if alloc.tier == ResourceTier.SYSTEM_RAM and alloc.priority == AllocationPriority.LOW
            ]

            for allocation in ram_allocations[:3]:
                # Try to create NVMe allocation
                nvme_id = self.allocate_resource(
                    allocation.consumer_id,
                    ResourceTier.NVME_CACHE,
                    allocation.allocated_bytes,
                    allocation.priority
                )

                if nvme_id:
                    # Remove RAM allocation
                    freed_mb += allocation.allocated_bytes / (1024 * 1024)
                    self.deallocate_resource(allocation.allocation_id)

            self._logger.info(f"Offloaded {freed_mb:.2f} MB to NVMe")

        except Exception as e:
            self._logger.error(f"Error offloading to NVMe: {e}")

        return freed_mb

    def get_current_allocations(self) -> Dict[str, ResourceAllocation]:
        """Get current resource allocations."""
        with self._lock:
            return self._allocations.copy()

    def get_tier_usage(self) -> Dict[ResourceTier, int]:
        """Get current tier usage."""
        with self._lock:
            return self._tier_usage.copy()

    def get_optimization_history(self) -> List[OptimizationResult]:
        """Get optimization history."""
        with self._lock:
            return list(self._optimization_history)

    def add_allocation_callback(self, callback: Callable[[ResourceAllocation], None]) -> None:
        """Add allocation callback."""
        self._allocation_callbacks.append(callback)

    def add_optimization_callback(self, callback: Callable[[OptimizationResult], None]) -> None:
        """Add optimization callback."""
        self._optimization_callbacks.append(callback)
