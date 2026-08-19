"""
MikroDok Configuration Manager Package
Provides comprehensive configuration loading and validation functionality.
"""

# Import all configuration management components
from .config_loader_lg import (
    ConfigurationLoader,
    IConfigurationLoader,
    ConfigurationSource,
    ConfigurationFormat,
    ConfigurationEntry,
    ConfigurationSchema,
    LoadResult,
    create_configuration_loader
)

from .settings_validator_lg import (
    SettingsValidator,
    ISettingsValidator,
    SettingType,
    SettingCategory,
    SettingConstraint,
    SettingDefinition,
    ValidationContext,
    SettingsValidationResult,
    create_settings_validator
)

__all__ = [
    # Configuration Loader
    'ConfigurationLoader',
    'IConfigurationLoader',
    'ConfigurationSource',
    'ConfigurationFormat',
    'ConfigurationEntry',
    'ConfigurationSchema',
    'LoadResult',
    'create_configuration_loader',

    # Settings Validator
    'SettingsValidator',
    'ISettingsValidator',
    'SettingType',
    'SettingCategory',
    'SettingConstraint',
    'SettingDefinition',
    'ValidationContext',
    'SettingsValidationResult',
    'create_settings_validator'
]
