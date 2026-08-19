"""
Base interfaces and data structures for vector search functionality.
Provides abstract base classes and common data structures for similarity calculation, KNN search, and index optimization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple, Union
import numpy as np


class SimilarityMetric(Enum):
    """Supported similarity metrics for vector comparison."""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"
    MANHATTAN = "manhattan"
    JACCARD = "jaccard"


class IndexType(Enum):
    """Supported vector index types for optimization."""
    FLAT = "flat"
    IVF = "ivf"
    HNSW = "hnsw"
    LSH = "lsh"
    ANNOY = "annoy"


class VectorSearchStatus(Enum):
    """Status of vector search operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OptimizationStrategy(Enum):
    """Index optimization strategies."""
    SPEED_OPTIMIZED = "speed_optimized"
    MEMORY_OPTIMIZED = "memory_optimized"
    BALANCED = "balanced"
    ACCURACY_OPTIMIZED = "accuracy_optimized"


@dataclass
class SearchResultItem:
    """Individual search result item."""
    chunk_id: str
    document_id: str
    similarity_score: float
    vector: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_preview: Optional[str] = None
    position_in_document: Optional[int] = None


@dataclass
class SimilarityResult:
    """Result of similarity calculation operation."""
    similarity_score: float
    metric_used: SimilarityMetric
    vector1_id: str
    vector2_id: str
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KNNSearchResult:
    """Result of K-nearest neighbor search operation."""
    status: VectorSearchStatus
    query_vector_id: str
    k_requested: int
    results: List[SearchResultItem] = field(default_factory=list)
    total_candidates: int = 0
    search_time_ms: float = 0.0
    index_type_used: Optional[IndexType] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexStatistics:
    """Statistics about vector index performance."""
    index_type: IndexType
    total_vectors: int
    index_size_bytes: int
    build_time_ms: float
    average_search_time_ms: float
    memory_usage_mb: float
    accuracy_score: float = 1.0
    last_optimized: Optional[datetime] = None


@dataclass
class IndexOptimizationResult:
    """Result of index optimization operation."""
    status: VectorSearchStatus
    original_index_type: IndexType
    optimized_index_type: IndexType
    optimization_strategy: OptimizationStrategy
    performance_improvement: float
    memory_reduction: float
    optimization_time_ms: float = 0.0
    statistics: Optional[IndexStatistics] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchConfig:
    """Configuration for vector search operations."""
    similarity_metric: SimilarityMetric = SimilarityMetric.COSINE
    k: int = 10
    similarity_threshold: float = 0.0
    max_candidates: int = 10000
    enable_filtering: bool = True
    return_vectors: bool = False
    include_metadata: bool = True
    timeout_seconds: int = 30


@dataclass
class OptimizationConfig:
    """Configuration for index optimization."""
    target_index_type: Optional[IndexType] = None
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    max_memory_mb: int = 1024
    target_accuracy: float = 0.95
    enable_auto_optimization: bool = True
    optimization_interval_hours: int = 24
    min_vectors_for_optimization: int = 1000


class ISimilarityCalculator(ABC):
    """Base interface for similarity calculation implementations."""
    
    @abstractmethod
    def calculate_similarity(self, vector1: np.ndarray, vector2: np.ndarray, 
                           metric: SimilarityMetric = SimilarityMetric.COSINE) -> SimilarityResult:
        """
        Calculate similarity between two vectors.
        
        Args:
            vector1: First vector for comparison
            vector2: Second vector for comparison
            metric: Similarity metric to use
            
        Returns:
            SimilarityResult with similarity score and metadata
        """
        pass
    
    @abstractmethod
    def batch_calculate_similarity(self, query_vector: np.ndarray, 
                                 candidate_vectors: np.ndarray,
                                 metric: SimilarityMetric = SimilarityMetric.COSINE) -> List[float]:
        """
        Calculate similarity between query vector and multiple candidates.
        
        Args:
            query_vector: Query vector
            candidate_vectors: Array of candidate vectors
            metric: Similarity metric to use
            
        Returns:
            List of similarity scores
        """
        pass
    
    @abstractmethod
    def get_supported_metrics(self) -> List[SimilarityMetric]:
        """
        Get list of supported similarity metrics.
        
        Returns:
            List of supported SimilarityMetric enums
        """
        pass


class IKNNSearch(ABC):
    """Base interface for K-nearest neighbor search implementations."""
    
    @abstractmethod
    def search(self, query_vector: np.ndarray, k: int, 
               config: Optional[SearchConfig] = None) -> KNNSearchResult:
        """
        Perform K-nearest neighbor search.
        
        Args:
            query_vector: Query vector to search for
            k: Number of nearest neighbors to return
            config: Optional search configuration
            
        Returns:
            KNNSearchResult with search results and metadata
        """
        pass
    
    @abstractmethod
    def add_vectors(self, vectors: np.ndarray, vector_ids: List[str], 
                   metadata: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Add vectors to the search index.
        
        Args:
            vectors: Array of vectors to add
            vector_ids: Unique identifiers for each vector
            metadata: Optional metadata for each vector
            
        Returns:
            True if successfully added, False otherwise
        """
        pass
    
    @abstractmethod
    def remove_vectors(self, vector_ids: List[str]) -> bool:
        """
        Remove vectors from the search index.
        
        Args:
            vector_ids: List of vector IDs to remove
            
        Returns:
            True if successfully removed, False otherwise
        """
        pass
    
    @abstractmethod
    def get_index_statistics(self) -> IndexStatistics:
        """
        Get statistics about the current index.
        
        Returns:
            IndexStatistics with performance metrics
        """
        pass


class IIndexOptimizer(ABC):
    """Base interface for vector index optimization implementations."""
    
    @abstractmethod
    def optimize_index(self, vectors: np.ndarray, current_index_type: IndexType,
                      config: Optional[OptimizationConfig] = None) -> IndexOptimizationResult:
        """
        Optimize vector index for better performance.
        
        Args:
            vectors: Array of vectors in the index
            current_index_type: Current index type
            config: Optional optimization configuration
            
        Returns:
            IndexOptimizationResult with optimization details
        """
        pass
    
    @abstractmethod
    def recommend_index_type(self, vector_count: int, vector_dimension: int,
                           query_patterns: Dict[str, Any]) -> IndexType:
        """
        Recommend optimal index type based on data characteristics.
        
        Args:
            vector_count: Number of vectors in the collection
            vector_dimension: Dimension of vectors
            query_patterns: Historical query patterns and performance data
            
        Returns:
            Recommended IndexType
        """
        pass
    
    @abstractmethod
    def estimate_performance(self, vectors: np.ndarray, index_type: IndexType) -> IndexStatistics:
        """
        Estimate performance metrics for a given index type.
        
        Args:
            vectors: Array of vectors to analyze
            index_type: Index type to estimate performance for
            
        Returns:
            Estimated IndexStatistics
        """
        pass
    
    @abstractmethod
    def get_optimization_strategies(self) -> List[OptimizationStrategy]:
        """
        Get list of supported optimization strategies.
        
        Returns:
            List of supported OptimizationStrategy enums
        """
        pass
