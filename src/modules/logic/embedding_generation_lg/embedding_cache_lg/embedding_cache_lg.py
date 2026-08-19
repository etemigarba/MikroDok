"""
Module: embedding_cache_lg
Description: LRU cache implementation for frequently accessed embeddings to reduce computation
Phase: 4
Location: /src/modules/logic/embedding_generation_lg/embedding_cache_lg/embedding_cache_lg.py
"""

# Standard library imports
import hashlib
import pickle
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import gzip

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.embedding_generation_lg.base_interfaces import (
    IEmbeddingCache,
    CacheResult,
    CacheConfig,
    CacheStatus,
    EmbeddingMetadata
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class CacheEntry:
    """Individual cache entry with metadata."""
    
    def __init__(self, vector: np.ndarray, metadata: Optional[EmbeddingMetadata] = None):
        """Initialize cache entry."""
        self.vector = vector
        self.metadata = metadata
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.access_count = 1
        self.size_bytes = self._calculate_size()
    
    def _calculate_size(self) -> int:
        """Calculate memory size of the entry."""
        vector_size = self.vector.nbytes if isinstance(self.vector, np.ndarray) else 0
        metadata_size = 1024 if self.metadata else 0  # Rough estimate
        return vector_size + metadata_size + 200  # Base overhead
    
    def access(self) -> None:
        """Record access to this entry."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class CacheOptimizer:
    """
    Optimizes cache performance through eviction policies and preloading strategies.
    
    Features:
    - Multiple eviction policies (LRU, LFU, TTL)
    - Memory usage monitoring
    - Access pattern analysis
    - Performance metrics tracking
    """
    
    def __init__(self, config: CacheConfig):
        """Initialize cache optimizer."""
        self._config = config
        self._logger = get_logger(__name__)
        
        # Performance tracking
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._total_requests = 0
        self._lock = threading.RLock()
    
    def should_evict_entry(self, entry: CacheEntry, current_time: datetime) -> bool:
        """Determine if entry should be evicted based on policy."""
        # TTL-based eviction
        if self._config.ttl_seconds:
            age_seconds = (current_time - entry.created_at).total_seconds()
            if age_seconds > self._config.ttl_seconds:
                return True
        
        return False
    
    def select_eviction_candidates(self, cache_entries: Dict[str, CacheEntry], 
                                 target_count: int) -> List[str]:
        """Select entries for eviction based on configured policy."""
        if not cache_entries or target_count <= 0:
            return []
        
        current_time = datetime.now()
        candidates = []
        
        # First, remove expired entries
        for chunk_id, entry in cache_entries.items():
            if self.should_evict_entry(entry, current_time):
                candidates.append(chunk_id)
        
        # If we need more candidates, apply eviction policy
        remaining_needed = target_count - len(candidates)
        if remaining_needed > 0:
            policy = self._config.eviction_policy.lower()
            
            if policy == "lru":
                # Least Recently Used
                sorted_entries = sorted(
                    cache_entries.items(),
                    key=lambda x: x[1].last_accessed
                )
            elif policy == "lfu":
                # Least Frequently Used
                sorted_entries = sorted(
                    cache_entries.items(),
                    key=lambda x: x[1].access_count
                )
            else:  # FIFO
                # First In, First Out
                sorted_entries = sorted(
                    cache_entries.items(),
                    key=lambda x: x[1].created_at
                )
            
            # Add candidates excluding already selected ones
            for chunk_id, _ in sorted_entries:
                if chunk_id not in candidates:
                    candidates.append(chunk_id)
                    if len(candidates) >= target_count:
                        break
        
        return candidates[:target_count]
    
    def record_hit(self) -> None:
        """Record cache hit."""
        with self._lock:
            self._hit_count += 1
            self._total_requests += 1
    
    def record_miss(self) -> None:
        """Record cache miss."""
        with self._lock:
            self._miss_count += 1
            self._total_requests += 1
    
    def record_eviction(self) -> None:
        """Record cache eviction."""
        with self._lock:
            self._eviction_count += 1
    
    def get_hit_rate(self) -> float:
        """Calculate current hit rate."""
        with self._lock:
            if self._total_requests == 0:
                return 0.0
            return self._hit_count / self._total_requests
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        with self._lock:
            return {
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "eviction_count": self._eviction_count,
                "total_requests": self._total_requests,
                "hit_rate": self.get_hit_rate(),
                "eviction_policy": self._config.eviction_policy
            }


class CacheManager:
    """
    Manages cache persistence and serialization.
    
    Features:
    - Disk persistence
    - Compression support
    - Atomic operations
    - Recovery mechanisms
    """
    
    def __init__(self, config: CacheConfig):
        """Initialize cache manager."""
        self._config = config
        self._logger = get_logger(__name__)
        self._persistence_enabled = config.enable_persistence and config.persistence_path
        
        if self._persistence_enabled:
            self._persistence_path = Path(config.persistence_path)
            self._persistence_path.mkdir(parents=True, exist_ok=True)
    
    def save_cache(self, cache_entries: Dict[str, CacheEntry]) -> bool:
        """Save cache to disk."""
        if not self._persistence_enabled:
            return True
        
        try:
            cache_file = self._persistence_path / "embedding_cache.pkl"
            temp_file = cache_file.with_suffix('.tmp')
            
            # Prepare data for serialization
            serializable_data = {}
            for chunk_id, entry in cache_entries.items():
                serializable_data[chunk_id] = {
                    'vector': entry.vector,
                    'metadata': entry.metadata,
                    'created_at': entry.created_at,
                    'last_accessed': entry.last_accessed,
                    'access_count': entry.access_count
                }
            
            # Save to temporary file first
            if self._config.compression_enabled:
                with gzip.open(temp_file, 'wb') as f:
                    pickle.dump(serializable_data, f)
            else:
                with open(temp_file, 'wb') as f:
                    pickle.dump(serializable_data, f)
            
            # Atomic move
            temp_file.replace(cache_file)
            
            self._logger.info(f"Cache saved to {cache_file}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save cache: {e}")
            return False
    
    def load_cache(self) -> Dict[str, CacheEntry]:
        """Load cache from disk."""
        if not self._persistence_enabled:
            return {}
        
        try:
            cache_file = self._persistence_path / "embedding_cache.pkl"
            if not cache_file.exists():
                return {}
            
            # Load data
            if self._config.compression_enabled:
                with gzip.open(cache_file, 'rb') as f:
                    serializable_data = pickle.load(f)
            else:
                with open(cache_file, 'rb') as f:
                    serializable_data = pickle.load(f)
            
            # Reconstruct cache entries
            cache_entries = {}
            for chunk_id, data in serializable_data.items():
                entry = CacheEntry(data['vector'], data['metadata'])
                entry.created_at = data['created_at']
                entry.last_accessed = data['last_accessed']
                entry.access_count = data['access_count']
                cache_entries[chunk_id] = entry
            
            self._logger.info(f"Cache loaded from {cache_file}: {len(cache_entries)} entries")
            return cache_entries
            
        except Exception as e:
            self._logger.error(f"Failed to load cache: {e}")
            return {}


class LRUEmbeddingCache:
    """
    Core LRU cache implementation with memory management.
    
    Features:
    - LRU eviction policy
    - Memory limit enforcement
    - Thread-safe operations
    - Access tracking
    """
    
    def __init__(self, config: CacheConfig):
        """Initialize LRU cache."""
        self._config = config
        self._logger = get_logger(__name__)
        
        # Cache storage
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Memory tracking
        self._current_memory_bytes = 0
        self._memory_limit_bytes = config.memory_limit_mb * 1024 * 1024
        
        # Components
        self._optimizer = CacheOptimizer(config)
        self._manager = CacheManager(config)
        
        # Load persisted cache
        if config.enable_persistence:
            self._load_persisted_cache()
    
    def _load_persisted_cache(self) -> None:
        """Load cache from persistence."""
        try:
            persisted_entries = self._manager.load_cache()
            with self._lock:
                for chunk_id, entry in persisted_entries.items():
                    if len(self._cache) < self._config.max_cache_size:
                        self._cache[chunk_id] = entry
                        self._current_memory_bytes += entry.size_bytes
                    else:
                        break
        except Exception as e:
            self._logger.error(f"Failed to load persisted cache: {e}")
    
    def get(self, chunk_id: str) -> CacheResult:
        """Retrieve entry from cache."""
        with self._lock:
            if chunk_id in self._cache:
                entry = self._cache[chunk_id]
                entry.access()
                
                # Move to end (most recently used)
                self._cache.move_to_end(chunk_id)
                
                self._optimizer.record_hit()
                
                return CacheResult(
                    status=CacheStatus.HIT,
                    chunk_id=chunk_id,
                    vector=entry.vector.copy(),
                    hit_count=entry.access_count,
                    last_accessed=entry.last_accessed,
                    cache_size_bytes=self._current_memory_bytes
                )
            else:
                self._optimizer.record_miss()
                
                return CacheResult(
                    status=CacheStatus.MISS,
                    chunk_id=chunk_id,
                    cache_size_bytes=self._current_memory_bytes
                )
    
    def put(self, chunk_id: str, vector: np.ndarray, 
            metadata: Optional[EmbeddingMetadata] = None) -> bool:
        """Store entry in cache."""
        try:
            entry = CacheEntry(vector.copy(), metadata)
            
            with self._lock:
                # Check if already exists
                if chunk_id in self._cache:
                    old_entry = self._cache[chunk_id]
                    self._current_memory_bytes -= old_entry.size_bytes
                
                # Check memory limit
                if (self._current_memory_bytes + entry.size_bytes > self._memory_limit_bytes or
                    len(self._cache) >= self._config.max_cache_size):
                    self._evict_entries()
                
                # Add new entry
                self._cache[chunk_id] = entry
                self._current_memory_bytes += entry.size_bytes
                
                # Move to end (most recently used)
                self._cache.move_to_end(chunk_id)
                
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to store entry {chunk_id}: {e}")
            return False
    
    def evict(self, chunk_id: str) -> bool:
        """Remove specific entry from cache."""
        with self._lock:
            if chunk_id in self._cache:
                entry = self._cache.pop(chunk_id)
                self._current_memory_bytes -= entry.size_bytes
                self._optimizer.record_eviction()
                return True
            return False
    
    def _evict_entries(self) -> None:
        """Evict entries to make space."""
        target_memory = self._memory_limit_bytes * 0.8  # Target 80% of limit
        target_count = int(self._config.max_cache_size * 0.8)  # Target 80% of max size
        
        entries_to_evict = []
        
        # Memory-based eviction
        if self._current_memory_bytes > target_memory:
            memory_to_free = self._current_memory_bytes - target_memory
            freed_memory = 0
            
            for chunk_id in list(self._cache.keys()):
                entry = self._cache[chunk_id]
                entries_to_evict.append(chunk_id)
                freed_memory += entry.size_bytes
                
                if freed_memory >= memory_to_free:
                    break
        
        # Count-based eviction
        if len(self._cache) > target_count:
            excess_count = len(self._cache) - target_count
            candidates = self._optimizer.select_eviction_candidates(
                dict(self._cache), excess_count
            )
            entries_to_evict.extend(candidates)
        
        # Remove duplicates and evict
        unique_evictions = list(set(entries_to_evict))
        for chunk_id in unique_evictions:
            if chunk_id in self._cache:
                entry = self._cache.pop(chunk_id)
                self._current_memory_bytes -= entry.size_bytes
                self._optimizer.record_eviction()
    
    def clear(self) -> bool:
        """Clear all entries from cache."""
        try:
            with self._lock:
                self._cache.clear()
                self._current_memory_bytes = 0
            return True
        except Exception as e:
            self._logger.error(f"Failed to clear cache: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            optimizer_stats = self._optimizer.get_statistics()
            
            return {
                "cache_size": len(self._cache),
                "max_cache_size": self._config.max_cache_size,
                "memory_usage_bytes": self._current_memory_bytes,
                "memory_limit_bytes": self._memory_limit_bytes,
                "memory_utilization": self._current_memory_bytes / self._memory_limit_bytes,
                "cache_utilization": len(self._cache) / self._config.max_cache_size,
                **optimizer_stats
            }


class EmbeddingCache(IEmbeddingCache):
    """
    Main embedding cache that provides LRU cache implementation for frequently accessed embeddings.
    
    Features:
    - LRU cache with 10,000 embeddings capacity
    - 2GB memory limit enforcement
    - Thread-safe operations
    - Persistence support
    - Compression for storage efficiency
    - Multiple eviction policies
    - Performance monitoring
    - Access pattern analysis
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize embedding cache."""
        self._config = config or CacheConfig()
        self._logger = get_logger(__name__)
        
        # Core cache implementation
        self._cache = LRUEmbeddingCache(self._config)
        
        # Background maintenance
        self._maintenance_enabled = True
        self._maintenance_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        if self._config.enable_persistence:
            self._start_maintenance_thread()
        
        self._logger.info("EmbeddingCache initialized successfully")
    
    def get(self, chunk_id: str) -> CacheResult:
        """
        Retrieve embedding from cache.
        
        Args:
            chunk_id: Unique identifier for the chunk
            
        Returns:
            CacheResult with vector if found
        """
        return self._cache.get(chunk_id)
    
    def put(self, chunk_id: str, vector: np.ndarray, 
            metadata: Optional[EmbeddingMetadata] = None) -> bool:
        """
        Store embedding in cache.
        
        Args:
            chunk_id: Unique identifier for the chunk
            vector: Embedding vector to store
            metadata: Optional metadata for the embedding
            
        Returns:
            True if successfully stored, False otherwise
        """
        return self._cache.put(chunk_id, vector, metadata)
    
    def evict(self, chunk_id: str) -> bool:
        """
        Remove embedding from cache.
        
        Args:
            chunk_id: Unique identifier for the chunk
            
        Returns:
            True if successfully evicted, False otherwise
        """
        return self._cache.evict(chunk_id)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        stats = self._cache.get_statistics()
        
        return {
            **stats,
            "configuration": {
                "max_cache_size": self._config.max_cache_size,
                "memory_limit_mb": self._config.memory_limit_mb,
                "eviction_policy": self._config.eviction_policy,
                "ttl_seconds": self._config.ttl_seconds,
                "persistence_enabled": self._config.enable_persistence,
                "compression_enabled": self._config.compression_enabled
            }
        }
    
    def clear_cache(self) -> bool:
        """
        Clear all entries from cache.
        
        Returns:
            True if successfully cleared, False otherwise
        """
        return self._cache.clear()
    
    def _start_maintenance_thread(self) -> None:
        """Start background maintenance thread."""
        if self._maintenance_thread is None or not self._maintenance_thread.is_alive():
            self._maintenance_thread = threading.Thread(
                target=self._maintenance_worker,
                daemon=True,
                name="EmbeddingCacheMaintenance"
            )
            self._maintenance_thread.start()
    
    def _maintenance_worker(self) -> None:
        """Background maintenance worker."""
        while not self._shutdown_event.is_set():
            try:
                # Save cache periodically
                if self._config.enable_persistence:
                    self._cache._manager.save_cache(dict(self._cache._cache))
                
                # Wait for next maintenance cycle
                self._shutdown_event.wait(300)  # 5 minutes
                
            except Exception as e:
                self._logger.error(f"Cache maintenance error: {e}")
                self._shutdown_event.wait(60)  # Wait 1 minute on error
    
    def shutdown(self) -> None:
        """Shutdown cache and save state."""
        self._maintenance_enabled = False
        self._shutdown_event.set()
        
        if self._maintenance_thread and self._maintenance_thread.is_alive():
            self._maintenance_thread.join(timeout=10)
        
        # Final save
        if self._config.enable_persistence:
            self._cache._manager.save_cache(dict(self._cache._cache))
        
        self._logger.info("EmbeddingCache shutdown completed")
