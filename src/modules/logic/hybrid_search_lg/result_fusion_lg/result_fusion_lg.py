"""
Module: result_fusion_lg
Description: Combines and ranks results from semantic and keyword searches using weighted fusion
Phase: 4
Location: /src/modules/logic/hybrid_search_lg/result_fusion_lg/
"""

# Standard library imports
import time
import math
import threading
from collections import defaultdict
from typing import Optional, List, Dict, Any, Set, Tuple
from datetime import datetime

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ValidationError
from ..base_interfaces import (
    IResultFusion,
    SemanticSearchResult,
    KeywordSearchResult,
    HybridSearchResult,
    SearchResultItem,
    FusionConfig,
    FusionStrategy,
    SearchType,
    SearchStatus
)


class ScoreNormalizer:
    """Handles score normalization for result fusion."""
    
    def __init__(self):
        """Initialize score normalizer."""
        self._logger = get_logger(__name__)
    
    def normalize_scores(self, results: List[SearchResultItem], 
                        method: str = "min_max") -> List[SearchResultItem]:
        """
        Normalize scores across search result sets.
        
        Args:
            results: List of search results to normalize
            method: Normalization method ('min_max', 'z_score', 'rank_based')
            
        Returns:
            List of results with normalized scores
        """
        try:
            if not results:
                return results
            
            scores = [result.score for result in results]
            
            if method == "min_max":
                normalized_scores = self._min_max_normalize(scores)
            elif method == "z_score":
                normalized_scores = self._z_score_normalize(scores)
            elif method == "rank_based":
                normalized_scores = self._rank_based_normalize(scores)
            else:
                self._logger.warning(f"Unknown normalization method: {method}, using min_max")
                normalized_scores = self._min_max_normalize(scores)
            
            # Update results with normalized scores
            normalized_results = []
            for i, result in enumerate(results):
                normalized_result = SearchResultItem(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    score=normalized_scores[i],
                    content=result.content,
                    search_type=result.search_type,
                    rank=result.rank,
                    metadata=result.metadata,
                    content_preview=result.content_preview,
                    position_in_document=result.position_in_document,
                    relevance_score=result.relevance_score,
                    confidence=result.confidence,
                    source_path=result.source_path,
                    timestamp=result.timestamp
                )
                normalized_results.append(normalized_result)
            
            return normalized_results
            
        except Exception as e:
            self._logger.error(f"Error normalizing scores: {e}")
            return results
    
    def _min_max_normalize(self, scores: List[float]) -> List[float]:
        """Apply min-max normalization to scores."""
        if not scores:
            return scores
        
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return [1.0] * len(scores)
        
        return [(score - min_score) / (max_score - min_score) for score in scores]
    
    def _z_score_normalize(self, scores: List[float]) -> List[float]:
        """Apply z-score normalization to scores."""
        if not scores:
            return scores
        
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return [0.5] * len(scores)
        
        z_scores = [(score - mean_score) / std_dev for score in scores]
        
        # Convert z-scores to [0, 1] range using sigmoid
        return [1 / (1 + math.exp(-z)) for z in z_scores]
    
    def _rank_based_normalize(self, scores: List[float]) -> List[float]:
        """Apply rank-based normalization to scores."""
        if not scores:
            return scores
        
        # Sort scores and assign ranks
        sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        ranks = [0] * len(scores)
        
        for rank, idx in enumerate(sorted_indices):
            ranks[idx] = rank + 1
        
        # Convert ranks to normalized scores
        max_rank = len(scores)
        return [(max_rank - rank + 1) / max_rank for rank in ranks]


