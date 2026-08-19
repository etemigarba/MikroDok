"""
Module: base_interfaces
Description: Base interfaces and data structures for document metadata extraction and structure analysis
Phase: 3
Location: /src/modules/logic/document_metadata_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field

# Third-party imports
# None required for base interfaces

# Local imports
# None required for base interfaces


class MetadataType(Enum):
    """Types of metadata that can be extracted from documents."""
    AUTHOR = "author"
    TITLE = "title"
    SUBJECT = "subject"
    KEYWORDS = "keywords"
    CREATOR = "creator"
    PRODUCER = "producer"
    CREATION_DATE = "creation_date"
    MODIFICATION_DATE = "modification_date"
    LANGUAGE = "language"
    PAGE_COUNT = "page_count"
    WORD_COUNT = "word_count"
    CHARACTER_COUNT = "character_count"
    CUSTOM = "custom"
    TECHNICAL = "technical"


class StructureType(Enum):
    """Types of structural elements in documents."""
    DOCUMENT = "document"
    SECTION = "section"
    CHAPTER = "chapter"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"
    TOC = "table_of_contents"


class ExtractionStatus(Enum):
    """Status of metadata extraction or structure analysis."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


@dataclass
class DocumentMetadata:
    """Container for document metadata information."""
    # Standard metadata
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[List[str]] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    language: Optional[str] = None
    
    # Document statistics
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None
    
    # Custom metadata
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    
    # Technical metadata
    file_format: Optional[str] = None
    file_size: Optional[int] = None
    encoding: Optional[str] = None
    version: Optional[str] = None
    
    # Extraction metadata
    extraction_timestamp: datetime = field(default_factory=datetime.now)
    extractor_version: str = "1.0.0"
    confidence_score: float = 1.0


@dataclass
class StructureElement:
    """Represents a structural element in a document."""
    element_type: StructureType
    level: int
    title: Optional[str] = None
    content: Optional[str] = None
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    page_number: Optional[int] = None
    parent_id: Optional[str] = None
    element_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    children: List['StructureElement'] = field(default_factory=list)


@dataclass
class DocumentStructure:
    """Container for document structure information."""
    root_element: StructureElement
    elements: List[StructureElement] = field(default_factory=list)
    hierarchy_depth: int = 0
    total_elements: int = 0
    structure_confidence: float = 1.0
    analysis_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MetadataExtractionResult:
    """Result of metadata extraction operation."""
    status: ExtractionStatus
    metadata: DocumentMetadata
    extraction_duration_ms: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    extracted_fields: List[MetadataType] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class StructureAnalysisResult:
    """Result of structure analysis operation."""
    status: ExtractionStatus
    structure: DocumentStructure
    analysis_duration_ms: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    detected_elements: List[StructureType] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)


class IMetadataExtractor(ABC):
    """Abstract base class for document metadata extractors."""
    
    @abstractmethod
    def extract_metadata(self, file_path: Path, content: Optional[str] = None) -> MetadataExtractionResult:
        """
        Extract metadata from a document.
        
        Args:
            file_path: Path to the document file
            content: Optional pre-extracted content
            
        Returns:
            MetadataExtractionResult with extracted metadata
        """
        pass
    
    @abstractmethod
    def extract_specific_metadata(self, file_path: Path, metadata_types: List[MetadataType]) -> MetadataExtractionResult:
        """
        Extract specific types of metadata from a document.
        
        Args:
            file_path: Path to the document file
            metadata_types: List of metadata types to extract
            
        Returns:
            MetadataExtractionResult with requested metadata
        """
        pass
    
    @abstractmethod
    def validate_metadata(self, metadata: DocumentMetadata) -> Tuple[bool, List[str]]:
        """
        Validate extracted metadata for completeness and accuracy.
        
        Args:
            metadata: Metadata to validate
            
        Returns:
            Tuple of (is_valid, validation_errors)
        """
        pass


class IStructureAnalyzer(ABC):
    """Abstract base class for document structure analyzers."""
    
    @abstractmethod
    def analyze_structure(self, file_path: Path, content: Optional[str] = None) -> StructureAnalysisResult:
        """
        Analyze the structure of a document.
        
        Args:
            file_path: Path to the document file
            content: Optional pre-extracted content
            
        Returns:
            StructureAnalysisResult with document structure
        """
        pass
    
    @abstractmethod
    def extract_hierarchy(self, content: str) -> List[StructureElement]:
        """
        Extract hierarchical structure from document content.
        
        Args:
            content: Document content to analyze
            
        Returns:
            List of structure elements in hierarchical order
        """
        pass
    
    @abstractmethod
    def detect_sections(self, content: str) -> List[StructureElement]:
        """
        Detect sections and their boundaries in document content.
        
        Args:
            content: Document content to analyze
            
        Returns:
            List of detected sections
        """
        pass
    
    @abstractmethod
    def analyze_headers(self, content: str) -> List[StructureElement]:
        """
        Analyze headers and their levels in document content.
        
        Args:
            content: Document content to analyze
            
        Returns:
            List of detected headers with their levels
        """
        pass


@dataclass
class MetadataExtractionConfig:
    """Configuration for metadata extraction operations."""
    extract_standard_metadata: bool = True
    extract_custom_metadata: bool = True
    extract_technical_metadata: bool = True
    calculate_statistics: bool = True
    validate_dates: bool = True
    normalize_text: bool = True
    language_detection: bool = True
    confidence_threshold: float = 0.5
    max_custom_fields: int = 100
    timeout_seconds: int = 30


@dataclass
class StructureAnalysisConfig:
    """Configuration for structure analysis operations."""
    analyze_hierarchy: bool = True
    detect_sections: bool = True
    analyze_headers: bool = True
    extract_toc: bool = True
    detect_lists: bool = True
    analyze_tables: bool = True
    detect_figures: bool = True
    min_confidence: float = 0.6
    max_depth: int = 10
    timeout_seconds: int = 60
