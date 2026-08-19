"""
MikroDok Resource Monitor Package
Provides comprehensive resource monitoring functionality for hardware tracking and performance optimization.
"""

# Import all resource monitoring components
from .hardware_monitor_lg.hardware_monitor_lg import (
    HardwareMonitor,
    IResourceMonitor,
    ResourceMetrics,
    MonitoringConfiguration,
    MonitoringThresholds,
    ResourceAlert,
    AlertSeverity
)

from .gpu_monitor_lg.gpu_monitor_lg import (
    GPUMonitor,
    GPUMetrics,
    GPUInfo,
    CUDAInfo,
    ROCmInfo
)

from .memory_monitor_lg.memory_monitor_lg import (
    MemoryMonitor,
    MemoryMetrics,
    MemoryAllocationPattern,
    SwapUsageInfo
)

from .disk_monitor_lg.disk_monitor_lg import (
    DiskMonitor,
    DiskMetrics,
    IOPerformanceMetrics,
    StorageInfo
)

from .thermal_monitor_lg.thermal_monitor_lg import (
    ThermalMonitor,
    ThermalMetrics,
    TemperatureThresholds,
    ThrottlingInfo
)

__all__ = [
    # Hardware Monitoring
    'HardwareMonitor',
    'IResourceMonitor',
    'ResourceMetrics',
    'MonitoringConfiguration',
    'MonitoringThresholds',
    'ResourceAlert',
    'AlertSeverity',
    
    # GPU Monitoring
    'GPUMonitor',
    'GPUMetrics',
    'GPUInfo',
    'CUDAInfo',
    'ROCmInfo',
    
    # Memory Monitoring
    'MemoryMonitor',
    'MemoryMetrics',
    'MemoryAllocationPattern',
    'SwapUsageInfo',
    
    # Disk Monitoring
    'DiskMonitor',
    'DiskMetrics',
    'IOPerformanceMetrics',
    'StorageInfo',
    
    # Thermal Monitoring
    'ThermalMonitor',
    'ThermalMetrics',
    'TemperatureThresholds',
    'ThrottlingInfo'
]
