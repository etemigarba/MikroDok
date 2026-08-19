"""
MikroDok Result List UI Package
Provides search results listing interface with pagination, highlighting, and relevance scoring.
"""

# Import result list components
try:
    from .result_list_ui import (
        ResultListUI,
        SearchResult,
        ResultDisplayMode,
        SortOption,
        FilterOption
    )
except ImportError:
    pass

__all__ = [
    'ResultListUI',
    'SearchResult',
    'ResultDisplayMode',
    'SortOption',
    'FilterOption'
]
