"""
MikroDok Chat Settings UI Package
Provides comprehensive chat configuration and preferences interface.
"""

# Import chat settings components
try:
    from .chat_settings_ui import ChatSettingsUI
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Chat settings UI components for MikroDok chat interface"

# Export main components
__all__ = [
    "ChatSettingsUI"
]
