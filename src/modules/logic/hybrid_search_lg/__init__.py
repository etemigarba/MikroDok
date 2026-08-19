"""
MikroDok Hybrid Search Package
Provides comprehensive hybrid search functionality combining semantic and keyword search with result fusion.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        ISemanticSearcher,
        IKeywordSearcher,
        IResultFusion,
        SearchResultItem,
        SemanticSearchResult,
        KeywordSearchResult,
        HybridSearchResult,
        SemanticSearchConfig,
        KeywordSearchConfig,
        FusionConfig,
        HybridSearchConfig,
        SearchType,
        FusionStrategy,
        SearchStatus,
        RankingMethod
    )
except ImportError:
    pass

# Import semantic searcher components
try:
    from .semantic_searcher_lg import (
        SemanticSearcher,
        VectorEmbedder,
        SimilarityMatcher,
        SemanticRanker
    )
except ImportError:
    pass

# Import keyword searcher components
try:
    from .keyword_searcher_lg import (
        KeywordSearcher,
        BM25Calculator,
        InvertedIndexBuilder,
        TermProcessor
    )
except ImportError:
    pass

# Import result fusion components
try:
    from .result_fusion_lg import (
        ResultFusion,
        ScoreNormalizer,
        RankFuser,
        DiversityOptimizer
    )
except ImportError:
    pass

__all__ = [
    # Base Interfaces
    'ISemanticSearcher',
    'IKeywordSearcher',
    'IResultFusion',
    'SearchResultItem',
    'SemanticSearchResult',
    'KeywordSearchResult',
    'HybridSearchResult',
    'SemanticSearchConfig',
    'KeywordSearchConfig',
    'FusionConfig',
    'HybridSearchConfig',
    'SearchType',
    'FusionStrategy',
    'SearchStatus',
    'RankingMethod',
    
    # Semantic Search
    'SemanticSearcher',
    'VectorEmbedder',
    'SimilarityMatcher',
    'SemanticRanker',
    
    # Keyword Search
    'KeywordSearcher',
    'BM25Calculator',
    'InvertedIndexBuilder',
    'TermProcessor',
    
    # Result Fusion
    'ResultFusion',
    'ScoreNormalizer',
    'RankFuser',
    'DiversityOptimizer'
]
