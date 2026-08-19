"""
Module: semantic_searcher_lg
Description: Performs vector-based semantic search using embeddings and similarity metrics
Phase: 4
Location: /src/modules/logic/hybrid_search_lg/semantic_searcher_lg/
"""

# Standard library imports
import time
import threading
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.vector_search_lg import (
    ISimilarityCalculator,
    IKNNSearch,
    SearchConfig,
    SimilarityMetric,
    SearchResultItem as VectorSearchResultItem,
    KNNSearchResult
)
from src.modules.logic.embedding_generation_lg import (
    IDocumentEmbedder,
    EmbeddingResult,
    EmbeddingConfig
)
from ..base_interfaces import (
    ISemanticSearcher,
    SemanticSearchResult,
    SemanticSearchConfig,
    SearchResultItem,
    SearchType,
    SearchStatus
)


class VectorEmbedder:
    """Handles vector embedding generation for semantic search."""
    
    def __init__(self, embedder: Optional[IDocumentEmbedder] = None):
        """Initialize vector embedder."""
        self._embedder = embedder
        self._logger = get_logger(__name__)
        self._lock = threading.RLock()
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._cache_size_limit = 1000
    
    def embed_query(self, query: str, config: Optional[SemanticSearchConfig] = None) -> np.ndarray:
        """
        Generate embedding vector for search query.
        
        Args:
            query: Query text to embed
            config: Optional semantic search configuration
            
        Returns:
            Query embedding vector
            
        Raises:
            ValidationError: If query is invalid or embedding fails
        """
        try:
            if not query or not query.strip():
                raise ValidationError("Query cannot be empty")
            
            # Check cache first
            cache_key = f"query:{hash(query)}"
            with self._lock:
                if cache_key in self._embedding_cache:
                    return self._embedding_cache[cache_key]
            
            if not self._embedder:
                # Fallback to simple word-based embedding for testing
                words = query.lower().split()
                vector_dim = config.vector_dimension if config else 384
                vector = np.random.random(vector_dim).astype(np.float32)
                vector = vector / np.linalg.norm(vector)  # Normalize
            else:
                # Use actual embedder
                embedding_config = EmbeddingConfig(
                    model_name=config.model_name if config else "sentence-transformers/all-MiniLM-L6-v2",
                    vector_dimensions=config.vector_dimension if config else 384
                )
                result = self._embedder.generate_embedding(query, embedding_config)
                if result.status.value != "completed" or result.vector is None:
                    raise ValidationError(f"Failed to generate embedding: {result.error_message}")
                vector = result.vector
            
            # Cache the result
            with self._lock:
                if len(self._embedding_cache) >= self._cache_size_limit:
                    # Remove oldest entry
                    oldest_key = next(iter(self._embedding_cache))
                    del self._embedding_cache[oldest_key]
                self._embedding_cache[cache_key] = vector
            
            return vector
            
        except Exception as e:
            self._logger.error(f"Error generating query embedding: {e}")
            raise ValidationError(f"Failed to generate query embedding: {e}")
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        with self._lock:
            self._embedding_cache.clear()


class SimilarityMatcher:
    """Handles similarity matching for semantic search."""
    
    def __init__(self, similarity_calculator: Optional[ISimilarityCalculator] = None):
        """Initialize similarity matcher."""
        self._similarity_calculator = similarity_calculator
        self._logger = get_logger(__name__)
    
    def find_similar_vectors(self, query_vector: np.ndarray, 
                           candidate_vectors: np.ndarray,
                           config: Optional[SemanticSearchConfig] = None) -> List[Tuple[int, float]]:
        """
        Find similar vectors using similarity calculation.
        
        Args:
            query_vector: Query embedding vector
            candidate_vectors: Array of candidate vectors
            config: Optional semantic search configuration
            
        Returns:
            List of (index, similarity_score) tuples sorted by similarity
        """
        try:
            config = config or SemanticSearchConfig()
            
            if self._similarity_calculator:
                # Use actual similarity calculator
                similarities = self._similarity_calculator.batch_calculate_similarity(
                    query_vector, candidate_vectors, SimilarityMetric.COSINE
                )
            else:
                # Fallback cosine similarity calculation
                query_norm = np.linalg.norm(query_vector)
                if query_norm == 0:
                    return []
                
                candidate_norms = np.linalg.norm(candidate_vectors, axis=1)
                valid_candidates = candidate_norms > 0
                
                similarities = np.zeros(candidate_vectors.shape[0])
                if np.any(valid_candidates):
                    dot_products = np.dot(candidate_vectors[valid_candidates], query_vector)
                    similarities[valid_candidates] = dot_products / (
                        candidate_norms[valid_candidates] * query_norm
                    )
                    similarities = np.clip(similarities, 0.0, 1.0)
            
            # Filter by threshold and get top results
            valid_indices = np.where(similarities >= config.similarity_threshold)[0]
            valid_similarities = similarities[valid_indices]
            
            # Sort by similarity (descending)
            sorted_indices = np.argsort(valid_similarities)[::-1]
            
            # Limit results
            max_results = min(config.max_results, len(sorted_indices))
            
            results = []
            for i in range(max_results):
                idx = valid_indices[sorted_indices[i]]
                score = valid_similarities[sorted_indices[i]]
                results.append((int(idx), float(score)))
            
            return results
            
        except Exception as e:
            self._logger.error(f"Error in similarity matching: {e}")
            return []


