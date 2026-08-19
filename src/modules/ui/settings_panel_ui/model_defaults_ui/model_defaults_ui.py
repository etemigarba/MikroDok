"""
Module: model_defaults_ui
Description: Comprehensive model defaults configuration interface for MikroDok application.
            Provides settings for default model architecture, training parameters, quantization options,
            checkpoint configuration, and resource allocation defaults. Features responsive design,
            theme-aware styling, accessibility compliance, and real-time validation.

Features:
- Model architecture defaults (1B, 3B, 7B parameter options)
- Training parameter defaults (learning rate, batch size, epochs)
- Quantization settings (INT4, INT8, FP16, FP32)
- Checkpoint configuration (auto-save intervals, frequency)
- Resource allocation defaults (memory limits, performance profiles)
- Theme-aware responsive design with breakpoint adaptation
- Real-time validation and error handling
- Import/export configuration capabilities
- Integration with settings persistence system

Phase: 4
Location: /src/modules/ui/settings_panel_ui/model_defaults_ui/model_defaults_ui.py
"""

# Standard library imports
import os
import json
import logging
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    ResponsiveLayoutManager,
    ColorPalette,
    TypographyScale,
    SpacingSystem,
    IconSystem,
    ScreenSize
)

# Configure logging
logger = logging.getLogger(__name__)


class ModelArchitectureType(Enum):
    """Model architecture types for defaults."""
    TRANSFORMER = "transformer"
    LLAMA = "llama"
    MISTRAL = "mistral"
    CUSTOM = "custom"


class ModelSizeCategory(Enum):
    """Model size categories for defaults."""
    SMALL_1B = "1B"
    MEDIUM_3B = "3B"
    LARGE_7B = "7B"
    CUSTOM = "custom"


class QuantizationType(Enum):
    """Model quantization types."""
    FP32 = "FP32"
    FP16 = "FP16"
    INT8 = "INT8"
    INT4 = "INT4"


class PerformanceProfile(Enum):
    """Performance profile options."""
    POWER_SAVER = "power_saver"
    BALANCED = "balanced"
    PERFORMANCE = "performance"
    MAXIMUM = "maximum"


class ValidationLevel(Enum):
    """Validation level options."""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    CUSTOM = "custom"


@dataclass
class ModelArchitectureDefaults:
    """Default model architecture configuration."""
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


@dataclass
class TrainingParameterDefaults:
    """Default training parameter configuration."""
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


@dataclass
class QuantizationDefaults:
    """Default quantization configuration."""
    default_quantization: QuantizationType = QuantizationType.FP16
    enable_dynamic_quantization: bool = True
    calibration_dataset_size: int = 1000
    preserve_accuracy_threshold: float = 0.95
    target_compression_ratio: float = 4.0
    quantize_embeddings: bool = True
    quantize_attention: bool = True
    quantize_feedforward: bool = True
    calibration_method: str = "entropy"
    batch_size: int = 32
    num_calibration_batches: int = 100


@dataclass
class CheckpointDefaults:
    """Default checkpoint configuration."""
    enable_checkpointing: bool = True
    checkpoint_interval: int = 1000
    save_best_only: bool = True
    max_checkpoints: int = 5
    checkpoint_directory: str = "./checkpoints"
    enable_early_stopping: bool = True
    early_stopping_patience: int = 10
    early_stopping_threshold: float = 0.001
    enable_tensorboard: bool = True
    enable_wandb: bool = False
    wandb_project: str = ""


@dataclass
class ResourceAllocationDefaults:
    """Default resource allocation configuration."""
    performance_profile: PerformanceProfile = PerformanceProfile.BALANCED
    max_memory_gb: float = 8.0
    gpu_enabled: bool = True
    cpu_threads: int = 4
    enable_mixed_precision: bool = True
    gradient_checkpointing: bool = False
    dataloader_num_workers: int = 2
    pin_memory: bool = True
    prefetch_factor: int = 2


@dataclass
class ModelDefaultsData:
    """Complete model defaults configuration data."""
    architecture: ModelArchitectureDefaults = field(default_factory=ModelArchitectureDefaults)
    training: TrainingParameterDefaults = field(default_factory=TrainingParameterDefaults)
    quantization: QuantizationDefaults = field(default_factory=QuantizationDefaults)
    checkpoints: CheckpointDefaults = field(default_factory=CheckpointDefaults)
    resources: ResourceAllocationDefaults = field(default_factory=ResourceAllocationDefaults)
    
    # Metadata
    config_name: str = "Default Configuration"
    config_description: str = "Standard model defaults for general use"
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)


@dataclass
class ModelDefaultsConfig:
    """Configuration for model defaults interface."""
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    show_advanced_options: bool = False
    show_expert_options: bool = False
    enable_real_time_validation: bool = True
    enable_auto_save: bool = True
    auto_save_interval_seconds: int = 30
    show_memory_estimates: bool = True
    show_performance_estimates: bool = True
    enable_config_templates: bool = True
    enable_config_export: bool = True
    enable_config_import: bool = True
    max_config_history: int = 10
    compact_mode: bool = False
    show_tooltips: bool = True
    enable_keyboard_shortcuts: bool = True
    theme_aware: bool = True


