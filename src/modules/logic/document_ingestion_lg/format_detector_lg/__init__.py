"""
Format Detector Module
Identifies document format through file extension and magic number verification, routes to appropriate processor.
"""

from .format_detector_lg import (
    FormatDetector,
    IFormatDetector,
    DocumentFormat,
    ProcessorType,
    FormatDetectionResult
)

__all__ = [
    'FormatDetector',
    'IFormatDetector',
    'DocumentFormat',
    'ProcessorType',
    'FormatDetectionResult'
]
