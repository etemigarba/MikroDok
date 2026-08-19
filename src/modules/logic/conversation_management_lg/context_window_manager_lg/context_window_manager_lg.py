"""
Module: context_window_manager_lg
Description: Manages context windows with token counting, boundary management, and context optimization
Phase: 4
Location: /src/modules/logic/conversation_management_lg/context_window_manager_lg/context_window_manager_lg.py
"""

# Standard library imports
import asyncio
import json
import re
import threading
import uuid
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging

# Third-party imports
# None required for this module

# Local imports
from ..base_interfaces import (
    IContextWindowManager,
    ContextWindow,
    ContextWindowConfig,
    ContextWindowResult,
    ContextWindowStrategy,
    ConversationMessage,
    MessagePriority,
    MessageRole
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)


class ContextWindowError(Exception):
    """Exception raised when context window operations fail."""
    pass


class TokenCountError(Exception):
    """Exception raised when token counting fails."""
    pass


class TokenCounter:
    """
    Handles token counting for messages and content.
    
    Provides accurate token counting using approximation algorithms
    optimized for performance and memory efficiency.
    """
    
    def __init__(self):
        """Initialize token counter."""
        self._logger = get_log_manager().get_logger(__name__)
        
        # Token estimation patterns (rough approximation)
        self._word_pattern = re.compile(r'\b\w+\b')
        self._punctuation_pattern = re.compile(r'[^\w\s]')
        
        # Average tokens per word for different content types
        self._tokens_per_word = {
            'english': 1.3,
            'code': 1.8,
            'mixed': 1.5
        }
    
    def count_tokens(self, content: str, content_type: str = 'mixed') -> int:
        """
        Count tokens in content.
        
        Args:
            content: Text content to count
            content_type: Type of content (english, code, mixed)
            
        Returns:
            int: Estimated token count
        """
        try:
            if not content:
                return 0
            
            # Count words and punctuation
            words = len(self._word_pattern.findall(content))
            punctuation = len(self._punctuation_pattern.findall(content))
            
            # Apply content-specific multiplier
            multiplier = self._tokens_per_word.get(content_type, 1.5)
            
            # Estimate tokens
            estimated_tokens = int((words * multiplier) + (punctuation * 0.5))
            
            return max(1, estimated_tokens)  # Minimum 1 token
            
        except Exception as e:
            self._logger.error(f"Error counting tokens: {e}")
            # Fallback: rough character-based estimation
            return max(1, len(content) // 4)
    
    def count_message_tokens(self, message: ConversationMessage) -> int:
        """
        Count tokens in a conversation message.
        
        Args:
            message: ConversationMessage to count
            
        Returns:
            int: Token count including metadata overhead
        """
        try:
            # Count content tokens
            content_tokens = self.count_tokens(message.content)
            
            # Add overhead for role and metadata
            overhead_tokens = 3  # Role, timestamp, etc.
            
            # Add function call tokens if present
            if message.function_call:
                function_tokens = self.count_tokens(json.dumps(message.function_call))
                overhead_tokens += function_tokens
            
            if message.function_response:
                response_tokens = self.count_tokens(json.dumps(message.function_response))
                overhead_tokens += response_tokens
            
            return content_tokens + overhead_tokens
            
        except Exception as e:
            self._logger.error(f"Error counting message tokens: {e}")
            return self.count_tokens(message.content)


class BoundaryManager:
    """
    Manages context window boundaries and message selection.
    
    Handles intelligent boundary detection and message prioritization
    for optimal context window construction.
    """
    
    def __init__(self, token_counter: TokenCounter):
        """Initialize boundary manager with token counter."""
        self._token_counter = token_counter
        self._logger = get_log_manager().get_logger(__name__)
    
    def find_optimal_boundary(self, messages: List[ConversationMessage], 
                            max_tokens: int, strategy: ContextWindowStrategy) -> Tuple[int, int]:
        """
        Find optimal boundary for context window.
        
        Args:
            messages: List of messages to analyze
            max_tokens: Maximum token limit
            strategy: Boundary selection strategy
            
        Returns:
            Tuple of (start_index, end_index) for optimal boundary
        """
        try:
            if not messages:
                return (0, 0)
            
            if strategy == ContextWindowStrategy.SLIDING_WINDOW:
                return self._sliding_window_boundary(messages, max_tokens)
            elif strategy == ContextWindowStrategy.TRUNCATE_OLDEST:
                return self._truncate_oldest_boundary(messages, max_tokens)
            elif strategy == ContextWindowStrategy.PRIORITY_BASED:
                return self._priority_based_boundary(messages, max_tokens)
            else:
                # Default to sliding window
                return self._sliding_window_boundary(messages, max_tokens)
                
        except Exception as e:
            self._logger.error(f"Error finding optimal boundary: {e}")
            return (max(0, len(messages) - 10), len(messages))  # Fallback
    
    def _sliding_window_boundary(self, messages: List[ConversationMessage], 
                               max_tokens: int) -> Tuple[int, int]:
        """Find boundary using sliding window strategy."""
        total_tokens = 0
        start_index = len(messages)
        
        # Work backwards from the most recent message
        for i in range(len(messages) - 1, -1, -1):
            message_tokens = self._token_counter.count_message_tokens(messages[i])
            
            if total_tokens + message_tokens <= max_tokens:
                total_tokens += message_tokens
                start_index = i
            else:
                break
        
        return (start_index, len(messages))
    
    def _truncate_oldest_boundary(self, messages: List[ConversationMessage], 
                                max_tokens: int) -> Tuple[int, int]:
        """Find boundary using truncate oldest strategy."""
        total_tokens = 0
        end_index = len(messages)
        
        # Work backwards, keeping system messages
        for i in range(len(messages) - 1, -1, -1):
            message_tokens = self._token_counter.count_message_tokens(messages[i])
            
            if total_tokens + message_tokens <= max_tokens:
                total_tokens += message_tokens
            else:
                # Keep system messages even if they exceed limit
                if messages[i].role == MessageRole.SYSTEM:
                    continue
                else:
                    end_index = i + 1
                    break
        
        return (0, end_index)
    
    def _priority_based_boundary(self, messages: List[ConversationMessage], 
                               max_tokens: int) -> Tuple[int, int]:
        """Find boundary using priority-based strategy."""
        # Sort messages by priority and recency
        prioritized = sorted(
            enumerate(messages),
            key=lambda x: (x[1].priority.value, x[0]),
            reverse=True
        )
        
        selected_indices = []
        total_tokens = 0
        
        for original_index, message in prioritized:
            message_tokens = self._token_counter.count_message_tokens(message)
            
            if total_tokens + message_tokens <= max_tokens:
                total_tokens += message_tokens
                selected_indices.append(original_index)
            else:
                break
        
        if not selected_indices:
            return (len(messages) - 1, len(messages))
        
        # Return contiguous range
        selected_indices.sort()
        return (selected_indices[0], selected_indices[-1] + 1)


class ContextOptimizer:
    """
    Optimizes context windows through compression and summarization.
    
    Provides intelligent context optimization strategies to maximize
    information density within token constraints.
    """
    
    def __init__(self, token_counter: TokenCounter):
        """Initialize context optimizer with token counter."""
        self._token_counter = token_counter
        self._logger = get_log_manager().get_logger(__name__)
    
    async def optimize_context(self, window: ContextWindow, 
                             config: ContextWindowConfig) -> ContextWindowResult:
        """
        Optimize context window.
        
        Args:
            window: ContextWindow to optimize
            config: Optimization configuration
            
        Returns:
            ContextWindowResult with optimization details
        """
        try:
            result = ContextWindowResult(success=False)
            
            if not window.messages:
                result.success = True
                return result
            
            # Apply compression if enabled
            if config.enable_compression and window.total_tokens > config.max_tokens:
                compression_result = await self._apply_compression(window, config)
                result.compression_applied = compression_result
            
            # Apply summarization if enabled
            if config.enable_summarization and window.total_tokens > config.max_tokens:
                summarization_result = await self._apply_summarization(window, config)
                result.summarization_applied = summarization_result
            
            # Update result
            result.success = True
            result.window = window
            result.messages_included = len(window.messages)
            result.total_tokens = window.total_tokens
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error optimizing context: {e}")
            return ContextWindowResult(
                success=False,
                errors=[f"Optimization failed: {str(e)}"]
            )
    
    async def _apply_compression(self, window: ContextWindow, 
                               config: ContextWindowConfig) -> bool:
        """Apply compression to context window."""
        try:
            # Simple compression: remove redundant whitespace and formatting
            for message in window.messages:
                original_content = message.content
                
                # Remove extra whitespace
                compressed_content = re.sub(r'\s+', ' ', original_content.strip())
                
                # Update message
                message.content = compressed_content
                message.token_count = self._token_counter.count_message_tokens(message)
            
            # Recalculate total tokens
            window.total_tokens = sum(msg.token_count for msg in window.messages)
            
            self._logger.debug(f"Applied compression to window {window.window_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error applying compression: {e}")
            return False
    
    async def _apply_summarization(self, window: ContextWindow, 
                                 config: ContextWindowConfig) -> bool:
        """Apply summarization to context window."""
        try:
            # Simple summarization: truncate older messages
            target_tokens = int(config.max_tokens * config.summarization_ratio)
            
            # Keep recent messages, summarize older ones
            total_tokens = 0
            keep_from_index = len(window.messages)
            
            # Work backwards to find cutoff point
            for i in range(len(window.messages) - 1, -1, -1):
                message_tokens = window.messages[i].token_count
                if total_tokens + message_tokens <= target_tokens:
                    total_tokens += message_tokens
                    keep_from_index = i
                else:
                    break
            
            # Create summary message for truncated content
            if keep_from_index > 0:
                truncated_count = keep_from_index
                summary_content = f"[Summary: {truncated_count} earlier messages truncated]"
                
                # Create summary message
                summary_message = ConversationMessage(
                    message_id=str(uuid.uuid4()),
                    session_id=window.session_id,
                    role=MessageRole.SYSTEM,
                    content=summary_content,
                    timestamp=window.messages[0].timestamp,
                    token_count=self._token_counter.count_tokens(summary_content),
                    priority=MessagePriority.LOW
                )
                
                # Replace truncated messages with summary
                window.messages = [summary_message] + window.messages[keep_from_index:]
                window.total_tokens = sum(msg.token_count for msg in window.messages)
            
            self._logger.debug(f"Applied summarization to window {window.window_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error applying summarization: {e}")
            return False


class ContextWindowManager(IContextWindowManager):
    """
    Production-ready context window manager.

    Manages context windows with token counting, boundary management, and context optimization
    for efficient conversation context handling with memory and performance optimization.
    """

    def __init__(self, default_config: Optional[ContextWindowConfig] = None):
        """Initialize context window manager with optional default configuration."""
        self._logger = get_log_manager().get_logger(__name__)
        self._default_config = default_config or ContextWindowConfig()

        # Initialize components
        self._token_counter = TokenCounter()
        self._boundary_manager = BoundaryManager(self._token_counter)
        self._optimizer = ContextOptimizer(self._token_counter)
        self._validator = ValidationEngine()

        # Thread-safe window tracking
        self._windows: Dict[str, ContextWindow] = {}
        self._window_configs: Dict[str, ContextWindowConfig] = {}
        self._window_locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()

        # Performance metrics
        self._operation_count = 0
        self._total_tokens_processed = 0

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
        window_id = str(uuid.uuid4())

        try:
            # Use provided config or default
            window_config = config or self._default_config

            # Validate configuration
            validation_result = await self._validate_config(window_config)
            if not validation_result.is_valid:
                raise ContextWindowError(f"Invalid configuration: {validation_result.errors}")

            # Create context window
            window = ContextWindow(
                window_id=window_id,
                session_id=session_id,
                messages=[],
                total_tokens=0,
                max_tokens=window_config.max_tokens,
                strategy=window_config.strategy,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={}
            )

            # Store window and configuration
            with self._global_lock:
                self._windows[window_id] = window
                self._window_configs[window_id] = window_config
                self._window_locks[window_id] = threading.RLock()

            self._logger.info(f"Created context window {window_id} for session {session_id}")
            return window_id

        except Exception as e:
            self._logger.error(f"Failed to create context window: {str(e)}")
            # Cleanup on failure
            with self._global_lock:
                self._windows.pop(window_id, None)
                self._window_configs.pop(window_id, None)
                self._window_locks.pop(window_id, None)
            raise

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
        try:
            if window_id not in self._windows:
                return ContextWindowResult(
                    success=False,
                    errors=[f"Window {window_id} not found"]
                )

            with self._window_locks[window_id]:
                window = self._windows[window_id]
                config = self._window_configs[window_id]

                # Count tokens for the message
                message.token_count = self._token_counter.count_message_tokens(message)

                # Check if adding this message would exceed limit
                if window.total_tokens + message.token_count > config.max_tokens:
                    # Apply boundary management
                    await self._manage_window_boundary(window, config, message.token_count)

                # Add message to window
                window.messages.append(message)
                window.total_tokens += message.token_count
                window.updated_at = datetime.now()

                # Update metrics
                self._operation_count += 1
                self._total_tokens_processed += message.token_count

                result = ContextWindowResult(
                    success=True,
                    window=window,
                    messages_included=len(window.messages),
                    total_tokens=window.total_tokens
                )

                self._logger.debug(f"Added message to window {window_id} "
                                 f"({message.token_count} tokens, {window.total_tokens} total)")

                return result

        except Exception as e:
            self._logger.error(f"Error adding message to window {window_id}: {str(e)}")
            return ContextWindowResult(
                success=False,
                errors=[f"Failed to add message: {str(e)}"]
            )

    async def get_window(self, window_id: str) -> Optional[ContextWindow]:
        """
        Get context window information.

        Args:
            window_id: Window identifier

        Returns:
            ContextWindow object or None if not found
        """
        try:
            return self._windows.get(window_id)

        except Exception as e:
            self._logger.error(f"Error getting window {window_id}: {str(e)}")
            return None

    async def optimize_window(self, window_id: str) -> ContextWindowResult:
        """
        Optimize context window by applying compression or summarization.

        Args:
            window_id: Window identifier

        Returns:
            ContextWindowResult with optimization details
        """
        try:
            if window_id not in self._windows:
                return ContextWindowResult(
                    success=False,
                    errors=[f"Window {window_id} not found"]
                )

            with self._window_locks[window_id]:
                window = self._windows[window_id]
                config = self._window_configs[window_id]

                # Apply optimization
                result = await self._optimizer.optimize_context(window, config)

                if result.success:
                    window.updated_at = datetime.now()
                    self._logger.info(f"Optimized window {window_id}")

                return result

        except Exception as e:
            self._logger.error(f"Error optimizing window {window_id}: {str(e)}")
            return ContextWindowResult(
                success=False,
                errors=[f"Optimization failed: {str(e)}"]
            )

    async def get_formatted_context(self, window_id: str) -> str:
        """
        Get formatted context for model input.

        Args:
            window_id: Window identifier

        Returns:
            Formatted context string
        """
        try:
            if window_id not in self._windows:
                return ""

            window = self._windows[window_id]

            # Format messages for model input
            formatted_parts = []

            for message in window.messages:
                # Format based on role
                if message.role == MessageRole.SYSTEM:
                    formatted_parts.append(f"System: {message.content}")
                elif message.role == MessageRole.USER:
                    formatted_parts.append(f"User: {message.content}")
                elif message.role == MessageRole.ASSISTANT:
                    formatted_parts.append(f"Assistant: {message.content}")
                elif message.role == MessageRole.FUNCTION:
                    if message.function_call:
                        formatted_parts.append(f"Function Call: {json.dumps(message.function_call)}")
                    if message.function_response:
                        formatted_parts.append(f"Function Response: {json.dumps(message.function_response)}")

            return "\n\n".join(formatted_parts)

        except Exception as e:
            self._logger.error(f"Error formatting context for window {window_id}: {str(e)}")
            return ""

    async def clear_window(self, window_id: str) -> bool:
        """
        Clear all messages from context window.

        Args:
            window_id: Window identifier

        Returns:
            True if cleared successfully
        """
        try:
            if window_id not in self._windows:
                return False

            with self._window_locks[window_id]:
                window = self._windows[window_id]
                window.messages.clear()
                window.total_tokens = 0
                window.updated_at = datetime.now()

            self._logger.info(f"Cleared context window {window_id}")
            return True

        except Exception as e:
            self._logger.error(f"Error clearing window {window_id}: {str(e)}")
            return False

    async def _manage_window_boundary(self, window: ContextWindow,
                                    config: ContextWindowConfig,
                                    new_message_tokens: int):
        """Manage window boundary when adding new message would exceed limit."""
        try:
            # Calculate how many tokens we need to free up
            tokens_needed = (window.total_tokens + new_message_tokens) - config.max_tokens

            if tokens_needed <= 0:
                return

            # Find optimal boundary
            start_idx, end_idx = self._boundary_manager.find_optimal_boundary(
                window.messages,
                config.max_tokens - new_message_tokens,
                config.strategy
            )

            # Remove messages outside boundary
            if start_idx > 0:
                removed_messages = window.messages[:start_idx]
                window.messages = window.messages[start_idx:]

                # Recalculate total tokens
                window.total_tokens = sum(msg.token_count for msg in window.messages)

                self._logger.debug(f"Removed {len(removed_messages)} messages from window {window.window_id}")

        except Exception as e:
            self._logger.error(f"Error managing window boundary: {e}")

    async def _validate_config(self, config: ContextWindowConfig) -> ValidationResult:
        """Validate context window configuration."""
        try:
            result = ValidationResult(is_valid=True)

            # Validate max tokens
            if config.max_tokens <= 0:
                result.add_error(ValidationError(
                    field_name="max_tokens",
                    error_message="Max tokens must be positive",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

            # Validate overlap tokens
            if config.overlap_tokens < 0:
                result.add_error(ValidationError(
                    field_name="overlap_tokens",
                    error_message="Overlap tokens cannot be negative",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

            # Validate overlap vs max tokens
            if config.overlap_tokens >= config.max_tokens:
                result.add_error(ValidationError(
                    field_name="overlap_tokens",
                    error_message="Overlap tokens must be less than max tokens",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.CONSTRAINT
                ))

            # Validate summarization ratio
            if config.summarization_ratio <= 0 or config.summarization_ratio > 1:
                result.add_error(ValidationError(
                    field_name="summarization_ratio",
                    error_message="Summarization ratio must be between 0 and 1",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

            # Validate compression ratio
            if config.compression_ratio <= 0 or config.compression_ratio > 1:
                result.add_error(ValidationError(
                    field_name="compression_ratio",
                    error_message="Compression ratio must be between 0 and 1",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

            return result

        except Exception as e:
            self._logger.error(f"Error validating config: {e}")
            result = ValidationResult(is_valid=False)
            result.add_error(ValidationError(
                field_name="general",
                error_message=f"Validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.GENERAL
            ))
            return result

    def get_window_count(self) -> int:
        """
        Get count of active windows.

        Returns:
            int: Number of active windows
        """
        with self._global_lock:
            return len(self._windows)

    def get_total_tokens_processed(self) -> int:
        """
        Get total tokens processed across all windows.

        Returns:
            int: Total tokens processed
        """
        return self._total_tokens_processed

    def get_operation_count(self) -> int:
        """
        Get total operation count.

        Returns:
            int: Total operations performed
        """
        return self._operation_count
