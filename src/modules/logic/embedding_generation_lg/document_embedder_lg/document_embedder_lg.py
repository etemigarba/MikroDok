"""
Module: document_embedder_lg
Description: Converts document chunks into high-dimensional vectors using transformer models (all-MiniLM-L6-v2)
Phase: 4
Location: /src/modules/logic/embedding_generation_lg/document_embedder_lg/document_embedder_lg.py
"""

# Standard library imports
import hashlib
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import warnings

# Third-party imports
import numpy as np

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Local imports
from src.modules.logic.embedding_generation_lg.base_interfaces import (
    IDocumentEmbedder,
    EmbeddingResult,
    EmbeddingMetadata,
    EmbeddingConfig,
    EmbeddingStatus,
    EmbeddingModel,
    VectorDimensions
)
from src.modules.logic.error_handling_lg import ValidationError
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationSeverity
from src.modules.logic.logging_infrastructure_lg import get_logger


class ModelManager:
    """
    Manages embedding model lifecycle including loading, caching, and device management.
    
    Features:
    - Model loading and caching
    - Device detection and optimization
    - Memory management
    - Model validation
    """
    
    def __init__(self, config: EmbeddingConfig):
        """Initialize model manager."""
        self._config = config
        self._logger = get_logger(__name__)
        self._models: Dict[str, Any] = {}
        self._lock = threading.RLock()
        
        # Device configuration
        self._device = self._detect_optimal_device()
        self._logger.info(f"ModelManager initialized with device: {self._device}")
    
    def _detect_optimal_device(self) -> str:
        """Detect optimal device for model execution."""
        if self._config.device != "auto":
            return self._config.device
        
        if TORCH_AVAILABLE and torch.cuda.is_available():
            return "cuda"
        elif TORCH_AVAILABLE and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"
    
    def load_model(self, model_name: EmbeddingModel) -> Any:
        """Load and cache embedding model."""
        model_key = f"{model_name.value}_{self._device}"
        
        with self._lock:
            if model_key in self._models:
                self._logger.debug(f"Using cached model: {model_name.value}")
                return self._models[model_key]
            
            try:
                if not SENTENCE_TRANSFORMERS_AVAILABLE:
                    raise ImportError("sentence-transformers library not available")
                
                self._logger.info(f"Loading model: {model_name.value}")
                start_time = time.time()
                
                if model_name == EmbeddingModel.CUSTOM and self._config.model_path:
                    model = SentenceTransformer(self._config.model_path, device=self._device)
                else:
                    model = SentenceTransformer(model_name.value, device=self._device)
                
                # Configure model settings
                model.max_seq_length = self._config.max_sequence_length
                
                load_time = time.time() - start_time
                self._logger.info(f"Model loaded successfully in {load_time:.2f}s")
                
                self._models[model_key] = model
                return model
                
            except Exception as e:
                self._logger.error(f"Failed to load model {model_name.value}: {e}")
                raise
    
    def get_model_info(self, model_name: EmbeddingModel) -> Dict[str, Any]:
        """Get information about a model."""
        try:
            model = self.load_model(model_name)
            
            return {
                "model_name": model_name.value,
                "device": self._device,
                "max_sequence_length": getattr(model, 'max_seq_length', self._config.max_sequence_length),
                "embedding_dimension": self._get_embedding_dimension(model_name),
                "model_loaded": True,
                "device_available": self._device != "cpu" or not TORCH_AVAILABLE
            }
        except Exception as e:
            return {
                "model_name": model_name.value,
                "device": self._device,
                "error": str(e),
                "model_loaded": False
            }
    
    def _get_embedding_dimension(self, model_name: EmbeddingModel) -> int:
        """Get embedding dimension for model."""
        dimension_map = {
            EmbeddingModel.ALL_MINILM_L6_V2: VectorDimensions.MINILM_L6.value,
            EmbeddingModel.ALL_MINILM_L12_V2: VectorDimensions.MINILM_L12.value,
            EmbeddingModel.ALL_MPNET_BASE_V2: VectorDimensions.MPNET_BASE.value,
            EmbeddingModel.DISTILBERT_BASE: VectorDimensions.DISTILBERT.value,
            EmbeddingModel.CUSTOM: VectorDimensions.CUSTOM.value
        }
        return dimension_map.get(model_name, VectorDimensions.CUSTOM.value)


