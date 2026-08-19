"""
Module: model_details_ui
Description: Comprehensive model details display interface with responsive design and theme integration.
            Provides detailed model information panel with architecture details, training history,
            performance metrics, version information, and deployment status. Features theme-aware styling,
            accessibility compliance, and responsive design that adapts to different screen sizes.
Phase: 4
Location: /src/modules/ui/model_registry_ui/model_details_ui/model_details_ui.py
"""

# Standard library imports
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable, Set, Union
from dataclasses import dataclass, field
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    ColorPalette,
    SpacingSystem,
    TypographyScale,
    IconSystem,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class ModelDetailsMode(Enum):
    """Model details display modes."""
    OVERVIEW = "overview"
    ARCHITECTURE = "architecture"
    TRAINING = "training"
    PERFORMANCE = "performance"
    VERSIONS = "versions"
    DEPLOYMENT = "deployment"
    COMPARISON = "comparison"


class ModelStatus(Enum):
    """Model status enumeration."""
    TRAINING = "training"
    COMPLETED = "completed"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    FAILED = "failed"
    PAUSED = "paused"


class ModelArchitecture(Enum):
    """Model architecture types."""
    TRANSFORMER_1B = "1B"
    TRANSFORMER_3B = "3B"
    TRANSFORMER_7B = "7B"


class QuantizationType(Enum):
    """Model quantization types."""
    FP32 = "FP32"
    FP16 = "FP16"
    INT8 = "INT8"
    INT4 = "INT4"


@dataclass
class ModelArchitectureInfo:
    """Model architecture information."""
    architecture: ModelArchitecture
    parameters_count: int
    hidden_size: int
    num_layers: int
    num_attention_heads: int
    vocab_size: int
    max_position_embeddings: int
    quantization_type: QuantizationType
    model_format: str = "PyTorch"
    base_model: Optional[str] = None
    custom_layers: List[str] = field(default_factory=list)
    optimization_level: str = "O2"
    precision: str = "mixed"


@dataclass
class ModelTrainingHistory:
    """Model training history information."""
    training_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_epochs: int = 0
    completed_epochs: int = 0
    total_steps: int = 0
    completed_steps: int = 0
    final_loss: Optional[float] = None
    best_loss: Optional[float] = None
    learning_rate: float = 0.0001
    batch_size: int = 32
    dataset_size: int = 0
    validation_split: float = 0.1
    early_stopping_patience: int = 3
    checkpoint_count: int = 0
    training_time_hours: Optional[float] = None
    gpu_hours_used: Optional[float] = None
    status: ModelStatus = ModelStatus.TRAINING


@dataclass
class ModelPerformanceMetrics:
    """Model performance metrics."""
    accuracy: Optional[float] = None
    perplexity: Optional[float] = None
    bleu_score: Optional[float] = None
    rouge_score: Optional[float] = None
    f1_score: Optional[float] = None
    inference_time_ms: Optional[float] = None
    throughput_tokens_per_second: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    gpu_utilization_percent: Optional[float] = None
    cpu_utilization_percent: Optional[float] = None
    latency_p50_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    latency_p99_ms: Optional[float] = None
    model_size_mb: Optional[float] = None
    disk_usage_mb: Optional[float] = None
    benchmark_date: Optional[datetime] = None
    hardware_config: Optional[str] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ModelVersionInfo:
    """Model version information."""
    version: str
    version_id: str
    parent_version: Optional[str] = None
    branch_name: Optional[str] = None
    commit_hash: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    changelog: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    is_stable: bool = False
    is_latest: bool = False
    download_count: int = 0
    file_size_mb: Optional[float] = None
    checksum: Optional[str] = None


@dataclass
class ModelDeploymentInfo:
    """Model deployment information."""
    deployment_id: Optional[str] = None
    deployment_status: str = "not_deployed"
    deployment_target: Optional[str] = None
    deployment_url: Optional[str] = None
    deployment_date: Optional[datetime] = None
    deployment_config: Dict[str, Any] = field(default_factory=dict)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    scaling_config: Dict[str, Any] = field(default_factory=dict)
    health_status: str = "unknown"
    uptime_hours: Optional[float] = None
    request_count: int = 0
    error_rate: float = 0.0
    average_response_time_ms: Optional[float] = None


@dataclass
class ModelDetailsData:
    """Complete model details data structure."""
    model_id: str
    name: str
    description: Optional[str] = None
    status: ModelStatus = ModelStatus.TRAINING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    project_id: Optional[str] = None
    model_path: Optional[str] = None
    architecture_info: Optional[ModelArchitectureInfo] = None
    training_history: Optional[ModelTrainingHistory] = None
    performance_metrics: Optional[ModelPerformanceMetrics] = None
    version_info: Optional[ModelVersionInfo] = None
    deployment_info: Optional[ModelDeploymentInfo] = None
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_favorite: bool = False
    access_count: int = 0
    last_accessed: Optional[datetime] = None


@dataclass
class ModelDetailsConfig:
    """Configuration for model details display."""
    mode: ModelDetailsMode = ModelDetailsMode.OVERVIEW
    show_architecture_details: bool = True
    show_training_history: bool = True
    show_performance_metrics: bool = True
    show_version_info: bool = True
    show_deployment_info: bool = True
    enable_comparison: bool = True
    enable_export: bool = True
    enable_deployment_actions: bool = True
    auto_refresh: bool = False
    refresh_interval: int = 30  # seconds
    max_history_items: int = 100
    show_technical_details: bool = True
    show_charts: bool = True
    enable_real_time_updates: bool = True
    compact_mode: bool = False


