"""
MikroDok State Synchronizer Package
Provides state synchronization functionality for maintaining consistency between frontend and backend.
"""

# Import state synchronizer components
try:
    from .state_synchronizer_lg import (
        StateSynchronizer,
        StateChangeDetector,
        StateUpdatePropagator,
        ConflictResolver,
        StateUpdate,
        SynchronizationResult
    )
except ImportError:
    pass

__all__ = [
    'StateSynchronizer',
    'StateChangeDetector',
    'StateUpdatePropagator',
    'ConflictResolver',
    'StateUpdate',
    'SynchronizationResult'
]
