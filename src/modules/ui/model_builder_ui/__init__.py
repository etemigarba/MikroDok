"""
Model Builder UI Module

This module provides user interface components for building and configuring models
in the MikroDok application.

Components:
- model_config_ui: Model architecture configuration interface
- training_controls_ui: Training start/stop/pause controls
- training_progress_ui: Real-time training progress display
- checkpoint_list_ui: Training checkpoint management

Phase: 4
Location: /src/modules/ui/model_builder_ui/
"""

# Import model config components
try:
    from .model_config_ui.model_config_ui import (
        ModelConfigUI,
        ModelConfigMode,
        ModelConfigurationForm,
        ModelArchitectureConfig,
        TrainingParameterConfig,
        ModelConfigValidationResult,
        ModelConfigFormConfig
    )
    
    __all__ = [
        'ModelConfigUI',
        'ModelConfigMode',
        'ModelConfigurationForm',
        'ModelArchitectureConfig',
        'TrainingParameterConfig',
        'ModelConfigValidationResult',
        'ModelConfigFormConfig'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import model config components: {e}")
    
    __all__ = []

# Import training controls components
try:
    from .training_controls_ui.training_controls_ui import (
        TrainingControlsUI,
        TrainingControlState,
        TrainingControlAction,
        TrainingControlsConfig,
        TrainingProgressData
    )

    __all__.extend([
        'TrainingControlsUI',
        'TrainingControlState',
        'TrainingControlAction',
        'TrainingControlsConfig',
        'TrainingProgressData'
    ])

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import training controls components: {e}")

# Import training progress components
try:
    from .training_progress_ui.training_progress_ui import (
        TrainingProgressUI,
        ProgressDisplayMode,
        ProgressStatus,
        TrainingProgressConfig,
        TrainingProgressData,
        ProgressMetrics
    )

    __all__.extend([
        'TrainingProgressUI',
        'ProgressDisplayMode',
        'ProgressStatus',
        'TrainingProgressConfig',
        'TrainingProgressData',
        'ProgressMetrics'
    ])

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import training progress components: {e}")

# Import checkpoint list components
try:
    from .checkpoint_list_ui.checkpoint_list_ui import (
        CheckpointListUI,
        TrainingCheckpointSortMode,
        TrainingCheckpointFilterMode,
        TrainingCheckpointDisplayMode,
        TrainingCheckpointListConfig,
        TrainingCheckpointSelectionMode,
        TrainingCheckpointItem,
        TrainingCheckpointListState
    )

    __all__.extend([
        'CheckpointListUI',
        'TrainingCheckpointSortMode',
        'TrainingCheckpointFilterMode',
        'TrainingCheckpointDisplayMode',
        'TrainingCheckpointListConfig',
        'TrainingCheckpointSelectionMode',
        'TrainingCheckpointItem',
        'TrainingCheckpointListState'
    ])

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import checkpoint list components: {e}")
