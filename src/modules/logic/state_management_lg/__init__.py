"""
MikroDok State Management Package
Provides comprehensive state management functionality for application state and persistence.
"""

# Import all state management components
from .app_state_manager_lg.app_state_manager_lg import (
    AppStateManager,
    ApplicationState,
    StateTransition,
    StateValidator,
    StateManagerConfiguration,
    StateManagerMetrics,
    StateManagerResult
)

from .state_persistence_lg.state_persistence_lg import (
    StatePersistenceManager,
    PersistenceMode,
    SerializationFormat,
    PersistenceConfiguration,
    StateSnapshot,
    PersistenceMetrics,
    StatePersistenceResult
)

__all__ = [
    # App State Manager
    'AppStateManager',
    'ApplicationState',
    'StateTransition',
    'StateValidator',
    'StateManagerConfiguration',
    'StateManagerMetrics',
    'StateManagerResult',
    
    # State Persistence
    'StatePersistenceManager',
    'PersistenceMode',
    'SerializationFormat',
    'PersistenceConfiguration',
    'StateSnapshot',
    'PersistenceMetrics',
    'StatePersistenceResult'
]