class RankFuser:
    """Handles rank-based fusion strategies."""
    
    def __init__(self):
        """Initialize rank fuser."""
        self._logger = get_logger(__name__)
    
    def reciprocal_rank_fusion(self, semantic_results: List[SearchResultItem],
                             keyword_results: List[SearchResultItem],
                             k: int = 60) -> List[SearchResultItem]:
        """
        Apply Reciprocal Rank Fusion (RRF) to combine results.
        
        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            k: RRF parameter (default: 60)
            
        Returns:
            Fused and ranked results
        """
        try:
            # Create document score mapping
            doc_scores = defaultdict(float)
            doc_items = {}
            
            # Process semantic results
            for rank, result in enumerate(semantic_results, 1):
                rrf_score = 1 / (k + rank)
                doc_scores[result.chunk_id] += rrf_score
                doc_items[result.chunk_id] = result
            
            # Process keyword results
            for rank, result in enumerate(keyword_results, 1):
                rrf_score = 1 / (k + rank)
                doc_scores[result.chunk_id] += rrf_score
                
                # Use keyword result if not already present
                if result.chunk_id not in doc_items:
                    doc_items[result.chunk_id] = result
            
            # Sort by fused score
            sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Build fused results
            fused_results = []
            for rank, (chunk_id, score) in enumerate(sorted_docs, 1):
                result = doc_items[chunk_id]
                fused_result = SearchResultItem(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    score=score,
                    content=result.content,
                    search_type=SearchType.HYBRID,
                    rank=rank,
                    metadata=result.metadata,
                    content_preview=result.content_preview,
                    position_in_document=result.position_in_document,
                    relevance_score=result.relevance_score,
                    confidence=result.confidence,
                    source_path=result.source_path,
                    timestamp=datetime.now()
                )
                fused_results.append(fused_result)
            
            return fused_results
            
        except Exception as e:
            self._logger.error(f"Error in reciprocal rank fusion: {e}")
            return []
    
    def borda_count_fusion(self, semantic_results: List[SearchResultItem],
                          keyword_results: List[SearchResultItem]) -> List[SearchResultItem]:
        """
        Apply Borda Count fusion to combine results.
        
        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            
        Returns:
            Fused and ranked results
        """
        try:
            # Create document score mapping
            doc_scores = defaultdict(float)
            doc_items = {}
            
            # Process semantic results (higher rank = higher score)
            semantic_count = len(semantic_results)
            for rank, result in enumerate(semantic_results, 1):
                borda_score = semantic_count - rank + 1
                doc_scores[result.chunk_id] += borda_score
                doc_items[result.chunk_id] = result
            
            # Process keyword results
            keyword_count = len(keyword_results)
            for rank, result in enumerate(keyword_results, 1):
                borda_score = keyword_count - rank + 1
                doc_scores[result.chunk_id] += borda_score
                
                if result.chunk_id not in doc_items:
                    doc_items[result.chunk_id] = result
            
            # Sort by fused score
            sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Build fused results
            fused_results = []
            for rank, (chunk_id, score) in enumerate(sorted_docs, 1):
                result = doc_items[chunk_id]
                fused_result = SearchResultItem(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    score=score,
                    content=result.content,
                    search_type=SearchType.HYBRID,
                    rank=rank,
                    metadata=result.metadata,
                    content_preview=result.content_preview,
                    position_in_document=result.position_in_document,
                    relevance_score=result.relevance_score,
                    confidence=result.confidence,
                    source_path=result.source_path,
                    timestamp=datetime.now()
                )
                fused_results.append(fused_result)
            
            return fused_results
            
        except Exception as e:
            self._logger.error(f"Error in Borda count fusion: {e}")
            return []


