"""
Dataset Selector UI Module

This module provides the interface for selecting and configuring training datasets
for the MikroDok application.

Components:
- DatasetSelectorUI: Main dataset selection interface with browsing and validation
- DatasetConfiguration: Dataset configuration data structures
- DatasetValidationResult: Dataset validation result structures

Phase: 4
Location: /src/modules/ui/training_configuration_ui/dataset_selector_ui/
"""

from .dataset_selector_ui import (
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

__all__ = [
    'DatasetSelectorUI',
    'DatasetConfiguration',
    'DatasetValidationResult',
    'DatasetSelectionMode',
    'DatasetSource',
    'DatasetFormat',
    'DatasetStatus',
    'DatasetMetrics',
    'DatasetSelectorConfig'
]
