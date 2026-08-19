"""
Module: hardware_validator_lg
Description: Validates system hardware meets minimum requirements, detects GPU capabilities and available resources
Phase: 1
Location: /src/modules/logic/system_requirements_lg/hardware_validator_lg/
"""

# Standard library imports
import os
import platform
import psutil
import subprocess
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

# Third-party imports
try:
    import GPUtil
    GPU_UTIL_AVAILABLE = True
except ImportError:
    GPU_UTIL_AVAILABLE = False

try:
    import cpuinfo
    CPU_INFO_AVAILABLE = True
except ImportError:
    CPU_INFO_AVAILABLE = False

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationResult, ValidationError, ValidationSeverity
)


class SystemArchitecture(Enum):
    """System architecture types."""
    X86_64 = "x86_64"
    ARM64 = "arm64"
    X86 = "x86"
    UNKNOWN = "unknown"


class HardwareCapability(Enum):
    """Hardware capability levels."""
    INSUFFICIENT = "INSUFFICIENT"
    MINIMUM = "MINIMUM"
    RECOMMENDED = "RECOMMENDED"
    OPTIMAL = "OPTIMAL"


@dataclass
class CPUInfo:
    """CPU information and capabilities."""
    name: str
    cores: int
    threads: int
    frequency: float  # GHz
    architecture: SystemArchitecture
    has_avx2: bool = False
    has_avx512: bool = False
    cache_l3_mb: Optional[int] = None
    vendor: Optional[str] = None


@dataclass
class GPUInfo:
    """GPU information and capabilities."""
    name: str
    memory_mb: int
    driver_version: Optional[str] = None
    cuda_version: Optional[str] = None
    compute_capability: Optional[str] = None
    is_nvidia: bool = False
    is_amd: bool = False
    is_intel: bool = False
    power_limit_w: Optional[int] = None


@dataclass
class MemoryInfo:
    """System memory information."""
    total_gb: float
    available_gb: float
    used_gb: float
    swap_total_gb: float
    swap_used_gb: float
    virtual_total_gb: float


@dataclass
class StorageInfo:
    """Storage device information."""
    total_gb: float
    free_gb: float
    used_gb: float
    device_type: str  # SSD, HDD, NVMe
    filesystem: str
    mount_point: str
    is_nvme: bool = False
    read_speed_mbps: Optional[float] = None
    write_speed_mbps: Optional[float] = None


@dataclass
class HardwareRequirement:
    """Hardware requirement specification."""
    component: str
    description: str
    minimum_value: Any
    recommended_value: Any
    current_value: Any = None
    capability_level: HardwareCapability = HardwareCapability.INSUFFICIENT
    meets_minimum: bool = False
    meets_recommended: bool = False
    error_message: Optional[str] = None


