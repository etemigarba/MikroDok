"""
Base interfaces for conversation management logic modules.
Provides abstract base classes and data structures for session tracking, context window management, and message processing.
Phase: 4
Location: /src/modules/logic/conversation_management_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
import uuid

# Third-party imports
# None required for this module

# Local imports
# None required for base interfaces


class SessionStatus(Enum):
    """Enumeration of conversation session statuses."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    RESUMED = "resumed"
    IDLE = "idle"
    TERMINATED = "terminated"
    ERROR = "error"


class MessageRole(Enum):
    """Enumeration of message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"


class MessageType(Enum):
    """Enumeration of message types."""
    TEXT = "text"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESPONSE = "function_response"
    SYSTEM_NOTIFICATION = "system_notification"


class ContextWindowStrategy(Enum):
    """Enumeration of context window management strategies."""
    SLIDING_WINDOW = "sliding_window"
    TRUNCATE_OLDEST = "truncate_oldest"
    SUMMARIZE_OLDEST = "summarize_oldest"
    PRIORITY_BASED = "priority_based"


class MessagePriority(Enum):
    """Enumeration of message priorities."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ConversationSession:
    """Data structure representing a conversation session."""
    session_id: str
    user_id: Optional[str] = None
    model_id: Optional[str] = None
    status: SessionStatus = SessionStatus.INITIALIZING
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    terminated_at: Optional[datetime] = None
    total_messages: int = 0
    total_tokens: int = 0
    context_length: int = 4096
    session_config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMessage:
    """Data structure representing a conversation message."""
    message_id: str
    session_id: str
    role: MessageRole
    content: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    priority: MessagePriority = MessagePriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    function_call: Optional[Dict[str, Any]] = None
    function_response: Optional[Dict[str, Any]] = None


@dataclass
class ContextWindow:
    """Data structure representing a context window."""
    window_id: str
    session_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 4096
    strategy: ContextWindowStrategy = ContextWindowStrategy.SLIDING_WINDOW
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionConfig:
    """Configuration for conversation sessions."""
    max_context_length: int = 4096
    max_messages: int = 1000
    idle_timeout_minutes: int = 30
    auto_save_interval_seconds: int = 60
    enable_message_compression: bool = False
    context_window_strategy: ContextWindowStrategy = ContextWindowStrategy.SLIDING_WINDOW
    preserve_system_messages: bool = True
    enable_function_calling: bool = False
    max_function_calls_per_message: int = 5
    session_persistence_enabled: bool = True


@dataclass
class MessageProcessingConfig:
    """Configuration for message processing."""
    enable_validation: bool = True
    enable_content_filtering: bool = True
    enable_token_counting: bool = True
    enable_metadata_extraction: bool = True
    max_message_length: int = 10000
    enable_function_parsing: bool = False
    enable_markdown_processing: bool = True
    enable_code_block_detection: bool = True
    content_encoding: str = "utf-8"


@dataclass
class ContextWindowConfig:
    """Configuration for context window management."""
    max_tokens: int = 4096
    overlap_tokens: int = 128
    strategy: ContextWindowStrategy = ContextWindowStrategy.SLIDING_WINDOW
    enable_summarization: bool = False
    summarization_ratio: float = 0.3
    priority_threshold: MessagePriority = MessagePriority.HIGH
    enable_compression: bool = False
    compression_ratio: float = 0.5
    boundary_detection_enabled: bool = True


@dataclass
class SessionMetrics:
    """Metrics for conversation sessions."""
    session_id: str
    total_messages: int = 0
    total_tokens: int = 0
    average_message_length: float = 0.0
    session_duration_seconds: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    messages_per_minute: float = 0.0
    tokens_per_minute: float = 0.0
    error_count: int = 0
    function_calls_count: int = 0