class SemanticRanker:
    """Handles ranking and reranking of semantic search results."""
    
    def __init__(self):
        """Initialize semantic ranker."""
        self._logger = get_logger(__name__)
    
    def rank_results(self, results: List[SearchResultItem], 
                    config: Optional[SemanticSearchConfig] = None) -> List[SearchResultItem]:
        """
        Rank search results by relevance score.
        
        Args:
            results: List of search results to rank
            config: Optional semantic search configuration
            
        Returns:
            Ranked list of search results
        """
        try:
            if not results:
                return results
            
            # Sort by score (descending)
            ranked_results = sorted(results, key=lambda x: x.score, reverse=True)
            
            # Update rank positions
            for i, result in enumerate(ranked_results):
                result.rank = i + 1
            
            return ranked_results
            
        except Exception as e:
            self._logger.error(f"Error ranking results: {e}")
            return results
    
    def rerank_results(self, results: List[SearchResultItem], query: str,
                      config: Optional[SemanticSearchConfig] = None) -> List[SearchResultItem]:
        """
        Rerank results using additional relevance signals.
        
        Args:
            results: List of search results to rerank
            query: Original search query
            config: Optional semantic search configuration
            
        Returns:
            Reranked list of search results
        """
        try:
            if not results or not config or not config.enable_reranking:
                return results
            
            # Simple reranking based on content length and position
            for result in results:
                # Boost score based on content quality indicators
                content_length_factor = min(len(result.content) / 1000, 1.0)
                position_factor = 1.0 / (result.position_in_document + 1) if result.position_in_document else 1.0
                
                # Apply reranking boost
                result.relevance_score = result.score * (1.0 + 0.1 * content_length_factor + 0.05 * position_factor)
            
            # Sort by relevance score
            reranked_results = sorted(results, key=lambda x: x.relevance_score, reverse=True)
            
            # Update ranks
            for i, result in enumerate(reranked_results):
                result.rank = i + 1
            
            return reranked_results
            
        except Exception as e:
            self._logger.error(f"Error reranking results: {e}")
            return results


