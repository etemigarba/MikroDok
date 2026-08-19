"""
Module: training_progress_ui
Description: Streamlined training progress visualization interface for model builder workflow.
            Provides real-time training progress display with loss curves, metrics tracking, and
            time estimates. Designed specifically for the model building process with responsive
            design, theme integration, and seamless integration with training controls.
Phase: 4
Location: /src/modules/ui/model_builder_ui/training_progress_ui/training_progress_ui.py
"""

# Standard library imports
import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field

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


class ProgressDisplayMode(Enum):
    """Training progress display modes."""
    COMPACT = "compact"
    DETAILED = "detailed"
    MINIMAL = "minimal"


class ProgressStatus(Enum):
    """Training progress status."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressMetrics:
    """Training progress metrics."""
    current_loss: float = 0.0
    best_loss: float = float('inf')
    current_accuracy: Optional[float] = None
    best_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    batch_size: int = 32
    memory_usage_mb: float = 0.0
    gpu_utilization: float = 0.0
    processing_speed: float = 0.0  # steps per second
    gradient_norm: Optional[float] = None
    validation_loss: Optional[float] = None
    validation_accuracy: Optional[float] = None


@dataclass
class TrainingProgressConfig:
    """Configuration for training progress display."""
    display_mode: ProgressDisplayMode = ProgressDisplayMode.DETAILED
    refresh_interval_seconds: float = 1.0
    show_loss_chart: bool = True
    show_accuracy_chart: bool = True
    show_metrics: bool = True
    show_time_estimates: bool = True
    show_resource_usage: bool = True
    enable_animations: bool = True
    compact_threshold_width: int = 600
    chart_history_points: int = 100
    auto_scale_charts: bool = True


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
    metrics: ProgressMetrics = field(default_factory=ProgressMetrics)
    last_updated: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    checkpoint_count: int = 0
    last_checkpoint_time: Optional[datetime] = None


class TrainingProgressUI(ThemeAwareUserControl):
    """
    Streamlined training progress visualization interface for model builder workflow.

    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time training progress display with loss curves
    - Metrics tracking (loss, accuracy, learning rate, etc.)
    - Time estimates and completion predictions
    - Resource usage monitoring (memory, GPU utilization)
    - Theme-aware styling with accessibility compliance
    - Multiple display modes (compact, detailed, minimal)
    - Integration with training controls and orchestration
    - Chart visualization for training metrics
    - Error handling and status display
    """

    def __init__(
        self,
        config: Optional[TrainingProgressConfig] = None,
        on_status_change: Optional[Callable[[ProgressStatus], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        """
        Initialize training progress UI.

        Args:
            config: Progress display configuration
            on_status_change: Callback for status changes
            on_error: Callback for error handling
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)

        # Configuration
        self._config = config or TrainingProgressConfig()
        self._on_status_change = on_status_change
        self._on_error = on_error

        # State
        self._progress_data = TrainingProgressData(
            session_id="",
            status=ProgressStatus.IDLE
        )
        self._loss_history: List[Tuple[int, float]] = []
        self._accuracy_history: List[Tuple[int, float]] = []
        self._update_timer: Optional[asyncio.Task] = None
        self._is_updating = False

        # UI Components
        self._main_container: Optional[ft.Container] = None
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._status_text: Optional[ft.Text] = None
        self._progress_text: Optional[ft.Text] = None
        self._time_text: Optional[ft.Text] = None
        self._metrics_container: Optional[ft.Container] = None
        self._loss_chart: Optional[ft.LineChart] = None
        self._accuracy_chart: Optional[ft.LineChart] = None
        self._error_banner: Optional[ft.Banner] = None

        # Logging
        self._logger = logging.getLogger(__name__)

        # Initialize UI
        self._initialize_ui()

    def _initialize_ui(self) -> None:
        """Initialize the user interface."""
        try:
            self._create_main_container()
            self._create_progress_components()
            self._create_metrics_components()
            self._create_chart_components()
            self._setup_responsive_layout()

        except Exception as ex:
            self._logger.error(f"Failed to initialize UI: {ex}")
            if self._on_error:
                self._on_error(f"UI initialization failed: {ex}")

    def _create_main_container(self) -> None:
        """Create main container with theme integration."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._main_container = ft.Container(
            content=ft.Column(
                controls=[],
                spacing=spacing.md,
                tight=True
            ),
            padding=spacing.md,
            bgcolor=palette.surface,
            border_radius=spacing.sm,
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_progress_components(self) -> None:
        """Create progress display components."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Status indicator with icon
        self._status_text = ft.Text(
            value="Ready to start training",
            style=typography.body_medium,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        # Progress bar
        self._progress_bar = ft.ProgressBar(
            value=0.0,
            color=palette.primary,
            bgcolor=palette.surface_variant,
            height=spacing.xs
        )

        # Progress text (epochs/steps)
        self._progress_text = ft.Text(
            value="0% (0/0 epochs, 0/0 steps)",
            style=typography.body_small,
            color=palette.text_secondary
        )

        # Time estimates
        if self._config.show_time_estimates:
            self._time_text = ft.Text(
                value="Elapsed: 00:00:00 | Remaining: --:--:--",
                style=typography.body_small,
                color=palette.text_secondary
            )

        # Error banner
        self._error_banner = ft.Banner(
            bgcolor=palette.error_container,
            leading=ft.Icon(icons.error, color=palette.error),
            content=ft.Text("", color=palette.on_error_container),
            actions=[
                ft.TextButton(
                    "Dismiss",
                    on_click=self._dismiss_error
                )
            ]
        )

    def _create_metrics_components(self) -> None:
        """Create metrics display components."""
        if not self._config.show_metrics:
            return

        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Metrics grid
        metrics_controls = []

        # Loss metrics
        loss_card = self._create_metric_card(
            "Loss",
            "0.000",
            "Best: ∞",
            palette.error
        )
        metrics_controls.append(loss_card)

        # Accuracy metrics (if available)
        accuracy_card = self._create_metric_card(
            "Accuracy",
            "--",
            "Best: --",
            palette.primary
        )
        metrics_controls.append(accuracy_card)

        # Learning rate
        lr_card = self._create_metric_card(
            "Learning Rate",
            "0.001",
            "",
            palette.secondary
        )
        metrics_controls.append(lr_card)

        # Resource usage (if enabled)
        if self._config.show_resource_usage:
            memory_card = self._create_metric_card(
                "Memory",
                "0 MB",
                "",
                palette.tertiary
            )
            metrics_controls.append(memory_card)

        self._metrics_container = ft.Container(
            content=ft.ResponsiveRow(
                controls=metrics_controls,
                spacing=spacing.sm
            ),
            padding=ft.padding.symmetric(vertical=spacing.sm)
        )

    def _create_metric_card(
        self,
        title: str,
        value: str,
        subtitle: str,
        accent_color: str
    ) -> ft.Container:
        """Create a metric display card."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title,
                        style=typography.label_small,
                        color=palette.text_secondary
                    ),
                    ft.Text(
                        value,
                        style=typography.title_medium,
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_600
                    ),
                    ft.Text(
                        subtitle,
                        style=typography.label_small,
                        color=accent_color
                    ) if subtitle else ft.Container()
                ],
                spacing=spacing.xs,
                tight=True
            ),
            padding=spacing.sm,
            bgcolor=palette.surface_variant,
            border_radius=spacing.xs,
            border=ft.border.all(1, accent_color, opacity=0.3),
            col={"xs": 12, "sm": 6, "md": 3}
        )

    def _create_chart_components(self) -> None:
        """Create chart visualization components."""
        if not (self._config.show_loss_chart or self._config.show_accuracy_chart):
            return

        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Loss chart
        if self._config.show_loss_chart:
            self._loss_chart = ft.LineChart(
                data_series=[
                    ft.LineChartData(
                        data_points=[],
                        stroke_width=2,
                        color=palette.error,
                        curved=True,
                        stroke_cap_round=True
                    )
                ],
                border=ft.border.all(1, palette.outline_variant),
                horizontal_grid_lines=ft.ChartGridLines(
                    color=palette.outline_variant,
                    width=1,
                    dash_pattern=[5, 5]
                ),
                vertical_grid_lines=ft.ChartGridLines(
                    color=palette.outline_variant,
                    width=1,
                    dash_pattern=[5, 5]
                ),
                left_axis=ft.ChartAxis(
                    title=ft.Text("Loss", style=typography.label_small),
                    title_size=40,
                    labels_size=30
                ),
                bottom_axis=ft.ChartAxis(
                    title=ft.Text("Epoch", style=typography.label_small),
                    title_size=40,
                    labels_size=30
                ),
                tooltip_bgcolor=palette.surface_variant,
                min_y=0,
                max_y=1,
                min_x=0,
                max_x=100
            )

        # Accuracy chart
        if self._config.show_accuracy_chart:
            self._accuracy_chart = ft.LineChart(
                data_series=[
                    ft.LineChartData(
                        data_points=[],
                        stroke_width=2,
                        color=palette.primary,
                        curved=True,
                        stroke_cap_round=True
                    )
                ],
                border=ft.border.all(1, palette.outline_variant),
                horizontal_grid_lines=ft.ChartGridLines(
                    color=palette.outline_variant,
                    width=1,
                    dash_pattern=[5, 5]
                ),
                vertical_grid_lines=ft.ChartGridLines(
                    color=palette.outline_variant,
                    width=1,
                    dash_pattern=[5, 5]
                ),
                left_axis=ft.ChartAxis(
                    title=ft.Text("Accuracy", style=typography.label_small),
                    title_size=40,
                    labels_size=30
                ),
                bottom_axis=ft.ChartAxis(
                    title=ft.Text("Epoch", style=typography.label_small),
                    title_size=40,
                    labels_size=30
                ),
                tooltip_bgcolor=palette.surface_variant,
                min_y=0,
                max_y=1,
                min_x=0,
                max_x=100
            )

    def _setup_responsive_layout(self) -> None:
        """Setup responsive layout based on display mode."""
        if not self._main_container:
            return

        layout_manager = self.get_layout_manager()
        current_breakpoint = layout_manager.get_current_breakpoint()

        # Determine display mode based on screen size
        if current_breakpoint in ["xs", "sm"] or self._config.display_mode == ProgressDisplayMode.COMPACT:
            self._setup_compact_layout()
        elif self._config.display_mode == ProgressDisplayMode.MINIMAL:
            self._setup_minimal_layout()
        else:
            self._setup_detailed_layout()

    def _setup_compact_layout(self) -> None:
        """Setup compact layout for small screens."""
        controls = []

        # Status and progress
        controls.append(self._status_text)
        controls.append(self._progress_bar)
        controls.append(self._progress_text)

        if self._time_text and self._config.show_time_estimates:
            controls.append(self._time_text)

        # Essential metrics only
        if self._config.show_metrics:
            essential_metrics = ft.ResponsiveRow(
                controls=[
                    self._create_metric_card("Loss", "0.000", "", self.get_palette().error),
                    self._create_metric_card("Progress", "0%", "", self.get_palette().primary)
                ]
            )
            controls.append(essential_metrics)

        self._main_container.content.controls = controls

    def _setup_minimal_layout(self) -> None:
        """Setup minimal layout with just essential information."""
        controls = [
            self._progress_bar,
            self._progress_text
        ]

        self._main_container.content.controls = controls

    def _setup_detailed_layout(self) -> None:
        """Setup detailed layout with all components."""
        controls = []

        # Header with status
        controls.append(self._status_text)

        # Progress section
        progress_section = ft.Column(
            controls=[
                self._progress_bar,
                self._progress_text
            ],
            spacing=self.get_spacing().xs
        )
        controls.append(progress_section)

        # Time estimates
        if self._time_text and self._config.show_time_estimates:
            controls.append(self._time_text)

        # Metrics
        if self._metrics_container and self._config.show_metrics:
            controls.append(self._metrics_container)

        # Charts
        if self._config.show_loss_chart or self._config.show_accuracy_chart:
            chart_controls = []

            if self._loss_chart:
                chart_controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Training Loss", style=self.get_typography().title_small),
                                ft.Container(
                                    content=self._loss_chart,
                                    height=200
                                )
                            ]
                        ),
                        col={"xs": 12, "md": 6}
                    )
                )

            if self._accuracy_chart:
                chart_controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Training Accuracy", style=self.get_typography().title_small),
                                ft.Container(
                                    content=self._accuracy_chart,
                                    height=200
                                )
                            ]
                        ),
                        col={"xs": 12, "md": 6}
                    )
                )

            if chart_controls:
                charts_row = ft.ResponsiveRow(controls=chart_controls)
                controls.append(charts_row)

        self._main_container.content.controls = controls

    def build(self) -> ft.Control:
        """Build the training progress UI component."""
        return self._main_container

    # Public API Methods

    def update_progress(self, progress_data: TrainingProgressData) -> None:
        """
        Update training progress data.

        Args:
            progress_data: New progress data
        """
        try:
            self._progress_data = progress_data
            self._update_displays()
            self._update_charts()

            # Handle status changes
            if self._on_status_change:
                self._on_status_change(progress_data.status)

        except Exception as ex:
            self._logger.error(f"Failed to update progress: {ex}")
            if self._on_error:
                self._on_error(f"Progress update failed: {ex}")

    def set_display_mode(self, mode: ProgressDisplayMode) -> None:
        """
        Set display mode.

        Args:
            mode: New display mode
        """
        try:
            self._config.display_mode = mode
            self._setup_responsive_layout()
            self._update_ui()

        except Exception as ex:
            self._logger.error(f"Failed to set display mode: {ex}")

    def start_auto_update(self) -> None:
        """Start automatic progress updates."""
        try:
            if self._update_timer and not self._update_timer.done():
                return

            self._update_timer = asyncio.create_task(self._auto_update_loop())

        except Exception as ex:
            self._logger.error(f"Failed to start auto update: {ex}")

    def stop_auto_update(self) -> None:
        """Stop automatic progress updates."""
        try:
            if self._update_timer and not self._update_timer.done():
                self._update_timer.cancel()
                self._update_timer = None

        except Exception as ex:
            self._logger.error(f"Failed to stop auto update: {ex}")

    def show_error(self, message: str) -> None:
        """
        Show error message.

        Args:
            message: Error message to display
        """
        try:
            if self._error_banner:
                self._error_banner.content.value = message
                self._error_banner.open = True
                self._update_ui()

        except Exception as ex:
            self._logger.error(f"Failed to show error: {ex}")

    def clear_error(self) -> None:
        """Clear error message."""
        try:
            if self._error_banner:
                self._error_banner.open = False
                self._update_ui()

        except Exception as ex:
            self._logger.error(f"Failed to clear error: {ex}")

    def reset_progress(self) -> None:
        """Reset progress to initial state."""
        try:
            self._progress_data = TrainingProgressData(
                session_id="",
                status=ProgressStatus.IDLE
            )
            self._loss_history.clear()
            self._accuracy_history.clear()
            self._update_displays()
            self._update_charts()

        except Exception as ex:
            self._logger.error(f"Failed to reset progress: {ex}")

    # Private Methods

    async def _auto_update_loop(self) -> None:
        """Automatic update loop for real-time progress."""
        try:
            while not self._update_timer.cancelled():
                if not self._is_updating:
                    self._is_updating = True
                    try:
                        self._update_displays()
                        self._update_charts()
                    finally:
                        self._is_updating = False

                await asyncio.sleep(self._config.refresh_interval_seconds)

        except asyncio.CancelledError:
            pass
        except Exception as ex:
            self._logger.error(f"Auto update loop error: {ex}")

    def _update_displays(self) -> None:
        """Update all display components."""
        try:
            self._update_status_display()
            self._update_progress_display()
            self._update_time_display()
            self._update_metrics_display()
            self._update_ui()

        except Exception as ex:
            self._logger.error(f"Failed to update displays: {ex}")

    def _update_status_display(self) -> None:
        """Update status display."""
        if not self._status_text:
            return

        status_messages = {
            ProgressStatus.IDLE: "Ready to start training",
            ProgressStatus.INITIALIZING: "Initializing training...",
            ProgressStatus.RUNNING: "Training in progress",
            ProgressStatus.PAUSED: "Training paused",
            ProgressStatus.COMPLETED: "Training completed successfully",
            ProgressStatus.FAILED: "Training failed",
            ProgressStatus.CANCELLED: "Training cancelled"
        }

        self._status_text.value = status_messages.get(
            self._progress_data.status,
            "Unknown status"
        )

        # Update color based on status
        palette = self.get_palette()
        status_colors = {
            ProgressStatus.IDLE: palette.text_secondary,
            ProgressStatus.INITIALIZING: palette.primary,
            ProgressStatus.RUNNING: palette.primary,
            ProgressStatus.PAUSED: palette.warning,
            ProgressStatus.COMPLETED: palette.success,
            ProgressStatus.FAILED: palette.error,
            ProgressStatus.CANCELLED: palette.text_secondary
        }

        self._status_text.color = status_colors.get(
            self._progress_data.status,
            palette.text_primary
        )

    def _update_progress_display(self) -> None:
        """Update progress display."""
        if not self._progress_bar or not self._progress_text:
            return

        progress = self._progress_data

        # Update progress bar
        self._progress_bar.value = progress.progress_percentage / 100.0

        # Update progress text
        self._progress_text.value = (
            f"{progress.progress_percentage:.1f}% "
            f"({progress.current_epoch}/{progress.total_epochs} epochs, "
            f"{progress.current_step}/{progress.total_steps} steps)"
        )

    def _update_time_display(self) -> None:
        """Update time display."""
        if not self._time_text or not self._config.show_time_estimates:
            return

        progress = self._progress_data

        # Format elapsed time
        elapsed_str = self._format_timedelta(progress.elapsed_time)

        # Format remaining time
        if progress.estimated_remaining:
            remaining_str = self._format_timedelta(progress.estimated_remaining)
        else:
            remaining_str = "--:--:--"

        self._time_text.value = f"Elapsed: {elapsed_str} | Remaining: {remaining_str}"

    def _update_metrics_display(self) -> None:
        """Update metrics display."""
        if not self._metrics_container or not self._config.show_metrics:
            return

        # This would update the metric cards with current values
        # Implementation depends on how metric cards are structured
        pass

    def _update_charts(self) -> None:
        """Update chart data."""
        try:
            progress = self._progress_data

            # Update loss history
            if self._loss_chart and progress.metrics.current_loss > 0:
                self._loss_history.append((progress.current_epoch, progress.metrics.current_loss))

                # Limit history size
                if len(self._loss_history) > self._config.chart_history_points:
                    self._loss_history = self._loss_history[-self._config.chart_history_points:]

                # Update chart data
                data_points = [
                    ft.LineChartDataPoint(x=epoch, y=loss)
                    for epoch, loss in self._loss_history
                ]

                if self._loss_chart.data_series:
                    self._loss_chart.data_series[0].data_points = data_points

                # Auto-scale if enabled
                if self._config.auto_scale_charts and self._loss_history:
                    min_loss = min(loss for _, loss in self._loss_history)
                    max_loss = max(loss for _, loss in self._loss_history)
                    self._loss_chart.min_y = max(0, min_loss * 0.9)
                    self._loss_chart.max_y = max_loss * 1.1

            # Update accuracy history
            if (self._accuracy_chart and
                progress.metrics.current_accuracy is not None and
                progress.metrics.current_accuracy > 0):

                self._accuracy_history.append((progress.current_epoch, progress.metrics.current_accuracy))

                # Limit history size
                if len(self._accuracy_history) > self._config.chart_history_points:
                    self._accuracy_history = self._accuracy_history[-self._config.chart_history_points:]

                # Update chart data
                data_points = [
                    ft.LineChartDataPoint(x=epoch, y=acc)
                    for epoch, acc in self._accuracy_history
                ]

                if self._accuracy_chart.data_series:
                    self._accuracy_chart.data_series[0].data_points = data_points

                # Auto-scale if enabled
                if self._config.auto_scale_charts and self._accuracy_history:
                    min_acc = min(acc for _, acc in self._accuracy_history)
                    max_acc = max(acc for _, acc in self._accuracy_history)
                    self._accuracy_chart.min_y = max(0, min_acc * 0.9)
                    self._accuracy_chart.max_y = min(1, max_acc * 1.1)

        except Exception as ex:
            self._logger.error(f"Failed to update charts: {ex}")

    def _format_timedelta(self, td: timedelta) -> str:
        """
        Format timedelta as HH:MM:SS.

        Args:
            td: Timedelta to format

        Returns:
            Formatted time string
        """
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _dismiss_error(self, e: ft.ControlEvent) -> None:
        """Dismiss error banner."""
        self.clear_error()

    def _update_ui(self) -> None:
        """Update the UI."""
        try:
            if hasattr(self, 'page') and self.page:
                self.page.update()
        except Exception as ex:
            self._logger.error(f"Failed to update UI: {ex}")

    # Theme Integration Methods

    def on_theme_changed(self) -> None:
        """Handle theme changes."""
        try:
            # Recreate components with new theme
            self._create_progress_components()
            self._create_metrics_components()
            self._create_chart_components()
            self._setup_responsive_layout()
            self._update_ui()

        except Exception as ex:
            self._logger.error(f"Failed to handle theme change: {ex}")

    # Cleanup Methods

    def dispose(self) -> None:
        """Cleanup resources."""
        try:
            self.stop_auto_update()

        except Exception as ex:
            self._logger.error(f"Failed to dispose: {ex}")

    def __del__(self):
        """Destructor."""
        try:
            self.dispose()
        except:
            pass
