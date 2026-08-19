"""
Adaptive Reallocation Module
Dynamically adjusts memory distribution based on performance metrics and resource availability.
"""

from .adaptive_reallocation_lg import (
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

__all__ = [
    'AdaptiveReallocator',
    'IAdaptiveReallocator',
    'ReallocationStrategy',
    'PerformanceMetrics',
    'ResourceAvailability',
    'ReallocationDecision',
    'AdaptationTrigger',
    'ReallocationResult',
    'OptimizationTarget'
]
