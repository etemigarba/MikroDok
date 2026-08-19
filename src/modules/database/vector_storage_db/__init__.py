"""
MikroDok Vector Storage Database Package
Provides database modules for vector storage, embedding management, and collection operations.
"""

# Import vector storage database components
try:
    from .chromadb_adapter_db.chromadb_adapter_db import ChromaDBAdapterDB
except ImportError:
    pass

try:
    from .embedding_repository_db.embedding_repository_db import EmbeddingRepositoryDB
except ImportError:
    pass

try:
    from .collection_manager_db.collection_manager_db import CollectionManagerDB
except ImportError:
    pass

try:
    from .vector_index_db.vector_index_db import VectorIndexDB
except ImportError:
    pass

try:
    from .chunk_mapping_db.chunk_mapping_db import VectorChunkMappingDB
except ImportError:
    pass

__all__ = [
    'ChromaDBAdapterDB',
    'EmbeddingRepositoryDB',
    'CollectionManagerDB',
    'VectorIndexDB',
    'VectorChunkMappingDB'
]
