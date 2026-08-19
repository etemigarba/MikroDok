"""
Module: base_interfaces
Description: Base interfaces and data structures for background services functionality
Phase: 4
Location: /src/modules/logic/background_services_lg/
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Set, Union, AsyncIterator
import asyncio
import threading


class ServiceStatus(Enum):
    """Status of a service."""
    UNKNOWN = "unknown"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class ServiceType(Enum):
    """Type of service."""
    CORE = "core"
    BACKGROUND = "background"
    MONITORING = "monitoring"
    MAINTENANCE = "maintenance"
    UTILITY = "utility"
    EXTERNAL = "external"


class TaskStatus(Enum):
    """Status of a background task."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """Priority levels for background tasks."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


class MaintenanceType(Enum):
    """Type of maintenance operation."""
    CLEANUP = "cleanup"
    OPTIMIZATION = "optimization"
    HEALTH_CHECK = "health_check"
    BACKUP = "backup"
    UPDATE = "update"
    REPAIR = "repair"
    MONITORING = "monitoring"


class HealthStatus(Enum):
    """Health status of a service or system."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ServiceInfo:
    """Information about a registered service."""
    service_id: str
    name: str
    service_type: ServiceType
    status: ServiceStatus
    version: str
    description: str
    start_time: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    endpoints: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    health_check_url: Optional[str] = None
    restart_count: int = 0


@dataclass
class ServiceDependency:
    """Service dependency information."""
    service_id: str
    dependent_service_id: str
    dependency_type: str  # "required", "optional", "weak"
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    retry_count: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackgroundTask:
    """Background task definition."""
    task_id: str
    name: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[timedelta] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of task execution."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[Exception] = None
    execution_time: Optional[timedelta] = None
    memory_usage: Optional[int] = None
    cpu_usage: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MaintenanceTask:
    """Maintenance task definition."""
    task_id: str
    name: str
    maintenance_type: MaintenanceType
    function: Callable
    schedule: str  # cron expression
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    timeout: timedelta = field(default_factory=lambda: timedelta(hours=1))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MaintenanceResult:
    """Result of maintenance task execution."""
    task_id: str
    maintenance_type: MaintenanceType
    success: bool
    start_time: datetime
    end_time: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Health check definition."""
    check_id: str
    name: str
    service_id: str
    check_function: Callable
    interval: timedelta = field(default_factory=lambda: timedelta(minutes=1))
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    enabled: bool = True
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    max_failures: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthMetrics:
    """Health metrics for a service."""
    service_id: str
    status: HealthStatus
    timestamp: datetime
    response_time: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[int] = None
    disk_usage: Optional[float] = None
    error_rate: Optional[float] = None
    uptime: Optional[timedelta] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ServiceAlert:
    """Service alert information."""
    alert_id: str
    service_id: str
    level: AlertLevel
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceConfig:
    """Service configuration."""
    auto_start: bool = True
    restart_on_failure: bool = True
    max_restart_attempts: int = 3
    health_check_interval: timedelta = field(default_factory=lambda: timedelta(minutes=1))
    heartbeat_interval: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    shutdown_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSchedulerConfig:
    """Task scheduler configuration."""
    max_concurrent_tasks: int = 10
    task_timeout: timedelta = field(default_factory=lambda: timedelta(hours=1))
    retry_delay: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    cleanup_interval: timedelta = field(default_factory=lambda: timedelta(hours=1))
    max_task_history: int = 1000
    enable_metrics: bool = True


@dataclass
class MaintenanceConfig:
    """Maintenance service configuration."""
    enabled: bool = True
    default_timeout: timedelta = field(default_factory=lambda: timedelta(hours=1))
    max_concurrent_tasks: int = 3
    cleanup_retention: timedelta = field(default_factory=lambda: timedelta(days=7))
    health_check_interval: timedelta = field(default_factory=lambda: timedelta(minutes=5))


@dataclass
class HealthMonitorConfig:
    """Health monitor configuration."""
    enabled: bool = True
    default_check_interval: timedelta = field(default_factory=lambda: timedelta(minutes=1))
    alert_threshold: int = 3
    metrics_retention: timedelta = field(default_factory=lambda: timedelta(days=7))
    enable_notifications: bool = True


@dataclass
class ServiceRegistrationResult:
    """Result of service registration."""
    success: bool
    service_id: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskExecutionResult:
    """Result of task execution."""
    success: bool
    task_id: str
    result: TaskResult
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MaintenanceExecutionResult:
    """Result of maintenance execution."""
    success: bool
    task_id: str
    result: MaintenanceResult
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class HealthCheckResult:
    """Result of health check."""
    success: bool
    check_id: str
    status: HealthStatus
    metrics: HealthMetrics
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


