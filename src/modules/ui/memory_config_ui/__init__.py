"""
Memory Configuration UI Module

This module provides user interface components for configuring memory allocation
settings and IDRAlloc modes in the MikroDok application.

Components:
- mode_selector_ui: Interface for selecting Legacy, Hybrid, or Auto IDRAlloc modes
- limit_configurator_ui: Memory limit configuration interface

Phase: 2
Location: /src/modules/ui/memory_config_ui/
"""

from .mode_selector_ui.mode_selector_ui import ModeSelectorUI

# Import will be added after resolving dependency issues
# from .limit_configurator_ui.limit_configurator_ui import (
#     LimitConfiguratorUI,
#     LimitType,
#     ValidationLevel,
#     TierLimit,
#     ValidationResult
# )

__all__ = [
    # Mode Selector UI
    'ModeSelectorUI',

    # Limit Configurator UI - temporarily commented until dependencies resolved
    # 'LimitConfiguratorUI',
    # 'LimitType',
    # 'ValidationLevel',
    # 'TierLimit',
    # 'ValidationResult'
]
