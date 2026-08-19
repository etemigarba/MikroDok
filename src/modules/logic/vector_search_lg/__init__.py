"""
MikroDok Vector Search Package
Provides comprehensive vector search functionality including similarity calculation, KNN search, and index optimization.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        ISimilarityCalculator,
        IKNNSearch,
        IIndexOptimizer,
        SimilarityResult,
        KNNSearchResult,
        IndexOptimizationResult,
        SimilarityMetric,
        IndexType,
        SearchConfig,
        OptimizationConfig,
        VectorSearchStatus,
        SearchResultItem,
        IndexStatistics,
        OptimizationStrategy
    )
except ImportError:
    pass

# Import similarity calculator components
try:
    from .similarity_calculator_lg import (
        SimilarityCalculator,
        CosineSimilarityCalculator,
        EuclideanSimilarityCalculator,
        DotProductSimilarityCalculator
    )
except ImportError:
    pass

# Import KNN search components
try:
    from .knn_search_lg import (
        KNNSearch,
        FlatKNNSearch,
        IVFKNNSearch,
        HNSWKNNSearch,
        SearchResultRanker
    )
except ImportError:
    pass

# Import index optimizer components
try:
    from .index_optimizer_lg import (
        IndexOptimizer,
        FlatIndexOptimizer,
        IVFIndexOptimizer,
        HNSWIndexOptimizer,
        AdaptiveIndexOptimizer
    )
except ImportError:
    pass

__all__ = [
    # Base Interfaces
    'ISimilarityCalculator',
    'IKNNSearch',
    'IIndexOptimizer',
    'SimilarityResult',
    'KNNSearchResult',
    'IndexOptimizationResult',
    'SimilarityMetric',
    'IndexType',
    'SearchConfig',
    'OptimizationConfig',
    'VectorSearchStatus',
    'SearchResultItem',
    'IndexStatistics',
    'OptimizationStrategy',
    
    # Similarity Calculator
    'SimilarityCalculator',
    'CosineSimilarityCalculator',
    'EuclideanSimilarityCalculator',
    'DotProductSimilarityCalculator',
    
    # KNN Search
    'KNNSearch',
    'FlatKNNSearch',
    'IVFKNNSearch',
    'HNSWKNNSearch',
    'SearchResultRanker',
    
    # Index Optimizer
    'IndexOptimizer',
    'FlatIndexOptimizer',
    'IVFIndexOptimizer',
    'HNSWIndexOptimizer',
    'AdaptiveIndexOptimizer'
]
