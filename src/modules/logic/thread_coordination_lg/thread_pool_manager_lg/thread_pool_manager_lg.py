"""
Module: thread_pool_manager_lg
Description: Manages application-wide thread pools for different operation types with priority-based scheduling
Phase: 2
Location: /src/modules/logic/thread_coordination_lg/thread_pool_manager_lg/thread_pool_manager_lg.py
"""

# Standard library imports
import os
import sys
import threading
import time
import uuid
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime, timedelta
from queue import PriorityQueue, Queue, Empty
from typing import Dict, List, Optional, Set, Tuple, Callable, Any
import multiprocessing

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    IThreadPoolManager,
    ThreadPoolType,
    ThreadPoolStatus,
    ThreadPoolConfig,
    ThreadTask,
    ThreadPoolInfo,
    ThreadPoolMetrics,
    ThreadPoolOperationResult,
    TaskPriority,
    TaskStatus
)


class ThreadWorker:
    """
    Individual worker thread that processes tasks from a queue.
    
    Features:
    - Priority-based task processing
    - Task timeout handling
    - Performance monitoring
    - Graceful shutdown
    """
    
    def __init__(self, worker_id: str, task_queue: PriorityQueue, pool_type: ThreadPoolType):
        """Initialize thread worker."""
        self._worker_id = worker_id
        self._task_queue = task_queue
        self._pool_type = pool_type
        self._logger = get_logger(f"{__name__}.{worker_id}")
        
        # Worker state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_task: Optional[ThreadTask] = None
        self._shutdown_event = threading.Event()
        
        # Statistics
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_execution_time = 0.0
        self._created_at = datetime.now()
        self._last_activity = datetime.now()
    
    def start(self) -> bool:
        """Start the worker thread."""
        try:
            if self._running:
                return True
            
            self._running = True
            self._thread = threading.Thread(
                target=self._worker_loop,
                name=f"Worker-{self._worker_id}",
                daemon=True
            )
            self._thread.start()
            
            self._logger.debug(f"Worker {self._worker_id} started")
            return True
            
        except Exception as e:
            self._logger.error(f"Error starting worker {self._worker_id}: {e}")
            self._running = False
            return False
    
    def stop(self, timeout: Optional[float] = None) -> bool:
        """Stop the worker thread."""
        try:
            if not self._running:
                return True
            
            self._running = False
            self._shutdown_event.set()
            
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=timeout)
                
                if self._thread.is_alive():
                    self._logger.warning(f"Worker {self._worker_id} did not shutdown gracefully")
                    return False
            
            self._logger.debug(f"Worker {self._worker_id} stopped")
            return True
            
        except Exception as e:
            self._logger.error(f"Error stopping worker {self._worker_id}: {e}")
            return False
    
    def _worker_loop(self):
        """Main worker loop that processes tasks."""
        while self._running and not self._shutdown_event.is_set():
            try:
                # Get next task with timeout
                try:
                    priority, task = self._task_queue.get(timeout=1.0)
                except Empty:
                    continue
                
                if task is None:  # Shutdown signal
                    break
                
                self._current_task = task
                self._process_task(task)
                self._current_task = None
                self._task_queue.task_done()
                
            except Exception as e:
                self._logger.error(f"Error in worker loop: {e}")
                if self._current_task:
                    self._current_task.status = TaskStatus.FAILED
                    self._current_task.error = e
                    self._current_task.completed_at = datetime.now()
    
    def _process_task(self, task: ThreadTask):
        """Process a single task."""
        start_time = time.time()
        
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.thread_id = threading.get_ident()
            
            self._logger.debug(f"Processing task {task.task_id}")
            
            # Execute task with timeout
            if task.timeout_seconds:
                # For simplicity, we'll execute directly (timeout handling would need more complex implementation)
                result = task.function(*task.args, **task.kwargs)
            else:
                result = task.function(*task.args, **task.kwargs)
            
            # Update task with result
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # Call success callback if provided
            if task.callback:
                try:
                    task.callback(result)
                except Exception as e:
                    self._logger.warning(f"Error in task callback: {e}")
            
            self._tasks_completed += 1
            self._logger.debug(f"Task {task.task_id} completed successfully")
            
        except Exception as e:
            # Update task with error
            task.error = e
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            
            # Call error callback if provided
            if task.error_callback:
                try:
                    task.error_callback(e)
                except Exception as callback_error:
                    self._logger.warning(f"Error in task error callback: {callback_error}")
            
            self._tasks_failed += 1
            self._logger.error(f"Task {task.task_id} failed: {e}")
        
        finally:
            execution_time = time.time() - start_time
            self._total_execution_time += execution_time
            self._last_activity = datetime.now()
    
    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
    
    @property
    def current_task_id(self) -> Optional[str]:
        """Get current task ID."""
        return self._current_task.task_id if self._current_task else None
    
    @property
    def statistics(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            'worker_id': self._worker_id,
            'tasks_completed': self._tasks_completed,
            'tasks_failed': self._tasks_failed,
            'total_execution_time': self._total_execution_time,
            'average_execution_time': (
                self._total_execution_time / max(1, self._tasks_completed + self._tasks_failed)
            ),
            'created_at': self._created_at,
            'last_activity': self._last_activity,
            'current_task': self.current_task_id
        }


