"""
MikroDok Source Panel UI Package
Provides comprehensive source document display and management interface components for RAG answers.
"""

# Import source panel components
try:
    from .source_panel_ui import (
        SourcePanelUI,
        SourceDisplayMode,
        SourceSortOption,
        SourceFilterOption
    )
except ImportError:
    pass

__all__ = [
    'SourcePanelUI',
    'SourceDisplayMode', 
    'SourceSortOption',
    'SourceFilterOption'
]
