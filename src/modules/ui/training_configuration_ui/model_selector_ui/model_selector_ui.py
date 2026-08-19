"""
Module: model_selector_ui
Description: Comprehensive model architecture selection interface with hardware compatibility checks,
            performance estimation, and configuration options. Provides intuitive selection of model
            architectures (1B, 3B, 7B parameters), quantization types, optimization levels, and
            advanced model settings with real-time validation and responsive design.
Phase: 4
Location: /src/modules/ui/training_configuration_ui/model_selector_ui/model_selector_ui.py
"""

# Standard library imports
import asyncio
import logging
import psutil
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl

# Training orchestration imports
try:
    from src.modules.logic.training_orchestration_lg.base_interfaces import (
        TrainingConfig,
        HyperparameterConfig,
        OptimizationStrategy
    )
    from src.modules.database.model_repository_db.model_dao_db.model_dao_db import (
        ModelArchitecture as DBModelArchitecture,
        QuantizationType as DBQuantizationType,
        ModelMetadata
    )
    TRAINING_ORCHESTRATION_AVAILABLE = True
except ImportError:
    TrainingConfig = None
    HyperparameterConfig = None
    OptimizationStrategy = None
    DBModelArchitecture = None
    DBQuantizationType = None
    ModelMetadata = None
    TRAINING_ORCHESTRATION_AVAILABLE = False

# Inference engine imports
try:
    from src.modules.logic.inference_engine_lg.base_interfaces import (
        ModelType,
        ModelFormat,
        TokenizerType
    )
    INFERENCE_ENGINE_AVAILABLE = True
except ImportError:
    ModelType = None
    ModelFormat = None
    TokenizerType = None
    INFERENCE_ENGINE_AVAILABLE = False


class ModelArchitecture(Enum):
    """Model architecture enumeration for UI."""
    SMALL_1B = "1B"
    MEDIUM_3B = "3B"
    LARGE_7B = "7B"


class ModelSize(Enum):
    """Model size categories."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class QuantizationType(Enum):
    """Model quantization types."""
    INT4 = "INT4"
    INT8 = "INT8"
    FP16 = "FP16"
    FP32 = "FP32"


class OptimizationLevel(Enum):
    """Model optimization levels."""
    BASIC = "basic"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    MAXIMUM = "maximum"


class ModelSelectionMode(Enum):
    """Model selection modes."""
    QUICK_SELECT = "quick_select"
    ADVANCED_CONFIG = "advanced_config"
    CUSTOM_MODEL = "custom_model"


class CompatibilityLevel(Enum):
    """Hardware compatibility levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    INCOMPATIBLE = "incompatible"


@dataclass
class ModelCompatibilityResult:
    """Model hardware compatibility assessment result."""
    architecture: ModelArchitecture
    quantization: QuantizationType
    compatibility_level: CompatibilityLevel
    performance_score: float  # 0.0 to 1.0
    memory_requirement_gb: float
    estimated_training_time_hours: float
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    hardware_requirements: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelConfiguration:
    """Complete model configuration."""
    architecture: ModelArchitecture
    quantization: QuantizationType
    optimization_level: OptimizationLevel
    model_type: Optional[str] = None
    base_model_path: Optional[str] = None
    custom_config: Dict[str, Any] = field(default_factory=dict)
    enable_mixed_precision: bool = True
    gradient_checkpointing: bool = False
    use_flash_attention: bool = False
    custom_tokenizer: Optional[str] = None


@dataclass
class ModelSelectionConfig:
    """Configuration for model selection interface."""
    mode: ModelSelectionMode = ModelSelectionMode.QUICK_SELECT
    show_compatibility_checks: bool = True
    show_performance_estimates: bool = True
    show_advanced_options: bool = False
    enable_custom_models: bool = False
    default_architecture: ModelArchitecture = ModelArchitecture.SMALL_1B
    default_quantization: QuantizationType = QuantizationType.FP16


