"""
Quick Actions UI Module

This module contains the quick actions interface for MikroDok application.
Provides quick start action buttons for creating models, importing documents, and starting training.

Phase: 1
Location: /src/modules/ui/main_dashboard_ui/quick_actions_ui/
"""

# Import quick actions components
try:
    from .quick_actions_ui import (
        QuickActionsUI,
        QuickAction,
        QuickActionsConfig,
        ActionLayout,
        ActionSize,
        ActionStyle,
        create_default_actions
    )
except ImportError:
    pass

__all__ = [
    'QuickActionsUI',
    'QuickAction',
    'QuickActionsConfig',
    'ActionLayout',
    'ActionSize',
    'ActionStyle',
    'create_default_actions'
]
