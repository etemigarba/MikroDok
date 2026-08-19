"""
Base interfaces and data structures for backup recovery operations.
Provides abstract base classes for backup management, recovery operations, 
checkpoint archiving, and state snapshotting.
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple


class BackupType(Enum):
    """Types of backup operations."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"
    CHECKPOINT = "checkpoint"
    MODEL_ONLY = "model_only"
    DATA_ONLY = "data_only"
    CONFIG_ONLY = "config_only"


class RecoveryType(Enum):
    """Types of recovery operations."""
    FULL_RESTORE = "full_restore"
    PARTIAL_RESTORE = "partial_restore"
    POINT_IN_TIME = "point_in_time"
    SELECTIVE_RESTORE = "selective_restore"
    ROLLBACK = "rollback"
    EMERGENCY_RESTORE = "emergency_restore"


class ArchiveType(Enum):
    """Types of archive operations."""
    CHECKPOINT_ARCHIVE = "checkpoint_archive"
    MODEL_ARCHIVE = "model_archive"
    DATA_ARCHIVE = "data_archive"
    COMPRESSED_ARCHIVE = "compressed_archive"
    ENCRYPTED_ARCHIVE = "encrypted_archive"


class SnapshotType(Enum):
    """Types of snapshot operations."""
    APPLICATION_STATE = "application_state"
    SYSTEM_STATE = "system_state"
    USER_STATE = "user_state"
    CONFIGURATION_STATE = "configuration_state"
    INCREMENTAL_STATE = "incremental_state"


class BackupStatus(Enum):
    """Status of backup operations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VALIDATING = "validating"
    COMPRESSING = "compressing"
    ENCRYPTING = "encrypting"


class RecoveryStatus(Enum):
    """Status of recovery operations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VALIDATING = "validating"
    RESTORING = "restoring"
    VERIFYING = "verifying"


@dataclass
class BackupConfig:
    """Configuration for backup operations."""
    backup_directory: Path
    backup_type: BackupType = BackupType.FULL
    compression_enabled: bool = True
    encryption_enabled: bool = False
    verify_integrity: bool = True
    retention_days: int = 30
    retention_count: int = 10
    max_backup_size: int = 50 * 1024 * 1024 * 1024  # 50GB
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    schedule_enabled: bool = False
    schedule_interval: int = 24  # hours
    parallel_operations: int = 4
    checksum_algorithm: str = "sha256"


@dataclass
class RecoveryConfig:
    """Configuration for recovery operations."""
    recovery_directory: Path
    recovery_type: RecoveryType = RecoveryType.FULL_RESTORE
    verify_before_restore: bool = True
    create_backup_before_restore: bool = True
    allow_partial_recovery: bool = False
    recovery_timeout: int = 3600  # seconds
    max_retry_attempts: int = 3
    rollback_on_failure: bool = True
    preserve_permissions: bool = True
    validate_checksums: bool = True


@dataclass
class ArchiveConfig:
    """Configuration for archive operations."""
    archive_directory: Path
    archive_type: ArchiveType = ArchiveType.CHECKPOINT_ARCHIVE
    compression_level: int = 6
    encryption_enabled: bool = False
    metadata_enabled: bool = True
    retention_policy: str = "time_based"
    retention_days: int = 90
    max_archive_size: int = 100 * 1024 * 1024 * 1024  # 100GB
    index_enabled: bool = True
    deduplication_enabled: bool = True


@dataclass
class SnapshotConfig:
    """Configuration for snapshot operations."""
    snapshot_directory: Path
    snapshot_type: SnapshotType = SnapshotType.APPLICATION_STATE
    incremental_enabled: bool = True
    compression_enabled: bool = True
    max_snapshots: int = 50
    snapshot_interval: int = 300  # seconds
    auto_cleanup: bool = True
    metadata_tracking: bool = True
    delta_compression: bool = True
    memory_efficient: bool = True


@dataclass
class BackupResult:
    """Result of backup operation."""
    success: bool
    backup_id: str
    backup_path: Path
    backup_type: BackupType
    start_time: datetime
    end_time: Optional[datetime] = None
    size_bytes: int = 0
    compressed_size: int = 0
    files_backed_up: int = 0
    checksum: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str) -> None:
        """Add error to result."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str) -> None:
        """Add warning to result."""
        self.warnings.append(warning)


@dataclass
class RecoveryResult:
    """Result of recovery operation."""
    success: bool
    recovery_id: str
    recovery_type: RecoveryType
    start_time: datetime
    end_time: Optional[datetime] = None
    files_restored: int = 0
    bytes_restored: int = 0
    backup_source: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    partial_recovery: bool = False
    rollback_performed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str) -> None:
        """Add error to result."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str) -> None:
        """Add warning to result."""
        self.warnings.append(warning)


