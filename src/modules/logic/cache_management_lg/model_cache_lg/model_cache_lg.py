"""
Module: model_cache_lg
Description: Specialized cache for model metadata and parameters with memory optimization and persistence
Phase: 4
Location: /src/modules/logic/cache_management_lg/model_cache_lg/model_cache_lg.py
"""

# Standard library imports
import gzip
import json
import pickle
import threading
import time
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import weakref

# Local imports
from src.modules.logic.cache_management_lg.base_interfaces import (
    IModelCache,
    CacheEntry,
    CacheResult,
    CacheStats,
    CacheConfig,
    CacheStatus,
    CacheType,
    CacheLevel,
    ModelCacheEntry,
    EvictionPolicy,
    CacheHitEvent,
    CacheMissEvent,
    CacheEvictionEvent,
    ICacheEventListener
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class ModelMetadata:
    """Model metadata container."""
    
    def __init__(self, model_id: str, model_type: str, model_config: Dict[str, Any]):
        """Initialize model metadata."""
        self.model_id = model_id
        self.model_type = model_type
        self.model_config = model_config
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.access_count = 0
        self.load_time_ms = 0.0
        self.memory_usage_bytes = 0
        self.performance_metrics = {}
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'model_id': self.model_id,
            'model_type': self.model_type,
            'model_config': self.model_config,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'access_count': self.access_count,
            'load_time_ms': self.load_time_ms,
            'memory_usage_bytes': self.memory_usage_bytes,
            'performance_metrics': self.performance_metrics
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetadata':
        """Create from dictionary."""
        metadata = cls(
            model_id=data['model_id'],
            model_type=data['model_type'],
            model_config=data['model_config']
        )
        
        metadata.created_at = datetime.fromisoformat(data['created_at'])
        metadata.last_accessed = datetime.fromisoformat(data['last_accessed'])
        metadata.access_count = data['access_count']
        metadata.load_time_ms = data['load_time_ms']
        metadata.memory_usage_bytes = data['memory_usage_bytes']
        metadata.performance_metrics = data['performance_metrics']
        
        return metadata


class ModelCachePersistence:
    """Handles model cache persistence to disk."""
    
    def __init__(self, persistence_path: Path, compression_enabled: bool = True):
        """Initialize persistence manager."""
        self.persistence_path = persistence_path
        self.compression_enabled = compression_enabled
        self._logger = get_logger(__name__)
        
        # Ensure directory exists
        self.persistence_path.mkdir(parents=True, exist_ok=True)
        
        # Cache files
        self.metadata_file = self.persistence_path / "model_metadata.json.gz"
        self.cache_file = self.persistence_path / "model_cache.pkl.gz"
    
    def save_metadata(self, metadata_dict: Dict[str, ModelMetadata]) -> bool:
        """Save model metadata to disk."""
        try:
            # Convert metadata to serializable format
            serializable_data = {
                model_id: metadata.to_dict()
                for model_id, metadata in metadata_dict.items()
            }
            
            # Save with compression
            if self.compression_enabled:
                with gzip.open(self.metadata_file, 'wt', encoding='utf-8') as f:
                    json.dump(serializable_data, f, indent=2)
            else:
                with open(self.metadata_file.with_suffix('.json'), 'w', encoding='utf-8') as f:
                    json.dump(serializable_data, f, indent=2)
            
            self._logger.debug(f"Saved metadata for {len(metadata_dict)} models")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save model metadata: {e}")
            return False
    
    def load_metadata(self) -> Dict[str, ModelMetadata]:
        """Load model metadata from disk."""
        try:
            metadata_dict = {}
            
            # Try compressed file first
            if self.metadata_file.exists():
                with gzip.open(self.metadata_file, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            elif self.metadata_file.with_suffix('.json').exists():
                with open(self.metadata_file.with_suffix('.json'), 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                return {}
            
            # Convert back to ModelMetadata objects
            for model_id, metadata_data in data.items():
                metadata_dict[model_id] = ModelMetadata.from_dict(metadata_data)
            
            self._logger.debug(f"Loaded metadata for {len(metadata_dict)} models")
            return metadata_dict
            
        except Exception as e:
            self._logger.error(f"Failed to load model metadata: {e}")
            return {}
    
    def save_cache_entries(self, cache_entries: Dict[str, ModelCacheEntry]) -> bool:
        """Save cache entries to disk."""
        try:
            # Only save metadata, not the actual model objects
            serializable_entries = {}
            
            for key, entry in cache_entries.items():
                serializable_entries[key] = {
                    'key': entry.key,
                    'model_id': entry.model_id,
                    'model_type': entry.model_type,
                    'model_size_bytes': entry.model_size_bytes,
                    'model_path': str(entry.model_path) if entry.model_path else None,
                    'model_config': entry.model_config,
                    'load_time_ms': entry.load_time_ms,
                    'created_at': entry.created_at.isoformat(),
                    'last_accessed': entry.last_accessed.isoformat(),
                    'last_used': entry.last_used.isoformat() if entry.last_used else None,
                    'access_count': entry.access_count,
                    'ttl_seconds': entry.ttl_seconds,
                    'metadata': entry.metadata
                }
            
            # Save with compression
            if self.compression_enabled:
                with gzip.open(self.cache_file, 'wb') as f:
                    pickle.dump(serializable_entries, f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                with open(self.cache_file.with_suffix('.pkl'), 'wb') as f:
                    pickle.dump(serializable_entries, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            self._logger.debug(f"Saved {len(cache_entries)} cache entries")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save cache entries: {e}")
            return False
    
    def load_cache_entries(self) -> Dict[str, Dict[str, Any]]:
        """Load cache entries from disk."""
        try:
            # Try compressed file first
            if self.cache_file.exists():
                with gzip.open(self.cache_file, 'rb') as f:
                    data = pickle.load(f)
            elif self.cache_file.with_suffix('.pkl').exists():
                with open(self.cache_file.with_suffix('.pkl'), 'rb') as f:
                    data = pickle.load(f)
            else:
                return {}
            
            self._logger.debug(f"Loaded {len(data)} cache entries")
            return data
            
        except Exception as e:
            self._logger.error(f"Failed to load cache entries: {e}")
            return {}


class ModelCacheCore:
    """Core model cache implementation."""
    
    def __init__(self, config: CacheConfig):
        """Initialize model cache core."""
        self._config = config
        self._logger = get_logger(__name__)
        
        # Cache storage
        self._cache: OrderedDict[str, ModelCacheEntry] = OrderedDict()
        self._model_metadata: Dict[str, ModelMetadata] = {}
        self._models_by_type: Dict[str, Set[str]] = defaultdict(set)
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
        
        # Persistence
        self._persistence: Optional[ModelCachePersistence] = None
        if config.enable_persistence and config.persistence_path:
            self._persistence = ModelCachePersistence(
                config.persistence_path,
                config.compression_enabled
            )
            self._load_persisted_data()
        
        # Background maintenance
        self._maintenance_enabled = config.enable_background_cleanup
        self._maintenance_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        if self._maintenance_enabled:
            self._start_maintenance_thread()
        
        self._logger.info(f"Model cache core initialized with max_size={config.max_size_bytes} bytes")
    
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
    
    def get_model(self, model_id: str) -> Optional[ModelCacheEntry]:
        """Get model from cache."""
        start_time = time.time()
        
        with self._acquire_lock():
            if model_id in self._cache:
                entry = self._cache[model_id]
                
                # Check if expired
                if entry.is_expired:
                    self._remove_entry(model_id)
                    self._miss_count += 1
                    
                    access_time_ms = (time.time() - start_time) * 1000
                    self._total_access_time_ms += access_time_ms
                    
                    return None
                
                # Update access tracking
                entry.access()
                entry.last_used = datetime.now()
                
                # Update metadata
                if model_id in self._model_metadata:
                    metadata = self._model_metadata[model_id]
                    metadata.last_accessed = datetime.now()
                    metadata.access_count += 1
                
                # Move to end (most recently used)
                self._cache.move_to_end(model_id)
                
                self._hit_count += 1
                
                access_time_ms = (time.time() - start_time) * 1000
                self._total_access_time_ms += access_time_ms
                
                return entry
            else:
                self._miss_count += 1
                
                access_time_ms = (time.time() - start_time) * 1000
                self._total_access_time_ms += access_time_ms
                
                return None
    
    def put_model(self, model_id: str, model_entry: ModelCacheEntry) -> bool:
        """Store model in cache."""
        try:
            with self._acquire_lock():
                # Check if already exists
                if model_id in self._cache:
                    old_entry = self._cache[model_id]
                    self._current_size_bytes -= old_entry.size_bytes
                    
                    # Remove from type index
                    self._models_by_type[old_entry.model_type].discard(model_id)
                
                # Check if we need to evict entries
                if (self._current_size_bytes + model_entry.size_bytes > self._max_size_bytes or
                    len(self._cache) >= self._max_entries):
                    self._evict_entries(model_entry.size_bytes)
                
                # Add new entry
                self._cache[model_id] = model_entry
                self._current_size_bytes += model_entry.size_bytes
                
                # Add to type index
                self._models_by_type[model_entry.model_type].add(model_id)
                
                # Update metadata
                if model_id not in self._model_metadata:
                    self._model_metadata[model_id] = ModelMetadata(
                        model_id=model_entry.model_id,
                        model_type=model_entry.model_type,
                        model_config=model_entry.model_config
                    )
                
                metadata = self._model_metadata[model_id]
                metadata.last_accessed = datetime.now()
                metadata.load_time_ms = model_entry.load_time_ms
                metadata.memory_usage_bytes = model_entry.size_bytes
                
                # Move to end (most recently used)
                self._cache.move_to_end(model_id)
                
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to put model {model_id}: {e}")
            return False

    def get_models_by_type(self, model_type: str) -> List[ModelCacheEntry]:
        """Get all models of a specific type."""
        with self._acquire_lock():
            models = []
            model_ids = self._models_by_type.get(model_type, set())

            for model_id in model_ids:
                if model_id in self._cache:
                    entry = self._cache[model_id]
                    if not entry.is_expired:
                        models.append(entry)

            return models

    def evict(self, model_id: str) -> bool:
        """Remove model from cache."""
        with self._acquire_lock():
            if model_id in self._cache:
                self._remove_entry(model_id)
                return True
            return False

    def _remove_entry(self, model_id: str) -> None:
        """Remove entry and update tracking."""
        if model_id in self._cache:
            entry = self._cache[model_id]
            self._current_size_bytes -= entry.size_bytes

            # Remove from type index
            self._models_by_type[entry.model_type].discard(model_id)

            del self._cache[model_id]

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
        """Evict least recently used models."""
        evicted_count = 0

        while (self._current_size_bytes + needed_bytes > target_size and
               self._cache and
               evicted_count < self._config.eviction_batch_size):

            # Remove from beginning (least recently used)
            model_id, entry = self._cache.popitem(last=False)
            self._current_size_bytes -= entry.size_bytes
            self._models_by_type[entry.model_type].discard(model_id)
            self._eviction_count += 1
            evicted_count += 1

            self._logger.debug(f"Evicted LRU model: {model_id}")

    def _evict_lfu(self, target_size: float, needed_bytes: int) -> None:
        """Evict least frequently used models."""
        if not self._cache:
            return

        # Sort by access count
        entries_by_frequency = sorted(
            self._cache.items(),
            key=lambda x: x[1].access_count
        )

        evicted_count = 0

        for model_id, entry in entries_by_frequency:
            if (self._current_size_bytes + needed_bytes <= target_size or
                evicted_count >= self._config.eviction_batch_size):
                break

            self._remove_entry(model_id)
            self._eviction_count += 1
            evicted_count += 1

            self._logger.debug(f"Evicted LFU model: {model_id}")

    def _evict_expired(self) -> None:
        """Evict expired models."""
        expired_ids = []

        for model_id, entry in self._cache.items():
            if entry.is_expired:
                expired_ids.append(model_id)

        for model_id in expired_ids:
            self._remove_entry(model_id)
            self._eviction_count += 1
            self._logger.debug(f"Evicted expired model: {model_id}")

    def _evict_adaptive(self, target_size: float, needed_bytes: int) -> None:
        """Adaptive eviction based on model usage patterns."""
        # First evict expired models
        self._evict_expired()

        # If still need space, prioritize by model type and usage
        if self._current_size_bytes + needed_bytes > target_size:
            # Calculate model priorities (lower = evict first)
            model_priorities = []

            for model_id, entry in self._cache.items():
                # Priority based on: recency, frequency, model type importance
                recency_score = (datetime.now() - entry.last_accessed).total_seconds() / 3600  # Hours
                frequency_score = 1.0 / max(1, entry.access_count)

                # Model type importance (can be configured)
                type_importance = {
                    'embedding': 0.8,
                    'language': 0.9,
                    'classification': 0.7,
                    'generation': 0.9
                }.get(entry.model_type, 0.5)

                priority = recency_score + frequency_score - type_importance
                model_priorities.append((priority, model_id, entry))

            # Sort by priority (highest first = evict first)
            model_priorities.sort(reverse=True)

            evicted_count = 0
            for priority, model_id, entry in model_priorities:
                if (self._current_size_bytes + needed_bytes <= target_size or
                    evicted_count >= self._config.eviction_batch_size):
                    break

                self._remove_entry(model_id)
                self._eviction_count += 1
                evicted_count += 1

                self._logger.debug(f"Evicted adaptive model: {model_id} (priority: {priority:.2f})")

    def clear(self) -> bool:
        """Clear all models from cache."""
        with self._acquire_lock():
            self._cache.clear()
            self._model_metadata.clear()
            self._models_by_type.clear()
            self._current_size_bytes = 0
            return True

    def get_size(self) -> Tuple[int, int]:
        """Get cache size information."""
        with self._acquire_lock():
            return len(self._cache), self._current_size_bytes

    def contains(self, model_id: str) -> bool:
        """Check if model exists in cache."""
        with self._acquire_lock():
            return model_id in self._cache and not self._cache[model_id].is_expired

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._acquire_lock():
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0
            miss_rate = self._miss_count / total_requests if total_requests > 0 else 0.0
            avg_access_time = self._total_access_time_ms / total_requests if total_requests > 0 else 0.0
            memory_usage_percent = (self._current_size_bytes / self._max_size_bytes) * 100.0

            return CacheStats(
                cache_type=CacheType.MODEL,
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

    def _load_persisted_data(self) -> None:
        """Load persisted cache data."""
        if not self._persistence:
            return

        try:
            # Load metadata
            self._model_metadata = self._persistence.load_metadata()

            # Load cache entries (metadata only, not actual models)
            cache_data = self._persistence.load_cache_entries()

            # Rebuild type index from metadata
            for model_id, metadata in self._model_metadata.items():
                self._models_by_type[metadata.model_type].add(model_id)

            self._logger.info(f"Loaded {len(self._model_metadata)} model metadata entries")

        except Exception as e:
            self._logger.error(f"Failed to load persisted data: {e}")

    def _save_persisted_data(self) -> None:
        """Save cache data to disk."""
        if not self._persistence:
            return

        try:
            # Save metadata
            self._persistence.save_metadata(self._model_metadata)

            # Save cache entries
            self._persistence.save_cache_entries(self._cache)

            self._logger.debug("Saved cache data to disk")

        except Exception as e:
            self._logger.error(f"Failed to save cache data: {e}")

    def _start_maintenance_thread(self) -> None:
        """Start background maintenance thread."""
        def maintenance_worker():
            while not self._shutdown_event.wait(self._config.cleanup_interval_seconds):
                try:
                    # Clean up expired entries
                    self._evict_expired()

                    # Save to disk if persistence enabled
                    if self._persistence:
                        self._save_persisted_data()

                except Exception as e:
                    self._logger.error(f"Background maintenance error: {e}")

        self._maintenance_thread = threading.Thread(target=maintenance_worker, daemon=True)
        self._maintenance_thread.start()
        self._logger.info("Background maintenance thread started")

    def shutdown(self) -> None:
        """Shutdown cache and cleanup resources."""
        self._shutdown_event.set()
        if self._maintenance_thread and self._maintenance_thread.is_alive():
            self._maintenance_thread.join(timeout=5.0)

        # Save final state
        if self._persistence:
            self._save_persisted_data()

        self.clear()
        self._logger.info("Model cache core shutdown complete")


class ModelCache(IModelCache):
    """
    Specialized cache for model metadata and parameters with memory optimization and persistence.

    Features:
    - Model-specific caching with metadata tracking
    - Type-based model organization and retrieval
    - Persistent storage of model metadata
    - Memory-optimized storage (metadata only, not full models)
    - Performance metrics tracking per model
    - Adaptive eviction based on model usage patterns
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize model cache.

        Args:
            config: Cache configuration
        """
        self._config = config or CacheConfig()
        self._logger = get_logger(__name__)

        # Core cache implementation
        self._cache = ModelCacheCore(self._config)

        # Event listeners
        self._event_listeners: List[ICacheEventListener] = []

        # Performance tracking
        self._start_time = datetime.now()

        self._logger.info("ModelCache initialized successfully")

    def get(self, key: str) -> CacheResult:
        """
        Retrieve value from cache.

        Args:
            key: Cache key (model_id)

        Returns:
            CacheResult with model entry if found
        """
        if not key:
            return CacheResult(status=CacheStatus.ERROR, key=key)

        entry = self._cache.get_model(key)

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
            key: Cache key (model_id)
            value: ModelCacheEntry to store
            ttl_seconds: Optional time-to-live

        Returns:
            True if successfully stored
        """
        if not key or not isinstance(value, ModelCacheEntry):
            return False

        # Use config default TTL if not specified
        if ttl_seconds is None:
            ttl_seconds = self._config.default_ttl_seconds

        # Update TTL
        value.ttl_seconds = ttl_seconds

        return self._cache.put_model(key, value)

    def evict(self, key: str) -> bool:
        """
        Remove entry from cache.

        Args:
            key: Cache key (model_id)

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
            key: Cache key (model_id)

        Returns:
            True if key exists
        """
        if not key:
            return False

        return self._cache.contains(key)

    # Model-specific methods
    def get_model(self, model_id: str) -> Optional[ModelCacheEntry]:
        """
        Get model metadata from cache.

        Args:
            model_id: Model identifier

        Returns:
            ModelCacheEntry if found
        """
        return self._cache.get_model(model_id)

    def put_model(self, model_id: str, model_entry: ModelCacheEntry) -> bool:
        """
        Store model metadata in cache.

        Args:
            model_id: Model identifier
            model_entry: Model cache entry

        Returns:
            True if successfully stored
        """
        return self._cache.put_model(model_id, model_entry)

    def get_models_by_type(self, model_type: str) -> List[ModelCacheEntry]:
        """
        Get all models of a specific type.

        Args:
            model_type: Type of model

        Returns:
            List of model cache entries
        """
        return self._cache.get_models_by_type(model_type)

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
        event = CacheHitEvent(CacheType.MODEL, key, size_bytes)
        for listener in self._event_listeners:
            try:
                listener.on_cache_hit(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    def _fire_miss_event(self, key: str) -> None:
        """Fire cache miss event."""
        event = CacheMissEvent(CacheType.MODEL, key)
        for listener in self._event_listeners:
            try:
                listener.on_cache_miss(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    def _fire_eviction_event(self, key: str, reason: str) -> None:
        """Fire cache eviction event."""
        event = CacheEvictionEvent(CacheType.MODEL, key, reason)
        for listener in self._event_listeners:
            try:
                listener.on_cache_eviction(event)
            except Exception as e:
                self._logger.warning(f"Event listener error: {e}")

    # Advanced operations
    def get_model_types(self) -> List[str]:
        """Get all model types in cache."""
        return list(self._cache._models_by_type.keys())

    def get_model_count_by_type(self) -> Dict[str, int]:
        """Get model count by type."""
        return {
            model_type: len(model_ids)
            for model_type, model_ids in self._cache._models_by_type.items()
        }

    def get_cache_info(self) -> Dict[str, Any]:
        """Get comprehensive cache information."""
        stats = self.get_stats()
        uptime = (datetime.now() - self._start_time).total_seconds()

        return {
            'cache_type': 'model',
            'cache_level': 'L1_MEMORY',
            'uptime_seconds': uptime,
            'configuration': {
                'max_entries': self._config.max_entries,
                'max_size_bytes': self._config.max_size_bytes,
                'eviction_policy': self._config.eviction_policy.value,
                'enable_persistence': self._config.enable_persistence,
                'persistence_path': str(self._config.persistence_path) if self._config.persistence_path else None
            },
            'statistics': {
                'total_entries': stats.total_entries,
                'total_size_bytes': stats.total_size_bytes,
                'hit_rate': stats.hit_rate,
                'miss_rate': stats.miss_rate,
                'eviction_count': stats.eviction_count,
                'average_access_time_ms': stats.average_access_time_ms
            },
            'model_types': self.get_model_count_by_type(),
            'event_listeners': len(self._event_listeners)
        }

    def optimize(self) -> bool:
        """Optimize cache performance."""
        try:
            # Clean up expired entries
            self._cache._evict_expired()

            # Save to disk if persistence enabled
            if self._cache._persistence:
                self._cache._save_persisted_data()

            self._logger.info("Model cache optimization completed")
            return True

        except Exception as e:
            self._logger.error(f"Model cache optimization failed: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown cache and cleanup resources."""
        self._cache.shutdown()
        self._event_listeners.clear()
        self._logger.info("ModelCache shutdown complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()

    def __len__(self) -> int:
        """Get number of models in cache."""
        return self.get_size()[0]

    def __contains__(self, model_id: str) -> bool:
        """Check if model exists in cache."""
        return self.contains(model_id)
