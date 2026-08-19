"""
Module: reranker_lg
Description: Implements cross-encoder reranking for improved result relevance
Phase: 4
Location: /src/modules/logic/context_builder_lg/reranker_lg/
"""

# Standard library imports
import time
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Third-party imports
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Local imports
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_chunking_lg.base_interfaces import DocumentChunk
from ..base_interfaces import (
    IReranker,
    RerankingResult,
    RerankingConfig,
    RerankingMethod
)


@dataclass
class QueryChunkPair:
    """Represents a query-chunk pair for scoring."""
    query: str
    chunk: DocumentChunk
    original_score: float
    pair_id: str


@dataclass
class ScoringFeatures:
    """Features extracted for scoring."""
    semantic_similarity: float
    keyword_overlap: float
    length_ratio: float
    position_score: float
    quality_score: float
    lexical_diversity: float


class CrossEncoderScorer:
    """Implements cross-encoder scoring for query-chunk pairs."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
        self._vectorizer = None
        self._is_initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize the cross-encoder scorer.
        
        Returns:
            True if initialization successful
        """
        try:
            # Initialize TF-IDF vectorizer for semantic scoring
            self._vectorizer = TfidfVectorizer(
                stop_words='english',
                max_features=5000,
                ngram_range=(1, 3),
                min_df=1,
                max_df=0.95
            )
            
            self._is_initialized = True
            return True
            
        except Exception as e:
            self._logger.error(f"Cross-encoder initialization failed: {e}")
            return False
    
    def extract_features(self, query: str, chunk: DocumentChunk) -> ScoringFeatures:
        """
        Extract features for query-chunk pair.
        
        Args:
            query: Search query
            chunk: Document chunk
            
        Returns:
            ScoringFeatures with extracted features
        """
        try:
            # Semantic similarity using TF-IDF
            semantic_sim = self._calculate_semantic_similarity(query, chunk.content)
            
            # Keyword overlap
            keyword_overlap = self._calculate_keyword_overlap(query, chunk.content)
            
            # Length ratio (query to chunk)
            length_ratio = self._calculate_length_ratio(query, chunk.content)
            
            # Position score from chunk metadata
            position_score = self._calculate_position_score(chunk)
            
            # Quality score from chunk metadata
            quality_score = chunk.metadata.get('quality_score', 0.5)
            
            # Lexical diversity
            lexical_diversity = self._calculate_lexical_diversity(chunk.content)
            
            return ScoringFeatures(
                semantic_similarity=semantic_sim,
                keyword_overlap=keyword_overlap,
                length_ratio=length_ratio,
                position_score=position_score,
                quality_score=quality_score,
                lexical_diversity=lexical_diversity
            )
            
        except Exception as e:
            self._logger.error(f"Feature extraction failed: {e}")
            return ScoringFeatures(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    
    def score_pair(self, query: str, chunk: DocumentChunk, original_score: float = 0.0) -> float:
        """
        Score a query-chunk pair using cross-encoder approach.
        
        Args:
            query: Search query
            chunk: Document chunk
            original_score: Original relevance score
            
        Returns:
            Cross-encoder score
        """
        try:
            if not self._is_initialized:
                if not self.initialize():
                    return original_score
            
            # Extract features
            features = self.extract_features(query, chunk)
            
            # Combine features using learned weights
            weights = {
                'semantic': 0.35,
                'keyword': 0.25,
                'length': 0.10,
                'position': 0.10,
                'quality': 0.15,
                'diversity': 0.05
            }
            
            cross_encoder_score = (
                features.semantic_similarity * weights['semantic'] +
                features.keyword_overlap * weights['keyword'] +
                features.length_ratio * weights['length'] +
                features.position_score * weights['position'] +
                features.quality_score * weights['quality'] +
                features.lexical_diversity * weights['diversity']
            )
            
            # Combine with original score
            combined_score = 0.7 * cross_encoder_score + 0.3 * original_score
            
            return max(0.0, min(1.0, combined_score))
            
        except Exception as e:
            self._logger.error(f"Cross-encoder scoring failed: {e}")
            return original_score
    
    def _calculate_semantic_similarity(self, query: str, content: str) -> float:
        """Calculate semantic similarity using TF-IDF."""
        try:
            if not self._vectorizer:
                return 0.0
            
            texts = [query, content]
            vectors = self._vectorizer.fit_transform(texts)
            
            if vectors.shape[0] >= 2:
                similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
                return max(0.0, min(1.0, similarity))
            
            return 0.0
            
        except Exception as e:
            self._logger.warning(f"Semantic similarity calculation failed: {e}")
            return 0.0
    
    def _calculate_keyword_overlap(self, query: str, content: str) -> float:
        """Calculate keyword overlap ratio."""
        try:
            query_words = set(query.lower().split())
            content_words = set(content.lower().split())
            
            if not query_words:
                return 0.0
            
            overlap = len(query_words.intersection(content_words))
            return overlap / len(query_words)
            
        except Exception as e:
            self._logger.warning(f"Keyword overlap calculation failed: {e}")
            return 0.0
    
    def _calculate_length_ratio(self, query: str, content: str) -> float:
        """Calculate optimal length ratio score."""
        try:
            query_len = len(query.split())
            content_len = len(content.split())
            
            if content_len == 0:
                return 0.0
            
            # Optimal ratio is around 1:10 to 1:50
            ratio = query_len / content_len
            
            if 0.02 <= ratio <= 0.1:  # 1:10 to 1:50
                return 1.0
            elif ratio < 0.02:
                return ratio / 0.02
            else:
                return max(0.1, 0.1 / ratio)
                
        except Exception as e:
            self._logger.warning(f"Length ratio calculation failed: {e}")
            return 0.5
    
    def _calculate_position_score(self, chunk: DocumentChunk) -> float:
        """Calculate position-based score."""
        try:
            position = chunk.metadata.get('position', 0)
            total_chunks = chunk.metadata.get('total_chunks', 1)
            
            if total_chunks <= 1:
                return 1.0
            
            # Exponential decay for position
            normalized_position = position / total_chunks
            return math.exp(-2 * normalized_position)
            
        except Exception as e:
            self._logger.warning(f"Position score calculation failed: {e}")
            return 0.5
    
    def _calculate_lexical_diversity(self, content: str) -> float:
        """Calculate lexical diversity score."""
        try:
            words = content.lower().split()
            if len(words) == 0:
                return 0.0
            
            unique_words = set(words)
            diversity = len(unique_words) / len(words)
            
            # Normalize to 0-1 range (optimal diversity is around 0.7)
            return min(1.0, diversity / 0.7)
            
        except Exception as e:
            self._logger.warning(f"Lexical diversity calculation failed: {e}")
            return 0.5


class QueryChunkPairProcessor:
    """Processes query-chunk pairs for reranking."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def create_pairs(self, query: str, chunks: List[DocumentChunk], 
                    original_scores: Optional[List[float]] = None) -> List[QueryChunkPair]:
        """
        Create query-chunk pairs for processing.
        
        Args:
            query: Search query
            chunks: List of chunks
            original_scores: Optional original scores
            
        Returns:
            List of QueryChunkPair objects
        """
        try:
            pairs = []
            scores = original_scores or [0.0] * len(chunks)
            
            for i, chunk in enumerate(chunks):
                pair = QueryChunkPair(
                    query=query,
                    chunk=chunk,
                    original_score=scores[i] if i < len(scores) else 0.0,
                    pair_id=f"{query[:20]}_{chunk.chunk_id}"
                )
                pairs.append(pair)
            
            return pairs
            
        except Exception as e:
            self._logger.error(f"Pair creation failed: {e}")
            return []
    
    def batch_process_pairs(self, pairs: List[QueryChunkPair], 
                          scorer: CrossEncoderScorer, batch_size: int = 16) -> List[float]:
        """
        Process pairs in batches for efficiency.
        
        Args:
            pairs: List of query-chunk pairs
            scorer: Cross-encoder scorer
            batch_size: Batch size for processing
            
        Returns:
            List of new scores
        """
        try:
            new_scores = []
            
            for i in range(0, len(pairs), batch_size):
                batch = pairs[i:i + batch_size]
                batch_scores = []
                
                for pair in batch:
                    score = scorer.score_pair(pair.query, pair.chunk, pair.original_score)
                    batch_scores.append(score)
                
                new_scores.extend(batch_scores)
            
            return new_scores
            
        except Exception as e:
            self._logger.error(f"Batch processing failed: {e}")
            return [pair.original_score for pair in pairs]


class RelevanceRanker:
    """Handles ranking and reordering of chunks."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def rank_by_scores(self, chunks: List[DocumentChunk], scores: List[float]) -> Tuple[List[DocumentChunk], List[float]]:
        """
        Rank chunks by scores in descending order.
        
        Args:
            chunks: List of chunks
            scores: List of scores
            
        Returns:
            Tuple of (ranked_chunks, ranked_scores)
        """
        try:
            if len(chunks) != len(scores):
                self._logger.warning("Chunk and score list lengths don't match")
                return chunks, scores
            
            # Create pairs and sort by score (descending)
            chunk_score_pairs = list(zip(chunks, scores))
            chunk_score_pairs.sort(key=lambda x: x[1], reverse=True)
            
            ranked_chunks, ranked_scores = zip(*chunk_score_pairs)
            return list(ranked_chunks), list(ranked_scores)
            
        except Exception as e:
            self._logger.error(f"Ranking failed: {e}")
            return chunks, scores
    
    def calculate_score_changes(self, original_scores: List[float], 
                              new_scores: List[float]) -> List[float]:
        """
        Calculate score changes after reranking.
        
        Args:
            original_scores: Original scores
            new_scores: New scores after reranking
            
        Returns:
            List of score changes
        """
        try:
            if len(original_scores) != len(new_scores):
                return [0.0] * len(new_scores)
            
            return [new - orig for orig, new in zip(original_scores, new_scores)]
            
        except Exception as e:
            self._logger.error(f"Score change calculation failed: {e}")
            return [0.0] * len(new_scores)


class Reranker(IReranker):
    """Main reranker implementation."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
        self.cross_encoder = CrossEncoderScorer()
        self.pair_processor = QueryChunkPairProcessor()
        self.ranker = RelevanceRanker()
        self._model_loaded = False
    
    def rerank_chunks(self, chunks: List[DocumentChunk], query: str, 
                     config: RerankingConfig) -> RerankingResult:
        """
        Rerank chunks using advanced scoring methods.
        
        Args:
            chunks: Chunks to rerank
            query: Search query
            config: Reranking configuration
            
        Returns:
            RerankingResult with reranked chunks
        """
        start_time = time.time()
        
        try:
            if not chunks:
                return RerankingResult(
                    reranked_chunks=[],
                    new_scores=[],
                    score_changes=[],
                    method_used=config.method,
                    processing_time=0.0,
                    success=False,
                    error_message="No chunks provided for reranking"
                )
            
            # Initialize scorer if needed
            if not self.cross_encoder._is_initialized:
                self.cross_encoder.initialize()
            
            # Get original scores (assume uniform if not provided)
            original_scores = [0.5] * len(chunks)
            
            # Apply reranking method
            if config.method == RerankingMethod.CROSS_ENCODER:
                new_scores = self._rerank_with_cross_encoder(chunks, query, config)
            elif config.method == RerankingMethod.QUERY_SIMILARITY:
                new_scores = self._rerank_with_query_similarity(chunks, query)
            else:
                # Default to cross-encoder
                new_scores = self._rerank_with_cross_encoder(chunks, query, config)
            
            # Apply score threshold
            if config.score_threshold > 0.0:
                filtered_pairs = [(chunk, score) for chunk, score in zip(chunks, new_scores) 
                                if score >= config.score_threshold]
                if filtered_pairs:
                    chunks, new_scores = zip(*filtered_pairs)
                    chunks, new_scores = list(chunks), list(new_scores)
            
            # Limit to top_k
            if config.top_k > 0 and len(chunks) > config.top_k:
                # Sort by score and take top_k
                chunk_score_pairs = list(zip(chunks, new_scores))
                chunk_score_pairs.sort(key=lambda x: x[1], reverse=True)
                chunk_score_pairs = chunk_score_pairs[:config.top_k]
                chunks, new_scores = zip(*chunk_score_pairs)
                chunks, new_scores = list(chunks), list(new_scores)
            
            # Rank chunks by new scores
            reranked_chunks, ranked_scores = self.ranker.rank_by_scores(chunks, new_scores)
            
            # Calculate score changes
            score_changes = self.ranker.calculate_score_changes(original_scores[:len(ranked_scores)], ranked_scores)
            
            processing_time = time.time() - start_time
            
            return RerankingResult(
                reranked_chunks=reranked_chunks,
                new_scores=ranked_scores,
                score_changes=score_changes,
                method_used=config.method,
                processing_time=processing_time,
                metadata={
                    'original_count': len(chunks),
                    'final_count': len(reranked_chunks),
                    'average_score': np.mean(ranked_scores) if ranked_scores else 0.0,
                    'score_variance': np.var(ranked_scores) if ranked_scores else 0.0,
                    'threshold_applied': config.score_threshold,
                    'top_k_applied': config.top_k
                },
                success=True
            )
            
        except Exception as e:
            self._logger.error(f"Reranking failed: {e}")
            return RerankingResult(
                reranked_chunks=[],
                new_scores=[],
                score_changes=[],
                method_used=config.method,
                processing_time=time.time() - start_time,
                success=False,
                error_message=f"Reranking failed: {e}"
            )
    
    def score_query_chunk_pairs(self, query: str, chunks: List[DocumentChunk]) -> List[float]:
        """
        Score query-chunk pairs for relevance.
        
        Args:
            query: Search query
            chunks: List of chunks
            
        Returns:
            List of relevance scores
        """
        try:
            pairs = self.pair_processor.create_pairs(query, chunks)
            return self.pair_processor.batch_process_pairs(pairs, self.cross_encoder)
        except Exception as e:
            self._logger.error(f"Query-chunk pair scoring failed: {e}")
            return [0.0] * len(chunks)
    
    def load_model(self, model_path: str) -> bool:
        """
        Load reranking model.
        
        Args:
            model_path: Path to model file
            
        Returns:
            True if model loaded successfully
        """
        try:
            # For now, just mark as loaded since we're using TF-IDF
            self._model_loaded = True
            self._logger.info(f"Model loading simulated for path: {model_path}")
            return True
        except Exception as e:
            self._logger.error(f"Model loading failed: {e}")
            return False
    
    def _rerank_with_cross_encoder(self, chunks: List[DocumentChunk], query: str, 
                                 config: RerankingConfig) -> List[float]:
        """Rerank using cross-encoder method."""
        pairs = self.pair_processor.create_pairs(query, chunks)
        return self.pair_processor.batch_process_pairs(pairs, self.cross_encoder, config.batch_size)
    
    def _rerank_with_query_similarity(self, chunks: List[DocumentChunk], query: str) -> List[float]:
        """Rerank using simple query similarity."""
        try:
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

            texts = [query] + [chunk.content for chunk in chunks]
            vectorizer = sklearn_feature_extraction.text.TfidfVectorizer(stop_words='english', max_features=1000)
            vectors = vectorizer.fit_transform(texts)

            query_vector = vectors[0:1]
            chunk_vectors = vectors[1:]

            similarities = sklearn_metrics.pairwise.cosine_similarity(query_vector, chunk_vectors)[0]
            return [max(0.0, min(1.0, score)) for score in similarities]
            
        except Exception as e:
            self._logger.error(f"Query similarity reranking failed: {e}")
            return [0.5] * len(chunks)
