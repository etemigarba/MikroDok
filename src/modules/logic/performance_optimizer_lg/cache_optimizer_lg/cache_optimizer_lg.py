"""
Module: cache_optimizer_lg
Description: Manages cache eviction policies and prefetching strategies based on access patterns and available memory
Phase: 2
Location: /src/modules/logic/performance_optimizer_lg/cache_optimizer_lg/
"""

# Standard library imports
import asyncio
import heapq
import logging
import statistics
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from collections import defaultdict, deque, OrderedDict
import weakref

# Local imports
from src.modules.logic.resource_monitor_lg import MemoryMetrics
from src.modules.logic.logging_infrastructure_lg import get_logger


class EvictionPolicy(Enum):
    """Cache eviction policies."""
    LRU = "LRU"  # Least Recently Used
    LFU = "LFU"  # Least Frequently Used
    FIFO = "FIFO"  # First In, First Out
    RANDOM = "RANDOM"  # Random eviction
    TTL = "TTL"  # Time To Live
    SIZE_BASED = "SIZE_BASED"  # Based on item size
    ADAPTIVE = "ADAPTIVE"  # Adaptive based on access patterns
    MEMORY_PRESSURE = "MEMORY_PRESSURE"  # Based on memory pressure


class PrefetchStrategy(Enum):
    """Cache prefetching strategies."""
    NONE = "NONE"
    SEQUENTIAL = "SEQUENTIAL"
    PATTERN_BASED = "PATTERN_BASED"
    FREQUENCY_BASED = "FREQUENCY_BASED"
    PREDICTIVE = "PREDICTIVE"
    LOCALITY_AWARE = "LOCALITY_AWARE"
    ADAPTIVE = "ADAPTIVE"


class CacheLevel(Enum):
    """Cache hierarchy levels."""
    L1_MEMORY = "L1_MEMORY"
    L2_MEMORY = "L2_MEMORY"
    L3_DISK_CACHE = "L3_DISK_CACHE"
    NVME_CACHE = "NVME_CACHE"
    SSD_CACHE = "SSD_CACHE"


@dataclass
class AccessPattern:
    """Represents cache access patterns."""
    key: str
    access_count: int
    last_access_time: datetime
    access_frequency: float  # Accesses per minute
    sequential_score: float  # 0.0 to 1.0
    locality_score: float  # 0.0 to 1.0
    size_bytes: int
    access_times: deque = field(default_factory=lambda: deque(maxlen=100))


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    timestamp: datetime
    cache_level: CacheLevel
    hit_rate: float
    miss_rate: float
    eviction_rate: float
    memory_usage_bytes: int
    memory_usage_percent: float
    average_access_time_ms: float
    prefetch_accuracy: float
    cache_efficiency: float


@dataclass
class CacheOptimizationResult:
    """Result of cache optimization."""
    timestamp: datetime
    optimization_type: str
    cache_level: CacheLevel
    items_evicted: int
    items_prefetched: int
    memory_freed_bytes: int
    performance_improvement_percent: float
    new_hit_rate: float
    optimization_time_ms: float


@dataclass
class CacheConfiguration:
    """Configuration for cache optimization."""
    # Size limits
    max_memory_usage_bytes: int = 1024 * 1024 * 1024  # 1GB
    max_memory_usage_percent: float = 80.0
    min_free_memory_bytes: int = 256 * 1024 * 1024  # 256MB
    
    # Eviction settings
    default_eviction_policy: EvictionPolicy = EvictionPolicy.ADAPTIVE
    eviction_batch_size: int = 100
    eviction_threshold_percent: float = 90.0
    
    # Prefetch settings
    default_prefetch_strategy: PrefetchStrategy = PrefetchStrategy.PATTERN_BASED
    prefetch_window_size: int = 10
    prefetch_confidence_threshold: float = 0.7
    max_prefetch_items: int = 50
    
    # Optimization settings
    optimization_interval_seconds: float = 30.0
    pattern_analysis_window_minutes: int = 15
    enable_adaptive_policies: bool = True
    enable_predictive_prefetch: bool = True
    
    # Performance settings
    access_tracking_window_size: int = 1000
    metrics_retention_minutes: int = 60


