"""
Module: memory_cache_lg
Description: In-memory caching for frequently accessed data with LRU eviction policy and thread-safe operations
Phase: 4
Location: /src/modules/logic/cache_management_lg/memory_cache_lg/memory_cache_lg.py
"""

# Standard library imports
import gc
import pickle
import threading
import time
import weakref
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import sys

# Local imports
from src.modules.logic.cache_management_lg.base_interfaces import (
    IMemoryCache,
    CacheEntry,
    CacheResult,
    CacheStats,
    CacheConfig,
    CacheStatus,
    CacheType,
    CacheLevel,
    EvictionPolicy,
    CacheEvent,
    CacheHitEvent,
    CacheMissEvent,
    CacheEvictionEvent,
    ICacheEventListener
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class MemoryCacheEntry(CacheEntry):
    """Memory cache entry with additional tracking."""
    
    def __init__(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Initialize memory cache entry."""
        now = datetime.now()
        
        # Calculate size
        size_bytes = self._calculate_size(value)
        
        super().__init__(
            key=key,
            value=value,
            size_bytes=size_bytes,
            created_at=now,
            last_accessed=now,
            ttl_seconds=ttl_seconds
        )
        
        # Memory-specific tracking
        self.memory_refs = weakref.WeakSet()
        self.access_frequency = 0.0
        self.last_frequency_update = now
    
    def _calculate_size(self, obj: Any) -> int:
        """Calculate approximate memory size of object."""
        try:
            # Try pickle size as approximation
            return len(pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception:
            # Fallback to sys.getsizeof
            return sys.getsizeof(obj)
    
    def update_frequency(self) -> None:
        """Update access frequency based on recent accesses."""
        now = datetime.now()
        time_delta = (now - self.last_frequency_update).total_seconds()
        
        if time_delta > 0:
            # Exponential decay of frequency
            decay_factor = max(0.1, 1.0 - (time_delta / 3600))  # 1 hour decay
            self.access_frequency = self.access_frequency * decay_factor + 1.0
            self.last_frequency_update = now
    
    def access(self) -> None:
        """Record access and update frequency."""
        super().access()
        self.update_frequency()


class LRUMemoryCache:
    """Core LRU memory cache implementation."""
    
    def __init__(self, config: CacheConfig):
        """Initialize LRU memory cache."""
        self._config = config
        self._logger = get_logger(__name__)
        
        # Cache storage
        self._cache: OrderedDict[str, MemoryCacheEntry] = OrderedDict()
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
        
        # Background cleanup
        self._cleanup_enabled = config.enable_background_cleanup
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        if self._cleanup_enabled:
            self._start_cleanup_thread()
        
        self._logger.info(f"LRU memory cache initialized with max_size={config.max_size_bytes} bytes")
    
    def _acquire_lock(self):
        """Acquire lock if thread safety is enabled."""
        if self._lock:
            return self._lock
        else:
            # Return a dummy context manager for non-thread-safe mode
            class DummyLock:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return DummyLock()
    
    def get(self, key: str) -> CacheResult:
        """Retrieve entry from cache."""
        start_time = time.time()
        
        with self._acquire_lock():
            if key in self._cache:
                entry = self._cache[key]
                
                # Check if expired
                if entry.is_expired:
                    self._remove_entry(key)
                    self._miss_count += 1
                    
                    access_time_ms = (time.time() - start_time) * 1000
                    self._total_access_time_ms += access_time_ms
                    
                    return CacheResult(
                        status=CacheStatus.EXPIRED,
                        key=key,
                        cache_level=CacheLevel.L1_MEMORY
                    )
                
                # Update access tracking
                entry.access()
                
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                
                self._hit_count += 1
                
                access_time_ms = (time.time() - start_time) * 1000
                self._total_access_time_ms += access_time_ms
                
                return CacheResult(
                    status=CacheStatus.HIT,
                    key=key,
                    value=entry.value,
                    size_bytes=entry.size_bytes,
                    hit_count=entry.access_count,
                    last_accessed=entry.last_accessed,
                    cache_level=CacheLevel.L1_MEMORY,
                    metadata=entry.metadata.copy()
                )
            else:
                self._miss_count += 1
                
                access_time_ms = (time.time() - start_time) * 1000
                self._total_access_time_ms += access_time_ms
                
                return CacheResult(
                    status=CacheStatus.MISS,
                    key=key,
                    cache_level=CacheLevel.L1_MEMORY
                )
    
    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Store entry in cache."""
        try:
            entry = MemoryCacheEntry(key, value, ttl_seconds)
            
            with self._acquire_lock():
                # Check if already exists
                if key in self._cache:
                    old_entry = self._cache[key]
                    self._current_size_bytes -= old_entry.size_bytes
                
                # Check if we need to evict entries
                if (self._current_size_bytes + entry.size_bytes > self._max_size_bytes or
                    len(self._cache) >= self._max_entries):
                    self._evict_entries(entry.size_bytes)
                
                # Add new entry
                self._cache[key] = entry
                self._current_size_bytes += entry.size_bytes
                
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to put entry {key}: {e}")
            return False
    
    def evict(self, key: str) -> bool:
        """Remove entry from cache."""
        with self._acquire_lock():
            if key in self._cache:
                self._remove_entry(key)
                return True
            return False
    
    def _remove_entry(self, key: str) -> None:
        """Remove entry and update size tracking."""
        if key in self._cache:
            entry = self._cache[key]
            self._current_size_bytes -= entry.size_bytes
            del self._cache[key]
    
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
        """Evict least recently used entries."""
        evicted_count = 0
        
        while (self._current_size_bytes + needed_bytes > target_size and 
               self._cache and 
               evicted_count < self._config.eviction_batch_size):
            
            # Remove from beginning (least recently used)
            key, entry = self._cache.popitem(last=False)
            self._current_size_bytes -= entry.size_bytes
            self._eviction_count += 1
            evicted_count += 1
            
            self._logger.debug(f"Evicted LRU entry: {key}")
    
    def _evict_lfu(self, target_size: float, needed_bytes: int) -> None:
        """Evict least frequently used entries."""
        if not self._cache:
            return
        
        # Sort by access frequency
        entries_by_frequency = sorted(
            self._cache.items(),
            key=lambda x: x[1].access_frequency
        )
        
        evicted_count = 0
        
        for key, entry in entries_by_frequency:
            if (self._current_size_bytes + needed_bytes <= target_size or
                evicted_count >= self._config.eviction_batch_size):
                break
            
            self._remove_entry(key)
            self._eviction_count += 1
            evicted_count += 1
            
            self._logger.debug(f"Evicted LFU entry: {key}")
    
    def _evict_expired(self) -> None:
        """Evict expired entries."""
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.is_expired:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_entry(key)
            self._eviction_count += 1
            self._logger.debug(f"Evicted expired entry: {key}")
    
    def _evict_adaptive(self, target_size: float, needed_bytes: int) -> None:
        """Adaptive eviction based on access patterns."""
        # First evict expired entries
        self._evict_expired()
        
        # If still need space, use LFU for frequently accessed items, LRU for others
        if self._current_size_bytes + needed_bytes > target_size:
            # Calculate average frequency
            if self._cache:
                avg_frequency = sum(entry.access_frequency for entry in self._cache.values()) / len(self._cache)
                
                # Separate high and low frequency entries
                low_freq_entries = [(k, v) for k, v in self._cache.items() if v.access_frequency < avg_frequency]
                
                # First evict low frequency entries using LRU
                low_freq_entries.sort(key=lambda x: x[1].last_accessed)
                
                evicted_count = 0
                for key, entry in low_freq_entries:
                    if (self._current_size_bytes + needed_bytes <= target_size or
                        evicted_count >= self._config.eviction_batch_size):
                        break
                    
                    self._remove_entry(key)
                    self._eviction_count += 1
                    evicted_count += 1
                    
                    self._logger.debug(f"Evicted adaptive entry: {key}")
    
    def clear(self) -> bool:
        """Clear all entries from cache."""
        with self._acquire_lock():
            self._cache.clear()
            self._current_size_bytes = 0
            return True
    
    def get_size(self) -> Tuple[int, int]:
        """Get cache size information."""
        with self._acquire_lock():
            return len(self._cache), self._current_size_bytes
    
    def contains(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self._acquire_lock():
            return key in self._cache and not self._cache[key].is_expired
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._acquire_lock():
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0
            miss_rate = self._miss_count / total_requests if total_requests > 0 else 0.0
            avg_access_time = self._total_access_time_ms / total_requests if total_requests > 0 else 0.0
            memory_usage_percent = (self._current_size_bytes / self._max_size_bytes) * 100.0
            
            return CacheStats(
                cache_type=CacheType.MEMORY,
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
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Get detailed memory usage information."""
        with self._acquire_lock():
            return {
                'total_entries': len(self._cache),
                'total_size_bytes': self._current_size_bytes,
                'max_size_bytes': self._max_size_bytes,
                'available_bytes': self._max_size_bytes - self._current_size_bytes,
                'usage_percent': int((self._current_size_bytes / self._max_size_bytes) * 100),
                'average_entry_size': self._current_size_bytes // len(self._cache) if self._cache else 0
            }
    
    def compact(self) -> bool:
        """Compact cache to reduce memory fragmentation."""
        try:
            with self._acquire_lock():
                # Force garbage collection
                gc.collect()
                
                # Rebuild cache to reduce fragmentation
                old_cache = self._cache.copy()
                self._cache.clear()
                self._current_size_bytes = 0
                
                # Re-add entries in access order
                for key, entry in old_cache.items():
                    if not entry.is_expired:
                        self._cache[key] = entry
                        self._current_size_bytes += entry.size_bytes
                
                self._logger.info(f"Cache compacted: {len(self._cache)} entries retained")
                return True
                
        except Exception as e:
            self._logger.error(f"Cache compaction failed: {e}")
            return False
    
    def _start_cleanup_thread(self) -> None:
        """Start background cleanup thread."""
        def cleanup_worker():
            while not self._shutdown_event.wait(self._config.cleanup_interval_seconds):
                try:
                    self._evict_expired()
                    
                    # Periodic compaction if memory usage is high
                    memory_usage = self.get_memory_usage()
                    if memory_usage['usage_percent'] > 80:
                        self.compact()
                        
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
        self._logger.info("Memory cache shutdown complete")


class MemoryCache(IMemoryCache):
    """
    High-performance in-memory cache with LRU eviction policy and thread-safe operations.

    Features:
    - Multiple eviction policies (LRU, LFU, TTL, Adaptive)
    - Thread-safe operations with configurable locking
    - Background cleanup and compaction
    - Detailed memory usage tracking
    - Event-driven architecture for monitoring
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize memory cache.

        Args:
            config: Cache configuration
        """
        self._config = config or CacheConfig()
        self._logger = get_logger(__name__)

        # Core cache implementation
        self._cache = LRUMemoryCache(self._config)

        # Event listeners
        self._event_listeners: List[ICacheEventListener] = []

        # Performance tracking
        self._start_time = datetime.now()

        self._logger.info("MemoryCache initialized successfully")

    def get(self, key: str) -> CacheResult:
        """
        Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            CacheResult with value if found
        """
        if not key:
            return CacheResult(status=CacheStatus.ERROR, key=key)

        result = self._cache.get(key)

        # Fire events
        if result.status == CacheStatus.HIT:
            self._fire_hit_event(key, result.size_bytes)
        else:
            self._fire_miss_event(key)

        return result

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
        if not key or value is None:
            return False

        # Use config default TTL if not specified
        if ttl_seconds is None:
            ttl_seconds = self._config.default_ttl_seconds

        return self._cache.put(key, value, ttl_seconds)

    def evict(self, key: str) -> bool:
        """
        Remove entry from cache.

        Args:
            key: Cache key

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
            key: Cache key

        Returns:
            True if key exists
        """
        if not key:
            return False

        return self._cache.contains(key)

    def get_memory_usage(self) -> Dict[str, int]:
        """
        Get detailed memory usage information.

        Returns:
            Dictionary with memory usage details
        """
        return self._cache.get_memory_usage()

    def compact(self) -> bool:
        """
        Compact cache to reduce memory fragmentation.

        Returns:
            True if compaction successful
        """
        return self._cache.compact()

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
        event = CacheHitEvent(CacheType.MEMORY, key, size_bytes)
        for listener in self._event_listeners:
            try:
                listener.on_cache_hit(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    def _fire_miss_event(self, key: str) -> None:
        """Fire cache miss event."""
        event = CacheMissEvent(CacheType.MEMORY, key)
        for listener in self._event_listeners:
            try:
                listener.on_cache_miss(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    def _fire_eviction_event(self, key: str, reason: str) -> None:
        """Fire cache eviction event."""
        event = CacheEvictionEvent(CacheType.MEMORY, key, reason)
        for listener in self._event_listeners:
            try:
                listener.on_cache_eviction(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    # Advanced operations
    def get_keys(self) -> List[str]:
        """Get all cache keys."""
        with self._cache._acquire_lock():
            return list(self._cache._cache.keys())

    def get_entries_by_pattern(self, pattern: str) -> Dict[str, Any]:
        """Get entries matching pattern."""
        import re

        regex = re.compile(pattern)
        matching_entries = {}

        with self._cache._acquire_lock():
            for key, entry in self._cache._cache.items():
                if regex.match(key) and not entry.is_expired:
                    matching_entries[key] = entry.value

        return matching_entries

    def get_cache_info(self) -> Dict[str, Any]:
        """Get comprehensive cache information."""
        stats = self.get_stats()
        memory_usage = self.get_memory_usage()
        uptime = (datetime.now() - self._start_time).total_seconds()

        return {
            'cache_type': 'memory',
            'cache_level': 'L1_MEMORY',
            'uptime_seconds': uptime,
            'configuration': {
                'max_entries': self._config.max_entries,
                'max_size_bytes': self._config.max_size_bytes,
                'eviction_policy': self._config.eviction_policy.value,
                'thread_safe': self._config.thread_safe,
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
            'memory_usage': memory_usage,
            'event_listeners': len(self._event_listeners)
        }

    def optimize(self) -> bool:
        """Optimize cache performance."""
        try:
            # Compact cache
            self.compact()

            # Clean up expired entries
            self._cache._evict_expired()

            # Force garbage collection
            import gc
            gc.collect()

            self._logger.info("Cache optimization completed")
            return True

        except Exception as e:
            self._logger.error(f"Cache optimization failed: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown cache and cleanup resources."""
        self._cache.shutdown()
        self._event_listeners.clear()
        self._logger.info("MemoryCache shutdown complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()

    def __len__(self) -> int:
        """Get number of entries in cache."""
        return self.get_size()[0]

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache."""
        return self.contains(key)

    def __getitem__(self, key: str) -> Any:
        """Get item from cache."""
        result = self.get(key)
        if result.status == CacheStatus.HIT:
            return result.value
        raise KeyError(f"Key '{key}' not found in cache")

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item in cache."""
        self.put(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete item from cache."""
        if not self.evict(key):
            raise KeyError(f"Key '{key}' not found in cache")
