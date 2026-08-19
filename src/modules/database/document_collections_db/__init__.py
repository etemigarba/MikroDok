"""
MikroDok Document Collections Database Package
Provides database modules for document collection organization and metadata management.
"""

# Import document collections database components
from .collection_manager_db.collection_manager_db import CollectionManagerDB
from .collection_metadata_db.collection_metadata_db import CollectionMetadataDB

__all__ = [
    'CollectionManagerDB',
    'CollectionMetadataDB'
]
