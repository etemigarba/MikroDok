"""
Hardware Monitor Module
Core monitoring service that continuously tracks GPU, CPU, RAM, and storage utilization with configurable sampling intervals.
"""

from .hardware_monitor_lg import (
    HardwareMonitor,
    IResourceMonitor,
    ResourceMetrics,
    MonitoringConfiguration,
    MonitoringThresholds,
    ResourceAlert,
    AlertSeverity
)

__all__ = [
    'HardwareMonitor',
    'IResourceMonitor',
    'ResourceMetrics',
    'MonitoringConfiguration',
    'MonitoringThresholds',
    'ResourceAlert',
    'AlertSeverity'
]
