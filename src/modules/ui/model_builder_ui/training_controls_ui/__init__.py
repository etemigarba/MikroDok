"""
MikroDok Training Controls UI Package
Provides streamlined training control interface for model builder workflow including start/stop/pause controls, progress monitoring, and session management.
"""

# Import training controls components
try:
    from .training_controls_ui import (
        TrainingControlsUI,
        TrainingControlState,
        TrainingControlAction,
        TrainingControlsConfig,
        TrainingProgressData
    )
    
    __all__ = [
        'TrainingControlsUI',
        'TrainingControlState',
        'TrainingControlAction',
        'TrainingControlsConfig',
        'TrainingProgressData'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import training controls components: {e}")
    
    __all__ = []
