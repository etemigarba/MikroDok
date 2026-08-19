"""
Module: form_controls_ui
Description: Comprehensive form controls UI component library with theme integration and responsive design.
            Provides reusable form inputs, sliders, toggles, validation components, and form layout utilities
            for the MikroDok application. Implements modern UI/UX patterns with accessibility compliance,
            responsive breakpoint-aware sizing, and full theme system integration.

Features:
- Comprehensive form control factory with all input types
- Real-time validation with visual feedback and accessibility
- Responsive design with breakpoint-aware component sizing
- Theme-aware styling with dark/light mode support
- Accessibility compliance with WCAG 2.1 AA standards
- Form layout utilities and section management
- State management and event handling
- Performance-optimized component rendering

Phase: 1 (Common Components)
Location: /src/modules/ui/common_components_ui/form_controls_ui/form_controls_ui.py

Usage Examples:

1. Basic Form Controls:
```python
from src.modules.ui.common_components_ui.form_controls_ui import FormControlsUI

# Create form controls instance
form_controls = FormControlsUI()

# Create text input
text_field = form_controls.create_text_field(
    label="Username",
    placeholder="Enter your username",
    required=True,
    validation_rules=[ValidationRule.REQUIRED, ValidationRule.MIN_LENGTH(3)]
)

# Create dropdown
dropdown = form_controls.create_dropdown(
    label="Model Size",
    options=["1B", "3B", "7B"],
    value="3B"
)
```

2. Form Layout and Validation:
```python
# Create form section
form_section = form_controls.create_form_section(
    title="Training Configuration",
    fields=[text_field, dropdown],
    collapsible=True
)

# Validate form
validation_result = form_controls.validate_form(form_section)
if validation_result.is_valid:
    print("Form is valid!")
```
"""

# Standard library imports
import re
import json
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ColorPalette,
    TypographyScale,
    SpacingSystem,
    IconSystem,
    ResponsiveLayoutManager,
    ScreenSize
)


class FormFieldType(Enum):
    """Enumeration of supported form field types."""
    TEXT = "text"
    PASSWORD = "password"
    EMAIL = "email"
    NUMBER = "number"
    SEARCH = "search"
    TEXTAREA = "textarea"
    DROPDOWN = "dropdown"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    TOGGLE = "toggle"
    SLIDER = "slider"
    RANGE = "range"
    DATE = "date"
    TIME = "time"
    FILE = "file"
    BUTTON = "button"


class ValidationRule(Enum):
    """Enumeration of validation rules."""
    REQUIRED = "required"
    EMAIL = "email"
    URL = "url"
    NUMERIC = "numeric"
    ALPHA = "alpha"
    ALPHANUMERIC = "alphanumeric"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    PATTERN = "pattern"
    CUSTOM = "custom"


class FormValidationState(Enum):
    """Enumeration of form validation states."""
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    UNTOUCHED = "untouched"


class ButtonVariant(Enum):
    """Enumeration of button variants."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    OUTLINED = "outlined"
    TEXT = "text"
    ICON = "icon"
    FAB = "fab"


class InputVariant(Enum):
    """Enumeration of input field variants."""
    FILLED = "filled"
    OUTLINED = "outlined"
    UNDERLINED = "underlined"


class SelectionVariant(Enum):
    """Enumeration of selection component variants."""
    STANDARD = "standard"
    COMPACT = "compact"
    CARD = "card"


@dataclass
class ValidationError:
    """Represents a form validation error."""
    field_name: str
    rule: ValidationRule
    message: str
    severity: str = "error"  # error, warning, info


@dataclass
class FormField:
    """Represents a form field configuration."""
    name: str
    field_type: FormFieldType
    label: str
    value: Any = None
    placeholder: str = ""
    required: bool = False
    disabled: bool = False
    readonly: bool = False
    validation_rules: List[ValidationRule] = field(default_factory=list)
    validation_state: FormValidationState = FormValidationState.UNTOUCHED
    validation_errors: List[ValidationError] = field(default_factory=list)
    options: List[str] = field(default_factory=list)  # For dropdown, radio, etc.
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    multiline: bool = False
    max_lines: int = 1
    on_change: Optional[Callable] = None
    on_submit: Optional[Callable] = None
    tooltip: str = ""
    help_text: str = ""
    variant: Union[InputVariant, SelectionVariant, ButtonVariant] = InputVariant.OUTLINED


@dataclass
class FormSection:
    """Represents a form section with grouped fields."""
    title: str
    fields: List[FormField]
    description: str = ""
    collapsible: bool = False
    collapsed: bool = False
    icon: str = ""


@dataclass
class FormLayout:
    """Represents a complete form layout."""
    title: str
    sections: List[FormSection]
    submit_text: str = "Submit"
    cancel_text: str = "Cancel"
    on_submit: Optional[Callable] = None
    on_cancel: Optional[Callable] = None


class FormValidator:
    """Form validation utility class."""
    
    @staticmethod
    def validate_field(field: FormField) -> List[ValidationError]:
        """
        Validate a single form field.
        
        Args:
            field: Form field to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        value = field.value
        
        # Required validation
        if ValidationRule.REQUIRED in field.validation_rules:
            if not value or (isinstance(value, str) and not value.strip()):
                errors.append(ValidationError(
                    field_name=field.name,
                    rule=ValidationRule.REQUIRED,
                    message=f"{field.label} is required"
                ))
                return errors  # Don't validate further if required field is empty
        
        # Skip other validations if field is empty and not required
        if not value:
            return errors
            
        # Email validation
        if ValidationRule.EMAIL in field.validation_rules:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, str(value)):
                errors.append(ValidationError(
                    field_name=field.name,
                    rule=ValidationRule.EMAIL,
                    message="Please enter a valid email address"
                ))
        
        # URL validation
        if ValidationRule.URL in field.validation_rules:
            url_pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'
            if not re.match(url_pattern, str(value)):
                errors.append(ValidationError(
                    field_name=field.name,
                    rule=ValidationRule.URL,
                    message="Please enter a valid URL"
                ))
        
        # Numeric validation
        if ValidationRule.NUMERIC in field.validation_rules:
            try:
                float(value)
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    field_name=field.name,
                    rule=ValidationRule.NUMERIC,
                    message="Please enter a valid number"
                ))
        
        # Length validations
        if isinstance(value, str):
            for rule in field.validation_rules:
                if isinstance(rule, tuple) and rule[0] == ValidationRule.MIN_LENGTH:
                    min_len = rule[1]
                    if len(value) < min_len:
                        errors.append(ValidationError(
                            field_name=field.name,
                            rule=ValidationRule.MIN_LENGTH,
                            message=f"Minimum length is {min_len} characters"
                        ))
                elif isinstance(rule, tuple) and rule[0] == ValidationRule.MAX_LENGTH:
                    max_len = rule[1]
                    if len(value) > max_len:
                        errors.append(ValidationError(
                            field_name=field.name,
                            rule=ValidationRule.MAX_LENGTH,
                            message=f"Maximum length is {max_len} characters"
                        ))
        
        return errors
    
    @staticmethod
    def validate_form(form_layout: FormLayout) -> Dict[str, Any]:
        """
        Validate an entire form layout.
        
        Args:
            form_layout: Form layout to validate
            
        Returns:
            Validation result dictionary
        """
        all_errors = []
        field_errors = {}
        
        for section in form_layout.sections:
            for field in section.fields:
                errors = FormValidator.validate_field(field)
                if errors:
                    all_errors.extend(errors)
                    field_errors[field.name] = errors
                    field.validation_state = FormValidationState.INVALID
                    field.validation_errors = errors
                else:
                    field.validation_state = FormValidationState.VALID
                    field.validation_errors = []
        
        return {
            "is_valid": len(all_errors) == 0,
            "errors": all_errors,
            "field_errors": field_errors,
            "error_count": len(all_errors)
        }


