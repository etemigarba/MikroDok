"""
Module: base_interfaces
Description: Base interfaces and data structures for training orchestration functionality
Phase: 4
Location: /src/modules/logic/training_orchestration_lg/
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union, AsyncIterator, Callable
import asyncio
from datetime import datetime, timedelta
import uuid
from pathlib import Path


class TrainingStatus(Enum):
    """Training session status enumeration."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESUMING = "resuming"


class TrainingPriority(Enum):
    """Training job priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class HyperparameterType(Enum):
    """Types of hyperparameters."""
    LEARNING_RATE = "learning_rate"
    BATCH_SIZE = "batch_size"
    EPOCHS = "epochs"
    OPTIMIZER = "optimizer"
    SCHEDULER = "scheduler"
    REGULARIZATION = "regularization"
    ARCHITECTURE = "architecture"
    CUSTOM = "custom"


class OptimizationStrategy(Enum):
    """Hyperparameter optimization strategies."""
    MANUAL = "manual"
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"
    ADAPTIVE = "adaptive"


@dataclass
class TrainingMetrics:
    """Training performance metrics."""
    epoch: int
    step: int
    loss: float
    accuracy: Optional[float] = None
    validation_loss: Optional[float] = None
    validation_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    batch_size: int = 32
    processing_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    gpu_utilization: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    custom_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class HyperparameterConfig:
    """Configuration for a single hyperparameter."""
    name: str
    value: Any
    param_type: HyperparameterType
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step_size: Optional[float] = None
    choices: Optional[List[Any]] = None
    is_tunable: bool = True
    description: Optional[str] = None
    validation_fn: Optional[Callable[[Any], bool]] = None


@dataclass
class TrainingConfig:
    """Complete training configuration."""
    model_name: str
    dataset_path: Path
    output_dir: Path
    hyperparameters: Dict[str, HyperparameterConfig]
    max_epochs: int = 100
    early_stopping_patience: int = 10
    checkpoint_interval: int = 1000
    validation_split: float = 0.2
    save_best_only: bool = True
    enable_mixed_precision: bool = False
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    warmup_steps: int = 0
    logging_steps: int = 100
    evaluation_strategy: str = "epoch"
    save_strategy: str = "epoch"
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingSession:
    """Training session information."""
    session_id: str
    model_id: str
    config: TrainingConfig
    status: TrainingStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    resumed_at: Optional[datetime] = None
    current_epoch: int = 0
    current_step: int = 0
    total_steps: int = 0
    best_metric: Optional[float] = None
    last_checkpoint_path: Optional[Path] = None
    error_message: Optional[str] = None
    metrics_history: List[TrainingMetrics] = field(default_factory=list)
    resource_allocation: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get total training duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return datetime.now() - self.started_at
        return None
    
    @property
    def progress_percentage(self) -> float:
        """Get training progress as percentage."""
        if self.total_steps > 0:
            return min(100.0, (self.current_step / self.total_steps) * 100.0)
        elif self.config.max_epochs > 0:
            return min(100.0, (self.current_epoch / self.config.max_epochs) * 100.0)
        return 0.0


@dataclass
class TrainingJob:
    """Training job in scheduler queue."""
    job_id: str
    session_id: str
    priority: TrainingPriority
    config: TrainingConfig
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    estimated_duration: Optional[timedelta] = None
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulerStatus:
    """Training scheduler status information."""
    active_jobs: int
    queued_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_capacity: int
    available_capacity: int
    average_queue_time: timedelta
    average_execution_time: timedelta
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionResult:
    """Result of training execution operation."""
    success: bool
    session_id: str
    final_metrics: Optional[TrainingMetrics] = None
    checkpoint_path: Optional[Path] = None
    error_message: Optional[str] = None
    execution_time: Optional[timedelta] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HyperparameterValidationResult:
    """Result of hyperparameter validation."""
    is_valid: bool
    parameter_name: str
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggested_value: Optional[Any] = None


@dataclass
class OptimizationResult:
    """Result of hyperparameter optimization."""
    best_config: Dict[str, Any]
    best_score: float
    optimization_history: List[Dict[str, Any]]
    total_trials: int
    successful_trials: int
    optimization_time: timedelta
    convergence_achieved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ISessionManager(ABC):
    """Base interface for training session management."""

    @abstractmethod
    async def create_session(self, model_id: str, config: TrainingConfig) -> str:
        """
        Create a new training session.

        Args:
            model_id: Unique model identifier
            config: Training configuration

        Returns:
            Session ID
        """
        pass

    @abstractmethod
    async def start_session(self, session_id: str) -> bool:
        """
        Start a training session.

        Args:
            session_id: Session identifier

        Returns:
            True if started successfully
        """
        pass

    @abstractmethod
    async def pause_session(self, session_id: str) -> bool:
        """
        Pause a running training session.

        Args:
            session_id: Session identifier

        Returns:
            True if paused successfully
        """
        pass

    @abstractmethod
    async def resume_session(self, session_id: str) -> bool:
        """
        Resume a paused training session.

        Args:
            session_id: Session identifier

        Returns:
            True if resumed successfully
        """
        pass

    @abstractmethod
    async def stop_session(self, session_id: str, save_checkpoint: bool = True) -> bool:
        """
        Stop a training session.

        Args:
            session_id: Session identifier
            save_checkpoint: Whether to save final checkpoint

        Returns:
            True if stopped successfully
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[TrainingSession]:
        """
        Get training session information.

        Args:
            session_id: Session identifier

        Returns:
            TrainingSession object or None if not found
        """
        pass

    @abstractmethod
    async def list_sessions(self, status_filter: Optional[TrainingStatus] = None) -> List[TrainingSession]:
        """
        List training sessions with optional status filter.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of TrainingSession objects
        """
        pass

    @abstractmethod
    async def update_session_metrics(self, session_id: str, metrics: TrainingMetrics) -> bool:
        """
        Update session with new training metrics.

        Args:
            session_id: Session identifier
            metrics: Training metrics to add

        Returns:
            True if updated successfully
        """
        pass


