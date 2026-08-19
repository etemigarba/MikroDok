"""
MikroDok Document Extraction Package
Provides comprehensive document extraction functionality for multiple formats including PDF, DOCX, HTML, Markdown, and OCR processing.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IDocumentExtractor,
        ExtractionResult,
        ExtractionMetadata,
        QualityMetrics,
        ExtractionType,
        ExtractionStatus,
        ContentType,
        TableData,
        ImageData,
        DocumentStructure
    )
except ImportError:
    pass

# Import PDF extractor components
try:
    from .pdf_extractor_lg import (
        PDFExtractor,
        PDFExtractionConfig,
        PDFTableExtractor,
        PDFImageExtractor
    )
except ImportError:
    pass

# Import DOCX extractor components
try:
    from .docx_extractor_lg import (
        DOCXExtractor,
        DOCXExtractionConfig,
        DOCXStructureParser,
        DOCXMetadataExtractor
    )
except ImportError:
    pass

# Import HTML extractor components
try:
    from .html_extractor_lg import (
        HTMLExtractor,
        HTMLExtractionConfig,
        HTMLStructureParser,
        HTMLMetadataExtractor
    )
except ImportError:
    pass

# Import Markdown extractor components
try:
    from .markdown_extractor_lg import (
        MarkdownExtractor,
        MarkdownExtractionConfig,
        MarkdownStructureParser,
        FrontmatterExtractor
    )
except ImportError:
    pass

# Import OCR processor components
try:
    from .ocr_processor_lg import (
        OCRProcessor,
        OCRConfig,
        ImagePreprocessor,
        LanguageDetector,
        ConfidenceAnalyzer
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IDocumentExtractor',
    'ExtractionResult',
    'ExtractionMetadata',
    'QualityMetrics',
    'ExtractionType',
    'ExtractionStatus',
    'ContentType',
    'TableData',
    'ImageData',
    'DocumentStructure',
    
    # PDF Extraction
    'PDFExtractor',
    'PDFExtractionConfig',
    'PDFTableExtractor',
    'PDFImageExtractor',
    
    # DOCX Extraction
    'DOCXExtractor',
    'DOCXExtractionConfig',
    'DOCXStructureParser',
    'DOCXMetadataExtractor',
    
    # HTML Extraction
    'HTMLExtractor',
    'HTMLExtractionConfig',
    'HTMLStructureParser',
    'HTMLMetadataExtractor',
    
    # Markdown Extraction
    'MarkdownExtractor',
    'MarkdownExtractionConfig',
    'MarkdownStructureParser',
    'FrontmatterExtractor',
    
    # OCR Processing
    'OCRProcessor',
    'OCRConfig',
    'ImagePreprocessor',
    'LanguageDetector',
    'ConfidenceAnalyzer'
]
