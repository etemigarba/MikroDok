"""
Module: hyperparameter_form_ui
Description: Comprehensive hyperparameter configuration form interface with validation, optimization suggestions,
            and real-time feedback. Provides intuitive form controls for all training hyperparameters including
            learning rate, batch size, epochs, optimizer settings, and advanced configuration options.
            Features responsive design, accessibility compliance, and full theme system integration.
Phase: 4
Location: /src/modules/ui/training_configuration_ui/hyperparameter_form_ui/hyperparameter_form_ui.py
"""

# Standard library imports
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime
import uuid

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)

# Training orchestration imports
try:
    from src.modules.logic.training_orchestration_lg.base_interfaces import (
        HyperparameterConfig,
        HyperparameterType,
        OptimizationStrategy,
        TrainingConfig
    )
    from src.modules.logic.training_orchestration_lg.hyperparameter_manager_lg.hyperparameter_manager_lg import (
        HyperparameterManager,
        HyperparameterValidator,
        HyperparameterOptimizer
    )
    TRAINING_ORCHESTRATION_AVAILABLE = True
except ImportError:
    HyperparameterConfig = None
    HyperparameterType = None
    OptimizationStrategy = None
    TrainingConfig = None
    HyperparameterManager = None
    HyperparameterValidator = None
    HyperparameterOptimizer = None
    TRAINING_ORCHESTRATION_AVAILABLE = False

# Logging infrastructure
try:
    from src.modules.logic.logging_infrastructure_lg import get_logger
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False


class HyperparameterFormMode(Enum):
    """Hyperparameter form display modes."""
    BASIC = "basic"
    ADVANCED = "advanced"
    EXPERT = "expert"
    OPTIMIZATION = "optimization"


class HyperparameterFieldType(Enum):
    """Types of hyperparameter form fields."""
    NUMERIC = "numeric"
    SLIDER = "slider"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    TEXT = "text"
    RANGE = "range"
    MULTI_SELECT = "multi_select"


class HyperparameterValidationState(Enum):
    """Validation states for hyperparameter fields."""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    PENDING = "pending"
    UNKNOWN = "unknown"


@dataclass
class ValidationMessage:
    """Validation message for hyperparameter fields."""
    field_name: str
    state: HyperparameterValidationState
    message: str
    severity: str = "info"  # info, warning, error
    suggestion: Optional[str] = None


@dataclass
class OptimizationSuggestion:
    """Optimization suggestion for hyperparameter values."""
    field_name: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float  # 0.0 to 1.0
    impact: str = "medium"  # low, medium, high


@dataclass
class HyperparameterField:
    """Configuration for a hyperparameter form field."""
    name: str
    label: str
    field_type: HyperparameterFieldType
    param_type: Optional[Any] = None  # HyperparameterType if available
    value: Any = None
    default_value: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Any]] = None
    description: Optional[str] = None
    tooltip: Optional[str] = None
    required: bool = True
    enabled: bool = True
    validation_state: HyperparameterValidationState = HyperparameterValidationState.UNKNOWN
    validation_message: Optional[str] = None
    optimization_suggestion: Optional[OptimizationSuggestion] = None


@dataclass
class FormValidationResult:
    """Result of form validation."""
    is_valid: bool
    field_validations: Dict[str, ValidationMessage]
    global_messages: List[ValidationMessage]
    suggestions: List[OptimizationSuggestion]
    estimated_training_time: Optional[str] = None
    resource_requirements: Optional[Dict[str, Any]] = None


@dataclass
class HyperparameterFormConfig:
    """Configuration for hyperparameter form."""
    mode: HyperparameterFormMode = HyperparameterFormMode.BASIC
    show_validation: bool = True
    show_suggestions: bool = True
    show_tooltips: bool = True
    enable_optimization: bool = True
    auto_validate: bool = True
    validation_delay_ms: int = 500
    show_advanced_fields: bool = False
    enable_presets: bool = True
    enable_export: bool = True
    enable_import: bool = True


