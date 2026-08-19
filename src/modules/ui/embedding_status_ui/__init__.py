"""
Module: embedding_status_ui
Description: Embedding status UI module for MikroDok application.
            Provides comprehensive embedding status monitoring interface including real-time
            progress tracking, vector index statistics, and embedding generation monitoring.
Phase: 4
Location: /src/modules/ui/embedding_status_ui/
"""

# Import embedding progress components
try:
    from .embedding_progress_ui.embedding_progress_ui import (
        EmbeddingProgressUI,
        EmbeddingProgressItem,
        EmbeddingProgressStatus,
        EmbeddingProgressConfig,
        EmbeddingProgressMetrics
    )
except ImportError:
    pass

# Import index stats components
try:
    from .index_stats_ui.index_stats_ui import (
        IndexStatsUI,
        IndexStatistics,
        IndexHealth,
        IndexOptimizationSuggestion
    )
except ImportError:
    pass

__all__ = [
    'EmbeddingProgressUI',
    'EmbeddingProgressItem',
    'EmbeddingProgressStatus',
    'EmbeddingProgressConfig',
    'EmbeddingProgressMetrics',
    'IndexStatsUI',
    'IndexStatistics',
    'IndexHealth',
    'IndexOptimizationSuggestion'
]
