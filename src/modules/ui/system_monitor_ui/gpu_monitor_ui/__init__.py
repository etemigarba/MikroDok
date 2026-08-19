"""
MikroDok GPU Monitor UI Package
Provides comprehensive GPU monitoring interface components including real-time metrics display, temperature monitoring, VRAM usage visualization, and compute utilization tracking.
Phase: 2
Location: /src/modules/ui/system_monitor_ui/gpu_monitor_ui/
"""

# Import GPU monitor components
try:
    from .gpu_monitor_ui import (
        GPUMonitorUI,
        GPUDisplayMode,
        GPUMetricsPanel,
        GPUInfoPanel,
        TemperatureGauge,
        UtilizationChart
    )

    __all__ = [
        'GPUMonitorUI',
        'GPUDisplayMode',
        'GPUMetricsPanel',
        'GPUInfoPanel',
        'TemperatureGauge',
        'UtilizationChart'
    ]

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import GPU monitor components: {e}")

    __all__ = []
