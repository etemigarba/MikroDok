"""
HTML Extractor Module
Parses HTML content while maintaining semantic structure using BeautifulSoup.
"""

from .html_extractor_lg import (
    HTMLExtractor,
    HTMLExtractionConfig,
    HTMLStructureParser,
    HTMLMetadataExtractor
)

__all__ = [
    'HTMLExtractor',
    'HTMLExtractionConfig',
    'HTMLStructureParser',
    'HTMLMetadataExtractor'
]
