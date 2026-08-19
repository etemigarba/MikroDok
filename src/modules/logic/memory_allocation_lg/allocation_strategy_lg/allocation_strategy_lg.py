"""
Module: allocation_strategy_lg
Description: Implements core allocation algorithms for Legacy, Hybrid, and Auto IDRAlloc modes with intelligent mode selection based on hardware capabilities
Phase: 2
Location: /src/modules/logic/memory_allocation_lg/allocation_strategy_lg/
"""

# Standard library imports
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Dict, List, Optional, Tuple

# Third-party imports
import psutil

# Local imports
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import (
    MemoryTier, PressureLevel
)


class IDRAllocMode(Enum):
    """IDRAlloc allocation modes."""
    LEGACY = "LEGACY"
    HYBRID = "HYBRID"
    AUTO = "AUTO"


class AllocationDecision(Enum):
    """Allocation decision types."""
    GPU_ONLY = "GPU_ONLY"
    RAM_FALLBACK = "RAM_FALLBACK"
    NVME_OFFLOAD = "NVME_OFFLOAD"
    TIERED_ALLOCATION = "TIERED_ALLOCATION"
    EMERGENCY_MODE = "EMERGENCY_MODE"


@dataclass
class HardwareProfile:
    """Hardware configuration profile."""
    gpu_vram_gb: float
    system_ram_gb: float
    nvme_capacity_gb: float
    nvme_bandwidth_gbps: float
    gpu_compute_capability: str
    cpu_cores: int
    memory_bandwidth_gbps: float


@dataclass
class AllocationMetrics:
    """Allocation performance metrics."""
    allocation_time_ms: float
    memory_efficiency: float
    bandwidth_utilization: float
    tier_distribution: Dict[str, float]
    pressure_level: PressureLevel
    success_rate: float


@dataclass
class StrategyConfiguration:
    """Configuration for allocation strategy."""
    mode: IDRAllocMode
    gpu_threshold_percent: float = 85.0
    ram_threshold_percent: float = 90.0
    nvme_threshold_percent: float = 95.0
    auto_mode_sensitivity: float = 0.8
    enable_predictive_allocation: bool = True
    emergency_threshold_percent: float = 98.0


@dataclass
class AllocationResult:
    """Result of allocation strategy execution."""
    decision: AllocationDecision
    tier_allocations: Dict[MemoryTier, int]
    confidence_score: float
    estimated_performance: float
    fallback_options: List[AllocationDecision]
    metrics: AllocationMetrics


class IAllocationStrategy(ABC):
    """Interface for memory allocation strategies."""
    
    @abstractmethod
    def determine_allocation_strategy(self, memory_requirement_bytes: int,
                                    hardware_profile: HardwareProfile,
                                    current_usage: Dict[MemoryTier, float]) -> AllocationResult:
        """Determine optimal allocation strategy."""
        pass
    
    @abstractmethod
    def evaluate_mode_effectiveness(self, mode: IDRAllocMode,
                                  performance_history: List[AllocationMetrics]) -> float:
        """Evaluate effectiveness of allocation mode."""
        pass
    
    @abstractmethod
    def recommend_mode_switch(self, current_mode: IDRAllocMode,
                            performance_metrics: AllocationMetrics) -> Optional[IDRAllocMode]:
        """Recommend mode switch based on performance."""
        pass


