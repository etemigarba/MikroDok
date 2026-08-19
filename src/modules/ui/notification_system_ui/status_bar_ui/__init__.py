"""
Status Bar UI Module

This module provides status bar components for the MikroDok notification system.
Includes persistent status message display with theme integration and responsive design.

Phase: 1
Location: /src/modules/ui/notification_system_ui/status_bar_ui/
"""

try:
    from .status_bar_ui import (
        StatusBarUI,
        StatusConfig,
        StatusType,
        StatusLevel,
        StatusState,
        create_status_bar,
        update_status_bar
    )
except ImportError:
    pass

__all__ = [
    "StatusBarUI",
    "StatusConfig", 
    "StatusType",
    "StatusLevel",
    "StatusState",
    "create_status_bar",
    "update_status_bar"
]
