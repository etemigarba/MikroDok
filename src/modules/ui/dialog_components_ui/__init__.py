"""
MikroDok Dialog Components UI Package
Provides reusable dialog components for the MikroDok application.
"""

# Import dialog components
try:
    from .confirmation_dialog_ui.confirmation_dialog_ui import (
        ConfirmationDialogUI,
        ConfirmationType,
        ConfirmationResult,
        ConfirmationDialogConfig,
        ConfirmationContext,
        ConfirmationOption,
        create_confirmation_dialog,
        create_delete_confirmation,
        create_destructive_action_confirmation
    )
except ImportError:
    pass

try:
    from .error_dialog_ui.error_dialog_ui import (
        ErrorDialogUI,
        ErrorSeverity,
        ErrorType,
        ErrorRecoveryAction
    )
except ImportError:
    pass

try:
    from .progress_dialog_ui.progress_dialog_ui import (
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

try:
    from .file_picker_ui.file_picker_ui import (
        FilePickerUI,
        FilePickerMode,
        FileFilter,
        FilePickerResult,
        FilePickerConfig,
        FilePickerState,
        create_file_picker_dialog,
        create_document_picker,
        create_directory_picker,
        create_model_file_picker,
        DOCUMENT_FILTERS,
        MODEL_FILTERS,
        ALL_FILES_FILTER
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Dialog components for MikroDok application"

# Export main components
__all__ = [
    "ConfirmationDialogUI",
    "ConfirmationType",
    "ConfirmationResult",
    "ConfirmationDialogConfig",
    "ConfirmationContext",
    "ConfirmationOption",
    "create_confirmation_dialog",
    "create_delete_confirmation",
    "create_destructive_action_confirmation",
    "ErrorDialogUI",
    "ErrorSeverity",
    "ErrorType",
    "ErrorRecoveryAction",
    "ProgressDialogUI",
    "ProgressType",
    "ProgressState",
    "ProgressDialogConfig",
    "ProgressDialogResult",
    "ProgressContext",
    "ProgressOption",
    "create_progress_dialog",
    "create_indeterminate_progress_dialog",
    "create_stepped_progress_dialog",
    "FilePickerUI",
    "FilePickerMode",
    "FileFilter",
    "FilePickerResult",
    "FilePickerConfig",
    "FilePickerState",
    "create_file_picker_dialog",
    "create_document_picker",
    "create_directory_picker",
    "create_model_file_picker",
    "DOCUMENT_FILTERS",
    "MODEL_FILTERS",
    "ALL_FILES_FILTER"
]
