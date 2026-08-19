"""
MikroDok Form Controls UI Package
Provides comprehensive form control components with theme integration and responsive design.
"""

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Form controls UI components for MikroDok application"

# Import form controls components
try:
    from .form_controls_ui import (
        FormControlsUI,
        FormFieldType,
        ValidationRule,
        FormValidationState,
        ButtonVariant,
        InputVariant,
        SelectionVariant,
        FormField,
        FormSection,
        FormLayout,
        ValidationError,
        FormValidator
    )
except ImportError:
    pass

# Export main components
__all__ = [
    "FormControlsUI",
    "FormFieldType",
    "ValidationRule", 
    "FormValidationState",
    "ButtonVariant",
    "InputVariant",
    "SelectionVariant",
    "FormField",
    "FormSection", 
    "FormLayout",
    "ValidationError",
    "FormValidator"
]
