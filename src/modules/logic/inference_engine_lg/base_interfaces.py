"""
Module: base_interfaces
Description: Base interfaces and data structures for inference engine functionality
Phase: 4
Location: /src/modules/logic/inference_engine_lg/
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union, AsyncIterator, Iterator
import asyncio
from datetime import datetime
from pathlib import Path
import numpy as np


class ModelType(Enum):
    """Supported model types for inference."""
    TRANSFORMER = "transformer"
    CAUSAL_LM = "causal_lm"
    SEQ2SEQ = "seq2seq"
    ENCODER_DECODER = "encoder_decoder"
    CUSTOM = "custom"


class ModelFormat(Enum):
    """Supported model file formats."""
    PYTORCH = "pytorch"
    HUGGINGFACE = "huggingface"
    ONNX = "onnx"
    SAFETENSORS = "safetensors"
    CUSTOM = "custom"


class TokenizerType(Enum):
    """Supported tokenizer types."""
    HUGGINGFACE = "huggingface"
    SENTENCEPIECE = "sentencepiece"
    TIKTOKEN = "tiktoken"
    CUSTOM = "custom"


class GenerationStrategy(Enum):
    """Text generation strategies."""
    GREEDY = "greedy"
    BEAM_SEARCH = "beam_search"
    SAMPLING = "sampling"
    TOP_K = "top_k"
    TOP_P = "top_p"
    NUCLEUS = "nucleus"
    CONTRASTIVE = "contrastive"


class StreamingMode(Enum):
    """Streaming response modes."""
    TOKEN_BY_TOKEN = "token_by_token"
    CHUNK_BASED = "chunk_based"
    SENTENCE_BASED = "sentence_based"
    DISABLED = "disabled"


class InferenceStatus(Enum):
    """Status of inference operations."""
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    GENERATING = "generating"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContextScope(Enum):
    """Scope of context management."""
    SESSION = "session"
    CONVERSATION = "conversation"
    TURN = "turn"
    GLOBAL = "global"


@dataclass
class ModelConfig:
    """Configuration for model loading and management."""
    model_path: Path
    model_type: ModelType = ModelType.TRANSFORMER
    model_format: ModelFormat = ModelFormat.HUGGINGFACE
    device: str = "cpu"  # cpu, cuda, mps
    precision: str = "float32"  # float32, float16, bfloat16, int8
    max_memory_gb: Optional[float] = None
    cache_dir: Optional[Path] = None
    trust_remote_code: bool = False
    use_auth_token: Optional[str] = None
    revision: Optional[str] = None
    torch_dtype: Optional[str] = None
    low_cpu_mem_usage: bool = True
    device_map: Optional[Union[str, Dict[str, Any]]] = None
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenizerConfig:
    """Configuration for tokenizer management."""
    tokenizer_path: Optional[Path] = None
    tokenizer_type: TokenizerType = TokenizerType.HUGGINGFACE
    max_length: int = 2048
    padding: Union[bool, str] = True
    truncation: Union[bool, str] = True
    add_special_tokens: bool = True
    return_tensors: str = "pt"
    return_attention_mask: bool = True
    return_token_type_ids: bool = False
    use_fast: bool = True
    trust_remote_code: bool = False
    custom_tokens: Dict[str, str] = field(default_factory=dict)
    special_tokens: Dict[str, str] = field(default_factory=dict)


@dataclass
class GenerationConfig:
    """Configuration for text generation."""
    max_new_tokens: int = 512
    min_new_tokens: int = 1
    temperature: float = 1.0
    top_k: int = 50
    top_p: float = 1.0
    repetition_penalty: float = 1.0
    length_penalty: float = 1.0
    num_beams: int = 1
    num_return_sequences: int = 1
    early_stopping: bool = False
    do_sample: bool = True
    pad_token_id: Optional[int] = None
    eos_token_id: Optional[int] = None
    bos_token_id: Optional[int] = None
    strategy: GenerationStrategy = GenerationStrategy.SAMPLING
    seed: Optional[int] = None
    use_cache: bool = True
    output_scores: bool = False
    return_dict_in_generate: bool = True
    custom_stopping_criteria: List[str] = field(default_factory=list)


@dataclass
class ContextConfig:
    """Configuration for context management."""
    max_context_length: int = 4096
    context_window_size: int = 2048
    overlap_tokens: int = 128
    scope: ContextScope = ContextScope.CONVERSATION
    preserve_system_prompt: bool = True
    enable_compression: bool = False
    compression_ratio: float = 0.5
    priority_tokens: List[str] = field(default_factory=list)
    context_templates: Dict[str, str] = field(default_factory=dict)


@dataclass
class StreamingConfig:
    """Configuration for streaming responses."""
    mode: StreamingMode = StreamingMode.TOKEN_BY_TOKEN
    chunk_size: int = 1
    buffer_size: int = 10
    flush_interval_ms: int = 50
    enable_partial_responses: bool = True
    include_metadata: bool = False
    timeout_seconds: int = 30
    max_concurrent_streams: int = 5


@dataclass
class ModelInfo:
    """Information about a loaded model."""
    model_name: str
    model_type: ModelType
    model_format: ModelFormat
    vocab_size: int
    max_position_embeddings: int
    hidden_size: int
    num_layers: int
    num_attention_heads: int
    device: str
    precision: str
    memory_usage_mb: float
    parameters_count: int
    is_loaded: bool = False
    load_time_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenizerInfo:
    """Information about a loaded tokenizer."""
    tokenizer_name: str
    tokenizer_type: TokenizerType
    vocab_size: int
    max_length: int
    special_tokens: Dict[str, int]
    is_fast: bool
    supports_batching: bool
    is_loaded: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextState:
    """Current state of conversation context."""
    context_id: str
    scope: ContextScope
    messages: List[Dict[str, Any]]
    total_tokens: int
    available_tokens: int
    system_prompt: Optional[str] = None
    user_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class GenerationResult:
    """Result of text generation operation."""
    generated_text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    generation_time_seconds: float
    tokens_per_second: float
    finish_reason: str
    logprobs: Optional[List[float]] = None
    scores: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StreamingChunk:
    """A chunk of streaming response."""
    chunk_id: str
    text: str
    is_final: bool
    token_count: int
    cumulative_tokens: int
    generation_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class InferenceMetrics:
    """Metrics for inference operations."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float = 0.0
    average_tokens_per_second: float = 0.0
    total_tokens_generated: int = 0
    memory_usage_mb: float = 0.0
    gpu_utilization_percent: float = 0.0
    cache_hit_rate: float = 0.0
    error_rate: float = 0.0
    uptime_seconds: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


