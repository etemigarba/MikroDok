"""
MikroDok Message Bubble UI Package
Provides individual message bubble components for chat interface.
"""

# Import message bubble components
try:
    from .message_bubble_ui import MessageBubbleUI
except ImportError:
    pass

__all__ = ['MessageBubbleUI']
