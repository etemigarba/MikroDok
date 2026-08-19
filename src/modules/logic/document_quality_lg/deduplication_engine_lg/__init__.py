"""
Deduplication Engine Module
Provides duplicate content detection using hash-based and semantic similarity methods.
"""

from .deduplication_engine_lg import (
    DeduplicationEngine,
    HashBasedDeduplicator,
    SemanticDeduplicator,
    DuplicateDetector
)

__all__ = [
    'DeduplicationEngine',
    'HashBasedDeduplicator',
    'SemanticDeduplicator',
    'DuplicateDetector'
]
