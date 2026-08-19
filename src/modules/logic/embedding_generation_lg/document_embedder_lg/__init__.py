"""
Document Embedder Module
Converts document chunks into high-dimensional vectors using transformer models (all-MiniLM-L6-v2).
"""

from .document_embedder_lg import (
    DocumentEmbedder,
    EmbeddingGenerator,
    ModelManager,
    VectorProcessor
)

__all__ = [
    'DocumentEmbedder',
    'EmbeddingGenerator',
    'ModelManager',
    'VectorProcessor'
]
