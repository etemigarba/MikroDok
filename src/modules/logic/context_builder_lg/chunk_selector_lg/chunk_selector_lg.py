"""
Module: chunk_selector_lg
Description: Selects optimal chunks for LLM context based on relevance and token limits
Phase: 4
Location: /src/modules/logic/context_builder_lg/chunk_selector_lg/
"""

# Standard library imports
import time
import math
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass

# Third-party imports
import numpy as np

# Lazy imports for sklearn to prevent scipy loading during app startup
_sklearn_feature_extraction = None
_sklearn_metrics = None

def _get_sklearn_feature_extraction():
    """Lazy import for sklearn.feature_extraction to prevent scipy loading during startup."""
    global _sklearn_feature_extraction
    if _sklearn_feature_extraction is None:
        try:
            from sklearn import feature_extraction
            _sklearn_feature_extraction = feature_extraction
        except ImportError:
            _sklearn_feature_extraction = False
    return _sklearn_feature_extraction

def _get_sklearn_metrics():
    """Lazy import for sklearn.metrics to prevent scipy loading during startup."""
    global _sklearn_metrics
    if _sklearn_metrics is None:
        try:
            from sklearn import metrics
            _sklearn_metrics = metrics
        except ImportError:
            _sklearn_metrics = False
    return _sklearn_metrics

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_chunking_lg.base_interfaces import DocumentChunk
from ..base_interfaces import (
    IChunkSelector,
    ChunkSelectionResult,
    SelectionCriteria,
    RelevanceScore,
    SelectionStrategy
)


@dataclass
class ScoringWeights:
    """Weights for different scoring components."""
    semantic_similarity: float = 0.4
    keyword_overlap: float = 0.3
    position_score: float = 0.1
    length_score: float = 0.1
    quality_score: float = 0.1