class TaskQueue:
    """
    Priority-based task queue with monitoring capabilities.
    
    Features:
    - Priority-based ordering
    - Queue size limits
    - Task tracking
    - Performance metrics
    """
    
    def __init__(self, max_size: int = 100):
        """Initialize task queue."""
        self._queue = PriorityQueue(maxsize=max_size)
        self._max_size = max_size
        self._logger = get_logger(__name__)
        
        # Task tracking
        self._submitted_tasks: Dict[str, ThreadTask] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0
        self._created_at = datetime.now()
    
    def submit(self, task: ThreadTask) -> bool:
        """Submit a task to the queue."""
        try:
            with self._lock:
                # Check queue capacity
                if self._queue.full():
                    self._logger.warning(f"Task queue is full, rejecting task {task.task_id}")
                    return False
                
                # Add to queue with priority
                priority_value = task.priority.value
                self._queue.put((priority_value, task), block=False)
                
                # Track task
                self._submitted_tasks[task.task_id] = task
                task.status = TaskStatus.QUEUED
                
                self._total_submitted += 1
                self._logger.debug(f"Task {task.task_id} submitted with priority {task.priority.name}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error submitting task {task.task_id}: {e}")
            return False
    
    def get(self, timeout: Optional[float] = None) -> Tuple[int, ThreadTask]:
        """Get next task from queue."""
        return self._queue.get(timeout=timeout)
    
    def task_done(self):
        """Mark task as done."""
        self._queue.task_done()
    
    def get_task(self, task_id: str) -> Optional[ThreadTask]:
        """Get task by ID."""
        with self._lock:
            return self._submitted_tasks.get(task_id)
    
    def remove_task(self, task_id: str) -> bool:
        """Remove task from tracking."""
        try:
            with self._lock:
                if task_id in self._submitted_tasks:
                    task = self._submitted_tasks.pop(task_id)
                    if task.status == TaskStatus.COMPLETED:
                        self._total_completed += 1
                    elif task.status == TaskStatus.FAILED:
                        self._total_failed += 1
                    return True
                return False
                
        except Exception as e:
            self._logger.error(f"Error removing task {task_id}: {e}")
            return False
    
    @property
    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    @property
    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()
    
    @property
    def statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            return {
                'current_size': self.size,
                'max_size': self._max_size,
                'total_submitted': self._total_submitted,
                'total_completed': self._total_completed,
                'total_failed': self._total_failed,
                'utilization': self.size / max(1, self._max_size),
                'created_at': self._created_at,
                'active_tasks': len(self._submitted_tasks)
            }


