"""
MikroDok Async Operations Package
Provides comprehensive asynchronous operations functionality including task scheduling and callback management.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        ITaskScheduler,
        ICallbackManager,
        TaskStatus,
        TaskPriority,
        CallbackType,
        CallbackStatus,
        SchedulerStatus,
        TaskDependencyType,
        AsyncTask,
        TaskDependency,
        TaskResult,
        CallbackInfo,
        CallbackResult,
        SchedulerConfig,
        CallbackConfig,
        TaskMetrics,
        CallbackMetrics,
        SchedulerMetrics,
        TaskExecutionResult,
        CallbackExecutionResult
    )
except ImportError:
    pass

# Import task scheduler components
try:
    from .task_scheduler_lg.task_scheduler_lg import (
        TaskScheduler,
        DependencyGraph,
        TaskQueue,
        TaskExecutor
    )
except ImportError:
    pass

# Import callback manager components
try:
    from .callback_manager_lg.callback_manager_lg import (
        CallbackManager,
        CallbackRegistry,
        EventDispatcher,
        ProgressTracker
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'ITaskScheduler',
    'ICallbackManager',
    'TaskStatus',
    'TaskPriority',
    'CallbackType',
    'CallbackStatus',
    'SchedulerStatus',
    'TaskDependencyType',
    'AsyncTask',
    'TaskDependency',
    'TaskResult',
    'CallbackInfo',
    'CallbackResult',
    'SchedulerConfig',
    'CallbackConfig',
    'TaskMetrics',
    'CallbackMetrics',
    'SchedulerMetrics',
    'TaskExecutionResult',
    'CallbackExecutionResult',
    
    # Task Scheduler
    'TaskScheduler',
    'DependencyGraph',
    'TaskQueue',
    'TaskExecutor',
    
    # Callback Manager
    'CallbackManager',
    'CallbackRegistry',
    'EventDispatcher',
    'ProgressTracker'
]
