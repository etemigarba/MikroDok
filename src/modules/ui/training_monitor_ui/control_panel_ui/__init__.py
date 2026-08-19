"""
MikroDok Training Control Panel UI Package
Provides comprehensive training control interface components including start/stop controls, status monitoring, and session management.
"""

# Import control panel components
try:
    from .control_panel_ui import (
        ControlPanelUI,
        TrainingControlState,
        ControlPanelConfiguration,
        TrainingControlAction,
        SessionControlAction
    )
    
    __all__ = [
        'ControlPanelUI',
        'TrainingControlState',
        'ControlPanelConfiguration',
        'TrainingControlAction',
        'SessionControlAction'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import control panel components: {e}")
    
    __all__ = []
