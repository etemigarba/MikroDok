"""
Module: index_optimizer_lg
Description: Optimizes vector indices (FLAT, IVF, HNSW) for performance based on collection size
Phase: 4
Location: /src/modules/logic/vector_search_lg/index_optimizer_lg/
"""

# Standard library imports
import time
import threading
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import math

# Third-party imports
import numpy as np

# Local imports
from ..base_interfaces import (
    IIndexOptimizer,
    IndexOptimizationResult,
    IndexStatistics,
    IndexType,
    OptimizationConfig,
    OptimizationStrategy,
    VectorSearchStatus
)
from ...logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


@dataclass
class OptimizationMetrics:
    """Metrics for evaluating optimization performance."""
    search_latency_ms: float
    memory_usage_mb: float
    build_time_ms: float
    accuracy_score: float
    throughput_qps: float


class FlatIndexOptimizer:
    """Optimizer for flat (brute-force) vector indices."""
    
    def __init__(self):
        """Initialize flat index optimizer."""
        self._logger = get_logger(__name__)
    
    def optimize(self, vectors: np.ndarray, config: OptimizationConfig) -> OptimizationMetrics:
        """
        Optimize flat index configuration.
        
        Args:
            vectors: Array of vectors to optimize for
            config: Optimization configuration
            
        Returns:
            OptimizationMetrics with performance estimates
        """
        try:
            vector_count, vector_dim = vectors.shape
            
            # Flat index is simple - optimization focuses on memory layout
            memory_usage = self._estimate_memory_usage(vector_count, vector_dim)
            search_latency = self._estimate_search_latency(vector_count, vector_dim)
            build_time = self._estimate_build_time(vector_count, vector_dim)
            
            # Flat index has perfect accuracy
            accuracy_score = 1.0
            
            # Throughput is inversely related to search latency
            throughput_qps = 1000.0 / max(search_latency, 1.0)
            
            return OptimizationMetrics(
                search_latency_ms=search_latency,
                memory_usage_mb=memory_usage,
                build_time_ms=build_time,
                accuracy_score=accuracy_score,
                throughput_qps=throughput_qps
            )
            
        except Exception as e:
            self._logger.error(f"Error optimizing flat index: {e}")
            return OptimizationMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
    
    def _estimate_memory_usage(self, vector_count: int, vector_dim: int) -> float:
        """Estimate memory usage for flat index."""
        # Vector storage + minimal overhead
        vector_storage = vector_count * vector_dim * 4  # float32
        overhead = vector_storage * 0.05  # 5% overhead
        return (vector_storage + overhead) / (1024 * 1024)
    
    def _estimate_search_latency(self, vector_count: int, vector_dim: int) -> float:
        """Estimate search latency for flat index."""
        # Linear search complexity O(n*d)
        base_latency = 0.001  # Base latency per vector comparison
        return base_latency * vector_count * math.log(vector_dim)
    
    def _estimate_build_time(self, vector_count: int, vector_dim: int) -> float:
        """Estimate build time for flat index."""
        # Flat index has minimal build time
        return vector_count * 0.001  # 1 microsecond per vector


