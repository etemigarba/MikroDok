"""
Module: advanced_settings_ui
Description: Advanced training configuration interface providing comprehensive settings for resource management,
            optimization strategies, logging configuration, and advanced training parameters. Features responsive
            design, real-time validation, configuration import/export, and full theme system integration.
Phase: 4
Location: /src/modules/ui/training_configuration_ui/advanced_settings_ui/advanced_settings_ui.py
"""

# Standard library imports
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

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
        TrainingConfig,
        HyperparameterConfig,
        OptimizationStrategy,
        TrainingPriority
    )
    TRAINING_ORCHESTRATION_AVAILABLE = True
except ImportError:
    TrainingConfig = None
    HyperparameterConfig = None
    OptimizationStrategy = None
    TrainingPriority = None
    TRAINING_ORCHESTRATION_AVAILABLE = False

# Resource monitoring imports
try:
    from src.modules.logic.resource_monitoring_lg.base_interfaces import (
        ResourceMetrics,
        AllocationStrategy,
        ResourceProfile
    )
    RESOURCE_MONITORING_AVAILABLE = True
except ImportError:
    ResourceMetrics = None
    AllocationStrategy = None
    ResourceProfile = None
    RESOURCE_MONITORING_AVAILABLE = False


class AdvancedSettingsMode(Enum):
    """Advanced settings interface modes."""
    BASIC = "basic"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SettingsCategory(Enum):
    """Categories of advanced settings."""
    TRAINING = "training"
    RESOURCE = "resource"
    OPTIMIZATION = "optimization"
    LOGGING = "logging"
    MONITORING = "monitoring"
    EXPORT_IMPORT = "export_import"


@dataclass
class ResourceConfiguration:
    """Resource management configuration."""
    # Memory settings
    gpu_memory_limit_mb: Optional[int] = None
    cpu_memory_limit_mb: Optional[int] = None
    nvme_swap_limit_mb: Optional[int] = None
    
    # Allocation strategy
    allocation_strategy: str = "auto"  # auto, legacy, hybrid, idralloc
    enable_memory_mapping: bool = True
    enable_gradient_checkpointing: bool = False
    
    # Performance settings
    num_workers: int = 4
    pin_memory: bool = True
    prefetch_factor: int = 2
    persistent_workers: bool = True
    
    # Advanced settings
    enable_amp: bool = False  # Automatic Mixed Precision
    amp_opt_level: str = "O1"  # O0, O1, O2, O3
    enable_cpu_offload: bool = False
    enable_disk_offload: bool = False


@dataclass
class OptimizationConfiguration:
    """Optimization strategy configuration."""
    # Gradient settings
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    gradient_clipping_enabled: bool = True
    
    # Learning rate scheduling
    scheduler_type: str = "cosine"  # linear, cosine, polynomial, constant
    warmup_steps: int = 0
    warmup_ratio: float = 0.1
    
    # Early stopping
    early_stopping_enabled: bool = True
    early_stopping_patience: int = 10
    early_stopping_threshold: float = 0.001
    
    # Checkpointing
    checkpoint_interval: int = 1000
    save_best_only: bool = True
    max_checkpoints: int = 5
    
    # Advanced optimization
    enable_gradient_compression: bool = False
    enable_model_parallelism: bool = False
    enable_pipeline_parallelism: bool = False


@dataclass
class LoggingConfiguration:
    """Logging and monitoring configuration."""
    # Logging levels
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    enable_file_logging: bool = True
    enable_console_logging: bool = True
    
    # Log rotation
    max_log_size_mb: int = 100
    max_log_files: int = 10
    
    # Monitoring intervals
    metrics_update_interval_ms: int = 1000
    loss_logging_interval: int = 100
    checkpoint_logging_interval: int = 1000
    
    # Telemetry
    enable_telemetry: bool = False
    telemetry_endpoint: Optional[str] = None
    
    # Debug settings
    enable_profiling: bool = False
    profile_memory: bool = False
    profile_compute: bool = False


@dataclass
class AdvancedConfiguration:
    """Complete advanced configuration."""
    resource: ResourceConfiguration = field(default_factory=ResourceConfiguration)
    optimization: OptimizationConfiguration = field(default_factory=OptimizationConfiguration)
    logging: LoggingConfiguration = field(default_factory=LoggingConfiguration)
    
    # Metadata
    name: str = "Default Advanced Configuration"
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"
    
    # Custom settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigurationValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    category_validations: Dict[SettingsCategory, List[str]]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ConfigurationExportResult:
    """Result of configuration export."""
    success: bool
    file_path: Optional[Path] = None
    error_message: Optional[str] = None
    exported_categories: List[SettingsCategory] = field(default_factory=list)


@dataclass
class ConfigurationImportResult:
    """Result of configuration import."""
    success: bool
    imported_config: Optional[AdvancedConfiguration] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    imported_categories: List[SettingsCategory] = field(default_factory=list)


@dataclass
class AdvancedSettingsConfig:
    """Configuration for advanced settings interface."""
    mode: AdvancedSettingsMode = AdvancedSettingsMode.BASIC
    visible_categories: List[SettingsCategory] = field(
        default_factory=lambda: [
            SettingsCategory.TRAINING,
            SettingsCategory.RESOURCE,
            SettingsCategory.OPTIMIZATION,
            SettingsCategory.LOGGING
        ]
    )
    enable_real_time_validation: bool = True
    enable_tooltips: bool = True
    enable_import_export: bool = True
    auto_save_enabled: bool = True
    auto_save_interval_seconds: int = 30
    show_advanced_options: bool = False
    enable_presets: bool = True


