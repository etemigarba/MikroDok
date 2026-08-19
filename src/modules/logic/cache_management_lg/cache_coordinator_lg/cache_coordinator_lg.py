"""
Module: cache_coordinator_lg
Description: Coordinates between different cache types and manages global cache policies
Phase: 4
Location: /src/modules/logic/cache_management_lg/cache_coordinator_lg/cache_coordinator_lg.py
"""

# Standard library imports
import asyncio
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import weakref

# Local imports
from src.modules.logic.cache_management_lg.base_interfaces import (
    ICacheManager,
    ICache,
    CacheType,
    CacheLevel,
    CacheStats,
    CacheConfig,
    CacheStatus,
    CacheResult,
    CacheEvent,
    CacheHitEvent,
    CacheMissEvent,
    CacheEvictionEvent,
    ICacheEventListener,
    CacheMetrics
)
from src.modules.logic.cache_management_lg.memory_cache_lg.memory_cache_lg import MemoryCache
from src.modules.logic.cache_management_lg.model_cache_lg.model_cache_lg import ModelCache
from src.modules.logic.cache_management_lg.embedding_cache_lg.embedding_cache_lg import EmbeddingCache
from src.modules.logic.logging_infrastructure_lg import get_logger


class CachePolicy:
    """Defines cache management policies."""
    
    def __init__(self):
        """Initialize cache policy."""
        # Memory management
        self.global_memory_limit_bytes = 4 * 1024 * 1024 * 1024  # 4GB
        self.memory_pressure_threshold = 0.85  # 85%
        self.emergency_cleanup_threshold = 0.95  # 95%
        
        # Cache priorities (higher = more important)
        self.cache_priorities = {
            CacheType.EMBEDDING: 10,
            CacheType.MODEL: 8,
            CacheType.MEMORY: 6,
            CacheType.QUERY: 4,
            CacheType.RESULT: 2
        }
        
        # Eviction policies per cache type
        self.eviction_policies = {
            CacheType.EMBEDDING: "adaptive",
            CacheType.MODEL: "lfu",
            CacheType.MEMORY: "lru",
            CacheType.QUERY: "ttl",
            CacheType.RESULT: "fifo"
        }
        
        # Optimization settings
        self.optimization_interval_seconds = 300  # 5 minutes
        self.stats_collection_interval_seconds = 60  # 1 minute
        self.cleanup_interval_seconds = 180  # 3 minutes
        
        # Performance thresholds
        self.min_hit_rate_threshold = 0.7
        self.max_miss_rate_threshold = 0.3
        self.max_average_access_time_ms = 10.0


class CacheCoordinatorEventListener(ICacheEventListener):
    """Event listener for cache coordination."""
    
    def __init__(self, coordinator_ref: weakref.ref):
        """Initialize event listener."""
        self.coordinator_ref = coordinator_ref
        self._logger = get_logger(__name__)
    
    def on_cache_hit(self, event: CacheHitEvent) -> None:
        """Handle cache hit event."""
        coordinator = self.coordinator_ref()
        if coordinator:
            coordinator._record_cache_event(event)
    
    def on_cache_miss(self, event: CacheMissEvent) -> None:
        """Handle cache miss event."""
        coordinator = self.coordinator_ref()
        if coordinator:
            coordinator._record_cache_event(event)
    
    def on_cache_eviction(self, event: CacheEvictionEvent) -> None:
        """Handle cache eviction event."""
        coordinator = self.coordinator_ref()
        if coordinator:
            coordinator._record_cache_event(event)


