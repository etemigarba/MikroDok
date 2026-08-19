"""
Module: model_config_ui
Description: Comprehensive model architecture configuration interface with training parameter forms,
            validation, and real-time feedback. Provides intuitive configuration of model architectures,
            training parameters, optimization settings, and advanced model options with responsive design
            and full theme integration.
Phase: 4
Location: /src/modules/ui/model_builder_ui/model_config_ui/model_config_ui.py
"""

# Standard library imports
import asyncio
import logging
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl

# Training orchestration imports
try:
    from src.modules.logic.training_orchestration_lg.base_interfaces import (
        TrainingConfig,
        HyperparameterConfig,
        OptimizationStrategy,
        TrainingStatus,
        HyperparameterType
    )
    TRAINING_ORCHESTRATION_AVAILABLE = True
except ImportError:
    TrainingConfig = None
    HyperparameterConfig = None
    OptimizationStrategy = None
    TrainingStatus = None
    HyperparameterType = None
    TRAINING_ORCHESTRATION_AVAILABLE = False

# Model optimization imports
try:
    from src.modules.logic.model_optimization_lg.base_interfaces import (
        QuantizationType,
        OptimizationLevel,
        ModelFormat
    )
    MODEL_OPTIMIZATION_AVAILABLE = True
except ImportError:
    QuantizationType = None
    OptimizationLevel = None
    ModelFormat = None
    MODEL_OPTIMIZATION_AVAILABLE = False

# Inference engine imports
try:
    from src.modules.logic.inference_engine_lg.base_interfaces import (
        ModelType,
        ModelConfig,
        TokenizerType
    )
    INFERENCE_ENGINE_AVAILABLE = True
except ImportError:
    ModelType = None
    ModelConfig = None
    TokenizerType = None
    INFERENCE_ENGINE_AVAILABLE = False


class ModelConfigMode(Enum):
    """Model configuration interface modes."""
    BASIC_CONFIG = "basic"
    ADVANCED_CONFIG = "advanced"
    EXPERT_CONFIG = "expert"
    IMPORT_CONFIG = "import"


class ModelArchitectureType(Enum):
    """Model architecture types for configuration."""
    TRANSFORMER = "transformer"
    LLAMA = "llama"
    MISTRAL = "mistral"
    CUSTOM = "custom"


class ModelSizeCategory(Enum):
    """Model size categories."""
    SMALL_1B = "1B"
    MEDIUM_3B = "3B"
    LARGE_7B = "7B"
    XLARGE_13B = "13B"
    CUSTOM = "custom"


class TrainingMode(Enum):
    """Training mode options."""
    FULL_TRAINING = "full"
    FINE_TUNING = "fine_tune"
    LORA_TRAINING = "lora"
    QLORA_TRAINING = "qlora"


class ValidationLevel(Enum):
    """Configuration validation levels."""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"


