"""
Module: base_interfaces
Description: Base interfaces and common data structures for document chunking modules
Phase: 3
Location: /src/modules/logic/document_chunking_lg/base_interfaces.py
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
from src.modules.logic.document_extraction_lg.base_interfaces import DocumentStructure


class ChunkingStatus(Enum):
    """Status of chunking operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SemanticBreakType(Enum):
    """Types of semantic break points."""
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"
    SECTION_END = "section_end"
    CHAPTER_END = "chapter_end"
    HARD_BREAK = "hard_break"
    TOKEN_LIMIT = "token_limit"


class OverlapStrategy(Enum):
    """Strategies for managing chunk overlap."""
    FIXED_SIZE = "fixed_size"
    PERCENTAGE = "percentage"
    SENTENCE_BOUNDARY = "sentence_boundary"
    SEMANTIC_BOUNDARY = "semantic_boundary"
    ADAPTIVE = "adaptive"


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""
    chunk_index: int
    start_char: int
    end_char: int
    token_count: int
    sentence_count: int
    paragraph_count: int
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    break_type: Optional[SemanticBreakType] = None
    overlap_start: Optional[int] = None
    overlap_end: Optional[int] = None
    quality_score: Optional[float] = None
    language: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class DocumentChunk:
    """Represents a processed document chunk."""
    chunk_id: str
    document_id: str
    content: str
    metadata: ChunkMetadata
    chunk_hash: Optional[str] = None
    embedding_vector: Optional[List[float]] = None
    
    @property
    def is_valid(self) -> bool:
        """Check if chunk is valid."""
        return (
            bool(self.content.strip()) and
            self.metadata.token_count > 0 and
            self.metadata.start_char >= 0 and
            self.metadata.end_char > self.metadata.start_char
        )
    
    @property
    def length(self) -> int:
        """Get chunk content length."""
        return len(self.content)


@dataclass
class ChunkConfig:
    """Configuration for document chunking."""
    max_chunk_size: int = 1024  # Maximum tokens per chunk
    min_chunk_size: int = 256   # Minimum tokens per chunk
    overlap_size: int = 128     # Overlap size in tokens
    overlap_strategy: OverlapStrategy = OverlapStrategy.SENTENCE_BOUNDARY
    preserve_sentences: bool = True
    preserve_paragraphs: bool = True
    respect_section_boundaries: bool = True
    target_chunk_size: int = 512
    quality_threshold: float = 0.7
    language: Optional[str] = None
    custom_separators: List[str] = field(default_factory=list)


@dataclass
class ChunkValidationResult:
    """Result of chunk validation."""
    is_valid: bool
    chunk_id: str
    validation_errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality_score: Optional[float] = None
    recommendations: List[str] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.validation_errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0


class ISemanticChunker(ABC):
    """Base interface for semantic document chunkers."""
    
    @abstractmethod
    def chunk_document(self, content: str, config: ChunkConfig, 
                      document_structure: Optional[DocumentStructure] = None) -> List[DocumentChunk]:
        """
        Split document content into semantic chunks.
        
        Args:
            content: Document text content
            config: Chunking configuration
            document_structure: Optional document structure information
            
        Returns:
            List of document chunks with metadata
        """
        pass
    
    @abstractmethod
    def estimate_chunk_count(self, content: str, config: ChunkConfig) -> int:
        """
        Estimate number of chunks that will be created.
        
        Args:
            content: Document text content
            config: Chunking configuration
            
        Returns:
            Estimated number of chunks
        """
        pass
    
    @abstractmethod
    def find_break_points(self, content: str, config: ChunkConfig) -> List[Tuple[int, SemanticBreakType]]:
        """
        Find optimal break points in content.
        
        Args:
            content: Document text content
            config: Chunking configuration
            
        Returns:
            List of (position, break_type) tuples
        """
        pass


class IOverlapManager(ABC):
    """Base interface for chunk overlap management."""
    
    @abstractmethod
    def calculate_overlap(self, chunks: List[DocumentChunk], config: ChunkConfig) -> List[DocumentChunk]:
        """
        Calculate and apply overlap between chunks.
        
        Args:
            chunks: List of document chunks
            config: Chunking configuration
            
        Returns:
            List of chunks with overlap applied
        """
        pass
    
    @abstractmethod
    def get_overlap_content(self, chunk1: DocumentChunk, chunk2: DocumentChunk, 
                           strategy: OverlapStrategy) -> str:
        """
        Get overlap content between two chunks.
        
        Args:
            chunk1: First chunk
            chunk2: Second chunk
            strategy: Overlap strategy to use
            
        Returns:
            Overlap content string
        """
        pass
    
    @abstractmethod
    def validate_overlap(self, chunks: List[DocumentChunk]) -> List[ValidationError]:
        """
        Validate overlap consistency across chunks.
        
        Args:
            chunks: List of document chunks
            
        Returns:
            List of validation errors
        """
        pass


class IChunkValidator(ABC):
    """Base interface for chunk validation."""
    
    @abstractmethod
    def validate_chunk(self, chunk: DocumentChunk, config: ChunkConfig) -> ChunkValidationResult:
        """
        Validate a single document chunk.
        
        Args:
            chunk: Document chunk to validate
            config: Chunking configuration
            
        Returns:
            Validation result with errors and recommendations
        """
        pass
    
    @abstractmethod
    def validate_chunks(self, chunks: List[DocumentChunk], config: ChunkConfig) -> List[ChunkValidationResult]:
        """
        Validate a list of document chunks.
        
        Args:
            chunks: List of document chunks
            config: Chunking configuration
            
        Returns:
            List of validation results
        """
        pass
    
    @abstractmethod
    def check_semantic_completeness(self, chunk: DocumentChunk) -> bool:
        """
        Check if chunk is semantically complete.
        
        Args:
            chunk: Document chunk to check
            
        Returns:
            True if chunk is semantically complete
        """
        pass
    
    @abstractmethod
    def calculate_quality_score(self, chunk: DocumentChunk) -> float:
        """
        Calculate quality score for a chunk.
        
        Args:
            chunk: Document chunk to score
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        pass