class RelevanceCalculator:
    """Calculates relevance scores for chunks."""
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()
        self._logger = get_logger(__name__)
        self._tfidf_vectorizer = None
        self._query_vector = None
    
    def calculate_semantic_similarity(self, query: str, chunk: DocumentChunk) -> float:
        """
        Calculate semantic similarity between query and chunk.
        
        Args:
            query: Search query
            chunk: Document chunk
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # Use TF-IDF for semantic similarity
            texts = [query, chunk.content]
            
            # Initialize sklearn components lazily
            sklearn_feature_extraction = _get_sklearn_feature_extraction()
            sklearn_metrics = _get_sklearn_metrics()

            if sklearn_feature_extraction is False or sklearn_metrics is False:
                # Fallback: simple text overlap similarity
                query_words = set(query.lower().split())
                chunk_words = set(chunk.content.lower().split())
                if not query_words or not chunk_words:
                    return 0.0
                intersection = len(query_words.intersection(chunk_words))
                union = len(query_words.union(chunk_words))
                return intersection / union if union > 0 else 0.0

            if self._tfidf_vectorizer is None:
                self._tfidf_vectorizer = sklearn_feature_extraction.text.TfidfVectorizer(
                    stop_words='english',
                    max_features=1000,
                    ngram_range=(1, 2)
                )
                vectors = self._tfidf_vectorizer.fit_transform(texts)
            else:
                vectors = self._tfidf_vectorizer.transform(texts)

            if vectors.shape[0] >= 2:
                similarity = sklearn_metrics.pairwise.cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
                return max(0.0, min(1.0, similarity))
            
            return 0.0
            
        except Exception as e:
            self._logger.warning(f"Semantic similarity calculation failed: {e}")
            return 0.0
    
    def calculate_keyword_overlap(self, query: str, chunk: DocumentChunk) -> float:
        """
        Calculate keyword overlap score.
        
        Args:
            query: Search query
            chunk: Document chunk
            
        Returns:
            Overlap score between 0.0 and 1.0
        """
        try:
            query_words = set(query.lower().split())
            chunk_words = set(chunk.content.lower().split())
            
            if not query_words:
                return 0.0
            
            overlap = len(query_words.intersection(chunk_words))
            return overlap / len(query_words)
            
        except Exception as e:
            self._logger.warning(f"Keyword overlap calculation failed: {e}")
            return 0.0
    
    def calculate_position_score(self, chunk: DocumentChunk) -> float:
        """
        Calculate position-based score (earlier chunks get higher scores).
        
        Args:
            chunk: Document chunk
            
        Returns:
            Position score between 0.0 and 1.0
        """
        try:
            # Favor chunks that appear earlier in the document
            position = chunk.metadata.get('position', 0)
            max_position = chunk.metadata.get('total_chunks', 1)
            
            if max_position <= 1:
                return 1.0
            
            # Exponential decay for position scoring
            normalized_position = position / max_position
            return math.exp(-2 * normalized_position)
            
        except Exception as e:
            self._logger.warning(f"Position score calculation failed: {e}")
            return 0.5
    
    def calculate_length_score(self, chunk: DocumentChunk) -> float:
        """
        Calculate length-based score (prefer chunks with optimal length).
        
        Args:
            chunk: Document chunk
            
        Returns:
            Length score between 0.0 and 1.0
        """
        try:
            content_length = len(chunk.content)
            
            # Optimal length range (200-800 characters)
            optimal_min = 200
            optimal_max = 800
            
            if optimal_min <= content_length <= optimal_max:
                return 1.0
            elif content_length < optimal_min:
                return content_length / optimal_min
            else:
                # Penalty for very long chunks
                return max(0.1, optimal_max / content_length)
                
        except Exception as e:
            self._logger.warning(f"Length score calculation failed: {e}")
            return 0.5
    
    def calculate_quality_score(self, chunk: DocumentChunk) -> float:
        """
        Calculate quality-based score from chunk metadata.
        
        Args:
            chunk: Document chunk
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        try:
            # Use quality score from chunk metadata if available
            quality = chunk.metadata.get('quality_score', 0.5)
            return max(0.0, min(1.0, quality))
            
        except Exception as e:
            self._logger.warning(f"Quality score calculation failed: {e}")
            return 0.5
    
    def calculate_relevance(self, query: str, chunk: DocumentChunk) -> RelevanceScore:
        """
        Calculate overall relevance score for a chunk.
        
        Args:
            query: Search query
            chunk: Document chunk
            
        Returns:
            RelevanceScore with detailed scoring information
        """
        try:
            # Calculate individual scores
            semantic_score = self.calculate_semantic_similarity(query, chunk)
            keyword_score = self.calculate_keyword_overlap(query, chunk)
            position_score = self.calculate_position_score(chunk)
            length_score = self.calculate_length_score(chunk)
            quality_score = self.calculate_quality_score(chunk)
            
            # Calculate weighted overall score
            overall_score = (
                semantic_score * self.weights.semantic_similarity +
                keyword_score * self.weights.keyword_overlap +
                position_score * self.weights.position_score +
                length_score * self.weights.length_score +
                quality_score * self.weights.quality_score
            )
            
            # Calculate confidence based on score distribution
            scores = [semantic_score, keyword_score, position_score, length_score, quality_score]
            score_variance = np.var(scores)
            confidence = 1.0 - min(0.5, score_variance)
            
            return RelevanceScore(
                chunk_id=chunk.chunk_id,
                score=overall_score,
                confidence=confidence,
                method="weighted_composite",
                metadata={
                    'semantic_similarity': semantic_score,
                    'keyword_overlap': keyword_score,
                    'position_score': position_score,
                    'length_score': length_score,
                    'quality_score': quality_score,
                    'weights_used': {
                        'semantic': self.weights.semantic_similarity,
                        'keyword': self.weights.keyword_overlap,
                        'position': self.weights.position_score,
                        'length': self.weights.length_score,
                        'quality': self.weights.quality_score
                    }
                }
            )
            
        except Exception as e:
            self._logger.error(f"Relevance calculation failed for chunk {chunk.chunk_id}: {e}")
            return RelevanceScore(
                chunk_id=chunk.chunk_id,
                score=0.0,
                confidence=0.0,
                method="error_fallback",
                metadata={'error': str(e)}
            )


