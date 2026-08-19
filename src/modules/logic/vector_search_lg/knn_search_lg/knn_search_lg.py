"""
Module: knn_search_lg
Description: K-nearest neighbor search implementation for finding similar document chunks
Phase: 4
Location: /src/modules/logic/vector_search_lg/knn_search_lg/
"""

# Standard library imports
import time
import heapq
import threading
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict

# Third-party imports
import numpy as np

# Lazy imports for sklearn to prevent scipy loading during app startup
_sklearn_neighbors = None
_sklearn_cluster = None

def _get_sklearn_neighbors():
    """Lazy import for sklearn.neighbors to prevent scipy loading during startup."""
    global _sklearn_neighbors
    if _sklearn_neighbors is None:
        try:
            from sklearn import neighbors
            _sklearn_neighbors = neighbors
        except ImportError:
            _sklearn_neighbors = False
    return _sklearn_neighbors

def _get_sklearn_cluster():
    """Lazy import for sklearn.cluster to prevent scipy loading during startup."""
    global _sklearn_cluster
    if _sklearn_cluster is None:
        try:
            from sklearn import cluster
            _sklearn_cluster = cluster
        except ImportError:
            _sklearn_cluster = False
    return _sklearn_cluster

# Local imports
from ..base_interfaces import (
    IKNNSearch,
    KNNSearchResult,
    SearchResultItem,
    SearchConfig,
    IndexStatistics,
    IndexType,
    VectorSearchStatus,
    SimilarityMetric
)
from ..similarity_calculator_lg.similarity_calculator_lg import SimilarityCalculator
from ...logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class SearchResultRanker:
    """Utility class for ranking and filtering search results."""
    
    def __init__(self):
        """Initialize search result ranker."""
        self._logger = get_logger(__name__)
    
    def rank_results(self, results: List[SearchResultItem], 
                    similarity_threshold: float = 0.0) -> List[SearchResultItem]:
        """
        Rank search results by similarity score and apply threshold filtering.
        
        Args:
            results: List of search results to rank
            similarity_threshold: Minimum similarity score threshold
            
        Returns:
            Ranked and filtered list of search results
        """
        try:
            # Filter by threshold
            filtered_results = [
                result for result in results 
                if result.similarity_score >= similarity_threshold
            ]
            
            # Sort by similarity score (descending)
            ranked_results = sorted(
                filtered_results,
                key=lambda x: x.similarity_score,
                reverse=True
            )
            
            return ranked_results
            
        except Exception as e:
            self._logger.error(f"Error ranking search results: {e}")
            return results
    
    def deduplicate_results(self, results: List[SearchResultItem],
                          similarity_threshold: float = 0.95) -> List[SearchResultItem]:
        """
        Remove duplicate results based on similarity threshold.
        
        Args:
            results: List of search results
            similarity_threshold: Threshold for considering results as duplicates
            
        Returns:
            Deduplicated list of search results
        """
        try:
            if not results:
                return results
            
            deduplicated = []
            seen_chunks = set()
            
            for result in results:
                # Simple deduplication by chunk_id
                if result.chunk_id not in seen_chunks:
                    deduplicated.append(result)
                    seen_chunks.add(result.chunk_id)
            
            return deduplicated
            
        except Exception as e:
            self._logger.error(f"Error deduplicating search results: {e}")
            return results


