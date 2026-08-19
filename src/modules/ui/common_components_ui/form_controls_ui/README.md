# Form Controls UI Module

## Overview

The `form_controls_ui` module provides a comprehensive set of themed form controls for the MikroDok application. It includes input fields, selection components, buttons, sliders, validation systems, and form layout utilities, all with full theme integration and responsive design.

## Features

- **Complete Form Control Library**: Text fields, dropdowns, radio buttons, checkboxes, toggles, sliders, and buttons
- **Theme Integration**: Full integration with MikroDok's theme system for consistent styling
- **Responsive Design**: Breakpoint-aware sizing and layout adaptation
- **Validation System**: Real-time validation with visual feedback and accessibility compliance
- **Form Layout Utilities**: Section grouping, form layouts, and field organization
- **Accessibility Compliance**: WCAG 2.1 AA compliant with proper ARIA labels and keyboard navigation
- **Performance Optimized**: Efficient rendering and state management

## Quick Start

```python
from src.modules.ui.common_components_ui.form_controls_ui import FormControlsUI, ValidationRule

# Create form controls instance
form_controls = FormControlsUI()

# Create a text field with validation
username_field = form_controls.create_text_field(
    label="Username",
    placeholder="Enter your username",
    required=True,
    validation_rules=[ValidationRule.REQUIRED, ValidationRule.MIN_LENGTH(3)]
)

# Create a dropdown
model_dropdown = form_controls.create_dropdown(
    label="Model Size",
    options=["1B", "3B", "7B"],
    value="3B"
)

# Create buttons
submit_button = form_controls.create_button(
    text="Submit",
    variant=ButtonVariant.PRIMARY,
    on_click=handle_submit
)

cancel_button = form_controls.create_button(
    text="Cancel",
    variant=ButtonVariant.OUTLINED,
    on_click=handle_cancel
)
```

## Components

### Input Fields

#### Text Field
```python
text_field = form_controls.create_text_field(
    label="Field Label",
    placeholder="Enter text...",
    required=True,
    validation_rules=[ValidationRule.REQUIRED],
    variant=InputVariant.OUTLINED
)
```

#### Password Field
```python
password_field = form_controls.create_password_field(
    label="Password",
    required=True,
    show_toggle=True
)
```

#### Number Field
```python
number_field = form_controls.create_number_field(
    label="Age",
    min_value=0,
    max_value=120,
    step=1,
    decimal_places=0
)
```

#### Email Field
```python
email_field = form_controls.create_email_field(
    label="Email Address",
    required=True
)
```

#### Search Field
```python
search_field = form_controls.create_search_field(
    placeholder="Search documents...",
    show_clear_button=True
)
```

### Selection Components

#### Dropdown
```python
dropdown = form_controls.create_dropdown(
    label="Select Option",
    options=["Option 1", "Option 2", "Option 3"],
    required=True
)
```

#### Radio Button Group
```python
radio_group = form_controls.create_radio_group(
    label="Training Method",
    options=["From Scratch", "Fine-Tune", "QLoRA"],
    orientation="vertical"
)
```

#### Checkbox Group
```python
checkbox_group = form_controls.create_checkbox_group(
    label="Features",
    options=["Feature A", "Feature B", "Feature C"],
    orientation="horizontal"
)
```

#### Toggle Switch
```python
toggle = form_controls.create_toggle_switch(
    label="Enable Auto-Save",
    description="Automatically save changes",
    value=True
)
```

### Buttons

#### Primary Button
```python
primary_button = form_controls.create_button(
    text="Start Training",
    variant=ButtonVariant.PRIMARY,
    icon="play_arrow"
)
```

#### Secondary Button
```python
secondary_button = form_controls.create_button(
    text="Save Draft",
    variant=ButtonVariant.SECONDARY
)
```

#### Outlined Button
```python
outlined_button = form_controls.create_button(
    text="Cancel",
    variant=ButtonVariant.OUTLINED
)
```

#### Icon Button
```python
icon_button = form_controls.create_button(
    text="",
    variant=ButtonVariant.ICON,
    icon="settings",
    tooltip="Settings"
)
```

#### Button Group
```python
button_group = form_controls.create_button_group([
    {"text": "Save", "variant": ButtonVariant.PRIMARY},
    {"text": "Cancel", "variant": ButtonVariant.OUTLINED}
], orientation="horizontal")
```

### Sliders and Progress