class TokenAwareSelector:
    """Selects chunks with token limit awareness."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Simple estimation: ~4 characters per token
        return max(1, len(text) // 4)
    
    def select_by_tokens(self, chunks: List[DocumentChunk], scores: List[RelevanceScore],
                        max_tokens: int) -> Tuple[List[DocumentChunk], List[RelevanceScore]]:
        """
        Select chunks within token limit.
        
        Args:
            chunks: Available chunks
            scores: Relevance scores for chunks
            max_tokens: Maximum token limit
            
        Returns:
            Tuple of (selected_chunks, selected_scores)
        """
        try:
            # Sort by relevance score (descending)
            chunk_score_pairs = list(zip(chunks, scores))
            chunk_score_pairs.sort(key=lambda x: x[1].score, reverse=True)
            
            selected_chunks = []
            selected_scores = []
            total_tokens = 0
            
            for chunk, score in chunk_score_pairs:
                chunk_tokens = self.estimate_tokens(chunk.content)
                
                if total_tokens + chunk_tokens <= max_tokens:
                    selected_chunks.append(chunk)
                    selected_scores.append(score)
                    total_tokens += chunk_tokens
                else:
                    # Check if we can fit a partial chunk
                    remaining_tokens = max_tokens - total_tokens
                    if remaining_tokens > 50:  # Minimum viable chunk size
                        # Truncate chunk to fit
                        chars_per_token = 4
                        max_chars = remaining_tokens * chars_per_token
                        truncated_content = chunk.content[:max_chars]
                        
                        # Create truncated chunk
                        truncated_chunk = DocumentChunk(
                            chunk_id=f"{chunk.chunk_id}_truncated",
                            content=truncated_content,
                            document_id=chunk.document_id,
                            metadata={**chunk.metadata, 'truncated': True}
                        )
                        
                        selected_chunks.append(truncated_chunk)
                        selected_scores.append(score)
                    break
            
            return selected_chunks, selected_scores
            
        except Exception as e:
            self._logger.error(f"Token-aware selection failed: {e}")
            return [], []


class QuerySimilarityScorer:
    """Scores chunks based on query similarity."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def score_similarity(self, query: str, chunks: List[DocumentChunk]) -> List[float]:
        """
        Score chunks based on similarity to query.
        
        Args:
            query: Search query
            chunks: List of chunks to score
            
        Returns:
            List of similarity scores
        """
        try:
            if not chunks:
                return []
            
            # Prepare texts for vectorization
            texts = [query] + [chunk.content for chunk in chunks]
            
            # Initialize sklearn components lazily
            sklearn_feature_extraction = _get_sklearn_feature_extraction()
            sklearn_metrics = _get_sklearn_metrics()

            if sklearn_feature_extraction is False or sklearn_metrics is False:
                # Fallback: simple text overlap similarity
                query_words = set(query.lower().split())
                similarities = []
                for chunk in chunks:
                    chunk_words = set(chunk.content.lower().split())
                    if not query_words or not chunk_words:
                        similarities.append(0.0)
                    else:
                        intersection = len(query_words.intersection(chunk_words))
                        union = len(query_words.union(chunk_words))
                        similarities.append(intersection / union if union > 0 else 0.0)
                return similarities

            # Create TF-IDF vectors
            vectorizer = sklearn_feature_extraction.text.TfidfVectorizer(
                stop_words='english',
                max_features=1000,
                ngram_range=(1, 2)
            )

            vectors = vectorizer.fit_transform(texts)
            query_vector = vectors[0:1]
            chunk_vectors = vectors[1:]

            # Calculate cosine similarities
            similarities = sklearn_metrics.pairwise.cosine_similarity(query_vector, chunk_vectors)[0]
            
            # Normalize scores to 0-1 range
            return [max(0.0, min(1.0, score)) for score in similarities]
            
        except Exception as e:
            self._logger.error(f"Query similarity scoring failed: {e}")
            return [0.0] * len(chunks)


