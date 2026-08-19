"""
Module: work_distributor_lg
Description: Distributes work across available threads with load balancing and performance optimization
Phase: 2
Location: /src/modules/logic/thread_coordination_lg/work_distributor_lg/
"""

# Standard library imports
import threading
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier
from ..base_interfaces import (
    IThreadPoolManager, ThreadPoolType, ThreadTask, TaskPriority, 
    ThreadPoolStatus, ThreadPoolInfo
)


class DistributionStrategy(Enum):
    """Work distribution strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    PRIORITY_BASED = "priority_based"
    AFFINITY_BASED = "affinity_based"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    BALANCED = "balanced"


class WorkloadType(Enum):
    """Types of workloads for distribution optimization."""
    CPU_INTENSIVE = "cpu_intensive"
    IO_INTENSIVE = "io_intensive"
    MEMORY_INTENSIVE = "memory_intensive"
    MIXED = "mixed"
    TRAINING = "training"
    INFERENCE = "inference"


@dataclass
class WorkItem:
    """Represents a unit of work to be distributed."""
    work_id: str
    task: ThreadTask
    workload_type: WorkloadType
    estimated_duration: Optional[float] = None
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    affinity_hints: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    assigned_pool: Optional[ThreadPoolType] = None
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    success: bool = False
    error: Optional[Exception] = None


@dataclass
class PoolLoadInfo:
    """Load information for a thread pool."""
    pool_type: ThreadPoolType
    active_threads: int
    max_threads: int
    queue_size: int
    avg_execution_time: float
    total_completed: int
    total_failed: int
    load_factor: float
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class DistributionConfig:
    """Configuration for work distribution."""
    default_strategy: DistributionStrategy = DistributionStrategy.BALANCED
    enable_load_balancing: bool = True
    enable_affinity: bool = True
    enable_performance_tracking: bool = True
    load_update_interval: float = 1.0
    rebalance_threshold: float = 0.3
    max_queue_ratio: float = 2.0
    enable_predictive_scheduling: bool = True
    history_window_size: int = 100


class WorkDistributor:
    """
    Distributes work across available threads with load balancing and performance optimization.
    
    Features:
    - Multiple distribution strategies
    - Load balancing across thread pools
    - Performance-based optimization
    - Affinity-based scheduling
    - Predictive workload distribution
    - Real-time load monitoring
    """
    
    def __init__(self, thread_pool_manager: IThreadPoolManager,
                 config: Optional[DistributionConfig] = None):
        """
        Initialize work distributor.
        
        Args:
            thread_pool_manager: Thread pool manager instance
            config: Distribution configuration
        """
        self.config = config or DistributionConfig()
        self._thread_pool_manager = thread_pool_manager
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()
        
        # Work tracking
        self._work_items: Dict[str, WorkItem] = {}
        self._pending_work: deque = deque()
        self._active_work: Dict[str, WorkItem] = {}
        self._completed_work: Dict[str, WorkItem] = {}
        
        # Load monitoring
        self._pool_loads: Dict[ThreadPoolType, PoolLoadInfo] = {}
        self._load_history: Dict[ThreadPoolType, deque] = defaultdict(
            lambda: deque(maxlen=self.config.history_window_size)
        )
        
        # Distribution state
        self._round_robin_index: Dict[ThreadPoolType, int] = defaultdict(int)
        self._affinity_map: Dict[str, ThreadPoolType] = {}
        
        # Synchronization
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        
        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Metrics
        self._total_distributed = 0
        self._distribution_failures = 0
        self._rebalance_count = 0
        
        self._logger.info("Work distributor initialized")
    
    def start(self) -> bool:
        """Start the work distributor."""
        try:
            with self._lock:
                if self._running:
                    self._logger.warning("Work distributor already running")
                    return True
                
                self._running = True
                self._shutdown_event.clear()
                
                # Initialize pool load information
                self._initialize_pool_loads()
                
                # Start monitoring thread
                self._monitor_thread = threading.Thread(
                    target=self._monitoring_loop,
                    name="WorkDistributorMonitor",
                    daemon=True
                )
                self._monitor_thread.start()
                
                self._logger.info("Work distributor started")
                return True
                
        except Exception as e:
            self._logger.error(f"Error starting work distributor: {e}")
            return False
    
    def stop(self, timeout: Optional[float] = None) -> bool:
        """Stop the work distributor."""
        try:
            with self._lock:
                if not self._running:
                    return True
                
                self._running = False
                self._shutdown_event.set()
                
                # Wait for monitoring thread
                if self._monitor_thread and self._monitor_thread.is_alive():
                    self._monitor_thread.join(timeout=timeout or 5.0)
                
                self._logger.info("Work distributor stopped")
                return True
                
        except Exception as e:
            self._logger.error(f"Error stopping work distributor: {e}")
            return False
    
    def distribute_work(self, task: ThreadTask, 
                       workload_type: WorkloadType = WorkloadType.MIXED,
                       strategy: Optional[DistributionStrategy] = None,
                       affinity_hints: Optional[List[str]] = None,
                       estimated_duration: Optional[float] = None) -> Optional[str]:
        """
        Distribute work to the most appropriate thread pool.
        
        Args:
            task: Task to distribute
            workload_type: Type of workload
            strategy: Distribution strategy to use
            affinity_hints: Pool affinity hints
            estimated_duration: Estimated execution time
            
        Returns:
            Work ID if distributed successfully, None otherwise
        """
        try:
            work_id = str(uuid.uuid4())
            
            # Create work item
            work_item = WorkItem(
                work_id=work_id,
                task=task,
                workload_type=workload_type,
                estimated_duration=estimated_duration,
                affinity_hints=affinity_hints or []
            )
            
            with self._lock:
                self._work_items[work_id] = work_item
                self._total_distributed += 1
            
            # Select target pool
            target_pool = self._select_target_pool(
                work_item, 
                strategy or self.config.default_strategy
            )
            
            if not target_pool:
                self._logger.error(f"No suitable pool found for work {work_id}")
                self._distribution_failures += 1
                return None
            
            # Submit to pool
            future = self._thread_pool_manager.submit_task(target_pool, task)
            
            if future:
                work_item.assigned_pool = target_pool
                work_item.assigned_at = datetime.now()
                
                with self._lock:
                    self._active_work[work_id] = work_item
                
                # Track completion
                future.add_done_callback(
                    lambda f: self._handle_work_completion(work_id, f)
                )
                
                self._logger.debug(f"Distributed work {work_id} to pool {target_pool.value}")
                return work_id
            else:
                self._logger.error(f"Failed to submit work {work_id} to pool {target_pool.value}")
                self._distribution_failures += 1
                return None
                
        except Exception as e:
            self._logger.error(f"Error distributing work: {e}")
            self._distribution_failures += 1
            return None

    def _select_target_pool(self, work_item: WorkItem,
                           strategy: DistributionStrategy) -> Optional[ThreadPoolType]:
        """Select the target thread pool for a work item."""
        try:
            # Get available pools
            available_pools = self._get_available_pools()

            if not available_pools:
                return None

            # Apply strategy
            if strategy == DistributionStrategy.ROUND_ROBIN:
                return self._select_round_robin(available_pools)

            elif strategy == DistributionStrategy.LEAST_LOADED:
                return self._select_least_loaded(available_pools)

            elif strategy == DistributionStrategy.PRIORITY_BASED:
                return self._select_priority_based(work_item, available_pools)

            elif strategy == DistributionStrategy.AFFINITY_BASED:
                return self._select_affinity_based(work_item, available_pools)

            elif strategy == DistributionStrategy.PERFORMANCE_OPTIMIZED:
                return self._select_performance_optimized(work_item, available_pools)

            else:  # BALANCED
                return self._select_balanced(work_item, available_pools)

        except Exception as e:
            self._logger.error(f"Error selecting target pool: {e}")
            return None

    def _get_available_pools(self) -> List[ThreadPoolType]:
        """Get list of available thread pools."""
        try:
            available_pools = []

            for pool_type in ThreadPoolType:
                pool_info = self._thread_pool_manager.get_pool_info(pool_type)
                if pool_info and pool_info.status == ThreadPoolStatus.ACTIVE:
                    available_pools.append(pool_type)

            return available_pools

        except Exception as e:
            self._logger.error(f"Error getting available pools: {e}")
            return []

    def _select_round_robin(self, available_pools: List[ThreadPoolType]) -> ThreadPoolType:
        """Select pool using round-robin strategy."""
        if not available_pools:
            return None

        # Simple round-robin across all available pools
        pool_type = available_pools[self._round_robin_index[None] % len(available_pools)]
        self._round_robin_index[None] = (self._round_robin_index[None] + 1) % len(available_pools)

        return pool_type

    def _select_least_loaded(self, available_pools: List[ThreadPoolType]) -> Optional[ThreadPoolType]:
        """Select the least loaded pool."""
        try:
            best_pool = None
            lowest_load = float('inf')

            for pool_type in available_pools:
                load_info = self._pool_loads.get(pool_type)
                if load_info and load_info.load_factor < lowest_load:
                    lowest_load = load_info.load_factor
                    best_pool = pool_type

            return best_pool

        except Exception as e:
            self._logger.error(f"Error selecting least loaded pool: {e}")
            return available_pools[0] if available_pools else None

    def _select_priority_based(self, work_item: WorkItem,
                              available_pools: List[ThreadPoolType]) -> Optional[ThreadPoolType]:
        """Select pool based on task priority and workload type."""
        try:
            task_priority = work_item.task.priority
            workload_type = work_item.workload_type

            # High priority tasks get dedicated pools
            if task_priority == TaskPriority.CRITICAL:
                if workload_type == WorkloadType.TRAINING and ThreadPoolType.TRAINING in available_pools:
                    return ThreadPoolType.TRAINING
                elif workload_type == WorkloadType.INFERENCE and ThreadPoolType.INFERENCE in available_pools:
                    return ThreadPoolType.INFERENCE

            # Map workload types to preferred pools
            workload_pool_map = {
                WorkloadType.TRAINING: ThreadPoolType.TRAINING,
                WorkloadType.INFERENCE: ThreadPoolType.INFERENCE,
                WorkloadType.CPU_INTENSIVE: ThreadPoolType.DOCUMENT_PROCESSING,
                WorkloadType.IO_INTENSIVE: ThreadPoolType.BACKGROUND,
                WorkloadType.MEMORY_INTENSIVE: ThreadPoolType.GENERAL
            }

            preferred_pool = workload_pool_map.get(workload_type, ThreadPoolType.GENERAL)

            if preferred_pool in available_pools:
                return preferred_pool

            # Fallback to least loaded
            return self._select_least_loaded(available_pools)

        except Exception as e:
            self._logger.error(f"Error in priority-based selection: {e}")
            return available_pools[0] if available_pools else None

    def _select_affinity_based(self, work_item: WorkItem,
                              available_pools: List[ThreadPoolType]) -> Optional[ThreadPoolType]:
        """Select pool based on affinity hints."""
        try:
            # Check affinity hints
            for hint in work_item.affinity_hints:
                if hint in self._affinity_map:
                    preferred_pool = self._affinity_map[hint]
                    if preferred_pool in available_pools:
                        return preferred_pool

            # Check for pool type hints in affinity
            for hint in work_item.affinity_hints:
                try:
                    pool_type = ThreadPoolType(hint.lower())
                    if pool_type in available_pools:
                        return pool_type
                except ValueError:
                    continue

            # Fallback to balanced selection
            return self._select_balanced(work_item, available_pools)

        except Exception as e:
            self._logger.error(f"Error in affinity-based selection: {e}")
            return available_pools[0] if available_pools else None

    def _select_performance_optimized(self, work_item: WorkItem,
                                    available_pools: List[ThreadPoolType]) -> Optional[ThreadPoolType]:
        """Select pool optimized for performance."""
        try:
            best_pool = None
            best_score = -1

            for pool_type in available_pools:
                load_info = self._pool_loads.get(pool_type)
                if not load_info:
                    continue

                # Calculate performance score
                utilization = load_info.active_threads / max(1, load_info.max_threads)
                queue_factor = load_info.queue_size / max(1, load_info.max_threads)
                avg_time = load_info.avg_execution_time

                # Lower is better for utilization and queue, higher is better for throughput
                score = (1.0 - utilization) * 0.4 + (1.0 - min(1.0, queue_factor)) * 0.3

                if avg_time > 0:
                    throughput_factor = 1.0 / avg_time
                    score += throughput_factor * 0.3

                if score > best_score:
                    best_score = score
                    best_pool = pool_type

            return best_pool or available_pools[0]

        except Exception as e:
            self._logger.error(f"Error in performance-optimized selection: {e}")
            return available_pools[0] if available_pools else None

    def _select_balanced(self, work_item: WorkItem,
                        available_pools: List[ThreadPoolType]) -> Optional[ThreadPoolType]:
        """Select pool using balanced approach."""
        try:
            # Combine multiple factors
            best_pool = None
            best_score = -1

            for pool_type in available_pools:
                load_info = self._pool_loads.get(pool_type)
                if not load_info:
                    continue

                # Calculate balanced score
                load_factor = 1.0 - load_info.load_factor
                queue_factor = 1.0 - min(1.0, load_info.queue_size / max(1, load_info.max_threads))

                # Workload type affinity
                affinity_score = self._calculate_workload_affinity(work_item.workload_type, pool_type)

                # Priority factor
                priority_factor = 1.0
                if work_item.task.priority == TaskPriority.CRITICAL:
                    priority_factor = 1.5
                elif work_item.task.priority == TaskPriority.HIGH:
                    priority_factor = 1.2

                # Combined score
                score = (load_factor * 0.3 + queue_factor * 0.3 +
                        affinity_score * 0.3 + priority_factor * 0.1)

                if score > best_score:
                    best_score = score
                    best_pool = pool_type

            return best_pool or available_pools[0]

        except Exception as e:
            self._logger.error(f"Error in balanced selection: {e}")
            return available_pools[0] if available_pools else None

    def _calculate_workload_affinity(self, workload_type: WorkloadType,
                                   pool_type: ThreadPoolType) -> float:
        """Calculate affinity score between workload and pool type."""
        affinity_map = {
            (WorkloadType.TRAINING, ThreadPoolType.TRAINING): 1.0,
            (WorkloadType.INFERENCE, ThreadPoolType.INFERENCE): 1.0,
            (WorkloadType.CPU_INTENSIVE, ThreadPoolType.DOCUMENT_PROCESSING): 0.8,
            (WorkloadType.IO_INTENSIVE, ThreadPoolType.BACKGROUND): 0.8,
            (WorkloadType.MEMORY_INTENSIVE, ThreadPoolType.GENERAL): 0.7,
            (WorkloadType.MIXED, ThreadPoolType.GENERAL): 0.6
        }

        return affinity_map.get((workload_type, pool_type), 0.5)

    def _handle_work_completion(self, work_id: str, future: Future) -> None:
        """Handle completion of a work item."""
        try:
            with self._lock:
                if work_id not in self._active_work:
                    return

                work_item = self._active_work.pop(work_id)
                work_item.completed_at = datetime.now()

                if work_item.assigned_at:
                    work_item.execution_time = (
                        work_item.completed_at - work_item.assigned_at
                    ).total_seconds()

                # Check if task succeeded
                try:
                    result = future.result()
                    work_item.success = True
                except Exception as e:
                    work_item.success = False
                    work_item.error = e

                # Move to completed
                self._completed_work[work_id] = work_item

                # Update pool load information
                if work_item.assigned_pool:
                    self._update_pool_load(work_item.assigned_pool, work_item)

                self._logger.debug(f"Work {work_id} completed: success={work_item.success}")

        except Exception as e:
            self._logger.error(f"Error handling work completion for {work_id}: {e}")

    def _initialize_pool_loads(self) -> None:
        """Initialize pool load information."""
        try:
            for pool_type in ThreadPoolType:
                pool_info = self._thread_pool_manager.get_pool_info(pool_type)
                if pool_info:
                    load_info = PoolLoadInfo(
                        pool_type=pool_type,
                        active_threads=0,
                        max_threads=pool_info.max_threads,
                        queue_size=0,
                        avg_execution_time=0.0,
                        total_completed=0,
                        total_failed=0,
                        load_factor=0.0
                    )
                    self._pool_loads[pool_type] = load_info

        except Exception as e:
            self._logger.error(f"Error initializing pool loads: {e}")

    def _update_pool_load(self, pool_type: ThreadPoolType, work_item: WorkItem) -> None:
        """Update load information for a pool."""
        try:
            load_info = self._pool_loads.get(pool_type)
            if not load_info:
                return

            # Update completion counts
            if work_item.success:
                load_info.total_completed += 1
            else:
                load_info.total_failed += 1

            # Update average execution time
            if work_item.execution_time:
                total_tasks = load_info.total_completed + load_info.total_failed
                if total_tasks > 1:
                    load_info.avg_execution_time = (
                        (load_info.avg_execution_time * (total_tasks - 1) + work_item.execution_time) / total_tasks
                    )
                else:
                    load_info.avg_execution_time = work_item.execution_time

            # Update load factor
            pool_info = self._thread_pool_manager.get_pool_info(pool_type)
            if pool_info:
                load_info.active_threads = pool_info.active_threads
                load_info.queue_size = pool_info.queue_size
                load_info.load_factor = load_info.active_threads / max(1, load_info.max_threads)

            load_info.last_updated = datetime.now()

            # Add to history
            self._load_history[pool_type].append({
                'timestamp': datetime.now(),
                'load_factor': load_info.load_factor,
                'queue_size': load_info.queue_size,
                'avg_execution_time': load_info.avg_execution_time
            })

        except Exception as e:
            self._logger.error(f"Error updating pool load for {pool_type.value}: {e}")

    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                self._update_all_pool_loads()
                self._check_rebalancing()
                self._shutdown_event.wait(self.config.load_update_interval)

            except Exception as e:
                self._logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1)

    def _update_all_pool_loads(self) -> None:
        """Update load information for all pools."""
        try:
            for pool_type in self._pool_loads:
                pool_info = self._thread_pool_manager.get_pool_info(pool_type)
                if pool_info:
                    load_info = self._pool_loads[pool_type]
                    load_info.active_threads = pool_info.active_threads
                    load_info.queue_size = pool_info.queue_size
                    load_info.load_factor = load_info.active_threads / max(1, load_info.max_threads)
                    load_info.last_updated = datetime.now()

        except Exception as e:
            self._logger.error(f"Error updating all pool loads: {e}")

    def _check_rebalancing(self) -> None:
        """Check if rebalancing is needed."""
        try:
            if not self.config.enable_load_balancing:
                return

            # Calculate load variance
            load_factors = [info.load_factor for info in self._pool_loads.values()]
            if not load_factors:
                return

            avg_load = sum(load_factors) / len(load_factors)
            max_load = max(load_factors)
            min_load = min(load_factors)

            # Check if rebalancing is needed
            if max_load - min_load > self.config.rebalance_threshold:
                self._logger.info(f"Load imbalance detected: max={max_load:.2f}, min={min_load:.2f}")
                self._rebalance_count += 1

        except Exception as e:
            self._logger.error(f"Error checking rebalancing: {e}")

    def get_work_status(self, work_id: str) -> Optional[str]:
        """Get the status of a work item."""
        try:
            with self._lock:
                if work_id in self._active_work:
                    return "active"
                elif work_id in self._completed_work:
                    return "completed"
                elif work_id in self._work_items:
                    return "pending"
                else:
                    return None

        except Exception as e:
            self._logger.error(f"Error getting work status for {work_id}: {e}")
            return None

    def get_work_result(self, work_id: str) -> Optional[Any]:
        """Get the result of completed work."""
        try:
            with self._lock:
                if work_id in self._completed_work:
                    work_item = self._completed_work[work_id]
                    if work_item.success:
                        return work_item.task.result if hasattr(work_item.task, 'result') else True
                    else:
                        raise work_item.error
                else:
                    return None

        except Exception as e:
            self._logger.error(f"Error getting work result for {work_id}: {e}")
            return None

    def get_distribution_metrics(self) -> Dict[str, Any]:
        """Get work distribution metrics."""
        try:
            with self._lock:
                active_count = len(self._active_work)
                completed_count = len(self._completed_work)

                # Calculate success rate
                success_count = sum(1 for item in self._completed_work.values() if item.success)
                success_rate = success_count / max(1, completed_count) * 100

                # Calculate average execution time
                execution_times = [
                    item.execution_time for item in self._completed_work.values()
                    if item.execution_time
                ]
                avg_execution_time = sum(execution_times) / max(1, len(execution_times))

                return {
                    'total_distributed': self._total_distributed,
                    'active_work': active_count,
                    'completed_work': completed_count,
                    'distribution_failures': self._distribution_failures,
                    'success_rate': success_rate,
                    'average_execution_time': avg_execution_time,
                    'rebalance_count': self._rebalance_count,
                    'pool_loads': {
                        pool_type.value: {
                            'load_factor': info.load_factor,
                            'active_threads': info.active_threads,
                            'max_threads': info.max_threads,
                            'queue_size': info.queue_size,
                            'avg_execution_time': info.avg_execution_time,
                            'total_completed': info.total_completed,
                            'total_failed': info.total_failed
                        }
                        for pool_type, info in self._pool_loads.items()
                    }
                }

        except Exception as e:
            self._logger.error(f"Error getting distribution metrics: {e}")
            return {}

    def set_affinity(self, hint: str, pool_type: ThreadPoolType) -> bool:
        """Set affinity mapping for a hint."""
        try:
            with self._lock:
                self._affinity_map[hint] = pool_type
                self._logger.debug(f"Set affinity: {hint} -> {pool_type.value}")
                return True

        except Exception as e:
            self._logger.error(f"Error setting affinity: {e}")
            return False

    def remove_affinity(self, hint: str) -> bool:
        """Remove affinity mapping for a hint."""
        try:
            with self._lock:
                if hint in self._affinity_map:
                    del self._affinity_map[hint]
                    self._logger.debug(f"Removed affinity for: {hint}")
                    return True
                return False

        except Exception as e:
            self._logger.error(f"Error removing affinity: {e}")
            return False

    def get_pool_recommendations(self, workload_type: WorkloadType) -> List[ThreadPoolType]:
        """Get recommended pools for a workload type."""
        try:
            recommendations = []

            # Get all available pools
            available_pools = self._get_available_pools()

            # Score each pool for the workload type
            pool_scores = []
            for pool_type in available_pools:
                affinity_score = self._calculate_workload_affinity(workload_type, pool_type)
                load_info = self._pool_loads.get(pool_type)

                if load_info:
                    load_score = 1.0 - load_info.load_factor
                    combined_score = affinity_score * 0.7 + load_score * 0.3
                else:
                    combined_score = affinity_score

                pool_scores.append((pool_type, combined_score))

            # Sort by score and return
            pool_scores.sort(key=lambda x: x[1], reverse=True)
            recommendations = [pool_type for pool_type, _ in pool_scores]

            return recommendations

        except Exception as e:
            self._logger.error(f"Error getting pool recommendations: {e}")
            return []

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


# Convenience functions
def create_work_item(task: ThreadTask,
                    workload_type: WorkloadType = WorkloadType.MIXED,
                    estimated_duration: Optional[float] = None,
                    affinity_hints: Optional[List[str]] = None) -> WorkItem:
    """
    Convenience function to create a WorkItem.

    Args:
        task: Thread task to wrap
        workload_type: Type of workload
        estimated_duration: Estimated execution time
        affinity_hints: Pool affinity hints

    Returns:
        WorkItem instance
    """
    return WorkItem(
        work_id=str(uuid.uuid4()),
        task=task,
        workload_type=workload_type,
        estimated_duration=estimated_duration,
        affinity_hints=affinity_hints or []
    )
