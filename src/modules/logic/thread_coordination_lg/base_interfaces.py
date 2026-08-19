"""
Module: base_interfaces
Description: Base interfaces and common data structures for thread coordination modules
Phase: 2
Location: /src/modules/logic/thread_coordination_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Set
import threading
from concurrent.futures import Future

# Local imports
from src.modules.logic.error_handling_lg import ValidationError


class ThreadPoolType(Enum):
    """Types of thread pools for different operations."""
    TRAINING = "training"
    DOCUMENT_PROCESSING = "document_processing"
    MONITORING = "monitoring"
    INFERENCE = "inference"
    BACKGROUND = "background"
    GENERAL = "general"


class ThreadPoolStatus(Enum):
    """Status of thread pool."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class LockType(Enum):
    """Types of locks for resource management."""
    MUTEX = "mutex"
    READ_WRITE = "read_write"
    SEMAPHORE = "semaphore"
    CONDITION = "condition"
    BARRIER = "barrier"
    EVENT = "event"


class LockStatus(Enum):
    """Status of lock acquisition."""
    AVAILABLE = "available"
    ACQUIRED = "acquired"
    WAITING = "waiting"
    TIMEOUT = "timeout"
    DEADLOCK = "deadlock"
    ERROR = "error"


class DeadlockDetectionStrategy(Enum):
    """Strategies for deadlock detection."""
    NONE = "none"
    TIMEOUT_BASED = "timeout_based"
    GRAPH_BASED = "graph_based"
    PRIORITY_BASED = "priority_based"
    HYBRID = "hybrid"


class TaskPriority(Enum):
    """Priority levels for tasks."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(Enum):
    """Status of task execution."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ThreadPoolConfig:
    """Configuration for thread pool."""
    pool_type: ThreadPoolType
    min_threads: int = 1
    max_threads: int = 4
    queue_size: int = 100
    thread_timeout_seconds: float = 30.0
    task_timeout_seconds: float = 300.0
    enable_monitoring: bool = True
    thread_name_prefix: str = "MikroDok"
    priority_levels: int = 5
    auto_scale: bool = True
    scale_factor: float = 1.5
    idle_timeout_seconds: float = 60.0


@dataclass
class LockConfig:
    """Configuration for lock management."""
    lock_type: LockType
    timeout_seconds: float = 30.0
    enable_deadlock_detection: bool = True
    deadlock_strategy: DeadlockDetectionStrategy = DeadlockDetectionStrategy.TIMEOUT_BASED
    max_waiters: int = 100
    priority_inheritance: bool = True
    fair_scheduling: bool = True
    enable_monitoring: bool = True


@dataclass
class ThreadTask:
    """Represents a task to be executed in a thread pool."""
    task_id: str
    function: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: Optional[float] = None
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    thread_id: Optional[int] = None
    future: Optional[Future] = None


@dataclass
class ResourceLock:
    """Represents a resource lock."""
    lock_id: str
    resource_id: str
    lock_type: LockType
    owner_thread_id: Optional[int] = None
    acquired_at: Optional[datetime] = None
    timeout_seconds: float = 30.0
    status: LockStatus = LockStatus.AVAILABLE
    waiters: Set[int] = field(default_factory=set)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreadPoolInfo:
    """Information about a thread pool."""
    pool_type: ThreadPoolType
    status: ThreadPoolStatus
    active_threads: int
    total_threads: int
    queued_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_task_time: float
    created_at: datetime
    last_activity: datetime


@dataclass
class LockInfo:
    """Information about a lock."""
    lock_id: str
    resource_id: str
    lock_type: LockType
    status: LockStatus
    owner_thread_id: Optional[int]
    waiter_count: int
    acquired_at: Optional[datetime]
    total_acquisitions: int
    average_hold_time: float
    created_at: datetime


