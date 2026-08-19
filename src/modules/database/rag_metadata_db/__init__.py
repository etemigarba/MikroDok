"""
MikroDok RAG Metadata Database Package
Provides database modules for RAG metadata management including chunk mapping and retrieval history.
"""

# Import RAG metadata database components
try:
    from .chunk_mapping_db.chunk_mapping_db import ChunkMappingDB
except ImportError:
    pass

try:
    from .retrieval_history_db.retrieval_history_db import RetrievalHistoryDB
except ImportError:
    pass

__all__ = [
    'ChunkMappingDB',
    'RetrievalHistoryDB'
]
