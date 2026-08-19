"""
MikroDok Chat Interface UI Package
Provides comprehensive chat interface components for real-time conversation management.
"""

# Import chat interface components
try:
    from .chat_window_ui.chat_window_ui import ChatWindowUI
except ImportError:
    pass

try:
    from .message_input_ui.message_input_ui import MessageInputUI
except ImportError:
    pass

try:
    from .session_history_ui.session_history_ui import SessionHistoryUI
except ImportError:
    pass

try:
    from .chat_settings_ui.chat_settings_ui import ChatSettingsUI
except ImportError:
    pass

try:
    from .message_bubble_ui.message_bubble_ui import MessageBubbleUI
except ImportError:
    pass

try:
    from .typing_indicator_ui.typing_indicator_ui import TypingIndicatorUI
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Chat interface UI components for MikroDok application"

# Export main components
__all__ = [
    "ChatWindowUI",
    "MessageInputUI", 
    "SessionHistoryUI",
    "ChatSettingsUI",
    "MessageBubbleUI",
    "TypingIndicatorUI"
]
