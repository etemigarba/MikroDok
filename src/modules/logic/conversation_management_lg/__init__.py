"""
MikroDok Conversation Management Package
Provides comprehensive conversation management functionality including session tracking, context window management, and message processing.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        # Enums
        SessionStatus,
        MessageRole,
        MessageType,
        ContextWindowStrategy,
        MessagePriority,
        
        # Data Classes
        ConversationSession,
        ConversationMessage,
        ContextWindow,
        SessionConfig,
        MessageProcessingConfig,
        ContextWindowConfig,
        SessionMetrics,
        MessageValidationResult,
        ContextWindowResult,
        
        # Interfaces
        ISessionTracker,
        IContextWindowManager,
        IMessageProcessor
    )
except ImportError:
    pass

# Import session tracker components
try:
    from .session_tracker_lg.session_tracker_lg import (
        SessionTracker,
        SessionStateManager,
        SessionCleanupManager
    )
except ImportError:
    pass

# Import context window manager components
try:
    from .context_window_manager_lg.context_window_manager_lg import (
        ContextWindowManager,
        TokenCounter,
        BoundaryManager,
        ContextOptimizer
    )
except ImportError:
    pass

# Import message processor components
try:
    from .message_processor_lg.message_processor_lg import (
        MessageProcessor,
        MessageValidator,
        MetadataExtractor,
        ContentFormatter
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'SessionStatus',
    'MessageRole',
    'MessageType',
    'ContextWindowStrategy',
    'MessagePriority',
    'ConversationSession',
    'ConversationMessage',
    'ContextWindow',
    'SessionConfig',
    'MessageProcessingConfig',
    'ContextWindowConfig',
    'SessionMetrics',
    'MessageValidationResult',
    'ContextWindowResult',
    'ISessionTracker',
    'IContextWindowManager',
    'IMessageProcessor',
    
    # Session Tracker
    'SessionTracker',
    'SessionStateManager',
    'SessionCleanupManager',
    
    # Context Window Manager
    'ContextWindowManager',
    'TokenCounter',
    'BoundaryManager',
    'ContextOptimizer',
    
    # Message Processor
    'MessageProcessor',
    'MessageValidator',
    'MetadataExtractor',
    'ContentFormatter'
]