class ModelDefaultsUI(ThemeAwareUserControl):
    """
    Comprehensive model defaults configuration interface.

    Features:
    - Responsive model defaults configuration with breakpoint-aware layouts
    - Model architecture defaults (1B, 3B, 7B parameter options)
    - Training parameter defaults with validation and estimates
    - Quantization settings with performance impact indicators
    - Checkpoint configuration with storage management
    - Resource allocation defaults with performance profiles
    - Theme-aware styling with accessibility compliance
    - Real-time validation and error handling
    - Configuration import/export capabilities
    - Integration with settings persistence system
    - Modern UI/UX with smooth animations and transitions
    """

    def __init__(self,
                 config: Optional[ModelDefaultsConfig] = None,
                 on_defaults_changed: Optional[Callable[[ModelDefaultsData], None]] = None,
                 on_config_saved: Optional[Callable[[ModelDefaultsData], None]] = None,
                 on_config_loaded: Optional[Callable[[ModelDefaultsData], None]] = None,
                 **kwargs):
        """
        Initialize the model defaults UI.

        Args:
            config: Model defaults configuration
            on_defaults_changed: Callback for when defaults change
            on_config_saved: Callback for when configuration is saved
            on_config_loaded: Callback for when configuration is loaded
            **kwargs: Additional arguments for UserControl
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or ModelDefaultsConfig()
        
        # Callbacks
        self._on_defaults_changed = on_defaults_changed
        self._on_config_saved = on_config_saved
        self._on_config_loaded = on_config_loaded
        
        # State
        self._current_defaults = ModelDefaultsData()
        self._original_defaults = ModelDefaultsData()
        self._has_unsaved_changes = False
        self._validation_errors: Dict[str, str] = {}
        self._is_loading = False
        self._is_saving = False
        
        # UI components
        self._header_container: Optional[ft.Container] = None
        self._tabs_container: Optional[ft.Container] = None
        self._content_container: Optional[ft.Container] = None
        self._action_bar: Optional[ft.Container] = None
        self._status_bar: Optional[ft.Container] = None
        self._validation_panel: Optional[ft.Container] = None
        
        # Tab components
        self._architecture_tab: Optional[ft.Container] = None
        self._training_tab: Optional[ft.Container] = None
        self._quantization_tab: Optional[ft.Container] = None
        self._checkpoints_tab: Optional[ft.Container] = None
        self._resources_tab: Optional[ft.Container] = None
        
        # Form controls
        self._form_controls: Dict[str, ft.Control] = {}
        self._tab_controls: Dict[str, ft.Tabs] = {}
        
        # Responsive manager
        self._responsive_manager: Optional[ResponsiveLayoutManager] = None
        
        # Auto-save timer
        self._auto_save_timer = None
        
        # Build UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the model defaults interface."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Initialize responsive manager
        self._responsive_manager = self.get_responsive_layout_manager()
        
        # Main container with responsive design
        self.content = ft.Column(
            controls=[
                self._create_header(),
                self._create_tabs(),
                self._create_validation_panel(),
                self._create_action_bar(),
                self._create_status_bar()
            ],
            spacing=spacing.md,
            expand=True
        )
        
        # Apply theme-aware styling
        self.bgcolor = palette.surface
        self.border_radius = self.get_responsive_value(8, 10, 12, 14)
        self.padding = self.get_responsive_padding(
            mobile=spacing.md,
            tablet=spacing.lg,
            desktop=spacing.xl
        )

    def _create_header(self) -> ft.Container:
        """Create the header section with title and controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Title
        title = ft.Text(
            "Model Defaults",
            size=typography.h2[0],
            weight=ft.FontWeight.W_600,
            color=palette.text_primary
        )

        # Subtitle
        subtitle = ft.Text(
            "Configure default settings for model architecture, training, and optimization",
            size=typography.body_medium[0],
            color=palette.text_secondary
        )

        # Action buttons
        reset_button = ft.IconButton(
            icon=icons.RESTORE,
            tooltip="Reset to defaults",
            on_click=self._handle_reset_defaults,
            icon_color=palette.text_secondary
        )

        import_button = ft.IconButton(
            icon=icons.UPLOAD,
            tooltip="Import configuration",
            on_click=self._handle_import_config,
            icon_color=palette.text_secondary
        )

        export_button = ft.IconButton(
            icon=icons.DOWNLOAD,
            tooltip="Export configuration",
            on_click=self._handle_export_config,
            icon_color=palette.text_secondary
        )

        # Header layout
        header_content = ft.Row(
            controls=[
                ft.Column(
                    controls=[title, subtitle],
                    spacing=spacing.xs,
                    expand=True
                ),
                ft.Row(
                    controls=[reset_button, import_button, export_button],
                    spacing=spacing.sm
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.START
        )

        self._header_container = ft.Container(
            content=header_content,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(8, 10, 12, 14)
        )

        return self._header_container

    def _create_tabs(self) -> ft.Container:
        """Create the main tabs container."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create tabs
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(
                    text="Architecture",
                    icon=ft.Icons.ARCHITECTURE,
                    content=self._create_architecture_tab()
                ),
                ft.Tab(
                    text="Training",
                    icon=ft.Icons.SCHOOL,
                    content=self._create_training_tab()
                ),
                ft.Tab(
                    text="Quantization",
                    icon=ft.Icons.COMPRESS,
                    content=self._create_quantization_tab()
                ),
                ft.Tab(
                    text="Checkpoints",
                    icon=ft.Icons.SAVE,
                    content=self._create_checkpoints_tab()
                ),
                ft.Tab(
                    text="Resources",
                    icon=ft.Icons.MEMORY,
                    content=self._create_resources_tab()
                )
            ],
            on_change=self._handle_tab_change
        )

        self._tabs_container = ft.Container(
            content=tabs,
            expand=True,
            bgcolor=palette.surface,
            border_radius=self.get_responsive_value(8, 10, 12, 14),
            padding=ft.padding.all(spacing.md)
        )

        return self._tabs_container

    def _create_architecture_tab(self) -> ft.Container:
        """Create the architecture defaults tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Architecture type selector
        architecture_type_section = self._create_settings_section(
            "Architecture Type",
            [
                self._create_dropdown_setting(
                    "architecture_type",
                    "Model Architecture",
                    "Select the default model architecture type",
                    [
                        ft.dropdown.Option("transformer", "Transformer"),
                        ft.dropdown.Option("llama", "LLaMA"),
                        ft.dropdown.Option("mistral", "Mistral"),
                        ft.dropdown.Option("custom", "Custom")
                    ],
                    self._current_defaults.architecture.architecture_type.value
                )
            ]
        )

        # Model size selector
        size_section = self._create_settings_section(
            "Model Size",
            [
                self._create_radio_group_setting(
                    "size_category",
                    "Default Model Size",
                    "Choose the default model parameter count",
                    [
                        ("1B", "Small (1B parameters)", "Lightweight model for basic tasks"),
                        ("3B", "Medium (3B parameters)", "Balanced model for general use"),
                        ("7B", "Large (7B parameters)", "High-performance model for complex tasks")
                    ],
                    self._current_defaults.architecture.size_category.value
                )
            ]
        )

        # Advanced architecture settings
        advanced_section = self._create_collapsible_section(
            "Advanced Architecture Settings",
            [
                self._create_number_setting(
                    "num_layers",
                    "Number of Layers",
                    "Default number of transformer layers",
                    self._current_defaults.architecture.num_layers,
                    min_value=1,
                    max_value=128
                ),
                self._create_number_setting(
                    "hidden_size",
                    "Hidden Size",
                    "Default hidden dimension size",
                    self._current_defaults.architecture.hidden_size,
                    min_value=256,
                    max_value=8192,
                    step=256
                ),
                self._create_number_setting(
                    "num_attention_heads",
                    "Attention Heads",
                    "Default number of attention heads",
                    self._current_defaults.architecture.num_attention_heads,
                    min_value=1,
                    max_value=64
                ),
                self._create_number_setting(
                    "vocab_size",
                    "Vocabulary Size",
                    "Default vocabulary size",
                    self._current_defaults.architecture.vocab_size,
                    min_value=1000,
                    max_value=100000,
                    step=1000
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[architecture_type_section, size_section, advanced_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_training_tab(self) -> ft.Container:
        """Create the training defaults tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Basic training settings
        basic_section = self._create_settings_section(
            "Basic Training Parameters",
            [
                self._create_number_setting(
                    "learning_rate",
                    "Learning Rate",
                    "Default learning rate for training",
                    self._current_defaults.training.learning_rate,
                    min_value=1e-6,
                    max_value=1e-1,
                    step=1e-5,
                    format_type="scientific"
                ),
                self._create_number_setting(
                    "batch_size",
                    "Batch Size",
                    "Default training batch size",
                    self._current_defaults.training.batch_size,
                    min_value=1,
                    max_value=128
                ),
                self._create_number_setting(
                    "max_epochs",
                    "Maximum Epochs",
                    "Default maximum number of training epochs",
                    self._current_defaults.training.max_epochs,
                    min_value=1,
                    max_value=1000
                ),
                self._create_number_setting(
                    "warmup_steps",
                    "Warmup Steps",
                    "Default number of warmup steps",
                    self._current_defaults.training.warmup_steps,
                    min_value=0,
                    max_value=10000
                )
            ]
        )

        # Optimization settings
        optimization_section = self._create_settings_section(
            "Optimization Parameters",
            [
                self._create_number_setting(
                    "weight_decay",
                    "Weight Decay",
                    "Default weight decay for regularization",
                    self._current_defaults.training.weight_decay,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.001
                ),
                self._create_number_setting(
                    "max_grad_norm",
                    "Gradient Clipping",
                    "Default maximum gradient norm for clipping",
                    self._current_defaults.training.max_grad_norm,
                    min_value=0.1,
                    max_value=10.0,
                    step=0.1
                ),
                self._create_dropdown_setting(
                    "lr_scheduler_type",
                    "Learning Rate Scheduler",
                    "Default learning rate scheduler type",
                    [
                        ft.dropdown.Option("linear", "Linear"),
                        ft.dropdown.Option("cosine", "Cosine"),
                        ft.dropdown.Option("polynomial", "Polynomial"),
                        ft.dropdown.Option("constant", "Constant")
                    ],
                    self._current_defaults.training.lr_scheduler_type
                )
            ]
        )

        # Advanced training settings
        advanced_section = self._create_collapsible_section(
            "Advanced Training Settings",
            [
                self._create_number_setting(
                    "gradient_accumulation_steps",
                    "Gradient Accumulation Steps",
                    "Default gradient accumulation steps",
                    self._current_defaults.training.gradient_accumulation_steps,
                    min_value=1,
                    max_value=64
                ),
                self._create_number_setting(
                    "save_steps",
                    "Save Steps",
                    "Default interval for saving checkpoints",
                    self._current_defaults.training.save_steps,
                    min_value=10,
                    max_value=10000,
                    step=10
                ),
                self._create_number_setting(
                    "eval_steps",
                    "Evaluation Steps",
                    "Default interval for evaluation",
                    self._current_defaults.training.eval_steps,
                    min_value=10,
                    max_value=10000,
                    step=10
                ),
                self._create_switch_setting(
                    "fp16",
                    "Mixed Precision (FP16)",
                    "Enable mixed precision training by default",
                    self._current_defaults.training.fp16
                ),
                self._create_switch_setting(
                    "load_best_model_at_end",
                    "Load Best Model at End",
                    "Load the best model checkpoint at training end",
                    self._current_defaults.training.load_best_model_at_end
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[basic_section, optimization_section, advanced_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_quantization_tab(self) -> ft.Container:
        """Create the quantization defaults tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Quantization type selector
        quantization_section = self._create_settings_section(
            "Quantization Settings",
            [
                self._create_radio_group_setting(
                    "default_quantization",
                    "Default Quantization Type",
                    "Choose the default quantization precision",
                    [
                        ("FP32", "Full Precision (FP32)", "Highest accuracy, largest size"),
                        ("FP16", "Half Precision (FP16)", "Good balance of accuracy and size"),
                        ("INT8", "8-bit Integer (INT8)", "Moderate compression with good accuracy"),
                        ("INT4", "4-bit Integer (INT4)", "Maximum compression, may reduce accuracy")
                    ],
                    self._current_defaults.quantization.default_quantization.value
                )
            ]
        )

        # Quantization options
        options_section = self._create_settings_section(
            "Quantization Options",
            [
                self._create_switch_setting(
                    "enable_dynamic_quantization",
                    "Dynamic Quantization",
                    "Enable dynamic quantization during inference",
                    self._current_defaults.quantization.enable_dynamic_quantization
                ),
                self._create_switch_setting(
                    "quantize_embeddings",
                    "Quantize Embeddings",
                    "Apply quantization to embedding layers",
                    self._current_defaults.quantization.quantize_embeddings
                ),
                self._create_switch_setting(
                    "quantize_attention",
                    "Quantize Attention",
                    "Apply quantization to attention layers",
                    self._current_defaults.quantization.quantize_attention
                ),
                self._create_switch_setting(
                    "quantize_feedforward",
                    "Quantize Feed-Forward",
                    "Apply quantization to feed-forward layers",
                    self._current_defaults.quantization.quantize_feedforward
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[quantization_section, options_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_checkpoints_tab(self) -> ft.Container:
        """Create the checkpoints defaults tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Checkpoint settings
        checkpoint_section = self._create_settings_section(
            "Checkpoint Configuration",
            [
                self._create_switch_setting(
                    "enable_checkpointing",
                    "Enable Checkpointing",
                    "Automatically save model checkpoints during training",
                    self._current_defaults.checkpoints.enable_checkpointing
                ),
                self._create_number_setting(
                    "checkpoint_interval",
                    "Checkpoint Interval",
                    "Default steps between checkpoint saves",
                    self._current_defaults.checkpoints.checkpoint_interval,
                    min_value=10,
                    max_value=10000,
                    step=10
                ),
                self._create_switch_setting(
                    "save_best_only",
                    "Save Best Only",
                    "Only save checkpoints that improve validation metrics",
                    self._current_defaults.checkpoints.save_best_only
                ),
                self._create_number_setting(
                    "max_checkpoints",
                    "Maximum Checkpoints",
                    "Maximum number of checkpoints to keep",
                    self._current_defaults.checkpoints.max_checkpoints,
                    min_value=1,
                    max_value=20
                )
            ]
        )

        # Early stopping settings
        early_stopping_section = self._create_settings_section(
            "Early Stopping",
            [
                self._create_switch_setting(
                    "enable_early_stopping",
                    "Enable Early Stopping",
                    "Stop training when validation metrics stop improving",
                    self._current_defaults.checkpoints.enable_early_stopping
                ),
                self._create_number_setting(
                    "early_stopping_patience",
                    "Early Stopping Patience",
                    "Number of epochs to wait before stopping",
                    self._current_defaults.checkpoints.early_stopping_patience,
                    min_value=1,
                    max_value=50
                ),
                self._create_number_setting(
                    "early_stopping_threshold",
                    "Early Stopping Threshold",
                    "Minimum improvement threshold",
                    self._current_defaults.checkpoints.early_stopping_threshold,
                    min_value=0.0001,
                    max_value=0.1,
                    step=0.0001,
                    format_type="scientific"
                )
            ]
        )

        # Logging settings
        logging_section = self._create_settings_section(
            "Training Logging",
            [
                self._create_switch_setting(
                    "enable_tensorboard",
                    "Enable TensorBoard",
                    "Log training metrics to TensorBoard",
                    self._current_defaults.checkpoints.enable_tensorboard
                ),
                self._create_switch_setting(
                    "enable_wandb",
                    "Enable Weights & Biases",
                    "Log training metrics to Weights & Biases",
                    self._current_defaults.checkpoints.enable_wandb
                ),
                self._create_text_setting(
                    "wandb_project",
                    "W&B Project Name",
                    "Default Weights & Biases project name",
                    self._current_defaults.checkpoints.wandb_project
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[checkpoint_section, early_stopping_section, logging_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_resources_tab(self) -> ft.Container:
        """Create the resources defaults tab."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Performance profile
        profile_section = self._create_settings_section(
            "Performance Profile",
            [
                self._create_radio_group_setting(
                    "performance_profile",
                    "Default Performance Profile",
                    "Choose the default resource allocation strategy",
                    [
                        ("power_saver", "Power Saver", "Minimize power consumption"),
                        ("balanced", "Balanced", "Balance performance and efficiency"),
                        ("performance", "Performance", "Maximize training speed"),
                        ("maximum", "Maximum", "Use all available resources")
                    ],
                    self._current_defaults.resources.performance_profile.value
                )
            ]
        )

        # Resource limits
        limits_section = self._create_settings_section(
            "Resource Limits",
            [
                self._create_number_setting(
                    "max_memory_gb",
                    "Maximum Memory (GB)",
                    "Default maximum memory allocation",
                    self._current_defaults.resources.max_memory_gb,
                    min_value=1.0,
                    max_value=128.0,
                    step=0.5
                ),
                self._create_number_setting(
                    "cpu_threads",
                    "CPU Threads",
                    "Default number of CPU threads to use",
                    self._current_defaults.resources.cpu_threads,
                    min_value=1,
                    max_value=32
                ),
                self._create_switch_setting(
                    "gpu_enabled",
                    "GPU Acceleration",
                    "Enable GPU acceleration by default",
                    self._current_defaults.resources.gpu_enabled
                ),
                self._create_switch_setting(
                    "enable_mixed_precision",
                    "Mixed Precision",
                    "Enable mixed precision training for better performance",
                    self._current_defaults.resources.enable_mixed_precision
                )
            ]
        )

        # Data loading settings
        dataloader_section = self._create_settings_section(
            "Data Loading",
            [
                self._create_number_setting(
                    "dataloader_num_workers",
                    "DataLoader Workers",
                    "Default number of data loading workers",
                    self._current_defaults.resources.dataloader_num_workers,
                    min_value=0,
                    max_value=16
                ),
                self._create_switch_setting(
                    "pin_memory",
                    "Pin Memory",
                    "Pin memory for faster GPU transfers",
                    self._current_defaults.resources.pin_memory
                ),
                self._create_number_setting(
                    "prefetch_factor",
                    "Prefetch Factor",
                    "Number of batches to prefetch",
                    self._current_defaults.resources.prefetch_factor,
                    min_value=1,
                    max_value=8
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[profile_section, limits_section, dataloader_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_validation_panel(self) -> ft.Container:
        """Create the validation panel for showing errors and warnings."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._validation_panel = ft.Container(
            content=ft.Column(
                controls=[],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.error_container,
            border_radius=self.get_responsive_value(6, 8, 10, 12),
            visible=False
        )

        return self._validation_panel

    def _create_action_bar(self) -> ft.Container:
        """Create the action bar with save, cancel, and reset buttons."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Save button
        save_button = ft.ElevatedButton(
            text="Save Defaults",
            icon=icons.SAVE,
            on_click=self._handle_save_defaults,
            style=ft.ButtonStyle(
                bgcolor=palette.primary,
                color=palette.text_primary
            )
        )

        # Cancel button
        cancel_button = ft.TextButton(
            text="Cancel",
            icon=icons.CANCEL,
            on_click=self._handle_cancel_changes,
            style=ft.ButtonStyle(
                color=palette.text_secondary
            )
        )

        # Reset button
        reset_button = ft.TextButton(
            text="Reset to Defaults",
            icon=icons.RESTORE,
            on_click=self._handle_reset_defaults,
            style=ft.ButtonStyle(
                color=palette.text_secondary
            )
        )

        # Action bar layout
        action_content = ft.Row(
            controls=[
                ft.Row(
                    controls=[reset_button],
                    expand=True
                ),
                ft.Row(
                    controls=[cancel_button, save_button],
                    spacing=spacing.sm
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        self._action_bar = ft.Container(
            content=action_content,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(8, 10, 12, 14)
        )

        return self._action_bar

    def _create_status_bar(self) -> ft.Container:
        """Create the status bar for showing save status and validation info."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Status text
        status_text = ft.Text(
            "Ready",
            size=typography.body_small[0],
            color=palette.text_secondary
        )

        # Unsaved changes indicator
        unsaved_indicator = ft.Row(
            controls=[
                ft.Icon(
                    icons.CIRCLE,
                    size=8,
                    color=palette.warning
                ),
                ft.Text(
                    "Unsaved changes",
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ],
            spacing=spacing.xs,
            visible=False
        )

        # Status bar layout
        status_content = ft.Row(
            controls=[
                status_text,
                unsaved_indicator
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        self._status_bar = ft.Container(
            content=status_content,
            padding=ft.padding.symmetric(
                horizontal=spacing.lg,
                vertical=spacing.sm
            ),
            bgcolor=palette.surface,
            border_radius=self.get_responsive_value(6, 8, 10, 12)
        )

        return self._status_bar

    def _create_settings_section(self, title: str, controls: List[ft.Control]) -> ft.Container:
        """Create a settings section with title and controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Section title
        section_title = ft.Text(
            title,
            size=typography.h4[0],
            weight=ft.FontWeight.W_600,
            color=palette.text_primary
        )

        # Section content
        section_content = ft.Column(
            controls=[section_title] + controls,
            spacing=spacing.md
        )

        return ft.Container(
            content=section_content,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(8, 10, 12, 14)
        )

    def _create_collapsible_section(self, title: str, controls: List[ft.Control]) -> ft.Container:
        """Create a collapsible settings section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Collapsible content
        collapsible_content = ft.Column(
            controls=controls,
            spacing=spacing.md,
            visible=False
        )

        # Toggle function
        def toggle_section(e):
            collapsible_content.visible = not collapsible_content.visible
            toggle_icon.icon = icons.EXPAND_LESS if collapsible_content.visible else icons.EXPAND_MORE
            self.update()

        # Toggle icon
        toggle_icon = ft.IconButton(
            icon=icons.EXPAND_MORE,
            on_click=toggle_section,
            icon_color=palette.text_secondary
        )

        # Section header
        section_header = ft.Row(
            controls=[
                ft.Text(
                    title,
                    size=typography.h4[0],
                    weight=ft.FontWeight.W_600,
                    color=palette.text_primary,
                    expand=True
                ),
                toggle_icon
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        # Section content
        section_content = ft.Column(
            controls=[section_header, collapsible_content],
            spacing=spacing.sm
        )

        return ft.Container(
            content=section_content,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(8, 10, 12, 14)
        )

    def _create_dropdown_setting(self, key: str, label: str, hint: str,
                                options: List[ft.dropdown.Option], value: str) -> ft.Container:
        """Create a dropdown setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label
        label_text = ft.Text(
            label,
            size=typography.body_medium[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary
        )

        # Hint text
        hint_text = ft.Text(
            hint,
            size=typography.body_small[0],
            color=palette.text_secondary
        )

        # Dropdown
        dropdown = ft.Dropdown(
            options=options,
            value=value,
            on_change=lambda e: self._handle_setting_change(key, e.control.value),
            bgcolor=palette.surface,
            border_color=palette.outline,
            text_style=ft.TextStyle(color=palette.text_primary)
        )

        self._form_controls[key] = dropdown

        return ft.Container(
            content=ft.Column(
                controls=[label_text, hint_text, dropdown],
                spacing=spacing.xs
            ),
            padding=ft.padding.all(spacing.sm)
        )

    def _create_radio_group_setting(self, key: str, label: str, hint: str,
                                   options: List[Tuple[str, str, str]], value: str) -> ft.Container:
        """Create a radio group setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label
        label_text = ft.Text(
            label,
            size=typography.body_medium[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary
        )

        # Hint text
        hint_text = ft.Text(
            hint,
            size=typography.body_small[0],
            color=palette.text_secondary
        )

        # Radio buttons
        radio_buttons = []
        for option_value, option_label, option_description in options:
            radio_button = ft.RadioListTile(
                value=option_value,
                title=ft.Text(option_label, color=palette.text_primary),
                subtitle=ft.Text(option_description, color=palette.text_secondary),
                group_value=value,
                on_change=lambda e: self._handle_setting_change(key, e.control.value)
            )
            radio_buttons.append(radio_button)

        # Store reference to radio group
        self._form_controls[key] = radio_buttons

        return ft.Container(
            content=ft.Column(
                controls=[label_text, hint_text] + radio_buttons,
                spacing=spacing.xs
            ),
            padding=ft.padding.all(spacing.sm)
        )

    def _create_number_setting(self, key: str, label: str, hint: str, value: float,
                              min_value: float = None, max_value: float = None,
                              step: float = 1, format_type: str = "decimal") -> ft.Container:
        """Create a number setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label
        label_text = ft.Text(
            label,
            size=typography.body_medium[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary
        )

        # Hint text
        hint_text = ft.Text(
            hint,
            size=typography.body_small[0],
            color=palette.text_secondary
        )

        # Number input
        if format_type == "scientific":
            value_str = f"{value:.2e}"
        else:
            value_str = str(value)

        number_input = ft.TextField(
            value=value_str,
            on_change=lambda e: self._handle_number_change(key, e.control.value, format_type),
            bgcolor=palette.surface,
            border_color=palette.outline,
            text_style=ft.TextStyle(color=palette.text_primary),
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self._form_controls[key] = number_input

        return ft.Container(
            content=ft.Column(
                controls=[label_text, hint_text, number_input],
                spacing=spacing.xs
            ),
            padding=ft.padding.all(spacing.sm)
        )

    def _create_switch_setting(self, key: str, label: str, hint: str, value: bool) -> ft.Container:
        """Create a switch setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Switch control
        switch = ft.Switch(
            value=value,
            on_change=lambda e: self._handle_setting_change(key, e.control.value),
            active_color=palette.primary
        )

        # Label and hint
        label_text = ft.Text(
            label,
            size=typography.body_medium[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary
        )

        hint_text = ft.Text(
            hint,
            size=typography.body_small[0],
            color=palette.text_secondary
        )

        self._form_controls[key] = switch

        # Layout
        content = ft.Row(
            controls=[
                ft.Column(
                    controls=[label_text, hint_text],
                    spacing=spacing.xs,
                    expand=True
                ),
                switch
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.sm)
        )

    def _create_text_setting(self, key: str, label: str, hint: str, value: str) -> ft.Container:
        """Create a text setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label
        label_text = ft.Text(
            label,
            size=typography.body_medium[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary
        )

        # Hint text
        hint_text = ft.Text(
            hint,
            size=typography.body_small[0],
            color=palette.text_secondary
        )

        # Text input
        text_input = ft.TextField(
            value=value,
            on_change=lambda e: self._handle_setting_change(key, e.control.value),
            bgcolor=palette.surface,
            border_color=palette.outline,
            text_style=ft.TextStyle(color=palette.text_primary)
        )

        self._form_controls[key] = text_input

        return ft.Container(
            content=ft.Column(
                controls=[label_text, hint_text, text_input],
                spacing=spacing.xs
            ),
            padding=ft.padding.all(spacing.sm)
        )

    # Event Handlers
    def _handle_tab_change(self, e) -> None:
        """Handle tab change events."""
        try:
            # Update UI if needed
            self.update()
        except Exception as ex:
            logger.error(f"Error handling tab change: {ex}")

    def _handle_setting_change(self, key: str, value: Any) -> None:
        """Handle setting value changes."""
        try:
            # Update the current defaults
            self._update_setting_value(key, value)

            # Mark as having unsaved changes
            self._has_unsaved_changes = True
            self._update_status_bar()

            # Validate the change
            self._validate_setting(key, value)

            # Trigger callback if provided
            if self._on_defaults_changed:
                self._on_defaults_changed(self._current_defaults)

            # Auto-save if enabled
            if self._config.enable_auto_save:
                self._schedule_auto_save()

        except Exception as ex:
            logger.error(f"Error handling setting change for {key}: {ex}")

    def _handle_number_change(self, key: str, value_str: str, format_type: str) -> None:
        """Handle number input changes with validation."""
        try:
            if format_type == "scientific":
                value = float(value_str)
            else:
                value = float(value_str) if '.' in value_str else int(value_str)

            self._handle_setting_change(key, value)

        except ValueError:
            # Invalid number format - show validation error
            self._validation_errors[key] = f"Invalid number format: {value_str}"
            self._update_validation_panel()

    def _handle_save_defaults(self, e) -> None:
        """Handle save defaults button click."""
        try:
            self._is_saving = True
            self._update_status_bar()

            # Validate all settings
            if not self._validate_all_settings():
                self._is_saving = False
                self._update_status_bar()
                return

            # Save the defaults
            self._save_defaults()

            # Update state
            self._original_defaults = ModelDefaultsData(**asdict(self._current_defaults))
            self._has_unsaved_changes = False
            self._is_saving = False

            # Update UI
            self._update_status_bar()

            # Trigger callback
            if self._on_config_saved:
                self._on_config_saved(self._current_defaults)

        except Exception as ex:
            logger.error(f"Error saving defaults: {ex}")
            self._is_saving = False
            self._update_status_bar()

    def _handle_cancel_changes(self, e) -> None:
        """Handle cancel changes button click."""
        try:
            # Restore original defaults
            self._current_defaults = ModelDefaultsData(**asdict(self._original_defaults))

            # Update form controls
            self._update_form_controls()

            # Clear unsaved changes
            self._has_unsaved_changes = False
            self._validation_errors.clear()

            # Update UI
            self._update_status_bar()
            self._update_validation_panel()

        except Exception as ex:
            logger.error(f"Error canceling changes: {ex}")

    def _handle_reset_defaults(self, e) -> None:
        """Handle reset to defaults button click."""
        try:
            # Reset to factory defaults
            self._current_defaults = ModelDefaultsData()

            # Update form controls
            self._update_form_controls()

            # Mark as having changes
            self._has_unsaved_changes = True
            self._validation_errors.clear()

            # Update UI
            self._update_status_bar()
            self._update_validation_panel()

            # Trigger callback
            if self._on_defaults_changed:
                self._on_defaults_changed(self._current_defaults)

        except Exception as ex:
            logger.error(f"Error resetting defaults: {ex}")

    def _handle_import_config(self, e) -> None:
        """Handle import configuration button click."""
        try:
            # TODO: Implement file picker for importing configuration
            logger.info("Import configuration requested")

        except Exception as ex:
            logger.error(f"Error importing configuration: {ex}")

    def _handle_export_config(self, e) -> None:
        """Handle export configuration button click."""
        try:
            # TODO: Implement file picker for exporting configuration
            logger.info("Export configuration requested")

        except Exception as ex:
            logger.error(f"Error exporting configuration: {ex}")

    # Utility Methods
    def _update_setting_value(self, key: str, value: Any) -> None:
        """Update a setting value in the current defaults."""
        try:
            # Parse the key path (e.g., "architecture.num_layers")
            parts = key.split('.')

            if len(parts) == 1:
                # Direct attribute
                if hasattr(self._current_defaults, key):
                    setattr(self._current_defaults, key, value)
            elif len(parts) == 2:
                # Nested attribute
                section_name, attr_name = parts
                section = getattr(self._current_defaults, section_name, None)
                if section and hasattr(section, attr_name):
                    setattr(section, attr_name, value)

        except Exception as ex:
            logger.error(f"Error updating setting value {key}: {ex}")

    def _validate_setting(self, key: str, value: Any) -> bool:
        """Validate a single setting value."""
        try:
            # Clear previous validation error
            if key in self._validation_errors:
                del self._validation_errors[key]

            # Perform validation based on setting type
            is_valid = True

            # Add specific validation logic here
            # For now, just basic type checking

            self._update_validation_panel()
            return is_valid

        except Exception as ex:
            logger.error(f"Error validating setting {key}: {ex}")
            return False

    def _validate_all_settings(self) -> bool:
        """Validate all current settings."""
        try:
            self._validation_errors.clear()

            # Validate architecture settings
            if self._current_defaults.architecture.num_layers < 1:
                self._validation_errors["num_layers"] = "Number of layers must be at least 1"

            if self._current_defaults.architecture.hidden_size < 256:
                self._validation_errors["hidden_size"] = "Hidden size must be at least 256"

            # Validate training settings
            if self._current_defaults.training.learning_rate <= 0:
                self._validation_errors["learning_rate"] = "Learning rate must be positive"

            if self._current_defaults.training.batch_size < 1:
                self._validation_errors["batch_size"] = "Batch size must be at least 1"

            # Update validation panel
            self._update_validation_panel()

            return len(self._validation_errors) == 0

        except Exception as ex:
            logger.error(f"Error validating all settings: {ex}")
            return False

    def _update_form_controls(self) -> None:
        """Update form controls with current defaults values."""
        try:
            # Update architecture controls
            if "architecture_type" in self._form_controls:
                self._form_controls["architecture_type"].value = self._current_defaults.architecture.architecture_type.value

            if "size_category" in self._form_controls:
                for radio in self._form_controls["size_category"]:
                    radio.group_value = self._current_defaults.architecture.size_category.value

            # Update training controls
            if "learning_rate" in self._form_controls:
                self._form_controls["learning_rate"].value = f"{self._current_defaults.training.learning_rate:.2e}"

            if "batch_size" in self._form_controls:
                self._form_controls["batch_size"].value = str(self._current_defaults.training.batch_size)

            # Update other controls as needed
            self.update()

        except Exception as ex:
            logger.error(f"Error updating form controls: {ex}")

    def _update_status_bar(self) -> None:
        """Update the status bar display."""
        try:
            if not self._status_bar:
                return

            # Get status components
            status_content = self._status_bar.content
            if isinstance(status_content, ft.Row) and len(status_content.controls) >= 2:
                status_text = status_content.controls[0]
                unsaved_indicator = status_content.controls[1]

                # Update status text
                if self._is_saving:
                    status_text.value = "Saving..."
                elif self._is_loading:
                    status_text.value = "Loading..."
                elif self._has_unsaved_changes:
                    status_text.value = "Modified"
                else:
                    status_text.value = "Ready"

                # Update unsaved changes indicator
                unsaved_indicator.visible = self._has_unsaved_changes

                self.update()

        except Exception as ex:
            logger.error(f"Error updating status bar: {ex}")

    def _update_validation_panel(self) -> None:
        """Update the validation panel with current errors."""
        try:
            if not self._validation_panel:
                return

            # Clear existing errors
            self._validation_panel.content.controls.clear()

            # Add current errors
            if self._validation_errors:
                palette = self.get_palette()
                typography = self.get_typography()
                spacing = self.get_spacing()
                icons = self.get_icons()

                for key, error_message in self._validation_errors.items():
                    error_row = ft.Row(
                        controls=[
                            ft.Icon(
                                icons.ERROR,
                                size=16,
                                color=palette.error
                            ),
                            ft.Text(
                                error_message,
                                size=typography.body_small[0],
                                color=palette.error
                            )
                        ],
                        spacing=spacing.xs
                    )
                    self._validation_panel.content.controls.append(error_row)

                self._validation_panel.visible = True
            else:
                self._validation_panel.visible = False

            self.update()

        except Exception as ex:
            logger.error(f"Error updating validation panel: {ex}")

    def _save_defaults(self) -> None:
        """Save the current defaults to persistent storage."""
        try:
            # TODO: Implement actual saving to database/file
            # For now, just log the action
            logger.info("Saving model defaults configuration")

            # Convert to dictionary for serialization
            defaults_dict = asdict(self._current_defaults)

            # Save to file (example implementation)
            config_path = Path("./config/model_defaults.json")
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, 'w') as f:
                json.dump(defaults_dict, f, indent=2, default=str)

            logger.info(f"Model defaults saved to {config_path}")

        except Exception as ex:
            logger.error(f"Error saving defaults: {ex}")
            raise

    def _load_defaults(self) -> None:
        """Load defaults from persistent storage."""
        try:
            # TODO: Implement actual loading from database/file
            # For now, just log the action
            logger.info("Loading model defaults configuration")

            config_path = Path("./config/model_defaults.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    defaults_dict = json.load(f)

                # Convert back to dataclass
                # This is a simplified implementation
                self._current_defaults = ModelDefaultsData()
                self._original_defaults = ModelDefaultsData(**asdict(self._current_defaults))

                logger.info(f"Model defaults loaded from {config_path}")
            else:
                logger.info("No saved defaults found, using factory defaults")

        except Exception as ex:
            logger.error(f"Error loading defaults: {ex}")

    def _schedule_auto_save(self) -> None:
        """Schedule auto-save if enabled."""
        try:
            if not self._config.enable_auto_save:
                return

            # Cancel existing timer
            if self._auto_save_timer:
                # TODO: Cancel timer implementation
                pass

            # Schedule new auto-save
            # TODO: Implement timer for auto-save
            logger.debug("Auto-save scheduled")

        except Exception as ex:
            logger.error(f"Error scheduling auto-save: {ex}")

    # Public API Methods
    def get_current_defaults(self) -> ModelDefaultsData:
        """Get the current defaults configuration."""
        return self._current_defaults

    def set_defaults(self, defaults: ModelDefaultsData) -> None:
        """Set the defaults configuration."""
        try:
            self._current_defaults = defaults
            self._update_form_controls()
            self._has_unsaved_changes = True
            self._update_status_bar()

            if self._on_defaults_changed:
                self._on_defaults_changed(self._current_defaults)

        except Exception as ex:
            logger.error(f"Error setting defaults: {ex}")

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self._has_unsaved_changes

    def save_configuration(self) -> bool:
        """Save the current configuration."""
        try:
            if self._validate_all_settings():
                self._save_defaults()
                self._has_unsaved_changes = False
                self._update_status_bar()
                return True
            return False
        except Exception as ex:
            logger.error(f"Error saving configuration: {ex}")
            return False

    def reset_to_defaults(self) -> None:
        """Reset all settings to factory defaults."""
        try:
            self._current_defaults = ModelDefaultsData()
            self._update_form_controls()
            self._has_unsaved_changes = True
            self._validation_errors.clear()
            self._update_status_bar()
            self._update_validation_panel()

            if self._on_defaults_changed:
                self._on_defaults_changed(self._current_defaults)

        except Exception as ex:
            logger.error(f"Error resetting to defaults: {ex}")

    def get_validation_errors(self) -> Dict[str, str]:
        """Get current validation errors."""
        return self._validation_errors.copy()

    def is_valid(self) -> bool:
        """Check if current configuration is valid."""
        return self._validate_all_settings()


# Helper functions for creating the UI
def create_model_defaults_ui(config: Optional[ModelDefaultsConfig] = None,
                           **kwargs) -> ModelDefaultsUI:
    """
    Create a model defaults UI instance.

    Args:
        config: Optional configuration for the UI
        **kwargs: Additional arguments for the UI

    Returns:
        ModelDefaultsUI instance
    """
    return ModelDefaultsUI(config=config, **kwargs)


def get_default_model_configuration() -> ModelDefaultsData:
    """
    Get the default model configuration.

    Returns:
        Default ModelDefaultsData instance
    """
    return ModelDefaultsData()
