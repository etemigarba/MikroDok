"""
MikroDok Confirmation Dialog UI Package
Provides confirmation dialogs for destructive actions with safety warnings.
"""

# Import confirmation dialog components
try:
    from .confirmation_dialog_ui import (
        ConfirmationDialogUI,
        ConfirmationType,
        ConfirmationResult,
        ConfirmationDialogConfig,
        ConfirmationContext,
        ConfirmationOption
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Confirmation dialog UI component for MikroDok application"

# Export main components
__all__ = [
    "ConfirmationDialogUI",
    "ConfirmationType",
    "ConfirmationResult",
    "ConfirmationDialogConfig",
    "ConfirmationContext",
    "ConfirmationOption"
]
