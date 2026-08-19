"""
MikroDok Background Services Package
Provides comprehensive background services functionality including service registry, task scheduling, maintenance services, and health monitoring.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        # Interfaces
        IServiceRegistry,
        ITaskScheduler,
        IMaintenanceService,
        IHealthMonitor,
        
        # Enums
        ServiceStatus,
        ServiceType,
        TaskStatus,
        TaskPriority,
        MaintenanceType,
        HealthStatus,
        AlertLevel,
        
        # Data Classes
        ServiceInfo,
        ServiceDependency,
        BackgroundTask,
        TaskResult,
        MaintenanceTask,
        MaintenanceResult,
        HealthCheck,
        HealthMetrics,
        ServiceAlert,
        
        # Configuration Classes
        ServiceConfig,
        TaskSchedulerConfig,
        MaintenanceConfig,
        HealthMonitorConfig,
        
        # Result Classes
        ServiceRegistrationResult,
        TaskExecutionResult,
        MaintenanceExecutionResult,
        HealthCheckResult
    )
except ImportError:
    pass

# Import service registry components
try:
    from .service_registry_lg.service_registry_lg import (
        ServiceRegistry,
        ServiceManager,
        DependencyResolver,
        ServiceLifecycleManager
    )
except ImportError:
    pass

# Import task scheduler components
try:
    from .task_scheduler_lg.task_scheduler_lg import (
        BackgroundTaskScheduler,
        TaskQueue,
        TaskExecutor,
        TaskDependencyManager
    )
except ImportError:
    pass

# Import maintenance service components
try:
    from .maintenance_service_lg.maintenance_service_lg import (
        MaintenanceService,
        MaintenanceScheduler,
        CleanupManager,
        SystemHealthChecker
    )
except ImportError:
    pass

# Import health monitor components
try:
    from .health_monitor_lg.health_monitor_lg import (
        HealthMonitor,
        ServiceHealthTracker,
        AlertManager,
        HealthMetricsCollector
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IServiceRegistry',
    'ITaskScheduler', 
    'IMaintenanceService',
    'IHealthMonitor',
    'ServiceStatus',
    'ServiceType',
    'TaskStatus',
    'TaskPriority',
    'MaintenanceType',
    'HealthStatus',
    'AlertLevel',
    'ServiceInfo',
    'ServiceDependency',
    'BackgroundTask',
    'TaskResult',
    'MaintenanceTask',
    'MaintenanceResult',
    'HealthCheck',
    'HealthMetrics',
    'ServiceAlert',
    'ServiceConfig',
    'TaskSchedulerConfig',
    'MaintenanceConfig',
    'HealthMonitorConfig',
    'ServiceRegistrationResult',
    'TaskExecutionResult',
    'MaintenanceExecutionResult',
    'HealthCheckResult',
    
    # Service Registry
    'ServiceRegistry',
    'ServiceManager',
    'DependencyResolver',
    'ServiceLifecycleManager',
    
    # Task Scheduler
    'BackgroundTaskScheduler',
    'TaskQueue',
    'TaskExecutor',
    'TaskDependencyManager',
    
    # Maintenance Service
    'MaintenanceService',
    'MaintenanceScheduler',
    'CleanupManager',
    'SystemHealthChecker',
    
    # Health Monitor
    'HealthMonitor',
    'ServiceHealthTracker',
    'AlertManager',
    'HealthMetricsCollector'
]
