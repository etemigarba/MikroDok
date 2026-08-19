"""
MikroDok Training Progress UI Package
Provides streamlined training progress visualization interface for model builder workflow with real-time monitoring and control capabilities.
"""

# Import training progress components
try:
    from .training_progress_ui import (
        TrainingProgressUI,
        ProgressDisplayMode,
        ProgressStatus,
        TrainingProgressConfig,
        TrainingProgressData,
        ProgressMetrics
    )
    
    __all__ = [
        'TrainingProgressUI',
        'ProgressDisplayMode',
        'ProgressStatus',
        'TrainingProgressConfig',
        'TrainingProgressData',
        'ProgressMetrics'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import training progress components: {e}")
    
    __all__ = []