class ITrainingExecutor(ABC):
    """Base interface for training execution."""

    @abstractmethod
    async def initialize(self, session: TrainingSession) -> bool:
        """
        Initialize training executor for a session.

        Args:
            session: Training session to initialize for

        Returns:
            True if initialized successfully
        """
        pass

    @abstractmethod
    async def execute_training(self, session_id: str) -> ExecutionResult:
        """
        Execute training for a session.

        Args:
            session_id: Session identifier

        Returns:
            ExecutionResult with training outcome
        """
        pass

    @abstractmethod
    async def execute_epoch(self, session_id: str, epoch: int) -> TrainingMetrics:
        """
        Execute a single training epoch.

        Args:
            session_id: Session identifier
            epoch: Epoch number

        Returns:
            TrainingMetrics for the epoch
        """
        pass

    @abstractmethod
    async def validate_model(self, session_id: str) -> TrainingMetrics:
        """
        Run validation on current model.

        Args:
            session_id: Session identifier

        Returns:
            Validation metrics
        """
        pass

    @abstractmethod
    async def save_checkpoint(self, session_id: str, checkpoint_name: Optional[str] = None) -> Path:
        """
        Save model checkpoint.

        Args:
            session_id: Session identifier
            checkpoint_name: Optional checkpoint name

        Returns:
            Path to saved checkpoint
        """
        pass

    @abstractmethod
    async def load_checkpoint(self, session_id: str, checkpoint_path: Path) -> bool:
        """
        Load model from checkpoint.

        Args:
            session_id: Session identifier
            checkpoint_path: Path to checkpoint file

        Returns:
            True if loaded successfully
        """
        pass


class IHyperparameterManager(ABC):
    """Base interface for hyperparameter management."""

    @abstractmethod
    async def validate_config(self, config: Dict[str, HyperparameterConfig]) -> List[HyperparameterValidationResult]:
        """
        Validate hyperparameter configuration.

        Args:
            config: Hyperparameter configuration to validate

        Returns:
            List of validation results
        """
        pass

    @abstractmethod
    async def optimize_hyperparameters(self, base_config: TrainingConfig,
                                     strategy: OptimizationStrategy,
                                     max_trials: int = 100) -> OptimizationResult:
        """
        Optimize hyperparameters using specified strategy.

        Args:
            base_config: Base training configuration
            strategy: Optimization strategy to use
            max_trials: Maximum number of trials

        Returns:
            OptimizationResult with best configuration
        """
        pass

    @abstractmethod
    async def suggest_hyperparameters(self, model_type: str, dataset_size: int) -> Dict[str, HyperparameterConfig]:
        """
        Suggest hyperparameters based on model type and dataset.

        Args:
            model_type: Type of model being trained
            dataset_size: Size of training dataset

        Returns:
            Dictionary of suggested hyperparameters
        """
        pass

    @abstractmethod
    async def update_hyperparameter(self, session_id: str, param_name: str, value: Any) -> bool:
        """
        Update a hyperparameter during training.

        Args:
            session_id: Session identifier
            param_name: Parameter name to update
            value: New parameter value

        Returns:
            True if updated successfully
        """
        pass

    @abstractmethod
    async def get_hyperparameter_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get hyperparameter change history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of hyperparameter changes
        """
        pass


class ITrainingScheduler(ABC):
    """Base interface for training job scheduling."""

    @abstractmethod
    async def schedule_job(self, job: TrainingJob) -> str:
        """
        Schedule a training job.

        Args:
            job: Training job to schedule

        Returns:
            Job ID
        """
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a scheduled job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled successfully
        """
        pass

    @abstractmethod
    async def get_job_status(self, job_id: str) -> Optional[TrainingJob]:
        """
        Get job status and information.

        Args:
            job_id: Job identifier

        Returns:
            TrainingJob object or None if not found
        """
        pass

    @abstractmethod
    async def list_jobs(self, status_filter: Optional[str] = None) -> List[TrainingJob]:
        """
        List scheduled jobs with optional status filter.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of TrainingJob objects
        """
        pass

    @abstractmethod
    async def get_scheduler_status(self) -> SchedulerStatus:
        """
        Get scheduler status and statistics.

        Returns:
            SchedulerStatus object
        """
        pass

    @abstractmethod
    async def set_job_priority(self, job_id: str, priority: TrainingPriority) -> bool:
        """
        Update job priority.

        Args:
            job_id: Job identifier
            priority: New priority level

        Returns:
            True if updated successfully
        """
        pass

    @abstractmethod
    async def estimate_queue_time(self, job: TrainingJob) -> timedelta:
        """
        Estimate queue time for a job.

        Args:
            job: Training job to estimate for

        Returns:
            Estimated queue time
        """
        pass
