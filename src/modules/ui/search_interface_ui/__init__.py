"""
MikroDok Search Interface UI Package
Provides comprehensive search interface components for the Interactive Search (RAG) functionality.
"""

# Import search interface components
try:
    from .search_bar_ui.search_bar_ui import (
        SearchBarUI,
        SearchMode,
        SearchSuggestion,
        SearchFilter
    )
except ImportError:
    pass

try:
    from .search_filters_ui.search_filters_ui import (
        SearchFiltersUI,
        FilterType,
        FilterValue,
        FilterGroup,
        DateRangeFilter,
        RelevanceFilter,
        DocumentTypeFilter,
        FileSizeFilter,
        LanguageFilter,
        TagFilter
    )
except ImportError:
    pass

try:
    from .search_mode_ui.search_mode_ui import (
        SearchModeUI,
        SearchModeConfig,
        SearchModeMetrics
    )
except ImportError:
    pass

try:
    from .rag_answer_ui.rag_answer_ui import (
        RAGAnswerUI,
        RAGAnswerLayout,
        RAGAnswerView,
        RAGAnswerConfig,
        RAGAnswerState
    )
except ImportError:
    pass

try:
    from .document_collection_ui.document_collection_ui import (
        DocumentCollectionUI,
        DocumentCollection,
        CollectionNode,
        CollectionStatus,
        CollectionType,
        CollectionViewMode,
        CollectionSortOption,
        CollectionFilterOption
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Search interface UI components for MikroDok application"

# Export main components
__all__ = [
    "SearchBarUI",
    "SearchMode",
    "SearchSuggestion",
    "SearchFilter",
    "SearchFiltersUI",
    "FilterType",
    "FilterValue",
    "FilterGroup",
    "DateRangeFilter",
    "RelevanceFilter",
    "DocumentTypeFilter",
    "FileSizeFilter",
    "LanguageFilter",
    "TagFilter",
    "SearchModeUI",
    "SearchModeConfig",
    "SearchModeMetrics",
    "RAGAnswerUI",
    "RAGAnswerLayout",
    "RAGAnswerView",
    "RAGAnswerConfig",
    "RAGAnswerState",
    "DocumentCollectionUI",
    "DocumentCollection",
    "CollectionNode",
    "CollectionStatus",
    "CollectionType",
    "CollectionViewMode",
    "CollectionSortOption",
    "CollectionFilterOption"
]
