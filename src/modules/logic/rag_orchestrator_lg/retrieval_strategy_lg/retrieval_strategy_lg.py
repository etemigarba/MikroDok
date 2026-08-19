"""
Module: retrieval_strategy_lg
Description: Implements different retrieval strategies (dense, sparse, hybrid)
Phase: 4
Location: /src/modules/logic/rag_orchestrator_lg/retrieval_strategy_lg/
"""

# Standard library imports
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
import logging
import threading
from collections import defaultdict

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.rag_orchestrator_lg.base_interfaces import (
    IRetrievalStrategy, RetrievalConfig, RetrievalResult, RetrievalMode
)
from src.modules.logic.document_chunking_lg.base_interfaces import DocumentChunk
from src.modules.logic.hybrid_search_lg.base_interfaces import (
    ISemanticSearcher, IKeywordSearcher, IResultFusion,
    HybridSearchResult, SemanticSearchConfig, KeywordSearchConfig, FusionConfig
)
from src.modules.logic.vector_search_lg.base_interfaces import IKNNSearcher, ISimilarityCalculator
from src.modules.logic.context_builder_lg.base_interfaces import IReranker, RerankingConfig
from src.modules.logic.logging_infrastructure_lg import get_logger


class AdaptiveRetrievalDecider:
    """Decides optimal retrieval strategy based on query characteristics."""
    
    def __init__(self):
        self._query_patterns = {
            'factual': ['what', 'when', 'where', 'who', 'how many'],
            'conceptual': ['why', 'how', 'explain', 'describe', 'compare'],
            'procedural': ['steps', 'process', 'procedure', 'method', 'way to']
        }
        self._performance_history = defaultdict(list)
        self._lock = threading.RLock()
    
    def decide_strategy(self, query: str, available_modes: List[RetrievalMode]) -> RetrievalMode:
        """
        Decide optimal retrieval strategy for query.
        
        Args:
            query: Input query string
            available_modes: Available retrieval modes
            
        Returns:
            Optimal RetrievalMode for the query
        """
        query_lower = query.lower()
        
        # Analyze query characteristics
        is_factual = any(pattern in query_lower for pattern in self._query_patterns['factual'])
        is_conceptual = any(pattern in query_lower for pattern in self._query_patterns['conceptual'])
        is_procedural = any(pattern in query_lower for pattern in self._query_patterns['procedural'])
        
        # Decision logic based on query type
        if is_factual and RetrievalMode.SPARSE_ONLY in available_modes:
            return RetrievalMode.SPARSE_ONLY
        elif is_conceptual and RetrievalMode.DENSE_ONLY in available_modes:
            return RetrievalMode.DENSE_ONLY
        elif is_procedural and RetrievalMode.HYBRID in available_modes:
            return RetrievalMode.HYBRID
        elif RetrievalMode.HYBRID in available_modes:
            return RetrievalMode.HYBRID
        elif available_modes:
            return available_modes[0]
        else:
            return RetrievalMode.DENSE_ONLY
    
    def update_performance(self, mode: RetrievalMode, query: str, 
                          relevance_score: float, processing_time: float) -> None:
        """Update performance history for strategy optimization."""
        with self._lock:
            self._performance_history[mode].append({
                'query': query,
                'relevance_score': relevance_score,
                'processing_time': processing_time,
                'timestamp': time.time()
            })
            
            # Keep only recent history (last 1000 entries)
            if len(self._performance_history[mode]) > 1000:
                self._performance_history[mode] = self._performance_history[mode][-1000:]


