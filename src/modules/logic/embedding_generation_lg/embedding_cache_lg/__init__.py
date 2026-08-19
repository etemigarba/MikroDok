"""
Embedding Cache Module
LRU cache implementation for frequently accessed embeddings to reduce computation.
"""

from .embedding_cache_lg import (
    EmbeddingCache,
    LRUEmbeddingCache,
    CacheManager,
    CacheOptimizer
)

__all__ = [
    'EmbeddingCache',
    'LRUEmbeddingCache',
    'CacheManager',
    'CacheOptimizer'
]
