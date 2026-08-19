"""
MikroDok Progress Dialog UI Package
Provides progress dialogs for long-running operations with cancellation support and real-time updates.
"""

# Import progress dialog components
try:
    from .progress_dialog_ui import (
        ProgressDialogUI,
        ProgressType,
        ProgressState,
        ProgressDialogConfig,
        ProgressDialogResult,
        ProgressContext,
        ProgressOption,
        create_progress_dialog,
        create_indeterminate_progress_dialog,
        create_stepped_progress_dialog
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Progress dialog UI component for MikroDok application"

# Export main components
__all__ = [
    "ProgressDialogUI",
    "ProgressType",
    "ProgressState",
    "ProgressDialogConfig",
    "ProgressDialogResult",
    "ProgressContext",
    "ProgressOption",
    "create_progress_dialog",
    "create_indeterminate_progress_dialog",
    "create_stepped_progress_dialog"
]
