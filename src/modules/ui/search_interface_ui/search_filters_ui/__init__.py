"""
MikroDok Search Filters UI Package
Advanced search filters component for document type, date range, relevance threshold, and other search criteria.
"""

# Import search filters components
try:
    from .search_filters_ui import (
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

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Advanced search filters UI component for MikroDok application"

# Export main components
__all__ = [
    "SearchFiltersUI",
    "FilterType",
    "FilterValue", 
    "FilterGroup",
    "DateRangeFilter",
    "RelevanceFilter",
    "DocumentTypeFilter",
    "FileSizeFilter",
    "LanguageFilter",
    "TagFilter"
]