class FlatKNNSearch:
    """Flat (brute-force) KNN search implementation for small to medium datasets."""
    
    def __init__(self, similarity_calculator: Optional[SimilarityCalculator] = None):
        """Initialize flat KNN search."""
        self._logger = get_logger(__name__)
        self._similarity_calculator = similarity_calculator or SimilarityCalculator()
        self._vectors = None
        self._vector_ids = []
        self._metadata = []
        self._lock = threading.RLock()
    
    def add_vectors(self, vectors: np.ndarray, vector_ids: List[str],
                   metadata: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Add vectors to the flat index."""
        try:
            with self._lock:
                if self._vectors is None:
                    self._vectors = vectors.copy()
                    self._vector_ids = vector_ids.copy()
                    self._metadata = metadata.copy() if metadata else [{}] * len(vector_ids)
                else:
                    self._vectors = np.vstack([self._vectors, vectors])
                    self._vector_ids.extend(vector_ids)
                    if metadata:
                        self._metadata.extend(metadata)
                    else:
                        self._metadata.extend([{}] * len(vector_ids))
                
                return True
                
        except Exception as e:
            self._logger.error(f"Error adding vectors to flat index: {e}")
            return False
    
    def search(self, query_vector: np.ndarray, k: int,
              config: Optional[SearchConfig] = None) -> List[SearchResultItem]:
        """Perform flat KNN search."""
        try:
            with self._lock:
                if self._vectors is None or len(self._vectors) == 0:
                    return []
                
                config = config or SearchConfig()
                
                # Calculate similarities for all vectors
                similarities = self._similarity_calculator.batch_calculate_similarity(
                    query_vector, self._vectors, config.similarity_metric
                )
                
                # Create result items
                results = []
                for i, similarity in enumerate(similarities):
                    if similarity >= config.similarity_threshold:
                        result_item = SearchResultItem(
                            chunk_id=self._vector_ids[i],
                            document_id=self._metadata[i].get('document_id', 'unknown'),
                            similarity_score=similarity,
                            vector=self._vectors[i] if config.return_vectors else None,
                            metadata=self._metadata[i] if config.include_metadata else {},
                            content_preview=self._metadata[i].get('content_preview'),
                            position_in_document=self._metadata[i].get('position_in_document')
                        )
                        results.append(result_item)
                
                # Sort by similarity and return top k
                results.sort(key=lambda x: x.similarity_score, reverse=True)
                return results[:k]
                
        except Exception as e:
            self._logger.error(f"Error in flat KNN search: {e}")
            return []


class IVFKNNSearch:
    """Inverted File (IVF) KNN search implementation for large datasets."""
    
    def __init__(self, n_clusters: int = 100, 
                 similarity_calculator: Optional[SimilarityCalculator] = None):
        """Initialize IVF KNN search."""
        self._logger = get_logger(__name__)
        self._similarity_calculator = similarity_calculator or SimilarityCalculator()
        self._n_clusters = n_clusters
        self._kmeans = None
        self._cluster_vectors = defaultdict(list)
        self._cluster_ids = defaultdict(list)
        self._cluster_metadata = defaultdict(list)
        self._lock = threading.RLock()
        self._is_trained = False
    
    def add_vectors(self, vectors: np.ndarray, vector_ids: List[str],
                   metadata: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Add vectors to the IVF index."""
        try:
            with self._lock:
                if not self._is_trained:
                    # Train clustering model
                    self._train_clusters(vectors)
                
                # Assign vectors to clusters
                cluster_assignments = self._kmeans.predict(vectors)
                
                for i, cluster_id in enumerate(cluster_assignments):
                    self._cluster_vectors[cluster_id].append(vectors[i])
                    self._cluster_ids[cluster_id].append(vector_ids[i])
                    if metadata:
                        self._cluster_metadata[cluster_id].append(metadata[i])
                    else:
                        self._cluster_metadata[cluster_id].append({})
                
                return True
                
        except Exception as e:
            self._logger.error(f"Error adding vectors to IVF index: {e}")
            return False
    
    def search(self, query_vector: np.ndarray, k: int,
              config: Optional[SearchConfig] = None) -> List[SearchResultItem]:
        """Perform IVF KNN search."""
        try:
            with self._lock:
                if not self._is_trained:
                    return []
                
                config = config or SearchConfig()
                
                # Find nearest clusters
                cluster_distances = []
                for cluster_id, center in enumerate(self._kmeans.cluster_centers_):
                    distance = np.linalg.norm(query_vector - center)
                    cluster_distances.append((distance, cluster_id))
                
                # Sort clusters by distance and search top clusters
                cluster_distances.sort()
                n_clusters_to_search = min(max(1, self._n_clusters // 10), len(cluster_distances))
                
                all_results = []
                for _, cluster_id in cluster_distances[:n_clusters_to_search]:
                    if cluster_id in self._cluster_vectors:
                        cluster_vectors = np.array(self._cluster_vectors[cluster_id])
                        if len(cluster_vectors) > 0:
                            # Search within cluster
                            similarities = self._similarity_calculator.batch_calculate_similarity(
                                query_vector, cluster_vectors, config.similarity_metric
                            )
                            
                            for i, similarity in enumerate(similarities):
                                if similarity >= config.similarity_threshold:
                                    result_item = SearchResultItem(
                                        chunk_id=self._cluster_ids[cluster_id][i],
                                        document_id=self._cluster_metadata[cluster_id][i].get('document_id', 'unknown'),
                                        similarity_score=similarity,
                                        vector=cluster_vectors[i] if config.return_vectors else None,
                                        metadata=self._cluster_metadata[cluster_id][i] if config.include_metadata else {},
                                        content_preview=self._cluster_metadata[cluster_id][i].get('content_preview'),
                                        position_in_document=self._cluster_metadata[cluster_id][i].get('position_in_document')
                                    )
                                    all_results.append(result_item)
                
                # Sort by similarity and return top k
                all_results.sort(key=lambda x: x.similarity_score, reverse=True)
                return all_results[:k]
                
        except Exception as e:
            self._logger.error(f"Error in IVF KNN search: {e}")
            return []
    
    def _train_clusters(self, vectors: np.ndarray):
        """Train clustering model for IVF index."""
        try:
            sklearn_cluster = _get_sklearn_cluster()
            if sklearn_cluster is False:
                raise ImportError("sklearn.cluster not available")

            n_clusters = min(self._n_clusters, len(vectors))
            self._kmeans = sklearn_cluster.KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            self._kmeans.fit(vectors)
            self._is_trained = True
            self._logger.info(f"IVF clustering trained with {n_clusters} clusters")
            
        except Exception as e:
            self._logger.error(f"Error training IVF clusters: {e}")
            self._is_trained = False


class HNSWKNNSearch:
    """Hierarchical Navigable Small World (HNSW) KNN search implementation."""
    
    def __init__(self, similarity_calculator: Optional[SimilarityCalculator] = None):
        """Initialize HNSW KNN search."""
        self._logger = get_logger(__name__)
        self._similarity_calculator = similarity_calculator or SimilarityCalculator()
        self._vectors = []
        self._vector_ids = []
        self._metadata = []
        self._lock = threading.RLock()
        
        # HNSW parameters
        self._max_connections = 16
        self._ef_construction = 200
        self._ef_search = 50
        
        # Graph structure (simplified implementation)
        self._graph = defaultdict(list)
        self._entry_point = None
    
    def add_vectors(self, vectors: np.ndarray, vector_ids: List[str],
                   metadata: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Add vectors to the HNSW index."""
        try:
            with self._lock:
                start_idx = len(self._vectors)
                
                for i, vector in enumerate(vectors):
                    self._vectors.append(vector)
                    self._vector_ids.append(vector_ids[i])
                    if metadata:
                        self._metadata.append(metadata[i])
                    else:
                        self._metadata.append({})
                    
                    current_idx = start_idx + i
                    
                    # Simple graph construction (simplified HNSW)
                    if self._entry_point is None:
                        self._entry_point = current_idx
                    else:
                        # Connect to nearest existing vectors
                        self._connect_to_graph(current_idx, vector)
                
                return True
                
        except Exception as e:
            self._logger.error(f"Error adding vectors to HNSW index: {e}")
            return False

    def search(self, query_vector: np.ndarray, k: int,
              config: Optional[SearchConfig] = None) -> List[SearchResultItem]:
        """Perform HNSW KNN search."""
        try:
            with self._lock:
                if not self._vectors or self._entry_point is None:
                    return []

                config = config or SearchConfig()

                # Simplified HNSW search (greedy search from entry point)
                visited = set()
                candidates = []

                # Start from entry point
                entry_similarity = self._similarity_calculator.calculate_similarity(
                    query_vector, self._vectors[self._entry_point], config.similarity_metric
                ).similarity_score

                heapq.heappush(candidates, (-entry_similarity, self._entry_point))
                visited.add(self._entry_point)

                # Greedy search
                while candidates and len(visited) < min(self._ef_search, len(self._vectors)):
                    _, current_idx = heapq.heappop(candidates)

                    # Check neighbors
                    for neighbor_idx in self._graph.get(current_idx, []):
                        if neighbor_idx not in visited:
                            visited.add(neighbor_idx)
                            neighbor_similarity = self._similarity_calculator.calculate_similarity(
                                query_vector, self._vectors[neighbor_idx], config.similarity_metric
                            ).similarity_score

                            if neighbor_similarity >= config.similarity_threshold:
                                heapq.heappush(candidates, (-neighbor_similarity, neighbor_idx))

                # Create result items from best candidates
                results = []
                candidate_list = []

                while candidates:
                    neg_similarity, idx = heapq.heappop(candidates)
                    candidate_list.append((-neg_similarity, idx))

                # Sort by similarity and take top k
                candidate_list.sort(reverse=True)

                for similarity, idx in candidate_list[:k]:
                    result_item = SearchResultItem(
                        chunk_id=self._vector_ids[idx],
                        document_id=self._metadata[idx].get('document_id', 'unknown'),
                        similarity_score=similarity,
                        vector=self._vectors[idx] if config.return_vectors else None,
                        metadata=self._metadata[idx] if config.include_metadata else {},
                        content_preview=self._metadata[idx].get('content_preview'),
                        position_in_document=self._metadata[idx].get('position_in_document')
                    )
                    results.append(result_item)

                return results

        except Exception as e:
            self._logger.error(f"Error in HNSW KNN search: {e}")
            return []

    def _connect_to_graph(self, new_idx: int, new_vector: np.ndarray):
        """Connect new vector to the HNSW graph."""
        try:
            # Find nearest neighbors to connect to
            similarities = []
            for i, existing_vector in enumerate(self._vectors[:-1]):  # Exclude the new vector itself
                similarity = self._similarity_calculator.calculate_similarity(
                    new_vector, existing_vector, SimilarityMetric.COSINE
                ).similarity_score
                similarities.append((similarity, i))

            # Sort by similarity and connect to top neighbors
            similarities.sort(reverse=True)
            max_connections = min(self._max_connections, len(similarities))

            for similarity, neighbor_idx in similarities[:max_connections]:
                # Bidirectional connection
                self._graph[new_idx].append(neighbor_idx)
                self._graph[neighbor_idx].append(new_idx)

        except Exception as e:
            self._logger.error(f"Error connecting to HNSW graph: {e}")


class KNNSearch(IKNNSearch):
    """
    Main KNN search implementation that supports multiple index types.
    Automatically selects the best search algorithm based on data size and configuration.
    """

    def __init__(self, index_type: IndexType = IndexType.FLAT,
                 similarity_calculator: Optional[SimilarityCalculator] = None):
        """Initialize KNN search with specified index type."""
        self._logger = get_logger(__name__)
        self._index_type = index_type
        self._similarity_calculator = similarity_calculator or SimilarityCalculator()
        self._ranker = SearchResultRanker()
        self._lock = threading.RLock()

        # Initialize search implementation based on index type
        if index_type == IndexType.FLAT:
            self._search_impl = FlatKNNSearch(self._similarity_calculator)
        elif index_type == IndexType.IVF:
            self._search_impl = IVFKNNSearch(similarity_calculator=self._similarity_calculator)
        elif index_type == IndexType.HNSW:
            self._search_impl = HNSWKNNSearch(self._similarity_calculator)
        else:
            self._logger.warning(f"Unsupported index type {index_type}, falling back to FLAT")
            self._search_impl = FlatKNNSearch(self._similarity_calculator)
            self._index_type = IndexType.FLAT

        # Statistics tracking
        self._total_vectors = 0
        self._total_searches = 0
        self._total_search_time = 0.0
        self._index_build_time = 0.0

        self._logger.info(f"KNNSearch initialized with {self._index_type} index")

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
        start_time = time.time()

        try:
            with self._lock:
                config = config or SearchConfig()

                # Validate inputs
                if len(query_vector.shape) != 1:
                    raise ValueError(f"Expected 1D query vector, got {len(query_vector.shape)}D")

                if k <= 0:
                    raise ValueError(f"k must be positive, got {k}")

                # Perform search using selected implementation
                raw_results = self._search_impl.search(query_vector, k, config)

                # Rank and filter results
                ranked_results = self._ranker.rank_results(raw_results, config.similarity_threshold)

                # Deduplicate if enabled
                if config.enable_filtering:
                    ranked_results = self._ranker.deduplicate_results(ranked_results)

                # Limit to requested k
                final_results = ranked_results[:k]

                search_time = (time.time() - start_time) * 1000

                # Update statistics
                self._total_searches += 1
                self._total_search_time += search_time

                return KNNSearchResult(
                    status=VectorSearchStatus.COMPLETED,
                    query_vector_id="query",
                    k_requested=k,
                    results=final_results,
                    total_candidates=len(raw_results),
                    search_time_ms=search_time,
                    index_type_used=self._index_type,
                    metadata={
                        "similarity_metric": config.similarity_metric.value,
                        "similarity_threshold": config.similarity_threshold,
                        "filtering_enabled": config.enable_filtering
                    }
                )

        except Exception as e:
            self._logger.error(f"Error in KNN search: {e}")
            search_time = (time.time() - start_time) * 1000

            return KNNSearchResult(
                status=VectorSearchStatus.FAILED,
                query_vector_id="query",
                k_requested=k,
                results=[],
                total_candidates=0,
                search_time_ms=search_time,
                index_type_used=self._index_type,
                metadata={"error": str(e)}
            )

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
        start_time = time.time()

        try:
            with self._lock:
                # Validate inputs
                if len(vectors.shape) != 2:
                    raise ValueError(f"Expected 2D vector array, got {len(vectors.shape)}D")

                if len(vector_ids) != vectors.shape[0]:
                    raise ValueError(f"Vector count mismatch: {len(vector_ids)} IDs vs {vectors.shape[0]} vectors")

                if metadata and len(metadata) != vectors.shape[0]:
                    raise ValueError(f"Metadata count mismatch: {len(metadata)} vs {vectors.shape[0]} vectors")

                # Add vectors to implementation
                success = self._search_impl.add_vectors(vectors, vector_ids, metadata)

                if success:
                    self._total_vectors += len(vectors)
                    self._index_build_time += (time.time() - start_time) * 1000
                    self._logger.info(f"Added {len(vectors)} vectors to {self._index_type} index")

                return success

        except Exception as e:
            self._logger.error(f"Error adding vectors to index: {e}")
            return False

    def remove_vectors(self, vector_ids: List[str]) -> bool:
        """
        Remove vectors from the search index.

        Args:
            vector_ids: List of vector IDs to remove

        Returns:
            True if successfully removed, False otherwise
        """
        try:
            # Note: This is a simplified implementation
            # Full implementation would require index rebuilding for most index types
            self._logger.warning("Vector removal not fully implemented for all index types")
            return False

        except Exception as e:
            self._logger.error(f"Error removing vectors from index: {e}")
            return False

    def get_index_statistics(self) -> IndexStatistics:
        """
        Get statistics about the current index.

        Returns:
            IndexStatistics with performance metrics
        """
        try:
            with self._lock:
                avg_search_time = (
                    self._total_search_time / self._total_searches
                    if self._total_searches > 0 else 0.0
                )

                return IndexStatistics(
                    index_type=self._index_type,
                    total_vectors=self._total_vectors,
                    index_size_bytes=self._estimate_index_size(),
                    build_time_ms=self._index_build_time,
                    average_search_time_ms=avg_search_time,
                    memory_usage_mb=self._estimate_memory_usage(),
                    accuracy_score=1.0,  # Simplified - would need benchmarking
                    last_optimized=None
                )

        except Exception as e:
            self._logger.error(f"Error getting index statistics: {e}")
            return IndexStatistics(
                index_type=self._index_type,
                total_vectors=0,
                index_size_bytes=0,
                build_time_ms=0.0,
                average_search_time_ms=0.0,
                memory_usage_mb=0.0
            )

    def _estimate_index_size(self) -> int:
        """Estimate index size in bytes."""
        # Simplified estimation
        vector_size = self._total_vectors * 384 * 4  # Assuming 384-dim float32 vectors
        overhead = vector_size * 0.2  # 20% overhead for index structures
        return int(vector_size + overhead)

    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage in MB."""
        return self._estimate_index_size() / (1024 * 1024)
