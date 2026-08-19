"""
Module: base_interfaces
Description: Base interfaces and data structures for training data pipeline components
Phase: 4
Location: /src/modules/logic/training_data_pipeline_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Iterator, AsyncIterator
import numpy as np

# Third-party imports
import torch
from torch.utils.data import DataLoader


class DataFormat(Enum):
    """Supported data formats for training."""
    TEXT = "text"
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"
    HDF5 = "hdf5"
    NUMPY = "numpy"
    TORCH = "torch"


class AugmentationType(Enum):
    """Types of data augmentation techniques."""
    SYNONYM_REPLACEMENT = "synonym_replacement"
    RANDOM_INSERTION = "random_insertion"
    RANDOM_SWAP = "random_swap"
    RANDOM_DELETION = "random_deletion"
    BACK_TRANSLATION = "back_translation"
    PARAPHRASING = "paraphrasing"
    NOISE_INJECTION = "noise_injection"
    CONTEXT_SHUFFLING = "context_shuffling"


class ValidationLevel(Enum):
    """Levels of data validation."""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    COMPREHENSIVE = "comprehensive"


class BatchStrategy(Enum):
    """Batch generation strategies."""
    SEQUENTIAL = "sequential"
    RANDOM = "random"
    BALANCED = "balanced"
    STRATIFIED = "stratified"
    DYNAMIC = "dynamic"


class DataStatus(Enum):
    """Status of data processing operations."""
    PENDING = "pending"
    LOADING = "loading"
    PROCESSING = "processing"
    VALIDATING = "validating"
    AUGMENTING = "augmenting"
    BATCHING = "batching"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DataLoaderConfig:
    """Configuration for data loading operations."""
    data_path: Path
    format: DataFormat
    batch_size: int = 32
    shuffle: bool = True
    num_workers: int = 4
    pin_memory: bool = True
    drop_last: bool = False
    prefetch_factor: int = 2
    persistent_workers: bool = True
    max_memory_usage_mb: int = 2048
    cache_enabled: bool = True
    validation_split: float = 0.2
    test_split: float = 0.1
    random_seed: int = 42
    enable_streaming: bool = False
    chunk_size: int = 1000
    compression: Optional[str] = None
    encoding: str = "utf-8"
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AugmentationConfig:
    """Configuration for data augmentation operations."""
    enabled_techniques: List[AugmentationType] = field(default_factory=list)
    augmentation_probability: float = 0.5
    max_augmentations_per_sample: int = 3
    preserve_original: bool = True
    synonym_replacement_ratio: float = 0.1
    random_insertion_ratio: float = 0.1
    random_swap_ratio: float = 0.1
    random_deletion_ratio: float = 0.1
    noise_level: float = 0.01
    back_translation_languages: List[str] = field(default_factory=lambda: ["de", "fr"])
    paraphrase_model: Optional[str] = None
    context_window_size: int = 512
    min_text_length: int = 10
    max_text_length: int = 2048
    quality_threshold: float = 0.8
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationConfig:
    """Configuration for data validation operations."""
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    check_format: bool = True
    check_encoding: bool = True
    check_completeness: bool = True
    check_duplicates: bool = True
    check_quality: bool = True
    check_consistency: bool = True
    min_text_length: int = 5
    max_text_length: int = 8192
    min_quality_score: float = 0.6
    max_duplicate_ratio: float = 0.1
    required_fields: List[str] = field(default_factory=list)
    forbidden_patterns: List[str] = field(default_factory=list)
    allowed_languages: List[str] = field(default_factory=lambda: ["en"])
    quality_metrics: List[str] = field(default_factory=lambda: ["readability", "coherence"])
    custom_validators: List[str] = field(default_factory=list)
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchConfig:
    """Configuration for batch generation operations."""
    batch_size: int = 32
    strategy: BatchStrategy = BatchStrategy.RANDOM
    max_sequence_length: int = 512
    padding_token: str = "<pad>"
    truncation_strategy: str = "longest_first"
    dynamic_padding: bool = True
    sort_by_length: bool = False
    group_by_length: bool = False
    length_bucket_size: int = 10
    drop_last_batch: bool = False
    pin_memory: bool = True
    collate_fn: Optional[str] = None
    tokenizer_config: Dict[str, Any] = field(default_factory=dict)
    special_tokens: Dict[str, str] = field(default_factory=dict)
    attention_mask: bool = True
    return_tensors: str = "pt"
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSample:
    """Individual data sample for training."""
    sample_id: str
    text: str
    label: Optional[Union[str, int, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_document: Optional[str] = None
    chunk_index: Optional[int] = None
    quality_score: Optional[float] = None
    augmented: bool = False
    augmentation_type: Optional[AugmentationType] = None
    created_at: datetime = field(default_factory=lambda: datetime.now())
    processed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert sample to dictionary."""
        return {
            'sample_id': self.sample_id,
            'text': self.text,
            'label': self.label,
            'metadata': self.metadata,
            'source_document': self.source_document,
            'chunk_index': self.chunk_index,
            'quality_score': self.quality_score,
            'augmented': self.augmented,
            'augmentation_type': self.augmentation_type.value if self.augmentation_type else None,
            'created_at': self.created_at.isoformat(),
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }


