"""
MikroDok Metadata Extractor Package
Provides document metadata extraction functionality including author, creation date, and custom metadata.
"""

from .metadata_extractor_lg import (
    MetadataExtractor,
    MetadataExtractionConfig,
    DocumentPropertyExtractor,
    CustomMetadataParser
)

__all__ = [
    'MetadataExtractor',
    'MetadataExtractionConfig',
    'DocumentPropertyExtractor',
    'CustomMetadataParser'
]
