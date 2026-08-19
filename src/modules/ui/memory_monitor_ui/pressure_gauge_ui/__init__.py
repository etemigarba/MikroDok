"""
MikroDok Pressure Gauge UI Package
Provides memory pressure visualization and monitoring functionality for the IDRAlloc system.
Phase: 2
Location: /src/modules/ui/memory_monitor_ui/pressure_gauge_ui/
"""

# Import pressure gauge components
try:
    from .pressure_gauge_ui import (
        PressureGaugeUI,
        PressureLevel,
        PressureIndicator,
        PressureThreshold,
        PressureGaugeConfig,
        GaugeStyle,
        PressureTrend,
        PressureEvent
    )
except ImportError:
    pass

__all__ = [
    'PressureGaugeUI',
    'PressureLevel',
    'PressureIndicator',
    'PressureThreshold',
    'PressureGaugeConfig',
    'GaugeStyle',
    'PressureTrend',
    'PressureEvent'
]
