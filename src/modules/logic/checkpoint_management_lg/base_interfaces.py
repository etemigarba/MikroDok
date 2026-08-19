"""
Module: base_interfaces
Description: Base interfaces and data structures for checkpoint management functionality
Phase: 4
Location: /src/modules/logic/checkpoint_management_lg/
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Set
import uuid

# Local imports
from src.modules.logic.error_handling_lg import ValidationError


class CheckpointType(Enum):
    """Types of checkpoints."""
    PERIODIC = "periodic"
    BEST_MODEL = "best_model"
    MILESTONE = "milestone"
    EMERGENCY = "emergency"
    MANUAL = "manual"
    FINAL = "final"


class CheckpointStatus(Enum):
    """Status of checkpoint operations."""
    CREATING = "creating"
    CREATED = "created"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    CORRUPTED = "corrupted"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    CLEANING = "cleaning"
    CLEANED = "cleaned"
    FAILED = "failed"


class RetentionPolicy(Enum):
    """Checkpoint retention policies."""
    KEEP_ALL = "keep_all"
    KEEP_BEST = "keep_best"
    KEEP_RECENT = "keep_recent"
    KEEP_MILESTONES = "keep_milestones"
    TIME_BASED = "time_based"
    COUNT_BASED = "count_based"
    SIZE_BASED = "size_based"


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""
    checkpoint_id: str
    checkpoint_type: CheckpointType
    status: CheckpointStatus
    file_path: Path
    created_at: datetime
    model_state_size: int
    optimizer_state_size: int
    total_size: int
    checksum: str
    training_step: int
    epoch: int
    loss_value: float
    metrics: Dict[str, float] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    description: Optional[str] = None
    parent_checkpoint_id: Optional[str] = None
    is_best: bool = False
    validation_errors: List[ValidationError] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'checkpoint_id': self.checkpoint_id,
            'checkpoint_type': self.checkpoint_type.value,
            'status': self.status.value,
            'file_path': str(self.file_path),
            'created_at': self.created_at.isoformat(),
            'model_state_size': self.model_state_size,
            'optimizer_state_size': self.optimizer_state_size,
            'total_size': self.total_size,
            'checksum': self.checksum,
            'training_step': self.training_step,
            'epoch': self.epoch,
            'loss_value': self.loss_value,
            'metrics': self.metrics,
            'tags': list(self.tags),
            'description': self.description,
            'parent_checkpoint_id': self.parent_checkpoint_id,
            'is_best': self.is_best,
            'validation_errors': [str(error) for error in self.validation_errors]
        }


@dataclass
class CheckpointConfig:
    """Configuration for checkpoint operations."""
    checkpoint_dir: Path
    checkpoint_prefix: str = "checkpoint"
    save_optimizer_state: bool = True
    save_scheduler_state: bool = True
    save_model_state: bool = True
    compression_enabled: bool = True
    encryption_enabled: bool = False
    verify_integrity: bool = True
    atomic_save: bool = True
    backup_count: int = 3
    max_checkpoint_size: int = 10 * 1024 * 1024 * 1024  # 10GB
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.checkpoint_dir:
            raise ValueError("Checkpoint directory must be specified")
        if self.backup_count < 0:
            raise ValueError("Backup count must be non-negative")
        if self.max_checkpoint_size <= 0:
            raise ValueError("Max checkpoint size must be positive")


@dataclass
class CheckpointValidationResult:
    """Result of checkpoint validation."""
    is_valid: bool
    checkpoint_id: str
    validation_time: datetime
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    integrity_check_passed: bool = True
    state_check_passed: bool = True
    corruption_detected: bool = False
    file_size: int = 0
    expected_checksum: Optional[str] = None
    actual_checksum: Optional[str] = None
    
    def add_error(self, error: ValidationError) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.warnings.append(warning)


@dataclass
class RecoveryResult:
    """Result of checkpoint recovery operation."""
    success: bool
    checkpoint_id: str
    recovery_time: datetime
    recovered_step: int
    recovered_epoch: int
    recovered_loss: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    partial_recovery: bool = False
    
    def add_error(self, error: str) -> None:
        """Add recovery error."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str) -> None:
        """Add recovery warning."""
        self.warnings.append(warning)


