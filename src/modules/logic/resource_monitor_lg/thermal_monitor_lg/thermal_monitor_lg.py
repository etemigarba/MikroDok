"""
Module: thermal_monitor_lg
Description: Temperature monitoring system with throttling detection and automatic performance adjustment capabilities
Phase: 2
Location: /src/modules/logic/resource_monitor_lg/thermal_monitor_lg/
"""

# Standard library imports
import asyncio
import platform
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import psutil

# Third-party imports
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine


class ThermalZone(Enum):
    """Types of thermal zones."""
    CPU = "CPU"
    GPU = "GPU"
    MOTHERBOARD = "MOTHERBOARD"
    MEMORY = "MEMORY"
    STORAGE = "STORAGE"
    AMBIENT = "AMBIENT"
    POWER_SUPPLY = "POWER_SUPPLY"
    UNKNOWN = "UNKNOWN"


class ThrottleReason(Enum):
    """Reasons for thermal throttling."""
    TEMPERATURE_LIMIT = "TEMPERATURE_LIMIT"
    POWER_LIMIT = "POWER_LIMIT"
    CURRENT_LIMIT = "CURRENT_LIMIT"
    VOLTAGE_LIMIT = "VOLTAGE_LIMIT"
    THERMAL_DESIGN_POWER = "THERMAL_DESIGN_POWER"
    SOFTWARE_LIMIT = "SOFTWARE_LIMIT"
    UNKNOWN = "UNKNOWN"


class ThermalSeverity(Enum):
    """Thermal alert severity levels."""
    NORMAL = "NORMAL"
    WARM = "WARM"
    HOT = "HOT"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class TemperatureThresholds:
    """Temperature thresholds for different severity levels."""
    normal_max: float = 60.0  # Celsius
    warm_threshold: float = 70.0
    hot_threshold: float = 80.0
    critical_threshold: float = 90.0
    emergency_threshold: float = 95.0
    hysteresis: float = 5.0  # Temperature drop needed to clear alert


@dataclass
class ThrottlingInfo:
    """Information about thermal throttling events."""
    is_throttling: bool
    throttle_reasons: List[ThrottleReason]
    throttle_start_time: Optional[datetime]
    throttle_duration_seconds: float
    performance_reduction_percent: float
    frequency_reduction_mhz: Optional[int]
    power_reduction_watts: Optional[float]
    recovery_time_estimate_seconds: Optional[float]


@dataclass
class ThermalSensor:
    """Individual thermal sensor information."""
    sensor_id: str
    name: str
    thermal_zone: ThermalZone
    current_temperature: float
    max_temperature: Optional[float]
    critical_temperature: Optional[float]
    is_active: bool
    last_updated: datetime
    sensor_path: Optional[str] = None
    accuracy: Optional[float] = None  # ±degrees


@dataclass
class ThermalMetrics:
    """Comprehensive thermal metrics."""
    timestamp: datetime
    sensors: List[ThermalSensor]
    cpu_temperature: Optional[float]
    gpu_temperature: Optional[float]
    motherboard_temperature: Optional[float]
    memory_temperature: Optional[float]
    storage_temperature: Optional[float]
    ambient_temperature: Optional[float]
    highest_temperature: float
    average_temperature: float
    thermal_severity: ThermalSeverity
    throttling_info: ThrottlingInfo
    cooling_efficiency: float  # 0.0 to 1.0
    temperature_trend: float  # degrees per minute
    heat_generation_estimate: float  # watts