class SemanticSearcher(ISemanticSearcher):
    """Main semantic search implementation using vector embeddings."""
    
    def __init__(self, 
                 embedder: Optional[IDocumentEmbedder] = None,
                 knn_search: Optional[IKNNSearch] = None,
                 similarity_calculator: Optional[ISimilarityCalculator] = None):
        """Initialize semantic searcher."""
        self._embedder = VectorEmbedder(embedder)
        self._knn_search = knn_search
        self._similarity_matcher = SimilarityMatcher(similarity_calculator)
        self._ranker = SemanticRanker()
        self._logger = get_logger(__name__)
        self._lock = threading.RLock()
        
        # Mock document store for testing
        self._document_store: Dict[str, Dict[str, Any]] = {}
        self._vector_store: Dict[str, np.ndarray] = {}
    
    def search(self, query: str, config: Optional[SemanticSearchConfig] = None) -> SemanticSearchResult:
        """
        Perform semantic search using vector embeddings.
        
        Args:
            query: Search query string
            config: Optional search configuration
            
        Returns:
            SemanticSearchResult with search results and metadata
        """
        start_time = time.time()
        config = config or SemanticSearchConfig()
        
        try:
            self._logger.info(f"Starting semantic search for query: {query[:100]}...")
            
            # Generate query embedding
            query_vector = self._embedder.embed_query(query, config)
            
            # Perform vector search
            result = self.search_by_vector(query_vector, config)
            result.query = query
            
            search_time = (time.time() - start_time) * 1000
            result.search_time_ms = search_time
            
            self._logger.info(f"Semantic search completed in {search_time:.2f}ms, found {len(result.results)} results")
            return result
            
        except Exception as e:
            self._logger.error(f"Error in semantic search: {e}")
            return SemanticSearchResult(
                status=SearchStatus.FAILED,
                query=query,
                search_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )
    
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
        start_time = time.time()
        config = config or SemanticSearchConfig()
        
        try:
            results = []
            
            if self._knn_search:
                # Use KNN search if available
                search_config = SearchConfig(
                    k=config.max_results,
                    similarity_threshold=config.similarity_threshold,
                    timeout_seconds=config.timeout_seconds
                )
                knn_result = self._knn_search.search(query_vector, config.max_results, search_config)
                
                # Convert KNN results to semantic search results
                for item in knn_result.results:
                    search_item = SearchResultItem(
                        chunk_id=item.chunk_id,
                        document_id=item.document_id,
                        score=item.similarity_score,
                        content=item.content_preview or "",
                        search_type=SearchType.SEMANTIC,
                        metadata=item.metadata,
                        position_in_document=item.position_in_document,
                        timestamp=datetime.now()
                    )
                    results.append(search_item)
            else:
                # Fallback to similarity matching with mock data
                if self._vector_store:
                    candidate_vectors = np.array(list(self._vector_store.values()))
                    chunk_ids = list(self._vector_store.keys())
                    
                    similar_indices = self._similarity_matcher.find_similar_vectors(
                        query_vector, candidate_vectors, config
                    )
                    
                    for idx, score in similar_indices:
                        chunk_id = chunk_ids[idx]
                        doc_info = self._document_store.get(chunk_id, {})
                        
                        search_item = SearchResultItem(
                            chunk_id=chunk_id,
                            document_id=doc_info.get("document_id", "unknown"),
                            score=score,
                            content=doc_info.get("content", ""),
                            search_type=SearchType.SEMANTIC,
                            metadata=doc_info.get("metadata", {}),
                            timestamp=datetime.now()
                        )
                        results.append(search_item)
            
            # Rank results
            ranked_results = self._ranker.rank_results(results, config)
            
            # Apply reranking if enabled
            if config.enable_reranking:
                ranked_results = self._ranker.rerank_results(ranked_results, "", config)
            
            search_time = (time.time() - start_time) * 1000
            
            return SemanticSearchResult(
                status=SearchStatus.COMPLETED,
                query="",
                query_vector=query_vector,
                results=ranked_results,
                total_candidates=len(self._vector_store),
                search_time_ms=search_time,
                similarity_threshold=config.similarity_threshold,
                vector_dimension=len(query_vector),
                model_used=config.model_name,
                metadata={
                    "config": config.__dict__,
                    "reranking_enabled": config.enable_reranking
                }
            )
            
        except Exception as e:
            self._logger.error(f"Error in vector search: {e}")
            return SemanticSearchResult(
                status=SearchStatus.FAILED,
                query="",
                query_vector=query_vector,
                search_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )
    
    def get_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate embedding vector for query text.
        
        Args:
            query: Query text to embed
            
        Returns:
            Query embedding vector
        """
        return self._embedder.embed_query(query)
    
    def get_supported_models(self) -> List[str]:
        """
        Get list of supported embedding models.
        
        Returns:
            List of supported model names
        """
        return [
            "sentence-transformers/all-MiniLM-L6-v2",
            "sentence-transformers/all-mpnet-base-v2",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ]
    
    def add_document(self, chunk_id: str, document_id: str, content: str, 
                    vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add document to the search index (for testing purposes).
        
        Args:
            chunk_id: Unique chunk identifier
            document_id: Document identifier
            content: Document content
            vector: Pre-computed vector (optional)
            metadata: Additional metadata
            
        Returns:
            True if document added successfully
        """
        try:
            with self._lock:
                self._document_store[chunk_id] = {
                    "document_id": document_id,
                    "content": content,
                    "metadata": metadata or {}
                }
                
                if vector is not None:
                    self._vector_store[chunk_id] = vector
                else:
                    # Generate vector if not provided
                    vector = self._embedder.embed_query(content)
                    self._vector_store[chunk_id] = vector
            
            return True
            
        except Exception as e:
            self._logger.error(f"Error adding document: {e}")
            return False
