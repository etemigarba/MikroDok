"""
MikroDok Semantic Searcher Package
Provides vector-based semantic search functionality using embeddings and similarity metrics.
"""

# Import semantic searcher components
try:
    from .semantic_searcher_lg import (
        SemanticSearcher,
        VectorEmbedder,
        SimilarityMatcher,
        SemanticRanker
    )
except ImportError:
    pass

__all__ = [
    'SemanticSearcher',
    'VectorEmbedder',
    'SimilarityMatcher',
    'SemanticRanker'
]