@dataclass
class ThreadPoolMetrics:
    """Metrics for thread pool performance."""
    pool_type: ThreadPoolType
    total_tasks_submitted: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    total_tasks_cancelled: int = 0
    average_execution_time: float = 0.0
    peak_thread_count: int = 0
    current_thread_count: int = 0
    queue_utilization: float = 0.0
    thread_utilization: float = 0.0
    throughput_per_second: float = 0.0
    error_rate: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class LockMetrics:
    """Metrics for lock performance."""
    lock_id: str
    total_acquisitions: int = 0
    total_contentions: int = 0
    total_timeouts: int = 0
    total_deadlocks: int = 0
    average_wait_time: float = 0.0
    average_hold_time: float = 0.0
    max_wait_time: float = 0.0
    max_hold_time: float = 0.0
    contention_rate: float = 0.0
    timeout_rate: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class LockAcquisitionResult:
    """Result of lock acquisition attempt."""
    success: bool
    lock_id: str
    acquired_at: Optional[datetime] = None
    wait_time_seconds: float = 0.0
    status: LockStatus = LockStatus.ERROR
    error_message: Optional[str] = None
    timeout_occurred: bool = False
    deadlock_detected: bool = False


@dataclass
class ThreadPoolOperationResult:
    """Result of thread pool operation."""
    success: bool
    operation: str
    pool_type: ThreadPoolType
    task_id: Optional[str] = None
    execution_time_seconds: float = 0.0
    error_message: Optional[str] = None
    result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IThreadPoolManager(ABC):
    """Base interface for thread pool management."""
    
    @abstractmethod
    def create_pool(self, config: ThreadPoolConfig) -> bool:
        """
        Create a new thread pool with the specified configuration.
        
        Args:
            config: Thread pool configuration
            
        Returns:
            True if pool created successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def submit_task(self, pool_type: ThreadPoolType, task: ThreadTask) -> Optional[Future]:
        """
        Submit a task to the specified thread pool.
        
        Args:
            pool_type: Type of thread pool to submit to
            task: Task to execute
            
        Returns:
            Future object for the task, None if submission failed
        """
        pass
    
    @abstractmethod
    def shutdown_pool(self, pool_type: ThreadPoolType, wait: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Shutdown a specific thread pool.
        
        Args:
            pool_type: Type of thread pool to shutdown
            wait: Whether to wait for completion
            timeout: Maximum time to wait for shutdown
            
        Returns:
            True if shutdown successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_pool_info(self, pool_type: ThreadPoolType) -> Optional[ThreadPoolInfo]:
        """
        Get information about a thread pool.
        
        Args:
            pool_type: Type of thread pool
            
        Returns:
            ThreadPoolInfo if pool exists, None otherwise
        """
        pass
    
    @abstractmethod
    def get_metrics(self, pool_type: Optional[ThreadPoolType] = None) -> Dict[ThreadPoolType, ThreadPoolMetrics]:
        """
        Get performance metrics for thread pools.
        
        Args:
            pool_type: Specific pool type, or None for all pools
            
        Returns:
            Dictionary of metrics by pool type
        """
        pass


class ILockManager(ABC):
    """Base interface for lock management."""
    
    @abstractmethod
    def create_lock(self, resource_id: str, config: LockConfig) -> str:
        """
        Create a new lock for a resource.
        
        Args:
            resource_id: Unique identifier for the resource
            config: Lock configuration
            
        Returns:
            Lock ID if created successfully
        """
        pass
    
    @abstractmethod
    def acquire_lock(self, lock_id: str, timeout: Optional[float] = None) -> LockAcquisitionResult:
        """
        Acquire a lock on a resource.
        
        Args:
            lock_id: Lock identifier
            timeout: Maximum time to wait for lock
            
        Returns:
            LockAcquisitionResult with acquisition details
        """
        pass
    
    @abstractmethod
    def release_lock(self, lock_id: str) -> bool:
        """
        Release a lock on a resource.
        
        Args:
            lock_id: Lock identifier
            
        Returns:
            True if released successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_lock_info(self, lock_id: str) -> Optional[LockInfo]:
        """
        Get information about a lock.
        
        Args:
            lock_id: Lock identifier
            
        Returns:
            LockInfo if lock exists, None otherwise
        """
        pass
    
    @abstractmethod
    def detect_deadlocks(self) -> List[Tuple[str, List[str]]]:
        """
        Detect potential deadlocks in the system.
        
        Returns:
            List of (deadlock_id, involved_lock_ids) tuples
        """
        pass
    
    @abstractmethod
    def get_metrics(self, lock_id: Optional[str] = None) -> Dict[str, LockMetrics]:
        """
        Get performance metrics for locks.
        
        Args:
            lock_id: Specific lock ID, or None for all locks
            
        Returns:
            Dictionary of metrics by lock ID
        """
        pass
