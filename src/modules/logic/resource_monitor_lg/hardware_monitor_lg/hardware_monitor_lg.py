"""
Module: hardware_monitor_lg
Description: Core monitoring service that continuously tracks GPU, CPU, RAM, and storage utilization with configurable sampling intervals
Phase: 2
Location: /src/modules/logic/resource_monitor_lg/hardware_monitor_lg/
"""

# Standard library imports
import asyncio
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Union
import psutil

# Third-party imports
try:
    import GPUtil
    GPU_UTIL_AVAILABLE = True
except ImportError:
    GPU_UTIL_AVAILABLE = False

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine


class AlertSeverity(Enum):
    """Alert severity levels for resource monitoring."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ResourceMetrics:
    """Comprehensive resource utilization metrics."""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_usage_percent: float
    disk_read_mb_per_sec: float
    disk_write_mb_per_sec: float
    gpu_usage_percent: Optional[float] = None
    gpu_memory_usage_percent: Optional[float] = None
    gpu_temperature_celsius: Optional[float] = None
    network_sent_mb_per_sec: float = 0.0
    network_recv_mb_per_sec: float = 0.0
    swap_usage_percent: float = 0.0
    load_average: Optional[List[float]] = None


@dataclass
class MonitoringThresholds:
    """Configurable thresholds for resource monitoring alerts."""
    cpu_warning: float = 80.0
    cpu_critical: float = 95.0
    memory_warning: float = 85.0
    memory_critical: float = 95.0
    disk_warning: float = 85.0
    disk_critical: float = 95.0
    gpu_warning: float = 85.0
    gpu_critical: float = 95.0
    temperature_warning: float = 75.0
    temperature_critical: float = 85.0


@dataclass
class MonitoringConfiguration:
    """Configuration for hardware monitoring."""
    sampling_interval_seconds: float = 1.0
    enable_gpu_monitoring: bool = True
    enable_network_monitoring: bool = True
    enable_disk_io_monitoring: bool = True
    history_retention_minutes: int = 60
    alert_cooldown_seconds: int = 30
    thresholds: MonitoringThresholds = field(default_factory=MonitoringThresholds)


@dataclass
class ResourceAlert:
    """Resource monitoring alert."""
    timestamp: datetime
    resource_type: str
    severity: AlertSeverity
    message: str
    current_value: float
    threshold_value: float
    metric_name: str


class IResourceMonitor(ABC):
    """Interface for resource monitors."""
    
    @abstractmethod
    async def start_monitoring(self) -> None:
        """Start the monitoring process."""
        pass
    
    @abstractmethod
    async def stop_monitoring(self) -> None:
        """Stop the monitoring process."""
        pass
    
    @abstractmethod
    def get_current_metrics(self) -> ResourceMetrics:
        """Get current resource metrics."""
        pass
    
    @abstractmethod
    def get_metrics_history(self, minutes: int = 5) -> List[ResourceMetrics]:
        """Get historical metrics."""
        pass
    
    @abstractmethod
    def configure_thresholds(self, thresholds: MonitoringThresholds) -> None:
        """Configure monitoring thresholds."""
        pass


class HardwareMonitor(IResourceMonitor):
    """Core hardware monitoring service with real-time resource tracking."""
    
    def __init__(self, 
                 config: Optional[MonitoringConfiguration] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the hardware monitor."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("hardware_monitor")
        self._validation_engine = ValidationEngine()
        
        # Configuration
        self._config = config or MonitoringConfiguration()
        self._thresholds = self._config.thresholds
        
        # Monitoring state
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        
        # Metrics storage
        self._metrics_history: List[ResourceMetrics] = []
        self._current_metrics: Optional[ResourceMetrics] = None
        self._last_alert_times: Dict[str, datetime] = {}
        
        # Alert callbacks
        self._alert_callbacks: List[Callable[[ResourceAlert], None]] = []
        
        # Performance tracking
        self._last_disk_io = None
        self._last_network_io = None
        self._last_measurement_time = None
        
        self._logger.info("Hardware monitor initialized")
    
    async def start_monitoring(self) -> None:
        """Start continuous hardware monitoring."""
        with self._lock:
            if self._is_monitoring:
                self._logger.warning("Monitoring already started")
                return
            
            self._is_monitoring = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._logger.info("Hardware monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop hardware monitoring."""
        with self._lock:
            if not self._is_monitoring:
                return
            
            self._is_monitoring = False
            
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                self._monitoring_task = None
            
            self._logger.info("Hardware monitoring stopped")
    
    def get_current_metrics(self) -> ResourceMetrics:
        """Get the most recent resource metrics."""
        with self._lock:
            if self._current_metrics is None:
                # Collect metrics synchronously if none available
                return self._collect_metrics()
            return self._current_metrics
    
    def get_metrics_history(self, minutes: int = 5) -> List[ResourceMetrics]:
        """Get historical metrics for the specified time period."""
        with self._lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            return [m for m in self._metrics_history if m.timestamp >= cutoff_time]
    
    def configure_thresholds(self, thresholds: MonitoringThresholds) -> None:
        """Configure monitoring thresholds."""
        with self._lock:
            self._thresholds = thresholds
            self._config.thresholds = thresholds
            self._logger.info("Monitoring thresholds updated")
    
    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]) -> None:
        """Add a callback for resource alerts."""
        self._alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable[[ResourceAlert], None]) -> None:
        """Remove an alert callback."""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._is_monitoring:
                start_time = time.time()
                
                # Collect metrics
                metrics = self._collect_metrics()
                
                with self._lock:
                    self._current_metrics = metrics
                    self._metrics_history.append(metrics)
                    
                    # Cleanup old metrics
                    cutoff_time = datetime.now(timezone.utc) - timedelta(
                        minutes=self._config.history_retention_minutes
                    )
                    self._metrics_history = [
                        m for m in self._metrics_history if m.timestamp >= cutoff_time
                    ]
                
                # Check thresholds and generate alerts
                self._check_thresholds(metrics)
                
                # Calculate sleep time to maintain sampling interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self._config.sampling_interval_seconds - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            self._logger.info("Monitoring loop cancelled")
            raise
        except Exception as e:
            self._logger.error(f"Error in monitoring loop: {str(e)}")
            raise

    def _collect_metrics(self) -> ResourceMetrics:
        """Collect current system resource metrics."""
        try:
            current_time = datetime.now(timezone.utc)

            # CPU metrics
            cpu_usage = psutil.cpu_percent(interval=None)

            # Memory metrics
            memory = psutil.virtual_memory()
            memory_usage_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)

            # Swap metrics
            swap = psutil.swap_memory()
            swap_usage_percent = swap.percent if swap.total > 0 else 0.0

            # Disk metrics
            disk_usage_percent = 0.0
            disk_read_mb_per_sec = 0.0
            disk_write_mb_per_sec = 0.0

            if self._config.enable_disk_io_monitoring:
                disk_usage = psutil.disk_usage('/')
                disk_usage_percent = (disk_usage.used / disk_usage.total) * 100

                # Calculate disk I/O rates
                current_disk_io = psutil.disk_io_counters()
                if current_disk_io and self._last_disk_io and self._last_measurement_time:
                    time_delta = (current_time - self._last_measurement_time).total_seconds()
                    if time_delta > 0:
                        read_bytes_delta = current_disk_io.read_bytes - self._last_disk_io.read_bytes
                        write_bytes_delta = current_disk_io.write_bytes - self._last_disk_io.write_bytes
                        disk_read_mb_per_sec = (read_bytes_delta / time_delta) / (1024**2)
                        disk_write_mb_per_sec = (write_bytes_delta / time_delta) / (1024**2)

                self._last_disk_io = current_disk_io

            # Network metrics
            network_sent_mb_per_sec = 0.0
            network_recv_mb_per_sec = 0.0

            if self._config.enable_network_monitoring:
                current_network_io = psutil.net_io_counters()
                if current_network_io and self._last_network_io and self._last_measurement_time:
                    time_delta = (current_time - self._last_measurement_time).total_seconds()
                    if time_delta > 0:
                        sent_bytes_delta = current_network_io.bytes_sent - self._last_network_io.bytes_sent
                        recv_bytes_delta = current_network_io.bytes_recv - self._last_network_io.bytes_recv
                        network_sent_mb_per_sec = (sent_bytes_delta / time_delta) / (1024**2)
                        network_recv_mb_per_sec = (recv_bytes_delta / time_delta) / (1024**2)

                self._last_network_io = current_network_io

            # GPU metrics (if available)
            gpu_usage_percent = None
            gpu_memory_usage_percent = None
            gpu_temperature_celsius = None

            if self._config.enable_gpu_monitoring and GPU_UTIL_AVAILABLE:
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]  # Use first GPU
                        gpu_usage_percent = gpu.load * 100
                        gpu_memory_usage_percent = gpu.memoryUtil * 100
                        gpu_temperature_celsius = gpu.temperature
                except Exception as e:
                    self._logger.debug(f"GPU monitoring error: {str(e)}")

            # Load average (Unix-like systems)
            load_average = None
            try:
                load_average = list(psutil.getloadavg())
            except (AttributeError, OSError):
                # Not available on Windows
                pass

            self._last_measurement_time = current_time

            return ResourceMetrics(
                timestamp=current_time,
                cpu_usage_percent=cpu_usage,
                memory_usage_percent=memory_usage_percent,
                memory_used_gb=memory_used_gb,
                memory_total_gb=memory_total_gb,
                disk_usage_percent=disk_usage_percent,
                disk_read_mb_per_sec=disk_read_mb_per_sec,
                disk_write_mb_per_sec=disk_write_mb_per_sec,
                gpu_usage_percent=gpu_usage_percent,
                gpu_memory_usage_percent=gpu_memory_usage_percent,
                gpu_temperature_celsius=gpu_temperature_celsius,
                network_sent_mb_per_sec=network_sent_mb_per_sec,
                network_recv_mb_per_sec=network_recv_mb_per_sec,
                swap_usage_percent=swap_usage_percent,
                load_average=load_average
            )

        except Exception as e:
            self._logger.error(f"Error collecting metrics: {str(e)}")
            # Return default metrics on error
            return ResourceMetrics(
                timestamp=datetime.now(timezone.utc),
                cpu_usage_percent=0.0,
                memory_usage_percent=0.0,
                memory_used_gb=0.0,
                memory_total_gb=8.0,
                disk_usage_percent=0.0,
                disk_read_mb_per_sec=0.0,
                disk_write_mb_per_sec=0.0
            )

    def _check_thresholds(self, metrics: ResourceMetrics) -> None:
        """Check metrics against thresholds and generate alerts."""
        current_time = datetime.now(timezone.utc)

        # Check CPU usage
        self._check_threshold(
            "cpu", metrics.cpu_usage_percent,
            self._thresholds.cpu_warning, self._thresholds.cpu_critical,
            current_time, "CPU Usage"
        )

        # Check memory usage
        self._check_threshold(
            "memory", metrics.memory_usage_percent,
            self._thresholds.memory_warning, self._thresholds.memory_critical,
            current_time, "Memory Usage"
        )

        # Check disk usage
        self._check_threshold(
            "disk", metrics.disk_usage_percent,
            self._thresholds.disk_warning, self._thresholds.disk_critical,
            current_time, "Disk Usage"
        )

        # Check GPU usage (if available)
        if metrics.gpu_usage_percent is not None:
            self._check_threshold(
                "gpu", metrics.gpu_usage_percent,
                self._thresholds.gpu_warning, self._thresholds.gpu_critical,
                current_time, "GPU Usage"
            )

        # Check GPU temperature (if available)
        if metrics.gpu_temperature_celsius is not None:
            self._check_threshold(
                "gpu_temperature", metrics.gpu_temperature_celsius,
                self._thresholds.temperature_warning, self._thresholds.temperature_critical,
                current_time, "GPU Temperature"
            )

    def _check_threshold(self, resource_type: str, current_value: float,
                        warning_threshold: float, critical_threshold: float,
                        current_time: datetime, metric_name: str) -> None:
        """Check a single metric against its thresholds."""
        alert_key = f"{resource_type}_alert"

        # Check if we're in cooldown period
        if alert_key in self._last_alert_times:
            time_since_last = (current_time - self._last_alert_times[alert_key]).total_seconds()
            if time_since_last < self._config.alert_cooldown_seconds:
                return

        severity = None
        threshold_value = None

        if current_value >= critical_threshold:
            severity = AlertSeverity.CRITICAL
            threshold_value = critical_threshold
        elif current_value >= warning_threshold:
            severity = AlertSeverity.HIGH
            threshold_value = warning_threshold

        if severity:
            alert = ResourceAlert(
                timestamp=current_time,
                resource_type=resource_type,
                severity=severity,
                message=f"{metric_name} is {severity.value.lower()}: {current_value:.1f}%",
                current_value=current_value,
                threshold_value=threshold_value,
                metric_name=metric_name
            )

            self._last_alert_times[alert_key] = current_time
            self._trigger_alert(alert)

    def _trigger_alert(self, alert: ResourceAlert) -> None:
        """Trigger an alert by calling all registered callbacks."""
        self._logger.warning(f"Resource alert: {alert.message}")

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self._logger.error(f"Error in alert callback: {str(e)}")

    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        try:
            info = {
                "cpu_count": psutil.cpu_count(),
                "cpu_count_logical": psutil.cpu_count(logical=True),
                "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                "disk_partitions": [],
                "boot_time": datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc),
                "platform": psutil.WINDOWS if hasattr(psutil, 'WINDOWS') else "unknown"
            }

            # Disk information
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    info["disk_partitions"].append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total_gb": usage.total / (1024**3),
                        "used_gb": usage.used / (1024**3),
                        "free_gb": usage.free / (1024**3)
                    })
                except (PermissionError, OSError):
                    continue

            # GPU information (if available)
            if GPU_UTIL_AVAILABLE:
                try:
                    gpus = GPUtil.getGPUs()
                    info["gpus"] = []
                    for gpu in gpus:
                        info["gpus"].append({
                            "id": gpu.id,
                            "name": gpu.name,
                            "memory_total_mb": gpu.memoryTotal,
                            "driver_version": gpu.driver
                        })
                except Exception as e:
                    self._logger.debug(f"GPU info error: {str(e)}")
                    info["gpus"] = []
            else:
                info["gpus"] = []

            return info

        except Exception as e:
            self._logger.error(f"Error getting system info: {str(e)}")
            return {"error": str(e)}

    def __del__(self):
        """Cleanup on destruction."""
        if hasattr(self, '_is_monitoring') and self._is_monitoring:
            asyncio.create_task(self.stop_monitoring())
