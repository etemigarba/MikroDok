"""
Module: tokenizer_manager_lg
Description: Manages tokenizers, encoding/decoding text, and handling special tokens
Phase: 4
Location: /src/modules/logic/inference_engine_lg/tokenizer_manager_lg/tokenizer_manager_lg.py
"""

# Standard library imports
import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import logging

# Third-party imports
try:
    from transformers import (
        AutoTokenizer,
        PreTrainedTokenizer,
        PreTrainedTokenizerFast
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import sentencepiece as spm
    SENTENCEPIECE_AVAILABLE = True
except ImportError:
    SENTENCEPIECE_AVAILABLE = False

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# Local imports
from src.modules.logic.inference_engine_lg.base_interfaces import (
    ITokenizerManager,
    TokenizerConfig,
    TokenizerInfo,
    TokenizerType,
    InferenceMetrics
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)


class TokenizerLoadingError(Exception):
    """Exception raised when tokenizer loading fails."""
    pass


class UnsupportedTokenizerError(Exception):
    """Exception raised when tokenizer type is not supported."""
    pass


class TokenizationError(Exception):
    """Exception raised when tokenization fails."""
    pass


class TokenizerManager(ITokenizerManager):
    """
    Production-ready tokenizer manager for text processing.
    
    Supports multiple tokenizer types (HuggingFace, SentencePiece, TikToken)
    with comprehensive encoding/decoding, special token handling, and error management.
    """
    
    def __init__(self):
        """Initialize tokenizer manager."""
        self._logger = get_log_manager().get_logger(__name__)
        self._tokenizer = None
        self._tokenizer_info: Optional[TokenizerInfo] = None
        self._config: Optional[TokenizerConfig] = None
        self._loading_lock = threading.RLock()
        self._validator = ValidationEngine()
        self._metrics = InferenceMetrics()
        
        # Tokenization cache for performance
        self._encoding_cache: Dict[str, Dict[str, Any]] = {}
        self._decoding_cache: Dict[str, str] = {}
        self._cache_max_size = 1000
        self._enable_caching = True
        
        self._logger.info("Tokenizer manager initialized")
    
    async def load_tokenizer(self, config: TokenizerConfig) -> bool:
        """
        Load a tokenizer with the specified configuration.
        
        Args:
            config: Tokenizer configuration
            
        Returns:
            True if tokenizer loaded successfully
        """
        # Validate configuration
        validation_result = self._validate_tokenizer_config(config)
        if not validation_result.is_valid:
            error_msg = f"Invalid tokenizer configuration: {validation_result.get_error_summary()}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)
        
        with self._loading_lock:
            try:
                self._logger.info(f"Loading tokenizer: {config.tokenizer_type.value}")
                start_time = time.time()
                
                # Load tokenizer based on type
                if config.tokenizer_type == TokenizerType.HUGGINGFACE:
                    tokenizer = await self._load_huggingface_tokenizer(config)
                elif config.tokenizer_type == TokenizerType.SENTENCEPIECE:
                    tokenizer = await self._load_sentencepiece_tokenizer(config)
                elif config.tokenizer_type == TokenizerType.TIKTOKEN:
                    tokenizer = await self._load_tiktoken_tokenizer(config)
                else:
                    raise UnsupportedTokenizerError(f"Unsupported tokenizer type: {config.tokenizer_type}")
                
                # Create tokenizer info
                load_time = time.time() - start_time
                self._tokenizer = tokenizer
                self._config = config
                self._tokenizer_info = await self._create_tokenizer_info(tokenizer, config)
                
                # Clear cache on new tokenizer load
                self._encoding_cache.clear()
                self._decoding_cache.clear()
                
                self._logger.info(f"Tokenizer loaded successfully in {load_time:.2f}s")
                
                # Update metrics
                self._metrics.successful_requests += 1
                
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to load tokenizer: {str(e)}")
                self._metrics.failed_requests += 1
                
                # Clean up on failure
                self._tokenizer = None
                self._tokenizer_info = None
                self._config = None
                
                if isinstance(e, (TokenizerLoadingError, UnsupportedTokenizerError)):
                    raise
                else:
                    raise TokenizerLoadingError(f"Tokenizer loading failed: {str(e)}")
    
    def encode(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Encode text to tokens.
        
        Args:
            text: Input text
            **kwargs: Additional encoding parameters
            
        Returns:
            Dictionary with encoded tokens and metadata
        """
        if not self._tokenizer:
            raise TokenizerLoadingError("No tokenizer loaded")
        
        # Check cache first
        cache_key = f"{text}_{hash(str(sorted(kwargs.items())))}"
        if self._enable_caching and cache_key in self._encoding_cache:
            return self._encoding_cache[cache_key].copy()
        
        try:
            start_time = time.time()
            
            # Prepare encoding arguments
            encoding_kwargs = {
                'max_length': self._config.max_length,
                'padding': self._config.padding,
                'truncation': self._config.truncation,
                'add_special_tokens': self._config.add_special_tokens,
                'return_tensors': self._config.return_tensors,
                'return_attention_mask': self._config.return_attention_mask,
                'return_token_type_ids': self._config.return_token_type_ids
            }
            
            # Override with provided kwargs
            encoding_kwargs.update(kwargs)
            
            # Encode based on tokenizer type
            if self._config.tokenizer_type == TokenizerType.HUGGINGFACE:
                result = self._encode_huggingface(text, encoding_kwargs)
            elif self._config.tokenizer_type == TokenizerType.SENTENCEPIECE:
                result = self._encode_sentencepiece(text, encoding_kwargs)
            elif self._config.tokenizer_type == TokenizerType.TIKTOKEN:
                result = self._encode_tiktoken(text, encoding_kwargs)
            else:
                raise TokenizationError(f"Encoding not supported for {self._config.tokenizer_type}")
            
            # Add metadata
            encoding_time = time.time() - start_time
            result['metadata'] = {
                'encoding_time_ms': encoding_time * 1000,
                'text_length': len(text),
                'tokenizer_type': self._config.tokenizer_type.value
            }
            
            # Cache result
            if self._enable_caching and len(self._encoding_cache) < self._cache_max_size:
                self._encoding_cache[cache_key] = result.copy()
            
            return result
            
        except Exception as e:
            self._logger.error(f"Failed to encode text: {str(e)}")
            raise TokenizationError(f"Text encoding failed: {str(e)}")
    
    def decode(self, token_ids: List[int], **kwargs) -> str:
        """
        Decode tokens to text.
        
        Args:
            token_ids: List of token IDs
            **kwargs: Additional decoding parameters
            
        Returns:
            Decoded text string
        """
        if not self._tokenizer:
            raise TokenizerLoadingError("No tokenizer loaded")
        
        # Check cache first
        cache_key = f"{str(token_ids)}_{hash(str(sorted(kwargs.items())))}"
        if self._enable_caching and cache_key in self._decoding_cache:
            return self._decoding_cache[cache_key]
        
        try:
            start_time = time.time()
            
            # Prepare decoding arguments
            decoding_kwargs = {
                'skip_special_tokens': kwargs.get('skip_special_tokens', True),
                'clean_up_tokenization_spaces': kwargs.get('clean_up_tokenization_spaces', True)
            }
            
            # Decode based on tokenizer type
            if self._config.tokenizer_type == TokenizerType.HUGGINGFACE:
                text = self._decode_huggingface(token_ids, decoding_kwargs)
            elif self._config.tokenizer_type == TokenizerType.SENTENCEPIECE:
                text = self._decode_sentencepiece(token_ids, decoding_kwargs)
            elif self._config.tokenizer_type == TokenizerType.TIKTOKEN:
                text = self._decode_tiktoken(token_ids, decoding_kwargs)
            else:
                raise TokenizationError(f"Decoding not supported for {self._config.tokenizer_type}")
            
            # Cache result
            if self._enable_caching and len(self._decoding_cache) < self._cache_max_size:
                self._decoding_cache[cache_key] = text
            
            decoding_time = time.time() - start_time
            self._logger.debug(f"Decoded {len(token_ids)} tokens in {decoding_time*1000:.1f}ms")
            
            return text
            
        except Exception as e:
            self._logger.error(f"Failed to decode tokens: {str(e)}")
            raise TokenizationError(f"Token decoding failed: {str(e)}")
    
    def get_tokenizer_info(self) -> Optional[TokenizerInfo]:
        """
        Get information about the currently loaded tokenizer.
        
        Returns:
            TokenizerInfo if tokenizer is loaded, None otherwise
        """
        return self._tokenizer_info
    
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in text.
        
        Args:
            text: Input text
            
        Returns:
            Number of tokens
        """
        try:
            if not self._tokenizer:
                raise TokenizerLoadingError("No tokenizer loaded")
            
            # Use efficient token counting without full encoding
            if self._config.tokenizer_type == TokenizerType.HUGGINGFACE:
                # For HuggingFace tokenizers, use encode without special processing
                tokens = self._tokenizer.encode(text, add_special_tokens=False)
                return len(tokens)
            elif self._config.tokenizer_type == TokenizerType.SENTENCEPIECE:
                tokens = self._tokenizer.encode(text)
                return len(tokens)
            elif self._config.tokenizer_type == TokenizerType.TIKTOKEN:
                tokens = self._tokenizer.encode(text)
                return len(tokens)
            else:
                # Fallback: use full encoding
                result = self.encode(text, add_special_tokens=False, return_tensors=None)
                if 'input_ids' in result:
                    return len(result['input_ids'])
                else:
                    return 0
                    
        except Exception as e:
            self._logger.error(f"Failed to count tokens: {str(e)}")
            return 0
    
    def get_tokenizer(self) -> Optional[Any]:
        """
        Get the currently loaded tokenizer instance.
        
        Returns:
            Tokenizer instance if loaded, None otherwise
        """
        return self._tokenizer
    
    def is_tokenizer_loaded(self) -> bool:
        """
        Check if a tokenizer is currently loaded.
        
        Returns:
            True if tokenizer is loaded
        """
        return self._tokenizer is not None
    
    def get_special_tokens(self) -> Dict[str, Union[str, int]]:
        """
        Get special tokens from the loaded tokenizer.
        
        Returns:
            Dictionary of special tokens
        """
        if not self._tokenizer or not self._tokenizer_info:
            return {}
        
        return self._tokenizer_info.special_tokens.copy()
    
    def add_special_tokens(self, special_tokens: Dict[str, str]) -> bool:
        """
        Add special tokens to the tokenizer.
        
        Args:
            special_tokens: Dictionary of special tokens to add
            
        Returns:
            True if tokens added successfully
        """
        try:
            if not self._tokenizer:
                raise TokenizerLoadingError("No tokenizer loaded")
            
            if self._config.tokenizer_type == TokenizerType.HUGGINGFACE:
                # Add special tokens to HuggingFace tokenizer
                num_added = self._tokenizer.add_special_tokens(special_tokens)
                self._logger.info(f"Added {num_added} special tokens")
                
                # Update tokenizer info
                if self._tokenizer_info:
                    self._tokenizer_info.special_tokens.update({
                        token: self._tokenizer.convert_tokens_to_ids(token) 
                        for token in special_tokens.values()
                    })
                    self._tokenizer_info.vocab_size = len(self._tokenizer)
                
                return True
            else:
                self._logger.warning(f"Adding special tokens not supported for {self._config.tokenizer_type}")
                return False
                
        except Exception as e:
            self._logger.error(f"Failed to add special tokens: {str(e)}")
            return False

    async def _load_huggingface_tokenizer(self, config: TokenizerConfig) -> Any:
        """
        Load HuggingFace tokenizer.

        Args:
            config: Tokenizer configuration

        Returns:
            Loaded tokenizer instance
        """
        try:
            if not TRANSFORMERS_AVAILABLE:
                raise ImportError("transformers library not available")

            # Determine tokenizer path
            tokenizer_path = config.tokenizer_path or config.tokenizer_path
            if not tokenizer_path:
                raise ValueError("Tokenizer path is required for HuggingFace tokenizers")

            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                str(tokenizer_path),
                use_fast=config.use_fast,
                trust_remote_code=config.trust_remote_code
            )

            # Add custom tokens if specified
            if config.custom_tokens:
                tokenizer.add_tokens(list(config.custom_tokens.values()))

            # Set special tokens if specified
            if config.special_tokens:
                tokenizer.add_special_tokens(config.special_tokens)

            return tokenizer

        except Exception as e:
            self._logger.error(f"Failed to load HuggingFace tokenizer: {str(e)}")
            raise TokenizerLoadingError(f"HuggingFace tokenizer loading failed: {str(e)}")

    async def _load_sentencepiece_tokenizer(self, config: TokenizerConfig) -> Any:
        """
        Load SentencePiece tokenizer.

        Args:
            config: Tokenizer configuration

        Returns:
            Loaded tokenizer instance
        """
        try:
            if not SENTENCEPIECE_AVAILABLE:
                raise ImportError("sentencepiece library not available")

            if not config.tokenizer_path:
                raise ValueError("Tokenizer path is required for SentencePiece tokenizers")

            # Load SentencePiece model
            tokenizer = spm.SentencePieceProcessor()
            tokenizer.load(str(config.tokenizer_path))

            return tokenizer

        except Exception as e:
            self._logger.error(f"Failed to load SentencePiece tokenizer: {str(e)}")
            raise TokenizerLoadingError(f"SentencePiece tokenizer loading failed: {str(e)}")

    async def _load_tiktoken_tokenizer(self, config: TokenizerConfig) -> Any:
        """
        Load TikToken tokenizer.

        Args:
            config: Tokenizer configuration

        Returns:
            Loaded tokenizer instance
        """
        try:
            if not TIKTOKEN_AVAILABLE:
                raise ImportError("tiktoken library not available")

            # Load TikToken encoding
            if config.tokenizer_path:
                # Load from file
                tokenizer = tiktoken.get_encoding(str(config.tokenizer_path))
            else:
                # Use default encoding
                tokenizer = tiktoken.get_encoding("cl100k_base")

            return tokenizer

        except Exception as e:
            self._logger.error(f"Failed to load TikToken tokenizer: {str(e)}")
            raise TokenizerLoadingError(f"TikToken tokenizer loading failed: {str(e)}")

    def _encode_huggingface(self, text: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Encode text using HuggingFace tokenizer."""
        try:
            result = self._tokenizer(text, **kwargs)

            # Convert to standard format
            output = {}
            if hasattr(result, 'input_ids'):
                output['input_ids'] = result.input_ids
            if hasattr(result, 'attention_mask'):
                output['attention_mask'] = result.attention_mask
            if hasattr(result, 'token_type_ids'):
                output['token_type_ids'] = result.token_type_ids

            # Convert tensors to lists if needed
            if kwargs.get('return_tensors') is None:
                for key, value in output.items():
                    if hasattr(value, 'tolist'):
                        output[key] = value.tolist()
                    elif hasattr(value, 'numpy'):
                        output[key] = value.numpy().tolist()

            return output

        except Exception as e:
            raise TokenizationError(f"HuggingFace encoding failed: {str(e)}")

    def _encode_sentencepiece(self, text: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Encode text using SentencePiece tokenizer."""
        try:
            # SentencePiece encoding
            token_ids = self._tokenizer.encode(text)

            # Create attention mask
            attention_mask = [1] * len(token_ids)

            # Apply padding and truncation
            max_length = kwargs.get('max_length', self._config.max_length)
            if kwargs.get('truncation', True) and len(token_ids) > max_length:
                token_ids = token_ids[:max_length]
                attention_mask = attention_mask[:max_length]

            if kwargs.get('padding', True) and len(token_ids) < max_length:
                pad_length = max_length - len(token_ids)
                token_ids.extend([0] * pad_length)  # Assuming 0 is pad token
                attention_mask.extend([0] * pad_length)

            return {
                'input_ids': token_ids,
                'attention_mask': attention_mask
            }

        except Exception as e:
            raise TokenizationError(f"SentencePiece encoding failed: {str(e)}")

    def _encode_tiktoken(self, text: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Encode text using TikToken tokenizer."""
        try:
            # TikToken encoding
            token_ids = self._tokenizer.encode(text)

            # Create attention mask
            attention_mask = [1] * len(token_ids)

            # Apply truncation
            max_length = kwargs.get('max_length', self._config.max_length)
            if kwargs.get('truncation', True) and len(token_ids) > max_length:
                token_ids = token_ids[:max_length]
                attention_mask = attention_mask[:max_length]

            return {
                'input_ids': token_ids,
                'attention_mask': attention_mask
            }

        except Exception as e:
            raise TokenizationError(f"TikToken encoding failed: {str(e)}")

    def _decode_huggingface(self, token_ids: List[int], kwargs: Dict[str, Any]) -> str:
        """Decode tokens using HuggingFace tokenizer."""
        try:
            return self._tokenizer.decode(token_ids, **kwargs)
        except Exception as e:
            raise TokenizationError(f"HuggingFace decoding failed: {str(e)}")

    def _decode_sentencepiece(self, token_ids: List[int], kwargs: Dict[str, Any]) -> str:
        """Decode tokens using SentencePiece tokenizer."""
        try:
            return self._tokenizer.decode(token_ids)
        except Exception as e:
            raise TokenizationError(f"SentencePiece decoding failed: {str(e)}")

    def _decode_tiktoken(self, token_ids: List[int], kwargs: Dict[str, Any]) -> str:
        """Decode tokens using TikToken tokenizer."""
        try:
            return self._tokenizer.decode(token_ids)
        except Exception as e:
            raise TokenizationError(f"TikToken decoding failed: {str(e)}")

    async def _create_tokenizer_info(self, tokenizer: Any, config: TokenizerConfig) -> TokenizerInfo:
        """
        Create tokenizer information object.

        Args:
            tokenizer: Loaded tokenizer instance
            config: Tokenizer configuration

        Returns:
            TokenizerInfo object
        """
        try:
            # Extract tokenizer information
            tokenizer_name = str(config.tokenizer_path) if config.tokenizer_path else "unknown"
            vocab_size = 0
            special_tokens = {}
            is_fast = False
            supports_batching = True

            if config.tokenizer_type == TokenizerType.HUGGINGFACE:
                tokenizer_name = getattr(tokenizer, 'name_or_path', tokenizer_name)
                vocab_size = len(tokenizer)
                is_fast = getattr(tokenizer, 'is_fast', False)

                # Get special tokens
                special_tokens = {
                    'pad_token': getattr(tokenizer, 'pad_token_id', None),
                    'eos_token': getattr(tokenizer, 'eos_token_id', None),
                    'bos_token': getattr(tokenizer, 'bos_token_id', None),
                    'unk_token': getattr(tokenizer, 'unk_token_id', None),
                    'cls_token': getattr(tokenizer, 'cls_token_id', None),
                    'sep_token': getattr(tokenizer, 'sep_token_id', None),
                    'mask_token': getattr(tokenizer, 'mask_token_id', None)
                }
                # Remove None values
                special_tokens = {k: v for k, v in special_tokens.items() if v is not None}

            elif config.tokenizer_type == TokenizerType.SENTENCEPIECE:
                vocab_size = tokenizer.get_piece_size()
                special_tokens = {
                    'unk_token': tokenizer.unk_id(),
                    'bos_token': tokenizer.bos_id(),
                    'eos_token': tokenizer.eos_id(),
                    'pad_token': tokenizer.pad_id()
                }

            elif config.tokenizer_type == TokenizerType.TIKTOKEN:
                vocab_size = tokenizer.n_vocab
                supports_batching = False  # TikToken doesn't support batching natively

            return TokenizerInfo(
                tokenizer_name=tokenizer_name,
                tokenizer_type=config.tokenizer_type,
                vocab_size=vocab_size,
                max_length=config.max_length,
                special_tokens=special_tokens,
                is_fast=is_fast,
                supports_batching=supports_batching,
                is_loaded=True,
                metadata={
                    'tokenizer_path': str(config.tokenizer_path) if config.tokenizer_path else None,
                    'use_fast': config.use_fast,
                    'trust_remote_code': config.trust_remote_code
                }
            )

        except Exception as e:
            self._logger.error(f"Failed to create tokenizer info: {str(e)}")
            # Return basic info on error
            return TokenizerInfo(
                tokenizer_name=str(config.tokenizer_path) if config.tokenizer_path else "unknown",
                tokenizer_type=config.tokenizer_type,
                vocab_size=0,
                max_length=config.max_length,
                special_tokens={},
                is_fast=False,
                supports_batching=True,
                is_loaded=True
            )

    def _validate_tokenizer_config(self, config: TokenizerConfig) -> ValidationResult:
        """
        Validate tokenizer configuration.

        Args:
            config: Configuration to validate

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate max length
            if config.max_length <= 0:
                result.add_error(ValidationError(
                    field_name="max_length",
                    error_message="Max length must be positive",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.RANGE
                ))

            # Validate tokenizer path for certain types
            if config.tokenizer_type in [TokenizerType.HUGGINGFACE, TokenizerType.SENTENCEPIECE]:
                if not config.tokenizer_path:
                    result.add_error(ValidationError(
                        field_name="tokenizer_path",
                        error_message=f"Tokenizer path is required for {config.tokenizer_type.value}",
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.REQUIRED
                    ))

            # Validate return tensors format
            valid_tensor_formats = ["pt", "tf", "np", None]
            if config.return_tensors not in valid_tensor_formats:
                result.add_error(ValidationError(
                    field_name="return_tensors",
                    error_message=f"Invalid return_tensors format. Valid options: {valid_tensor_formats}",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.CONSTRAINT
                ))

        except Exception as e:
            result.add_error(ValidationError(
                field_name="general",
                error_message=f"Validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.CUSTOM
            ))

        return result

    def clear_cache(self) -> None:
        """Clear encoding and decoding caches."""
        try:
            self._encoding_cache.clear()
            self._decoding_cache.clear()
            self._logger.info("Tokenizer caches cleared")
        except Exception as e:
            self._logger.error(f"Failed to clear caches: {str(e)}")

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            'encoding_cache_size': len(self._encoding_cache),
            'decoding_cache_size': len(self._decoding_cache),
            'max_cache_size': self._cache_max_size,
            'caching_enabled': self._enable_caching
        }

    def set_cache_enabled(self, enabled: bool) -> None:
        """
        Enable or disable caching.

        Args:
            enabled: Whether to enable caching
        """
        self._enable_caching = enabled
        if not enabled:
            self.clear_cache()
        self._logger.info(f"Tokenizer caching {'enabled' if enabled else 'disabled'}")

    def get_metrics(self) -> InferenceMetrics:
        """
        Get tokenizer manager metrics.

        Returns:
            InferenceMetrics with current statistics
        """
        try:
            self._metrics.metadata = {
                'tokenizer_loaded': self.is_tokenizer_loaded(),
                'tokenizer_type': self._config.tokenizer_type.value if self._config else None,
                'vocab_size': self._tokenizer_info.vocab_size if self._tokenizer_info else 0,
                'max_length': self._config.max_length if self._config else 0,
                'cache_stats': self.get_cache_stats()
            }

            return self._metrics

        except Exception as e:
            self._logger.error(f"Failed to get metrics: {str(e)}")
            return InferenceMetrics()

    async def shutdown(self) -> bool:
        """
        Shutdown tokenizer manager and cleanup resources.

        Returns:
            True if shutdown successful
        """
        try:
            # Clear caches
            self.clear_cache()

            # Clear references
            self._tokenizer = None
            self._tokenizer_info = None
            self._config = None

            self._logger.info("Tokenizer manager shutdown completed")
            return True

        except Exception as e:
            self._logger.error(f"Failed to shutdown tokenizer manager: {str(e)}")
            return False
