"""
Module: task_scheduler_lg
Description: Background task scheduling, execution, priority management, and dependency handling with async support
Phase: 4
Location: /src/modules/logic/background_services_lg/task_scheduler_lg/
"""

# Standard library imports
import asyncio
import heapq
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Any, Tuple
import concurrent.futures
import weakref

# Local imports
from ..base_interfaces import (
    ITaskScheduler, BackgroundTask, TaskResult, TaskStatus, TaskPriority,
    TaskSchedulerConfig, TaskExecutionResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class TaskQueue:
    """
    Priority-based task queue with dependency support.
    
    Features:
    - Priority-based scheduling
    - Task dependency management
    - Thread-safe operations
    - Task timeout handling
    """
    
    def __init__(self):
        """Initialize task queue."""
        self._logger = get_logger(__name__)
        self._queue: List[Tuple[int, float, str, BackgroundTask]] = []  # (priority, timestamp, task_id, task)
        self._tasks: Dict[str, BackgroundTask] = {}
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)  # task_id -> dependencies
        self._dependents: Dict[str, Set[str]] = defaultdict(set)   # task_id -> dependents
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._counter = 0  # For stable sorting
    
    def add_task(self, task: BackgroundTask) -> bool:
        """Add a task to the queue."""
        try:
            with self._condition:
                if task.task_id in self._tasks:
                    self._logger.warning(f"Task {task.task_id} already in queue")
                    return False
                
                # Store task
                self._tasks[task.task_id] = task
                
                # Add dependencies
                for dep_id in task.dependencies:
                    self._dependencies[task.task_id].add(dep_id)
                    self._dependents[dep_id].add(task.task_id)
                
                # Add to priority queue if ready to run
                if self._is_ready_to_run(task.task_id):
                    self._add_to_priority_queue(task)
                
                task.status = TaskStatus.QUEUED
                self._condition.notify_all()
                
                self._logger.debug(f"Added task {task.task_id} to queue")
                return True
                
        except Exception as e:
            self._logger.error(f"Error adding task {task.task_id}: {e}")
            return False
    
    def get_next_task(self, timeout: Optional[float] = None) -> Optional[BackgroundTask]:
        """Get the next task to execute."""
        try:
            with self._condition:
                end_time = time.time() + timeout if timeout else None
                
                while not self._queue:
                    if end_time and time.time() >= end_time:
                        return None
                    
                    wait_time = end_time - time.time() if end_time else None
                    self._condition.wait(timeout=wait_time)
                
                # Get highest priority task
                _, _, task_id, task = heapq.heappop(self._queue)
                
                # Verify task is still ready
                if not self._is_ready_to_run(task_id):
                    # Task dependencies changed, skip it
                    return self.get_next_task(timeout)
                
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
                
                self._logger.debug(f"Retrieved task {task_id} from queue")
                return task
                
        except Exception as e:
            self._logger.error(f"Error getting next task: {e}")
            return None
    
    def complete_task(self, task_id: str, result: TaskResult) -> None:
        """Mark a task as completed and check dependents."""
        try:
            with self._condition:
                task = self._tasks.get(task_id)
                if not task:
                    return
                
                task.status = result.status
                task.completed_at = datetime.now()
                
                # If task completed successfully, check dependents
                if result.status == TaskStatus.COMPLETED:
                    for dependent_id in self._dependents[task_id]:
                        if self._is_ready_to_run(dependent_id):
                            dependent_task = self._tasks[dependent_id]
                            self._add_to_priority_queue(dependent_task)
                
                # Clean up dependencies
                for dep_id in self._dependencies[task_id]:
                    self._dependents[dep_id].discard(task_id)
                
                self._dependencies[task_id].clear()
                self._condition.notify_all()
                
                self._logger.debug(f"Completed task {task_id} with status {result.status.value}")
                
        except Exception as e:
            self._logger.error(f"Error completing task {task_id}: {e}")
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the queue."""
        try:
            with self._condition:
                task = self._tasks.pop(task_id, None)
                if not task:
                    return False
                
                # Remove from priority queue (mark as cancelled)
                task.status = TaskStatus.CANCELLED
                
                # Clean up dependencies
                for dep_id in self._dependencies[task_id]:
                    self._dependents[dep_id].discard(task_id)
                
                for dependent_id in self._dependents[task_id]:
                    self._dependencies[dependent_id].discard(task_id)
                
                self._dependencies[task_id].clear()
                self._dependents[task_id].clear()
                
                self._condition.notify_all()
                
                self._logger.debug(f"Removed task {task_id} from queue")
                return True
                
        except Exception as e:
            self._logger.error(f"Error removing task {task_id}: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get a task by ID."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[BackgroundTask]:
        """List tasks in the queue."""
        with self._lock:
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return tasks
    
    def _is_ready_to_run(self, task_id: str) -> bool:
        """Check if a task is ready to run (all dependencies completed)."""
        dependencies = self._dependencies[task_id]
        for dep_id in dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    def _add_to_priority_queue(self, task: BackgroundTask) -> None:
        """Add task to priority queue."""
        # Use negative priority for max-heap behavior
        priority = -task.priority.value
        timestamp = time.time()
        self._counter += 1
        
        heapq.heappush(self._queue, (priority, timestamp, self._counter, task))
        task.status = TaskStatus.QUEUED


class TaskExecutor:
    """
    Executes background tasks with timeout and retry support.
    
    Features:
    - Async task execution
    - Timeout handling
    - Retry logic
    - Resource monitoring
    - Error handling
    """
    
    def __init__(self, max_workers: int = 5):
        """Initialize task executor."""
        self._logger = get_logger(__name__)
        self._max_workers = max_workers
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._lock = threading.RLock()
    
    async def execute_task(self, task: BackgroundTask) -> TaskResult:
        """Execute a background task."""
        start_time = datetime.now()
        
        try:
            self._logger.info(f"Executing task {task.task_id}: {task.name}")
            
            # Create task result
            result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.RUNNING
            )
            
            # Execute with timeout
            if task.timeout:
                try:
                    task_result = await asyncio.wait_for(
                        self._run_task_function(task),
                        timeout=task.timeout.total_seconds()
                    )
                    result.result = task_result
                    result.status = TaskStatus.COMPLETED
                    
                except asyncio.TimeoutError:
                    self._logger.warning(f"Task {task.task_id} timed out")
                    result.status = TaskStatus.FAILED
                    result.error = TimeoutError(f"Task timed out after {task.timeout}")
                    
            else:
                task_result = await self._run_task_function(task)
                result.result = task_result
                result.status = TaskStatus.COMPLETED
            
            # Calculate execution time
            result.execution_time = datetime.now() - start_time
            
            self._logger.info(f"Task {task.task_id} completed with status {result.status.value}")
            return result
            
        except Exception as e:
            self._logger.error(f"Error executing task {task.task_id}: {e}")
            
            result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=e,
                execution_time=datetime.now() - start_time
            )
            return result
    
    async def _run_task_function(self, task: BackgroundTask) -> Any:
        """Run the task function."""
        loop = asyncio.get_event_loop()
        
        # Run in thread pool to avoid blocking
        if asyncio.iscoroutinefunction(task.function):
            return await task.function(*task.args, **task.kwargs)
        else:
            return await loop.run_in_executor(
                self._executor,
                lambda: task.function(*task.args, **task.kwargs)
            )
    
    def shutdown(self) -> None:
        """Shutdown the task executor."""
        self._executor.shutdown(wait=True)
        self._logger.info("Task executor shutdown complete")


class TaskDependencyManager:
    """
    Manages task dependencies and execution order.

    Features:
    - Dependency graph management
    - Circular dependency detection
    - Execution order optimization
    - Dependency validation
    """

    def __init__(self):
        """Initialize dependency manager."""
        self._logger = get_logger(__name__)
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._dependents: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()

    def add_dependency(self, task_id: str, dependency_id: str) -> bool:
        """Add a task dependency."""
        try:
            with self._lock:
                # Check for circular dependencies
                if self._would_create_cycle(task_id, dependency_id):
                    self._logger.warning(f"Circular dependency detected: {task_id} -> {dependency_id}")
                    return False

                self._dependencies[task_id].add(dependency_id)
                self._dependents[dependency_id].add(task_id)

                self._logger.debug(f"Added dependency: {task_id} depends on {dependency_id}")
                return True

        except Exception as e:
            self._logger.error(f"Error adding dependency {task_id} -> {dependency_id}: {e}")
            return False

    def remove_dependency(self, task_id: str, dependency_id: str) -> bool:
        """Remove a task dependency."""
        try:
            with self._lock:
                self._dependencies[task_id].discard(dependency_id)
                self._dependents[dependency_id].discard(task_id)

                self._logger.debug(f"Removed dependency: {task_id} -> {dependency_id}")
                return True

        except Exception as e:
            self._logger.error(f"Error removing dependency {task_id} -> {dependency_id}: {e}")
            return False

    def get_execution_order(self, task_ids: Set[str]) -> List[str]:
        """Get the order in which tasks should be executed."""
        try:
            with self._lock:
                # Topological sort
                in_degree = {tid: 0 for tid in task_ids}

                # Calculate in-degrees
                for task_id in task_ids:
                    for dep in self._dependencies[task_id]:
                        if dep in task_ids:
                            in_degree[task_id] += 1

                # Start with tasks that have no dependencies
                queue = deque([tid for tid in task_ids if in_degree[tid] == 0])
                result = []

                while queue:
                    current = queue.popleft()
                    result.append(current)

                    # Update in-degrees of dependents
                    for dependent in self._dependents[current]:
                        if dependent in task_ids:
                            in_degree[dependent] -= 1
                            if in_degree[dependent] == 0:
                                queue.append(dependent)

                # Check for remaining tasks (circular dependencies)
                remaining = [tid for tid in task_ids if tid not in result]
                if remaining:
                    self._logger.warning(f"Circular dependencies detected for tasks: {remaining}")
                    result.extend(remaining)  # Add them anyway

                return result

        except Exception as e:
            self._logger.error(f"Error calculating execution order: {e}")
            return list(task_ids)

    def _would_create_cycle(self, task_id: str, dependency_id: str) -> bool:
        """Check if adding a dependency would create a cycle."""
        # Use DFS to check if dependency_id can reach task_id
        visited = set()

        def dfs(current: str) -> bool:
            if current == task_id:
                return True
            if current in visited:
                return False

            visited.add(current)
            for dep in self._dependencies[current]:
                if dfs(dep):
                    return True
            return False

        return dfs(dependency_id)


class BackgroundTaskScheduler(ITaskScheduler):
    """
    Main background task scheduler implementation.

    Features:
    - Async task scheduling and execution
    - Priority-based task queue
    - Dependency management
    - Retry logic
    - Resource monitoring
    - Thread-safe operations
    """

    def __init__(self, config: Optional[TaskSchedulerConfig] = None):
        """Initialize background task scheduler."""
        self._logger = get_logger(__name__)
        self._config = config or TaskSchedulerConfig()

        # Core components
        self._task_queue = TaskQueue()
        self._task_executor = TaskExecutor(max_workers=self._config.max_concurrent_tasks)
        self._dependency_manager = TaskDependencyManager()

        # Task storage and results
        self._task_results: Dict[str, TaskResult] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}

        # Scheduler state
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Thread safety
        self._lock = threading.RLock()

        self._logger.info("Background task scheduler initialized")

    async def schedule_task(self, task: BackgroundTask) -> bool:
        """Schedule a background task."""
        try:
            # Generate task ID if not provided
            if not task.task_id:
                task.task_id = str(uuid.uuid4())

            # Add to queue
            success = self._task_queue.add_task(task)

            if success:
                self._logger.info(f"Scheduled task {task.task_id}: {task.name}")

            return success

        except Exception as e:
            self._logger.error(f"Error scheduling task {task.task_id}: {e}")
            return False

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        try:
            with self._lock:
                # Cancel running task
                if task_id in self._running_tasks:
                    running_task = self._running_tasks[task_id]
                    running_task.cancel()
                    del self._running_tasks[task_id]

                # Remove from queue
                success = self._task_queue.remove_task(task_id)

                if success:
                    self._logger.info(f"Cancelled task {task_id}")

                return success

        except Exception as e:
            self._logger.error(f"Error cancelling task {task_id}: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get task information."""
        return self._task_queue.get_task(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[BackgroundTask]:
        """List scheduled tasks."""
        return self._task_queue.list_tasks(status)

    async def execute_task(self, task_id: str) -> TaskExecutionResult:
        """Execute a specific task."""
        try:
            task = self._task_queue.get_task(task_id)
            if not task:
                message = f"Task {task_id} not found"
                self._logger.error(message)
                return TaskExecutionResult(
                    success=False,
                    task_id=task_id,
                    result=TaskResult(task_id=task_id, status=TaskStatus.FAILED),
                    message=message
                )

            # Execute task
            result = await self._task_executor.execute_task(task)

            # Store result
            with self._lock:
                self._task_results[task_id] = result

            # Complete task in queue
            self._task_queue.complete_task(task_id, result)

            message = f"Task {task_id} executed with status {result.status.value}"
            self._logger.info(message)

            return TaskExecutionResult(
                success=result.status == TaskStatus.COMPLETED,
                task_id=task_id,
                result=result,
                message=message
            )

        except Exception as e:
            error_msg = f"Error executing task {task_id}: {e}"
            self._logger.error(error_msg)

            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=e
            )

            return TaskExecutionResult(
                success=False,
                task_id=task_id,
                result=result,
                message=error_msg
            )

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task execution result."""
        with self._lock:
            return self._task_results.get(task_id)

    async def start_scheduler(self) -> None:
        """Start the task scheduler."""
        if self._running:
            self._logger.warning("Task scheduler is already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self._logger.info("Task scheduler started")

    async def stop_scheduler(self) -> None:
        """Stop the task scheduler."""
        if not self._running:
            return

        self._running = False

        # Cancel scheduler tasks
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel running tasks
        with self._lock:
            for task in self._running_tasks.values():
                task.cancel()
            self._running_tasks.clear()

        # Shutdown executor
        self._task_executor.shutdown()

        self._logger.info("Task scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                # Get next task
                task = self._task_queue.get_next_task(timeout=1.0)

                if task:
                    # Execute task asynchronously
                    execution_task = asyncio.create_task(self.execute_task(task.task_id))

                    with self._lock:
                        self._running_tasks[task.task_id] = execution_task

                    # Clean up completed tasks
                    def cleanup_task(task_id: str):
                        def _cleanup(future):
                            with self._lock:
                                self._running_tasks.pop(task_id, None)
                        return _cleanup

                    execution_task.add_done_callback(cleanup_task(task.task_id))

            except Exception as e:
                self._logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(1)

    async def _cleanup_loop(self) -> None:
        """Cleanup loop for old task results."""
        while self._running:
            try:
                await asyncio.sleep(self._config.cleanup_interval.total_seconds())

                # Clean up old results
                cutoff_time = datetime.now() - timedelta(hours=24)

                with self._lock:
                    to_remove = []
                    for task_id, result in self._task_results.items():
                        task = self._task_queue.get_task(task_id)
                        if (task and task.completed_at and
                            task.completed_at < cutoff_time):
                            to_remove.append(task_id)

                    for task_id in to_remove:
                        self._task_results.pop(task_id, None)

                    if to_remove:
                        self._logger.debug(f"Cleaned up {len(to_remove)} old task results")

            except Exception as e:
                self._logger.error(f"Error in cleanup loop: {e}")
