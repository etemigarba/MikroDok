"""
Module: deployment_wizard_ui
Description: Step-by-step model deployment configuration wizard interface with export format selection,
            quantization options, platform targeting, and package generation. Provides guided workflow
            for model deployment with validation, progress tracking, and comprehensive configuration options.

Features:
- Multi-step wizard interface with navigation controls
- Export format selection (ONNX, PyTorch, TensorFlow, GGUF)
- Quantization configuration (INT4, INT8, FP16, FP32)
- Platform targeting (Windows, macOS, Linux, Mobile)
- Optimization level configuration with size/performance trade-offs
- Package generation with progress feedback
- Model compatibility validation
- Responsive design with theme integration
- Accessibility compliance with keyboard navigation

Phase: 8
Location: /src/modules/ui/model_registry_ui/deployment_wizard_ui/deployment_wizard_ui.py
"""

# Standard library imports
import os
import json
import logging
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class DeploymentWizardStep(Enum):
    """Deployment wizard step enumeration."""
    MODEL_SELECTION = "model_selection"
    EXPORT_FORMAT = "export_format"
    QUANTIZATION = "quantization"
    PLATFORM_TARGET = "platform_target"
    OPTIMIZATION = "optimization"
    PACKAGE_GENERATION = "package_generation"
    COMPLETION = "completion"


class ExportFormat(Enum):
    """Model export format enumeration."""
    ONNX = "onnx"
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    GGUF = "gguf"
    COREML = "coreml"
    TENSORRT = "tensorrt"


class QuantizationType(Enum):
    """Model quantization type enumeration."""
    FP32 = "fp32"
    FP16 = "fp16"
    INT8 = "int8"
    INT4 = "int4"
    DYNAMIC = "dynamic"