@dataclass
class CleanupResult:
    """Result of checkpoint cleanup operation."""
    success: bool
    cleanup_time: datetime
    checkpoints_removed: int
    space_freed: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    removed_checkpoint_ids: List[str] = field(default_factory=list)
    
    def add_error(self, error: str) -> None:
        """Add cleanup error."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str) -> None:
        """Add cleanup warning."""
        self.warnings.append(warning)


class ICheckpointCreator(ABC):
    """Interface for checkpoint creation operations."""
    
    @abstractmethod
    def create_checkpoint(self, model_state: Dict[str, Any], optimizer_state: Dict[str, Any],
                         training_step: int, epoch: int, loss_value: float,
                         checkpoint_type: CheckpointType = CheckpointType.PERIODIC,
                         metadata: Optional[Dict[str, Any]] = None) -> CheckpointMetadata:
        """
        Create a new checkpoint.
        
        Args:
            model_state: Model state dictionary
            optimizer_state: Optimizer state dictionary
            training_step: Current training step
            epoch: Current epoch
            loss_value: Current loss value
            checkpoint_type: Type of checkpoint
            metadata: Additional metadata
            
        Returns:
            CheckpointMetadata for the created checkpoint
        """
        pass
    
    @abstractmethod
    def save_checkpoint_async(self, checkpoint_metadata: CheckpointMetadata) -> bool:
        """
        Save checkpoint asynchronously.
        
        Args:
            checkpoint_metadata: Checkpoint metadata
            
        Returns:
            True if save initiated successfully
        """
        pass


class ICheckpointValidator(ABC):
    """Interface for checkpoint validation operations."""
    
    @abstractmethod
    def validate_checkpoint(self, checkpoint_path: Path) -> CheckpointValidationResult:
        """
        Validate a checkpoint file.
        
        Args:
            checkpoint_path: Path to checkpoint file
            
        Returns:
            CheckpointValidationResult with validation details
        """
        pass
    
    @abstractmethod
    def verify_integrity(self, checkpoint_path: Path, expected_checksum: str) -> bool:
        """
        Verify checkpoint integrity.
        
        Args:
            checkpoint_path: Path to checkpoint file
            expected_checksum: Expected checksum
            
        Returns:
            True if integrity check passes
        """
        pass


class ICheckpointRecovery(ABC):
    """Interface for checkpoint recovery operations."""
    
    @abstractmethod
    def recover_from_checkpoint(self, checkpoint_path: Path) -> RecoveryResult:
        """
        Recover training state from checkpoint.
        
        Args:
            checkpoint_path: Path to checkpoint file
            
        Returns:
            RecoveryResult with recovery details
        """
        pass
    
    @abstractmethod
    def find_latest_checkpoint(self, checkpoint_dir: Path) -> Optional[Path]:
        """
        Find the latest valid checkpoint.
        
        Args:
            checkpoint_dir: Directory containing checkpoints
            
        Returns:
            Path to latest checkpoint or None if not found
        """
        pass


class ICheckpointCleaner(ABC):
    """Interface for checkpoint cleanup operations."""
    
    @abstractmethod
    def cleanup_checkpoints(self, retention_policy: RetentionPolicy,
                           retention_count: int = 5,
                           retention_days: int = 30) -> CleanupResult:
        """
        Clean up old checkpoints based on retention policy.
        
        Args:
            retention_policy: Policy for checkpoint retention
            retention_count: Number of checkpoints to keep
            retention_days: Number of days to keep checkpoints
            
        Returns:
            CleanupResult with cleanup details
        """
        pass
    
    @abstractmethod
    def get_cleanup_candidates(self, retention_policy: RetentionPolicy,
                              retention_count: int = 5,
                              retention_days: int = 30) -> List[CheckpointMetadata]:
        """
        Get list of checkpoints that can be cleaned up.
        
        Args:
            retention_policy: Policy for checkpoint retention
            retention_count: Number of checkpoints to keep
            retention_days: Number of days to keep checkpoints
            
        Returns:
            List of checkpoint metadata for cleanup candidates
        """
        pass
