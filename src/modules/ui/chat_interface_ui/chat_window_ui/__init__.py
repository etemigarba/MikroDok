"""
MikroDok Chat Window UI Package
Main chat window component with conversation display and message management.
"""

# Import chat window components
try:
    from .chat_window_ui import ChatWindowUI
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Chat window UI component for MikroDok application"

# Export main components
__all__ = ["ChatWindowUI"]