@dataclass
class HardwareValidationResult:
    """Hardware validation result."""
    overall_capability: HardwareCapability
    can_run_application: bool
    requirements: List[HardwareRequirement] = field(default_factory=list)
    cpu_info: Optional[CPUInfo] = None
    gpu_info: List[GPUInfo] = field(default_factory=list)
    memory_info: Optional[MemoryInfo] = None
    storage_info: List[StorageInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    validation_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_validation_time: float = 0.0


class IHardwareValidator(ABC):
    """Interface for hardware validators."""
    
    @abstractmethod
    def validate_hardware(self) -> HardwareValidationResult:
        """Validate all hardware requirements."""
        pass
    
    @abstractmethod
    def validate_cpu(self) -> HardwareRequirement:
        """Validate CPU requirements."""
        pass
    
    @abstractmethod
    def validate_memory(self) -> HardwareRequirement:
        """Validate memory requirements."""
        pass
    
    @abstractmethod
    def validate_storage(self) -> HardwareRequirement:
        """Validate storage requirements."""
        pass
    
    @abstractmethod
    def validate_gpu(self) -> HardwareRequirement:
        """Validate GPU requirements."""
        pass
    
    @abstractmethod
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        pass


class HardwareValidator(IHardwareValidator):
    """
    Validates system hardware meets minimum requirements.
    
    Performs comprehensive hardware validation including CPU capabilities,
    memory availability, storage requirements, and GPU detection.
    """
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the hardware validator."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("hardware_validator")
        self._validation_engine = ValidationEngine()
        
        # Hardware requirements
        self._lock = threading.RLock()
        
        # Minimum requirements
        self._min_ram_gb = 8
        self._recommended_ram_gb = 32
        self._min_storage_gb = 50
        self._recommended_storage_gb = 500
        self._min_cpu_cores = 4
        self._recommended_cpu_cores = 8
        self._min_cpu_frequency_ghz = 2.0
        self._recommended_cpu_frequency_ghz = 3.0
        
        # Cache for system information
        self._system_info_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes
        
        self._logger.info("HardwareValidator initialized successfully")
    
    def validate_hardware(self) -> HardwareValidationResult:
        """
        Validate all hardware requirements.
        
        Returns:
            HardwareValidationResult with comprehensive validation results
        """
        start_time = datetime.now(timezone.utc)
        self._logger.info("Starting hardware validation")
        
        try:
            result = HardwareValidationResult(
                overall_capability=HardwareCapability.INSUFFICIENT,
                can_run_application=False
            )
            
            # Validate individual components
            cpu_req = self.validate_cpu()
            memory_req = self.validate_memory()
            storage_req = self.validate_storage()
            gpu_req = self.validate_gpu()
            
            result.requirements = [cpu_req, memory_req, storage_req, gpu_req]
            
            # Collect detailed system information
            result.cpu_info = self._get_cpu_info()
            result.memory_info = self._get_memory_info()
            result.storage_info = self._get_storage_info()
            result.gpu_info = self._get_gpu_info()
            
            # Determine overall capability
            result.overall_capability = self._determine_overall_capability(result.requirements)
            result.can_run_application = result.overall_capability != HardwareCapability.INSUFFICIENT
            
            # Add warnings and recommendations
            self._add_recommendations(result)
            
            validation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            result.total_validation_time = validation_time
            
            self._logger.info(f"Hardware validation completed: {result.overall_capability.value} "
                            f"({validation_time:.3f}s)")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Hardware validation failed: {str(e)}")
            result = HardwareValidationResult(
                overall_capability=HardwareCapability.INSUFFICIENT,
                can_run_application=False
            )
            result.errors.append(f"Hardware validation error: {str(e)}")
            result.total_validation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            return result

    def validate_cpu(self) -> HardwareRequirement:
        """
        Validate CPU requirements.

        Returns:
            HardwareRequirement with CPU validation results
        """
        try:
            cpu_info = self._get_cpu_info()

            requirement = HardwareRequirement(
                component="CPU",
                description="Central Processing Unit capabilities",
                minimum_value=f"{self._min_cpu_cores} cores @ {self._min_cpu_frequency_ghz}GHz",
                recommended_value=f"{self._recommended_cpu_cores} cores @ {self._recommended_cpu_frequency_ghz}GHz",
                current_value=f"{cpu_info.cores} cores @ {cpu_info.frequency:.1f}GHz"
            )

            # Check core count
            cores_ok = cpu_info.cores >= self._min_cpu_cores
            cores_recommended = cpu_info.cores >= self._recommended_cpu_cores

            # Check frequency
            freq_ok = cpu_info.frequency >= self._min_cpu_frequency_ghz
            freq_recommended = cpu_info.frequency >= self._recommended_cpu_frequency_ghz

            # Check architecture support
            arch_supported = cpu_info.architecture in [SystemArchitecture.X86_64, SystemArchitecture.ARM64]

            # Check AVX2 support (recommended for ML workloads)
            avx2_supported = cpu_info.has_avx2

            requirement.meets_minimum = cores_ok and freq_ok and arch_supported
            requirement.meets_recommended = cores_recommended and freq_recommended and avx2_supported

            if requirement.meets_recommended:
                requirement.capability_level = HardwareCapability.RECOMMENDED
            elif requirement.meets_minimum:
                requirement.capability_level = HardwareCapability.MINIMUM
                if not avx2_supported:
                    requirement.error_message = "CPU lacks AVX2 support - performance may be reduced"
            else:
                requirement.capability_level = HardwareCapability.INSUFFICIENT
                issues = []
                if not cores_ok:
                    issues.append(f"insufficient cores ({cpu_info.cores} < {self._min_cpu_cores})")
                if not freq_ok:
                    issues.append(f"low frequency ({cpu_info.frequency:.1f} < {self._min_cpu_frequency_ghz}GHz)")
                if not arch_supported:
                    issues.append(f"unsupported architecture ({cpu_info.architecture.value})")
                requirement.error_message = "CPU requirements not met: " + ", ".join(issues)

            return requirement

        except Exception as e:
            self._logger.error(f"CPU validation failed: {str(e)}")
            return HardwareRequirement(
                component="CPU",
                description="Central Processing Unit capabilities",
                minimum_value="Unknown",
                recommended_value="Unknown",
                current_value="Error",
                capability_level=HardwareCapability.INSUFFICIENT,
                error_message=f"CPU validation error: {str(e)}"
            )

    def validate_memory(self) -> HardwareRequirement:
        """
        Validate memory requirements.

        Returns:
            HardwareRequirement with memory validation results
        """
        try:
            memory_info = self._get_memory_info()

            requirement = HardwareRequirement(
                component="Memory",
                description="System RAM availability",
                minimum_value=f"{self._min_ram_gb}GB",
                recommended_value=f"{self._recommended_ram_gb}GB",
                current_value=f"{memory_info.total_gb:.1f}GB"
            )

            requirement.meets_minimum = memory_info.total_gb >= self._min_ram_gb
            requirement.meets_recommended = memory_info.total_gb >= self._recommended_ram_gb

            if requirement.meets_recommended:
                requirement.capability_level = HardwareCapability.RECOMMENDED
            elif requirement.meets_minimum:
                requirement.capability_level = HardwareCapability.MINIMUM
                requirement.error_message = f"Memory below recommended: {memory_info.total_gb:.1f}GB < {self._recommended_ram_gb}GB"
            else:
                requirement.capability_level = HardwareCapability.INSUFFICIENT
                requirement.error_message = f"Insufficient memory: {memory_info.total_gb:.1f}GB < {self._min_ram_gb}GB"

            return requirement

        except Exception as e:
            self._logger.error(f"Memory validation failed: {str(e)}")
            return HardwareRequirement(
                component="Memory",
                description="System RAM availability",
                minimum_value="Unknown",
                recommended_value="Unknown",
                current_value="Error",
                capability_level=HardwareCapability.INSUFFICIENT,
                error_message=f"Memory validation error: {str(e)}"
            )

    def validate_storage(self) -> HardwareRequirement:
        """
        Validate storage requirements.

        Returns:
            HardwareRequirement with storage validation results
        """
        try:
            storage_info = self._get_storage_info()

            # Find the storage device with the most free space
            if not storage_info:
                raise ValueError("No storage devices found")

            primary_storage = max(storage_info, key=lambda s: s.free_gb)

            requirement = HardwareRequirement(
                component="Storage",
                description="Available disk space",
                minimum_value=f"{self._min_storage_gb}GB",
                recommended_value=f"{self._recommended_storage_gb}GB",
                current_value=f"{primary_storage.free_gb:.1f}GB ({primary_storage.device_type})"
            )

            requirement.meets_minimum = primary_storage.free_gb >= self._min_storage_gb
            requirement.meets_recommended = primary_storage.free_gb >= self._recommended_storage_gb

            # Bonus points for NVMe/SSD
            is_fast_storage = primary_storage.is_nvme or primary_storage.device_type == "SSD"

            if requirement.meets_recommended and is_fast_storage:
                requirement.capability_level = HardwareCapability.OPTIMAL
            elif requirement.meets_recommended:
                requirement.capability_level = HardwareCapability.RECOMMENDED
            elif requirement.meets_minimum:
                requirement.capability_level = HardwareCapability.MINIMUM
                if not is_fast_storage:
                    requirement.error_message = f"Storage below recommended: {primary_storage.free_gb:.1f}GB < {self._recommended_storage_gb}GB, using {primary_storage.device_type}"
                else:
                    requirement.error_message = f"Storage below recommended: {primary_storage.free_gb:.1f}GB < {self._recommended_storage_gb}GB"
            else:
                requirement.capability_level = HardwareCapability.INSUFFICIENT
                requirement.error_message = f"Insufficient storage: {primary_storage.free_gb:.1f}GB < {self._min_storage_gb}GB"

            return requirement

        except Exception as e:
            self._logger.error(f"Storage validation failed: {str(e)}")
            return HardwareRequirement(
                component="Storage",
                description="Available disk space",
                minimum_value="Unknown",
                recommended_value="Unknown",
                current_value="Error",
                capability_level=HardwareCapability.INSUFFICIENT,
                error_message=f"Storage validation error: {str(e)}"
            )

    def validate_gpu(self) -> HardwareRequirement:
        """
        Validate GPU requirements.

        Returns:
            HardwareRequirement with GPU validation results
        """
        try:
            gpu_info = self._get_gpu_info()

            requirement = HardwareRequirement(
                component="GPU",
                description="Graphics Processing Unit capabilities",
                minimum_value="Optional (CPU fallback available)",
                recommended_value="NVIDIA GPU with 8GB+ VRAM or AMD GPU with ROCm support",
                current_value=f"{len(gpu_info)} GPU(s) detected" if gpu_info else "No GPU detected"
            )

            if not gpu_info:
                # No GPU is acceptable - CPU fallback available
                requirement.capability_level = HardwareCapability.MINIMUM
                requirement.meets_minimum = True
                requirement.meets_recommended = False
                requirement.error_message = "No GPU detected - will use CPU-only mode (slower performance)"
            else:
                # Evaluate best GPU
                best_gpu = max(gpu_info, key=lambda g: g.memory_mb)
                requirement.current_value = f"{best_gpu.name} ({best_gpu.memory_mb}MB VRAM)"

                # Check for NVIDIA with CUDA or AMD with ROCm
                has_cuda = any(gpu.is_nvidia and gpu.cuda_version for gpu in gpu_info)
                has_rocm = any(gpu.is_amd for gpu in gpu_info)
                has_sufficient_vram = best_gpu.memory_mb >= 8192  # 8GB

                requirement.meets_minimum = True  # GPU is always a bonus
                requirement.meets_recommended = (has_cuda or has_rocm) and has_sufficient_vram

                if requirement.meets_recommended:
                    requirement.capability_level = HardwareCapability.OPTIMAL
                elif has_cuda or has_rocm:
                    requirement.capability_level = HardwareCapability.RECOMMENDED
                    if not has_sufficient_vram:
                        requirement.error_message = f"GPU VRAM below recommended: {best_gpu.memory_mb}MB < 8192MB"
                else:
                    requirement.capability_level = HardwareCapability.MINIMUM
                    requirement.error_message = "GPU detected but lacks CUDA/ROCm support"

            return requirement

        except Exception as e:
            self._logger.error(f"GPU validation failed: {str(e)}")
            return HardwareRequirement(
                component="GPU",
                description="Graphics Processing Unit capabilities",
                minimum_value="Unknown",
                recommended_value="Unknown",
                current_value="Error",
                capability_level=HardwareCapability.INSUFFICIENT,
                error_message=f"GPU validation error: {str(e)}"
            )

    def get_system_info(self) -> Dict[str, Any]:
        """
        Get comprehensive system information.

        Returns:
            Dictionary with detailed system information
        """
        try:
            # Check cache
            now = datetime.now(timezone.utc)
            if (self._system_info_cache and self._cache_timestamp and
                (now - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds):
                return self._system_info_cache

            # Collect system information
            system_info = {
                'platform': {
                    'system': platform.system(),
                    'release': platform.release(),
                    'version': platform.version(),
                    'machine': platform.machine(),
                    'processor': platform.processor(),
                    'architecture': platform.architecture(),
                    'python_version': platform.python_version()
                },
                'cpu': self._get_cpu_info().__dict__,
                'memory': self._get_memory_info().__dict__,
                'storage': [storage.__dict__ for storage in self._get_storage_info()],
                'gpu': [gpu.__dict__ for gpu in self._get_gpu_info()],
                'environment': {
                    'path': os.environ.get('PATH', ''),
                    'python_path': os.environ.get('PYTHONPATH', ''),
                    'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES', ''),
                    'home': os.environ.get('HOME', os.environ.get('USERPROFILE', ''))
                }
            }

            # Cache the result
            with self._lock:
                self._system_info_cache = system_info
                self._cache_timestamp = now

            return system_info

        except Exception as e:
            self._logger.error(f"Failed to collect system information: {str(e)}")
            return {'error': str(e)}

    def _get_cpu_info(self) -> CPUInfo:
        """Get detailed CPU information."""
        try:
            # Basic CPU info from psutil
            cpu_count = psutil.cpu_count(logical=False) or 1
            cpu_count_logical = psutil.cpu_count(logical=True) or 1
            cpu_freq = psutil.cpu_freq()
            frequency = cpu_freq.current / 1000.0 if cpu_freq else 2.0  # Convert MHz to GHz

            # Architecture detection
            machine = platform.machine().lower()
            if 'x86_64' in machine or 'amd64' in machine:
                arch = SystemArchitecture.X86_64
            elif 'arm64' in machine or 'aarch64' in machine:
                arch = SystemArchitecture.ARM64
            elif 'x86' in machine or 'i386' in machine or 'i686' in machine:
                arch = SystemArchitecture.X86
            else:
                arch = SystemArchitecture.UNKNOWN

            # Try to get detailed CPU info
            cpu_name = platform.processor() or "Unknown CPU"
            vendor = None
            has_avx2 = False
            has_avx512 = False
            cache_l3_mb = None

            if CPU_INFO_AVAILABLE:
                try:
                    cpu_info_dict = cpuinfo.get_cpu_info()
                    cpu_name = cpu_info_dict.get('brand_raw', cpu_name)
                    vendor = cpu_info_dict.get('vendor_id_raw', vendor)

                    # Check for instruction set support
                    flags = cpu_info_dict.get('flags', [])
                    has_avx2 = 'avx2' in flags
                    has_avx512 = any(flag.startswith('avx512') for flag in flags)

                    # Try to get cache info
                    cache_info = cpu_info_dict.get('cache', {})
                    if 'l3_cache_size' in cache_info:
                        cache_l3_mb = cache_info['l3_cache_size'] // (1024 * 1024)

                except Exception as e:
                    self._logger.warning(f"Failed to get detailed CPU info: {str(e)}")

            return CPUInfo(
                name=cpu_name,
                cores=cpu_count,
                threads=cpu_count_logical,
                frequency=frequency,
                architecture=arch,
                has_avx2=has_avx2,
                has_avx512=has_avx512,
                cache_l3_mb=cache_l3_mb,
                vendor=vendor
            )

        except Exception as e:
            self._logger.error(f"Failed to get CPU info: {str(e)}")
            return CPUInfo(
                name="Unknown CPU",
                cores=1,
                threads=1,
                frequency=2.0,
                architecture=SystemArchitecture.UNKNOWN
            )

    def _get_memory_info(self) -> MemoryInfo:
        """Get detailed memory information."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return MemoryInfo(
                total_gb=memory.total / (1024**3),
                available_gb=memory.available / (1024**3),
                used_gb=memory.used / (1024**3),
                swap_total_gb=swap.total / (1024**3),
                swap_used_gb=swap.used / (1024**3),
                virtual_total_gb=(memory.total + swap.total) / (1024**3)
            )

        except Exception as e:
            self._logger.error(f"Failed to get memory info: {str(e)}")
            return MemoryInfo(
                total_gb=8.0,  # Default assumption
                available_gb=4.0,
                used_gb=4.0,
                swap_total_gb=0.0,
                swap_used_gb=0.0,
                virtual_total_gb=8.0
            )

    def _get_storage_info(self) -> List[StorageInfo]:
        """Get detailed storage information."""
        try:
            storage_devices = []

            # Get disk usage for all mounted filesystems
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)

                    # Determine device type
                    device_type = "HDD"  # Default
                    is_nvme = False

                    # Try to determine if it's SSD/NVMe
                    device_name = partition.device.lower()
                    if 'nvme' in device_name:
                        device_type = "NVMe"
                        is_nvme = True
                    elif 'ssd' in device_name or self._is_ssd_device(partition.device):
                        device_type = "SSD"

                    storage_info = StorageInfo(
                        total_gb=usage.total / (1024**3),
                        free_gb=usage.free / (1024**3),
                        used_gb=usage.used / (1024**3),
                        device_type=device_type,
                        filesystem=partition.fstype,
                        mount_point=partition.mountpoint,
                        is_nvme=is_nvme
                    )

                    storage_devices.append(storage_info)

                except (PermissionError, OSError) as e:
                    self._logger.warning(f"Cannot access partition {partition.mountpoint}: {str(e)}")
                    continue

            return storage_devices

        except Exception as e:
            self._logger.error(f"Failed to get storage info: {str(e)}")
            return [StorageInfo(
                total_gb=100.0,
                free_gb=50.0,
                used_gb=50.0,
                device_type="Unknown",
                filesystem="Unknown",
                mount_point="/"
            )]

    def _get_gpu_info(self) -> List[GPUInfo]:
        """Get detailed GPU information."""
        try:
            gpu_devices = []

            if GPU_UTIL_AVAILABLE:
                try:
                    gpus = GPUtil.getGPUs()
                    for gpu in gpus:
                        gpu_info = GPUInfo(
                            name=gpu.name,
                            memory_mb=int(gpu.memoryTotal),
                            driver_version=gpu.driver,
                            is_nvidia=True,  # GPUtil primarily supports NVIDIA
                            power_limit_w=None
                        )

                        # Try to get CUDA version
                        try:
                            result = subprocess.run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader,nounits'],
                                                  capture_output=True, text=True, timeout=2)
                            if result.returncode == 0:
                                gpu_info.cuda_version = result.stdout.strip()
                        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                            pass

                        gpu_devices.append(gpu_info)

                except Exception as e:
                    self._logger.warning(f"Failed to get NVIDIA GPU info: {str(e)}")

            # Try to detect AMD GPUs
            try:
                result = subprocess.run(['rocm-smi', '--showproductname'],
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if 'GPU' in line and ':' in line:
                            gpu_name = line.split(':', 1)[1].strip()
                            gpu_info = GPUInfo(
                                name=gpu_name,
                                memory_mb=8192,  # Default assumption for AMD GPUs
                                is_amd=True
                            )
                            gpu_devices.append(gpu_info)
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

            # Try to detect Intel GPUs
            try:
                result = subprocess.run(['intel_gpu_top', '-l'],
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and 'Intel' in result.stdout:
                    gpu_info = GPUInfo(
                        name="Intel Integrated Graphics",
                        memory_mb=2048,  # Shared memory assumption
                        is_intel=True
                    )
                    gpu_devices.append(gpu_info)
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

            return gpu_devices

        except Exception as e:
            self._logger.error(f"Failed to get GPU info: {str(e)}")
            return []

    def _is_ssd_device(self, device_path: str) -> bool:
        """Check if a device is an SSD."""
        try:
            # On Linux, check /sys/block for rotational flag
            if platform.system() == "Linux":
                device_name = os.path.basename(device_path)
                # Remove partition numbers
                device_name = ''.join(c for c in device_name if not c.isdigit())
                rotational_path = f"/sys/block/{device_name}/queue/rotational"

                if os.path.exists(rotational_path):
                    with open(rotational_path, 'r') as f:
                        return f.read().strip() == '0'

            # On Windows, assume modern systems have SSDs
            elif platform.system() == "Windows":
                return True  # Conservative assumption

            return False

        except Exception:
            return False

    def _determine_overall_capability(self, requirements: List[HardwareRequirement]) -> HardwareCapability:
        """Determine overall system capability based on individual requirements."""
        if not requirements:
            return HardwareCapability.INSUFFICIENT

        # Count capability levels
        capability_counts = {
            HardwareCapability.INSUFFICIENT: 0,
            HardwareCapability.MINIMUM: 0,
            HardwareCapability.RECOMMENDED: 0,
            HardwareCapability.OPTIMAL: 0
        }

        for req in requirements:
            capability_counts[req.capability_level] += 1

        # If any component is insufficient, overall is insufficient
        if capability_counts[HardwareCapability.INSUFFICIENT] > 0:
            return HardwareCapability.INSUFFICIENT

        # If all components are optimal, overall is optimal
        if capability_counts[HardwareCapability.OPTIMAL] == len(requirements):
            return HardwareCapability.OPTIMAL

        # If most components are recommended or better, overall is recommended
        recommended_or_better = (capability_counts[HardwareCapability.RECOMMENDED] +
                               capability_counts[HardwareCapability.OPTIMAL])
        if recommended_or_better >= len(requirements) * 0.75:
            return HardwareCapability.RECOMMENDED

        # Otherwise, minimum capability
        return HardwareCapability.MINIMUM

    def _add_recommendations(self, result: HardwareValidationResult) -> None:
        """Add recommendations and warnings to the validation result."""
        try:
            # CPU recommendations
            if result.cpu_info:
                if not result.cpu_info.has_avx2:
                    result.warnings.append("CPU lacks AVX2 support - consider upgrading for better ML performance")

                if result.cpu_info.cores < self._recommended_cpu_cores:
                    result.warnings.append(f"Consider upgrading to {self._recommended_cpu_cores}+ CPU cores for optimal performance")

            # Memory recommendations
            if result.memory_info:
                if result.memory_info.total_gb < self._recommended_ram_gb:
                    result.warnings.append(f"Consider upgrading to {self._recommended_ram_gb}GB+ RAM for optimal performance")

                # Check available memory
                if result.memory_info.available_gb < result.memory_info.total_gb * 0.5:
                    result.warnings.append("High memory usage detected - close unnecessary applications")

            # Storage recommendations
            if result.storage_info:
                primary_storage = max(result.storage_info, key=lambda s: s.free_gb)

                if primary_storage.device_type == "HDD":
                    result.warnings.append("Consider upgrading to SSD/NVMe storage for better performance")

                if primary_storage.free_gb < self._recommended_storage_gb:
                    result.warnings.append(f"Consider freeing up disk space - recommended {self._recommended_storage_gb}GB+ available")

            # GPU recommendations
            if not result.gpu_info:
                result.warnings.append("No GPU detected - training will be slower using CPU-only mode")
            else:
                nvidia_gpus = [gpu for gpu in result.gpu_info if gpu.is_nvidia]
                if not nvidia_gpus:
                    result.warnings.append("No NVIDIA GPU with CUDA support detected - consider NVIDIA GPU for optimal ML performance")
                else:
                    best_gpu = max(nvidia_gpus, key=lambda g: g.memory_mb)
                    if best_gpu.memory_mb < 8192:
                        result.warnings.append("GPU VRAM below 8GB - may limit model size and batch size")

        except Exception as e:
            self._logger.error(f"Failed to add recommendations: {str(e)}")
            result.warnings.append("Unable to generate performance recommendations")
