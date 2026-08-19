"""
Module: message_processor_lg
Description: Processes conversation messages with validation, formatting, and metadata handling
Phase: 4
Location: /src/modules/logic/conversation_management_lg/message_processor_lg/message_processor_lg.py
"""

# Standard library imports
import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging
import html

# Third-party imports
# None required for this module

# Local imports
from ..base_interfaces import (
    IMessageProcessor,
    ConversationMessage,
    MessageProcessingConfig,
    MessageValidationResult,
    MessageRole,
    MessageType,
    MessagePriority
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)


class MessageProcessingError(Exception):
    """Exception raised when message processing fails."""
    pass


class MessageValidationError(Exception):
    """Exception raised when message validation fails."""
    pass


class MessageValidator:
    """
    Validates conversation messages for content, structure, and safety.
    
    Provides comprehensive validation including content filtering,
    length checks, and format validation with configurable rules.
    """
    
    def __init__(self):
        """Initialize message validator."""
        self._logger = get_log_manager().get_logger(__name__)
        self._validation_engine = ValidationEngine()
        
        # Content filtering patterns
        self._profanity_patterns = [
            # Basic profanity detection patterns (simplified for demo)
            r'\b(spam|test123|placeholder)\b'
        ]
        
        # Suspicious patterns
        self._suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script injection
            r'javascript:',  # JavaScript URLs
            r'data:text/html',  # Data URLs
            r'vbscript:',  # VBScript
        ]
        
        # Code block patterns
        self._code_patterns = [
            r'```[\s\S]*?```',  # Markdown code blocks
            r'`[^`]+`',  # Inline code
            r'<code>[\s\S]*?</code>',  # HTML code tags
        ]
    
    async def validate_message(self, message: ConversationMessage, 
                             config: MessageProcessingConfig) -> MessageValidationResult:
        """
        Validate a conversation message.
        
        Args:
            message: Message to validate
            config: Processing configuration
            
        Returns:
            MessageValidationResult with validation details
        """
        try:
            result = MessageValidationResult(is_valid=True)
            
            # Basic structure validation
            if not await self._validate_structure(message, result):
                result.is_valid = False
            
            # Content validation
            if config.enable_validation:
                if not await self._validate_content(message, config, result):
                    result.is_valid = False
            
            # Content filtering
            if config.enable_content_filtering:
                if not await self._filter_content(message, result):
                    result.is_valid = False
            
            # Token counting
            if config.enable_token_counting:
                result.token_count = await self._count_tokens(message.content)
            
            # Metadata extraction
            if config.enable_metadata_extraction:
                result.extracted_metadata = await self._extract_metadata(message.content)
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error validating message: {e}")
            return MessageValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"]
            )
    
    async def _validate_structure(self, message: ConversationMessage, 
                                result: MessageValidationResult) -> bool:
        """Validate message structure."""
        try:
            is_valid = True
            
            # Check required fields
            if not message.message_id:
                result.errors.append("Message ID is required")
                is_valid = False
            
            if not message.session_id:
                result.errors.append("Session ID is required")
                is_valid = False
            
            if not message.content:
                result.errors.append("Message content is required")
                is_valid = False
            
            # Validate role
            if not isinstance(message.role, MessageRole):
                result.errors.append("Invalid message role")
                is_valid = False
            
            # Validate message type
            if not isinstance(message.message_type, MessageType):
                result.errors.append("Invalid message type")
                is_valid = False
            
            return is_valid
            
        except Exception as e:
            result.errors.append(f"Structure validation error: {str(e)}")
            return False
    
    async def _validate_content(self, message: ConversationMessage, 
                              config: MessageProcessingConfig,
                              result: MessageValidationResult) -> bool:
        """Validate message content."""
        try:
            is_valid = True
            
            # Check content length
            if len(message.content) > config.max_message_length:
                result.errors.append(f"Message exceeds maximum length of {config.max_message_length}")
                is_valid = False
            
            # Check encoding
            try:
                message.content.encode(config.content_encoding)
            except UnicodeEncodeError:
                result.errors.append(f"Message contains invalid characters for {config.content_encoding}")
                is_valid = False
            
            # Function call validation
            if config.enable_function_parsing and message.function_call:
                if not await self._validate_function_call(message.function_call, result):
                    is_valid = False
            
            return is_valid
            
        except Exception as e:
            result.errors.append(f"Content validation error: {str(e)}")
            return False
    
    async def _filter_content(self, message: ConversationMessage, 
                            result: MessageValidationResult) -> bool:
        """Filter message content for safety."""
        try:
            content = message.content.lower()
            
            # Check for profanity
            for pattern in self._profanity_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    result.warnings.append("Message contains potentially inappropriate content")
                    break
            
            # Check for suspicious patterns
            for pattern in self._suspicious_patterns:
                if re.search(pattern, message.content, re.IGNORECASE):
                    result.errors.append("Message contains suspicious content")
                    return False
            
            return True
            
        except Exception as e:
            result.errors.append(f"Content filtering error: {str(e)}")
            return False
    
    async def _validate_function_call(self, function_call: Dict[str, Any], 
                                    result: MessageValidationResult) -> bool:
        """Validate function call structure."""
        try:
            if not isinstance(function_call, dict):
                result.errors.append("Function call must be a dictionary")
                return False
            
            if 'name' not in function_call:
                result.errors.append("Function call must have a 'name' field")
                return False
            
            if 'arguments' in function_call:
                try:
                    json.dumps(function_call['arguments'])
                except (TypeError, ValueError):
                    result.errors.append("Function call arguments must be JSON serializable")
                    return False
            
            return True
            
        except Exception as e:
            result.errors.append(f"Function call validation error: {str(e)}")
            return False
    
    async def _count_tokens(self, content: str) -> int:
        """Count tokens in content (simplified approximation)."""
        try:
            # Simple token counting: words + punctuation
            words = len(re.findall(r'\b\w+\b', content))
            punctuation = len(re.findall(r'[^\w\s]', content))
            return max(1, int((words * 1.3) + (punctuation * 0.5)))
            
        except Exception:
            return max(1, len(content) // 4)  # Fallback
    
    async def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from message content."""
        try:
            metadata = {}
            
            # Detect code blocks
            code_blocks = re.findall(r'```[\s\S]*?```', content)
            if code_blocks:
                metadata['has_code_blocks'] = True
                metadata['code_block_count'] = len(code_blocks)
            
            # Detect URLs
            urls = re.findall(r'https?://[^\s]+', content)
            if urls:
                metadata['has_urls'] = True
                metadata['url_count'] = len(urls)
            
            # Detect mentions (simplified)
            mentions = re.findall(r'@\w+', content)
            if mentions:
                metadata['has_mentions'] = True
                metadata['mention_count'] = len(mentions)
            
            # Content statistics
            metadata['character_count'] = len(content)
            metadata['word_count'] = len(re.findall(r'\b\w+\b', content))
            metadata['line_count'] = len(content.split('\n'))
            
            return metadata
            
        except Exception as e:
            return {'extraction_error': str(e)}


class MetadataExtractor:
    """
    Extracts structured metadata from message content.
    
    Provides intelligent metadata extraction including content analysis,
    entity detection, and semantic information extraction.
    """
    
    def __init__(self):
        """Initialize metadata extractor."""
        self._logger = get_log_manager().get_logger(__name__)
        
        # Pattern definitions
        self._email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self._phone_pattern = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
        self._url_pattern = re.compile(r'https?://[^\s]+')
        self._hashtag_pattern = re.compile(r'#\w+')
        self._mention_pattern = re.compile(r'@\w+')
    
    async def extract_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from content.
        
        Args:
            content: Message content to analyze
            
        Returns:
            Dictionary of extracted metadata
        """
        try:
            metadata = {}
            
            # Basic statistics
            metadata.update(await self._extract_basic_stats(content))
            
            # Entity extraction
            metadata.update(await self._extract_entities(content))
            
            # Content type detection
            metadata.update(await self._detect_content_type(content))
            
            # Language detection (simplified)
            metadata.update(await self._detect_language(content))
            
            # Sentiment analysis (simplified)
            metadata.update(await self._analyze_sentiment(content))
            
            return metadata
            
        except Exception as e:
            self._logger.error(f"Error extracting metadata: {e}")
            return {'extraction_error': str(e)}
    
    async def _extract_basic_stats(self, content: str) -> Dict[str, Any]:
        """Extract basic content statistics."""
        return {
            'character_count': len(content),
            'word_count': len(re.findall(r'\b\w+\b', content)),
            'sentence_count': len(re.findall(r'[.!?]+', content)),
            'paragraph_count': len([p for p in content.split('\n\n') if p.strip()]),
            'line_count': len(content.split('\n'))
        }
    
    async def _extract_entities(self, content: str) -> Dict[str, Any]:
        """Extract entities from content."""
        entities = {}
        
        # Extract emails
        emails = self._email_pattern.findall(content)
        if emails:
            entities['emails'] = emails
            entities['has_emails'] = True
        
        # Extract phone numbers
        phones = self._phone_pattern.findall(content)
        if phones:
            entities['phone_numbers'] = phones
            entities['has_phone_numbers'] = True
        
        # Extract URLs
        urls = self._url_pattern.findall(content)
        if urls:
            entities['urls'] = urls
            entities['has_urls'] = True
        
        # Extract hashtags
        hashtags = self._hashtag_pattern.findall(content)
        if hashtags:
            entities['hashtags'] = hashtags
            entities['has_hashtags'] = True
        
        # Extract mentions
        mentions = self._mention_pattern.findall(content)
        if mentions:
            entities['mentions'] = mentions
            entities['has_mentions'] = True
        
        return entities
    
    async def _detect_content_type(self, content: str) -> Dict[str, Any]:
        """Detect content type and format."""
        content_type = {}
        
        # Code detection
        if re.search(r'```[\s\S]*?```', content):
            content_type['has_code_blocks'] = True
            content_type['content_type'] = 'code'
        
        # Markdown detection
        if re.search(r'[*_#`]', content):
            content_type['has_markdown'] = True
            content_type['format'] = 'markdown'
        
        # HTML detection
        if re.search(r'<[^>]+>', content):
            content_type['has_html'] = True
            content_type['format'] = 'html'
        
        # JSON detection
        try:
            json.loads(content)
            content_type['is_json'] = True
            content_type['format'] = 'json'
        except (json.JSONDecodeError, ValueError):
            pass
        
        return content_type
    
    async def _detect_language(self, content: str) -> Dict[str, Any]:
        """Detect content language (simplified)."""
        # Simplified language detection based on character patterns
        if re.search(r'[а-яё]', content.lower()):
            return {'detected_language': 'russian'}
        elif re.search(r'[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]', content.lower()):
            return {'detected_language': 'european'}
        elif re.search(r'[一-龯]', content):
            return {'detected_language': 'chinese'}
        else:
            return {'detected_language': 'english'}
    
    async def _analyze_sentiment(self, content: str) -> Dict[str, Any]:
        """Analyze content sentiment (simplified)."""
        # Simplified sentiment analysis using keyword matching
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'disappointing', 'frustrating']
        
        content_lower = content.lower()
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        if positive_count > negative_count:
            sentiment = 'positive'
        elif negative_count > positive_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        return {
            'sentiment': sentiment,
            'positive_indicators': positive_count,
            'negative_indicators': negative_count
        }


