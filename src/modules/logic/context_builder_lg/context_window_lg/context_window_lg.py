"""
Module: context_window_lg
Description: Manages context window construction with token counting and optimization
Phase: 4
Location: /src/modules/logic/context_builder_lg/context_window_lg/
"""

# Standard library imports
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Third-party imports
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_chunking_lg.base_interfaces import DocumentChunk
from ..base_interfaces import (
    IContextWindow,
    ContextWindowResult,
    ContextConfig,
    ContextBoundary,
    ContextOptimization
)


@dataclass
class TokenizationConfig:
    """Configuration for tokenization."""
    language: str = "english"
    preserve_whitespace: bool = True
    handle_special_tokens: bool = True
    estimate_ratio: float = 4.0  # characters per token


class TokenCounter:
    """Handles token counting with multiple methods."""
    
    def __init__(self, config: Optional[TokenizationConfig] = None):
        self.config = config or TokenizationConfig()
        self._logger = get_logger(__name__)
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using NLTK word tokenization.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        try:
            if not text.strip():
                return 0
            
            # Use NLTK word tokenizer for accurate token counting
            tokens = word_tokenize(text, language=self.config.language)
            return len(tokens)
            
        except Exception as e:
            self._logger.warning(f"NLTK tokenization failed, using estimation: {e}")
            return self.estimate_tokens(text)
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count using character-to-token ratio.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        
        # Simple estimation based on character count
        return max(1, int(len(text) / self.config.estimate_ratio))
    
    def count_sentences(self, text: str) -> int:
        """
        Count sentences in text.
        
        Args:
            text: Text to count sentences for
            
        Returns:
            Number of sentences
        """
        try:
            if not text.strip():
                return 0
            
            sentences = sent_tokenize(text, language=self.config.language)
            return len(sentences)
            
        except Exception as e:
            self._logger.warning(f"Sentence tokenization failed: {e}")
            # Fallback to simple period counting
            return len(re.findall(r'[.!?]+', text))
    
    def split_by_tokens(self, text: str, max_tokens: int) -> List[str]:
        """
        Split text into segments with maximum token count.
        
        Args:
            text: Text to split
            max_tokens: Maximum tokens per segment
            
        Returns:
            List of text segments
        """
        try:
            if not text or max_tokens <= 0:
                return []
            
            total_tokens = self.count_tokens(text)
            if total_tokens <= max_tokens:
                return [text]
            
            # Split by sentences first
            sentences = sent_tokenize(text, language=self.config.language)
            segments = []
            current_segment = []
            current_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = self.count_tokens(sentence)
                
                if current_tokens + sentence_tokens <= max_tokens:
                    current_segment.append(sentence)
                    current_tokens += sentence_tokens
                else:
                    if current_segment:
                        segments.append(' '.join(current_segment))
                        current_segment = []
                        current_tokens = 0
                    
                    # Handle very long sentences
                    if sentence_tokens > max_tokens:
                        # Split by words
                        words = sentence.split()
                        word_segment = []
                        word_tokens = 0
                        
                        for word in words:
                            word_token_count = self.count_tokens(word)
                            if word_tokens + word_token_count <= max_tokens:
                                word_segment.append(word)
                                word_tokens += word_token_count
                            else:
                                if word_segment:
                                    segments.append(' '.join(word_segment))
                                word_segment = [word]
                                word_tokens = word_token_count
                        
                        if word_segment:
                            current_segment = word_segment
                            current_tokens = word_tokens
                    else:
                        current_segment = [sentence]
                        current_tokens = sentence_tokens
            
            if current_segment:
                segments.append(' '.join(current_segment))
            
            return segments
            
        except Exception as e:
            self._logger.error(f"Token-based splitting failed: {e}")
            # Fallback to character-based splitting
            chars_per_token = int(self.config.estimate_ratio)
            max_chars = max_tokens * chars_per_token
            return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]


