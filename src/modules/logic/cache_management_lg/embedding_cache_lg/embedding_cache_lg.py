"""
Module: embedding_cache_lg
Description: LRU cache for document embeddings and vectors with compression and batch operations
Phase: 4
Location: /src/modules/logic/cache_management_lg/embedding_cache_lg/embedding_cache_lg.py
"""

# Standard library imports
import gzip
import hashlib
import pickle
import threading
import time
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import weakref

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.cache_management_lg.base_interfaces import (
    IEmbeddingCache,
    CacheEntry,
    CacheResult,
    CacheStats,
    CacheConfig,
    CacheStatus,
    CacheType,
    CacheLevel,
    EmbeddingCacheEntry,
    EvictionPolicy,
    CacheHitEvent,
    CacheMissEvent,
    CacheEvictionEvent,
    ICacheEventListener
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class CompressedEmbeddingEntry(EmbeddingCacheEntry):
    """Embedding cache entry with compression support."""
    
    def __init__(self, chunk_id: str, vector: np.ndarray, model_name: str, 
                 chunk_hash: str, compression_enabled: bool = True):
        """Initialize compressed embedding entry."""
        now = datetime.now()
        
        # Store original vector info
        self.original_vector = vector
        self.original_size_bytes = vector.nbytes
        self.compression_enabled = compression_enabled
        
        # Compress vector if enabled
        if compression_enabled:
            compressed_data, compression_ratio = self._compress_vector(vector)
            stored_vector = compressed_data
            size_bytes = len(compressed_data) if isinstance(compressed_data, bytes) else compressed_data.nbytes
        else:
            stored_vector = vector.copy()
            compression_ratio = 1.0
            size_bytes = vector.nbytes
        
        # Initialize base entry
        super().__init__(
            key=chunk_id,
            value=stored_vector,
            size_bytes=size_bytes,
            created_at=now,
            last_accessed=now,
            chunk_id=chunk_id,
            vector=stored_vector,
            vector_dimension=len(vector),
            model_name=model_name,
            chunk_hash=chunk_hash,
            compression_ratio=compression_ratio
        )
        
        # Additional tracking
        self.access_frequency = 0.0
        self.last_frequency_update = now
    
    def _compress_vector(self, vector: np.ndarray) -> Tuple[bytes, float]:
        """Compress vector using gzip."""
        try:
            # Convert to bytes
            vector_bytes = vector.tobytes()
            
            # Compress
            compressed_bytes = gzip.compress(vector_bytes, compresslevel=6)
            
            # Calculate compression ratio
            compression_ratio = len(vector_bytes) / len(compressed_bytes)
            
            return compressed_bytes, compression_ratio
            
        except Exception:
            # Fallback to no compression
            return vector.copy(), 1.0
    
    def _decompress_vector(self, compressed_data: bytes, dtype: np.dtype, shape: Tuple[int, ...]) -> np.ndarray:
        """Decompress vector from bytes."""
        try:
            # Decompress
            vector_bytes = gzip.decompress(compressed_data)
            
            # Convert back to numpy array
            vector = np.frombuffer(vector_bytes, dtype=dtype).reshape(shape)
            
            return vector
            
        except Exception:
            # Return empty array on error
            return np.array([])
    
    def get_vector(self) -> np.ndarray:
        """Get decompressed vector."""
        if self.compression_enabled and isinstance(self.vector, bytes):
            # Decompress on demand
            return self._decompress_vector(
                self.vector,
                self.original_vector.dtype,
                self.original_vector.shape
            )
        else:
            return self.vector.copy()
    
    def update_frequency(self) -> None:
        """Update access frequency."""
        now = datetime.now()
        time_delta = (now - self.last_frequency_update).total_seconds()
        
        if time_delta > 0:
            # Exponential decay
            decay_factor = max(0.1, 1.0 - (time_delta / 3600))  # 1 hour decay
            self.access_frequency = self.access_frequency * decay_factor + 1.0
            self.last_frequency_update = now
    
    def access(self) -> None:
        """Record access and update frequency."""
        super().access()
        self.update_frequency()


class EmbeddingBatchProcessor:
    """Handles batch operations for embedding cache."""
    
    def __init__(self, cache_ref: weakref.ref, batch_size: int = 100):
        """Initialize batch processor."""
        self.cache_ref = cache_ref
        self.batch_size = batch_size
        self._logger = get_logger(__name__)
    
    def batch_get(self, chunk_ids: List[str]) -> Dict[str, EmbeddingCacheEntry]:
        """Get multiple embeddings in batch."""
        cache = self.cache_ref()
        if not cache:
            return {}
        
        results = {}
        
        # Process in batches to avoid memory issues
        for i in range(0, len(chunk_ids), self.batch_size):
            batch_ids = chunk_ids[i:i + self.batch_size]
            
            with cache._acquire_lock():
                for chunk_id in batch_ids:
                    if chunk_id in cache._cache:
                        entry = cache._cache[chunk_id]
                        if not entry.is_expired:
                            entry.access()
                            cache._cache.move_to_end(chunk_id)
                            results[chunk_id] = entry
        
        return results
    
    def batch_put(self, embeddings: Dict[str, EmbeddingCacheEntry]) -> int:
        """Store multiple embeddings in batch."""
        cache = self.cache_ref()
        if not cache:
            return 0
        
        successful_count = 0
        
        # Process in batches
        embedding_items = list(embeddings.items())
        for i in range(0, len(embedding_items), self.batch_size):
            batch_items = embedding_items[i:i + self.batch_size]
            
            with cache._acquire_lock():
                for chunk_id, entry in batch_items:
                    try:
                        # Check if already exists
                        if chunk_id in cache._cache:
                            old_entry = cache._cache[chunk_id]
                            cache._current_size_bytes -= old_entry.size_bytes
                            cache._embeddings_by_model[old_entry.model_name].discard(chunk_id)
                        
                        # Check memory limits
                        if (cache._current_size_bytes + entry.size_bytes > cache._max_size_bytes or
                            len(cache._cache) >= cache._max_entries):
                            cache._evict_entries(entry.size_bytes)
                        
                        # Add entry
                        cache._cache[chunk_id] = entry
                        cache._current_size_bytes += entry.size_bytes
                        cache._embeddings_by_model[entry.model_name].add(chunk_id)
                        cache._cache.move_to_end(chunk_id)
                        
                        successful_count += 1
                        
                    except Exception as e:
                        cache._logger.error(f"Failed to put embedding {chunk_id}: {e}")
        
        return successful_count


class EmbeddingCacheCore:
    """Core embedding cache implementation."""
    
    def __init__(self, config: CacheConfig):
        """Initialize embedding cache core."""
        self._config = config
        self._logger = get_logger(__name__)
        
        # Cache storage
        self._cache: OrderedDict[str, CompressedEmbeddingEntry] = OrderedDict()
        self._embeddings_by_model: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock() if config.thread_safe else None
        
        # Memory tracking
        self._current_size_bytes = 0
        self._max_size_bytes = config.max_size_bytes
        self._max_entries = config.max_entries
        
        # Statistics
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._total_access_time_ms = 0.0
        self._compression_savings_bytes = 0
        
        # Batch processor
        self._batch_processor = EmbeddingBatchProcessor(weakref.ref(self))
        
        # Background cleanup
        self._cleanup_enabled = config.enable_background_cleanup
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        if self._cleanup_enabled:
            self._start_cleanup_thread()
        
        self._logger.info(f"Embedding cache core initialized with max_size={config.max_size_bytes} bytes")
    
    def _acquire_lock(self):
        """Acquire lock if thread safety is enabled."""
        if self._lock:
            return self._lock
        else:
            # Return a dummy context manager
            class DummyLock:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return DummyLock()
    
    def get_embedding(self, chunk_id: str) -> Optional[EmbeddingCacheEntry]:
        """Get embedding from cache."""
        start_time = time.time()
        
        with self._acquire_lock():
            if chunk_id in self._cache:
                entry = self._cache[chunk_id]
                
                # Check if expired
                if entry.is_expired:
                    self._remove_entry(chunk_id)
                    self._miss_count += 1
                    
                    access_time_ms = (time.time() - start_time) * 1000
                    self._total_access_time_ms += access_time_ms
                    
                    return None
                
                # Update access tracking
                entry.access()
                
                # Move to end (most recently used)
                self._cache.move_to_end(chunk_id)
                
                self._hit_count += 1
                
                access_time_ms = (time.time() - start_time) * 1000
                self._total_access_time_ms += access_time_ms
                
                return entry
            else:
                self._miss_count += 1
                
                access_time_ms = (time.time() - start_time) * 1000
                self._total_access_time_ms += access_time_ms
                
                return None
    
    def put_embedding(self, chunk_id: str, embedding_entry: EmbeddingCacheEntry) -> bool:
        """Store embedding in cache."""
        try:
            # Convert to compressed entry if needed
            if not isinstance(embedding_entry, CompressedEmbeddingEntry):
                compressed_entry = CompressedEmbeddingEntry(
                    chunk_id=chunk_id,
                    vector=embedding_entry.vector,
                    model_name=embedding_entry.model_name,
                    chunk_hash=embedding_entry.chunk_hash,
                    compression_enabled=self._config.compression_enabled
                )
            else:
                compressed_entry = embedding_entry
            
            with self._acquire_lock():
                # Check if already exists
                if chunk_id in self._cache:
                    old_entry = self._cache[chunk_id]
                    self._current_size_bytes -= old_entry.size_bytes
                    self._embeddings_by_model[old_entry.model_name].discard(chunk_id)
                
                # Check if we need to evict entries
                if (self._current_size_bytes + compressed_entry.size_bytes > self._max_size_bytes or
                    len(self._cache) >= self._max_entries):
                    self._evict_entries(compressed_entry.size_bytes)
                
                # Add new entry
                self._cache[chunk_id] = compressed_entry
                self._current_size_bytes += compressed_entry.size_bytes
                self._embeddings_by_model[compressed_entry.model_name].add(chunk_id)
                
                # Track compression savings
                if compressed_entry.compression_enabled:
                    original_size = compressed_entry.original_size_bytes
                    compressed_size = compressed_entry.size_bytes
                    self._compression_savings_bytes += (original_size - compressed_size)
                
                # Move to end (most recently used)
                self._cache.move_to_end(chunk_id)
                
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to put embedding {chunk_id}: {e}")
            return False

    def get_embeddings_by_model(self, model_name: str) -> List[EmbeddingCacheEntry]:
        """Get all embeddings for a specific model."""
        with self._acquire_lock():
            embeddings = []
            chunk_ids = self._embeddings_by_model.get(model_name, set())

            for chunk_id in chunk_ids:
                if chunk_id in self._cache:
                    entry = self._cache[chunk_id]
                    if not entry.is_expired:
                        embeddings.append(entry)

            return embeddings

    def batch_get(self, chunk_ids: List[str]) -> Dict[str, EmbeddingCacheEntry]:
        """Get multiple embeddings in batch."""
        return self._batch_processor.batch_get(chunk_ids)

    def batch_put(self, embeddings: Dict[str, EmbeddingCacheEntry]) -> int:
        """Store multiple embeddings in batch."""
        return self._batch_processor.batch_put(embeddings)

    def evict(self, chunk_id: str) -> bool:
        """Remove embedding from cache."""
        with self._acquire_lock():
            if chunk_id in self._cache:
                self._remove_entry(chunk_id)
                return True
            return False

    def _remove_entry(self, chunk_id: str) -> None:
        """Remove entry and update tracking."""
        if chunk_id in self._cache:
            entry = self._cache[chunk_id]
            self._current_size_bytes -= entry.size_bytes
            self._embeddings_by_model[entry.model_name].discard(chunk_id)
            del self._cache[chunk_id]

    def _evict_entries(self, needed_bytes: int = 0) -> None:
        """Evict entries based on policy."""
        target_size = self._max_size_bytes * (self._config.eviction_threshold_percent / 100.0)

        if self._config.eviction_policy == EvictionPolicy.LRU:
            self._evict_lru(target_size, needed_bytes)
        elif self._config.eviction_policy == EvictionPolicy.LFU:
            self._evict_lfu(target_size, needed_bytes)
        elif self._config.eviction_policy == EvictionPolicy.TTL:
            self._evict_expired()
        else:  # ADAPTIVE
            self._evict_adaptive(target_size, needed_bytes)

    def _evict_lru(self, target_size: float, needed_bytes: int) -> None:
        """Evict least recently used embeddings."""
        evicted_count = 0

        while (self._current_size_bytes + needed_bytes > target_size and
               self._cache and
               evicted_count < self._config.eviction_batch_size):

            # Remove from beginning (least recently used)
            chunk_id, entry = self._cache.popitem(last=False)
            self._current_size_bytes -= entry.size_bytes
            self._embeddings_by_model[entry.model_name].discard(chunk_id)
            self._eviction_count += 1
            evicted_count += 1

            self._logger.debug(f"Evicted LRU embedding: {chunk_id}")

    def _evict_lfu(self, target_size: float, needed_bytes: int) -> None:
        """Evict least frequently used embeddings."""
        if not self._cache:
            return

        # Sort by access frequency
        entries_by_frequency = sorted(
            self._cache.items(),
            key=lambda x: x[1].access_frequency
        )

        evicted_count = 0

        for chunk_id, entry in entries_by_frequency:
            if (self._current_size_bytes + needed_bytes <= target_size or
                evicted_count >= self._config.eviction_batch_size):
                break

            self._remove_entry(chunk_id)
            self._eviction_count += 1
            evicted_count += 1

            self._logger.debug(f"Evicted LFU embedding: {chunk_id}")

    def _evict_expired(self) -> None:
        """Evict expired embeddings."""
        expired_ids = []

        for chunk_id, entry in self._cache.items():
            if entry.is_expired:
                expired_ids.append(chunk_id)

        for chunk_id in expired_ids:
            self._remove_entry(chunk_id)
            self._eviction_count += 1
            self._logger.debug(f"Evicted expired embedding: {chunk_id}")

    def _evict_adaptive(self, target_size: float, needed_bytes: int) -> None:
        """Adaptive eviction based on embedding usage patterns."""
        # First evict expired embeddings
        self._evict_expired()

        # If still need space, use hybrid approach
        if self._current_size_bytes + needed_bytes > target_size:
            # Calculate embedding priorities
            embedding_priorities = []

            for chunk_id, entry in self._cache.items():
                # Priority based on: recency, frequency, model importance
                recency_score = (datetime.now() - entry.last_accessed).total_seconds() / 3600
                frequency_score = 1.0 / max(1, entry.access_frequency)

                # Model importance (embedding models are generally important)
                model_importance = 0.8

                priority = recency_score + frequency_score - model_importance
                embedding_priorities.append((priority, chunk_id, entry))

            # Sort by priority (highest first = evict first)
            embedding_priorities.sort(reverse=True)

            evicted_count = 0
            for priority, chunk_id, entry in embedding_priorities:
                if (self._current_size_bytes + needed_bytes <= target_size or
                    evicted_count >= self._config.eviction_batch_size):
                    break

                self._remove_entry(chunk_id)
                self._eviction_count += 1
                evicted_count += 1

                self._logger.debug(f"Evicted adaptive embedding: {chunk_id} (priority: {priority:.2f})")

    def clear(self) -> bool:
        """Clear all embeddings from cache."""
        with self._acquire_lock():
            self._cache.clear()
            self._embeddings_by_model.clear()
            self._current_size_bytes = 0
            self._compression_savings_bytes = 0
            return True

    def get_size(self) -> Tuple[int, int]:
        """Get cache size information."""
        with self._acquire_lock():
            return len(self._cache), self._current_size_bytes

    def contains(self, chunk_id: str) -> bool:
        """Check if embedding exists in cache."""
        with self._acquire_lock():
            return chunk_id in self._cache and not self._cache[chunk_id].is_expired

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._acquire_lock():
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0
            miss_rate = self._miss_count / total_requests if total_requests > 0 else 0.0
            avg_access_time = self._total_access_time_ms / total_requests if total_requests > 0 else 0.0
            memory_usage_percent = (self._current_size_bytes / self._max_size_bytes) * 100.0

            return CacheStats(
                cache_type=CacheType.EMBEDDING,
                cache_level=CacheLevel.L1_MEMORY,
                total_entries=len(self._cache),
                total_size_bytes=self._current_size_bytes,
                hit_count=self._hit_count,
                miss_count=self._miss_count,
                eviction_count=self._eviction_count,
                hit_rate=hit_rate,
                miss_rate=miss_rate,
                average_access_time_ms=avg_access_time,
                memory_usage_percent=memory_usage_percent
            )

    def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        with self._acquire_lock():
            total_original_size = 0
            total_compressed_size = 0
            compressed_count = 0

            for entry in self._cache.values():
                if hasattr(entry, 'compression_enabled') and entry.compression_enabled:
                    total_original_size += entry.original_size_bytes
                    total_compressed_size += entry.size_bytes
                    compressed_count += 1

            compression_ratio = total_original_size / total_compressed_size if total_compressed_size > 0 else 1.0

            return {
                'compression_enabled': self._config.compression_enabled,
                'compressed_entries': compressed_count,
                'total_entries': len(self._cache),
                'original_size_bytes': total_original_size,
                'compressed_size_bytes': total_compressed_size,
                'compression_ratio': compression_ratio,
                'savings_bytes': total_original_size - total_compressed_size,
                'savings_percent': ((total_original_size - total_compressed_size) / total_original_size * 100) if total_original_size > 0 else 0.0
            }

    def _start_cleanup_thread(self) -> None:
        """Start background cleanup thread."""
        def cleanup_worker():
            while not self._shutdown_event.wait(self._config.cleanup_interval_seconds):
                try:
                    # Clean up expired entries
                    self._evict_expired()

                    # Periodic optimization
                    if len(self._cache) > self._max_entries * 0.8:
                        self._evict_entries()

                except Exception as e:
                    self._logger.error(f"Background cleanup error: {e}")

        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        self._logger.info("Background cleanup thread started")

    def shutdown(self) -> None:
        """Shutdown cache and cleanup resources."""
        self._shutdown_event.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)

        self.clear()
        self._logger.info("Embedding cache core shutdown complete")


