"""
MikroDok Index Statistics UI Package
Provides comprehensive vector index statistics monitoring interface with real-time performance tracking and optimization recommendations.
"""

# Import index statistics components
try:
    from .index_stats_ui import (
        IndexStatsUI,
        IndexStatistics,
        IndexHealth,
        IndexOptimizationSuggestion
    )
except ImportError:
    pass

__all__ = [
    'IndexStatsUI',
    'IndexStatistics',
    'IndexHealth',
    'IndexOptimizationSuggestion'
]
