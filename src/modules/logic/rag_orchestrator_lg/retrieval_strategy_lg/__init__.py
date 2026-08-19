"""
MikroDok RAG Retrieval Strategy Package
Provides retrieval strategy functionality for different retrieval approaches in RAG pipelines.
"""

try:
    from .retrieval_strategy_lg import (
        RetrievalStrategy,
        AdaptiveRetrievalDecider
    )
except ImportError:
    pass

__all__ = [
    'RetrievalStrategy',
    'AdaptiveRetrievalDecider'
]
