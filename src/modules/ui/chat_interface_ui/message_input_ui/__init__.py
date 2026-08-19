"""
MikroDok Message Input UI Package
Provides comprehensive message input interface for chat functionality.
"""

# Import message input components
try:
    from .message_input_ui import MessageInputUI
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Message input UI components for MikroDok chat interface"

# Export main components
__all__ = [
    "MessageInputUI"
]
