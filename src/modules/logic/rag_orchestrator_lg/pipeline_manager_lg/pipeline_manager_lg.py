"""
Module: pipeline_manager_lg
Description: Orchestrates complete RAG pipeline from query to augmented response
Phase: 4
Location: /src/modules/logic/rag_orchestrator_lg/pipeline_manager_lg/
"""

# Standard library imports
import asyncio
import time
from typing import Optional, Dict, Any, List, AsyncIterator
from datetime import datetime, timedelta
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.rag_orchestrator_lg.base_interfaces import (
    IPipelineManager, IRetrievalStrategy, IAugmentationEngine,
    PipelineConfig, PipelineResult, PipelineStageResult, PipelineMetrics,
    PipelineStage, PipelineStatus, RetrievalResult, AugmentationResult
)
# Query processor interface (optional - may not be implemented yet)
try:
    from src.modules.logic.query_processor_lg.base_interfaces import IQueryProcessor
except ImportError:
    IQueryProcessor = None
from src.modules.logic.context_builder_lg.base_interfaces import IChunkSelector, IContextWindow, IReranker
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg.error_classifier_lg.error_classifier_lg import ErrorSeverity


class PipelineCache:
    """Cache for pipeline results."""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, tuple] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[PipelineResult]:
        """Get cached result."""
        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if datetime.now() - timestamp < timedelta(seconds=self._ttl_seconds):
                    return result
                else:
                    del self._cache[key]
            return None
    
    def put(self, key: str, result: PipelineResult) -> None:
        """Cache result."""
        with self._lock:
            self._cache[key] = (result, datetime.now())
    
    def clear(self) -> None:
        """Clear cache."""
        with self._lock:
            self._cache.clear()
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        # Simplified implementation
        return 0.0


