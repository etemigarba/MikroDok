"""
Module: dependency_checker_lg
Description: Verifies required software dependencies, CUDA drivers, and system libraries are properly installed
Phase: 1
Location: /src/modules/logic/system_requirements_lg/dependency_checker_lg/
"""

# Standard library imports
import importlib
import os
import platform
import shutil
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
try:
    from importlib.metadata import version, distributions
except ImportError:
    # Fallback for Python < 3.8
    import pkg_resources

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationResult, ValidationError, ValidationSeverity
)


class DependencyType(Enum):
    """Types of dependencies."""
    PYTHON_PACKAGE = "python_package"
    SYSTEM_LIBRARY = "system_library"
    EXECUTABLE = "executable"
    DRIVER = "driver"
    ENVIRONMENT_VARIABLE = "environment_variable"
    OPTIONAL = "optional"


class DependencyStatus(Enum):
    """Dependency validation status."""
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    ERROR = "ERROR"
    NOT_CHECKED = "NOT_CHECKED"


@dataclass
class PackageInfo:
    """Python package information."""
    name: str
    version: Optional[str] = None
    location: Optional[str] = None
    required_version: Optional[str] = None
    is_installed: bool = False
    is_version_compatible: bool = False


@dataclass
class LibraryInfo:
    """System library information."""
    name: str
    path: Optional[str] = None
    version: Optional[str] = None
    is_available: bool = False


@dataclass
class DriverInfo:
    """Driver information."""
    name: str
    version: Optional[str] = None
    is_installed: bool = False
    required_version: Optional[str] = None
    is_version_compatible: bool = False


@dataclass
class DependencyRequirement:
    """Dependency requirement specification."""
    name: str
    dependency_type: DependencyType
    description: str
    required_version: Optional[str] = None
    minimum_version: Optional[str] = None
    is_required: bool = True
    current_version: Optional[str] = None
    status: DependencyStatus = DependencyStatus.NOT_CHECKED
    error_message: Optional[str] = None
    installation_command: Optional[str] = None


@dataclass
class DependencyValidationResult:
    """Dependency validation result."""
    overall_status: DependencyStatus
    can_proceed: bool
    requirements: List[DependencyRequirement] = field(default_factory=list)
    python_packages: List[PackageInfo] = field(default_factory=list)
    system_libraries: List[LibraryInfo] = field(default_factory=list)
    drivers: List[DriverInfo] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    missing_optional: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    validation_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_validation_time: float = 0.0


class IDependencyChecker(ABC):
    """Interface for dependency checkers."""
    
    @abstractmethod
    def validate_dependencies(self) -> DependencyValidationResult:
        """Validate all dependencies."""
        pass
    
    @abstractmethod
    def check_python_packages(self) -> List[PackageInfo]:
        """Check Python package dependencies."""
        pass
    
    @abstractmethod
    def check_system_libraries(self) -> List[LibraryInfo]:
        """Check system library dependencies."""
        pass
    
    @abstractmethod
    def check_drivers(self) -> List[DriverInfo]:
        """Check driver dependencies."""
        pass
    
    @abstractmethod
    def check_executables(self) -> Dict[str, bool]:
        """Check executable dependencies."""
        pass
    
    @abstractmethod
    def get_dependency_info(self) -> Dict[str, Any]:
        """Get comprehensive dependency information."""
        pass


