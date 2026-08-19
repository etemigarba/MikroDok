"""
PDF Extractor Module
Extracts text, tables, and metadata from PDF documents using PDFPlumber integration.
"""

from .pdf_extractor_lg import (
    PDFExtractor,
    PDFExtractionConfig,
    PDFTableExtractor,
    PDFImageExtractor
)

__all__ = [
    'PDFExtractor',
    'PDFExtractionConfig',
    'PDFTableExtractor',
    'PDFImageExtractor'
]
