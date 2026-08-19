"""
MikroDok Search Bar UI Package
Advanced search input component with auto-complete suggestions and intelligent search capabilities.
"""

# Import search bar components
try:
    from .search_bar_ui import (
        SearchBarUI,
        SearchMode,
        SearchSuggestion,
        SearchFilter
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Advanced search bar UI component for MikroDok application"

# Export main components
__all__ = [
    "SearchBarUI",
    "SearchMode",
    "SearchSuggestion", 
    "SearchFilter"
]
