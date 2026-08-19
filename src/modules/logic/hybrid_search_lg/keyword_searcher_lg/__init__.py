"""
MikroDok Keyword Searcher Package
Provides BM25-based keyword search functionality with inverted indexing.
"""

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

__all__ = [
    'KeywordSearcher',
    'BM25Calculator',
    'InvertedIndexBuilder',
    'TermProcessor'
]
