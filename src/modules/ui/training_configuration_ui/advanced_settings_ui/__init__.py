"""
MikroDok Advanced Training Settings UI Package
Provides comprehensive advanced training configuration interface components including resource management,
optimization strategies, logging configuration, and advanced training parameters.
"""

# Import advanced settings components
try:
    from .advanced_settings_ui import (
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
    
    __all__ = [
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
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import advanced settings components: {e}")
    
    __all__ = []

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Advanced training configuration UI components for MikroDok"
