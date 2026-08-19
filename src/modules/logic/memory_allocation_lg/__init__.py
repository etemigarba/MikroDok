"""
MikroDok Memory Allocation Package
Provides intelligent memory allocation strategies for the IDRAlloc system.
"""

# Import allocation strategy components
from .allocation_strategy_lg.allocation_strategy_lg import (
    AllocationStrategy,
    IAllocationStrategy,
    IDRAllocMode,
    AllocationDecision,
    HardwareProfile,
    AllocationMetrics,
    StrategyConfiguration,
    AllocationResult
)

# Import memory tier manager components
from .memory_tier_manager_lg.memory_tier_manager_lg import (
    MemoryTierManager,
    IMemoryTierManager,
    MemoryTierInfo,
    TierCapacity,
    TierBandwidth,
    TierStatus,
    TierConfiguration,
    TierMetrics
)

# Import layer distribution components
from .layer_distribution_lg.layer_distribution_lg import (
    LayerDistributor,
    ILayerDistributor,
    LayerAllocationMap,
    LayerInfo,
    AccessPattern,
    LayerPriority,
    DistributionStrategy,
    DistributionResult
)

__all__ = [
    # Allocation Strategy
    'AllocationStrategy',
    'IAllocationStrategy',
    'IDRAllocMode',
    'AllocationDecision',
    'HardwareProfile',
    'AllocationMetrics',
    'StrategyConfiguration',
    'AllocationResult',
    
    # Memory Tier Manager
    'MemoryTierManager',
    'IMemoryTierManager',
    'MemoryTierInfo',
    'TierCapacity',
    'TierBandwidth',
    'TierStatus',
    'TierConfiguration',
    'TierMetrics',
    
    # Layer Distribution
    'LayerDistributor',
    'ILayerDistributor',
    'LayerAllocationMap',
    'LayerInfo',
    'AccessPattern',
    'LayerPriority',
    'DistributionStrategy',
    'DistributionResult'
]
