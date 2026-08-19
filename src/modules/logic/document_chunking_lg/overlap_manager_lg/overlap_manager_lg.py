"""
Module: overlap_manager_lg
Description: Manages chunk overlap strategies to maintain context continuity between segments
Phase: 3
Location: /src/modules/logic/document_chunking_lg/overlap_manager_lg/
"""

# Standard library imports
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Third-party imports
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from ..base_interfaces import (
    IOverlapManager,
    DocumentChunk,
    ChunkConfig,
    ChunkMetadata,
    OverlapStrategy
)


@dataclass
class OverlapConfig:
    """Configuration for overlap management."""
    strategy: OverlapStrategy = OverlapStrategy.SENTENCE_BOUNDARY
    fixed_size: int = 128  # Fixed overlap size in tokens
    percentage: float = 0.1  # Percentage overlap (0.0-1.0)
    min_overlap: int = 50   # Minimum overlap size
    max_overlap: int = 300  # Maximum overlap size
    preserve_sentences: bool = True
    preserve_context: bool = True
    language: str = "english"


class OverlapCalculator:
    """Calculates optimal overlap sizes based on strategy."""
    
    def __init__(self, language: str = "english"):
        self.language = language
        self._logger = get_logger(__name__)
        
        # Download required NLTK data if not present
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
    
    def calculate_overlap_size(self, chunk: DocumentChunk, strategy: OverlapStrategy, 
                              config: OverlapConfig) -> int:
        """
        Calculate overlap size for a chunk based on strategy.
        
        Args:
            chunk: Document chunk
            strategy: Overlap strategy to use
            config: Overlap configuration
            
        Returns:
            Overlap size in characters
        """
        try:
            if strategy == OverlapStrategy.FIXED_SIZE:
                return self._calculate_fixed_overlap(chunk, config)
            elif strategy == OverlapStrategy.PERCENTAGE:
                return self._calculate_percentage_overlap(chunk, config)
            elif strategy == OverlapStrategy.SENTENCE_BOUNDARY:
                return self._calculate_sentence_boundary_overlap(chunk, config)
            elif strategy == OverlapStrategy.SEMANTIC_BOUNDARY:
                return self._calculate_semantic_boundary_overlap(chunk, config)
            elif strategy == OverlapStrategy.ADAPTIVE:
                return self._calculate_adaptive_overlap(chunk, config)
            else:
                return config.fixed_size
                
        except Exception as e:
            self._logger.warning(f"Overlap calculation failed: {e}")
            return config.fixed_size
    
    def _calculate_fixed_overlap(self, chunk: DocumentChunk, config: OverlapConfig) -> int:
        """Calculate fixed size overlap."""
        # Convert tokens to approximate characters (4:1 ratio)
        char_overlap = config.fixed_size * 4
        return min(char_overlap, len(chunk.content) // 2)
    
    def _calculate_percentage_overlap(self, chunk: DocumentChunk, config: OverlapConfig) -> int:
        """Calculate percentage-based overlap."""
        overlap_size = int(len(chunk.content) * config.percentage)
        return max(config.min_overlap, min(overlap_size, config.max_overlap))
    
    def _calculate_sentence_boundary_overlap(self, chunk: DocumentChunk, config: OverlapConfig) -> int:
        """Calculate overlap based on sentence boundaries."""
        try:
            sentences = sent_tokenize(chunk.content, language=self.language)
            
            if len(sentences) <= 1:
                return self._calculate_fixed_overlap(chunk, config)
            
            # Take last 1-2 sentences for overlap
            overlap_sentences = sentences[-2:] if len(sentences) > 2 else sentences[-1:]
            overlap_content = ' '.join(overlap_sentences)
            
            return min(len(overlap_content), config.max_overlap)
            
        except Exception:
            return self._calculate_fixed_overlap(chunk, config)
    
    def _calculate_semantic_boundary_overlap(self, chunk: DocumentChunk, config: OverlapConfig) -> int:
        """Calculate overlap based on semantic boundaries."""
        # Look for natural semantic breaks (paragraphs, sections)
        content = chunk.content
        
        # Find paragraph breaks
        paragraphs = content.split('\n\n')
        if len(paragraphs) > 1:
            # Use last paragraph for overlap
            last_paragraph = paragraphs[-1]
            overlap_size = len(last_paragraph)
            return max(config.min_overlap, min(overlap_size, config.max_overlap))
        
        # Fallback to sentence boundary
        return self._calculate_sentence_boundary_overlap(chunk, config)
    
    def _calculate_adaptive_overlap(self, chunk: DocumentChunk, config: OverlapConfig) -> int:
        """Calculate adaptive overlap based on content characteristics."""
        content = chunk.content
        
        # Analyze content characteristics
        sentence_count = len(sent_tokenize(content, language=self.language))
        paragraph_count = len(content.split('\n\n'))
        
        # Adjust overlap based on content structure
        if sentence_count <= 2:
            # Short content, use minimal overlap
            return config.min_overlap
        elif paragraph_count > 1:
            # Multi-paragraph content, use semantic boundary
            return self._calculate_semantic_boundary_overlap(chunk, config)
        else:
            # Single paragraph, use sentence boundary
            return self._calculate_sentence_boundary_overlap(chunk, config)


class ContextPreserver:
    """Preserves context information across chunk boundaries."""
    
    def __init__(self, language: str = "english"):
        self.language = language
        self._logger = get_logger(__name__)
    
    def extract_context_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """
        Extract key context words from content.
        
        Args:
            content: Text content
            max_keywords: Maximum number of keywords to extract
            
        Returns:
            List of context keywords
        """
        try:
            # Simple keyword extraction based on word frequency
            words = word_tokenize(content.lower(), language=self.language)
            
            # Filter out common stop words and short words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            keywords = [word for word in words if len(word) > 3 and word not in stop_words and word.isalpha()]
            
            # Count word frequencies
            word_freq = {}
            for word in keywords:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # Sort by frequency and return top keywords
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [word for word, freq in sorted_words[:max_keywords]]
            
        except Exception as e:
            self._logger.warning(f"Context keyword extraction failed: {e}")
            return []
    
    def find_context_boundaries(self, content: str) -> List[Tuple[int, str]]:
        """
        Find natural context boundaries in content.
        
        Args:
            content: Text content
            
        Returns:
            List of (position, boundary_type) tuples
        """
        boundaries = []
        
        # Find paragraph boundaries
        for match in re.finditer(r'\n\s*\n', content):
            boundaries.append((match.end(), 'paragraph'))
        
        # Find section headers
        for match in re.finditer(r'^#+\s+.*$|^[A-Z][^a-z]*$', content, re.MULTILINE):
            boundaries.append((match.start(), 'section'))
        
        # Find list boundaries
        for match in re.finditer(r'^\s*[-*+]\s+', content, re.MULTILINE):
            boundaries.append((match.start(), 'list'))
        
        return sorted(boundaries, key=lambda x: x[0])


class OverlapManager(IOverlapManager):
    """Manages chunk overlap to maintain context continuity."""
    
    def __init__(self, config: Optional[OverlapConfig] = None):
        self.config = config or OverlapConfig()
        self.calculator = OverlapCalculator(self.config.language)
        self.context_preserver = ContextPreserver(self.config.language)
        self._logger = get_logger(__name__)
    
    def calculate_overlap(self, chunks: List[DocumentChunk], config: ChunkConfig) -> List[DocumentChunk]:
        """
        Calculate and apply overlap between chunks.
        
        Args:
            chunks: List of document chunks
            config: Chunking configuration
            
        Returns:
            List of chunks with overlap applied
        """
        try:
            if len(chunks) <= 1:
                return chunks
            
            self._logger.info(f"Calculating overlap for {len(chunks)} chunks")
            
            overlapped_chunks = []
            
            for i, chunk in enumerate(chunks):
                if i == 0:
                    # First chunk has no previous overlap
                    overlapped_chunks.append(chunk)
                    continue
                
                previous_chunk = chunks[i - 1]
                
                # Calculate overlap content
                overlap_content = self.get_overlap_content(
                    previous_chunk, chunk, config.overlap_strategy
                )
                
                # Update chunk metadata with overlap information
                if overlap_content:
                    # Prepend overlap to current chunk
                    new_content = overlap_content + " " + chunk.content
                    
                    # Update metadata
                    new_metadata = ChunkMetadata(
                        chunk_index=chunk.metadata.chunk_index,
                        start_char=chunk.metadata.start_char - len(overlap_content),
                        end_char=chunk.metadata.end_char,
                        token_count=chunk.metadata.token_count + len(overlap_content.split()),
                        sentence_count=chunk.metadata.sentence_count,
                        paragraph_count=chunk.metadata.paragraph_count,
                        page_number=chunk.metadata.page_number,
                        section_title=chunk.metadata.section_title,
                        break_type=chunk.metadata.break_type,
                        overlap_start=chunk.metadata.start_char - len(overlap_content),
                        overlap_end=chunk.metadata.start_char,
                        quality_score=chunk.metadata.quality_score,
                        language=chunk.metadata.language,
                        created_at=chunk.metadata.created_at
                    )
                    
                    # Create new chunk with overlap
                    overlapped_chunk = DocumentChunk(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        content=new_content,
                        metadata=new_metadata,
                        chunk_hash=chunk.chunk_hash,
                        embedding_vector=chunk.embedding_vector
                    )
                    
                    overlapped_chunks.append(overlapped_chunk)
                else:
                    overlapped_chunks.append(chunk)
            
            self._logger.info(f"Applied overlap to {len(overlapped_chunks)} chunks")
            return overlapped_chunks
            
        except Exception as e:
            self._logger.error(f"Overlap calculation failed: {e}")
            return chunks  # Return original chunks on failure
    
    def get_overlap_content(self, chunk1: DocumentChunk, chunk2: DocumentChunk, 
                           strategy: OverlapStrategy) -> str:
        """
        Get overlap content between two chunks.
        
        Args:
            chunk1: First chunk (previous)
            chunk2: Second chunk (current)
            strategy: Overlap strategy to use
            
        Returns:
            Overlap content string
        """
        try:
            overlap_size = self.calculator.calculate_overlap_size(chunk1, strategy, self.config)
            
            if overlap_size <= 0:
                return ""
            
            # Extract overlap from end of first chunk
            content = chunk1.content
            
            if strategy == OverlapStrategy.SENTENCE_BOUNDARY:
                return self._get_sentence_overlap(content, overlap_size)
            elif strategy == OverlapStrategy.SEMANTIC_BOUNDARY:
                return self._get_semantic_overlap(content, overlap_size)
            else:
                # Fixed size or percentage overlap
                return content[-overlap_size:].strip()
                
        except Exception as e:
            self._logger.warning(f"Overlap content extraction failed: {e}")
            return ""
    
    def validate_overlap(self, chunks: List[DocumentChunk]) -> List[ValidationError]:
        """
        Validate overlap consistency across chunks.
        
        Args:
            chunks: List of document chunks
            
        Returns:
            List of validation errors
        """
        errors = []
        
        try:
            for i in range(1, len(chunks)):
                current_chunk = chunks[i]
                previous_chunk = chunks[i - 1]
                
                # Check for overlap metadata
                if (current_chunk.metadata.overlap_start is not None and 
                    current_chunk.metadata.overlap_end is not None):
                    
                    overlap_size = (current_chunk.metadata.overlap_end - 
                                  current_chunk.metadata.overlap_start)
                    
                    # Validate overlap size is reasonable
                    if overlap_size < 0:
                        errors.append(ValidationError(
                            field_name=f"chunk_{i}_overlap",
                            error_message="Negative overlap size detected",
                            actual_value=overlap_size
                        ))
                    
                    if overlap_size > len(current_chunk.content) // 2:
                        errors.append(ValidationError(
                            field_name=f"chunk_{i}_overlap",
                            error_message="Overlap size exceeds 50% of chunk content",
                            actual_value=overlap_size
                        ))
                
                # Check for content continuity
                if not self._check_content_continuity(previous_chunk, current_chunk):
                    errors.append(ValidationError(
                        field_name=f"chunk_{i}_continuity",
                        error_message="Content continuity broken between chunks",
                        actual_value=f"chunks {i-1} and {i}"
                    ))
            
        except Exception as e:
            errors.append(ValidationError(
                field_name="overlap_validation",
                error_message=f"Overlap validation failed: {str(e)}",
                actual_value=len(chunks)
            ))
        
        return errors
    
    def _get_sentence_overlap(self, content: str, max_size: int) -> str:
        """Get overlap content based on sentence boundaries."""
        try:
            sentences = sent_tokenize(content, language=self.config.language)
            
            if not sentences:
                return content[-max_size:].strip()
            
            # Take last sentences that fit within max_size
            overlap_sentences = []
            current_size = 0
            
            for sentence in reversed(sentences):
                if current_size + len(sentence) <= max_size:
                    overlap_sentences.insert(0, sentence)
                    current_size += len(sentence)
                else:
                    break
            
            return ' '.join(overlap_sentences)
            
        except Exception:
            return content[-max_size:].strip()
    
    def _get_semantic_overlap(self, content: str, max_size: int) -> str:
        """Get overlap content based on semantic boundaries."""
        # Find the last complete semantic unit (paragraph, section, etc.)
        boundaries = self.context_preserver.find_context_boundaries(content)
        
        if boundaries:
            # Find the last boundary that leaves enough content for overlap
            for pos, boundary_type in reversed(boundaries):
                if len(content) - pos <= max_size:
                    return content[pos:].strip()
        
        # Fallback to sentence-based overlap
        return self._get_sentence_overlap(content, max_size)
    
    def _check_content_continuity(self, chunk1: DocumentChunk, chunk2: DocumentChunk) -> bool:
        """Check if content flows naturally between chunks."""
        try:
            # Simple heuristic: check if chunks have reasonable character position continuity
            if (chunk1.metadata.end_char > chunk2.metadata.start_char and
                chunk2.metadata.overlap_start is None):
                return False  # Overlapping positions without overlap metadata
            
            # Check for reasonable gap between chunks
            gap = chunk2.metadata.start_char - chunk1.metadata.end_char
            if gap > 1000:  # Arbitrary threshold for large gaps
                return False
            
            return True
            
        except Exception:
            return True  # Assume continuity if check fails