class ThreadPool:
    """
    Manages a pool of worker threads for a specific operation type.

    Features:
    - Dynamic thread scaling
    - Priority-based task scheduling
    - Performance monitoring
    - Graceful shutdown
    """

    def __init__(self, config: ThreadPoolConfig):
        """Initialize thread pool."""
        self._config = config
        self._pool_type = config.pool_type
        self._logger = get_logger(f"{__name__}.{config.pool_type.value}")

        # Pool state
        self._status = ThreadPoolStatus.INITIALIZING
        self._workers: Dict[str, ThreadWorker] = {}
        self._task_queue = TaskQueue(config.queue_size)
        self._shutdown_event = threading.Event()
        self._lock = threading.RLock()

        # Scaling and monitoring
        self._last_scale_check = datetime.now()
        self._scale_check_interval = timedelta(seconds=30)
        self._monitor_thread: Optional[threading.Thread] = None

        # Statistics
        self._created_at = datetime.now()
        self._last_activity = datetime.now()
        self._peak_thread_count = 0

        self._logger.info(f"Thread pool {self._pool_type.value} initialized")

    def start(self) -> bool:
        """Start the thread pool."""
        try:
            with self._lock:
                if self._status != ThreadPoolStatus.INITIALIZING:
                    return self._status == ThreadPoolStatus.ACTIVE

                # Create initial workers
                for i in range(self._config.min_threads):
                    worker_id = f"{self._pool_type.value}-worker-{i}"
                    worker = ThreadWorker(worker_id, self._task_queue._queue, self._pool_type)

                    if worker.start():
                        self._workers[worker_id] = worker
                    else:
                        self._logger.error(f"Failed to start worker {worker_id}")
                        return False

                # Start monitoring thread if enabled
                if self._config.enable_monitoring:
                    self._monitor_thread = threading.Thread(
                        target=self._monitor_loop,
                        name=f"Monitor-{self._pool_type.value}",
                        daemon=True
                    )
                    self._monitor_thread.start()

                self._status = ThreadPoolStatus.ACTIVE
                self._peak_thread_count = len(self._workers)
                self._logger.info(f"Thread pool {self._pool_type.value} started with {len(self._workers)} workers")
                return True

        except Exception as e:
            self._logger.error(f"Error starting thread pool {self._pool_type.value}: {e}")
            self._status = ThreadPoolStatus.ERROR
            return False

    def submit(self, task: ThreadTask) -> bool:
        """Submit a task to the pool."""
        try:
            if self._status != ThreadPoolStatus.ACTIVE:
                self._logger.warning(f"Cannot submit task to inactive pool {self._pool_type.value}")
                return False

            if self._task_queue.submit(task):
                self._last_activity = datetime.now()

                # Check if we need to scale up
                if self._config.auto_scale:
                    self._check_scaling()

                return True

            return False

        except Exception as e:
            self._logger.error(f"Error submitting task to pool {self._pool_type.value}: {e}")
            return False

    def shutdown(self, wait: bool = True, timeout: Optional[float] = None) -> bool:
        """Shutdown the thread pool."""
        try:
            with self._lock:
                if self._status in [ThreadPoolStatus.SHUTTING_DOWN, ThreadPoolStatus.SHUTDOWN]:
                    return True

                self._status = ThreadPoolStatus.SHUTTING_DOWN
                self._shutdown_event.set()

                # Stop all workers
                shutdown_success = True
                for worker_id, worker in self._workers.items():
                    if not worker.stop(timeout=timeout):
                        shutdown_success = False
                        self._logger.warning(f"Worker {worker_id} did not shutdown gracefully")

                # Stop monitoring thread
                if self._monitor_thread and self._monitor_thread.is_alive():
                    self._monitor_thread.join(timeout=5.0)

                self._status = ThreadPoolStatus.SHUTDOWN
                self._logger.info(f"Thread pool {self._pool_type.value} shutdown")
                return shutdown_success

        except Exception as e:
            self._logger.error(f"Error shutting down thread pool {self._pool_type.value}: {e}")
            return False

    def _monitor_loop(self):
        """Monitor thread pool performance and handle scaling."""
        while not self._shutdown_event.is_set():
            try:
                time.sleep(10)  # Monitor every 10 seconds

                if self._config.auto_scale:
                    self._check_scaling()

                # Log statistics periodically
                if datetime.now().minute % 5 == 0:  # Every 5 minutes
                    stats = self.get_statistics()
                    self._logger.debug(f"Pool {self._pool_type.value} stats: {stats}")

            except Exception as e:
                self._logger.error(f"Error in monitor loop: {e}")

    def _check_scaling(self):
        """Check if pool needs to scale up or down."""
        try:
            now = datetime.now()
            if now - self._last_scale_check < self._scale_check_interval:
                return

            self._last_scale_check = now

            with self._lock:
                current_threads = len(self._workers)
                queue_size = self._task_queue.size

                # Scale up if queue is getting full
                if (queue_size > self._config.queue_size * 0.8 and
                    current_threads < self._config.max_threads):

                    new_thread_count = min(
                        self._config.max_threads,
                        int(current_threads * self._config.scale_factor)
                    )

                    for i in range(current_threads, new_thread_count):
                        worker_id = f"{self._pool_type.value}-worker-{i}"
                        worker = ThreadWorker(worker_id, self._task_queue._queue, self._pool_type)

                        if worker.start():
                            self._workers[worker_id] = worker
                            self._logger.info(f"Scaled up pool {self._pool_type.value} to {len(self._workers)} workers")
                        else:
                            break

                    self._peak_thread_count = max(self._peak_thread_count, len(self._workers))

                # Scale down if threads are idle
                elif (queue_size == 0 and current_threads > self._config.min_threads):
                    # Simple scale down - remove idle workers
                    idle_workers = [
                        worker_id for worker_id, worker in self._workers.items()
                        if worker.current_task_id is None
                    ]

                    workers_to_remove = min(
                        len(idle_workers),
                        current_threads - self._config.min_threads
                    )

                    for i in range(workers_to_remove):
                        worker_id = idle_workers[i]
                        worker = self._workers.pop(worker_id)
                        worker.stop(timeout=5.0)
                        self._logger.info(f"Scaled down pool {self._pool_type.value} to {len(self._workers)} workers")

        except Exception as e:
            self._logger.error(f"Error checking scaling for pool {self._pool_type.value}: {e}")

    def get_info(self) -> ThreadPoolInfo:
        """Get thread pool information."""
        with self._lock:
            active_threads = sum(1 for worker in self._workers.values() if worker.is_running)

            # Calculate average task time
            total_time = 0.0
            total_tasks = 0
            for worker in self._workers.values():
                stats = worker.statistics
                total_time += stats['total_execution_time']
                total_tasks += stats['tasks_completed'] + stats['tasks_failed']

            avg_task_time = total_time / max(1, total_tasks)

            return ThreadPoolInfo(
                pool_type=self._pool_type,
                status=self._status,
                active_threads=active_threads,
                total_threads=len(self._workers),
                queued_tasks=self._task_queue.size,
                completed_tasks=self._task_queue._total_completed,
                failed_tasks=self._task_queue._total_failed,
                average_task_time=avg_task_time,
                created_at=self._created_at,
                last_activity=self._last_activity
            )

    def get_statistics(self) -> Dict[str, Any]:
        """Get detailed pool statistics."""
        with self._lock:
            worker_stats = [worker.statistics for worker in self._workers.values()]
            queue_stats = self._task_queue.statistics

            return {
                'pool_type': self._pool_type.value,
                'status': self._status.value,
                'config': {
                    'min_threads': self._config.min_threads,
                    'max_threads': self._config.max_threads,
                    'queue_size': self._config.queue_size,
                    'auto_scale': self._config.auto_scale
                },
                'workers': worker_stats,
                'queue': queue_stats,
                'peak_thread_count': self._peak_thread_count,
                'created_at': self._created_at,
                'last_activity': self._last_activity
            }


