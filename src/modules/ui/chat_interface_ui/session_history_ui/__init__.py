"""
MikroDok Session History UI Package
Provides comprehensive session history interface for chat functionality.
"""

# Import session history components
try:
    from .session_history_ui import SessionHistoryUI
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Session history UI components for MikroDok chat interface"

# Export main components
__all__ = [
    "SessionHistoryUI"
]