# Base Interfaces

class IModelLoader(ABC):
    """Base interface for model loading and management."""

    @abstractmethod
    async def load_model(self, config: ModelConfig) -> bool:
        """
        Load a model with the specified configuration.

        Args:
            config: Model configuration

        Returns:
            True if model loaded successfully
        """
        pass

    @abstractmethod
    async def unload_model(self) -> bool:
        """
        Unload the currently loaded model.

        Returns:
            True if model unloaded successfully
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Optional[ModelInfo]:
        """
        Get information about the currently loaded model.

        Returns:
            ModelInfo if model is loaded, None otherwise
        """
        pass

    @abstractmethod
    def is_model_loaded(self) -> bool:
        """
        Check if a model is currently loaded.

        Returns:
            True if model is loaded
        """
        pass

    @abstractmethod
    async def validate_model(self, model_path: Path) -> bool:
        """
        Validate a model file before loading.

        Args:
            model_path: Path to model file

        Returns:
            True if model is valid
        """
        pass


class ITokenizerManager(ABC):
    """Base interface for tokenizer management."""

    @abstractmethod
    async def load_tokenizer(self, config: TokenizerConfig) -> bool:
        """
        Load a tokenizer with the specified configuration.

        Args:
            config: Tokenizer configuration

        Returns:
            True if tokenizer loaded successfully
        """
        pass

    @abstractmethod
    def encode(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Encode text to tokens.

        Args:
            text: Input text
            **kwargs: Additional encoding parameters

        Returns:
            Dictionary with encoded tokens and metadata
        """
        pass

    @abstractmethod
    def decode(self, token_ids: List[int], **kwargs) -> str:
        """
        Decode tokens to text.

        Args:
            token_ids: List of token IDs
            **kwargs: Additional decoding parameters

        Returns:
            Decoded text string
        """
        pass

    @abstractmethod
    def get_tokenizer_info(self) -> Optional[TokenizerInfo]:
        """
        Get information about the currently loaded tokenizer.

        Returns:
            TokenizerInfo if tokenizer is loaded, None otherwise
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in text.

        Args:
            text: Input text

        Returns:
            Number of tokens
        """
        pass


