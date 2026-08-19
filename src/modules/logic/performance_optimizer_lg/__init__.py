"""
MikroDok Performance Optimizer Package
Provides comprehensive performance optimization functionality for resource management and system efficiency.
"""

# Import optimization trigger components
from .optimization_trigger_lg.optimization_trigger_lg import (
    OptimizationTrigger,
    IOptimizationTrigger,
    TriggerCondition,
    TriggerType,
    OptimizationAction,
    TriggerConfiguration,
    MetricThreshold,
    TriggerEvent,
    OptimizationContext
)

# Import memory pressure handler components
from .memory_pressure_handler_lg.memory_pressure_handler_lg import (
    MemoryPressureHandler,
    IMemoryPressureHandler,
    PressureLevel,
    MemoryAction,
    AllocationStrategy,
    CleanupStrategy,
    MemoryTier,
    PressureConfiguration,
    MemoryPressureEvent
)

# Import batch size optimizer components
from .batch_size_optimizer_lg.batch_size_optimizer_lg import (
    BatchSizeOptimizer,
    IBatchSizeOptimizer,
    BatchOptimizationStrategy,
    ResourceConstraints,
    BatchConfiguration,
    OptimizationMetrics,
    BatchSizeRecommendation,
    PerformanceProfile
)

# Import cache optimizer components
from .cache_optimizer_lg.cache_optimizer_lg import (
    CacheOptimizer,
    ICacheOptimizer,
    EvictionPolicy,
    PrefetchStrategy,
    CacheConfiguration,
    AccessPattern,
    CacheMetrics,
    CacheOptimizationResult,
    CacheLevel
)

__all__ = [
    # Optimization Trigger
    'OptimizationTrigger',
    'IOptimizationTrigger',
    'TriggerCondition',
    'TriggerType',
    'OptimizationAction',
    'TriggerConfiguration',
    'MetricThreshold',
    'TriggerEvent',
    'OptimizationContext',
    
    # Memory Pressure Handler
    'MemoryPressureHandler',
    'IMemoryPressureHandler',
    'PressureLevel',
    'MemoryAction',
    'AllocationStrategy',
    'CleanupStrategy',
    'MemoryTier',
    'PressureConfiguration',
    'MemoryPressureEvent',
    
    # Batch Size Optimizer
    'BatchSizeOptimizer',
    'IBatchSizeOptimizer',
    'BatchOptimizationStrategy',
    'ResourceConstraints',
    'BatchConfiguration',
    'OptimizationMetrics',
    'BatchSizeRecommendation',
    'PerformanceProfile',
    
    # Cache Optimizer
    'CacheOptimizer',
    'ICacheOptimizer',
    'EvictionPolicy',
    'PrefetchStrategy',
    'CacheConfiguration',
    'AccessPattern',
    'CacheMetrics',
    'CacheOptimizationResult',
    'CacheLevel'
]
