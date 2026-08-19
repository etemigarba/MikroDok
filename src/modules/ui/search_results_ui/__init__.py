"""
MikroDok Search Results UI Package
Provides comprehensive search results display components for the Interactive Search (RAG) functionality.
"""

# Import search results components
try:
    from .result_list_ui.result_list_ui import (
        ResultListUI,
        SearchResult,
        ResultDisplayMode,
        SortOption,
        FilterOption
    )
except ImportError:
    pass

try:
    from .result_card_ui.result_card_ui import (
        ResultCardUI,
        ResultCard,
        CardLayout
    )
except ImportError:
    pass

try:
    from .citation_viewer_ui.citation_viewer_ui import (
        CitationViewerUI,
        Citation,
        CitationFormat
    )
except ImportError:
    pass

try:
    from .search_results_ui import (
        SearchResultsUI,
        SearchResultsConfig,
        SearchResultsState,
        SearchResultsLayout,
        SearchResultsView
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Search results UI components for MikroDok application"

# Export main components
__all__ = [
    "SearchResultsUI",
    "SearchResultsConfig",
    "SearchResultsState",
    "SearchResultsLayout",
    "SearchResultsView",
    "ResultListUI",
    "SearchResult",
    "ResultDisplayMode",
    "SortOption",
    "FilterOption",
    "ResultCardUI",
    "ResultCard",
    "CardLayout",
    "CitationViewerUI",
    "Citation",
    "CitationFormat"
]