@dataclass
class ArchiveResult:
    """Result of archive operation."""
    success: bool
    archive_id: str
    archive_path: Path
    archive_type: ArchiveType
    start_time: datetime
    end_time: Optional[datetime] = None
    original_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 0.0
    files_archived: int = 0
    checksum: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str) -> None:
        """Add error to result."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str) -> None:
        """Add warning to result."""
        self.warnings.append(warning)


@dataclass
class SnapshotResult:
    """Result of snapshot operation."""
    success: bool
    snapshot_id: str
    snapshot_path: Path
    snapshot_type: SnapshotType
    start_time: datetime
    end_time: Optional[datetime] = None
    size_bytes: int = 0
    is_incremental: bool = False
    parent_snapshot: Optional[str] = None
    checksum: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str) -> None:
        """Add error to result."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str) -> None:
        """Add warning to result."""
        self.warnings.append(warning)


class IBackupManager(ABC):
    """Interface for backup management operations."""
    
    @abstractmethod
    def create_backup(self, source_paths: List[Path], backup_config: BackupConfig) -> BackupResult:
        """
        Create a backup of specified paths.
        
        Args:
            source_paths: Paths to backup
            backup_config: Backup configuration
            
        Returns:
            BackupResult with operation details
        """
        pass
    
    @abstractmethod
    def schedule_backup(self, source_paths: List[Path], backup_config: BackupConfig) -> bool:
        """
        Schedule automatic backup.
        
        Args:
            source_paths: Paths to backup
            backup_config: Backup configuration
            
        Returns:
            True if scheduling successful
        """
        pass
    
    @abstractmethod
    def list_backups(self, backup_directory: Path) -> List[Dict[str, Any]]:
        """
        List available backups.
        
        Args:
            backup_directory: Directory containing backups
            
        Returns:
            List of backup metadata
        """
        pass
    
    @abstractmethod
    def validate_backup(self, backup_path: Path) -> bool:
        """
        Validate backup integrity.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if backup is valid
        """
        pass


class IRecoveryEngine(ABC):
    """Interface for recovery operations."""
    
    @abstractmethod
    def recover_from_backup(self, backup_path: Path, recovery_config: RecoveryConfig) -> RecoveryResult:
        """
        Recover from backup.
        
        Args:
            backup_path: Path to backup file
            recovery_config: Recovery configuration
            
        Returns:
            RecoveryResult with operation details
        """
        pass
    
    @abstractmethod
    def find_latest_backup(self, backup_directory: Path, backup_type: Optional[BackupType] = None) -> Optional[Path]:
        """
        Find latest backup.
        
        Args:
            backup_directory: Directory containing backups
            backup_type: Optional backup type filter
            
        Returns:
            Path to latest backup or None
        """
        pass
    
    @abstractmethod
    def verify_recovery(self, recovery_path: Path, original_backup: Path) -> bool:
        """
        Verify recovery integrity.
        
        Args:
            recovery_path: Path to recovered data
            original_backup: Path to original backup
            
        Returns:
            True if recovery is valid
        """
        pass


class ICheckpointArchiver(ABC):
    """Interface for checkpoint archiving operations."""
    
    @abstractmethod
    def archive_checkpoint(self, checkpoint_path: Path, archive_config: ArchiveConfig) -> ArchiveResult:
        """
        Archive checkpoint.
        
        Args:
            checkpoint_path: Path to checkpoint
            archive_config: Archive configuration
            
        Returns:
            ArchiveResult with operation details
        """
        pass
    
    @abstractmethod
    def extract_checkpoint(self, archive_path: Path, extract_path: Path) -> bool:
        """
        Extract checkpoint from archive.
        
        Args:
            archive_path: Path to archive
            extract_path: Path to extract to
            
        Returns:
            True if extraction successful
        """
        pass
    
    @abstractmethod
    def list_archived_checkpoints(self, archive_directory: Path) -> List[Dict[str, Any]]:
        """
        List archived checkpoints.
        
        Args:
            archive_directory: Directory containing archives
            
        Returns:
            List of archive metadata
        """
        pass


class IStateSnapshotter(ABC):
    """Interface for state snapshot operations."""
    
    @abstractmethod
    def create_snapshot(self, state_data: Dict[str, Any], snapshot_config: SnapshotConfig) -> SnapshotResult:
        """
        Create state snapshot.
        
        Args:
            state_data: State data to snapshot
            snapshot_config: Snapshot configuration
            
        Returns:
            SnapshotResult with operation details
        """
        pass
    
    @abstractmethod
    def restore_snapshot(self, snapshot_path: Path) -> Dict[str, Any]:
        """
        Restore state from snapshot.
        
        Args:
            snapshot_path: Path to snapshot
            
        Returns:
            Restored state data
        """
        pass
    
    @abstractmethod
    def list_snapshots(self, snapshot_directory: Path) -> List[Dict[str, Any]]:
        """
        List available snapshots.
        
        Args:
            snapshot_directory: Directory containing snapshots
            
        Returns:
            List of snapshot metadata
        """
        pass
    
    @abstractmethod
    def cleanup_snapshots(self, snapshot_config: SnapshotConfig) -> int:
        """
        Clean up old snapshots.
        
        Args:
            snapshot_config: Snapshot configuration
            
        Returns:
            Number of snapshots cleaned up
        """
        pass
