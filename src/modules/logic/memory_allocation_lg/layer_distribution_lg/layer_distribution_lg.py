"""
Module: layer_distribution_lg
Description: Distributes model layers across memory tiers based on access patterns and criticality (embeddings, output layers prioritized)
Phase: 2
Location: /src/modules/logic/memory_allocation_lg/layer_distribution_lg/
"""

# Standard library imports
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Dict, List, Optional, Set, Tuple

# Local imports
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import MemoryTier


class LayerPriority(Enum):
    """Layer priority levels for memory allocation."""
    CRITICAL = "CRITICAL"  # Embeddings, output layers
    HIGH = "HIGH"  # Attention layers, key transformations
    MEDIUM = "MEDIUM"  # Hidden layers, intermediate computations
    LOW = "LOW"  # Temporary buffers, cache layers


class AccessPattern(Enum):
    """Layer access patterns during training/inference."""
    SEQUENTIAL = "SEQUENTIAL"  # Accessed in order
    RANDOM = "RANDOM"  # Accessed randomly
    FREQUENT = "FREQUENT"  # Accessed very frequently
    SPARSE = "SPARSE"  # Accessed infrequently
    BATCH_DEPENDENT = "BATCH_DEPENDENT"  # Access depends on batch


class DistributionStrategy(Enum):
    """Layer distribution strategies."""
    PRIORITY_BASED = "PRIORITY_BASED"  # Distribute by layer priority
    ACCESS_PATTERN = "ACCESS_PATTERN"  # Distribute by access patterns
    SIZE_OPTIMIZED = "SIZE_OPTIMIZED"  # Distribute by layer size
    BALANCED = "BALANCED"  # Balanced distribution
    PERFORMANCE_OPTIMIZED = "PERFORMANCE_OPTIMIZED"  # Optimize for performance


@dataclass
class LayerInfo:
    """Information about a model layer."""
    layer_id: str
    layer_name: str
    layer_type: str
    size_bytes: int
    priority: LayerPriority
    access_pattern: AccessPattern
    access_frequency: float
    dependencies: List[str]
    is_trainable: bool
    compute_intensity: float


@dataclass
class LayerAllocationMap:
    """Mapping of layers to memory tiers."""
    layer_id: str
    tier: MemoryTier
    offset: int
    size_bytes: int
    allocation_time: datetime
    access_count: int
    last_access: datetime
    transfer_cost: float


@dataclass
class DistributionResult:
    """Result of layer distribution operation."""
    strategy_used: DistributionStrategy
    total_layers: int
    tier_distribution: Dict[MemoryTier, int]
    allocation_map: List[LayerAllocationMap]
    estimated_performance: float
    memory_efficiency: float
    distribution_time_ms: float
    warnings: List[str]


class ILayerDistributor(ABC):
    """Interface for layer distribution systems."""
    
    @abstractmethod
    def distribute_layers(self, layers: List[LayerInfo], 
                         available_tiers: Dict[MemoryTier, int],
                         strategy: DistributionStrategy) -> DistributionResult:
        """Distribute layers across memory tiers."""
        pass
    
    @abstractmethod
    def optimize_distribution(self, current_allocation: List[LayerAllocationMap],
                            performance_metrics: Dict[str, float]) -> List[LayerAllocationMap]:
        """Optimize existing layer distribution."""
        pass
    
    @abstractmethod
    def predict_access_pattern(self, layer_info: LayerInfo, 
                             training_mode: bool) -> AccessPattern:
        """Predict access pattern for a layer."""
        pass
    
    @abstractmethod
    def calculate_transfer_cost(self, source_tier: MemoryTier, 
                              target_tier: MemoryTier, size_bytes: int) -> float:
        """Calculate cost of transferring layer between tiers."""
        pass