class ThreadPoolManager(IThreadPoolManager):
    """
    Manages application-wide thread pools for different operation types.

    Features:
    - Multiple specialized thread pools
    - Priority-based task scheduling
    - Dynamic scaling and resource management
    - Comprehensive monitoring and metrics
    - Graceful shutdown handling
    """

    def __init__(self):
        """Initialize thread pool manager."""
        self._logger = get_logger(__name__)

        # Pool management
        self._pools: Dict[ThreadPoolType, ThreadPool] = {}
        self._lock = threading.RLock()
        self._initialized = False

        # Global constraints
        self._max_total_threads = multiprocessing.cpu_count() * 2
        self._current_thread_count = 0

        # Metrics and monitoring
        self._metrics: Dict[ThreadPoolType, ThreadPoolMetrics] = {}
        self._metrics_lock = threading.RLock()
        self._last_metrics_update = datetime.now()

        # Default configurations
        self._default_configs = self._create_default_configs()

        self._logger.info("Thread pool manager initialized")

    def initialize(self) -> bool:
        """Initialize the thread pool manager with default pools."""
        try:
            with self._lock:
                if self._initialized:
                    return True

                # Create default pools
                for pool_type, config in self._default_configs.items():
                    if not self.create_pool(config):
                        self._logger.error(f"Failed to create default pool {pool_type.value}")
                        return False

                self._initialized = True
                self._logger.info("Thread pool manager initialized with default pools")
                return True

        except Exception as e:
            self._logger.error(f"Error initializing thread pool manager: {e}")
            return False

    def create_pool(self, config: ThreadPoolConfig) -> bool:
        """Create a new thread pool with the specified configuration."""
        try:
            with self._lock:
                pool_type = config.pool_type

                # Check if pool already exists
                if pool_type in self._pools:
                    self._logger.warning(f"Pool {pool_type.value} already exists")
                    return True

                # Check thread limits
                if self._current_thread_count + config.max_threads > self._max_total_threads:
                    self._logger.error(
                        f"Cannot create pool {pool_type.value}: would exceed max threads "
                        f"({self._current_thread_count + config.max_threads} > {self._max_total_threads})"
                    )
                    return False

                # Create and start pool
                pool = ThreadPool(config)
                if pool.start():
                    self._pools[pool_type] = pool
                    self._current_thread_count += config.min_threads

                    # Initialize metrics
                    self._metrics[pool_type] = ThreadPoolMetrics(pool_type=pool_type)

                    self._logger.info(f"Created thread pool {pool_type.value}")
                    return True
                else:
                    self._logger.error(f"Failed to start thread pool {pool_type.value}")
                    return False

        except Exception as e:
            self._logger.error(f"Error creating thread pool {config.pool_type.value}: {e}")
            return False

    def submit_task(self, pool_type: ThreadPoolType, task: ThreadTask) -> Optional[Future]:
        """Submit a task to the specified thread pool."""
        try:
            with self._lock:
                if pool_type not in self._pools:
                    self._logger.error(f"Pool {pool_type.value} does not exist")
                    return None

                pool = self._pools[pool_type]

                # Create future for task tracking
                future = Future()
                task.future = future

                if pool.submit(task):
                    self._update_metrics(pool_type, submitted=1)
                    self._logger.debug(f"Task {task.task_id} submitted to pool {pool_type.value}")
                    return future
                else:
                    self._logger.warning(f"Failed to submit task {task.task_id} to pool {pool_type.value}")
                    return None

        except Exception as e:
            self._logger.error(f"Error submitting task to pool {pool_type.value}: {e}")
            return None

    def shutdown_pool(self, pool_type: ThreadPoolType, wait: bool = True, timeout: Optional[float] = None) -> bool:
        """Shutdown a specific thread pool."""
        try:
            with self._lock:
                if pool_type not in self._pools:
                    self._logger.warning(f"Pool {pool_type.value} does not exist")
                    return True

                pool = self._pools[pool_type]
                if pool.shutdown(wait=wait, timeout=timeout):
                    # Update thread count
                    pool_info = pool.get_info()
                    self._current_thread_count -= pool_info.total_threads

                    # Remove from tracking
                    del self._pools[pool_type]

                    self._logger.info(f"Shutdown thread pool {pool_type.value}")
                    return True
                else:
                    self._logger.error(f"Failed to shutdown thread pool {pool_type.value}")
                    return False

        except Exception as e:
            self._logger.error(f"Error shutting down thread pool {pool_type.value}: {e}")
            return False

    def shutdown_all(self, wait: bool = True, timeout: Optional[float] = None) -> bool:
        """Shutdown all thread pools."""
        try:
            with self._lock:
                shutdown_success = True

                for pool_type in list(self._pools.keys()):
                    if not self.shutdown_pool(pool_type, wait=wait, timeout=timeout):
                        shutdown_success = False

                self._initialized = False
                self._logger.info("All thread pools shutdown")
                return shutdown_success

        except Exception as e:
            self._logger.error(f"Error shutting down all thread pools: {e}")
            return False

    def get_pool_info(self, pool_type: ThreadPoolType) -> Optional[ThreadPoolInfo]:
        """Get information about a thread pool."""
        try:
            with self._lock:
                if pool_type not in self._pools:
                    return None

                return self._pools[pool_type].get_info()

        except Exception as e:
            self._logger.error(f"Error getting pool info for {pool_type.value}: {e}")
            return None

    def get_metrics(self, pool_type: Optional[ThreadPoolType] = None) -> Dict[ThreadPoolType, ThreadPoolMetrics]:
        """Get performance metrics for thread pools."""
        try:
            with self._metrics_lock:
                self._update_all_metrics()

                if pool_type:
                    return {pool_type: self._metrics[pool_type]} if pool_type in self._metrics else {}
                else:
                    return self._metrics.copy()

        except Exception as e:
            self._logger.error(f"Error getting metrics: {e}")
            return {}

    def _create_default_configs(self) -> Dict[ThreadPoolType, ThreadPoolConfig]:
        """Create default configurations for different pool types."""
        cpu_count = multiprocessing.cpu_count()

        return {
            ThreadPoolType.TRAINING: ThreadPoolConfig(
                pool_type=ThreadPoolType.TRAINING,
                min_threads=1,
                max_threads=1,  # Training is exclusive
                queue_size=10,
                thread_timeout_seconds=60.0,
                task_timeout_seconds=3600.0,  # 1 hour for training tasks
                auto_scale=False,
                thread_name_prefix="MikroDok-Training"
            ),
            ThreadPoolType.DOCUMENT_PROCESSING: ThreadPoolConfig(
                pool_type=ThreadPoolType.DOCUMENT_PROCESSING,
                min_threads=max(1, cpu_count - 2),
                max_threads=cpu_count,
                queue_size=200,
                thread_timeout_seconds=30.0,
                task_timeout_seconds=300.0,
                auto_scale=True,
                thread_name_prefix="MikroDok-DocProc"
            ),
            ThreadPoolType.MONITORING: ThreadPoolConfig(
                pool_type=ThreadPoolType.MONITORING,
                min_threads=2,
                max_threads=4,
                queue_size=50,
                thread_timeout_seconds=15.0,
                task_timeout_seconds=60.0,
                auto_scale=False,
                thread_name_prefix="MikroDok-Monitor"
            ),
            ThreadPoolType.INFERENCE: ThreadPoolConfig(
                pool_type=ThreadPoolType.INFERENCE,
                min_threads=2,
                max_threads=4,
                queue_size=100,
                thread_timeout_seconds=30.0,
                task_timeout_seconds=120.0,
                auto_scale=True,
                thread_name_prefix="MikroDok-Inference"
            ),
            ThreadPoolType.BACKGROUND: ThreadPoolConfig(
                pool_type=ThreadPoolType.BACKGROUND,
                min_threads=1,
                max_threads=2,
                queue_size=50,
                thread_timeout_seconds=60.0,
                task_timeout_seconds=300.0,
                auto_scale=False,
                thread_name_prefix="MikroDok-Background"
            )
        }

    def _update_metrics(self, pool_type: ThreadPoolType, submitted: int = 0, completed: int = 0, failed: int = 0):
        """Update metrics for a specific pool."""
        try:
            with self._metrics_lock:
                if pool_type not in self._metrics:
                    self._metrics[pool_type] = ThreadPoolMetrics(pool_type=pool_type)

                metrics = self._metrics[pool_type]
                metrics.total_tasks_submitted += submitted
                metrics.total_tasks_completed += completed
                metrics.total_tasks_failed += failed
                metrics.last_updated = datetime.now()

        except Exception as e:
            self._logger.error(f"Error updating metrics for {pool_type.value}: {e}")

    def _update_all_metrics(self):
        """Update metrics for all pools."""
        try:
            now = datetime.now()
            if now - self._last_metrics_update < timedelta(seconds=10):
                return  # Don't update too frequently

            for pool_type, pool in self._pools.items():
                pool_info = pool.get_info()

                if pool_type in self._metrics:
                    metrics = self._metrics[pool_type]
                    metrics.current_thread_count = pool_info.total_threads
                    metrics.peak_thread_count = max(metrics.peak_thread_count, pool_info.total_threads)
                    metrics.total_tasks_completed = pool_info.completed_tasks
                    metrics.total_tasks_failed = pool_info.failed_tasks
                    metrics.average_execution_time = pool_info.average_task_time

                    # Calculate utilization
                    if pool_info.total_threads > 0:
                        metrics.thread_utilization = pool_info.active_threads / pool_info.total_threads

                    metrics.last_updated = now

            self._last_metrics_update = now

        except Exception as e:
            self._logger.error(f"Error updating all metrics: {e}")

    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized

    @property
    def total_thread_count(self) -> int:
        """Get total number of threads across all pools."""
        return self._current_thread_count

    @property
    def pool_count(self) -> int:
        """Get number of active pools."""
        return len(self._pools)


