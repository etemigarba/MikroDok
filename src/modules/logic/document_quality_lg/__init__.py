"""
MikroDok Document Quality Package
Provides comprehensive document quality analysis functionality including content analysis, deduplication, and quality scoring.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IContentAnalyzer,
        IDeduplicationEngine,
        IQualityScorer,
        ContentAnalysisResult,
        DeduplicationResult,
        QualityScoreResult,
        QualityMetric,
        QualityCategory,
        DuplicateType,
        SimilarityMethod,
        AnalysisConfig,
        DeduplicationConfig,
        QualityScoringConfig
    )
except ImportError:
    pass

# Import content analyzer components
try:
    from .content_analyzer_lg.content_analyzer_lg import (
        ContentAnalyzer,
        TextCoherenceAnalyzer,
        CompletenessAnalyzer,
        ExtractionAccuracyAnalyzer
    )
except ImportError:
    pass

# Import deduplication engine components
try:
    from .deduplication_engine_lg.deduplication_engine_lg import (
        DeduplicationEngine,
        HashBasedDeduplicator,
        SemanticDeduplicator,
        DuplicateDetector
    )
except ImportError:
    pass

# Import quality scorer components
try:
    from .quality_scorer_lg.quality_scorer_lg import (
        QualityScorer,
        MetricCalculator,
        ScoreAggregator,
        QualityThresholdManager
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IContentAnalyzer',
    'IDeduplicationEngine',
    'IQualityScorer',
    'ContentAnalysisResult',
    'DeduplicationResult',
    'QualityScoreResult',
    'QualityMetric',
    'QualityCategory',
    'DuplicateType',
    'SimilarityMethod',
    'AnalysisConfig',
    'DeduplicationConfig',
    'QualityScoringConfig',
    
    # Content Analysis
    'ContentAnalyzer',
    'TextCoherenceAnalyzer',
    'CompletenessAnalyzer',
    'ExtractionAccuracyAnalyzer',
    
    # Deduplication
    'DeduplicationEngine',
    'HashBasedDeduplicator',
    'SemanticDeduplicator',
    'DuplicateDetector',
    
    # Quality Scoring
    'QualityScorer',
    'MetricCalculator',
    'ScoreAggregator',
    'QualityThresholdManager'
]