class BoundaryManager:
    """Manages context boundaries and chunk organization."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def create_boundaries(self, chunks: List[DocumentChunk], context_text: str) -> List[ContextBoundary]:
        """
        Create boundary information for chunks in context.
        
        Args:
            chunks: List of chunks in context
            context_text: Combined context text
            
        Returns:
            List of context boundaries
        """
        try:
            boundaries = []
            current_position = 0
            
            for i, chunk in enumerate(chunks):
                chunk_content = chunk.content
                start_pos = context_text.find(chunk_content, current_position)
                
                if start_pos != -1:
                    end_pos = start_pos + len(chunk_content)
                    
                    boundary = ContextBoundary(
                        start_position=start_pos,
                        end_position=end_pos,
                        chunk_id=chunk.chunk_id,
                        token_count=len(chunk_content.split()),  # Simple token estimation
                        boundary_type="chunk_boundary",
                        metadata={
                            'chunk_index': i,
                            'document_id': chunk.document_id,
                            'original_position': chunk.metadata.get('position', 0)
                        }
                    )
                    
                    boundaries.append(boundary)
                    current_position = end_pos
                else:
                    self._logger.warning(f"Could not find chunk {chunk.chunk_id} in context text")
            
            return boundaries
            
        except Exception as e:
            self._logger.error(f"Boundary creation failed: {e}")
            return []
    
    def validate_boundaries(self, boundaries: List[ContextBoundary], context_text: str) -> bool:
        """
        Validate that boundaries are consistent with context text.
        
        Args:
            boundaries: List of boundaries to validate
            context_text: Context text
            
        Returns:
            True if boundaries are valid
        """
        try:
            for boundary in boundaries:
                if boundary.start_position < 0 or boundary.end_position > len(context_text):
                    return False
                
                if boundary.start_position >= boundary.end_position:
                    return False
            
            # Check for overlaps
            sorted_boundaries = sorted(boundaries, key=lambda b: b.start_position)
            for i in range(len(sorted_boundaries) - 1):
                if sorted_boundaries[i].end_position > sorted_boundaries[i + 1].start_position:
                    return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"Boundary validation failed: {e}")
            return False


class ContextOptimizer:
    """Optimizes context for token efficiency and relevance."""
    
    def __init__(self, token_counter: TokenCounter):
        self.token_counter = token_counter
        self._logger = get_logger(__name__)
    
    def optimize_for_tokens(self, context_text: str, target_tokens: int) -> str:
        """
        Optimize context to fit within target token count.
        
        Args:
            context_text: Original context text
            target_tokens: Target token count
            
        Returns:
            Optimized context text
        """
        try:
            current_tokens = self.token_counter.count_tokens(context_text)
            
            if current_tokens <= target_tokens:
                return context_text
            
            # Split into segments and select most important ones
            segments = self.token_counter.split_by_tokens(context_text, target_tokens // 3)
            
            if not segments:
                return context_text[:target_tokens * 4]  # Fallback to character truncation
            
            # Select segments that fit within token limit
            selected_segments = []
            total_tokens = 0
            
            for segment in segments:
                segment_tokens = self.token_counter.count_tokens(segment)
                if total_tokens + segment_tokens <= target_tokens:
                    selected_segments.append(segment)
                    total_tokens += segment_tokens
                else:
                    break
            
            return ' '.join(selected_segments)
            
        except Exception as e:
            self._logger.error(f"Token optimization failed: {e}")
            return context_text
    
    def optimize_for_relevance(self, context_text: str, query: str) -> str:
        """
        Optimize context for relevance to query.
        
        Args:
            context_text: Original context text
            query: Search query
            
        Returns:
            Relevance-optimized context text
        """
        try:
            # Simple relevance optimization: prioritize sentences with query terms
            query_terms = set(query.lower().split())
            sentences = sent_tokenize(context_text)
            
            # Score sentences by query term overlap
            scored_sentences = []
            for sentence in sentences:
                sentence_words = set(sentence.lower().split())
                overlap = len(query_terms.intersection(sentence_words))
                scored_sentences.append((sentence, overlap))
            
            # Sort by relevance score (descending)
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            
            # Return reordered sentences
            return ' '.join([sentence for sentence, _ in scored_sentences])
            
        except Exception as e:
            self._logger.error(f"Relevance optimization failed: {e}")
            return context_text
    
    def optimize_for_coherence(self, context_text: str) -> str:
        """
        Optimize context for coherence and readability.
        
        Args:
            context_text: Original context text
            
        Returns:
            Coherence-optimized context text
        """
        try:
            # Simple coherence optimization: ensure proper sentence flow
            sentences = sent_tokenize(context_text)
            
            # Remove duplicate sentences
            unique_sentences = []
            seen_sentences = set()
            
            for sentence in sentences:
                sentence_clean = sentence.strip().lower()
                if sentence_clean not in seen_sentences and len(sentence_clean) > 10:
                    unique_sentences.append(sentence)
                    seen_sentences.add(sentence_clean)
            
            return ' '.join(unique_sentences)
            
        except Exception as e:
            self._logger.error(f"Coherence optimization failed: {e}")
            return context_text


class ContextWindow(IContextWindow):
    """Main context window implementation."""
    
    def __init__(self, tokenization_config: Optional[TokenizationConfig] = None):
        self._logger = get_logger(__name__)
        self.token_counter = TokenCounter(tokenization_config)
        self.boundary_manager = BoundaryManager()
        self.optimizer = ContextOptimizer(self.token_counter)
    
    def build_context(self, chunks: List[DocumentChunk], config: ContextConfig) -> ContextWindowResult:
        """
        Build context window from selected chunks.
        
        Args:
            chunks: Selected chunks to include
            config: Context configuration
            
        Returns:
            ContextWindowResult with constructed context
        """
        start_time = time.time()
        
        try:
            if not chunks:
                return ContextWindowResult(
                    context_text="",
                    boundaries=[],
                    total_tokens=0,
                    chunk_count=0,
                    optimization_applied=config.optimization,
                    success=False,
                    error_message="No chunks provided for context building"
                )
            
            # Combine chunks into context text
            context_parts = []
            for i, chunk in enumerate(chunks):
                if config.include_citations:
                    citation = f"[{i+1}] "
                    context_parts.append(f"{citation}{chunk.content}")
                else:
                    context_parts.append(chunk.content)
            
            # Join with custom separators or default
            separator = config.custom_separators[0] if config.custom_separators else "\n\n"
            context_text = separator.join(context_parts)
            
            # Apply optimization
            optimized_text = self.optimize_context(context_text, config)
            
            # Create boundaries
            boundaries = self.boundary_manager.create_boundaries(chunks, optimized_text)
            
            # Count tokens
            total_tokens = self.count_tokens(optimized_text)
            
            # Create citations if enabled
            citations = []
            if config.include_citations:
                for i, chunk in enumerate(chunks):
                    citations.append({
                        'index': i + 1,
                        'chunk_id': chunk.chunk_id,
                        'document_id': chunk.document_id,
                        'source': chunk.metadata.get('source', 'Unknown')
                    })
            
            processing_time = time.time() - start_time
            
            return ContextWindowResult(
                context_text=optimized_text,
                boundaries=boundaries,
                total_tokens=total_tokens,
                chunk_count=len(chunks),
                optimization_applied=config.optimization,
                citations=citations,
                metadata={
                    'original_length': len(context_text),
                    'optimized_length': len(optimized_text),
                    'compression_ratio': len(optimized_text) / len(context_text) if context_text else 1.0,
                    'processing_time': processing_time,
                    'separator_used': separator,
                    'boundaries_valid': self.boundary_manager.validate_boundaries(boundaries, optimized_text)
                },
                success=True
            )
            
        except Exception as e:
            self._logger.error(f"Context building failed: {e}")
            return ContextWindowResult(
                context_text="",
                boundaries=[],
                total_tokens=0,
                chunk_count=0,
                optimization_applied=config.optimization,
                success=False,
                error_message=f"Context building failed: {e}"
            )
    
    def optimize_context(self, context_text: str, config: ContextConfig) -> str:
        """
        Optimize context for token efficiency and relevance.
        
        Args:
            context_text: Raw context text
            config: Optimization configuration
            
        Returns:
            Optimized context text
        """
        try:
            optimized_text = context_text
            
            if config.optimization == ContextOptimization.TOKEN_EFFICIENT:
                optimized_text = self.optimizer.optimize_for_tokens(
                    optimized_text, config.target_tokens
                )
            elif config.optimization == ContextOptimization.COHERENCE_FOCUSED:
                optimized_text = self.optimizer.optimize_for_coherence(optimized_text)
            elif config.optimization == ContextOptimization.ADAPTIVE:
                # Apply multiple optimizations
                optimized_text = self.optimizer.optimize_for_coherence(optimized_text)
                optimized_text = self.optimizer.optimize_for_tokens(
                    optimized_text, config.target_tokens
                )
            
            # Ensure we don't exceed max tokens
            current_tokens = self.count_tokens(optimized_text)
            if current_tokens > config.max_context_tokens:
                optimized_text = self.optimizer.optimize_for_tokens(
                    optimized_text, config.max_context_tokens
                )
            
            return optimized_text
            
        except Exception as e:
            self._logger.error(f"Context optimization failed: {e}")
            return context_text
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return self.token_counter.count_tokens(text)
