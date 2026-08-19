"""
MikroDok Inference Engine Package
Provides comprehensive inference functionality for language models including context management,
response generation, streaming, model loading, tokenization, and configuration management.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        # Interfaces
        IModelLoader,
        ITokenizerManager,
        IContextManager,
        IResponseGenerator,
        IStreamingHandler,
        IGenerationConfig,
        
        # Enums
        ModelType,
        ModelFormat,
        TokenizerType,
        GenerationStrategy,
        StreamingMode,
        InferenceStatus,
        ContextScope,
        
        # Configuration Classes
        ModelConfig,
        TokenizerConfig,
        GenerationConfig,
        ContextConfig,
        StreamingConfig,
        
        # Data Classes
        ModelInfo,
        TokenizerInfo,
        ContextState,
        GenerationResult,
        StreamingChunk,
        InferenceMetrics
    )
except ImportError:
    pass

# Import context manager components
try:
    from .context_manager_lg.context_manager_lg import (
        ContextManager,
        ContextCompressionError,
        ContextLimitExceededError
    )
except ImportError:
    pass

# Import response generator components
try:
    from .response_generator_lg.response_generator_lg import (
        ResponseGenerator,
        GenerationError,
        ModelNotLoadedError,
        CustomStoppingCriteria
    )
except ImportError:
    pass

# Import streaming handler components
try:
    from .streaming_handler_lg.streaming_handler_lg import (
        StreamingHandler,
        StreamingError,
        StreamNotFoundError,
        StreamingSession
    )
except ImportError:
    pass

# Import model loader components
try:
    from .model_loader_lg.model_loader_lg import (
        ModelLoader,
        ModelLoadingError,
        UnsupportedModelFormatError,
        InsufficientMemoryError
    )
except ImportError:
    pass

# Import tokenizer manager components
try:
    from .tokenizer_manager_lg.tokenizer_manager_lg import (
        TokenizerManager,
        TokenizerLoadingError,
        UnsupportedTokenizerError,
        TokenizationError
    )
except ImportError:
    pass

# Import generation config components
try:
    from .generation_config_lg.generation_config_lg import (
        GenerationConfigManager,
        ConfigurationError
    )
except ImportError:
    pass

__all__ = [
    # Base Interfaces
    'IModelLoader',
    'ITokenizerManager',
    'IContextManager',
    'IResponseGenerator',
    'IStreamingHandler',
    'IGenerationConfig',
    
    # Enums
    'ModelType',
    'ModelFormat',
    'TokenizerType',
    'GenerationStrategy',
    'StreamingMode',
    'InferenceStatus',
    'ContextScope',
    
    # Configuration Classes
    'ModelConfig',
    'TokenizerConfig',
    'GenerationConfig',
    'ContextConfig',
    'StreamingConfig',
    
    # Data Classes
    'ModelInfo',
    'TokenizerInfo',
    'ContextState',
    'GenerationResult',
    'StreamingChunk',
    'InferenceMetrics',
    
    # Context Manager
    'ContextManager',
    'ContextCompressionError',
    'ContextLimitExceededError',
    
    # Response Generator
    'ResponseGenerator',
    'GenerationError',
    'ModelNotLoadedError',
    'CustomStoppingCriteria',
    
    # Streaming Handler
    'StreamingHandler',
    'StreamingError',
    'StreamNotFoundError',
    'StreamingSession',
    
    # Model Loader
    'ModelLoader',
    'ModelLoadingError',
    'UnsupportedModelFormatError',
    'InsufficientMemoryError',
    
    # Tokenizer Manager
    'TokenizerManager',
    'TokenizerLoadingError',
    'UnsupportedTokenizerError',
    'TokenizationError',
    
    # Generation Config
    'GenerationConfigManager',
    'ConfigurationError'
]
