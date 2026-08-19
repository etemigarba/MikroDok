"""
Module: context_manager_lg
Description: Manages conversation context, context windows, and context state during inference operations
Phase: 4
Location: /src/modules/logic/inference_engine_lg/context_manager_lg/context_manager_lg.py
"""

# Standard library imports
import asyncio
import json
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import logging

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.inference_engine_lg.base_interfaces import (
    IContextManager,
    ContextConfig,
    ContextState,
    ContextScope,
    InferenceMetrics
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)


class ContextCompressionError(Exception):
    """Exception raised when context compression fails."""
    pass


class ContextLimitExceededError(Exception):
    """Exception raised when context limit is exceeded."""
    pass


class ContextManager(IContextManager):
    """
    Production-ready context manager for inference operations.
    
    Manages conversation context, context windows, and context state with
    memory optimization, compression, and thread-safe operations.
    """
    
    def __init__(self, default_config: Optional[ContextConfig] = None):
        """Initialize context manager with optional default configuration."""
        self._logger = get_log_manager().get_logger(__name__)
        self._default_config = default_config or ContextConfig()
        self._contexts: Dict[str, ContextState] = {}
        self._context_configs: Dict[str, ContextConfig] = {}
        self._context_locks: Dict[str, threading.RLock] = defaultdict(threading.RLock)
        self._global_lock = threading.RLock()
        self._validator = ValidationEngine()
        self._metrics = InferenceMetrics()
        self._cleanup_interval = 3600  # 1 hour
        self._last_cleanup = time.time()
        
        # Context compression settings
        self._compression_enabled = False
        self._compression_threshold = 0.8  # Compress when 80% full
        
        self._logger.info("Context manager initialized")
    
    async def create_context(self, context_id: str, config: ContextConfig) -> bool:
        """
        Create a new context session.
        
        Args:
            context_id: Unique context identifier
            config: Context configuration
            
        Returns:
            True if context created successfully
        """
        try:
            # Validate inputs
            if not context_id or not context_id.strip():
                raise ValueError("Context ID cannot be empty")
            
            validation_result = self._validate_context_config(config)
            if not validation_result.is_valid:
                error_msg = f"Invalid context configuration: {validation_result.get_error_summary()}"
                self._logger.error(error_msg)
                raise ValueError(error_msg)
            
            with self._global_lock:
                # Check if context already exists
                if context_id in self._contexts:
                    self._logger.warning(f"Context {context_id} already exists, overwriting")
                
                # Create new context state
                context_state = ContextState(
                    context_id=context_id,
                    scope=config.scope,
                    messages=[],
                    total_tokens=0,
                    available_tokens=config.max_context_length,
                    system_prompt=None,
                    user_context={},
                    metadata={
                        'created_by': 'context_manager',
                        'config': config.__dict__
                    }
                )
                
                # Store context and configuration
                self._contexts[context_id] = context_state
                self._context_configs[context_id] = config
                
                # Initialize context lock
                if context_id not in self._context_locks:
                    self._context_locks[context_id] = threading.RLock()
                
                self._logger.info(f"Created context {context_id} with scope {config.scope.value}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to create context {context_id}: {str(e)}")
            return False
    
    async def add_message(self, context_id: str, role: str, content: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a message to the context.
        
        Args:
            context_id: Context identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional message metadata
            
        Returns:
            True if message added successfully
        """
        try:
            # Validate inputs
            if not context_id or context_id not in self._contexts:
                raise ValueError(f"Context {context_id} not found")
            
            if role not in ['user', 'assistant', 'system']:
                raise ValueError(f"Invalid role: {role}")
            
            if not content or not content.strip():
                raise ValueError("Message content cannot be empty")
            
            with self._context_locks[context_id]:
                context = self._contexts[context_id]
                config = self._context_configs[context_id]
                
                # Estimate token count (rough approximation: 1 token ≈ 4 characters)
                estimated_tokens = len(content) // 4
                
                # Check if adding this message would exceed context limit
                if context.total_tokens + estimated_tokens > config.max_context_length:
                    if config.enable_compression:
                        await self._compress_context(context_id)
                    else:
                        await self._truncate_context(context_id, estimated_tokens)
                
                # Create message
                message = {
                    'role': role,
                    'content': content,
                    'timestamp': datetime.now().isoformat(),
                    'tokens': estimated_tokens,
                    'metadata': metadata or {}
                }
                
                # Handle system messages specially
                if role == 'system':
                    if config.preserve_system_prompt:
                        context.system_prompt = content
                    else:
                        context.messages.append(message)
                else:
                    context.messages.append(message)
                
                # Update token counts
                context.total_tokens += estimated_tokens
                context.available_tokens = config.max_context_length - context.total_tokens
                context.updated_at = datetime.now()
                
                self._logger.debug(f"Added {role} message to context {context_id} "
                                 f"({estimated_tokens} tokens, {context.total_tokens} total)")
                
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to add message to context {context_id}: {str(e)}")
            return False
    
    def get_context(self, context_id: str) -> Optional[ContextState]:
        """
        Get current context state.
        
        Args:
            context_id: Context identifier
            
        Returns:
            ContextState if context exists, None otherwise
        """
        try:
            with self._global_lock:
                if context_id not in self._contexts:
                    return None
                
                # Perform cleanup if needed
                self._cleanup_expired_contexts()
                
                # Return a copy to prevent external modification
                context = self._contexts[context_id]
                return ContextState(
                    context_id=context.context_id,
                    scope=context.scope,
                    messages=context.messages.copy(),
                    total_tokens=context.total_tokens,
                    available_tokens=context.available_tokens,
                    system_prompt=context.system_prompt,
                    user_context=context.user_context.copy(),
                    metadata=context.metadata.copy(),
                    created_at=context.created_at,
                    updated_at=context.updated_at
                )
                
        except Exception as e:
            self._logger.error(f"Failed to get context {context_id}: {str(e)}")
            return None
    
    async def clear_context(self, context_id: str) -> bool:
        """
        Clear context history.
        
        Args:
            context_id: Context identifier
            
        Returns:
            True if context cleared successfully
        """
        try:
            with self._context_locks[context_id]:
                if context_id not in self._contexts:
                    self._logger.warning(f"Context {context_id} not found for clearing")
                    return False
                
                context = self._contexts[context_id]
                config = self._context_configs[context_id]
                
                # Clear messages but preserve system prompt if configured
                context.messages.clear()
                context.total_tokens = 0
                context.available_tokens = config.max_context_length
                context.user_context.clear()
                context.updated_at = datetime.now()
                
                # Preserve system prompt if configured
                if config.preserve_system_prompt and context.system_prompt:
                    system_tokens = len(context.system_prompt) // 4
                    context.total_tokens = system_tokens
                    context.available_tokens = config.max_context_length - system_tokens
                
                self._logger.info(f"Cleared context {context_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to clear context {context_id}: {str(e)}")
            return False
    
    def format_context_for_generation(self, context_id: str) -> str:
        """
        Format context for text generation.
        
        Args:
            context_id: Context identifier
            
        Returns:
            Formatted context string
        """
        try:
            with self._context_locks[context_id]:
                if context_id not in self._contexts:
                    self._logger.warning(f"Context {context_id} not found for formatting")
                    return ""
                
                context = self._contexts[context_id]
                config = self._context_configs[context_id]
                formatted_parts = []
                
                # Add system prompt if present
                if context.system_prompt:
                    formatted_parts.append(f"System: {context.system_prompt}")
                
                # Add conversation messages
                for message in context.messages:
                    role = message['role'].capitalize()
                    content = message['content']
                    formatted_parts.append(f"{role}: {content}")
                
                # Use custom template if available
                if 'conversation' in config.context_templates:
                    template = config.context_templates['conversation']
                    return template.format(context='\n'.join(formatted_parts))
                
                return '\n'.join(formatted_parts)
                
        except Exception as e:
            self._logger.error(f"Failed to format context {context_id}: {str(e)}")
            return ""

    async def _compress_context(self, context_id: str) -> bool:
        """
        Compress context by removing older messages while preserving important ones.

        Args:
            context_id: Context identifier

        Returns:
            True if compression successful
        """
        try:
            context = self._contexts[context_id]
            config = self._context_configs[context_id]

            if not config.enable_compression:
                return False

            # Calculate target size after compression
            target_tokens = int(config.max_context_length * config.compression_ratio)

            # Keep system prompt and recent messages
            preserved_messages = []
            current_tokens = 0

            # Add recent messages in reverse order
            for message in reversed(context.messages):
                message_tokens = message.get('tokens', len(message['content']) // 4)
                if current_tokens + message_tokens <= target_tokens:
                    preserved_messages.insert(0, message)
                    current_tokens += message_tokens
                else:
                    break

            # Update context
            context.messages = preserved_messages
            context.total_tokens = current_tokens
            context.available_tokens = config.max_context_length - current_tokens

            # Add system prompt tokens if present
            if context.system_prompt:
                system_tokens = len(context.system_prompt) // 4
                context.total_tokens += system_tokens
                context.available_tokens -= system_tokens

            self._logger.info(f"Compressed context {context_id} to {current_tokens} tokens")
            return True

        except Exception as e:
            self._logger.error(f"Failed to compress context {context_id}: {str(e)}")
            raise ContextCompressionError(f"Context compression failed: {str(e)}")

    async def _truncate_context(self, context_id: str, required_tokens: int) -> bool:
        """
        Truncate context by removing oldest messages to make room.

        Args:
            context_id: Context identifier
            required_tokens: Number of tokens needed

        Returns:
            True if truncation successful
        """
        try:
            context = self._contexts[context_id]
            config = self._context_configs[context_id]

            # Remove oldest messages until we have enough space
            while (context.total_tokens + required_tokens > config.max_context_length
                   and context.messages):
                removed_message = context.messages.pop(0)
                removed_tokens = removed_message.get('tokens', len(removed_message['content']) // 4)
                context.total_tokens -= removed_tokens
                context.available_tokens += removed_tokens

            # Check if we still don't have enough space
            if context.total_tokens + required_tokens > config.max_context_length:
                raise ContextLimitExceededError(
                    f"Cannot fit {required_tokens} tokens in context {context_id}"
                )

            self._logger.info(f"Truncated context {context_id} to {context.total_tokens} tokens")
            return True

        except Exception as e:
            self._logger.error(f"Failed to truncate context {context_id}: {str(e)}")
            return False

    def _validate_context_config(self, config: ContextConfig) -> ValidationResult:
        """
        Validate context configuration.

        Args:
            config: Configuration to validate

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate max context length
            if config.max_context_length <= 0:
                result.add_error(ValidationError(
                    field_name="max_context_length",
                    error_message="Max context length must be positive",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

            # Validate context window size
            if config.context_window_size <= 0:
                result.add_error(ValidationError(
                    field_name="context_window_size",
                    error_message="Context window size must be positive",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

            # Validate window size vs max length
            if config.context_window_size > config.max_context_length:
                result.add_error(ValidationError(
                    field_name="context_window_size",
                    error_message="Context window size cannot exceed max context length",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.CONSTRAINT
                ))

            # Validate compression ratio
            if config.compression_ratio <= 0 or config.compression_ratio > 1:
                result.add_error(ValidationError(
                    field_name="compression_ratio",
                    error_message="Compression ratio must be between 0 and 1",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

        except Exception as e:
            result.add_error(ValidationError(
                field_name="general",
                error_message=f"Validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.CUSTOM
            ))

        return result

    def _cleanup_expired_contexts(self) -> None:
        """Clean up expired contexts based on scope and age."""
        try:
            current_time = time.time()

            # Only run cleanup periodically
            if current_time - self._last_cleanup < self._cleanup_interval:
                return

            expired_contexts = []
            cutoff_time = datetime.now() - timedelta(hours=24)  # 24 hour expiry

            for context_id, context in self._contexts.items():
                # Clean up old contexts based on scope
                if context.scope == ContextScope.TURN and context.updated_at < cutoff_time:
                    expired_contexts.append(context_id)
                elif context.scope == ContextScope.SESSION and context.updated_at < cutoff_time:
                    expired_contexts.append(context_id)

            # Remove expired contexts
            for context_id in expired_contexts:
                del self._contexts[context_id]
                del self._context_configs[context_id]
                if context_id in self._context_locks:
                    del self._context_locks[context_id]

            if expired_contexts:
                self._logger.info(f"Cleaned up {len(expired_contexts)} expired contexts")

            self._last_cleanup = current_time

        except Exception as e:
            self._logger.error(f"Failed to cleanup expired contexts: {str(e)}")

    def get_metrics(self) -> InferenceMetrics:
        """
        Get context manager metrics.

        Returns:
            InferenceMetrics with current statistics
        """
        try:
            with self._global_lock:
                total_contexts = len(self._contexts)
                total_messages = sum(len(ctx.messages) for ctx in self._contexts.values())
                total_tokens = sum(ctx.total_tokens for ctx in self._contexts.values())

                self._metrics.metadata = {
                    'total_contexts': total_contexts,
                    'total_messages': total_messages,
                    'total_tokens': total_tokens,
                    'active_locks': len(self._context_locks)
                }

                return self._metrics

        except Exception as e:
            self._logger.error(f"Failed to get metrics: {str(e)}")
            return InferenceMetrics()

    async def shutdown(self) -> bool:
        """
        Shutdown context manager and cleanup resources.

        Returns:
            True if shutdown successful
        """
        try:
            with self._global_lock:
                # Clear all contexts
                self._contexts.clear()
                self._context_configs.clear()
                self._context_locks.clear()

                self._logger.info("Context manager shutdown completed")
                return True

        except Exception as e:
            self._logger.error(f"Failed to shutdown context manager: {str(e)}")
            return False
