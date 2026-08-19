"""
OCR Processor Module
Performs optical character recognition on images and scanned documents using Tesseract.
"""

from .ocr_processor_lg import (
    OCRProcessor,
    OCRConfig,
    ImagePreprocessor,
    LanguageDetector,
    ConfidenceAnalyzer
)

__all__ = [
    'OCRProcessor',
    'OCRConfig',
    'ImagePreprocessor',
    'LanguageDetector',
    'ConfidenceAnalyzer'
]