@dataclass
class DataBatch:
    """Batch of training data samples."""
    batch_id: str
    samples: List[DataSample]
    input_ids: Optional[torch.Tensor] = None
    attention_mask: Optional[torch.Tensor] = None
    labels: Optional[torch.Tensor] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 0
    sequence_length: int = 0
    memory_usage_mb: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now())
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.batch_size:
            self.batch_size = len(self.samples)
    
    def to_device(self, device: torch.device) -> 'DataBatch':
        """Move batch tensors to specified device."""
        if self.input_ids is not None:
            self.input_ids = self.input_ids.to(device)
        if self.attention_mask is not None:
            self.attention_mask = self.attention_mask.to(device)
        if self.labels is not None:
            self.labels = self.labels.to(device)
        return self


@dataclass
class LoadingResult:
    """Result of data loading operation."""
    status: DataStatus
    total_samples: int
    loaded_samples: int
    failed_samples: int
    train_samples: int = 0
    validation_samples: int = 0
    test_samples: int = 0
    loading_time_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    data_format: Optional[DataFormat] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class AugmentationResult:
    """Result of data augmentation operation."""
    status: DataStatus
    original_samples: int
    augmented_samples: int
    total_samples: int
    augmentation_techniques: List[AugmentationType] = field(default_factory=list)
    augmentation_time_seconds: float = 0.0
    quality_improvement: float = 0.0
    diversity_score: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class ValidationResult:
    """Result of data validation operation."""
    status: DataStatus
    total_samples: int
    valid_samples: int
    invalid_samples: int
    validation_level: ValidationLevel
    quality_score: float = 0.0
    completeness_score: float = 0.0
    consistency_score: float = 0.0
    duplicate_ratio: float = 0.0
    validation_time_seconds: float = 0.0
    issues_found: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class BatchGenerationResult:
    """Result of batch generation operation."""
    status: DataStatus
    total_batches: int
    generated_batches: int
    total_samples: int
    batch_strategy: BatchStrategy
    average_batch_size: float = 0.0
    average_sequence_length: float = 0.0
    generation_time_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    padding_efficiency: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


class IDataLoader(ABC):
    """Base interface for data loading operations."""

    @abstractmethod
    def load_data(self, config: DataLoaderConfig) -> LoadingResult:
        """
        Load training data from specified source.

        Args:
            config: Data loading configuration

        Returns:
            LoadingResult with loading details
        """
        pass

    @abstractmethod
    def get_train_loader(self) -> Optional[DataLoader]:
        """Get training data loader."""
        pass

    @abstractmethod
    def get_validation_loader(self) -> Optional[DataLoader]:
        """Get validation data loader."""
        pass

    @abstractmethod
    def get_test_loader(self) -> Optional[DataLoader]:
        """Get test data loader."""
        pass

    @abstractmethod
    def get_sample_count(self) -> Tuple[int, int, int]:
        """
        Get sample counts for train, validation, and test sets.

        Returns:
            Tuple of (train_count, validation_count, test_count)
        """
        pass

    @abstractmethod
    def get_data_statistics(self) -> Dict[str, Any]:
        """Get comprehensive data statistics."""
        pass

    @abstractmethod
    def clear_cache(self) -> bool:
        """Clear data cache."""
        pass


