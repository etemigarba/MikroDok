"""
MikroDok Training Configuration UI Package
Provides comprehensive training configuration interface components including hyperparameter forms, model selection, dataset selection, and advanced settings.
"""

# Import hyperparameter form components
try:
    from .hyperparameter_form_ui.hyperparameter_form_ui import (
        HyperparameterFormUI,
        HyperparameterFormMode,
        HyperparameterFormConfig,
        HyperparameterFieldType,
        HyperparameterValidationState,
        FormValidationResult
    )
    
    __all__ = [
        'HyperparameterFormUI',
        'HyperparameterFormMode',
        'HyperparameterFormConfig',
        'HyperparameterFieldType',
        'HyperparameterValidationState',
        'FormValidationResult'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import hyperparameter form components: {e}")
    
    __all__ = []

# Import model selector components
try:
    from .model_selector_ui.model_selector_ui import (
        ModelSelectorUI,
        ModelArchitecture,
        ModelSize,
        ModelConfiguration,
        QuantizationType,
        OptimizationLevel,
        ModelSelectionMode,
        ModelCompatibilityResult,
        ModelSelectionConfig
    )

    __all__.extend([
        'ModelSelectorUI',
        'ModelArchitecture',
        'ModelSize',
        'ModelConfiguration',
        'QuantizationType',
        'OptimizationLevel',
        'ModelSelectionMode',
        'ModelCompatibilityResult',
        'ModelSelectionConfig'
    ])

except ImportError as e:
    import warnings
    warnings.warn(f"Could not import model selector components: {e}")

try:
    from .dataset_selector_ui.dataset_selector_ui import (
        DatasetSelectorUI,
        DatasetConfiguration,
        DatasetValidationResult,
        DatasetSelectionMode,
        DatasetSource,
        DatasetFormat,
        DatasetStatus,
        DatasetMetrics,
        DatasetSelectorConfig
    )

    __all__.extend([
        'DatasetSelectorUI',
        'DatasetConfiguration',
        'DatasetValidationResult',
        'DatasetSelectionMode',
        'DatasetSource',
        'DatasetFormat',
        'DatasetStatus',
        'DatasetMetrics',
        'DatasetSelectorConfig'
    ])

except ImportError as e:
    import warnings
    warnings.warn(f"Could not import dataset selector components: {e}")

try:
    from .advanced_settings_ui.advanced_settings_ui import (
        AdvancedSettingsUI,
        AdvancedConfiguration,
        SettingsCategory,
        ResourceConfiguration,
        OptimizationConfiguration,
        LoggingConfiguration,
        AdvancedSettingsConfig,
        AdvancedSettingsMode,
        ConfigurationValidationResult,
        ConfigurationExportResult,
        ConfigurationImportResult
    )

    __all__.extend([
        'AdvancedSettingsUI',
        'AdvancedConfiguration',
        'SettingsCategory',
        'ResourceConfiguration',
        'OptimizationConfiguration',
        'LoggingConfiguration',
        'AdvancedSettingsConfig',
        'AdvancedSettingsMode',
        'ConfigurationValidationResult',
        'ConfigurationExportResult',
        'ConfigurationImportResult'
    ])

except ImportError as e:
    import warnings
    warnings.warn(f"Could not import advanced settings components: {e}")
