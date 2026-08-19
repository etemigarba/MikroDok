"""
Embedding Cache Module
LRU cache for document embeddings and vectors with compression and batch operations.
"""

from .embedding_cache_lg import (
    EmbeddingCache,
    EmbeddingCacheCore,
    CompressedEmbeddingEntry,
    EmbeddingBatchProcessor
)

__all__ = [
    'EmbeddingCache',
    'EmbeddingCacheCore',
    'CompressedEmbeddingEntry',
    'EmbeddingBatchProcessor'
]