class ThermalMonitor:
    """Advanced thermal monitoring with throttling detection and performance adjustment."""
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the thermal monitor."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("thermal_monitor")
        self._validation_engine = ValidationEngine()
        
        # Monitoring state
        self._lock = threading.RLock()
        self._monitoring_enabled = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._sampling_interval = 2.0  # Slower sampling for thermal
        self._history_retention_minutes = 120  # Longer retention for thermal analysis
        
        # Metrics storage
        self._metrics_history: List[ThermalMetrics] = []
        self._current_metrics: Optional[ThermalMetrics] = None
        
        # Thermal sensors
        self._thermal_sensors: List[ThermalSensor] = []
        self._sensor_refresh_interval = 300  # Refresh sensors every 5 minutes
        self._last_sensor_refresh: Optional[datetime] = None
        
        # Thresholds and configuration
        self._thresholds = TemperatureThresholds()
        self._enable_auto_throttling = True
        self._throttling_active = False
        self._throttle_start_time: Optional[datetime] = None
        
        # Alert callbacks
        self._thermal_alert_callbacks: List[Callable[[ThermalSeverity, float], None]] = []
        self._throttling_callbacks: List[Callable[[ThrottlingInfo], None]] = []
        
        # Performance tracking
        self._last_temperatures: Dict[str, float] = {}
        self._temperature_history: Dict[str, List[Tuple[datetime, float]]] = {}
        
        # Initialize thermal detection
        self._initialize_thermal_sensors()
        
        self._logger.info(f"Thermal monitor initialized with {len(self._thermal_sensors)} sensors")
    
    def _initialize_thermal_sensors(self) -> None:
        """Initialize thermal sensor detection."""
        try:
            self._thermal_sensors.clear()
            
            # Detect CPU thermal sensors
            self._detect_cpu_sensors()
            
            # Detect GPU thermal sensors
            self._detect_gpu_sensors()
            
            # Detect system thermal sensors
            self._detect_system_sensors()
            
            self._last_sensor_refresh = datetime.now(timezone.utc)
            
        except Exception as e:
            self._logger.error(f"Error initializing thermal sensors: {str(e)}")
    
    def _detect_cpu_sensors(self) -> None:
        """Detect CPU thermal sensors."""
        try:
            # Try to get CPU temperature from psutil
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                
                for sensor_name, sensor_list in temps.items():
                    for i, sensor in enumerate(sensor_list):
                        if 'cpu' in sensor_name.lower() or 'core' in sensor_name.lower():
                            thermal_sensor = ThermalSensor(
                                sensor_id=f"cpu_{sensor_name}_{i}",
                                name=f"CPU {sensor_name} {i}",
                                thermal_zone=ThermalZone.CPU,
                                current_temperature=sensor.current,
                                max_temperature=sensor.high,
                                critical_temperature=sensor.critical,
                                is_active=True,
                                last_updated=datetime.now(timezone.utc),
                                sensor_path=sensor_name
                            )
                            self._thermal_sensors.append(thermal_sensor)
            
            # Platform-specific CPU temperature detection
            if platform.system() == "Linux":
                self._detect_linux_cpu_sensors()
            elif platform.system() == "Windows":
                self._detect_windows_cpu_sensors()
                
        except Exception as e:
            self._logger.debug(f"Error detecting CPU sensors: {str(e)}")
    
    def _detect_gpu_sensors(self) -> None:
        """Detect GPU thermal sensors."""
        try:
            if PYNVML_AVAILABLE:
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                
                for i in range(device_count):
                    try:
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        name = pynvml.nvmlDeviceGetName(handle)
                        name = name.decode() if isinstance(name, bytes) else str(name)
                        
                        # Get current temperature
                        temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                        
                        # Get temperature thresholds
                        try:
                            max_temp = pynvml.nvmlDeviceGetTemperatureThreshold(handle, pynvml.NVML_TEMPERATURE_THRESHOLD_SLOWDOWN)
                        except:
                            max_temp = None
                        
                        try:
                            critical_temp = pynvml.nvmlDeviceGetTemperatureThreshold(handle, pynvml.NVML_TEMPERATURE_THRESHOLD_SHUTDOWN)
                        except:
                            critical_temp = None
                        
                        thermal_sensor = ThermalSensor(
                            sensor_id=f"gpu_{i}",
                            name=f"GPU {i} ({name})",
                            thermal_zone=ThermalZone.GPU,
                            current_temperature=temperature,
                            max_temperature=max_temp,
                            critical_temperature=critical_temp,
                            is_active=True,
                            last_updated=datetime.now(timezone.utc),
                            accuracy=1.0  # NVIDIA sensors are typically accurate to ±1°C
                        )
                        self._thermal_sensors.append(thermal_sensor)
                        
                    except Exception as e:
                        self._logger.debug(f"Error getting GPU {i} temperature: {str(e)}")
                        
        except Exception as e:
            self._logger.debug(f"Error detecting GPU sensors: {str(e)}")
    
    def _detect_system_sensors(self) -> None:
        """Detect system thermal sensors (motherboard, memory, etc.)."""
        try:
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                
                for sensor_name, sensor_list in temps.items():
                    for i, sensor in enumerate(sensor_list):
                        sensor_name_lower = sensor_name.lower()
                        
                        # Skip CPU sensors (already handled)
                        if 'cpu' in sensor_name_lower or 'core' in sensor_name_lower:
                            continue
                        
                        # Determine thermal zone
                        thermal_zone = ThermalZone.UNKNOWN
                        if 'motherboard' in sensor_name_lower or 'mb' in sensor_name_lower:
                            thermal_zone = ThermalZone.MOTHERBOARD
                        elif 'memory' in sensor_name_lower or 'ram' in sensor_name_lower:
                            thermal_zone = ThermalZone.MEMORY
                        elif 'storage' in sensor_name_lower or 'disk' in sensor_name_lower or 'nvme' in sensor_name_lower:
                            thermal_zone = ThermalZone.STORAGE
                        elif 'ambient' in sensor_name_lower or 'case' in sensor_name_lower:
                            thermal_zone = ThermalZone.AMBIENT
                        elif 'psu' in sensor_name_lower or 'power' in sensor_name_lower:
                            thermal_zone = ThermalZone.POWER_SUPPLY
                        
                        thermal_sensor = ThermalSensor(
                            sensor_id=f"system_{sensor_name}_{i}",
                            name=f"{sensor_name} {i}",
                            thermal_zone=thermal_zone,
                            current_temperature=sensor.current,
                            max_temperature=sensor.high,
                            critical_temperature=sensor.critical,
                            is_active=True,
                            last_updated=datetime.now(timezone.utc),
                            sensor_path=sensor_name
                        )
                        self._thermal_sensors.append(thermal_sensor)
                        
        except Exception as e:
            self._logger.debug(f"Error detecting system sensors: {str(e)}")
    
    def _detect_linux_cpu_sensors(self) -> None:
        """Detect CPU sensors on Linux systems."""
        try:
            # Try reading from /sys/class/thermal
            import glob
            thermal_zones = glob.glob('/sys/class/thermal/thermal_zone*')
            
            for zone_path in thermal_zones:
                try:
                    with open(f"{zone_path}/type", 'r') as f:
                        zone_type = f.read().strip()
                    
                    with open(f"{zone_path}/temp", 'r') as f:
                        temp_millicelsius = int(f.read().strip())
                        temperature = temp_millicelsius / 1000.0
                    
                    if 'cpu' in zone_type.lower() or 'x86_pkg_temp' in zone_type.lower():
                        thermal_sensor = ThermalSensor(
                            sensor_id=f"linux_cpu_{zone_type}",
                            name=f"CPU {zone_type}",
                            thermal_zone=ThermalZone.CPU,
                            current_temperature=temperature,
                            max_temperature=None,
                            critical_temperature=None,
                            is_active=True,
                            last_updated=datetime.now(timezone.utc),
                            sensor_path=zone_path
                        )
                        self._thermal_sensors.append(thermal_sensor)
                        
                except (OSError, ValueError, FileNotFoundError):
                    continue
                    
        except Exception as e:
            self._logger.debug(f"Error detecting Linux CPU sensors: {str(e)}")
    
    def _detect_windows_cpu_sensors(self) -> None:
        """Detect CPU sensors on Windows systems."""
        try:
            # Try using WMI to get CPU temperature
            import subprocess
            
            cmd = 'Get-WmiObject -Namespace "root/OpenHardwareMonitor" -Class Sensor | Where-Object {$_.SensorType -eq "Temperature" -and $_.Name -like "*CPU*"} | Select-Object Name, Value'
            
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                for line in lines[2:]:  # Skip header lines
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            name = parts[0]
                            temperature = float(parts[1])
                            
                            thermal_sensor = ThermalSensor(
                                sensor_id=f"windows_cpu_{name}",
                                name=f"CPU {name}",
                                thermal_zone=ThermalZone.CPU,
                                current_temperature=temperature,
                                max_temperature=None,
                                critical_temperature=None,
                                is_active=True,
                                last_updated=datetime.now(timezone.utc)
                            )
                            self._thermal_sensors.append(thermal_sensor)
                            
                        except ValueError:
                            continue
                            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            self._logger.debug("Windows WMI temperature detection not available")

    async def start_monitoring(self, sampling_interval: float = 2.0) -> None:
        """Start thermal monitoring."""
        with self._lock:
            if self._monitoring_enabled:
                self._logger.warning("Thermal monitoring already started")
                return

            self._sampling_interval = sampling_interval
            self._monitoring_enabled = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._logger.info("Thermal monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop thermal monitoring."""
        with self._lock:
            if not self._monitoring_enabled:
                return

            self._monitoring_enabled = False

            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                self._monitoring_task = None

            self._logger.info("Thermal monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main thermal monitoring loop."""
        try:
            while self._monitoring_enabled:
                start_time = time.time()

                # Refresh sensors periodically
                current_time = datetime.now(timezone.utc)
                if (self._last_sensor_refresh is None or
                    (current_time - self._last_sensor_refresh).total_seconds() > self._sensor_refresh_interval):
                    self._initialize_thermal_sensors()

                # Collect metrics
                metrics = self._collect_thermal_metrics()

                with self._lock:
                    self._current_metrics = metrics
                    self._metrics_history.append(metrics)

                    # Cleanup old metrics
                    cutoff_time = datetime.now(timezone.utc) - timedelta(
                        minutes=self._history_retention_minutes
                    )
                    self._metrics_history = [
                        m for m in self._metrics_history if m.timestamp >= cutoff_time
                    ]

                    # Check for thermal alerts and throttling
                    self._check_thermal_conditions(metrics)

                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self._sampling_interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            self._logger.info("Thermal monitoring loop cancelled")
            raise
        except Exception as e:
            self._logger.error(f"Error in thermal monitoring loop: {str(e)}")
            raise

    def _collect_thermal_metrics(self) -> ThermalMetrics:
        """Collect comprehensive thermal metrics."""
        try:
            current_time = datetime.now(timezone.utc)

            # Update sensor readings
            updated_sensors = []
            temperatures = []

            for sensor in self._thermal_sensors:
                try:
                    # Update sensor temperature
                    updated_temp = self._read_sensor_temperature(sensor)
                    if updated_temp is not None:
                        updated_sensor = ThermalSensor(
                            sensor_id=sensor.sensor_id,
                            name=sensor.name,
                            thermal_zone=sensor.thermal_zone,
                            current_temperature=updated_temp,
                            max_temperature=sensor.max_temperature,
                            critical_temperature=sensor.critical_temperature,
                            is_active=True,
                            last_updated=current_time,
                            sensor_path=sensor.sensor_path,
                            accuracy=sensor.accuracy
                        )
                        updated_sensors.append(updated_sensor)
                        temperatures.append(updated_temp)

                        # Store temperature history
                        if sensor.sensor_id not in self._temperature_history:
                            self._temperature_history[sensor.sensor_id] = []

                        self._temperature_history[sensor.sensor_id].append((current_time, updated_temp))

                        # Keep only recent history (last hour)
                        cutoff_time = current_time - timedelta(hours=1)
                        self._temperature_history[sensor.sensor_id] = [
                            (t, temp) for t, temp in self._temperature_history[sensor.sensor_id]
                            if t >= cutoff_time
                        ]

                except Exception as e:
                    self._logger.debug(f"Error reading sensor {sensor.sensor_id}: {str(e)}")
                    continue

            # Calculate aggregate metrics
            if temperatures:
                highest_temperature = max(temperatures)
                average_temperature = sum(temperatures) / len(temperatures)
            else:
                highest_temperature = 0.0
                average_temperature = 0.0

            # Extract specific zone temperatures
            cpu_temp = self._get_zone_temperature(updated_sensors, ThermalZone.CPU)
            gpu_temp = self._get_zone_temperature(updated_sensors, ThermalZone.GPU)
            motherboard_temp = self._get_zone_temperature(updated_sensors, ThermalZone.MOTHERBOARD)
            memory_temp = self._get_zone_temperature(updated_sensors, ThermalZone.MEMORY)
            storage_temp = self._get_zone_temperature(updated_sensors, ThermalZone.STORAGE)
            ambient_temp = self._get_zone_temperature(updated_sensors, ThermalZone.AMBIENT)

            # Determine thermal severity
            thermal_severity = self._calculate_thermal_severity(highest_temperature)

            # Check for throttling
            throttling_info = self._detect_throttling(updated_sensors)

            # Calculate cooling efficiency and temperature trend
            cooling_efficiency = self._calculate_cooling_efficiency(updated_sensors)
            temperature_trend = self._calculate_temperature_trend(updated_sensors)

            # Estimate heat generation
            heat_generation = self._estimate_heat_generation(updated_sensors)

            return ThermalMetrics(
                timestamp=current_time,
                sensors=updated_sensors,
                cpu_temperature=cpu_temp,
                gpu_temperature=gpu_temp,
                motherboard_temperature=motherboard_temp,
                memory_temperature=memory_temp,
                storage_temperature=storage_temp,
                ambient_temperature=ambient_temp,
                highest_temperature=highest_temperature,
                average_temperature=average_temperature,
                thermal_severity=thermal_severity,
                throttling_info=throttling_info,
                cooling_efficiency=cooling_efficiency,
                temperature_trend=temperature_trend,
                heat_generation_estimate=heat_generation
            )

        except Exception as e:
            self._logger.error(f"Error collecting thermal metrics: {str(e)}")
            # Return default metrics on error
            return ThermalMetrics(
                timestamp=datetime.now(timezone.utc),
                sensors=[],
                cpu_temperature=None,
                gpu_temperature=None,
                motherboard_temperature=None,
                memory_temperature=None,
                storage_temperature=None,
                ambient_temperature=None,
                highest_temperature=0.0,
                average_temperature=0.0,
                thermal_severity=ThermalSeverity.NORMAL,
                throttling_info=ThrottlingInfo(
                    is_throttling=False,
                    throttle_reasons=[],
                    throttle_start_time=None,
                    throttle_duration_seconds=0.0,
                    performance_reduction_percent=0.0,
                    frequency_reduction_mhz=None,
                    power_reduction_watts=None,
                    recovery_time_estimate_seconds=None
                ),
                cooling_efficiency=1.0,
                temperature_trend=0.0,
                heat_generation_estimate=0.0
            )

    def _read_sensor_temperature(self, sensor: ThermalSensor) -> Optional[float]:
        """Read current temperature from a sensor."""
        try:
            if sensor.thermal_zone == ThermalZone.GPU and PYNVML_AVAILABLE:
                # GPU sensor reading
                gpu_id = int(sensor.sensor_id.split('_')[1])
                handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
                return float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))

            elif sensor.sensor_path and hasattr(psutil, 'sensors_temperatures'):
                # psutil sensor reading
                temps = psutil.sensors_temperatures()
                if sensor.sensor_path in temps:
                    sensor_index = int(sensor.sensor_id.split('_')[-1]) if '_' in sensor.sensor_id else 0
                    if sensor_index < len(temps[sensor.sensor_path]):
                        return temps[sensor.sensor_path][sensor_index].current

            elif sensor.sensor_path and sensor.sensor_path.startswith('/sys/class/thermal'):
                # Linux thermal zone reading
                with open(f"{sensor.sensor_path}/temp", 'r') as f:
                    temp_millicelsius = int(f.read().strip())
                    return temp_millicelsius / 1000.0

            return None

        except Exception as e:
            self._logger.debug(f"Error reading sensor {sensor.sensor_id}: {str(e)}")
            return None

    def _get_zone_temperature(self, sensors: List[ThermalSensor], zone: ThermalZone) -> Optional[float]:
        """Get average temperature for a specific thermal zone."""
        zone_temps = [s.current_temperature for s in sensors if s.thermal_zone == zone]
        return sum(zone_temps) / len(zone_temps) if zone_temps else None

    def _calculate_thermal_severity(self, highest_temp: float) -> ThermalSeverity:
        """Calculate thermal severity based on highest temperature."""
        if highest_temp >= self._thresholds.emergency_threshold:
            return ThermalSeverity.EMERGENCY
        elif highest_temp >= self._thresholds.critical_threshold:
            return ThermalSeverity.CRITICAL
        elif highest_temp >= self._thresholds.hot_threshold:
            return ThermalSeverity.HOT
        elif highest_temp >= self._thresholds.warm_threshold:
            return ThermalSeverity.WARM
        else:
            return ThermalSeverity.NORMAL

    def _detect_throttling(self, sensors: List[ThermalSensor]) -> ThrottlingInfo:
        """Detect thermal throttling conditions."""
        try:
            is_throttling = False
            throttle_reasons = []
            performance_reduction = 0.0

            # Check GPU throttling
            for sensor in sensors:
                if sensor.thermal_zone == ThermalZone.GPU and PYNVML_AVAILABLE:
                    try:
                        gpu_id = int(sensor.sensor_id.split('_')[1])
                        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)

                        # Check throttle reasons
                        throttle_status = pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(handle)

                        if throttle_status & pynvml.nvmlClocksThrottleReasonSwThermalSlowdown:
                            is_throttling = True
                            throttle_reasons.append(ThrottleReason.TEMPERATURE_LIMIT)

                        if throttle_status & pynvml.nvmlClocksThrottleReasonHwThermalSlowdown:
                            is_throttling = True
                            throttle_reasons.append(ThrottleReason.TEMPERATURE_LIMIT)

                        if throttle_status & pynvml.nvmlClocksThrottleReasonSwPowerCap:
                            is_throttling = True
                            throttle_reasons.append(ThrottleReason.POWER_LIMIT)

                        if throttle_status & pynvml.nvmlClocksThrottleReasonHwPowerBrakeSlowdown:
                            is_throttling = True
                            throttle_reasons.append(ThrottleReason.POWER_LIMIT)

                        # Estimate performance reduction
                        if is_throttling:
                            try:
                                current_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                                max_clock = pynvml.nvmlDeviceGetMaxClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                                if max_clock > 0:
                                    performance_reduction = max(performance_reduction,
                                                              ((max_clock - current_clock) / max_clock) * 100)
                            except:
                                pass

                    except Exception as e:
                        self._logger.debug(f"Error checking GPU throttling: {str(e)}")

            # Check CPU throttling (temperature-based heuristic)
            cpu_sensors = [s for s in sensors if s.thermal_zone == ThermalZone.CPU]
            if cpu_sensors:
                max_cpu_temp = max(s.current_temperature for s in cpu_sensors)
                if max_cpu_temp >= self._thresholds.critical_threshold:
                    is_throttling = True
                    throttle_reasons.append(ThrottleReason.TEMPERATURE_LIMIT)
                    # Estimate CPU performance reduction based on temperature
                    temp_excess = max_cpu_temp - self._thresholds.critical_threshold
                    performance_reduction = max(performance_reduction, min(50.0, temp_excess * 5))

            # Update throttling state
            if is_throttling and not self._throttling_active:
                self._throttling_active = True
                self._throttle_start_time = datetime.now(timezone.utc)
            elif not is_throttling and self._throttling_active:
                self._throttling_active = False
                self._throttle_start_time = None

            # Calculate throttle duration
            throttle_duration = 0.0
            if self._throttling_active and self._throttle_start_time:
                throttle_duration = (datetime.now(timezone.utc) - self._throttle_start_time).total_seconds()

            # Estimate recovery time
            recovery_time = None
            if is_throttling:
                # Simple heuristic: recovery time based on temperature excess
                max_temp = max((s.current_temperature for s in sensors), default=0.0)
                if max_temp > self._thresholds.hot_threshold:
                    temp_excess = max_temp - self._thresholds.hot_threshold
                    recovery_time = temp_excess * 30  # 30 seconds per degree excess

            return ThrottlingInfo(
                is_throttling=is_throttling,
                throttle_reasons=list(set(throttle_reasons)),  # Remove duplicates
                throttle_start_time=self._throttle_start_time,
                throttle_duration_seconds=throttle_duration,
                performance_reduction_percent=performance_reduction,
                frequency_reduction_mhz=None,  # Would need more detailed monitoring
                power_reduction_watts=None,    # Would need power monitoring
                recovery_time_estimate_seconds=recovery_time
            )

        except Exception as e:
            self._logger.error(f"Error detecting throttling: {str(e)}")
            return ThrottlingInfo(
                is_throttling=False,
                throttle_reasons=[],
                throttle_start_time=None,
                throttle_duration_seconds=0.0,
                performance_reduction_percent=0.0,
                frequency_reduction_mhz=None,
                power_reduction_watts=None,
                recovery_time_estimate_seconds=None
            )

    def _calculate_cooling_efficiency(self, sensors: List[ThermalSensor]) -> float:
        """Calculate cooling system efficiency (0.0 to 1.0)."""
        try:
            if not sensors:
                return 1.0

            # Simple heuristic based on temperature distribution
            temperatures = [s.current_temperature for s in sensors]
            if not temperatures:
                return 1.0

            avg_temp = sum(temperatures) / len(temperatures)
            max_temp = max(temperatures)

            # Good cooling: low average temperature and small temperature spread
            temp_spread = max_temp - min(temperatures)

            # Normalize efficiency (lower temperatures and smaller spread = better efficiency)
            temp_efficiency = max(0.0, 1.0 - (avg_temp - 30.0) / 50.0)  # 30°C baseline, 80°C max
            spread_efficiency = max(0.0, 1.0 - temp_spread / 30.0)  # 30°C max spread

            return (temp_efficiency + spread_efficiency) / 2.0

        except Exception:
            return 1.0

    def _calculate_temperature_trend(self, sensors: List[ThermalSensor]) -> float:
        """Calculate temperature trend in degrees per minute."""
        try:
            if not sensors:
                return 0.0

            trends = []
            current_time = datetime.now(timezone.utc)

            for sensor in sensors:
                if sensor.sensor_id in self._temperature_history:
                    history = self._temperature_history[sensor.sensor_id]

                    # Need at least 2 points for trend
                    if len(history) >= 2:
                        # Use last 5 minutes of data
                        cutoff_time = current_time - timedelta(minutes=5)
                        recent_history = [(t, temp) for t, temp in history if t >= cutoff_time]

                        if len(recent_history) >= 2:
                            # Simple linear trend calculation
                            time_points = [(t - recent_history[0][0]).total_seconds() for t, _ in recent_history]
                            temp_points = [temp for _, temp in recent_history]

                            # Linear regression
                            n = len(time_points)
                            sum_x = sum(time_points)
                            sum_y = sum(temp_points)
                            sum_xy = sum(x * y for x, y in zip(time_points, temp_points))
                            sum_x2 = sum(x * x for x in time_points)

                            if n * sum_x2 - sum_x * sum_x != 0:
                                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                                # Convert from degrees per second to degrees per minute
                                trend_per_minute = slope * 60.0
                                trends.append(trend_per_minute)

            # Return average trend
            return sum(trends) / len(trends) if trends else 0.0

        except Exception:
            return 0.0

    def _estimate_heat_generation(self, sensors: List[ThermalSensor]) -> float:
        """Estimate heat generation in watts."""
        try:
            # Simple heuristic based on temperature levels
            if not sensors:
                return 0.0

            total_heat = 0.0

            for sensor in sensors:
                temp = sensor.current_temperature

                # Estimate heat based on component type and temperature
                if sensor.thermal_zone == ThermalZone.CPU:
                    # CPU heat estimation (rough approximation)
                    if temp > 30:
                        total_heat += (temp - 30) * 2.0  # 2W per degree above 30°C

                elif sensor.thermal_zone == ThermalZone.GPU:
                    # GPU heat estimation
                    if temp > 30:
                        total_heat += (temp - 30) * 3.0  # 3W per degree above 30°C

                else:
                    # Other components
                    if temp > 30:
                        total_heat += (temp - 30) * 0.5  # 0.5W per degree above 30°C

            return total_heat

        except Exception:
            return 0.0

    def _check_thermal_conditions(self, metrics: ThermalMetrics) -> None:
        """Check thermal conditions and trigger alerts/actions."""
        try:
            # Check for thermal alerts
            if metrics.thermal_severity != ThermalSeverity.NORMAL:
                for callback in self._thermal_alert_callbacks:
                    try:
                        callback(metrics.thermal_severity, metrics.highest_temperature)
                    except Exception as e:
                        self._logger.error(f"Error in thermal alert callback: {str(e)}")

            # Check for throttling alerts
            if metrics.throttling_info.is_throttling:
                for callback in self._throttling_callbacks:
                    try:
                        callback(metrics.throttling_info)
                    except Exception as e:
                        self._logger.error(f"Error in throttling callback: {str(e)}")

            # Log significant thermal events
            if metrics.thermal_severity == ThermalSeverity.CRITICAL:
                self._logger.warning(f"Critical temperature detected: {metrics.highest_temperature:.1f}°C")
            elif metrics.thermal_severity == ThermalSeverity.EMERGENCY:
                self._logger.error(f"Emergency temperature detected: {metrics.highest_temperature:.1f}°C")

            if metrics.throttling_info.is_throttling:
                self._logger.warning(f"Thermal throttling active: {metrics.throttling_info.performance_reduction_percent:.1f}% performance reduction")

        except Exception as e:
            self._logger.error(f"Error checking thermal conditions: {str(e)}")

    def get_current_metrics(self) -> Optional[ThermalMetrics]:
        """Get the most recent thermal metrics."""
        with self._lock:
            if self._current_metrics is None:
                return self._collect_thermal_metrics()
            return self._current_metrics

    def get_metrics_history(self, minutes: int = 30) -> List[ThermalMetrics]:
        """Get historical thermal metrics."""
        with self._lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            return [m for m in self._metrics_history if m.timestamp >= cutoff_time]

    def get_thermal_sensors(self) -> List[ThermalSensor]:
        """Get all thermal sensors."""
        with self._lock:
            return self._thermal_sensors.copy()

    def configure_thresholds(self, thresholds: TemperatureThresholds) -> None:
        """Configure temperature thresholds."""
        with self._lock:
            self._thresholds = thresholds
            self._logger.info("Temperature thresholds updated")

    def add_thermal_alert_callback(self, callback: Callable[[ThermalSeverity, float], None]) -> None:
        """Add a thermal alert callback."""
        self._thermal_alert_callbacks.append(callback)

    def add_throttling_callback(self, callback: Callable[[ThrottlingInfo], None]) -> None:
        """Add a throttling alert callback."""
        self._throttling_callbacks.append(callback)

    def get_thermal_summary(self) -> Dict[str, Any]:
        """Get a comprehensive thermal summary."""
        with self._lock:
            current = self.get_current_metrics()
            if not current:
                return {"error": "No thermal metrics available"}

            sensor_summaries = []
            for sensor in current.sensors:
                sensor_summaries.append({
                    "name": sensor.name,
                    "zone": sensor.thermal_zone.value,
                    "temperature": sensor.current_temperature,
                    "max_temperature": sensor.max_temperature,
                    "critical_temperature": sensor.critical_temperature,
                    "is_active": sensor.is_active
                })

            return {
                "highest_temperature": current.highest_temperature,
                "average_temperature": current.average_temperature,
                "thermal_severity": current.thermal_severity.value,
                "cpu_temperature": current.cpu_temperature,
                "gpu_temperature": current.gpu_temperature,
                "motherboard_temperature": current.motherboard_temperature,
                "is_throttling": current.throttling_info.is_throttling,
                "throttle_reasons": [r.value for r in current.throttling_info.throttle_reasons],
                "performance_reduction_percent": current.throttling_info.performance_reduction_percent,
                "cooling_efficiency": current.cooling_efficiency,
                "temperature_trend_per_minute": current.temperature_trend,
                "heat_generation_watts": current.heat_generation_estimate,
                "sensor_count": len(current.sensors),
                "sensors": sensor_summaries
            }

    def is_overheating(self) -> bool:
        """Check if system is currently overheating."""
        current = self.get_current_metrics()
        if not current:
            return False

        return current.thermal_severity in [ThermalSeverity.CRITICAL, ThermalSeverity.EMERGENCY]

    def refresh_sensors(self) -> None:
        """Manually refresh thermal sensors."""
        with self._lock:
            self._logger.info("Manually refreshing thermal sensors")
            self._initialize_thermal_sensors()

    def __del__(self):
        """Cleanup on destruction."""
        if self._monitoring_enabled:
            asyncio.create_task(self.stop_monitoring())

        # Cleanup NVML
        if PYNVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
