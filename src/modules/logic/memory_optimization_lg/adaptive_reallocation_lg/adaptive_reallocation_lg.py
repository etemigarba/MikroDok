"""
Module: adaptive_reallocation_lg
Description: Dynamically adjusts memory distribution based on performance metrics and resource availability
Phase: 7
Location: /src/modules/logic/memory_optimization_lg/adaptive_reallocation_lg/
"""

# Standard library imports
import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable, Any
import statistics
import math

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import MemoryTier
from src.modules.logic.memory_allocation_lg.memory_tier_manager_lg import MemoryTierManager


class ReallocationStrategy(Enum):
    """Memory reallocation strategies."""
    PERFORMANCE_OPTIMIZED = "PERFORMANCE_OPTIMIZED"
    CAPACITY_OPTIMIZED = "CAPACITY_OPTIMIZED"
    BALANCED = "BALANCED"
    EMERGENCY_CONSOLIDATION = "EMERGENCY_CONSOLIDATION"
    PREDICTIVE = "PREDICTIVE"


class AdaptationTrigger(Enum):
    """Triggers for adaptive reallocation."""
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"
    MEMORY_PRESSURE = "MEMORY_PRESSURE"
    TIER_IMBALANCE = "TIER_IMBALANCE"
    WORKLOAD_CHANGE = "WORKLOAD_CHANGE"
    SCHEDULED_OPTIMIZATION = "SCHEDULED_OPTIMIZATION"
    MANUAL_REQUEST = "MANUAL_REQUEST"


class OptimizationTarget(Enum):
    """Optimization targets for reallocation."""
    MINIMIZE_LATENCY = "MINIMIZE_LATENCY"
    MAXIMIZE_THROUGHPUT = "MAXIMIZE_THROUGHPUT"
    BALANCE_LOAD = "BALANCE_LOAD"
    REDUCE_FRAGMENTATION = "REDUCE_FRAGMENTATION"
    CONSERVE_POWER = "CONSERVE_POWER"


@dataclass
class PerformanceMetrics:
    """Performance metrics for reallocation decisions."""
    timestamp: datetime
    memory_bandwidth_gbps: float
    access_latency_ms: float
    cache_hit_ratio: float
    throughput_ops_per_sec: float
    tier_utilization: Dict[MemoryTier, float]
    fragmentation_ratio: float
    power_consumption_watts: float
    temperature_celsius: float


@dataclass
class ResourceAvailability:
    """Current resource availability across tiers."""
    timestamp: datetime
    tier_capacities: Dict[MemoryTier, int]  # bytes
    tier_available: Dict[MemoryTier, int]   # bytes
    tier_bandwidth: Dict[MemoryTier, float] # GB/s
    tier_latency: Dict[MemoryTier, float]   # ms
    tier_power_usage: Dict[MemoryTier, float] # watts
    tier_temperature: Dict[MemoryTier, float] # celsius


@dataclass
class ReallocationDecision:
    """Decision for memory reallocation."""
    source_tier: MemoryTier
    target_tier: MemoryTier
    data_size_bytes: int
    data_identifier: str
    priority: int
    estimated_benefit: float
    estimated_cost: float
    confidence_score: float
    reasoning: str


@dataclass
class ReallocationResult:
    """Result of a reallocation operation."""
    decision: ReallocationDecision
    success: bool
    actual_transfer_time_ms: float
    performance_improvement: float
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class IAdaptiveReallocator(ABC):
    """Interface for adaptive memory reallocation systems."""
    
    @abstractmethod
    async def start_adaptation(self) -> None:
        """Start adaptive reallocation monitoring."""
        pass
    
    @abstractmethod
    async def stop_adaptation(self) -> None:
        """Stop adaptive reallocation monitoring."""
        pass
    
    @abstractmethod
    async def analyze_reallocation_opportunities(self) -> List[ReallocationDecision]:
        """Analyze current state for reallocation opportunities."""
        pass
    
    @abstractmethod
    async def execute_reallocation(self, decision: ReallocationDecision) -> ReallocationResult:
        """Execute a reallocation decision."""
        pass
    
    @abstractmethod
    def set_optimization_target(self, target: OptimizationTarget) -> None:
        """Set the optimization target for reallocation."""
        pass
    
    @abstractmethod
    def register_adaptation_callback(self, callback: Callable[[ReallocationResult], None]) -> None:
        """Register callback for reallocation events."""
        pass