class IDataAugmentation(ABC):
    """Base interface for data augmentation operations."""

    @abstractmethod
    def augment_sample(self, sample: DataSample, config: AugmentationConfig) -> List[DataSample]:
        """
        Augment a single data sample.

        Args:
            sample: Original data sample
            config: Augmentation configuration

        Returns:
            List of augmented samples (including original if preserve_original=True)
        """
        pass

    @abstractmethod
    def augment_batch(self, samples: List[DataSample], config: AugmentationConfig) -> AugmentationResult:
        """
        Augment a batch of data samples.

        Args:
            samples: List of original samples
            config: Augmentation configuration

        Returns:
            AugmentationResult with augmentation details
        """
        pass

    @abstractmethod
    def get_available_techniques(self) -> List[AugmentationType]:
        """Get list of available augmentation techniques."""
        pass

    @abstractmethod
    def estimate_augmentation_time(self, sample_count: int, config: AugmentationConfig) -> float:
        """
        Estimate time required for augmentation.

        Args:
            sample_count: Number of samples to augment
            config: Augmentation configuration

        Returns:
            Estimated time in seconds
        """
        pass


class IDataValidator(ABC):
    """Base interface for data validation operations."""

    @abstractmethod
    def validate_sample(self, sample: DataSample, config: ValidationConfig) -> bool:
        """
        Validate a single data sample.

        Args:
            sample: Data sample to validate
            config: Validation configuration

        Returns:
            True if sample is valid
        """
        pass

    @abstractmethod
    def validate_batch(self, samples: List[DataSample], config: ValidationConfig) -> ValidationResult:
        """
        Validate a batch of data samples.

        Args:
            samples: List of samples to validate
            config: Validation configuration

        Returns:
            ValidationResult with validation details
        """
        pass

    @abstractmethod
    def validate_dataset(self, data_path: Path, config: ValidationConfig) -> ValidationResult:
        """
        Validate entire dataset.

        Args:
            data_path: Path to dataset
            config: Validation configuration

        Returns:
            ValidationResult with validation details
        """
        pass

    @abstractmethod
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get current validation rules."""
        pass


class IBatchGenerator(ABC):
    """Base interface for batch generation operations."""

    @abstractmethod
    def generate_batch(self, samples: List[DataSample], config: BatchConfig) -> DataBatch:
        """
        Generate a single training batch.

        Args:
            samples: List of data samples
            config: Batch configuration

        Returns:
            DataBatch ready for training
        """
        pass

    @abstractmethod
    def generate_batches(self, samples: List[DataSample], config: BatchConfig) -> Iterator[DataBatch]:
        """
        Generate multiple training batches.

        Args:
            samples: List of data samples
            config: Batch configuration

        Yields:
            DataBatch objects ready for training
        """
        pass

    @abstractmethod
    async def generate_batches_async(self, samples: List[DataSample],
                                   config: BatchConfig) -> AsyncIterator[DataBatch]:
        """
        Generate training batches asynchronously.

        Args:
            samples: List of data samples
            config: Batch configuration

        Yields:
            DataBatch objects ready for training
        """
        pass

    @abstractmethod
    def estimate_batch_count(self, sample_count: int, config: BatchConfig) -> int:
        """
        Estimate number of batches for given samples.

        Args:
            sample_count: Number of samples
            config: Batch configuration

        Returns:
            Estimated batch count
        """
        pass

    @abstractmethod
    def get_batch_statistics(self) -> Dict[str, Any]:
        """Get batch generation statistics."""
        pass
