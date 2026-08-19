"""
MikroDok CPU Monitor UI Package
Provides comprehensive CPU monitoring interface components including real-time usage graphs, per-core visualization, thermal monitoring, and load average tracking.
Phase: 2
Location: /src/modules/ui/system_monitor_ui/cpu_monitor_ui/
"""

# Import CPU monitor components
try:
    from .cpu_monitor_ui import (
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

    __all__ = [
        'CPUMonitorUI',
        'CPUDisplayMode',
        'CPUMetricsPanel',
        'CPUCoreChart',
        'CPULoadGauge',
        'CPUTemperatureGauge',
        'CPUFrequencyChart',
        'CPUAlertThreshold',
        'CPUMonitorConfiguration'
    ]

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import CPU monitor components: {e}")

    __all__ = []
