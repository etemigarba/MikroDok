"""
MikroDok Error Dialog UI Package
Provides error notification dialogs with severity levels and recovery actions.
"""

# Import error dialog components
try:
    from .error_dialog_ui import (
        ErrorDialogUI,
        ErrorSeverity,
        ErrorType,
        ErrorRecoveryAction,
        ErrorDialogConfig,
        ErrorDialogResult,
        ErrorContext,
        RecoveryOption
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Error dialog UI component for MikroDok application"

# Export main components
__all__ = [
    "ErrorDialogUI",
    "ErrorSeverity",
    "ErrorType",
    "ErrorRecoveryAction",
    "ErrorDialogConfig",
    "ErrorDialogResult",
    "ErrorContext",
    "RecoveryOption"
]
