"""
MikroDok Index Optimizer Package
Provides comprehensive vector index optimization functionality for performance tuning.
"""

# Import index optimizer components
try:
    from .index_optimizer_lg import (
        IndexOptimizer,
        FlatIndexOptimizer,
        IVFIndexOptimizer,
        HNSWIndexOptimizer,
        AdaptiveIndexOptimizer
    )
except ImportError:
    pass

__all__ = [
    'IndexOptimizer',
    'FlatIndexOptimizer',
    'IVFIndexOptimizer',
    'HNSWIndexOptimizer',
    'AdaptiveIndexOptimizer'
]
