"""
MikroDok Application Lifecycle Package
Provides comprehensive application lifecycle management functionality.
"""

# Import all application lifecycle components
from .startup_manager_lg.startup_manager_lg import (
    StartupManager,
    StartupPhase,
    StartupStatus,
    StartupConfiguration,
    StartupMetrics,
    StartupManagerResult
)

from .shutdown_handler_lg.shutdown_handler_lg import (
    ShutdownHandler,
    ShutdownTrigger,
    ShutdownMode,
    ShutdownStatus,
    ShutdownConfiguration,
    ShutdownMetrics,
    ShutdownHandlerResult
)

from .crash_recovery_lg.crash_recovery_lg import (
    CrashRecoveryManager,
    RecoveryMode,
    CheckpointType,
    RecoveryStatus,
    RecoveryConfiguration,
    CheckpointData,
    RecoveryMetrics,
    CrashRecoveryResult
)

__all__ = [
    # Startup Management
    'StartupManager',
    'StartupPhase',
    'StartupStatus',
    'StartupConfiguration',
    'StartupMetrics',
    'StartupManagerResult',

    # Shutdown Handling
    'ShutdownHandler',
    'ShutdownTrigger',
    'ShutdownMode',
    'ShutdownStatus',
    'ShutdownConfiguration',
    'ShutdownMetrics',
    'ShutdownHandlerResult',

    # Crash Recovery
    'CrashRecoveryManager',
    'RecoveryMode',
    'CheckpointType',
    'RecoveryStatus',
    'RecoveryConfiguration',
    'CheckpointData',
    'RecoveryMetrics',
    'CrashRecoveryResult'
]