class DiversityOptimizer:
    """Handles diversity optimization for search results."""
    
    def __init__(self):
        """Initialize diversity optimizer."""
        self._logger = get_logger(__name__)
    
    def optimize_diversity(self, results: List[SearchResultItem], 
                          diversity_factor: float = 0.1) -> List[SearchResultItem]:
        """
        Optimize result diversity using Maximal Marginal Relevance (MMR).
        
        Args:
            results: List of search results to optimize
            diversity_factor: Factor controlling diversity vs relevance trade-off
            
        Returns:
            Diversified list of search results
        """
        try:
            if not results or diversity_factor <= 0:
                return results
            
            # Simple diversity optimization based on document sources
            diversified_results = []
            used_documents = set()
            
            # First pass: select highest scoring results from different documents
            for result in results:
                if result.document_id not in used_documents:
                    diversified_results.append(result)
                    used_documents.add(result.document_id)
            
            # Second pass: add remaining results if needed
            remaining_slots = len(results) - len(diversified_results)
            if remaining_slots > 0:
                remaining_results = [r for r in results if r not in diversified_results]
                diversified_results.extend(remaining_results[:remaining_slots])
            
            # Update ranks
            for i, result in enumerate(diversified_results):
                result.rank = i + 1
            
            return diversified_results
            
        except Exception as e:
            self._logger.error(f"Error optimizing diversity: {e}")
            return results


