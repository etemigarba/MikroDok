"""
MikroDok Search Index Database Package
Provides database modules for search indexing including inverted index and document frequency management.
"""

# Import search index database components
try:
    from .inverted_index_db.inverted_index_db import InvertedIndexDB
except ImportError:
    pass

try:
    from .document_frequency_db.document_frequency_db import DocumentFrequencyDB
except ImportError:
    pass

__all__ = [
    'InvertedIndexDB',
    'DocumentFrequencyDB'
]
