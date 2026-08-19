"""
Module: base_interfaces
Description: Base interfaces and common data structures for embedding generation modules
Phase: 4
Location: /src/modules/logic/embedding_generation_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Iterator
import numpy as np

# Local imports
from src.modules.logic.error_handling_lg import ValidationError


class EmbeddingStatus(Enum):
    """Status of embedding operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchStatus(Enum):
    """Status of batch processing operation."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class CacheStatus(Enum):
    """Status of cache operation."""
    HIT = "hit"
    MISS = "miss"
    EVICTED = "evicted"
    STORED = "stored"
    ERROR = "error"


class EmbeddingModel(Enum):
    """Supported embedding models."""
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    ALL_MINILM_L12_V2 = "all-MiniLM-L12-v2"
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"
    DISTILBERT_BASE = "distilbert-base-uncased"
    CUSTOM = "custom"


class VectorDimensions(Enum):
    """Standard vector dimensions for different models."""
    MINILM_L6 = 384
    MINILM_L12 = 384
    MPNET_BASE = 768
    DISTILBERT = 768
    CUSTOM = 512


@dataclass
class EmbeddingMetadata:
    """Metadata for embedding operations."""
    chunk_id: str
    document_id: str
    model_name: str
    model_version: str
    vector_dimensions: int
    processing_timestamp: datetime
    processing_duration_ms: float
    chunk_text_length: int
    chunk_token_count: int
    confidence_score: float = 1.0
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    technical_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    status: EmbeddingStatus
    chunk_id: str
    vector: Optional[np.ndarray] = None
    metadata: Optional[EmbeddingMetadata] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


@dataclass
class BatchProcessingResult:
    """Result of batch processing operation."""
    status: BatchStatus
    batch_id: str
    total_chunks: int
    processed_chunks: int
    successful_embeddings: int
    failed_embeddings: int
    embeddings: List[EmbeddingResult] = field(default_factory=list)
    processing_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CacheResult:
    """Result of cache operation."""
    status: CacheStatus
    chunk_id: str
    vector: Optional[np.ndarray] = None
    hit_count: int = 0
    last_accessed: Optional[datetime] = None
    cache_size_bytes: int = 0


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation."""
    model_name: EmbeddingModel = EmbeddingModel.ALL_MINILM_L6_V2
    model_path: Optional[str] = None
    device: str = "cpu"  # cpu, cuda, mps
    max_sequence_length: int = 512
    normalize_embeddings: bool = True
    batch_size: int = 32
    enable_caching: bool = True
    cache_size_limit: int = 10000
    processing_timeout_seconds: int = 300
    quality_threshold: float = 0.7
    retry_attempts: int = 3
    custom_model_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    batch_size: int = 64
    max_batch_size: int = 128
    min_batch_size: int = 16
    adaptive_batching: bool = True
    memory_limit_mb: int = 2048
    processing_timeout_seconds: int = 600
    max_concurrent_batches: int = 4
    queue_size_limit: int = 1000
    priority_processing: bool = True
    auto_optimization: bool = True


@dataclass
class CacheConfig:
    """Configuration for embedding cache."""
    max_cache_size: int = 10000
    memory_limit_mb: int = 2048
    eviction_policy: str = "lru"  # lru, lfu, fifo
    ttl_seconds: Optional[int] = None
    enable_persistence: bool = False
    persistence_path: Optional[str] = None
    compression_enabled: bool = True
    preload_enabled: bool = False
    hit_rate_threshold: float = 0.8


class IDocumentEmbedder(ABC):
    """Base interface for document embedding generators."""
    
    @abstractmethod
    def generate_embedding(self, text: str, chunk_id: str, document_id: str) -> EmbeddingResult:
        """
        Generate embedding for a single text chunk.
        
        Args:
            text: Text content to embed
            chunk_id: Unique identifier for the chunk
            document_id: Identifier of the source document
            
        Returns:
            EmbeddingResult with vector and metadata
        """
        pass
    
    @abstractmethod
    def generate_embeddings_batch(self, texts: List[str], chunk_ids: List[str], 
                                 document_ids: List[str]) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple text chunks.
        
        Args:
            texts: List of text content to embed
            chunk_ids: List of unique identifiers for chunks
            document_ids: List of source document identifiers
            
        Returns:
            List of EmbeddingResult objects
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current embedding model.
        
        Returns:
            Dictionary with model information
        """
        pass
    
    @abstractmethod
    def validate_input(self, text: str) -> List[ValidationError]:
        """
        Validate input text for embedding generation.
        
        Args:
            text: Text to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        pass


class IBatchProcessor(ABC):
    """Base interface for batch processing of embeddings."""
    
    @abstractmethod
    def add_to_queue(self, text: str, chunk_id: str, document_id: str, priority: int = 0) -> bool:
        """
        Add a text chunk to the processing queue.
        
        Args:
            text: Text content to process
            chunk_id: Unique identifier for the chunk
            document_id: Source document identifier
            priority: Processing priority (higher = more urgent)
            
        Returns:
            True if successfully queued, False otherwise
        """
        pass
    
    @abstractmethod
    def process_batch(self, batch_size: Optional[int] = None) -> BatchProcessingResult:
        """
        Process a batch of queued items.
        
        Args:
            batch_size: Optional override for batch size
            
        Returns:
            BatchProcessingResult with processing details
        """
        pass
    
    @abstractmethod
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current status of the processing queue.
        
        Returns:
            Dictionary with queue statistics
        """
        pass
    
    @abstractmethod
    def clear_queue(self) -> bool:
        """
        Clear all items from the processing queue.
        
        Returns:
            True if successfully cleared, False otherwise
        """
        pass


class IEmbeddingCache(ABC):
    """Base interface for embedding cache systems."""
    
    @abstractmethod
    def get(self, chunk_id: str) -> CacheResult:
        """
        Retrieve embedding from cache.
        
        Args:
            chunk_id: Unique identifier for the chunk
            
        Returns:
            CacheResult with vector if found
        """
        pass
    
    @abstractmethod
    def put(self, chunk_id: str, vector: np.ndarray, metadata: Optional[EmbeddingMetadata] = None) -> bool:
        """
        Store embedding in cache.
        
        Args:
            chunk_id: Unique identifier for the chunk
            vector: Embedding vector to store
            metadata: Optional metadata for the embedding
            
        Returns:
            True if successfully stored, False otherwise
        """
        pass
    
    @abstractmethod
    def evict(self, chunk_id: str) -> bool:
        """
        Remove embedding from cache.
        
        Args:
            chunk_id: Unique identifier for the chunk
            
        Returns:
            True if successfully evicted, False otherwise
        """
        pass
    
    @abstractmethod
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        pass
    
    @abstractmethod
    def clear_cache(self) -> bool:
        """
        Clear all entries from cache.
        
        Returns:
            True if successfully cleared, False otherwise
        """
        pass