class ResultFusion(IResultFusion):
    """Main result fusion implementation for combining search results."""
    
    def __init__(self):
        """Initialize result fusion."""
        self._score_normalizer = ScoreNormalizer()
        self._rank_fuser = RankFuser()
        self._diversity_optimizer = DiversityOptimizer()
        self._logger = get_logger(__name__)
        self._lock = threading.RLock()
    
    def fuse_results(self, semantic_results: SemanticSearchResult,
                    keyword_results: KeywordSearchResult,
                    config: Optional[FusionConfig] = None) -> HybridSearchResult:
        """
        Combine semantic and keyword search results.
        
        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            config: Optional fusion configuration
            
        Returns:
            HybridSearchResult with fused results
        """
        start_time = time.time()
        config = config or FusionConfig()
        
        try:
            self._logger.info(f"Fusing results using strategy: {config.strategy.value}")
            
            # Normalize scores if enabled
            semantic_items = semantic_results.results
            keyword_items = keyword_results.results
            
            if config.score_normalization:
                semantic_items = self._score_normalizer.normalize_scores(
                    semantic_items, config.calibration_method
                )
                keyword_items = self._score_normalizer.normalize_scores(
                    keyword_items, config.calibration_method
                )
            
            # Apply fusion strategy
            if config.strategy == FusionStrategy.WEIGHTED_SUM:
                fused_results = self._weighted_sum_fusion(
                    semantic_items, keyword_items, config
                )
            elif config.strategy == FusionStrategy.RECIPROCAL_RANK_FUSION:
                fused_results = self._rank_fuser.reciprocal_rank_fusion(
                    semantic_items, keyword_items
                )
            elif config.strategy == FusionStrategy.BORDA_COUNT:
                fused_results = self._rank_fuser.borda_count_fusion(
                    semantic_items, keyword_items
                )
            elif config.strategy == FusionStrategy.LINEAR_COMBINATION:
                fused_results = self._linear_combination_fusion(
                    semantic_items, keyword_items, config
                )
            else:
                self._logger.warning(f"Unknown fusion strategy: {config.strategy}, using weighted sum")
                fused_results = self._weighted_sum_fusion(
                    semantic_items, keyword_items, config
                )
            
            # Apply diversity optimization if enabled
            if config.diversity_factor > 0:
                fused_results = self._diversity_optimizer.optimize_diversity(
                    fused_results, config.diversity_factor
                )
            
            # Filter by relevance threshold
            if config.relevance_threshold > 0:
                fused_results = [
                    result for result in fused_results 
                    if result.score >= config.relevance_threshold
                ]
            
            # Limit results
            fused_results = fused_results[:config.max_results]
            
            fusion_time = (time.time() - start_time) * 1000
            total_search_time = semantic_results.search_time_ms + keyword_results.search_time_ms
            
            self._logger.info(f"Result fusion completed in {fusion_time:.2f}ms, "
                            f"produced {len(fused_results)} results")
            
            return HybridSearchResult(
                status=SearchStatus.COMPLETED,
                query=semantic_results.query or keyword_results.query,
                fusion_strategy=config.strategy,
                semantic_results=semantic_results,
                keyword_results=keyword_results,
                fused_results=fused_results,
                total_search_time_ms=total_search_time,
                fusion_time_ms=fusion_time,
                semantic_weight=config.semantic_weight,
                keyword_weight=config.keyword_weight,
                metadata={
                    "config": config.__dict__,
                    "semantic_count": len(semantic_results.results),
                    "keyword_count": len(keyword_results.results),
                    "fusion_count": len(fused_results)
                }
            )
            
        except Exception as e:
            self._logger.error(f"Error in result fusion: {e}")
            return HybridSearchResult(
                status=SearchStatus.FAILED,
                query=semantic_results.query or keyword_results.query,
                fusion_strategy=config.strategy,
                semantic_results=semantic_results,
                keyword_results=keyword_results,
                fusion_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )
    
    def _weighted_sum_fusion(self, semantic_results: List[SearchResultItem],
                           keyword_results: List[SearchResultItem],
                           config: FusionConfig) -> List[SearchResultItem]:
        """Apply weighted sum fusion strategy."""
        doc_scores = defaultdict(float)
        doc_items = {}
        
        # Process semantic results
        for result in semantic_results:
            weighted_score = result.score * config.semantic_weight
            doc_scores[result.chunk_id] += weighted_score
            doc_items[result.chunk_id] = result
        
        # Process keyword results
        for result in keyword_results:
            weighted_score = result.score * config.keyword_weight
            doc_scores[result.chunk_id] += weighted_score
            
            if result.chunk_id not in doc_items:
                doc_items[result.chunk_id] = result
        
        # Sort by fused score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Build fused results
        fused_results = []
        for rank, (chunk_id, score) in enumerate(sorted_docs, 1):
            result = doc_items[chunk_id]
            fused_result = SearchResultItem(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                score=score,
                content=result.content,
                search_type=SearchType.HYBRID,
                rank=rank,
                metadata=result.metadata,
                content_preview=result.content_preview,
                position_in_document=result.position_in_document,
                relevance_score=result.relevance_score,
                confidence=result.confidence,
                source_path=result.source_path,
                timestamp=datetime.now()
            )
            fused_results.append(fused_result)
        
        return fused_results
    
    def _linear_combination_fusion(self, semantic_results: List[SearchResultItem],
                                 keyword_results: List[SearchResultItem],
                                 config: FusionConfig) -> List[SearchResultItem]:
        """Apply linear combination fusion strategy."""
        # Similar to weighted sum but with different normalization
        return self._weighted_sum_fusion(semantic_results, keyword_results, config)
    
    def normalize_scores(self, results: List[SearchResultItem], 
                        method: str = "min_max") -> List[SearchResultItem]:
        """
        Normalize scores across different search result sets.
        
        Args:
            results: List of search results to normalize
            method: Normalization method to use
            
        Returns:
            List of results with normalized scores
        """
        return self._score_normalizer.normalize_scores(results, method)
    
    def calculate_fusion_score(self, semantic_score: float, keyword_score: float,
                             semantic_weight: float, keyword_weight: float) -> float:
        """
        Calculate fused score from individual search scores.
        
        Args:
            semantic_score: Score from semantic search
            keyword_score: Score from keyword search
            semantic_weight: Weight for semantic score
            keyword_weight: Weight for keyword score
            
        Returns:
            Fused score
        """
        try:
            return semantic_score * semantic_weight + keyword_score * keyword_weight
        except Exception as e:
            self._logger.error(f"Error calculating fusion score: {e}")
            return 0.0
    
    def get_supported_strategies(self) -> List[FusionStrategy]:
        """
        Get list of supported fusion strategies.
        
        Returns:
            List of supported FusionStrategy enums
        """
        return [
            FusionStrategy.WEIGHTED_SUM,
            FusionStrategy.RECIPROCAL_RANK_FUSION,
            FusionStrategy.BORDA_COUNT,
            FusionStrategy.LINEAR_COMBINATION
        ]
