"""
Module: semantic_chunker_lg
Description: Splits documents into semantically coherent chunks (512-1024 tokens) preserving context
Phase: 3
Location: /src/modules/logic/document_chunking_lg/semantic_chunker_lg/
"""

# Standard library imports
import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

# Third-party imports
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_extraction_lg.base_interfaces import DocumentStructure
from ..base_interfaces import (
    ISemanticChunker,
    DocumentChunk,
    ChunkConfig,
    ChunkMetadata,
    SemanticBreakType,
    ChunkingStatus
)


@dataclass
class SemanticChunkingConfig:
    """Configuration for semantic chunking."""
    max_tokens: int = 1024
    min_tokens: int = 256
    target_tokens: int = 512
    sentence_overlap: int = 2
    preserve_code_blocks: bool = True
    preserve_tables: bool = True
    respect_headers: bool = True
    language: str = "english"
    custom_patterns: List[str] = field(default_factory=list)


class TokenCounter:
    """Handles token counting for different content types."""
    
    def __init__(self, language: str = "english"):
        self.language = language
        self._logger = get_logger(__name__)
        
        # Download required NLTK data if not present
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using word tokenization.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        try:
            if not text.strip():
                return 0
            
            # Use NLTK word tokenizer for accurate token counting
            tokens = word_tokenize(text, language=self.language)
            return len(tokens)
            
        except Exception as e:
            self._logger.warning(f"Token counting failed, using word split: {e}")
            # Fallback to simple word splitting
            return len(text.split())
    
    def estimate_tokens_from_chars(self, char_count: int) -> int:
        """
        Estimate token count from character count.
        
        Args:
            char_count: Number of characters
            
        Returns:
            Estimated token count
        """
        # Average ratio of characters to tokens (approximately 4:1)
        return max(1, char_count // 4)


class BreakPointDetector:
    """Detects optimal break points for semantic chunking."""
    
    def __init__(self, language: str = "english"):
        self.language = language
        self._logger = get_logger(__name__)
        
        # Sentence boundary patterns
        self.sentence_endings = re.compile(r'[.!?]+\s+')
        self.paragraph_breaks = re.compile(r'\n\s*\n')
        self.section_headers = re.compile(r'^#+\s+.*$|^[A-Z][^a-z]*$', re.MULTILINE)
        
        # Code block patterns
        self.code_blocks = re.compile(r'```[\s\S]*?```|`[^`]+`')
        
        # Table patterns
        self.table_patterns = re.compile(r'\|.*\|')
    
    def find_sentence_boundaries(self, text: str) -> List[int]:
        """
        Find sentence boundary positions in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of sentence boundary positions
        """
        try:
            sentences = sent_tokenize(text, language=self.language)
            boundaries = []
            current_pos = 0
            
            for sentence in sentences:
                sentence_start = text.find(sentence, current_pos)
                if sentence_start != -1:
                    sentence_end = sentence_start + len(sentence)
                    boundaries.append(sentence_end)
                    current_pos = sentence_end
            
            return boundaries
            
        except Exception as e:
            self._logger.warning(f"Sentence boundary detection failed: {e}")
            # Fallback to regex-based detection
            return [match.end() for match in self.sentence_endings.finditer(text)]
    
    def find_paragraph_boundaries(self, text: str) -> List[int]:
        """
        Find paragraph boundary positions in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of paragraph boundary positions
        """
        return [match.end() for match in self.paragraph_breaks.finditer(text)]
    
    def find_section_boundaries(self, text: str) -> List[int]:
        """
        Find section header positions in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of section boundary positions
        """
        return [match.start() for match in self.section_headers.finditer(text)]
    
    def find_optimal_break_point(self, text: str, target_position: int, 
                                max_distance: int = 200) -> Tuple[int, SemanticBreakType]:
        """
        Find the optimal break point near target position.
        
        Args:
            text: Text to analyze
            target_position: Target break position
            max_distance: Maximum distance to search from target
            
        Returns:
            Tuple of (position, break_type)
        """
        if target_position >= len(text):
            return len(text), SemanticBreakType.HARD_BREAK
        
        search_start = max(0, target_position - max_distance)
        search_end = min(len(text), target_position + max_distance)
        search_text = text[search_start:search_end]
        
        # Find different types of boundaries in search area
        sentence_boundaries = self.find_sentence_boundaries(search_text)
        paragraph_boundaries = self.find_paragraph_boundaries(search_text)
        section_boundaries = self.find_section_boundaries(search_text)
        
        # Adjust positions to absolute coordinates
        sentence_boundaries = [pos + search_start for pos in sentence_boundaries]
        paragraph_boundaries = [pos + search_start for pos in paragraph_boundaries]
        section_boundaries = [pos + search_start for pos in section_boundaries]
        
        # Find closest boundary to target position
        candidates = []
        
        for pos in section_boundaries:
            if search_start <= pos <= search_end:
                candidates.append((abs(pos - target_position), pos, SemanticBreakType.SECTION_END))
        
        for pos in paragraph_boundaries:
            if search_start <= pos <= search_end:
                candidates.append((abs(pos - target_position), pos, SemanticBreakType.PARAGRAPH_END))
        
        for pos in sentence_boundaries:
            if search_start <= pos <= search_end:
                candidates.append((abs(pos - target_position), pos, SemanticBreakType.SENTENCE_END))
        
        if candidates:
            # Sort by distance and return closest
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1], candidates[0][2]
        
        # No good boundary found, use target position
        return target_position, SemanticBreakType.HARD_BREAK