class VectorProcessor:
    """
    Processes and validates embedding vectors.
    
    Features:
    - Vector normalization
    - Quality validation
    - Dimension verification
    - Statistical analysis
    """
    
    def __init__(self, config: EmbeddingConfig):
        """Initialize vector processor."""
        self._config = config
        self._logger = get_logger(__name__)
    
    def process_vector(self, vector: np.ndarray, chunk_id: str) -> Tuple[np.ndarray, Dict[str, float]]:
        """Process and validate embedding vector."""
        try:
            # Ensure vector is numpy array
            if not isinstance(vector, np.ndarray):
                vector = np.array(vector)
            
            # Validate dimensions
            if vector.ndim != 1:
                raise ValueError(f"Expected 1D vector, got {vector.ndim}D")
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(vector)
            
            # Normalize if configured
            if self._config.normalize_embeddings:
                vector = self._normalize_vector(vector)
            
            # Validate quality
            if quality_metrics.get('magnitude', 0) < self._config.quality_threshold:
                self._logger.warning(f"Low quality vector for chunk {chunk_id}")
            
            return vector, quality_metrics
            
        except Exception as e:
            self._logger.error(f"Vector processing failed for chunk {chunk_id}: {e}")
            raise
    
    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize vector to unit length."""
        norm = np.linalg.norm(vector)
        if norm == 0:
            self._logger.warning("Zero vector encountered during normalization")
            return vector
        return vector / norm
    
    def _calculate_quality_metrics(self, vector: np.ndarray) -> Dict[str, float]:
        """Calculate quality metrics for vector."""
        return {
            'magnitude': float(np.linalg.norm(vector)),
            'mean': float(np.mean(vector)),
            'std': float(np.std(vector)),
            'min': float(np.min(vector)),
            'max': float(np.max(vector)),
            'sparsity': float(np.count_nonzero(vector) / len(vector)),
            'entropy': float(self._calculate_entropy(vector))
        }
    
    def _calculate_entropy(self, vector: np.ndarray) -> float:
        """Calculate entropy of vector values."""
        try:
            # Normalize to probabilities
            abs_vector = np.abs(vector)
            if np.sum(abs_vector) == 0:
                return 0.0
            
            probs = abs_vector / np.sum(abs_vector)
            probs = probs[probs > 0]  # Remove zeros
            
            return -np.sum(probs * np.log2(probs))
        except Exception:
            return 0.0


class EmbeddingGenerator:
    """
    Core embedding generation engine.
    
    Features:
    - Text preprocessing
    - Batch processing
    - Error handling
    - Performance monitoring
    """
    
    def __init__(self, config: EmbeddingConfig):
        """Initialize embedding generator."""
        self._config = config
        self._logger = get_logger(__name__)
        self._model_manager = ModelManager(config)
        self._vector_processor = VectorProcessor(config)
        
        # Performance tracking
        self._generation_count = 0
        self._total_processing_time = 0.0
        self._lock = threading.RLock()
    
    def generate_single(self, text: str, chunk_id: str, document_id: str) -> EmbeddingResult:
        """Generate embedding for single text chunk."""
        start_time = time.time()
        
        try:
            # Validate input
            validation_errors = self._validate_input(text)
            if validation_errors:
                return EmbeddingResult(
                    status=EmbeddingStatus.FAILED,
                    chunk_id=chunk_id,
                    error_message=f"Validation failed: {validation_errors[0].message}"
                )
            
            # Preprocess text
            processed_text = self._preprocess_text(text)
            
            # Load model
            model = self._model_manager.load_model(self._config.model_name)
            
            # Generate embedding
            embedding_vector = model.encode(processed_text, convert_to_numpy=True)
            
            # Process vector
            processed_vector, quality_metrics = self._vector_processor.process_vector(
                embedding_vector, chunk_id
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            # Create metadata
            metadata = EmbeddingMetadata(
                chunk_id=chunk_id,
                document_id=document_id,
                model_name=self._config.model_name.value,
                model_version="1.0.0",
                vector_dimensions=len(processed_vector),
                processing_timestamp=datetime.now(),
                processing_duration_ms=processing_time,
                chunk_text_length=len(text),
                chunk_token_count=len(processed_text.split()),
                quality_metrics=quality_metrics
            )
            
            # Update statistics
            with self._lock:
                self._generation_count += 1
                self._total_processing_time += processing_time
            
            return EmbeddingResult(
                status=EmbeddingStatus.SUCCESS,
                chunk_id=chunk_id,
                vector=processed_vector,
                metadata=metadata,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self._logger.error(f"Embedding generation failed for chunk {chunk_id}: {e}")
            
            return EmbeddingResult(
                status=EmbeddingStatus.FAILED,
                chunk_id=chunk_id,
                error_message=str(e),
                processing_time_ms=processing_time
            )
    
    def generate_batch(self, texts: List[str], chunk_ids: List[str], 
                      document_ids: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for batch of text chunks."""
        if len(texts) != len(chunk_ids) or len(texts) != len(document_ids):
            raise ValueError("Input lists must have same length")
        
        start_time = time.time()
        results = []
        
        try:
            # Validate all inputs first
            valid_indices = []
            for i, text in enumerate(texts):
                validation_errors = self._validate_input(text)
                if validation_errors:
                    results.append(EmbeddingResult(
                        status=EmbeddingStatus.FAILED,
                        chunk_id=chunk_ids[i],
                        error_message=f"Validation failed: {validation_errors[0].message}"
                    ))
                else:
                    valid_indices.append(i)
            
            if not valid_indices:
                return results
            
            # Process valid texts
            valid_texts = [self._preprocess_text(texts[i]) for i in valid_indices]
            valid_chunk_ids = [chunk_ids[i] for i in valid_indices]
            valid_document_ids = [document_ids[i] for i in valid_indices]
            
            # Load model
            model = self._model_manager.load_model(self._config.model_name)
            
            # Generate embeddings in batch
            embedding_vectors = model.encode(valid_texts, convert_to_numpy=True, batch_size=self._config.batch_size)
            
            # Process each vector
            for i, vector in enumerate(embedding_vectors):
                try:
                    processed_vector, quality_metrics = self._vector_processor.process_vector(
                        vector, valid_chunk_ids[i]
                    )
                    
                    processing_time = (time.time() - start_time) * 1000 / len(valid_texts)
                    
                    metadata = EmbeddingMetadata(
                        chunk_id=valid_chunk_ids[i],
                        document_id=valid_document_ids[i],
                        model_name=self._config.model_name.value,
                        model_version="1.0.0",
                        vector_dimensions=len(processed_vector),
                        processing_timestamp=datetime.now(),
                        processing_duration_ms=processing_time,
                        chunk_text_length=len(texts[valid_indices[i]]),
                        chunk_token_count=len(valid_texts[i].split()),
                        quality_metrics=quality_metrics
                    )
                    
                    results.append(EmbeddingResult(
                        status=EmbeddingStatus.SUCCESS,
                        chunk_id=valid_chunk_ids[i],
                        vector=processed_vector,
                        metadata=metadata,
                        processing_time_ms=processing_time
                    ))
                    
                except Exception as e:
                    results.append(EmbeddingResult(
                        status=EmbeddingStatus.FAILED,
                        chunk_id=valid_chunk_ids[i],
                        error_message=str(e)
                    ))
            
            # Update statistics
            with self._lock:
                self._generation_count += len(valid_indices)
                self._total_processing_time += (time.time() - start_time) * 1000
            
            return results
            
        except Exception as e:
            self._logger.error(f"Batch embedding generation failed: {e}")
            # Return failed results for remaining items
            for i in range(len(results), len(texts)):
                results.append(EmbeddingResult(
                    status=EmbeddingStatus.FAILED,
                    chunk_id=chunk_ids[i],
                    error_message=str(e)
                ))
            return results
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for embedding generation."""
        # Basic text cleaning
        text = text.strip()
        
        # Truncate if too long
        if len(text) > self._config.max_sequence_length * 4:  # Rough token estimation
            text = text[:self._config.max_sequence_length * 4]
            self._logger.debug("Text truncated due to length limit")
        
        return text
    
    def _validate_input(self, text: str) -> List[ValidationError]:
        """Validate input text."""
        errors = []
        
        if not text or not text.strip():
            errors.append(ValidationError(
                field="text",
                message="Text cannot be empty",
                severity=ValidationSeverity.ERROR
            ))
        
        if len(text.strip()) < 3:
            errors.append(ValidationError(
                field="text",
                message="Text too short for meaningful embedding",
                severity=ValidationSeverity.WARNING
            ))
        
        return errors
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get generation statistics."""
        with self._lock:
            avg_time = self._total_processing_time / max(self._generation_count, 1)
            return {
                "total_generations": self._generation_count,
                "total_processing_time_ms": self._total_processing_time,
                "average_processing_time_ms": avg_time,
                "model_name": self._config.model_name.value,
                "device": self._model_manager._device
            }