@dataclass
class ModelArchitectureConfig:
    """Model architecture configuration."""
    architecture_type: ModelArchitectureType = ModelArchitectureType.TRANSFORMER
    size_category: ModelSizeCategory = ModelSizeCategory.MEDIUM_3B
    num_layers: int = 32
    hidden_size: int = 4096
    num_attention_heads: int = 32
    intermediate_size: int = 11008
    vocab_size: int = 32000
    max_position_embeddings: int = 4096
    rope_theta: float = 10000.0
    attention_dropout: float = 0.0
    hidden_dropout: float = 0.0
    initializer_range: float = 0.02
    rms_norm_eps: float = 1e-6
    use_cache: bool = True
    tie_word_embeddings: bool = False
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingParameterConfig:
    """Training parameter configuration."""
    training_mode: TrainingMode = TrainingMode.FINE_TUNING
    learning_rate: float = 5e-5
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    max_epochs: int = 3
    warmup_steps: int = 100
    weight_decay: float = 0.01
    adam_beta1: float = 0.9
    adam_beta2: float = 0.999
    adam_epsilon: float = 1e-8
    max_grad_norm: float = 1.0
    lr_scheduler_type: str = "cosine"
    save_steps: int = 500
    eval_steps: int = 500
    logging_steps: int = 10
    save_total_limit: int = 3
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False
    evaluation_strategy: str = "steps"
    save_strategy: str = "steps"
    fp16: bool = True
    bf16: bool = False
    dataloader_num_workers: int = 0
    remove_unused_columns: bool = True
    label_smoothing_factor: float = 0.0
    optim: str = "adamw_torch"
    group_by_length: bool = False
    length_column_name: str = "length"
    report_to: List[str] = field(default_factory=list)
    custom_parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelConfigurationForm:
    """Complete model configuration form data."""
    architecture: ModelArchitectureConfig = field(default_factory=ModelArchitectureConfig)
    training: TrainingParameterConfig = field(default_factory=TrainingParameterConfig)
    model_name: str = ""
    model_description: str = ""
    base_model_path: Optional[str] = None
    output_directory: str = "./models"
    dataset_path: Optional[str] = None
    validation_split: float = 0.1
    test_split: float = 0.1
    random_seed: int = 42
    enable_checkpointing: bool = True
    enable_early_stopping: bool = True
    early_stopping_patience: int = 3
    enable_tensorboard: bool = True
    enable_wandb: bool = False
    wandb_project: str = ""
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ModelConfigValidationResult:
    """Model configuration validation result."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    estimated_memory_gb: Optional[float] = None
    estimated_training_time_hours: Optional[float] = None
    compatibility_score: float = 1.0


@dataclass
class ModelConfigFormConfig:
    """Configuration for model config form interface."""
    mode: ModelConfigMode = ModelConfigMode.BASIC_CONFIG
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    show_advanced_options: bool = False
    show_expert_options: bool = False
    enable_real_time_validation: bool = True
    enable_auto_save: bool = True
    auto_save_interval_seconds: int = 30
    show_memory_estimates: bool = True
    show_time_estimates: bool = True
    enable_config_templates: bool = True
    enable_config_export: bool = True
    enable_config_import: bool = True
    max_config_history: int = 10


class ModelConfigUI(ThemeAwareUserControl):
    """
    Comprehensive model architecture configuration interface.

    Provides intuitive configuration of model architectures and training parameters
    with real-time validation, responsive design, and theme integration.

    Features:
    - Interactive model architecture configuration forms
    - Training parameter configuration with validation
    - Real-time memory and time estimation
    - Configuration templates and presets
    - Import/export functionality
    - Responsive design with theme integration
    - Advanced and expert configuration modes
    """

    def __init__(self,
                 on_config_change: Optional[Callable[[ModelConfigurationForm], None]] = None,
                 on_config_save: Optional[Callable[[ModelConfigurationForm], None]] = None,
                 config: Optional[ModelConfigFormConfig] = None,
                 initial_config: Optional[ModelConfigurationForm] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self._logger = logging.getLogger(__name__)

        # Configuration
        self._config = config or ModelConfigFormConfig()
        self._on_config_change = on_config_change
        self._on_config_save = on_config_save

        # State management
        self._current_form = initial_config or ModelConfigurationForm()
        self._validation_result = ModelConfigValidationResult(is_valid=True)
        self._is_modified = False
        self._auto_save_timer = None
        self._config_history: List[ModelConfigurationForm] = []

        # UI components
        self._mode_selector = None
        self._architecture_form = None
        self._training_form = None
        self._validation_panel = None
        self._action_buttons = None
        self._status_bar = None

        # Form fields
        self._form_fields: Dict[str, ft.Control] = {}
        self._field_validators: Dict[str, Callable] = {}

        # Initialize validation
        self._setup_validation()

    def _setup_validation(self):
        """Setup field validators."""
        self._field_validators = {
            'model_name': self._validate_model_name,
            'learning_rate': self._validate_learning_rate,
            'batch_size': self._validate_batch_size,
            'max_epochs': self._validate_max_epochs,
            'num_layers': self._validate_num_layers,
            'hidden_size': self._validate_hidden_size,
            'num_attention_heads': self._validate_attention_heads,
            'vocab_size': self._validate_vocab_size,
            'max_position_embeddings': self._validate_position_embeddings
        }

    def build(self) -> ft.Control:
        """Build the model configuration interface."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                self._create_header(),
                ft.Divider(color=palette.outline_variant),
                self._create_mode_selector(),
                ft.Divider(color=palette.outline_variant),
                self._create_main_content(),
                ft.Divider(color=palette.outline_variant),
                self._create_action_bar()
            ], spacing=spacing.section_spacing),
            padding=ft.padding.all(spacing.container_padding),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_header(self) -> ft.Control:
        """Create the header section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Row([
                ft.Icon(
                    ft.Icons.SETTINGS,
                    color=palette.primary,
                    size=24
                ),
                ft.Column([
                    ft.Text(
                        "Model Configuration",
                        style=typography.headline_medium,
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "Configure model architecture and training parameters",
                        style=typography.body_medium,
                        color=palette.text_secondary
                    )
                ], spacing=spacing.xs, expand=True),
                self._create_header_actions()
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.all(spacing.md)
        )

    def _create_header_actions(self) -> ft.Control:
        """Create header action buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Row([
            ft.IconButton(
                icon=ft.Icons.UPLOAD_FILE,
                tooltip="Import Configuration",
                on_click=self._on_import_config,
                icon_color=palette.text_secondary
            ),
            ft.IconButton(
                icon=ft.Icons.DOWNLOAD,
                tooltip="Export Configuration",
                on_click=self._on_export_config,
                icon_color=palette.text_secondary
            ),
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                tooltip="Reset to Defaults",
                on_click=self._on_reset_config,
                icon_color=palette.text_secondary
            )
        ], spacing=spacing.xs)

    def _create_mode_selector(self) -> ft.Control:
        """Create mode selector tabs."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        tabs = []
        for mode in ModelConfigMode:
            tabs.append(ft.Tab(
                text=mode.value.replace('_', ' ').title(),
                content=ft.Container()  # Content will be set dynamically
            ))

        self._mode_selector = ft.Tabs(
            selected_index=list(ModelConfigMode).index(self._config.mode),
            on_change=self._on_mode_change,
            tabs=tabs,
            indicator_color=palette.primary,
            label_color=palette.text_primary,
            unselected_label_color=palette.text_secondary
        )

        return self._mode_selector

    def _create_main_content(self) -> ft.Control:
        """Create main content based on current mode."""
        if self._config.mode == ModelConfigMode.BASIC_CONFIG:
            return self._create_basic_config_form()
        elif self._config.mode == ModelConfigMode.ADVANCED_CONFIG:
            return self._create_advanced_config_form()
        elif self._config.mode == ModelConfigMode.EXPERT_CONFIG:
            return self._create_expert_config_form()
        else:  # IMPORT_CONFIG
            return self._create_import_config_form()

    def _create_basic_config_form(self) -> ft.Control:
        """Create basic configuration form."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                self._create_model_info_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_basic_architecture_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_basic_training_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_validation_section()
            ], spacing=spacing.section_spacing),
            padding=ft.padding.all(spacing.md)
        )

    def _create_advanced_config_form(self) -> ft.Control:
        """Create advanced configuration form."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                self._create_model_info_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_advanced_architecture_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_advanced_training_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_optimization_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_validation_section()
            ], spacing=spacing.section_spacing),
            padding=ft.padding.all(spacing.md)
        )

    def _create_expert_config_form(self) -> ft.Control:
        """Create expert configuration form."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                self._create_model_info_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_expert_architecture_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_expert_training_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_optimization_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_advanced_options_section(),
                ft.Divider(color=palette.outline_variant),
                self._create_validation_section()
            ], spacing=spacing.section_spacing),
            padding=ft.padding.all(spacing.md)
        )

    def _create_import_config_form(self) -> ft.Control:
        """Create import configuration form."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Import Configuration",
                    style=typography.headline_small,
                    color=palette.text_primary
                ),
                ft.Text(
                    "Import model configuration from file or paste JSON configuration",
                    style=typography.body_medium,
                    color=palette.text_secondary
                ),
                ft.Container(height=spacing.md),
                ft.Row([
                    ft.ElevatedButton(
                        text="Choose File",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=self._on_choose_config_file,
                        bgcolor=palette.primary,
                        color=palette.text_primary
                    ),
                    ft.Text("or", color=palette.text_secondary),
                    ft.ElevatedButton(
                        text="Paste JSON",
                        icon=ft.Icons.CONTENT_PASTE,
                        on_click=self._on_paste_config,
                        bgcolor=palette.secondary,
                        color=palette.text_primary
                    )
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=spacing.lg),
                ft.TextField(
                    label="Configuration JSON",
                    multiline=True,
                    min_lines=10,
                    max_lines=20,
                    value="",
                    on_change=self._on_config_json_change,
                    border_color=palette.outline,
                    focused_border_color=palette.primary,
                    label_style=ft.TextStyle(color=palette.text_secondary),
                    text_style=ft.TextStyle(color=palette.text_primary)
                ),
                ft.Container(height=spacing.md),
                ft.ElevatedButton(
                    text="Import Configuration",
                    icon=ft.Icons.CHECK,
                    on_click=self._on_import_json_config,
                    bgcolor=palette.success,
                    color=palette.text_primary
                )
            ], spacing=spacing.md, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.lg)
        )

    def _create_model_info_section(self) -> ft.Control:
        """Create model information section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        model_name_field = ft.TextField(
            label="Model Name",
            value=self._current_form.model_name,
            on_change=lambda e: self._on_field_change('model_name', e.control.value),
            border_color=palette.outline,
            focused_border_color=palette.primary,
            label_style=ft.TextStyle(color=palette.text_secondary),
            text_style=ft.TextStyle(color=palette.text_primary),
            expand=True
        )
        self._form_fields['model_name'] = model_name_field

        description_field = ft.TextField(
            label="Description",
            value=self._current_form.model_description,
            multiline=True,
            min_lines=2,
            max_lines=4,
            on_change=lambda e: self._on_field_change('model_description', e.control.value),
            border_color=palette.outline,
            focused_border_color=palette.primary,
            label_style=ft.TextStyle(color=palette.text_secondary),
            text_style=ft.TextStyle(color=palette.text_primary)
        )
        self._form_fields['model_description'] = description_field

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Model Information",
                    style=typography.headline_small,
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                model_name_field,
                ft.Container(height=spacing.sm),
                description_field
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8)
        )

    def _create_basic_architecture_section(self) -> ft.Control:
        """Create basic architecture configuration section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Architecture type dropdown
        architecture_dropdown = ft.Dropdown(
            label="Architecture Type",
            value=self._current_form.architecture.architecture_type.value,
            options=[ft.dropdown.Option(arch.value, arch.value.title()) for arch in ModelArchitectureType],
            on_change=lambda e: self._on_field_change('architecture_type', e.control.value),
            border_color=palette.outline,
            focused_border_color=palette.primary,
            label_style=ft.TextStyle(color=palette.text_secondary),
            text_style=ft.TextStyle(color=palette.text_primary),
            expand=True
        )
        self._form_fields['architecture_type'] = architecture_dropdown

        # Size category dropdown
        size_dropdown = ft.Dropdown(
            label="Model Size",
            value=self._current_form.architecture.size_category.value,
            options=[ft.dropdown.Option(size.value, size.value) for size in ModelSizeCategory],
            on_change=lambda e: self._on_field_change('size_category', e.control.value),
            border_color=palette.outline,
            focused_border_color=palette.primary,
            label_style=ft.TextStyle(color=palette.text_secondary),
            text_style=ft.TextStyle(color=palette.text_primary),
            expand=True
        )
        self._form_fields['size_category'] = size_dropdown

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Model Architecture",
                    style=typography.headline_small,
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                ft.Row([
                    architecture_dropdown,
                    ft.Container(width=spacing.md),
                    size_dropdown
                ], expand=True)
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8)
        )

    def _create_basic_training_section(self) -> ft.Control:
        """Create basic training configuration section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Training mode dropdown
        training_mode_dropdown = ft.Dropdown(
            label="Training Mode",
            value=self._current_form.training.training_mode.value,
            options=[ft.dropdown.Option(mode.value, mode.value.replace('_', ' ').title()) for mode in TrainingMode],
            on_change=lambda e: self._on_field_change('training_mode', e.control.value),
            border_color=palette.outline,
            focused_border_color=palette.primary,
            label_style=ft.TextStyle(color=palette.text_secondary),
            text_style=ft.TextStyle(color=palette.text_primary),
            expand=True
        )
        self._form_fields['training_mode'] = training_mode_dropdown

        # Learning rate field
        learning_rate_field = ft.TextField(
            label="Learning Rate",
            value=str(self._current_form.training.learning_rate),
            on_change=lambda e: self._on_field_change('learning_rate', e.control.value),
            border_color=palette.outline,
            focused_border_color=palette.primary,
            label_style=ft.TextStyle(color=palette.text_secondary),
            text_style=ft.TextStyle(color=palette.text_primary),
            expand=True
        )
        self._form_fields['learning_rate'] = learning_rate_field

        # Batch size field
        batch_size_field = ft.TextField(
            label="Batch Size",
            value=str(self._current_form.training.batch_size),
            on_change=lambda e: self._on_field_change('batch_size', e.control.value),
            border_color=palette.outline,
            focused_border_color=palette.primary,
            label_style=ft.TextStyle(color=palette.text_secondary),
            text_style=ft.TextStyle(color=palette.text_primary),
            expand=True
        )
        self._form_fields['batch_size'] = batch_size_field

        # Max epochs field
        max_epochs_field = ft.TextField(
            label="Max Epochs",
            value=str(self._current_form.training.max_epochs),
            on_change=lambda e: self._on_field_change('max_epochs', e.control.value),
            border_color=palette.outline,
            focused_border_color=palette.primary,
            label_style=ft.TextStyle(color=palette.text_secondary),
            text_style=ft.TextStyle(color=palette.text_primary),
            expand=True
        )
        self._form_fields['max_epochs'] = max_epochs_field

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Training Parameters",
                    style=typography.headline_small,
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                training_mode_dropdown,
                ft.Container(height=spacing.sm),
                ft.Row([
                    learning_rate_field,
                    ft.Container(width=spacing.md),
                    batch_size_field
                ], expand=True),
                ft.Container(height=spacing.sm),
                ft.Row([
                    max_epochs_field,
                    ft.Container(width=spacing.md),
                    ft.Container(expand=True)  # Spacer
                ], expand=True)
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8)
        )

    def _create_validation_section(self) -> ft.Control:
        """Create validation and estimation section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Validation status
        validation_status = ft.Container(
            content=ft.Row([
                ft.Icon(
                    ft.Icons.CHECK_CIRCLE if self._validation_result.is_valid else ft.Icons.ERROR,
                    color=palette.success if self._validation_result.is_valid else palette.error,
                    size=20
                ),
                ft.Text(
                    "Configuration Valid" if self._validation_result.is_valid else "Configuration Invalid",
                    style=typography.body_medium,
                    color=palette.success if self._validation_result.is_valid else palette.error
                )
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.sm),
            bgcolor=palette.success_container if self._validation_result.is_valid else palette.error_container,
            border_radius=ft.border_radius.all(4)
        )

        # Memory estimation
        memory_estimate = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.MEMORY, color=palette.primary, size=16),
                ft.Text(
                    f"Est. Memory: {self._validation_result.estimated_memory_gb or 'N/A'} GB",
                    style=typography.body_small,
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs),
            visible=self._config.show_memory_estimates
        )

        # Time estimation
        time_estimate = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SCHEDULE, color=palette.primary, size=16),
                ft.Text(
                    f"Est. Training Time: {self._validation_result.estimated_training_time_hours or 'N/A'} hours",
                    style=typography.body_small,
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs),
            visible=self._config.show_time_estimates
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Validation & Estimates",
                    style=typography.headline_small,
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                validation_status,
                ft.Container(height=spacing.sm),
                ft.Row([
                    memory_estimate,
                    ft.Container(width=spacing.lg),
                    time_estimate
                ], expand=True)
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8)
        )

    def _create_action_bar(self) -> ft.Control:
        """Create action button bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Row([
                ft.ElevatedButton(
                    text="Reset",
                    icon=ft.Icons.REFRESH,
                    on_click=self._on_reset_config,
                    bgcolor=palette.secondary,
                    color=palette.text_primary
                ),
                ft.Container(expand=True),  # Spacer
                ft.ElevatedButton(
                    text="Save Draft",
                    icon=ft.Icons.SAVE,
                    on_click=self._on_save_draft,
                    bgcolor=palette.secondary,
                    color=palette.text_primary
                ),
                ft.Container(width=spacing.md),
                ft.ElevatedButton(
                    text="Save Configuration",
                    icon=ft.Icons.CHECK,
                    on_click=self._on_save_config,
                    bgcolor=palette.primary,
                    color=palette.text_primary,
                    disabled=not self._validation_result.is_valid
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.all(spacing.md)
        )

    # Event handlers
    def _on_mode_change(self, e):
        """Handle mode change."""
        try:
            mode_index = e.control.selected_index
            new_mode = list(ModelConfigMode)[mode_index]
            self._config.mode = new_mode
            self._logger.info(f"Mode changed to: {new_mode.value}")
            self.update()
        except Exception as ex:
            self._logger.error(f"Error changing mode: {ex}")

    def _on_field_change(self, field_name: str, value: Any):
        """Handle field value change."""
        try:
            self._set_field_value(field_name, value)
            self._is_modified = True

            if self._config.enable_real_time_validation:
                self._validate_configuration()

            if self._on_config_change:
                self._on_config_change(self._current_form)

            self._start_auto_save_timer()
            self.update()

        except Exception as ex:
            self._logger.error(f"Error handling field change for {field_name}: {ex}")

    def _set_field_value(self, field_name: str, value: Any):
        """Set field value in the configuration."""
        if field_name == 'model_name':
            self._current_form.model_name = str(value)
        elif field_name == 'model_description':
            self._current_form.model_description = str(value)
        elif field_name == 'architecture_type':
            self._current_form.architecture.architecture_type = ModelArchitectureType(value)
        elif field_name == 'size_category':
            self._current_form.architecture.size_category = ModelSizeCategory(value)
        elif field_name == 'training_mode':
            self._current_form.training.training_mode = TrainingMode(value)
        elif field_name == 'learning_rate':
            self._current_form.training.learning_rate = float(value)
        elif field_name == 'batch_size':
            self._current_form.training.batch_size = int(value)
        elif field_name == 'max_epochs':
            self._current_form.training.max_epochs = int(value)

    def _on_import_config(self, e):
        """Handle import configuration."""
        try:
            self._config.mode = ModelConfigMode.IMPORT_CONFIG
            self.update()
        except Exception as ex:
            self._logger.error(f"Error switching to import mode: {ex}")

    def _on_export_config(self, e):
        """Handle export configuration."""
        try:
            config_dict = self._form_to_dict(self._current_form)
            config_json = json.dumps(config_dict, indent=2, default=str)

            # In a real implementation, this would open a file save dialog
            self._logger.info("Configuration exported")

        except Exception as ex:
            self._logger.error(f"Error exporting configuration: {ex}")

    def _on_reset_config(self, e):
        """Handle reset configuration."""
        try:
            self._current_form = ModelConfigurationForm()
            self._is_modified = False
            self._validate_configuration()
            self.update()

        except Exception as ex:
            self._logger.error(f"Error resetting configuration: {ex}")

    def _on_save_draft(self, e):
        """Handle save draft."""
        try:
            self._save_to_history()
            self._is_modified = False
            self._logger.info("Configuration draft saved")

        except Exception as ex:
            self._logger.error(f"Error saving draft: {ex}")

    def _on_save_config(self, e):
        """Handle save configuration."""
        try:
            if self._validation_result.is_valid:
                self._save_to_history()
                self._is_modified = False

                if self._on_config_save:
                    self._on_config_save(self._current_form)

                self._logger.info("Configuration saved successfully")
            else:
                self._logger.warning("Cannot save invalid configuration")

        except Exception as ex:
            self._logger.error(f"Error saving configuration: {ex}")

    def _on_choose_config_file(self, e):
        """Handle choose configuration file."""
        try:
            # In a real implementation, this would open a file picker
            self._logger.info("File picker would open here")

        except Exception as ex:
            self._logger.error(f"Error opening file picker: {ex}")

    def _on_paste_config(self, e):
        """Handle paste configuration."""
        try:
            # In a real implementation, this would get clipboard content
            self._logger.info("Clipboard content would be pasted here")

        except Exception as ex:
            self._logger.error(f"Error pasting configuration: {ex}")

    def _on_config_json_change(self, e):
        """Handle configuration JSON change."""
        try:
            json_text = e.control.value
            if json_text.strip():
                config_dict = json.loads(json_text)
                self._current_form = self._dict_to_form(config_dict)
                self._validate_configuration()

        except json.JSONDecodeError as ex:
            self._logger.warning(f"Invalid JSON: {ex}")
        except Exception as ex:
            self._logger.error(f"Error parsing configuration JSON: {ex}")

    def _on_import_json_config(self, e):
        """Handle import JSON configuration."""
        try:
            self._config.mode = ModelConfigMode.BASIC_CONFIG
            self._is_modified = True
            self.update()

        except Exception as ex:
            self._logger.error(f"Error importing JSON configuration: {ex}")

    # Validation methods
    def _validate_configuration(self):
        """Validate the current configuration."""
        try:
            errors = []
            warnings = []
            suggestions = []

            # Validate model name
            if not self._current_form.model_name.strip():
                errors.append("Model name is required")

            # Validate training parameters
            if self._current_form.training.learning_rate <= 0:
                errors.append("Learning rate must be positive")

            if self._current_form.training.batch_size <= 0:
                errors.append("Batch size must be positive")

            if self._current_form.training.max_epochs <= 0:
                errors.append("Max epochs must be positive")

            # Validate architecture parameters
            if self._current_form.architecture.num_layers <= 0:
                errors.append("Number of layers must be positive")

            if self._current_form.architecture.hidden_size <= 0:
                errors.append("Hidden size must be positive")

            # Generate warnings and suggestions
            if self._current_form.training.learning_rate > 0.01:
                warnings.append("Learning rate is quite high, consider reducing it")

            if self._current_form.training.batch_size > 32:
                suggestions.append("Consider using gradient accumulation for large batch sizes")

            # Estimate memory and time
            estimated_memory = self._estimate_memory_usage()
            estimated_time = self._estimate_training_time()

            self._validation_result = ModelConfigValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                estimated_memory_gb=estimated_memory,
                estimated_training_time_hours=estimated_time,
                compatibility_score=1.0 if len(errors) == 0 else 0.5
            )

        except Exception as ex:
            self._logger.error(f"Error validating configuration: {ex}")
            self._validation_result = ModelConfigValidationResult(
                is_valid=False,
                errors=[f"Validation error: {ex}"]
            )

    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage based on model configuration."""
        try:
            # Simple estimation based on model size
            size_multipliers = {
                ModelSizeCategory.SMALL_1B: 4.0,
                ModelSizeCategory.MEDIUM_3B: 12.0,
                ModelSizeCategory.LARGE_7B: 28.0,
                ModelSizeCategory.XLARGE_13B: 52.0,
                ModelSizeCategory.CUSTOM: 16.0
            }

            base_memory = size_multipliers.get(
                self._current_form.architecture.size_category, 16.0
            )

            # Adjust for training mode
            if self._current_form.training.training_mode == TrainingMode.FULL_TRAINING:
                base_memory *= 3.0  # Full training requires more memory
            elif self._current_form.training.training_mode == TrainingMode.FINE_TUNING:
                base_memory *= 2.0  # Fine-tuning requires moderate memory
            else:  # LoRA/QLoRA
                base_memory *= 1.2  # LoRA requires minimal additional memory

            # Adjust for batch size
            batch_multiplier = max(1.0, self._current_form.training.batch_size / 4.0)
            base_memory *= batch_multiplier

            return round(base_memory, 1)

        except Exception as ex:
            self._logger.error(f"Error estimating memory usage: {ex}")
            return None

    def _estimate_training_time(self) -> float:
        """Estimate training time based on configuration."""
        try:
            # Simple estimation based on model size and epochs
            size_multipliers = {
                ModelSizeCategory.SMALL_1B: 1.0,
                ModelSizeCategory.MEDIUM_3B: 3.0,
                ModelSizeCategory.LARGE_7B: 7.0,
                ModelSizeCategory.XLARGE_13B: 13.0,
                ModelSizeCategory.CUSTOM: 5.0
            }

            base_time_per_epoch = size_multipliers.get(
                self._current_form.architecture.size_category, 5.0
            )

            total_time = base_time_per_epoch * self._current_form.training.max_epochs

            # Adjust for training mode
            if self._current_form.training.training_mode == TrainingMode.FULL_TRAINING:
                total_time *= 2.0
            elif self._current_form.training.training_mode in [TrainingMode.LORA_TRAINING, TrainingMode.QLORA_TRAINING]:
                total_time *= 0.5

            return round(total_time, 1)

        except Exception as ex:
            self._logger.error(f"Error estimating training time: {ex}")
            return None

    def _start_auto_save_timer(self):
        """Start auto-save timer."""
        if self._config.enable_auto_save and self._auto_save_timer:
            self._auto_save_timer.cancel()

        if self._config.enable_auto_save:
            self._auto_save_timer = asyncio.create_task(
                self._auto_save_after_delay()
            )

    async def _auto_save_after_delay(self):
        """Auto-save after delay."""
        try:
            await asyncio.sleep(self._config.auto_save_interval_seconds)
            if self._is_modified:
                self._save_to_history()
                self._logger.info("Auto-saved configuration")
        except asyncio.CancelledError:
            pass
        except Exception as ex:
            self._logger.error(f"Error during auto-save: {ex}")

    def _save_to_history(self):
        """Save current configuration to history."""
        try:
            # Create a copy of the current form
            config_copy = ModelConfigurationForm(
                architecture=ModelArchitectureConfig(**self._current_form.architecture.__dict__),
                training=TrainingParameterConfig(**self._current_form.training.__dict__),
                **{k: v for k, v in self._current_form.__dict__.items()
                   if k not in ['architecture', 'training']}
            )
            config_copy.modified_at = datetime.now(timezone.utc)

            self._config_history.append(config_copy)

            # Limit history size
            if len(self._config_history) > self._config.max_config_history:
                self._config_history.pop(0)

        except Exception as ex:
            self._logger.error(f"Error saving to history: {ex}")

    def _form_to_dict(self, form: ModelConfigurationForm) -> Dict[str, Any]:
        """Convert form to dictionary."""
        try:
            return {
                'model_name': form.model_name,
                'model_description': form.model_description,
                'base_model_path': form.base_model_path,
                'output_directory': form.output_directory,
                'dataset_path': form.dataset_path,
                'validation_split': form.validation_split,
                'test_split': form.test_split,
                'random_seed': form.random_seed,
                'architecture': {
                    'architecture_type': form.architecture.architecture_type.value,
                    'size_category': form.architecture.size_category.value,
                    'num_layers': form.architecture.num_layers,
                    'hidden_size': form.architecture.hidden_size,
                    'num_attention_heads': form.architecture.num_attention_heads,
                    'intermediate_size': form.architecture.intermediate_size,
                    'vocab_size': form.architecture.vocab_size,
                    'max_position_embeddings': form.architecture.max_position_embeddings,
                    'custom_config': form.architecture.custom_config
                },
                'training': {
                    'training_mode': form.training.training_mode.value,
                    'learning_rate': form.training.learning_rate,
                    'batch_size': form.training.batch_size,
                    'gradient_accumulation_steps': form.training.gradient_accumulation_steps,
                    'max_epochs': form.training.max_epochs,
                    'warmup_steps': form.training.warmup_steps,
                    'weight_decay': form.training.weight_decay,
                    'custom_parameters': form.training.custom_parameters
                },
                'tags': form.tags,
                'notes': form.notes,
                'created_at': form.created_at.isoformat(),
                'modified_at': form.modified_at.isoformat()
            }
        except Exception as ex:
            self._logger.error(f"Error converting form to dict: {ex}")
            return {}

    def _dict_to_form(self, config_dict: Dict[str, Any]) -> ModelConfigurationForm:
        """Convert dictionary to form."""
        try:
            architecture = ModelArchitectureConfig(
                architecture_type=ModelArchitectureType(config_dict.get('architecture', {}).get('architecture_type', 'transformer')),
                size_category=ModelSizeCategory(config_dict.get('architecture', {}).get('size_category', '3B')),
                num_layers=config_dict.get('architecture', {}).get('num_layers', 32),
                hidden_size=config_dict.get('architecture', {}).get('hidden_size', 4096),
                num_attention_heads=config_dict.get('architecture', {}).get('num_attention_heads', 32),
                intermediate_size=config_dict.get('architecture', {}).get('intermediate_size', 11008),
                vocab_size=config_dict.get('architecture', {}).get('vocab_size', 32000),
                max_position_embeddings=config_dict.get('architecture', {}).get('max_position_embeddings', 4096),
                custom_config=config_dict.get('architecture', {}).get('custom_config', {})
            )

            training = TrainingParameterConfig(
                training_mode=TrainingMode(config_dict.get('training', {}).get('training_mode', 'fine_tune')),
                learning_rate=config_dict.get('training', {}).get('learning_rate', 5e-5),
                batch_size=config_dict.get('training', {}).get('batch_size', 4),
                gradient_accumulation_steps=config_dict.get('training', {}).get('gradient_accumulation_steps', 4),
                max_epochs=config_dict.get('training', {}).get('max_epochs', 3),
                warmup_steps=config_dict.get('training', {}).get('warmup_steps', 100),
                weight_decay=config_dict.get('training', {}).get('weight_decay', 0.01),
                custom_parameters=config_dict.get('training', {}).get('custom_parameters', {})
            )

            return ModelConfigurationForm(
                architecture=architecture,
                training=training,
                model_name=config_dict.get('model_name', ''),
                model_description=config_dict.get('model_description', ''),
                base_model_path=config_dict.get('base_model_path'),
                output_directory=config_dict.get('output_directory', './models'),
                dataset_path=config_dict.get('dataset_path'),
                validation_split=config_dict.get('validation_split', 0.1),
                test_split=config_dict.get('test_split', 0.1),
                random_seed=config_dict.get('random_seed', 42),
                tags=config_dict.get('tags', []),
                notes=config_dict.get('notes', '')
            )
        except Exception as ex:
            self._logger.error(f"Error converting dict to form: {ex}")
            return ModelConfigurationForm()

    # Field validation methods
    def _validate_model_name(self, value: str) -> bool:
        """Validate model name."""
        return bool(value and value.strip())

    def _validate_learning_rate(self, value: str) -> bool:
        """Validate learning rate."""
        try:
            lr = float(value)
            return 0 < lr <= 1.0
        except ValueError:
            return False

    def _validate_batch_size(self, value: str) -> bool:
        """Validate batch size."""
        try:
            bs = int(value)
            return bs > 0
        except ValueError:
            return False

    def _validate_max_epochs(self, value: str) -> bool:
        """Validate max epochs."""
        try:
            epochs = int(value)
            return epochs > 0
        except ValueError:
            return False

    def _validate_num_layers(self, value: str) -> bool:
        """Validate number of layers."""
        try:
            layers = int(value)
            return layers > 0
        except ValueError:
            return False

    def _validate_hidden_size(self, value: str) -> bool:
        """Validate hidden size."""
        try:
            size = int(value)
            return size > 0
        except ValueError:
            return False

    def _validate_attention_heads(self, value: str) -> bool:
        """Validate attention heads."""
        try:
            heads = int(value)
            return heads > 0
        except ValueError:
            return False

    def _validate_vocab_size(self, value: str) -> bool:
        """Validate vocabulary size."""
        try:
            size = int(value)
            return size > 0
        except ValueError:
            return False

    def _validate_position_embeddings(self, value: str) -> bool:
        """Validate position embeddings."""
        try:
            pos = int(value)
            return pos > 0
        except ValueError:
            return False

    # Public methods for advanced and expert configurations
    def _create_advanced_architecture_section(self) -> ft.Control:
        """Create advanced architecture section (placeholder)."""
        return self._create_basic_architecture_section()

    def _create_advanced_training_section(self) -> ft.Control:
        """Create advanced training section (placeholder)."""
        return self._create_basic_training_section()

    def _create_expert_architecture_section(self) -> ft.Control:
        """Create expert architecture section (placeholder)."""
        return self._create_basic_architecture_section()

    def _create_expert_training_section(self) -> ft.Control:
        """Create expert training section (placeholder)."""
        return self._create_basic_training_section()

    def _create_optimization_section(self) -> ft.Control:
        """Create optimization section (placeholder)."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Optimization Settings",
                    style=typography.headline_small,
                    color=palette.text_primary
                ),
                ft.Text(
                    "Advanced optimization settings will be available in future versions",
                    style=typography.body_medium,
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8)
        )

    def _create_advanced_options_section(self) -> ft.Control:
        """Create advanced options section (placeholder)."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Advanced Options",
                    style=typography.headline_small,
                    color=palette.text_primary
                ),
                ft.Text(
                    "Advanced configuration options will be available in future versions",
                    style=typography.body_medium,
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8)
        )

    # Public API methods
    def get_configuration(self) -> ModelConfigurationForm:
        """Get current configuration."""
        return self._current_form

    def set_configuration(self, config: ModelConfigurationForm):
        """Set configuration."""
        self._current_form = config
        self._validate_configuration()
        self.update()

    def get_validation_result(self) -> ModelConfigValidationResult:
        """Get validation result."""
        return self._validation_result

    def export_configuration(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return self._form_to_dict(self._current_form)

    def import_configuration(self, config_dict: Dict[str, Any]):
        """Import configuration from dictionary."""
        self._current_form = self._dict_to_form(config_dict)
        self._validate_configuration()
        self.update()
