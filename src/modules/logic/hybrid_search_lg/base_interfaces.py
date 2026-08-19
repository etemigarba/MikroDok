"""
Base interfaces and data structures for hybrid search functionality.
Provides abstract base classes and common data structures for semantic search, keyword search, and result fusion.
Phase: 4
Location: /src/modules/logic/hybrid_search_lg/
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple, Union
import numpy as np


class SearchType(Enum):
    """Types of search operations."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class FusionStrategy(Enum):
    """Strategies for combining search results."""
    WEIGHTED_SUM = "weighted_sum"
    RANK_FUSION = "rank_fusion"
    RECIPROCAL_RANK_FUSION = "reciprocal_rank_fusion"
    BORDA_COUNT = "borda_count"
    CONDORCET = "condorcet"
    LINEAR_COMBINATION = "linear_combination"


class SearchStatus(Enum):
    """Status of search operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RankingMethod(Enum):
    """Methods for ranking search results."""
    SCORE_BASED = "score_based"
    POSITION_BASED = "position_based"
    HYBRID_RANKING = "hybrid_ranking"
    RELEVANCE_FEEDBACK = "relevance_feedback"


@dataclass
class SearchResultItem:
    """Individual search result item with comprehensive metadata."""
    chunk_id: str
    document_id: str
    score: float
    content: str
    search_type: SearchType
    rank: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_preview: Optional[str] = None
    position_in_document: Optional[int] = None
    relevance_score: float = 0.0
    confidence: float = 1.0
    source_path: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class SemanticSearchResult:
    """Result of semantic search operation."""
    status: SearchStatus
    query: str
    query_vector: Optional[np.ndarray] = None
    results: List[SearchResultItem] = field(default_factory=list)
    total_candidates: int = 0
    search_time_ms: float = 0.0
    similarity_threshold: float = 0.0
    vector_dimension: int = 0
    model_used: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KeywordSearchResult:
    """Result of keyword search operation."""
    status: SearchStatus
    query: str
    query_terms: List[str] = field(default_factory=list)
    results: List[SearchResultItem] = field(default_factory=list)
    total_documents: int = 0
    search_time_ms: float = 0.0
    algorithm_used: str = "BM25"
    term_frequencies: Dict[str, int] = field(default_factory=dict)
    document_frequencies: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridSearchResult:
    """Result of hybrid search operation combining semantic and keyword results."""
    status: SearchStatus
    query: str
    fusion_strategy: FusionStrategy
    semantic_results: Optional[SemanticSearchResult] = None
    keyword_results: Optional[KeywordSearchResult] = None
    fused_results: List[SearchResultItem] = field(default_factory=list)
    total_search_time_ms: float = 0.0
    fusion_time_ms: float = 0.0
    semantic_weight: float = 0.5
    keyword_weight: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticSearchConfig:
    """Configuration for semantic search operations."""
    similarity_threshold: float = 0.0
    max_results: int = 100
    vector_dimension: int = 384
    similarity_metric: str = "cosine"
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    enable_reranking: bool = False
    reranking_top_k: int = 50
    include_metadata: bool = True
    timeout_seconds: int = 30


@dataclass
class KeywordSearchConfig:
    """Configuration for keyword search operations."""
    algorithm: str = "BM25"
    k1: float = 1.2  # BM25 term frequency saturation parameter
    b: float = 0.75  # BM25 length normalization parameter
    max_results: int = 100
    min_term_length: int = 2
    enable_stemming: bool = True
    enable_stopword_removal: bool = True
    case_sensitive: bool = False
    fuzzy_matching: bool = False
    fuzzy_threshold: float = 0.8
    timeout_seconds: int = 30


@dataclass
class FusionConfig:
    """Configuration for result fusion operations."""
    strategy: FusionStrategy = FusionStrategy.WEIGHTED_SUM
    semantic_weight: float = 0.5
    keyword_weight: float = 0.5
    max_results: int = 50
    score_normalization: bool = True
    rank_normalization: bool = True
    diversity_factor: float = 0.0
    relevance_threshold: float = 0.0
    enable_score_calibration: bool = False
    calibration_method: str = "min_max"


@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search operations."""
    search_types: List[SearchType] = field(default_factory=lambda: [SearchType.SEMANTIC, SearchType.KEYWORD])
    semantic_config: SemanticSearchConfig = field(default_factory=SemanticSearchConfig)
    keyword_config: KeywordSearchConfig = field(default_factory=KeywordSearchConfig)
    fusion_config: FusionConfig = field(default_factory=FusionConfig)
    enable_parallel_search: bool = True
    timeout_seconds: int = 60
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600


class ISemanticSearcher(ABC):
    """Base interface for semantic search implementations."""
    
    @abstractmethod
    def search(self, query: str, config: Optional[SemanticSearchConfig] = None) -> SemanticSearchResult:
        """
        Perform semantic search using vector embeddings.
        
        Args:
            query: Search query string
            config: Optional search configuration
            
        Returns:
            SemanticSearchResult with search results and metadata
        """
        pass
    
    @abstractmethod
    def search_by_vector(self, query_vector: np.ndarray, 
                        config: Optional[SemanticSearchConfig] = None) -> SemanticSearchResult:
        """
        Perform semantic search using pre-computed query vector.
        
        Args:
            query_vector: Pre-computed query embedding vector
            config: Optional search configuration
            
        Returns:
            SemanticSearchResult with search results and metadata
        """
        pass
    
    @abstractmethod
    def get_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate embedding vector for query text.
        
        Args:
            query: Query text to embed
            
        Returns:
            Query embedding vector
        """
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """
        Get list of supported embedding models.
        
        Returns:
            List of supported model names
        """
        pass


class IKeywordSearcher(ABC):
    """Base interface for keyword search implementations."""
    
    @abstractmethod
    def search(self, query: str, config: Optional[KeywordSearchConfig] = None) -> KeywordSearchResult:
        """
        Perform keyword-based search using BM25 or similar algorithms.
        
        Args:
            query: Search query string
            config: Optional search configuration
            
        Returns:
            KeywordSearchResult with search results and metadata
        """
        pass
    
    @abstractmethod
    def build_index(self, documents: List[Dict[str, Any]]) -> bool:
        """
        Build inverted index for keyword search.
        
        Args:
            documents: List of documents to index
            
        Returns:
            True if index built successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def update_index(self, document: Dict[str, Any]) -> bool:
        """
        Update index with new document.
        
        Args:
            document: Document to add to index
            
        Returns:
            True if update successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_term_statistics(self, term: str) -> Dict[str, Any]:
        """
        Get statistics for a specific term.
        
        Args:
            term: Term to get statistics for
            
        Returns:
            Dictionary with term frequency, document frequency, etc.
        """
        pass


class IResultFusion(ABC):
    """Base interface for result fusion implementations."""
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get_supported_strategies(self) -> List[FusionStrategy]:
        """
        Get list of supported fusion strategies.
        
        Returns:
            List of supported FusionStrategy enums
        """
        pass
