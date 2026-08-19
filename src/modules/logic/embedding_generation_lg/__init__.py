"""
MikroDok Embedding Generation Package
Provides comprehensive embedding generation functionality for document vectorization and similarity search.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IDocumentEmbedder,
        IBatchProcessor,
        IEmbeddingCache,
        EmbeddingResult,
        EmbeddingMetadata,
        BatchProcessingResult,
        CacheResult,
        EmbeddingConfig,
        BatchConfig,
        CacheConfig,
        EmbeddingStatus,
        BatchStatus,
        CacheStatus,
        EmbeddingModel,
        VectorDimensions
    )
except ImportError:
    pass

# Import document embedder components
try:
    from .document_embedder_lg import (
        DocumentEmbedder,
        EmbeddingGenerator,
        ModelManager,
        VectorProcessor
    )
except ImportError:
    pass

# Import batch processor components
try:
    from .batch_processor_lg import (
        BatchProcessor,
        EmbeddingBatchManager,
        BatchQueue,
        BatchOptimizer
    )
except ImportError:
    pass

# Import embedding cache components
try:
    from .embedding_cache_lg import (
        EmbeddingCache,
        LRUEmbeddingCache,
        CacheManager,
        CacheOptimizer
    )
except ImportError:
    pass

__all__ = [
    # Base Interfaces
    'IDocumentEmbedder',
    'IBatchProcessor', 
    'IEmbeddingCache',
    'EmbeddingResult',
    'EmbeddingMetadata',
    'BatchProcessingResult',
    'CacheResult',
    'EmbeddingConfig',
    'BatchConfig',
    'CacheConfig',
    'EmbeddingStatus',
    'BatchStatus',
    'CacheStatus',
    'EmbeddingModel',
    'VectorDimensions',
    
    # Document Embedder
    'DocumentEmbedder',
    'EmbeddingGenerator',
    'ModelManager',
    'VectorProcessor',
    
    # Batch Processor
    'BatchProcessor',
    'EmbeddingBatchManager',
    'BatchQueue',
    'BatchOptimizer',
    
    # Embedding Cache
    'EmbeddingCache',
    'LRUEmbeddingCache',
    'CacheManager',
    'CacheOptimizer'
]
