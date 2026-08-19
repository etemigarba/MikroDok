"""
Module: base_interfaces
Description: Base interfaces and data structures for context builder functionality
Phase: 4
Location: /src/modules/logic/context_builder_lg/
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np

from src.modules.logic.document_chunking_lg.base_interfaces import DocumentChunk


class SelectionStrategy(Enum):
    """Strategies for chunk selection."""
    RELEVANCE_BASED = "relevance_based"
    TOKEN_OPTIMIZED = "token_optimized"
    HYBRID = "hybrid"
    DIVERSITY_AWARE = "diversity_aware"
    TEMPORAL_AWARE = "temporal_aware"


class RerankingMethod(Enum):
    """Methods for reranking chunks."""
    CROSS_ENCODER = "cross_encoder"
    QUERY_SIMILARITY = "query_similarity"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    HYBRID_SCORING = "hybrid_scoring"
    LEARNED_RANKING = "learned_ranking"


class ContextOptimization(Enum):
    """Context optimization strategies."""
    TOKEN_EFFICIENT = "token_efficient"
    RELEVANCE_MAXIMIZED = "relevance_maximized"
    DIVERSITY_BALANCED = "diversity_balanced"
    COHERENCE_FOCUSED = "coherence_focused"
    ADAPTIVE = "adaptive"


@dataclass
class RelevanceScore:
    """Relevance score for a chunk."""
    chunk_id: str
    score: float
    confidence: float
    method: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextBoundary:
    """Context boundary information."""
    start_position: int
    end_position: int
    chunk_id: str
    token_count: int
    boundary_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SelectionCriteria:
    """Criteria for chunk selection."""
    max_tokens: int = 2048
    min_relevance_score: float = 0.1
    max_chunks: int = 10
    diversity_threshold: float = 0.8
    strategy: SelectionStrategy = SelectionStrategy.HYBRID
    include_metadata: bool = True
    preserve_order: bool = False
    custom_weights: Dict[str, float] = field(default_factory=dict)


@dataclass
class ContextConfig:
    """Configuration for context window construction."""
    max_context_tokens: int = 4096
    target_tokens: int = 2048
    min_tokens: int = 512
    overlap_tokens: int = 128
    optimization: ContextOptimization = ContextOptimization.ADAPTIVE
    preserve_boundaries: bool = True
    include_citations: bool = True
    compression_enabled: bool = False
    custom_separators: List[str] = field(default_factory=list)


@dataclass
class RerankingConfig:
    """Configuration for reranking."""
    method: RerankingMethod = RerankingMethod.CROSS_ENCODER
    top_k: int = 20
    score_threshold: float = 0.0
    normalize_scores: bool = True
    combine_scores: bool = True
    score_weights: Dict[str, float] = field(default_factory=dict)
    model_path: Optional[str] = None
    batch_size: int = 16


@dataclass
class ChunkSelectionResult:
    """Result of chunk selection operation."""
    selected_chunks: List[DocumentChunk]
    relevance_scores: List[RelevanceScore]
    total_tokens: int
    selection_metadata: Dict[str, Any]
    processing_time: float
    strategy_used: SelectionStrategy
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class ContextWindowResult:
    """Result of context window construction."""
    context_text: str
    boundaries: List[ContextBoundary]
    total_tokens: int
    chunk_count: int
    optimization_applied: ContextOptimization
    citations: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class RerankingResult:
    """Result of reranking operation."""
    reranked_chunks: List[DocumentChunk]
    new_scores: List[float]
    score_changes: List[float]
    method_used: RerankingMethod
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None


class IChunkSelector(ABC):
    """Base interface for chunk selectors."""
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def estimate_token_usage(self, chunks: List[DocumentChunk]) -> int:
        """
        Estimate total token usage for chunks.
        
        Args:
            chunks: List of chunks
            
        Returns:
            Estimated token count
        """
        pass


class IContextWindow(ABC):
    """Base interface for context window managers."""
    
    @abstractmethod
    def build_context(self, chunks: List[DocumentChunk], config: ContextConfig) -> ContextWindowResult:
        """
        Build context window from selected chunks.
        
        Args:
            chunks: Selected chunks to include
            config: Context configuration
            
        Returns:
            ContextWindowResult with constructed context
        """
        pass
    
    @abstractmethod
    def optimize_context(self, context_text: str, config: ContextConfig) -> str:
        """
        Optimize context for token efficiency and relevance.
        
        Args:
            context_text: Raw context text
            config: Optimization configuration
            
        Returns:
            Optimized context text
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        pass


class IReranker(ABC):
    """Base interface for rerankers."""
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def score_query_chunk_pairs(self, query: str, chunks: List[DocumentChunk]) -> List[float]:
        """
        Score query-chunk pairs for relevance.
        
        Args:
            query: Search query
            chunks: List of chunks
            
        Returns:
            List of relevance scores
        """
        pass
    
    @abstractmethod
    def load_model(self, model_path: str) -> bool:
        """
        Load reranking model.
        
        Args:
            model_path: Path to model file
            
        Returns:
            True if model loaded successfully
        """
        pass
