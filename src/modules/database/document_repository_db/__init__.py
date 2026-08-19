"""
MikroDok Document Repository Database Package
Provides database modules for document repository management, including DAO operations,
chunk storage, and collection organization.
"""

# Import document repository database components
try:
    from .document_dao_db.document_dao_db import DocumentDAODB
except ImportError:
    pass

try:
    from .document_chunks_db.document_chunks_db import DocumentChunksDB
except ImportError:
    pass

try:
    from .document_collection_db.document_collection_db import DocumentCollectionDB
except ImportError:
    pass

__all__ = [
    'DocumentDAODB',
    'DocumentChunksDB',
    'DocumentCollectionDB'
]
