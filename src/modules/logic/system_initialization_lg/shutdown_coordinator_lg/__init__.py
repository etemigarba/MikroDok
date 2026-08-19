"""
Shutdown Coordinator Module
Handles graceful application shutdown with resource cleanup.
"""

from .shutdown_coordinator_lg import (
    ShutdownCoordinator,
    ShutdownPhase,
    ShutdownResult,
    CleanupStatus,
    ShutdownContext
)

__all__ = [
    'ShutdownCoordinator',
    'ShutdownPhase',
    'ShutdownResult',
    'CleanupStatus',
    'ShutdownContext'
]
