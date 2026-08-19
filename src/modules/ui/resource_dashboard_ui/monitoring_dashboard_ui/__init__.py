"""
Monitoring Dashboard UI Package
Provides comprehensive real-time system resource monitoring interface.
"""

try:
    from .monitoring_dashboard_ui import (
        MonitoringDashboardUI,
        DashboardConfiguration
    )

    __all__ = [
        'MonitoringDashboardUI',
        'DashboardConfiguration'
    ]
except ImportError as e:
    # Handle import errors gracefully
    print(f"Warning: Could not import monitoring dashboard components: {e}")
    __all__ = []
