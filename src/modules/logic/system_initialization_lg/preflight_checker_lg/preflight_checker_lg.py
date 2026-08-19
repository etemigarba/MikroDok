"""
Module: preflight_checker_lg
Description: Validates system requirements before initialization
Phase: 1
Location: /src/modules/logic/system_initialization_lg/preflight_checker_lg/
"""

# Standard library imports
import os
import sys
import platform
import shutil
import psutil
import subprocess
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationResult, ValidationError, ValidationSeverity
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager


class RequirementStatus(Enum):
    """System requirement validation status."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    NOT_CHECKED = "NOT_CHECKED"
    SKIPPED = "SKIPPED"


class HardwareCapability(Enum):
    """Hardware capability levels."""
    MINIMUM = "MINIMUM"
    RECOMMENDED = "RECOMMENDED"
    OPTIMAL = "OPTIMAL"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass
class SystemRequirement:
    """System requirement specification."""
    name: str
    description: str
    requirement_type: str
    minimum_value: Any
    recommended_value: Any
    current_value: Any = None
    status: RequirementStatus = RequirementStatus.NOT_CHECKED
    error_message: Optional[str] = None
    capability_level: HardwareCapability = HardwareCapability.INSUFFICIENT


@dataclass
class ValidationReport:
    """Comprehensive system validation report."""
    overall_status: RequirementStatus
    can_proceed: bool
    requirements: List[SystemRequirement] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    system_info: Dict[str, Any] = field(default_factory=dict)
    validation_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_validation_time: float = 0.0


class PreflightChecker:
    """
    Validates system requirements before application initialization.
    
    Performs comprehensive system checks including hardware specifications,
    OS compatibility, storage requirements, and dependency validation.
    """
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the preflight checker."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("preflight_checker")
        self._validation_engine = ValidationEngine()
        
        # System requirements
        self._requirements: List[SystemRequirement] = []
        self._lock = threading.RLock()
        
        # Configuration
        self._minimum_ram_gb = 8
        self._recommended_ram_gb = 32
        self._minimum_storage_gb = 50
        self._recommended_storage_gb = 500
        self._minimum_python_version = (3, 12, 0)
        
        # Initialize requirements
        self._initialize_requirements()
        
        self._logger.info("PreflightChecker initialized successfully")
    
    def validate_system_requirements(self) -> ValidationReport:
        """
        Validate all system requirements.
        
        Returns:
            ValidationReport with comprehensive validation results
        """
        start_time = datetime.now(timezone.utc)
        self._logger.info("Starting system requirements validation")
        
        try:
            # Initialize report
            report = ValidationReport(
                overall_status=RequirementStatus.PASSED,
                can_proceed=True
            )
            
            # Collect system information
            report.system_info = self._collect_system_info()
            
            # Validate each requirement
            with self._lock:
                requirements_copy = self._requirements.copy()
            
            for requirement in requirements_copy:
                self._validate_requirement(requirement)
                report.requirements.append(requirement)
                
                # Update overall status
                if requirement.status == RequirementStatus.FAILED:
                    report.overall_status = RequirementStatus.FAILED
                    report.can_proceed = False
                    report.errors.append(requirement.error_message or f"Requirement failed: {requirement.name}")
                elif requirement.status == RequirementStatus.WARNING:
                    if report.overall_status == RequirementStatus.PASSED:
                        report.overall_status = RequirementStatus.WARNING
                    report.warnings.append(requirement.error_message or f"Requirement warning: {requirement.name}")
            
            # Calculate validation time
            end_time = datetime.now(timezone.utc)
            report.total_validation_time = (end_time - start_time).total_seconds()
            
            self._logger.info(f"System validation completed: {report.overall_status.value} "
                            f"({report.total_validation_time:.2f}s)")
            
            return report
            
        except Exception as e:
            self._logger.error(f"System validation failed: {str(e)}")
            return ValidationReport(
                overall_status=RequirementStatus.FAILED,
                can_proceed=False,
                errors=[f"Validation error: {str(e)}"],
                total_validation_time=(datetime.now(timezone.utc) - start_time).total_seconds()
            )
    
    def check_gpu_capabilities(self) -> Dict[str, Any]:
        """
        Check GPU capabilities and CUDA/ROCm support.
        
        Returns:
            Dictionary with GPU information
        """
        gpu_info = {
            "gpus_available": False,
            "cuda_available": False,
            "rocm_available": False,
            "gpu_count": 0,
            "gpu_details": [],
            "total_vram_gb": 0,
            "driver_version": None
        }
        
        try:
            # Check NVIDIA GPUs
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    gpu_info["cuda_available"] = True
                    gpu_info["gpus_available"] = True
                    
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split(', ')
                            if len(parts) >= 3:
                                gpu_info["gpu_details"].append({
                                    "name": parts[0],
                                    "vram_mb": int(parts[1]),
                                    "type": "NVIDIA"
                                })
                                gpu_info["total_vram_gb"] += int(parts[1]) / 1024
                                gpu_info["driver_version"] = parts[2]
                    
                    gpu_info["gpu_count"] = len(gpu_info["gpu_details"])
                    
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                pass
            
            # Check AMD GPUs (ROCm)
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showproductname", "--showmeminfo", "vram"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and not gpu_info["cuda_available"]:
                    gpu_info["rocm_available"] = True
                    gpu_info["gpus_available"] = True
                    # Parse ROCm output (simplified)
                    gpu_info["gpu_count"] = 1  # Simplified detection
                    
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                pass
            
            self._logger.info(f"GPU detection completed: {gpu_info['gpu_count']} GPUs found")
            
        except Exception as e:
            self._logger.error(f"GPU capability check failed: {str(e)}")
        
        return gpu_info

    def check_memory_requirements(self) -> Dict[str, Any]:
        """
        Check system memory and swap configuration.

        Returns:
            Dictionary with memory information
        """
        memory_info = {
            "total_ram_gb": 0,
            "available_ram_gb": 0,
            "used_ram_gb": 0,
            "swap_total_gb": 0,
            "swap_available_gb": 0,
            "meets_minimum": False,
            "meets_recommended": False
        }

        try:
            # Get memory information
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            memory_info["total_ram_gb"] = memory.total / (1024**3)
            memory_info["available_ram_gb"] = memory.available / (1024**3)
            memory_info["used_ram_gb"] = memory.used / (1024**3)
            memory_info["swap_total_gb"] = swap.total / (1024**3)
            memory_info["swap_available_gb"] = (swap.total - swap.used) / (1024**3)

            memory_info["meets_minimum"] = memory_info["total_ram_gb"] >= self._minimum_ram_gb
            memory_info["meets_recommended"] = memory_info["total_ram_gb"] >= self._recommended_ram_gb

            self._logger.info(f"Memory check: {memory_info['total_ram_gb']:.1f}GB total, "
                            f"{memory_info['available_ram_gb']:.1f}GB available")

        except Exception as e:
            self._logger.error(f"Memory check failed: {str(e)}")

        return memory_info

    def check_storage_requirements(self) -> Dict[str, Any]:
        """
        Check storage space and NVMe paths.

        Returns:
            Dictionary with storage information
        """
        storage_info = {
            "total_space_gb": 0,
            "free_space_gb": 0,
            "used_space_gb": 0,
            "meets_minimum": False,
            "meets_recommended": False,
            "nvme_paths": [],
            "database_path_writable": False,
            "model_path_writable": False
        }

        try:
            # Check main storage
            current_path = Path.cwd()
            disk_usage = shutil.disk_usage(current_path)

            storage_info["total_space_gb"] = disk_usage.total / (1024**3)
            storage_info["free_space_gb"] = disk_usage.free / (1024**3)
            storage_info["used_space_gb"] = (disk_usage.total - disk_usage.free) / (1024**3)

            storage_info["meets_minimum"] = storage_info["free_space_gb"] >= self._minimum_storage_gb
            storage_info["meets_recommended"] = storage_info["free_space_gb"] >= self._recommended_storage_gb

            # Check NVMe paths
            storage_info["nvme_paths"] = self._detect_nvme_drives()

            # Check write permissions
            storage_info["database_path_writable"] = self._check_path_writable("data")
            storage_info["model_path_writable"] = self._check_path_writable("models")

            self._logger.info(f"Storage check: {storage_info['free_space_gb']:.1f}GB free of "
                            f"{storage_info['total_space_gb']:.1f}GB total")

        except Exception as e:
            self._logger.error(f"Storage check failed: {str(e)}")

        return storage_info

    def check_python_version(self) -> Dict[str, Any]:
        """
        Check Python version compatibility.

        Returns:
            Dictionary with Python version information
        """
        python_info = {
            "version": sys.version,
            "version_tuple": sys.version_info[:3],
            "meets_minimum": False,
            "is_compatible": False
        }

        try:
            python_info["meets_minimum"] = python_info["version_tuple"] >= self._minimum_python_version
            python_info["is_compatible"] = python_info["meets_minimum"]

            self._logger.info(f"Python version: {python_info['version']}")

        except Exception as e:
            self._logger.error(f"Python version check failed: {str(e)}")

        return python_info

    def _validate_requirement(self, requirement: SystemRequirement) -> None:
        """
        Validate a single system requirement.

        Args:
            requirement: System requirement to validate
        """
        try:
            if requirement.requirement_type == "memory":
                memory_info = self.check_memory_requirements()
                requirement.current_value = memory_info["total_ram_gb"]

                if memory_info["meets_minimum"]:
                    if memory_info["meets_recommended"]:
                        requirement.status = RequirementStatus.PASSED
                        requirement.capability_level = HardwareCapability.RECOMMENDED
                    else:
                        requirement.status = RequirementStatus.WARNING
                        requirement.capability_level = HardwareCapability.MINIMUM
                        requirement.error_message = f"RAM below recommended: {requirement.current_value:.1f}GB < {self._recommended_ram_gb}GB"
                else:
                    requirement.status = RequirementStatus.FAILED
                    requirement.capability_level = HardwareCapability.INSUFFICIENT
                    requirement.error_message = f"Insufficient RAM: {requirement.current_value:.1f}GB < {self._minimum_ram_gb}GB"

            elif requirement.requirement_type == "storage":
                storage_info = self.check_storage_requirements()
                requirement.current_value = storage_info["free_space_gb"]

                if storage_info["meets_minimum"]:
                    if storage_info["meets_recommended"]:
                        requirement.status = RequirementStatus.PASSED
                        requirement.capability_level = HardwareCapability.RECOMMENDED
                    else:
                        requirement.status = RequirementStatus.WARNING
                        requirement.capability_level = HardwareCapability.MINIMUM
                        requirement.error_message = f"Storage below recommended: {requirement.current_value:.1f}GB < {self._recommended_storage_gb}GB"
                else:
                    requirement.status = RequirementStatus.FAILED
                    requirement.capability_level = HardwareCapability.INSUFFICIENT
                    requirement.error_message = f"Insufficient storage: {requirement.current_value:.1f}GB < {self._minimum_storage_gb}GB"

            elif requirement.requirement_type == "python":
                python_info = self.check_python_version()
                requirement.current_value = python_info["version_tuple"]

                if python_info["is_compatible"]:
                    requirement.status = RequirementStatus.PASSED
                    requirement.capability_level = HardwareCapability.RECOMMENDED
                else:
                    requirement.status = RequirementStatus.FAILED
                    requirement.capability_level = HardwareCapability.INSUFFICIENT
                    requirement.error_message = f"Python version incompatible: {requirement.current_value} < {self._minimum_python_version}"

            elif requirement.requirement_type == "gpu":
                gpu_info = self.check_gpu_capabilities()
                requirement.current_value = gpu_info["gpu_count"]

                if gpu_info["gpus_available"]:
                    requirement.status = RequirementStatus.PASSED
                    requirement.capability_level = HardwareCapability.OPTIMAL
                else:
                    requirement.status = RequirementStatus.WARNING
                    requirement.capability_level = HardwareCapability.MINIMUM
                    requirement.error_message = "No GPU detected - will use CPU only"

            else:
                requirement.status = RequirementStatus.SKIPPED
                requirement.error_message = f"Unknown requirement type: {requirement.requirement_type}"

        except Exception as e:
            requirement.status = RequirementStatus.FAILED
            requirement.error_message = f"Validation error: {str(e)}"
            self._logger.error(f"Requirement validation failed for {requirement.name}: {str(e)}")

    def _collect_system_info(self) -> Dict[str, Any]:
        """
        Collect comprehensive system information.

        Returns:
            Dictionary with system information
        """
        system_info = {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "cpu_count": psutil.cpu_count(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "boot_time": psutil.boot_time(),
            "current_time": datetime.now(timezone.utc).isoformat()
        }

        try:
            # Add memory info
            memory = psutil.virtual_memory()
            system_info["memory_total_gb"] = memory.total / (1024**3)
            system_info["memory_available_gb"] = memory.available / (1024**3)

            # Add disk info
            disk_usage = shutil.disk_usage(Path.cwd())
            system_info["disk_total_gb"] = disk_usage.total / (1024**3)
            system_info["disk_free_gb"] = disk_usage.free / (1024**3)

        except Exception as e:
            self._logger.error(f"Error collecting system info: {str(e)}")

        return system_info

    def _initialize_requirements(self) -> None:
        """Initialize system requirements."""
        with self._lock:
            self._requirements = [
                SystemRequirement(
                    name="Python Version",
                    description="Python interpreter version compatibility",
                    requirement_type="python",
                    minimum_value=self._minimum_python_version,
                    recommended_value=self._minimum_python_version
                ),
                SystemRequirement(
                    name="System Memory",
                    description="Available system RAM",
                    requirement_type="memory",
                    minimum_value=self._minimum_ram_gb,
                    recommended_value=self._recommended_ram_gb
                ),
                SystemRequirement(
                    name="Storage Space",
                    description="Available disk space",
                    requirement_type="storage",
                    minimum_value=self._minimum_storage_gb,
                    recommended_value=self._recommended_storage_gb
                ),
                SystemRequirement(
                    name="GPU Support",
                    description="GPU acceleration capability",
                    requirement_type="gpu",
                    minimum_value=0,
                    recommended_value=1
                )
            ]

        self._logger.debug(f"Initialized {len(self._requirements)} system requirements")

    def _detect_nvme_drives(self) -> List[str]:
        """
        Detect NVMe drives for IDRAlloc.

        Returns:
            List of NVMe drive paths
        """
        nvme_paths = []

        try:
            # Check for NVMe devices on Linux
            if platform.system() == "Linux":
                nvme_dir = Path("/dev")
                for device in nvme_dir.glob("nvme*n*"):
                    if device.is_block_device():
                        nvme_paths.append(str(device))

            # Check for NVMe devices on Windows
            elif platform.system() == "Windows":
                try:
                    result = subprocess.run(
                        ["wmic", "diskdrive", "where", "InterfaceType='NVMe'", "get", "DeviceID"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            line = line.strip()
                            if line and line != "DeviceID":
                                nvme_paths.append(line)

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

        except Exception as e:
            self._logger.error(f"NVMe detection failed: {str(e)}")

        return nvme_paths

    def _check_path_writable(self, path_name: str) -> bool:
        """
        Check if a path is writable.

        Args:
            path_name: Name of the path to check

        Returns:
            True if path is writable
        """
        try:
            path = Path(path_name)
            path.mkdir(parents=True, exist_ok=True)

            # Try to create a test file
            test_file = path / ".write_test"
            test_file.write_text("test")
            test_file.unlink()

            return True

        except Exception as e:
            self._logger.error(f"Path write check failed for {path_name}: {str(e)}")
            return False
