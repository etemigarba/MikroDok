"""
Module: base_interfaces
Description: Base interfaces and data structures for cache management system
Phase: 4
Location: /src/modules/logic/cache_management_lg/base_interfaces.py
"""

# Standard library imports
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import weakref

# Third-party imports
import numpy as np


class CacheType(Enum):
    """Types of cache systems."""
    MEMORY = "memory"
    MODEL = "model"
    EMBEDDING = "embedding"
    QUERY = "query"
    RESULT = "result"


class CacheStatus(Enum):
    """Cache operation status."""
    HIT = "hit"
    MISS = "miss"
    ERROR = "error"
    EXPIRED = "expired"
    EVICTED = "evicted"


class EvictionPolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In, First Out
    TTL = "ttl"  # Time To Live
    ADAPTIVE = "adaptive"  # Adaptive based on access patterns


class CacheLevel(Enum):
    """Cache hierarchy levels."""
    L1_MEMORY = "l1_memory"  # Fast in-memory cache
    L2_COMPRESSED = "l2_compressed"  # Compressed memory cache
    L3_DISK = "l3_disk"  # Disk-based cache
    L4_DISTRIBUTED = "l4_distributed"  # Distributed cache


@dataclass
class CacheEntry:
    """Base cache entry with metadata."""
    key: str
    value: Any
    size_bytes: int
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.last_accessed is None:
            self.last_accessed = self.created_at
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl_seconds is None:
            return False
        return datetime.now() - self.created_at > timedelta(seconds=self.ttl_seconds)
    
    @property
    def age_seconds(self) -> float:
        """Get entry age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
    
    def access(self) -> None:
        """Record access to this entry."""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class CacheResult:
    """Result of cache operation."""
    status: CacheStatus
    key: str
    value: Optional[Any] = None
    size_bytes: int = 0
    hit_count: int = 0
    last_accessed: Optional[datetime] = None
    cache_level: Optional[CacheLevel] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheStats:
    """Cache performance statistics."""
    cache_type: CacheType
    cache_level: CacheLevel
    total_entries: int
    total_size_bytes: int
    hit_count: int
    miss_count: int
    eviction_count: int
    hit_rate: float
    miss_rate: float
    average_access_time_ms: float
    memory_usage_percent: float
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def total_requests(self) -> int:
        """Total cache requests."""
        return self.hit_count + self.miss_count


@dataclass
class CacheConfig:
    """Configuration for cache systems."""
    # Size limits
    max_entries: int = 10000
    max_size_bytes: int = 1024 * 1024 * 1024  # 1GB
    memory_limit_percent: float = 80.0
    
    # Eviction policy
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    eviction_batch_size: int = 100
    eviction_threshold_percent: float = 90.0
    
    # TTL settings
    default_ttl_seconds: Optional[int] = None
    enable_ttl_cleanup: bool = True
    ttl_cleanup_interval_seconds: int = 300
    
    # Persistence
    enable_persistence: bool = False
    persistence_path: Optional[Path] = None
    persistence_interval_seconds: int = 600
    compression_enabled: bool = True
    
    # Performance
    enable_stats: bool = True
    stats_update_interval_seconds: int = 60
    enable_background_cleanup: bool = True
    cleanup_interval_seconds: int = 300
    
    # Thread safety
    thread_safe: bool = True
    lock_timeout_seconds: float = 5.0


@dataclass
class ModelCacheEntry(CacheEntry):
    """Cache entry for model metadata."""
    model_id: str = ""
    model_type: str = ""
    model_size_bytes: int = 0
    model_path: Optional[Path] = None
    model_config: Dict[str, Any] = field(default_factory=dict)
    load_time_ms: float = 0.0
    last_used: Optional[datetime] = None

    def __post_init__(self):
        """Initialize model-specific fields."""
        super().__post_init__()
        if self.last_used is None:
            self.last_used = self.created_at


@dataclass
class EmbeddingCacheEntry(CacheEntry):
    """Cache entry for embeddings."""
    chunk_id: str = ""
    vector: Optional[np.ndarray] = None
    vector_dimension: int = 0
    model_name: str = ""
    chunk_hash: str = ""
    compression_ratio: float = 1.0

    def __post_init__(self):
        """Initialize embedding-specific fields."""
        super().__post_init__()
        if self.vector is not None:
            self.vector_dimension = len(self.vector)
            # Update size to include vector size
            self.size_bytes += self.vector.nbytes
        else:
            self.vector_dimension = 0


class ICache(ABC):
    """Base interface for all cache implementations."""
    
    @abstractmethod
    def get(self, key: str) -> CacheResult:
        """
        Retrieve value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            CacheResult with value if found
        """
        pass
    
    @abstractmethod
    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl_seconds: Optional time-to-live
            
        Returns:
            True if successfully stored
        """
        pass
    
    @abstractmethod
    def evict(self, key: str) -> bool:
        """
        Remove entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successfully evicted
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """
        Clear all entries from cache.
        
        Returns:
            True if successfully cleared
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> CacheStats:
        """
        Get cache performance statistics.
        
        Returns:
            CacheStats object
        """
        pass
    
    @abstractmethod
    def get_size(self) -> Tuple[int, int]:
        """
        Get cache size information.
        
        Returns:
            Tuple of (entry_count, total_bytes)
        """
        pass
    
    @abstractmethod
    def contains(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        pass


class ICacheManager(ABC):
    """Base interface for cache management and coordination."""
    
    @abstractmethod
    def register_cache(self, cache_type: CacheType, cache: ICache) -> bool:
        """
        Register a cache instance.
        
        Args:
            cache_type: Type of cache
            cache: Cache instance
            
        Returns:
            True if successfully registered
        """
        pass
    
    @abstractmethod
    def unregister_cache(self, cache_type: CacheType) -> bool:
        """
        Unregister a cache instance.
        
        Args:
            cache_type: Type of cache
            
        Returns:
            True if successfully unregistered
        """
        pass
    
    @abstractmethod
    def get_cache(self, cache_type: CacheType) -> Optional[ICache]:
        """
        Get cache instance by type.
        
        Args:
            cache_type: Type of cache
            
        Returns:
            Cache instance if found
        """
        pass
    
    @abstractmethod
    def clear_all_caches(self) -> bool:
        """
        Clear all registered caches.
        
        Returns:
            True if all caches cleared successfully
        """
        pass
    
    @abstractmethod
    def get_global_stats(self) -> Dict[CacheType, CacheStats]:
        """
        Get statistics for all caches.
        
        Returns:
            Dictionary mapping cache types to their stats
        """
        pass
    
    @abstractmethod
    def optimize_caches(self) -> bool:
        """
        Trigger optimization for all caches.

        Returns:
            True if optimization completed successfully
        """
        pass


class IMemoryCache(ICache):
    """Interface for in-memory cache systems."""

    @abstractmethod
    def get_memory_usage(self) -> Dict[str, int]:
        """
        Get detailed memory usage information.

        Returns:
            Dictionary with memory usage details
        """
        pass

    @abstractmethod
    def compact(self) -> bool:
        """
        Compact cache to reduce memory fragmentation.

        Returns:
            True if compaction successful
        """
        pass


class IModelCache(ICache):
    """Interface for model metadata cache systems."""

    @abstractmethod
    def get_model(self, model_id: str) -> Optional[ModelCacheEntry]:
        """
        Get model metadata from cache.

        Args:
            model_id: Model identifier

        Returns:
            ModelCacheEntry if found
        """
        pass

    @abstractmethod
    def put_model(self, model_id: str, model_entry: ModelCacheEntry) -> bool:
        """
        Store model metadata in cache.

        Args:
            model_id: Model identifier
            model_entry: Model cache entry

        Returns:
            True if successfully stored
        """
        pass

    @abstractmethod
    def get_models_by_type(self, model_type: str) -> List[ModelCacheEntry]:
        """
        Get all models of a specific type.

        Args:
            model_type: Type of model

        Returns:
            List of model cache entries
        """
        pass


class IEmbeddingCache(ICache):
    """Interface for embedding cache systems."""

    @abstractmethod
    def get_embedding(self, chunk_id: str) -> Optional[EmbeddingCacheEntry]:
        """
        Get embedding from cache.

        Args:
            chunk_id: Chunk identifier

        Returns:
            EmbeddingCacheEntry if found
        """
        pass

    @abstractmethod
    def put_embedding(self, chunk_id: str, embedding_entry: EmbeddingCacheEntry) -> bool:
        """
        Store embedding in cache.

        Args:
            chunk_id: Chunk identifier
            embedding_entry: Embedding cache entry

        Returns:
            True if successfully stored
        """
        pass

    @abstractmethod
    def get_embeddings_by_model(self, model_name: str) -> List[EmbeddingCacheEntry]:
        """
        Get all embeddings for a specific model.

        Args:
            model_name: Name of the embedding model

        Returns:
            List of embedding cache entries
        """
        pass

    @abstractmethod
    def batch_get(self, chunk_ids: List[str]) -> Dict[str, EmbeddingCacheEntry]:
        """
        Get multiple embeddings in batch.

        Args:
            chunk_ids: List of chunk identifiers

        Returns:
            Dictionary mapping chunk IDs to cache entries
        """
        pass

    @abstractmethod
    def batch_put(self, embeddings: Dict[str, EmbeddingCacheEntry]) -> int:
        """
        Store multiple embeddings in batch.

        Args:
            embeddings: Dictionary mapping chunk IDs to cache entries

        Returns:
            Number of successfully stored embeddings
        """
        pass


# Cache event system for coordination
class CacheEvent:
    """Base class for cache events."""

    def __init__(self, cache_type: CacheType, timestamp: Optional[datetime] = None):
        self.cache_type = cache_type
        self.timestamp = timestamp or datetime.now()


class CacheHitEvent(CacheEvent):
    """Event fired on cache hit."""

    def __init__(self, cache_type: CacheType, key: str, size_bytes: int):
        super().__init__(cache_type)
        self.key = key
        self.size_bytes = size_bytes


class CacheMissEvent(CacheEvent):
    """Event fired on cache miss."""

    def __init__(self, cache_type: CacheType, key: str):
        super().__init__(cache_type)
        self.key = key


class CacheEvictionEvent(CacheEvent):
    """Event fired on cache eviction."""

    def __init__(self, cache_type: CacheType, key: str, reason: str):
        super().__init__(cache_type)
        self.key = key
        self.reason = reason


class ICacheEventListener(ABC):
    """Interface for cache event listeners."""

    @abstractmethod
    def on_cache_hit(self, event: CacheHitEvent) -> None:
        """Handle cache hit event."""
        pass

    @abstractmethod
    def on_cache_miss(self, event: CacheMissEvent) -> None:
        """Handle cache miss event."""
        pass

    @abstractmethod
    def on_cache_eviction(self, event: CacheEvictionEvent) -> None:
        """Handle cache eviction event."""
        pass


# Utility classes for cache management
class CacheKeyGenerator:
    """Utility for generating consistent cache keys."""

    @staticmethod
    def generate_key(*args, **kwargs) -> str:
        """Generate cache key from arguments."""
        import hashlib

        # Combine all arguments into a string
        key_parts = []
        for arg in args:
            key_parts.append(str(arg))

        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")

        key_string = "|".join(key_parts)

        # Generate hash for consistent key
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    @staticmethod
    def generate_model_key(model_id: str, model_type: str, version: str = "latest") -> str:
        """Generate key for model cache."""
        return f"model:{model_type}:{model_id}:{version}"

    @staticmethod
    def generate_embedding_key(chunk_id: str, model_name: str, chunk_hash: str) -> str:
        """Generate key for embedding cache."""
        return f"embedding:{model_name}:{chunk_id}:{chunk_hash[:16]}"


class CacheMetrics:
    """Utility for tracking cache metrics."""

    def __init__(self):
        self._metrics: Dict[CacheType, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def record_hit(self, cache_type: CacheType, key: str, size_bytes: int) -> None:
        """Record cache hit."""
        with self._lock:
            if cache_type not in self._metrics:
                self._metrics[cache_type] = {
                    'hits': 0, 'misses': 0, 'evictions': 0,
                    'total_size': 0, 'last_updated': datetime.now()
                }

            self._metrics[cache_type]['hits'] += 1
            self._metrics[cache_type]['total_size'] += size_bytes
            self._metrics[cache_type]['last_updated'] = datetime.now()

    def record_miss(self, cache_type: CacheType, key: str) -> None:
        """Record cache miss."""
        with self._lock:
            if cache_type not in self._metrics:
                self._metrics[cache_type] = {
                    'hits': 0, 'misses': 0, 'evictions': 0,
                    'total_size': 0, 'last_updated': datetime.now()
                }

            self._metrics[cache_type]['misses'] += 1
            self._metrics[cache_type]['last_updated'] = datetime.now()

    def record_eviction(self, cache_type: CacheType, key: str, size_bytes: int) -> None:
        """Record cache eviction."""
        with self._lock:
            if cache_type not in self._metrics:
                self._metrics[cache_type] = {
                    'hits': 0, 'misses': 0, 'evictions': 0,
                    'total_size': 0, 'last_updated': datetime.now()
                }

            self._metrics[cache_type]['evictions'] += 1
            self._metrics[cache_type]['total_size'] -= size_bytes
            self._metrics[cache_type]['last_updated'] = datetime.now()

    def get_metrics(self, cache_type: CacheType) -> Dict[str, Any]:
        """Get metrics for cache type."""
        with self._lock:
            return self._metrics.get(cache_type, {}).copy()

    def get_all_metrics(self) -> Dict[CacheType, Dict[str, Any]]:
        """Get all metrics."""
        with self._lock:
            return {k: v.copy() for k, v in self._metrics.items()}