class SemanticChunker(ISemanticChunker):
    """Semantic document chunker that preserves context and meaning."""
    
    def __init__(self, config: Optional[SemanticChunkingConfig] = None):
        self.config = config or SemanticChunkingConfig()
        self.token_counter = TokenCounter(self.config.language)
        self.break_detector = BreakPointDetector(self.config.language)
        self._logger = get_logger(__name__)
    
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
        try:
            if not content.strip():
                return []
            
            self._logger.info(f"Starting semantic chunking of {len(content)} characters")
            
            chunks = []
            current_position = 0
            chunk_index = 0
            
            while current_position < len(content):
                # Calculate target end position based on token count
                target_tokens = config.target_chunk_size
                estimated_chars = target_tokens * 4  # Rough estimate
                target_end = min(len(content), current_position + estimated_chars)
                
                # Find optimal break point
                break_position, break_type = self.break_detector.find_optimal_break_point(
                    content, target_end
                )
                
                # Extract chunk content
                chunk_content = content[current_position:break_position].strip()
                
                if chunk_content:
                    # Count actual tokens
                    token_count = self.token_counter.count_tokens(chunk_content)
                    
                    # Ensure chunk meets minimum size requirements
                    if token_count < config.min_chunk_size and break_position < len(content):
                        # Extend chunk to meet minimum size
                        extended_end = self._extend_chunk_to_minimum(
                            content, break_position, config.min_chunk_size
                        )
                        chunk_content = content[current_position:extended_end].strip()
                        token_count = self.token_counter.count_tokens(chunk_content)
                        break_position = extended_end
                    
                    # Create chunk metadata
                    metadata = ChunkMetadata(
                        chunk_index=chunk_index,
                        start_char=current_position,
                        end_char=break_position,
                        token_count=token_count,
                        sentence_count=len(self.break_detector.find_sentence_boundaries(chunk_content)),
                        paragraph_count=len(self.break_detector.find_paragraph_boundaries(chunk_content)) + 1,
                        break_type=break_type
                    )
                    
                    # Create document chunk
                    chunk = DocumentChunk(
                        chunk_id=str(uuid.uuid4()),
                        document_id="",  # Will be set by caller
                        content=chunk_content,
                        metadata=metadata,
                        chunk_hash=self._calculate_chunk_hash(chunk_content)
                    )
                    
                    chunks.append(chunk)
                    chunk_index += 1
                
                # Move to next position
                current_position = break_position
                
                # Safety check to prevent infinite loops
                if current_position >= len(content):
                    break
            
            self._logger.info(f"Created {len(chunks)} semantic chunks")
            return chunks
            
        except Exception as e:
            self._logger.error(f"Semantic chunking failed: {e}")
            raise ValidationError(
                field_name="content",
                error_message=f"Semantic chunking failed: {str(e)}",
                actual_value=len(content)
            )
    
    def estimate_chunk_count(self, content: str, config: ChunkConfig) -> int:
        """
        Estimate number of chunks that will be created.
        
        Args:
            content: Document text content
            config: Chunking configuration
            
        Returns:
            Estimated number of chunks
        """
        if not content.strip():
            return 0
        
        total_tokens = self.token_counter.count_tokens(content)
        avg_chunk_size = (config.max_chunk_size + config.min_chunk_size) // 2
        
        return max(1, total_tokens // avg_chunk_size)
    
    def find_break_points(self, content: str, config: ChunkConfig) -> List[Tuple[int, SemanticBreakType]]:
        """
        Find optimal break points in content.
        
        Args:
            content: Document text content
            config: Chunking configuration
            
        Returns:
            List of (position, break_type) tuples
        """
        break_points = []
        current_position = 0
        
        while current_position < len(content):
            target_tokens = config.target_chunk_size
            estimated_chars = target_tokens * 4
            target_end = min(len(content), current_position + estimated_chars)
            
            break_position, break_type = self.break_detector.find_optimal_break_point(
                content, target_end
            )
            
            break_points.append((break_position, break_type))
            current_position = break_position
            
            if current_position >= len(content):
                break
        
        return break_points
    
    def _extend_chunk_to_minimum(self, content: str, current_end: int, min_tokens: int) -> int:
        """
        Extend chunk to meet minimum token requirements.
        
        Args:
            content: Full document content
            current_end: Current chunk end position
            min_tokens: Minimum required tokens
            
        Returns:
            New end position
        """
        max_extension = min(len(content), current_end + 500)  # Limit extension
        
        for pos in range(current_end, max_extension, 50):
            chunk_content = content[:pos]
            if self.token_counter.count_tokens(chunk_content) >= min_tokens:
                return pos
        
        return max_extension
    
    def _calculate_chunk_hash(self, content: str) -> str:
        """
        Calculate SHA-256 hash of chunk content.
        
        Args:
            content: Chunk content
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