class ModelSelectorUI(ThemeAwareUserControl):
    """
    Comprehensive model architecture selection interface.
    
    Provides intuitive selection of model architectures with real-time hardware
    compatibility checks, performance estimation, and advanced configuration options.
    
    Features:
    - Interactive model architecture selection (1B, 3B, 7B parameters)
    - Real-time hardware compatibility validation
    - Performance estimation and resource requirements
    - Quantization and optimization configuration
    - Responsive design with theme integration
    - Advanced model configuration options
    """
    
    def __init__(self, 
                 on_model_change: Optional[Callable[[ModelConfiguration], None]] = None,
                 config: Optional[ModelSelectionConfig] = None,
                 initial_config: Optional[ModelConfiguration] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self._logger = logging.getLogger(__name__)
        
        # Configuration
        self._config = config or ModelSelectionConfig()
        self._on_model_change = on_model_change
        
        # State management
        self._current_config = initial_config or ModelConfiguration(
            architecture=self._config.default_architecture,
            quantization=self._config.default_quantization,
            optimization_level=OptimizationLevel.STANDARD
        )
        self._compatibility_results: Dict[Tuple[ModelArchitecture, QuantizationType], ModelCompatibilityResult] = {}
        self._is_checking_compatibility = False
        
        # UI components
        self._architecture_cards: Dict[ModelArchitecture, ft.Container] = {}
        self._quantization_dropdown: Optional[ft.Dropdown] = None
        self._optimization_dropdown: Optional[ft.Dropdown] = None
        self._compatibility_panel: Optional[ft.Container] = None
        self._advanced_panel: Optional[ft.Container] = None
        self._performance_indicator: Optional[ft.Container] = None
        
        # Model information
        self._model_info = {
            ModelArchitecture.SMALL_1B: {
                "title": "Small Model (1B)",
                "description": "Lightweight model for basic tasks and limited resources",
                "parameters": "1 Billion",
                "memory_min": "2-4 GB",
                "memory_recommended": "6-8 GB",
                "use_cases": ["Basic Q&A", "Simple text generation", "Resource-constrained environments"],
                "icon": ft.Icons.MEMORY
            },
            ModelArchitecture.MEDIUM_3B: {
                "title": "Medium Model (3B)",
                "description": "Balanced model for general-purpose applications",
                "parameters": "3 Billion",
                "memory_min": "6-8 GB",
                "memory_recommended": "12-16 GB",
                "use_cases": ["General Q&A", "Document analysis", "Code assistance"],
                "icon": ft.Icons.PSYCHOLOGY
            },
            ModelArchitecture.LARGE_7B: {
                "title": "Large Model (7B)",
                "description": "High-performance model for complex tasks",
                "parameters": "7 Billion",
                "memory_min": "12-16 GB",
                "memory_recommended": "24-32 GB",
                "use_cases": ["Complex reasoning", "Advanced analysis", "Professional applications"],
                "icon": ft.Icons.ROCKET_LAUNCH
            }
        }
        
        # Initialize compatibility checking
        self._initialize_compatibility_checking()
    
    def _initialize_compatibility_checking(self) -> None:
        """Initialize hardware compatibility checking."""
        try:
            # Get system information
            self._system_memory_gb = psutil.virtual_memory().total / (1024**3)
            self._system_cpu_count = psutil.cpu_count()
            
            # Check for GPU availability (simplified check)
            self._has_gpu = False
            try:
                import torch
                self._has_gpu = torch.cuda.is_available()
                if self._has_gpu:
                    self._gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                else:
                    self._gpu_memory_gb = 0
            except ImportError:
                self._gpu_memory_gb = 0
                
        except Exception as e:
            self._logger.warning(f"Failed to initialize hardware detection: {e}")
            self._system_memory_gb = 8.0  # Default assumption
            self._system_cpu_count = 4
            self._has_gpu = False
            self._gpu_memory_gb = 0

    def get_current_configuration(self) -> ModelConfiguration:
        """Get the current model configuration."""
        return self._current_config

    def set_configuration(self, config: ModelConfiguration) -> None:
        """Set the model configuration."""
        self._current_config = config
        self._update_ui_from_config()
        if self._on_model_change:
            self._on_model_change(config)

    def build(self) -> ft.Control:
        """Build the model selector interface."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create main layout based on mode
        if self._config.mode == ModelSelectionMode.QUICK_SELECT:
            content = self._create_quick_select_layout()
        elif self._config.mode == ModelSelectionMode.ADVANCED_CONFIG:
            content = self._create_advanced_config_layout()
        else:
            content = self._create_custom_model_layout()

        return self.create_responsive_container(
            content=ft.Column([
                self._create_header(),
                ft.Divider(color=palette.outline_variant),
                content,
                ft.Divider(color=palette.outline_variant) if self._config.show_compatibility_checks else None,
                self._create_compatibility_panel() if self._config.show_compatibility_checks else None
            ], spacing=spacing.section_spacing),
            padding=self.get_breakpoint_value(
                mobile=spacing.container_padding,
                tablet=spacing.container_padding + 4,
                desktop=spacing.container_padding + 8,
                large=spacing.container_padding + 12
            )
        )

    def _create_header(self) -> ft.Control:
        """Create the header section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Row([
            ft.Icon(
                ft.Icons.ARCHITECTURE,
                color=palette.primary,
                size=self.get_breakpoint_value(mobile=24, tablet=28, desktop=32, large=36)
            ),
            ft.Column([
                ft.Text(
                    "Model Architecture Selection",
                    style=typography.heading_medium,
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_600
                ),
                ft.Text(
                    "Choose the model architecture and configuration for your training",
                    style=typography.body_medium,
                    color=palette.on_surface_variant
                )
            ], spacing=spacing.element_spacing // 2, expand=True)
        ], spacing=spacing.element_spacing)

    def _create_quick_select_layout(self) -> ft.Control:
        """Create quick select layout with architecture cards."""
        spacing = self.get_spacing()

        # Create architecture selection cards
        architecture_cards = self._create_architecture_cards()

        # Create configuration options
        config_options = self._create_configuration_options()

        return ft.Column([
            ft.Text(
                "Select Model Architecture",
                style=self.get_typography().heading_small,
                color=self.get_palette().on_surface,
                weight=ft.FontWeight.W_500
            ),
            self.create_responsive_grid(
                children=architecture_cards,
                mobile_cols=1,
                tablet_cols=2,
                desktop_cols=3,
                large_cols=3,
                spacing=spacing.element_spacing
            ),
            config_options
        ], spacing=spacing.section_spacing)

    def _create_architecture_cards(self) -> List[ft.Control]:
        """Create architecture selection cards."""
        cards = []
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        for architecture in ModelArchitecture:
            info = self._model_info[architecture]
            is_selected = self._current_config.architecture == architecture

            # Create use cases list
            use_cases = ft.Column([
                ft.Text(
                    f"• {use_case}",
                    style=typography.body_small,
                    color=palette.on_surface_variant
                ) for use_case in info["use_cases"]
            ], spacing=spacing.element_spacing // 4)

            card_content = ft.Container(
                content=ft.Column([
                    # Header with icon and title
                    ft.Row([
                        ft.Icon(
                            info["icon"],
                            color=palette.primary if is_selected else palette.on_surface_variant,
                            size=self.get_breakpoint_value(mobile=24, tablet=28, desktop=32, large=36)
                        ),
                        ft.Column([
                            ft.Text(
                                info["title"],
                                style=typography.heading_small,
                                color=palette.primary if is_selected else palette.on_surface,
                                weight=ft.FontWeight.W_600
                            ),
                            ft.Text(
                                info["parameters"],
                                style=typography.body_small,
                                color=palette.on_surface_variant
                            )
                        ], spacing=spacing.element_spacing // 4, expand=True)
                    ], spacing=spacing.element_spacing),

                    # Description
                    ft.Text(
                        info["description"],
                        style=typography.body_medium,
                        color=palette.on_surface_variant
                    ),

                    # Memory requirements
                    ft.Container(
                        content=ft.Column([
                            ft.Text(
                                "Memory Requirements:",
                                style=typography.body_small,
                                color=palette.on_surface,
                                weight=ft.FontWeight.W_500
                            ),
                            ft.Text(
                                f"Minimum: {info['memory_min']}",
                                style=typography.body_small,
                                color=palette.on_surface_variant
                            ),
                            ft.Text(
                                f"Recommended: {info['memory_recommended']}",
                                style=typography.body_small,
                                color=palette.on_surface_variant
                            )
                        ], spacing=spacing.element_spacing // 4),
                        bgcolor=palette.surface_variant,
                        padding=ft.padding.all(spacing.container_padding // 2),
                        border_radius=ft.border_radius.all(4)
                    ),

                    # Use cases
                    ft.Column([
                        ft.Text(
                            "Best for:",
                            style=typography.body_small,
                            color=palette.on_surface,
                            weight=ft.FontWeight.W_500
                        ),
                        use_cases
                    ], spacing=spacing.element_spacing // 2)

                ], spacing=spacing.element_spacing),
                padding=ft.padding.all(spacing.container_padding),
                bgcolor=palette.surface_variant if is_selected else palette.surface,
                border=ft.border.all(
                    2 if is_selected else 1,
                    palette.primary if is_selected else palette.outline_variant
                ),
                border_radius=ft.border_radius.all(8),
                on_click=lambda e, arch=architecture: self._on_architecture_select(arch)
            )

            self._architecture_cards[architecture] = card_content
            cards.append(card_content)

        return cards

    def _create_configuration_options(self) -> ft.Control:
        """Create configuration options panel."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Quantization dropdown
        quantization_options = [
            ft.dropdown.Option(key=q.value, text=f"{q.value} - {self._get_quantization_description(q)}")
            for q in QuantizationType
        ]

        self._quantization_dropdown = ft.Dropdown(
            label="Quantization Type",
            value=self._current_config.quantization.value,
            options=quantization_options,
            on_change=self._on_quantization_change,
            bgcolor=palette.surface,
            border_color=palette.outline_variant,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.on_surface),
            label_style=ft.TextStyle(color=palette.on_surface_variant)
        )

        # Optimization level dropdown
        optimization_options = [
            ft.dropdown.Option(key=o.value, text=f"{o.value.title()} - {self._get_optimization_description(o)}")
            for o in OptimizationLevel
        ]

        self._optimization_dropdown = ft.Dropdown(
            label="Optimization Level",
            value=self._current_config.optimization_level.value,
            options=optimization_options,
            on_change=self._on_optimization_change,
            bgcolor=palette.surface,
            border_color=palette.outline_variant,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.on_surface),
            label_style=ft.TextStyle(color=palette.on_surface_variant)
        )

        # Advanced options toggle
        advanced_toggle = None
        if self._config.show_advanced_options:
            advanced_toggle = ft.Switch(
                label="Show Advanced Options",
                value=False,
                on_change=self._on_advanced_toggle,
                active_color=palette.primary
            )

        config_content = [
            ft.Text(
                "Configuration Options",
                style=typography.heading_small,
                color=palette.on_surface,
                weight=ft.FontWeight.W_500
            ),
            self.create_responsive_grid(
                children=[self._quantization_dropdown, self._optimization_dropdown],
                mobile_cols=1,
                tablet_cols=2,
                desktop_cols=2,
                large_cols=2,
                spacing=spacing.element_spacing
            )
        ]

        if advanced_toggle:
            config_content.append(advanced_toggle)

        return ft.Column(config_content, spacing=spacing.element_spacing)

    def _create_compatibility_panel(self) -> ft.Control:
        """Create hardware compatibility panel."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Get compatibility result for current configuration
        compatibility_key = (self._current_config.architecture, self._current_config.quantization)
        compatibility_result = self._compatibility_results.get(compatibility_key)

        if not compatibility_result:
            # Trigger compatibility check
            asyncio.create_task(self._check_compatibility())

            return ft.Container(
                content=ft.Row([
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=palette.primary),
                    ft.Text(
                        "Checking hardware compatibility...",
                        style=typography.body_medium,
                        color=palette.on_surface_variant
                    )
                ], spacing=spacing.element_spacing),
                padding=ft.padding.all(spacing.container_padding),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(8)
            )

        # Create compatibility display
        compatibility_color = self._get_compatibility_color(compatibility_result.compatibility_level)
        compatibility_icon = self._get_compatibility_icon(compatibility_result.compatibility_level)

        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.Icon(
                        compatibility_icon,
                        color=compatibility_color,
                        size=24
                    ),
                    ft.Text(
                        "Hardware Compatibility",
                        style=typography.heading_small,
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    )
                ], spacing=spacing.element_spacing),

                # Compatibility level
                ft.Row([
                    ft.Text(
                        "Compatibility:",
                        style=typography.body_medium,
                        color=palette.on_surface_variant
                    ),
                    ft.Text(
                        compatibility_result.compatibility_level.value.title(),
                        style=typography.body_medium,
                        color=compatibility_color,
                        weight=ft.FontWeight.W_500
                    )
                ], spacing=spacing.element_spacing),

                # Performance score
                ft.Row([
                    ft.Text(
                        "Performance Score:",
                        style=typography.body_medium,
                        color=palette.on_surface_variant
                    ),
                    ft.Text(
                        f"{compatibility_result.performance_score:.1%}",
                        style=typography.body_medium,
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    )
                ], spacing=spacing.element_spacing),

                # Memory requirement
                ft.Row([
                    ft.Text(
                        "Memory Required:",
                        style=typography.body_medium,
                        color=palette.on_surface_variant
                    ),
                    ft.Text(
                        f"{compatibility_result.memory_requirement_gb:.1f} GB",
                        style=typography.body_medium,
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    )
                ], spacing=spacing.element_spacing),

                # Estimated training time
                ft.Row([
                    ft.Text(
                        "Est. Training Time:",
                        style=typography.body_medium,
                        color=palette.on_surface_variant
                    ),
                    ft.Text(
                        f"{compatibility_result.estimated_training_time_hours:.1f} hours",
                        style=typography.body_medium,
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    )
                ], spacing=spacing.element_spacing),

                # Warnings
                self._create_warnings_section(compatibility_result.warnings) if compatibility_result.warnings else None,

                # Recommendations
                self._create_recommendations_section(compatibility_result.recommendations) if compatibility_result.recommendations else None

            ], spacing=spacing.element_spacing),
            padding=ft.padding.all(spacing.container_padding),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, compatibility_color)
        )

    def _create_warnings_section(self, warnings: List[str]) -> ft.Control:
        """Create warnings section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        warning_items = [
            ft.Row([
                ft.Icon(ft.Icons.WARNING, color=palette.error, size=16),
                ft.Text(
                    warning,
                    style=typography.body_small,
                    color=palette.on_surface_variant,
                    expand=True
                )
            ], spacing=spacing.element_spacing // 2)
            for warning in warnings
        ]

        return ft.Column([
            ft.Text(
                "Warnings:",
                style=typography.body_medium,
                color=palette.error,
                weight=ft.FontWeight.W_500
            ),
            ft.Column(warning_items, spacing=spacing.element_spacing // 2)
        ], spacing=spacing.element_spacing // 2)

    def _create_recommendations_section(self, recommendations: List[str]) -> ft.Control:
        """Create recommendations section."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        recommendation_items = [
            ft.Row([
                ft.Icon(ft.Icons.LIGHTBULB, color=palette.primary, size=16),
                ft.Text(
                    recommendation,
                    style=typography.body_small,
                    color=palette.on_surface_variant,
                    expand=True
                )
            ], spacing=spacing.element_spacing // 2)
            for recommendation in recommendations
        ]

        return ft.Column([
            ft.Text(
                "Recommendations:",
                style=typography.body_medium,
                color=palette.primary,
                weight=ft.FontWeight.W_500
            ),
            ft.Column(recommendation_items, spacing=spacing.element_spacing // 2)
        ], spacing=spacing.element_spacing // 2)

    # Event handlers
    def _on_architecture_select(self, architecture: ModelArchitecture) -> None:
        """Handle architecture selection."""
        if self._current_config.architecture != architecture:
            self._current_config.architecture = architecture
            self._update_architecture_cards()
            self._trigger_compatibility_check()
            if self._on_model_change:
                self._on_model_change(self._current_config)

    def _on_quantization_change(self, e: ft.ControlEvent) -> None:
        """Handle quantization type change."""
        if e.control.value:
            self._current_config.quantization = QuantizationType(e.control.value)
            self._trigger_compatibility_check()
            if self._on_model_change:
                self._on_model_change(self._current_config)

    def _on_optimization_change(self, e: ft.ControlEvent) -> None:
        """Handle optimization level change."""
        if e.control.value:
            self._current_config.optimization_level = OptimizationLevel(e.control.value)
            if self._on_model_change:
                self._on_model_change(self._current_config)

    def _on_advanced_toggle(self, e: ft.ControlEvent) -> None:
        """Handle advanced options toggle."""
        # This would show/hide advanced configuration panel
        # Implementation depends on advanced panel creation
        pass

    # UI update methods
    def _update_ui_from_config(self) -> None:
        """Update UI components from current configuration."""
        self._update_architecture_cards()
        if self._quantization_dropdown:
            self._quantization_dropdown.value = self._current_config.quantization.value
        if self._optimization_dropdown:
            self._optimization_dropdown.value = self._current_config.optimization_level.value
        self.update()

    def _update_architecture_cards(self) -> None:
        """Update architecture card selection states."""
        palette = self.get_palette()

        for architecture, card in self._architecture_cards.items():
            is_selected = self._current_config.architecture == architecture

            # Update card styling
            card.bgcolor = palette.surface_variant if is_selected else palette.surface
            card.border = ft.border.all(
                2 if is_selected else 1,
                palette.primary if is_selected else palette.outline_variant
            )

            # Update icon color in the card content
            if hasattr(card.content, 'controls') and len(card.content.controls) > 0:
                header_row = card.content.controls[0]
                if hasattr(header_row, 'controls') and len(header_row.controls) > 0:
                    icon = header_row.controls[0]
                    if hasattr(icon, 'color'):
                        icon.color = palette.primary if is_selected else palette.on_surface_variant

        self.update()

    def _trigger_compatibility_check(self) -> None:
        """Trigger hardware compatibility check."""
        if not self._is_checking_compatibility:
            asyncio.create_task(self._check_compatibility())

    async def _check_compatibility(self) -> None:
        """Check hardware compatibility for current configuration."""
        if self._is_checking_compatibility:
            return

        self._is_checking_compatibility = True

        try:
            compatibility_key = (self._current_config.architecture, self._current_config.quantization)

            # Simulate compatibility checking (replace with actual logic)
            await asyncio.sleep(0.5)  # Simulate processing time

            # Calculate compatibility based on hardware
            compatibility_result = self._calculate_compatibility(
                self._current_config.architecture,
                self._current_config.quantization
            )

            self._compatibility_results[compatibility_key] = compatibility_result

            # Update UI
            if hasattr(self, 'page') and self.page:
                self.update()

        except Exception as e:
            self._logger.error(f"Failed to check compatibility: {e}")
        finally:
            self._is_checking_compatibility = False

    def _calculate_compatibility(self, architecture: ModelArchitecture, quantization: QuantizationType) -> ModelCompatibilityResult:
        """Calculate hardware compatibility for given configuration."""
        # Memory requirements based on architecture and quantization
        memory_requirements = {
            (ModelArchitecture.SMALL_1B, QuantizationType.INT4): 2.0,
            (ModelArchitecture.SMALL_1B, QuantizationType.INT8): 3.0,
            (ModelArchitecture.SMALL_1B, QuantizationType.FP16): 4.0,
            (ModelArchitecture.SMALL_1B, QuantizationType.FP32): 6.0,
            (ModelArchitecture.MEDIUM_3B, QuantizationType.INT4): 6.0,
            (ModelArchitecture.MEDIUM_3B, QuantizationType.INT8): 8.0,
            (ModelArchitecture.MEDIUM_3B, QuantizationType.FP16): 12.0,
            (ModelArchitecture.MEDIUM_3B, QuantizationType.FP32): 18.0,
            (ModelArchitecture.LARGE_7B, QuantizationType.INT4): 14.0,
            (ModelArchitecture.LARGE_7B, QuantizationType.INT8): 18.0,
            (ModelArchitecture.LARGE_7B, QuantizationType.FP16): 28.0,
            (ModelArchitecture.LARGE_7B, QuantizationType.FP32): 42.0,
        }

        memory_required = memory_requirements.get((architecture, quantization), 8.0)

        # Calculate compatibility level
        available_memory = max(self._system_memory_gb, self._gpu_memory_gb)
        memory_ratio = available_memory / memory_required

        if memory_ratio >= 2.0:
            compatibility_level = CompatibilityLevel.EXCELLENT
            performance_score = 0.95
        elif memory_ratio >= 1.5:
            compatibility_level = CompatibilityLevel.GOOD
            performance_score = 0.80
        elif memory_ratio >= 1.0:
            compatibility_level = CompatibilityLevel.FAIR
            performance_score = 0.60
        elif memory_ratio >= 0.8:
            compatibility_level = CompatibilityLevel.POOR
            performance_score = 0.30
        else:
            compatibility_level = CompatibilityLevel.INCOMPATIBLE
            performance_score = 0.10

        # Generate warnings and recommendations
        warnings = []
        recommendations = []

        if memory_ratio < 1.0:
            warnings.append(f"Insufficient memory: {available_memory:.1f} GB available, {memory_required:.1f} GB required")
            recommendations.append("Consider upgrading system memory or using a smaller model")

        if not self._has_gpu and architecture in [ModelArchitecture.MEDIUM_3B, ModelArchitecture.LARGE_7B]:
            warnings.append("No GPU detected - training will be significantly slower")
            recommendations.append("Consider using GPU acceleration for better performance")

        if quantization == QuantizationType.FP32:
            recommendations.append("Consider using FP16 or INT8 quantization to reduce memory usage")

        # Estimate training time (simplified calculation)
        base_time_hours = {
            ModelArchitecture.SMALL_1B: 2.0,
            ModelArchitecture.MEDIUM_3B: 6.0,
            ModelArchitecture.LARGE_7B: 12.0
        }

        time_multiplier = 1.0
        if not self._has_gpu:
            time_multiplier *= 5.0  # CPU training is much slower
        if quantization == QuantizationType.FP32:
            time_multiplier *= 1.5
        elif quantization == QuantizationType.INT4:
            time_multiplier *= 0.7

        estimated_time = base_time_hours[architecture] * time_multiplier

        return ModelCompatibilityResult(
            architecture=architecture,
            quantization=quantization,
            compatibility_level=compatibility_level,
            performance_score=performance_score,
            memory_requirement_gb=memory_required,
            estimated_training_time_hours=estimated_time,
            warnings=warnings,
            recommendations=recommendations,
            hardware_requirements={
                "memory_gb": memory_required,
                "gpu_recommended": architecture != ModelArchitecture.SMALL_1B,
                "cpu_cores": max(4, self._system_cpu_count)
            }
        )

    # Utility methods
    def _get_quantization_description(self, quantization: QuantizationType) -> str:
        """Get description for quantization type."""
        descriptions = {
            QuantizationType.INT4: "Smallest size, fastest inference, lower quality",
            QuantizationType.INT8: "Small size, fast inference, good quality",
            QuantizationType.FP16: "Balanced size and quality",
            QuantizationType.FP32: "Largest size, highest quality"
        }
        return descriptions.get(quantization, "Unknown")

    def _get_optimization_description(self, optimization: OptimizationLevel) -> str:
        """Get description for optimization level."""
        descriptions = {
            OptimizationLevel.BASIC: "Minimal optimizations, fastest compilation",
            OptimizationLevel.STANDARD: "Balanced optimizations and compilation time",
            OptimizationLevel.AGGRESSIVE: "Heavy optimizations, slower compilation",
            OptimizationLevel.MAXIMUM: "Maximum optimizations, slowest compilation"
        }
        return descriptions.get(optimization, "Unknown")

    def _get_compatibility_color(self, level: CompatibilityLevel) -> str:
        """Get color for compatibility level."""
        palette = self.get_palette()
        colors = {
            CompatibilityLevel.EXCELLENT: palette.success,
            CompatibilityLevel.GOOD: palette.primary,
            CompatibilityLevel.FAIR: palette.warning,
            CompatibilityLevel.POOR: palette.error,
            CompatibilityLevel.INCOMPATIBLE: palette.error
        }
        return colors.get(level, palette.on_surface_variant)

    def _get_compatibility_icon(self, level: CompatibilityLevel) -> str:
        """Get icon for compatibility level."""
        icons = {
            CompatibilityLevel.EXCELLENT: ft.Icons.CHECK_CIRCLE,
            CompatibilityLevel.GOOD: ft.Icons.THUMB_UP,
            CompatibilityLevel.FAIR: ft.Icons.WARNING,
            CompatibilityLevel.POOR: ft.Icons.ERROR,
            CompatibilityLevel.INCOMPATIBLE: ft.Icons.CANCEL
        }
        return icons.get(level, ft.Icons.HELP)

    def _create_advanced_config_layout(self) -> ft.Control:
        """Create advanced configuration layout."""
        # This would include additional configuration options
        # For now, return the quick select layout with additional options
        return self._create_quick_select_layout()

    def _create_custom_model_layout(self) -> ft.Control:
        """Create custom model configuration layout."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Column([
            ft.Text(
                "Custom Model Configuration",
                style=typography.heading_small,
                color=palette.on_surface,
                weight=ft.FontWeight.W_500
            ),
            ft.Text(
                "Custom model configuration is not yet implemented.",
                style=typography.body_medium,
                color=palette.on_surface_variant
            ),
            ft.ElevatedButton(
                text="Switch to Quick Select",
                on_click=lambda e: self._switch_to_quick_select(),
                bgcolor=palette.primary,
                color=palette.on_primary
            )
        ], spacing=spacing.element_spacing)

    def _switch_to_quick_select(self) -> None:
        """Switch to quick select mode."""
        self._config.mode = ModelSelectionMode.QUICK_SELECT
        self.content = self.build()
        self.update()

    # Public API methods
    def refresh_compatibility(self) -> None:
        """Refresh hardware compatibility check."""
        self._compatibility_results.clear()
        self._trigger_compatibility_check()

    def get_hardware_info(self) -> Dict[str, Any]:
        """Get current hardware information."""
        return {
            "system_memory_gb": self._system_memory_gb,
            "system_cpu_count": self._system_cpu_count,
            "has_gpu": self._has_gpu,
            "gpu_memory_gb": self._gpu_memory_gb
        }

    def validate_configuration(self) -> Tuple[bool, List[str]]:
        """Validate current model configuration."""
        errors = []

        # Check if configuration is complete
        if not self._current_config.architecture:
            errors.append("Model architecture must be selected")

        if not self._current_config.quantization:
            errors.append("Quantization type must be selected")

        if not self._current_config.optimization_level:
            errors.append("Optimization level must be selected")

        # Check hardware compatibility
        compatibility_key = (self._current_config.architecture, self._current_config.quantization)
        compatibility_result = self._compatibility_results.get(compatibility_key)

        if compatibility_result and compatibility_result.compatibility_level == CompatibilityLevel.INCOMPATIBLE:
            errors.append("Selected configuration is incompatible with current hardware")

        return len(errors) == 0, errors

    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration as dictionary."""
        return {
            "architecture": self._current_config.architecture.value,
            "quantization": self._current_config.quantization.value,
            "optimization_level": self._current_config.optimization_level.value,
            "model_type": self._current_config.model_type,
            "base_model_path": self._current_config.base_model_path,
            "custom_config": self._current_config.custom_config,
            "enable_mixed_precision": self._current_config.enable_mixed_precision,
            "gradient_checkpointing": self._current_config.gradient_checkpointing,
            "use_flash_attention": self._current_config.use_flash_attention,
            "custom_tokenizer": self._current_config.custom_tokenizer
        }

    def import_configuration(self, config_dict: Dict[str, Any]) -> None:
        """Import configuration from dictionary."""
        try:
            self._current_config = ModelConfiguration(
                architecture=ModelArchitecture(config_dict.get("architecture", ModelArchitecture.SMALL_1B.value)),
                quantization=QuantizationType(config_dict.get("quantization", QuantizationType.FP16.value)),
                optimization_level=OptimizationLevel(config_dict.get("optimization_level", OptimizationLevel.STANDARD.value)),
                model_type=config_dict.get("model_type"),
                base_model_path=config_dict.get("base_model_path"),
                custom_config=config_dict.get("custom_config", {}),
                enable_mixed_precision=config_dict.get("enable_mixed_precision", True),
                gradient_checkpointing=config_dict.get("gradient_checkpointing", False),
                use_flash_attention=config_dict.get("use_flash_attention", False),
                custom_tokenizer=config_dict.get("custom_tokenizer")
            )
            self._update_ui_from_config()
            self._trigger_compatibility_check()

            if self._on_model_change:
                self._on_model_change(self._current_config)

        except (ValueError, KeyError) as e:
            self._logger.error(f"Failed to import configuration: {e}")
            raise ValueError(f"Invalid configuration format: {e}")