class ContentFormatter:
    """
    Formats message content for different output types.

    Provides flexible content formatting including plain text, markdown,
    HTML, and custom format support with sanitization and validation.
    """

    def __init__(self):
        """Initialize content formatter."""
        self._logger = get_log_manager().get_logger(__name__)

    async def format_message(self, message: ConversationMessage,
                           format_type: str = "plain") -> str:
        """
        Format message for display or processing.

        Args:
            message: Message to format
            format_type: Format type (plain, markdown, html, json)

        Returns:
            Formatted message string
        """
        try:
            if format_type == "plain":
                return await self._format_plain(message)
            elif format_type == "markdown":
                return await self._format_markdown(message)
            elif format_type == "html":
                return await self._format_html(message)
            elif format_type == "json":
                return await self._format_json(message)
            else:
                # Default to plain text
                return await self._format_plain(message)

        except Exception as e:
            self._logger.error(f"Error formatting message: {e}")
            return message.content  # Fallback to original content

    async def _format_plain(self, message: ConversationMessage) -> str:
        """Format message as plain text."""
        timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        role = message.role.value.title()

        formatted = f"[{timestamp}] {role}: {message.content}"

        # Add function call information if present
        if message.function_call:
            formatted += f"\n  Function Call: {message.function_call['name']}"

        if message.function_response:
            formatted += f"\n  Function Response: {json.dumps(message.function_response)}"

        return formatted

    async def _format_markdown(self, message: ConversationMessage) -> str:
        """Format message as markdown."""
        timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        role = message.role.value.title()

        # Escape markdown special characters in content
        content = self._escape_markdown(message.content)

        formatted = f"**{role}** _{timestamp}_\n\n{content}"

        # Add function call information
        if message.function_call:
            formatted += f"\n\n`Function Call: {message.function_call['name']}`"

        if message.function_response:
            formatted += f"\n\n```json\n{json.dumps(message.function_response, indent=2)}\n```"

        return formatted

    async def _format_html(self, message: ConversationMessage) -> str:
        """Format message as HTML."""
        timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        role = message.role.value.title()

        # Escape HTML special characters
        content = html.escape(message.content)

        # Convert newlines to <br> tags
        content = content.replace('\n', '<br>')

        formatted = f"""
        <div class="message {message.role.value}">
            <div class="message-header">
                <span class="role">{role}</span>
                <span class="timestamp">{timestamp}</span>
            </div>
            <div class="message-content">{content}</div>
        """

        # Add function call information
        if message.function_call:
            formatted += f'<div class="function-call">Function Call: {html.escape(message.function_call["name"])}</div>'

        if message.function_response:
            response_json = html.escape(json.dumps(message.function_response, indent=2))
            formatted += f'<div class="function-response"><pre>{response_json}</pre></div>'

        formatted += "</div>"

        return formatted

    async def _format_json(self, message: ConversationMessage) -> str:
        """Format message as JSON."""
        message_dict = {
            'message_id': message.message_id,
            'session_id': message.session_id,
            'role': message.role.value,
            'content': message.content,
            'message_type': message.message_type.value,
            'timestamp': message.timestamp.isoformat(),
            'token_count': message.token_count,
            'priority': message.priority.value,
            'metadata': message.metadata
        }

        if message.function_call:
            message_dict['function_call'] = message.function_call

        if message.function_response:
            message_dict['function_response'] = message.function_response

        return json.dumps(message_dict, indent=2)

    def _escape_markdown(self, text: str) -> str:
        """Escape markdown special characters."""
        # Escape markdown special characters
        special_chars = ['*', '_', '`', '#', '+', '-', '.', '!', '[', ']', '(', ')']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text


