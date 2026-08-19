"""
Module: base_interfaces
Description: Base interfaces and common data structures for document extraction modules
Phase: 3
Location: /src/modules/logic/document_extraction_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.document_ingestion_lg.format_detector_lg import DocumentFormat


class ExtractionType(Enum):
    """Types of content extraction."""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    METADATA = "metadata"
    STRUCTURE = "structure"
    ANNOTATION = "annotation"
    FORM_FIELD = "form_field"
    HYPERLINK = "hyperlink"


class ExtractionStatus(Enum):
    """Status of extraction operation."""
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CORRUPTED = "CORRUPTED"
    UNSUPPORTED = "UNSUPPORTED"


class ContentType(Enum):
    """Types of extracted content."""
    PLAIN_TEXT = "plain_text"
    FORMATTED_TEXT = "formatted_text"
    STRUCTURED_DATA = "structured_data"
    BINARY_DATA = "binary_data"
    MARKUP = "markup"


@dataclass
class TableData:
    """Structured table data from document extraction."""
    headers: List[str]
    rows: List[List[str]]
    caption: Optional[str] = None
    page_number: Optional[int] = None
    bounding_box: Optional[Dict[str, float]] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageData:
    """Image data from document extraction."""
    image_id: str
    image_data: bytes
    format: str  # PNG, JPEG, etc.
    width: int
    height: int
    page_number: Optional[int] = None
    bounding_box: Optional[Dict[str, float]] = None
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentStructure:
    """Document structure information."""
    title: Optional[str] = None
    headings: List[Dict[str, Any]] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None
    language: Optional[str] = None
    reading_order: List[str] = field(default_factory=list)


@dataclass
class QualityMetrics:
    """Quality metrics for extracted content."""
    overall_confidence: float  # 0.0 to 1.0
    text_confidence: float = 0.0
    structure_confidence: float = 0.0
    table_confidence: float = 0.0
    image_confidence: float = 0.0
    completeness_score: float = 0.0  # Percentage of content successfully extracted
    readability_score: float = 0.0
    corruption_indicators: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


@dataclass
class ExtractionMetadata:
    """Metadata about the extraction process."""
    document_format: DocumentFormat
    file_size: int
    extraction_timestamp: datetime
    extractor_version: str
    processing_duration_ms: float
    pages_processed: int = 0
    total_pages: int = 0
    extraction_config: Dict[str, Any] = field(default_factory=dict)
    document_properties: Dict[str, Any] = field(default_factory=dict)
    technical_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Complete result of document extraction."""
    status: ExtractionStatus
    content: str  # Main text content
    metadata: ExtractionMetadata
    quality_metrics: QualityMetrics
    document_structure: Optional[DocumentStructure] = None
    tables: List[TableData] = field(default_factory=list)
    images: List[ImageData] = field(default_factory=list)
    hyperlinks: List[Dict[str, str]] = field(default_factory=list)
    annotations: List[Dict[str, Any]] = field(default_factory=list)
    form_fields: List[Dict[str, Any]] = field(default_factory=list)
    validation_errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def is_successful(self) -> bool:
        """Check if extraction was successful."""
        return self.status in [ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL_SUCCESS]
    
    @property
    def has_content(self) -> bool:
        """Check if extraction produced any content."""
        return bool(self.content.strip() or self.tables or self.images)
    
    def get_content_summary(self) -> Dict[str, int]:
        """Get summary of extracted content."""
        return {
            "text_length": len(self.content),
            "table_count": len(self.tables),
            "image_count": len(self.images),
            "hyperlink_count": len(self.hyperlinks),
            "annotation_count": len(self.annotations),
            "form_field_count": len(self.form_fields)
        }


class IDocumentExtractor(ABC):
    """Base interface for document extractors."""
    
    @abstractmethod
    def extract(self, file_path: Union[str, Path], config: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """
        Extract content from document.
        
        Args:
            file_path: Path to the document file
            config: Optional extraction configuration
            
        Returns:
            ExtractionResult with extracted content and metadata
        """
        pass
    
    @abstractmethod
    def is_supported_format(self, file_path: Union[str, Path]) -> bool:
        """
        Check if file format is supported by this extractor.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            True if format is supported, False otherwise
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[DocumentFormat]:
        """
        Get list of supported document formats.
        
        Returns:
            List of supported DocumentFormat enums
        """
        pass
    
    @abstractmethod
    def validate_file(self, file_path: Union[str, Path]) -> List[ValidationError]:
        """
        Validate file before extraction.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            List of validation errors (empty if valid)
        """
        pass
    
    @abstractmethod
    def get_extraction_config_schema(self) -> Dict[str, Any]:
        """
        Get schema for extraction configuration.
        
        Returns:
            JSON schema for configuration validation
        """
        pass
    
    @abstractmethod
    def estimate_processing_time(self, file_path: Union[str, Path]) -> float:
        """
        Estimate processing time for document.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Estimated processing time in seconds
        """
        pass