class LayerDistributor(ILayerDistributor):
    """Distributes model layers across memory tiers based on access patterns and criticality."""
    
    def __init__(self):
        """Initialize layer distributor."""
        self._logger = logging.getLogger(__name__)
        self._lock = Lock()
        
        # Distribution history and metrics
        self._distribution_history: List[DistributionResult] = []
        self._layer_access_history: Dict[str, List[Tuple[datetime, MemoryTier]]] = {}
        
        # Performance characteristics of tiers
        self._tier_performance = {
            MemoryTier.GPU_VRAM: 1.0,
            MemoryTier.SYSTEM_RAM: 0.6,
            MemoryTier.NVME_CACHE: 0.3,
            MemoryTier.SSD_STORAGE: 0.1
        }
        
        # Transfer costs between tiers (relative)
        self._transfer_costs = {
            (MemoryTier.GPU_VRAM, MemoryTier.SYSTEM_RAM): 1.0,
            (MemoryTier.SYSTEM_RAM, MemoryTier.GPU_VRAM): 1.2,
            (MemoryTier.SYSTEM_RAM, MemoryTier.NVME_CACHE): 2.0,
            (MemoryTier.NVME_CACHE, MemoryTier.SYSTEM_RAM): 2.5,
            (MemoryTier.GPU_VRAM, MemoryTier.NVME_CACHE): 3.0,
            (MemoryTier.NVME_CACHE, MemoryTier.GPU_VRAM): 4.0
        }
        
        self._logger.info("Layer distributor initialized")
    
    def distribute_layers(self, layers: List[LayerInfo], 
                         available_tiers: Dict[MemoryTier, int],
                         strategy: DistributionStrategy) -> DistributionResult:
        """
        Distribute layers across memory tiers.
        
        Args:
            layers: List of layer information
            available_tiers: Available capacity per tier in bytes
            strategy: Distribution strategy to use
            
        Returns:
            Distribution result with allocation mapping
        """
        start_time = time.time()
        warnings = []
        
        try:
            with self._lock:
                self._logger.info(f"Distributing {len(layers)} layers using strategy {strategy}")
                
                # Validate inputs
                if not layers:
                    return self._create_empty_result(strategy, "No layers to distribute")
                
                if not available_tiers:
                    return self._create_empty_result(strategy, "No memory tiers available")
                
                # Sort layers based on strategy
                sorted_layers = self._sort_layers_by_strategy(layers, strategy)
                
                # Perform distribution
                allocation_map = []
                tier_usage = {tier: 0 for tier in available_tiers.keys()}
                
                for layer in sorted_layers:
                    allocation = self._allocate_layer(
                        layer, available_tiers, tier_usage, strategy
                    )
                    
                    if allocation:
                        allocation_map.append(allocation)
                        tier_usage[allocation.tier] += allocation.size_bytes
                    else:
                        warnings.append(f"Failed to allocate layer {layer.layer_id}")
                
                # Calculate metrics
                tier_distribution = self._calculate_tier_distribution(allocation_map)
                estimated_performance = self._estimate_distribution_performance(allocation_map)
                memory_efficiency = self._calculate_memory_efficiency(allocation_map, available_tiers)
                
                distribution_time = (time.time() - start_time) * 1000
                
                # Create result
                result = DistributionResult(
                    strategy_used=strategy,
                    total_layers=len(layers),
                    tier_distribution=tier_distribution,
                    allocation_map=allocation_map,
                    estimated_performance=estimated_performance,
                    memory_efficiency=memory_efficiency,
                    distribution_time_ms=distribution_time,
                    warnings=warnings
                )
                
                # Record distribution
                self._distribution_history.append(result)
                
                # Limit history size
                if len(self._distribution_history) > 100:
                    self._distribution_history = self._distribution_history[-50:]
                
                self._logger.info(f"Layer distribution completed: {len(allocation_map)}/{len(layers)} layers allocated")
                
                return result
                
        except Exception as e:
            self._logger.error(f"Error distributing layers: {e}")
            return self._create_empty_result(strategy, f"Distribution error: {e}")
    
    def optimize_distribution(self, current_allocation: List[LayerAllocationMap],
                            performance_metrics: Dict[str, float]) -> List[LayerAllocationMap]:
        """
        Optimize existing layer distribution based on performance metrics.
        
        Args:
            current_allocation: Current layer allocation
            performance_metrics: Performance metrics for optimization
            
        Returns:
            Optimized allocation mapping
        """
        try:
            with self._lock:
                if not current_allocation:
                    return []
                
                optimized_allocation = current_allocation.copy()
                
                # Analyze performance bottlenecks
                bottlenecks = self._identify_performance_bottlenecks(
                    current_allocation, performance_metrics
                )
                
                # Optimize based on bottlenecks
                for layer_id, issue in bottlenecks.items():
                    allocation = next((a for a in optimized_allocation if a.layer_id == layer_id), None)
                    
                    if allocation:
                        new_tier = self._suggest_tier_optimization(allocation, issue)
                        if new_tier and new_tier != allocation.tier:
                            allocation.tier = new_tier
                            allocation.transfer_cost = self.calculate_transfer_cost(
                                allocation.tier, new_tier, allocation.size_bytes
                            )
                            self._logger.debug(f"Optimized layer {layer_id}: moved to {new_tier}")
                
                return optimized_allocation
                
        except Exception as e:
            self._logger.error(f"Error optimizing distribution: {e}")
            return current_allocation
    
    def predict_access_pattern(self, layer_info: LayerInfo, 
                             training_mode: bool) -> AccessPattern:
        """
        Predict access pattern for a layer.
        
        Args:
            layer_info: Layer information
            training_mode: Whether in training mode
            
        Returns:
            Predicted access pattern
        """
        try:
            # Use layer type and characteristics to predict access pattern
            layer_type = layer_info.layer_type.lower()
            
            # Critical layers are accessed frequently
            if layer_info.priority == LayerPriority.CRITICAL:
                return AccessPattern.FREQUENT
            
            # Embedding layers
            if "embedding" in layer_type or "embed" in layer_type:
                return AccessPattern.FREQUENT if training_mode else AccessPattern.SEQUENTIAL
            
            # Attention layers
            if "attention" in layer_type or "attn" in layer_type:
                return AccessPattern.FREQUENT
            
            # Output layers
            if "output" in layer_type or "classifier" in layer_type:
                return AccessPattern.FREQUENT
            
            # Hidden/intermediate layers
            if "hidden" in layer_type or "linear" in layer_type or "dense" in layer_type:
                return AccessPattern.SEQUENTIAL
            
            # Normalization layers
            if "norm" in layer_type or "batch" in layer_type:
                return AccessPattern.FREQUENT
            
            # Default based on access frequency
            if layer_info.access_frequency > 0.8:
                return AccessPattern.FREQUENT
            elif layer_info.access_frequency > 0.5:
                return AccessPattern.SEQUENTIAL
            elif layer_info.access_frequency > 0.2:
                return AccessPattern.SPARSE
            else:
                return AccessPattern.RANDOM
                
        except Exception as e:
            self._logger.error(f"Error predicting access pattern: {e}")
            return AccessPattern.SEQUENTIAL
    
    def calculate_transfer_cost(self, source_tier: MemoryTier, 
                              target_tier: MemoryTier, size_bytes: int) -> float:
        """
        Calculate cost of transferring layer between tiers.
        
        Args:
            source_tier: Source memory tier
            target_tier: Target memory tier
            size_bytes: Size of data to transfer
            
        Returns:
            Transfer cost (relative units)
        """
        try:
            if source_tier == target_tier:
                return 0.0
            
            # Get base transfer cost
            base_cost = self._transfer_costs.get((source_tier, target_tier), 5.0)
            
            # Scale by size (larger transfers are relatively more efficient)
            size_mb = size_bytes / (1024 * 1024)
            size_factor = 1.0 + (size_mb / 1000.0)  # Slight increase for larger transfers
            
            return base_cost * size_factor
            
        except Exception as e:
            self._logger.error(f"Error calculating transfer cost: {e}")
            return 10.0  # High cost as fallback

    def _sort_layers_by_strategy(self, layers: List[LayerInfo],
                                strategy: DistributionStrategy) -> List[LayerInfo]:
        """Sort layers based on distribution strategy."""
        try:
            if strategy == DistributionStrategy.PRIORITY_BASED:
                # Sort by priority (critical first), then by size
                return sorted(layers, key=lambda l: (
                    self._priority_to_numeric(l.priority),
                    -l.size_bytes
                ))

            elif strategy == DistributionStrategy.ACCESS_PATTERN:
                # Sort by access frequency, then by priority
                return sorted(layers, key=lambda l: (
                    -l.access_frequency,
                    self._priority_to_numeric(l.priority)
                ))

            elif strategy == DistributionStrategy.SIZE_OPTIMIZED:
                # Sort by size (largest first)
                return sorted(layers, key=lambda l: -l.size_bytes)

            elif strategy == DistributionStrategy.PERFORMANCE_OPTIMIZED:
                # Sort by compute intensity and priority
                return sorted(layers, key=lambda l: (
                    self._priority_to_numeric(l.priority),
                    -l.compute_intensity,
                    -l.access_frequency
                ))

            else:  # BALANCED
                # Balanced approach considering multiple factors
                return sorted(layers, key=lambda l: (
                    self._priority_to_numeric(l.priority),
                    -l.access_frequency * 0.5 - l.compute_intensity * 0.3 - (l.size_bytes / 1024**3) * 0.2
                ))

        except Exception as e:
            self._logger.error(f"Error sorting layers: {e}")
            return layers

    def _priority_to_numeric(self, priority: LayerPriority) -> int:
        """Convert priority to numeric value for sorting."""
        priority_map = {
            LayerPriority.CRITICAL: 0,
            LayerPriority.HIGH: 1,
            LayerPriority.MEDIUM: 2,
            LayerPriority.LOW: 3
        }
        return priority_map.get(priority, 4)

    def _allocate_layer(self, layer: LayerInfo,
                       available_tiers: Dict[MemoryTier, int],
                       tier_usage: Dict[MemoryTier, int],
                       strategy: DistributionStrategy) -> Optional[LayerAllocationMap]:
        """Allocate a single layer to appropriate tier."""
        try:
            # Determine preferred tiers based on layer characteristics
            preferred_tiers = self._get_preferred_tiers(layer, strategy)

            # Try to allocate in preferred order
            for tier in preferred_tiers:
                if tier not in available_tiers:
                    continue

                available_capacity = available_tiers[tier] - tier_usage[tier]

                if available_capacity >= layer.size_bytes:
                    # Allocate in this tier
                    allocation = LayerAllocationMap(
                        layer_id=layer.layer_id,
                        tier=tier,
                        offset=tier_usage[tier],  # Simplified offset calculation
                        size_bytes=layer.size_bytes,
                        allocation_time=datetime.now(timezone.utc),
                        access_count=0,
                        last_access=datetime.now(timezone.utc),
                        transfer_cost=0.0  # No transfer cost for initial allocation
                    )

                    return allocation

            # No suitable tier found
            self._logger.warning(f"Could not allocate layer {layer.layer_id} (size: {layer.size_bytes})")
            return None

        except Exception as e:
            self._logger.error(f"Error allocating layer {layer.layer_id}: {e}")
            return None

    def _get_preferred_tiers(self, layer: LayerInfo,
                           strategy: DistributionStrategy) -> List[MemoryTier]:
        """Get preferred tiers for layer allocation."""
        try:
            # Base tier preferences
            if layer.priority == LayerPriority.CRITICAL:
                # Critical layers prefer GPU VRAM
                preferred = [MemoryTier.GPU_VRAM, MemoryTier.SYSTEM_RAM, MemoryTier.NVME_CACHE]

            elif layer.priority == LayerPriority.HIGH:
                # High priority layers prefer GPU or fast RAM
                if layer.access_frequency > 0.7:
                    preferred = [MemoryTier.GPU_VRAM, MemoryTier.SYSTEM_RAM, MemoryTier.NVME_CACHE]
                else:
                    preferred = [MemoryTier.SYSTEM_RAM, MemoryTier.GPU_VRAM, MemoryTier.NVME_CACHE]

            elif layer.priority == LayerPriority.MEDIUM:
                # Medium priority layers prefer RAM
                preferred = [MemoryTier.SYSTEM_RAM, MemoryTier.NVME_CACHE, MemoryTier.GPU_VRAM]

            else:  # LOW priority
                # Low priority layers can use slower tiers
                preferred = [MemoryTier.NVME_CACHE, MemoryTier.SYSTEM_RAM, MemoryTier.GPU_VRAM]

            # Adjust based on strategy
            if strategy == DistributionStrategy.SIZE_OPTIMIZED:
                # Large layers prefer tiers with more capacity
                if layer.size_bytes > 1024**3:  # > 1GB
                    preferred = [MemoryTier.NVME_CACHE, MemoryTier.SYSTEM_RAM, MemoryTier.GPU_VRAM]

            elif strategy == DistributionStrategy.PERFORMANCE_OPTIMIZED:
                # High compute intensity layers prefer faster tiers
                if layer.compute_intensity > 0.8:
                    preferred = [MemoryTier.GPU_VRAM, MemoryTier.SYSTEM_RAM, MemoryTier.NVME_CACHE]

            return preferred

        except Exception as e:
            self._logger.error(f"Error getting preferred tiers: {e}")
            return [MemoryTier.SYSTEM_RAM, MemoryTier.NVME_CACHE, MemoryTier.GPU_VRAM]

    def _calculate_tier_distribution(self, allocation_map: List[LayerAllocationMap]) -> Dict[MemoryTier, int]:
        """Calculate number of layers per tier."""
        try:
            distribution = {}

            for allocation in allocation_map:
                tier = allocation.tier
                distribution[tier] = distribution.get(tier, 0) + 1

            return distribution

        except Exception as e:
            self._logger.error(f"Error calculating tier distribution: {e}")
            return {}

    def _estimate_distribution_performance(self, allocation_map: List[LayerAllocationMap]) -> float:
        """Estimate performance of layer distribution."""
        try:
            if not allocation_map:
                return 0.0

            total_performance = 0.0
            total_size = 0

            for allocation in allocation_map:
                tier_performance = self._tier_performance.get(allocation.tier, 0.1)
                weighted_performance = tier_performance * allocation.size_bytes
                total_performance += weighted_performance
                total_size += allocation.size_bytes

            if total_size > 0:
                return total_performance / total_size

            return 0.0

        except Exception as e:
            self._logger.error(f"Error estimating distribution performance: {e}")
            return 0.5

    def _calculate_memory_efficiency(self, allocation_map: List[LayerAllocationMap],
                                   available_tiers: Dict[MemoryTier, int]) -> float:
        """Calculate memory efficiency of distribution."""
        try:
            if not allocation_map or not available_tiers:
                return 0.0

            # Calculate utilization per tier
            tier_usage = {}
            for allocation in allocation_map:
                tier = allocation.tier
                tier_usage[tier] = tier_usage.get(tier, 0) + allocation.size_bytes

            # Calculate weighted efficiency
            total_efficiency = 0.0
            total_capacity = 0

            for tier, capacity in available_tiers.items():
                usage = tier_usage.get(tier, 0)
                utilization = usage / capacity if capacity > 0 else 0.0

                # Efficiency is good utilization without over-allocation
                efficiency = min(1.0, utilization) * (1.0 - max(0.0, utilization - 1.0))

                total_efficiency += efficiency * capacity
                total_capacity += capacity

            if total_capacity > 0:
                return total_efficiency / total_capacity

            return 0.0

        except Exception as e:
            self._logger.error(f"Error calculating memory efficiency: {e}")
            return 0.5

    def _create_empty_result(self, strategy: DistributionStrategy,
                           warning: str) -> DistributionResult:
        """Create empty distribution result with warning."""
        return DistributionResult(
            strategy_used=strategy,
            total_layers=0,
            tier_distribution={},
            allocation_map=[],
            estimated_performance=0.0,
            memory_efficiency=0.0,
            distribution_time_ms=0.0,
            warnings=[warning]
        )

    def _identify_performance_bottlenecks(self, allocation_map: List[LayerAllocationMap],
                                        performance_metrics: Dict[str, float]) -> Dict[str, str]:
        """Identify performance bottlenecks in current allocation."""
        try:
            bottlenecks = {}

            # Analyze metrics for bottlenecks
            memory_pressure = performance_metrics.get('memory_pressure', 0.0)
            bandwidth_utilization = performance_metrics.get('bandwidth_utilization', 0.0)
            access_latency = performance_metrics.get('access_latency', 0.0)

            # Identify layers that might benefit from tier changes
            for allocation in allocation_map:
                layer_id = allocation.layer_id

                # High memory pressure and layer in GPU
                if memory_pressure > 0.8 and allocation.tier == MemoryTier.GPU_VRAM:
                    bottlenecks[layer_id] = "high_memory_pressure"

                # High bandwidth utilization and layer in slow tier
                elif bandwidth_utilization > 0.9 and allocation.tier == MemoryTier.NVME_CACHE:
                    bottlenecks[layer_id] = "bandwidth_bottleneck"

                # High access latency
                elif access_latency > 100.0:  # microseconds
                    bottlenecks[layer_id] = "access_latency"

            return bottlenecks

        except Exception as e:
            self._logger.error(f"Error identifying bottlenecks: {e}")
            return {}

    def _suggest_tier_optimization(self, allocation: LayerAllocationMap,
                                 issue: str) -> Optional[MemoryTier]:
        """Suggest tier optimization based on identified issue."""
        try:
            current_tier = allocation.tier

            if issue == "high_memory_pressure":
                # Move from GPU to RAM
                if current_tier == MemoryTier.GPU_VRAM:
                    return MemoryTier.SYSTEM_RAM
                elif current_tier == MemoryTier.SYSTEM_RAM:
                    return MemoryTier.NVME_CACHE

            elif issue == "bandwidth_bottleneck":
                # Move to faster tier
                if current_tier == MemoryTier.NVME_CACHE:
                    return MemoryTier.SYSTEM_RAM
                elif current_tier == MemoryTier.SYSTEM_RAM:
                    return MemoryTier.GPU_VRAM

            elif issue == "access_latency":
                # Move to faster tier if possible
                if current_tier != MemoryTier.GPU_VRAM:
                    return MemoryTier.GPU_VRAM

            return None

        except Exception as e:
            self._logger.error(f"Error suggesting tier optimization: {e}")
            return None

    def get_distribution_statistics(self) -> Dict[str, float]:
        """Get distribution performance statistics."""
        try:
            if not self._distribution_history:
                return {}

            recent_distributions = self._distribution_history[-20:]  # Last 20 distributions

            # Calculate statistics
            avg_performance = sum(d.estimated_performance for d in recent_distributions) / len(recent_distributions)
            avg_efficiency = sum(d.memory_efficiency for d in recent_distributions) / len(recent_distributions)
            avg_distribution_time = sum(d.distribution_time_ms for d in recent_distributions) / len(recent_distributions)

            # Strategy usage
            strategy_counts = {}
            for dist in recent_distributions:
                strategy = dist.strategy_used.value
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

            return {
                'average_performance': avg_performance,
                'average_efficiency': avg_efficiency,
                'average_distribution_time_ms': avg_distribution_time,
                'total_distributions': len(self._distribution_history),
                'recent_distributions': len(recent_distributions),
                **{f'strategy_{k}_percent': (v / len(recent_distributions)) * 100
                   for k, v in strategy_counts.items()}
            }

        except Exception as e:
            self._logger.error(f"Error getting distribution statistics: {e}")
            return {}
