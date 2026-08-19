"""
MikroDok Result Fusion Package
Provides weighted fusion algorithms for combining semantic and keyword search results.
"""

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
    'ResultFusion',
    'ScoreNormalizer',
    'RankFuser',
    'DiversityOptimizer'
]