class IContextManager(ABC):
    """Base interface for context management."""

    @abstractmethod
    async def create_context(self, context_id: str, config: ContextConfig) -> bool:
        """
        Create a new context session.

        Args:
            context_id: Unique context identifier
            config: Context configuration

        Returns:
            True if context created successfully
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_context(self, context_id: str) -> Optional[ContextState]:
        """
        Get current context state.

        Args:
            context_id: Context identifier

        Returns:
            ContextState if context exists, None otherwise
        """
        pass

    @abstractmethod
    async def clear_context(self, context_id: str) -> bool:
        """
        Clear context history.

        Args:
            context_id: Context identifier

        Returns:
            True if context cleared successfully
        """
        pass

    @abstractmethod
    def format_context_for_generation(self, context_id: str) -> str:
        """
        Format context for text generation.

        Args:
            context_id: Context identifier

        Returns:
            Formatted context string
        """
        pass


class IResponseGenerator(ABC):
    """Base interface for response generation."""

    @abstractmethod
    async def generate_response(self, prompt: str, context_id: Optional[str] = None,
                              config: Optional[GenerationConfig] = None) -> GenerationResult:
        """
        Generate a text response for the given prompt.

        Args:
            prompt: Input prompt
            context_id: Optional context identifier
            config: Optional generation configuration

        Returns:
            GenerationResult with generated text and metadata
        """
        pass

    @abstractmethod
    async def generate_response_batch(self, prompts: List[str],
                                    context_ids: Optional[List[str]] = None,
                                    config: Optional[GenerationConfig] = None) -> List[GenerationResult]:
        """
        Generate responses for multiple prompts.

        Args:
            prompts: List of input prompts
            context_ids: Optional list of context identifiers
            config: Optional generation configuration

        Returns:
            List of GenerationResult objects
        """
        pass

    @abstractmethod
    async def cancel_generation(self, request_id: str) -> bool:
        """
        Cancel an ongoing generation request.

        Args:
            request_id: Generation request identifier

        Returns:
            True if cancellation successful
        """
        pass

    @abstractmethod
    def get_generation_status(self, request_id: str) -> InferenceStatus:
        """
        Get status of a generation request.

        Args:
            request_id: Generation request identifier

        Returns:
            Current status of the request
        """
        pass


class IStreamingHandler(ABC):
    """Base interface for streaming response handling."""

    @abstractmethod
    async def start_streaming(self, prompt: str, context_id: Optional[str] = None,
                            config: Optional[StreamingConfig] = None) -> str:
        """
        Start streaming text generation.

        Args:
            prompt: Input prompt
            context_id: Optional context identifier
            config: Optional streaming configuration

        Returns:
            Stream identifier
        """
        pass

    @abstractmethod
    async def get_stream_chunk(self, stream_id: str) -> Optional[StreamingChunk]:
        """
        Get the next chunk from a stream.

        Args:
            stream_id: Stream identifier

        Returns:
            StreamingChunk if available, None if stream ended
        """
        pass

    @abstractmethod
    async def stream_response(self, prompt: str, context_id: Optional[str] = None,
                            config: Optional[StreamingConfig] = None) -> AsyncIterator[StreamingChunk]:
        """
        Stream text generation as an async iterator.

        Args:
            prompt: Input prompt
            context_id: Optional context identifier
            config: Optional streaming configuration

        Yields:
            StreamingChunk objects
        """
        pass

    @abstractmethod
    async def stop_streaming(self, stream_id: str) -> bool:
        """
        Stop a streaming session.

        Args:
            stream_id: Stream identifier

        Returns:
            True if stream stopped successfully
        """
        pass

    @abstractmethod
    def get_active_streams(self) -> List[str]:
        """
        Get list of active stream identifiers.

        Returns:
            List of active stream IDs
        """
        pass


class IGenerationConfig(ABC):
    """Base interface for generation configuration management."""

    @abstractmethod
    def create_config(self, **kwargs) -> GenerationConfig:
        """
        Create a generation configuration.

        Args:
            **kwargs: Configuration parameters

        Returns:
            GenerationConfig object
        """
        pass

    @abstractmethod
    def validate_config(self, config: GenerationConfig) -> List[str]:
        """
        Validate generation configuration.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        pass

    @abstractmethod
    def get_preset_configs(self) -> Dict[str, GenerationConfig]:
        """
        Get predefined configuration presets.

        Returns:
            Dictionary of preset configurations
        """
        pass

    @abstractmethod
    def save_config(self, name: str, config: GenerationConfig) -> bool:
        """
        Save a configuration preset.

        Args:
            name: Preset name
            config: Configuration to save

        Returns:
            True if saved successfully
        """
        pass

    @abstractmethod
    def load_config(self, name: str) -> Optional[GenerationConfig]:
        """
        Load a configuration preset.

        Args:
            name: Preset name

        Returns:
            GenerationConfig if found, None otherwise
        """
        pass