class FormControlsUI(ThemeAwareUserControl):
    """
    Comprehensive form controls UI component with responsive design and theme integration.
    
    Features:
    - Complete form control factory for all input types
    - Real-time validation with visual feedback
    - Responsive design with breakpoint-aware sizing
    - Theme-aware styling with accessibility compliance
    - Form layout utilities and section management
    - State management and event handling
    - Performance-optimized rendering
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._form_fields: Dict[str, FormField] = {}
        self._validation_enabled = True
        self._auto_validate = True
        self._form_layout: Optional[FormLayout] = None
        
    def build(self):
        """Build the form controls UI."""
        return ft.Container()  # Base container, actual controls created via factory methods

    # ============================================================================
    # TEXT INPUT COMPONENTS
    # ============================================================================

    def create_text_field(
        self,
        label: str,
        name: Optional[str] = None,
        value: str = "",
        placeholder: str = "",
        required: bool = False,
        disabled: bool = False,
        readonly: bool = False,
        multiline: bool = False,
        max_lines: int = 1,
        max_length: Optional[int] = None,
        validation_rules: Optional[List[ValidationRule]] = None,
        on_change: Optional[Callable] = None,
        on_submit: Optional[Callable] = None,
        variant: InputVariant = InputVariant.OUTLINED,
        tooltip: str = "",
        help_text: str = "",
        prefix_icon: Optional[str] = None,
        suffix_icon: Optional[str] = None,
        **kwargs
    ) -> ft.TextField:
        """
        Create a themed text field with validation support.

        Args:
            label: Field label
            name: Field name for form handling
            value: Initial value
            placeholder: Placeholder text
            required: Whether field is required
            disabled: Whether field is disabled
            readonly: Whether field is read-only
            multiline: Whether field supports multiple lines
            max_lines: Maximum number of lines for multiline
            max_length: Maximum character length
            validation_rules: List of validation rules
            on_change: Change event handler
            on_submit: Submit event handler
            variant: Input field variant
            tooltip: Tooltip text
            help_text: Help text below field
            prefix_icon: Icon before text
            suffix_icon: Icon after text
            **kwargs: Additional Flet TextField properties

        Returns:
            Configured TextField component
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Responsive sizing
        field_height = rlm.get_breakpoint_value(
            mobile=44, tablet=48, desktop=52, large=56
        )
        font_size = rlm.get_responsive_font_size(typography.body_medium[0])

        # Create form field for tracking
        field_name = name or label.lower().replace(" ", "_")
        form_field = FormField(
            name=field_name,
            field_type=FormFieldType.TEXTAREA if multiline else FormFieldType.TEXT,
            label=label,
            value=value,
            placeholder=placeholder,
            required=required,
            disabled=disabled,
            readonly=readonly,
            validation_rules=validation_rules or [],
            multiline=multiline,
            max_lines=max_lines,
            on_change=on_change,
            on_submit=on_submit,
            tooltip=tooltip,
            help_text=help_text,
            variant=variant
        )
        self._form_fields[field_name] = form_field

        # Validation wrapper
        def handle_change(e):
            form_field.value = e.control.value
            if self._auto_validate:
                self._validate_field(form_field, e.control)
            if on_change:
                on_change(e)

        # Configure text field based on variant
        text_field_props = {
            "label": label,
            "value": value,
            "hint_text": placeholder,
            "multiline": multiline,
            "max_lines": max_lines if multiline else 1,
            "disabled": disabled,
            "read_only": readonly,
            "on_change": handle_change,
            "on_submit": on_submit,
            "text_style": ft.TextStyle(
                size=font_size,
                color=palette.text_primary
            ),
            "label_style": ft.TextStyle(
                size=font_size - 2,
                color=palette.text_secondary
            ),
            "hint_style": ft.TextStyle(
                size=font_size,
                color=palette.text_tertiary
            ),
            "cursor_color": palette.primary,
            "selection_color": palette.selection,
            **kwargs
        }

        # Apply variant-specific styling
        if variant == InputVariant.OUTLINED:
            text_field_props.update({
                "border_color": palette.outline,
                "focused_border_color": palette.primary,
                "bgcolor": palette.surface,
                "filled": False
            })
        elif variant == InputVariant.FILLED:
            text_field_props.update({
                "bgcolor": palette.surface_variant,
                "border_color": ft.Colors.TRANSPARENT,
                "focused_border_color": palette.primary,
                "filled": True
            })
        elif variant == InputVariant.UNDERLINED:
            text_field_props.update({
                "border": ft.InputBorder.UNDERLINE,
                "border_color": palette.outline,
                "focused_border_color": palette.primary,
                "bgcolor": ft.Colors.TRANSPARENT,
                "filled": False
            })

        # Add icons if specified
        if prefix_icon:
            text_field_props["prefix_icon"] = prefix_icon
        if suffix_icon:
            text_field_props["suffix_icon"] = suffix_icon

        # Set height for single-line fields
        if not multiline:
            text_field_props["height"] = field_height

        # Add max length if specified
        if max_length:
            text_field_props["max_length"] = max_length

        # Add tooltip if specified
        if tooltip:
            text_field_props["tooltip"] = tooltip

        text_field = ft.TextField(**text_field_props)

        # Wrap with help text if provided
        if help_text:
            return self._wrap_with_help_text(text_field, help_text)

        return text_field

    def create_password_field(
        self,
        label: str = "Password",
        name: Optional[str] = None,
        value: str = "",
        placeholder: str = "Enter password",
        required: bool = True,
        show_toggle: bool = True,
        validation_rules: Optional[List[ValidationRule]] = None,
        on_change: Optional[Callable] = None,
        **kwargs
    ) -> ft.TextField:
        """
        Create a themed password field with show/hide toggle.

        Args:
            label: Field label
            name: Field name
            value: Initial value
            placeholder: Placeholder text
            required: Whether field is required
            show_toggle: Whether to show password visibility toggle
            validation_rules: List of validation rules
            on_change: Change event handler
            **kwargs: Additional properties

        Returns:
            Configured password TextField
        """
        # Add password-specific validation rules
        rules = validation_rules or []
        if required and ValidationRule.REQUIRED not in rules:
            rules.append(ValidationRule.REQUIRED)

        suffix_icon = self.get_icon('VISIBILITY_OFF') if show_toggle else None

        password_field = self.create_text_field(
            label=label,
            name=name or "password",
            value=value,
            placeholder=placeholder,
            required=required,
            validation_rules=rules,
            on_change=on_change,
            suffix_icon=suffix_icon,
            password=True,
            can_reveal_password=show_toggle,
            **kwargs
        )

        return password_field

    def create_number_field(
        self,
        label: str,
        name: Optional[str] = None,
        value: Optional[float] = None,
        placeholder: str = "",
        required: bool = False,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        step: Optional[float] = None,
        decimal_places: int = 2,
        validation_rules: Optional[List[ValidationRule]] = None,
        on_change: Optional[Callable] = None,
        **kwargs
    ) -> ft.TextField:
        """
        Create a themed number input field with validation.

        Args:
            label: Field label
            name: Field name
            value: Initial numeric value
            placeholder: Placeholder text
            required: Whether field is required
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            step: Step increment for number input
            decimal_places: Number of decimal places to display
            validation_rules: List of validation rules
            on_change: Change event handler
            **kwargs: Additional properties

        Returns:
            Configured number TextField
        """
        # Add numeric validation rules
        rules = validation_rules or []
        if ValidationRule.NUMERIC not in rules:
            rules.append(ValidationRule.NUMERIC)
        if required and ValidationRule.REQUIRED not in rules:
            rules.append(ValidationRule.REQUIRED)
        if min_value is not None:
            rules.append((ValidationRule.MIN_VALUE, min_value))
        if max_value is not None:
            rules.append((ValidationRule.MAX_VALUE, max_value))

        # Format initial value
        display_value = ""
        if value is not None:
            if decimal_places == 0:
                display_value = str(int(value))
            else:
                display_value = f"{value:.{decimal_places}f}"

        def handle_number_change(e):
            try:
                # Parse the input value
                input_value = e.control.value.strip()
                if input_value:
                    parsed_value = float(input_value)
                    # Apply min/max constraints
                    if min_value is not None:
                        parsed_value = max(parsed_value, min_value)
                    if max_value is not None:
                        parsed_value = min(parsed_value, max_value)

                    # Update the field value
                    if decimal_places == 0:
                        parsed_value = int(parsed_value)

                    # Store the parsed value in form field
                    field_name = name or label.lower().replace(" ", "_")
                    if field_name in self._form_fields:
                        self._form_fields[field_name].value = parsed_value

                if on_change:
                    on_change(e)
            except ValueError:
                # Invalid number input - let validation handle it
                if on_change:
                    on_change(e)

        number_field = self.create_text_field(
            label=label,
            name=name or "number",
            value=display_value,
            placeholder=placeholder,
            required=required,
            validation_rules=rules,
            on_change=handle_number_change,
            **kwargs
        )

        # Store additional number field properties
        field_name = name or label.lower().replace(" ", "_")
        if field_name in self._form_fields:
            form_field = self._form_fields[field_name]
            form_field.field_type = FormFieldType.NUMBER
            form_field.min_value = min_value
            form_field.max_value = max_value
            form_field.step = step

        return number_field

    def create_search_field(
        self,
        label: str = "Search",
        name: Optional[str] = None,
        value: str = "",
        placeholder: str = "Search...",
        on_change: Optional[Callable] = None,
        on_submit: Optional[Callable] = None,
        show_clear_button: bool = True,
        **kwargs
    ) -> ft.TextField:
        """
        Create a themed search input field.

        Args:
            label: Field label
            name: Field name
            value: Initial value
            placeholder: Placeholder text
            on_change: Change event handler
            on_submit: Submit event handler
            show_clear_button: Whether to show clear button
            **kwargs: Additional properties

        Returns:
            Configured search TextField
        """
        prefix_icon = self.get_icon('SEARCH')
        suffix_icon = self.get_icon('CLEAR') if show_clear_button and value else None

        def handle_search_change(e):
            # Update suffix icon based on content
            if show_clear_button:
                if e.control.value:
                    e.control.suffix_icon = self.get_icon('CLEAR')
                else:
                    e.control.suffix_icon = None
                e.control.update()

            if on_change:
                on_change(e)

        search_field = self.create_text_field(
            label=label,
            name=name or "search",
            value=value,
            placeholder=placeholder,
            required=False,
            validation_rules=[],
            on_change=handle_search_change,
            on_submit=on_submit,
            prefix_icon=prefix_icon,
            suffix_icon=suffix_icon,
            **kwargs
        )

        # Update form field type
        field_name = name or "search"
        if field_name in self._form_fields:
            self._form_fields[field_name].field_type = FormFieldType.SEARCH

        return search_field

    def create_email_field(
        self,
        label: str = "Email",
        name: Optional[str] = None,
        value: str = "",
        placeholder: str = "Enter email address",
        required: bool = False,
        validation_rules: Optional[List[ValidationRule]] = None,
        on_change: Optional[Callable] = None,
        **kwargs
    ) -> ft.TextField:
        """
        Create a themed email input field with validation.

        Args:
            label: Field label
            name: Field name
            value: Initial value
            placeholder: Placeholder text
            required: Whether field is required
            validation_rules: List of validation rules
            on_change: Change event handler
            **kwargs: Additional properties

        Returns:
            Configured email TextField
        """
        # Add email validation rules
        rules = validation_rules or []
        if ValidationRule.EMAIL not in rules:
            rules.append(ValidationRule.EMAIL)
        if required and ValidationRule.REQUIRED not in rules:
            rules.append(ValidationRule.REQUIRED)

        email_field = self.create_text_field(
            label=label,
            name=name or "email",
            value=value,
            placeholder=placeholder,
            required=required,
            validation_rules=rules,
            on_change=on_change,
            prefix_icon=self.get_icon('EMAIL'),
            **kwargs
        )

        # Update form field type
        field_name = name or "email"
        if field_name in self._form_fields:
            self._form_fields[field_name].field_type = FormFieldType.EMAIL

        return email_field

    # ============================================================================
    # SELECTION COMPONENTS
    # ============================================================================

    def create_dropdown(
        self,
        label: str,
        options: List[str],
        name: Optional[str] = None,
        value: Optional[str] = None,
        placeholder: str = "Select an option",
        required: bool = False,
        disabled: bool = False,
        validation_rules: Optional[List[ValidationRule]] = None,
        on_change: Optional[Callable] = None,
        variant: SelectionVariant = SelectionVariant.STANDARD,
        **kwargs
    ) -> ft.Dropdown:
        """
        Create a themed dropdown selection component.

        Args:
            label: Field label
            options: List of option values
            name: Field name
            value: Initial selected value
            placeholder: Placeholder text
            required: Whether field is required
            disabled: Whether field is disabled
            validation_rules: List of validation rules
            on_change: Change event handler
            variant: Selection variant
            **kwargs: Additional properties

        Returns:
            Configured Dropdown component
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Responsive sizing
        field_height = rlm.get_breakpoint_value(
            mobile=44, tablet=48, desktop=52, large=56
        )
        font_size = rlm.get_responsive_font_size(typography.body_medium[0])

        # Create form field for tracking
        field_name = name or label.lower().replace(" ", "_")
        form_field = FormField(
            name=field_name,
            field_type=FormFieldType.DROPDOWN,
            label=label,
            value=value,
            required=required,
            disabled=disabled,
            validation_rules=validation_rules or [],
            options=options,
            on_change=on_change,
            variant=variant
        )
        self._form_fields[field_name] = form_field

        # Validation wrapper
        def handle_change(e):
            form_field.value = e.control.value
            if self._auto_validate:
                self._validate_field(form_field, e.control)
            if on_change:
                on_change(e)

        # Create dropdown options
        dropdown_options = [
            ft.dropdown.Option(key=option, text=option)
            for option in options
        ]

        dropdown_props = {
            "label": label,
            "value": value,
            "hint_text": placeholder,
            "options": dropdown_options,
            "disabled": disabled,
            "on_change": handle_change,
            "height": field_height,
            "text_style": ft.TextStyle(
                size=font_size,
                color=palette.text_primary
            ),
            "label_style": ft.TextStyle(
                size=font_size - 2,
                color=palette.text_secondary
            ),
            "hint_style": ft.TextStyle(
                size=font_size,
                color=palette.text_tertiary
            ),
            "bgcolor": palette.surface,
            "border_color": palette.outline,
            "focused_border_color": palette.primary,
            **kwargs
        }

        dropdown = ft.Dropdown(**dropdown_props)
        return dropdown

    def create_radio_group(
        self,
        label: str,
        options: List[str],
        name: Optional[str] = None,
        value: Optional[str] = None,
        required: bool = False,
        disabled: bool = False,
        orientation: str = "vertical",  # vertical or horizontal
        validation_rules: Optional[List[ValidationRule]] = None,
        on_change: Optional[Callable] = None,
        **kwargs
    ) -> ft.Container:
        """
        Create a themed radio button group.

        Args:
            label: Group label
            options: List of option values
            name: Field name
            value: Initial selected value
            required: Whether field is required
            disabled: Whether field is disabled
            orientation: Layout orientation (vertical/horizontal)
            validation_rules: List of validation rules
            on_change: Change event handler
            **kwargs: Additional properties

        Returns:
            Container with radio button group
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create form field for tracking
        field_name = name or label.lower().replace(" ", "_")
        form_field = FormField(
            name=field_name,
            field_type=FormFieldType.RADIO,
            label=label,
            value=value,
            required=required,
            disabled=disabled,
            validation_rules=validation_rules or [],
            options=options,
            on_change=on_change
        )
        self._form_fields[field_name] = form_field

        # Validation wrapper
        def handle_change(e):
            form_field.value = e.control.value
            if self._auto_validate:
                self._validate_field(form_field, e.control)
            if on_change:
                on_change(e)

        # Create radio buttons
        radio_buttons = []
        for option in options:
            radio_button = ft.RadioListTile(
                value=option,
                title=ft.Text(
                    option,
                    style=ft.TextStyle(
                        size=rlm.get_responsive_font_size(typography.body_medium[0]),
                        color=palette.text_primary
                    )
                ),
                group_value=value,
                on_change=handle_change,
                disabled=disabled,
                active_color=palette.primary,
                fill_color=palette.primary
            )
            radio_buttons.append(radio_button)

        # Create group label
        group_label = ft.Text(
            label,
            style=ft.TextStyle(
                size=rlm.get_responsive_font_size(typography.body_medium[0]),
                color=palette.text_primary,
                weight=ft.FontWeight.W_500
            )
        )

        # Layout radio buttons
        if orientation == "horizontal":
            radio_layout = ft.Row(
                controls=radio_buttons,
                spacing=spacing.lg,
                wrap=True
            )
        else:
            radio_layout = ft.Column(
                controls=radio_buttons,
                spacing=spacing.sm,
                tight=True
            )

        container = ft.Container(
            content=ft.Column(
                controls=[group_label, radio_layout],
                spacing=spacing.sm,
                tight=True
            ),
            padding=ft.padding.all(spacing.sm)
        )

        return container

    def create_checkbox_group(
        self,
        label: str,
        options: List[str],
        name: Optional[str] = None,
        values: Optional[List[str]] = None,
        required: bool = False,
        disabled: bool = False,
        orientation: str = "vertical",
        validation_rules: Optional[List[ValidationRule]] = None,
        on_change: Optional[Callable] = None,
        **kwargs
    ) -> ft.Container:
        """
        Create a themed checkbox group for multiple selections.

        Args:
            label: Group label
            options: List of option values
            name: Field name
            values: List of initially selected values
            required: Whether at least one selection is required
            disabled: Whether group is disabled
            orientation: Layout orientation (vertical/horizontal)
            validation_rules: List of validation rules
            on_change: Change event handler
            **kwargs: Additional properties

        Returns:
            Container with checkbox group
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create form field for tracking
        field_name = name or label.lower().replace(" ", "_")
        form_field = FormField(
            name=field_name,
            field_type=FormFieldType.CHECKBOX,
            label=label,
            value=values or [],
            required=required,
            disabled=disabled,
            validation_rules=validation_rules or [],
            options=options,
            on_change=on_change
        )
        self._form_fields[field_name] = form_field

        # Track selected values
        selected_values = set(values or [])

        def handle_checkbox_change(option):
            def on_checkbox_change(e):
                if e.control.value:
                    selected_values.add(option)
                else:
                    selected_values.discard(option)

                form_field.value = list(selected_values)
                if self._auto_validate:
                    self._validate_field(form_field, e.control)
                if on_change:
                    on_change(e)
            return on_checkbox_change

        # Create checkboxes
        checkboxes = []
        for option in options:
            checkbox = ft.Checkbox(
                label=option,
                value=option in selected_values,
                on_change=handle_checkbox_change(option),
                disabled=disabled,
                active_color=palette.primary,
                check_color=palette.surface,
                label_style=ft.TextStyle(
                    size=rlm.get_responsive_font_size(typography.body_medium[0]),
                    color=palette.text_primary
                )
            )
            checkboxes.append(checkbox)

        # Create group label
        group_label = ft.Text(
            label,
            style=ft.TextStyle(
                size=rlm.get_responsive_font_size(typography.body_medium[0]),
                color=palette.text_primary,
                weight=ft.FontWeight.W_500
            )
        )

        # Layout checkboxes
        if orientation == "horizontal":
            checkbox_layout = ft.Row(
                controls=checkboxes,
                spacing=spacing.lg,
                wrap=True
            )
        else:
            checkbox_layout = ft.Column(
                controls=checkboxes,
                spacing=spacing.sm,
                tight=True
            )

        container = ft.Container(
            content=ft.Column(
                controls=[group_label, checkbox_layout],
                spacing=spacing.sm,
                tight=True
            ),
            padding=ft.padding.all(spacing.sm)
        )

        return container

    def create_toggle_switch(
        self,
        label: str,
        name: Optional[str] = None,
        value: bool = False,
        disabled: bool = False,
        on_change: Optional[Callable] = None,
        description: str = "",
        **kwargs
    ) -> ft.Container:
        """
        Create a themed toggle switch component.

        Args:
            label: Switch label
            name: Field name
            value: Initial switch state
            disabled: Whether switch is disabled
            on_change: Change event handler
            description: Optional description text
            **kwargs: Additional properties

        Returns:
            Container with toggle switch
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create form field for tracking
        field_name = name or label.lower().replace(" ", "_")
        form_field = FormField(
            name=field_name,
            field_type=FormFieldType.TOGGLE,
            label=label,
            value=value,
            disabled=disabled,
            on_change=on_change
        )
        self._form_fields[field_name] = form_field

        # Validation wrapper
        def handle_change(e):
            form_field.value = e.control.value
            if on_change:
                on_change(e)

        # Create switch
        switch = ft.Switch(
            value=value,
            on_change=handle_change,
            disabled=disabled,
            active_color=palette.primary,
            inactive_thumb_color=palette.surface,
            inactive_track_color=palette.outline
        )

        # Create label
        switch_label = ft.Text(
            label,
            style=ft.TextStyle(
                size=rlm.get_responsive_font_size(typography.body_medium[0]),
                color=palette.text_primary,
                weight=ft.FontWeight.W_500
            )
        )

        # Create description if provided
        controls = [
            ft.Row(
                controls=[switch_label, switch],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        ]

        if description:
            desc_text = ft.Text(
                description,
                style=ft.TextStyle(
                    size=rlm.get_responsive_font_size(typography.body_small[0]),
                    color=palette.text_secondary
                )
            )
            controls.append(desc_text)

        container = ft.Container(
            content=ft.Column(
                controls=controls,
                spacing=spacing.xs,
                tight=True
            ),
            padding=ft.padding.all(spacing.sm)
        )

        return container

    # ============================================================================
    # BUTTON COMPONENTS
    # ============================================================================

    def create_button(
        self,
        text: str,
        name: Optional[str] = None,
        on_click: Optional[Callable] = None,
        variant: ButtonVariant = ButtonVariant.PRIMARY,
        disabled: bool = False,
        icon: Optional[str] = None,
        icon_position: str = "left",  # left, right, top, bottom
        width: Optional[float] = None,
        height: Optional[float] = None,
        tooltip: str = "",
        **kwargs
    ) -> ft.Control:
        """
        Create a themed button component.

        Args:
            text: Button text
            name: Button name/identifier
            on_click: Click event handler
            variant: Button variant
            disabled: Whether button is disabled
            icon: Optional icon name
            icon_position: Icon position relative to text
            width: Button width (responsive if None)
            height: Button height (responsive if None)
            tooltip: Tooltip text
            **kwargs: Additional properties

        Returns:
            Configured button component
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Responsive sizing
        button_height = height or rlm.get_breakpoint_value(
            mobile=40, tablet=44, desktop=48, large=52
        )
        button_width = width
        font_size = rlm.get_responsive_font_size(typography.body_medium[0])

        # Create button based on variant
        if variant == ButtonVariant.PRIMARY:
            button = ft.ElevatedButton(
                text=text,
                on_click=on_click,
                disabled=disabled,
                icon=icon,
                width=button_width,
                height=button_height,
                style=ft.ButtonStyle(
                    bgcolor=palette.primary,
                    color=palette.surface,
                    text_style=ft.TextStyle(
                        size=font_size,
                        weight=ft.FontWeight.W_500
                    ),
                    elevation=2,
                    shadow_color=palette.primary,
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                **kwargs
            )
        elif variant == ButtonVariant.SECONDARY:
            button = ft.ElevatedButton(
                text=text,
                on_click=on_click,
                disabled=disabled,
                icon=icon,
                width=button_width,
                height=button_height,
                style=ft.ButtonStyle(
                    bgcolor=palette.surface_variant,
                    color=palette.text_primary,
                    text_style=ft.TextStyle(
                        size=font_size,
                        weight=ft.FontWeight.W_500
                    ),
                    elevation=1,
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                **kwargs
            )
        elif variant == ButtonVariant.OUTLINED:
            button = ft.OutlinedButton(
                text=text,
                on_click=on_click,
                disabled=disabled,
                icon=icon,
                width=button_width,
                height=button_height,
                style=ft.ButtonStyle(
                    color=palette.primary,
                    text_style=ft.TextStyle(
                        size=font_size,
                        weight=ft.FontWeight.W_500
                    ),
                    side=ft.BorderSide(
                        width=1,
                        color=palette.outline
                    ),
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                **kwargs
            )
        elif variant == ButtonVariant.TEXT:
            button = ft.TextButton(
                text=text,
                on_click=on_click,
                disabled=disabled,
                icon=icon,
                width=button_width,
                height=button_height,
                style=ft.ButtonStyle(
                    color=palette.primary,
                    text_style=ft.TextStyle(
                        size=font_size,
                        weight=ft.FontWeight.W_500
                    ),
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                **kwargs
            )
        elif variant == ButtonVariant.ICON:
            button = ft.IconButton(
                icon=icon or self.get_icon('HELP'),
                on_click=on_click,
                disabled=disabled,
                icon_size=rlm.get_breakpoint_value(
                    mobile=20, tablet=22, desktop=24, large=26
                ),
                icon_color=palette.text_primary,
                bgcolor=palette.surface_variant,
                **kwargs
            )
        elif variant == ButtonVariant.FAB:
            button = ft.FloatingActionButton(
                icon=icon or self.get_icon('ADD'),
                on_click=on_click,
                disabled=disabled,
                bgcolor=palette.primary,
                foreground_color=palette.surface,
                **kwargs
            )
        else:
            # Default to primary
            button = ft.ElevatedButton(
                text=text,
                on_click=on_click,
                disabled=disabled,
                icon=icon,
                width=button_width,
                height=button_height,
                **kwargs
            )

        # Add tooltip if specified
        if tooltip:
            button.tooltip = tooltip

        return button

    def create_button_group(
        self,
        buttons: List[Dict[str, Any]],
        orientation: str = "horizontal",
        spacing: Optional[int] = None,
        **kwargs
    ) -> ft.Control:
        """
        Create a group of themed buttons.

        Args:
            buttons: List of button configurations
            orientation: Layout orientation (horizontal/vertical)
            spacing: Spacing between buttons
            **kwargs: Additional properties

        Returns:
            Container with button group
        """
        spacing_value = spacing or self.get_spacing().md

        # Create buttons from configurations
        button_controls = []
        for button_config in buttons:
            button = self.create_button(**button_config)
            button_controls.append(button)

        # Layout buttons
        if orientation == "horizontal":
            layout = ft.Row(
                controls=button_controls,
                spacing=spacing_value,
                alignment=ft.MainAxisAlignment.START,
                **kwargs
            )
        else:
            layout = ft.Column(
                controls=button_controls,
                spacing=spacing_value,
                alignment=ft.MainAxisAlignment.START,
                tight=True,
                **kwargs
            )

        return layout

    # ============================================================================
    # SLIDER AND RANGE COMPONENTS
    # ============================================================================

    def create_slider(
        self,
        label: str,
        name: Optional[str] = None,
        value: float = 0.0,
        min_value: float = 0.0,
        max_value: float = 100.0,
        step: float = 1.0,
        divisions: Optional[int] = None,
        show_value: bool = True,
        show_labels: bool = True,
        disabled: bool = False,
        on_change: Optional[Callable] = None,
        on_change_end: Optional[Callable] = None,
        format_value: Optional[Callable[[float], str]] = None,
        **kwargs
    ) -> ft.Container:
        """
        Create a themed slider component.

        Args:
            label: Slider label
            name: Field name
            value: Initial value
            min_value: Minimum value
            max_value: Maximum value
            step: Step increment
            divisions: Number of discrete divisions
            show_value: Whether to show current value
            show_labels: Whether to show min/max labels
            disabled: Whether slider is disabled
            on_change: Change event handler
            on_change_end: Change end event handler
            format_value: Custom value formatter function
            **kwargs: Additional properties

        Returns:
            Container with slider component
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create form field for tracking
        field_name = name or label.lower().replace(" ", "_")
        form_field = FormField(
            name=field_name,
            field_type=FormFieldType.SLIDER,
            label=label,
            value=value,
            min_value=min_value,
            max_value=max_value,
            step=step,
            disabled=disabled,
            on_change=on_change
        )
        self._form_fields[field_name] = form_field

        # Value formatter
        def format_slider_value(val: float) -> str:
            if format_value:
                return format_value(val)
            if step >= 1:
                return str(int(val))
            else:
                decimal_places = len(str(step).split('.')[-1])
                return f"{val:.{decimal_places}f}"

        # Current value display
        current_value_text = ft.Text(
            format_slider_value(value),
            style=ft.TextStyle(
                size=rlm.get_responsive_font_size(typography.body_small[0]),
                color=palette.text_primary,
                weight=ft.FontWeight.W_500
            )
        )

        # Validation wrapper
        def handle_change(e):
            form_field.value = e.control.value
            if show_value:
                current_value_text.value = format_slider_value(e.control.value)
                current_value_text.update()
            if on_change:
                on_change(e)

        def handle_change_end(e):
            if on_change_end:
                on_change_end(e)

        # Create slider
        slider = ft.Slider(
            value=value,
            min=min_value,
            max=max_value,
            divisions=divisions,
            disabled=disabled,
            on_change=handle_change,
            on_change_end=handle_change_end,
            active_color=palette.primary,
            inactive_color=palette.outline,
            thumb_color=palette.primary,
            **kwargs
        )

        # Create header with label and value
        header_controls = [
            ft.Text(
                label,
                style=ft.TextStyle(
                    size=rlm.get_responsive_font_size(typography.body_medium[0]),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                )
            )
        ]

        if show_value:
            header_controls.append(current_value_text)

        header = ft.Row(
            controls=header_controls,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        # Create labels if requested
        controls = [header, slider]

        if show_labels:
            labels = ft.Row(
                controls=[
                    ft.Text(
                        format_slider_value(min_value),
                        style=ft.TextStyle(
                            size=rlm.get_responsive_font_size(typography.caption[0]),
                            color=palette.text_secondary
                        )
                    ),
                    ft.Text(
                        format_slider_value(max_value),
                        style=ft.TextStyle(
                            size=rlm.get_responsive_font_size(typography.caption[0]),
                            color=palette.text_secondary
                        )
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
            controls.append(labels)

        container = ft.Container(
            content=ft.Column(
                controls=controls,
                spacing=spacing.xs,
                tight=True
            ),
            padding=ft.padding.all(spacing.sm)
        )

        return container

    def create_progress_indicator(
        self,
        value: Optional[float] = None,
        label: str = "",
        show_percentage: bool = True,
        variant: str = "linear",  # linear, circular
        color: Optional[str] = None,
        height: Optional[float] = None,
        width: Optional[float] = None,
        **kwargs
    ) -> ft.Control:
        """
        Create a themed progress indicator.

        Args:
            value: Progress value (0.0 to 1.0, None for indeterminate)
            label: Progress label
            show_percentage: Whether to show percentage text
            variant: Progress variant (linear/circular)
            color: Custom progress color
            height: Custom height for linear progress
            width: Custom width
            **kwargs: Additional properties

        Returns:
            Progress indicator component
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        progress_color = color or palette.primary

        if variant == "circular":
            progress = ft.ProgressRing(
                value=value,
                color=progress_color,
                bgcolor=palette.surface_variant,
                width=width or rlm.get_breakpoint_value(
                    mobile=40, tablet=44, desktop=48, large=52
                ),
                height=width or rlm.get_breakpoint_value(
                    mobile=40, tablet=44, desktop=48, large=52
                ),
                **kwargs
            )

            if label or show_percentage:
                controls = []
                if label:
                    controls.append(
                        ft.Text(
                            label,
                            style=ft.TextStyle(
                                size=rlm.get_responsive_font_size(typography.body_medium[0]),
                                color=palette.text_primary
                            )
                        )
                    )

                if show_percentage and value is not None:
                    controls.append(
                        ft.Text(
                            f"{int(value * 100)}%",
                            style=ft.TextStyle(
                                size=rlm.get_responsive_font_size(typography.body_small[0]),
                                color=palette.text_secondary
                            )
                        )
                    )

                return ft.Column(
                    controls=[
                        ft.Column(controls=controls, spacing=spacing.xs, tight=True),
                        progress
                    ],
                    spacing=spacing.sm,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True
                )

            return progress

        else:  # linear
            progress = ft.ProgressBar(
                value=value,
                color=progress_color,
                bgcolor=palette.surface_variant,
                height=height or rlm.get_breakpoint_value(
                    mobile=4, tablet=6, desktop=8, large=8
                ),
                **kwargs
            )

            if label or show_percentage:
                header_controls = []
                if label:
                    header_controls.append(
                        ft.Text(
                            label,
                            style=ft.TextStyle(
                                size=rlm.get_responsive_font_size(typography.body_medium[0]),
                                color=palette.text_primary
                            )
                        )
                    )

                if show_percentage and value is not None:
                    header_controls.append(
                        ft.Text(
                            f"{int(value * 100)}%",
                            style=ft.TextStyle(
                                size=rlm.get_responsive_font_size(typography.body_small[0]),
                                color=palette.text_secondary
                            )
                        )
                    )

                header = ft.Row(
                    controls=header_controls,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )

                return ft.Column(
                    controls=[header, progress],
                    spacing=spacing.xs,
                    tight=True
                )

            return progress

    # ============================================================================
    # VALIDATION SYSTEM
    # ============================================================================

    def _validate_field(self, form_field: FormField, control: ft.Control) -> bool:
        """
        Validate a single form field and update UI.

        Args:
            form_field: Form field to validate
            control: UI control to update

        Returns:
            True if field is valid
        """
        errors = FormValidator.validate_field(form_field)

        # Update field validation state
        if errors:
            form_field.validation_state = FormValidationState.INVALID
            form_field.validation_errors = errors

            # Update control appearance for error state
            if hasattr(control, 'border_color'):
                control.border_color = self.get_palette().error
            if hasattr(control, 'error_text'):
                control.error_text = errors[0].message

            control.update()
            return False
        else:
            form_field.validation_state = FormValidationState.VALID
            form_field.validation_errors = []

            # Update control appearance for valid state
            if hasattr(control, 'border_color'):
                control.border_color = self.get_palette().outline
            if hasattr(control, 'error_text'):
                control.error_text = None

            control.update()
            return True

    def validate_all_fields(self) -> Dict[str, Any]:
        """
        Validate all form fields.

        Returns:
            Validation result dictionary
        """
        all_errors = []
        field_errors = {}

        for field_name, form_field in self._form_fields.items():
            errors = FormValidator.validate_field(form_field)
            if errors:
                all_errors.extend(errors)
                field_errors[field_name] = errors
                form_field.validation_state = FormValidationState.INVALID
                form_field.validation_errors = errors
            else:
                form_field.validation_state = FormValidationState.VALID
                form_field.validation_errors = []

        return {
            "is_valid": len(all_errors) == 0,
            "errors": all_errors,
            "field_errors": field_errors,
            "error_count": len(all_errors),
            "valid_fields": [name for name, field in self._form_fields.items()
                           if field.validation_state == FormValidationState.VALID],
            "invalid_fields": [name for name, field in self._form_fields.items()
                             if field.validation_state == FormValidationState.INVALID]
        }

    def get_form_data(self) -> Dict[str, Any]:
        """
        Get current form data.

        Returns:
            Dictionary of field names and values
        """
        return {name: field.value for name, field in self._form_fields.items()}

    def set_form_data(self, data: Dict[str, Any]) -> None:
        """
        Set form data from dictionary.

        Args:
            data: Dictionary of field names and values
        """
        for name, value in data.items():
            if name in self._form_fields:
                self._form_fields[name].value = value

    def clear_form(self) -> None:
        """Clear all form fields."""
        for field in self._form_fields.values():
            if field.field_type in [FormFieldType.TEXT, FormFieldType.EMAIL,
                                  FormFieldType.PASSWORD, FormFieldType.SEARCH]:
                field.value = ""
            elif field.field_type == FormFieldType.NUMBER:
                field.value = 0
            elif field.field_type in [FormFieldType.CHECKBOX]:
                field.value = []
            elif field.field_type == FormFieldType.TOGGLE:
                field.value = False
            elif field.field_type in [FormFieldType.DROPDOWN, FormFieldType.RADIO]:
                field.value = None
            elif field.field_type in [FormFieldType.SLIDER, FormFieldType.RANGE]:
                field.value = field.min_value or 0

            field.validation_state = FormValidationState.UNTOUCHED
            field.validation_errors = []

    def enable_auto_validation(self, enabled: bool = True) -> None:
        """
        Enable or disable automatic validation on field changes.

        Args:
            enabled: Whether to enable auto-validation
        """
        self._auto_validate = enabled

    def _wrap_with_help_text(self, control: ft.Control, help_text: str) -> ft.Container:
        """
        Wrap a control with help text.

        Args:
            control: Control to wrap
            help_text: Help text to display

        Returns:
            Container with control and help text
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        help_text_control = ft.Text(
            help_text,
            style=ft.TextStyle(
                size=rlm.get_responsive_font_size(typography.caption[0]),
                color=palette.text_secondary
            )
        )

        return ft.Container(
            content=ft.Column(
                controls=[control, help_text_control],
                spacing=spacing.xs,
                tight=True
            )
        )

    # ============================================================================
    # FORM LAYOUT COMPONENTS
    # ============================================================================

    def create_form_section(
        self,
        title: str,
        fields: List[ft.Control],
        description: str = "",
        collapsible: bool = False,
        collapsed: bool = False,
        icon: Optional[str] = None,
        spacing: Optional[int] = None,
        **kwargs
    ) -> ft.Container:
        """
        Create a form section with grouped fields.

        Args:
            title: Section title
            fields: List of form field controls
            description: Optional section description
            collapsible: Whether section can be collapsed
            collapsed: Initial collapsed state
            icon: Optional section icon
            spacing: Custom spacing between fields
            **kwargs: Additional properties

        Returns:
            Container with form section
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing_system = self.get_spacing()
        rlm = self.get_responsive_layout()

        field_spacing = spacing or spacing_system.lg

        # Create section header
        header_controls = []

        if icon:
            header_controls.append(
                ft.Icon(
                    icon,
                    size=rlm.get_breakpoint_value(
                        mobile=18, tablet=20, desktop=22, large=24
                    ),
                    color=palette.text_primary
                )
            )

        title_text = ft.Text(
            title,
            style=ft.TextStyle(
                size=rlm.get_responsive_font_size(typography.h4[0]),
                color=palette.text_primary,
                weight=ft.FontWeight.W_600
            )
        )
        header_controls.append(title_text)

        if collapsible:
            collapse_icon = ft.IconButton(
                icon=self.get_icon('EXPAND_LESS') if not collapsed else self.get_icon('EXPAND_MORE'),
                icon_size=rlm.get_breakpoint_value(
                    mobile=18, tablet=20, desktop=22, large=24
                ),
                icon_color=palette.text_secondary,
                on_click=lambda e: self._toggle_section_collapse(e, fields)
            )
            header_controls.append(collapse_icon)

        header = ft.Row(
            controls=header_controls,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        # Create section content
        section_controls = [header]

        if description:
            desc_text = ft.Text(
                description,
                style=ft.TextStyle(
                    size=rlm.get_responsive_font_size(typography.body_small[0]),
                    color=palette.text_secondary
                )
            )
            section_controls.append(desc_text)

        # Add fields container
        fields_container = ft.Column(
            controls=fields,
            spacing=field_spacing,
            tight=True
        )

        if collapsible and collapsed:
            fields_container.visible = False

        section_controls.append(fields_container)

        # Create section container
        section_container = ft.Container(
            content=ft.Column(
                controls=section_controls,
                spacing=spacing_system.md,
                tight=True
            ),
            padding=ft.padding.all(spacing_system.lg),
            border=ft.border.all(1, palette.outline),
            border_radius=8,
            bgcolor=palette.surface,
            **kwargs
        )

        return section_container

    def _toggle_section_collapse(self, e, fields_container):
        """Toggle section collapse state."""
        # This would be implemented with proper state management
        # For now, just toggle visibility
        if hasattr(fields_container, 'visible'):
            fields_container.visible = not fields_container.visible
            fields_container.update()

        # Update icon
        if fields_container.visible:
            e.control.icon = self.get_icon('EXPAND_LESS')
        else:
            e.control.icon = self.get_icon('EXPAND_MORE')
        e.control.update()

    def create_form_layout(
        self,
        sections: List[ft.Control],
        title: str = "",
        submit_button: Optional[ft.Control] = None,
        cancel_button: Optional[ft.Control] = None,
        actions_alignment: str = "right",  # left, center, right, space_between
        max_width: Optional[float] = None,
        **kwargs
    ) -> ft.Container:
        """
        Create a complete form layout with sections and actions.

        Args:
            sections: List of form section controls
            title: Form title
            submit_button: Submit button control
            cancel_button: Cancel button control
            actions_alignment: Alignment of action buttons
            max_width: Maximum form width
            **kwargs: Additional properties

        Returns:
            Container with complete form layout
        """
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Responsive max width
        form_max_width = max_width or rlm.get_breakpoint_value(
            mobile=None, tablet=600, desktop=800, large=1000
        )

        form_controls = []

        # Add form title if provided
        if title:
            title_text = ft.Text(
                title,
                style=ft.TextStyle(
                    size=rlm.get_responsive_font_size(typography.h2[0]),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_600
                )
            )
            form_controls.append(title_text)

        # Add sections
        form_controls.extend(sections)

        # Add action buttons if provided
        if submit_button or cancel_button:
            action_controls = []

            if cancel_button:
                action_controls.append(cancel_button)
            if submit_button:
                action_controls.append(submit_button)

            # Determine alignment
            if actions_alignment == "left":
                alignment = ft.MainAxisAlignment.START
            elif actions_alignment == "center":
                alignment = ft.MainAxisAlignment.CENTER
            elif actions_alignment == "space_between":
                alignment = ft.MainAxisAlignment.SPACE_BETWEEN
            else:  # right
                alignment = ft.MainAxisAlignment.END

            actions_row = ft.Row(
                controls=action_controls,
                alignment=alignment,
                spacing=spacing.md
            )

            form_controls.append(actions_row)

        # Create form container
        form_content = ft.Column(
            controls=form_controls,
            spacing=spacing.xl,
            tight=True,
            scroll=ft.ScrollMode.AUTO
        )

        form_container = ft.Container(
            content=form_content,
            width=form_max_width,
            padding=ft.padding.all(spacing.xl),
            bgcolor=palette.background_primary,
            border_radius=12,
            **kwargs
        )

        # Center the form if max_width is set
        if form_max_width:
            return ft.Container(
                content=form_container,
                alignment=ft.alignment.center,
                expand=True
            )

        return form_container

    def create_field_group(
        self,
        fields: List[ft.Control],
        orientation: str = "vertical",  # vertical, horizontal, grid
        columns: Optional[int] = None,
        spacing: Optional[int] = None,
        equal_width: bool = False,
        **kwargs
    ) -> ft.Control:
        """
        Create a group of form fields with specified layout.

        Args:
            fields: List of form field controls
            orientation: Layout orientation
            columns: Number of columns for grid layout
            spacing: Custom spacing between fields
            equal_width: Whether fields should have equal width
            **kwargs: Additional properties

        Returns:
            Layout control with grouped fields
        """
        spacing_value = spacing or self.get_spacing().md
        rlm = self.get_responsive_layout()

        if orientation == "horizontal":
            if equal_width:
                # Make all fields expand equally
                for field in fields:
                    if hasattr(field, 'expand'):
                        field.expand = True

            return ft.Row(
                controls=fields,
                spacing=spacing_value,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                **kwargs
            )

        elif orientation == "grid":
            # Use responsive columns if not specified
            grid_columns = columns or rlm.get_responsive_columns()

            # Create grid using ResponsiveLayoutManager
            return rlm.create_responsive_grid(
                children=fields,
                mobile_cols=1,
                tablet_cols=min(2, grid_columns),
                desktop_cols=grid_columns,
                large_cols=grid_columns,
                spacing=spacing_value,
                **kwargs
            )

        else:  # vertical
            return ft.Column(
                controls=fields,
                spacing=spacing_value,
                tight=True,
                **kwargs
            )
