"""
Module: similarity_calculator_lg
Description: Implements cosine similarity calculations for semantic search operations
Phase: 4
Location: /src/modules/logic/vector_search_lg/similarity_calculator_lg/
"""

# Standard library imports
import time
import logging
from typing import List, Optional, Dict, Any
import threading

# Third-party imports
import numpy as np
from scipy.spatial.distance import cosine, euclidean, cityblock
from scipy.stats import pearsonr

# Local imports
from ..base_interfaces import (
    ISimilarityCalculator,
    SimilarityResult,
    SimilarityMetric
)
from ...logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class CosineSimilarityCalculator:
    """Optimized cosine similarity calculator with vectorized operations."""
    
    def __init__(self):
        """Initialize cosine similarity calculator."""
        self._logger = get_logger(__name__)
    
    def calculate(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors using optimized computation.
        
        Args:
            vector1: First vector
            vector2: Second vector
            
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        try:
            # Normalize vectors for efficiency
            norm1 = np.linalg.norm(vector1)
            norm2 = np.linalg.norm(vector2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Calculate cosine similarity using dot product
            dot_product = np.dot(vector1, vector2)
            similarity = dot_product / (norm1 * norm2)
            
            # Ensure result is in valid range [0, 1]
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            self._logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def batch_calculate(self, query_vector: np.ndarray, candidate_vectors: np.ndarray) -> np.ndarray:
        """
        Calculate cosine similarity between query vector and multiple candidates.
        
        Args:
            query_vector: Query vector (1D array)
            candidate_vectors: Array of candidate vectors (2D array)
            
        Returns:
            Array of similarity scores
        """
        try:
            # Normalize query vector
            query_norm = np.linalg.norm(query_vector)
            if query_norm == 0:
                return np.zeros(candidate_vectors.shape[0])
            
            # Normalize candidate vectors
            candidate_norms = np.linalg.norm(candidate_vectors, axis=1)
            valid_candidates = candidate_norms > 0
            
            # Initialize result array
            similarities = np.zeros(candidate_vectors.shape[0])
            
            if np.any(valid_candidates):
                # Vectorized cosine similarity calculation
                dot_products = np.dot(candidate_vectors[valid_candidates], query_vector)
                similarities[valid_candidates] = dot_products / (
                    candidate_norms[valid_candidates] * query_norm
                )
                
                # Ensure results are in valid range [0, 1]
                similarities = np.clip(similarities, 0.0, 1.0)
            
            return similarities
            
        except Exception as e:
            self._logger.error(f"Error in batch cosine similarity calculation: {e}")
            return np.zeros(candidate_vectors.shape[0])


class EuclideanSimilarityCalculator:
    """Euclidean distance-based similarity calculator."""
    
    def __init__(self):
        """Initialize Euclidean similarity calculator."""
        self._logger = get_logger(__name__)
    
    def calculate(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate Euclidean similarity between two vectors.
        
        Args:
            vector1: First vector
            vector2: Second vector
            
        Returns:
            Euclidean similarity score (0.0 to 1.0)
        """
        try:
            # Calculate Euclidean distance
            distance = np.linalg.norm(vector1 - vector2)
            
            # Convert distance to similarity (inverse relationship)
            # Using exponential decay for better similarity distribution
            similarity = np.exp(-distance)
            
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            self._logger.error(f"Error calculating Euclidean similarity: {e}")
            return 0.0
    
    def batch_calculate(self, query_vector: np.ndarray, candidate_vectors: np.ndarray) -> np.ndarray:
        """
        Calculate Euclidean similarity between query vector and multiple candidates.
        
        Args:
            query_vector: Query vector (1D array)
            candidate_vectors: Array of candidate vectors (2D array)
            
        Returns:
            Array of similarity scores
        """
        try:
            # Vectorized Euclidean distance calculation
            distances = np.linalg.norm(candidate_vectors - query_vector, axis=1)
            
            # Convert distances to similarities
            similarities = np.exp(-distances)
            
            return np.clip(similarities, 0.0, 1.0)
            
        except Exception as e:
            self._logger.error(f"Error in batch Euclidean similarity calculation: {e}")
            return np.zeros(candidate_vectors.shape[0])


class DotProductSimilarityCalculator:
    """Dot product-based similarity calculator."""
    
    def __init__(self):
        """Initialize dot product similarity calculator."""
        self._logger = get_logger(__name__)
    
    def calculate(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate dot product similarity between two vectors.
        
        Args:
            vector1: First vector
            vector2: Second vector
            
        Returns:
            Normalized dot product similarity score (0.0 to 1.0)
        """
        try:
            # Calculate dot product
            dot_product = np.dot(vector1, vector2)
            
            # Normalize by vector magnitudes for better comparison
            norm1 = np.linalg.norm(vector1)
            norm2 = np.linalg.norm(vector2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Normalize dot product to [0, 1] range
            max_possible = norm1 * norm2
            normalized_similarity = (dot_product + max_possible) / (2 * max_possible)
            
            return max(0.0, min(1.0, normalized_similarity))
            
        except Exception as e:
            self._logger.error(f"Error calculating dot product similarity: {e}")
            return 0.0
    
    def batch_calculate(self, query_vector: np.ndarray, candidate_vectors: np.ndarray) -> np.ndarray:
        """
        Calculate dot product similarity between query vector and multiple candidates.
        
        Args:
            query_vector: Query vector (1D array)
            candidate_vectors: Array of candidate vectors (2D array)
            
        Returns:
            Array of similarity scores
        """
        try:
            # Vectorized dot product calculation
            dot_products = np.dot(candidate_vectors, query_vector)
            
            # Calculate norms for normalization
            query_norm = np.linalg.norm(query_vector)
            candidate_norms = np.linalg.norm(candidate_vectors, axis=1)
            
            if query_norm == 0:
                return np.zeros(candidate_vectors.shape[0])
            
            # Normalize dot products
            max_possibles = candidate_norms * query_norm
            valid_candidates = max_possibles > 0
            
            similarities = np.zeros(candidate_vectors.shape[0])
            similarities[valid_candidates] = (
                (dot_products[valid_candidates] + max_possibles[valid_candidates]) / 
                (2 * max_possibles[valid_candidates])
            )
            
            return np.clip(similarities, 0.0, 1.0)
            
        except Exception as e:
            self._logger.error(f"Error in batch dot product similarity calculation: {e}")
            return np.zeros(candidate_vectors.shape[0])


class SimilarityCalculator(ISimilarityCalculator):
    """
    Main similarity calculator that supports multiple similarity metrics.
    Provides thread-safe, optimized similarity calculations for vector search operations.
    """
    
    def __init__(self):
        """Initialize similarity calculator with all supported metrics."""
        self._logger = get_logger(__name__)
        self._lock = threading.RLock()
        
        # Initialize specialized calculators
        self._cosine_calculator = CosineSimilarityCalculator()
        self._euclidean_calculator = EuclideanSimilarityCalculator()
        self._dot_product_calculator = DotProductSimilarityCalculator()
        
        # Supported metrics
        self._supported_metrics = [
            SimilarityMetric.COSINE,
            SimilarityMetric.EUCLIDEAN,
            SimilarityMetric.DOT_PRODUCT,
            SimilarityMetric.MANHATTAN
        ]
        
        self._logger.info("SimilarityCalculator initialized successfully")
    
    def calculate_similarity(self, vector1: np.ndarray, vector2: np.ndarray,
                           metric: SimilarityMetric = SimilarityMetric.COSINE) -> SimilarityResult:
        """
        Calculate similarity between two vectors using specified metric.
        
        Args:
            vector1: First vector for comparison
            vector2: Second vector for comparison
            metric: Similarity metric to use
            
        Returns:
            SimilarityResult with similarity score and metadata
        """
        start_time = time.time()
        
        try:
            with self._lock:
                # Validate inputs
                if vector1.shape != vector2.shape:
                    raise ValueError(f"Vector shapes don't match: {vector1.shape} vs {vector2.shape}")
                
                if len(vector1.shape) != 1:
                    raise ValueError(f"Expected 1D vectors, got {len(vector1.shape)}D")
                
                # Calculate similarity based on metric
                if metric == SimilarityMetric.COSINE:
                    similarity_score = self._cosine_calculator.calculate(vector1, vector2)
                elif metric == SimilarityMetric.EUCLIDEAN:
                    similarity_score = self._euclidean_calculator.calculate(vector1, vector2)
                elif metric == SimilarityMetric.DOT_PRODUCT:
                    similarity_score = self._dot_product_calculator.calculate(vector1, vector2)
                elif metric == SimilarityMetric.MANHATTAN:
                    similarity_score = self._calculate_manhattan_similarity(vector1, vector2)
                else:
                    raise ValueError(f"Unsupported similarity metric: {metric}")
                
                processing_time = (time.time() - start_time) * 1000
                
                return SimilarityResult(
                    similarity_score=similarity_score,
                    metric_used=metric,
                    vector1_id="vector1",
                    vector2_id="vector2",
                    processing_time_ms=processing_time,
                    metadata={
                        "vector_dimension": vector1.shape[0],
                        "calculation_method": "optimized"
                    }
                )
                
        except Exception as e:
            self._logger.error(f"Error calculating similarity: {e}")
            processing_time = (time.time() - start_time) * 1000
            
            return SimilarityResult(
                similarity_score=0.0,
                metric_used=metric,
                vector1_id="vector1",
                vector2_id="vector2",
                processing_time_ms=processing_time,
                metadata={"error": str(e)}
            )

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
        try:
            with self._lock:
                # Validate inputs
                if len(query_vector.shape) != 1:
                    raise ValueError(f"Expected 1D query vector, got {len(query_vector.shape)}D")

                if len(candidate_vectors.shape) != 2:
                    raise ValueError(f"Expected 2D candidate array, got {len(candidate_vectors.shape)}D")

                if candidate_vectors.shape[1] != query_vector.shape[0]:
                    raise ValueError(f"Vector dimension mismatch: {candidate_vectors.shape[1]} vs {query_vector.shape[0]}")

                # Calculate similarities based on metric
                if metric == SimilarityMetric.COSINE:
                    similarities = self._cosine_calculator.batch_calculate(query_vector, candidate_vectors)
                elif metric == SimilarityMetric.EUCLIDEAN:
                    similarities = self._euclidean_calculator.batch_calculate(query_vector, candidate_vectors)
                elif metric == SimilarityMetric.DOT_PRODUCT:
                    similarities = self._dot_product_calculator.batch_calculate(query_vector, candidate_vectors)
                elif metric == SimilarityMetric.MANHATTAN:
                    similarities = self._batch_calculate_manhattan_similarity(query_vector, candidate_vectors)
                else:
                    raise ValueError(f"Unsupported similarity metric: {metric}")

                return similarities.tolist()

        except Exception as e:
            self._logger.error(f"Error in batch similarity calculation: {e}")
            return [0.0] * candidate_vectors.shape[0]

    def get_supported_metrics(self) -> List[SimilarityMetric]:
        """
        Get list of supported similarity metrics.

        Returns:
            List of supported SimilarityMetric enums
        """
        return self._supported_metrics.copy()

    def _calculate_manhattan_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate Manhattan (L1) distance-based similarity.

        Args:
            vector1: First vector
            vector2: Second vector

        Returns:
            Manhattan similarity score (0.0 to 1.0)
        """
        try:
            # Calculate Manhattan distance
            distance = np.sum(np.abs(vector1 - vector2))

            # Convert distance to similarity using exponential decay
            similarity = np.exp(-distance / len(vector1))

            return max(0.0, min(1.0, similarity))

        except Exception as e:
            self._logger.error(f"Error calculating Manhattan similarity: {e}")
            return 0.0

    def _batch_calculate_manhattan_similarity(self, query_vector: np.ndarray,
                                            candidate_vectors: np.ndarray) -> np.ndarray:
        """
        Calculate Manhattan similarity between query vector and multiple candidates.

        Args:
            query_vector: Query vector (1D array)
            candidate_vectors: Array of candidate vectors (2D array)

        Returns:
            Array of similarity scores
        """
        try:
            # Vectorized Manhattan distance calculation
            distances = np.sum(np.abs(candidate_vectors - query_vector), axis=1)

            # Convert distances to similarities
            similarities = np.exp(-distances / len(query_vector))

            return np.clip(similarities, 0.0, 1.0)

        except Exception as e:
            self._logger.error(f"Error in batch Manhattan similarity calculation: {e}")
            return np.zeros(candidate_vectors.shape[0])