class DependencyChecker(IDependencyChecker):
    """
    Verifies required software dependencies are properly installed.
    
    Performs comprehensive dependency validation including Python packages,
    system libraries, CUDA drivers, and external tools.
    """
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the dependency checker."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("dependency_checker")
        self._validation_engine = ValidationEngine()
        
        # Dependency requirements
        self._lock = threading.RLock()
        
        # Initialize dependency requirements
        self._requirements: List[DependencyRequirement] = []
        self._initialize_requirements()
        
        # Cache for dependency information
        self._dependency_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes
        
        self._logger.info("DependencyChecker initialized successfully")
    
    def validate_dependencies(self) -> DependencyValidationResult:
        """
        Validate all dependencies.
        
        Returns:
            DependencyValidationResult with comprehensive validation results
        """
        start_time = datetime.now(timezone.utc)
        self._logger.info("Starting dependency validation")
        
        try:
            result = DependencyValidationResult(
                overall_status=DependencyStatus.SATISFIED,
                can_proceed=True
            )
            
            # Validate each requirement
            with self._lock:
                requirements_copy = self._requirements.copy()
            
            for requirement in requirements_copy:
                self._validate_requirement(requirement)
                result.requirements.append(requirement)
                
                # Track missing dependencies
                if requirement.status == DependencyStatus.MISSING:
                    if requirement.is_required:
                        result.missing_required.append(requirement.name)
                    else:
                        result.missing_optional.append(requirement.name)
            
            # Collect detailed information
            result.python_packages = self.check_python_packages()
            result.system_libraries = self.check_system_libraries()
            result.drivers = self.check_drivers()
            
            # Determine overall status
            result.overall_status = self._determine_overall_status(result.requirements)
            result.can_proceed = (result.overall_status != DependencyStatus.ERROR and 
                                len(result.missing_required) == 0)
            
            # Add recommendations
            self._add_recommendations(result)
            
            validation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            result.total_validation_time = validation_time
            
            self._logger.info(f"Dependency validation completed: {result.overall_status.value} "
                            f"({validation_time:.3f}s)")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Dependency validation failed: {str(e)}")
            result = DependencyValidationResult(
                overall_status=DependencyStatus.ERROR,
                can_proceed=False
            )
            result.errors.append(f"Dependency validation error: {str(e)}")
            result.total_validation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            return result

    def check_python_packages(self) -> List[PackageInfo]:
        """
        Check Python package dependencies.

        Returns:
            List of PackageInfo with package status
        """
        try:
            packages = []

            # Required packages for MikroDok
            required_packages = {
                'flet': '>=0.21.0',
                'psutil': '>=5.9.0',
                'numpy': '>=1.24.0',
                'torch': '>=2.0.0',
                'transformers': '>=4.30.0',
                'datasets': '>=2.12.0',
                'tokenizers': '>=0.13.0',
                'accelerate': '>=0.20.0',
                'safetensors': '>=0.3.0',
                'huggingface-hub': '>=0.15.0',
                'tqdm': '>=4.65.0',
                'requests': '>=2.31.0',
                'packaging': '>=23.0',
                'pyyaml': '>=6.0',
                'pillow': '>=10.0.0',
                'matplotlib': '>=3.7.0',
                'scikit-learn': '>=1.3.0'
            }

            # Optional packages
            optional_packages = {
                'GPUtil': '>=1.4.0',
                'py-cpuinfo': '>=9.0.0',
                'nvidia-ml-py': '>=12.0.0',
                'tensorboard': '>=2.13.0',
                'wandb': '>=0.15.0',
                'jupyter': '>=1.0.0',
                'ipython': '>=8.0.0'
            }

            all_packages = {**required_packages, **optional_packages}

            for package_name, version_spec in all_packages.items():
                package_info = self._check_package(package_name, version_spec)
                packages.append(package_info)

            return packages

        except Exception as e:
            self._logger.error(f"Failed to check Python packages: {str(e)}")
            return []

    def check_system_libraries(self) -> List[LibraryInfo]:
        """
        Check system library dependencies.

        Returns:
            List of LibraryInfo with library status
        """
        try:
            libraries = []

            # System libraries based on platform
            if platform.system() == "Linux":
                required_libs = [
                    'libc.so.6',
                    'libstdc++.so.6',
                    'libgcc_s.so.1',
                    'libm.so.6',
                    'libpthread.so.0',
                    'libdl.so.2'
                ]

                optional_libs = [
                    'libcuda.so.1',
                    'libcudart.so.12',
                    'libcublas.so.12',
                    'libcurand.so.10',
                    'libcusparse.so.12'
                ]

            elif platform.system() == "Windows":
                required_libs = [
                    'msvcrt.dll',
                    'kernel32.dll',
                    'user32.dll'
                ]

                optional_libs = [
                    'nvcuda.dll',
                    'cudart64_12.dll',
                    'cublas64_12.dll'
                ]

            elif platform.system() == "Darwin":  # macOS
                required_libs = [
                    'libc++.1.dylib',
                    'libSystem.B.dylib'
                ]

                optional_libs = [
                    'libcuda.dylib',
                    'Metal.framework'
                ]
            else:
                required_libs = []
                optional_libs = []

            all_libs = required_libs + optional_libs

            for lib_name in all_libs:
                lib_info = self._check_library(lib_name)
                libraries.append(lib_info)

            return libraries

        except Exception as e:
            self._logger.error(f"Failed to check system libraries: {str(e)}")
            return []

    def check_drivers(self) -> List[DriverInfo]:
        """
        Check driver dependencies.

        Returns:
            List of DriverInfo with driver status
        """
        try:
            drivers = []

            # NVIDIA CUDA driver
            cuda_driver = self._check_cuda_driver()
            if cuda_driver:
                drivers.append(cuda_driver)

            # AMD ROCm driver (Linux only)
            if platform.system() == "Linux":
                rocm_driver = self._check_rocm_driver()
                if rocm_driver:
                    drivers.append(rocm_driver)

            # Intel GPU driver
            intel_driver = self._check_intel_driver()
            if intel_driver:
                drivers.append(intel_driver)

            return drivers

        except Exception as e:
            self._logger.error(f"Failed to check drivers: {str(e)}")
            return []

    def check_executables(self) -> Dict[str, bool]:
        """
        Check executable dependencies.

        Returns:
            Dictionary mapping executable names to availability status
        """
        try:
            executables = {}

            # Required executables
            required_exes = ['python', 'pip']

            # Optional executables
            optional_exes = [
                'nvidia-smi',
                'nvcc',
                'rocm-smi',
                'git',
                'curl',
                'wget'
            ]

            all_exes = required_exes + optional_exes

            for exe_name in all_exes:
                executables[exe_name] = shutil.which(exe_name) is not None

            return executables

        except Exception as e:
            self._logger.error(f"Failed to check executables: {str(e)}")
            return {}

    def get_dependency_info(self) -> Dict[str, Any]:
        """
        Get comprehensive dependency information.

        Returns:
            Dictionary with detailed dependency information
        """
        try:
            # Check cache
            now = datetime.now(timezone.utc)
            if (self._dependency_cache and self._cache_timestamp and
                (now - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds):
                return self._dependency_cache

            # Collect dependency information
            dependency_info = {
                'python': {
                    'version': sys.version,
                    'executable': sys.executable,
                    'path': sys.path,
                    'platform': platform.platform(),
                    'packages': [pkg.__dict__ for pkg in self.check_python_packages()]
                },
                'system': {
                    'libraries': [lib.__dict__ for lib in self.check_system_libraries()],
                    'executables': self.check_executables()
                },
                'drivers': [driver.__dict__ for driver in self.check_drivers()],
                'environment': {
                    'PATH': os.environ.get('PATH', ''),
                    'PYTHONPATH': os.environ.get('PYTHONPATH', ''),
                    'CUDA_VISIBLE_DEVICES': os.environ.get('CUDA_VISIBLE_DEVICES', ''),
                    'CUDA_HOME': os.environ.get('CUDA_HOME', ''),
                    'ROCM_PATH': os.environ.get('ROCM_PATH', ''),
                    'LD_LIBRARY_PATH': os.environ.get('LD_LIBRARY_PATH', ''),
                    'DYLD_LIBRARY_PATH': os.environ.get('DYLD_LIBRARY_PATH', '')
                }
            }

            # Cache the result
            with self._lock:
                self._dependency_cache = dependency_info
                self._cache_timestamp = now

            return dependency_info

        except Exception as e:
            self._logger.error(f"Failed to collect dependency information: {str(e)}")
            return {'error': str(e)}

    def _initialize_requirements(self) -> None:
        """Initialize dependency requirements."""
        with self._lock:
            self._requirements = [
                # Python version requirement
                DependencyRequirement(
                    name="Python",
                    dependency_type=DependencyType.PYTHON_PACKAGE,
                    description="Python interpreter version",
                    minimum_version="3.12.0",
                    is_required=True,
                    installation_command="Download from python.org"
                ),

                # Core Python packages
                DependencyRequirement(
                    name="flet",
                    dependency_type=DependencyType.PYTHON_PACKAGE,
                    description="Flet UI framework",
                    minimum_version="0.21.0",
                    is_required=True,
                    installation_command="pip install flet>=0.21.0"
                ),

                DependencyRequirement(
                    name="torch",
                    dependency_type=DependencyType.PYTHON_PACKAGE,
                    description="PyTorch machine learning framework",
                    minimum_version="2.0.0",
                    is_required=True,
                    installation_command="pip install torch>=2.0.0"
                ),

                DependencyRequirement(
                    name="transformers",
                    dependency_type=DependencyType.PYTHON_PACKAGE,
                    description="Hugging Face Transformers library",
                    minimum_version="4.30.0",
                    is_required=True,
                    installation_command="pip install transformers>=4.30.0"
                ),

                # Optional GPU support
                DependencyRequirement(
                    name="CUDA Driver",
                    dependency_type=DependencyType.DRIVER,
                    description="NVIDIA CUDA driver for GPU acceleration",
                    minimum_version="11.7",
                    is_required=False,
                    installation_command="Download from nvidia.com/drivers"
                ),

                DependencyRequirement(
                    name="ROCm",
                    dependency_type=DependencyType.DRIVER,
                    description="AMD ROCm driver for GPU acceleration",
                    minimum_version="5.0",
                    is_required=False,
                    installation_command="Install ROCm from AMD documentation"
                ),

                # System executables
                DependencyRequirement(
                    name="git",
                    dependency_type=DependencyType.EXECUTABLE,
                    description="Git version control system",
                    is_required=False,
                    installation_command="Install Git from git-scm.com"
                )
            ]

    def _validate_requirement(self, requirement: DependencyRequirement) -> None:
        """Validate a single dependency requirement."""
        try:
            if requirement.dependency_type == DependencyType.PYTHON_PACKAGE:
                self._validate_python_package(requirement)
            elif requirement.dependency_type == DependencyType.EXECUTABLE:
                self._validate_executable(requirement)
            elif requirement.dependency_type == DependencyType.DRIVER:
                self._validate_driver(requirement)
            elif requirement.dependency_type == DependencyType.SYSTEM_LIBRARY:
                self._validate_system_library(requirement)
            else:
                requirement.status = DependencyStatus.NOT_CHECKED
                requirement.error_message = f"Unknown dependency type: {requirement.dependency_type}"

        except Exception as e:
            requirement.status = DependencyStatus.ERROR
            requirement.error_message = f"Validation error: {str(e)}"

    def _validate_python_package(self, requirement: DependencyRequirement) -> None:
        """Validate a Python package requirement."""
        try:
            if requirement.name == "Python":
                # Special case for Python version
                current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
                requirement.current_version = current_version

                if requirement.minimum_version:
                    min_version = tuple(map(int, requirement.minimum_version.split('.')))
                    current_tuple = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)

                    if current_tuple >= min_version:
                        requirement.status = DependencyStatus.SATISFIED
                    else:
                        requirement.status = DependencyStatus.VERSION_MISMATCH
                        requirement.error_message = f"Python version {current_version} < {requirement.minimum_version}"
                else:
                    requirement.status = DependencyStatus.SATISFIED
            else:
                # Regular package check
                package_info = self._check_package(requirement.name, requirement.minimum_version)
                requirement.current_version = package_info.version

                if package_info.is_installed:
                    if package_info.is_version_compatible:
                        requirement.status = DependencyStatus.SATISFIED
                    else:
                        requirement.status = DependencyStatus.VERSION_MISMATCH
                        requirement.error_message = f"Version {package_info.version} does not meet requirement {requirement.minimum_version}"
                else:
                    requirement.status = DependencyStatus.MISSING
                    requirement.error_message = f"Package {requirement.name} is not installed"

        except Exception as e:
            requirement.status = DependencyStatus.ERROR
            requirement.error_message = f"Package validation error: {str(e)}"

    def _validate_executable(self, requirement: DependencyRequirement) -> None:
        """Validate an executable requirement."""
        try:
            executable_path = shutil.which(requirement.name)
            if executable_path:
                requirement.status = DependencyStatus.SATISFIED
                requirement.current_version = executable_path
            else:
                requirement.status = DependencyStatus.MISSING
                requirement.error_message = f"Executable {requirement.name} not found in PATH"

        except Exception as e:
            requirement.status = DependencyStatus.ERROR
            requirement.error_message = f"Executable validation error: {str(e)}"

    def _validate_driver(self, requirement: DependencyRequirement) -> None:
        """Validate a driver requirement."""
        try:
            if "CUDA" in requirement.name:
                driver_info = self._check_cuda_driver()
                if driver_info and driver_info.is_installed:
                    requirement.status = DependencyStatus.SATISFIED
                    requirement.current_version = driver_info.version
                else:
                    requirement.status = DependencyStatus.MISSING
                    requirement.error_message = "CUDA driver not found"

            elif "ROCm" in requirement.name:
                driver_info = self._check_rocm_driver()
                if driver_info and driver_info.is_installed:
                    requirement.status = DependencyStatus.SATISFIED
                    requirement.current_version = driver_info.version
                else:
                    requirement.status = DependencyStatus.MISSING
                    requirement.error_message = "ROCm driver not found"
            else:
                requirement.status = DependencyStatus.NOT_CHECKED
                requirement.error_message = f"Unknown driver: {requirement.name}"

        except Exception as e:
            requirement.status = DependencyStatus.ERROR
            requirement.error_message = f"Driver validation error: {str(e)}"

    def _validate_system_library(self, requirement: DependencyRequirement) -> None:
        """Validate a system library requirement."""
        try:
            lib_info = self._check_library(requirement.name)
            if lib_info.is_available:
                requirement.status = DependencyStatus.SATISFIED
                requirement.current_version = lib_info.path
            else:
                requirement.status = DependencyStatus.MISSING
                requirement.error_message = f"System library {requirement.name} not found"

        except Exception as e:
            requirement.status = DependencyStatus.ERROR
            requirement.error_message = f"Library validation error: {str(e)}"

    def _check_package(self, package_name: str, version_spec: Optional[str] = None) -> PackageInfo:
        """Check if a Python package is installed and meets version requirements."""
        try:
            # Try to import the package
            try:
                module = importlib.import_module(package_name.replace('-', '_'))
                is_installed = True

                # Try to get version
                version = None
                if hasattr(module, '__version__'):
                    version = module.__version__
                else:
                    # Try pkg_resources
                    try:
                        dist = pkg_resources.get_distribution(package_name)
                        version = dist.version
                    except:
                        pass

                # Check version compatibility
                is_version_compatible = True
                if version_spec and version:
                    try:
                        # Simple version comparison (supports >=, >, ==, <, <=)
                        is_version_compatible = self._compare_versions(version, version_spec)
                    except:
                        is_version_compatible = False

                return PackageInfo(
                    name=package_name,
                    version=version,
                    is_installed=is_installed,
                    is_version_compatible=is_version_compatible,
                    required_version=version_spec
                )

            except ImportError:
                return PackageInfo(
                    name=package_name,
                    is_installed=False,
                    required_version=version_spec
                )

        except Exception as e:
            self._logger.error(f"Failed to check package {package_name}: {str(e)}")
            return PackageInfo(
                name=package_name,
                is_installed=False,
                required_version=version_spec
            )

    def _check_library(self, lib_name: str) -> LibraryInfo:
        """Check if a system library is available."""
        try:
            # Try to find the library using various methods
            lib_path = None
            is_available = False

            # Method 1: Check common library paths
            if platform.system() == "Linux":
                common_paths = ['/lib', '/usr/lib', '/usr/local/lib', '/lib64', '/usr/lib64']
                for path in common_paths:
                    full_path = os.path.join(path, lib_name)
                    if os.path.exists(full_path):
                        lib_path = full_path
                        is_available = True
                        break

            elif platform.system() == "Windows":
                # Check system32 and other Windows paths
                system_paths = [
                    os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'System32'),
                    os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'SysWOW64')
                ]
                for path in system_paths:
                    full_path = os.path.join(path, lib_name)
                    if os.path.exists(full_path):
                        lib_path = full_path
                        is_available = True
                        break

            elif platform.system() == "Darwin":  # macOS
                common_paths = ['/usr/lib', '/usr/local/lib', '/System/Library/Frameworks']
                for path in common_paths:
                    full_path = os.path.join(path, lib_name)
                    if os.path.exists(full_path):
                        lib_path = full_path
                        is_available = True
                        break

            return LibraryInfo(
                name=lib_name,
                path=lib_path,
                is_available=is_available
            )

        except Exception as e:
            self._logger.error(f"Failed to check library {lib_name}: {str(e)}")
            return LibraryInfo(name=lib_name, is_available=False)

    def _check_cuda_driver(self) -> Optional[DriverInfo]:
        """Check NVIDIA CUDA driver."""
        try:
            # Try nvidia-smi command
            result = subprocess.run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader,nounits'],
                                  capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0] if result.stdout.strip() else None
                return DriverInfo(
                    name="NVIDIA CUDA Driver",
                    version=version,
                    is_installed=True,
                    is_version_compatible=True
                )
            else:
                return DriverInfo(
                    name="NVIDIA CUDA Driver",
                    is_installed=False
                )

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return DriverInfo(
                name="NVIDIA CUDA Driver",
                is_installed=False
            )

    def _check_rocm_driver(self) -> Optional[DriverInfo]:
        """Check AMD ROCm driver."""
        try:
            # Try rocm-smi command
            result = subprocess.run(['rocm-smi', '--showdriverversion'],
                                  capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Parse version from output
                version = None
                for line in result.stdout.split('\n'):
                    if 'Driver version' in line:
                        version = line.split(':')[-1].strip()
                        break

                return DriverInfo(
                    name="AMD ROCm Driver",
                    version=version,
                    is_installed=True,
                    is_version_compatible=True
                )
            else:
                return DriverInfo(
                    name="AMD ROCm Driver",
                    is_installed=False
                )

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return DriverInfo(
                name="AMD ROCm Driver",
                is_installed=False
            )

    def _check_intel_driver(self) -> Optional[DriverInfo]:
        """Check Intel GPU driver."""
        try:
            # Try intel_gpu_top command
            result = subprocess.run(['intel_gpu_top', '-l'],
                                  capture_output=True, text=True, timeout=5)

            if result.returncode == 0 and 'Intel' in result.stdout:
                return DriverInfo(
                    name="Intel GPU Driver",
                    is_installed=True,
                    is_version_compatible=True
                )
            else:
                return DriverInfo(
                    name="Intel GPU Driver",
                    is_installed=False
                )

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return DriverInfo(
                name="Intel GPU Driver",
                is_installed=False
            )

    def _compare_versions(self, current_version: str, version_spec: str) -> bool:
        """Compare version strings with specification."""
        try:
            # Parse version specification (e.g., ">=1.2.3", "==2.0.0")
            import re

            # Extract operator and version
            match = re.match(r'([><=!]+)(.+)', version_spec.strip())
            if not match:
                # No operator, assume exact match
                return current_version == version_spec.strip()

            operator, required_version = match.groups()

            # Convert versions to tuples for comparison
            def version_tuple(v):
                return tuple(map(int, v.split('.')))

            current_tuple = version_tuple(current_version)
            required_tuple = version_tuple(required_version)

            # Apply operator
            if operator == '>=':
                return current_tuple >= required_tuple
            elif operator == '>':
                return current_tuple > required_tuple
            elif operator == '==':
                return current_tuple == required_tuple
            elif operator == '<=':
                return current_tuple <= required_tuple
            elif operator == '<':
                return current_tuple < required_tuple
            elif operator == '!=':
                return current_tuple != required_tuple
            else:
                return False

        except Exception:
            return False

    def _determine_overall_status(self, requirements: List[DependencyRequirement]) -> DependencyStatus:
        """Determine overall dependency status."""
        if not requirements:
            return DependencyStatus.SATISFIED

        # Count status types
        status_counts = {
            DependencyStatus.SATISFIED: 0,
            DependencyStatus.MISSING: 0,
            DependencyStatus.VERSION_MISMATCH: 0,
            DependencyStatus.ERROR: 0,
            DependencyStatus.NOT_CHECKED: 0
        }

        required_missing = 0

        for req in requirements:
            status_counts[req.status] += 1
            if req.is_required and req.status in [DependencyStatus.MISSING, DependencyStatus.ERROR]:
                required_missing += 1

        # If any required dependencies are missing or have errors
        if required_missing > 0:
            return DependencyStatus.ERROR

        # If any dependencies have version mismatches
        if status_counts[DependencyStatus.VERSION_MISMATCH] > 0:
            return DependencyStatus.VERSION_MISMATCH

        # If any optional dependencies are missing
        if status_counts[DependencyStatus.MISSING] > 0:
            return DependencyStatus.PARTIALLY_SATISFIED

        # All satisfied
        return DependencyStatus.SATISFIED

    def _add_recommendations(self, result: DependencyValidationResult) -> None:
        """Add recommendations to the validation result."""
        try:
            # Check for missing required dependencies
            if result.missing_required:
                result.errors.append(f"Missing required dependencies: {', '.join(result.missing_required)}")

            # Check for missing optional dependencies
            if result.missing_optional:
                result.warnings.append(f"Missing optional dependencies: {', '.join(result.missing_optional)}")
                result.warnings.append("Optional dependencies can improve performance or provide additional features")

            # GPU-specific recommendations
            cuda_available = any(driver.name == "NVIDIA CUDA Driver" and driver.is_installed
                               for driver in result.drivers)
            rocm_available = any(driver.name == "AMD ROCm Driver" and driver.is_installed
                               for driver in result.drivers)

            if not cuda_available and not rocm_available:
                result.warnings.append("No GPU acceleration available - training will be slower")
                result.warnings.append("Consider installing NVIDIA CUDA or AMD ROCm drivers for GPU acceleration")

            # Python version recommendations
            if sys.version_info < (3, 12):
                result.warnings.append(f"Python {sys.version_info.major}.{sys.version_info.minor} detected - Python 3.12+ recommended for optimal performance")

        except Exception as e:
            self._logger.error(f"Failed to add recommendations: {str(e)}")
            result.warnings.append("Unable to generate dependency recommendations")
