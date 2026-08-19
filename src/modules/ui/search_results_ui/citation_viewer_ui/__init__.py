"""
MikroDok Citation Viewer UI Package
Provides citation display and management components for search results with source references.
"""

# Import citation viewer components
try:
    from .citation_viewer_ui import (
        CitationViewerUI,
        Citation,
        CitationFormat
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Citation viewer UI component for MikroDok application"

# Export main components
__all__ = [
    "CitationViewerUI",
    "Citation",
    "CitationFormat"
]
