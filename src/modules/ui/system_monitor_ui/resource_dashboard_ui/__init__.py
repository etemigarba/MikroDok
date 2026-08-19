"""
Resource Dashboard UI Package
Provides comprehensive system resource monitoring dashboard interface.
Phase: 2
Location: /src/modules/ui/system_monitor_ui/resource_dashboard_ui/
"""

try:
    from .resource_dashboard_ui import (
        ResourceDashboardUI,
        DashboardConfiguration,
        ResourceMetrics,
        MonitoringMode
    )

    __all__ = [
        'ResourceDashboardUI',
        'DashboardConfiguration',
        'ResourceMetrics',
        'MonitoringMode'
    ]
except ImportError as e:
    # Handle import errors gracefully
    print(f"Warning: Could not import resource dashboard components: {e}")
    __all__ = []