class IVFIndexOptimizer:
    """Optimizer for Inverted File (IVF) vector indices."""
    
    def __init__(self):
        """Initialize IVF index optimizer."""
        self._logger = get_logger(__name__)
    
    def optimize(self, vectors: np.ndarray, config: OptimizationConfig) -> Tuple[OptimizationMetrics, Dict[str, Any]]:
        """
        Optimize IVF index configuration.
        
        Args:
            vectors: Array of vectors to optimize for
            config: Optimization configuration
            
        Returns:
            Tuple of OptimizationMetrics and optimal parameters
        """
        try:
            vector_count, vector_dim = vectors.shape
            
            # Determine optimal number of clusters
            optimal_clusters = self._calculate_optimal_clusters(vector_count, config)
            
            # Estimate performance metrics
            memory_usage = self._estimate_memory_usage(vector_count, vector_dim, optimal_clusters)
            search_latency = self._estimate_search_latency(vector_count, vector_dim, optimal_clusters)
            build_time = self._estimate_build_time(vector_count, vector_dim, optimal_clusters)
            
            # IVF has slight accuracy loss due to clustering
            accuracy_score = self._estimate_accuracy(optimal_clusters, vector_count)
            
            # Throughput calculation
            throughput_qps = 1000.0 / max(search_latency, 1.0)
            
            optimal_params = {
                "n_clusters": optimal_clusters,
                "probe_clusters": max(1, optimal_clusters // 10),
                "cluster_assignment_method": "kmeans"
            }
            
            metrics = OptimizationMetrics(
                search_latency_ms=search_latency,
                memory_usage_mb=memory_usage,
                build_time_ms=build_time,
                accuracy_score=accuracy_score,
                throughput_qps=throughput_qps
            )
            
            return metrics, optimal_params
            
        except Exception as e:
            self._logger.error(f"Error optimizing IVF index: {e}")
            return OptimizationMetrics(0.0, 0.0, 0.0, 0.0, 0.0), {}
    
    def _calculate_optimal_clusters(self, vector_count: int, config: OptimizationConfig) -> int:
        """Calculate optimal number of clusters for IVF index."""
        if config.optimization_strategy == OptimizationStrategy.SPEED_OPTIMIZED:
            # More clusters for faster search
            return min(int(math.sqrt(vector_count) * 2), vector_count // 10)
        elif config.optimization_strategy == OptimizationStrategy.MEMORY_OPTIMIZED:
            # Fewer clusters to save memory
            return min(int(math.sqrt(vector_count) * 0.5), vector_count // 20)
        elif config.optimization_strategy == OptimizationStrategy.ACCURACY_OPTIMIZED:
            # Moderate clusters for better accuracy
            return min(int(math.sqrt(vector_count)), vector_count // 15)
        else:  # BALANCED
            return min(int(math.sqrt(vector_count)), vector_count // 12)
    
    def _estimate_memory_usage(self, vector_count: int, vector_dim: int, n_clusters: int) -> float:
        """Estimate memory usage for IVF index."""
        # Vector storage + cluster centers + inverted lists
        vector_storage = vector_count * vector_dim * 4  # float32
        cluster_centers = n_clusters * vector_dim * 4
        inverted_lists_overhead = vector_count * 8  # Pointers and metadata
        
        total_bytes = vector_storage + cluster_centers + inverted_lists_overhead
        return total_bytes / (1024 * 1024)
    
    def _estimate_search_latency(self, vector_count: int, vector_dim: int, n_clusters: int) -> float:
        """Estimate search latency for IVF index."""
        # Cluster selection + search within clusters
        cluster_search_time = n_clusters * 0.001  # Time to find nearest clusters
        avg_cluster_size = vector_count / n_clusters
        probe_clusters = max(1, n_clusters // 10)
        within_cluster_search = probe_clusters * avg_cluster_size * 0.0001
        
        return cluster_search_time + within_cluster_search
    
    def _estimate_build_time(self, vector_count: int, vector_dim: int, n_clusters: int) -> float:
        """Estimate build time for IVF index."""
        # K-means clustering + assignment
        kmeans_time = vector_count * vector_dim * n_clusters * 0.001
        assignment_time = vector_count * 0.01
        return kmeans_time + assignment_time
    
    def _estimate_accuracy(self, n_clusters: int, vector_count: int) -> float:
        """Estimate accuracy for IVF index."""
        # Accuracy decreases with more aggressive clustering
        cluster_ratio = n_clusters / vector_count
        if cluster_ratio > 0.1:
            return 0.99  # High accuracy with many clusters
        elif cluster_ratio > 0.05:
            return 0.95  # Good accuracy
        elif cluster_ratio > 0.01:
            return 0.90  # Moderate accuracy
        else:
            return 0.85  # Lower accuracy with few clusters


class HNSWIndexOptimizer:
    """Optimizer for Hierarchical Navigable Small World (HNSW) indices."""
    
    def __init__(self):
        """Initialize HNSW index optimizer."""
        self._logger = get_logger(__name__)
    
    def optimize(self, vectors: np.ndarray, config: OptimizationConfig) -> Tuple[OptimizationMetrics, Dict[str, Any]]:
        """
        Optimize HNSW index configuration.
        
        Args:
            vectors: Array of vectors to optimize for
            config: Optimization configuration
            
        Returns:
            Tuple of OptimizationMetrics and optimal parameters
        """
        try:
            vector_count, vector_dim = vectors.shape
            
            # Determine optimal HNSW parameters
            optimal_params = self._calculate_optimal_params(vector_count, config)
            
            # Estimate performance metrics
            memory_usage = self._estimate_memory_usage(vector_count, vector_dim, optimal_params)
            search_latency = self._estimate_search_latency(vector_count, optimal_params)
            build_time = self._estimate_build_time(vector_count, vector_dim, optimal_params)
            
            # HNSW has good accuracy with proper parameters
            accuracy_score = self._estimate_accuracy(optimal_params)
            
            # Throughput calculation
            throughput_qps = 1000.0 / max(search_latency, 1.0)
            
            metrics = OptimizationMetrics(
                search_latency_ms=search_latency,
                memory_usage_mb=memory_usage,
                build_time_ms=build_time,
                accuracy_score=accuracy_score,
                throughput_qps=throughput_qps
            )
            
            return metrics, optimal_params
            
        except Exception as e:
            self._logger.error(f"Error optimizing HNSW index: {e}")
            return OptimizationMetrics(0.0, 0.0, 0.0, 0.0, 0.0), {}
    
    def _calculate_optimal_params(self, vector_count: int, config: OptimizationConfig) -> Dict[str, Any]:
        """Calculate optimal HNSW parameters."""
        if config.optimization_strategy == OptimizationStrategy.SPEED_OPTIMIZED:
            return {
                "max_connections": 32,
                "ef_construction": 400,
                "ef_search": 100,
                "ml": 1.0 / math.log(2.0)
            }
        elif config.optimization_strategy == OptimizationStrategy.MEMORY_OPTIMIZED:
            return {
                "max_connections": 8,
                "ef_construction": 100,
                "ef_search": 50,
                "ml": 1.0 / math.log(2.0)
            }
        elif config.optimization_strategy == OptimizationStrategy.ACCURACY_OPTIMIZED:
            return {
                "max_connections": 48,
                "ef_construction": 800,
                "ef_search": 200,
                "ml": 1.0 / math.log(2.0)
            }
        else:  # BALANCED
            return {
                "max_connections": 16,
                "ef_construction": 200,
                "ef_search": 50,
                "ml": 1.0 / math.log(2.0)
            }
    
    def _estimate_memory_usage(self, vector_count: int, vector_dim: int, params: Dict[str, Any]) -> float:
        """Estimate memory usage for HNSW index."""
        # Vector storage + graph structure
        vector_storage = vector_count * vector_dim * 4  # float32
        
        # Graph connections (bidirectional)
        max_connections = params["max_connections"]
        avg_connections = max_connections * 0.7  # Not all nodes have max connections
        graph_storage = vector_count * avg_connections * 8  # 8 bytes per connection
        
        # Layer structure overhead
        layer_overhead = vector_count * 16  # Metadata per node
        
        total_bytes = vector_storage + graph_storage + layer_overhead
        return total_bytes / (1024 * 1024)
    
    def _estimate_search_latency(self, vector_count: int, params: Dict[str, Any]) -> float:
        """Estimate search latency for HNSW index."""
        # Logarithmic search complexity
        ef_search = params["ef_search"]
        search_complexity = math.log(vector_count) * ef_search
        base_latency = 0.0001  # Base latency per comparison
        
        return search_complexity * base_latency
    
    def _estimate_build_time(self, vector_count: int, vector_dim: int, params: Dict[str, Any]) -> float:
        """Estimate build time for HNSW index."""
        # Build time depends on ef_construction and connections
        ef_construction = params["ef_construction"]
        max_connections = params["max_connections"]
        
        # Each insertion requires searching and connecting
        insertion_complexity = math.log(vector_count) * ef_construction * max_connections
        base_time = 0.001  # Base time per operation
        
        return vector_count * insertion_complexity * base_time
    
    def _estimate_accuracy(self, params: Dict[str, Any]) -> float:
        """Estimate accuracy for HNSW index."""
        # Accuracy depends on ef_search and max_connections
        ef_search = params["ef_search"]
        max_connections = params["max_connections"]
        
        # Higher ef_search and connections improve accuracy
        accuracy_factor = min(1.0, (ef_search * max_connections) / 1000.0)
        return 0.85 + (accuracy_factor * 0.14)  # Range: 0.85 to 0.99


class AdaptiveIndexOptimizer:
    """Adaptive optimizer that selects the best index type and parameters."""

    def __init__(self):
        """Initialize adaptive index optimizer."""
        self._logger = get_logger(__name__)
        self._flat_optimizer = FlatIndexOptimizer()
        self._ivf_optimizer = IVFIndexOptimizer()
        self._hnsw_optimizer = HNSWIndexOptimizer()

    def recommend_index_type(self, vector_count: int, vector_dimension: int,
                           query_patterns: Dict[str, Any], config: OptimizationConfig) -> IndexType:
        """
        Recommend optimal index type based on data characteristics.

        Args:
            vector_count: Number of vectors in the collection
            vector_dimension: Dimension of vectors
            query_patterns: Historical query patterns and performance data
            config: Optimization configuration

        Returns:
            Recommended IndexType
        """
        try:
            # Decision rules based on collection size and requirements
            if vector_count < 1000:
                # Small collections - flat index is efficient
                return IndexType.FLAT

            elif vector_count < 100000:
                # Medium collections - choose based on strategy
                if config.optimization_strategy == OptimizationStrategy.SPEED_OPTIMIZED:
                    return IndexType.HNSW
                elif config.optimization_strategy == OptimizationStrategy.MEMORY_OPTIMIZED:
                    return IndexType.IVF
                else:
                    return IndexType.IVF

            else:
                # Large collections - advanced indices required
                if config.optimization_strategy == OptimizationStrategy.ACCURACY_OPTIMIZED:
                    return IndexType.HNSW
                elif config.optimization_strategy == OptimizationStrategy.MEMORY_OPTIMIZED:
                    return IndexType.IVF
                else:
                    return IndexType.HNSW

        except Exception as e:
            self._logger.error(f"Error recommending index type: {e}")
            return IndexType.FLAT

    def compare_index_types(self, vectors: np.ndarray,
                          config: OptimizationConfig) -> Dict[IndexType, OptimizationMetrics]:
        """
        Compare performance of different index types.

        Args:
            vectors: Array of vectors to analyze
            config: Optimization configuration

        Returns:
            Dictionary mapping index types to their performance metrics
        """
        try:
            results = {}

            # Evaluate flat index
            flat_metrics = self._flat_optimizer.optimize(vectors, config)
            results[IndexType.FLAT] = flat_metrics

            # Evaluate IVF index
            ivf_metrics, _ = self._ivf_optimizer.optimize(vectors, config)
            results[IndexType.IVF] = ivf_metrics

            # Evaluate HNSW index
            hnsw_metrics, _ = self._hnsw_optimizer.optimize(vectors, config)
            results[IndexType.HNSW] = hnsw_metrics

            return results

        except Exception as e:
            self._logger.error(f"Error comparing index types: {e}")
            return {}


class IndexOptimizer(IIndexOptimizer):
    """
    Main index optimizer that supports multiple index types and optimization strategies.
    Provides comprehensive optimization analysis and recommendations.
    """

    def __init__(self):
        """Initialize index optimizer with all supported optimizers."""
        self._logger = get_logger(__name__)
        self._lock = threading.RLock()

        # Initialize specialized optimizers
        self._flat_optimizer = FlatIndexOptimizer()
        self._ivf_optimizer = IVFIndexOptimizer()
        self._hnsw_optimizer = HNSWIndexOptimizer()
        self._adaptive_optimizer = AdaptiveIndexOptimizer()

        # Supported strategies
        self._supported_strategies = [
            OptimizationStrategy.SPEED_OPTIMIZED,
            OptimizationStrategy.MEMORY_OPTIMIZED,
            OptimizationStrategy.BALANCED,
            OptimizationStrategy.ACCURACY_OPTIMIZED
        ]

        self._logger.info("IndexOptimizer initialized successfully")

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
        start_time = time.time()

        try:
            with self._lock:
                config = config or OptimizationConfig()

                # Validate inputs
                if len(vectors.shape) != 2:
                    raise ValueError(f"Expected 2D vector array, got {len(vectors.shape)}D")

                vector_count, vector_dim = vectors.shape

                if vector_count == 0:
                    raise ValueError("Cannot optimize empty vector collection")

                # Get current performance baseline
                current_metrics = self._get_current_metrics(vectors, current_index_type, config)

                # Determine optimal index type
                if config.target_index_type:
                    optimal_index_type = config.target_index_type
                else:
                    optimal_index_type = self._adaptive_optimizer.recommend_index_type(
                        vector_count, vector_dim, {}, config
                    )

                # Get optimized performance metrics
                optimized_metrics = self._get_optimized_metrics(vectors, optimal_index_type, config)

                # Calculate improvements
                performance_improvement = self._calculate_performance_improvement(
                    current_metrics, optimized_metrics
                )
                memory_reduction = self._calculate_memory_reduction(
                    current_metrics, optimized_metrics
                )

                optimization_time = (time.time() - start_time) * 1000

                # Create index statistics
                statistics = IndexStatistics(
                    index_type=optimal_index_type,
                    total_vectors=vector_count,
                    index_size_bytes=int(optimized_metrics.memory_usage_mb * 1024 * 1024),
                    build_time_ms=optimized_metrics.build_time_ms,
                    average_search_time_ms=optimized_metrics.search_latency_ms,
                    memory_usage_mb=optimized_metrics.memory_usage_mb,
                    accuracy_score=optimized_metrics.accuracy_score
                )

                return IndexOptimizationResult(
                    status=VectorSearchStatus.COMPLETED,
                    original_index_type=current_index_type,
                    optimized_index_type=optimal_index_type,
                    optimization_strategy=config.optimization_strategy,
                    performance_improvement=performance_improvement,
                    memory_reduction=memory_reduction,
                    optimization_time_ms=optimization_time,
                    statistics=statistics,
                    metadata={
                        "vector_count": vector_count,
                        "vector_dimension": vector_dim,
                        "current_metrics": current_metrics.__dict__,
                        "optimized_metrics": optimized_metrics.__dict__
                    }
                )

        except Exception as e:
            self._logger.error(f"Error optimizing index: {e}")
            optimization_time = (time.time() - start_time) * 1000

            return IndexOptimizationResult(
                status=VectorSearchStatus.FAILED,
                original_index_type=current_index_type,
                optimized_index_type=current_index_type,
                optimization_strategy=config.optimization_strategy if config else OptimizationStrategy.BALANCED,
                performance_improvement=0.0,
                memory_reduction=0.0,
                optimization_time_ms=optimization_time,
                metadata={"error": str(e)}
            )

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
        try:
            with self._lock:
                config = OptimizationConfig()  # Use default configuration
                return self._adaptive_optimizer.recommend_index_type(
                    vector_count, vector_dimension, query_patterns, config
                )

        except Exception as e:
            self._logger.error(f"Error recommending index type: {e}")
            return IndexType.FLAT

    def estimate_performance(self, vectors: np.ndarray, index_type: IndexType) -> IndexStatistics:
        """
        Estimate performance metrics for a given index type.

        Args:
            vectors: Array of vectors to analyze
            index_type: Index type to estimate performance for

        Returns:
            Estimated IndexStatistics
        """
        try:
            with self._lock:
                config = OptimizationConfig()
                metrics = self._get_optimized_metrics(vectors, index_type, config)

                vector_count = vectors.shape[0]

                return IndexStatistics(
                    index_type=index_type,
                    total_vectors=vector_count,
                    index_size_bytes=int(metrics.memory_usage_mb * 1024 * 1024),
                    build_time_ms=metrics.build_time_ms,
                    average_search_time_ms=metrics.search_latency_ms,
                    memory_usage_mb=metrics.memory_usage_mb,
                    accuracy_score=metrics.accuracy_score
                )

        except Exception as e:
            self._logger.error(f"Error estimating performance: {e}")
            return IndexStatistics(
                index_type=index_type,
                total_vectors=0,
                index_size_bytes=0,
                build_time_ms=0.0,
                average_search_time_ms=0.0,
                memory_usage_mb=0.0
            )

    def get_optimization_strategies(self) -> List[OptimizationStrategy]:
        """
        Get list of supported optimization strategies.

        Returns:
            List of supported OptimizationStrategy enums
        """
        return self._supported_strategies.copy()

    def _get_current_metrics(self, vectors: np.ndarray, index_type: IndexType,
                           config: OptimizationConfig) -> OptimizationMetrics:
        """Get performance metrics for current index type."""
        return self._get_optimized_metrics(vectors, index_type, config)

    def _get_optimized_metrics(self, vectors: np.ndarray, index_type: IndexType,
                             config: OptimizationConfig) -> OptimizationMetrics:
        """Get optimized performance metrics for specified index type."""
        try:
            if index_type == IndexType.FLAT:
                return self._flat_optimizer.optimize(vectors, config)
            elif index_type == IndexType.IVF:
                metrics, _ = self._ivf_optimizer.optimize(vectors, config)
                return metrics
            elif index_type == IndexType.HNSW:
                metrics, _ = self._hnsw_optimizer.optimize(vectors, config)
                return metrics
            else:
                # Fallback to flat index
                return self._flat_optimizer.optimize(vectors, config)

        except Exception as e:
            self._logger.error(f"Error getting optimized metrics: {e}")
            return OptimizationMetrics(0.0, 0.0, 0.0, 0.0, 0.0)

    def _calculate_performance_improvement(self, current: OptimizationMetrics,
                                         optimized: OptimizationMetrics) -> float:
        """Calculate performance improvement percentage."""
        try:
            if current.search_latency_ms == 0:
                return 0.0

            improvement = (current.search_latency_ms - optimized.search_latency_ms) / current.search_latency_ms
            return max(0.0, improvement * 100.0)

        except Exception:
            return 0.0

    def _calculate_memory_reduction(self, current: OptimizationMetrics,
                                  optimized: OptimizationMetrics) -> float:
        """Calculate memory reduction percentage."""
        try:
            if current.memory_usage_mb == 0:
                return 0.0

            reduction = (current.memory_usage_mb - optimized.memory_usage_mb) / current.memory_usage_mb
            return max(0.0, reduction * 100.0)

        except Exception:
            return 0.0
