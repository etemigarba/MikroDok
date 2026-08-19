"""
MikroDok Document Chunking Package
Provides comprehensive document chunking functionality including semantic chunking, overlap management, and chunk validation.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        ISemanticChunker,
        IOverlapManager,
        IChunkValidator,
        DocumentChunk,
        ChunkConfig,
        ChunkMetadata,
        OverlapStrategy,
        ChunkValidationResult,
        ChunkingStatus,
        SemanticBreakType
    )
except ImportError:
    pass

# Import semantic chunker components
try:
    from .semantic_chunker_lg.semantic_chunker_lg import (
        SemanticChunker,
        SemanticChunkingConfig,
        TokenCounter,
        BreakPointDetector
    )
except ImportError:
    pass

# Import overlap manager components
try:
    from .overlap_manager_lg.overlap_manager_lg import (
        OverlapManager,
        OverlapConfig,
        OverlapCalculator,
        ContextPreserver
    )
except ImportError:
    pass

# Import chunk validator components
try:
    from .chunk_validator_lg.chunk_validator_lg import (
        ChunkValidator,
        ChunkValidationConfig,
        BoundaryValidator,
        SemanticValidator,
        TokenValidator
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'ISemanticChunker',
    'IOverlapManager',
    'IChunkValidator',
    'DocumentChunk',
    'ChunkConfig',
    'ChunkMetadata',
    'OverlapStrategy',
    'ChunkValidationResult',
    'ChunkingStatus',
    'SemanticBreakType',
    
    # Semantic Chunking
    'SemanticChunker',
    'SemanticChunkingConfig',
    'TokenCounter',
    'BreakPointDetector',
    
    # Overlap Management
    'OverlapManager',
    'OverlapConfig',
    'OverlapCalculator',
    'ContextPreserver',
    
    # Chunk Validation
    'ChunkValidator',
    'ChunkValidationConfig',
    'BoundaryValidator',
    'SemanticValidator',
    'TokenValidator'
]
