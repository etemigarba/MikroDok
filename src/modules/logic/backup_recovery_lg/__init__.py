"""
MikroDok Backup Recovery Package
Provides comprehensive backup and recovery functionality for models, data, and application state.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IBackupManager,
        IRecoveryEngine,
        ICheckpointArchiver,
        IStateSnapshotter,
        BackupConfig,
        RecoveryConfig,
        ArchiveConfig,
        SnapshotConfig,
        BackupResult,
        RecoveryResult,
        ArchiveResult,
        SnapshotResult,
        BackupType,
        RecoveryType,
        ArchiveType,
        SnapshotType,
        BackupStatus,
        RecoveryStatus
    )
except ImportError:
    pass

# Import backup manager components
try:
    from .backup_manager_lg.backup_manager_lg import (
        BackupManager,
        BackupScheduler,
        BackupValidator,
        BackupCompressor
    )
except ImportError:
    pass

# Import recovery engine components
try:
    from .recovery_engine_lg.recovery_engine_lg import (
        RecoveryEngine,
        RecoveryValidator,
        RecoveryOrchestrator,
        IntegrityVerifier
    )
except ImportError:
    pass

# Import checkpoint archiver components
try:
    from .checkpoint_archiver_lg.checkpoint_archiver_lg import (
        CheckpointArchiver,
        ArchiveManager,
        MetadataManager,
        CompressionManager
    )
except ImportError:
    pass

# Import state snapshotter components
try:
    from .state_snapshotter_lg.state_snapshotter_lg import (
        StateSnapshotter,
        SnapshotManager,
        IncrementalSnapshotter,
        SnapshotCompressor
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IBackupManager',
    'IRecoveryEngine', 
    'ICheckpointArchiver',
    'IStateSnapshotter',
    'BackupConfig',
    'RecoveryConfig',
    'ArchiveConfig',
    'SnapshotConfig',
    'BackupResult',
    'RecoveryResult',
    'ArchiveResult',
    'SnapshotResult',
    'BackupType',
    'RecoveryType',
    'ArchiveType',
    'SnapshotType',
    'BackupStatus',
    'RecoveryStatus',
    
    # Backup Manager
    'BackupManager',
    'BackupScheduler',
    'BackupValidator',
    'BackupCompressor',
    
    # Recovery Engine
    'RecoveryEngine',
    'RecoveryValidator',
    'RecoveryOrchestrator',
    'IntegrityVerifier',
    
    # Checkpoint Archiver
    'CheckpointArchiver',
    'ArchiveManager',
    'MetadataManager',
    'CompressionManager',
    
    # State Snapshotter
    'StateSnapshotter',
    'SnapshotManager',
    'IncrementalSnapshotter',
    'SnapshotCompressor'
]
