"""
Module: footer_status_ui
Description: Footer status UI module for MikroDok application.
            Provides comprehensive footer status bar with system information, resource monitoring,
            version details, and quick access controls. Features responsive design with theme integration.
Phase: 1
Location: /src/modules/ui/navigation_ui/footer_status_ui/
"""

__all__ = [
    "FooterStatusUI",
    "SystemStatusInfo",
    "ResourceMetrics",
    "FooterConfig",
    "StatusIndicator",
    "QuickAction"
]

# Import footer status components when available
try:
    from .footer_status_ui import (
        FooterStatusUI,
        SystemStatusInfo,
        ResourceMetrics,
        FooterConfig,
        StatusIndicator,
        QuickAction
    )
except ImportError:
    FooterStatusUI = None
    SystemStatusInfo = None
    ResourceMetrics = None
    FooterConfig = None
    StatusIndicator = None
    QuickAction = None