class IServiceRegistry(ABC):
    """Base interface for service registry."""

    @abstractmethod
    def register_service(self, service_info: ServiceInfo, config: Optional[ServiceConfig] = None) -> ServiceRegistrationResult:
        """Register a new service."""
        pass

    @abstractmethod
    def unregister_service(self, service_id: str) -> bool:
        """Unregister a service."""
        pass

    @abstractmethod
    def get_service(self, service_id: str) -> Optional[ServiceInfo]:
        """Get service information."""
        pass

    @abstractmethod
    def list_services(self, service_type: Optional[ServiceType] = None, status: Optional[ServiceStatus] = None) -> List[ServiceInfo]:
        """List registered services."""
        pass

    @abstractmethod
    def update_service_status(self, service_id: str, status: ServiceStatus) -> bool:
        """Update service status."""
        pass

    @abstractmethod
    def add_dependency(self, dependency: ServiceDependency) -> bool:
        """Add service dependency."""
        pass

    @abstractmethod
    def get_dependencies(self, service_id: str) -> List[ServiceDependency]:
        """Get service dependencies."""
        pass

    @abstractmethod
    def start_service(self, service_id: str) -> bool:
        """Start a service."""
        pass

    @abstractmethod
    def stop_service(self, service_id: str) -> bool:
        """Stop a service."""
        pass


class ITaskScheduler(ABC):
    """Base interface for background task scheduler."""

    @abstractmethod
    async def schedule_task(self, task: BackgroundTask) -> bool:
        """Schedule a background task."""
        pass

    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get task information."""
        pass

    @abstractmethod
    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[BackgroundTask]:
        """List scheduled tasks."""
        pass

    @abstractmethod
    async def execute_task(self, task_id: str) -> TaskExecutionResult:
        """Execute a specific task."""
        pass

    @abstractmethod
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task execution result."""
        pass

    @abstractmethod
    async def start_scheduler(self) -> None:
        """Start the task scheduler."""
        pass

    @abstractmethod
    async def stop_scheduler(self) -> None:
        """Stop the task scheduler."""
        pass


class IMaintenanceService(ABC):
    """Base interface for maintenance service."""

    @abstractmethod
    def schedule_maintenance(self, task: MaintenanceTask) -> bool:
        """Schedule a maintenance task."""
        pass

    @abstractmethod
    def cancel_maintenance(self, task_id: str) -> bool:
        """Cancel a maintenance task."""
        pass

    @abstractmethod
    def get_maintenance_task(self, task_id: str) -> Optional[MaintenanceTask]:
        """Get maintenance task information."""
        pass

    @abstractmethod
    def list_maintenance_tasks(self, maintenance_type: Optional[MaintenanceType] = None) -> List[MaintenanceTask]:
        """List maintenance tasks."""
        pass

    @abstractmethod
    async def execute_maintenance(self, task_id: str) -> MaintenanceExecutionResult:
        """Execute a maintenance task."""
        pass

    @abstractmethod
    def get_maintenance_history(self, days: int = 7) -> List[MaintenanceResult]:
        """Get maintenance execution history."""
        pass

    @abstractmethod
    async def start_service(self) -> None:
        """Start the maintenance service."""
        pass

    @abstractmethod
    async def stop_service(self) -> None:
        """Stop the maintenance service."""
        pass


class IHealthMonitor(ABC):
    """Base interface for health monitor."""

    @abstractmethod
    def register_health_check(self, health_check: HealthCheck) -> bool:
        """Register a health check."""
        pass

    @abstractmethod
    def unregister_health_check(self, check_id: str) -> bool:
        """Unregister a health check."""
        pass

    @abstractmethod
    async def execute_health_check(self, check_id: str) -> HealthCheckResult:
        """Execute a specific health check."""
        pass

    @abstractmethod
    def get_service_health(self, service_id: str) -> Optional[HealthMetrics]:
        """Get current health metrics for a service."""
        pass

    @abstractmethod
    def get_health_history(self, service_id: str, hours: int = 24) -> List[HealthMetrics]:
        """Get health metrics history."""
        pass

    @abstractmethod
    def create_alert(self, alert: ServiceAlert) -> bool:
        """Create a service alert."""
        pass

    @abstractmethod
    def get_active_alerts(self, service_id: Optional[str] = None) -> List[ServiceAlert]:
        """Get active alerts."""
        pass

    @abstractmethod
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        pass

    @abstractmethod
    async def start_monitoring(self) -> None:
        """Start health monitoring."""
        pass

    @abstractmethod
    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        pass