class HyperparameterFormUI(ThemeAwareUserControl):
    """
    Comprehensive hyperparameter configuration form interface.
    
    Provides intuitive form controls for all training hyperparameters with
    real-time validation, optimization suggestions, and responsive design.
    
    Features:
    - Responsive form layout with breakpoint-aware field sizing
    - Real-time validation with visual feedback
    - Optimization suggestions based on model type and dataset
    - Preset configurations for common scenarios
    - Import/export functionality for hyperparameter sets
    - Accessibility-compliant form controls
    - Full theme system integration
    """
    
    def __init__(
        self,
        config: Optional[HyperparameterFormConfig] = None,
        initial_values: Optional[Dict[str, Any]] = None,
        on_value_change: Optional[Callable[[str, Any], None]] = None,
        on_validation_change: Optional[Callable[[FormValidationResult], None]] = None,
        on_submit: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self.config = config or HyperparameterFormConfig()
        self.initial_values = initial_values or {}
        
        # Callbacks
        self.on_value_change = on_value_change
        self.on_validation_change = on_validation_change
        self.on_submit = on_submit
        
        # State
        self.fields: Dict[str, HyperparameterField] = {}
        self.field_controls: Dict[str, ft.Control] = {}
        self.current_values: Dict[str, Any] = {}
        self.validation_result: Optional[FormValidationResult] = None
        self.validation_timer: Optional[asyncio.Task] = None
        
        # Components
        self.form_container: Optional[ft.Container] = None
        self.validation_panel: Optional[ft.Container] = None
        self.suggestion_panel: Optional[ft.Container] = None
        self.action_bar: Optional[ft.Container] = None
        
        # Managers
        self.hyperparameter_manager: Optional[Any] = None
        self.validator: Optional[Any] = None
        
        # Logger
        if LOGGING_AVAILABLE:
            self.logger = get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self._initialize_managers()
        self._setup_fields()
        self._load_initial_values()
    
    def _initialize_managers(self) -> None:
        """Initialize hyperparameter managers if available."""
        if TRAINING_ORCHESTRATION_AVAILABLE:
            try:
                self.hyperparameter_manager = HyperparameterManager()
                self.validator = HyperparameterValidator()
            except Exception as e:
                self.logger.warning(f"Could not initialize hyperparameter managers: {e}")
    
    def _setup_fields(self) -> None:
        """Setup hyperparameter form fields based on configuration mode."""
        # Basic hyperparameters (always shown)
        basic_fields = [
            HyperparameterField(
                name="learning_rate",
                label="Learning Rate",
                field_type=HyperparameterFieldType.NUMERIC,
                param_type=HyperparameterType.LEARNING_RATE if TRAINING_ORCHESTRATION_AVAILABLE else None,
                value=0.001,
                default_value=0.001,
                min_value=1e-8,
                max_value=1.0,
                step=1e-6,
                description="Controls how much to change the model in response to the estimated error",
                tooltip="Lower values make training more stable but slower. Higher values speed up training but may cause instability.",
                required=True
            ),
            HyperparameterField(
                name="batch_size",
                label="Batch Size",
                field_type=HyperparameterFieldType.DROPDOWN,
                param_type=HyperparameterType.BATCH_SIZE if TRAINING_ORCHESTRATION_AVAILABLE else None,
                value=32,
                default_value=32,
                choices=[8, 16, 32, 64, 128, 256, 512],
                description="Number of training examples processed together in one forward/backward pass",
                tooltip="Larger batch sizes use more memory but may improve training stability. Smaller batches use less memory but may be noisier.",
                required=True
            ),
            HyperparameterField(
                name="epochs",
                label="Epochs",
                field_type=HyperparameterFieldType.NUMERIC,
                param_type=HyperparameterType.EPOCHS if TRAINING_ORCHESTRATION_AVAILABLE else None,
                value=100,
                default_value=100,
                min_value=1,
                max_value=1000,
                step=1,
                description="Number of complete passes through the training dataset",
                tooltip="More epochs allow the model to learn more but may lead to overfitting. Monitor validation loss to determine optimal number.",
                required=True
            ),
            HyperparameterField(
                name="optimizer",
                label="Optimizer",
                field_type=HyperparameterFieldType.DROPDOWN,
                param_type=HyperparameterType.OPTIMIZER if TRAINING_ORCHESTRATION_AVAILABLE else None,
                value="adamw",
                default_value="adamw",
                choices=["adam", "adamw", "sgd", "rmsprop", "adagrad"],
                description="Algorithm used to update model weights during training",
                tooltip="AdamW is generally recommended for most tasks. SGD with momentum works well for computer vision. Adam is good for NLP tasks.",
                required=True
            )
        ]
        
        # Add basic fields
        for field in basic_fields:
            self.fields[field.name] = field

        # Advanced hyperparameters (shown in advanced/expert mode)
        if self.config.mode in [HyperparameterFormMode.ADVANCED, HyperparameterFormMode.EXPERT]:
            advanced_fields = [
                HyperparameterField(
                    name="weight_decay",
                    label="Weight Decay",
                    field_type=HyperparameterFieldType.NUMERIC,
                    param_type=HyperparameterType.REGULARIZATION if TRAINING_ORCHESTRATION_AVAILABLE else None,
                    value=0.01,
                    default_value=0.01,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.001,
                    description="L2 regularization strength to prevent overfitting",
                    tooltip="Higher values prevent overfitting but may underfitting. Start with 0.01 and adjust based on validation performance.",
                    required=False
                ),
                HyperparameterField(
                    name="scheduler",
                    label="Learning Rate Scheduler",
                    field_type=HyperparameterFieldType.DROPDOWN,
                    param_type=HyperparameterType.SCHEDULER if TRAINING_ORCHESTRATION_AVAILABLE else None,
                    value="cosine",
                    default_value="cosine",
                    choices=["none", "linear", "cosine", "exponential", "step"],
                    description="Strategy for adjusting learning rate during training",
                    tooltip="Cosine annealing works well for most tasks. Linear decay is simple and effective. Step decay reduces LR at fixed intervals.",
                    required=False
                ),
                HyperparameterField(
                    name="warmup_steps",
                    label="Warmup Steps",
                    field_type=HyperparameterFieldType.NUMERIC,
                    value=1000,
                    default_value=1000,
                    min_value=0,
                    max_value=10000,
                    step=100,
                    description="Number of steps to gradually increase learning rate from 0",
                    tooltip="Warmup helps stabilize training in the beginning. Use 10% of total training steps as a starting point.",
                    required=False
                ),
                HyperparameterField(
                    name="gradient_clip_norm",
                    label="Gradient Clipping",
                    field_type=HyperparameterFieldType.NUMERIC,
                    value=1.0,
                    default_value=1.0,
                    min_value=0.1,
                    max_value=10.0,
                    step=0.1,
                    description="Maximum norm for gradient clipping to prevent exploding gradients",
                    tooltip="Prevents gradient explosion. 1.0 is a good default. Increase if gradients are too small, decrease if training is unstable.",
                    required=False
                )
            ]

            for field in advanced_fields:
                self.fields[field.name] = field

        # Expert hyperparameters (shown only in expert mode)
        if self.config.mode == HyperparameterFormMode.EXPERT:
            expert_fields = [
                HyperparameterField(
                    name="beta1",
                    label="Adam Beta1",
                    field_type=HyperparameterFieldType.NUMERIC,
                    value=0.9,
                    default_value=0.9,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.01,
                    description="Exponential decay rate for first moment estimates in Adam optimizer",
                    tooltip="Controls momentum in Adam. 0.9 is the standard value. Lower values reduce momentum.",
                    required=False
                ),
                HyperparameterField(
                    name="beta2",
                    label="Adam Beta2",
                    field_type=HyperparameterFieldType.NUMERIC,
                    value=0.999,
                    default_value=0.999,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.001,
                    description="Exponential decay rate for second moment estimates in Adam optimizer",
                    tooltip="Controls adaptive learning rate in Adam. 0.999 is the standard value. Lower values make adaptation faster.",
                    required=False
                ),
                HyperparameterField(
                    name="epsilon",
                    label="Adam Epsilon",
                    field_type=HyperparameterFieldType.NUMERIC,
                    value=1e-8,
                    default_value=1e-8,
                    min_value=1e-12,
                    max_value=1e-4,
                    step=1e-9,
                    description="Small constant for numerical stability in Adam optimizer",
                    tooltip="Prevents division by zero. 1e-8 is the standard value. Rarely needs adjustment.",
                    required=False
                ),
                HyperparameterField(
                    name="label_smoothing",
                    label="Label Smoothing",
                    field_type=HyperparameterFieldType.NUMERIC,
                    value=0.0,
                    default_value=0.0,
                    min_value=0.0,
                    max_value=0.5,
                    step=0.01,
                    description="Amount of label smoothing to apply for regularization",
                    tooltip="Prevents overconfident predictions. 0.1 is a common value for classification tasks. 0.0 disables smoothing.",
                    required=False
                )
            ]

            for field in expert_fields:
                self.fields[field.name] = field

    def _load_initial_values(self) -> None:
        """Load initial values into form fields."""
        for field_name, value in self.initial_values.items():
            if field_name in self.fields:
                self.fields[field_name].value = value
                self.current_values[field_name] = value

        # Set default values for fields without initial values
        for field_name, field in self.fields.items():
            if field_name not in self.current_values:
                self.current_values[field_name] = field.value or field.default_value

    def build(self) -> ft.Control:
        """Build the hyperparameter form interface."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Get responsive layout manager
        self._ensure_responsive_manager()

        # Create form sections
        form_sections = []

        # Header section with mode selector
        header_section = self._create_header_section()
        if header_section:
            form_sections.append(header_section)

        # Basic parameters section
        basic_section = self._create_basic_parameters_section()
        if basic_section:
            form_sections.append(basic_section)

        # Advanced parameters section (if enabled)
        if self.config.mode in [HyperparameterFormMode.ADVANCED, HyperparameterFormMode.EXPERT]:
            advanced_section = self._create_advanced_parameters_section()
            if advanced_section:
                form_sections.append(advanced_section)

        # Expert parameters section (if enabled)
        if self.config.mode == HyperparameterFormMode.EXPERT:
            expert_section = self._create_expert_parameters_section()
            if expert_section:
                form_sections.append(expert_section)

        # Validation panel (if enabled)
        if self.config.show_validation:
            validation_section = self._create_validation_section()
            if validation_section:
                form_sections.append(validation_section)

        # Suggestion panel (if enabled)
        if self.config.show_suggestions:
            suggestion_section = self._create_suggestion_section()
            if suggestion_section:
                form_sections.append(suggestion_section)

        # Action bar
        action_section = self._create_action_section()
        if action_section:
            form_sections.append(action_section)

        # Create main form container
        self.form_container = ft.Container(
            content=ft.Column(
                controls=form_sections,
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO,
                expand=True
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline),
            expand=True
        )

        return self.form_container

    def _create_header_section(self) -> Optional[ft.Container]:
        """Create header section with title and mode selector."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Title
        title = ft.Text(
            "Hyperparameter Configuration",
            style=self.get_text_style("heading_large"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_600
        )

        # Mode selector
        mode_options = [
            ft.dropdown.Option(key="basic", text="Basic"),
            ft.dropdown.Option(key="advanced", text="Advanced"),
            ft.dropdown.Option(key="expert", text="Expert"),
            ft.dropdown.Option(key="optimization", text="Optimization")
        ]

        mode_selector = ft.Dropdown(
            label="Configuration Mode",
            value=self.config.mode.value,
            options=mode_options,
            on_change=self._on_mode_change,
            width=200,
            bgcolor=palette.surface_variant,
            border_color=palette.outline,
            text_style=self.get_text_style("body_medium"),
            label_style=self.get_text_style("label_medium")
        )

        # Description
        mode_descriptions = {
            HyperparameterFormMode.BASIC: "Essential hyperparameters for most training scenarios",
            HyperparameterFormMode.ADVANCED: "Additional parameters for fine-tuning performance",
            HyperparameterFormMode.EXPERT: "All available parameters for maximum control",
            HyperparameterFormMode.OPTIMIZATION: "Automated hyperparameter optimization settings"
        }

        description = ft.Text(
            mode_descriptions.get(self.config.mode, ""),
            style=self.get_text_style("body_small"),
            color=palette.text_secondary,
            italic=True
        )

        # Header row
        header_row = ft.Row(
            controls=[
                ft.Column(
                    controls=[title, description],
                    spacing=spacing.xs,
                    expand=True
                ),
                mode_selector
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.START
        )

        return ft.Container(
            content=header_row,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline)
        )

    def _create_basic_parameters_section(self) -> Optional[ft.Container]:
        """Create basic parameters section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Filter basic fields
        basic_fields = [
            field for field in self.fields.values()
            if field.name in ["learning_rate", "batch_size", "epochs", "optimizer"]
        ]

        if not basic_fields:
            return None

        # Section title
        section_title = ft.Text(
            "Basic Parameters",
            style=self.get_text_style("heading_medium"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        # Create field controls
        field_controls = []
        for field in basic_fields:
            field_control = self._create_field_control(field)
            if field_control:
                field_controls.append(field_control)

        # Responsive grid layout
        if self._responsive_manager:
            current_screen_size = self._responsive_manager.get_current_screen_size()
            columns = 2 if current_screen_size.name in ["DESKTOP", "LARGE_DESKTOP"] else 1
        else:
            columns = 2

        # Create grid
        grid_rows = []
        for i in range(0, len(field_controls), columns):
            row_controls = field_controls[i:i + columns]
            # Pad row if needed
            while len(row_controls) < columns:
                row_controls.append(ft.Container())

            grid_row = ft.Row(
                controls=row_controls,
                spacing=spacing.md,
                alignment=ft.MainAxisAlignment.START
            )
            grid_rows.append(grid_row)

        content = ft.Column(
            controls=[section_title] + grid_rows,
            spacing=spacing.md
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline)
        )

    def _create_advanced_parameters_section(self) -> Optional[ft.Container]:
        """Create advanced parameters section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Filter advanced fields
        advanced_fields = [
            field for field in self.fields.values()
            if field.name in ["weight_decay", "scheduler", "warmup_steps", "gradient_clip_norm"]
        ]

        if not advanced_fields:
            return None

        # Section title
        section_title = ft.Text(
            "Advanced Parameters",
            style=self.get_text_style("heading_medium"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        # Create field controls
        field_controls = []
        for field in advanced_fields:
            field_control = self._create_field_control(field)
            if field_control:
                field_controls.append(field_control)

        # Responsive grid layout
        if self._responsive_manager:
            current_screen_size = self._responsive_manager.get_current_screen_size()
            columns = 2 if current_screen_size.name in ["DESKTOP", "LARGE_DESKTOP"] else 1
        else:
            columns = 2

        # Create grid
        grid_rows = []
        for i in range(0, len(field_controls), columns):
            row_controls = field_controls[i:i + columns]
            # Pad row if needed
            while len(row_controls) < columns:
                row_controls.append(ft.Container())

            grid_row = ft.Row(
                controls=row_controls,
                spacing=spacing.md,
                alignment=ft.MainAxisAlignment.START
            )
            grid_rows.append(grid_row)

        content = ft.Column(
            controls=[section_title] + grid_rows,
            spacing=spacing.md
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline)
        )

    def _create_expert_parameters_section(self) -> Optional[ft.Container]:
        """Create expert parameters section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Filter expert fields
        expert_fields = [
            field for field in self.fields.values()
            if field.name in ["beta1", "beta2", "epsilon", "label_smoothing"]
        ]

        if not expert_fields:
            return None

        # Section title
        section_title = ft.Text(
            "Expert Parameters",
            style=self.get_text_style("heading_medium"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        # Warning message
        warning_message = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        name=self.get_icon("WARNING"),
                        color=palette.warning,
                        size=16
                    ),
                    ft.Text(
                        "Expert parameters require deep understanding of optimization algorithms. Modify with caution.",
                        style=self.get_text_style("body_small"),
                        color=palette.warning,
                        expand=True
                    )
                ],
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.START
            ),
            padding=ft.padding.all(spacing.sm),
            bgcolor=f"{palette.warning}20",  # 20% opacity
            border_radius=spacing.xs,
            border=ft.border.all(1, palette.warning)
        )

        # Create field controls
        field_controls = []
        for field in expert_fields:
            field_control = self._create_field_control(field)
            if field_control:
                field_controls.append(field_control)

        # Responsive grid layout
        if self._responsive_manager:
            current_screen_size = self._responsive_manager.get_current_screen_size()
            columns = 2 if current_screen_size.name in ["DESKTOP", "LARGE_DESKTOP"] else 1
        else:
            columns = 2

        # Create grid
        grid_rows = []
        for i in range(0, len(field_controls), columns):
            row_controls = field_controls[i:i + columns]
            # Pad row if needed
            while len(row_controls) < columns:
                row_controls.append(ft.Container())

            grid_row = ft.Row(
                controls=row_controls,
                spacing=spacing.md,
                alignment=ft.MainAxisAlignment.START
            )
            grid_rows.append(grid_row)

        content = ft.Column(
            controls=[section_title, warning_message] + grid_rows,
            spacing=spacing.md
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline)
        )

    def _create_validation_section(self) -> Optional[ft.Container]:
        """Create validation feedback section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Section title
        section_title = ft.Text(
            "Validation Status",
            style=self.get_text_style("heading_medium"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        # Validation messages container
        validation_messages = ft.Column(
            controls=[
                ft.Text(
                    "Validation will appear here as you modify parameters",
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary,
                    italic=True
                )
            ],
            spacing=spacing.xs
        )

        self.validation_panel = ft.Container(
            content=validation_messages,
            padding=ft.padding.all(spacing.sm),
            bgcolor=palette.surface_variant,
            border_radius=spacing.xs,
            min_height=100
        )

        content = ft.Column(
            controls=[section_title, self.validation_panel],
            spacing=spacing.sm
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline)
        )

    def _create_suggestion_section(self) -> Optional[ft.Container]:
        """Create optimization suggestions section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Section title
        section_title = ft.Text(
            "Optimization Suggestions",
            style=self.get_text_style("heading_medium"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        # Suggestions container
        suggestions_content = ft.Column(
            controls=[
                ft.Text(
                    "Optimization suggestions will appear here based on your configuration",
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary,
                    italic=True
                )
            ],
            spacing=spacing.xs
        )

        self.suggestion_panel = ft.Container(
            content=suggestions_content,
            padding=ft.padding.all(spacing.sm),
            bgcolor=palette.surface_variant,
            border_radius=spacing.xs,
            min_height=100
        )

        content = ft.Column(
            controls=[section_title, self.suggestion_panel],
            spacing=spacing.sm
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline)
        )

    def _create_action_section(self) -> Optional[ft.Container]:
        """Create action buttons section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Action buttons
        buttons = []

        # Reset button
        reset_button = ft.ElevatedButton(
            text="Reset to Defaults",
            icon=self.get_icon("REFRESH"),
            on_click=self._on_reset_click,
            style=ft.ButtonStyle(
                bgcolor=palette.surface_variant,
                color=palette.text_primary,
                elevation=2
            )
        )
        buttons.append(reset_button)

        # Load preset button
        if self.config.enable_presets:
            preset_button = ft.ElevatedButton(
                text="Load Preset",
                icon=self.get_icon("DOWNLOAD"),
                on_click=self._on_load_preset_click,
                style=ft.ButtonStyle(
                    bgcolor=palette.surface_variant,
                    color=palette.text_primary,
                    elevation=2
                )
            )
            buttons.append(preset_button)

        # Export button
        if self.config.enable_export:
            export_button = ft.ElevatedButton(
                text="Export Config",
                icon=self.get_icon("UPLOAD"),
                on_click=self._on_export_click,
                style=ft.ButtonStyle(
                    bgcolor=palette.surface_variant,
                    color=palette.text_primary,
                    elevation=2
                )
            )
            buttons.append(export_button)

        # Validate button
        validate_button = ft.ElevatedButton(
            text="Validate Configuration",
            icon=self.get_icon("CHECK"),
            on_click=self._on_validate_click,
            style=ft.ButtonStyle(
                bgcolor=palette.primary,
                color=palette.background_primary,
                elevation=4
            )
        )
        buttons.append(validate_button)

        # Apply button
        apply_button = ft.ElevatedButton(
            text="Apply Configuration",
            icon=self.get_icon("SAVE"),
            on_click=self._on_apply_click,
            style=ft.ButtonStyle(
                bgcolor=palette.success,
                color=palette.background_primary,
                elevation=4
            )
        )
        buttons.append(apply_button)

        # Button row
        button_row = ft.Row(
            controls=buttons,
            spacing=spacing.md,
            alignment=ft.MainAxisAlignment.END,
            wrap=True
        )

        self.action_bar = ft.Container(
            content=button_row,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline)
        )

        return self.action_bar

    def _create_field_control(self, field: HyperparameterField) -> Optional[ft.Container]:
        """Create a form control for a hyperparameter field."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        if not field.enabled:
            return None

        # Create field control based on type
        field_control = None

        if field.field_type == HyperparameterFieldType.NUMERIC:
            field_control = ft.TextField(
                label=field.label,
                value=str(field.value) if field.value is not None else "",
                hint_text=field.description,
                on_change=lambda e, name=field.name: self._on_field_change(name, e.control.value),
                keyboard_type=ft.KeyboardType.NUMBER,
                bgcolor=palette.surface_variant,
                border_color=palette.outline,
                text_style=self.get_text_style("body_medium"),
                label_style=self.get_text_style("label_medium"),
                expand=True
            )

        elif field.field_type == HyperparameterFieldType.DROPDOWN:
            options = []
            if field.choices:
                for choice in field.choices:
                    options.append(ft.dropdown.Option(key=str(choice), text=str(choice)))

            field_control = ft.Dropdown(
                label=field.label,
                value=str(field.value) if field.value is not None else None,
                options=options,
                on_change=lambda e, name=field.name: self._on_field_change(name, e.control.value),
                bgcolor=palette.surface_variant,
                border_color=palette.outline,
                text_style=self.get_text_style("body_medium"),
                label_style=self.get_text_style("label_medium"),
                expand=True
            )

        elif field.field_type == HyperparameterFieldType.SLIDER:
            field_control = ft.Slider(
                min=field.min_value or 0,
                max=field.max_value or 100,
                value=float(field.value) if field.value is not None else 0,
                divisions=100,
                label=f"{field.value}",
                on_change=lambda e, name=field.name: self._on_field_change(name, e.control.value),
                active_color=palette.primary,
                inactive_color=palette.outline,
                expand=True
            )

        elif field.field_type == HyperparameterFieldType.CHECKBOX:
            field_control = ft.Checkbox(
                label=field.label,
                value=bool(field.value) if field.value is not None else False,
                on_change=lambda e, name=field.name: self._on_field_change(name, e.control.value),
                active_color=palette.primary,
                check_color=palette.background_primary
            )

        if field_control is None:
            return None

        # Store field control reference
        self.field_controls[field.name] = field_control

        # Create field container with validation indicator
        field_container_controls = []

        # Add label for non-checkbox fields
        if field.field_type != HyperparameterFieldType.CHECKBOX:
            label_row = ft.Row(
                controls=[
                    ft.Text(
                        field.label,
                        style=self.get_text_style("label_medium"),
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        "*" if field.required else "",
                        style=self.get_text_style("label_small"),
                        color=palette.error
                    )
                ],
                spacing=spacing.xs
            )
            field_container_controls.append(label_row)

        # Add field control
        field_container_controls.append(field_control)

        # Add description if available
        if field.description and field.field_type != HyperparameterFieldType.CHECKBOX:
            description_text = ft.Text(
                field.description,
                style=self.get_text_style("body_small"),
                color=palette.text_secondary,
                size=12
            )
            field_container_controls.append(description_text)

        # Add validation message if available
        if field.validation_message:
            validation_color = {
                HyperparameterValidationState.VALID: palette.success,
                HyperparameterValidationState.INVALID: palette.error,
                HyperparameterValidationState.WARNING: palette.warning,
                HyperparameterValidationState.PENDING: palette.info
            }.get(field.validation_state, palette.text_secondary)

            validation_icon = {
                HyperparameterValidationState.VALID: self.get_icon("CHECK"),
                HyperparameterValidationState.INVALID: self.get_icon("ERROR"),
                HyperparameterValidationState.WARNING: self.get_icon("WARNING"),
                HyperparameterValidationState.PENDING: self.get_icon("PENDING")
            }.get(field.validation_state, self.get_icon("INFO"))

            validation_row = ft.Row(
                controls=[
                    ft.Icon(
                        name=validation_icon,
                        color=validation_color,
                        size=14
                    ),
                    ft.Text(
                        field.validation_message,
                        style=self.get_text_style("body_small"),
                        color=validation_color,
                        size=11,
                        expand=True
                    )
                ],
                spacing=spacing.xs
            )
            field_container_controls.append(validation_row)

        # Create field container
        field_container = ft.Container(
            content=ft.Column(
                controls=field_container_controls,
                spacing=spacing.xs,
                tight=True
            ),
            padding=ft.padding.all(spacing.sm),
            bgcolor=palette.surface,
            border_radius=spacing.xs,
            border=ft.border.all(1, palette.outline),
            expand=True
        )

        return field_container

    # Event Handlers

    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        """Handle mode change event."""
        try:
            new_mode = HyperparameterFormMode(e.control.value)
            if new_mode != self.config.mode:
                self.config.mode = new_mode
                self._setup_fields()  # Rebuild fields for new mode
                self.content = self.build()  # Rebuild UI
                self.update()

                self.logger.info(f"Hyperparameter form mode changed to: {new_mode.value}")
        except Exception as ex:
            self.logger.error(f"Error changing hyperparameter form mode: {ex}")

    def _on_field_change(self, field_name: str, value: Any) -> None:
        """Handle field value change event."""
        try:
            # Convert value to appropriate type
            if field_name in self.fields:
                field = self.fields[field_name]

                # Type conversion
                if field.field_type == HyperparameterFieldType.NUMERIC:
                    try:
                        if field.step and field.step < 1:
                            value = float(value) if value else 0.0
                        else:
                            value = int(float(value)) if value else 0
                    except (ValueError, TypeError):
                        value = field.default_value

                elif field.field_type == HyperparameterFieldType.DROPDOWN:
                    # Try to convert back to original type if it was numeric
                    if field.choices and len(field.choices) > 0:
                        first_choice = field.choices[0]
                        if isinstance(first_choice, (int, float)):
                            try:
                                value = type(first_choice)(value)
                            except (ValueError, TypeError):
                                value = first_choice

                # Update current values
                self.current_values[field_name] = value
                field.value = value

                # Trigger validation if auto-validate is enabled
                if self.config.auto_validate:
                    self._schedule_validation()

                # Call callback if provided
                if self.on_value_change:
                    self.on_value_change(field_name, value)

                self.logger.debug(f"Field {field_name} changed to: {value}")

        except Exception as ex:
            self.logger.error(f"Error handling field change for {field_name}: {ex}")

    def _on_reset_click(self, e: ft.ControlEvent) -> None:
        """Handle reset button click."""
        try:
            # Reset all fields to default values
            for field_name, field in self.fields.items():
                field.value = field.default_value
                self.current_values[field_name] = field.default_value

                # Update field control if it exists
                if field_name in self.field_controls:
                    control = self.field_controls[field_name]
                    if hasattr(control, 'value'):
                        control.value = str(field.default_value) if field.default_value is not None else ""

            # Rebuild form
            self.content = self.build()
            self.update()

            self.logger.info("Hyperparameter form reset to default values")

        except Exception as ex:
            self.logger.error(f"Error resetting hyperparameter form: {ex}")

    def _on_load_preset_click(self, e: ft.ControlEvent) -> None:
        """Handle load preset button click."""
        try:
            # This would typically open a dialog to select presets
            # For now, we'll just log the action
            self.logger.info("Load preset clicked - preset selection dialog would open here")

        except Exception as ex:
            self.logger.error(f"Error loading preset: {ex}")

    def _on_export_click(self, e: ft.ControlEvent) -> None:
        """Handle export button click."""
        try:
            # Export current configuration
            config_data = {
                "hyperparameters": self.current_values,
                "mode": self.config.mode.value,
                "timestamp": str(datetime.now()),
                "version": "1.0"
            }

            # This would typically open a save dialog
            # For now, we'll just log the configuration
            self.logger.info(f"Export configuration: {json.dumps(config_data, indent=2)}")

        except Exception as ex:
            self.logger.error(f"Error exporting configuration: {ex}")

    def _on_validate_click(self, e: ft.ControlEvent) -> None:
        """Handle validate button click."""
        try:
            self._perform_validation()
        except Exception as ex:
            self.logger.error(f"Error validating configuration: {ex}")

    def _on_apply_click(self, e: ft.ControlEvent) -> None:
        """Handle apply button click."""
        try:
            # Validate first
            validation_result = self._perform_validation()

            if validation_result and validation_result.is_valid:
                # Call submit callback if provided
                if self.on_submit:
                    self.on_submit(self.current_values.copy())

                self.logger.info("Hyperparameter configuration applied successfully")
            else:
                self.logger.warning("Cannot apply configuration - validation failed")

        except Exception as ex:
            self.logger.error(f"Error applying configuration: {ex}")

    # Validation Methods

    def _schedule_validation(self) -> None:
        """Schedule validation with delay to avoid excessive validation calls."""
        try:
            # Cancel existing validation timer
            if self.validation_timer and not self.validation_timer.done():
                self.validation_timer.cancel()

            # Schedule new validation
            async def delayed_validation():
                await asyncio.sleep(self.config.validation_delay_ms / 1000.0)
                self._perform_validation()

            self.validation_timer = asyncio.create_task(delayed_validation())

        except Exception as ex:
            self.logger.error(f"Error scheduling validation: {ex}")

    def _perform_validation(self) -> Optional[FormValidationResult]:
        """Perform comprehensive validation of all hyperparameters."""
        try:
            field_validations = {}
            global_messages = []
            suggestions = []

            # Validate individual fields
            for field_name, field in self.fields.items():
                validation = self._validate_field(field)
                if validation:
                    field_validations[field_name] = validation
                    field.validation_state = validation.state
                    field.validation_message = validation.message

            # Perform global validation
            global_validations = self._validate_global_constraints()
            global_messages.extend(global_validations)

            # Generate optimization suggestions
            if self.config.show_suggestions:
                optimization_suggestions = self._generate_suggestions()
                suggestions.extend(optimization_suggestions)

            # Determine overall validity
            is_valid = all(
                v.state in [HyperparameterValidationState.VALID, HyperparameterValidationState.WARNING]
                for v in field_validations.values()
            ) and not any(
                m.severity == "error" for m in global_messages
            )

            # Create validation result
            self.validation_result = FormValidationResult(
                is_valid=is_valid,
                field_validations=field_validations,
                global_messages=global_messages,
                suggestions=suggestions,
                estimated_training_time=self._estimate_training_time(),
                resource_requirements=self._estimate_resource_requirements()
            )

            # Update validation UI
            self._update_validation_ui()

            # Call validation callback if provided
            if self.on_validation_change:
                self.on_validation_change(self.validation_result)

            return self.validation_result

        except Exception as ex:
            self.logger.error(f"Error performing validation: {ex}")
            return None

    def _validate_field(self, field: HyperparameterField) -> Optional[ValidationMessage]:
        """Validate a single hyperparameter field."""
        try:
            value = field.value

            # Check required fields
            if field.required and (value is None or value == ""):
                return ValidationMessage(
                    field_name=field.name,
                    state=HyperparameterValidationState.INVALID,
                    message="This field is required",
                    severity="error"
                )

            # Skip validation if field is empty and not required
            if value is None or value == "":
                return None

            # Numeric validation
            if field.field_type == HyperparameterFieldType.NUMERIC:
                try:
                    numeric_value = float(value)

                    # Range validation
                    if field.min_value is not None and numeric_value < field.min_value:
                        return ValidationMessage(
                            field_name=field.name,
                            state=HyperparameterValidationState.INVALID,
                            message=f"Value must be at least {field.min_value}",
                            severity="error",
                            suggestion=f"Consider using {field.min_value} or higher"
                        )

                    if field.max_value is not None and numeric_value > field.max_value:
                        return ValidationMessage(
                            field_name=field.name,
                            state=HyperparameterValidationState.INVALID,
                            message=f"Value must be at most {field.max_value}",
                            severity="error",
                            suggestion=f"Consider using {field.max_value} or lower"
                        )

                    # Special validation for specific parameters
                    if field.name == "learning_rate":
                        if numeric_value > 0.1:
                            return ValidationMessage(
                                field_name=field.name,
                                state=HyperparameterValidationState.WARNING,
                                message="Learning rate is quite high - may cause training instability",
                                severity="warning",
                                suggestion="Consider using a value between 1e-5 and 1e-2"
                            )
                        elif numeric_value < 1e-6:
                            return ValidationMessage(
                                field_name=field.name,
                                state=HyperparameterValidationState.WARNING,
                                message="Learning rate is very low - training may be slow",
                                severity="warning",
                                suggestion="Consider using a value between 1e-5 and 1e-2"
                            )

                    elif field.name == "batch_size":
                        # Check if batch size is power of 2
                        if numeric_value > 0 and (numeric_value & (numeric_value - 1)) != 0:
                            return ValidationMessage(
                                field_name=field.name,
                                state=HyperparameterValidationState.WARNING,
                                message="Batch size is not a power of 2 - may be less efficient",
                                severity="warning",
                                suggestion="Consider using 32, 64, 128, or 256"
                            )

                except (ValueError, TypeError):
                    return ValidationMessage(
                        field_name=field.name,
                        state=HyperparameterValidationState.INVALID,
                        message="Invalid numeric value",
                        severity="error"
                    )

            # Dropdown validation
            elif field.field_type == HyperparameterFieldType.DROPDOWN:
                if field.choices and value not in [str(choice) for choice in field.choices]:
                    return ValidationMessage(
                        field_name=field.name,
                        state=HyperparameterValidationState.INVALID,
                        message="Invalid selection",
                        severity="error"
                    )

            # Use external validator if available
            if self.validator and TRAINING_ORCHESTRATION_AVAILABLE:
                try:
                    # Create HyperparameterConfig for validation
                    param_config = HyperparameterConfig(
                        name=field.name,
                        value=value,
                        param_type=field.param_type or HyperparameterType.CUSTOM,
                        min_value=field.min_value,
                        max_value=field.max_value,
                        description=field.description
                    )

                    validation_result = self.validator.validate_parameter(param_config)

                    if not validation_result.is_valid:
                        return ValidationMessage(
                            field_name=field.name,
                            state=HyperparameterValidationState.INVALID,
                            message=validation_result.message,
                            severity="error",
                            suggestion=validation_result.suggestion
                        )

                except Exception as e:
                    self.logger.warning(f"External validation failed for {field.name}: {e}")

            # If we get here, validation passed
            return ValidationMessage(
                field_name=field.name,
                state=HyperparameterValidationState.VALID,
                message="Valid",
                severity="info"
            )

        except Exception as ex:
            self.logger.error(f"Error validating field {field.name}: {ex}")
            return ValidationMessage(
                field_name=field.name,
                state=HyperparameterValidationState.INVALID,
                message="Validation error",
                severity="error"
            )

    def _validate_global_constraints(self) -> List[ValidationMessage]:
        """Validate global constraints across multiple parameters."""
        messages = []

        try:
            # Check learning rate vs batch size relationship
            lr = self.current_values.get("learning_rate")
            batch_size = self.current_values.get("batch_size")

            if lr and batch_size:
                try:
                    lr_val = float(lr)
                    batch_val = int(batch_size)

                    # Large batch size with high learning rate warning
                    if batch_val >= 128 and lr_val >= 0.01:
                        messages.append(ValidationMessage(
                            field_name="global",
                            state=HyperparameterValidationState.WARNING,
                            message="Large batch size with high learning rate may cause training instability",
                            severity="warning",
                            suggestion="Consider reducing learning rate when using large batch sizes"
                        ))

                    # Small batch size with very low learning rate warning
                    elif batch_val <= 16 and lr_val <= 1e-5:
                        messages.append(ValidationMessage(
                            field_name="global",
                            state=HyperparameterValidationState.WARNING,
                            message="Small batch size with very low learning rate may slow training significantly",
                            severity="warning",
                            suggestion="Consider increasing learning rate for small batch sizes"
                        ))

                except (ValueError, TypeError):
                    pass

            # Check epochs vs early stopping
            epochs = self.current_values.get("epochs")
            if epochs:
                try:
                    epoch_val = int(epochs)
                    if epoch_val > 500:
                        messages.append(ValidationMessage(
                            field_name="global",
                            state=HyperparameterValidationState.WARNING,
                            message="Very high epoch count - consider using early stopping",
                            severity="warning",
                            suggestion="Monitor validation loss and use early stopping to prevent overfitting"
                        ))
                except (ValueError, TypeError):
                    pass

        except Exception as ex:
            self.logger.error(f"Error validating global constraints: {ex}")

        return messages

    def _generate_suggestions(self) -> List[OptimizationSuggestion]:
        """Generate optimization suggestions based on current configuration."""
        suggestions = []

        try:
            # Learning rate suggestions
            lr = self.current_values.get("learning_rate")
            optimizer = self.current_values.get("optimizer")

            if lr and optimizer:
                try:
                    lr_val = float(lr)

                    # Optimizer-specific learning rate suggestions
                    if optimizer == "sgd" and lr_val < 0.01:
                        suggestions.append(OptimizationSuggestion(
                            field_name="learning_rate",
                            current_value=lr_val,
                            suggested_value=0.01,
                            reason="SGD typically works better with higher learning rates",
                            confidence=0.7,
                            impact="medium"
                        ))

                    elif optimizer in ["adam", "adamw"] and lr_val > 0.001:
                        suggestions.append(OptimizationSuggestion(
                            field_name="learning_rate",
                            current_value=lr_val,
                            suggested_value=0.001,
                            reason="Adam-based optimizers typically work well with lower learning rates",
                            confidence=0.8,
                            impact="medium"
                        ))

                except (ValueError, TypeError):
                    pass

            # Batch size suggestions based on available memory
            batch_size = self.current_values.get("batch_size")
            if batch_size:
                try:
                    batch_val = int(batch_size)

                    # Suggest power of 2 if not already
                    if batch_val > 0 and (batch_val & (batch_val - 1)) != 0:
                        # Find nearest power of 2
                        import math
                        lower_power = 2 ** int(math.log2(batch_val))
                        upper_power = lower_power * 2

                        suggested_batch = lower_power if abs(batch_val - lower_power) < abs(batch_val - upper_power) else upper_power

                        suggestions.append(OptimizationSuggestion(
                            field_name="batch_size",
                            current_value=batch_val,
                            suggested_value=suggested_batch,
                            reason="Power of 2 batch sizes are more efficient on most hardware",
                            confidence=0.9,
                            impact="low"
                        ))

                except (ValueError, TypeError):
                    pass

        except Exception as ex:
            self.logger.error(f"Error generating suggestions: {ex}")

        return suggestions

    def _estimate_training_time(self) -> Optional[str]:
        """Estimate training time based on current configuration."""
        try:
            epochs = self.current_values.get("epochs")
            batch_size = self.current_values.get("batch_size")

            if epochs and batch_size:
                epoch_val = int(epochs)
                batch_val = int(batch_size)

                # Very rough estimation (would need actual dataset size and hardware info)
                # Assuming 10,000 samples and 1 second per batch on average
                estimated_samples = 10000
                batches_per_epoch = max(1, estimated_samples // batch_val)
                total_batches = epoch_val * batches_per_epoch
                estimated_seconds = total_batches * 1  # 1 second per batch assumption

                # Convert to human readable format
                if estimated_seconds < 60:
                    return f"~{estimated_seconds:.0f} seconds"
                elif estimated_seconds < 3600:
                    return f"~{estimated_seconds/60:.1f} minutes"
                else:
                    return f"~{estimated_seconds/3600:.1f} hours"

        except (ValueError, TypeError, Exception):
            pass

        return "Unable to estimate"

    def _estimate_resource_requirements(self) -> Optional[Dict[str, Any]]:
        """Estimate resource requirements based on current configuration."""
        try:
            batch_size = self.current_values.get("batch_size")

            if batch_size:
                batch_val = int(batch_size)

                # Very rough estimation
                estimated_memory_gb = batch_val * 0.1  # 100MB per sample assumption
                estimated_gpu_memory_gb = batch_val * 0.05  # 50MB GPU memory per sample

                return {
                    "estimated_ram_gb": round(estimated_memory_gb, 1),
                    "estimated_gpu_memory_gb": round(estimated_gpu_memory_gb, 1),
                    "recommended_cpu_cores": min(16, max(4, batch_val // 8)),
                    "disk_space_gb": "Depends on model size and checkpoints"
                }

        except (ValueError, TypeError, Exception):
            pass

        return None

    def _update_validation_ui(self) -> None:
        """Update validation UI with current validation results."""
        try:
            if not self.validation_panel or not self.validation_result:
                return

            palette = self.get_palette()
            spacing = self.get_spacing()

            validation_controls = []

            # Overall status
            overall_status = "Valid" if self.validation_result.is_valid else "Invalid"
            status_color = palette.success if self.validation_result.is_valid else palette.error
            status_icon = self.get_icon("CHECK") if self.validation_result.is_valid else self.get_icon("ERROR")

            status_row = ft.Row(
                controls=[
                    ft.Icon(name=status_icon, color=status_color, size=16),
                    ft.Text(
                        f"Configuration Status: {overall_status}",
                        style=self.get_text_style("body_medium"),
                        color=status_color,
                        weight=ft.FontWeight.W_500
                    )
                ],
                spacing=spacing.xs
            )
            validation_controls.append(status_row)

            # Field validations
            if self.validation_result.field_validations:
                for field_name, validation in self.validation_result.field_validations.items():
                    if validation.state != HyperparameterValidationState.VALID:
                        validation_color = {
                            HyperparameterValidationState.INVALID: palette.error,
                            HyperparameterValidationState.WARNING: palette.warning,
                            HyperparameterValidationState.PENDING: palette.info
                        }.get(validation.state, palette.text_secondary)

                        validation_icon = {
                            HyperparameterValidationState.INVALID: self.get_icon("ERROR"),
                            HyperparameterValidationState.WARNING: self.get_icon("WARNING"),
                            HyperparameterValidationState.PENDING: self.get_icon("PENDING")
                        }.get(validation.state, self.get_icon("INFO"))

                        field_row = ft.Row(
                            controls=[
                                ft.Icon(name=validation_icon, color=validation_color, size=14),
                                ft.Text(
                                    f"{field_name}: {validation.message}",
                                    style=self.get_text_style("body_small"),
                                    color=validation_color,
                                    expand=True
                                )
                            ],
                            spacing=spacing.xs
                        )
                        validation_controls.append(field_row)

            # Global messages
            for message in self.validation_result.global_messages:
                message_color = {
                    "error": palette.error,
                    "warning": palette.warning,
                    "info": palette.info
                }.get(message.severity, palette.text_secondary)

                message_icon = {
                    "error": self.get_icon("ERROR"),
                    "warning": self.get_icon("WARNING"),
                    "info": self.get_icon("INFO")
                }.get(message.severity, self.get_icon("INFO"))

                message_row = ft.Row(
                    controls=[
                        ft.Icon(name=message_icon, color=message_color, size=14),
                        ft.Text(
                            message.message,
                            style=self.get_text_style("body_small"),
                            color=message_color,
                            expand=True
                        )
                    ],
                    spacing=spacing.xs
                )
                validation_controls.append(message_row)

            # Training time estimate
            if self.validation_result.estimated_training_time:
                time_row = ft.Row(
                    controls=[
                        ft.Icon(name=self.get_icon("TIME"), color=palette.text_secondary, size=14),
                        ft.Text(
                            f"Estimated training time: {self.validation_result.estimated_training_time}",
                            style=self.get_text_style("body_small"),
                            color=palette.text_secondary
                        )
                    ],
                    spacing=spacing.xs
                )
                validation_controls.append(time_row)

            # Update validation panel content
            self.validation_panel.content = ft.Column(
                controls=validation_controls if validation_controls else [
                    ft.Text(
                        "No validation messages",
                        style=self.get_text_style("body_small"),
                        color=palette.text_secondary,
                        italic=True
                    )
                ],
                spacing=spacing.xs
            )

            # Update suggestions panel if available
            if self.suggestion_panel and self.validation_result.suggestions:
                self._update_suggestions_ui()

        except Exception as ex:
            self.logger.error(f"Error updating validation UI: {ex}")

    def _update_suggestions_ui(self) -> None:
        """Update suggestions UI with current optimization suggestions."""
        try:
            if not self.suggestion_panel or not self.validation_result or not self.validation_result.suggestions:
                return

            palette = self.get_palette()
            spacing = self.get_spacing()

            suggestion_controls = []

            for suggestion in self.validation_result.suggestions:
                # Confidence indicator
                confidence_color = palette.success if suggestion.confidence > 0.8 else (
                    palette.warning if suggestion.confidence > 0.5 else palette.error
                )

                # Impact indicator
                impact_icon = {
                    "high": self.get_icon("PRIORITY_HIGH"),
                    "medium": self.get_icon("PRIORITY_MEDIUM"),
                    "low": self.get_icon("PRIORITY_LOW")
                }.get(suggestion.impact, self.get_icon("INFO"))

                suggestion_card = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(name=impact_icon, color=palette.primary, size=16),
                                    ft.Text(
                                        f"{suggestion.field_name}",
                                        style=self.get_text_style("label_medium"),
                                        color=palette.text_primary,
                                        weight=ft.FontWeight.W_500,
                                        expand=True
                                    ),
                                    ft.Text(
                                        f"{suggestion.confidence:.0%}",
                                        style=self.get_text_style("body_small"),
                                        color=confidence_color
                                    )
                                ],
                                spacing=spacing.xs
                            ),
                            ft.Text(
                                suggestion.reason,
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary
                            ),
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        f"Current: {suggestion.current_value}",
                                        style=self.get_text_style("body_small"),
                                        color=palette.text_secondary
                                    ),
                                    ft.Text(
                                        "→",
                                        style=self.get_text_style("body_small"),
                                        color=palette.text_secondary
                                    ),
                                    ft.Text(
                                        f"Suggested: {suggestion.suggested_value}",
                                        style=self.get_text_style("body_small"),
                                        color=palette.primary,
                                        weight=ft.FontWeight.W_500
                                    )
                                ],
                                spacing=spacing.xs
                            )
                        ],
                        spacing=spacing.xs,
                        tight=True
                    ),
                    padding=ft.padding.all(spacing.sm),
                    bgcolor=palette.surface_variant,
                    border_radius=spacing.xs,
                    border=ft.border.all(1, palette.outline)
                )
                suggestion_controls.append(suggestion_card)

            # Update suggestions panel content
            self.suggestion_panel.content = ft.Column(
                controls=suggestion_controls if suggestion_controls else [
                    ft.Text(
                        "No optimization suggestions available",
                        style=self.get_text_style("body_small"),
                        color=palette.text_secondary,
                        italic=True
                    )
                ],
                spacing=spacing.sm
            )

        except Exception as ex:
            self.logger.error(f"Error updating suggestions UI: {ex}")

    # Public Methods

    def get_current_values(self) -> Dict[str, Any]:
        """Get current hyperparameter values."""
        return self.current_values.copy()

    def set_values(self, values: Dict[str, Any]) -> None:
        """Set hyperparameter values programmatically."""
        try:
            for field_name, value in values.items():
                if field_name in self.fields:
                    self.fields[field_name].value = value
                    self.current_values[field_name] = value

            # Rebuild form to reflect changes
            self.content = self.build()
            self.update()

            # Trigger validation
            if self.config.auto_validate:
                self._schedule_validation()

        except Exception as ex:
            self.logger.error(f"Error setting values: {ex}")

    def get_validation_result(self) -> Optional[FormValidationResult]:
        """Get current validation result."""
        return self.validation_result

    def validate(self) -> Optional[FormValidationResult]:
        """Manually trigger validation and return result."""
        return self._perform_validation()

    def reset_to_defaults(self) -> None:
        """Reset all fields to their default values."""
        self._on_reset_click(None)

    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration as dictionary."""
        return {
            "hyperparameters": self.current_values.copy(),
            "mode": self.config.mode.value,
            "validation_result": {
                "is_valid": self.validation_result.is_valid if self.validation_result else False,
                "estimated_training_time": self.validation_result.estimated_training_time if self.validation_result else None,
                "resource_requirements": self.validation_result.resource_requirements if self.validation_result else None
            } if self.validation_result else None,
            "timestamp": str(datetime.now()),
            "version": "1.0"
        }

    def import_configuration(self, config_data: Dict[str, Any]) -> bool:
        """Import configuration from dictionary."""
        try:
            if "hyperparameters" in config_data:
                self.set_values(config_data["hyperparameters"])
                return True
            return False
        except Exception as ex:
            self.logger.error(f"Error importing configuration: {ex}")
            return False
