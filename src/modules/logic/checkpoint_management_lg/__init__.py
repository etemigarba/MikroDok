"""
MikroDok Checkpoint Management Package
Provides comprehensive checkpoint management functionality for model state preservation and recovery.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        ICheckpointCreator,
        ICheckpointValidator,
        ICheckpointRecovery,
        ICheckpointCleaner,
        CheckpointMetadata,
        CheckpointType,
        CheckpointStatus,
        CheckpointValidationResult,
        RecoveryResult,
        CleanupResult,
        RetentionPolicy,
        CheckpointConfig
    )
except ImportError:
    pass

# Import checkpoint creator components
try:
    from .checkpoint_creator_lg.checkpoint_creator_lg import (
        CheckpointCreator,
        CheckpointCreationConfig,
        StateSerializer,
        IntegrityCalculator
    )
except ImportError:
    pass

# Import checkpoint validator components
try:
    from .checkpoint_validator_lg.checkpoint_validator_lg import (
        CheckpointValidator,
        CheckpointValidationConfig,
        IntegrityValidator,
        StateValidator,
        CorruptionDetector
    )
except ImportError:
    pass

# Import checkpoint recovery components
try:
    from .checkpoint_recovery_lg.checkpoint_recovery_lg import (
        CheckpointRecovery,
        RecoveryConfig,
        StateRestorer,
        RecoveryOrchestrator
    )
except ImportError:
    pass

# Import checkpoint cleaner components
try:
    from .checkpoint_cleaner_lg.checkpoint_cleaner_lg import (
        CheckpointCleaner,
        CleanupConfig,
        RetentionManager,
        CleanupOrchestrator
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'ICheckpointCreator',
    'ICheckpointValidator',
    'ICheckpointRecovery',
    'ICheckpointCleaner',
    'CheckpointMetadata',
    'CheckpointType',
    'CheckpointStatus',
    'CheckpointValidationResult',
    'RecoveryResult',
    'CleanupResult',
    'RetentionPolicy',
    'CheckpointConfig',
    
    # Checkpoint Creator
    'CheckpointCreator',
    'CheckpointCreationConfig',
    'StateSerializer',
    'IntegrityCalculator',
    
    # Checkpoint Validator
    'CheckpointValidator',
    'CheckpointValidationConfig',
    'IntegrityValidator',
    'StateValidator',
    'CorruptionDetector',
    
    # Checkpoint Recovery
    'CheckpointRecovery',
    'RecoveryConfig',
    'StateRestorer',
    'RecoveryOrchestrator',
    
    # Checkpoint Cleaner
    'CheckpointCleaner',
    'CleanupConfig',
    'RetentionManager',
    'CleanupOrchestrator'
]
