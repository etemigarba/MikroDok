"""
MikroDok System Monitor UI Package
Provides comprehensive system monitoring interface components including resource dashboard, CPU monitoring, GPU monitoring, and memory monitoring.
Phase: 2
Location: /src/modules/ui/system_monitor_ui/
"""

# Import system monitor components
try:
    from .resource_dashboard_ui.resource_dashboard_ui import (
        ResourceDashboardUI,
        DashboardConfiguration,
        ResourceMetrics,
        MonitoringMode
    )
except ImportError:
    pass

# Import CPU monitor components
try:
    from .cpu_monitor_ui.cpu_monitor_ui import (
        CPUMonitorUI,
        CPUDisplayMode,
        CPUMetricsPanel,
        CPUCoreChart,
        CPULoadGauge,
        CPUTemperatureGauge,
        CPUFrequencyChart,
        CPUAlertThreshold,
        CPUMonitorConfiguration
    )
except ImportError:
    pass

# Import GPU monitor components
try:
    from .gpu_monitor_ui.gpu_monitor_ui import (
        GPUMonitorUI,
        GPUDisplayMode,
        GPUMetricsPanel,
        GPUInfoPanel,
        TemperatureGauge,
        UtilizationChart,
        GPUAlertThreshold,
        GPUMonitorConfiguration
    )
except ImportError:
    pass

# Import memory monitor components
try:
    from .memory_monitor_ui.memory_monitor_ui import (
        MemoryMonitorUI,
        MemoryDisplayMode,
        MemoryMetricsPanel,
        MemoryUsageChart,
        MemoryPressureGauge,
        MemoryAllocationChart,
        MemoryAlertThreshold,
        MemoryMonitorConfiguration
    )
except ImportError:
    pass

# Import allocation control components
try:
    from .allocation_control_ui.allocation_control_ui import (
        AllocationControlUI,
        AllocationControlMode,
        AllocationControlConfiguration,
        MemoryLimitConfiguration,
        ThermalLimitConfiguration,
        AllocationControlState,
        AllocationControlAction
    )
except ImportError:
    pass

__all__ = [
    # Resource dashboard components
    'ResourceDashboardUI',
    'DashboardConfiguration',
    'ResourceMetrics',
    'MonitoringMode',
    # CPU monitor components
    'CPUMonitorUI',
    'CPUDisplayMode',
    'CPUMetricsPanel',
    'CPUCoreChart',
    'CPULoadGauge',
    'CPUTemperatureGauge',
    'CPUFrequencyChart',
    'CPUAlertThreshold',
    'CPUMonitorConfiguration',
    # GPU monitor components
    'GPUMonitorUI',
    'GPUDisplayMode',
    'GPUMetricsPanel',
    'GPUInfoPanel',
    'TemperatureGauge',
    'UtilizationChart',
    'GPUAlertThreshold',
    'GPUMonitorConfiguration',
    # Memory monitor components
    'MemoryMonitorUI',
    'MemoryDisplayMode',
    'MemoryMetricsPanel',
    'MemoryUsageChart',
    'MemoryPressureGauge',
    'MemoryAllocationChart',
    'MemoryAlertThreshold',
    'MemoryMonitorConfiguration',
    # Allocation control components
    'AllocationControlUI',
    'AllocationControlMode',
    'AllocationControlConfiguration',
    'MemoryLimitConfiguration',
    'ThermalLimitConfiguration',
    'AllocationControlState',
    'AllocationControlAction'
]
