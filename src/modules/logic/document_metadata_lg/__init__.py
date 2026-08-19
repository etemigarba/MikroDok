"""
MikroDok Document Metadata Package
Provides comprehensive document metadata extraction and structure analysis functionality.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IMetadataExtractor,
        IStructureAnalyzer,
        DocumentMetadata,
        DocumentStructure,
        StructureElement,
        MetadataExtractionResult,
        StructureAnalysisResult,
        MetadataType,
        StructureType,
        ExtractionStatus
    )
except ImportError:
    pass

# Import metadata extractor components
try:
    from .metadata_extractor_lg import (
        MetadataExtractor,
        MetadataExtractionConfig,
        DocumentPropertyExtractor,
        CustomMetadataParser
    )
except ImportError:
    pass

# Import structure analyzer components
try:
    from .structure_analyzer_lg import (
        StructureAnalyzer,
        StructureAnalysisConfig,
        HierarchyParser,
        SectionDetector,
        HeaderAnalyzer
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IMetadataExtractor',
    'IStructureAnalyzer',
    'DocumentMetadata',
    'DocumentStructure',
    'StructureElement',
    'MetadataExtractionResult',
    'StructureAnalysisResult',
    'MetadataType',
    'StructureType',
    'ExtractionStatus',
    
    # Metadata Extraction
    'MetadataExtractor',
    'MetadataExtractionConfig',
    'DocumentPropertyExtractor',
    'CustomMetadataParser',
    
    # Structure Analysis
    'StructureAnalyzer',
    'StructureAnalysisConfig',
    'HierarchyParser',
    'SectionDetector',
    'HeaderAnalyzer'
]