@dataclass
class MessageValidationResult:
    """Result of message validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processed_content: Optional[str] = None
    extracted_metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0


@dataclass
class ContextWindowResult:
    """Result of context window operations."""
    success: bool
    window: Optional[ContextWindow] = None
    messages_included: int = 0
    messages_excluded: int = 0
    total_tokens: int = 0
    compression_applied: bool = False
    summarization_applied: bool = False
    errors: List[str] = field(default_factory=list)


class ISessionTracker(ABC):
    """Base interface for conversation session tracking."""

    @abstractmethod
    async def create_session(self, user_id: Optional[str] = None, 
                           config: Optional[SessionConfig] = None) -> str:
        """
        Create a new conversation session.

        Args:
            user_id: Optional user identifier
            config: Optional session configuration

        Returns:
            Session ID
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Get session information.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession object or None if not found
        """
        pass

    @abstractmethod
    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update session last activity timestamp.

        Args:
            session_id: Session identifier

        Returns:
            True if updated successfully
        """
        pass

    @abstractmethod
    async def pause_session(self, session_id: str) -> bool:
        """
        Pause an active session.

        Args:
            session_id: Session identifier

        Returns:
            True if paused successfully
        """
        pass

    @abstractmethod
    async def resume_session(self, session_id: str) -> bool:
        """
        Resume a paused session.

        Args:
            session_id: Session identifier

        Returns:
            True if resumed successfully
        """
        pass

    @abstractmethod
    async def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a session.

        Args:
            session_id: Session identifier

        Returns:
            True if terminated successfully
        """
        pass

    @abstractmethod
    async def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """
        Get session metrics.

        Args:
            session_id: Session identifier

        Returns:
            SessionMetrics object or None if not found
        """
        pass

    @abstractmethod
    async def cleanup_idle_sessions(self, idle_timeout_minutes: int = 30) -> int:
        """
        Clean up idle sessions.

        Args:
            idle_timeout_minutes: Timeout in minutes

        Returns:
            Number of sessions cleaned up
        """
        pass


class IContextWindowManager(ABC):
    """Base interface for context window management."""

    @abstractmethod
    async def create_window(self, session_id: str,
                          config: Optional[ContextWindowConfig] = None) -> str:
        """
        Create a new context window for a session.

        Args:
            session_id: Session identifier
            config: Optional window configuration

        Returns:
            Window ID
        """
        pass

    @abstractmethod
    async def add_message_to_window(self, window_id: str,
                                  message: ConversationMessage) -> ContextWindowResult:
        """
        Add a message to the context window.

        Args:
            window_id: Window identifier
            message: Message to add

        Returns:
            ContextWindowResult with operation details
        """
        pass

    @abstractmethod
    async def get_window(self, window_id: str) -> Optional[ContextWindow]:
        """
        Get context window information.

        Args:
            window_id: Window identifier

        Returns:
            ContextWindow object or None if not found
        """
        pass

    @abstractmethod
    async def optimize_window(self, window_id: str) -> ContextWindowResult:
        """
        Optimize context window by applying compression or summarization.

        Args:
            window_id: Window identifier

        Returns:
            ContextWindowResult with optimization details
        """
        pass

    @abstractmethod
    async def get_formatted_context(self, window_id: str) -> str:
        """
        Get formatted context for model input.

        Args:
            window_id: Window identifier

        Returns:
            Formatted context string
        """
        pass

    @abstractmethod
    async def clear_window(self, window_id: str) -> bool:
        """
        Clear all messages from context window.

        Args:
            window_id: Window identifier

        Returns:
            True if cleared successfully
        """
        pass


class IMessageProcessor(ABC):
    """Base interface for message processing."""

    @abstractmethod
    async def process_message(self, content: str, role: MessageRole,
                            session_id: str, config: Optional[MessageProcessingConfig] = None) -> MessageValidationResult:
        """
        Process and validate a message.

        Args:
            content: Message content
            role: Message role
            session_id: Session identifier
            config: Optional processing configuration

        Returns:
            MessageValidationResult with processing details
        """
        pass

    @abstractmethod
    async def create_message(self, content: str, role: MessageRole,
                           session_id: str, metadata: Optional[Dict[str, Any]] = None) -> ConversationMessage:
        """
        Create a conversation message.

        Args:
            content: Message content
            role: Message role
            session_id: Session identifier
            metadata: Optional message metadata

        Returns:
            ConversationMessage object
        """
        pass

    @abstractmethod
    async def validate_message(self, message: ConversationMessage) -> MessageValidationResult:
        """
        Validate a message.

        Args:
            message: Message to validate

        Returns:
            MessageValidationResult with validation details
        """
        pass

    @abstractmethod
    async def extract_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extract metadata from message content.

        Args:
            content: Message content

        Returns:
            Dictionary of extracted metadata
        """
        pass

    @abstractmethod
    async def count_tokens(self, content: str) -> int:
        """
        Count tokens in message content.

        Args:
            content: Message content

        Returns:
            Token count
        """
        pass

    @abstractmethod
    async def format_message(self, message: ConversationMessage,
                           format_type: str = "plain") -> str:
        """
        Format message for display or processing.

        Args:
            message: Message to format
            format_type: Format type (plain, markdown, html)

        Returns:
            Formatted message string
        """
        pass
