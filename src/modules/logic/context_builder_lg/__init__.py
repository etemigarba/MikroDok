"""
MikroDok Context Builder Package
Provides comprehensive context building functionality for LLM input optimization including chunk selection, context window management, and reranking.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IChunkSelector,
        IContextWindow,
        IReranker,
        ChunkSelectionResult,
        ContextWindowResult,
        RerankingResult,
        SelectionCriteria,
        ContextConfig,
        RerankingConfig,
        RelevanceScore,
        ContextBoundary,
        SelectionStrategy,
        RerankingMethod,
        ContextOptimization
    )
except ImportError:
    pass

# Import chunk selector components
try:
    from .chunk_selector_lg.chunk_selector_lg import (
        ChunkSelector,
        RelevanceCalculator,
        TokenAwareSelector,
        QuerySimilarityScorer
    )
except ImportError:
    pass

# Import context window components
try:
    from .context_window_lg.context_window_lg import (
        ContextWindow,
        TokenCounter,
        BoundaryManager,
        ContextOptimizer
    )
except ImportError:
    pass

# Import reranker components
try:
    from .reranker_lg.reranker_lg import (
        Reranker,
        CrossEncoderScorer,
        QueryChunkPairProcessor,
        RelevanceRanker
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IChunkSelector',
    'IContextWindow',
    'IReranker',
    'ChunkSelectionResult',
    'ContextWindowResult',
    'RerankingResult',
    'SelectionCriteria',
    'ContextConfig',
    'RerankingConfig',
    'RelevanceScore',
    'ContextBoundary',
    'SelectionStrategy',
    'RerankingMethod',
    'ContextOptimization',
    
    # Chunk Selection
    'ChunkSelector',
    'RelevanceCalculator',
    'TokenAwareSelector',
    'QuerySimilarityScorer',
    
    # Context Window
    'ContextWindow',
    'TokenCounter',
    'BoundaryManager',
    'ContextOptimizer',
    
    # Reranking
    'Reranker',
    'CrossEncoderScorer',
    'QueryChunkPairProcessor',
    'RelevanceRanker'
]
