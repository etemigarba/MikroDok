"""
Settings Validator Module
Validates user settings against schema and ensures configuration integrity.
"""

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
