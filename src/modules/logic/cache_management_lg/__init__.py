"""
Cache Management Module
Comprehensive caching system with multiple cache types and coordination.

This module provides:
- Memory cache for frequently accessed data
- Model cache for model metadata and parameters
- Embedding cache for document embeddings and vectors
- Cache coordinator for managing multiple cache types
- Base interfaces and utilities for cache management
"""

# Import base interfaces and utilities
from .base_interfaces import (
    # Enums
    CacheType,
    CacheStatus,
    EvictionPolicy,
    CacheLevel,
    
    # Data classes
    CacheEntry,
    CacheResult,
    CacheStats,
    CacheConfig,
    ModelCacheEntry,
    EmbeddingCacheEntry,
    
    # Interfaces
    ICache,
    ICacheManager,
    IMemoryCache,
    IModelCache,
    IEmbeddingCache,
    ICacheEventListener,
    
    # Events
    CacheEvent,
    CacheHitEvent,
    CacheMissEvent,
    CacheEvictionEvent,
    
    # Utilities
    CacheKeyGenerator,
    CacheMetrics
)

# Import cache implementations
from .memory_cache_lg import (
    MemoryCache,
    LRUMemoryCache,
    MemoryCacheEntry
)

from .model_cache_lg import (
    ModelCache,
    ModelCacheCore,
    ModelMetadata,
    ModelCachePersistence
)

from .embedding_cache_lg import (
    EmbeddingCache,
    EmbeddingCacheCore,
    CompressedEmbeddingEntry,
    EmbeddingBatchProcessor
)

from .cache_coordinator_lg import (
    CacheCoordinator,
    CacheCoordinatorCore,
    CachePolicy,
    CacheCoordinatorEventListener
)

__all__ = [
    # Base Interfaces and Enums
    'CacheType',
    'CacheStatus',
    'EvictionPolicy',
    'CacheLevel',
    'CacheEntry',
    'CacheResult',
    'CacheStats',
    'CacheConfig',
    'ModelCacheEntry',
    'EmbeddingCacheEntry',
    'ICache',
    'ICacheManager',
    'IMemoryCache',
    'IModelCache',
    'IEmbeddingCache',
    'ICacheEventListener',
    'CacheEvent',
    'CacheHitEvent',
    'CacheMissEvent',
    'CacheEvictionEvent',
    'CacheKeyGenerator',
    'CacheMetrics',
    
    # Memory Cache
    'MemoryCache',
    'LRUMemoryCache',
    'MemoryCacheEntry',
    
    # Model Cache
    'ModelCache',
    'ModelCacheCore',
    'ModelMetadata',
    'ModelCachePersistence',
    
    # Embedding Cache
    'EmbeddingCache',
    'EmbeddingCacheCore',
    'CompressedEmbeddingEntry',
    'EmbeddingBatchProcessor',
    
    # Cache Coordinator
    'CacheCoordinator',
    'CacheCoordinatorCore',
    'CachePolicy',
    'CacheCoordinatorEventListener'
]

# Version information
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Comprehensive caching system for MikroDok application"

# Module metadata
__module_info__ = {
    "name": "cache_management_lg",
    "phase": 4,
    "location": "/src/modules/logic/cache_management_lg/",
    "description": "Multi-tier caching system with coordination and optimization",
    "dependencies": [
        "logging_infrastructure_lg",
        "performance_optimizer_lg"
    ],
    "features": [
        "In-memory caching with LRU eviction",
        "Model metadata caching with persistence",
        "Embedding vector caching with compression",
        "Multi-cache coordination and optimization",
        "Event-driven cache monitoring",
        "Background optimization and cleanup",
        "Memory pressure handling",
        "Performance metrics and analytics"
    ]
}

def get_module_info():
    """Get module information."""
    return __module_info__.copy()

def create_default_cache_coordinator():
    """Create a cache coordinator with default configuration."""
    return CacheCoordinator()

def create_cache_config(cache_type: CacheType, **kwargs) -> CacheConfig:
    """
    Create cache configuration for specific cache type.
    
    Args:
        cache_type: Type of cache
        **kwargs: Configuration parameters
        
    Returns:
        CacheConfig instance
    """
    # Default configurations per cache type
    defaults = {
        CacheType.MEMORY: {
            'max_entries': 10000,
            'max_size_bytes': 512 * 1024 * 1024,  # 512MB
            'eviction_policy': EvictionPolicy.LRU,
            'enable_background_cleanup': True
        },
        CacheType.MODEL: {
            'max_entries': 1000,
            'max_size_bytes': 1024 * 1024 * 1024,  # 1GB
            'eviction_policy': EvictionPolicy.LFU,
            'enable_persistence': True,
            'compression_enabled': True
        },
        CacheType.EMBEDDING: {
            'max_entries': 50000,
            'max_size_bytes': 2 * 1024 * 1024 * 1024,  # 2GB
            'eviction_policy': EvictionPolicy.ADAPTIVE,
            'compression_enabled': True,
            'enable_background_cleanup': True
        }
    }
    
    # Merge defaults with provided kwargs
    config_params = defaults.get(cache_type, {})
    config_params.update(kwargs)
    
    return CacheConfig(**config_params)
