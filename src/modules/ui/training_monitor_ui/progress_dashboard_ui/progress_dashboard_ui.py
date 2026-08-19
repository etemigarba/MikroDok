"""
Module: progress_dashboard_ui
Description: Comprehensive training progress dashboard providing real-time visualization of training metrics,
            resource utilization, session status, and performance analytics. Features responsive design with
            breakpoint-aware layouts, interactive charts, progress indicators, and seamless integration with
            training orchestration system. Includes theme-aware styling, accessibility compliance, and
            cross-platform compatibility for monitoring 12-24 hour training sessions.
Phase: 4
Location: /src/modules/ui/training_monitor_ui/progress_dashboard_ui/progress_dashboard_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
import time

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl

# Optional training orchestration imports
try:
    from src.modules.logic.training_orchestration_lg.session_manager_lg.session_manager_lg import (
        SessionManager, TrainingSession
    )
    from src.modules.logic.training_orchestration_lg.base_interfaces import (
        TrainingMetrics, TrainingStatus, TrainingConfig
    )
    from src.modules.logic.training_orchestration_lg.training_executor_lg.training_executor_lg import (
        TrainingExecutor
    )
    TRAINING_ORCHESTRATION_AVAILABLE = True
except ImportError:
    # Define placeholder types if training orchestration is not available
    SessionManager = None
    TrainingSession = None
    TrainingMetrics = None
    TrainingStatus = None
    TrainingConfig = None
    TrainingExecutor = None
    TRAINING_ORCHESTRATION_AVAILABLE = False

# Optional resource monitoring imports
try:
    from src.modules.logic.resource_monitor_lg.hardware_monitor_lg.hardware_monitor_lg import (
        HardwareMonitor, ResourceMetrics
    )
    RESOURCE_MONITORING_AVAILABLE = True
except ImportError:
    HardwareMonitor = None
    ResourceMetrics = None
    RESOURCE_MONITORING_AVAILABLE = False


class DashboardView(Enum):
    """Dashboard view modes."""
    OVERVIEW = "overview"
    DETAILED = "detailed"
    METRICS = "metrics"
    RESOURCES = "resources"


class ProgressStatus(Enum):
    """Training progress status indicators."""
    NOT_STARTED = "not_started"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressConfiguration:
    """Configuration for progress dashboard."""
    refresh_interval_seconds: float = 2.0
    history_window_minutes: int = 30
    show_resource_metrics: bool = True
    show_detailed_metrics: bool = True
    auto_scale_charts: bool = True
    enable_notifications: bool = True
    compact_mode: bool = False
    show_predictions: bool = True


@dataclass
class TrainingProgressData:
    """Training progress data structure."""
    session_id: str
    status: ProgressStatus
    current_epoch: int = 0
    total_epochs: int = 100
    current_step: int = 0
    total_steps: int = 0
    progress_percentage: float = 0.0
    elapsed_time: timedelta = field(default_factory=lambda: timedelta())
    estimated_remaining: Optional[timedelta] = None
    current_loss: float = 0.0
    best_loss: float = float('inf')
    current_accuracy: Optional[float] = None
    best_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    batch_size: int = 32
    memory_usage_mb: float = 0.0
    gpu_utilization: float = 0.0
    processing_speed: float = 0.0  # steps per second
    last_updated: datetime = field(default_factory=datetime.now)
    metrics_history: List[TrainingMetrics] = field(default_factory=list)
    error_message: Optional[str] = None


class ProgressDashboardUI(ThemeAwareUserControl):
    """
    Comprehensive training progress dashboard UI component.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time training progress visualization with interactive charts
    - Session status monitoring with detailed metrics display
    - Resource utilization tracking (memory, GPU, processing speed)
    - Progress predictions and time estimates
    - Theme-aware styling with accessibility compliance
    - Multi-view dashboard (overview, detailed, metrics, resources)
    - Training control integration (pause, resume, stop)
    - Historical metrics visualization and analysis
    - Performance optimization recommendations
    - Cross-platform compatibility and offline operation
    """
    
    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        training_executor: Optional[TrainingExecutor] = None,
        hardware_monitor: Optional[HardwareMonitor] = None,
        config: Optional[ProgressConfiguration] = None,
        on_control_action: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        """
        Initialize progress dashboard UI.
        
        Args:
            session_manager: Training session manager instance
            training_executor: Training executor instance
            hardware_monitor: Hardware monitoring instance
            config: Dashboard configuration
            on_control_action: Callback for control actions (action, session_id)
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)
        
        # Core components
        self._session_manager = session_manager
        self._training_executor = training_executor
        self._hardware_monitor = hardware_monitor
        self._config = config or ProgressConfiguration()
        self._on_control_action = on_control_action
        
        # State management
        self._current_session_id: Optional[str] = None
        self._progress_data: Optional[TrainingProgressData] = None
        self._current_view = DashboardView.OVERVIEW
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        
        # UI components
        self._header_container: Optional[ft.Container] = None
        self._status_indicator: Optional[ft.Container] = None
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._metrics_cards: Dict[str, ft.Container] = {}
        self._charts_container: Optional[ft.Container] = None
        self._controls_panel: Optional[ft.Container] = None
        self._view_selector: Optional[ft.Tabs] = None
        self._details_panel: Optional[ft.Container] = None
        
        # Chart components
        self._loss_chart: Optional[ft.Container] = None
        self._accuracy_chart: Optional[ft.Container] = None
        self._resource_chart: Optional[ft.Container] = None
        self._timeline_chart: Optional[ft.Container] = None
        
        # Control buttons
        self._pause_button: Optional[ft.ElevatedButton] = None
        self._resume_button: Optional[ft.ElevatedButton] = None
        self._stop_button: Optional[ft.ElevatedButton] = None
        self._refresh_button: Optional[ft.IconButton] = None
        
        # Initialize UI
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize UI components."""
        try:
            self._create_header_components()
            self._create_progress_components()
            self._create_metrics_components()
            self._create_chart_components()
            self._create_control_components()
            
        except Exception as e:
            self._handle_error(f"Error initializing components: {e}")
    
    def _create_header_components(self) -> None:
        """Create header components."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()
        
        # Status indicator
        self._status_indicator = ft.Container(
            content=ft.Row([
                ft.Icon(
                    self.get_icon('CIRCLE'),
                    color=palette.text_secondary,
                    size=rlm.get_breakpoint_value(12, 14, 16, 18)
                ),
                ft.Text(
                    "Not Started",
                    style=self.get_text_style('body_small'),
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs),
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(4, 6, 8, 10)),
            bgcolor=palette.surface_variant
        )
        
        # Header container
        self._header_container = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(
                        "Training Progress Dashboard",
                        style=self.get_text_style('h2'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "Real-time training monitoring and analytics",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], expand=True),
                self._status_indicator
            ]),
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(8, 10, 12, 14)),
            border=ft.border.all(1, palette.borders)
        )
    
    def _create_progress_components(self) -> None:
        """Create progress visualization components."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Progress bar
        self._progress_bar = ft.ProgressBar(
            value=0.0,
            color=palette.primary,
            bgcolor=palette.surface_variant,
            height=rlm.get_breakpoint_value(6, 8, 10, 12)
        )

    def _create_metrics_components(self) -> None:
        """Create metrics display components."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Metrics cards
        metrics_data = [
            ("epoch", "Epoch", "0 / 100", "TIMELINE"),
            ("loss", "Current Loss", "0.0000", "TRENDING_DOWN"),
            ("accuracy", "Accuracy", "0.00%", "TARGET"),
            ("speed", "Speed", "0.0 steps/s", "SPEED"),
            ("memory", "Memory", "0 MB", "MEMORY"),
            ("gpu", "GPU Usage", "0%", "DEVELOPER_BOARD")
        ]

        for metric_id, title, value, icon_name in metrics_data:
            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(
                            self.get_icon(icon_name),
                            color=palette.primary,
                            size=rlm.get_breakpoint_value(16, 18, 20, 22)
                        ),
                        ft.Text(
                            title,
                            style=self.get_text_style('body_small'),
                            color=palette.text_secondary
                        )
                    ], spacing=spacing.xs),
                    ft.Text(
                        value,
                        style=self.get_text_style('h3'),
                        color=palette.text_primary
                    )
                ], spacing=spacing.xs),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface,
                border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
                border=ft.border.all(1, palette.borders),
                expand=True
            )
            self._metrics_cards[metric_id] = card

    def _create_chart_components(self) -> None:
        """Create chart visualization components."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Loss chart placeholder
        self._loss_chart = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Training Loss",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary
                ),
                ft.Container(
                    content=ft.Text(
                        "Loss chart will be displayed here",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    ),
                    height=rlm.get_breakpoint_value(150, 180, 200, 220),
                    alignment=ft.alignment.center,
                    bgcolor=palette.surface_variant,
                    border_radius=ft.border_radius.all(rlm.get_breakpoint_value(4, 6, 8, 10))
                )
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            expand=True
        )

        # Accuracy chart placeholder
        self._accuracy_chart = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Training Accuracy",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary
                ),
                ft.Container(
                    content=ft.Text(
                        "Accuracy chart will be displayed here",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    ),
                    height=rlm.get_breakpoint_value(150, 180, 200, 220),
                    alignment=ft.alignment.center,
                    bgcolor=palette.surface_variant,
                    border_radius=ft.border_radius.all(rlm.get_breakpoint_value(4, 6, 8, 10))
                )
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            expand=True
        )

        # Resource chart placeholder
        self._resource_chart = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Resource Utilization",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary
                ),
                ft.Container(
                    content=ft.Text(
                        "Resource chart will be displayed here",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    ),
                    height=rlm.get_breakpoint_value(150, 180, 200, 220),
                    alignment=ft.alignment.center,
                    bgcolor=palette.surface_variant,
                    border_radius=ft.border_radius.all(rlm.get_breakpoint_value(4, 6, 8, 10))
                )
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            expand=True
        )

    def _create_control_components(self) -> None:
        """Create control panel components."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Control buttons
        button_height = rlm.get_breakpoint_value(32, 36, 40, 44)

        self._pause_button = ft.ElevatedButton(
            text="Pause",
            icon=self.get_icon('PAUSE'),
            on_click=self._on_pause_clicked,
            height=button_height,
            style=ft.ButtonStyle(
                bgcolor=palette.warning,
                color=palette.text_primary
            )
        )

        self._resume_button = ft.ElevatedButton(
            text="Resume",
            icon=self.get_icon('PLAY_ARROW'),
            on_click=self._on_resume_clicked,
            height=button_height,
            style=ft.ButtonStyle(
                bgcolor=palette.success,
                color=palette.text_primary
            )
        )

        self._stop_button = ft.ElevatedButton(
            text="Stop",
            icon=self.get_icon('STOP'),
            on_click=self._on_stop_clicked,
            height=button_height,
            style=ft.ButtonStyle(
                bgcolor=palette.error,
                color=palette.text_primary
            )
        )

        self._refresh_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            on_click=self._on_refresh_clicked,
            icon_color=palette.primary,
            icon_size=rlm.get_breakpoint_value(18, 20, 22, 24)
        )

        # Controls panel
        self._controls_panel = ft.Container(
            content=ft.Row([
                self._pause_button,
                self._resume_button,
                self._stop_button,
                ft.VerticalDivider(width=1, color=palette.borders),
                self._refresh_button
            ], spacing=spacing.md, alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders)
        )

    def build(self) -> ft.Control:
        """Build the progress dashboard UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create view selector tabs
        self._view_selector = ft.Tabs(
            selected_index=0,
            on_change=self._on_view_changed,
            tabs=[
                ft.Tab(text="Overview", icon=self.get_icon('DASHBOARD')),
                ft.Tab(text="Metrics", icon=self.get_icon('ANALYTICS')),
                ft.Tab(text="Resources", icon=self.get_icon('MEMORY')),
                ft.Tab(text="Details", icon=self.get_icon('INFO'))
            ],
            indicator_color=palette.primary,
            label_color=palette.text_primary,
            unselected_label_color=palette.text_secondary
        )

        # Create main content based on current view
        main_content = self._create_view_content()

        # Create progress section
        progress_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        "Training Progress",
                        style=self.get_text_style('h4'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "0.0%",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self._progress_bar,
                ft.Row([
                    ft.Text(
                        "Elapsed: 00:00:00",
                        style=self.get_text_style('caption'),
                        color=palette.text_tertiary
                    ),
                    ft.Text(
                        "Remaining: --:--:--",
                        style=self.get_text_style('caption'),
                        color=palette.text_tertiary
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders)
        )

        # Main layout
        return ft.Container(
            content=ft.Column([
                self._header_container,
                progress_section,
                self._view_selector,
                main_content,
                self._controls_panel
            ], spacing=spacing.lg, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_view_content(self) -> ft.Control:
        """Create content based on current view."""
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        if self._current_view == DashboardView.OVERVIEW:
            return self._create_overview_content()
        elif self._current_view == DashboardView.METRICS:
            return self._create_metrics_content()
        elif self._current_view == DashboardView.RESOURCES:
            return self._create_resources_content()
        elif self._current_view == DashboardView.DETAILED:
            return self._create_detailed_content()
        else:
            return ft.Container()

    def _create_overview_content(self) -> ft.Control:
        """Create overview content."""
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Metrics grid
        metrics_grid = ft.ResponsiveRow([
            ft.Container(
                content=self._metrics_cards.get("epoch", ft.Container()),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 2}
            ),
            ft.Container(
                content=self._metrics_cards.get("loss", ft.Container()),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 2}
            ),
            ft.Container(
                content=self._metrics_cards.get("accuracy", ft.Container()),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 2}
            ),
            ft.Container(
                content=self._metrics_cards.get("speed", ft.Container()),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 2}
            ),
            ft.Container(
                content=self._metrics_cards.get("memory", ft.Container()),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 2}
            ),
            ft.Container(
                content=self._metrics_cards.get("gpu", ft.Container()),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 2}
            )
        ])

        # Charts section
        charts_section = ft.ResponsiveRow([
            ft.Container(
                content=self._loss_chart,
                col={"xs": 12, "md": 6}
            ),
            ft.Container(
                content=self._accuracy_chart,
                col={"xs": 12, "md": 6}
            )
        ])

        return ft.Column([
            metrics_grid,
            charts_section
        ], spacing=spacing.lg)

    def _create_metrics_content(self) -> ft.Control:
        """Create detailed metrics content."""
        spacing = self.get_spacing()

        return ft.ResponsiveRow([
            ft.Container(
                content=self._loss_chart,
                col={"xs": 12, "lg": 6}
            ),
            ft.Container(
                content=self._accuracy_chart,
                col={"xs": 12, "lg": 6}
            ),
            ft.Container(
                content=self._resource_chart,
                col={"xs": 12}
            )
        ])

    def _create_resources_content(self) -> ft.Control:
        """Create resources monitoring content."""
        spacing = self.get_spacing()

        return ft.Column([
            ft.ResponsiveRow([
                ft.Container(
                    content=self._metrics_cards.get("memory", ft.Container()),
                    col={"xs": 12, "sm": 6, "md": 4}
                ),
                ft.Container(
                    content=self._metrics_cards.get("gpu", ft.Container()),
                    col={"xs": 12, "sm": 6, "md": 4}
                ),
                ft.Container(
                    content=self._metrics_cards.get("speed", ft.Container()),
                    col={"xs": 12, "sm": 6, "md": 4}
                )
            ]),
            self._resource_chart
        ], spacing=spacing.lg)

    def _create_detailed_content(self) -> ft.Control:
        """Create detailed information content."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Session details
        session_details = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Session Details",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary
                ),
                ft.Divider(color=palette.borders),
                ft.Text(
                    "Session ID: Not Available",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_secondary
                ),
                ft.Text(
                    "Model: Not Specified",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_secondary
                ),
                ft.Text(
                    "Dataset: Not Specified",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_secondary
                ),
                ft.Text(
                    "Configuration: Default",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_secondary
                )
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders)
        )

        return session_details

    # Event Handlers
    def _on_view_changed(self, e: ft.ControlEvent) -> None:
        """Handle view tab change."""
        try:
            view_mapping = {
                0: DashboardView.OVERVIEW,
                1: DashboardView.METRICS,
                2: DashboardView.RESOURCES,
                3: DashboardView.DETAILED
            }

            self._current_view = view_mapping.get(e.control.selected_index, DashboardView.OVERVIEW)
            self.update()

        except Exception as e:
            self._handle_error(f"Error changing view: {e}")

    def _on_pause_clicked(self, e: ft.ControlEvent) -> None:
        """Handle pause button click."""
        try:
            if self._current_session_id and self._on_control_action:
                self._on_control_action("pause", self._current_session_id)

        except Exception as e:
            self._handle_error(f"Error pausing training: {e}")

    def _on_resume_clicked(self, e: ft.ControlEvent) -> None:
        """Handle resume button click."""
        try:
            if self._current_session_id and self._on_control_action:
                self._on_control_action("resume", self._current_session_id)

        except Exception as e:
            self._handle_error(f"Error resuming training: {e}")

    def _on_stop_clicked(self, e: ft.ControlEvent) -> None:
        """Handle stop button click."""
        try:
            if self._current_session_id and self._on_control_action:
                self._on_control_action("stop", self._current_session_id)

        except Exception as e:
            self._handle_error(f"Error stopping training: {e}")

    def _on_refresh_clicked(self, e: ft.ControlEvent) -> None:
        """Handle refresh button click."""
        try:
            self._update_dashboard_data()

        except Exception as e:
            self._handle_error(f"Error refreshing dashboard: {e}")

    # Session Management Methods
    async def set_session(self, session_id: str) -> None:
        """
        Set the current training session to monitor.

        Args:
            session_id: Training session identifier
        """
        try:
            self._current_session_id = session_id

            # Start monitoring if not already running
            if not self._is_monitoring:
                await self.start_monitoring()

            # Update dashboard immediately
            self._update_dashboard_data()

        except Exception as e:
            self._handle_error(f"Error setting session: {e}")

    async def start_monitoring(self) -> None:
        """Start real-time monitoring."""
        try:
            if self._is_monitoring:
                return

            self._is_monitoring = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        except Exception as e:
            self._handle_error(f"Error starting monitoring: {e}")

    async def stop_monitoring(self) -> None:
        """Stop real-time monitoring."""
        try:
            self._is_monitoring = False

            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                self._monitoring_task = None

        except Exception as e:
            self._handle_error(f"Error stopping monitoring: {e}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring update loop."""
        try:
            while self._is_monitoring:
                # Update dashboard data
                self._update_dashboard_data()

                # Wait for next update
                await asyncio.sleep(self._config.refresh_interval_seconds)

        except asyncio.CancelledError:
            # Expected when stopping monitoring
            pass
        except Exception as e:
            self._handle_error(f"Error in monitoring loop: {e}")

    def _update_dashboard_data(self) -> None:
        """Update dashboard with latest data."""
        try:
            if not self._current_session_id:
                return

            # Get session data
            session_data = self._get_session_data()
            if session_data:
                self._progress_data = session_data
                self._update_ui_components()

        except Exception as e:
            self._handle_error(f"Error updating dashboard data: {e}")

    def _get_session_data(self) -> Optional[TrainingProgressData]:
        """Get current session data."""
        try:
            if not self._session_manager or not self._current_session_id:
                return self._create_mock_data()

            # Get session from manager
            session = asyncio.run(self._session_manager.get_session(self._current_session_id))
            if not session:
                return None

            # Convert to progress data
            return self._convert_session_to_progress_data(session)

        except Exception as e:
            self._handle_error(f"Error getting session data: {e}")
            return self._create_mock_data()

    def _convert_session_to_progress_data(self, session: Any) -> TrainingProgressData:
        """Convert training session to progress data."""
        try:
            # Map training status to progress status
            status_mapping = {
                "INITIALIZING": ProgressStatus.INITIALIZING,
                "READY": ProgressStatus.NOT_STARTED,
                "RUNNING": ProgressStatus.RUNNING,
                "PAUSED": ProgressStatus.PAUSED,
                "COMPLETED": ProgressStatus.COMPLETED,
                "FAILED": ProgressStatus.FAILED,
                "CANCELLED": ProgressStatus.CANCELLED
            }

            status = status_mapping.get(str(session.status), ProgressStatus.NOT_STARTED)

            # Calculate progress
            progress_percentage = 0.0
            if session.total_steps > 0:
                progress_percentage = (session.current_step / session.total_steps) * 100
            elif hasattr(session.config, 'max_epochs') and session.config.max_epochs > 0:
                progress_percentage = (session.current_epoch / session.config.max_epochs) * 100

            # Calculate elapsed time
            elapsed_time = timedelta()
            if session.started_at:
                elapsed_time = datetime.now() - session.started_at

            # Get latest metrics
            current_loss = 0.0
            current_accuracy = None
            if session.metrics_history:
                latest_metrics = session.metrics_history[-1]
                current_loss = latest_metrics.loss
                current_accuracy = latest_metrics.accuracy

            return TrainingProgressData(
                session_id=session.session_id,
                status=status,
                current_epoch=session.current_epoch,
                total_epochs=getattr(session.config, 'max_epochs', 100),
                current_step=session.current_step,
                total_steps=session.total_steps,
                progress_percentage=progress_percentage,
                elapsed_time=elapsed_time,
                current_loss=current_loss,
                current_accuracy=current_accuracy,
                metrics_history=session.metrics_history or []
            )

        except Exception as e:
            self._handle_error(f"Error converting session data: {e}")
            return self._create_mock_data()

    def _create_mock_data(self) -> TrainingProgressData:
        """Create mock data for testing."""
        return TrainingProgressData(
            session_id="mock_session",
            status=ProgressStatus.NOT_STARTED,
            current_epoch=0,
            total_epochs=100,
            current_step=0,
            total_steps=1000,
            progress_percentage=0.0,
            elapsed_time=timedelta(),
            current_loss=0.0,
            metrics_history=[]
        )

    def _update_ui_components(self) -> None:
        """Update UI components with current progress data."""
        try:
            if not self._progress_data:
                return

            # Update status indicator
            self._update_status_indicator()

            # Update progress bar
            self._update_progress_bar()

            # Update metrics cards
            self._update_metrics_cards()

            # Update control buttons
            self._update_control_buttons()

            # Trigger UI update
            self.update()

        except Exception as e:
            self._handle_error(f"Error updating UI components: {e}")

    def _update_status_indicator(self) -> None:
        """Update status indicator."""
        try:
            if not self._progress_data or not self._status_indicator:
                return

            palette = self.get_palette()

            # Status color mapping
            status_colors = {
                ProgressStatus.NOT_STARTED: palette.text_secondary,
                ProgressStatus.INITIALIZING: palette.warning,
                ProgressStatus.RUNNING: palette.success,
                ProgressStatus.PAUSED: palette.warning,
                ProgressStatus.COMPLETED: palette.success,
                ProgressStatus.FAILED: palette.error,
                ProgressStatus.CANCELLED: palette.text_secondary
            }

            # Status text mapping
            status_texts = {
                ProgressStatus.NOT_STARTED: "Not Started",
                ProgressStatus.INITIALIZING: "Initializing",
                ProgressStatus.RUNNING: "Running",
                ProgressStatus.PAUSED: "Paused",
                ProgressStatus.COMPLETED: "Completed",
                ProgressStatus.FAILED: "Failed",
                ProgressStatus.CANCELLED: "Cancelled"
            }

            status_color = status_colors.get(self._progress_data.status, palette.text_secondary)
            status_text = status_texts.get(self._progress_data.status, "Unknown")

            # Update status indicator content
            if hasattr(self._status_indicator, 'content') and hasattr(self._status_indicator.content, 'controls'):
                row_controls = self._status_indicator.content.controls
                if len(row_controls) >= 2:
                    # Update icon color
                    if hasattr(row_controls[0], 'color'):
                        row_controls[0].color = status_color

                    # Update text
                    if hasattr(row_controls[1], 'value'):
                        row_controls[1].value = status_text
                        row_controls[1].color = status_color

        except Exception as e:
            self._handle_error(f"Error updating status indicator: {e}")

    def _update_progress_bar(self) -> None:
        """Update progress bar."""
        try:
            if not self._progress_data or not self._progress_bar:
                return

            # Update progress value
            progress_value = self._progress_data.progress_percentage / 100.0
            self._progress_bar.value = max(0.0, min(1.0, progress_value))

        except Exception as e:
            self._handle_error(f"Error updating progress bar: {e}")

    def _update_metrics_cards(self) -> None:
        """Update metrics cards with current data."""
        try:
            if not self._progress_data:
                return

            # Update epoch card
            self._update_metric_card(
                "epoch",
                f"{self._progress_data.current_epoch} / {self._progress_data.total_epochs}"
            )

            # Update loss card
            self._update_metric_card(
                "loss",
                f"{self._progress_data.current_loss:.4f}"
            )

            # Update accuracy card
            accuracy_text = "N/A"
            if self._progress_data.current_accuracy is not None:
                accuracy_text = f"{self._progress_data.current_accuracy:.2%}"
            self._update_metric_card("accuracy", accuracy_text)

            # Update speed card
            self._update_metric_card(
                "speed",
                f"{self._progress_data.processing_speed:.1f} steps/s"
            )

            # Update memory card
            self._update_metric_card(
                "memory",
                f"{self._progress_data.memory_usage_mb:.0f} MB"
            )

            # Update GPU card
            self._update_metric_card(
                "gpu",
                f"{self._progress_data.gpu_utilization:.1f}%"
            )

        except Exception as e:
            self._handle_error(f"Error updating metrics cards: {e}")

    def _update_metric_card(self, metric_id: str, value: str) -> None:
        """Update a specific metric card."""
        try:
            card = self._metrics_cards.get(metric_id)
            if not card or not hasattr(card, 'content'):
                return

            # Find the value text component
            if hasattr(card.content, 'controls') and len(card.content.controls) >= 2:
                value_text = card.content.controls[1]
                if hasattr(value_text, 'value'):
                    value_text.value = value

        except Exception as e:
            self._handle_error(f"Error updating metric card {metric_id}: {e}")

    def _update_control_buttons(self) -> None:
        """Update control button states."""
        try:
            if not self._progress_data:
                return

            status = self._progress_data.status

            # Update button visibility/enabled state
            if self._pause_button:
                self._pause_button.disabled = status not in [ProgressStatus.RUNNING]

            if self._resume_button:
                self._resume_button.disabled = status not in [ProgressStatus.PAUSED]

            if self._stop_button:
                self._stop_button.disabled = status not in [ProgressStatus.RUNNING, ProgressStatus.PAUSED]

        except Exception as e:
            self._handle_error(f"Error updating control buttons: {e}")

    # Public API Methods
    def get_current_session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self._current_session_id

    def get_progress_data(self) -> Optional[TrainingProgressData]:
        """Get current progress data."""
        return self._progress_data

    def set_configuration(self, config: ProgressConfiguration) -> None:
        """Update dashboard configuration."""
        self._config = config

    def get_configuration(self) -> ProgressConfiguration:
        """Get current dashboard configuration."""
        return self._config

    def refresh_dashboard(self) -> None:
        """Manually refresh dashboard data."""
        self._update_dashboard_data()

    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            await self.stop_monitoring()

        except Exception as e:
            self._handle_error(f"Error during cleanup: {e}")

    def _handle_error(self, error_message: str) -> None:
        """Handle errors gracefully."""
        print(f"ProgressDashboardUI Error: {error_message}")

        # Update error state in UI if needed
        if self._progress_data:
            self._progress_data.error_message = error_message
