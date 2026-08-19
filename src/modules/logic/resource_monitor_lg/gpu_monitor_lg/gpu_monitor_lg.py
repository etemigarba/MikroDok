"""
Module: gpu_monitor_lg
Description: Specialized GPU monitoring including VRAM usage, temperature, compute utilization, and CUDA/ROCm compatibility detection
Phase: 2
Location: /src/modules/logic/resource_monitor_lg/gpu_monitor_lg/
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
from typing import Dict, List, Optional, Any, Union
import re

# Third-party imports
try:
    import GPUtil
    GPU_UTIL_AVAILABLE = True
except ImportError:
    GPU_UTIL_AVAILABLE = False

try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine


class GPUVendor(Enum):
    """GPU vendor types."""
    NVIDIA = "NVIDIA"
    AMD = "AMD"
    INTEL = "INTEL"
    UNKNOWN = "UNKNOWN"


class ComputePlatform(Enum):
    """GPU compute platforms."""
    CUDA = "CUDA"
    ROCM = "ROCM"
    OPENCL = "OPENCL"
    DIRECTML = "DIRECTML"
    UNKNOWN = "UNKNOWN"


@dataclass
class CUDAInfo:
    """CUDA runtime information."""
    available: bool = False
    version: Optional[str] = None
    driver_version: Optional[str] = None
    device_count: int = 0
    devices: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ROCmInfo:
    """ROCm runtime information."""
    available: bool = False
    version: Optional[str] = None
    device_count: int = 0
    devices: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GPUInfo:
    """Comprehensive GPU information."""
    gpu_id: int
    name: str
    vendor: GPUVendor
    memory_total_mb: int
    memory_free_mb: int
    memory_used_mb: int
    temperature_celsius: Optional[float]
    utilization_percent: float
    memory_utilization_percent: float
    power_draw_watts: Optional[float]
    power_limit_watts: Optional[float]
    clock_speed_mhz: Optional[int]
    memory_clock_mhz: Optional[int]
    driver_version: Optional[str]
    compute_capability: Optional[str]
    pci_bus_id: Optional[str]
    uuid: Optional[str]


@dataclass
class GPUMetrics:
    """GPU performance metrics over time."""
    timestamp: datetime
    gpu_id: int
    utilization_percent: float
    memory_utilization_percent: float
    memory_used_mb: int
    memory_free_mb: int
    temperature_celsius: Optional[float]
    power_draw_watts: Optional[float]
    clock_speed_mhz: Optional[int]
    memory_clock_mhz: Optional[int]
    fan_speed_percent: Optional[float]
    throttle_reasons: List[str] = field(default_factory=list)


class GPUMonitor:
    """Specialized GPU monitoring with vendor-specific optimizations."""
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the GPU monitor."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("gpu_monitor")
        self._validation_engine = ValidationEngine()
        
        # GPU state
        self._lock = threading.RLock()
        self._gpu_infos: List[GPUInfo] = []
        self._metrics_history: Dict[int, List[GPUMetrics]] = {}
        self._cuda_info: Optional[CUDAInfo] = None
        self._rocm_info: Optional[ROCmInfo] = None
        
        # Monitoring configuration
        self._monitoring_enabled = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._sampling_interval = 1.0
        self._history_retention_minutes = 60
        
        # Initialize GPU detection
        self._initialize_gpu_detection()
        
        self._logger.info(f"GPU monitor initialized with {len(self._gpu_infos)} GPUs detected")
    
    def _initialize_gpu_detection(self) -> None:
        """Initialize GPU detection and gather system information."""
        try:
            # Detect CUDA
            self._cuda_info = self._detect_cuda()
            
            # Detect ROCm
            self._rocm_info = self._detect_rocm()
            
            # Detect GPUs
            self._detect_gpus()
            
        except Exception as e:
            self._logger.error(f"Error initializing GPU detection: {str(e)}")
    
    def _detect_cuda(self) -> CUDAInfo:
        """Detect CUDA availability and information."""
        cuda_info = CUDAInfo()
        
        try:
            if PYNVML_AVAILABLE:
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                cuda_info.available = True
                cuda_info.device_count = device_count
                
                # Get CUDA version
                try:
                    cuda_version = pynvml.nvmlSystemGetCudaDriverVersion()
                    cuda_info.version = f"{cuda_version // 1000}.{(cuda_version % 1000) // 10}"
                except:
                    pass
                
                # Get driver version
                try:
                    driver_version = pynvml.nvmlSystemGetDriverVersion()
                    cuda_info.driver_version = driver_version.decode() if isinstance(driver_version, bytes) else str(driver_version)
                except:
                    pass
                
                # Get device information
                for i in range(device_count):
                    try:
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        name = pynvml.nvmlDeviceGetName(handle)
                        name = name.decode() if isinstance(name, bytes) else str(name)
                        
                        cuda_info.devices.append({
                            "index": i,
                            "name": name,
                            "handle": handle
                        })
                    except Exception as e:
                        self._logger.debug(f"Error getting CUDA device {i}: {str(e)}")
                        
        except Exception as e:
            self._logger.debug(f"CUDA detection failed: {str(e)}")
            
        return cuda_info
    
    def _detect_rocm(self) -> ROCmInfo:
        """Detect ROCm availability and information."""
        rocm_info = ROCmInfo()
        
        try:
            # Try to detect ROCm through rocm-smi
            result = subprocess.run(
                ["rocm-smi", "--showid"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                rocm_info.available = True
                # Parse device count from output
                lines = result.stdout.strip().split('\n')
                device_count = 0
                for line in lines:
                    if 'GPU' in line and 'ID' in line:
                        device_count += 1
                rocm_info.device_count = device_count
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            self._logger.debug("ROCm not detected")
            
        return rocm_info
    
    def _detect_gpus(self) -> None:
        """Detect and catalog all available GPUs."""
        self._gpu_infos.clear()
        
        # Try NVIDIA GPUs first
        if self._cuda_info and self._cuda_info.available:
            self._detect_nvidia_gpus()
        
        # Try AMD GPUs
        if self._rocm_info and self._rocm_info.available:
            self._detect_amd_gpus()
        
        # Fallback to GPUtil if available
        if not self._gpu_infos and GPU_UTIL_AVAILABLE:
            self._detect_gpus_fallback()
    
    def _detect_nvidia_gpus(self) -> None:
        """Detect NVIDIA GPUs using NVML."""
        if not PYNVML_AVAILABLE or not self._cuda_info:
            return
        
        try:
            for device_info in self._cuda_info.devices:
                handle = device_info["handle"]
                gpu_id = device_info["index"]
                
                # Get memory info
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                
                # Get utilization
                try:
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_util = utilization.gpu
                    memory_util = utilization.memory
                except:
                    gpu_util = 0.0
                    memory_util = 0.0
                
                # Get temperature
                try:
                    temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except:
                    temperature = None
                
                # Get power info
                try:
                    power_draw = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert to watts
                except:
                    power_draw = None
                
                try:
                    power_limit = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)[1] / 1000.0
                except:
                    power_limit = None
                
                # Get clock speeds
                try:
                    graphics_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                    memory_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                except:
                    graphics_clock = None
                    memory_clock = None
                
                # Get UUID
                try:
                    uuid = pynvml.nvmlDeviceGetUUID(handle)
                    uuid = uuid.decode() if isinstance(uuid, bytes) else str(uuid)
                except:
                    uuid = None
                
                # Get PCI info
                try:
                    pci_info = pynvml.nvmlDeviceGetPciInfo(handle)
                    pci_bus_id = f"{pci_info.domain:04x}:{pci_info.bus:02x}:{pci_info.device:02x}.{pci_info.pciDeviceId}"
                except:
                    pci_bus_id = None
                
                gpu_info = GPUInfo(
                    gpu_id=gpu_id,
                    name=device_info["name"],
                    vendor=GPUVendor.NVIDIA,
                    memory_total_mb=memory_info.total // (1024 * 1024),
                    memory_free_mb=memory_info.free // (1024 * 1024),
                    memory_used_mb=memory_info.used // (1024 * 1024),
                    temperature_celsius=temperature,
                    utilization_percent=gpu_util,
                    memory_utilization_percent=memory_util,
                    power_draw_watts=power_draw,
                    power_limit_watts=power_limit,
                    clock_speed_mhz=graphics_clock,
                    memory_clock_mhz=memory_clock,
                    driver_version=self._cuda_info.driver_version,
                    compute_capability=None,  # Would need additional NVML calls
                    pci_bus_id=pci_bus_id,
                    uuid=uuid
                )
                
                self._gpu_infos.append(gpu_info)
                self._metrics_history[gpu_id] = []
                
        except Exception as e:
            self._logger.error(f"Error detecting NVIDIA GPUs: {str(e)}")
    
    def _detect_amd_gpus(self) -> None:
        """Detect AMD GPUs using ROCm tools."""
        # ROCm GPU detection would be implemented here
        # This is a placeholder for AMD GPU detection
        self._logger.debug("AMD GPU detection not fully implemented")
    
    def _detect_gpus_fallback(self) -> None:
        """Fallback GPU detection using GPUtil."""
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpu_info = GPUInfo(
                    gpu_id=gpu.id,
                    name=gpu.name,
                    vendor=self._determine_vendor(gpu.name),
                    memory_total_mb=gpu.memoryTotal,
                    memory_free_mb=gpu.memoryFree,
                    memory_used_mb=gpu.memoryUsed,
                    temperature_celsius=gpu.temperature,
                    utilization_percent=gpu.load * 100,
                    memory_utilization_percent=gpu.memoryUtil * 100,
                    power_draw_watts=None,
                    power_limit_watts=None,
                    clock_speed_mhz=None,
                    memory_clock_mhz=None,
                    driver_version=gpu.driver,
                    compute_capability=None,
                    pci_bus_id=None,
                    uuid=gpu.uuid if hasattr(gpu, 'uuid') else None
                )
                
                self._gpu_infos.append(gpu_info)
                self._metrics_history[gpu.id] = []
                
        except Exception as e:
            self._logger.error(f"Fallback GPU detection failed: {str(e)}")
    
    def _determine_vendor(self, gpu_name: str) -> GPUVendor:
        """Determine GPU vendor from name."""
        gpu_name_lower = gpu_name.lower()
        if 'nvidia' in gpu_name_lower or 'geforce' in gpu_name_lower or 'quadro' in gpu_name_lower:
            return GPUVendor.NVIDIA
        elif 'amd' in gpu_name_lower or 'radeon' in gpu_name_lower:
            return GPUVendor.AMD
        elif 'intel' in gpu_name_lower:
            return GPUVendor.INTEL
        else:
            return GPUVendor.UNKNOWN

    async def start_monitoring(self, sampling_interval: float = 1.0) -> None:
        """Start GPU monitoring."""
        with self._lock:
            if self._monitoring_enabled:
                self._logger.warning("GPU monitoring already started")
                return

            self._sampling_interval = sampling_interval
            self._monitoring_enabled = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._logger.info("GPU monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop GPU monitoring."""
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

            self._logger.info("GPU monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main GPU monitoring loop."""
        try:
            while self._monitoring_enabled:
                start_time = time.time()

                # Collect metrics for all GPUs
                for gpu_info in self._gpu_infos:
                    metrics = self._collect_gpu_metrics(gpu_info.gpu_id)
                    if metrics:
                        with self._lock:
                            self._metrics_history[gpu_info.gpu_id].append(metrics)

                            # Cleanup old metrics
                            cutoff_time = datetime.now(timezone.utc) - timedelta(
                                minutes=self._history_retention_minutes
                            )
                            self._metrics_history[gpu_info.gpu_id] = [
                                m for m in self._metrics_history[gpu_info.gpu_id]
                                if m.timestamp >= cutoff_time
                            ]

                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self._sampling_interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            self._logger.info("GPU monitoring loop cancelled")
            raise
        except Exception as e:
            self._logger.error(f"Error in GPU monitoring loop: {str(e)}")
            raise

    def _collect_gpu_metrics(self, gpu_id: int) -> Optional[GPUMetrics]:
        """Collect current metrics for a specific GPU."""
        try:
            if not self._cuda_info or not self._cuda_info.available or not PYNVML_AVAILABLE:
                return None

            if gpu_id >= len(self._cuda_info.devices):
                return None

            handle = self._cuda_info.devices[gpu_id]["handle"]
            current_time = datetime.now(timezone.utc)

            # Get memory info
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

            # Get utilization
            try:
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = utilization.gpu
                memory_util = utilization.memory
            except:
                gpu_util = 0.0
                memory_util = 0.0

            # Get temperature
            try:
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except:
                temperature = None

            # Get power draw
            try:
                power_draw = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            except:
                power_draw = None

            # Get clock speeds
            try:
                graphics_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                memory_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
            except:
                graphics_clock = None
                memory_clock = None

            # Get fan speed
            try:
                fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
            except:
                fan_speed = None

            # Get throttle reasons
            throttle_reasons = []
            try:
                throttle_status = pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(handle)
                if throttle_status & pynvml.nvmlClocksThrottleReasonGpuIdle:
                    throttle_reasons.append("GPU Idle")
                if throttle_status & pynvml.nvmlClocksThrottleReasonApplicationsClocksSetting:
                    throttle_reasons.append("Applications Clocks Setting")
                if throttle_status & pynvml.nvmlClocksThrottleReasonSwPowerCap:
                    throttle_reasons.append("SW Power Cap")
                if throttle_status & pynvml.nvmlClocksThrottleReasonHwSlowdown:
                    throttle_reasons.append("HW Slowdown")
                if throttle_status & pynvml.nvmlClocksThrottleReasonSyncBoost:
                    throttle_reasons.append("Sync Boost")
                if throttle_status & pynvml.nvmlClocksThrottleReasonSwThermalSlowdown:
                    throttle_reasons.append("SW Thermal Slowdown")
                if throttle_status & pynvml.nvmlClocksThrottleReasonHwThermalSlowdown:
                    throttle_reasons.append("HW Thermal Slowdown")
                if throttle_status & pynvml.nvmlClocksThrottleReasonHwPowerBrakeSlowdown:
                    throttle_reasons.append("HW Power Brake Slowdown")
            except:
                pass

            return GPUMetrics(
                timestamp=current_time,
                gpu_id=gpu_id,
                utilization_percent=gpu_util,
                memory_utilization_percent=memory_util,
                memory_used_mb=memory_info.used // (1024 * 1024),
                memory_free_mb=memory_info.free // (1024 * 1024),
                temperature_celsius=temperature,
                power_draw_watts=power_draw,
                clock_speed_mhz=graphics_clock,
                memory_clock_mhz=memory_clock,
                fan_speed_percent=fan_speed,
                throttle_reasons=throttle_reasons
            )

        except Exception as e:
            self._logger.error(f"Error collecting GPU {gpu_id} metrics: {str(e)}")
            return None

    def get_gpu_info(self, gpu_id: Optional[int] = None) -> Union[List[GPUInfo], Optional[GPUInfo]]:
        """Get GPU information for specific GPU or all GPUs."""
        with self._lock:
            if gpu_id is None:
                return self._gpu_infos.copy()

            for gpu_info in self._gpu_infos:
                if gpu_info.gpu_id == gpu_id:
                    return gpu_info

            return None

    def get_gpu_metrics(self, gpu_id: int, minutes: int = 5) -> List[GPUMetrics]:
        """Get historical metrics for a specific GPU."""
        with self._lock:
            if gpu_id not in self._metrics_history:
                return []

            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            return [
                m for m in self._metrics_history[gpu_id]
                if m.timestamp >= cutoff_time
            ]

    def get_current_gpu_metrics(self, gpu_id: int) -> Optional[GPUMetrics]:
        """Get the most recent metrics for a specific GPU."""
        with self._lock:
            if gpu_id not in self._metrics_history or not self._metrics_history[gpu_id]:
                # Collect metrics synchronously if none available
                return self._collect_gpu_metrics(gpu_id)

            return self._metrics_history[gpu_id][-1]

    def get_cuda_info(self) -> Optional[CUDAInfo]:
        """Get CUDA runtime information."""
        return self._cuda_info

    def get_rocm_info(self) -> Optional[ROCmInfo]:
        """Get ROCm runtime information."""
        return self._rocm_info

    def get_compute_platforms(self) -> List[ComputePlatform]:
        """Get available compute platforms."""
        platforms = []

        if self._cuda_info and self._cuda_info.available:
            platforms.append(ComputePlatform.CUDA)

        if self._rocm_info and self._rocm_info.available:
            platforms.append(ComputePlatform.ROCM)

        # Check for OpenCL (basic detection)
        try:
            import pyopencl
            platforms.append(ComputePlatform.OPENCL)
        except ImportError:
            pass

        return platforms

    def is_gpu_available(self) -> bool:
        """Check if any GPU is available."""
        return len(self._gpu_infos) > 0

    def get_gpu_count(self) -> int:
        """Get the number of available GPUs."""
        return len(self._gpu_infos)

    def get_total_gpu_memory_mb(self) -> int:
        """Get total GPU memory across all GPUs."""
        return sum(gpu.memory_total_mb for gpu in self._gpu_infos)

    def get_available_gpu_memory_mb(self) -> int:
        """Get available GPU memory across all GPUs."""
        return sum(gpu.memory_free_mb for gpu in self._gpu_infos)

    def refresh_gpu_info(self) -> None:
        """Refresh GPU information and detection."""
        with self._lock:
            self._logger.info("Refreshing GPU information")
            self._initialize_gpu_detection()

    def get_gpu_utilization_summary(self) -> Dict[str, Any]:
        """Get a summary of GPU utilization across all GPUs."""
        with self._lock:
            if not self._gpu_infos:
                return {"error": "No GPUs available"}

            total_gpus = len(self._gpu_infos)
            total_memory_mb = sum(gpu.memory_total_mb for gpu in self._gpu_infos)
            used_memory_mb = sum(gpu.memory_used_mb for gpu in self._gpu_infos)
            avg_utilization = sum(gpu.utilization_percent for gpu in self._gpu_infos) / total_gpus
            avg_memory_util = sum(gpu.memory_utilization_percent for gpu in self._gpu_infos) / total_gpus

            temperatures = [gpu.temperature_celsius for gpu in self._gpu_infos if gpu.temperature_celsius is not None]
            avg_temperature = sum(temperatures) / len(temperatures) if temperatures else None
            max_temperature = max(temperatures) if temperatures else None

            power_draws = [gpu.power_draw_watts for gpu in self._gpu_infos if gpu.power_draw_watts is not None]
            total_power_draw = sum(power_draws) if power_draws else None

            return {
                "total_gpus": total_gpus,
                "total_memory_mb": total_memory_mb,
                "used_memory_mb": used_memory_mb,
                "memory_utilization_percent": (used_memory_mb / total_memory_mb) * 100 if total_memory_mb > 0 else 0,
                "average_gpu_utilization_percent": avg_utilization,
                "average_memory_utilization_percent": avg_memory_util,
                "average_temperature_celsius": avg_temperature,
                "max_temperature_celsius": max_temperature,
                "total_power_draw_watts": total_power_draw,
                "cuda_available": self._cuda_info.available if self._cuda_info else False,
                "rocm_available": self._rocm_info.available if self._rocm_info else False
            }

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
