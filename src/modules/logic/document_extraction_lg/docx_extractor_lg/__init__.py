"""
DOCX Extractor Module
Processes Word documents preserving formatting and structure using python-docx.
"""

from .docx_extractor_lg import (
    DOCXExtractor,
    DOCXExtractionConfig,
    DOCXStructureParser,
    DOCXMetadataExtractor
)

__all__ = [
    'DOCXExtractor',
    'DOCXExtractionConfig',
    'DOCXStructureParser',
    'DOCXMetadataExtractor'
]
