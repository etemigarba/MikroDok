"""
Module: async_task_manager_lg
Description: Handles asynchronous operation lifecycle and callbacks with thread coordination
Phase: 2
Location: /src/modules/logic/thread_coordination_lg/async_task_manager_lg/
"""

# Standard library imports
import asyncio
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union, Awaitable

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier
from src.modules.logic.async_operations_lg.base_interfaces import (
    AsyncTask, TaskResult, TaskStatus, TaskPriority, ICallbackManager
)
from ..base_interfaces import (
    ThreadPoolType, ThreadTask, TaskPriority as ThreadTaskPriority
)


class AsyncTaskStatus(Enum):
    """Extended status for async task management."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_CALLBACK = "awaiting_callback"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class AsyncTaskContext:
    """Context information for async task execution."""
    task_id: str
    async_task: AsyncTask
    thread_task: Optional[ThreadTask] = None
    future: Optional[Future] = None
    callbacks: List[Callable] = field(default_factory=list)
    error_callbacks: List[Callable] = field(default_factory=list)
    progress_callbacks: List[Callable] = field(default_factory=list)
    status: AsyncTaskStatus = AsyncTaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[Exception] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AsyncTaskConfig:
    """Configuration for async task manager."""
    max_concurrent_tasks: int = 50
    default_timeout: float = 300.0
    enable_callbacks: bool = True
    enable_progress_tracking: bool = True
    callback_timeout: float = 30.0
    cleanup_interval: float = 60.0
    max_callback_retries: int = 3
    callback_retry_delay: float = 1.0


class AsyncTaskManager:
    """
    Manages asynchronous operation lifecycle and callbacks with thread coordination.
    
    Features:
    - Async task lifecycle management
    - Callback coordination and execution
    - Integration with thread pool manager
    - Progress tracking and monitoring
    - Error handling and recovery
    - Task cancellation and timeout handling
    """
    
    def __init__(self, config: Optional[AsyncTaskConfig] = None):
        """
        Initialize async task manager.
        
        Args:
            config: Task manager configuration
        """
        self.config = config or AsyncTaskConfig()
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()
        
        # Task tracking
        self._tasks: Dict[str, AsyncTaskContext] = {}
        self._running_tasks: Set[str] = set()
        self._completed_tasks: Set[str] = set()
        self._failed_tasks: Set[str] = set()
        
        # Synchronization
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        
        # Callback execution
        self._callback_executor = ThreadPoolExecutor(
            max_workers=10,
            thread_name_prefix="AsyncTaskCallback"
        )
        
        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Metrics
        self._total_tasks = 0
        self._completed_count = 0
        self._failed_count = 0
        self._cancelled_count = 0
        
        self._logger.info("Async task manager initialized")
    
    def start(self) -> bool:
        """Start the async task manager."""
        try:
            with self._lock:
                if self._running:
                    self._logger.warning("Async task manager already running")
                    return True
                
                self._running = True
                self._shutdown_event.clear()
                
                # Start cleanup thread
                self._cleanup_thread = threading.Thread(
                    target=self._cleanup_loop,
                    name="AsyncTaskCleanup",
                    daemon=True
                )
                self._cleanup_thread.start()
                
                self._logger.info("Async task manager started")
                return True
                
        except Exception as e:
            self._logger.error(f"Error starting async task manager: {e}")
            return False
    
    def stop(self, timeout: Optional[float] = None) -> bool:
        """Stop the async task manager."""
        try:
            with self._lock:
                if not self._running:
                    return True
                
                self._running = False
                self._shutdown_event.set()
                
                # Cancel all running tasks
                for task_id in list(self._running_tasks):
                    self.cancel_task(task_id)
                
                # Wait for cleanup thread
                if self._cleanup_thread and self._cleanup_thread.is_alive():
                    self._cleanup_thread.join(timeout=timeout or 5.0)
                
                # Shutdown callback executor
                self._callback_executor.shutdown(wait=True, timeout=timeout or 5.0)
                
                self._logger.info("Async task manager stopped")
                return True
                
        except Exception as e:
            self._logger.error(f"Error stopping async task manager: {e}")
            return False
    
    async def submit_async_task(self, async_task: AsyncTask,
                               callbacks: Optional[List[Callable]] = None,
                               error_callbacks: Optional[List[Callable]] = None,
                               progress_callbacks: Optional[List[Callable]] = None) -> str:
        """
        Submit an async task for execution.
        
        Args:
            async_task: Async task to execute
            callbacks: Success callbacks
            error_callbacks: Error callbacks
            progress_callbacks: Progress callbacks
            
        Returns:
            Task ID for tracking
        """
        try:
            task_id = async_task.task_id or str(uuid.uuid4())
            
            # Create task context
            context = AsyncTaskContext(
                task_id=task_id,
                async_task=async_task,
                callbacks=callbacks or [],
                error_callbacks=error_callbacks or [],
                progress_callbacks=progress_callbacks or []
            )
            
            with self._lock:
                if task_id in self._tasks:
                    raise ValueError(f"Task {task_id} already exists")
                
                self._tasks[task_id] = context
                self._total_tasks += 1
            
            # Execute task
            await self._execute_async_task(context)
            
            self._logger.debug(f"Submitted async task {task_id}")
            return task_id
            
        except Exception as e:
            self._logger.error(f"Error submitting async task: {e}")
            raise
    
    async def _execute_async_task(self, context: AsyncTaskContext) -> None:
        """Execute an async task with lifecycle management."""
        try:
            task_id = context.task_id
            async_task = context.async_task
            
            # Update status
            context.status = AsyncTaskStatus.RUNNING
            context.started_at = datetime.now()
            
            with self._lock:
                self._running_tasks.add(task_id)
            
            # Execute the task
            if asyncio.iscoroutinefunction(async_task.function):
                # Async function
                result = await async_task.function(*async_task.args, **async_task.kwargs)
            else:
                # Sync function - run in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: async_task.function(*async_task.args, **async_task.kwargs)
                )
            
            # Task completed successfully
            context.result = result
            context.status = AsyncTaskStatus.COMPLETED
            context.completed_at = datetime.now()
            
            with self._lock:
                self._running_tasks.discard(task_id)
                self._completed_tasks.add(task_id)
                self._completed_count += 1
            
            # Execute success callbacks
            if self.config.enable_callbacks and context.callbacks:
                await self._execute_callbacks(context, context.callbacks, result)
            
            self._logger.debug(f"Async task {task_id} completed successfully")
            
        except asyncio.CancelledError:
            # Task was cancelled
            context.status = AsyncTaskStatus.CANCELLED
            context.completed_at = datetime.now()
            
            with self._lock:
                self._running_tasks.discard(task_id)
                self._cancelled_count += 1
            
            self._logger.info(f"Async task {task_id} was cancelled")
            
        except Exception as e:
            # Task failed
            context.error = e
            context.status = AsyncTaskStatus.FAILED
            context.completed_at = datetime.now()
            
            with self._lock:
                self._running_tasks.discard(task_id)
                self._failed_tasks.add(task_id)
                self._failed_count += 1
            
            # Execute error callbacks
            if self.config.enable_callbacks and context.error_callbacks:
                await self._execute_callbacks(context, context.error_callbacks, e)
            
            self._logger.error(f"Async task {task_id} failed: {e}")

    async def _execute_callbacks(self, context: AsyncTaskContext,
                               callbacks: List[Callable],
                               callback_arg: Any) -> None:
        """Execute callbacks for a task."""
        try:
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await asyncio.wait_for(
                            callback(context.task_id, callback_arg),
                            timeout=self.config.callback_timeout
                        )
                    else:
                        # Run sync callback in thread pool
                        loop = asyncio.get_event_loop()
                        await asyncio.wait_for(
                            loop.run_in_executor(
                                self._callback_executor,
                                callback,
                                context.task_id,
                                callback_arg
                            ),
                            timeout=self.config.callback_timeout
                        )

                except asyncio.TimeoutError:
                    self._logger.warning(f"Callback timeout for task {context.task_id}")
                except Exception as e:
                    self._logger.error(f"Callback error for task {context.task_id}: {e}")

        except Exception as e:
            self._logger.error(f"Error executing callbacks for task {context.task_id}: {e}")

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        try:
            with self._lock:
                if task_id not in self._tasks:
                    self._logger.warning(f"Task {task_id} not found")
                    return False

                context = self._tasks[task_id]

                if context.status in [AsyncTaskStatus.COMPLETED,
                                    AsyncTaskStatus.FAILED,
                                    AsyncTaskStatus.CANCELLED]:
                    self._logger.warning(f"Task {task_id} already finished")
                    return False

                # Cancel the task
                if context.future:
                    context.future.cancel()

                context.status = AsyncTaskStatus.CANCELLED
                context.completed_at = datetime.now()

                self._running_tasks.discard(task_id)
                self._cancelled_count += 1

                self._logger.info(f"Cancelled task {task_id}")
                return True

        except Exception as e:
            self._logger.error(f"Error cancelling task {task_id}: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[AsyncTaskStatus]:
        """Get the status of a task."""
        try:
            with self._lock:
                if task_id not in self._tasks:
                    return None
                return self._tasks[task_id].status

        except Exception as e:
            self._logger.error(f"Error getting task status for {task_id}: {e}")
            return None

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """Get the result of a completed task."""
        try:
            with self._lock:
                if task_id not in self._tasks:
                    return None

                context = self._tasks[task_id]
                if context.status == AsyncTaskStatus.COMPLETED:
                    return context.result
                elif context.status == AsyncTaskStatus.FAILED:
                    raise context.error
                else:
                    return None

        except Exception as e:
            self._logger.error(f"Error getting task result for {task_id}: {e}")
            return None

    def get_task_progress(self, task_id: str) -> Optional[float]:
        """Get the progress of a task."""
        try:
            with self._lock:
                if task_id not in self._tasks:
                    return None
                return self._tasks[task_id].progress

        except Exception as e:
            self._logger.error(f"Error getting task progress for {task_id}: {e}")
            return None

    def update_task_progress(self, task_id: str, progress: float,
                           message: Optional[str] = None) -> bool:
        """Update the progress of a task."""
        try:
            with self._lock:
                if task_id not in self._tasks:
                    return False

                context = self._tasks[task_id]
                context.progress = max(0.0, min(1.0, progress))

                if message:
                    context.metadata['progress_message'] = message

                # Execute progress callbacks
                if (self.config.enable_callbacks and
                    self.config.enable_progress_tracking and
                    context.progress_callbacks):

                    # Schedule callback execution
                    asyncio.create_task(
                        self._execute_callbacks(
                            context,
                            context.progress_callbacks,
                            {'progress': progress, 'message': message}
                        )
                    )

                return True

        except Exception as e:
            self._logger.error(f"Error updating task progress for {task_id}: {e}")
            return False

    def get_running_tasks(self) -> List[str]:
        """Get list of currently running task IDs."""
        try:
            with self._lock:
                return list(self._running_tasks)

        except Exception as e:
            self._logger.error(f"Error getting running tasks: {e}")
            return []

    def get_task_metrics(self) -> Dict[str, Any]:
        """Get task execution metrics."""
        try:
            with self._lock:
                return {
                    'total_tasks': self._total_tasks,
                    'running_tasks': len(self._running_tasks),
                    'completed_tasks': self._completed_count,
                    'failed_tasks': self._failed_count,
                    'cancelled_tasks': self._cancelled_count,
                    'active_tasks': len(self._tasks),
                    'completion_rate': (
                        self._completed_count / max(1, self._total_tasks) * 100
                    ),
                    'failure_rate': (
                        self._failed_count / max(1, self._total_tasks) * 100
                    )
                }

        except Exception as e:
            self._logger.error(f"Error getting task metrics: {e}")
            return {}

    def _cleanup_loop(self) -> None:
        """Background cleanup loop for completed tasks."""
        while self._running and not self._shutdown_event.is_set():
            try:
                self._cleanup_completed_tasks()
                self._shutdown_event.wait(self.config.cleanup_interval)

            except Exception as e:
                self._logger.error(f"Error in cleanup loop: {e}")
                time.sleep(1)

    def _cleanup_completed_tasks(self) -> None:
        """Clean up old completed tasks."""
        try:
            current_time = datetime.now()
            cleanup_threshold = 3600  # 1 hour

            with self._lock:
                tasks_to_remove = []

                for task_id, context in self._tasks.items():
                    if (context.status in [AsyncTaskStatus.COMPLETED,
                                         AsyncTaskStatus.FAILED,
                                         AsyncTaskStatus.CANCELLED] and
                        context.completed_at and
                        (current_time - context.completed_at).total_seconds() > cleanup_threshold):

                        tasks_to_remove.append(task_id)

                # Remove old tasks
                for task_id in tasks_to_remove:
                    del self._tasks[task_id]
                    self._completed_tasks.discard(task_id)
                    self._failed_tasks.discard(task_id)

                if tasks_to_remove:
                    self._logger.debug(f"Cleaned up {len(tasks_to_remove)} old tasks")

        except Exception as e:
            self._logger.error(f"Error cleaning up tasks: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


# Convenience functions
def create_async_task(task_id: Optional[str] = None,
                     function: Optional[Union[Callable, Awaitable]] = None,
                     args: tuple = (),
                     kwargs: Optional[Dict[str, Any]] = None,
                     priority: TaskPriority = TaskPriority.NORMAL,
                     timeout_seconds: Optional[float] = None) -> AsyncTask:
    """
    Convenience function to create an AsyncTask.

    Args:
        task_id: Unique task identifier (auto-generated if None)
        function: Function or coroutine to execute
        args: Function arguments
        kwargs: Function keyword arguments
        priority: Task priority
        timeout_seconds: Task timeout

    Returns:
        AsyncTask instance
    """
    if task_id is None:
        task_id = str(uuid.uuid4())

    if kwargs is None:
        kwargs = {}

    return AsyncTask(
        task_id=task_id,
        name=getattr(function, '__name__', 'unnamed_task'),
        function=function,
        args=args,
        kwargs=kwargs,
        priority=priority,
        timeout_seconds=timeout_seconds
    )
