"""
Module: resource_monitoring_db_service
Description: Database service layer for Phase 2 resource monitoring that initializes and coordinates
            all resource monitoring database modules with proper lifecycle management.
Phase: 2
Location: /src/modules/database/resource_monitoring_db_service.py
"""

# Standard library imports
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager

# Resource monitoring database imports
from src.modules.database.resource_monitoring_db.monitoring_metrics_db.monitoring_metrics_db import (
    MonitoringMetricsDB
)
from src.modules.database.resource_monitoring_db.performance_history_db.performance_history_db import (
    PerformanceHistoryDB
)
from src.modules.database.resource_monitoring_db.optimization_log_db.optimization_log_db import (
    OptimizationLogDB
)
from src.modules.database.resource_monitoring_db.threshold_config_db.threshold_config_db import (
    ThresholdConfigDB
)
from src.modules.database.resource_monitoring_db.thermal_history_db.thermal_history_db import (
    ThermalHistoryDB
)

# Resource monitoring imports
from src.modules.logic.resource_monitor_lg.hardware_monitor_lg.hardware_monitor_lg import ResourceMetrics


class DatabaseServiceStatus(Enum):
    """Database service status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DatabaseServiceConfig:
    """Configuration for database service."""
    enable_metrics_storage: bool = True
    enable_performance_history: bool = True
    enable_optimization_logging: bool = True
    enable_threshold_management: bool = True
    enable_thermal_history: bool = True
    metrics_retention_days: int = 30
    performance_retention_days: int = 7
    optimization_retention_days: int = 90
    thermal_retention_days: int = 7
    batch_size: int = 100
    flush_interval_seconds: float = 5.0


@dataclass
class DatabaseServiceMetrics:
    """Database service metrics."""
    status: DatabaseServiceStatus
    total_records_stored: int
    metrics_records: int
    performance_records: int
    optimization_records: int
    thermal_records: int
    last_flush: Optional[datetime]
    errors_encountered: int


class ResourceMonitoringDatabaseService:
    """
    Resource monitoring database service.

    Coordinates all Phase 2 database modules with:
    - Unified initialization and lifecycle management
    - Batch processing for performance
    - Automatic data retention management
    - Error handling and recovery
    - Performance monitoring and optimization
    """

    def __init__(
        self,
        app_state_manager: AppStateManager,
        config: Optional[DatabaseServiceConfig] = None
    ):
        """
        Initialize resource monitoring database service.

        Args:
            app_state_manager: Application state manager
            config: Database service configuration
        """
        self._app_state_manager = app_state_manager
        self._config = config or DatabaseServiceConfig()
        self._logger = get_log_manager(app_state_manager).get_logger(__name__)

        # Service state
        self._status = DatabaseServiceStatus.STOPPED
        self._flush_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()

        # Database components
        self._monitoring_metrics_db: Optional[MonitoringMetricsDB] = None
        self._performance_history_db: Optional[PerformanceHistoryDB] = None
        self._optimization_log_db: Optional[OptimizationLogDB] = None
        self._threshold_config_db: Optional[ThresholdConfigDB] = None
        self._thermal_history_db: Optional[ThermalHistoryDB] = None

        # Batch processing
        self._pending_metrics: List[Dict[str, Any]] = []
        self._pending_performance: List[Dict[str, Any]] = []
        self._pending_optimizations: List[Dict[str, Any]] = []
        self._pending_thermal: List[Dict[str, Any]] = []

        # Service metrics
        self._service_metrics = DatabaseServiceMetrics(
            status=DatabaseServiceStatus.STOPPED,
            total_records_stored=0,
            metrics_records=0,
            performance_records=0,
            optimization_records=0,
            thermal_records=0,
            last_flush=None,
            errors_encountered=0
        )

        self._logger.info("Resource monitoring database service initialized")

    async def start_service(self) -> bool:
        """Start the database service."""
        try:
            with self._lock:
                if self._status != DatabaseServiceStatus.STOPPED:
                    self._logger.warning(f"Service already running (status: {self._status.value})")
                    return False

                self._status = DatabaseServiceStatus.STARTING

            self._logger.info("Starting resource monitoring database service...")

            # Initialize database components
            await self._initialize_databases()

            # Start background tasks
            self._flush_task = asyncio.create_task(self._flush_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            # Update service state
            with self._lock:
                self._status = DatabaseServiceStatus.RUNNING
                self._service_metrics.status = DatabaseServiceStatus.RUNNING

            self._logger.info("Resource monitoring database service started successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to start database service: {e}", exc_info=True)

            with self._lock:
                self._status = DatabaseServiceStatus.ERROR
                self._service_metrics.status = DatabaseServiceStatus.ERROR
                self._service_metrics.errors_encountered += 1

            return False

    async def _initialize_databases(self) -> None:
        """Initialize all database components."""
        try:
            if self._config.enable_metrics_storage:
                self._monitoring_metrics_db = MonitoringMetricsDB()
                await self._monitoring_metrics_db.initialize()

            if self._config.enable_performance_history:
                self._performance_history_db = PerformanceHistoryDB()
                await self._performance_history_db.initialize()

            if self._config.enable_optimization_logging:
                self._optimization_log_db = OptimizationLogDB()
                await self._optimization_log_db.initialize()

            if self._config.enable_threshold_management:
                self._threshold_config_db = ThresholdConfigDB()
                await self._threshold_config_db.initialize()

            if self._config.enable_thermal_history:
                self._thermal_history_db = ThermalHistoryDB()
                await self._thermal_history_db.initialize()

            self._logger.info("All database components initialized")

        except Exception as e:
            self._logger.error(f"Failed to initialize databases: {e}")
            raise
