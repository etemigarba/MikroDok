"""
MikroDok Search Cache Database Package
Provides database modules for search caching including query cache and result cache management.
"""

# Import search cache database components
try:
    from .query_cache_db.query_cache_db import QueryCacheDB
except ImportError:
    pass

try:
    from .result_cache_db.result_cache_db import ResultCacheDB
except ImportError:
    pass

__all__ = [
    'QueryCacheDB',
    'ResultCacheDB'
]
