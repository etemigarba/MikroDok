"""
MikroDok Document Collection UI Package
Provides document collection tree view interface for organizing imported documents in the search interface.
"""

# Import document collection components
try:
    from .document_collection_ui import (
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

__all__ = [
    'DocumentCollectionUI',
    'DocumentCollection',
    'CollectionNode',
    'CollectionStatus',
    'CollectionType',
    'CollectionViewMode',
    'CollectionSortOption',
    'CollectionFilterOption'
]