class ICacheOptimizer(ABC):
    """Interface for cache optimization systems."""
    
    @abstractmethod
    async def optimize_cache(self, cache_level: CacheLevel, 
                           memory_metrics: MemoryMetrics) -> CacheOptimizationResult:
        """Optimize cache for a specific level."""
        pass
    
    @abstractmethod
    def record_access(self, cache_level: CacheLevel, key: str, 
                     hit: bool, size_bytes: int) -> None:
        """Record a cache access for pattern analysis."""
        pass
    
    @abstractmethod
    def get_eviction_candidates(self, cache_level: CacheLevel, 
                               target_bytes: int) -> List[str]:
        """Get candidates for cache eviction."""
        pass
    
    @abstractmethod
    def get_prefetch_candidates(self, cache_level: CacheLevel, 
                               current_key: str) -> List[str]:
        """Get candidates for cache prefetching."""
        pass
    
    @abstractmethod
    async def start_optimization(self) -> None:
        """Start continuous cache optimization."""
        pass
    
    @abstractmethod
    async def stop_optimization(self) -> None:
        """Stop continuous cache optimization."""
        pass


class CacheOptimizer(ICacheOptimizer):
    """
    Manages cache eviction policies and prefetching strategies based on access patterns and available memory.
    
    This class analyzes cache access patterns and optimizes cache behavior to maximize
    hit rates while respecting memory constraints.
    """
    
    def __init__(self, config: Optional[CacheConfiguration] = None):
        """
        Initialize the cache optimizer.
        
        Args:
            config: Configuration for cache optimization behavior
        """
        self._config = config or CacheConfiguration()
        self._logger = get_logger(__name__)
        
        # Optimization state
        self._optimization_active = False
        self._optimization_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        
        # Access pattern tracking
        self._access_patterns: Dict[CacheLevel, Dict[str, AccessPattern]] = defaultdict(dict)
        self._access_history: Dict[CacheLevel, deque] = defaultdict(lambda: deque(maxlen=self._config.access_tracking_window_size))
        
        # Cache metrics
        self._cache_metrics: Dict[CacheLevel, deque] = defaultdict(lambda: deque(maxlen=100))
        self._current_metrics: Dict[CacheLevel, CacheMetrics] = {}
        
        # Optimization tracking
        self._optimization_history: deque = deque(maxlen=100)
        self._eviction_policies: Dict[CacheLevel, EvictionPolicy] = {}
        self._prefetch_strategies: Dict[CacheLevel, PrefetchStrategy] = {}
        
        # Pattern analysis
        self._sequential_patterns: Dict[CacheLevel, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        self._frequency_patterns: Dict[CacheLevel, Dict[str, float]] = defaultdict(dict)
        self._locality_groups: Dict[CacheLevel, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        
        # Performance tracking
        self._hit_rates: Dict[CacheLevel, deque] = defaultdict(lambda: deque(maxlen=50))
        self._optimization_times: deque = deque(maxlen=50)
        
        # Initialize default policies
        self._initialize_default_policies()
        
        self._logger.info("Cache optimizer initialized")
    
    async def optimize_cache(self, cache_level: CacheLevel, 
                           memory_metrics: MemoryMetrics) -> CacheOptimizationResult:
        """Optimize cache for a specific level."""
        start_time = time.time()
        
        try:
            with self._lock:
                # Analyze current cache state
                cache_analysis = self._analyze_cache_state(cache_level, memory_metrics)
                
                # Determine optimization actions
                optimization_actions = self._determine_optimization_actions(
                    cache_level, cache_analysis, memory_metrics
                )
                
                # Execute optimizations
                result = await self._execute_optimizations(
                    cache_level, optimization_actions, cache_analysis
                )
                
                # Update metrics
                self._update_cache_metrics(cache_level, result)
                
                # Track optimization
                self._track_optimization(result)
                
                optimization_time = (time.time() - start_time) * 1000
                result.optimization_time_ms = optimization_time
                self._optimization_times.append(optimization_time)
                
                self._logger.info(f"Cache optimization completed for {cache_level.value}: "
                                f"evicted={result.items_evicted}, prefetched={result.items_prefetched}, "
                                f"time={optimization_time:.1f}ms")
                
                return result
                
        except Exception as e:
            self._logger.error(f"Error optimizing cache {cache_level.value}: {e}")
            return CacheOptimizationResult(
                timestamp=datetime.now(timezone.utc),
                optimization_type="error",
                cache_level=cache_level,
                items_evicted=0,
                items_prefetched=0,
                memory_freed_bytes=0,
                performance_improvement_percent=0.0,
                new_hit_rate=0.0,
                optimization_time_ms=0.0
            )
    
    def record_access(self, cache_level: CacheLevel, key: str, 
                     hit: bool, size_bytes: int) -> None:
        """Record a cache access for pattern analysis."""
        try:
            current_time = datetime.now(timezone.utc)
            
            with self._lock:
                # Update access pattern
                if key not in self._access_patterns[cache_level]:
                    self._access_patterns[cache_level][key] = AccessPattern(
                        key=key,
                        access_count=0,
                        last_access_time=current_time,
                        access_frequency=0.0,
                        sequential_score=0.0,
                        locality_score=0.0,
                        size_bytes=size_bytes
                    )
                
                pattern = self._access_patterns[cache_level][key]
                pattern.access_count += 1
                pattern.last_access_time = current_time
                pattern.access_times.append(current_time)
                pattern.size_bytes = size_bytes
                
                # Update frequency
                if len(pattern.access_times) >= 2:
                    time_span = (pattern.access_times[-1] - pattern.access_times[0]).total_seconds() / 60.0
                    pattern.access_frequency = len(pattern.access_times) / max(time_span, 1.0)
                
                # Record access in history
                self._access_history[cache_level].append({
                    'key': key,
                    'timestamp': current_time,
                    'hit': hit,
                    'size_bytes': size_bytes
                })
                
                # Update hit rate tracking
                recent_accesses = list(self._access_history[cache_level])[-100:]
                if recent_accesses:
                    hit_count = sum(1 for access in recent_accesses if access['hit'])
                    hit_rate = hit_count / len(recent_accesses)
                    self._hit_rates[cache_level].append(hit_rate)
                
                # Analyze patterns periodically
                if len(self._access_history[cache_level]) % 100 == 0:
                    asyncio.create_task(self._analyze_access_patterns(cache_level))
            
        except Exception as e:
            self._logger.error(f"Error recording access for {key}: {e}")
    
    def get_eviction_candidates(self, cache_level: CacheLevel, 
                               target_bytes: int) -> List[str]:
        """Get candidates for cache eviction."""
        try:
            with self._lock:
                policy = self._eviction_policies.get(cache_level, self._config.default_eviction_policy)
                patterns = self._access_patterns[cache_level]
                
                if not patterns:
                    return []
                
                candidates = []
                
                if policy == EvictionPolicy.LRU:
                    # Least Recently Used
                    sorted_patterns = sorted(
                        patterns.items(),
                        key=lambda x: x[1].last_access_time
                    )
                elif policy == EvictionPolicy.LFU:
                    # Least Frequently Used
                    sorted_patterns = sorted(
                        patterns.items(),
                        key=lambda x: x[1].access_frequency
                    )
                elif policy == EvictionPolicy.SIZE_BASED:
                    # Largest items first
                    sorted_patterns = sorted(
                        patterns.items(),
                        key=lambda x: x[1].size_bytes,
                        reverse=True
                    )
                else:  # ADAPTIVE or default
                    # Score-based eviction
                    scored_patterns = []
                    for key, pattern in patterns.items():
                        score = self._calculate_eviction_score(pattern)
                        scored_patterns.append((key, pattern, score))
                    
                    sorted_patterns = sorted(scored_patterns, key=lambda x: x[2])
                    sorted_patterns = [(key, pattern) for key, pattern, _ in sorted_patterns]
                
                # Select candidates until target bytes reached
                total_bytes = 0
                for key, pattern in sorted_patterns:
                    candidates.append(key)
                    total_bytes += pattern.size_bytes
                    if total_bytes >= target_bytes:
                        break
                
                return candidates
                
        except Exception as e:
            self._logger.error(f"Error getting eviction candidates: {e}")
            return []

    def get_prefetch_candidates(self, cache_level: CacheLevel,
                               current_key: str) -> List[str]:
        """Get candidates for cache prefetching."""
        try:
            with self._lock:
                strategy = self._prefetch_strategies.get(cache_level, self._config.default_prefetch_strategy)

                if strategy == PrefetchStrategy.NONE:
                    return []

                candidates = []

                if strategy == PrefetchStrategy.SEQUENTIAL:
                    candidates = self._get_sequential_prefetch_candidates(cache_level, current_key)
                elif strategy == PrefetchStrategy.PATTERN_BASED:
                    candidates = self._get_pattern_based_prefetch_candidates(cache_level, current_key)
                elif strategy == PrefetchStrategy.FREQUENCY_BASED:
                    candidates = self._get_frequency_based_prefetch_candidates(cache_level, current_key)
                elif strategy == PrefetchStrategy.LOCALITY_AWARE:
                    candidates = self._get_locality_aware_prefetch_candidates(cache_level, current_key)
                else:  # ADAPTIVE or PREDICTIVE
                    candidates = self._get_adaptive_prefetch_candidates(cache_level, current_key)

                # Limit number of prefetch candidates
                return candidates[:self._config.max_prefetch_items]

        except Exception as e:
            self._logger.error(f"Error getting prefetch candidates: {e}")
            return []

    async def start_optimization(self) -> None:
        """Start continuous cache optimization."""
        if self._optimization_active:
            self._logger.warning("Cache optimization already running")
            return

        self._optimization_active = True
        self._optimization_task = asyncio.create_task(self._optimization_loop())
        self._logger.info("Cache optimization started")

    async def stop_optimization(self) -> None:
        """Stop continuous cache optimization."""
        if not self._optimization_active:
            return

        self._optimization_active = False
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass

        self._logger.info("Cache optimization stopped")

    async def _optimization_loop(self) -> None:
        """Main optimization loop."""
        self._logger.info("Starting cache optimization loop")

        while self._optimization_active:
            try:
                # This would typically get current memory metrics and optimize
                # For now, we'll skip the actual optimization in the loop
                await asyncio.sleep(self._config.optimization_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(5.0)

    def _analyze_cache_state(self, cache_level: CacheLevel,
                            memory_metrics: MemoryMetrics) -> Dict[str, Any]:
        """Analyze current cache state."""
        try:
            analysis = {
                'memory_pressure': 0.0,
                'hit_rate': 0.0,
                'access_patterns_count': 0,
                'total_cache_size_bytes': 0,
                'eviction_needed': False,
                'prefetch_opportunities': 0
            }

            # Memory pressure analysis
            if memory_metrics:
                analysis['memory_pressure'] = memory_metrics.usage_percent / 100.0

                # Check if eviction is needed
                if (memory_metrics.usage_percent > self._config.eviction_threshold_percent or
                    memory_metrics.available_ram_mb * 1024 * 1024 < self._config.min_free_memory_bytes):
                    analysis['eviction_needed'] = True

            # Hit rate analysis
            if cache_level in self._hit_rates and self._hit_rates[cache_level]:
                analysis['hit_rate'] = statistics.mean(list(self._hit_rates[cache_level])[-10:])

            # Access patterns analysis
            patterns = self._access_patterns[cache_level]
            analysis['access_patterns_count'] = len(patterns)
            analysis['total_cache_size_bytes'] = sum(p.size_bytes for p in patterns.values())

            # Prefetch opportunities
            recent_accesses = list(self._access_history[cache_level])[-50:]
            sequential_accesses = self._count_sequential_accesses(recent_accesses)
            analysis['prefetch_opportunities'] = sequential_accesses

            return analysis

        except Exception as e:
            self._logger.error(f"Error analyzing cache state: {e}")
            return {}

    def _determine_optimization_actions(self, cache_level: CacheLevel,
                                       cache_analysis: Dict[str, Any],
                                       memory_metrics: MemoryMetrics) -> Dict[str, Any]:
        """Determine what optimization actions to take."""
        try:
            actions = {
                'evict_items': False,
                'prefetch_items': False,
                'adjust_policy': False,
                'target_eviction_bytes': 0,
                'target_prefetch_count': 0
            }

            # Eviction decisions
            if cache_analysis.get('eviction_needed', False):
                actions['evict_items'] = True

                # Calculate target eviction bytes
                memory_pressure = cache_analysis.get('memory_pressure', 0.0)
                if memory_pressure > 0.9:
                    # Aggressive eviction
                    actions['target_eviction_bytes'] = int(
                        cache_analysis.get('total_cache_size_bytes', 0) * 0.3
                    )
                elif memory_pressure > 0.8:
                    # Moderate eviction
                    actions['target_eviction_bytes'] = int(
                        cache_analysis.get('total_cache_size_bytes', 0) * 0.2
                    )
                else:
                    # Conservative eviction
                    actions['target_eviction_bytes'] = int(
                        cache_analysis.get('total_cache_size_bytes', 0) * 0.1
                    )

            # Prefetch decisions
            hit_rate = cache_analysis.get('hit_rate', 0.0)
            prefetch_opportunities = cache_analysis.get('prefetch_opportunities', 0)

            if (hit_rate < 0.8 and prefetch_opportunities > 5 and
                not actions['evict_items'] and memory_pressure < 0.7):
                actions['prefetch_items'] = True
                actions['target_prefetch_count'] = min(
                    self._config.max_prefetch_items,
                    prefetch_opportunities
                )

            # Policy adjustment decisions
            if len(self._optimization_history) >= 10:
                recent_results = list(self._optimization_history)[-10:]
                avg_improvement = statistics.mean([r.performance_improvement_percent for r in recent_results])
                if avg_improvement < 5.0:  # Poor performance
                    actions['adjust_policy'] = True

            return actions

        except Exception as e:
            self._logger.error(f"Error determining optimization actions: {e}")
            return {}

    async def _execute_optimizations(self, cache_level: CacheLevel,
                                   actions: Dict[str, Any],
                                   cache_analysis: Dict[str, Any]) -> CacheOptimizationResult:
        """Execute optimization actions."""
        try:
            result = CacheOptimizationResult(
                timestamp=datetime.now(timezone.utc),
                optimization_type="cache_optimization",
                cache_level=cache_level,
                items_evicted=0,
                items_prefetched=0,
                memory_freed_bytes=0,
                performance_improvement_percent=0.0,
                new_hit_rate=cache_analysis.get('hit_rate', 0.0),
                optimization_time_ms=0.0
            )

            # Execute eviction
            if actions.get('evict_items', False):
                target_bytes = actions.get('target_eviction_bytes', 0)
                eviction_candidates = self.get_eviction_candidates(cache_level, target_bytes)

                result.items_evicted = len(eviction_candidates)
                result.memory_freed_bytes = sum(
                    self._access_patterns[cache_level][key].size_bytes
                    for key in eviction_candidates
                    if key in self._access_patterns[cache_level]
                )

                # Remove evicted items from tracking
                for key in eviction_candidates:
                    if key in self._access_patterns[cache_level]:
                        del self._access_patterns[cache_level][key]

            # Execute prefetching
            if actions.get('prefetch_items', False):
                # Get recent access for prefetch context
                recent_accesses = list(self._access_history[cache_level])[-10:]
                if recent_accesses:
                    last_key = recent_accesses[-1]['key']
                    prefetch_candidates = self.get_prefetch_candidates(cache_level, last_key)
                    result.items_prefetched = len(prefetch_candidates)

            # Adjust policies if needed
            if actions.get('adjust_policy', False):
                await self._adjust_optimization_policies(cache_level, cache_analysis)
                result.optimization_type = "policy_adjustment"

            # Calculate performance improvement estimate
            if result.items_evicted > 0 or result.items_prefetched > 0:
                result.performance_improvement_percent = self._estimate_performance_improvement(
                    result, cache_analysis
                )

            return result

        except Exception as e:
            self._logger.error(f"Error executing optimizations: {e}")
            return CacheOptimizationResult(
                timestamp=datetime.now(timezone.utc),
                optimization_type="error",
                cache_level=cache_level,
                items_evicted=0,
                items_prefetched=0,
                memory_freed_bytes=0,
                performance_improvement_percent=0.0,
                new_hit_rate=0.0,
                optimization_time_ms=0.0
            )

    def _calculate_eviction_score(self, pattern: AccessPattern) -> float:
        """Calculate eviction score for an access pattern (lower = more likely to evict)."""
        try:
            current_time = datetime.now(timezone.utc)

            # Time since last access (normalized)
            time_since_access = (current_time - pattern.last_access_time).total_seconds() / 3600.0  # Hours
            recency_score = min(1.0, time_since_access / 24.0)  # Normalize to 24 hours

            # Frequency score (inverse)
            frequency_score = 1.0 / (pattern.access_frequency + 1.0)

            # Size penalty (larger items more likely to be evicted)
            size_score = min(1.0, pattern.size_bytes / (1024 * 1024))  # Normalize to 1MB

            # Combine scores (lower = more likely to evict)
            eviction_score = (
                0.4 * recency_score +
                0.4 * frequency_score +
                0.2 * size_score
            )

            return eviction_score

        except Exception:
            return 0.5

    def _get_sequential_prefetch_candidates(self, cache_level: CacheLevel,
                                          current_key: str) -> List[str]:
        """Get prefetch candidates based on sequential access patterns."""
        try:
            candidates = []
            sequential_patterns = self._sequential_patterns[cache_level]

            if current_key in sequential_patterns:
                # Get next items in sequence
                sequence = sequential_patterns[current_key]
                candidates.extend(sequence[:self._config.prefetch_window_size])

            return candidates

        except Exception:
            return []

    def _get_pattern_based_prefetch_candidates(self, cache_level: CacheLevel,
                                             current_key: str) -> List[str]:
        """Get prefetch candidates based on access patterns."""
        try:
            candidates = []

            # Look for items frequently accessed together
            locality_groups = self._locality_groups[cache_level]
            if current_key in locality_groups:
                related_items = list(locality_groups[current_key])
                candidates.extend(related_items[:self._config.prefetch_window_size])

            return candidates

        except Exception:
            return []

    def _get_frequency_based_prefetch_candidates(self, cache_level: CacheLevel,
                                               current_key: str) -> List[str]:
        """Get prefetch candidates based on access frequency."""
        try:
            patterns = self._access_patterns[cache_level]

            # Sort by frequency and get top candidates
            sorted_patterns = sorted(
                patterns.items(),
                key=lambda x: x[1].access_frequency,
                reverse=True
            )

            candidates = [key for key, _ in sorted_patterns[:self._config.prefetch_window_size]]

            # Remove current key if present
            if current_key in candidates:
                candidates.remove(current_key)

            return candidates

        except Exception:
            return []

    def _get_locality_aware_prefetch_candidates(self, cache_level: CacheLevel,
                                              current_key: str) -> List[str]:
        """Get prefetch candidates based on locality of reference."""
        try:
            candidates = []
            patterns = self._access_patterns[cache_level]

            if current_key not in patterns:
                return candidates

            current_pattern = patterns[current_key]

            # Find items with high locality scores relative to current item
            for key, pattern in patterns.items():
                if key != current_key and pattern.locality_score > 0.7:
                    candidates.append(key)

            # Sort by locality score and limit
            candidates.sort(key=lambda k: patterns[k].locality_score, reverse=True)
            return candidates[:self._config.prefetch_window_size]

        except Exception:
            return []

    def _get_adaptive_prefetch_candidates(self, cache_level: CacheLevel,
                                        current_key: str) -> List[str]:
        """Get prefetch candidates using adaptive strategy."""
        try:
            # Combine multiple strategies
            sequential_candidates = self._get_sequential_prefetch_candidates(cache_level, current_key)
            pattern_candidates = self._get_pattern_based_prefetch_candidates(cache_level, current_key)
            frequency_candidates = self._get_frequency_based_prefetch_candidates(cache_level, current_key)

            # Merge and deduplicate
            all_candidates = []
            all_candidates.extend(sequential_candidates[:3])
            all_candidates.extend(pattern_candidates[:3])
            all_candidates.extend(frequency_candidates[:3])

            # Remove duplicates while preserving order
            seen = set()
            unique_candidates = []
            for candidate in all_candidates:
                if candidate not in seen:
                    seen.add(candidate)
                    unique_candidates.append(candidate)

            return unique_candidates[:self._config.prefetch_window_size]

        except Exception:
            return []

    async def _analyze_access_patterns(self, cache_level: CacheLevel) -> None:
        """Analyze access patterns for optimization."""
        try:
            patterns = self._access_patterns[cache_level]
            access_history = list(self._access_history[cache_level])

            # Update sequential patterns
            await self._update_sequential_patterns(cache_level, access_history)

            # Update locality patterns
            await self._update_locality_patterns(cache_level, patterns)

            # Update frequency patterns
            await self._update_frequency_patterns(cache_level, patterns)

        except Exception as e:
            self._logger.error(f"Error analyzing access patterns: {e}")

    async def _update_sequential_patterns(self, cache_level: CacheLevel,
                                        access_history: List[Dict[str, Any]]) -> None:
        """Update sequential access patterns."""
        try:
            sequential_patterns = self._sequential_patterns[cache_level]

            # Look for sequential access patterns in recent history
            for i in range(len(access_history) - 1):
                current_key = access_history[i]['key']
                next_key = access_history[i + 1]['key']

                if current_key not in sequential_patterns:
                    sequential_patterns[current_key] = []

                if next_key not in sequential_patterns[current_key]:
                    sequential_patterns[current_key].append(next_key)

                # Limit sequence length
                if len(sequential_patterns[current_key]) > self._config.prefetch_window_size:
                    sequential_patterns[current_key] = sequential_patterns[current_key][-self._config.prefetch_window_size:]

        except Exception as e:
            self._logger.error(f"Error updating sequential patterns: {e}")

    async def _update_locality_patterns(self, cache_level: CacheLevel,
                                       patterns: Dict[str, AccessPattern]) -> None:
        """Update locality of reference patterns."""
        try:
            locality_groups = self._locality_groups[cache_level]

            # Group items accessed within time windows
            time_window = timedelta(minutes=5)

            for key1, pattern1 in patterns.items():
                for key2, pattern2 in patterns.items():
                    if key1 != key2:
                        # Check if accessed within time window
                        time_diff = abs((pattern1.last_access_time - pattern2.last_access_time).total_seconds())
                        if time_diff <= time_window.total_seconds():
                            locality_groups[key1].add(key2)
                            locality_groups[key2].add(key1)

                            # Update locality scores
                            pattern1.locality_score = min(1.0, len(locality_groups[key1]) / 10.0)
                            pattern2.locality_score = min(1.0, len(locality_groups[key2]) / 10.0)

        except Exception as e:
            self._logger.error(f"Error updating locality patterns: {e}")

    async def _update_frequency_patterns(self, cache_level: CacheLevel,
                                        patterns: Dict[str, AccessPattern]) -> None:
        """Update frequency-based patterns."""
        try:
            frequency_patterns = self._frequency_patterns[cache_level]

            for key, pattern in patterns.items():
                frequency_patterns[key] = pattern.access_frequency

        except Exception as e:
            self._logger.error(f"Error updating frequency patterns: {e}")

    def _count_sequential_accesses(self, access_history: List[Dict[str, Any]]) -> int:
        """Count sequential access patterns in history."""
        try:
            sequential_count = 0

            for i in range(len(access_history) - 1):
                current_key = access_history[i]['key']
                next_key = access_history[i + 1]['key']

                # Simple heuristic: check if keys are numerically sequential
                try:
                    current_num = int(current_key.split('_')[-1])
                    next_num = int(next_key.split('_')[-1])
                    if next_num == current_num + 1:
                        sequential_count += 1
                except (ValueError, IndexError):
                    pass

            return sequential_count

        except Exception:
            return 0

    async def _adjust_optimization_policies(self, cache_level: CacheLevel,
                                          cache_analysis: Dict[str, Any]) -> None:
        """Adjust optimization policies based on performance."""
        try:
            current_hit_rate = cache_analysis.get('hit_rate', 0.0)

            # Adjust eviction policy
            if current_hit_rate < 0.6:
                # Poor hit rate - try more conservative eviction
                if self._eviction_policies.get(cache_level) != EvictionPolicy.LFU:
                    self._eviction_policies[cache_level] = EvictionPolicy.LFU
                    self._logger.info(f"Switched to LFU eviction policy for {cache_level.value}")
            elif current_hit_rate > 0.9:
                # Excellent hit rate - can be more aggressive
                if self._eviction_policies.get(cache_level) != EvictionPolicy.LRU:
                    self._eviction_policies[cache_level] = EvictionPolicy.LRU
                    self._logger.info(f"Switched to LRU eviction policy for {cache_level.value}")

            # Adjust prefetch strategy
            prefetch_opportunities = cache_analysis.get('prefetch_opportunities', 0)
            if prefetch_opportunities > 10:
                # High sequential access - use sequential prefetch
                self._prefetch_strategies[cache_level] = PrefetchStrategy.SEQUENTIAL
            elif current_hit_rate < 0.7:
                # Poor hit rate - use adaptive prefetch
                self._prefetch_strategies[cache_level] = PrefetchStrategy.ADAPTIVE

        except Exception as e:
            self._logger.error(f"Error adjusting optimization policies: {e}")

    def _estimate_performance_improvement(self, result: CacheOptimizationResult,
                                        cache_analysis: Dict[str, Any]) -> float:
        """Estimate performance improvement from optimization."""
        try:
            improvement = 0.0

            # Improvement from eviction (memory pressure relief)
            if result.items_evicted > 0:
                memory_pressure = cache_analysis.get('memory_pressure', 0.0)
                if memory_pressure > 0.8:
                    improvement += 10.0  # Significant improvement from pressure relief
                else:
                    improvement += 5.0   # Moderate improvement

            # Improvement from prefetching (hit rate increase)
            if result.items_prefetched > 0:
                current_hit_rate = cache_analysis.get('hit_rate', 0.0)
                if current_hit_rate < 0.7:
                    improvement += 15.0  # Significant improvement potential
                else:
                    improvement += 5.0   # Moderate improvement

            return min(50.0, improvement)  # Cap at 50% improvement

        except Exception:
            return 0.0

    def _update_cache_metrics(self, cache_level: CacheLevel,
                             result: CacheOptimizationResult) -> None:
        """Update cache metrics after optimization."""
        try:
            current_time = datetime.now(timezone.utc)

            # Calculate current metrics
            hit_rate = result.new_hit_rate
            miss_rate = 1.0 - hit_rate

            patterns = self._access_patterns[cache_level]
            total_size = sum(p.size_bytes for p in patterns.values())
            memory_usage_percent = min(100.0, (total_size / self._config.max_memory_usage_bytes) * 100)

            metrics = CacheMetrics(
                timestamp=current_time,
                cache_level=cache_level,
                hit_rate=hit_rate,
                miss_rate=miss_rate,
                eviction_rate=result.items_evicted / max(1, len(patterns)),
                memory_usage_bytes=total_size,
                memory_usage_percent=memory_usage_percent,
                average_access_time_ms=1.0,  # Placeholder
                prefetch_accuracy=0.8,  # Placeholder
                cache_efficiency=hit_rate * (1.0 - memory_usage_percent / 100.0)
            )

            self._cache_metrics[cache_level].append(metrics)
            self._current_metrics[cache_level] = metrics

        except Exception as e:
            self._logger.error(f"Error updating cache metrics: {e}")

    def _track_optimization(self, result: CacheOptimizationResult) -> None:
        """Track optimization result for analysis."""
        try:
            with self._lock:
                self._optimization_history.append(result)

        except Exception as e:
            self._logger.error(f"Error tracking optimization: {e}")

    def _initialize_default_policies(self) -> None:
        """Initialize default optimization policies."""
        try:
            # Set default policies for all cache levels
            for cache_level in CacheLevel:
                self._eviction_policies[cache_level] = self._config.default_eviction_policy
                self._prefetch_strategies[cache_level] = self._config.default_prefetch_strategy

        except Exception as e:
            self._logger.error(f"Error initializing default policies: {e}")

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get statistics about cache optimization."""
        with self._lock:
            avg_optimization_time = (
                statistics.mean(self._optimization_times) if self._optimization_times else 0.0
            )

            total_patterns = sum(len(patterns) for patterns in self._access_patterns.values())

            avg_hit_rates = {}
            for cache_level, hit_rates in self._hit_rates.items():
                if hit_rates:
                    avg_hit_rates[cache_level.value] = statistics.mean(hit_rates)

            return {
                'optimization_active': self._optimization_active,
                'total_access_patterns': total_patterns,
                'optimization_history': len(self._optimization_history),
                'average_optimization_time_ms': avg_optimization_time,
                'average_hit_rates': avg_hit_rates,
                'cache_levels_monitored': len(self._access_patterns),
                'eviction_policies': {level.value: policy.value for level, policy in self._eviction_policies.items()},
                'prefetch_strategies': {level.value: strategy.value for level, strategy in self._prefetch_strategies.items()}
            }