class PlatformTarget(Enum):
    """Deployment platform target enumeration."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"


class OptimizationLevel(Enum):
    """Optimization level enumeration."""
    SIZE_OPTIMIZED = "size_optimized"
    BALANCED = "balanced"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    CUSTOM = "custom"


class DeploymentValidationState(Enum):
    """Deployment validation state enumeration."""
    PENDING = "pending"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"


class PackageGenerationStatus(Enum):
    """Package generation status enumeration."""
    NOT_STARTED = "not_started"
    PREPARING = "preparing"
    CONVERTING = "converting"
    OPTIMIZING = "optimizing"
    PACKAGING = "packaging"
    COMPLETED = "completed"
    FAILED = "failed"


class WizardNavigationState(Enum):
    """Wizard navigation state enumeration."""
    FIRST_STEP = "first_step"
    MIDDLE_STEP = "middle_step"
    LAST_STEP = "last_step"
    COMPLETED = "completed"


@dataclass
class ModelCompatibilityInfo:
    """Model compatibility information."""
    model_id: str
    model_name: str
    architecture: str
    size_mb: float
    supported_formats: Set[ExportFormat] = field(default_factory=set)
    supported_quantizations: Set[QuantizationType] = field(default_factory=set)
    supported_platforms: Set[PlatformTarget] = field(default_factory=set)
    compatibility_score: float = 1.0
    warnings: List[str] = field(default_factory=list)
    requirements: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentConfiguration:
    """Deployment configuration data."""
    model_id: str
    export_format: Optional[ExportFormat] = None
    quantization_type: Optional[QuantizationType] = None
    platform_targets: Set[PlatformTarget] = field(default_factory=set)
    optimization_level: OptimizationLevel = OptimizationLevel.BALANCED
    custom_optimization: Dict[str, Any] = field(default_factory=dict)
    output_directory: Optional[str] = None
    package_name: Optional[str] = None
    include_runtime: bool = True
    include_dependencies: bool = True
    compression_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PackageGenerationProgress:
    """Package generation progress information."""
    status: PackageGenerationStatus = PackageGenerationStatus.NOT_STARTED
    current_step: str = ""
    progress_percentage: float = 0.0
    estimated_time_remaining: Optional[float] = None
    generated_files: List[str] = field(default_factory=list)
    package_size_mb: Optional[float] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class DeploymentWizardData:
    """Complete deployment wizard data structure."""
    model_compatibility: Optional[ModelCompatibilityInfo] = None
    deployment_config: DeploymentConfiguration = field(default_factory=lambda: DeploymentConfiguration(""))
    validation_state: DeploymentValidationState = DeploymentValidationState.PENDING
    generation_progress: PackageGenerationProgress = field(default_factory=PackageGenerationProgress)
    current_step: DeploymentWizardStep = DeploymentWizardStep.MODEL_SELECTION
    step_validation: Dict[DeploymentWizardStep, bool] = field(default_factory=dict)
    step_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DeploymentWizardConfig:
    """Deployment wizard configuration."""
    enable_model_selection: bool = True
    enable_format_validation: bool = True
    enable_compatibility_check: bool = True
    enable_progress_tracking: bool = True
    enable_package_preview: bool = True
    auto_validate_steps: bool = True
    show_advanced_options: bool = False
    max_package_size_mb: float = 1024.0
    supported_formats: Set[ExportFormat] = field(default_factory=lambda: {
        ExportFormat.ONNX, ExportFormat.PYTORCH, ExportFormat.TENSORFLOW, ExportFormat.GGUF
    })
    supported_quantizations: Set[QuantizationType] = field(default_factory=lambda: {
        QuantizationType.FP32, QuantizationType.FP16, QuantizationType.INT8, QuantizationType.INT4
    })
    supported_platforms: Set[PlatformTarget] = field(default_factory=lambda: {
        PlatformTarget.WINDOWS, PlatformTarget.MACOS, PlatformTarget.LINUX
    })
    default_output_directory: Optional[str] = None
    enable_compression: bool = True
    enable_runtime_inclusion: bool = True
    validation_timeout_seconds: float = 30.0
    generation_timeout_seconds: float = 300.0


class DeploymentWizardUI(ThemeAwareUserControl):
    """
    Step-by-step model deployment configuration wizard interface.
    
    Provides guided workflow for model deployment with export format selection,
    quantization options, platform targeting, and package generation.
    
    Features:
    - Multi-step wizard with navigation controls
    - Model compatibility validation
    - Export format and quantization configuration
    - Platform targeting and optimization settings
    - Package generation with progress tracking
    - Responsive design with theme integration
    """
    
    def __init__(
        self,
        model_id: Optional[str] = None,
        config: Optional[DeploymentWizardConfig] = None,
        on_deployment_completed: Optional[Callable[[str, str], None]] = None,
        on_wizard_cancelled: Optional[Callable[[], None]] = None,
        on_step_changed: Optional[Callable[[DeploymentWizardStep], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self.model_id = model_id
        self.config = config or DeploymentWizardConfig()
        
        # Callbacks
        self.on_deployment_completed = on_deployment_completed
        self.on_wizard_cancelled = on_wizard_cancelled
        self.on_step_changed = on_step_changed
        
        # State
        self.wizard_data = DeploymentWizardData()
        if model_id:
            self.wizard_data.deployment_config.model_id = model_id
        
        # UI components
        self._step_indicator = None
        self._step_content = None
        self._navigation_bar = None
        self._progress_overlay = None
        
        # Step components
        self._step_components = {}
        
        # Initialize wizard data
        self._initialize_wizard_data()
    
    def _initialize_wizard_data(self) -> None:
        """Initialize wizard data with default values."""
        try:
            # Initialize step validation
            for step in DeploymentWizardStep:
                self.wizard_data.step_validation[step] = False
            
            # Set default configuration
            if self.model_id:
                self.wizard_data.deployment_config.model_id = self.model_id
                self.wizard_data.deployment_config.package_name = f"model_{self.model_id}_deployment"
            
            # Set default output directory
            if self.config.default_output_directory:
                self.wizard_data.deployment_config.output_directory = self.config.default_output_directory
            
            logger.info(f"Initialized deployment wizard for model: {self.model_id}")
            
        except Exception as e:
            logger.error(f"Error initializing wizard data: {e}")

    def build(self) -> ft.Control:
        """Build the deployment wizard interface."""
        try:
            # Get responsive layout manager
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Build step indicator
            self._step_indicator = self._build_step_indicator()

            # Build step content
            self._step_content = self._build_step_content()

            # Build navigation bar
            self._navigation_bar = self._build_navigation_bar()

            # Build progress overlay
            self._progress_overlay = self._build_progress_overlay()

            # Main wizard container
            wizard_content = ft.Column(
                controls=[
                    # Header with step indicator
                    ft.Container(
                        content=self._step_indicator,
                        padding=ft.padding.all(responsive.get_padding(current_screen)),
                        bgcolor=self.get_palette().surface,
                        border=ft.border.only(
                            bottom=ft.BorderSide(1, self.get_palette().outline_variant)
                        )
                    ),

                    # Step content area
                    ft.Container(
                        content=self._step_content,
                        padding=ft.padding.all(responsive.get_padding(current_screen)),
                        expand=True
                    ),

                    # Navigation bar
                    ft.Container(
                        content=self._navigation_bar,
                        padding=ft.padding.all(responsive.get_padding(current_screen)),
                        bgcolor=self.get_palette().surface_variant,
                        border=ft.border.only(
                            top=ft.BorderSide(1, self.get_palette().outline_variant)
                        )
                    )
                ],
                spacing=0,
                expand=True
            )

            # Wrap in stack for progress overlay
            return ft.Stack(
                controls=[
                    wizard_content,
                    self._progress_overlay
                ],
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building deployment wizard: {e}")
            return self._build_error_state(str(e))

    def _build_step_indicator(self) -> ft.Control:
        """Build step progress indicator."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            steps = list(DeploymentWizardStep)
            current_step_index = steps.index(self.wizard_data.current_step)

            # Build step indicators
            step_indicators = []
            for i, step in enumerate(steps):
                is_current = i == current_step_index
                is_completed = i < current_step_index
                is_valid = self.wizard_data.step_validation.get(step, False)

                # Step circle
                if is_completed or is_valid:
                    step_icon = ft.Icon(
                        self.get_icon("CHECK"),
                        color=self.get_palette().primary,
                        size=responsive.get_icon_size(current_screen, "sm")
                    )
                    circle_color = self.get_palette().primary
                elif is_current:
                    step_icon = ft.Text(
                        str(i + 1),
                        color=self.get_palette().on_primary,
                        size=responsive.get_font_size(current_screen, 12),
                        weight=ft.FontWeight.BOLD
                    )
                    circle_color = self.get_palette().primary
                else:
                    step_icon = ft.Text(
                        str(i + 1),
                        color=self.get_palette().on_surface_variant,
                        size=responsive.get_font_size(current_screen, 12)
                    )
                    circle_color = self.get_palette().surface_variant

                step_circle = ft.Container(
                    content=step_icon,
                    width=responsive.get_size(current_screen, 32),
                    height=responsive.get_size(current_screen, 32),
                    bgcolor=circle_color,
                    border_radius=16,
                    alignment=ft.alignment.center
                )

                # Step label
                step_label = ft.Text(
                    step.value.replace("_", " ").title(),
                    color=self.get_palette().on_surface if is_current else self.get_palette().on_surface_variant,
                    size=responsive.get_font_size(current_screen, 12),
                    weight=ft.FontWeight.W_500 if is_current else ft.FontWeight.NORMAL,
                    text_align=ft.TextAlign.CENTER
                )

                # Step container
                step_container = ft.Column(
                    controls=[step_circle, step_label],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=responsive.get_spacing(current_screen, "xs")
                )

                step_indicators.append(step_container)

                # Add connector line (except for last step)
                if i < len(steps) - 1:
                    connector = ft.Container(
                        height=2,
                        bgcolor=self.get_palette().primary if is_completed else self.get_palette().outline_variant,
                        expand=True,
                        margin=ft.margin.symmetric(horizontal=responsive.get_spacing(current_screen, "sm"))
                    )
                    step_indicators.append(connector)

            return ft.Container(
                content=ft.Row(
                    controls=step_indicators,
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                width=None,
                alignment=ft.alignment.center
            )

        except Exception as e:
            logger.error(f"Error building step indicator: {e}")
            return ft.Container()

    def _build_step_content(self) -> ft.Control:
        """Build current step content."""
        try:
            current_step = self.wizard_data.current_step

            # Get or create step component
            if current_step not in self._step_components:
                self._step_components[current_step] = self._create_step_component(current_step)

            step_component = self._step_components[current_step]

            return ft.Container(
                content=step_component,
                expand=True,
                alignment=ft.alignment.top_center
            )

        except Exception as e:
            logger.error(f"Error building step content: {e}")
            return self._build_error_state("Failed to load step content")

    def _create_step_component(self, step: DeploymentWizardStep) -> ft.Control:
        """Create component for specific wizard step."""
        try:
            if step == DeploymentWizardStep.MODEL_SELECTION:
                return self._build_model_selection_step()
            elif step == DeploymentWizardStep.EXPORT_FORMAT:
                return self._build_export_format_step()
            elif step == DeploymentWizardStep.QUANTIZATION:
                return self._build_quantization_step()
            elif step == DeploymentWizardStep.PLATFORM_TARGET:
                return self._build_platform_target_step()
            elif step == DeploymentWizardStep.OPTIMIZATION:
                return self._build_optimization_step()
            elif step == DeploymentWizardStep.PACKAGE_GENERATION:
                return self._build_package_generation_step()
            elif step == DeploymentWizardStep.COMPLETION:
                return self._build_completion_step()
            else:
                return self._build_error_state(f"Unknown step: {step}")

        except Exception as e:
            logger.error(f"Error creating step component for {step}: {e}")
            return self._build_error_state(f"Failed to create {step.value} step")

    def _build_model_selection_step(self) -> ft.Control:
        """Build model selection step."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Step title and description
            title = ft.Text(
                "Select Model for Deployment",
                style=self.get_text_style("headline_medium"),
                color=self.get_palette().on_surface
            )

            description = ft.Text(
                "Choose the model you want to deploy and review its compatibility information.",
                style=self.get_text_style("body_large"),
                color=self.get_palette().on_surface_variant
            )

            # Model info card
            model_info = self._build_model_info_card()

            # Compatibility check
            compatibility_info = self._build_compatibility_info()

            return ft.Column(
                controls=[
                    title,
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    description,
                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),
                    model_info,
                    ft.Container(height=responsive.get_spacing(current_screen, "md")),
                    compatibility_info
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building model selection step: {e}")
            return self._build_error_state("Failed to load model selection")

    def _build_export_format_step(self) -> ft.Control:
        """Build export format selection step."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Step title and description
            title = ft.Text(
                "Choose Export Format",
                style=self.get_text_style("headline_medium"),
                color=self.get_palette().on_surface
            )

            description = ft.Text(
                "Select the format for your deployed model. Different formats have different compatibility and performance characteristics.",
                style=self.get_text_style("body_large"),
                color=self.get_palette().on_surface_variant
            )

            # Format options
            format_options = []
            for format_type in self.config.supported_formats:
                format_card = self._build_format_option_card(format_type)
                format_options.append(format_card)

            # Format grid
            format_grid = ft.GridView(
                controls=format_options,
                runs_count=responsive.get_columns(current_screen),
                max_extent=responsive.get_size(current_screen, 300),
                child_aspect_ratio=1.2,
                spacing=responsive.get_spacing(current_screen, "md"),
                run_spacing=responsive.get_spacing(current_screen, "md")
            )

            return ft.Column(
                controls=[
                    title,
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    description,
                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),
                    ft.Container(
                        content=format_grid,
                        height=responsive.get_size(current_screen, 400),
                        expand=True
                    )
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building export format step: {e}")
            return self._build_error_state("Failed to load export format selection")

    def _build_quantization_step(self) -> ft.Control:
        """Build quantization configuration step."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Step title and description
            title = ft.Text(
                "Configure Quantization",
                style=self.get_text_style("headline_medium"),
                color=self.get_palette().on_surface
            )

            description = ft.Text(
                "Choose quantization settings to optimize model size and performance. Lower precision reduces size but may affect accuracy.",
                style=self.get_text_style("body_large"),
                color=self.get_palette().on_surface_variant
            )

            # Quantization options
            quantization_options = []
            for quant_type in self.config.supported_quantizations:
                quant_card = self._build_quantization_option_card(quant_type)
                quantization_options.append(quant_card)

            # Quantization grid
            quant_grid = ft.GridView(
                controls=quantization_options,
                runs_count=responsive.get_columns(current_screen),
                max_extent=responsive.get_size(current_screen, 280),
                child_aspect_ratio=1.3,
                spacing=responsive.get_spacing(current_screen, "md"),
                run_spacing=responsive.get_spacing(current_screen, "md")
            )

            # Advanced options
            advanced_options = self._build_quantization_advanced_options()

            return ft.Column(
                controls=[
                    title,
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    description,
                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),
                    ft.Container(
                        content=quant_grid,
                        height=responsive.get_size(current_screen, 300)
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "md")),
                    advanced_options if self.config.show_advanced_options else ft.Container()
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building quantization step: {e}")
            return self._build_error_state("Failed to load quantization configuration")

    def _build_navigation_bar(self) -> ft.Control:
        """Build wizard navigation bar."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            steps = list(DeploymentWizardStep)
            current_index = steps.index(self.wizard_data.current_step)

            # Previous button
            prev_button = ft.OutlinedButton(
                text="Previous",
                icon=self.get_icon("ARROW_BACK"),
                on_click=self._on_previous_clicked,
                disabled=current_index == 0,
                style=ft.ButtonStyle(
                    color=self.get_palette().primary,
                    side=ft.BorderSide(1, self.get_palette().primary)
                )
            )

            # Cancel button
            cancel_button = ft.TextButton(
                text="Cancel",
                on_click=self._on_cancel_clicked,
                style=ft.ButtonStyle(
                    color=self.get_palette().error
                )
            )

            # Next/Complete button
            is_last_step = current_index == len(steps) - 1
            next_button_text = "Complete" if is_last_step else "Next"
            next_button_icon = self.get_icon("CHECK") if is_last_step else self.get_icon("ARROW_FORWARD")

            next_button = ft.ElevatedButton(
                text=next_button_text,
                icon=next_button_icon,
                on_click=self._on_next_clicked,
                disabled=not self._is_current_step_valid(),
                style=ft.ButtonStyle(
                    color=self.get_palette().on_primary,
                    bgcolor=self.get_palette().primary
                )
            )

            # Navigation layout
            return ft.Row(
                controls=[
                    cancel_button,
                    ft.Container(expand=True),  # Spacer
                    prev_button,
                    ft.Container(width=responsive.get_spacing(current_screen, "sm")),
                    next_button
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

        except Exception as e:
            logger.error(f"Error building navigation bar: {e}")
            return ft.Container()

    def _build_progress_overlay(self) -> ft.Control:
        """Build progress overlay for package generation."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Progress content
            progress_content = ft.Column(
                controls=[
                    ft.Text(
                        "Generating Deployment Package",
                        style=self.get_text_style("headline_small"),
                        color=self.get_palette().on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "md")),
                    ft.ProgressBar(
                        value=self.wizard_data.generation_progress.progress_percentage / 100.0,
                        color=self.get_palette().primary,
                        bgcolor=self.get_palette().surface_variant
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    ft.Text(
                        self.wizard_data.generation_progress.current_step,
                        style=self.get_text_style("body_medium"),
                        color=self.get_palette().on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0
            )

            # Progress dialog
            progress_dialog = ft.Container(
                content=progress_content,
                width=responsive.get_size(current_screen, 400),
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().surface,
                border_radius=responsive.get_border_radius(current_screen),
                border=ft.border.all(1, self.get_palette().outline_variant),
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=8,
                    color=self.get_palette().shadow,
                    offset=ft.Offset(0, 4)
                )
            )

            # Overlay container
            return ft.Container(
                content=progress_dialog,
                alignment=ft.alignment.center,
                bgcolor=self.get_color_with_opacity(self.get_palette().surface, 0.8),
                visible=self.wizard_data.generation_progress.status in [
                    PackageGenerationStatus.PREPARING,
                    PackageGenerationStatus.CONVERTING,
                    PackageGenerationStatus.OPTIMIZING,
                    PackageGenerationStatus.PACKAGING
                ]
            )

        except Exception as e:
            logger.error(f"Error building progress overlay: {e}")
            return ft.Container()

    def _build_model_info_card(self) -> ft.Control:
        """Build model information card."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Mock model data (in real implementation, this would come from model registry)
            model_name = f"Model {self.model_id}" if self.model_id else "No Model Selected"
            model_size = "2.3 GB"
            model_architecture = "Transformer"

            # Model info content
            info_content = ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                self.get_icon("MODEL_TRAINING"),
                                color=self.get_palette().primary,
                                size=responsive.get_icon_size(current_screen, "lg")
                            ),
                            ft.Container(width=responsive.get_spacing(current_screen, "md")),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        model_name,
                                        style=self.get_text_style("title_medium"),
                                        color=self.get_palette().on_surface
                                    ),
                                    ft.Text(
                                        f"Architecture: {model_architecture} • Size: {model_size}",
                                        style=self.get_text_style("body_medium"),
                                        color=self.get_palette().on_surface_variant
                                    )
                                ],
                                spacing=responsive.get_spacing(current_screen, "xs"),
                                expand=True
                            )
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    )
                ],
                spacing=0
            )

            return ft.Container(
                content=info_content,
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().surface_variant,
                border_radius=responsive.get_border_radius(current_screen),
                border=ft.border.all(1, self.get_palette().outline_variant)
            )

        except Exception as e:
            logger.error(f"Error building model info card: {e}")
            return ft.Container()

    def _build_compatibility_info(self) -> ft.Control:
        """Build compatibility information display."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Compatibility status
            status_icon = ft.Icon(
                self.get_icon("CHECK_CIRCLE"),
                color=self.get_palette().success,
                size=responsive.get_icon_size(current_screen, "md")
            )

            status_text = ft.Text(
                "Model is compatible with all deployment formats",
                style=self.get_text_style("body_medium"),
                color=self.get_palette().success
            )

            # Supported formats
            format_chips = []
            for format_type in [ExportFormat.ONNX, ExportFormat.PYTORCH, ExportFormat.TENSORFLOW]:
                chip = ft.Container(
                    content=ft.Text(
                        format_type.value.upper(),
                        style=self.get_text_style("label_small"),
                        color=self.get_palette().on_primary_container
                    ),
                    padding=ft.padding.symmetric(
                        horizontal=responsive.get_spacing(current_screen, "sm"),
                        vertical=responsive.get_spacing(current_screen, "xs")
                    ),
                    bgcolor=self.get_palette().primary_container,
                    border_radius=responsive.get_border_radius(current_screen, "sm")
                )
                format_chips.append(chip)

            return ft.Column(
                controls=[
                    ft.Row(
                        controls=[status_icon, status_text],
                        spacing=responsive.get_spacing(current_screen, "sm"),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    ft.Text(
                        "Supported Formats:",
                        style=self.get_text_style("label_medium"),
                        color=self.get_palette().on_surface_variant
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "xs")),
                    ft.Row(
                        controls=format_chips,
                        spacing=responsive.get_spacing(current_screen, "sm"),
                        wrap=True
                    )
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building compatibility info: {e}")
            return ft.Container()

    def _build_format_option_card(self, format_type: ExportFormat) -> ft.Control:
        """Build format option card."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            is_selected = self.wizard_data.deployment_config.export_format == format_type

            # Format descriptions
            format_info = {
                ExportFormat.ONNX: {
                    "title": "ONNX",
                    "description": "Cross-platform standard for ML models",
                    "icon": "SETTINGS",
                    "pros": ["Cross-platform", "Optimized runtime", "Wide support"],
                    "cons": ["Limited features", "Conversion complexity"]
                },
                ExportFormat.PYTORCH: {
                    "title": "PyTorch",
                    "description": "Native PyTorch format with full features",
                    "icon": "PSYCHOLOGY",
                    "pros": ["Full feature support", "Easy debugging", "Native format"],
                    "cons": ["Larger size", "PyTorch dependency"]
                },
                ExportFormat.TENSORFLOW: {
                    "title": "TensorFlow",
                    "description": "TensorFlow SavedModel format",
                    "icon": "MEMORY",
                    "pros": ["TF ecosystem", "Production ready", "Serving support"],
                    "cons": ["TF dependency", "Conversion needed"]
                },
                ExportFormat.GGUF: {
                    "title": "GGUF",
                    "description": "Optimized format for inference",
                    "icon": "SPEED",
                    "pros": ["Small size", "Fast inference", "CPU optimized"],
                    "cons": ["Limited support", "Quantization required"]
                }
            }

            info = format_info.get(format_type, {
                "title": format_type.value.upper(),
                "description": f"{format_type.value} format",
                "icon": "HELP",
                "pros": [],
                "cons": []
            })

            # Card content
            card_content = ft.Column(
                controls=[
                    # Header
                    ft.Row(
                        controls=[
                            ft.Icon(
                                self.get_icon(info["icon"]),
                                color=self.get_palette().primary if is_selected else self.get_palette().on_surface_variant,
                                size=responsive.get_icon_size(current_screen, "md")
                            ),
                            ft.Text(
                                info["title"],
                                style=self.get_text_style("title_medium"),
                                color=self.get_palette().on_surface
                            )
                        ],
                        spacing=responsive.get_spacing(current_screen, "sm"),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),

                    # Description
                    ft.Text(
                        info["description"],
                        style=self.get_text_style("body_small"),
                        color=self.get_palette().on_surface_variant
                    ),

                    # Pros/Cons (if space allows)
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    ft.Text(
                        "✓ " + ", ".join(info["pros"][:2]),
                        style=self.get_text_style("caption"),
                        color=self.get_palette().success,
                        max_lines=2
                    ) if info["pros"] else ft.Container()
                ],
                spacing=responsive.get_spacing(current_screen, "xs"),
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

            # Card container
            return ft.Container(
                content=card_content,
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().primary_container if is_selected else self.get_palette().surface,
                border_radius=responsive.get_border_radius(current_screen),
                border=ft.border.all(
                    2 if is_selected else 1,
                    self.get_palette().primary if is_selected else self.get_palette().outline_variant
                ),
                on_click=lambda e, fmt=format_type: self._on_format_selected(fmt),
                ink=True
            )

        except Exception as e:
            logger.error(f"Error building format option card: {e}")
            return ft.Container()

    def _build_quantization_option_card(self, quant_type: QuantizationType) -> ft.Control:
        """Build quantization option card."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            is_selected = self.wizard_data.deployment_config.quantization_type == quant_type

            # Quantization info
            quant_info = {
                QuantizationType.FP32: {
                    "title": "FP32",
                    "description": "Full precision (32-bit)",
                    "size_reduction": "0%",
                    "accuracy": "100%",
                    "speed": "Baseline"
                },
                QuantizationType.FP16: {
                    "title": "FP16",
                    "description": "Half precision (16-bit)",
                    "size_reduction": "50%",
                    "accuracy": "99%",
                    "speed": "1.5x faster"
                },
                QuantizationType.INT8: {
                    "title": "INT8",
                    "description": "8-bit integer quantization",
                    "size_reduction": "75%",
                    "accuracy": "95%",
                    "speed": "2-3x faster"
                },
                QuantizationType.INT4: {
                    "title": "INT4",
                    "description": "4-bit integer quantization",
                    "size_reduction": "87%",
                    "accuracy": "90%",
                    "speed": "3-4x faster"
                }
            }

            info = quant_info.get(quant_type, {
                "title": quant_type.value.upper(),
                "description": f"{quant_type.value} quantization",
                "size_reduction": "Unknown",
                "accuracy": "Unknown",
                "speed": "Unknown"
            })

            # Card content
            card_content = ft.Column(
                controls=[
                    ft.Text(
                        info["title"],
                        style=self.get_text_style("title_medium"),
                        color=self.get_palette().on_surface
                    ),
                    ft.Text(
                        info["description"],
                        style=self.get_text_style("body_small"),
                        color=self.get_palette().on_surface_variant
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    ft.Column(
                        controls=[
                            ft.Text(
                                f"Size: -{info['size_reduction']}",
                                style=self.get_text_style("caption"),
                                color=self.get_palette().success
                            ),
                            ft.Text(
                                f"Accuracy: {info['accuracy']}",
                                style=self.get_text_style("caption"),
                                color=self.get_palette().on_surface_variant
                            ),
                            ft.Text(
                                f"Speed: {info['speed']}",
                                style=self.get_text_style("caption"),
                                color=self.get_palette().primary
                            )
                        ],
                        spacing=responsive.get_spacing(current_screen, "xs")
                    )
                ],
                spacing=responsive.get_spacing(current_screen, "xs"),
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

            return ft.Container(
                content=card_content,
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().primary_container if is_selected else self.get_palette().surface,
                border_radius=responsive.get_border_radius(current_screen),
                border=ft.border.all(
                    2 if is_selected else 1,
                    self.get_palette().primary if is_selected else self.get_palette().outline_variant
                ),
                on_click=lambda e, qt=quant_type: self._on_quantization_selected(qt),
                ink=True
            )

        except Exception as e:
            logger.error(f"Error building quantization option card: {e}")
            return ft.Container()

    def _build_error_state(self, message: str) -> ft.Control:
        """Build error state display."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            self.get_icon("ERROR"),
                            color=self.get_palette().error,
                            size=responsive.get_icon_size(current_screen, "xl")
                        ),
                        ft.Container(height=responsive.get_spacing(current_screen, "md")),
                        ft.Text(
                            "Error",
                            style=self.get_text_style("headline_small"),
                            color=self.get_palette().error,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                        ft.Text(
                            message,
                            style=self.get_text_style("body_medium"),
                            color=self.get_palette().on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    # Event Handlers
    def _on_previous_clicked(self, e: ft.ControlEvent) -> None:
        """Handle previous button click."""
        try:
            steps = list(DeploymentWizardStep)
            current_index = steps.index(self.wizard_data.current_step)

            if current_index > 0:
                self.wizard_data.current_step = steps[current_index - 1]
                self._update_wizard_display()

                if self.on_step_changed:
                    self.on_step_changed(self.wizard_data.current_step)

        except Exception as e:
            logger.error(f"Error handling previous click: {e}")

    def _on_next_clicked(self, e: ft.ControlEvent) -> None:
        """Handle next button click."""
        try:
            if not self._is_current_step_valid():
                return

            steps = list(DeploymentWizardStep)
            current_index = steps.index(self.wizard_data.current_step)

            if current_index < len(steps) - 1:
                # Move to next step
                self.wizard_data.current_step = steps[current_index + 1]
                self._update_wizard_display()

                if self.on_step_changed:
                    self.on_step_changed(self.wizard_data.current_step)
            else:
                # Complete wizard
                self._complete_wizard()

        except Exception as e:
            logger.error(f"Error handling next click: {e}")

    def _on_cancel_clicked(self, e: ft.ControlEvent) -> None:
        """Handle cancel button click."""
        try:
            if self.on_wizard_cancelled:
                self.on_wizard_cancelled()
        except Exception as e:
            logger.error(f"Error handling cancel click: {e}")

    def _on_format_selected(self, format_type: ExportFormat) -> None:
        """Handle export format selection."""
        try:
            self.wizard_data.deployment_config.export_format = format_type
            self._validate_current_step()
            self._update_wizard_display()

        except Exception as e:
            logger.error(f"Error handling format selection: {e}")

    def _on_quantization_selected(self, quant_type: QuantizationType) -> None:
        """Handle quantization type selection."""
        try:
            self.wizard_data.deployment_config.quantization_type = quant_type
            self._validate_current_step()
            self._update_wizard_display()

        except Exception as e:
            logger.error(f"Error handling quantization selection: {e}")

    # Helper Methods
    def _is_current_step_valid(self) -> bool:
        """Check if current step is valid."""
        try:
            current_step = self.wizard_data.current_step

            if current_step == DeploymentWizardStep.MODEL_SELECTION:
                return bool(self.wizard_data.deployment_config.model_id)
            elif current_step == DeploymentWizardStep.EXPORT_FORMAT:
                return self.wizard_data.deployment_config.export_format is not None
            elif current_step == DeploymentWizardStep.QUANTIZATION:
                return self.wizard_data.deployment_config.quantization_type is not None
            elif current_step == DeploymentWizardStep.PLATFORM_TARGET:
                return len(self.wizard_data.deployment_config.platform_targets) > 0
            elif current_step == DeploymentWizardStep.OPTIMIZATION:
                return True  # Always valid
            elif current_step == DeploymentWizardStep.PACKAGE_GENERATION:
                return self.wizard_data.generation_progress.status == PackageGenerationStatus.COMPLETED
            else:
                return True

        except Exception as e:
            logger.error(f"Error validating current step: {e}")
            return False

    def _validate_current_step(self) -> None:
        """Validate current step and update validation state."""
        try:
            is_valid = self._is_current_step_valid()
            self.wizard_data.step_validation[self.wizard_data.current_step] = is_valid

        except Exception as e:
            logger.error(f"Error validating current step: {e}")

    def _update_wizard_display(self) -> None:
        """Update wizard display after state change."""
        try:
            # Rebuild step content
            self._step_content.content = self._create_step_component(self.wizard_data.current_step)

            # Rebuild step indicator
            self._step_indicator.content = self._build_step_indicator().content

            # Rebuild navigation
            self._navigation_bar.content = self._build_navigation_bar().content

            # Update the display
            self.update()

        except Exception as e:
            logger.error(f"Error updating wizard display: {e}")

    def _complete_wizard(self) -> None:
        """Complete the deployment wizard."""
        try:
            if self.on_deployment_completed and self.wizard_data.deployment_config.model_id:
                # Generate package path
                package_path = f"deployment_package_{self.wizard_data.deployment_config.model_id}"
                self.on_deployment_completed(self.wizard_data.deployment_config.model_id, package_path)

        except Exception as e:
            logger.error(f"Error completing wizard: {e}")

    # Placeholder methods for remaining steps
    def _build_platform_target_step(self) -> ft.Control:
        """Build platform target selection step."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Step title and description
            title = ft.Text(
                "Select Target Platforms",
                style=self.get_text_style("headline_medium"),
                color=self.get_palette().on_surface
            )

            description = ft.Text(
                "Choose the platforms where your model will be deployed. You can select multiple platforms.",
                style=self.get_text_style("body_large"),
                color=self.get_palette().on_surface_variant
            )

            # Platform options
            platform_options = []
            for platform in self.config.supported_platforms:
                platform_card = self._build_platform_option_card(platform)
                platform_options.append(platform_card)

            # Platform grid
            platform_grid = ft.GridView(
                controls=platform_options,
                runs_count=responsive.get_columns(current_screen),
                max_extent=responsive.get_size(current_screen, 250),
                child_aspect_ratio=1.5,
                spacing=responsive.get_spacing(current_screen, "md"),
                run_spacing=responsive.get_spacing(current_screen, "md")
            )

            return ft.Column(
                controls=[
                    title,
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    description,
                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),
                    ft.Container(
                        content=platform_grid,
                        height=responsive.get_size(current_screen, 300),
                        expand=True
                    )
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building platform target step: {e}")
            return self._build_error_state("Failed to load platform selection")

    def _build_optimization_step(self) -> ft.Control:
        """Build optimization configuration step."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Step title and description
            title = ft.Text(
                "Optimization Settings",
                style=self.get_text_style("headline_medium"),
                color=self.get_palette().on_surface
            )

            description = ft.Text(
                "Configure optimization settings to balance model size and performance for your deployment needs.",
                style=self.get_text_style("body_large"),
                color=self.get_palette().on_surface_variant
            )

            # Optimization level selector
            optimization_selector = self._build_optimization_level_selector()

            # Advanced options
            advanced_options = self._build_optimization_advanced_options()

            return ft.Column(
                controls=[
                    title,
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    description,
                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),
                    optimization_selector,
                    ft.Container(height=responsive.get_spacing(current_screen, "md")),
                    advanced_options if self.config.show_advanced_options else ft.Container()
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building optimization step: {e}")
            return self._build_error_state("Failed to load optimization settings")

    def _build_package_generation_step(self) -> ft.Control:
        """Build package generation step."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Step title and description
            title = ft.Text(
                "Generate Deployment Package",
                style=self.get_text_style("headline_medium"),
                color=self.get_palette().on_surface
            )

            description = ft.Text(
                "Review your configuration and generate the deployment package.",
                style=self.get_text_style("body_large"),
                color=self.get_palette().on_surface_variant
            )

            # Configuration summary
            config_summary = self._build_configuration_summary()

            # Generation controls
            generation_controls = self._build_generation_controls()

            return ft.Column(
                controls=[
                    title,
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    description,
                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),
                    config_summary,
                    ft.Container(height=responsive.get_spacing(current_screen, "md")),
                    generation_controls
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building package generation step: {e}")
            return self._build_error_state("Failed to load package generation")

    def _build_completion_step(self) -> ft.Control:
        """Build completion step."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Success content
            success_content = ft.Column(
                controls=[
                    ft.Icon(
                        self.get_icon("CHECK_CIRCLE"),
                        color=self.get_palette().success,
                        size=responsive.get_icon_size(current_screen, "xl")
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),
                    ft.Text(
                        "Deployment Package Created Successfully!",
                        style=self.get_text_style("headline_medium"),
                        color=self.get_palette().on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "md")),
                    ft.Text(
                        "Your model has been packaged and is ready for deployment.",
                        style=self.get_text_style("body_large"),
                        color=self.get_palette().on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),

                    # Package info
                    self._build_package_info_card(),

                    ft.Container(height=responsive.get_spacing(current_screen, "lg")),

                    # Action buttons
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                text="Open Package Location",
                                icon=self.get_icon("FOLDER_OPEN"),
                                on_click=self._on_open_package_location,
                                style=ft.ButtonStyle(
                                    color=self.get_palette().primary,
                                    side=ft.BorderSide(1, self.get_palette().primary)
                                )
                            ),
                            ft.ElevatedButton(
                                text="Create Another Package",
                                icon=self.get_icon("ADD"),
                                on_click=self._on_create_another_package,
                                style=ft.ButtonStyle(
                                    color=self.get_palette().on_primary,
                                    bgcolor=self.get_palette().primary
                                )
                            )
                        ],
                        spacing=responsive.get_spacing(current_screen, "md"),
                        alignment=ft.MainAxisAlignment.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0
            )

            return ft.Container(
                content=success_content,
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building completion step: {e}")
            return self._build_error_state("Failed to load completion step")

    def _build_platform_option_card(self, platform: PlatformTarget) -> ft.Control:
        """Build platform option card."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            is_selected = platform in self.wizard_data.deployment_config.platform_targets

            # Platform info
            platform_info = {
                PlatformTarget.WINDOWS: {
                    "title": "Windows",
                    "icon": "COMPUTER",
                    "description": "Windows 10/11 desktop"
                },
                PlatformTarget.MACOS: {
                    "title": "macOS",
                    "icon": "LAPTOP_MAC",
                    "description": "macOS 10.15+ systems"
                },
                PlatformTarget.LINUX: {
                    "title": "Linux",
                    "icon": "TERMINAL",
                    "description": "Linux distributions"
                },
                PlatformTarget.ANDROID: {
                    "title": "Android",
                    "icon": "PHONE_ANDROID",
                    "description": "Android mobile devices"
                },
                PlatformTarget.IOS: {
                    "title": "iOS",
                    "icon": "PHONE_IPHONE",
                    "description": "iPhone and iPad"
                },
                PlatformTarget.WEB: {
                    "title": "Web",
                    "icon": "WEB",
                    "description": "Web browsers"
                }
            }

            info = platform_info.get(platform, {
                "title": platform.value.title(),
                "icon": "HELP",
                "description": f"{platform.value} platform"
            })

            # Card content
            card_content = ft.Column(
                controls=[
                    ft.Icon(
                        self.get_icon(info["icon"]),
                        color=self.get_palette().primary if is_selected else self.get_palette().on_surface_variant,
                        size=responsive.get_icon_size(current_screen, "lg")
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    ft.Text(
                        info["title"],
                        style=self.get_text_style("title_medium"),
                        color=self.get_palette().on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        info["description"],
                        style=self.get_text_style("body_small"),
                        color=self.get_palette().on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=responsive.get_spacing(current_screen, "xs")
            )

            return ft.Container(
                content=card_content,
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().primary_container if is_selected else self.get_palette().surface,
                border_radius=responsive.get_border_radius(current_screen),
                border=ft.border.all(
                    2 if is_selected else 1,
                    self.get_palette().primary if is_selected else self.get_palette().outline_variant
                ),
                on_click=lambda e, p=platform: self._on_platform_selected(p),
                ink=True
            )

        except Exception as e:
            logger.error(f"Error building platform option card: {e}")
            return ft.Container()

    def _build_optimization_level_selector(self) -> ft.Control:
        """Build optimization level selector."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Optimization options
            optimization_options = []
            for opt_level in OptimizationLevel:
                if opt_level != OptimizationLevel.CUSTOM:  # Skip custom for now
                    option_card = self._build_optimization_option_card(opt_level)
                    optimization_options.append(option_card)

            return ft.Column(
                controls=[
                    ft.Text(
                        "Optimization Level",
                        style=self.get_text_style("title_medium"),
                        color=self.get_palette().on_surface
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                    ft.Row(
                        controls=optimization_options,
                        spacing=responsive.get_spacing(current_screen, "md"),
                        wrap=True
                    )
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building optimization level selector: {e}")
            return ft.Container()

    def _build_optimization_option_card(self, opt_level: OptimizationLevel) -> ft.Control:
        """Build optimization option card."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            is_selected = self.wizard_data.deployment_config.optimization_level == opt_level

            # Optimization info
            opt_info = {
                OptimizationLevel.SIZE_OPTIMIZED: {
                    "title": "Size Optimized",
                    "description": "Minimize package size",
                    "icon": "COMPRESS"
                },
                OptimizationLevel.BALANCED: {
                    "title": "Balanced",
                    "description": "Balance size and performance",
                    "icon": "BALANCE"
                },
                OptimizationLevel.PERFORMANCE_OPTIMIZED: {
                    "title": "Performance Optimized",
                    "description": "Maximize inference speed",
                    "icon": "SPEED"
                }
            }

            info = opt_info.get(opt_level, {
                "title": opt_level.value.replace("_", " ").title(),
                "description": f"{opt_level.value} optimization",
                "icon": "SETTINGS"
            })

            # Card content
            card_content = ft.Column(
                controls=[
                    ft.Icon(
                        self.get_icon(info["icon"]),
                        color=self.get_palette().primary if is_selected else self.get_palette().on_surface_variant,
                        size=responsive.get_icon_size(current_screen, "md")
                    ),
                    ft.Container(height=responsive.get_spacing(current_screen, "xs")),
                    ft.Text(
                        info["title"],
                        style=self.get_text_style("label_large"),
                        color=self.get_palette().on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        info["description"],
                        style=self.get_text_style("caption"),
                        color=self.get_palette().on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0
            )

            return ft.Container(
                content=card_content,
                padding=ft.padding.all(responsive.get_padding(current_screen, "sm")),
                bgcolor=self.get_palette().primary_container if is_selected else self.get_palette().surface,
                border_radius=responsive.get_border_radius(current_screen),
                border=ft.border.all(
                    2 if is_selected else 1,
                    self.get_palette().primary if is_selected else self.get_palette().outline_variant
                ),
                on_click=lambda e, opt=opt_level: self._on_optimization_selected(opt),
                ink=True,
                width=responsive.get_size(current_screen, 150)
            )

        except Exception as e:
            logger.error(f"Error building optimization option card: {e}")
            return ft.Container()

    def _build_quantization_advanced_options(self) -> ft.Control:
        """Build advanced quantization options."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Advanced Options",
                            style=self.get_text_style("title_small"),
                            color=self.get_palette().on_surface
                        ),
                        ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                        ft.Checkbox(
                            label="Enable dynamic quantization",
                            value=False,
                            on_change=self._on_dynamic_quantization_changed
                        ),
                        ft.Checkbox(
                            label="Optimize for mobile deployment",
                            value=False,
                            on_change=self._on_mobile_optimization_changed
                        )
                    ],
                    spacing=responsive.get_spacing(current_screen, "xs")
                ),
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().surface_variant,
                border_radius=responsive.get_border_radius(current_screen)
            )

        except Exception as e:
            logger.error(f"Error building quantization advanced options: {e}")
            return ft.Container()

    # Additional event handlers
    def _on_platform_selected(self, platform: PlatformTarget) -> None:
        """Handle platform selection."""
        try:
            if platform in self.wizard_data.deployment_config.platform_targets:
                self.wizard_data.deployment_config.platform_targets.remove(platform)
            else:
                self.wizard_data.deployment_config.platform_targets.add(platform)

            self._validate_current_step()
            self._update_wizard_display()

        except Exception as e:
            logger.error(f"Error handling platform selection: {e}")

    def _on_optimization_selected(self, opt_level: OptimizationLevel) -> None:
        """Handle optimization level selection."""
        try:
            self.wizard_data.deployment_config.optimization_level = opt_level
            self._validate_current_step()
            self._update_wizard_display()

        except Exception as e:
            logger.error(f"Error handling optimization selection: {e}")

    def _on_dynamic_quantization_changed(self, e: ft.ControlEvent) -> None:
        """Handle dynamic quantization option change."""
        try:
            # Store in custom optimization config
            if "quantization" not in self.wizard_data.deployment_config.custom_optimization:
                self.wizard_data.deployment_config.custom_optimization["quantization"] = {}

            self.wizard_data.deployment_config.custom_optimization["quantization"]["dynamic"] = e.control.value

        except Exception as e:
            logger.error(f"Error handling dynamic quantization change: {e}")

    def _on_mobile_optimization_changed(self, e: ft.ControlEvent) -> None:
        """Handle mobile optimization option change."""
        try:
            # Store in custom optimization config
            if "mobile" not in self.wizard_data.deployment_config.custom_optimization:
                self.wizard_data.deployment_config.custom_optimization["mobile"] = {}

            self.wizard_data.deployment_config.custom_optimization["mobile"]["enabled"] = e.control.value

        except Exception as e:
            logger.error(f"Error handling mobile optimization change: {e}")

    def _on_open_package_location(self, e: ft.ControlEvent) -> None:
        """Handle open package location click."""
        try:
            # In a real implementation, this would open the file explorer
            logger.info("Opening package location")

        except Exception as e:
            logger.error(f"Error opening package location: {e}")

    def _on_create_another_package(self, e: ft.ControlEvent) -> None:
        """Handle create another package click."""
        try:
            # Reset wizard to first step
            self.wizard_data.current_step = DeploymentWizardStep.MODEL_SELECTION
            self.wizard_data.generation_progress = PackageGenerationProgress()

            # Clear step validation except model selection
            for step in DeploymentWizardStep:
                if step != DeploymentWizardStep.MODEL_SELECTION:
                    self.wizard_data.step_validation[step] = False

            self._update_wizard_display()

        except Exception as e:
            logger.error(f"Error creating another package: {e}")

    def _build_configuration_summary(self) -> ft.Control:
        """Build configuration summary display."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            config = self.wizard_data.deployment_config

            # Summary items
            summary_items = [
                ("Model", config.model_id or "Not selected"),
                ("Export Format", config.export_format.value.upper() if config.export_format else "Not selected"),
                ("Quantization", config.quantization_type.value.upper() if config.quantization_type else "Not selected"),
                ("Platforms", ", ".join([p.value.title() for p in config.platform_targets]) if config.platform_targets else "None selected"),
                ("Optimization", config.optimization_level.value.replace("_", " ").title())
            ]

            summary_controls = []
            for label, value in summary_items:
                summary_controls.append(
                    ft.Row(
                        controls=[
                            ft.Text(
                                f"{label}:",
                                style=self.get_text_style("label_medium"),
                                color=self.get_palette().on_surface_variant,
                                width=responsive.get_size(current_screen, 120)
                            ),
                            ft.Text(
                                value,
                                style=self.get_text_style("body_medium"),
                                color=self.get_palette().on_surface,
                                expand=True
                            )
                        ],
                        spacing=responsive.get_spacing(current_screen, "sm")
                    )
                )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Configuration Summary",
                            style=self.get_text_style("title_medium"),
                            color=self.get_palette().on_surface
                        ),
                        ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                        *summary_controls
                    ],
                    spacing=responsive.get_spacing(current_screen, "xs")
                ),
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().surface_variant,
                border_radius=responsive.get_border_radius(current_screen),
                border=ft.border.all(1, self.get_palette().outline_variant)
            )

        except Exception as e:
            logger.error(f"Error building configuration summary: {e}")
            return ft.Container()

    def _build_generation_controls(self) -> ft.Control:
        """Build package generation controls."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            # Generation button
            generate_button = ft.ElevatedButton(
                text="Generate Package",
                icon=self.get_icon("BUILD"),
                on_click=self._on_generate_package_clicked,
                disabled=self.wizard_data.generation_progress.status in [
                    PackageGenerationStatus.PREPARING,
                    PackageGenerationStatus.CONVERTING,
                    PackageGenerationStatus.OPTIMIZING,
                    PackageGenerationStatus.PACKAGING
                ],
                style=ft.ButtonStyle(
                    color=self.get_palette().on_primary,
                    bgcolor=self.get_palette().primary
                )
            )

            # Progress display
            progress_display = ft.Container()
            if self.wizard_data.generation_progress.status != PackageGenerationStatus.NOT_STARTED:
                progress_display = self._build_generation_progress_display()

            return ft.Column(
                controls=[
                    generate_button,
                    ft.Container(height=responsive.get_spacing(current_screen, "md")),
                    progress_display
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )

        except Exception as e:
            logger.error(f"Error building generation controls: {e}")
            return ft.Container()

    def _build_generation_progress_display(self) -> ft.Control:
        """Build generation progress display."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            progress = self.wizard_data.generation_progress

            # Status color
            status_color = self.get_palette().primary
            if progress.status == PackageGenerationStatus.COMPLETED:
                status_color = self.get_palette().success
            elif progress.status == PackageGenerationStatus.FAILED:
                status_color = self.get_palette().error

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Status: {progress.status.value.replace('_', ' ').title()}",
                            style=self.get_text_style("label_medium"),
                            color=status_color
                        ),
                        ft.Container(height=responsive.get_spacing(current_screen, "xs")),
                        ft.ProgressBar(
                            value=progress.progress_percentage / 100.0,
                            color=status_color,
                            bgcolor=self.get_palette().surface_variant
                        ),
                        ft.Container(height=responsive.get_spacing(current_screen, "xs")),
                        ft.Text(
                            progress.current_step,
                            style=self.get_text_style("body_small"),
                            color=self.get_palette().on_surface_variant
                        )
                    ],
                    spacing=0
                ),
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().surface_variant,
                border_radius=responsive.get_border_radius(current_screen)
            )

        except Exception as e:
            logger.error(f"Error building generation progress display: {e}")
            return ft.Container()

    def _build_package_info_card(self) -> ft.Control:
        """Build package information card."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            progress = self.wizard_data.generation_progress

            # Package info
            package_info = [
                ("Package Size", f"{progress.package_size_mb:.1f} MB" if progress.package_size_mb else "Unknown"),
                ("Files Generated", str(len(progress.generated_files))),
                ("Format", self.wizard_data.deployment_config.export_format.value.upper() if self.wizard_data.deployment_config.export_format else "Unknown"),
                ("Platforms", str(len(self.wizard_data.deployment_config.platform_targets)))
            ]

            info_controls = []
            for label, value in package_info:
                info_controls.append(
                    ft.Row(
                        controls=[
                            ft.Text(
                                f"{label}:",
                                style=self.get_text_style("label_medium"),
                                color=self.get_palette().on_surface_variant,
                                width=responsive.get_size(current_screen, 120)
                            ),
                            ft.Text(
                                value,
                                style=self.get_text_style("body_medium"),
                                color=self.get_palette().on_surface,
                                expand=True
                            )
                        ],
                        spacing=responsive.get_spacing(current_screen, "sm")
                    )
                )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Package Information",
                            style=self.get_text_style("title_medium"),
                            color=self.get_palette().on_surface
                        ),
                        ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                        *info_controls
                    ],
                    spacing=responsive.get_spacing(current_screen, "xs")
                ),
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().surface_variant,
                border_radius=responsive.get_border_radius(current_screen),
                border=ft.border.all(1, self.get_palette().outline_variant)
            )

        except Exception as e:
            logger.error(f"Error building package info card: {e}")
            return ft.Container()

    def _build_optimization_advanced_options(self) -> ft.Control:
        """Build advanced optimization options."""
        try:
            responsive = self.get_responsive_layout()
            current_screen = responsive.get_current_screen_size()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Advanced Options",
                            style=self.get_text_style("title_small"),
                            color=self.get_palette().on_surface
                        ),
                        ft.Container(height=responsive.get_spacing(current_screen, "sm")),
                        ft.Checkbox(
                            label="Include runtime dependencies",
                            value=self.wizard_data.deployment_config.include_runtime,
                            on_change=self._on_include_runtime_changed
                        ),
                        ft.Checkbox(
                            label="Enable compression",
                            value=self.wizard_data.deployment_config.compression_enabled,
                            on_change=self._on_compression_changed
                        )
                    ],
                    spacing=responsive.get_spacing(current_screen, "xs")
                ),
                padding=ft.padding.all(responsive.get_padding(current_screen)),
                bgcolor=self.get_palette().surface_variant,
                border_radius=responsive.get_border_radius(current_screen)
            )

        except Exception as e:
            logger.error(f"Error building optimization advanced options: {e}")
            return ft.Container()

    def _on_generate_package_clicked(self, e: ft.ControlEvent) -> None:
        """Handle generate package button click."""
        try:
            # Start package generation simulation
            self.wizard_data.generation_progress.status = PackageGenerationStatus.PREPARING
            self.wizard_data.generation_progress.current_step = "Preparing model files..."
            self.wizard_data.generation_progress.progress_percentage = 10.0

            # Update display
            self._update_wizard_display()

            # In a real implementation, this would trigger actual package generation
            logger.info("Starting package generation")

        except Exception as e:
            logger.error(f"Error handling generate package click: {e}")

    def _on_include_runtime_changed(self, e: ft.ControlEvent) -> None:
        """Handle include runtime option change."""
        try:
            self.wizard_data.deployment_config.include_runtime = e.control.value
        except Exception as e:
            logger.error(f"Error handling include runtime change: {e}")

    def _on_compression_changed(self, e: ft.ControlEvent) -> None:
        """Handle compression option change."""
        try:
            self.wizard_data.deployment_config.compression_enabled = e.control.value
        except Exception as e:
            logger.error(f"Error handling compression change: {e}")

    # Public API methods
    def set_model_id(self, model_id: str) -> None:
        """Set the model ID for deployment."""
        try:
            self.model_id = model_id
            self.wizard_data.deployment_config.model_id = model_id
            self.wizard_data.step_validation[DeploymentWizardStep.MODEL_SELECTION] = True

            if self._is_built:
                self._update_wizard_display()

        except Exception as e:
            logger.error(f"Error setting model ID: {e}")

    def get_deployment_configuration(self) -> DeploymentConfiguration:
        """Get current deployment configuration."""
        return self.wizard_data.deployment_config

    def reset_wizard(self) -> None:
        """Reset wizard to initial state."""
        try:
            self.wizard_data = DeploymentWizardData()
            if self.model_id:
                self.wizard_data.deployment_config.model_id = self.model_id

            self._initialize_wizard_data()

            if self._is_built:
                self._update_wizard_display()

        except Exception as e:
            logger.error(f"Error resetting wizard: {e}")
