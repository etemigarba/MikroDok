"""
MikroDok Cache Persistence Database Package
Provides database modules for persistent caching including model cache, query cache, and embedding cache management.
"""

# Import cache persistence database components
try:
    from .model_cache_db.model_cache_db import ModelCacheDB
except ImportError:
    pass

try:
    from .query_cache_db.query_cache_db import QueryCacheDB
except ImportError:
    pass

try:
    from .embedding_cache_db.embedding_cache_db import EmbeddingCacheDB
except ImportError:
    pass

__all__ = [
    'ModelCacheDB',
    'QueryCacheDB',
    'EmbeddingCacheDB'
]
