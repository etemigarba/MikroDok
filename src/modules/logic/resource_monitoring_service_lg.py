"""
Module: resource_monitoring_service_lg
Description: Comprehensive resource monitoring service with predictive analytics
Phase: 2
Location: /src/modules/logic/
"""

# Standard library imports
import asyncio
import threading
from datetime import datetime
from enum import Enum
from typing import Optional, Set, Callable
from dataclasses import dataclass

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine

# Resource Monitor imports
from src.modules.logic.resource_monitor_lg.hardware_monitor_lg.hardware_monitor_lg import (
    HardwareMonitor, ResourceMetrics, MonitoringConfiguration, MonitoringThresholds
)


class ServiceStatus(Enum):
    """Service status enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class MonitoringMode(Enum):
    """Monitoring mode enumeration."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


@dataclass
class ServiceConfiguration:
    """Configuration for resource monitoring service."""
    monitoring_mode: MonitoringMode = MonitoringMode.STANDARD
    monitoring_interval_seconds: float = 1.0
    enable_gpu_monitoring: bool = True
    enable_thermal_monitoring: bool = True
    enable_predictions: bool = True
    enable_optimizations: bool = True
    max_history_hours: int = 24
    auto_optimization: bool = True
    performance_thresholds: Optional[MonitoringThresholds] = None


@dataclass
class ServiceMetrics:
    """Service-level metrics and status."""
    status: ServiceStatus
    uptime_seconds: float
    total_metrics_collected: int
    optimizations_triggered: int
    predictions_generated: int
    errors_encountered: int
    last_update: datetime
    current_resource_metrics: Optional[ResourceMetrics] = None


class ResourceMonitoringService:
    """Comprehensive resource monitoring service with predictive analytics."""

    def __init__(
        self,
        app_state_manager: AppStateManager,
        config: Optional[ServiceConfiguration] = None
    ):
        """
        Initialize resource monitoring service.

        Args:
            app_state_manager: Application state manager
            config: Service configuration
        """
        self._app_state_manager = app_state_manager
        self._config = config or ServiceConfiguration()
        self._logger = get_log_manager(app_state_manager).get_logger(__name__)
        self._validation_engine = ValidationEngine()

        # Service state
        self._status = ServiceStatus.STOPPED
        self._start_time: Optional[datetime] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._optimization_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()

        # Metrics and statistics
        self._service_metrics = ServiceMetrics(
            status=ServiceStatus.STOPPED,
            uptime_seconds=0.0,
            total_metrics_collected=0,
            optimizations_triggered=0,
            predictions_generated=0,
            errors_encountered=0,
            last_update=datetime.now()
        )

        # Component initialization
        self._initialize_components()

        # Event callbacks
        self._status_callbacks: Set[Callable[[ServiceStatus], None]] = set()
        self._metrics_callbacks: Set[Callable[[ResourceMetrics], None]] = set()
        self._optimization_callbacks: Set[Callable[[str], None]] = set()

        self._logger.info("Resource monitoring service initialized")

    def _initialize_components(self) -> None:
        """Initialize all monitoring components."""
        try:
            # Initialize monitoring configuration with correct parameters
            monitoring_config = MonitoringConfiguration(
                sampling_interval_seconds=self._config.monitoring_interval_seconds,
                enable_gpu_monitoring=self._config.enable_gpu_monitoring,
                enable_network_monitoring=True,
                enable_disk_io_monitoring=True,
                history_retention_minutes=60
            )

            # Initialize core monitors
            self._hardware_monitor = HardwareMonitor(monitoring_config)

            self._logger.info("All monitoring components initialized successfully")

        except Exception as e:
            self._logger.error(f"Failed to initialize monitoring components: {e}", exc_info=True)
            raise

    async def start_service(self) -> bool:
        """
        Start the resource monitoring service.

        Returns:
            True if service started successfully, False otherwise
        """
        try:
            with self._lock:
                if self._status != ServiceStatus.STOPPED:
                    self._logger.warning(f"Service already running or starting (status: {self._status.value})")
                    return False

                self._status = ServiceStatus.STARTING
                self._notify_status_change(ServiceStatus.STARTING)

            self._logger.info("Starting resource monitoring service...")

            # Start core monitors
            await self._start_monitors()

            with self._lock:
                self._status = ServiceStatus.RUNNING
                self._start_time = datetime.now()
                self._notify_status_change(ServiceStatus.RUNNING)

            self._logger.info("Resource monitoring service started successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to start resource monitoring service: {e}", exc_info=True)
            with self._lock:
                self._status = ServiceStatus.ERROR
                self._notify_status_change(ServiceStatus.ERROR)
            return False

    async def _start_monitors(self) -> None:
        """Start all monitoring components."""
        try:
            if self._hardware_monitor:
                await self._hardware_monitor.start_monitoring()

        except Exception as e:
            self._logger.error(f"Failed to start monitors: {e}", exc_info=True)
            raise

    def _notify_status_change(self, status: ServiceStatus) -> None:
        """Notify status change callbacks."""
        for callback in self._status_callbacks:
            try:
                callback(status)
            except Exception as e:
                self._logger.error(f"Error in status callback: {e}")

    async def stop_service(self) -> bool:
        """
        Stop the resource monitoring service.

        Returns:
            True if service stopped successfully, False otherwise
        """
        try:
            with self._lock:
                if self._status == ServiceStatus.STOPPED:
                    self._logger.warning("Service already stopped")
                    return True

                self._status = ServiceStatus.STOPPING
                self._notify_status_change(ServiceStatus.STOPPING)

            self._logger.info("Stopping resource monitoring service...")

            # Stop monitors
            await self._stop_monitors()

            with self._lock:
                self._status = ServiceStatus.STOPPED
                self._start_time = None
                self._notify_status_change(ServiceStatus.STOPPED)

            self._logger.info("Resource monitoring service stopped successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to stop resource monitoring service: {e}", exc_info=True)
            with self._lock:
                self._status = ServiceStatus.ERROR
                self._notify_status_change(ServiceStatus.ERROR)
            return False

    async def _stop_monitors(self) -> None:
        """Stop all monitoring components."""
        try:
            if self._hardware_monitor:
                await self._hardware_monitor.stop_monitoring()

        except Exception as e:
            self._logger.error(f"Failed to stop monitors: {e}", exc_info=True)
            raise

    def get_service_metrics(self) -> ServiceMetrics:
        """Get current service metrics."""
        with self._lock:
            if self._start_time:
                self._service_metrics.uptime_seconds = (datetime.now() - self._start_time).total_seconds()
            return self._service_metrics