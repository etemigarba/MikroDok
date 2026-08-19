"""
Module: base_interfaces
Description: Base interfaces and data structures for async operations
Phase: 2
Location: /src/modules/logic/async_operations_lg/
"""

# Standard library imports
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Union, Awaitable
from concurrent.futures import Future
import uuid

# Third-party imports
# None required

# Local imports
# None required


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    WAITING_DEPENDENCIES = "waiting_dependencies"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


class CallbackType(Enum):
    """Callback types."""
    ON_START = "on_start"
    ON_PROGRESS = "on_progress"
    ON_SUCCESS = "on_success"
    ON_ERROR = "on_error"
    ON_COMPLETE = "on_complete"
    ON_CANCEL = "on_cancel"
    ON_TIMEOUT = "on_timeout"


class CallbackStatus(Enum):
    """Callback execution status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SchedulerStatus(Enum):
    """Scheduler status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class TaskDependencyType(Enum):
    """Task dependency types."""
    HARD = "hard"  # Must complete successfully
    SOFT = "soft"  # Must complete (success or failure)
    CONDITIONAL = "conditional"  # Conditional dependency


@dataclass
class TaskDependency:
    """Represents a task dependency."""
    task_id: str
    dependency_type: TaskDependencyType = TaskDependencyType.HARD
    condition: Optional[Callable[[Any], bool]] = None


@dataclass
class AsyncTask:
    """Represents an asynchronous task."""
    task_id: str
    name: str
    function: Union[Callable, Awaitable]
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    dependencies: List[TaskDependency] = field(default_factory=list)
    timeout_seconds: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    future: Optional[Future] = None


@dataclass
class TaskResult:
    """Task execution result."""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallbackInfo:
    """Callback information."""
    callback_id: str
    callback_type: CallbackType
    function: Callable
    task_id: Optional[str] = None
    priority: int = 0
    timeout_seconds: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallbackResult:
    """Callback execution result."""
    callback_id: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulerConfig:
    """Task scheduler configuration."""
    max_concurrent_tasks: int = 10
    max_queue_size: int = 1000
    default_timeout: float = 300.0
    enable_retry: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_dependency_tracking: bool = True
    enable_priority_scheduling: bool = True
    heartbeat_interval: float = 1.0
    cleanup_interval: float = 60.0
    persist_tasks: bool = True
    database_path: Optional[str] = None


@dataclass
class CallbackConfig:
    """Callback manager configuration."""
    max_concurrent_callbacks: int = 20
    default_timeout: float = 30.0
    enable_async_callbacks: bool = True
    enable_error_recovery: bool = True
    max_retry_attempts: int = 3
    retry_delay: float = 0.5
    enable_progress_tracking: bool = True
    progress_update_interval: float = 1.0
    enable_event_batching: bool = True
    batch_size: int = 100
    batch_timeout: float = 5.0


@dataclass
class TaskMetrics:
    """Task execution metrics."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    average_execution_time: float = 0.0
    total_execution_time: float = 0.0
    queue_size: int = 0
    active_tasks: int = 0
    retry_count: int = 0


@dataclass
class CallbackMetrics:
    """Callback execution metrics."""
    total_callbacks: int = 0
    successful_callbacks: int = 0
    failed_callbacks: int = 0
    average_execution_time: float = 0.0
    total_execution_time: float = 0.0
    active_callbacks: int = 0
    queued_callbacks: int = 0


@dataclass
class SchedulerMetrics:
    """Scheduler performance metrics."""
    uptime_seconds: float = 0.0
    tasks_processed: int = 0
    tasks_per_second: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    queue_utilization: float = 0.0
    dependency_resolution_time: float = 0.0


@dataclass
class TaskExecutionResult:
    """Complete task execution result."""
    task: AsyncTask
    result: TaskResult
    callbacks_executed: List[CallbackResult] = field(default_factory=list)
    dependencies_resolved: List[str] = field(default_factory=list)
    metrics: TaskMetrics = field(default_factory=TaskMetrics)


@dataclass
class CallbackExecutionResult:
    """Complete callback execution result."""
    callback: CallbackInfo
    result: CallbackResult
    task_context: Optional[AsyncTask] = None
    metrics: CallbackMetrics = field(default_factory=CallbackMetrics)


class ITaskScheduler(ABC):
    """Base interface for task scheduling with dependency tracking."""
    
    @abstractmethod
    async def start(self) -> bool:
        """Start the task scheduler."""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """Stop the task scheduler."""
        pass
    
    @abstractmethod
    async def schedule_task(self, task: AsyncTask) -> bool:
        """Schedule a task for execution."""
        pass
    
    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled or running task."""
        pass
    
    @abstractmethod
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a task."""
        pass
    
    @abstractmethod
    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a completed task."""
        pass
    
    @abstractmethod
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """Wait for a task to complete."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> SchedulerMetrics:
        """Get scheduler performance metrics."""
        pass
    
    @abstractmethod
    async def pause(self) -> bool:
        """Pause task execution."""
        pass
    
    @abstractmethod
    async def resume(self) -> bool:
        """Resume task execution."""
        pass


class ICallbackManager(ABC):
    """Base interface for callback management."""
    
    @abstractmethod
    async def register_callback(self, callback: CallbackInfo) -> bool:
        """Register a callback."""
        pass
    
    @abstractmethod
    async def unregister_callback(self, callback_id: str) -> bool:
        """Unregister a callback."""
        pass
    
    @abstractmethod
    async def execute_callbacks(self, callback_type: CallbackType, 
                              task_context: Optional[AsyncTask] = None,
                              **kwargs) -> List[CallbackResult]:
        """Execute callbacks of a specific type."""
        pass
    
    @abstractmethod
    async def notify_progress(self, task_id: str, progress: float, 
                            message: Optional[str] = None) -> bool:
        """Notify progress for a task."""
        pass
    
    @abstractmethod
    async def notify_completion(self, task_id: str, result: TaskResult) -> bool:
        """Notify task completion."""
        pass
    
    @abstractmethod
    async def notify_error(self, task_id: str, error: Exception) -> bool:
        """Notify task error."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> CallbackMetrics:
        """Get callback execution metrics."""
        pass
    
    @abstractmethod
    async def clear_callbacks(self, task_id: Optional[str] = None) -> bool:
        """Clear callbacks for a specific task or all callbacks."""
        pass
