"""
Cache Optimizer Module
Manages cache eviction policies and prefetching strategies based on access patterns and available memory.
"""

from .cache_optimizer_lg import (
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