#### Slider
```python
slider = form_controls.create_slider(
    label="Learning Rate",
    min_value=0.0001,
    max_value=0.1,
    step=0.0001,
    value=0.001,
    show_value=True,
    format_value=lambda x: f"{x:.4f}"
)
```

#### Progress Indicator
```python
# Linear progress
progress_bar = form_controls.create_progress_indicator(
    value=0.75,
    label="Training Progress",
    variant="linear"
)

# Circular progress
progress_ring = form_controls.create_progress_indicator(
    value=0.5,
    variant="circular"
)
```

## Validation System

### Validation Rules

The module supports various validation rules:

- `ValidationRule.REQUIRED`: Field is required
- `ValidationRule.EMAIL`: Valid email format
- `ValidationRule.URL`: Valid URL format
- `ValidationRule.NUMERIC`: Numeric values only
- `ValidationRule.MIN_LENGTH`: Minimum character length
- `ValidationRule.MAX_LENGTH`: Maximum character length
- `ValidationRule.MIN_VALUE`: Minimum numeric value
- `ValidationRule.MAX_VALUE`: Maximum numeric value
- `ValidationRule.PATTERN`: Custom regex pattern

### Real-time Validation

```python
# Enable auto-validation (default)
form_controls.enable_auto_validation(True)

# Validate all fields manually
validation_result = form_controls.validate_all_fields()
if validation_result["is_valid"]:
    print("Form is valid!")
else:
    print(f"Errors: {validation_result['errors']}")
```

### Form Data Management

```python
# Get form data
form_data = form_controls.get_form_data()

# Set form data
form_controls.set_form_data({
    "username": "john_doe",
    "email": "john@example.com"
})

# Clear form
form_controls.clear_form()
```

## Form Layout

### Form Sections

```python
# Create form section
section = form_controls.create_form_section(
    title="User Information",
    fields=[username_field, email_field],
    description="Enter your account details",
    collapsible=True,
    icon="person"
)
```

### Complete Form Layout

```python
# Create complete form
form_layout = form_controls.create_form_layout(
    title="User Registration",
    sections=[user_section, preferences_section],
    submit_button=submit_button,
    cancel_button=cancel_button,
    actions_alignment="right"
)
```

### Field Groups

```python
# Horizontal field group
horizontal_group = form_controls.create_field_group(
    fields=[first_name_field, last_name_field],
    orientation="horizontal",
    equal_width=True
)

# Grid layout
grid_group = form_controls.create_field_group(
    fields=[field1, field2, field3, field4],
    orientation="grid",
    columns=2
)
```

## Responsive Design

All components automatically adapt to different screen sizes:

- **Mobile (0-575px)**: Single column layouts, larger touch targets
- **Tablet (576-991px)**: Two-column layouts, medium sizing
- **Desktop (992-1599px)**: Multi-column layouts, standard sizing
- **Large Desktop (1600px+)**: Wide layouts, larger sizing

## Theme Integration

Components automatically inherit theme colors, typography, and spacing:

```python
# Components use theme colors
palette = form_controls.get_palette()
typography = form_controls.get_typography()
spacing = form_controls.get_spacing()

# Responsive layout manager
rlm = form_controls.get_responsive_layout()
```

## Accessibility Features

- **Keyboard Navigation**: Full keyboard support with logical tab order
- **Screen Reader Support**: Proper ARIA labels and descriptions
- **High Contrast**: Theme-aware color schemes
- **Touch Targets**: Minimum 44px touch targets on mobile
- **Focus Indicators**: Clear focus states for all interactive elements
- **Error Announcements**: Accessible error messaging

## Performance Considerations

- **Lazy Rendering**: Components rendered on demand
- **State Management**: Efficient form state tracking
- **Validation Debouncing**: Prevents excessive validation calls
- **Memory Management**: Proper cleanup of event handlers
- **Responsive Caching**: Cached responsive calculations

## Error Handling

The module includes comprehensive error handling:

- **Validation Errors**: User-friendly validation messages
- **Component Errors**: Graceful fallbacks for component failures
- **Theme Errors**: Default styling when theme is unavailable
- **Event Errors**: Safe event handler execution

## Best Practices

1. **Use Validation Rules**: Always add appropriate validation rules
2. **Enable Auto-Validation**: For better user experience
3. **Group Related Fields**: Use form sections and field groups
4. **Provide Help Text**: Add tooltips and descriptions
5. **Test Responsiveness**: Verify layouts on different screen sizes
6. **Follow Accessibility Guidelines**: Use proper labels and ARIA attributes

## API Reference

See the module docstrings for detailed API documentation of all classes and methods.
