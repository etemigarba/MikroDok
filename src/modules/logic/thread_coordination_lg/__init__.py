"""
MikroDok Thread Coordination Package
Provides comprehensive thread coordination functionality including thread pool management and lock management.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IThreadPoolManager,
        ILockManager,
        ThreadPoolType,
        ThreadPoolStatus,
        LockType,
        LockStatus,
        DeadlockDetectionStrategy,
        ThreadPoolConfig,
        LockConfig,
        ThreadPoolInfo,
        LockInfo,
        ThreadTask,
        ResourceLock,
        ThreadPoolMetrics,
        LockMetrics,
        TaskPriority,
        TaskStatus,
        LockAcquisitionResult,
        ThreadPoolOperationResult
    )
except ImportError:
    pass

# Import thread pool manager components
try:
    from .thread_pool_manager_lg.thread_pool_manager_lg import (
        ThreadPoolManager,
        ThreadPool,
        TaskQueue,
        ThreadWorker
    )
except ImportError:
    pass

# Import lock manager components
try:
    from .lock_manager_lg.lock_manager_lg import (
        LockManager,
        ResourceLockManager,
        DeadlockDetector,
        LockRegistry
    )
except ImportError:
    pass

# Import async task manager components
try:
    from .async_task_manager_lg.async_task_manager_lg import (
        AsyncTaskManager,
        AsyncTaskContext,
        AsyncTaskConfig,
        AsyncTaskStatus
    )
except ImportError:
    pass

# Import work distributor components
try:
    from .work_distributor_lg.work_distributor_lg import (
        WorkDistributor,
        WorkItem,
        PoolLoadInfo,
        DistributionConfig,
        DistributionStrategy,
        WorkloadType
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IThreadPoolManager',
    'ILockManager',
    'ThreadPoolType',
    'ThreadPoolStatus',
    'LockType',
    'LockStatus',
    'DeadlockDetectionStrategy',
    'ThreadPoolConfig',
    'LockConfig',
    'ThreadPoolInfo',
    'LockInfo',
    'ThreadTask',
    'ResourceLock',
    'ThreadPoolMetrics',
    'LockMetrics',
    'TaskPriority',
    'TaskStatus',
    'LockAcquisitionResult',
    'ThreadPoolOperationResult',
    
    # Thread Pool Manager
    'ThreadPoolManager',
    'ThreadPool',
    'TaskQueue',
    'ThreadWorker',
    
    # Lock Manager
    'LockManager',
    'ResourceLockManager',
    'DeadlockDetector',
    'LockRegistry',

    # Async Task Manager
    'AsyncTaskManager',
    'AsyncTaskContext',
    'AsyncTaskConfig',
    'AsyncTaskStatus',

    # Work Distributor
    'WorkDistributor',
    'WorkItem',
    'PoolLoadInfo',
    'DistributionConfig',
    'DistributionStrategy',
    'WorkloadType'
]