class EmbeddingCache(IEmbeddingCache):
    """
    LRU cache for document embeddings and vectors with compression and batch operations.

    Features:
    - Vector compression to reduce memory usage
    - Batch operations for efficient bulk processing
    - Model-based organization and retrieval
    - Adaptive eviction based on access patterns
    - Thread-safe operations with configurable locking
    - Detailed compression and performance metrics
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize embedding cache.

        Args:
            config: Cache configuration
        """
        self._config = config or CacheConfig()
        self._logger = get_logger(__name__)

        # Core cache implementation
        self._cache = EmbeddingCacheCore(self._config)

        # Event listeners
        self._event_listeners: List[ICacheEventListener] = []

        # Performance tracking
        self._start_time = datetime.now()

        self._logger.info("EmbeddingCache initialized successfully")

    def get(self, key: str) -> CacheResult:
        """
        Retrieve value from cache.

        Args:
            key: Cache key (chunk_id)

        Returns:
            CacheResult with embedding entry if found
        """
        if not key:
            return CacheResult(status=CacheStatus.ERROR, key=key)

        entry = self._cache.get_embedding(key)

        if entry:
            # Fire hit event
            self._fire_hit_event(key, entry.size_bytes)

            return CacheResult(
                status=CacheStatus.HIT,
                key=key,
                value=entry,
                size_bytes=entry.size_bytes,
                hit_count=entry.access_count,
                last_accessed=entry.last_accessed,
                cache_level=CacheLevel.L1_MEMORY,
                metadata=entry.metadata.copy()
            )
        else:
            # Fire miss event
            self._fire_miss_event(key)

            return CacheResult(
                status=CacheStatus.MISS,
                key=key,
                cache_level=CacheLevel.L1_MEMORY
            )

    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Store value in cache.

        Args:
            key: Cache key (chunk_id)
            value: EmbeddingCacheEntry to store
            ttl_seconds: Optional time-to-live

        Returns:
            True if successfully stored
        """
        if not key or not isinstance(value, EmbeddingCacheEntry):
            return False

        # Use config default TTL if not specified
        if ttl_seconds is None:
            ttl_seconds = self._config.default_ttl_seconds

        # Update TTL
        value.ttl_seconds = ttl_seconds

        return self._cache.put_embedding(key, value)

    def evict(self, key: str) -> bool:
        """
        Remove entry from cache.

        Args:
            key: Cache key (chunk_id)

        Returns:
            True if successfully evicted
        """
        if not key:
            return False

        success = self._cache.evict(key)

        if success:
            self._fire_eviction_event(key, "manual")

        return success

    def clear(self) -> bool:
        """
        Clear all entries from cache.

        Returns:
            True if successfully cleared
        """
        return self._cache.clear()

    def get_stats(self) -> CacheStats:
        """
        Get cache performance statistics.

        Returns:
            CacheStats object
        """
        return self._cache.get_stats()

    def get_size(self) -> Tuple[int, int]:
        """
        Get cache size information.

        Returns:
            Tuple of (entry_count, total_bytes)
        """
        return self._cache.get_size()

    def contains(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key (chunk_id)

        Returns:
            True if key exists
        """
        if not key:
            return False

        return self._cache.contains(key)

    # Embedding-specific methods
    def get_embedding(self, chunk_id: str) -> Optional[EmbeddingCacheEntry]:
        """
        Get embedding from cache.

        Args:
            chunk_id: Chunk identifier

        Returns:
            EmbeddingCacheEntry if found
        """
        return self._cache.get_embedding(chunk_id)

    def put_embedding(self, chunk_id: str, embedding_entry: EmbeddingCacheEntry) -> bool:
        """
        Store embedding in cache.

        Args:
            chunk_id: Chunk identifier
            embedding_entry: Embedding cache entry

        Returns:
            True if successfully stored
        """
        return self._cache.put_embedding(chunk_id, embedding_entry)

    def get_embeddings_by_model(self, model_name: str) -> List[EmbeddingCacheEntry]:
        """
        Get all embeddings for a specific model.

        Args:
            model_name: Name of the embedding model

        Returns:
            List of embedding cache entries
        """
        return self._cache.get_embeddings_by_model(model_name)

    def batch_get(self, chunk_ids: List[str]) -> Dict[str, EmbeddingCacheEntry]:
        """
        Get multiple embeddings in batch.

        Args:
            chunk_ids: List of chunk identifiers

        Returns:
            Dictionary mapping chunk IDs to cache entries
        """
        return self._cache.batch_get(chunk_ids)

    def batch_put(self, embeddings: Dict[str, EmbeddingCacheEntry]) -> int:
        """
        Store multiple embeddings in batch.

        Args:
            embeddings: Dictionary mapping chunk IDs to cache entries

        Returns:
            Number of successfully stored embeddings
        """
        return self._cache.batch_put(embeddings)

    # Event management
    def add_event_listener(self, listener: ICacheEventListener) -> None:
        """Add cache event listener."""
        if listener not in self._event_listeners:
            self._event_listeners.append(listener)

    def remove_event_listener(self, listener: ICacheEventListener) -> None:
        """Remove cache event listener."""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    def _fire_hit_event(self, key: str, size_bytes: int) -> None:
        """Fire cache hit event."""
        event = CacheHitEvent(CacheType.EMBEDDING, key, size_bytes)
        for listener in self._event_listeners:
            try:
                listener.on_cache_hit(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    def _fire_miss_event(self, key: str) -> None:
        """Fire cache miss event."""
        event = CacheMissEvent(CacheType.EMBEDDING, key)
        for listener in self._event_listeners:
            try:
                listener.on_cache_miss(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    def _fire_eviction_event(self, key: str, reason: str) -> None:
        """Fire cache eviction event."""
        event = CacheEvictionEvent(CacheType.EMBEDDING, key, reason)
        for listener in self._event_listeners:
            try:
                listener.on_cache_eviction(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    # Advanced operations
    def get_model_names(self) -> List[str]:
        """Get all model names in cache."""
        return list(self._cache._embeddings_by_model.keys())

    def get_embedding_count_by_model(self) -> Dict[str, int]:
        """Get embedding count by model."""
        return {
            model_name: len(chunk_ids)
            for model_name, chunk_ids in self._cache._embeddings_by_model.items()
        }

    def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return self._cache.get_compression_stats()

    def get_cache_info(self) -> Dict[str, Any]:
        """Get comprehensive cache information."""
        stats = self.get_stats()
        compression_stats = self.get_compression_stats()
        uptime = (datetime.now() - self._start_time).total_seconds()

        return {
            'cache_type': 'embedding',
            'cache_level': 'L1_MEMORY',
            'uptime_seconds': uptime,
            'configuration': {
                'max_entries': self._config.max_entries,
                'max_size_bytes': self._config.max_size_bytes,
                'eviction_policy': self._config.eviction_policy.value,
                'compression_enabled': self._config.compression_enabled,
                'enable_persistence': self._config.enable_persistence
            },
            'statistics': {
                'total_entries': stats.total_entries,
                'total_size_bytes': stats.total_size_bytes,
                'hit_rate': stats.hit_rate,
                'miss_rate': stats.miss_rate,
                'eviction_count': stats.eviction_count,
                'average_access_time_ms': stats.average_access_time_ms
            },
            'compression': compression_stats,
            'models': self.get_embedding_count_by_model(),
            'event_listeners': len(self._event_listeners)
        }

    def optimize(self) -> bool:
        """Optimize cache performance."""
        try:
            # Clean up expired entries
            self._cache._evict_expired()

            # Force garbage collection for better memory management
            import gc
            gc.collect()

            self._logger.info("Embedding cache optimization completed")
            return True

        except Exception as e:
            self._logger.error(f"Embedding cache optimization failed: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown cache and cleanup resources."""
        self._cache.shutdown()
        self._event_listeners.clear()
        self._logger.info("EmbeddingCache shutdown complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()

    def __len__(self) -> int:
        """Get number of embeddings in cache."""
        return self.get_size()[0]

    def __contains__(self, chunk_id: str) -> bool:
        """Check if embedding exists in cache."""
        return self.contains(chunk_id)
