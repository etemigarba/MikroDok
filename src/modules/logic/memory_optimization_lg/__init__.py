"""
MikroDok Memory Optimization Package
Provides intelligent memory optimization functionality for the IDRAlloc system.
"""

# Import memory pressure detector components
try:
    from .memory_pressure_detector_lg.memory_pressure_detector_lg import (
        MemoryPressureDetector,
        IMemoryPressureDetector,
        PressureLevel,
        PressureTrend,
        MemoryMetrics,
        PressureThreshold,
        PredictionModel,
        AllocationHistory,
        PressureEvent
    )
except ImportError:
    pass

# Import adaptive reallocation components
try:
    from .adaptive_reallocation_lg.adaptive_reallocation_lg import (
        AdaptiveReallocator,
        IAdaptiveReallocator,
        ReallocationStrategy,
        PerformanceMetrics,
        ResourceAvailability,
        ReallocationDecision,
        AdaptationTrigger,
        ReallocationResult,
        OptimizationTarget
    )
except ImportError:
    pass

# Import fragmentation manager components
try:
    from .fragmentation_manager_lg.fragmentation_manager_lg import (
        FragmentationManager,
        IFragmentationManager,
        FragmentationLevel,
        DefragmentationStrategy,
        MemoryPool,
        FragmentationMetrics,
        DefragmentationResult,
        PoolConfiguration,
        FragmentationEvent
    )
except ImportError:
    pass

__all__ = [
    # Memory Pressure Detector
    'MemoryPressureDetector',
    'IMemoryPressureDetector',
    'PressureLevel',
    'PressureTrend',
    'MemoryMetrics',
    'PressureThreshold',
    'PredictionModel',
    'AllocationHistory',
    'PressureEvent',
    
    # Adaptive Reallocation
    'AdaptiveReallocator',
    'IAdaptiveReallocator',
    'ReallocationStrategy',
    'PerformanceMetrics',
    'ResourceAvailability',
    'ReallocationDecision',
    'AdaptationTrigger',
    'ReallocationResult',
    'OptimizationTarget',
    
    # Fragmentation Manager
    'FragmentationManager',
    'IFragmentationManager',
    'FragmentationLevel',
    'DefragmentationStrategy',
    'MemoryPool',
    'FragmentationMetrics',
    'DefragmentationResult',
    'PoolConfiguration',
    'FragmentationEvent'
]