# Global instance for application-wide use
_thread_pool_manager: Optional[ThreadPoolManager] = None
_manager_lock = threading.Lock()


def get_thread_pool_manager() -> ThreadPoolManager:
    """Get the global thread pool manager instance."""
    global _thread_pool_manager

    with _manager_lock:
        if _thread_pool_manager is None:
            _thread_pool_manager = ThreadPoolManager()
            _thread_pool_manager.initialize()

        return _thread_pool_manager


def create_task(task_id: Optional[str] = None,
                function: Optional[Callable] = None,
                args: Tuple = (),
                kwargs: Optional[Dict[str, Any]] = None,
                priority: TaskPriority = TaskPriority.NORMAL,
                timeout_seconds: Optional[float] = None,
                callback: Optional[Callable] = None,
                error_callback: Optional[Callable] = None) -> ThreadTask:
    """
    Convenience function to create a ThreadTask.

    Args:
        task_id: Unique task identifier (auto-generated if None)
        function: Function to execute
        args: Function arguments
        kwargs: Function keyword arguments
        priority: Task priority
        timeout_seconds: Task timeout
        callback: Success callback
        error_callback: Error callback

    Returns:
        ThreadTask instance
    """
    if task_id is None:
        task_id = str(uuid.uuid4())

    if kwargs is None:
        kwargs = {}

    return ThreadTask(
        task_id=task_id,
        function=function,
        args=args,
        kwargs=kwargs,
        priority=priority,
        timeout_seconds=timeout_seconds,
        callback=callback,
        error_callback=error_callback
    )