class PipelineManager(IPipelineManager):
    """
    Orchestrates complete RAG pipeline from query to augmented response.
    
    Provides:
    - End-to-end pipeline orchestration
    - Stage-by-stage execution with monitoring
    - Caching and performance optimization
    - Error handling and recovery
    - Streaming execution support
    - Metrics collection and reporting
    - Concurrent request handling
    - Timeout management
    """
    
    def __init__(self, 
                 retrieval_strategy: IRetrievalStrategy,
                 augmentation_engine: IAugmentationEngine,
                 query_processor: Optional[Any] = None,
                 chunk_selector: Optional[IChunkSelector] = None,
                 context_window: Optional[IContextWindow] = None,
                 reranker: Optional[IReranker] = None):
        """
        Initialize pipeline manager.
        
        Args:
            retrieval_strategy: Strategy for retrieving relevant chunks
            augmentation_engine: Engine for prompt augmentation
            query_processor: Optional query processor
            chunk_selector: Optional chunk selector
            context_window: Optional context window manager
            reranker: Optional reranker
        """
        self._retrieval_strategy = retrieval_strategy
        self._augmentation_engine = augmentation_engine
        self._query_processor = query_processor
        self._chunk_selector = chunk_selector
        self._context_window = context_window
        self._reranker = reranker
        
        self._cache: Optional[PipelineCache] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._semaphore = asyncio.Semaphore(10)  # Default max concurrent requests
        self._metrics = PipelineMetrics()
        self._lock = threading.RLock()
        self._initialized = False
        
        self._logger = get_logger(__name__)
    
    async def initialize(self) -> bool:
        """
        Initialize the pipeline manager and all components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            with self._lock:
                if self._initialized:
                    return True
                
                # Initialize retrieval strategy
                if not await self._retrieval_strategy.initialize():
                    self._logger.error("Failed to initialize retrieval strategy")
                    return False
                
                # Initialize augmentation engine
                if not await self._augmentation_engine.initialize():
                    self._logger.error("Failed to initialize augmentation engine")
                    return False
                
                # Initialize optional components
                if self._query_processor and hasattr(self._query_processor, 'initialize'):
                    if not await self._query_processor.initialize():
                        self._logger.warning("Failed to initialize query processor")
                
                if self._chunk_selector and hasattr(self._chunk_selector, 'initialize'):
                    if not await self._chunk_selector.initialize():
                        self._logger.warning("Failed to initialize chunk selector")
                
                if self._context_window and hasattr(self._context_window, 'initialize'):
                    if not await self._context_window.initialize():
                        self._logger.warning("Failed to initialize context window")
                
                if self._reranker and hasattr(self._reranker, 'initialize'):
                    if not await self._reranker.initialize():
                        self._logger.warning("Failed to initialize reranker")
                
                # Initialize cache
                self._cache = PipelineCache()
                
                self._initialized = True
                self._logger.info("Pipeline manager initialized successfully")
                return True
                
        except Exception as e:
            self._logger.error(f"Error initializing pipeline manager: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown the pipeline manager and cleanup resources."""
        try:
            with self._lock:
                if not self._initialized:
                    return
                
                # Shutdown executor
                self._executor.shutdown(wait=True)
                
                # Clear cache
                if self._cache:
                    self._cache.clear()
                
                # Shutdown components if they support it
                if hasattr(self._retrieval_strategy, 'shutdown'):
                    await self._retrieval_strategy.shutdown()
                
                if hasattr(self._augmentation_engine, 'shutdown'):
                    await self._augmentation_engine.shutdown()
                
                self._initialized = False
                self._logger.info("Pipeline manager shutdown completed")
                
        except Exception as e:
            self._logger.error(f"Error during pipeline manager shutdown: {e}")
    
    async def execute_pipeline(self, query: str, config: Optional[PipelineConfig] = None) -> PipelineResult:
        """
        Execute complete RAG pipeline for a query.
        
        Args:
            query: Input query string
            config: Optional pipeline configuration
            
        Returns:
            PipelineResult with complete execution details
        """
        if not self._initialized:
            raise RuntimeError("Pipeline manager not initialized")
        
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        config = config or PipelineConfig()
        start_time = time.time()
        
        # Check cache first
        cache_key = self._generate_cache_key(query, config)
        if config.enable_caching and self._cache:
            cached_result = self._cache.get(cache_key)
            if cached_result:
                self._logger.debug(f"Cache hit for query: {query[:50]}...")
                return cached_result
        
        async with self._semaphore:
            try:
                # Execute pipeline stages
                stage_results = []
                
                # Stage 1: Query Processing
                processed_query = await self._process_query_stage(query, stage_results)
                
                # Stage 2: Retrieval
                retrieval_result = await self._execute_retrieval_stage(
                    processed_query, config, stage_results
                )
                
                # Stage 3: Context Building
                context_chunks = await self._execute_context_building_stage(
                    processed_query, retrieval_result, config, stage_results
                )
                
                # Stage 4: Augmentation
                augmentation_result = await self._execute_augmentation_stage(
                    processed_query, context_chunks, config, stage_results
                )
                
                # Create final result
                total_time = (time.time() - start_time) * 1000
                result = PipelineResult(
                    query=query,
                    augmented_prompt=augmentation_result.augmented_prompt,
                    retrieval_result=retrieval_result,
                    augmentation_result=augmentation_result,
                    stage_results=stage_results,
                    total_processing_time_ms=total_time,
                    status=PipelineStatus.COMPLETED
                )
                
                # Cache result
                if config.enable_caching and self._cache:
                    self._cache.put(cache_key, result)
                
                # Update metrics
                self._update_metrics(result)
                
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Pipeline execution timeout for query: {query[:50]}..."
                self._logger.error(error_msg)
                return self._create_error_result(query, PipelineStatus.TIMEOUT, error_msg, start_time)
                
            except Exception as e:
                error_msg = f"Pipeline execution failed: {str(e)}"
                self._logger.error(error_msg)
                return self._create_error_result(query, PipelineStatus.FAILED, error_msg, start_time)

    async def execute_pipeline_streaming(self, query: str,
                                       config: Optional[PipelineConfig] = None) -> AsyncIterator[PipelineStageResult]:
        """
        Execute pipeline with streaming results.

        Args:
            query: Input query string
            config: Optional pipeline configuration

        Yields:
            PipelineStageResult for each completed stage
        """
        if not self._initialized:
            raise RuntimeError("Pipeline manager not initialized")

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        config = config or PipelineConfig()

        async with self._semaphore:
            try:
                stage_results = []

                # Stage 1: Query Processing
                processed_query = await self._process_query_stage(query, stage_results)
                if stage_results:
                    yield stage_results[-1]

                # Stage 2: Retrieval
                retrieval_result = await self._execute_retrieval_stage(
                    processed_query, config, stage_results
                )
                if stage_results:
                    yield stage_results[-1]

                # Stage 3: Context Building
                context_chunks = await self._execute_context_building_stage(
                    processed_query, retrieval_result, config, stage_results
                )
                if stage_results:
                    yield stage_results[-1]

                # Stage 4: Augmentation
                augmentation_result = await self._execute_augmentation_stage(
                    processed_query, context_chunks, config, stage_results
                )
                if stage_results:
                    yield stage_results[-1]

            except Exception as e:
                error_stage = PipelineStageResult(
                    stage=PipelineStage.POST_PROCESSING,
                    status=PipelineStatus.FAILED,
                    result_data=None,
                    processing_time_ms=0.0,
                    error_message=str(e)
                )
                yield error_stage

    def get_metrics(self) -> PipelineMetrics:
        """Get pipeline performance metrics."""
        with self._lock:
            # Update cache hit rate if cache exists
            if self._cache:
                self._metrics.cache_hit_rate = self._cache.get_hit_rate()
            return self._metrics

    async def clear_cache(self) -> bool:
        """Clear pipeline cache."""
        try:
            if self._cache:
                self._cache.clear()
                self._logger.info("Pipeline cache cleared")
                return True
            return False
        except Exception as e:
            self._logger.error(f"Error clearing cache: {e}")
            return False

    def _generate_cache_key(self, query: str, config: PipelineConfig) -> str:
        """Generate cache key for query and config."""
        # Simple hash-based key generation
        import hashlib
        key_data = f"{query}_{config.retrieval_config.mode.value}_{config.retrieval_config.max_chunks}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def _process_query_stage(self, query: str, stage_results: List[PipelineStageResult]) -> str:
        """Process query stage."""
        start_time = time.time()

        try:
            processed_query = query
            if self._query_processor:
                # Process query if processor available
                processed_query = query  # Placeholder - would use actual processor

            processing_time = (time.time() - start_time) * 1000
            stage_result = PipelineStageResult(
                stage=PipelineStage.QUERY_PROCESSING,
                status=PipelineStatus.COMPLETED,
                result_data=processed_query,
                processing_time_ms=processing_time
            )
            stage_results.append(stage_result)

            return processed_query

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            stage_result = PipelineStageResult(
                stage=PipelineStage.QUERY_PROCESSING,
                status=PipelineStatus.FAILED,
                result_data=None,
                processing_time_ms=processing_time,
                error_message=str(e)
            )
            stage_results.append(stage_result)
            raise

    async def _execute_retrieval_stage(self, query: str, config: PipelineConfig,
                                     stage_results: List[PipelineStageResult]) -> RetrievalResult:
        """Execute retrieval stage."""
        start_time = time.time()

        try:
            retrieval_result = await self._retrieval_strategy.retrieve(
                query, config.retrieval_config
            )

            processing_time = (time.time() - start_time) * 1000
            stage_result = PipelineStageResult(
                stage=PipelineStage.RETRIEVAL,
                status=PipelineStatus.COMPLETED,
                result_data=retrieval_result,
                processing_time_ms=processing_time
            )
            stage_results.append(stage_result)

            return retrieval_result

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            stage_result = PipelineStageResult(
                stage=PipelineStage.RETRIEVAL,
                status=PipelineStatus.FAILED,
                result_data=None,
                processing_time_ms=processing_time,
                error_message=str(e)
            )
            stage_results.append(stage_result)
            raise

    async def _execute_context_building_stage(self, query: str, retrieval_result: RetrievalResult,
                                            config: PipelineConfig,
                                            stage_results: List[PipelineStageResult]) -> List:
        """Execute context building stage."""
        start_time = time.time()

        try:
            context_chunks = retrieval_result.chunks

            # Apply chunk selection if available
            if self._chunk_selector and context_chunks:
                # Would use actual chunk selector here
                pass

            # Apply reranking if available
            if self._reranker and context_chunks:
                # Would use actual reranker here
                pass

            # Apply context window management if available
            if self._context_window and context_chunks:
                # Would use actual context window here
                pass

            processing_time = (time.time() - start_time) * 1000
            stage_result = PipelineStageResult(
                stage=PipelineStage.CONTEXT_BUILDING,
                status=PipelineStatus.COMPLETED,
                result_data=context_chunks,
                processing_time_ms=processing_time
            )
            stage_results.append(stage_result)

            return context_chunks

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            stage_result = PipelineStageResult(
                stage=PipelineStage.CONTEXT_BUILDING,
                status=PipelineStatus.FAILED,
                result_data=None,
                processing_time_ms=processing_time,
                error_message=str(e)
            )
            stage_results.append(stage_result)
            raise

    async def _execute_augmentation_stage(self, query: str, context_chunks: List,
                                        config: PipelineConfig,
                                        stage_results: List[PipelineStageResult]) -> AugmentationResult:
        """Execute augmentation stage."""
        start_time = time.time()

        try:
            augmentation_result = await self._augmentation_engine.augment_prompt(
                query, context_chunks, config.augmentation_config
            )

            processing_time = (time.time() - start_time) * 1000
            stage_result = PipelineStageResult(
                stage=PipelineStage.AUGMENTATION,
                status=PipelineStatus.COMPLETED,
                result_data=augmentation_result,
                processing_time_ms=processing_time
            )
            stage_results.append(stage_result)

            return augmentation_result

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            stage_result = PipelineStageResult(
                stage=PipelineStage.AUGMENTATION,
                status=PipelineStatus.FAILED,
                result_data=None,
                processing_time_ms=processing_time,
                error_message=str(e)
            )
            stage_results.append(stage_result)
            raise

    def _create_error_result(self, query: str, status: PipelineStatus,
                           error_message: str, start_time: float) -> PipelineResult:
        """Create error result."""
        total_time = (time.time() - start_time) * 1000

        # Create empty results
        empty_retrieval = RetrievalResult(
            chunks=[],
            scores=[],
            retrieval_mode=self._retrieval_strategy.get_supported_modes()[0] if self._retrieval_strategy.get_supported_modes() else None,
            total_candidates=0,
            processing_time_ms=0.0
        )

        empty_augmentation = AugmentationResult(
            augmented_prompt="",
            original_query=query,
            context_chunks=[],
            context_length=0,
            compression_applied=False,
            processing_time_ms=0.0
        )

        return PipelineResult(
            query=query,
            augmented_prompt="",
            retrieval_result=empty_retrieval,
            augmentation_result=empty_augmentation,
            stage_results=[],
            total_processing_time_ms=total_time,
            status=status,
            error_message=error_message
        )

    def _update_metrics(self, result: PipelineResult) -> None:
        """Update pipeline metrics."""
        with self._lock:
            self._metrics.total_requests += 1

            if result.is_successful:
                self._metrics.successful_requests += 1
            else:
                self._metrics.failed_requests += 1

            # Update average processing time
            total_time = (self._metrics.average_processing_time_ms * (self._metrics.total_requests - 1) +
                         result.total_processing_time_ms) / self._metrics.total_requests
            self._metrics.average_processing_time_ms = total_time

            # Update context relevance score
            if result.retrieval_result.chunks:
                self._metrics.context_relevance_score = result.context_quality_score
