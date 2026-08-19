"""
MikroDok System Requirements Package
Provides comprehensive system requirements validation functionality.
"""

# Import all system requirements components
from .hardware_validator_lg.hardware_validator_lg import (
    HardwareValidator,
    IHardwareValidator,
    HardwareRequirement,
    HardwareCapability,
    HardwareValidationResult,
    SystemArchitecture,
    GPUInfo,
    CPUInfo,
    MemoryInfo,
    StorageInfo
)

from .dependency_checker_lg.dependency_checker_lg import (
    DependencyChecker,
    IDependencyChecker,
    DependencyRequirement,
    DependencyType,
    DependencyStatus,
    DependencyValidationResult,
    PackageInfo,
    LibraryInfo,
    DriverInfo
)

__all__ = [
    # Hardware Validation
    'HardwareValidator',
    'IHardwareValidator',
    'HardwareRequirement',
    'HardwareCapability',
    'HardwareValidationResult',
    'SystemArchitecture',
    'GPUInfo',
    'CPUInfo',
    'MemoryInfo',
    'StorageInfo',
    
    # Dependency Checking
    'DependencyChecker',
    'IDependencyChecker',
    'DependencyRequirement',
    'DependencyType',
    'DependencyStatus',
    'DependencyValidationResult',
    'PackageInfo',
    'LibraryInfo',
    'DriverInfo'
]