class CacheCoordinatorCore:
    """Core cache coordination implementation."""
    
    def __init__(self, policy: CachePolicy):
        """Initialize cache coordinator core."""
        self.policy = policy
        self._logger = get_logger(__name__)
        
        # Cache registry
        self._caches: Dict[CacheType, ICache] = {}
        self._cache_configs: Dict[CacheType, CacheConfig] = {}
        self._lock = threading.RLock()
        
        # Event handling
        self._event_listener = CacheCoordinatorEventListener(weakref.ref(self))
        self._global_metrics = CacheMetrics()
        
        # Performance tracking
        self._cache_events: Dict[CacheType, List[CacheEvent]] = defaultdict(list)
        self._performance_history: Dict[CacheType, List[CacheStats]] = defaultdict(list)
        
        # Background tasks
        self._optimization_enabled = True
        self._optimization_task: Optional[asyncio.Task] = None
        self._stats_collection_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        self._logger.info("Cache coordinator core initialized")
    
    def register_cache(self, cache_type: CacheType, cache: ICache, config: CacheConfig) -> bool:
        """Register a cache instance."""
        try:
            with self._lock:
                if cache_type in self._caches:
                    self._logger.warning(f"Cache type {cache_type} already registered, replacing")
                
                self._caches[cache_type] = cache
                self._cache_configs[cache_type] = config
                
                # Add event listener if supported
                if hasattr(cache, 'add_event_listener'):
                    cache.add_event_listener(self._event_listener)
                
                self._logger.info(f"Registered cache: {cache_type}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to register cache {cache_type}: {e}")
            return False
    
    def unregister_cache(self, cache_type: CacheType) -> bool:
        """Unregister a cache instance."""
        try:
            with self._lock:
                if cache_type not in self._caches:
                    return False
                
                cache = self._caches[cache_type]
                
                # Remove event listener if supported
                if hasattr(cache, 'remove_event_listener'):
                    cache.remove_event_listener(self._event_listener)
                
                del self._caches[cache_type]
                del self._cache_configs[cache_type]
                
                # Clean up tracking data
                if cache_type in self._cache_events:
                    del self._cache_events[cache_type]
                if cache_type in self._performance_history:
                    del self._performance_history[cache_type]
                
                self._logger.info(f"Unregistered cache: {cache_type}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to unregister cache {cache_type}: {e}")
            return False
    
    def get_cache(self, cache_type: CacheType) -> Optional[ICache]:
        """Get cache instance by type."""
        with self._lock:
            return self._caches.get(cache_type)
    
    def clear_all_caches(self) -> bool:
        """Clear all registered caches."""
        try:
            with self._lock:
                for cache_type, cache in self._caches.items():
                    try:
                        cache.clear()
                        self._logger.debug(f"Cleared cache: {cache_type}")
                    except Exception as e:
                        self._logger.error(f"Failed to clear cache {cache_type}: {e}")
                
                # Clear tracking data
                self._cache_events.clear()
                self._performance_history.clear()
                
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to clear all caches: {e}")
            return False
    
    def get_global_stats(self) -> Dict[CacheType, CacheStats]:
        """Get statistics for all caches."""
        stats = {}
        
        with self._lock:
            for cache_type, cache in self._caches.items():
                try:
                    stats[cache_type] = cache.get_stats()
                except Exception as e:
                    self._logger.error(f"Failed to get stats for cache {cache_type}: {e}")
        
        return stats
    
    def get_global_memory_usage(self) -> Dict[str, Any]:
        """Get global memory usage across all caches."""
        total_memory_bytes = 0
        cache_memory_usage = {}
        
        with self._lock:
            for cache_type, cache in self._caches.items():
                try:
                    _, memory_bytes = cache.get_size()
                    cache_memory_usage[cache_type.value] = memory_bytes
                    total_memory_bytes += memory_bytes
                except Exception as e:
                    self._logger.error(f"Failed to get memory usage for cache {cache_type}: {e}")
                    cache_memory_usage[cache_type.value] = 0
        
        memory_usage_percent = (total_memory_bytes / self.policy.global_memory_limit_bytes) * 100.0
        
        return {
            'total_memory_bytes': total_memory_bytes,
            'memory_limit_bytes': self.policy.global_memory_limit_bytes,
            'memory_usage_percent': memory_usage_percent,
            'cache_memory_usage': cache_memory_usage,
            'memory_pressure': memory_usage_percent > self.policy.memory_pressure_threshold * 100,
            'emergency_cleanup_needed': memory_usage_percent > self.policy.emergency_cleanup_threshold * 100
        }
    
    def optimize_caches(self) -> bool:
        """Trigger optimization for all caches."""
        try:
            memory_usage = self.get_global_memory_usage()
            
            # Check if memory pressure requires action
            if memory_usage['memory_pressure']:
                self._handle_memory_pressure(memory_usage)
            
            # Optimize individual caches
            with self._lock:
                for cache_type, cache in self._caches.items():
                    try:
                        if hasattr(cache, 'optimize'):
                            cache.optimize()
                        self._logger.debug(f"Optimized cache: {cache_type}")
                    except Exception as e:
                        self._logger.error(f"Failed to optimize cache {cache_type}: {e}")
            
            return True
            
        except Exception as e:
            self._logger.error(f"Cache optimization failed: {e}")
            return False
    
    def _handle_memory_pressure(self, memory_usage: Dict[str, Any]) -> None:
        """Handle memory pressure by evicting from lower priority caches."""
        if memory_usage['emergency_cleanup_needed']:
            self._logger.warning("Emergency memory cleanup triggered")
            
            # Sort caches by priority (lowest first for eviction)
            cache_priorities = sorted(
                self._caches.items(),
                key=lambda x: self.policy.cache_priorities.get(x[0], 0)
            )
            
            # Evict from lower priority caches first
            for cache_type, cache in cache_priorities:
                try:
                    # Get current memory usage
                    current_usage = self.get_global_memory_usage()
                    if current_usage['memory_usage_percent'] < self.policy.memory_pressure_threshold * 100:
                        break
                    
                    # Evict some entries
                    if hasattr(cache, '_cache') and hasattr(cache._cache, '_evict_entries'):
                        cache._cache._evict_entries()
                        self._logger.info(f"Emergency eviction from cache: {cache_type}")
                    
                except Exception as e:
                    self._logger.error(f"Emergency eviction failed for cache {cache_type}: {e}")
    
    def _record_cache_event(self, event: CacheEvent) -> None:
        """Record cache event for analysis."""
        try:
            # Record in global metrics
            if isinstance(event, CacheHitEvent):
                self._global_metrics.record_hit(event.cache_type, event.key, event.size_bytes)
            elif isinstance(event, CacheMissEvent):
                self._global_metrics.record_miss(event.cache_type, event.key)
            elif isinstance(event, CacheEvictionEvent):
                self._global_metrics.record_eviction(event.cache_type, event.key, 0)
            
            # Store event for analysis (keep last 1000 events per cache)
            events_list = self._cache_events[event.cache_type]
            events_list.append(event)
            if len(events_list) > 1000:
                events_list.pop(0)
                
        except Exception as e:
            self._logger.error(f"Failed to record cache event: {e}")
    
    async def start_background_tasks(self) -> None:
        """Start background optimization and monitoring tasks."""
        try:
            # Start optimization task
            self._optimization_task = asyncio.create_task(self._optimization_worker())
            
            # Start stats collection task
            self._stats_collection_task = asyncio.create_task(self._stats_collection_worker())
            
            # Start cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_worker())
            
            self._logger.info("Background tasks started")
            
        except Exception as e:
            self._logger.error(f"Failed to start background tasks: {e}")
    
    async def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        try:
            self._shutdown_event.set()
            
            # Cancel tasks
            tasks = [self._optimization_task, self._stats_collection_task, self._cleanup_task]
            for task in tasks:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            self._logger.info("Background tasks stopped")
            
        except Exception as e:
            self._logger.error(f"Failed to stop background tasks: {e}")
    
    async def _optimization_worker(self) -> None:
        """Background optimization worker."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.policy.optimization_interval_seconds)
                
                if not self._shutdown_event.is_set():
                    self.optimize_caches()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Optimization worker error: {e}")
    
    async def _stats_collection_worker(self) -> None:
        """Background stats collection worker."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.policy.stats_collection_interval_seconds)
                
                if not self._shutdown_event.is_set():
                    # Collect stats from all caches
                    stats = self.get_global_stats()
                    
                    # Store in history (keep last 100 entries per cache)
                    for cache_type, cache_stats in stats.items():
                        history = self._performance_history[cache_type]
                        history.append(cache_stats)
                        if len(history) > 100:
                            history.pop(0)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Stats collection worker error: {e}")
    
    async def _cleanup_worker(self) -> None:
        """Background cleanup worker."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.policy.cleanup_interval_seconds)
                
                if not self._shutdown_event.is_set():
                    # Clean up old events and stats
                    cutoff_time = datetime.now() - timedelta(hours=1)
                    
                    for cache_type in list(self._cache_events.keys()):
                        events = self._cache_events[cache_type]
                        self._cache_events[cache_type] = [
                            event for event in events
                            if event.timestamp > cutoff_time
                        ]
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Cleanup worker error: {e}")
    
    def shutdown(self) -> None:
        """Shutdown coordinator and cleanup resources."""
        # Stop background tasks
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(self.stop_background_tasks())
        
        # Shutdown all caches
        with self._lock:
            for cache_type, cache in self._caches.items():
                try:
                    if hasattr(cache, 'shutdown'):
                        cache.shutdown()
                except Exception as e:
                    self._logger.error(f"Failed to shutdown cache {cache_type}: {e}")
        
        self._logger.info("Cache coordinator core shutdown complete")


class CacheCoordinator(ICacheManager):
    """
    Coordinates between different cache types and manages global cache policies.

    Features:
    - Multi-cache coordination and management
    - Global memory pressure handling
    - Performance monitoring and optimization
    - Event-driven cache coordination
    - Background optimization and cleanup
    - Configurable cache policies and priorities
    """

    def __init__(self, policy: Optional[CachePolicy] = None):
        """
        Initialize cache coordinator.

        Args:
            policy: Cache management policy
        """
        self._policy = policy or CachePolicy()
        self._logger = get_logger(__name__)

        # Core coordinator
        self._coordinator = CacheCoordinatorCore(self._policy)

        # Auto-create default caches
        self._auto_create_caches = True
        self._default_caches_created = False

        # Performance tracking
        self._start_time = datetime.now()

        self._logger.info("CacheCoordinator initialized successfully")

    def register_cache(self, cache_type: CacheType, cache: ICache) -> bool:
        """
        Register a cache instance.

        Args:
            cache_type: Type of cache
            cache: Cache instance

        Returns:
            True if successfully registered
        """
        # Create default config if cache doesn't have one
        if hasattr(cache, '_config'):
            config = cache._config
        else:
            config = CacheConfig()

        return self._coordinator.register_cache(cache_type, cache, config)

    def unregister_cache(self, cache_type: CacheType) -> bool:
        """
        Unregister a cache instance.

        Args:
            cache_type: Type of cache

        Returns:
            True if successfully unregistered
        """
        return self._coordinator.unregister_cache(cache_type)

    def get_cache(self, cache_type: CacheType) -> Optional[ICache]:
        """
        Get cache instance by type.

        Args:
            cache_type: Type of cache

        Returns:
            Cache instance if found
        """
        # Auto-create default caches if enabled
        if self._auto_create_caches and not self._default_caches_created:
            self._create_default_caches()

        return self._coordinator.get_cache(cache_type)

    def clear_all_caches(self) -> bool:
        """
        Clear all registered caches.

        Returns:
            True if all caches cleared successfully
        """
        return self._coordinator.clear_all_caches()

    def get_global_stats(self) -> Dict[CacheType, CacheStats]:
        """
        Get statistics for all caches.

        Returns:
            Dictionary mapping cache types to their stats
        """
        return self._coordinator.get_global_stats()

    def optimize_caches(self) -> bool:
        """
        Trigger optimization for all caches.

        Returns:
            True if optimization completed successfully
        """
        return self._coordinator.optimize_caches()

    # Extended functionality
    def get_global_memory_usage(self) -> Dict[str, Any]:
        """Get global memory usage across all caches."""
        return self._coordinator.get_global_memory_usage()

    def get_cache_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        stats = self.get_global_stats()
        memory_usage = self.get_global_memory_usage()
        uptime = (datetime.now() - self._start_time).total_seconds()

        # Calculate aggregate metrics
        total_entries = sum(stat.total_entries for stat in stats.values())
        total_hits = sum(stat.hit_count for stat in stats.values())
        total_misses = sum(stat.miss_count for stat in stats.values())
        total_requests = total_hits + total_misses

        global_hit_rate = total_hits / total_requests if total_requests > 0 else 0.0
        global_miss_rate = total_misses / total_requests if total_requests > 0 else 0.0

        avg_access_time = sum(
            stat.average_access_time_ms * (stat.hit_count + stat.miss_count)
            for stat in stats.values()
        ) / total_requests if total_requests > 0 else 0.0

        return {
            'coordinator_info': {
                'uptime_seconds': uptime,
                'registered_caches': len(stats),
                'policy': {
                    'global_memory_limit_bytes': self._policy.global_memory_limit_bytes,
                    'memory_pressure_threshold': self._policy.memory_pressure_threshold,
                    'optimization_interval_seconds': self._policy.optimization_interval_seconds
                }
            },
            'global_performance': {
                'total_entries': total_entries,
                'total_requests': total_requests,
                'global_hit_rate': global_hit_rate,
                'global_miss_rate': global_miss_rate,
                'average_access_time_ms': avg_access_time
            },
            'memory_usage': memory_usage,
            'cache_stats': {cache_type.value: stat for cache_type, stat in stats.items()},
            'performance_alerts': self._get_performance_alerts(stats, memory_usage)
        }

    def _get_performance_alerts(self, stats: Dict[CacheType, CacheStats],
                               memory_usage: Dict[str, Any]) -> List[str]:
        """Get performance alerts based on thresholds."""
        alerts = []

        # Memory pressure alerts
        if memory_usage['emergency_cleanup_needed']:
            alerts.append("CRITICAL: Emergency memory cleanup needed")
        elif memory_usage['memory_pressure']:
            alerts.append("WARNING: Memory pressure detected")

        # Performance alerts
        for cache_type, stat in stats.items():
            if stat.hit_rate < self._policy.min_hit_rate_threshold:
                alerts.append(f"WARNING: Low hit rate for {cache_type.value}: {stat.hit_rate:.2f}")

            if stat.miss_rate > self._policy.max_miss_rate_threshold:
                alerts.append(f"WARNING: High miss rate for {cache_type.value}: {stat.miss_rate:.2f}")

            if stat.average_access_time_ms > self._policy.max_average_access_time_ms:
                alerts.append(f"WARNING: Slow access time for {cache_type.value}: {stat.average_access_time_ms:.2f}ms")

        return alerts

    def _create_default_caches(self) -> None:
        """Create default cache instances."""
        try:
            # Create memory cache
            memory_config = CacheConfig(
                max_entries=10000,
                max_size_bytes=512 * 1024 * 1024,  # 512MB
                eviction_policy=EvictionPolicy.LRU
            )
            memory_cache = MemoryCache(memory_config)
            self.register_cache(CacheType.MEMORY, memory_cache)

            # Create model cache
            model_config = CacheConfig(
                max_entries=1000,
                max_size_bytes=1024 * 1024 * 1024,  # 1GB
                eviction_policy=EvictionPolicy.LFU,
                enable_persistence=True,
                persistence_path=Path("./cache/models")
            )
            model_cache = ModelCache(model_config)
            self.register_cache(CacheType.MODEL, model_cache)

            # Create embedding cache
            embedding_config = CacheConfig(
                max_entries=50000,
                max_size_bytes=2 * 1024 * 1024 * 1024,  # 2GB
                eviction_policy=EvictionPolicy.ADAPTIVE,
                compression_enabled=True
            )
            embedding_cache = EmbeddingCache(embedding_config)
            self.register_cache(CacheType.EMBEDDING, embedding_cache)

            self._default_caches_created = True
            self._logger.info("Default caches created successfully")

        except Exception as e:
            self._logger.error(f"Failed to create default caches: {e}")

    async def start_background_optimization(self) -> None:
        """Start background optimization tasks."""
        await self._coordinator.start_background_tasks()

    async def stop_background_optimization(self) -> None:
        """Stop background optimization tasks."""
        await self._coordinator.stop_background_tasks()

    def get_cache_events(self, cache_type: Optional[CacheType] = None) -> Dict[CacheType, List[CacheEvent]]:
        """Get recent cache events."""
        if cache_type:
            return {cache_type: self._coordinator._cache_events.get(cache_type, [])}
        else:
            return dict(self._coordinator._cache_events)

    def get_performance_history(self, cache_type: Optional[CacheType] = None) -> Dict[CacheType, List[CacheStats]]:
        """Get performance history."""
        if cache_type:
            return {cache_type: self._coordinator._performance_history.get(cache_type, [])}
        else:
            return dict(self._coordinator._performance_history)

    def force_memory_cleanup(self) -> bool:
        """Force memory cleanup across all caches."""
        try:
            memory_usage = self.get_global_memory_usage()
            self._coordinator._handle_memory_pressure(memory_usage)
            return True
        except Exception as e:
            self._logger.error(f"Force memory cleanup failed: {e}")
            return False

    def update_policy(self, policy: CachePolicy) -> None:
        """Update cache management policy."""
        self._policy = policy
        self._coordinator.policy = policy
        self._logger.info("Cache policy updated")

    def shutdown(self) -> None:
        """Shutdown coordinator and all caches."""
        self._coordinator.shutdown()
        self._logger.info("CacheCoordinator shutdown complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()

    # Convenience methods for direct cache access
    def get_memory_cache(self) -> Optional[MemoryCache]:
        """Get memory cache instance."""
        return self.get_cache(CacheType.MEMORY)

    def get_model_cache(self) -> Optional[ModelCache]:
        """Get model cache instance."""
        return self.get_cache(CacheType.MODEL)

    def get_embedding_cache(self) -> Optional[EmbeddingCache]:
        """Get embedding cache instance."""
        return self.get_cache(CacheType.EMBEDDING)
