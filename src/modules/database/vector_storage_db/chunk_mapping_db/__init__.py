"""
MikroDok Chunk Mapping Database Package
Provides database functionality for maintaining relationships between document chunks and their embeddings.
"""

from .chunk_mapping_db import VectorChunkMappingDB

__all__ = [
    'VectorChunkMappingDB'
]