class RetrievalStrategy(IRetrievalStrategy):
    """
    Implements different retrieval strategies (dense, sparse, hybrid).
    
    Provides:
    - Dense retrieval using semantic search
    - Sparse retrieval using keyword search
    - Hybrid retrieval combining both approaches
    - Adaptive strategy selection
    - Multi-stage retrieval with refinement
    - Performance monitoring and optimization
    - Index management and updates
    - Fallback mechanisms
    """
    
    def __init__(self,
                 semantic_searcher: Optional[ISemanticSearcher] = None,
                 keyword_searcher: Optional[IKeywordSearcher] = None,
                 result_fusion: Optional[IResultFusion] = None,
                 knn_searcher: Optional[IKNNSearcher] = None,
                 similarity_calculator: Optional[ISimilarityCalculator] = None,
                 reranker: Optional[IReranker] = None):
        """
        Initialize retrieval strategy.
        
        Args:
            semantic_searcher: Semantic search implementation
            keyword_searcher: Keyword search implementation
            result_fusion: Result fusion implementation
            knn_searcher: KNN search implementation
            similarity_calculator: Similarity calculation implementation
            reranker: Reranking implementation
        """
        self._semantic_searcher = semantic_searcher
        self._keyword_searcher = keyword_searcher
        self._result_fusion = result_fusion
        self._knn_searcher = knn_searcher
        self._similarity_calculator = similarity_calculator
        self._reranker = reranker
        
        self._adaptive_decider = AdaptiveRetrievalDecider()
        self._metrics = defaultdict(float)
        self._lock = threading.RLock()
        self._initialized = False
        
        self._logger = get_logger(__name__)
    
    async def initialize(self) -> bool:
        """
        Initialize the retrieval strategy and all components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            with self._lock:
                if self._initialized:
                    return True
                
                # Initialize semantic searcher
                if self._semantic_searcher and hasattr(self._semantic_searcher, 'initialize'):
                    if not await self._semantic_searcher.initialize():
                        self._logger.warning("Failed to initialize semantic searcher")
                
                # Initialize keyword searcher
                if self._keyword_searcher and hasattr(self._keyword_searcher, 'initialize'):
                    if not await self._keyword_searcher.initialize():
                        self._logger.warning("Failed to initialize keyword searcher")
                
                # Initialize result fusion
                if self._result_fusion and hasattr(self._result_fusion, 'initialize'):
                    if not await self._result_fusion.initialize():
                        self._logger.warning("Failed to initialize result fusion")
                
                # Initialize KNN searcher
                if self._knn_searcher and hasattr(self._knn_searcher, 'initialize'):
                    if not await self._knn_searcher.initialize():
                        self._logger.warning("Failed to initialize KNN searcher")
                
                # Initialize similarity calculator
                if self._similarity_calculator and hasattr(self._similarity_calculator, 'initialize'):
                    if not await self._similarity_calculator.initialize():
                        self._logger.warning("Failed to initialize similarity calculator")
                
                # Initialize reranker
                if self._reranker and hasattr(self._reranker, 'initialize'):
                    if not await self._reranker.initialize():
                        self._logger.warning("Failed to initialize reranker")
                
                self._initialized = True
                self._logger.info("Retrieval strategy initialized successfully")
                return True
                
        except Exception as e:
            self._logger.error(f"Error initializing retrieval strategy: {e}")
            return False
    
    async def retrieve(self, query: str, config: Optional[RetrievalConfig] = None) -> RetrievalResult:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: Search query string
            config: Optional retrieval configuration
            
        Returns:
            RetrievalResult with retrieved chunks and metadata
        """
        if not self._initialized:
            raise RuntimeError("Retrieval strategy not initialized")
        
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        config = config or RetrievalConfig()
        start_time = time.time()
        
        try:
            # Determine retrieval mode
            retrieval_mode = config.mode
            if retrieval_mode == RetrievalMode.ADAPTIVE:
                retrieval_mode = self._adaptive_decider.decide_strategy(
                    query, self.get_supported_modes()
                )
            
            # Execute retrieval based on mode
            if retrieval_mode == RetrievalMode.DENSE_ONLY:
                result = await self._execute_dense_retrieval(query, config)
            elif retrieval_mode == RetrievalMode.SPARSE_ONLY:
                result = await self._execute_sparse_retrieval(query, config)
            elif retrieval_mode == RetrievalMode.HYBRID:
                result = await self._execute_hybrid_retrieval(query, config)
            elif retrieval_mode == RetrievalMode.MULTI_STAGE:
                result = await self._execute_multi_stage_retrieval(query, config)
            else:
                # Fallback to hybrid if available
                if self._can_execute_hybrid():
                    result = await self._execute_hybrid_retrieval(query, config)
                else:
                    result = await self._execute_dense_retrieval(query, config)
            
            # Apply reranking if enabled and available
            if config.enable_reranking and self._reranker and result.chunks:
                result = await self._apply_reranking(query, result, config)
            
            # Update performance metrics
            processing_time = (time.time() - start_time) * 1000
            result.processing_time_ms = processing_time
            
            # Update adaptive decider
            if result.chunks:
                avg_score = np.mean(result.scores) if result.scores else 0.0
                self._adaptive_decider.update_performance(
                    retrieval_mode, query, avg_score, processing_time
                )
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error during retrieval: {e}")
            # Return empty result on error
            return RetrievalResult(
                chunks=[],
                scores=[],
                retrieval_mode=config.mode,
                total_candidates=0,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={'error': str(e)}
            )

    def get_supported_modes(self) -> List[RetrievalMode]:
        """
        Get list of supported retrieval modes.

        Returns:
            List of supported RetrievalMode enums
        """
        supported_modes = []

        if self._semantic_searcher or self._knn_searcher:
            supported_modes.append(RetrievalMode.DENSE_ONLY)

        if self._keyword_searcher:
            supported_modes.append(RetrievalMode.SPARSE_ONLY)

        if self._can_execute_hybrid():
            supported_modes.append(RetrievalMode.HYBRID)

        if supported_modes:
            supported_modes.extend([RetrievalMode.ADAPTIVE, RetrievalMode.MULTI_STAGE])

        return supported_modes

    async def update_index(self, chunks: List[DocumentChunk]) -> bool:
        """
        Update retrieval index with new chunks.

        Args:
            chunks: List of document chunks to index

        Returns:
            True if index updated successfully, False otherwise
        """
        try:
            success = True

            # Update semantic search index
            if self._semantic_searcher:
                documents = [{'id': chunk.chunk_id, 'content': chunk.content} for chunk in chunks]
                if hasattr(self._semantic_searcher, 'build_index'):
                    if not await self._semantic_searcher.build_index(documents):
                        success = False
                        self._logger.warning("Failed to update semantic search index")

            # Update keyword search index
            if self._keyword_searcher:
                documents = [{'id': chunk.chunk_id, 'content': chunk.content} for chunk in chunks]
                if hasattr(self._keyword_searcher, 'build_index'):
                    if not self._keyword_searcher.build_index(documents):
                        success = False
                        self._logger.warning("Failed to update keyword search index")

            # Update KNN search index
            if self._knn_searcher:
                if hasattr(self._knn_searcher, 'add_vectors'):
                    # Would need to generate embeddings for chunks
                    pass

            if success:
                self._logger.info(f"Successfully updated index with {len(chunks)} chunks")

            return success

        except Exception as e:
            self._logger.error(f"Error updating index: {e}")
            return False

    def get_retrieval_metrics(self) -> Dict[str, float]:
        """Get retrieval performance metrics."""
        with self._lock:
            return dict(self._metrics)

    def _can_execute_hybrid(self) -> bool:
        """Check if hybrid retrieval can be executed."""
        return (self._semantic_searcher is not None and
                self._keyword_searcher is not None and
                self._result_fusion is not None)

    async def _execute_dense_retrieval(self, query: str, config: RetrievalConfig) -> RetrievalResult:
        """Execute dense (semantic) retrieval."""
        if not self._semantic_searcher and not self._knn_searcher:
            raise RuntimeError("No dense retrieval component available")

        try:
            chunks = []
            scores = []
            total_candidates = 0

            if self._semantic_searcher:
                search_config = SemanticSearchConfig(
                    max_results=config.max_chunks,
                    similarity_threshold=config.similarity_threshold
                )
                result = self._semantic_searcher.search(query, search_config)

                # Convert search results to chunks
                for item in result.results:
                    chunk = DocumentChunk(
                        chunk_id=item.document_id,
                        content=item.content,
                        metadata=item.metadata
                    )
                    chunks.append(chunk)
                    scores.append(item.score)

                total_candidates = result.total_found

            elif self._knn_searcher:
                # Use KNN searcher as fallback
                # Would need query embedding here
                pass

            return RetrievalResult(
                chunks=chunks,
                scores=scores,
                retrieval_mode=RetrievalMode.DENSE_ONLY,
                total_candidates=total_candidates,
                processing_time_ms=0.0,
                metadata={'strategy': 'dense'}
            )

        except Exception as e:
            self._logger.error(f"Error in dense retrieval: {e}")
            raise

    async def _execute_sparse_retrieval(self, query: str, config: RetrievalConfig) -> RetrievalResult:
        """Execute sparse (keyword) retrieval."""
        if not self._keyword_searcher:
            raise RuntimeError("No sparse retrieval component available")

        try:
            search_config = KeywordSearchConfig(
                max_results=config.max_chunks,
                min_score=config.similarity_threshold
            )
            result = self._keyword_searcher.search(query, search_config)

            chunks = []
            scores = []

            # Convert search results to chunks
            for item in result.results:
                chunk = DocumentChunk(
                    chunk_id=item.document_id,
                    content=item.content,
                    metadata=item.metadata
                )
                chunks.append(chunk)
                scores.append(item.score)

            return RetrievalResult(
                chunks=chunks,
                scores=scores,
                retrieval_mode=RetrievalMode.SPARSE_ONLY,
                total_candidates=result.total_found,
                processing_time_ms=0.0,
                metadata={'strategy': 'sparse'}
            )

        except Exception as e:
            self._logger.error(f"Error in sparse retrieval: {e}")
            raise

    async def _execute_hybrid_retrieval(self, query: str, config: RetrievalConfig) -> RetrievalResult:
        """Execute hybrid retrieval combining dense and sparse."""
        if not self._can_execute_hybrid():
            raise RuntimeError("Hybrid retrieval components not available")

        try:
            # Execute both dense and sparse retrieval
            dense_config = SemanticSearchConfig(
                max_results=config.max_chunks,
                similarity_threshold=config.similarity_threshold
            )
            sparse_config = KeywordSearchConfig(
                max_results=config.max_chunks,
                min_score=config.similarity_threshold
            )

            # Run searches concurrently
            dense_task = asyncio.create_task(
                asyncio.to_thread(self._semantic_searcher.search, query, dense_config)
            )
            sparse_task = asyncio.create_task(
                asyncio.to_thread(self._keyword_searcher.search, query, sparse_config)
            )

            dense_result, sparse_result = await asyncio.gather(dense_task, sparse_task)

            # Fuse results
            fusion_config = FusionConfig(
                max_results=config.max_chunks,
                diversity_threshold=config.diversity_threshold
            )
            fused_result = self._result_fusion.fuse_results(
                dense_result, sparse_result, fusion_config
            )

            chunks = []
            scores = []

            # Convert fused results to chunks
            for item in fused_result.results:
                chunk = DocumentChunk(
                    chunk_id=item.document_id,
                    content=item.content,
                    metadata=item.metadata
                )
                chunks.append(chunk)
                scores.append(item.score)

            return RetrievalResult(
                chunks=chunks,
                scores=scores,
                retrieval_mode=RetrievalMode.HYBRID,
                total_candidates=fused_result.total_found,
                processing_time_ms=0.0,
                metadata={'strategy': 'hybrid', 'fusion_strategy': fusion_config.strategy.value}
            )

        except Exception as e:
            self._logger.error(f"Error in hybrid retrieval: {e}")
            raise

    async def _execute_multi_stage_retrieval(self, query: str, config: RetrievalConfig) -> RetrievalResult:
        """Execute multi-stage retrieval with refinement."""
        try:
            # Stage 1: Initial broad retrieval
            initial_config = RetrievalConfig(
                mode=RetrievalMode.HYBRID if self._can_execute_hybrid() else RetrievalMode.DENSE_ONLY,
                max_chunks=config.max_chunks * 2,  # Retrieve more initially
                similarity_threshold=config.similarity_threshold * 0.8  # Lower threshold
            )

            initial_result = await self.retrieve(query, initial_config)

            # Stage 2: Refinement with reranking
            if initial_result.chunks and self._reranker:
                reranking_config = RerankingConfig(
                    max_results=config.max_chunks,
                    diversity_threshold=config.diversity_threshold
                )

                reranked_result = await self._reranker.rerank_chunks(
                    initial_result.chunks, query, reranking_config
                )

                return RetrievalResult(
                    chunks=reranked_result.chunks,
                    scores=[score.score for score in reranked_result.scores],
                    retrieval_mode=RetrievalMode.MULTI_STAGE,
                    total_candidates=initial_result.total_candidates,
                    processing_time_ms=0.0,
                    metadata={'strategy': 'multi_stage', 'stages': 2}
                )

            # Fallback to initial result if no reranker
            return RetrievalResult(
                chunks=initial_result.chunks[:config.max_chunks],
                scores=initial_result.scores[:config.max_chunks],
                retrieval_mode=RetrievalMode.MULTI_STAGE,
                total_candidates=initial_result.total_candidates,
                processing_time_ms=0.0,
                metadata={'strategy': 'multi_stage', 'stages': 1}
            )

        except Exception as e:
            self._logger.error(f"Error in multi-stage retrieval: {e}")
            raise

    async def _apply_reranking(self, query: str, result: RetrievalResult,
                             config: RetrievalConfig) -> RetrievalResult:
        """Apply reranking to retrieval results."""
        try:
            reranking_config = RerankingConfig(
                max_results=config.max_chunks,
                diversity_threshold=config.diversity_threshold
            )

            reranked_result = await self._reranker.rerank_chunks(
                result.chunks, query, reranking_config
            )

            return RetrievalResult(
                chunks=reranked_result.chunks,
                scores=[score.score for score in reranked_result.scores],
                retrieval_mode=result.retrieval_mode,
                total_candidates=result.total_candidates,
                processing_time_ms=result.processing_time_ms,
                metadata={**result.metadata, 'reranked': True}
            )

        except Exception as e:
            self._logger.warning(f"Error applying reranking: {e}")
            return result  # Return original result if reranking fails