class MessageProcessor(IMessageProcessor):
    """
    Production-ready message processor.

    Processes conversation messages with validation, formatting, and metadata handling
    providing comprehensive message processing capabilities with performance optimization.
    """

    def __init__(self, default_config: Optional[MessageProcessingConfig] = None):
        """Initialize message processor with optional default configuration."""
        self._logger = get_log_manager().get_logger(__name__)
        self._default_config = default_config or MessageProcessingConfig()

        # Initialize components
        self._validator = MessageValidator()
        self._metadata_extractor = MetadataExtractor()
        self._formatter = ContentFormatter()

        # Performance metrics
        self._messages_processed = 0
        self._validation_errors = 0
        self._processing_time_total = 0.0

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
        try:
            start_time = datetime.now()

            # Use provided config or default
            processing_config = config or self._default_config

            # Create temporary message for validation
            temp_message = ConversationMessage(
                message_id=str(uuid.uuid4()),
                session_id=session_id,
                role=role,
                content=content,
                timestamp=datetime.now()
            )

            # Validate message
            result = await self._validator.validate_message(temp_message, processing_config)

            # Extract metadata if enabled
            if processing_config.enable_metadata_extraction and result.is_valid:
                extracted_metadata = await self._metadata_extractor.extract_metadata(content)
                result.extracted_metadata.update(extracted_metadata)

            # Process content if valid
            if result.is_valid:
                result.processed_content = await self._process_content(content, processing_config)

            # Update metrics
            self._messages_processed += 1
            if not result.is_valid:
                self._validation_errors += 1

            processing_time = (datetime.now() - start_time).total_seconds()
            self._processing_time_total += processing_time

            return result

        except Exception as e:
            self._logger.error(f"Error processing message: {str(e)}")
            return MessageValidationResult(
                is_valid=False,
                errors=[f"Processing error: {str(e)}"]
            )

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
        try:
            # Generate unique message ID
            message_id = str(uuid.uuid4())

            # Determine message type based on content and role
            message_type = MessageType.TEXT
            if role == MessageRole.FUNCTION:
                message_type = MessageType.FUNCTION_CALL
            elif role == MessageRole.SYSTEM and 'notification' in content.lower():
                message_type = MessageType.SYSTEM_NOTIFICATION

            # Count tokens
            token_count = await self.count_tokens(content)

            # Create message
            message = ConversationMessage(
                message_id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                message_type=message_type,
                timestamp=datetime.now(),
                token_count=token_count,
                priority=MessagePriority.NORMAL,
                metadata=metadata or {}
            )

            self._logger.debug(f"Created message {message_id} for session {session_id}")
            return message

        except Exception as e:
            self._logger.error(f"Error creating message: {str(e)}")
            raise MessageProcessingError(f"Failed to create message: {str(e)}")

    async def validate_message(self, message: ConversationMessage) -> MessageValidationResult:
        """
        Validate a message.

        Args:
            message: Message to validate

        Returns:
            MessageValidationResult with validation details
        """
        try:
            return await self._validator.validate_message(message, self._default_config)

        except Exception as e:
            self._logger.error(f"Error validating message: {str(e)}")
            return MessageValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"]
            )

    async def extract_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extract metadata from message content.

        Args:
            content: Message content

        Returns:
            Dictionary of extracted metadata
        """
        try:
            return await self._metadata_extractor.extract_metadata(content)

        except Exception as e:
            self._logger.error(f"Error extracting metadata: {str(e)}")
            return {'extraction_error': str(e)}

    async def count_tokens(self, content: str) -> int:
        """
        Count tokens in message content.

        Args:
            content: Message content

        Returns:
            Token count
        """
        try:
            return await self._validator._count_tokens(content)

        except Exception as e:
            self._logger.error(f"Error counting tokens: {str(e)}")
            return max(1, len(content) // 4)  # Fallback

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
        try:
            return await self._formatter.format_message(message, format_type)

        except Exception as e:
            self._logger.error(f"Error formatting message: {str(e)}")
            return message.content  # Fallback

    async def _process_content(self, content: str, config: MessageProcessingConfig) -> str:
        """Process message content based on configuration."""
        try:
            processed_content = content

            # Markdown processing
            if config.enable_markdown_processing:
                processed_content = await self._process_markdown(processed_content)

            # Code block detection
            if config.enable_code_block_detection:
                processed_content = await self._process_code_blocks(processed_content)

            return processed_content

        except Exception as e:
            self._logger.error(f"Error processing content: {e}")
            return content  # Return original on error

    async def _process_markdown(self, content: str) -> str:
        """Process markdown formatting in content."""
        try:
            # Simple markdown processing - convert basic formatting
            # Bold: **text** or __text__
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'__(.*?)__', r'<strong>\1</strong>', content)

            # Italic: *text* or _text_
            content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
            content = re.sub(r'_(.*?)_', r'<em>\1</em>', content)

            # Code: `text`
            content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)

            return content

        except Exception as e:
            self._logger.error(f"Error processing markdown: {e}")
            return content

    async def _process_code_blocks(self, content: str) -> str:
        """Process code blocks in content."""
        try:
            # Detect and mark code blocks
            code_blocks = re.findall(r'```[\s\S]*?```', content)

            for i, block in enumerate(code_blocks):
                # Add code block metadata
                placeholder = f"[CODE_BLOCK_{i}]"
                content = content.replace(block, placeholder, 1)

            return content

        except Exception as e:
            self._logger.error(f"Error processing code blocks: {e}")
            return content

    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            Dictionary of processing statistics
        """
        return {
            'messages_processed': self._messages_processed,
            'validation_errors': self._validation_errors,
            'error_rate': self._validation_errors / max(1, self._messages_processed),
            'average_processing_time': self._processing_time_total / max(1, self._messages_processed),
            'total_processing_time': self._processing_time_total
        }