class ModelDetailsUI(ThemeAwareUserControl):
    """
    Comprehensive model details display interface.

    Features:
    - Responsive model details view with breakpoint-aware layouts
    - Multiple display modes (overview, architecture, training, performance, versions, deployment)
    - Interactive model information panels with charts and visualizations
    - Architecture details panel with technical specifications
    - Training history with progress tracking and metrics
    - Performance metrics with benchmarking results
    - Version management with git-style version tree
    - Deployment status and management controls
    - Theme-aware styling with accessibility compliance
    - Integration with model registry and management system
    - Modern UI/UX with smooth animations and transitions
    - Real-time updates and status monitoring
    """

    def __init__(
        self,
        model_data: Optional[ModelDetailsData] = None,
        config: Optional[ModelDetailsConfig] = None,
        on_model_updated: Optional[Callable[[ModelDetailsData], None]] = None,
        on_deployment_action: Optional[Callable[[str, str], None]] = None,
        on_export_requested: Optional[Callable[[str, str], None]] = None,
        on_comparison_requested: Optional[Callable[[List[str]], None]] = None,
        **kwargs
    ):
        """
        Initialize model details UI.

        Args:
            model_data: Model data to display
            config: Display configuration
            on_model_updated: Callback for model updates
            on_deployment_action: Callback for deployment actions
            on_export_requested: Callback for export requests
            on_comparison_requested: Callback for comparison requests
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)

        # Initialize data and configuration
        self.model_data = model_data
        self.config = config or ModelDetailsConfig()

        # Callbacks
        self.on_model_updated = on_model_updated
        self.on_deployment_action = on_deployment_action
        self.on_export_requested = on_export_requested
        self.on_comparison_requested = on_comparison_requested

        # UI state
        self._current_mode = self.config.mode
        self._is_loading = False
        self._error_message = None
        self._refresh_timer = None
        self._last_update = None

        # UI components
        self._mode_tabs = None
        self._content_container = None
        self._overview_panel = None
        self._architecture_panel = None
        self._training_panel = None
        self._performance_panel = None
        self._versions_panel = None
        self._deployment_panel = None
        self._action_bar = None
        self._status_indicator = None

        # Threading
        self._update_lock = threading.Lock()

        logger.info(f"ModelDetailsUI initialized for model: {model_data.model_id if model_data else 'None'}")

    def build(self) -> ft.Control:
        """Build the model details interface."""
        try:
            # Get responsive layout manager
            layout_manager = self.get_responsive_layout_manager()
            screen_size = layout_manager.get_screen_size_category()

            # Build main container based on screen size
            if screen_size in ["mobile", "tablet"]:
                return self._build_mobile_layout()
            else:
                return self._build_desktop_layout()

        except Exception as e:
            logger.error(f"Error building model details UI: {e}")
            return self._build_error_state(str(e))

    def _build_desktop_layout(self) -> ft.Control:
        """Build desktop layout for model details."""
        try:
            # Header with model info and actions
            header = self._build_header()

            # Mode tabs
            mode_tabs = self._build_mode_tabs()

            # Content area
            content = self._build_content_area()

            # Action bar
            action_bar = self._build_action_bar()

            # Main layout
            return ft.Container(
                content=ft.Column(
                    controls=[
                        header,
                        mode_tabs,
                        ft.Divider(
                            height=1,
                            color=self.get_color("outline_variant")
                        ),
                        ft.Expanded(child=content),
                        action_bar
                    ],
                    spacing=0,
                    expand=True
                ),
                padding=self.get_spacing("lg"),
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building desktop layout: {e}")
            return self._build_error_state(str(e))

    def _build_mobile_layout(self) -> ft.Control:
        """Build mobile layout for model details."""
        try:
            # Compact header
            header = self._build_compact_header()

            # Mode selector (dropdown instead of tabs)
            mode_selector = self._build_mode_selector()

            # Content area
            content = self._build_content_area()

            # Floating action button
            fab = self._build_floating_action_button()

            # Main layout
            return ft.Stack(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                header,
                                mode_selector,
                                ft.Expanded(child=content)
                            ],
                            spacing=self.get_spacing("sm"),
                            expand=True
                        ),
                        padding=self.get_spacing("md"),
                        expand=True
                    ),
                    ft.Container(
                        content=fab,
                        bottom=self.get_spacing("lg"),
                        right=self.get_spacing("lg")
                    )
                ],
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building mobile layout: {e}")
            return self._build_error_state(str(e))

    def _build_header(self) -> ft.Control:
        """Build header with model information and status."""
        try:
            if not self.model_data:
                return ft.Container()

            # Model icon and status
            status_color = self._get_status_color(self.model_data.status)
            model_icon = ft.Icon(
                name=self.get_icon("MODEL"),
                size=self.get_responsive_size("icon_large"),
                color=status_color
            )

            # Model name and description
            name_text = ft.Text(
                value=self.model_data.name,
                style=self.get_text_style("headline_medium"),
                color=self.get_color("on_surface"),
                weight=ft.FontWeight.BOLD
            )

            description_text = ft.Text(
                value=self.model_data.description or "No description available",
                style=self.get_text_style("body_medium"),
                color=self.get_color("on_surface_variant"),
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            # Status chip
            status_chip = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            name=self._get_status_icon(self.model_data.status),
                            size=self.get_responsive_size("icon_small"),
                            color=self.get_color("on_primary")
                        ),
                        ft.Text(
                            value=self.model_data.status.value.title(),
                            style=self.get_text_style("label_medium"),
                            color=self.get_color("on_primary"),
                            weight=ft.FontWeight.BOLD
                        )
                    ],
                    spacing=self.get_spacing("xs"),
                    tight=True
                ),
                padding=ft.padding.symmetric(
                    horizontal=self.get_spacing("sm"),
                    vertical=self.get_spacing("xs")
                ),
                border_radius=ft.border_radius.all(16),
                bgcolor=status_color
            )

            # Model metadata
            metadata_items = []
            if self.model_data.architecture_info:
                metadata_items.append(
                    self._build_metadata_item(
                        "Architecture",
                        self.model_data.architecture_info.architecture.value
                    )
                )
            if self.model_data.version_info:
                metadata_items.append(
                    self._build_metadata_item(
                        "Version",
                        self.model_data.version_info.version
                    )
                )
            if self.model_data.created_at:
                metadata_items.append(
                    self._build_metadata_item(
                        "Created",
                        self.model_data.created_at.strftime("%Y-%m-%d")
                    )
                )

            metadata_row = ft.Row(
                controls=metadata_items,
                spacing=self.get_spacing("lg"),
                wrap=True
            )

            # Header layout
            return ft.Container(
                content=ft.Row(
                    controls=[
                        model_icon,
                        ft.Expanded(
                            child=ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[name_text, status_chip],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                                    ),
                                    description_text,
                                    ft.Container(height=self.get_spacing("xs")),
                                    metadata_row
                                ],
                                spacing=self.get_spacing("xs"),
                                cross_axis_alignment=ft.CrossAxisAlignment.START
                            )
                        )
                    ],
                    spacing=self.get_spacing("md"),
                    alignment=ft.MainAxisAlignment.START
                ),
                padding=self.get_spacing("lg"),
                border=ft.border.only(
                    bottom=ft.BorderSide(1, self.get_color("outline_variant"))
                )
            )

        except Exception as e:
            logger.error(f"Error building header: {e}")
            return ft.Container()

    def _build_compact_header(self) -> ft.Control:
        """Build compact header for mobile layout."""
        try:
            if not self.model_data:
                return ft.Container()

            # Model name and status in compact layout
            name_text = ft.Text(
                value=self.model_data.name,
                style=self.get_text_style("title_medium"),
                color=self.get_color("on_surface"),
                weight=ft.FontWeight.BOLD,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            status_color = self._get_status_color(self.model_data.status)
            status_indicator = ft.Container(
                content=ft.Text(
                    value=self.model_data.status.value.upper(),
                    style=self.get_text_style("label_small"),
                    color=self.get_color("on_primary"),
                    weight=ft.FontWeight.BOLD
                ),
                padding=ft.padding.symmetric(
                    horizontal=self.get_spacing("xs"),
                    vertical=2
                ),
                border_radius=ft.border_radius.all(8),
                bgcolor=status_color
            )

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Expanded(child=name_text),
                        status_indicator
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=self.get_spacing("md")
            )

        except Exception as e:
            logger.error(f"Error building compact header: {e}")
            return ft.Container()

    def _build_mode_tabs(self) -> ft.Control:
        """Build mode selection tabs."""
        try:
            tabs = []

            # Define available modes
            modes = [
                (ModelDetailsMode.OVERVIEW, "Overview", "DASHBOARD"),
                (ModelDetailsMode.ARCHITECTURE, "Architecture", "ARCHITECTURE"),
                (ModelDetailsMode.TRAINING, "Training", "SCHOOL"),
                (ModelDetailsMode.PERFORMANCE, "Performance", "SPEED"),
                (ModelDetailsMode.VERSIONS, "Versions", "HISTORY"),
                (ModelDetailsMode.DEPLOYMENT, "Deployment", "CLOUD_UPLOAD")
            ]

            for mode, label, icon_name in modes:
                # Check if mode should be shown based on config
                if not self._should_show_mode(mode):
                    continue

                tab = ft.Tab(
                    text=label,
                    icon=self.get_icon(icon_name),
                    content=ft.Container()  # Content will be built separately
                )
                tabs.append(tab)

            self._mode_tabs = ft.Tabs(
                tabs=tabs,
                selected_index=self._get_mode_index(self._current_mode),
                on_change=self._on_mode_changed,
                indicator_color=self.get_color("primary"),
                label_color=self.get_color("on_surface"),
                unselected_label_color=self.get_color("on_surface_variant"),
                indicator_tab_size=True
            )

            return ft.Container(
                content=self._mode_tabs,
                padding=ft.padding.symmetric(horizontal=self.get_spacing("lg"))
            )

        except Exception as e:
            logger.error(f"Error building mode tabs: {e}")
            return ft.Container()

    def _build_mode_selector(self) -> ft.Control:
        """Build mode selector dropdown for mobile."""
        try:
            # Define available modes
            modes = [
                (ModelDetailsMode.OVERVIEW, "Overview"),
                (ModelDetailsMode.ARCHITECTURE, "Architecture"),
                (ModelDetailsMode.TRAINING, "Training"),
                (ModelDetailsMode.PERFORMANCE, "Performance"),
                (ModelDetailsMode.VERSIONS, "Versions"),
                (ModelDetailsMode.DEPLOYMENT, "Deployment")
            ]

            # Filter modes based on config
            available_modes = [
                (mode, label) for mode, label in modes
                if self._should_show_mode(mode)
            ]

            dropdown = ft.Dropdown(
                value=self._current_mode.value,
                options=[
                    ft.dropdown.Option(key=mode.value, text=label)
                    for mode, label in available_modes
                ],
                on_change=self._on_mode_dropdown_changed,
                border_color=self.get_color("outline"),
                focused_border_color=self.get_color("primary"),
                text_style=self.get_text_style("body_medium"),
                expand=True
            )

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            name=self.get_icon("TUNE"),
                            size=self.get_responsive_size("icon_medium"),
                            color=self.get_color("on_surface_variant")
                        ),
                        ft.Expanded(child=dropdown)
                    ],
                    spacing=self.get_spacing("sm")
                ),
                padding=self.get_spacing("md")
            )

        except Exception as e:
            logger.error(f"Error building mode selector: {e}")
            return ft.Container()

    def _build_content_area(self) -> ft.Control:
        """Build content area based on current mode."""
        try:
            if not self.model_data:
                return self._build_no_data_state()

            if self._is_loading:
                return self._build_loading_state()

            if self._error_message:
                return self._build_error_state(self._error_message)

            # Build content based on current mode
            content = None
            if self._current_mode == ModelDetailsMode.OVERVIEW:
                content = self._build_overview_panel()
            elif self._current_mode == ModelDetailsMode.ARCHITECTURE:
                content = self._build_architecture_panel()
            elif self._current_mode == ModelDetailsMode.TRAINING:
                content = self._build_training_panel()
            elif self._current_mode == ModelDetailsMode.PERFORMANCE:
                content = self._build_performance_panel()
            elif self._current_mode == ModelDetailsMode.VERSIONS:
                content = self._build_versions_panel()
            elif self._current_mode == ModelDetailsMode.DEPLOYMENT:
                content = self._build_deployment_panel()
            else:
                content = self._build_overview_panel()

            self._content_container = ft.Container(
                content=content,
                padding=self.get_spacing("lg"),
                expand=True
            )

            return self._content_container

        except Exception as e:
            logger.error(f"Error building content area: {e}")
            return self._build_error_state(str(e))

    def _build_action_bar(self) -> ft.Control:
        """Build action bar with model operations."""
        try:
            actions = []

            # Export action
            if self.config.enable_export:
                export_button = ft.ElevatedButton(
                    text="Export",
                    icon=self.get_icon("DOWNLOAD"),
                    on_click=self._on_export_clicked,
                    style=ft.ButtonStyle(
                        color=self.get_color("on_primary"),
                        bgcolor=self.get_color("primary")
                    )
                )
                actions.append(export_button)

            # Comparison action
            if self.config.enable_comparison:
                compare_button = ft.OutlinedButton(
                    text="Compare",
                    icon=self.get_icon("COMPARE"),
                    on_click=self._on_compare_clicked,
                    style=ft.ButtonStyle(
                        color=self.get_color("primary"),
                        side=ft.BorderSide(1, self.get_color("primary"))
                    )
                )
                actions.append(compare_button)

            # Deployment actions
            if self.config.enable_deployment_actions and self.model_data:
                if self.model_data.deployment_info and self.model_data.deployment_info.deployment_status == "deployed":
                    deploy_button = ft.OutlinedButton(
                        text="Manage Deployment",
                        icon=self.get_icon("SETTINGS"),
                        on_click=self._on_manage_deployment_clicked,
                        style=ft.ButtonStyle(
                            color=self.get_color("secondary"),
                            side=ft.BorderSide(1, self.get_color("secondary"))
                        )
                    )
                else:
                    deploy_button = ft.ElevatedButton(
                        text="Deploy",
                        icon=self.get_icon("CLOUD_UPLOAD"),
                        on_click=self._on_deploy_clicked,
                        style=ft.ButtonStyle(
                            color=self.get_color("on_secondary"),
                            bgcolor=self.get_color("secondary")
                        )
                    )
                actions.append(deploy_button)

            if not actions:
                return ft.Container()

            return ft.Container(
                content=ft.Row(
                    controls=actions,
                    spacing=self.get_spacing("md"),
                    alignment=ft.MainAxisAlignment.END
                ),
                padding=self.get_spacing("lg"),
                border=ft.border.only(
                    top=ft.BorderSide(1, self.get_color("outline_variant"))
                )
            )

        except Exception as e:
            logger.error(f"Error building action bar: {e}")
            return ft.Container()

    def _build_floating_action_button(self) -> ft.Control:
        """Build floating action button for mobile."""
        try:
            return ft.FloatingActionButton(
                icon=self.get_icon("MORE_VERT"),
                on_click=self._on_mobile_actions_clicked,
                bgcolor=self.get_color("primary"),
                foreground_color=self.get_color("on_primary")
            )
        except Exception as e:
            logger.error(f"Error building floating action button: {e}")
            return ft.Container()

    def _build_overview_panel(self) -> ft.Control:
        """Build overview panel with key model information."""
        try:
            panels = []

            # Model summary card
            summary_card = self._build_model_summary_card()
            panels.append(summary_card)

            # Quick stats
            if self.model_data.performance_metrics or self.model_data.architecture_info:
                stats_card = self._build_quick_stats_card()
                panels.append(stats_card)

            # Recent activity
            if self.model_data.training_history:
                activity_card = self._build_recent_activity_card()
                panels.append(activity_card)

            # Layout panels in responsive grid
            layout_manager = self.get_responsive_layout_manager()
            screen_size = layout_manager.get_screen_size_category()

            if screen_size in ["mobile", "tablet"]:
                # Stack vertically on smaller screens
                return ft.Column(
                    controls=panels,
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO
                )
            else:
                # Grid layout on desktop
                return ft.Column(
                    controls=[
                        ft.Row(
                            controls=panels[:2] if len(panels) >= 2 else panels,
                            spacing=self.get_spacing("lg"),
                            expand=True
                        ),
                        ft.Container(height=self.get_spacing("lg")),
                        ft.Row(
                            controls=panels[2:] if len(panels) > 2 else [],
                            spacing=self.get_spacing("lg"),
                            expand=True
                        )
                    ],
                    spacing=0,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                )

        except Exception as e:
            logger.error(f"Error building overview panel: {e}")
            return self._build_error_state(str(e))

    def _build_architecture_panel(self) -> ft.Control:
        """Build architecture details panel."""
        try:
            if not self.model_data.architecture_info:
                return self._build_no_data_state("No architecture information available")

            arch_info = self.model_data.architecture_info

            # Architecture overview
            overview_items = [
                ("Architecture", arch_info.architecture.value),
                ("Parameters", f"{arch_info.parameters_count:,}" if arch_info.parameters_count else "Unknown"),
                ("Model Format", arch_info.model_format),
                ("Quantization", arch_info.quantization_type.value),
                ("Precision", arch_info.precision),
                ("Optimization Level", arch_info.optimization_level)
            ]

            overview_card = self._build_info_card(
                "Architecture Overview",
                overview_items,
                icon_name="ARCHITECTURE"
            )

            # Technical details
            technical_items = [
                ("Hidden Size", str(arch_info.hidden_size)),
                ("Layers", str(arch_info.num_layers)),
                ("Attention Heads", str(arch_info.num_attention_heads)),
                ("Vocabulary Size", f"{arch_info.vocab_size:,}"),
                ("Max Position Embeddings", f"{arch_info.max_position_embeddings:,}")
            ]

            if arch_info.base_model:
                technical_items.insert(0, ("Base Model", arch_info.base_model))

            technical_card = self._build_info_card(
                "Technical Specifications",
                technical_items,
                icon_name="SETTINGS"
            )

            # Custom layers (if any)
            cards = [overview_card, technical_card]

            if arch_info.custom_layers:
                custom_layers_card = self._build_custom_layers_card(arch_info.custom_layers)
                cards.append(custom_layers_card)

            # Layout
            layout_manager = self.get_responsive_layout_manager()
            screen_size = layout_manager.get_screen_size_category()

            if screen_size in ["mobile", "tablet"]:
                return ft.Column(
                    controls=cards,
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO
                )
            else:
                return ft.Row(
                    controls=cards,
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                )

        except Exception as e:
            logger.error(f"Error building architecture panel: {e}")
            return self._build_error_state(str(e))

    def _build_training_panel(self) -> ft.Control:
        """Build training history panel."""
        try:
            if not self.model_data.training_history:
                return self._build_no_data_state("No training history available")

            training = self.model_data.training_history

            # Training overview
            overview_items = [
                ("Training ID", training.training_id),
                ("Status", training.status.value.title()),
                ("Start Time", training.start_time.strftime("%Y-%m-%d %H:%M:%S")),
                ("Learning Rate", f"{training.learning_rate:.6f}"),
                ("Batch Size", str(training.batch_size)),
                ("Dataset Size", f"{training.dataset_size:,}" if training.dataset_size else "Unknown")
            ]

            if training.end_time:
                overview_items.insert(3, ("End Time", training.end_time.strftime("%Y-%m-%d %H:%M:%S")))

            if training.training_time_hours:
                overview_items.append(("Training Time", f"{training.training_time_hours:.1f} hours"))

            overview_card = self._build_info_card(
                "Training Overview",
                overview_items,
                icon_name="SCHOOL"
            )

            # Progress information
            progress_items = [
                ("Epochs", f"{training.completed_epochs}/{training.total_epochs}"),
                ("Steps", f"{training.completed_steps:,}/{training.total_steps:,}" if training.total_steps else f"{training.completed_steps:,}"),
                ("Checkpoints", str(training.checkpoint_count)),
                ("Validation Split", f"{training.validation_split:.1%}"),
                ("Early Stopping Patience", str(training.early_stopping_patience))
            ]

            if training.final_loss is not None:
                progress_items.append(("Final Loss", f"{training.final_loss:.6f}"))

            if training.best_loss is not None:
                progress_items.append(("Best Loss", f"{training.best_loss:.6f}"))

            if training.gpu_hours_used:
                progress_items.append(("GPU Hours", f"{training.gpu_hours_used:.1f}"))

            progress_card = self._build_info_card(
                "Training Progress",
                progress_items,
                icon_name="TRENDING_UP"
            )

            # Layout
            layout_manager = self.get_responsive_layout_manager()
            screen_size = layout_manager.get_screen_size_category()

            if screen_size in ["mobile", "tablet"]:
                return ft.Column(
                    controls=[overview_card, progress_card],
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO
                )
            else:
                return ft.Row(
                    controls=[overview_card, progress_card],
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                )

        except Exception as e:
            logger.error(f"Error building training panel: {e}")
            return self._build_error_state(str(e))

    def _build_performance_panel(self) -> ft.Control:
        """Build performance metrics panel."""
        try:
            if not self.model_data.performance_metrics:
                return self._build_no_data_state("No performance metrics available")

            metrics = self.model_data.performance_metrics

            # Accuracy metrics
            accuracy_items = []
            if metrics.accuracy is not None:
                accuracy_items.append(("Accuracy", f"{metrics.accuracy:.2%}"))
            if metrics.perplexity is not None:
                accuracy_items.append(("Perplexity", f"{metrics.perplexity:.2f}"))
            if metrics.bleu_score is not None:
                accuracy_items.append(("BLEU Score", f"{metrics.bleu_score:.3f}"))
            if metrics.rouge_score is not None:
                accuracy_items.append(("ROUGE Score", f"{metrics.rouge_score:.3f}"))
            if metrics.f1_score is not None:
                accuracy_items.append(("F1 Score", f"{metrics.f1_score:.3f}"))

            accuracy_card = self._build_info_card(
                "Accuracy Metrics",
                accuracy_items,
                icon_name="TARGET"
            ) if accuracy_items else None

            # Performance metrics
            performance_items = []
            if metrics.inference_time_ms is not None:
                performance_items.append(("Inference Time", f"{metrics.inference_time_ms:.1f} ms"))
            if metrics.throughput_tokens_per_second is not None:
                performance_items.append(("Throughput", f"{metrics.throughput_tokens_per_second:.1f} tokens/sec"))
            if metrics.latency_p50_ms is not None:
                performance_items.append(("Latency P50", f"{metrics.latency_p50_ms:.1f} ms"))
            if metrics.latency_p95_ms is not None:
                performance_items.append(("Latency P95", f"{metrics.latency_p95_ms:.1f} ms"))
            if metrics.latency_p99_ms is not None:
                performance_items.append(("Latency P99", f"{metrics.latency_p99_ms:.1f} ms"))

            performance_card = self._build_info_card(
                "Performance Metrics",
                performance_items,
                icon_name="SPEED"
            ) if performance_items else None

            # Resource usage
            resource_items = []
            if metrics.memory_usage_mb is not None:
                resource_items.append(("Memory Usage", f"{metrics.memory_usage_mb:.1f} MB"))
            if metrics.model_size_mb is not None:
                resource_items.append(("Model Size", f"{metrics.model_size_mb:.1f} MB"))
            if metrics.disk_usage_mb is not None:
                resource_items.append(("Disk Usage", f"{metrics.disk_usage_mb:.1f} MB"))
            if metrics.gpu_utilization_percent is not None:
                resource_items.append(("GPU Utilization", f"{metrics.gpu_utilization_percent:.1f}%"))
            if metrics.cpu_utilization_percent is not None:
                resource_items.append(("CPU Utilization", f"{metrics.cpu_utilization_percent:.1f}%"))

            if metrics.hardware_config:
                resource_items.append(("Hardware Config", metrics.hardware_config))
            if metrics.benchmark_date:
                resource_items.append(("Benchmark Date", metrics.benchmark_date.strftime("%Y-%m-%d")))

            resource_card = self._build_info_card(
                "Resource Usage",
                resource_items,
                icon_name="MEMORY"
            ) if resource_items else None

            # Custom metrics
            custom_card = None
            if metrics.custom_metrics:
                custom_items = [
                    (key.replace("_", " ").title(), f"{value:.3f}")
                    for key, value in metrics.custom_metrics.items()
                ]
                custom_card = self._build_info_card(
                    "Custom Metrics",
                    custom_items,
                    icon_name="ANALYTICS"
                )

            # Collect available cards
            cards = [card for card in [accuracy_card, performance_card, resource_card, custom_card] if card is not None]

            if not cards:
                return self._build_no_data_state("No performance data to display")

            # Layout
            layout_manager = self.get_responsive_layout_manager()
            screen_size = layout_manager.get_screen_size_category()

            if screen_size in ["mobile", "tablet"]:
                return ft.Column(
                    controls=cards,
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO
                )
            else:
                # Grid layout for desktop
                rows = []
                for i in range(0, len(cards), 2):
                    row_cards = cards[i:i+2]
                    rows.append(
                        ft.Row(
                            controls=row_cards,
                            spacing=self.get_spacing("lg"),
                            expand=True
                        )
                    )

                return ft.Column(
                    controls=rows,
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                )

        except Exception as e:
            logger.error(f"Error building performance panel: {e}")
            return self._build_error_state(str(e))

    def _build_versions_panel(self) -> ft.Control:
        """Build version information panel."""
        try:
            if not self.model_data.version_info:
                return self._build_no_data_state("No version information available")

            version = self.model_data.version_info

            # Version details
            version_items = [
                ("Version", version.version),
                ("Version ID", version.version_id),
                ("Created", version.created_at.strftime("%Y-%m-%d %H:%M:%S")),
                ("Is Latest", "Yes" if version.is_latest else "No"),
                ("Is Stable", "Yes" if version.is_stable else "No"),
                ("Download Count", f"{version.download_count:,}")
            ]

            if version.parent_version:
                version_items.insert(2, ("Parent Version", version.parent_version))
            if version.branch_name:
                version_items.insert(-2, ("Branch", version.branch_name))
            if version.commit_hash:
                version_items.insert(-2, ("Commit", version.commit_hash[:8]))
            if version.created_by:
                version_items.insert(-2, ("Created By", version.created_by))
            if version.file_size_mb:
                version_items.append(("File Size", f"{version.file_size_mb:.1f} MB"))

            version_card = self._build_info_card(
                "Version Information",
                version_items,
                icon_name="HISTORY"
            )

            # Tags and changelog
            additional_info = []

            if version.tags:
                tags_text = ft.Text(
                    value="Tags:",
                    style=self.get_text_style("label_medium"),
                    color=self.get_color("on_surface"),
                    weight=ft.FontWeight.BOLD
                )

                tag_chips = []
                for tag in sorted(version.tags):
                    chip = ft.Container(
                        content=ft.Text(
                            value=tag,
                            style=self.get_text_style("label_small"),
                            color=self.get_color("on_secondary_container")
                        ),
                        padding=ft.padding.symmetric(
                            horizontal=self.get_spacing("sm"),
                            vertical=self.get_spacing("xs")
                        ),
                        border_radius=ft.border_radius.all(12),
                        bgcolor=self.get_color("secondary_container")
                    )
                    tag_chips.append(chip)

                tags_section = ft.Column(
                    controls=[
                        tags_text,
                        ft.Container(height=self.get_spacing("xs")),
                        ft.Row(
                            controls=tag_chips,
                            spacing=self.get_spacing("xs"),
                            wrap=True
                        )
                    ],
                    spacing=0
                )
                additional_info.append(tags_section)

            if version.changelog:
                changelog_text = ft.Text(
                    value="Changelog:",
                    style=self.get_text_style("label_medium"),
                    color=self.get_color("on_surface"),
                    weight=ft.FontWeight.BOLD
                )

                changelog_content = ft.Text(
                    value=version.changelog,
                    style=self.get_text_style("body_medium"),
                    color=self.get_color("on_surface_variant"),
                    selectable=True
                )

                changelog_section = ft.Column(
                    controls=[
                        changelog_text,
                        ft.Container(height=self.get_spacing("xs")),
                        changelog_content
                    ],
                    spacing=0
                )
                additional_info.append(changelog_section)

            # Layout
            controls = [version_card]
            if additional_info:
                additional_card = ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=additional_info,
                            spacing=self.get_spacing("lg")
                        ),
                        padding=self.get_spacing("lg")
                    ),
                    elevation=1,
                    surface_tint_color=self.get_color("surface_tint")
                )
                controls.append(additional_card)

            return ft.Column(
                controls=controls,
                spacing=self.get_spacing("lg"),
                scroll=ft.ScrollMode.AUTO
            )

        except Exception as e:
            logger.error(f"Error building versions panel: {e}")
            return self._build_error_state(str(e))

    def _build_deployment_panel(self) -> ft.Control:
        """Build deployment information panel."""
        try:
            if not self.model_data.deployment_info:
                return self._build_no_deployment_state()

            deployment = self.model_data.deployment_info

            # Deployment status
            status_items = [
                ("Status", deployment.deployment_status.replace("_", " ").title()),
                ("Health", deployment.health_status.replace("_", " ").title())
            ]

            if deployment.deployment_id:
                status_items.insert(0, ("Deployment ID", deployment.deployment_id))
            if deployment.deployment_target:
                status_items.append(("Target", deployment.deployment_target))
            if deployment.deployment_url:
                status_items.append(("URL", deployment.deployment_url))
            if deployment.deployment_date:
                status_items.append(("Deployed", deployment.deployment_date.strftime("%Y-%m-%d %H:%M:%S")))
            if deployment.uptime_hours is not None:
                status_items.append(("Uptime", f"{deployment.uptime_hours:.1f} hours"))

            status_card = self._build_info_card(
                "Deployment Status",
                status_items,
                icon_name="CLOUD_UPLOAD"
            )

            # Performance metrics
            perf_items = []
            if deployment.request_count > 0:
                perf_items.append(("Total Requests", f"{deployment.request_count:,}"))
            if deployment.error_rate >= 0:
                perf_items.append(("Error Rate", f"{deployment.error_rate:.2%}"))
            if deployment.average_response_time_ms is not None:
                perf_items.append(("Avg Response Time", f"{deployment.average_response_time_ms:.1f} ms"))

            perf_card = self._build_info_card(
                "Performance Metrics",
                perf_items,
                icon_name="SPEED"
            ) if perf_items else None

            # Resource requirements
            resource_items = []
            if deployment.resource_requirements:
                for key, value in deployment.resource_requirements.items():
                    resource_items.append((key.replace("_", " ").title(), str(value)))

            resource_card = self._build_info_card(
                "Resource Requirements",
                resource_items,
                icon_name="MEMORY"
            ) if resource_items else None

            # Scaling configuration
            scaling_items = []
            if deployment.scaling_config:
                for key, value in deployment.scaling_config.items():
                    scaling_items.append((key.replace("_", " ").title(), str(value)))

            scaling_card = self._build_info_card(
                "Scaling Configuration",
                scaling_items,
                icon_name="SETTINGS"
            ) if scaling_items else None

            # Collect available cards
            cards = [card for card in [status_card, perf_card, resource_card, scaling_card] if card is not None]

            # Layout
            layout_manager = self.get_responsive_layout_manager()
            screen_size = layout_manager.get_screen_size_category()

            if screen_size in ["mobile", "tablet"]:
                return ft.Column(
                    controls=cards,
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO
                )
            else:
                # Grid layout for desktop
                rows = []
                for i in range(0, len(cards), 2):
                    row_cards = cards[i:i+2]
                    rows.append(
                        ft.Row(
                            controls=row_cards,
                            spacing=self.get_spacing("lg"),
                            expand=True
                        )
                    )

                return ft.Column(
                    controls=rows,
                    spacing=self.get_spacing("lg"),
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                )

        except Exception as e:
            logger.error(f"Error building deployment panel: {e}")
            return self._build_error_state(str(e))

    # Helper methods for building UI components
    def _build_info_card(self, title: str, items: List[Tuple[str, str]], icon_name: str = "INFO") -> ft.Control:
        """Build an information card with key-value pairs."""
        try:
            # Card header
            header = ft.Row(
                controls=[
                    ft.Icon(
                        name=self.get_icon(icon_name),
                        size=self.get_responsive_size("icon_medium"),
                        color=self.get_color("primary")
                    ),
                    ft.Text(
                        value=title,
                        style=self.get_text_style("title_medium"),
                        color=self.get_color("on_surface"),
                        weight=ft.FontWeight.BOLD
                    )
                ],
                spacing=self.get_spacing("sm")
            )

            # Card content
            content_items = []
            for label, value in items:
                item = ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Text(
                                value=label,
                                style=self.get_text_style("body_medium"),
                                color=self.get_color("on_surface_variant"),
                                weight=ft.FontWeight.W500
                            ),
                            width=self.get_responsive_size("info_label_width")
                        ),
                        ft.Expanded(
                            child=ft.Text(
                                value=value,
                                style=self.get_text_style("body_medium"),
                                color=self.get_color("on_surface"),
                                selectable=True
                            )
                        )
                    ],
                    spacing=self.get_spacing("md")
                )
                content_items.append(item)

            content = ft.Column(
                controls=content_items,
                spacing=self.get_spacing("sm")
            )

            return ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            header,
                            ft.Divider(
                                height=1,
                                color=self.get_color("outline_variant")
                            ),
                            content
                        ],
                        spacing=self.get_spacing("md")
                    ),
                    padding=self.get_spacing("lg")
                ),
                elevation=1,
                surface_tint_color=self.get_color("surface_tint")
            )

        except Exception as e:
            logger.error(f"Error building info card: {e}")
            return ft.Container()

    def _build_metadata_item(self, label: str, value: str) -> ft.Control:
        """Build a metadata item for the header."""
        try:
            return ft.Column(
                controls=[
                    ft.Text(
                        value=label,
                        style=self.get_text_style("label_small"),
                        color=self.get_color("on_surface_variant"),
                        weight=ft.FontWeight.W500
                    ),
                    ft.Text(
                        value=value,
                        style=self.get_text_style("body_small"),
                        color=self.get_color("on_surface"),
                        weight=ft.FontWeight.BOLD
                    )
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.START
            )
        except Exception as e:
            logger.error(f"Error building metadata item: {e}")
            return ft.Container()

    def _build_model_summary_card(self) -> ft.Control:
        """Build model summary card for overview."""
        try:
            if not self.model_data:
                return ft.Container()

            # Summary items
            summary_items = [
                ("Model ID", self.model_data.model_id),
                ("Status", self.model_data.status.value.title()),
                ("Created", self.model_data.created_at.strftime("%Y-%m-%d")),
                ("Last Updated", self.model_data.updated_at.strftime("%Y-%m-%d"))
            ]

            if self.model_data.created_by:
                summary_items.insert(-2, ("Created By", self.model_data.created_by))
            if self.model_data.project_id:
                summary_items.insert(1, ("Project", self.model_data.project_id))
            if self.model_data.access_count > 0:
                summary_items.append(("Access Count", str(self.model_data.access_count)))
            if self.model_data.last_accessed:
                summary_items.append(("Last Accessed", self.model_data.last_accessed.strftime("%Y-%m-%d")))

            return self._build_info_card(
                "Model Summary",
                summary_items,
                icon_name="INFO"
            )

        except Exception as e:
            logger.error(f"Error building model summary card: {e}")
            return ft.Container()

    def _build_quick_stats_card(self) -> ft.Control:
        """Build quick statistics card."""
        try:
            stats_items = []

            # Architecture stats
            if self.model_data.architecture_info:
                arch = self.model_data.architecture_info
                stats_items.append(("Parameters", f"{arch.parameters_count:,}" if arch.parameters_count else "Unknown"))
                stats_items.append(("Architecture", arch.architecture.value))
                stats_items.append(("Quantization", arch.quantization_type.value))

            # Performance stats
            if self.model_data.performance_metrics:
                perf = self.model_data.performance_metrics
                if perf.accuracy is not None:
                    stats_items.append(("Accuracy", f"{perf.accuracy:.1%}"))
                if perf.inference_time_ms is not None:
                    stats_items.append(("Inference Time", f"{perf.inference_time_ms:.1f} ms"))
                if perf.model_size_mb is not None:
                    stats_items.append(("Model Size", f"{perf.model_size_mb:.1f} MB"))

            if not stats_items:
                return ft.Container()

            return self._build_info_card(
                "Quick Statistics",
                stats_items,
                icon_name="ANALYTICS"
            )

        except Exception as e:
            logger.error(f"Error building quick stats card: {e}")
            return ft.Container()

    def _build_recent_activity_card(self) -> ft.Control:
        """Build recent activity card."""
        try:
            if not self.model_data.training_history:
                return ft.Container()

            training = self.model_data.training_history
            activity_items = [
                ("Training Status", training.status.value.title()),
                ("Progress", f"{training.completed_epochs}/{training.total_epochs} epochs"),
                ("Checkpoints", str(training.checkpoint_count))
            ]

            if training.final_loss is not None:
                activity_items.append(("Final Loss", f"{training.final_loss:.6f}"))
            if training.training_time_hours is not None:
                activity_items.append(("Training Time", f"{training.training_time_hours:.1f} hours"))

            return self._build_info_card(
                "Recent Activity",
                activity_items,
                icon_name="HISTORY"
            )

        except Exception as e:
            logger.error(f"Error building recent activity card: {e}")
            return ft.Container()

    def _build_custom_layers_card(self, custom_layers: List[str]) -> ft.Control:
        """Build custom layers information card."""
        try:
            layers_text = ft.Text(
                value="Custom Layers:",
                style=self.get_text_style("label_medium"),
                color=self.get_color("on_surface"),
                weight=ft.FontWeight.BOLD
            )

            layer_items = []
            for i, layer in enumerate(custom_layers, 1):
                layer_item = ft.Text(
                    value=f"{i}. {layer}",
                    style=self.get_text_style("body_medium"),
                    color=self.get_color("on_surface_variant")
                )
                layer_items.append(layer_item)

            content = ft.Column(
                controls=[layers_text] + layer_items,
                spacing=self.get_spacing("xs")
            )

            return ft.Card(
                content=ft.Container(
                    content=content,
                    padding=self.get_spacing("lg")
                ),
                elevation=1,
                surface_tint_color=self.get_color("surface_tint")
            )

        except Exception as e:
            logger.error(f"Error building custom layers card: {e}")
            return ft.Container()

    # State management methods
    def _build_loading_state(self) -> ft.Control:
        """Build loading state display."""
        try:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(
                            width=self.get_responsive_size("progress_ring"),
                            height=self.get_responsive_size("progress_ring"),
                            stroke_width=4,
                            color=self.get_color("primary")
                        ),
                        ft.Container(height=self.get_spacing("md")),
                        ft.Text(
                            value="Loading model details...",
                            style=self.get_text_style("body_large"),
                            color=self.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=self.get_spacing("md")
                ),
                alignment=ft.alignment.center,
                expand=True
            )
        except Exception as e:
            logger.error(f"Error building loading state: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state display."""
        try:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=self.get_icon("ERROR"),
                            size=self.get_responsive_size("icon_large"),
                            color=self.get_color("error")
                        ),
                        ft.Container(height=self.get_spacing("md")),
                        ft.Text(
                            value="Error Loading Model Details",
                            style=self.get_text_style("headline_small"),
                            color=self.get_color("error"),
                            text_align=ft.TextAlign.CENTER,
                            weight=ft.FontWeight.BOLD
                        ),
                        ft.Container(height=self.get_spacing("sm")),
                        ft.Text(
                            value=error_message,
                            style=self.get_text_style("body_medium"),
                            color=self.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Container(height=self.get_spacing("lg")),
                        ft.ElevatedButton(
                            text="Retry",
                            icon=self.get_icon("REFRESH"),
                            on_click=self._on_retry_clicked,
                            style=ft.ButtonStyle(
                                color=self.get_color("on_primary"),
                                bgcolor=self.get_color("primary")
                            )
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

    def _build_no_data_state(self, message: str = "No data available") -> ft.Control:
        """Build no data state display."""
        try:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=self.get_icon("INBOX"),
                            size=self.get_responsive_size("icon_large"),
                            color=self.get_color("on_surface_variant")
                        ),
                        ft.Container(height=self.get_spacing("md")),
                        ft.Text(
                            value=message,
                            style=self.get_text_style("body_large"),
                            color=self.get_color("on_surface_variant"),
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
            logger.error(f"Error building no data state: {e}")
            return ft.Container()

    def _build_no_deployment_state(self) -> ft.Control:
        """Build no deployment state with deployment option."""
        try:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=self.get_icon("CLOUD_OFF"),
                            size=self.get_responsive_size("icon_large"),
                            color=self.get_color("on_surface_variant")
                        ),
                        ft.Container(height=self.get_spacing("md")),
                        ft.Text(
                            value="Model Not Deployed",
                            style=self.get_text_style("headline_small"),
                            color=self.get_color("on_surface"),
                            text_align=ft.TextAlign.CENTER,
                            weight=ft.FontWeight.BOLD
                        ),
                        ft.Container(height=self.get_spacing("sm")),
                        ft.Text(
                            value="This model has not been deployed yet. Deploy it to start serving predictions.",
                            style=self.get_text_style("body_medium"),
                            color=self.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Container(height=self.get_spacing("lg")),
                        ft.ElevatedButton(
                            text="Deploy Model",
                            icon=self.get_icon("CLOUD_UPLOAD"),
                            on_click=self._on_deploy_clicked,
                            style=ft.ButtonStyle(
                                color=self.get_color("on_primary"),
                                bgcolor=self.get_color("primary")
                            )
                        ) if self.config.enable_deployment_actions else ft.Container()
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0
                ),
                alignment=ft.alignment.center,
                expand=True
            )
        except Exception as e:
            logger.error(f"Error building no deployment state: {e}")
            return ft.Container()

    # Event handlers
    def _on_mode_changed(self, e: ft.ControlEvent) -> None:
        """Handle mode tab change."""
        try:
            if self._mode_tabs and e.control.selected_index is not None:
                modes = [mode for mode in ModelDetailsMode if self._should_show_mode(mode)]
                if 0 <= e.control.selected_index < len(modes):
                    new_mode = modes[e.control.selected_index]
                    if new_mode != self._current_mode:
                        self._current_mode = new_mode
                        self._refresh_content()
        except Exception as e:
            logger.error(f"Error handling mode change: {e}")

    def _on_mode_dropdown_changed(self, e: ft.ControlEvent) -> None:
        """Handle mode dropdown change."""
        try:
            if e.control.value:
                new_mode = ModelDetailsMode(e.control.value)
                if new_mode != self._current_mode:
                    self._current_mode = new_mode
                    self._refresh_content()
        except Exception as e:
            logger.error(f"Error handling mode dropdown change: {e}")

    def _on_export_clicked(self, e: ft.ControlEvent) -> None:
        """Handle export button click."""
        try:
            if self.on_export_requested and self.model_data:
                self.on_export_requested(self.model_data.model_id, "full")
        except Exception as e:
            logger.error(f"Error handling export click: {e}")

    def _on_compare_clicked(self, e: ft.ControlEvent) -> None:
        """Handle compare button click."""
        try:
            if self.on_comparison_requested and self.model_data:
                self.on_comparison_requested([self.model_data.model_id])
        except Exception as e:
            logger.error(f"Error handling compare click: {e}")

    def _on_deploy_clicked(self, e: ft.ControlEvent) -> None:
        """Handle deploy button click."""
        try:
            if self.on_deployment_action and self.model_data:
                self.on_deployment_action(self.model_data.model_id, "deploy")
        except Exception as e:
            logger.error(f"Error handling deploy click: {e}")

    def _on_manage_deployment_clicked(self, e: ft.ControlEvent) -> None:
        """Handle manage deployment button click."""
        try:
            if self.on_deployment_action and self.model_data:
                self.on_deployment_action(self.model_data.model_id, "manage")
        except Exception as e:
            logger.error(f"Error handling manage deployment click: {e}")

    def _on_mobile_actions_clicked(self, e: ft.ControlEvent) -> None:
        """Handle mobile actions button click."""
        try:
            # Show action sheet or menu for mobile
            actions = []

            if self.config.enable_export:
                actions.append(("Export", self._on_export_clicked))
            if self.config.enable_comparison:
                actions.append(("Compare", self._on_compare_clicked))
            if self.config.enable_deployment_actions:
                if self.model_data and self.model_data.deployment_info and self.model_data.deployment_info.deployment_status == "deployed":
                    actions.append(("Manage Deployment", self._on_manage_deployment_clicked))
                else:
                    actions.append(("Deploy", self._on_deploy_clicked))

            # For now, just trigger the first action
            if actions:
                actions[0][1](e)

        except Exception as e:
            logger.error(f"Error handling mobile actions click: {e}")

    def _on_retry_clicked(self, e: ft.ControlEvent) -> None:
        """Handle retry button click."""
        try:
            self._error_message = None
            self.refresh_data()
        except Exception as e:
            logger.error(f"Error handling retry click: {e}")

    # Utility methods
    def _should_show_mode(self, mode: ModelDetailsMode) -> bool:
        """Check if a mode should be shown based on configuration."""
        try:
            if mode == ModelDetailsMode.ARCHITECTURE:
                return self.config.show_architecture_details
            elif mode == ModelDetailsMode.TRAINING:
                return self.config.show_training_history
            elif mode == ModelDetailsMode.PERFORMANCE:
                return self.config.show_performance_metrics
            elif mode == ModelDetailsMode.VERSIONS:
                return self.config.show_version_info
            elif mode == ModelDetailsMode.DEPLOYMENT:
                return self.config.show_deployment_info
            else:
                return True  # Always show overview and comparison
        except Exception as e:
            logger.error(f"Error checking mode visibility: {e}")
            return True

    def _get_mode_index(self, mode: ModelDetailsMode) -> int:
        """Get the index of a mode in the available modes list."""
        try:
            modes = [m for m in ModelDetailsMode if self._should_show_mode(m)]
            return modes.index(mode) if mode in modes else 0
        except Exception as e:
            logger.error(f"Error getting mode index: {e}")
            return 0

    def _get_status_color(self, status: ModelStatus) -> str:
        """Get color for model status."""
        try:
            status_colors = {
                ModelStatus.TRAINING: self.get_color("warning"),
                ModelStatus.COMPLETED: self.get_color("success"),
                ModelStatus.DEPLOYED: self.get_color("info"),
                ModelStatus.ARCHIVED: self.get_color("on_surface_variant"),
                ModelStatus.FAILED: self.get_color("error"),
                ModelStatus.PAUSED: self.get_color("warning")
            }
            return status_colors.get(status, self.get_color("on_surface_variant"))
        except Exception as e:
            logger.error(f"Error getting status color: {e}")
            return self.get_color("on_surface_variant")

    def _get_status_icon(self, status: ModelStatus) -> str:
        """Get icon for model status."""
        try:
            status_icons = {
                ModelStatus.TRAINING: "SCHOOL",
                ModelStatus.COMPLETED: "CHECK_CIRCLE",
                ModelStatus.DEPLOYED: "CLOUD_DONE",
                ModelStatus.ARCHIVED: "ARCHIVE",
                ModelStatus.FAILED: "ERROR",
                ModelStatus.PAUSED: "PAUSE_CIRCLE"
            }
            return self.get_icon(status_icons.get(status, "HELP"))
        except Exception as e:
            logger.error(f"Error getting status icon: {e}")
            return self.get_icon("HELP")

    def _refresh_content(self) -> None:
        """Refresh the content area."""
        try:
            if self._content_container:
                new_content = self._build_content_area()
                self._content_container.content = new_content.content
                self._content_container.update()
        except Exception as e:
            logger.error(f"Error refreshing content: {e}")

    # Public methods
    def update_model_data(self, model_data: ModelDetailsData) -> None:
        """Update the model data and refresh the display."""
        try:
            with self._update_lock:
                self.model_data = model_data
                self._last_update = datetime.now(timezone.utc)

                if self.on_model_updated:
                    self.on_model_updated(model_data)

                # Refresh the UI
                self.content = self.build()
                self.update()

        except Exception as e:
            logger.error(f"Error updating model data: {e}")

    def refresh_data(self) -> None:
        """Refresh the model data display."""
        try:
            self._is_loading = True
            self._error_message = None

            # Refresh the UI to show loading state
            self.content = self.build()
            self.update()

            # In a real implementation, this would trigger data loading
            # For now, just clear the loading state
            self._is_loading = False
            self.content = self.build()
            self.update()

        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            self._is_loading = False
            self._error_message = str(e)
            self.content = self.build()
            self.update()

    def set_mode(self, mode: ModelDetailsMode) -> None:
        """Set the current display mode."""
        try:
            if mode != self._current_mode and self._should_show_mode(mode):
                self._current_mode = mode

                # Update tabs if available
                if self._mode_tabs:
                    self._mode_tabs.selected_index = self._get_mode_index(mode)
                    self._mode_tabs.update()

                self._refresh_content()

        except Exception as e:
            logger.error(f"Error setting mode: {e}")

    def get_current_mode(self) -> ModelDetailsMode:
        """Get the current display mode."""
        return self._current_mode

    def set_config(self, config: ModelDetailsConfig) -> None:
        """Update the configuration and refresh the display."""
        try:
            self.config = config

            # Refresh the UI
            self.content = self.build()
            self.update()

        except Exception as e:
            logger.error(f"Error setting config: {e}")
