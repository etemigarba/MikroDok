"""
MikroDok System Tray Icon UI Package
Provides system tray icon functionality with context menu and notification integration.
"""

# Import tray icon components
try:
    from .tray_icon_ui import (
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
