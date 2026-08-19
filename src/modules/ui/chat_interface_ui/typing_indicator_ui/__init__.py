"""
Chat Interface UI - Typing Indicator Module

This module provides real-time typing indicators for the chat interface,
showing when users or AI are actively typing messages.

Components:
- TypingIndicatorUI: Main typing indicator component with animations
- TypingState: Enumeration for different typing states
- TypingConfig: Configuration for typing indicator behavior

Phase: 7 (Inference Engine & Chat Interface)
"""

from .typing_indicator_ui import (
    TypingIndicatorUI,
    TypingState,
    TypingConfig,
    TypingAnimationType,
    TypingIndicatorData
)

__all__ = [
    'TypingIndicatorUI',
    'TypingState', 
    'TypingConfig',
    'TypingAnimationType',
    'TypingIndicatorData'
]