class ChunkSelector(IChunkSelector):
    """Main chunk selector implementation."""
    
    def __init__(self, scoring_weights: Optional[ScoringWeights] = None):
        self._logger = get_logger(__name__)
        self.relevance_calculator = RelevanceCalculator(scoring_weights)
        self.token_selector = TokenAwareSelector()
        self.similarity_scorer = QuerySimilarityScorer()
    
    def select_chunks(self, chunks: List[DocumentChunk], query: str, 
                     criteria: SelectionCriteria) -> ChunkSelectionResult:
        """
        Select optimal chunks based on relevance and criteria.
        
        Args:
            chunks: List of available chunks
            query: Search query
            criteria: Selection criteria
            
        Returns:
            ChunkSelectionResult with selected chunks and metadata
        """
        start_time = time.time()
        
        try:
            if not chunks:
                return ChunkSelectionResult(
                    selected_chunks=[],
                    relevance_scores=[],
                    total_tokens=0,
                    selection_metadata={'reason': 'no_chunks_provided'},
                    processing_time=0.0,
                    strategy_used=criteria.strategy,
                    success=False,
                    error_message="No chunks provided for selection"
                )
            
            # Calculate relevance scores
            relevance_scores = self.calculate_relevance_scores(chunks, query)
            
            # Filter by minimum relevance
            filtered_pairs = [
                (chunk, score) for chunk, score in zip(chunks, relevance_scores)
                if score.score >= criteria.min_relevance_score
            ]
            
            if not filtered_pairs:
                return ChunkSelectionResult(
                    selected_chunks=[],
                    relevance_scores=[],
                    total_tokens=0,
                    selection_metadata={'reason': 'no_chunks_meet_relevance_threshold'},
                    processing_time=time.time() - start_time,
                    strategy_used=criteria.strategy,
                    success=False,
                    error_message=f"No chunks meet minimum relevance threshold of {criteria.min_relevance_score}"
                )
            
            filtered_chunks, filtered_scores = zip(*filtered_pairs)
            filtered_chunks = list(filtered_chunks)
            filtered_scores = list(filtered_scores)
            
            # Apply selection strategy
            if criteria.strategy == SelectionStrategy.TOKEN_OPTIMIZED:
                selected_chunks, selected_scores = self.token_selector.select_by_tokens(
                    filtered_chunks, filtered_scores, criteria.max_tokens
                )
            else:
                # Default to relevance-based selection with token awareness
                selected_chunks, selected_scores = self._select_by_relevance_and_tokens(
                    filtered_chunks, filtered_scores, criteria
                )
            
            # Limit to max_chunks
            if len(selected_chunks) > criteria.max_chunks:
                selected_chunks = selected_chunks[:criteria.max_chunks]
                selected_scores = selected_scores[:criteria.max_chunks]
            
            total_tokens = sum(self.token_selector.estimate_tokens(chunk.content) 
                             for chunk in selected_chunks)
            
            processing_time = time.time() - start_time
            
            return ChunkSelectionResult(
                selected_chunks=selected_chunks,
                relevance_scores=selected_scores,
                total_tokens=total_tokens,
                selection_metadata={
                    'original_chunk_count': len(chunks),
                    'filtered_chunk_count': len(filtered_chunks),
                    'final_chunk_count': len(selected_chunks),
                    'average_relevance': np.mean([s.score for s in selected_scores]) if selected_scores else 0.0,
                    'token_utilization': total_tokens / criteria.max_tokens if criteria.max_tokens > 0 else 0.0
                },
                processing_time=processing_time,
                strategy_used=criteria.strategy,
                success=True
            )
            
        except Exception as e:
            self._logger.error(f"Chunk selection failed: {e}")
            return ChunkSelectionResult(
                selected_chunks=[],
                relevance_scores=[],
                total_tokens=0,
                selection_metadata={'error_details': str(e)},
                processing_time=time.time() - start_time,
                strategy_used=criteria.strategy,
                success=False,
                error_message=f"Chunk selection failed: {e}"
            )
    
    def calculate_relevance_scores(self, chunks: List[DocumentChunk], 
                                 query: str) -> List[RelevanceScore]:
        """
        Calculate relevance scores for chunks.
        
        Args:
            chunks: List of chunks to score
            query: Search query
            
        Returns:
            List of relevance scores
        """
        try:
            return [self.relevance_calculator.calculate_relevance(query, chunk) 
                   for chunk in chunks]
        except Exception as e:
            self._logger.error(f"Relevance score calculation failed: {e}")
            return [RelevanceScore(
                chunk_id=chunk.chunk_id,
                score=0.0,
                confidence=0.0,
                method="error_fallback",
                metadata={'error': str(e)}
            ) for chunk in chunks]
    
    def estimate_token_usage(self, chunks: List[DocumentChunk]) -> int:
        """
        Estimate total token usage for chunks.
        
        Args:
            chunks: List of chunks
            
        Returns:
            Estimated token count
        """
        try:
            return sum(self.token_selector.estimate_tokens(chunk.content) 
                      for chunk in chunks)
        except Exception as e:
            self._logger.error(f"Token estimation failed: {e}")
            return 0
    
    def _select_by_relevance_and_tokens(self, chunks: List[DocumentChunk], 
                                      scores: List[RelevanceScore],
                                      criteria: SelectionCriteria) -> Tuple[List[DocumentChunk], List[RelevanceScore]]:
        """
        Select chunks by relevance while respecting token limits.
        
        Args:
            chunks: Available chunks
            scores: Relevance scores
            criteria: Selection criteria
            
        Returns:
            Tuple of (selected_chunks, selected_scores)
        """
        try:
            # Sort by relevance score (descending)
            chunk_score_pairs = list(zip(chunks, scores))
            chunk_score_pairs.sort(key=lambda x: x[1].score, reverse=True)
            
            selected_chunks = []
            selected_scores = []
            total_tokens = 0
            
            for chunk, score in chunk_score_pairs:
                chunk_tokens = self.token_selector.estimate_tokens(chunk.content)
                
                if total_tokens + chunk_tokens <= criteria.max_tokens:
                    selected_chunks.append(chunk)
                    selected_scores.append(score)
                    total_tokens += chunk_tokens
                else:
                    break
            
            return selected_chunks, selected_scores
            
        except Exception as e:
            self._logger.error(f"Relevance and token selection failed: {e}")
            return [], []