class AdaptiveReallocator(IAdaptiveReallocator):
    """
    Dynamically adjusts memory distribution based on performance metrics and resource availability.
    
    This reallocator uses machine learning and heuristic analysis to optimize memory allocation
    across tiers for maximum performance and efficiency.
    """
    
    def __init__(self, 
                 memory_tier_manager: Optional[MemoryTierManager] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the adaptive reallocator."""
        self._memory_tier_manager = memory_tier_manager or MemoryTierManager()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("adaptive_reallocator")
        self._validation_engine = ValidationEngine()
        
        # Configuration
        self._optimization_target = OptimizationTarget.BALANCE_LOAD
        self._reallocation_strategy = ReallocationStrategy.BALANCED
        
        # Monitoring state
        self._adaptation_active = False
        self._adaptation_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        
        # Performance tracking
        self._performance_history: deque = deque(maxlen=100)
        self._resource_history: deque = deque(maxlen=100)
        self._reallocation_history: deque = deque(maxlen=50)
        
        # Analysis state
        self._current_performance: Optional[PerformanceMetrics] = None
        self._current_resources: Optional[ResourceAvailability] = None
        self._last_analysis_time = datetime.now(timezone.utc)
        
        # Event handling
        self._adaptation_callbacks: List[Callable[[ReallocationResult], None]] = []
        
        # Decision making
        self._decision_weights = {
            'performance_impact': 0.4,
            'resource_efficiency': 0.3,
            'power_consumption': 0.2,
            'implementation_cost': 0.1
        }
        
        self._logger.info("Adaptive reallocator initialized")
    
    async def start_adaptation(self) -> None:
        """Start adaptive reallocation monitoring."""
        try:
            with self._lock:
                if self._adaptation_active:
                    self._logger.warning("Adaptive reallocation already active")
                    return
                
                self._adaptation_active = True
                self._adaptation_task = asyncio.create_task(self._adaptation_loop())
                
            self._logger.info("Adaptive reallocation started")
            
        except Exception as e:
            self._logger.error(f"Error starting adaptive reallocation: {e}")
            raise
    
    async def stop_adaptation(self) -> None:
        """Stop adaptive reallocation monitoring."""
        try:
            with self._lock:
                if not self._adaptation_active:
                    return
                
                self._adaptation_active = False
                
                if self._adaptation_task:
                    self._adaptation_task.cancel()
                    try:
                        await self._adaptation_task
                    except asyncio.CancelledError:
                        pass
                    self._adaptation_task = None
                
            self._logger.info("Adaptive reallocation stopped")
            
        except Exception as e:
            self._logger.error(f"Error stopping adaptive reallocation: {e}")
    
    async def analyze_reallocation_opportunities(self) -> List[ReallocationDecision]:
        """Analyze current state for reallocation opportunities."""
        try:
            # Collect current metrics
            performance = await self._collect_performance_metrics()
            resources = await self._collect_resource_availability()
            
            if not performance or not resources:
                return []
            
            decisions = []
            
            # Analyze tier imbalances
            imbalance_decisions = self._analyze_tier_imbalances(performance, resources)
            decisions.extend(imbalance_decisions)
            
            # Analyze performance bottlenecks
            bottleneck_decisions = self._analyze_performance_bottlenecks(performance, resources)
            decisions.extend(bottleneck_decisions)
            
            # Analyze fragmentation issues
            fragmentation_decisions = self._analyze_fragmentation_issues(performance, resources)
            decisions.extend(fragmentation_decisions)
            
            # Sort decisions by estimated benefit
            decisions.sort(key=lambda d: d.estimated_benefit, reverse=True)
            
            # Filter by confidence threshold
            high_confidence_decisions = [d for d in decisions if d.confidence_score > 0.7]
            
            self._logger.debug(f"Found {len(high_confidence_decisions)} high-confidence reallocation opportunities")
            
            return high_confidence_decisions[:5]  # Return top 5 decisions
            
        except Exception as e:
            self._logger.error(f"Error analyzing reallocation opportunities: {e}")
            return []
    
    async def execute_reallocation(self, decision: ReallocationDecision) -> ReallocationResult:
        """Execute a reallocation decision."""
        start_time = time.time()
        
        try:
            self._logger.info(f"Executing reallocation: {decision.data_identifier} "
                            f"from {decision.source_tier.value} to {decision.target_tier.value}")
            
            # Validate decision
            if not self._validate_reallocation_decision(decision):
                return ReallocationResult(
                    decision=decision,
                    success=False,
                    actual_transfer_time_ms=0,
                    performance_improvement=0,
                    error_message="Decision validation failed"
                )
            
            # Check resource availability
            if not await self._check_target_capacity(decision):
                return ReallocationResult(
                    decision=decision,
                    success=False,
                    actual_transfer_time_ms=0,
                    performance_improvement=0,
                    error_message="Insufficient capacity in target tier"
                )
            
            # Perform the reallocation
            success = await self._perform_data_transfer(decision)
            
            transfer_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Measure performance improvement
            performance_improvement = 0.0
            if success:
                performance_improvement = await self._measure_performance_improvement(decision)
            
            result = ReallocationResult(
                decision=decision,
                success=success,
                actual_transfer_time_ms=transfer_time,
                performance_improvement=performance_improvement,
                error_message=None if success else "Transfer failed"
            )
            
            # Update history
            with self._lock:
                self._reallocation_history.append(result)
            
            # Notify callbacks
            for callback in self._adaptation_callbacks:
                try:
                    callback(result)
                except Exception as e:
                    self._logger.error(f"Error in adaptation callback: {e}")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error executing reallocation: {e}")
            return ReallocationResult(
                decision=decision,
                success=False,
                actual_transfer_time_ms=(time.time() - start_time) * 1000,
                performance_improvement=0,
                error_message=str(e)
            )
    
    def set_optimization_target(self, target: OptimizationTarget) -> None:
        """Set the optimization target for reallocation."""
        try:
            with self._lock:
                self._optimization_target = target
                
                # Adjust decision weights based on target
                if target == OptimizationTarget.MINIMIZE_LATENCY:
                    self._decision_weights = {
                        'performance_impact': 0.6,
                        'resource_efficiency': 0.2,
                        'power_consumption': 0.1,
                        'implementation_cost': 0.1
                    }
                elif target == OptimizationTarget.MAXIMIZE_THROUGHPUT:
                    self._decision_weights = {
                        'performance_impact': 0.5,
                        'resource_efficiency': 0.4,
                        'power_consumption': 0.05,
                        'implementation_cost': 0.05
                    }
                elif target == OptimizationTarget.CONSERVE_POWER:
                    self._decision_weights = {
                        'performance_impact': 0.2,
                        'resource_efficiency': 0.3,
                        'power_consumption': 0.4,
                        'implementation_cost': 0.1
                    }
                
            self._logger.info(f"Optimization target set to {target.value}")
            
        except Exception as e:
            self._logger.error(f"Error setting optimization target: {e}")
    
    def register_adaptation_callback(self, callback: Callable[[ReallocationResult], None]) -> None:
        """Register callback for reallocation events."""
        try:
            with self._lock:
                self._adaptation_callbacks.append(callback)
            self._logger.debug("Adaptation callback registered")
            
        except Exception as e:
            self._logger.error(f"Error registering adaptation callback: {e}")

    async def _adaptation_loop(self) -> None:
        """Main adaptation monitoring loop."""
        try:
            while self._adaptation_active:
                # Analyze reallocation opportunities
                decisions = await self.analyze_reallocation_opportunities()

                # Execute high-priority decisions
                for decision in decisions[:2]:  # Execute top 2 decisions per cycle
                    if decision.priority > 7:  # High priority threshold
                        result = await self.execute_reallocation(decision)
                        if result.success:
                            self._logger.info(f"Successful reallocation improved performance by {result.performance_improvement:.2%}")

                # Wait for next analysis cycle
                await asyncio.sleep(30.0)  # 30-second intervals

        except asyncio.CancelledError:
            self._logger.info("Adaptive reallocation monitoring cancelled")
        except Exception as e:
            self._logger.error(f"Error in adaptation loop: {e}")

    async def _collect_performance_metrics(self) -> Optional[PerformanceMetrics]:
        """Collect current performance metrics."""
        try:
            # Get tier utilization from memory tier manager
            tier_usage = self._memory_tier_manager.get_tier_usage()

            # Simulate performance metrics (in real implementation, these would come from hardware monitoring)
            metrics = PerformanceMetrics(
                timestamp=datetime.now(timezone.utc),
                memory_bandwidth_gbps=self._estimate_memory_bandwidth(tier_usage),
                access_latency_ms=self._estimate_access_latency(tier_usage),
                cache_hit_ratio=self._estimate_cache_hit_ratio(),
                throughput_ops_per_sec=self._estimate_throughput(),
                tier_utilization=tier_usage,
                fragmentation_ratio=self._estimate_fragmentation_ratio(),
                power_consumption_watts=self._estimate_power_consumption(tier_usage),
                temperature_celsius=self._estimate_temperature()
            )

            with self._lock:
                self._current_performance = metrics
                self._performance_history.append(metrics)

            return metrics

        except Exception as e:
            self._logger.error(f"Error collecting performance metrics: {e}")
            return None

    async def _collect_resource_availability(self) -> Optional[ResourceAvailability]:
        """Collect current resource availability."""
        try:
            # Get tier information from memory tier manager
            tier_capacities = {}
            tier_available = {}
            tier_bandwidth = {}
            tier_latency = {}
            tier_power_usage = {}
            tier_temperature = {}

            for tier in MemoryTier:
                tier_info = self._memory_tier_manager.get_tier_info(tier)
                if tier_info:
                    tier_capacities[tier] = tier_info.capacity.total_bytes
                    tier_available[tier] = tier_info.capacity.available_bytes
                    tier_bandwidth[tier] = tier_info.bandwidth.read_bandwidth_gbps
                    tier_latency[tier] = tier_info.bandwidth.access_latency_ms
                    tier_power_usage[tier] = getattr(tier_info, 'power_usage_watts', 0.0)
                    tier_temperature[tier] = getattr(tier_info, 'temperature_celsius', 25.0)

            resources = ResourceAvailability(
                timestamp=datetime.now(timezone.utc),
                tier_capacities=tier_capacities,
                tier_available=tier_available,
                tier_bandwidth=tier_bandwidth,
                tier_latency=tier_latency,
                tier_power_usage=tier_power_usage,
                tier_temperature=tier_temperature
            )

            with self._lock:
                self._current_resources = resources
                self._resource_history.append(resources)

            return resources

        except Exception as e:
            self._logger.error(f"Error collecting resource availability: {e}")
            return None

    def _analyze_tier_imbalances(self, performance: PerformanceMetrics,
                               resources: ResourceAvailability) -> List[ReallocationDecision]:
        """Analyze tier imbalances for reallocation opportunities."""
        decisions = []

        try:
            # Find overutilized and underutilized tiers
            utilization_threshold_high = 0.85
            utilization_threshold_low = 0.30

            overutilized_tiers = []
            underutilized_tiers = []

            for tier, utilization in performance.tier_utilization.items():
                if utilization > utilization_threshold_high:
                    overutilized_tiers.append((tier, utilization))
                elif utilization < utilization_threshold_low:
                    underutilized_tiers.append((tier, utilization))

            # Create reallocation decisions for imbalances
            for over_tier, over_util in overutilized_tiers:
                for under_tier, under_util in underutilized_tiers:
                    # Skip if target tier has worse performance characteristics
                    if not self._is_beneficial_transfer(over_tier, under_tier, resources):
                        continue

                    # Calculate transfer size (move 10% of overutilized tier)
                    transfer_size = int(resources.tier_capacities[over_tier] * 0.1)

                    # Calculate benefit and cost
                    benefit = self._calculate_imbalance_benefit(over_util, under_util)
                    cost = self._calculate_transfer_cost(over_tier, under_tier, transfer_size, resources)

                    decision = ReallocationDecision(
                        source_tier=over_tier,
                        target_tier=under_tier,
                        data_size_bytes=transfer_size,
                        data_identifier=f"imbalance_correction_{over_tier.value}_to_{under_tier.value}",
                        priority=8,
                        estimated_benefit=benefit,
                        estimated_cost=cost,
                        confidence_score=0.8,
                        reasoning=f"Rebalance overutilized {over_tier.value} ({over_util:.1%}) to underutilized {under_tier.value} ({under_util:.1%})"
                    )

                    decisions.append(decision)

            return decisions

        except Exception as e:
            self._logger.error(f"Error analyzing tier imbalances: {e}")
            return []

    def _analyze_performance_bottlenecks(self, performance: PerformanceMetrics,
                                       resources: ResourceAvailability) -> List[ReallocationDecision]:
        """Analyze performance bottlenecks for reallocation opportunities."""
        decisions = []

        try:
            # Identify performance bottlenecks
            if performance.access_latency_ms > 10.0:  # High latency threshold
                # Move frequently accessed data to faster tiers
                for slow_tier in [MemoryTier.SSD_STORAGE, MemoryTier.NVME_CACHE]:
                    for fast_tier in [MemoryTier.GPU_VRAM, MemoryTier.SYSTEM_RAM]:
                        if (slow_tier in resources.tier_available and
                            fast_tier in resources.tier_available and
                            resources.tier_available[fast_tier] > 0):

                            transfer_size = min(
                                int(resources.tier_capacities[slow_tier] * 0.05),  # 5% of slow tier
                                resources.tier_available[fast_tier] // 2  # Half of available fast tier
                            )

                            if transfer_size > 1024 * 1024:  # Minimum 1MB transfer
                                benefit = self._calculate_latency_benefit(slow_tier, fast_tier, resources)
                                cost = self._calculate_transfer_cost(slow_tier, fast_tier, transfer_size, resources)

                                decision = ReallocationDecision(
                                    source_tier=slow_tier,
                                    target_tier=fast_tier,
                                    data_size_bytes=transfer_size,
                                    data_identifier=f"latency_optimization_{slow_tier.value}_to_{fast_tier.value}",
                                    priority=9,
                                    estimated_benefit=benefit,
                                    estimated_cost=cost,
                                    confidence_score=0.75,
                                    reasoning=f"Reduce latency by moving data from {slow_tier.value} to {fast_tier.value}"
                                )

                                decisions.append(decision)

            if performance.memory_bandwidth_gbps < 50.0:  # Low bandwidth threshold
                # Optimize for bandwidth by redistributing load
                decisions.extend(self._create_bandwidth_optimization_decisions(performance, resources))

            return decisions

        except Exception as e:
            self._logger.error(f"Error analyzing performance bottlenecks: {e}")
            return []

    def _analyze_fragmentation_issues(self, performance: PerformanceMetrics,
                                    resources: ResourceAvailability) -> List[ReallocationDecision]:
        """Analyze fragmentation issues for reallocation opportunities."""
        decisions = []

        try:
            if performance.fragmentation_ratio > 0.3:  # High fragmentation threshold
                # Create defragmentation decisions
                for tier in MemoryTier:
                    if tier in performance.tier_utilization:
                        utilization = performance.tier_utilization[tier]

                        # If tier is fragmented and has moderate utilization
                        if 0.4 < utilization < 0.8:
                            # Suggest temporary consolidation
                            for target_tier in MemoryTier:
                                if (target_tier != tier and
                                    target_tier in resources.tier_available and
                                    resources.tier_available[target_tier] > resources.tier_capacities[tier] * 0.1):

                                    transfer_size = int(resources.tier_capacities[tier] * utilization * 0.5)

                                    benefit = self._calculate_defragmentation_benefit(tier, performance.fragmentation_ratio)
                                    cost = self._calculate_transfer_cost(tier, target_tier, transfer_size, resources)

                                    decision = ReallocationDecision(
                                        source_tier=tier,
                                        target_tier=target_tier,
                                        data_size_bytes=transfer_size,
                                        data_identifier=f"defragmentation_{tier.value}_to_{target_tier.value}",
                                        priority=6,
                                        estimated_benefit=benefit,
                                        estimated_cost=cost,
                                        confidence_score=0.65,
                                        reasoning=f"Defragment {tier.value} by temporarily moving data to {target_tier.value}"
                                    )

                                    decisions.append(decision)
                                    break  # Only one defragmentation decision per tier

            return decisions

        except Exception as e:
            self._logger.error(f"Error analyzing fragmentation issues: {e}")
            return []

    def _validate_reallocation_decision(self, decision: ReallocationDecision) -> bool:
        """Validate a reallocation decision."""
        try:
            # Basic validation
            if decision.data_size_bytes <= 0:
                return False

            if decision.source_tier == decision.target_tier:
                return False

            # Check if source and target tiers are valid
            if not self._current_resources:
                return False

            if (decision.source_tier not in self._current_resources.tier_capacities or
                decision.target_tier not in self._current_resources.tier_capacities):
                return False

            # Check confidence threshold
            if decision.confidence_score < 0.5:
                return False

            return True

        except Exception as e:
            self._logger.error(f"Error validating reallocation decision: {e}")
            return False

    async def _check_target_capacity(self, decision: ReallocationDecision) -> bool:
        """Check if target tier has sufficient capacity."""
        try:
            if not self._current_resources:
                return False

            available_bytes = self._current_resources.tier_available.get(decision.target_tier, 0)
            return available_bytes >= decision.data_size_bytes

        except Exception as e:
            self._logger.error(f"Error checking target capacity: {e}")
            return False

    async def _perform_data_transfer(self, decision: ReallocationDecision) -> bool:
        """Perform the actual data transfer."""
        try:
            # In a real implementation, this would interface with the memory bridging system
            # For now, we'll simulate the transfer

            self._logger.debug(f"Simulating transfer of {decision.data_size_bytes} bytes "
                             f"from {decision.source_tier.value} to {decision.target_tier.value}")

            # Simulate transfer time based on data size and tier characteristics
            if not self._current_resources:
                return False

            source_bandwidth = self._current_resources.tier_bandwidth.get(decision.source_tier, 1.0)
            target_bandwidth = self._current_resources.tier_bandwidth.get(decision.target_tier, 1.0)
            effective_bandwidth = min(source_bandwidth, target_bandwidth)

            transfer_time_seconds = decision.data_size_bytes / (effective_bandwidth * 1024**3)  # Convert GB/s to bytes/s

            # Simulate the transfer delay
            await asyncio.sleep(min(transfer_time_seconds, 0.1))  # Cap simulation delay at 100ms

            # Simulate 95% success rate
            import random
            return random.random() < 0.95

        except Exception as e:
            self._logger.error(f"Error performing data transfer: {e}")
            return False

    async def _measure_performance_improvement(self, decision: ReallocationDecision) -> float:
        """Measure performance improvement after reallocation."""
        try:
            # In a real implementation, this would measure actual performance metrics
            # For now, we'll estimate based on tier characteristics

            if not self._current_resources:
                return 0.0

            source_latency = self._current_resources.tier_latency.get(decision.source_tier, 10.0)
            target_latency = self._current_resources.tier_latency.get(decision.target_tier, 10.0)

            # Calculate latency improvement
            latency_improvement = max(0, (source_latency - target_latency) / source_latency)

            # Calculate bandwidth improvement
            source_bandwidth = self._current_resources.tier_bandwidth.get(decision.source_tier, 1.0)
            target_bandwidth = self._current_resources.tier_bandwidth.get(decision.target_tier, 1.0)
            bandwidth_improvement = max(0, (target_bandwidth - source_bandwidth) / source_bandwidth)

            # Weighted average improvement
            overall_improvement = (latency_improvement * 0.6 + bandwidth_improvement * 0.4)

            return min(overall_improvement, 1.0)  # Cap at 100% improvement

        except Exception as e:
            self._logger.error(f"Error measuring performance improvement: {e}")
            return 0.0

    # Helper methods for estimation and calculation
    def _estimate_memory_bandwidth(self, tier_usage: Dict[MemoryTier, float]) -> float:
        """Estimate current memory bandwidth."""
        try:
            # Simulate bandwidth based on tier utilization
            total_bandwidth = 0.0
            for tier, utilization in tier_usage.items():
                if tier == MemoryTier.GPU_VRAM:
                    tier_bandwidth = 900.0 * (1.0 - utilization * 0.3)  # GB/s, reduced by utilization
                elif tier == MemoryTier.SYSTEM_RAM:
                    tier_bandwidth = 50.0 * (1.0 - utilization * 0.2)
                elif tier == MemoryTier.NVME_CACHE:
                    tier_bandwidth = 7.0 * (1.0 - utilization * 0.1)
                else:
                    tier_bandwidth = 0.5 * (1.0 - utilization * 0.1)

                total_bandwidth += tier_bandwidth * utilization

            return total_bandwidth

        except Exception:
            return 50.0  # Default bandwidth

    def _estimate_access_latency(self, tier_usage: Dict[MemoryTier, float]) -> float:
        """Estimate current access latency."""
        try:
            # Weighted average latency based on tier usage
            total_latency = 0.0
            total_weight = 0.0

            for tier, utilization in tier_usage.items():
                if tier == MemoryTier.GPU_VRAM:
                    tier_latency = 0.1  # ms
                elif tier == MemoryTier.SYSTEM_RAM:
                    tier_latency = 0.05
                elif tier == MemoryTier.NVME_CACHE:
                    tier_latency = 0.02
                else:
                    tier_latency = 5.0

                total_latency += tier_latency * utilization
                total_weight += utilization

            return total_latency / max(total_weight, 0.1)

        except Exception:
            return 1.0  # Default latency

    def _estimate_cache_hit_ratio(self) -> float:
        """Estimate cache hit ratio."""
        try:
            # Simulate cache hit ratio based on recent performance
            if self._performance_history:
                recent_performance = list(self._performance_history)[-5:]
                avg_utilization = statistics.mean([
                    statistics.mean(p.tier_utilization.values())
                    for p in recent_performance
                ])
                # Higher utilization generally means lower cache hit ratio
                return max(0.5, 0.95 - avg_utilization * 0.3)
            return 0.85

        except Exception:
            return 0.85

    def _estimate_throughput(self) -> float:
        """Estimate current throughput."""
        try:
            # Simulate throughput based on bandwidth and latency
            if self._current_performance:
                bandwidth_factor = self._current_performance.memory_bandwidth_gbps / 100.0
                latency_factor = 10.0 / max(self._current_performance.access_latency_ms, 0.1)
                return bandwidth_factor * latency_factor * 1000.0  # ops/sec
            return 5000.0

        except Exception:
            return 5000.0

    def _estimate_fragmentation_ratio(self) -> float:
        """Estimate memory fragmentation ratio."""
        try:
            # Simulate fragmentation based on allocation patterns
            if self._reallocation_history:
                recent_reallocations = len([r for r in self._reallocation_history
                                          if (datetime.now(timezone.utc) - r.timestamp).total_seconds() < 300])
                # More recent reallocations suggest higher fragmentation
                return min(0.5, recent_reallocations * 0.05)
            return 0.1

        except Exception:
            return 0.1

    def _estimate_power_consumption(self, tier_usage: Dict[MemoryTier, float]) -> float:
        """Estimate power consumption."""
        try:
            total_power = 0.0
            for tier, utilization in tier_usage.items():
                if tier == MemoryTier.GPU_VRAM:
                    tier_power = 300.0 * utilization  # Watts
                elif tier == MemoryTier.SYSTEM_RAM:
                    tier_power = 50.0 * utilization
                elif tier == MemoryTier.NVME_CACHE:
                    tier_power = 10.0 * utilization
                else:
                    tier_power = 5.0 * utilization

                total_power += tier_power

            return total_power

        except Exception:
            return 100.0

    def _estimate_temperature(self) -> float:
        """Estimate system temperature."""
        try:
            # Simulate temperature based on power consumption
            if self._current_performance:
                base_temp = 25.0  # Celsius
                power_factor = self._current_performance.power_consumption_watts / 100.0
                return base_temp + power_factor * 15.0
            return 35.0

        except Exception:
            return 35.0

    def _is_beneficial_transfer(self, source_tier: MemoryTier, target_tier: MemoryTier,
                              resources: ResourceAvailability) -> bool:
        """Check if transfer between tiers is beneficial."""
        try:
            source_latency = resources.tier_latency.get(source_tier, 10.0)
            target_latency = resources.tier_latency.get(target_tier, 10.0)

            source_bandwidth = resources.tier_bandwidth.get(source_tier, 1.0)
            target_bandwidth = resources.tier_bandwidth.get(target_tier, 1.0)

            # Transfer is beneficial if target has better performance characteristics
            return (target_latency < source_latency * 1.2 or target_bandwidth > source_bandwidth * 1.2)

        except Exception:
            return False

    def _calculate_imbalance_benefit(self, over_utilization: float, under_utilization: float) -> float:
        """Calculate benefit of rebalancing tier utilization."""
        try:
            # Benefit is proportional to the imbalance severity
            imbalance_severity = over_utilization - under_utilization
            return min(1.0, imbalance_severity * 2.0)

        except Exception:
            return 0.0

    def _calculate_latency_benefit(self, source_tier: MemoryTier, target_tier: MemoryTier,
                                 resources: ResourceAvailability) -> float:
        """Calculate benefit of latency optimization."""
        try:
            source_latency = resources.tier_latency.get(source_tier, 10.0)
            target_latency = resources.tier_latency.get(target_tier, 10.0)

            if target_latency >= source_latency:
                return 0.0

            latency_improvement = (source_latency - target_latency) / source_latency
            return min(1.0, latency_improvement * 2.0)

        except Exception:
            return 0.0

    def _calculate_defragmentation_benefit(self, tier: MemoryTier, fragmentation_ratio: float) -> float:
        """Calculate benefit of defragmentation."""
        try:
            # Benefit is proportional to fragmentation severity
            return min(1.0, fragmentation_ratio * 1.5)

        except Exception:
            return 0.0

    def _calculate_transfer_cost(self, source_tier: MemoryTier, target_tier: MemoryTier,
                               transfer_size: int, resources: ResourceAvailability) -> float:
        """Calculate cost of data transfer."""
        try:
            # Cost factors: transfer time, power consumption, resource contention
            source_bandwidth = resources.tier_bandwidth.get(source_tier, 1.0)
            target_bandwidth = resources.tier_bandwidth.get(target_tier, 1.0)
            effective_bandwidth = min(source_bandwidth, target_bandwidth)

            # Transfer time cost (normalized)
            transfer_time_seconds = transfer_size / (effective_bandwidth * 1024**3)
            time_cost = min(1.0, transfer_time_seconds / 10.0)  # Normalize to 10 seconds max

            # Power consumption cost
            source_power = resources.tier_power_usage.get(source_tier, 10.0)
            target_power = resources.tier_power_usage.get(target_tier, 10.0)
            power_cost = min(1.0, (source_power + target_power) / 200.0)  # Normalize to 200W max

            # Resource contention cost (based on current utilization)
            if self._current_performance:
                source_util = self._current_performance.tier_utilization.get(source_tier, 0.5)
                target_util = self._current_performance.tier_utilization.get(target_tier, 0.5)
                contention_cost = (source_util + target_util) / 2.0
            else:
                contention_cost = 0.5

            # Weighted total cost
            total_cost = (time_cost * 0.4 + power_cost * 0.3 + contention_cost * 0.3)
            return min(1.0, total_cost)

        except Exception:
            return 0.5  # Default moderate cost

    def _create_bandwidth_optimization_decisions(self, performance: PerformanceMetrics,
                                               resources: ResourceAvailability) -> List[ReallocationDecision]:
        """Create decisions for bandwidth optimization."""
        decisions = []

        try:
            # Identify tiers with bandwidth bottlenecks
            for tier, utilization in performance.tier_utilization.items():
                if utilization > 0.8:  # High utilization threshold
                    tier_bandwidth = resources.tier_bandwidth.get(tier, 1.0)

                    # Find alternative tiers with better bandwidth
                    for alt_tier in MemoryTier:
                        if alt_tier != tier:
                            alt_bandwidth = resources.tier_bandwidth.get(alt_tier, 1.0)
                            alt_utilization = performance.tier_utilization.get(alt_tier, 0.0)

                            if alt_bandwidth > tier_bandwidth * 1.5 and alt_utilization < 0.6:
                                transfer_size = int(resources.tier_capacities[tier] * 0.2)

                                benefit = self._calculate_latency_benefit(tier, alt_tier, resources)
                                cost = self._calculate_transfer_cost(tier, alt_tier, transfer_size, resources)

                                decision = ReallocationDecision(
                                    source_tier=tier,
                                    target_tier=alt_tier,
                                    data_size_bytes=transfer_size,
                                    data_identifier=f"bandwidth_optimization_{tier.value}_to_{alt_tier.value}",
                                    priority=7,
                                    estimated_benefit=benefit,
                                    estimated_cost=cost,
                                    confidence_score=0.7,
                                    reasoning=f"Optimize bandwidth by moving data from {tier.value} to {alt_tier.value}"
                                )

                                decisions.append(decision)
                                break  # One decision per bottlenecked tier

            return decisions

        except Exception as e:
            self._logger.error(f"Error creating bandwidth optimization decisions: {e}")
            return []
