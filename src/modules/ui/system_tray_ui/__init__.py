"""
MikroDok System Tray UI Package
Provides system tray integration functionality for the MikroDok application.
"""

# Import system tray components
try:
    from .tray_icon_ui.tray_icon_ui import (
        TrayIconUI,
        TrayIconState,
        TrayMenuAction,
        TrayNotification,
        TrayIconConfig
    )
except ImportError:
    pass

__all__ = [
    'TrayIconUI',
    'TrayIconState', 
    'TrayMenuAction',
    'TrayNotification',
    'TrayIconConfig'
]
