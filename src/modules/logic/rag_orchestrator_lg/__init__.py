"""
MikroDok RAG Orchestrator Package
Provides comprehensive RAG (Retrieval-Augmented Generation) orchestration functionality including pipeline management, retrieval strategies, and prompt augmentation.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IPipelineManager,
        IRetrievalStrategy,
        IAugmentationEngine,
        RetrievalMode,
        AugmentationStrategy,
        PipelineStage,
        PipelineStatus,
        RetrievalConfig,
        AugmentationConfig,
        PipelineConfig,
        RetrievalResult,
        AugmentationResult,
        PipelineStageResult,
        PipelineResult,
        PipelineMetrics
    )
except ImportError:
    pass

# Import pipeline manager components
try:
    from .pipeline_manager_lg.pipeline_manager_lg import (
        PipelineManager,
        PipelineCache
    )
except ImportError:
    pass

# Import retrieval strategy components
try:
    from .retrieval_strategy_lg.retrieval_strategy_lg import (
        RetrievalStrategy,
        AdaptiveRetrievalDecider
    )
except ImportError:
    pass

# Import augmentation engine components
try:
    from .augmentation_engine_lg.augmentation_engine_lg import (
        AugmentationEngine,
        ContextCompressor,
        TemplateValidator
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IPipelineManager',
    'IRetrievalStrategy',
    'IAugmentationEngine',
    'RetrievalMode',
    'AugmentationStrategy',
    'PipelineStage',
    'PipelineStatus',
    'RetrievalConfig',
    'AugmentationConfig',
    'PipelineConfig',
    'RetrievalResult',
    'AugmentationResult',
    'PipelineStageResult',
    'PipelineResult',
    'PipelineMetrics',
    
    # Pipeline Manager
    'PipelineManager',
    'PipelineCache',
    
    # Retrieval Strategy
    'RetrievalStrategy',
    'AdaptiveRetrievalDecider',
    
    # Augmentation Engine
    'AugmentationEngine',
    'ContextCompressor',
    'TemplateValidator'
]