class AllocationStrategy(IAllocationStrategy):
    """Core allocation strategy implementation for IDRAlloc system."""
    
    def __init__(self, config: StrategyConfiguration):
        """Initialize allocation strategy."""
        self._config = config
        self._logger = logging.getLogger(__name__)
        self._lock = Lock()
        
        # Performance tracking
        self._allocation_history: List[AllocationResult] = []
        self._mode_performance: Dict[IDRAllocMode, List[AllocationMetrics]] = {
            mode: [] for mode in IDRAllocMode
        }
        
        # Hardware detection cache
        self._hardware_cache: Optional[HardwareProfile] = None
        self._cache_timestamp = 0.0
        self._cache_ttl = 300.0  # 5 minutes
        
        self._logger.info(f"Allocation strategy initialized with mode: {config.mode}")
    
    def determine_allocation_strategy(self, memory_requirement_bytes: int,
                                    hardware_profile: HardwareProfile,
                                    current_usage: Dict[MemoryTier, float]) -> AllocationResult:
        """
        Determine optimal allocation strategy based on requirements and hardware.
        
        Args:
            memory_requirement_bytes: Required memory in bytes
            hardware_profile: Hardware configuration
            current_usage: Current memory usage per tier
            
        Returns:
            Allocation result with strategy and metrics
        """
        start_time = time.time()
        
        try:
            with self._lock:
                # Analyze current memory pressure
                pressure_level = self._analyze_memory_pressure(current_usage)
                
                # Determine allocation decision based on mode
                if self._config.mode == IDRAllocMode.LEGACY:
                    decision = self._legacy_allocation(memory_requirement_bytes, hardware_profile, current_usage)
                elif self._config.mode == IDRAllocMode.HYBRID:
                    decision = self._hybrid_allocation(memory_requirement_bytes, hardware_profile, current_usage)
                else:  # AUTO mode
                    decision = self._auto_allocation(memory_requirement_bytes, hardware_profile, current_usage)
                
                # Calculate tier allocations
                tier_allocations = self._calculate_tier_allocations(
                    decision, memory_requirement_bytes, hardware_profile
                )
                
                # Estimate performance
                estimated_performance = self._estimate_performance(
                    decision, tier_allocations, hardware_profile
                )
                
                # Generate fallback options
                fallback_options = self._generate_fallback_options(
                    decision, memory_requirement_bytes, current_usage
                )
                
                # Calculate confidence score
                confidence_score = self._calculate_confidence_score(
                    decision, current_usage, hardware_profile
                )
                
                # Create metrics
                allocation_time = (time.time() - start_time) * 1000
                metrics = AllocationMetrics(
                    allocation_time_ms=allocation_time,
                    memory_efficiency=self._calculate_memory_efficiency(tier_allocations),
                    bandwidth_utilization=self._calculate_bandwidth_utilization(tier_allocations, hardware_profile),
                    tier_distribution=self._calculate_tier_distribution(tier_allocations),
                    pressure_level=pressure_level,
                    success_rate=self._calculate_success_rate()
                )
                
                # Create result
                result = AllocationResult(
                    decision=decision,
                    tier_allocations=tier_allocations,
                    confidence_score=confidence_score,
                    estimated_performance=estimated_performance,
                    fallback_options=fallback_options,
                    metrics=metrics
                )
                
                # Record allocation
                self._allocation_history.append(result)
                self._mode_performance[self._config.mode].append(metrics)
                
                # Limit history size
                if len(self._allocation_history) > 1000:
                    self._allocation_history = self._allocation_history[-500:]
                
                self._logger.debug(f"Allocation strategy determined: {decision} (confidence: {confidence_score:.2f})")
                
                return result
                
        except Exception as e:
            self._logger.error(f"Error determining allocation strategy: {e}")
            # Return emergency fallback
            return self._emergency_allocation(memory_requirement_bytes)
    
    def evaluate_mode_effectiveness(self, mode: IDRAllocMode,
                                  performance_history: List[AllocationMetrics]) -> float:
        """
        Evaluate effectiveness of allocation mode.
        
        Args:
            mode: IDRAlloc mode to evaluate
            performance_history: Historical performance metrics
            
        Returns:
            Effectiveness score (0.0 to 1.0)
        """
        try:
            if not performance_history:
                return 0.5  # Neutral score for no data
            
            # Calculate weighted effectiveness score
            total_score = 0.0
            weights = {
                'memory_efficiency': 0.3,
                'bandwidth_utilization': 0.25,
                'success_rate': 0.25,
                'allocation_time': 0.2
            }
            
            # Memory efficiency score
            avg_memory_efficiency = sum(m.memory_efficiency for m in performance_history) / len(performance_history)
            total_score += weights['memory_efficiency'] * avg_memory_efficiency
            
            # Bandwidth utilization score
            avg_bandwidth = sum(m.bandwidth_utilization for m in performance_history) / len(performance_history)
            total_score += weights['bandwidth_utilization'] * avg_bandwidth
            
            # Success rate score
            avg_success_rate = sum(m.success_rate for m in performance_history) / len(performance_history)
            total_score += weights['success_rate'] * avg_success_rate
            
            # Allocation time score (inverted - lower is better)
            avg_allocation_time = sum(m.allocation_time_ms for m in performance_history) / len(performance_history)
            time_score = max(0.0, 1.0 - (avg_allocation_time / 1000.0))  # Normalize to 1 second
            total_score += weights['allocation_time'] * time_score
            
            return min(1.0, max(0.0, total_score))
            
        except Exception as e:
            self._logger.error(f"Error evaluating mode effectiveness: {e}")
            return 0.5
    
    def recommend_mode_switch(self, current_mode: IDRAllocMode,
                            performance_metrics: AllocationMetrics) -> Optional[IDRAllocMode]:
        """
        Recommend mode switch based on performance.
        
        Args:
            current_mode: Current allocation mode
            performance_metrics: Recent performance metrics
            
        Returns:
            Recommended mode or None if no switch needed
        """
        try:
            # Evaluate current mode performance
            current_effectiveness = self.evaluate_mode_effectiveness(
                current_mode, self._mode_performance[current_mode][-10:]  # Last 10 allocations
            )
            
            # Check if performance is below threshold
            if current_effectiveness >= self._config.auto_mode_sensitivity:
                return None  # Current mode is performing well
            
            # Evaluate alternative modes
            best_mode = current_mode
            best_score = current_effectiveness
            
            for mode in IDRAllocMode:
                if mode == current_mode:
                    continue
                
                mode_history = self._mode_performance[mode][-10:]
                if not mode_history:
                    continue  # No data for this mode
                
                effectiveness = self.evaluate_mode_effectiveness(mode, mode_history)
                if effectiveness > best_score + 0.1:  # Require significant improvement
                    best_mode = mode
                    best_score = effectiveness
            
            if best_mode != current_mode:
                self._logger.info(f"Recommending mode switch from {current_mode} to {best_mode} "
                                f"(effectiveness: {current_effectiveness:.2f} -> {best_score:.2f})")
                return best_mode
            
            return None

        except Exception as e:
            self._logger.error(f"Error recommending mode switch: {e}")
            return None

    def _analyze_memory_pressure(self, current_usage: Dict[MemoryTier, float]) -> PressureLevel:
        """Analyze current memory pressure across tiers."""
        try:
            max_usage = max(current_usage.values()) if current_usage else 0.0

            if max_usage >= self._config.emergency_threshold_percent:
                return PressureLevel.CRITICAL
            elif max_usage >= self._config.nvme_threshold_percent:
                return PressureLevel.HIGH
            elif max_usage >= self._config.ram_threshold_percent:
                return PressureLevel.MODERATE
            else:
                return PressureLevel.LOW

        except Exception:
            return PressureLevel.MODERATE

    def _legacy_allocation(self, memory_requirement_bytes: int,
                          hardware_profile: HardwareProfile,
                          current_usage: Dict[MemoryTier, float]) -> AllocationDecision:
        """Legacy allocation strategy - GPU first, then RAM, then NVMe."""
        try:
            gpu_usage = current_usage.get(MemoryTier.GPU_VRAM, 0.0)
            ram_usage = current_usage.get(MemoryTier.SYSTEM_RAM, 0.0)

            # Calculate available space
            gpu_available_gb = hardware_profile.gpu_vram_gb * (1.0 - gpu_usage / 100.0)
            ram_available_gb = hardware_profile.system_ram_gb * (1.0 - ram_usage / 100.0)

            memory_requirement_gb = memory_requirement_bytes / (1024**3)

            if memory_requirement_gb <= gpu_available_gb * 0.8:  # Leave 20% buffer
                return AllocationDecision.GPU_ONLY
            elif memory_requirement_gb <= ram_available_gb * 0.8:
                return AllocationDecision.RAM_FALLBACK
            else:
                return AllocationDecision.NVME_OFFLOAD

        except Exception:
            return AllocationDecision.EMERGENCY_MODE

    def _hybrid_allocation(self, memory_requirement_bytes: int,
                          hardware_profile: HardwareProfile,
                          current_usage: Dict[MemoryTier, float]) -> AllocationDecision:
        """Hybrid allocation strategy - intelligent tier distribution."""
        try:
            memory_requirement_gb = memory_requirement_bytes / (1024**3)

            # Calculate tier capacities and usage
            gpu_usage = current_usage.get(MemoryTier.GPU_VRAM, 0.0)
            ram_usage = current_usage.get(MemoryTier.SYSTEM_RAM, 0.0)
            nvme_usage = current_usage.get(MemoryTier.NVME_CACHE, 0.0)

            # Check if tiered allocation is beneficial
            total_available = (
                hardware_profile.gpu_vram_gb * (1.0 - gpu_usage / 100.0) +
                hardware_profile.system_ram_gb * (1.0 - ram_usage / 100.0) * 0.5 +  # Weight RAM lower
                hardware_profile.nvme_capacity_gb * (1.0 - nvme_usage / 100.0) * 0.1  # Weight NVMe much lower
            )

            if memory_requirement_gb <= total_available:
                return AllocationDecision.TIERED_ALLOCATION
            else:
                return self._legacy_allocation(memory_requirement_bytes, hardware_profile, current_usage)

        except Exception:
            return AllocationDecision.EMERGENCY_MODE

    def _auto_allocation(self, memory_requirement_bytes: int,
                        hardware_profile: HardwareProfile,
                        current_usage: Dict[MemoryTier, float]) -> AllocationDecision:
        """Auto allocation strategy - adaptive based on performance history."""
        try:
            # Use performance history to make intelligent decisions
            recent_performance = self._mode_performance[IDRAllocMode.AUTO][-5:]

            if not recent_performance:
                # No history, use hybrid approach
                return self._hybrid_allocation(memory_requirement_bytes, hardware_profile, current_usage)

            # Analyze recent performance patterns
            avg_efficiency = sum(m.memory_efficiency for m in recent_performance) / len(recent_performance)
            avg_bandwidth = sum(m.bandwidth_utilization for m in recent_performance) / len(recent_performance)

            # Make decision based on performance patterns
            if avg_efficiency > 0.8 and avg_bandwidth > 0.7:
                # Good performance, continue with current approach
                return self._hybrid_allocation(memory_requirement_bytes, hardware_profile, current_usage)
            elif avg_efficiency < 0.5:
                # Poor efficiency, try legacy approach
                return self._legacy_allocation(memory_requirement_bytes, hardware_profile, current_usage)
            else:
                # Moderate performance, use tiered allocation
                return AllocationDecision.TIERED_ALLOCATION

        except Exception:
            return AllocationDecision.EMERGENCY_MODE

    def _calculate_tier_allocations(self, decision: AllocationDecision,
                                   memory_requirement_bytes: int,
                                   hardware_profile: HardwareProfile) -> Dict[MemoryTier, int]:
        """Calculate memory allocation per tier based on decision."""
        allocations = {tier: 0 for tier in MemoryTier}

        try:
            if decision == AllocationDecision.GPU_ONLY:
                allocations[MemoryTier.GPU_VRAM] = memory_requirement_bytes

            elif decision == AllocationDecision.RAM_FALLBACK:
                allocations[MemoryTier.SYSTEM_RAM] = memory_requirement_bytes

            elif decision == AllocationDecision.NVME_OFFLOAD:
                allocations[MemoryTier.NVME_CACHE] = memory_requirement_bytes

            elif decision == AllocationDecision.TIERED_ALLOCATION:
                # Distribute across tiers based on performance characteristics
                gpu_portion = min(0.6, hardware_profile.gpu_vram_gb / (memory_requirement_bytes / (1024**3)))
                ram_portion = min(0.3, (1.0 - gpu_portion))
                nvme_portion = 1.0 - gpu_portion - ram_portion

                allocations[MemoryTier.GPU_VRAM] = int(memory_requirement_bytes * gpu_portion)
                allocations[MemoryTier.SYSTEM_RAM] = int(memory_requirement_bytes * ram_portion)
                allocations[MemoryTier.NVME_CACHE] = int(memory_requirement_bytes * nvme_portion)

            else:  # EMERGENCY_MODE
                # Minimal GPU allocation, rest to system RAM
                allocations[MemoryTier.GPU_VRAM] = min(memory_requirement_bytes, int(0.5 * 1024**3))  # 512MB max
                allocations[MemoryTier.SYSTEM_RAM] = memory_requirement_bytes - allocations[MemoryTier.GPU_VRAM]

        except Exception as e:
            self._logger.error(f"Error calculating tier allocations: {e}")
            # Fallback to system RAM
            allocations[MemoryTier.SYSTEM_RAM] = memory_requirement_bytes

        return allocations

    def _estimate_performance(self, decision: AllocationDecision,
                             tier_allocations: Dict[MemoryTier, int],
                             hardware_profile: HardwareProfile) -> float:
        """Estimate performance score for allocation decision."""
        try:
            # Base performance scores for each tier
            tier_performance = {
                MemoryTier.GPU_VRAM: 1.0,
                MemoryTier.SYSTEM_RAM: 0.6,
                MemoryTier.NVME_CACHE: 0.3,
                MemoryTier.SSD_STORAGE: 0.1
            }

            total_bytes = sum(tier_allocations.values())
            if total_bytes == 0:
                return 0.0

            weighted_performance = 0.0
            for tier, bytes_allocated in tier_allocations.items():
                if bytes_allocated > 0:
                    weight = bytes_allocated / total_bytes
                    weighted_performance += weight * tier_performance.get(tier, 0.1)

            # Apply hardware-specific adjustments
            if hardware_profile.nvme_bandwidth_gbps > 5.0:
                # High-speed NVMe, boost NVMe performance
                nvme_weight = tier_allocations.get(MemoryTier.NVME_CACHE, 0) / total_bytes
                weighted_performance += nvme_weight * 0.2

            return min(1.0, weighted_performance)

        except Exception:
            return 0.5

    def _generate_fallback_options(self, primary_decision: AllocationDecision,
                                  memory_requirement_bytes: int,
                                  current_usage: Dict[MemoryTier, float]) -> List[AllocationDecision]:
        """Generate fallback allocation options."""
        fallbacks = []

        try:
            # Add fallback options based on primary decision
            if primary_decision == AllocationDecision.GPU_ONLY:
                fallbacks.extend([AllocationDecision.RAM_FALLBACK, AllocationDecision.TIERED_ALLOCATION])
            elif primary_decision == AllocationDecision.RAM_FALLBACK:
                fallbacks.extend([AllocationDecision.NVME_OFFLOAD, AllocationDecision.TIERED_ALLOCATION])
            elif primary_decision == AllocationDecision.TIERED_ALLOCATION:
                fallbacks.extend([AllocationDecision.RAM_FALLBACK, AllocationDecision.NVME_OFFLOAD])
            else:
                fallbacks.extend([AllocationDecision.RAM_FALLBACK, AllocationDecision.EMERGENCY_MODE])

            # Always include emergency mode as final fallback
            if AllocationDecision.EMERGENCY_MODE not in fallbacks:
                fallbacks.append(AllocationDecision.EMERGENCY_MODE)

        except Exception:
            fallbacks = [AllocationDecision.EMERGENCY_MODE]

        return fallbacks[:3]  # Limit to 3 fallback options

    def _calculate_confidence_score(self, decision: AllocationDecision,
                                   current_usage: Dict[MemoryTier, float],
                                   hardware_profile: HardwareProfile) -> float:
        """Calculate confidence score for allocation decision."""
        try:
            base_confidence = 0.7

            # Adjust based on memory pressure
            max_usage = max(current_usage.values()) if current_usage else 0.0
            if max_usage < 70.0:
                base_confidence += 0.2
            elif max_usage > 90.0:
                base_confidence -= 0.3

            # Adjust based on decision type
            if decision == AllocationDecision.GPU_ONLY:
                base_confidence += 0.1  # High confidence for GPU allocation
            elif decision == AllocationDecision.EMERGENCY_MODE:
                base_confidence -= 0.4  # Low confidence for emergency mode

            # Adjust based on hardware capabilities
            if hardware_profile.nvme_bandwidth_gbps > 5.0:
                base_confidence += 0.1  # Good NVMe performance

            return min(1.0, max(0.0, base_confidence))

        except Exception:
            return 0.5

    def _calculate_memory_efficiency(self, tier_allocations: Dict[MemoryTier, int]) -> float:
        """Calculate memory efficiency score."""
        try:
            total_allocation = sum(tier_allocations.values())
            if total_allocation == 0:
                return 0.0

            # Weight efficiency by tier performance
            efficiency_weights = {
                MemoryTier.GPU_VRAM: 1.0,
                MemoryTier.SYSTEM_RAM: 0.8,
                MemoryTier.NVME_CACHE: 0.5,
                MemoryTier.SSD_STORAGE: 0.2
            }

            weighted_efficiency = 0.0
            for tier, allocation in tier_allocations.items():
                if allocation > 0:
                    weight = allocation / total_allocation
                    tier_efficiency = efficiency_weights.get(tier, 0.1)
                    weighted_efficiency += weight * tier_efficiency

            return weighted_efficiency

        except Exception:
            return 0.5

    def _calculate_bandwidth_utilization(self, tier_allocations: Dict[MemoryTier, int],
                                        hardware_profile: HardwareProfile) -> float:
        """Calculate bandwidth utilization score."""
        try:
            # Estimate bandwidth requirements based on allocations
            total_allocation = sum(tier_allocations.values())
            if total_allocation == 0:
                return 0.0

            # Bandwidth scores based on tier characteristics
            bandwidth_scores = {
                MemoryTier.GPU_VRAM: 1.0,  # Highest bandwidth
                MemoryTier.SYSTEM_RAM: 0.7,  # Good bandwidth
                MemoryTier.NVME_CACHE: min(0.6, hardware_profile.nvme_bandwidth_gbps / 10.0),  # Variable
                MemoryTier.SSD_STORAGE: 0.2  # Limited bandwidth
            }

            weighted_bandwidth = 0.0
            for tier, allocation in tier_allocations.items():
                if allocation > 0:
                    weight = allocation / total_allocation
                    tier_bandwidth = bandwidth_scores.get(tier, 0.1)
                    weighted_bandwidth += weight * tier_bandwidth

            return weighted_bandwidth

        except Exception:
            return 0.5

    def _calculate_tier_distribution(self, tier_allocations: Dict[MemoryTier, int]) -> Dict[str, float]:
        """Calculate tier distribution percentages."""
        try:
            total_allocation = sum(tier_allocations.values())
            if total_allocation == 0:
                return {}

            distribution = {}
            for tier, allocation in tier_allocations.items():
                if allocation > 0:
                    percentage = (allocation / total_allocation) * 100.0
                    distribution[tier.value] = percentage

            return distribution

        except Exception:
            return {}

    def _calculate_success_rate(self) -> float:
        """Calculate recent allocation success rate."""
        try:
            if not self._allocation_history:
                return 1.0

            # Look at last 20 allocations
            recent_allocations = self._allocation_history[-20:]
            successful = sum(1 for alloc in recent_allocations
                           if alloc.decision != AllocationDecision.EMERGENCY_MODE)

            return successful / len(recent_allocations)

        except Exception:
            return 0.5

    def _emergency_allocation(self, memory_requirement_bytes: int) -> AllocationResult:
        """Create emergency allocation result."""
        try:
            # Minimal allocation to system RAM
            tier_allocations = {tier: 0 for tier in MemoryTier}
            tier_allocations[MemoryTier.SYSTEM_RAM] = memory_requirement_bytes

            metrics = AllocationMetrics(
                allocation_time_ms=1.0,
                memory_efficiency=0.3,
                bandwidth_utilization=0.4,
                tier_distribution={"SYSTEM_RAM": 100.0},
                pressure_level=PressureLevel.CRITICAL,
                success_rate=0.5
            )

            return AllocationResult(
                decision=AllocationDecision.EMERGENCY_MODE,
                tier_allocations=tier_allocations,
                confidence_score=0.2,
                estimated_performance=0.3,
                fallback_options=[],
                metrics=metrics
            )

        except Exception as e:
            self._logger.error(f"Error creating emergency allocation: {e}")
            # Absolute fallback
            return AllocationResult(
                decision=AllocationDecision.EMERGENCY_MODE,
                tier_allocations={MemoryTier.SYSTEM_RAM: memory_requirement_bytes},
                confidence_score=0.1,
                estimated_performance=0.1,
                fallback_options=[],
                metrics=AllocationMetrics(
                    allocation_time_ms=1.0,
                    memory_efficiency=0.1,
                    bandwidth_utilization=0.1,
                    tier_distribution={},
                    pressure_level=PressureLevel.CRITICAL,
                    success_rate=0.1
                )
            )

    def get_allocation_statistics(self) -> Dict[str, float]:
        """Get allocation performance statistics."""
        try:
            if not self._allocation_history:
                return {}

            recent_allocations = self._allocation_history[-100:]  # Last 100 allocations

            # Calculate statistics
            avg_confidence = sum(alloc.confidence_score for alloc in recent_allocations) / len(recent_allocations)
            avg_performance = sum(alloc.estimated_performance for alloc in recent_allocations) / len(recent_allocations)
            avg_allocation_time = sum(alloc.metrics.allocation_time_ms for alloc in recent_allocations) / len(recent_allocations)

            # Decision distribution
            decision_counts = {}
            for alloc in recent_allocations:
                decision = alloc.decision.value
                decision_counts[decision] = decision_counts.get(decision, 0) + 1

            return {
                'average_confidence': avg_confidence,
                'average_performance': avg_performance,
                'average_allocation_time_ms': avg_allocation_time,
                'total_allocations': len(self._allocation_history),
                'recent_allocations': len(recent_allocations),
                **{f'decision_{k}_percent': (v / len(recent_allocations)) * 100
                   for k, v in decision_counts.items()}
            }

        except Exception as e:
            self._logger.error(f"Error getting allocation statistics: {e}")
            return {}
