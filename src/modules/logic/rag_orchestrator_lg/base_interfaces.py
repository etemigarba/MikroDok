"""
Module: base_interfaces
Description: Base interfaces and data structures for RAG orchestrator functionality
Phase: 4
Location: /src/modules/logic/rag_orchestrator_lg/
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union, AsyncIterator
import asyncio
from datetime import datetime
import numpy as np

from src.modules.logic.document_chunking_lg.base_interfaces import DocumentChunk
from src.modules.logic.context_builder_lg.base_interfaces import (
    ChunkSelectionResult, ContextWindowResult, RerankingResult
)
from src.modules.logic.hybrid_search_lg.base_interfaces import (
    HybridSearchResult, SearchResultItem
)


class RetrievalMode(Enum):
    """Retrieval modes for RAG pipeline."""
    DENSE_ONLY = "dense_only"
    SPARSE_ONLY = "sparse_only"
    HYBRID = "hybrid"
    ADAPTIVE = "adaptive"
    MULTI_STAGE = "multi_stage"


class AugmentationStrategy(Enum):
    """Strategies for prompt augmentation."""
    SIMPLE_CONCATENATION = "simple_concatenation"
    TEMPLATE_BASED = "template_based"
    CONTEXT_AWARE = "context_aware"
    HIERARCHICAL = "hierarchical"
    ADAPTIVE_FORMATTING = "adaptive_formatting"


class PipelineStage(Enum):
    """Stages in the RAG pipeline."""
    QUERY_PROCESSING = "query_processing"
    RETRIEVAL = "retrieval"
    CONTEXT_BUILDING = "context_building"
    AUGMENTATION = "augmentation"
    GENERATION = "generation"
    POST_PROCESSING = "post_processing"


class PipelineStatus(Enum):
    """Status of pipeline execution."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class RetrievalConfig:
    """Configuration for retrieval strategies."""
    mode: RetrievalMode = RetrievalMode.HYBRID
    max_chunks: int = 10
    similarity_threshold: float = 0.7
    diversity_threshold: float = 0.3
    enable_reranking: bool = True
    timeout_seconds: int = 30
    fallback_strategy: Optional[RetrievalMode] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AugmentationConfig:
    """Configuration for prompt augmentation."""
    strategy: AugmentationStrategy = AugmentationStrategy.TEMPLATE_BASED
    max_context_length: int = 4000
    context_template: str = "Context: {context}\n\nQuestion: {query}\n\nAnswer:"
    include_metadata: bool = True
    preserve_formatting: bool = True
    enable_compression: bool = False
    compression_ratio: float = 0.8
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Configuration for RAG pipeline."""
    retrieval_config: RetrievalConfig = field(default_factory=RetrievalConfig)
    augmentation_config: AugmentationConfig = field(default_factory=AugmentationConfig)
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    enable_streaming: bool = False
    max_concurrent_requests: int = 10
    timeout_seconds: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Result from retrieval strategy."""
    chunks: List[DocumentChunk]
    scores: List[float]
    retrieval_mode: RetrievalMode
    total_candidates: int
    processing_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_empty(self) -> bool:
        """Check if retrieval returned no results."""
        return len(self.chunks) == 0


@dataclass
class AugmentationResult:
    """Result from prompt augmentation."""
    augmented_prompt: str
    original_query: str
    context_chunks: List[DocumentChunk]
    context_length: int
    compression_applied: bool
    processing_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def compression_ratio(self) -> float:
        """Calculate actual compression ratio."""
        if not self.context_chunks:
            return 0.0
        original_length = sum(len(chunk.content) for chunk in self.context_chunks)
        return self.context_length / original_length if original_length > 0 else 0.0


@dataclass
class PipelineStageResult:
    """Result from a pipeline stage."""
    stage: PipelineStage
    status: PipelineStatus
    result_data: Any
    processing_time_ms: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Complete result from RAG pipeline execution."""
    query: str
    augmented_prompt: str
    retrieval_result: RetrievalResult
    augmentation_result: AugmentationResult
    stage_results: List[PipelineStageResult]
    total_processing_time_ms: float
    status: PipelineStatus
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_successful(self) -> bool:
        """Check if pipeline execution was successful."""
        return self.status == PipelineStatus.COMPLETED
    
    @property
    def context_quality_score(self) -> float:
        """Calculate overall context quality score."""
        if not self.retrieval_result.chunks:
            return 0.0
        return np.mean(self.retrieval_result.scores)


@dataclass
class PipelineMetrics:
    """Metrics for pipeline performance."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_processing_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    retrieval_accuracy: float = 0.0
    context_relevance_score: float = 0.0
    throughput_requests_per_second: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0


class IPipelineManager(ABC):
    """Base interface for RAG pipeline managers."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the pipeline manager."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the pipeline manager."""
        pass
    
    @abstractmethod
    async def execute_pipeline(self, query: str, config: Optional[PipelineConfig] = None) -> PipelineResult:
        """
        Execute complete RAG pipeline for a query.
        
        Args:
            query: Input query string
            config: Optional pipeline configuration
            
        Returns:
            PipelineResult with complete execution details
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get_metrics(self) -> PipelineMetrics:
        """Get pipeline performance metrics."""
        pass
    
    @abstractmethod
    async def clear_cache(self) -> bool:
        """Clear pipeline cache."""
        pass


class IRetrievalStrategy(ABC):
    """Base interface for retrieval strategies."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the retrieval strategy."""
        pass

    @abstractmethod
    async def retrieve(self, query: str, config: Optional[RetrievalConfig] = None) -> RetrievalResult:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: Search query string
            config: Optional retrieval configuration

        Returns:
            RetrievalResult with retrieved chunks and metadata
        """
        pass

    @abstractmethod
    def get_supported_modes(self) -> List[RetrievalMode]:
        """
        Get list of supported retrieval modes.

        Returns:
            List of supported RetrievalMode enums
        """
        pass

    @abstractmethod
    async def update_index(self, chunks: List[DocumentChunk]) -> bool:
        """
        Update retrieval index with new chunks.

        Args:
            chunks: List of document chunks to index

        Returns:
            True if index updated successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_retrieval_metrics(self) -> Dict[str, float]:
        """Get retrieval performance metrics."""
        pass


class IAugmentationEngine(ABC):
    """Base interface for prompt augmentation engines."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the augmentation engine."""
        pass

    @abstractmethod
    async def augment_prompt(self, query: str, context_chunks: List[DocumentChunk],
                           config: Optional[AugmentationConfig] = None) -> AugmentationResult:
        """
        Augment prompt with retrieved context.

        Args:
            query: Original query string
            context_chunks: Retrieved context chunks
            config: Optional augmentation configuration

        Returns:
            AugmentationResult with augmented prompt and metadata
        """
        pass

    @abstractmethod
    def get_supported_strategies(self) -> List[AugmentationStrategy]:
        """
        Get list of supported augmentation strategies.

        Returns:
            List of supported AugmentationStrategy enums
        """
        pass

    @abstractmethod
    async def compress_context(self, context: str, target_length: int) -> Tuple[str, float]:
        """
        Compress context to target length.

        Args:
            context: Original context string
            target_length: Target length in characters

        Returns:
            Tuple of (compressed_context, compression_ratio)
        """
        pass

    @abstractmethod
    def validate_template(self, template: str) -> bool:
        """
        Validate augmentation template.

        Args:
            template: Template string to validate

        Returns:
            True if template is valid, False otherwise
        """
        pass
