"""
MikroDok System Monitor Memory Monitor UI Package
Provides comprehensive memory monitoring interface components for system resource monitoring.
Phase: 2
Location: /src/modules/ui/system_monitor_ui/memory_monitor_ui/
"""

# Import memory monitor components
try:
    from .memory_monitor_ui import (
        MemoryMonitorUI,
        MemoryDisplayMode,
        MemoryMetricsPanel,
        MemoryUsageChart,
        MemoryPressureGauge,
        MemoryAllocationChart,
        MemoryAlertThreshold,
        MemoryMonitorConfiguration
    )

    __all__ = [
        'MemoryMonitorUI',
        'MemoryDisplayMode',
        'MemoryMetricsPanel',
        'MemoryUsageChart',
        'MemoryPressureGauge',
        'MemoryAllocationChart',
        'MemoryAlertThreshold',
        'MemoryMonitorConfiguration'
    ]

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import memory monitor components: {e}")

    __all__ = []