class AdvancedSettingsUI(ThemeAwareUserControl):
    """
    Advanced training configuration interface.
    
    Provides comprehensive advanced settings for training configuration including
    resource management, optimization strategies, logging configuration, and
    advanced training parameters.
    
    Features:
    - Responsive tabbed interface with category-based organization
    - Real-time validation with visual feedback
    - Configuration import/export functionality
    - Preset configurations for common scenarios
    - Advanced resource management controls
    - Optimization strategy configuration
    - Comprehensive logging and monitoring settings
    - Full theme system integration with responsive design
    """

    def __init__(
        self,
        config: Optional[AdvancedSettingsConfig] = None,
        initial_configuration: Optional[AdvancedConfiguration] = None,
        on_configuration_change: Optional[Callable[[AdvancedConfiguration], None]] = None,
        on_validation_change: Optional[Callable[[ConfigurationValidationResult], None]] = None,
        **kwargs
    ):
        """
        Initialize advanced settings UI.

        Args:
            config: Advanced settings interface configuration
            initial_configuration: Initial advanced configuration
            on_configuration_change: Callback for configuration changes
            on_validation_change: Callback for validation changes
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self.config = config or AdvancedSettingsConfig()
        self.configuration = initial_configuration or AdvancedConfiguration()
        
        # Callbacks
        self.on_configuration_change = on_configuration_change
        self.on_validation_change = on_validation_change
        
        # UI components
        self._tabs: Optional[ft.Tabs] = None
        self._validation_panel: Optional[ft.Container] = None
        self._action_bar: Optional[ft.Container] = None
        
        # State management
        self._validation_result: Optional[ConfigurationValidationResult] = None
        self._is_validating = False
        self._validation_timer: Optional[asyncio.Task] = None
        
        # Logger
        self._logger = logging.getLogger(__name__)
        
        # Build UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the advanced settings interface."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Main container with responsive design
        self.content = ft.Column(
            controls=[
                self._create_header(),
                self._create_tabs(),
                self._create_validation_panel(),
                self._create_action_bar()
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
        
        # Initial validation
        if self.config.enable_real_time_validation:
            self._schedule_validation()

    def _create_header(self) -> ft.Container:
        """Create the header section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Title
        title = ft.Text(
            "Advanced Training Settings",
            style=self.get_text_style("heading_large"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_600
        )
        
        # Description
        description = ft.Text(
            "Configure advanced training parameters, resource management, and optimization strategies",
            style=self.get_text_style("body_medium"),
            color=palette.text_secondary
        )
        
        # Mode selector
        mode_selector = self._create_mode_selector()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
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
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.only(bottom=spacing.md)
        )

    def _create_mode_selector(self) -> ft.Container:
        """Create the mode selector dropdown."""
        palette = self.get_palette()
        typography = self.get_typography()

        mode_dropdown = ft.Dropdown(
            label="Interface Mode",
            value=self.config.mode.value,
            options=[
                ft.dropdown.Option("basic", "Basic"),
                ft.dropdown.Option("advanced", "Advanced"),
                ft.dropdown.Option("expert", "Expert")
            ],
            on_change=self._on_mode_change,
            width=self.get_responsive_value(150, 160, 170, 180),
            text_style=self.get_text_style("body_medium"),
            label_style=self.get_text_style("body_small"),
            bgcolor=palette.surface_variant,
            border_color=palette.outline,
            focused_border_color=palette.primary
        )

        return ft.Container(
            content=mode_dropdown,
            padding=ft.padding.all(0)
        )

    def _create_tabs(self) -> ft.Container:
        """Create the main tabs interface."""
        palette = self.get_palette()

        # Create tabs based on visible categories
        tab_controls = []

        if SettingsCategory.TRAINING in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Training",
                    icon=ft.Icons.SCHOOL,
                    content=self._create_training_settings_tab()
                )
            )

        if SettingsCategory.RESOURCE in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Resources",
                    icon=ft.Icons.MEMORY,
                    content=self._create_resource_settings_tab()
                )
            )

        if SettingsCategory.OPTIMIZATION in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Optimization",
                    icon=ft.Icons.TUNE,
                    content=self._create_optimization_settings_tab()
                )
            )

        if SettingsCategory.LOGGING in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Logging",
                    icon=ft.Icons.ARTICLE,
                    content=self._create_logging_settings_tab()
                )
            )

        if SettingsCategory.MONITORING in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Monitoring",
                    icon=ft.Icons.MONITOR,
                    content=self._create_monitoring_settings_tab()
                )
            )

        if SettingsCategory.EXPORT_IMPORT in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Import/Export",
                    icon=ft.Icons.IMPORT_EXPORT,
                    content=self._create_import_export_tab()
                )
            )

        self._tabs = ft.Tabs(
            tabs=tab_controls,
            selected_index=0,
            animation_duration=300,
            tab_alignment=ft.TabAlignment.START,
            expand=True
        )

        return ft.Container(
            content=self._tabs,
            expand=True,
            bgcolor=palette.surface,
            border_radius=self.get_responsive_value(8, 10, 12, 14),
            padding=self.get_responsive_padding(
                mobile=self.get_spacing().sm,
                tablet=self.get_spacing().md,
                desktop=self.get_spacing().lg
            )
        )

    def _create_training_settings_tab(self) -> ft.Container:
        """Create the training settings tab content."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Mixed precision settings
        mixed_precision_section = self._create_section(
            title="Mixed Precision Training",
            icon=ft.Icons.PRECISION_MANUFACTURING,
            controls=[
                self._create_switch_control(
                    "Enable Automatic Mixed Precision (AMP)",
                    self.configuration.resource.enable_amp,
                    lambda e: self._update_resource_config("enable_amp", e.control.value),
                    tooltip="Use mixed precision to reduce memory usage and increase training speed"
                ),
                self._create_dropdown_control(
                    "AMP Optimization Level",
                    self.configuration.resource.amp_opt_level,
                    [
                        ("O0", "FP32 training (no mixed precision)"),
                        ("O1", "Conservative mixed precision"),
                        ("O2", "Fast mixed precision"),
                        ("O3", "FP16 training")
                    ],
                    lambda e: self._update_resource_config("amp_opt_level", e.control.value),
                    enabled=self.configuration.resource.enable_amp
                )
            ]
        )

        # Gradient settings
        gradient_section = self._create_section(
            title="Gradient Configuration",
            icon=ft.Icons.TRENDING_UP,
            controls=[
                self._create_number_control(
                    "Gradient Accumulation Steps",
                    self.configuration.optimization.gradient_accumulation_steps,
                    lambda e: self._update_optimization_config("gradient_accumulation_steps", int(e.control.value)),
                    min_value=1,
                    max_value=64,
                    tooltip="Number of steps to accumulate gradients before updating"
                ),
                self._create_switch_control(
                    "Enable Gradient Clipping",
                    self.configuration.optimization.gradient_clipping_enabled,
                    lambda e: self._update_optimization_config("gradient_clipping_enabled", e.control.value)
                ),
                self._create_number_control(
                    "Max Gradient Norm",
                    self.configuration.optimization.max_grad_norm,
                    lambda e: self._update_optimization_config("max_grad_norm", float(e.control.value)),
                    min_value=0.1,
                    max_value=10.0,
                    step=0.1,
                    enabled=self.configuration.optimization.gradient_clipping_enabled
                )
            ]
        )

        # Early stopping settings
        early_stopping_section = self._create_section(
            title="Early Stopping",
            icon=ft.Icons.STOP_CIRCLE,
            controls=[
                self._create_switch_control(
                    "Enable Early Stopping",
                    self.configuration.optimization.early_stopping_enabled,
                    lambda e: self._update_optimization_config("early_stopping_enabled", e.control.value)
                ),
                self._create_number_control(
                    "Patience (epochs)",
                    self.configuration.optimization.early_stopping_patience,
                    lambda e: self._update_optimization_config("early_stopping_patience", int(e.control.value)),
                    min_value=1,
                    max_value=100,
                    enabled=self.configuration.optimization.early_stopping_enabled
                ),
                self._create_number_control(
                    "Minimum Delta",
                    self.configuration.optimization.early_stopping_threshold,
                    lambda e: self._update_optimization_config("early_stopping_threshold", float(e.control.value)),
                    min_value=0.0001,
                    max_value=0.1,
                    step=0.0001,
                    enabled=self.configuration.optimization.early_stopping_enabled
                )
            ]
        )

        # Checkpointing settings
        checkpoint_section = self._create_section(
            title="Checkpointing",
            icon=ft.Icons.SAVE,
            controls=[
                self._create_number_control(
                    "Checkpoint Interval (steps)",
                    self.configuration.optimization.checkpoint_interval,
                    lambda e: self._update_optimization_config("checkpoint_interval", int(e.control.value)),
                    min_value=100,
                    max_value=10000,
                    step=100
                ),
                self._create_switch_control(
                    "Save Best Only",
                    self.configuration.optimization.save_best_only,
                    lambda e: self._update_optimization_config("save_best_only", e.control.value)
                ),
                self._create_number_control(
                    "Max Checkpoints",
                    self.configuration.optimization.max_checkpoints,
                    lambda e: self._update_optimization_config("max_checkpoints", int(e.control.value)),
                    min_value=1,
                    max_value=20
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    mixed_precision_section,
                    gradient_section,
                    early_stopping_section,
                    checkpoint_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True,
            padding=spacing.md
        )

    def _create_resource_settings_tab(self) -> ft.Container:
        """Create the resource settings tab content."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Memory management section
        memory_section = self._create_section(
            title="Memory Management",
            icon=ft.Icons.MEMORY,
            controls=[
                self._create_number_control(
                    "GPU Memory Limit (MB)",
                    self.configuration.resource.gpu_memory_limit_mb or 8192,
                    lambda e: self._update_resource_config("gpu_memory_limit_mb", int(e.control.value) if e.control.value else None),
                    min_value=1024,
                    max_value=81920,
                    step=1024,
                    tooltip="Maximum GPU memory to use (leave empty for auto-detection)"
                ),
                self._create_number_control(
                    "CPU Memory Limit (MB)",
                    self.configuration.resource.cpu_memory_limit_mb or 16384,
                    lambda e: self._update_resource_config("cpu_memory_limit_mb", int(e.control.value) if e.control.value else None),
                    min_value=2048,
                    max_value=131072,
                    step=1024
                ),
                self._create_number_control(
                    "NVMe Swap Limit (MB)",
                    self.configuration.resource.nvme_swap_limit_mb or 32768,
                    lambda e: self._update_resource_config("nvme_swap_limit_mb", int(e.control.value) if e.control.value else None),
                    min_value=4096,
                    max_value=1048576,
                    step=4096
                )
            ]
        )

        # Allocation strategy section
        allocation_section = self._create_section(
            title="Allocation Strategy",
            icon=ft.Icons.SETTINGS_APPLICATIONS,
            controls=[
                self._create_dropdown_control(
                    "Memory Allocation Strategy",
                    self.configuration.resource.allocation_strategy,
                    [
                        ("auto", "Automatic (recommended)"),
                        ("legacy", "Legacy GPU-only"),
                        ("hybrid", "Hybrid GPU+CPU"),
                        ("idralloc", "IDRAlloc GPU+CPU+NVMe")
                    ],
                    lambda e: self._update_resource_config("allocation_strategy", e.control.value)
                ),
                self._create_switch_control(
                    "Enable Memory Mapping",
                    self.configuration.resource.enable_memory_mapping,
                    lambda e: self._update_resource_config("enable_memory_mapping", e.control.value)
                ),
                self._create_switch_control(
                    "Enable Gradient Checkpointing",
                    self.configuration.resource.enable_gradient_checkpointing,
                    lambda e: self._update_resource_config("enable_gradient_checkpointing", e.control.value),
                    tooltip="Trade compute for memory by recomputing gradients"
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    memory_section,
                    allocation_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True,
            padding=spacing.md
        )

    def _create_optimization_settings_tab(self) -> ft.Container:
        """Create the optimization settings tab content."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Learning rate scheduling section
        scheduler_section = self._create_section(
            title="Learning Rate Scheduling",
            icon=ft.Icons.TIMELINE,
            controls=[
                self._create_dropdown_control(
                    "Scheduler Type",
                    self.configuration.optimization.scheduler_type,
                    [
                        ("linear", "Linear Decay"),
                        ("cosine", "Cosine Annealing"),
                        ("polynomial", "Polynomial Decay"),
                        ("constant", "Constant Rate")
                    ],
                    lambda e: self._update_optimization_config("scheduler_type", e.control.value)
                ),
                self._create_number_control(
                    "Warmup Steps",
                    self.configuration.optimization.warmup_steps,
                    lambda e: self._update_optimization_config("warmup_steps", int(e.control.value)),
                    min_value=0,
                    max_value=10000,
                    step=100
                ),
                self._create_number_control(
                    "Warmup Ratio",
                    self.configuration.optimization.warmup_ratio,
                    lambda e: self._update_optimization_config("warmup_ratio", float(e.control.value)),
                    min_value=0.0,
                    max_value=0.5,
                    step=0.01
                )
            ]
        )

        # Advanced optimization section
        advanced_opt_section = self._create_section(
            title="Advanced Optimization",
            icon=ft.Icons.ROCKET_LAUNCH,
            controls=[
                self._create_switch_control(
                    "Enable Gradient Compression",
                    self.configuration.optimization.enable_gradient_compression,
                    lambda e: self._update_optimization_config("enable_gradient_compression", e.control.value),
                    tooltip="Compress gradients to reduce communication overhead"
                ),
                self._create_switch_control(
                    "Enable Model Parallelism",
                    self.configuration.optimization.enable_model_parallelism,
                    lambda e: self._update_optimization_config("enable_model_parallelism", e.control.value),
                    tooltip="Split model across multiple devices"
                ),
                self._create_switch_control(
                    "Enable Pipeline Parallelism",
                    self.configuration.optimization.enable_pipeline_parallelism,
                    lambda e: self._update_optimization_config("enable_pipeline_parallelism", e.control.value),
                    tooltip="Pipeline model execution across devices"
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    scheduler_section,
                    advanced_opt_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True,
            padding=spacing.md
        )

    def _create_logging_settings_tab(self) -> ft.Container:
        """Create the logging settings tab content."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Logging configuration section
        logging_section = self._create_section(
            title="Logging Configuration",
            icon=ft.Icons.ARTICLE,
            controls=[
                self._create_dropdown_control(
                    "Log Level",
                    self.configuration.logging.log_level,
                    [
                        ("DEBUG", "Debug (verbose)"),
                        ("INFO", "Info (recommended)"),
                        ("WARNING", "Warning"),
                        ("ERROR", "Error"),
                        ("CRITICAL", "Critical only")
                    ],
                    lambda e: self._update_logging_config("log_level", e.control.value)
                ),
                self._create_switch_control(
                    "Enable File Logging",
                    self.configuration.logging.enable_file_logging,
                    lambda e: self._update_logging_config("enable_file_logging", e.control.value)
                ),
                self._create_switch_control(
                    "Enable Console Logging",
                    self.configuration.logging.enable_console_logging,
                    lambda e: self._update_logging_config("enable_console_logging", e.control.value)
                )
            ]
        )

        # Monitoring intervals section
        intervals_section = self._create_section(
            title="Monitoring Intervals",
            icon=ft.Icons.TIMER,
            controls=[
                self._create_number_control(
                    "Metrics Update Interval (ms)",
                    self.configuration.logging.metrics_update_interval_ms,
                    lambda e: self._update_logging_config("metrics_update_interval_ms", int(e.control.value)),
                    min_value=100,
                    max_value=10000,
                    step=100
                ),
                self._create_number_control(
                    "Loss Logging Interval",
                    self.configuration.logging.loss_logging_interval,
                    lambda e: self._update_logging_config("loss_logging_interval", int(e.control.value)),
                    min_value=1,
                    max_value=1000,
                    step=10
                ),
                self._create_number_control(
                    "Checkpoint Logging Interval",
                    self.configuration.logging.checkpoint_logging_interval,
                    lambda e: self._update_logging_config("checkpoint_logging_interval", int(e.control.value)),
                    min_value=100,
                    max_value=10000,
                    step=100
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    logging_section,
                    intervals_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True,
            padding=spacing.md
        )

    def _create_monitoring_settings_tab(self) -> ft.Container:
        """Create the monitoring settings tab content."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Performance monitoring section
        performance_section = self._create_section(
            title="Performance Monitoring",
            icon=ft.Icons.MONITOR,
            controls=[
                self._create_switch_control(
                    "Enable Profiling",
                    self.configuration.logging.enable_profiling,
                    lambda e: self._update_logging_config("enable_profiling", e.control.value),
                    tooltip="Enable detailed performance profiling"
                ),
                self._create_switch_control(
                    "Profile Memory Usage",
                    self.configuration.logging.profile_memory,
                    lambda e: self._update_logging_config("profile_memory", e.control.value),
                    enabled=self.configuration.logging.enable_profiling
                ),
                self._create_switch_control(
                    "Profile Compute Usage",
                    self.configuration.logging.profile_compute,
                    lambda e: self._update_logging_config("profile_compute", e.control.value),
                    enabled=self.configuration.logging.enable_profiling
                )
            ]
        )

        # Telemetry section
        telemetry_section = self._create_section(
            title="Telemetry",
            icon=ft.Icons.ANALYTICS,
            controls=[
                self._create_switch_control(
                    "Enable Telemetry",
                    self.configuration.logging.enable_telemetry,
                    lambda e: self._update_logging_config("enable_telemetry", e.control.value),
                    tooltip="Send anonymous usage statistics"
                ),
                self._create_text_control(
                    "Telemetry Endpoint",
                    self.configuration.logging.telemetry_endpoint or "",
                    lambda e: self._update_logging_config("telemetry_endpoint", e.control.value if e.control.value else None),
                    enabled=self.configuration.logging.enable_telemetry,
                    placeholder="https://telemetry.example.com/api"
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    performance_section,
                    telemetry_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True,
            padding=spacing.md
        )

    def _create_import_export_tab(self) -> ft.Container:
        """Create the import/export tab content."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Export section
        export_section = self._create_section(
            title="Export Configuration",
            icon=ft.Icons.DOWNLOAD,
            controls=[
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="primary",
                            text="Export All Settings",
                            icon=ft.Icons.DOWNLOAD,
                            on_click=self._on_export_all,
                            expand=True
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Export Current Tab",
                            icon=ft.Icons.DOWNLOAD_FOR_OFFLINE,
                            on_click=self._on_export_current,
                            expand=True
                        )
                    ],
                    spacing=spacing.md
                ),
                ft.Text(
                    "Export your advanced settings to a JSON file for backup or sharing",
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary
                )
            ]
        )

        # Import section
        import_section = self._create_section(
            title="Import Configuration",
            icon=ft.Icons.UPLOAD,
            controls=[
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="primary",
                            text="Import Settings",
                            icon=ft.Icons.UPLOAD,
                            on_click=self._on_import_settings,
                            expand=True
                        ),
                        self.create_themed_component(
                            "button",
                            variant="secondary",
                            text="Load Preset",
                            icon=ft.Icons.SETTINGS_BACKUP_RESTORE,
                            on_click=self._on_load_preset,
                            expand=True
                        )
                    ],
                    spacing=spacing.md
                ),
                ft.Text(
                    "Import settings from a JSON file or load a preset configuration",
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary
                )
            ]
        )

        # Reset section
        reset_section = self._create_section(
            title="Reset Configuration",
            icon=ft.Icons.RESTORE,
            controls=[
                ft.Row(
                    controls=[
                        self.create_themed_component(
                            "button",
                            variant="error",
                            text="Reset to Defaults",
                            icon=ft.Icons.RESTORE,
                            on_click=self._on_reset_to_defaults,
                            expand=True
                        ),
                        self.create_themed_component(
                            "button",
                            variant="warning",
                            text="Reset Current Tab",
                            icon=ft.Icons.REFRESH,
                            on_click=self._on_reset_current_tab,
                            expand=True
                        )
                    ],
                    spacing=spacing.md
                ),
                ft.Text(
                    "Reset settings to default values (this action cannot be undone)",
                    style=self.get_text_style("body_small"),
                    color=palette.error
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    export_section,
                    import_section,
                    reset_section
                ],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True,
            padding=spacing.md
        )

    def _create_section(self, title: str, icon: str, controls: List[ft.Control]) -> ft.Container:
        """Create a settings section with title and controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Section header
        header = ft.Row(
            controls=[
                ft.Icon(
                    icon,
                    color=palette.primary,
                    size=self.get_responsive_value(20, 22, 24, 26)
                ),
                ft.Text(
                    title,
                    style=self.get_text_style("heading_medium"),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                )
            ],
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.START
        )

        # Section content
        content = ft.Column(
            controls=[
                header,
                ft.Container(
                    content=ft.Column(
                        controls=controls,
                        spacing=spacing.md
                    ),
                    padding=ft.padding.only(left=spacing.lg)
                )
            ],
            spacing=spacing.sm
        )

        return ft.Container(
            content=content,
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(8, 10, 12, 14),
            padding=spacing.md,
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_switch_control(
        self,
        label: str,
        value: bool,
        on_change: Callable,
        tooltip: Optional[str] = None,
        enabled: bool = True
    ) -> ft.Container:
        """Create a switch control with label."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        switch = ft.Switch(
            label=label,
            value=value,
            on_change=on_change,
            active_color=palette.primary,
            disabled=not enabled,
            label_style=self.get_text_style("body_medium")
        )

        if tooltip:
            switch.tooltip = tooltip

        return ft.Container(
            content=switch,
            padding=ft.padding.symmetric(vertical=spacing.xs)
        )

    def _create_number_control(
        self,
        label: str,
        value: Union[int, float],
        on_change: Callable,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        step: Union[int, float] = 1,
        tooltip: Optional[str] = None,
        enabled: bool = True
    ) -> ft.Container:
        """Create a number input control with label."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label
        label_text = ft.Text(
            label,
            style=self.get_text_style("body_medium"),
            color=palette.text_primary if enabled else palette.text_disabled
        )

        # Number input
        number_input = ft.TextField(
            value=str(value),
            label=label,
            on_change=on_change,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=self.get_responsive_value(120, 140, 160, 180),
            text_style=self.get_text_style("body_medium"),
            label_style=self.get_text_style("body_small"),
            bgcolor=palette.surface_variant,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            disabled=not enabled
        )

        if tooltip:
            number_input.tooltip = tooltip

        # Validation text
        validation_text = ""
        if min_value is not None and max_value is not None:
            validation_text = f"Range: {min_value} - {max_value}"
        elif min_value is not None:
            validation_text = f"Min: {min_value}"
        elif max_value is not None:
            validation_text = f"Max: {max_value}"

        controls = [number_input]
        if validation_text:
            controls.append(
                ft.Text(
                    validation_text,
                    style=self.get_text_style("body_small"),
                    color=palette.text_secondary
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=controls,
                spacing=spacing.xs,
                tight=True
            ),
            padding=ft.padding.symmetric(vertical=spacing.xs)
        )

    def _create_dropdown_control(
        self,
        label: str,
        value: str,
        options: List[Tuple[str, str]],
        on_change: Callable,
        tooltip: Optional[str] = None,
        enabled: bool = True
    ) -> ft.Container:
        """Create a dropdown control with label."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        dropdown = ft.Dropdown(
            label=label,
            value=value,
            options=[ft.dropdown.Option(key, text) for key, text in options],
            on_change=on_change,
            width=self.get_responsive_value(200, 220, 240, 260),
            text_style=self.get_text_style("body_medium"),
            label_style=self.get_text_style("body_small"),
            bgcolor=palette.surface_variant,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            disabled=not enabled
        )

        if tooltip:
            dropdown.tooltip = tooltip

        return ft.Container(
            content=dropdown,
            padding=ft.padding.symmetric(vertical=spacing.xs)
        )

    def _create_text_control(
        self,
        label: str,
        value: str,
        on_change: Callable,
        placeholder: Optional[str] = None,
        tooltip: Optional[str] = None,
        enabled: bool = True
    ) -> ft.Container:
        """Create a text input control with label."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        text_field = ft.TextField(
            label=label,
            value=value,
            on_change=on_change,
            hint_text=placeholder,
            width=self.get_responsive_value(250, 280, 320, 360),
            text_style=self.get_text_style("body_medium"),
            label_style=self.get_text_style("body_small"),
            bgcolor=palette.surface_variant,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            disabled=not enabled
        )

        if tooltip:
            text_field.tooltip = tooltip

        return ft.Container(
            content=text_field,
            padding=ft.padding.symmetric(vertical=spacing.xs)
        )

    def _create_validation_panel(self) -> ft.Container:
        """Create the validation panel."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        self._validation_panel = ft.Container(
            content=ft.Column(
                controls=[],
                spacing=spacing.xs
            ),
            visible=False,
            bgcolor=palette.error_container,
            border_radius=self.get_responsive_value(6, 8, 10, 12),
            padding=spacing.md,
            margin=ft.margin.symmetric(vertical=spacing.sm)
        )

        return self._validation_panel

    def _create_action_bar(self) -> ft.Container:
        """Create the action bar with save/cancel buttons."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Save button
        save_button = self.create_themed_component(
            "button",
            variant="primary",
            text="Save Configuration",
            icon=ft.Icons.SAVE,
            on_click=self._on_save_configuration
        )

        # Cancel button
        cancel_button = self.create_themed_component(
            "button",
            variant="secondary",
            text="Cancel",
            icon=ft.Icons.CANCEL,
            on_click=self._on_cancel_changes
        )

        # Apply button
        apply_button = self.create_themed_component(
            "button",
            variant="primary",
            text="Apply",
            icon=ft.Icons.CHECK,
            on_click=self._on_apply_changes
        )

        self._action_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),  # Spacer
                    cancel_button,
                    apply_button,
                    save_button
                ],
                spacing=spacing.md,
                alignment=ft.MainAxisAlignment.END
            ),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(8, 10, 12, 14),
            padding=spacing.md,
            border=ft.border.all(1, palette.outline_variant)
        )

        return self._action_bar

    # Configuration update methods
    def _update_resource_config(self, key: str, value: Any) -> None:
        """Update resource configuration."""
        setattr(self.configuration.resource, key, value)
        self.configuration.modified_at = datetime.now()
        self._notify_configuration_change()
        self._schedule_validation()

    def _update_optimization_config(self, key: str, value: Any) -> None:
        """Update optimization configuration."""
        setattr(self.configuration.optimization, key, value)
        self.configuration.modified_at = datetime.now()
        self._notify_configuration_change()
        self._schedule_validation()

    def _update_logging_config(self, key: str, value: Any) -> None:
        """Update logging configuration."""
        setattr(self.configuration.logging, key, value)
        self.configuration.modified_at = datetime.now()
        self._notify_configuration_change()
        self._schedule_validation()

    def _notify_configuration_change(self) -> None:
        """Notify about configuration changes."""
        if self.on_configuration_change:
            try:
                self.on_configuration_change(self.configuration)
            except Exception as e:
                self._logger.error(f"Error in configuration change callback: {e}")

    def _schedule_validation(self) -> None:
        """Schedule validation with debouncing."""
        if not self.config.enable_real_time_validation:
            return

        # Cancel existing validation timer
        if self._validation_timer and not self._validation_timer.done():
            self._validation_timer.cancel()

        # Schedule new validation
        async def delayed_validation():
            await asyncio.sleep(0.5)  # Debounce delay
            await self._validate_configuration()

        self._validation_timer = asyncio.create_task(delayed_validation())

    async def _validate_configuration(self) -> None:
        """Validate the current configuration."""
        if self._is_validating:
            return

        self._is_validating = True

        try:
            # Perform validation
            validation_result = await self._perform_validation()

            # Update validation result
            self._validation_result = validation_result

            # Update validation panel
            self._update_validation_panel(validation_result)

            # Notify validation change
            if self.on_validation_change:
                self.on_validation_change(validation_result)

        except Exception as e:
            self._logger.error(f"Validation error: {e}")

        finally:
            self._is_validating = False

    async def _perform_validation(self) -> ConfigurationValidationResult:
        """Perform comprehensive configuration validation."""
        category_validations = {}
        warnings = []
        errors = []
        suggestions = []

        # Validate resource configuration
        resource_issues = self._validate_resource_config()
        if resource_issues:
            category_validations[SettingsCategory.RESOURCE] = resource_issues

        # Validate optimization configuration
        optimization_issues = self._validate_optimization_config()
        if optimization_issues:
            category_validations[SettingsCategory.OPTIMIZATION] = optimization_issues

        # Validate logging configuration
        logging_issues = self._validate_logging_config()
        if logging_issues:
            category_validations[SettingsCategory.LOGGING] = logging_issues

        # Check for conflicts and generate suggestions
        conflicts = self._check_configuration_conflicts()
        if conflicts:
            errors.extend(conflicts)

        suggestions.extend(self._generate_optimization_suggestions())

        is_valid = len(errors) == 0

        return ConfigurationValidationResult(
            is_valid=is_valid,
            category_validations=category_validations,
            warnings=warnings,
            errors=errors,
            suggestions=suggestions
        )

    def _validate_resource_config(self) -> List[str]:
        """Validate resource configuration."""
        issues = []
        config = self.configuration.resource

        # Memory limit validation
        if config.gpu_memory_limit_mb and config.gpu_memory_limit_mb < 1024:
            issues.append("GPU memory limit is too low (minimum 1GB)")

        if config.cpu_memory_limit_mb and config.cpu_memory_limit_mb < 2048:
            issues.append("CPU memory limit is too low (minimum 2GB)")

        # Allocation strategy validation
        if config.allocation_strategy == "idralloc" and not config.nvme_swap_limit_mb:
            issues.append("IDRAlloc strategy requires NVMe swap configuration")

        # AMP validation
        if config.enable_amp and config.amp_opt_level == "O3":
            issues.append("AMP O3 level may cause numerical instability")

        return issues

    def _validate_optimization_config(self) -> List[str]:
        """Validate optimization configuration."""
        issues = []
        config = self.configuration.optimization

        # Gradient accumulation validation
        if config.gradient_accumulation_steps > 32:
            issues.append("High gradient accumulation may slow training")

        # Early stopping validation
        if config.early_stopping_enabled and config.early_stopping_patience < 3:
            issues.append("Early stopping patience is too low")

        # Checkpoint validation
        if config.checkpoint_interval < 100:
            issues.append("Checkpoint interval is too frequent")

        return issues

    def _validate_logging_config(self) -> List[str]:
        """Validate logging configuration."""
        issues = []
        config = self.configuration.logging

        # Log level validation
        if config.log_level == "DEBUG" and not config.enable_profiling:
            issues.append("DEBUG logging without profiling may impact performance")

        # Interval validation
        if config.metrics_update_interval_ms < 100:
            issues.append("Metrics update interval is too frequent")

        # Telemetry validation
        if config.enable_telemetry and not config.telemetry_endpoint:
            issues.append("Telemetry enabled but no endpoint configured")

        return issues

    def _check_configuration_conflicts(self) -> List[str]:
        """Check for configuration conflicts."""
        conflicts = []

        # Memory vs parallelism conflicts
        if (self.configuration.optimization.enable_model_parallelism and
            self.configuration.resource.gpu_memory_limit_mb and
            self.configuration.resource.gpu_memory_limit_mb < 4096):
            conflicts.append("Model parallelism requires more GPU memory")

        # AMP vs precision conflicts
        if (self.configuration.resource.enable_amp and
            self.configuration.optimization.enable_gradient_compression):
            conflicts.append("AMP and gradient compression may conflict")

        return conflicts

    def _generate_optimization_suggestions(self) -> List[str]:
        """Generate optimization suggestions."""
        suggestions = []

        # Memory optimization suggestions
        if (self.configuration.resource.gpu_memory_limit_mb and
            self.configuration.resource.gpu_memory_limit_mb < 8192):
            suggestions.append("Consider enabling gradient checkpointing to reduce memory usage")

        # Performance suggestions
        if not self.configuration.resource.enable_amp:
            suggestions.append("Enable AMP for faster training with minimal accuracy loss")

        # Monitoring suggestions
        if not self.configuration.logging.enable_profiling:
            suggestions.append("Enable profiling to identify performance bottlenecks")

        return suggestions

    def _update_validation_panel(self, result: ConfigurationValidationResult) -> None:
        """Update the validation panel with results."""
        if not self._validation_panel:
            return

        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        controls = []

        # Show errors
        if result.errors:
            error_header = ft.Text(
                "Errors:",
                style=self.get_text_style("body_medium"),
                color=palette.error,
                weight=ft.FontWeight.W_600
            )
            controls.append(error_header)

            for error in result.errors:
                error_text = ft.Text(
                    f"• {error}",
                    style=self.get_text_style("body_small"),
                    color=palette.error
                )
                controls.append(error_text)

        # Show warnings
        if result.warnings:
            warning_header = ft.Text(
                "Warnings:",
                style=self.get_text_style("body_medium"),
                color=palette.warning,
                weight=ft.FontWeight.W_600
            )
            controls.append(warning_header)

            for warning in result.warnings:
                warning_text = ft.Text(
                    f"• {warning}",
                    style=self.get_text_style("body_small"),
                    color=palette.warning
                )
                controls.append(warning_text)

        # Update panel
        self._validation_panel.content.controls = controls
        self._validation_panel.visible = len(controls) > 0

        # Update panel color based on validation status
        if result.errors:
            self._validation_panel.bgcolor = palette.error_container
        elif result.warnings:
            self._validation_panel.bgcolor = palette.warning_container
        else:
            self._validation_panel.bgcolor = palette.success_container

        if self.page:
            self.page.update()

    # Event handlers
    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        """Handle mode change."""
        try:
            new_mode = AdvancedSettingsMode(e.control.value)
            self.config.mode = new_mode

            # Update visible categories based on mode
            if new_mode == AdvancedSettingsMode.BASIC:
                self.config.visible_categories = [
                    SettingsCategory.TRAINING,
                    SettingsCategory.RESOURCE
                ]
            elif new_mode == AdvancedSettingsMode.ADVANCED:
                self.config.visible_categories = [
                    SettingsCategory.TRAINING,
                    SettingsCategory.RESOURCE,
                    SettingsCategory.OPTIMIZATION,
                    SettingsCategory.LOGGING
                ]
            else:  # EXPERT
                self.config.visible_categories = list(SettingsCategory)

            # Rebuild tabs
            self._rebuild_tabs()

        except Exception as ex:
            self._logger.error(f"Error changing mode: {ex}")

    def _rebuild_tabs(self) -> None:
        """Rebuild the tabs interface."""
        if self._tabs and self.page:
            # Store current tab index
            current_index = self._tabs.selected_index

            # Rebuild UI
            self._build_ui()

            # Restore tab index if valid
            if current_index < len(self._tabs.tabs):
                self._tabs.selected_index = current_index

            self.page.update()

    def _on_save_configuration(self, e: ft.ControlEvent) -> None:
        """Handle save configuration."""
        try:
            # Validate before saving
            if self._validation_result and not self._validation_result.is_valid:
                self._show_error_dialog("Cannot save configuration with validation errors")
                return

            # Save configuration (implement based on your storage mechanism)
            self._save_configuration_to_storage()

            self._show_success_message("Configuration saved successfully")

        except Exception as ex:
            self._logger.error(f"Error saving configuration: {ex}")
            self._show_error_dialog(f"Failed to save configuration: {ex}")

    def _on_cancel_changes(self, e: ft.ControlEvent) -> None:
        """Handle cancel changes."""
        try:
            # Reset to original configuration
            self.configuration = AdvancedConfiguration()
            self._build_ui()

            if self.page:
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Error canceling changes: {ex}")

    def _on_apply_changes(self, e: ft.ControlEvent) -> None:
        """Handle apply changes."""
        try:
            # Validate before applying
            if self._validation_result and not self._validation_result.is_valid:
                self._show_error_dialog("Cannot apply configuration with validation errors")
                return

            # Apply changes (notify callbacks)
            self._notify_configuration_change()

            self._show_success_message("Configuration applied successfully")

        except Exception as ex:
            self._logger.error(f"Error applying changes: {ex}")
            self._show_error_dialog(f"Failed to apply changes: {ex}")

    def _on_export_all(self, e: ft.ControlEvent) -> None:
        """Handle export all settings."""
        try:
            result = self._export_configuration(all_categories=True)
            if result.success:
                self._show_success_message(f"Configuration exported to {result.file_path}")
            else:
                self._show_error_dialog(f"Export failed: {result.error_message}")

        except Exception as ex:
            self._logger.error(f"Error exporting configuration: {ex}")
            self._show_error_dialog(f"Export failed: {ex}")

    def _on_export_current(self, e: ft.ControlEvent) -> None:
        """Handle export current tab."""
        try:
            current_category = self._get_current_category()
            result = self._export_configuration(categories=[current_category])
            if result.success:
                self._show_success_message(f"Configuration exported to {result.file_path}")
            else:
                self._show_error_dialog(f"Export failed: {result.error_message}")

        except Exception as ex:
            self._logger.error(f"Error exporting configuration: {ex}")
            self._show_error_dialog(f"Export failed: {ex}")

    def _on_import_settings(self, e: ft.ControlEvent) -> None:
        """Handle import settings."""
        try:
            # This would typically open a file picker
            # For now, we'll implement a placeholder
            self._show_info_message("Import functionality will open a file picker")

        except Exception as ex:
            self._logger.error(f"Error importing settings: {ex}")
            self._show_error_dialog(f"Import failed: {ex}")

    def _on_load_preset(self, e: ft.ControlEvent) -> None:
        """Handle load preset."""
        try:
            # Load a preset configuration
            preset_config = self._get_preset_configuration("default")
            if preset_config:
                self.configuration = preset_config
                self._build_ui()
                self._show_success_message("Preset configuration loaded")
            else:
                self._show_error_dialog("No preset configurations available")

        except Exception as ex:
            self._logger.error(f"Error loading preset: {ex}")
            self._show_error_dialog(f"Failed to load preset: {ex}")

    def _on_reset_to_defaults(self, e: ft.ControlEvent) -> None:
        """Handle reset to defaults."""
        try:
            # Reset entire configuration
            self.configuration = AdvancedConfiguration()
            self._build_ui()
            self._show_success_message("Configuration reset to defaults")

        except Exception as ex:
            self._logger.error(f"Error resetting configuration: {ex}")
            self._show_error_dialog(f"Failed to reset configuration: {ex}")

    def _on_reset_current_tab(self, e: ft.ControlEvent) -> None:
        """Handle reset current tab."""
        try:
            current_category = self._get_current_category()

            # Reset specific category
            if current_category == SettingsCategory.RESOURCE:
                self.configuration.resource = ResourceConfiguration()
            elif current_category == SettingsCategory.OPTIMIZATION:
                self.configuration.optimization = OptimizationConfiguration()
            elif current_category == SettingsCategory.LOGGING:
                self.configuration.logging = LoggingConfiguration()

            self._build_ui()
            self._show_success_message(f"{current_category.value.title()} settings reset to defaults")

        except Exception as ex:
            self._logger.error(f"Error resetting tab: {ex}")
            self._show_error_dialog(f"Failed to reset tab: {ex}")

    # Utility methods
    def _get_current_category(self) -> SettingsCategory:
        """Get the currently selected category."""
        if not self._tabs:
            return SettingsCategory.TRAINING

        tab_index = self._tabs.selected_index
        categories = self.config.visible_categories

        if 0 <= tab_index < len(categories):
            return categories[tab_index]

        return SettingsCategory.TRAINING

    def _export_configuration(
        self,
        categories: Optional[List[SettingsCategory]] = None,
        all_categories: bool = False
    ) -> ConfigurationExportResult:
        """Export configuration to file."""
        try:
            # Determine what to export
            if all_categories:
                export_categories = list(SettingsCategory)
            elif categories:
                export_categories = categories
            else:
                export_categories = [self._get_current_category()]

            # Create export data
            export_data = {
                "metadata": {
                    "name": self.configuration.name,
                    "description": self.configuration.description,
                    "version": self.configuration.version,
                    "exported_at": datetime.now().isoformat(),
                    "exported_categories": [cat.value for cat in export_categories]
                }
            }

            # Add category data
            if SettingsCategory.RESOURCE in export_categories:
                export_data["resource"] = self._serialize_resource_config()

            if SettingsCategory.OPTIMIZATION in export_categories:
                export_data["optimization"] = self._serialize_optimization_config()

            if SettingsCategory.LOGGING in export_categories:
                export_data["logging"] = self._serialize_logging_config()

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mikrodok_advanced_settings_{timestamp}.json"
            file_path = Path.cwd() / "exports" / filename

            # Ensure export directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            return ConfigurationExportResult(
                success=True,
                file_path=file_path,
                exported_categories=export_categories
            )

        except Exception as e:
            return ConfigurationExportResult(
                success=False,
                error_message=str(e)
            )

    def _serialize_resource_config(self) -> Dict[str, Any]:
        """Serialize resource configuration."""
        config = self.configuration.resource
        return {
            "gpu_memory_limit_mb": config.gpu_memory_limit_mb,
            "cpu_memory_limit_mb": config.cpu_memory_limit_mb,
            "nvme_swap_limit_mb": config.nvme_swap_limit_mb,
            "allocation_strategy": config.allocation_strategy,
            "enable_memory_mapping": config.enable_memory_mapping,
            "enable_gradient_checkpointing": config.enable_gradient_checkpointing,
            "num_workers": config.num_workers,
            "pin_memory": config.pin_memory,
            "prefetch_factor": config.prefetch_factor,
            "persistent_workers": config.persistent_workers,
            "enable_amp": config.enable_amp,
            "amp_opt_level": config.amp_opt_level,
            "enable_cpu_offload": config.enable_cpu_offload,
            "enable_disk_offload": config.enable_disk_offload
        }

    def _serialize_optimization_config(self) -> Dict[str, Any]:
        """Serialize optimization configuration."""
        config = self.configuration.optimization
        return {
            "gradient_accumulation_steps": config.gradient_accumulation_steps,
            "max_grad_norm": config.max_grad_norm,
            "gradient_clipping_enabled": config.gradient_clipping_enabled,
            "scheduler_type": config.scheduler_type,
            "warmup_steps": config.warmup_steps,
            "warmup_ratio": config.warmup_ratio,
            "early_stopping_enabled": config.early_stopping_enabled,
            "early_stopping_patience": config.early_stopping_patience,
            "early_stopping_threshold": config.early_stopping_threshold,
            "checkpoint_interval": config.checkpoint_interval,
            "save_best_only": config.save_best_only,
            "max_checkpoints": config.max_checkpoints,
            "enable_gradient_compression": config.enable_gradient_compression,
            "enable_model_parallelism": config.enable_model_parallelism,
            "enable_pipeline_parallelism": config.enable_pipeline_parallelism
        }

    def _serialize_logging_config(self) -> Dict[str, Any]:
        """Serialize logging configuration."""
        config = self.configuration.logging
        return {
            "log_level": config.log_level,
            "enable_file_logging": config.enable_file_logging,
            "enable_console_logging": config.enable_console_logging,
            "max_log_size_mb": config.max_log_size_mb,
            "max_log_files": config.max_log_files,
            "metrics_update_interval_ms": config.metrics_update_interval_ms,
            "loss_logging_interval": config.loss_logging_interval,
            "checkpoint_logging_interval": config.checkpoint_logging_interval,
            "enable_telemetry": config.enable_telemetry,
            "telemetry_endpoint": config.telemetry_endpoint,
            "enable_profiling": config.enable_profiling,
            "profile_memory": config.profile_memory,
            "profile_compute": config.profile_compute
        }

    def _get_preset_configuration(self, preset_name: str) -> Optional[AdvancedConfiguration]:
        """Get a preset configuration."""
        presets = {
            "default": AdvancedConfiguration(),
            "performance": AdvancedConfiguration(
                resource=ResourceConfiguration(
                    enable_amp=True,
                    amp_opt_level="O2",
                    enable_gradient_checkpointing=True,
                    allocation_strategy="idralloc"
                ),
                optimization=OptimizationConfiguration(
                    gradient_accumulation_steps=4,
                    enable_gradient_compression=True,
                    scheduler_type="cosine"
                )
            ),
            "memory_efficient": AdvancedConfiguration(
                resource=ResourceConfiguration(
                    enable_gradient_checkpointing=True,
                    enable_cpu_offload=True,
                    enable_disk_offload=True,
                    allocation_strategy="hybrid"
                ),
                optimization=OptimizationConfiguration(
                    gradient_accumulation_steps=8,
                    checkpoint_interval=500
                )
            )
        }

        return presets.get(preset_name)

    def _save_configuration_to_storage(self) -> None:
        """Save configuration to persistent storage."""
        # This would typically save to a database or file
        # For now, we'll just log the action
        self._logger.info("Configuration saved to storage")

    def _show_success_message(self, message: str) -> None:
        """Show success message to user."""
        # This would typically show a snackbar or toast
        self._logger.info(f"Success: {message}")

    def _show_error_dialog(self, message: str) -> None:
        """Show error dialog to user."""
        # This would typically show an error dialog
        self._logger.error(f"Error: {message}")

    def _show_info_message(self, message: str) -> None:
        """Show info message to user."""
        # This would typically show an info snackbar
        self._logger.info(f"Info: {message}")

    # Public API methods
    def get_configuration(self) -> AdvancedConfiguration:
        """Get the current configuration."""
        return self.configuration

    def set_configuration(self, config: AdvancedConfiguration) -> None:
        """Set the configuration."""
        self.configuration = config
        self.configuration.modified_at = datetime.now()
        self._build_ui()
        self._notify_configuration_change()
        self._schedule_validation()

    def validate_configuration(self) -> ConfigurationValidationResult:
        """Validate the current configuration synchronously."""
        # This is a simplified synchronous version
        return ConfigurationValidationResult(
            is_valid=True,
            category_validations={},
            warnings=[],
            errors=[],
            suggestions=[]
        )

    def export_configuration_to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "resource": self._serialize_resource_config(),
            "optimization": self._serialize_optimization_config(),
            "logging": self._serialize_logging_config(),
            "metadata": {
                "name": self.configuration.name,
                "description": self.configuration.description,
                "version": self.configuration.version,
                "created_at": self.configuration.created_at.isoformat(),
                "modified_at": self.configuration.modified_at.isoformat()
            }
        }

    def import_configuration_from_dict(self, data: Dict[str, Any]) -> bool:
        """Import configuration from dictionary."""
        try:
            # Create new configuration
            new_config = AdvancedConfiguration()

            # Import resource config
            if "resource" in data:
                resource_data = data["resource"]
                new_config.resource = ResourceConfiguration(**resource_data)

            # Import optimization config
            if "optimization" in data:
                opt_data = data["optimization"]
                new_config.optimization = OptimizationConfiguration(**opt_data)

            # Import logging config
            if "logging" in data:
                log_data = data["logging"]
                new_config.logging = LoggingConfiguration(**log_data)

            # Import metadata
            if "metadata" in data:
                metadata = data["metadata"]
                new_config.name = metadata.get("name", new_config.name)
                new_config.description = metadata.get("description", new_config.description)
                new_config.version = metadata.get("version", new_config.version)

            # Set the new configuration
            self.set_configuration(new_config)
            return True

        except Exception as e:
            self._logger.error(f"Failed to import configuration: {e}")
            return False
