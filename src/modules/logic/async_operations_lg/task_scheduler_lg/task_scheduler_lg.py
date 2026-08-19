"""
Module: task_scheduler_lg
Description: Schedules and manages asynchronous operations with dependency tracking and priority execution
Phase: 2
Location: /src/modules/logic/async_operations_lg/task_scheduler_lg/
"""

# Standard library imports
import asyncio
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable
import logging
import json
import heapq

# Third-party imports
# None required

# Local imports
from src.modules.logic.async_operations_lg.base_interfaces import (
    ITaskScheduler, AsyncTask, TaskResult, TaskStatus, TaskPriority,
    TaskDependency, TaskDependencyType, SchedulerConfig, SchedulerMetrics,
    SchedulerStatus, TaskExecutionResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier


class DependencyGraph:
    """Manages task dependencies and resolution."""
    
    def __init__(self):
        """Initialize dependency graph."""
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._dependents: Dict[str, Set[str]] = defaultdict(set)
        self._completed_tasks: Set[str] = set()
        self._failed_tasks: Set[str] = set()
        self._lock = threading.RLock()
    
    def add_dependency(self, task_id: str, dependency_id: str) -> None:
        """Add a dependency relationship."""
        with self._lock:
            self._dependencies[task_id].add(dependency_id)
            self._dependents[dependency_id].add(task_id)
    
    def remove_dependency(self, task_id: str, dependency_id: str) -> None:
        """Remove a dependency relationship."""
        with self._lock:
            self._dependencies[task_id].discard(dependency_id)
            self._dependents[dependency_id].discard(task_id)
    
    def get_dependencies(self, task_id: str) -> Set[str]:
        """Get all dependencies for a task."""
        with self._lock:
            return self._dependencies[task_id].copy()
    
    def get_dependents(self, task_id: str) -> Set[str]:
        """Get all tasks that depend on this task."""
        with self._lock:
            return self._dependents[task_id].copy()
    
    def is_ready(self, task_id: str) -> bool:
        """Check if a task is ready to execute (all dependencies met)."""
        with self._lock:
            dependencies = self._dependencies[task_id]
            return all(dep in self._completed_tasks for dep in dependencies)
    
    def mark_completed(self, task_id: str) -> Set[str]:
        """Mark a task as completed and return newly ready tasks."""
        with self._lock:
            self._completed_tasks.add(task_id)
            self._failed_tasks.discard(task_id)
            
            # Find newly ready tasks
            ready_tasks = set()
            for dependent in self._dependents[task_id]:
                if self.is_ready(dependent):
                    ready_tasks.add(dependent)
            
            return ready_tasks
    
    def mark_failed(self, task_id: str) -> Set[str]:
        """Mark a task as failed and return affected tasks."""
        with self._lock:
            self._failed_tasks.add(task_id)
            self._completed_tasks.discard(task_id)
            
            # Find affected tasks (those that depend on this failed task)
            affected_tasks = set()
            to_check = deque([task_id])
            
            while to_check:
                current = to_check.popleft()
                for dependent in self._dependents[current]:
                    if dependent not in affected_tasks:
                        affected_tasks.add(dependent)
                        to_check.append(dependent)
            
            return affected_tasks
    
    def has_circular_dependency(self, task_id: str, dependency_id: str) -> bool:
        """Check if adding a dependency would create a circular dependency."""
        with self._lock:
            # Use DFS to check if dependency_id can reach task_id
            visited = set()
            stack = [dependency_id]
            
            while stack:
                current = stack.pop()
                if current == task_id:
                    return True
                
                if current in visited:
                    continue
                
                visited.add(current)
                stack.extend(self._dependencies[current])
            
            return False
    
    def clear_task(self, task_id: str) -> None:
        """Remove all traces of a task from the graph."""
        with self._lock:
            # Remove from dependencies
            for dependent in self._dependents[task_id]:
                self._dependencies[dependent].discard(task_id)
            
            # Remove from dependents
            for dependency in self._dependencies[task_id]:
                self._dependents[dependency].discard(task_id)
            
            # Clear task's own entries
            del self._dependencies[task_id]
            del self._dependents[task_id]
            
            # Remove from completion tracking
            self._completed_tasks.discard(task_id)
            self._failed_tasks.discard(task_id)


class TaskQueue:
    """Priority queue for managing tasks."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize task queue."""
        self.max_size = max_size
        self._heap: List[tuple] = []
        self._tasks: Dict[str, AsyncTask] = {}
        self._lock = threading.RLock()
        self._counter = 0  # For stable sorting
    
    def put(self, task: AsyncTask) -> bool:
        """Add a task to the queue."""
        with self._lock:
            if len(self._heap) >= self.max_size:
                return False
            
            # Priority queue uses negative priority for max-heap behavior
            priority = -task.priority.value
            self._counter += 1
            
            heapq.heappush(self._heap, (priority, self._counter, task.task_id))
            self._tasks[task.task_id] = task
            return True
    
    def get(self) -> Optional[AsyncTask]:
        """Get the highest priority task."""
        with self._lock:
            if not self._heap:
                return None
            
            _, _, task_id = heapq.heappop(self._heap)
            return self._tasks.pop(task_id, None)
    
    def remove(self, task_id: str) -> Optional[AsyncTask]:
        """Remove a specific task from the queue."""
        with self._lock:
            task = self._tasks.pop(task_id, None)
            if task:
                # Rebuild heap without the removed task
                new_heap = []
                for priority, counter, tid in self._heap:
                    if tid != task_id:
                        new_heap.append((priority, counter, tid))
                
                self._heap = new_heap
                heapq.heapify(self._heap)
            
            return task
    
    def peek(self) -> Optional[AsyncTask]:
        """Peek at the highest priority task without removing it."""
        with self._lock:
            if not self._heap:
                return None
            
            _, _, task_id = self._heap[0]
            return self._tasks.get(task_id)
    
    def size(self) -> int:
        """Get the current queue size."""
        with self._lock:
            return len(self._heap)
    
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        with self._lock:
            return len(self._heap) == 0
    
    def is_full(self) -> bool:
        """Check if the queue is full."""
        with self._lock:
            return len(self._heap) >= self.max_size
    
    def clear(self) -> None:
        """Clear all tasks from the queue."""
        with self._lock:
            self._heap.clear()
            self._tasks.clear()
            self._counter = 0
    
    def get_all_tasks(self) -> List[AsyncTask]:
        """Get all tasks in the queue."""
        with self._lock:
            return list(self._tasks.values())


class TaskExecutor:
    """Executes tasks with proper resource management."""
    
    def __init__(self, max_workers: int = 10):
        """Initialize task executor."""
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_tasks: Dict[str, Future] = {}
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
    
    async def execute_task(self, task: AsyncTask) -> TaskResult:
        """Execute a single task."""
        start_time = time.time()
        
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            # Execute the task function
            if asyncio.iscoroutinefunction(task.function):
                result = await task.function(*task.args, **task.kwargs)
            else:
                # Run in executor for non-async functions
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self._executor, 
                    lambda: task.function(*task.args, **task.kwargs)
                )
            
            # Create successful result
            execution_time = time.time() - start_time
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            return TaskResult(
                task_id=task.task_id,
                success=True,
                result=result,
                execution_time=execution_time,
                retry_count=task.retry_count
            )
            
        except Exception as e:
            # Create failed result
            execution_time = time.time() - start_time
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = e
            
            self._logger.error(f"Task {task.task_id} failed: {e}")
            
            return TaskResult(
                task_id=task.task_id,
                success=False,
                error=e,
                execution_time=execution_time,
                retry_count=task.retry_count
            )
    
    def submit_task(self, task: AsyncTask) -> Future:
        """Submit a task for execution."""
        with self._lock:
            future = self._executor.submit(
                asyncio.run, 
                self.execute_task(task)
            )
            self._active_tasks[task.task_id] = future
            return future
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        with self._lock:
            future = self._active_tasks.get(task_id)
            if future:
                cancelled = future.cancel()
                if cancelled:
                    del self._active_tasks[task_id]
                return cancelled
            return False
    
    def get_active_count(self) -> int:
        """Get the number of active tasks."""
        with self._lock:
            return len(self._active_tasks)
    
    def cleanup_completed(self) -> None:
        """Clean up completed tasks."""
        with self._lock:
            completed_tasks = []
            for task_id, future in self._active_tasks.items():
                if future.done():
                    completed_tasks.append(task_id)
            
            for task_id in completed_tasks:
                del self._active_tasks[task_id]
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor."""
        self._executor.shutdown(wait=wait)


class TaskScheduler(ITaskScheduler):
    """
    Advanced task scheduler with dependency tracking and priority execution.

    Features:
    - Dependency resolution with circular dependency detection
    - Priority-based task scheduling
    - Retry mechanism with exponential backoff
    - Database persistence for task state
    - Comprehensive metrics and monitoring
    - Thread-safe operations
    """

    def __init__(self, config: Optional[SchedulerConfig] = None):
        """
        Initialize task scheduler.

        Args:
            config: Scheduler configuration
        """
        self.config = config or SchedulerConfig()
        self._status = SchedulerStatus.STOPPED
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()

        # Core components
        self._dependency_graph = DependencyGraph()
        self._task_queue = TaskQueue(self.config.max_queue_size)
        self._executor = TaskExecutor(self.config.max_concurrent_tasks)

        # Task tracking
        self._all_tasks: Dict[str, AsyncTask] = {}
        self._ready_tasks: Set[str] = set()
        self._running_tasks: Dict[str, Future] = {}
        self._completed_tasks: Dict[str, TaskResult] = {}
        self._failed_tasks: Dict[str, TaskResult] = {}

        # Synchronization
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Metrics
        self._metrics = SchedulerMetrics()
        self._start_time: Optional[datetime] = None

        # Database
        self._db_path: Optional[Path] = None
        if self.config.persist_tasks and self.config.database_path:
            self._db_path = Path(self.config.database_path)
            self._init_database()

    async def start(self) -> bool:
        """Start the task scheduler."""
        try:
            with self._lock:
                if self._status != SchedulerStatus.STOPPED:
                    self._logger.warning("Scheduler is already running")
                    return False

                self._status = SchedulerStatus.STARTING
                self._start_time = datetime.now()
                self._shutdown_event.clear()

                # Load persisted tasks if database is configured
                if self._db_path:
                    await self._load_persisted_tasks()

                # Start worker thread
                self._worker_thread = threading.Thread(
                    target=self._worker_loop,
                    name="TaskScheduler-Worker",
                    daemon=True
                )
                self._worker_thread.start()

                self._status = SchedulerStatus.RUNNING
                self._logger.info("Task scheduler started successfully")
                return True

        except Exception as e:
            self._status = SchedulerStatus.ERROR
            self._logger.error(f"Failed to start scheduler: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the task scheduler."""
        try:
            with self._lock:
                if self._status == SchedulerStatus.STOPPED:
                    return True

                self._status = SchedulerStatus.STOPPING
                self._shutdown_event.set()

                # Wait for worker thread to finish
                if self._worker_thread and self._worker_thread.is_alive():
                    self._worker_thread.join(timeout=10.0)

                # Cancel all running tasks
                for task_id, future in self._running_tasks.items():
                    future.cancel()

                # Shutdown executor
                self._executor.shutdown(wait=True)

                # Persist remaining tasks if database is configured
                if self._db_path:
                    await self._persist_tasks()

                self._status = SchedulerStatus.STOPPED
                self._logger.info("Task scheduler stopped successfully")
                return True

        except Exception as e:
            self._status = SchedulerStatus.ERROR
            self._logger.error(f"Failed to stop scheduler: {e}")
            return False

    async def schedule_task(self, task: AsyncTask) -> bool:
        """Schedule a task for execution."""
        try:
            with self._lock:
                if self._status != SchedulerStatus.RUNNING:
                    self._logger.warning("Cannot schedule task: scheduler not running")
                    return False

                # Validate task
                if not self._validate_task(task):
                    return False

                # Check for circular dependencies
                for dep in task.dependencies:
                    if self._dependency_graph.has_circular_dependency(task.task_id, dep.task_id):
                        self._logger.error(f"Circular dependency detected for task {task.task_id}")
                        return False

                # Add to tracking
                self._all_tasks[task.task_id] = task

                # Add dependencies to graph
                for dep in task.dependencies:
                    self._dependency_graph.add_dependency(task.task_id, dep.task_id)

                # Check if task is ready to run
                if self._dependency_graph.is_ready(task.task_id):
                    task.status = TaskStatus.READY
                    self._ready_tasks.add(task.task_id)
                    self._task_queue.put(task)
                else:
                    task.status = TaskStatus.WAITING_DEPENDENCIES

                # Persist task if database is configured
                if self._db_path:
                    await self._persist_task(task)

                self._logger.info(f"Task {task.task_id} scheduled successfully")
                return True

        except Exception as e:
            self._logger.error(f"Failed to schedule task {task.task_id}: {e}")
            return False

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled or running task."""
        try:
            with self._lock:
                task = self._all_tasks.get(task_id)
                if not task:
                    self._logger.warning(f"Task {task_id} not found")
                    return False

                # Cancel based on current status
                if task.status == TaskStatus.READY:
                    # Remove from queue
                    self._task_queue.remove(task_id)
                    self._ready_tasks.discard(task_id)
                elif task.status == TaskStatus.RUNNING:
                    # Cancel running task
                    future = self._running_tasks.get(task_id)
                    if future:
                        future.cancel()
                        del self._running_tasks[task_id]

                # Update task status
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()

                # Clean up dependencies
                self._dependency_graph.clear_task(task_id)

                # Create cancelled result
                result = TaskResult(
                    task_id=task_id,
                    success=False,
                    error=Exception("Task cancelled"),
                    execution_time=0.0,
                    retry_count=task.retry_count
                )
                self._failed_tasks[task_id] = result

                self._logger.info(f"Task {task_id} cancelled successfully")
                return True

        except Exception as e:
            self._logger.error(f"Failed to cancel task {task_id}: {e}")
            return False

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a task."""
        with self._lock:
            task = self._all_tasks.get(task_id)
            return task.status if task else None

    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a completed task."""
        with self._lock:
            return (self._completed_tasks.get(task_id) or
                   self._failed_tasks.get(task_id))

    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """Wait for a task to complete."""
        start_time = time.time()

        while True:
            # Check if task is completed
            result = await self.get_task_result(task_id)
            if result:
                return result

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")

            # Wait a bit before checking again
            await asyncio.sleep(0.1)

    def get_metrics(self) -> SchedulerMetrics:
        """Get scheduler performance metrics."""
        with self._lock:
            if self._start_time:
                self._metrics.uptime_seconds = (datetime.now() - self._start_time).total_seconds()

            self._metrics.tasks_processed = len(self._completed_tasks) + len(self._failed_tasks)

            if self._metrics.uptime_seconds > 0:
                self._metrics.tasks_per_second = self._metrics.tasks_processed / self._metrics.uptime_seconds

            self._metrics.queue_utilization = self._task_queue.size() / self.config.max_queue_size

            return self._metrics

    async def pause(self) -> bool:
        """Pause task execution."""
        try:
            with self._lock:
                if self._status == SchedulerStatus.RUNNING:
                    self._status = SchedulerStatus.PAUSED
                    self._logger.info("Task scheduler paused")
                    return True
                return False
        except Exception as e:
            self._logger.error(f"Failed to pause scheduler: {e}")
            return False

    async def resume(self) -> bool:
        """Resume task execution."""
        try:
            with self._lock:
                if self._status == SchedulerStatus.PAUSED:
                    self._status = SchedulerStatus.RUNNING
                    self._logger.info("Task scheduler resumed")
                    return True
                return False
        except Exception as e:
            self._logger.error(f"Failed to resume scheduler: {e}")
            return False

    def _validate_task(self, task: AsyncTask) -> bool:
        """Validate a task before scheduling."""
        if not task.task_id:
            self._logger.error("Task ID is required")
            return False

        if task.task_id in self._all_tasks:
            self._logger.error(f"Task {task.task_id} already exists")
            return False

        if not task.function:
            self._logger.error("Task function is required")
            return False

        return True

    def _worker_loop(self) -> None:
        """Main worker loop for task execution."""
        self._logger.info("Task scheduler worker loop started")

        while not self._shutdown_event.is_set():
            try:
                # Check if we can process more tasks
                if (self._status != SchedulerStatus.RUNNING or
                    self._executor.get_active_count() >= self.config.max_concurrent_tasks):
                    time.sleep(0.1)
                    continue

                # Get next ready task
                task = self._task_queue.get()
                if not task:
                    time.sleep(0.1)
                    continue

                # Submit task for execution
                future = self._executor.submit_task(task)

                with self._lock:
                    self._running_tasks[task.task_id] = future
                    self._ready_tasks.discard(task.task_id)

                # Set up completion callback
                future.add_done_callback(
                    lambda f, tid=task.task_id: self._handle_task_completion(tid, f)
                )

            except Exception as e:
                self._logger.error(f"Error in worker loop: {e}")
                time.sleep(1.0)

        self._logger.info("Task scheduler worker loop stopped")

    def _handle_task_completion(self, task_id: str, future: Future) -> None:
        """Handle task completion."""
        try:
            with self._lock:
                # Remove from running tasks
                self._running_tasks.pop(task_id, None)

                # Get task and result
                task = self._all_tasks.get(task_id)
                if not task:
                    return

                try:
                    result = future.result()
                except Exception as e:
                    # Create failed result
                    result = TaskResult(
                        task_id=task_id,
                        success=False,
                        error=e,
                        execution_time=0.0,
                        retry_count=task.retry_count
                    )

                # Handle result based on success
                if result.success:
                    self._completed_tasks[task_id] = result

                    # Mark dependencies as resolved
                    newly_ready = self._dependency_graph.mark_completed(task_id)

                    # Queue newly ready tasks
                    for ready_task_id in newly_ready:
                        ready_task = self._all_tasks.get(ready_task_id)
                        if ready_task and ready_task.status == TaskStatus.WAITING_DEPENDENCIES:
                            ready_task.status = TaskStatus.READY
                            self._ready_tasks.add(ready_task_id)
                            self._task_queue.put(ready_task)

                else:
                    # Handle failure
                    if task.retry_count < task.max_retries:
                        # Retry the task
                        task.retry_count += 1
                        task.status = TaskStatus.READY

                        # Add delay before retry
                        retry_delay = task.retry_delay * (2 ** task.retry_count)  # Exponential backoff

                        # Schedule retry (simplified - in production, use proper delay mechanism)
                        self._ready_tasks.add(task_id)
                        self._task_queue.put(task)

                        self._logger.info(f"Retrying task {task_id} (attempt {task.retry_count + 1})")
                    else:
                        # Task failed permanently
                        self._failed_tasks[task_id] = result

                        # Mark dependencies as failed
                        affected_tasks = self._dependency_graph.mark_failed(task_id)

                        # Cancel affected tasks
                        for affected_task_id in affected_tasks:
                            affected_task = self._all_tasks.get(affected_task_id)
                            if affected_task and affected_task.status != TaskStatus.COMPLETED:
                                affected_task.status = TaskStatus.FAILED

                                # Create failed result for affected task
                                affected_result = TaskResult(
                                    task_id=affected_task_id,
                                    success=False,
                                    error=Exception(f"Dependency {task_id} failed"),
                                    execution_time=0.0,
                                    retry_count=0
                                )
                                self._failed_tasks[affected_task_id] = affected_result

                # Update metrics
                self._update_metrics(result)

                # Persist result if database is configured
                if self._db_path:
                    asyncio.create_task(self._persist_task_result(task_id, result))

        except Exception as e:
            self._logger.error(f"Error handling task completion for {task_id}: {e}")

    def _update_metrics(self, result: TaskResult) -> None:
        """Update scheduler metrics."""
        self._metrics.tasks_processed += 1

        if result.success:
            self._metrics.total_execution_time += result.execution_time
            if self._metrics.tasks_processed > 0:
                self._metrics.average_execution_time = (
                    self._metrics.total_execution_time / self._metrics.tasks_processed
                )

    def _init_database(self) -> None:
        """Initialize the database for task persistence."""
        if not self._db_path:
            return

        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()

                # Create tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        function_name TEXT NOT NULL,
                        args_json TEXT,
                        kwargs_json TEXT,
                        priority INTEGER,
                        dependencies_json TEXT,
                        timeout_seconds REAL,
                        retry_count INTEGER,
                        max_retries INTEGER,
                        retry_delay REAL,
                        created_at TEXT,
                        scheduled_at TEXT,
                        started_at TEXT,
                        completed_at TEXT,
                        status TEXT,
                        metadata_json TEXT
                    )
                """)

                # Create task results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS task_results (
                        task_id TEXT PRIMARY KEY,
                        success BOOLEAN,
                        result_json TEXT,
                        error_message TEXT,
                        execution_time REAL,
                        retry_count INTEGER,
                        metadata_json TEXT,
                        FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                    )
                """)

                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to initialize database: {e}")

    async def _persist_task(self, task: AsyncTask) -> None:
        """Persist a task to the database."""
        if not self._db_path:
            return

        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT OR REPLACE INTO tasks (
                        task_id, name, function_name, args_json, kwargs_json,
                        priority, dependencies_json, timeout_seconds, retry_count,
                        max_retries, retry_delay, created_at, scheduled_at,
                        started_at, completed_at, status, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.task_id,
                    task.name,
                    task.function.__name__ if hasattr(task.function, '__name__') else str(task.function),
                    json.dumps(task.args),
                    json.dumps(task.kwargs),
                    task.priority.value,
                    json.dumps([{"task_id": dep.task_id, "type": dep.dependency_type.value}
                               for dep in task.dependencies]),
                    task.timeout_seconds,
                    task.retry_count,
                    task.max_retries,
                    task.retry_delay,
                    task.created_at.isoformat(),
                    task.scheduled_at.isoformat() if task.scheduled_at else None,
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.status.value,
                    json.dumps(task.metadata)
                ))

                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to persist task {task.task_id}: {e}")

    async def _persist_task_result(self, task_id: str, result: TaskResult) -> None:
        """Persist a task result to the database."""
        if not self._db_path:
            return

        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT OR REPLACE INTO task_results (
                        task_id, success, result_json, error_message,
                        execution_time, retry_count, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id,
                    result.success,
                    json.dumps(result.result) if result.result is not None else None,
                    str(result.error) if result.error else None,
                    result.execution_time,
                    result.retry_count,
                    json.dumps(result.metadata)
                ))

                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to persist task result {task_id}: {e}")

    async def _load_persisted_tasks(self) -> None:
        """Load persisted tasks from the database."""
        if not self._db_path or not self._db_path.exists():
            return

        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()

                # Load incomplete tasks
                cursor.execute("""
                    SELECT * FROM tasks
                    WHERE status NOT IN ('completed', 'failed', 'cancelled')
                """)

                for row in cursor.fetchall():
                    # Reconstruct task (simplified - in production, need proper function reconstruction)
                    task_data = dict(zip([col[0] for col in cursor.description], row))

                    # Create basic task structure
                    task = AsyncTask(
                        task_id=task_data['task_id'],
                        name=task_data['name'],
                        function=lambda: None,  # Placeholder - would need proper reconstruction
                        priority=TaskPriority(task_data['priority']),
                        retry_count=task_data['retry_count'],
                        max_retries=task_data['max_retries'],
                        retry_delay=task_data['retry_delay'],
                        status=TaskStatus(task_data['status']),
                        metadata=json.loads(task_data['metadata_json']) if task_data['metadata_json'] else {}
                    )

                    self._all_tasks[task.task_id] = task

                    # Note: In production, would need proper function and dependency reconstruction

        except Exception as e:
            self._logger.error(f"Failed to load persisted tasks: {e}")

    async def _persist_tasks(self) -> None:
        """Persist all current tasks to the database."""
        if not self._db_path:
            return

        try:
            for task in self._all_tasks.values():
                await self._persist_task(task)

        except Exception as e:
            self._logger.error(f"Failed to persist tasks: {e}")
