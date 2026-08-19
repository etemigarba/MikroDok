"""
MikroDok Similarity Calculator Package
Provides comprehensive similarity calculation functionality for vector search operations.
"""

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

__all__ = [
    'SimilarityCalculator',
    'CosineSimilarityCalculator',
    'EuclideanSimilarityCalculator',
    'DotProductSimilarityCalculator'
]
