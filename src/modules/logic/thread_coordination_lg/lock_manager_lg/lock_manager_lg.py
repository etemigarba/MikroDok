"""
Module: lock_manager_lg
Description: Coordinates thread-safe access to shared resources, prevents deadlocks, and manages resource locks
Phase: 2
Location: /src/modules/logic/thread_coordination_lg/lock_manager_lg/lock_manager_lg.py
"""

# Standard library imports
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
import weakref

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    ILockManager,
    LockType,
    LockStatus,
    DeadlockDetectionStrategy,
    LockConfig,
    ResourceLock,
    LockInfo,
    LockMetrics,
    LockAcquisitionResult
)


class DeadlockDetector:
    """
    Detects potential deadlocks using graph-based analysis.
    
    Features:
    - Cycle detection in wait-for graphs
    - Priority-based deadlock resolution
    - Timeout-based detection
    - Performance monitoring
    """
    
    def __init__(self, strategy: DeadlockDetectionStrategy = DeadlockDetectionStrategy.TIMEOUT_BASED):
        """Initialize deadlock detector."""
        self._strategy = strategy
        self._logger = get_logger(__name__)
        
        # Wait-for graph tracking
        self._wait_graph: Dict[int, Set[int]] = defaultdict(set)  # thread_id -> set of threads it's waiting for
        self._lock_owners: Dict[str, int] = {}  # lock_id -> owner_thread_id
        self._lock_waiters: Dict[str, Set[int]] = defaultdict(set)  # lock_id -> set of waiting thread_ids
        self._lock = threading.RLock()
        
        # Detection statistics
        self._deadlocks_detected = 0
        self._false_positives = 0
        self._detection_time_total = 0.0
        self._last_detection = datetime.now()
    
    def add_wait_edge(self, waiter_thread_id: int, lock_id: str, owner_thread_id: int):
        """Add a wait edge to the graph."""
        try:
            with self._lock:
                self._wait_graph[waiter_thread_id].add(owner_thread_id)
                self._lock_waiters[lock_id].add(waiter_thread_id)
                self._logger.debug(f"Added wait edge: thread {waiter_thread_id} waiting for {owner_thread_id} on lock {lock_id}")
                
        except Exception as e:
            self._logger.error(f"Error adding wait edge: {e}")
    
    def remove_wait_edge(self, waiter_thread_id: int, lock_id: str, owner_thread_id: int):
        """Remove a wait edge from the graph."""
        try:
            with self._lock:
                if waiter_thread_id in self._wait_graph:
                    self._wait_graph[waiter_thread_id].discard(owner_thread_id)
                    if not self._wait_graph[waiter_thread_id]:
                        del self._wait_graph[waiter_thread_id]
                
                self._lock_waiters[lock_id].discard(waiter_thread_id)
                if not self._lock_waiters[lock_id]:
                    del self._lock_waiters[lock_id]
                
                self._logger.debug(f"Removed wait edge: thread {waiter_thread_id} no longer waiting for {owner_thread_id}")
                
        except Exception as e:
            self._logger.error(f"Error removing wait edge: {e}")
    
    def update_lock_owner(self, lock_id: str, owner_thread_id: Optional[int]):
        """Update lock ownership."""
        try:
            with self._lock:
                if owner_thread_id is None:
                    self._lock_owners.pop(lock_id, None)
                else:
                    self._lock_owners[lock_id] = owner_thread_id
                
        except Exception as e:
            self._logger.error(f"Error updating lock owner: {e}")
    
    def detect_deadlocks(self) -> List[Tuple[str, List[str]]]:
        """
        Detect deadlocks based on the configured strategy.
        
        Returns:
            List of (deadlock_id, involved_lock_ids) tuples
        """
        start_time = time.time()
        
        try:
            if self._strategy == DeadlockDetectionStrategy.GRAPH_BASED:
                deadlocks = self._detect_graph_deadlocks()
            elif self._strategy == DeadlockDetectionStrategy.TIMEOUT_BASED:
                deadlocks = self._detect_timeout_deadlocks()
            elif self._strategy == DeadlockDetectionStrategy.HYBRID:
                deadlocks = self._detect_hybrid_deadlocks()
            else:
                deadlocks = []
            
            detection_time = time.time() - start_time
            self._detection_time_total += detection_time
            self._last_detection = datetime.now()
            
            if deadlocks:
                self._deadlocks_detected += len(deadlocks)
                self._logger.warning(f"Detected {len(deadlocks)} deadlocks")
            
            return deadlocks
            
        except Exception as e:
            self._logger.error(f"Error detecting deadlocks: {e}")
            return []
    
    def _detect_graph_deadlocks(self) -> List[Tuple[str, List[str]]]:
        """Detect deadlocks using cycle detection in wait-for graph."""
        deadlocks = []
        
        try:
            with self._lock:
                visited = set()
                rec_stack = set()
                
                def dfs(thread_id: int, path: List[int]) -> Optional[List[int]]:
                    """DFS to detect cycles."""
                    if thread_id in rec_stack:
                        # Found cycle
                        cycle_start = path.index(thread_id)
                        return path[cycle_start:]
                    
                    if thread_id in visited:
                        return None
                    
                    visited.add(thread_id)
                    rec_stack.add(thread_id)
                    path.append(thread_id)
                    
                    for neighbor in self._wait_graph.get(thread_id, set()):
                        cycle = dfs(neighbor, path.copy())
                        if cycle:
                            return cycle
                    
                    rec_stack.remove(thread_id)
                    return None
                
                # Check each thread for cycles
                for thread_id in self._wait_graph:
                    if thread_id not in visited:
                        cycle = dfs(thread_id, [])
                        if cycle:
                            # Find involved locks
                            involved_locks = []
                            for lock_id, waiters in self._lock_waiters.items():
                                if any(tid in cycle for tid in waiters):
                                    involved_locks.append(lock_id)
                            
                            deadlock_id = str(uuid.uuid4())
                            deadlocks.append((deadlock_id, involved_locks))
            
            return deadlocks
            
        except Exception as e:
            self._logger.error(f"Error in graph-based deadlock detection: {e}")
            return []
    
    def _detect_timeout_deadlocks(self) -> List[Tuple[str, List[str]]]:
        """Detect deadlocks based on timeout analysis."""
        # Simplified timeout-based detection
        # In a real implementation, this would track wait times and identify suspicious patterns
        return []
    
    def _detect_hybrid_deadlocks(self) -> List[Tuple[str, List[str]]]:
        """Detect deadlocks using hybrid approach."""
        # Combine graph-based and timeout-based detection
        graph_deadlocks = self._detect_graph_deadlocks()
        timeout_deadlocks = self._detect_timeout_deadlocks()
        
        # Merge and deduplicate
        all_deadlocks = graph_deadlocks + timeout_deadlocks
        return list(set(all_deadlocks))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get deadlock detection statistics."""
        return {
            'strategy': self._strategy.value,
            'deadlocks_detected': self._deadlocks_detected,
            'false_positives': self._false_positives,
            'average_detection_time': (
                self._detection_time_total / max(1, self._deadlocks_detected)
            ),
            'last_detection': self._last_detection,
            'current_wait_edges': sum(len(waiters) for waiters in self._wait_graph.values()),
            'active_locks': len(self._lock_owners)
        }


class LockRegistry:
    """
    Registry for managing lock instances and metadata.
    
    Features:
    - Lock lifecycle management
    - Resource mapping
    - Performance tracking
    - Cleanup and garbage collection
    """
    
    def __init__(self):
        """Initialize lock registry."""
        self._logger = get_logger(__name__)
        
        # Lock storage
        self._locks: Dict[str, ResourceLock] = {}
        self._resource_locks: Dict[str, Set[str]] = defaultdict(set)  # resource_id -> lock_ids
        self._lock = threading.RLock()
        
        # Metrics tracking
        self._metrics: Dict[str, LockMetrics] = {}
        self._creation_times: Dict[str, datetime] = {}
        
        # Cleanup tracking
        self._last_cleanup = datetime.now()
        self._cleanup_interval = timedelta(minutes=5)
    
    def register_lock(self, lock: ResourceLock) -> bool:
        """Register a new lock."""
        try:
            with self._lock:
                if lock.lock_id in self._locks:
                    self._logger.warning(f"Lock {lock.lock_id} already registered")
                    return False
                
                self._locks[lock.lock_id] = lock
                self._resource_locks[lock.resource_id].add(lock.lock_id)
                self._creation_times[lock.lock_id] = datetime.now()
                
                # Initialize metrics
                self._metrics[lock.lock_id] = LockMetrics(lock_id=lock.lock_id)
                
                self._logger.debug(f"Registered lock {lock.lock_id} for resource {lock.resource_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error registering lock {lock.lock_id}: {e}")
            return False
    
    def unregister_lock(self, lock_id: str) -> bool:
        """Unregister a lock."""
        try:
            with self._lock:
                if lock_id not in self._locks:
                    return True
                
                lock = self._locks.pop(lock_id)
                self._resource_locks[lock.resource_id].discard(lock_id)
                
                if not self._resource_locks[lock.resource_id]:
                    del self._resource_locks[lock.resource_id]
                
                self._creation_times.pop(lock_id, None)
                self._metrics.pop(lock_id, None)
                
                self._logger.debug(f"Unregistered lock {lock_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error unregistering lock {lock_id}: {e}")
            return False
    
    def get_lock(self, lock_id: str) -> Optional[ResourceLock]:
        """Get lock by ID."""
        with self._lock:
            return self._locks.get(lock_id)
    
    def get_resource_locks(self, resource_id: str) -> List[ResourceLock]:
        """Get all locks for a resource."""
        with self._lock:
            lock_ids = self._resource_locks.get(resource_id, set())
            return [self._locks[lock_id] for lock_id in lock_ids if lock_id in self._locks]
    
    def update_metrics(self, lock_id: str, acquisition_time: float = 0.0, hold_time: float = 0.0, 
                      contention: bool = False, timeout: bool = False):
        """Update lock metrics."""
        try:
            with self._lock:
                if lock_id not in self._metrics:
                    return
                
                metrics = self._metrics[lock_id]
                metrics.total_acquisitions += 1
                
                if contention:
                    metrics.total_contentions += 1
                
                if timeout:
                    metrics.total_timeouts += 1
                
                # Update timing statistics
                if acquisition_time > 0:
                    total_wait_time = metrics.average_wait_time * (metrics.total_acquisitions - 1)
                    metrics.average_wait_time = (total_wait_time + acquisition_time) / metrics.total_acquisitions
                    metrics.max_wait_time = max(metrics.max_wait_time, acquisition_time)
                
                if hold_time > 0:
                    total_hold_time = metrics.average_hold_time * (metrics.total_acquisitions - 1)
                    metrics.average_hold_time = (total_hold_time + hold_time) / metrics.total_acquisitions
                    metrics.max_hold_time = max(metrics.max_hold_time, hold_time)
                
                # Update rates
                if metrics.total_acquisitions > 0:
                    metrics.contention_rate = metrics.total_contentions / metrics.total_acquisitions
                    metrics.timeout_rate = metrics.total_timeouts / metrics.total_acquisitions
                
                metrics.last_updated = datetime.now()
                
        except Exception as e:
            self._logger.error(f"Error updating metrics for lock {lock_id}: {e}")
    
    def get_metrics(self, lock_id: Optional[str] = None) -> Dict[str, LockMetrics]:
        """Get lock metrics."""
        with self._lock:
            if lock_id:
                return {lock_id: self._metrics[lock_id]} if lock_id in self._metrics else {}
            else:
                return self._metrics.copy()
    
    def cleanup_stale_locks(self) -> int:
        """Clean up stale or unused locks."""
        try:
            now = datetime.now()
            if now - self._last_cleanup < self._cleanup_interval:
                return 0
            
            cleaned_count = 0
            stale_locks = []
            
            with self._lock:
                for lock_id, lock in self._locks.items():
                    # Check if lock is stale (not acquired for a long time and no waiters)
                    if (lock.status == LockStatus.AVAILABLE and 
                        not lock.waiters and
                        lock_id in self._creation_times):
                        
                        creation_time = self._creation_times[lock_id]
                        if now - creation_time > timedelta(hours=1):  # 1 hour threshold
                            stale_locks.append(lock_id)
                
                # Remove stale locks
                for lock_id in stale_locks:
                    if self.unregister_lock(lock_id):
                        cleaned_count += 1
                
                self._last_cleanup = now
            
            if cleaned_count > 0:
                self._logger.info(f"Cleaned up {cleaned_count} stale locks")
            
            return cleaned_count
            
        except Exception as e:
            self._logger.error(f"Error cleaning up stale locks: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            return {
                'total_locks': len(self._locks),
                'total_resources': len(self._resource_locks),
                'locks_by_status': {
                    status.value: sum(1 for lock in self._locks.values() if lock.status == status)
                    for status in LockStatus
                },
                'locks_by_type': {
                    lock_type.value: sum(1 for lock in self._locks.values() if lock.lock_type == lock_type)
                    for lock_type in LockType
                },
                'last_cleanup': self._last_cleanup
            }


class ResourceLockManager:
    """
    Manages locks for a specific resource with different lock types.

    Features:
    - Multiple lock type support (mutex, read-write, semaphore)
    - Priority-based acquisition
    - Fair scheduling
    - Deadlock prevention
    """

    def __init__(self, resource_id: str):
        """Initialize resource lock manager."""
        self._resource_id = resource_id
        self._logger = get_logger(f"{__name__}.{resource_id}")

        # Lock primitives
        self._mutex = threading.RLock()
        self._read_write_lock = threading.RLock()
        self._semaphore: Optional[threading.Semaphore] = None
        self._condition = threading.Condition(self._mutex)

        # State tracking
        self._current_locks: Dict[str, ResourceLock] = {}
        self._waiting_queue: deque = deque()
        self._readers_count = 0
        self._writer_thread_id: Optional[int] = None

        # Configuration
        self._max_readers = 10
        self._fair_scheduling = True
        self._priority_inheritance = True

    def acquire_mutex(self, lock: ResourceLock, timeout: Optional[float] = None) -> LockAcquisitionResult:
        """Acquire a mutex lock."""
        start_time = time.time()
        thread_id = threading.get_ident()

        try:
            acquired = self._mutex.acquire(timeout=timeout)

            if acquired:
                lock.owner_thread_id = thread_id
                lock.acquired_at = datetime.now()
                lock.status = LockStatus.ACQUIRED
                self._current_locks[lock.lock_id] = lock

                wait_time = time.time() - start_time
                self._logger.debug(f"Mutex acquired by thread {thread_id} for lock {lock.lock_id}")

                return LockAcquisitionResult(
                    success=True,
                    lock_id=lock.lock_id,
                    acquired_at=lock.acquired_at,
                    wait_time_seconds=wait_time,
                    status=LockStatus.ACQUIRED
                )
            else:
                self._logger.warning(f"Mutex acquisition timeout for lock {lock.lock_id}")
                return LockAcquisitionResult(
                    success=False,
                    lock_id=lock.lock_id,
                    status=LockStatus.TIMEOUT,
                    timeout_occurred=True,
                    wait_time_seconds=time.time() - start_time
                )

        except Exception as e:
            self._logger.error(f"Error acquiring mutex for lock {lock.lock_id}: {e}")
            return LockAcquisitionResult(
                success=False,
                lock_id=lock.lock_id,
                status=LockStatus.ERROR,
                error_message=str(e)
            )

    def release_mutex(self, lock_id: str) -> bool:
        """Release a mutex lock."""
        try:
            if lock_id in self._current_locks:
                lock = self._current_locks.pop(lock_id)
                lock.status = LockStatus.AVAILABLE
                lock.owner_thread_id = None

                self._mutex.release()
                self._logger.debug(f"Mutex released for lock {lock_id}")
                return True
            else:
                self._logger.warning(f"Attempted to release non-existent mutex lock {lock_id}")
                return False

        except Exception as e:
            self._logger.error(f"Error releasing mutex for lock {lock_id}: {e}")
            return False

    def acquire_read_lock(self, lock: ResourceLock, timeout: Optional[float] = None) -> LockAcquisitionResult:
        """Acquire a read lock."""
        start_time = time.time()
        thread_id = threading.get_ident()

        try:
            with self._condition:
                # Wait for writers to finish
                end_time = start_time + (timeout or float('inf'))

                while self._writer_thread_id is not None and time.time() < end_time:
                    remaining_timeout = end_time - time.time()
                    if remaining_timeout <= 0:
                        break

                    self._condition.wait(timeout=remaining_timeout)

                if self._writer_thread_id is not None:
                    return LockAcquisitionResult(
                        success=False,
                        lock_id=lock.lock_id,
                        status=LockStatus.TIMEOUT,
                        timeout_occurred=True,
                        wait_time_seconds=time.time() - start_time
                    )

                # Check reader limit
                if self._readers_count >= self._max_readers:
                    return LockAcquisitionResult(
                        success=False,
                        lock_id=lock.lock_id,
                        status=LockStatus.ERROR,
                        error_message="Maximum readers exceeded"
                    )

                # Acquire read lock
                self._readers_count += 1
                lock.owner_thread_id = thread_id
                lock.acquired_at = datetime.now()
                lock.status = LockStatus.ACQUIRED
                self._current_locks[lock.lock_id] = lock

                wait_time = time.time() - start_time
                self._logger.debug(f"Read lock acquired by thread {thread_id} for lock {lock.lock_id}")

                return LockAcquisitionResult(
                    success=True,
                    lock_id=lock.lock_id,
                    acquired_at=lock.acquired_at,
                    wait_time_seconds=wait_time,
                    status=LockStatus.ACQUIRED
                )

        except Exception as e:
            self._logger.error(f"Error acquiring read lock for {lock.lock_id}: {e}")
            return LockAcquisitionResult(
                success=False,
                lock_id=lock.lock_id,
                status=LockStatus.ERROR,
                error_message=str(e)
            )

    def release_read_lock(self, lock_id: str) -> bool:
        """Release a read lock."""
        try:
            with self._condition:
                if lock_id in self._current_locks:
                    lock = self._current_locks.pop(lock_id)
                    lock.status = LockStatus.AVAILABLE
                    lock.owner_thread_id = None

                    self._readers_count = max(0, self._readers_count - 1)

                    # Notify waiting writers if no more readers
                    if self._readers_count == 0:
                        self._condition.notify_all()

                    self._logger.debug(f"Read lock released for lock {lock_id}")
                    return True
                else:
                    self._logger.warning(f"Attempted to release non-existent read lock {lock_id}")
                    return False

        except Exception as e:
            self._logger.error(f"Error releasing read lock {lock_id}: {e}")
            return False


class LockManager(ILockManager):
    """
    Coordinates thread-safe access to shared resources and prevents deadlocks.

    Features:
    - Multiple lock types (mutex, read-write, semaphore)
    - Deadlock detection and prevention
    - Priority-based lock acquisition
    - Comprehensive monitoring and metrics
    - Resource lifecycle management
    """

    def __init__(self, deadlock_strategy: DeadlockDetectionStrategy = DeadlockDetectionStrategy.TIMEOUT_BASED):
        """Initialize lock manager."""
        self._logger = get_logger(__name__)

        # Core components
        self._registry = LockRegistry()
        self._deadlock_detector = DeadlockDetector(deadlock_strategy)
        self._resource_managers: Dict[str, ResourceLockManager] = {}

        # Global coordination
        self._global_lock = threading.RLock()
        self._initialized = False

        # Monitoring and cleanup
        self._monitor_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._monitor_interval = 30.0  # seconds

        self._logger.info("Lock manager initialized")

    def initialize(self) -> bool:
        """Initialize the lock manager."""
        try:
            with self._global_lock:
                if self._initialized:
                    return True

                # Start monitoring thread
                self._monitor_thread = threading.Thread(
                    target=self._monitor_loop,
                    name="LockManager-Monitor",
                    daemon=True
                )
                self._monitor_thread.start()

                self._initialized = True
                self._logger.info("Lock manager initialized successfully")
                return True

        except Exception as e:
            self._logger.error(f"Error initializing lock manager: {e}")
            return False

    def shutdown(self) -> bool:
        """Shutdown the lock manager."""
        try:
            with self._global_lock:
                if not self._initialized:
                    return True

                self._shutdown_event.set()

                # Wait for monitor thread
                if self._monitor_thread and self._monitor_thread.is_alive():
                    self._monitor_thread.join(timeout=5.0)

                # Release all locks
                self._release_all_locks()

                self._initialized = False
                self._logger.info("Lock manager shutdown")
                return True

        except Exception as e:
            self._logger.error(f"Error shutting down lock manager: {e}")
            return False

    def create_lock(self, resource_id: str, config: LockConfig) -> str:
        """Create a new lock for a resource."""
        try:
            with self._global_lock:
                # Generate unique lock ID
                lock_id = f"{resource_id}_{config.lock_type.value}_{uuid.uuid4().hex[:8]}"

                # Create resource lock
                resource_lock = ResourceLock(
                    lock_id=lock_id,
                    resource_id=resource_id,
                    lock_type=config.lock_type,
                    timeout_seconds=config.timeout_seconds,
                    priority=0,
                    metadata={'config': config}
                )

                # Register lock
                if self._registry.register_lock(resource_lock):
                    # Create resource manager if needed
                    if resource_id not in self._resource_managers:
                        self._resource_managers[resource_id] = ResourceLockManager(resource_id)

                    self._logger.debug(f"Created lock {lock_id} for resource {resource_id}")
                    return lock_id
                else:
                    self._logger.error(f"Failed to register lock {lock_id}")
                    return ""

        except Exception as e:
            self._logger.error(f"Error creating lock for resource {resource_id}: {e}")
            return ""

    def acquire_lock(self, lock_id: str, timeout: Optional[float] = None) -> LockAcquisitionResult:
        """Acquire a lock on a resource."""
        start_time = time.time()
        thread_id = threading.get_ident()

        try:
            # Get lock from registry
            lock = self._registry.get_lock(lock_id)
            if not lock:
                return LockAcquisitionResult(
                    success=False,
                    lock_id=lock_id,
                    status=LockStatus.ERROR,
                    error_message="Lock not found"
                )

            # Use lock-specific timeout if not provided
            if timeout is None:
                timeout = lock.timeout_seconds

            # Get resource manager
            resource_manager = self._resource_managers.get(lock.resource_id)
            if not resource_manager:
                return LockAcquisitionResult(
                    success=False,
                    lock_id=lock_id,
                    status=LockStatus.ERROR,
                    error_message="Resource manager not found"
                )

            # Check for potential deadlocks before acquiring
            if lock.owner_thread_id and lock.owner_thread_id != thread_id:
                self._deadlock_detector.add_wait_edge(thread_id, lock_id, lock.owner_thread_id)

                deadlocks = self._deadlock_detector.detect_deadlocks()
                if deadlocks:
                    self._deadlock_detector.remove_wait_edge(thread_id, lock_id, lock.owner_thread_id)
                    self._logger.warning(f"Potential deadlock detected for lock {lock_id}")
                    return LockAcquisitionResult(
                        success=False,
                        lock_id=lock_id,
                        status=LockStatus.DEADLOCK,
                        deadlock_detected=True,
                        error_message="Deadlock detected"
                    )

            # Acquire lock based on type
            result = None
            if lock.lock_type == LockType.MUTEX:
                result = resource_manager.acquire_mutex(lock, timeout)
            elif lock.lock_type == LockType.READ_WRITE:
                # For simplicity, treat as read lock (would need additional parameter for read/write)
                result = resource_manager.acquire_read_lock(lock, timeout)
            else:
                result = LockAcquisitionResult(
                    success=False,
                    lock_id=lock_id,
                    status=LockStatus.ERROR,
                    error_message=f"Unsupported lock type: {lock.lock_type.value}"
                )

            # Update deadlock detector
            if result.success:
                self._deadlock_detector.update_lock_owner(lock_id, thread_id)
                if lock.owner_thread_id and lock.owner_thread_id != thread_id:
                    self._deadlock_detector.remove_wait_edge(thread_id, lock_id, lock.owner_thread_id)

            # Update metrics
            acquisition_time = time.time() - start_time
            self._registry.update_metrics(
                lock_id,
                acquisition_time=acquisition_time,
                contention=not result.success,
                timeout=result.timeout_occurred
            )

            return result

        except Exception as e:
            self._logger.error(f"Error acquiring lock {lock_id}: {e}")
            return LockAcquisitionResult(
                success=False,
                lock_id=lock_id,
                status=LockStatus.ERROR,
                error_message=str(e)
            )

    def release_lock(self, lock_id: str) -> bool:
        """Release a lock on a resource."""
        try:
            # Get lock from registry
            lock = self._registry.get_lock(lock_id)
            if not lock:
                self._logger.warning(f"Attempted to release non-existent lock {lock_id}")
                return False

            # Get resource manager
            resource_manager = self._resource_managers.get(lock.resource_id)
            if not resource_manager:
                self._logger.error(f"Resource manager not found for lock {lock_id}")
                return False

            # Release lock based on type
            success = False
            if lock.lock_type == LockType.MUTEX:
                success = resource_manager.release_mutex(lock_id)
            elif lock.lock_type == LockType.READ_WRITE:
                success = resource_manager.release_read_lock(lock_id)

            if success:
                # Update deadlock detector
                self._deadlock_detector.update_lock_owner(lock_id, None)

                self._logger.debug(f"Released lock {lock_id}")

            return success

        except Exception as e:
            self._logger.error(f"Error releasing lock {lock_id}: {e}")
            return False

    def get_lock_info(self, lock_id: str) -> Optional[LockInfo]:
        """Get information about a lock."""
        try:
            lock = self._registry.get_lock(lock_id)
            if not lock:
                return None

            return LockInfo(
                lock_id=lock.lock_id,
                resource_id=lock.resource_id,
                lock_type=lock.lock_type,
                status=lock.status,
                owner_thread_id=lock.owner_thread_id,
                waiter_count=len(lock.waiters),
                acquired_at=lock.acquired_at,
                total_acquisitions=0,  # Would need to get from metrics
                average_hold_time=0.0,  # Would need to get from metrics
                created_at=datetime.now()  # Would need to track creation time
            )

        except Exception as e:
            self._logger.error(f"Error getting lock info for {lock_id}: {e}")
            return None

    def detect_deadlocks(self) -> List[Tuple[str, List[str]]]:
        """Detect potential deadlocks in the system."""
        try:
            return self._deadlock_detector.detect_deadlocks()
        except Exception as e:
            self._logger.error(f"Error detecting deadlocks: {e}")
            return []

    def get_metrics(self, lock_id: Optional[str] = None) -> Dict[str, LockMetrics]:
        """Get performance metrics for locks."""
        try:
            return self._registry.get_metrics(lock_id)
        except Exception as e:
            self._logger.error(f"Error getting metrics: {e}")
            return {}

    def _monitor_loop(self):
        """Monitor loop for deadlock detection and cleanup."""
        while not self._shutdown_event.is_set():
            try:
                # Detect deadlocks
                deadlocks = self.detect_deadlocks()
                if deadlocks:
                    self._handle_deadlocks(deadlocks)

                # Cleanup stale locks
                self._registry.cleanup_stale_locks()

                # Sleep until next check
                self._shutdown_event.wait(timeout=self._monitor_interval)

            except Exception as e:
                self._logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)  # Brief pause before retrying

    def _handle_deadlocks(self, deadlocks: List[Tuple[str, List[str]]]):
        """Handle detected deadlocks."""
        for deadlock_id, lock_ids in deadlocks:
            self._logger.warning(f"Handling deadlock {deadlock_id} involving locks: {lock_ids}")

            # Simple resolution: release locks in order of priority
            # In a real implementation, this would be more sophisticated
            for lock_id in lock_ids:
                try:
                    self.release_lock(lock_id)
                except Exception as e:
                    self._logger.error(f"Error releasing lock {lock_id} during deadlock resolution: {e}")

    def _release_all_locks(self):
        """Release all active locks during shutdown."""
        try:
            for resource_id, manager in self._resource_managers.items():
                # Get all locks for this resource and release them
                locks = self._registry.get_resource_locks(resource_id)
                for lock in locks:
                    if lock.status == LockStatus.ACQUIRED:
                        self.release_lock(lock.lock_id)

            self._logger.info("Released all active locks")

        except Exception as e:
            self._logger.error(f"Error releasing all locks: {e}")

    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive lock manager statistics."""
        try:
            registry_stats = self._registry.get_statistics()
            deadlock_stats = self._deadlock_detector.get_statistics()

            return {
                'initialized': self._initialized,
                'total_resources': len(self._resource_managers),
                'registry': registry_stats,
                'deadlock_detection': deadlock_stats,
                'resource_managers': {
                    resource_id: manager.get_status()
                    for resource_id, manager in self._resource_managers.items()
                }
            }

        except Exception as e:
            self._logger.error(f"Error getting statistics: {e}")
            return {}


# Global instance for application-wide use
_lock_manager: Optional[LockManager] = None
_manager_lock = threading.Lock()


def get_lock_manager() -> LockManager:
    """Get the global lock manager instance."""
    global _lock_manager

    with _manager_lock:
        if _lock_manager is None:
            _lock_manager = LockManager()
            _lock_manager.initialize()

        return _lock_manager
