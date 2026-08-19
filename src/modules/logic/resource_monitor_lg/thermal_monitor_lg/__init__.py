"""
Thermal Monitor Module
Temperature monitoring system with throttling detection and automatic performance adjustment capabilities.
"""

from .thermal_monitor_lg import (
    ThermalMonitor,
    ThermalMetrics,
    TemperatureThresholds,
    ThrottlingInfo
)

__all__ = [
    'ThermalMonitor',
    'ThermalMetrics',
    'TemperatureThresholds',
    'ThrottlingInfo'
]