class DocumentEmbedder(IDocumentEmbedder):
    """
    Main document embedder that converts document chunks into high-dimensional vectors.
    
    Features:
    - Multiple embedding model support
    - Batch processing optimization
    - Quality validation and metrics
    - Comprehensive error handling
    - Performance monitoring
    - Device optimization (CPU/GPU/MPS)
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """Initialize document embedder."""
        self._config = config or EmbeddingConfig()
        self._logger = get_logger(__name__)
        self._generator = EmbeddingGenerator(self._config)
        
        self._logger.info("DocumentEmbedder initialized successfully")
    
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
        return self._generator.generate_single(text, chunk_id, document_id)
    
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
        return self._generator.generate_batch(texts, chunk_ids, document_ids)
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current embedding model.
        
        Returns:
            Dictionary with model information
        """
        model_info = self._generator._model_manager.get_model_info(self._config.model_name)
        stats = self._generator.get_statistics()
        
        return {
            **model_info,
            "statistics": stats,
            "configuration": {
                "batch_size": self._config.batch_size,
                "max_sequence_length": self._config.max_sequence_length,
                "normalize_embeddings": self._config.normalize_embeddings,
                "quality_threshold": self._config.quality_threshold
            }
        }
    
    def validate_input(self, text: str) -> List[ValidationError]:
        """
        Validate input text for embedding generation.
        
        Args:
            text: Text to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        return self._generator._validate_input(text)
