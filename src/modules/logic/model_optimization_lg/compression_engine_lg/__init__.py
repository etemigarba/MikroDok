"""
Compression Engine Module
Compresses model artifacts for efficient storage using multiple compression algorithms with integrity verification.
"""

from .compression_engine_lg import CompressionEngine

__all__ = [
    'CompressionEngine'
]
