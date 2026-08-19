"""
Model Configuration UI Module

This module provides the interface for configuring model architectures and training
parameters in the MikroDok application.

Components:
- ModelConfigUI: Main model configuration interface with architecture and parameter forms

Phase: 4
Location: /src/modules/ui/model_builder_ui/model_config_ui/
"""

from .model_config_ui import (
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
