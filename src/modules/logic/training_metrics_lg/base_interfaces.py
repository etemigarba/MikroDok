"""
Module: base_interfaces
Description: Base interfaces and data structures for training metrics functionality
Phase: 4
Location: /src/modules/logic/training_metrics_lg/
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
from datetime import datetime
from pathlib import Path
import numpy as np


class LossType(Enum):
    """Types of loss functions."""
    CROSS_ENTROPY = "cross_entropy"
    MSE = "mse"
    MAE = "mae"
    HUBER = "huber"
    FOCAL = "focal"
    CUSTOM = "custom"


class MetricType(Enum):
    """Types of training metrics."""
    LOSS = "loss"
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    PERPLEXITY = "perplexity"
    BLEU = "bleu"
    ROUGE = "rouge"
    CUSTOM = "custom"


class AggregationStrategy(Enum):
    """Metric aggregation strategies."""
    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    STD = "std"
    PERCENTILE = "percentile"
    WEIGHTED_AVERAGE = "weighted_average"
    EXPONENTIAL_MOVING_AVERAGE = "ema"


class ExportFormat(Enum):
    """Metric export formats."""
    JSON = "json"
    CSV = "csv"
    TENSORBOARD = "tensorboard"
    WANDB = "wandb"
    MLFLOW = "mlflow"
    CUSTOM = "custom"


class EarlyStoppingCriteria(Enum):
    """Early stopping criteria."""
    VALIDATION_LOSS = "validation_loss"
    VALIDATION_ACCURACY = "validation_accuracy"
    TRAINING_LOSS = "training_loss"
    CUSTOM_METRIC = "custom_metric"
    COMBINED = "combined"


@dataclass
class LossConfiguration:
    """Configuration for loss calculation."""
    loss_type: LossType
    reduction: str = "mean"  # mean, sum, none
    weight: Optional[np.ndarray] = None
    ignore_index: int = -100
    label_smoothing: float = 0.0
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricConfiguration:
    """Configuration for metric calculation."""
    metric_type: MetricType
    average: str = "macro"  # macro, micro, weighted
    zero_division: Union[str, int] = "warn"
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregationConfiguration:
    """Configuration for metric aggregation."""
    strategy: AggregationStrategy
    window_size: int = 100
    percentile: float = 0.95
    alpha: float = 0.1  # For EMA
    weights: Optional[List[float]] = None
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EarlyStoppingConfiguration:
    """Configuration for early stopping."""
    criteria: EarlyStoppingCriteria
    patience: int = 10
    min_delta: float = 0.001
    restore_best_weights: bool = True
    mode: str = "min"  # min, max
    baseline: Optional[float] = None
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportConfiguration:
    """Configuration for metric export."""
    format: ExportFormat
    output_path: Path
    include_metadata: bool = True
    compression: Optional[str] = None
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LossResult:
    """Result of loss calculation."""
    loss_value: float
    loss_type: LossType
    batch_size: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricResult:
    """Result of metric calculation."""
    metric_value: float
    metric_type: MetricType
    epoch: int
    step: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedMetrics:
    """Aggregated training metrics."""
    metrics: Dict[str, float]
    aggregation_strategy: AggregationStrategy
    window_size: int
    timestamp: datetime
    confidence_score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EarlyStoppingResult:
    """Result of early stopping evaluation."""
    should_stop: bool
    current_patience: int
    best_value: float
    improvement: float
    criteria: EarlyStoppingCriteria
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportResult:
    """Result of metric export operation."""
    success: bool
    output_path: Path
    format: ExportFormat
    record_count: int
    file_size_bytes: int
    timestamp: datetime
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ILossCalculator(ABC):
    """Base interface for loss calculation."""

    @abstractmethod
    def calculate_loss(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        config: LossConfiguration
    ) -> LossResult:
        """Calculate loss between predictions and targets."""
        pass

    @abstractmethod
    def calculate_batch_loss(
        self,
        batch_predictions: List[np.ndarray],
        batch_targets: List[np.ndarray],
        config: LossConfiguration
    ) -> List[LossResult]:
        """Calculate loss for multiple batches."""
        pass


class IMetricAggregator(ABC):
    """Base interface for metric aggregation."""

    @abstractmethod
    def add_metric(self, metric: MetricResult) -> None:
        """Add a metric for aggregation."""
        pass

    @abstractmethod
    def aggregate_metrics(
        self,
        config: AggregationConfiguration
    ) -> AggregatedMetrics:
        """Aggregate collected metrics."""
        pass

    @abstractmethod
    def get_metric_history(
        self,
        metric_type: MetricType,
        window_size: Optional[int] = None
    ) -> List[MetricResult]:
        """Get metric history."""
        pass


class IEarlyStopping(ABC):
    """Base interface for early stopping."""

    @abstractmethod
    def update(
        self,
        current_value: float,
        epoch: int
    ) -> EarlyStoppingResult:
        """Update early stopping with current metric value."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset early stopping state."""
        pass

    @abstractmethod
    def get_best_value(self) -> float:
        """Get the best metric value seen so far."""
        pass


class IMetricExporter(ABC):
    """Base interface for metric export."""

    @abstractmethod
    def export_metrics(
        self,
        metrics: List[MetricResult],
        config: ExportConfiguration
    ) -> ExportResult:
        """Export metrics to specified format."""
        pass

    @abstractmethod
    def export_aggregated_metrics(
        self,
        aggregated_metrics: AggregatedMetrics,
        config: ExportConfiguration
    ) -> ExportResult:
        """Export aggregated metrics."""
        pass
