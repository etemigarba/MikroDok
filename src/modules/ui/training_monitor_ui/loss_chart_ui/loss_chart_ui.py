"""
Module: loss_chart_ui
Description: Real-time loss curve visualization with interactive charts for training monitoring.
            Provides comprehensive loss tracking with multiple chart types, time range selection,
            zoom/pan controls, and theme-aware visualization components for long training sessions.
Phase: 4
Location: /src/modules/ui/training_monitor_ui/loss_chart_ui/loss_chart_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import math
import threading
from collections import deque

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl


class LossType(Enum):
    """Loss type enumeration for different loss categories."""
    TRAINING = "training"
    VALIDATION = "validation"
    TEST = "test"
    COMBINED = "combined"


class ChartViewMode(Enum):
    """Chart view mode enumeration."""
    REAL_TIME = "real_time"
    HISTORICAL = "historical"
    COMPARISON = "comparison"
    DETAILED = "detailed"


class ChartTimeRange(Enum):
    """Time range enumeration for chart display."""
    LAST_HOUR = "last_hour"
    LAST_6_HOURS = "last_6_hours"
    LAST_24_HOURS = "last_24_hours"
    ALL_TIME = "all_time"
    CUSTOM = "custom"


@dataclass
class LossDataPoint:
    """Data structure for individual loss data points."""
    timestamp: datetime
    epoch: int
    step: int
    loss_value: float
    loss_type: LossType
    learning_rate: Optional[float] = None
    gradient_norm: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LossChartData:
    """Container for loss chart data with efficient storage."""
    training_losses: deque = field(default_factory=lambda: deque(maxlen=10000))
    validation_losses: deque = field(default_factory=lambda: deque(maxlen=10000))
    test_losses: deque = field(default_factory=lambda: deque(maxlen=1000))
    max_points: int = 10000
    
    def add_data_point(self, data_point: LossDataPoint) -> None:
        """Add a new data point to the appropriate loss collection."""
        if data_point.loss_type == LossType.TRAINING:
            self.training_losses.append(data_point)
        elif data_point.loss_type == LossType.VALIDATION:
            self.validation_losses.append(data_point)
        elif data_point.loss_type == LossType.TEST:
            self.test_losses.append(data_point)
    
    def get_data_points(self, loss_type: LossType, 
                       time_range: Optional[ChartTimeRange] = None) -> List[LossDataPoint]:
        """Get data points for specified loss type and time range."""
        if loss_type == LossType.TRAINING:
            data = list(self.training_losses)
        elif loss_type == LossType.VALIDATION:
            data = list(self.validation_losses)
        elif loss_type == LossType.TEST:
            data = list(self.test_losses)
        else:
            return []
        
        if time_range and time_range != ChartTimeRange.ALL_TIME:
            cutoff_time = self._get_cutoff_time(time_range)
            data = [dp for dp in data if dp.timestamp >= cutoff_time]
        
        return data
    
    def _get_cutoff_time(self, time_range: ChartTimeRange) -> datetime:
        """Get cutoff time for time range filtering."""
        now = datetime.now()
        if time_range == ChartTimeRange.LAST_HOUR:
            return now - timedelta(hours=1)
        elif time_range == ChartTimeRange.LAST_6_HOURS:
            return now - timedelta(hours=6)
        elif time_range == ChartTimeRange.LAST_24_HOURS:
            return now - timedelta(hours=24)
        return now


@dataclass
class LossChartConfig:
    """Configuration for loss chart display and behavior."""
    # Chart appearance
    show_training_loss: bool = True
    show_validation_loss: bool = True
    show_test_loss: bool = False
    show_grid: bool = True
    show_legend: bool = True
    show_tooltips: bool = True
    
    # Chart behavior
    auto_scale: bool = True
    smooth_curves: bool = True
    real_time_updates: bool = True
    update_interval_ms: int = 1000
    
    # Data management
    max_data_points: int = 10000
    data_compression: bool = True
    
    # Export options
    enable_export: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["PNG", "SVG", "CSV"])
    
    # Performance
    enable_data_buffering: bool = True
    buffer_size: int = 100
    enable_lazy_loading: bool = True


class LossChartUI(ThemeAwareUserControl):
    """
    Real-time loss curve visualization UI component.

    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time loss visualization with interactive charts
    - Multiple loss type support (training, validation, test)
    - Time range selection and zoom/pan controls
    - Theme-aware styling with accessibility compliance
    - Performance optimization for long training sessions
    - Export functionality and data management
    - Interactive tooltips and legend
    - Smooth curve rendering with configurable updates
    - Memory-efficient data buffering and compression
    """

    def __init__(self,
                 config: Optional[LossChartConfig] = None,
                 on_data_point_click: Optional[Callable[[LossDataPoint], None]] = None,
                 on_time_range_change: Optional[Callable[[ChartTimeRange], None]] = None,
                 on_export_request: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize loss chart UI component.

        Args:
            config: Chart configuration settings
            on_data_point_click: Callback for data point click events
            on_time_range_change: Callback for time range changes
            on_export_request: Callback for export requests
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)

        # Configuration and callbacks
        self._config = config or LossChartConfig()
        self._on_data_point_click = on_data_point_click
        self._on_time_range_change = on_time_range_change
        self._on_export_request = on_export_request

        # Data management
        self._chart_data = LossChartData()
        self._current_view_mode = ChartViewMode.REAL_TIME
        self._current_time_range = ChartTimeRange.ALL_TIME
        self._data_lock = threading.Lock()

        # UI components
        self._chart_container = None
        self._loss_chart = None
        self._control_panel = None
        self._legend_panel = None
        self._status_bar = None

        # Chart state
        self._is_paused = False
        self._zoom_level = 1.0
        self._pan_offset = 0.0
        self._last_update_time = datetime.now()

        # Performance tracking
        self._update_timer = None
        self._pending_updates = []
        self._chart_bounds = {"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 1}

    def build(self) -> ft.Control:
        """Build the loss chart UI component."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Main container with responsive layout
        return ft.Container(
            content=ft.Column([
                self._create_header_section(),
                self._create_chart_section(),
                self._create_control_section()
            ], spacing=spacing.sm, expand=True),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(8, 10, 12, 14)),
            border=ft.border.all(1, palette.borders),
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_header_section(self) -> ft.Control:
        """Create header section with title and quick controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Title and status
        title_section = ft.Row([
            ft.Icon(
                name=self.get_icon('SHOW_CHART'),
                color=palette.primary,
                size=rlm.get_breakpoint_value(20, 22, 24, 26)
            ),
            ft.Text(
                "Training Loss",
                style=self.get_text_style('h4'),
                color=palette.text_primary
            ),
            ft.Container(expand=True),
            self._create_status_indicator()
        ], alignment=ft.MainAxisAlignment.START)

        # Quick controls
        quick_controls = ft.Row([
            self._create_view_mode_selector(),
            self._create_time_range_selector(),
            self._create_action_buttons()
        ], spacing=spacing.sm)

        return ft.Container(
            content=ft.Column([
                title_section,
                quick_controls
            ], spacing=spacing.xs),
            padding=ft.padding.only(bottom=spacing.sm)
        )

    def _create_status_indicator(self) -> ft.Control:
        """Create status indicator showing chart state."""
        palette = self.get_palette()

        status_color = palette.success if not self._is_paused else palette.warning
        status_text = "Live" if not self._is_paused else "Paused"

        return ft.Container(
            content=ft.Row([
                ft.Container(
                    width=self.get_responsive_layout().get_breakpoint_value(6, 7, 8, 9),
                    height=self.get_responsive_layout().get_breakpoint_value(6, 7, 8, 9),
                    bgcolor=status_color,
                    border_radius=ft.border_radius.all(self.get_responsive_layout().get_breakpoint_value(3, 3, 4, 4))
                ),
                ft.Text(
                    status_text,
                    style=self.get_text_style('caption'),
                    color=status_color
                )
            ], spacing=4),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            bgcolor=f"{status_color}20",
            border_radius=ft.border_radius.all(12)
        )

    def _create_view_mode_selector(self) -> ft.Control:
        """Create view mode selector dropdown."""
        palette = self.get_palette()

        return ft.Dropdown(
            value=self._current_view_mode.value,
            options=[
                ft.dropdown.Option(ChartViewMode.REAL_TIME.value, "Real-time"),
                ft.dropdown.Option(ChartViewMode.HISTORICAL.value, "Historical"),
                ft.dropdown.Option(ChartViewMode.COMPARISON.value, "Comparison"),
                ft.dropdown.Option(ChartViewMode.DETAILED.value, "Detailed")
            ],
            on_change=self._on_view_mode_change,
            width=self.get_responsive_layout().get_breakpoint_value(100, 110, 120, 130),
            height=self.get_responsive_layout().get_breakpoint_value(32, 34, 36, 38),
            text_style=self.get_text_style('body_small'),
            border_color=palette.borders
        )

    def _create_time_range_selector(self) -> ft.Control:
        """Create time range selector dropdown."""
        palette = self.get_palette()

        return ft.Dropdown(
            value=self._current_time_range.value,
            options=[
                ft.dropdown.Option(ChartTimeRange.LAST_HOUR.value, "Last Hour"),
                ft.dropdown.Option(ChartTimeRange.LAST_6_HOURS.value, "Last 6 Hours"),
                ft.dropdown.Option(ChartTimeRange.LAST_24_HOURS.value, "Last 24 Hours"),
                ft.dropdown.Option(ChartTimeRange.ALL_TIME.value, "All Time"),
                ft.dropdown.Option(ChartTimeRange.CUSTOM.value, "Custom")
            ],
            on_change=self._on_time_range_change_internal,
            width=self.get_responsive_layout().get_breakpoint_value(120, 130, 140, 150),
            height=self.get_responsive_layout().get_breakpoint_value(32, 34, 36, 38),
            text_style=self.get_text_style('body_small'),
            border_color=palette.borders
        )

    def _create_action_buttons(self) -> ft.Control:
        """Create action buttons for chart controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Row([
            ft.IconButton(
                icon=self.get_icon('PAUSE') if not self._is_paused else self.get_icon('PLAY'),
                tooltip="Pause/Resume updates",
                on_click=self._toggle_pause,
                icon_color=palette.text_secondary,
                icon_size=20
            ),
            ft.IconButton(
                icon=self.get_icon('REFRESH'),
                tooltip="Reset zoom",
                on_click=self._reset_zoom,
                icon_color=palette.text_secondary,
                icon_size=20
            ),
            ft.IconButton(
                icon=self.get_icon('DOWNLOAD'),
                tooltip="Export chart",
                on_click=self._show_export_dialog,
                icon_color=palette.text_secondary,
                icon_size=20
            )
        ], spacing=spacing.xs)

    def _create_chart_section(self) -> ft.Control:
        """Create main chart section with loss visualization."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Chart container with responsive height
        chart_height = rlm.get_breakpoint_value(300, 350, 400, 450)

        self._chart_container = ft.Container(
            content=self._create_loss_chart(),
            height=chart_height,
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders),
            padding=ft.padding.all(spacing.sm)
        )

        # Legend panel
        self._legend_panel = self._create_legend_panel()

        return ft.Column([
            self._chart_container,
            self._legend_panel if self._config.show_legend else ft.Container()
        ], spacing=spacing.sm)

    def _create_loss_chart(self) -> ft.Control:
        """Create the main loss chart with line visualization."""
        palette = self.get_palette()
        rlm = self.get_responsive_layout()

        # Chart styling based on breakpoint
        stroke_width = rlm.get_breakpoint_value(2, 2, 3, 3)

        # Create line chart data series
        data_series = []

        # Training loss series
        if self._config.show_training_loss:
            training_series = ft.LineChartData(
                data_points=[],
                stroke_width=stroke_width,
                color=palette.primary,
                curved=self._config.smooth_curves,
                stroke_cap_round=True,
                below_line_bgcolor=f"{palette.primary}20" if self._current_view_mode == ChartViewMode.REAL_TIME else None
            )
            data_series.append(training_series)

        # Validation loss series
        if self._config.show_validation_loss:
            validation_series = ft.LineChartData(
                data_points=[],
                stroke_width=stroke_width,
                color=palette.secondary,
                curved=self._config.smooth_curves,
                stroke_cap_round=True,
                below_line_bgcolor=f"{palette.secondary}20" if self._current_view_mode == ChartViewMode.REAL_TIME else None
            )
            data_series.append(validation_series)

        # Test loss series
        if self._config.show_test_loss:
            test_series = ft.LineChartData(
                data_points=[],
                stroke_width=stroke_width,
                color=palette.info,
                curved=self._config.smooth_curves,
                stroke_cap_round=True
            )
            data_series.append(test_series)

        # Create line chart
        self._loss_chart = ft.LineChart(
            data_series=data_series,
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5] if self._config.show_grid else None
            ) if self._config.show_grid else None,
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5] if self._config.show_grid else None
            ) if self._config.show_grid else None,
            left_axis=ft.ChartAxis(
                title=ft.Text(
                    "Loss Value",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                ),
                title_size=40,
                labels_size=40
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text(
                    "Training Steps" if self._current_view_mode == ChartViewMode.REAL_TIME else "Time",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                ),
                title_size=40,
                labels_size=40
            ),
            tooltip_bgcolor=palette.surface,
            expand=True
        )

        return self._loss_chart

    def _create_legend_panel(self) -> ft.Control:
        """Create legend panel showing loss types and colors."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        legend_items = []

        if self._config.show_training_loss:
            legend_items.append(self._create_legend_item("Training Loss", palette.primary))

        if self._config.show_validation_loss:
            legend_items.append(self._create_legend_item("Validation Loss", palette.secondary))

        if self._config.show_test_loss:
            legend_items.append(self._create_legend_item("Test Loss", palette.info))

        return ft.Container(
            content=ft.Row(
                controls=legend_items,
                spacing=spacing.md,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=ft.padding.symmetric(vertical=spacing.sm)
        )

    def _create_legend_item(self, label: str, color: str) -> ft.Control:
        """Create individual legend item."""
        spacing = self.get_spacing()

        return ft.Row([
            ft.Container(
                width=self.get_responsive_layout().get_breakpoint_value(12, 14, 16, 18),
                height=self.get_responsive_layout().get_breakpoint_value(2, 2, 3, 3),
                bgcolor=color,
                border_radius=ft.border_radius.all(self.get_responsive_layout().get_breakpoint_value(1, 1, 2, 2))
            ),
            ft.Text(
                label,
                style=self.get_text_style('body_small'),
                color=self.get_palette().text_secondary
            )
        ], spacing=spacing.xs)

    def _create_control_section(self) -> ft.Control:
        """Create control section with chart options."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Chart options
        options_row = ft.Row([
            ft.Checkbox(
                label="Show Grid",
                value=self._config.show_grid,
                on_change=self._on_grid_toggle,
                label_style=self.get_text_style('body_small')
            ),
            ft.Checkbox(
                label="Smooth Curves",
                value=self._config.smooth_curves,
                on_change=self._on_smooth_toggle,
                label_style=self.get_text_style('body_small')
            ),
            ft.Checkbox(
                label="Auto Scale",
                value=self._config.auto_scale,
                on_change=self._on_auto_scale_toggle,
                label_style=self.get_text_style('body_small')
            )
        ], spacing=spacing.md)

        # Status information
        self._status_bar = ft.Container(
            content=ft.Row([
                ft.Text(
                    "Data Points: 0",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                ),
                ft.Text(
                    "Last Update: Never",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                ),
                ft.Text(
                    "Zoom: 100%",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                )
            ], spacing=spacing.md),
            padding=ft.padding.symmetric(vertical=spacing.xs)
        )

        return ft.Column([
            options_row,
            self._status_bar
        ], spacing=spacing.sm)

    # Event Handlers
    def _on_view_mode_change(self, e) -> None:
        """Handle view mode change."""
        try:
            self._current_view_mode = ChartViewMode(e.control.value)
            self._update_chart_display()
        except Exception as ex:
            print(f"Error changing view mode: {ex}")

    def _on_time_range_change_internal(self, e) -> None:
        """Handle time range change."""
        try:
            self._current_time_range = ChartTimeRange(e.control.value)
            self._update_chart_display()

            if self._on_time_range_change:
                self._on_time_range_change(self._current_time_range)
        except Exception as ex:
            print(f"Error changing time range: {ex}")

    def _toggle_pause(self, e) -> None:
        """Toggle pause/resume for real-time updates."""
        self._is_paused = not self._is_paused
        self._update_status_indicator()

        if hasattr(e.control, 'icon'):
            e.control.icon = self.get_icon('PAUSE') if not self._is_paused else self.get_icon('PLAY')

        if hasattr(e.control, 'update'):
            e.control.update()

    def _reset_zoom(self, e) -> None:
        """Reset chart zoom to default."""
        self._zoom_level = 1.0
        self._pan_offset = 0.0
        self._update_chart_display()
        self._update_status_bar()

    def _show_export_dialog(self, e) -> None:
        """Show export options dialog."""
        if self._on_export_request:
            self._on_export_request("PNG")  # Default format

    def _on_grid_toggle(self, e) -> None:
        """Handle grid visibility toggle."""
        self._config.show_grid = e.control.value
        self._update_chart_display()

    def _on_smooth_toggle(self, e) -> None:
        """Handle smooth curves toggle."""
        self._config.smooth_curves = e.control.value
        self._update_chart_display()

    def _on_auto_scale_toggle(self, e) -> None:
        """Handle auto scale toggle."""
        self._config.auto_scale = e.control.value
        self._update_chart_display()

    # Data Management Methods
    def add_loss_data_point(self, data_point: LossDataPoint) -> None:
        """
        Add a new loss data point to the chart.

        Args:
            data_point: Loss data point to add
        """
        try:
            with self._data_lock:
                self._chart_data.add_data_point(data_point)

                if self._config.real_time_updates and not self._is_paused:
                    self._schedule_chart_update()

        except Exception as ex:
            print(f"Error adding data point: {ex}")

    def add_multiple_data_points(self, data_points: List[LossDataPoint]) -> None:
        """
        Add multiple loss data points efficiently.

        Args:
            data_points: List of loss data points to add
        """
        try:
            with self._data_lock:
                for data_point in data_points:
                    self._chart_data.add_data_point(data_point)

                if self._config.real_time_updates and not self._is_paused:
                    self._schedule_chart_update()

        except Exception as ex:
            print(f"Error adding multiple data points: {ex}")

    def clear_chart_data(self, loss_type: Optional[LossType] = None) -> None:
        """
        Clear chart data for specified loss type or all types.

        Args:
            loss_type: Loss type to clear, or None for all types
        """
        try:
            with self._data_lock:
                if loss_type is None:
                    self._chart_data.training_losses.clear()
                    self._chart_data.validation_losses.clear()
                    self._chart_data.test_losses.clear()
                elif loss_type == LossType.TRAINING:
                    self._chart_data.training_losses.clear()
                elif loss_type == LossType.VALIDATION:
                    self._chart_data.validation_losses.clear()
                elif loss_type == LossType.TEST:
                    self._chart_data.test_losses.clear()

                self._update_chart_display()

        except Exception as ex:
            print(f"Error clearing chart data: {ex}")

    def set_time_range(self, time_range: ChartTimeRange) -> None:
        """
        Set the chart time range programmatically.

        Args:
            time_range: Time range to set
        """
        self._current_time_range = time_range
        self._update_chart_display()

    def set_view_mode(self, view_mode: ChartViewMode) -> None:
        """
        Set the chart view mode programmatically.

        Args:
            view_mode: View mode to set
        """
        self._current_view_mode = view_mode
        self._update_chart_display()

    # Chart Update Methods
    def _schedule_chart_update(self) -> None:
        """Schedule a chart update with throttling."""
        current_time = datetime.now()
        time_since_last_update = (current_time - self._last_update_time).total_seconds() * 1000

        if time_since_last_update >= self._config.update_interval_ms:
            self._update_chart_display()
            self._last_update_time = current_time

    def _update_chart_display(self) -> None:
        """Update the chart display with current data."""
        try:
            if not self._loss_chart:
                return

            with self._data_lock:
                # Update chart data series
                self._update_chart_data_series()

                # Update chart bounds if auto-scaling
                if self._config.auto_scale:
                    self._update_chart_bounds()

                # Update status bar
                self._update_status_bar()

                # Trigger UI update
                if hasattr(self._loss_chart, 'update'):
                    self._loss_chart.update()

        except Exception as ex:
            print(f"Error updating chart display: {ex}")

    def _update_chart_data_series(self) -> None:
        """Update chart data series with current loss data."""
        if not self._loss_chart or not self._loss_chart.data_series:
            return

        series_index = 0

        # Update training loss series
        if self._config.show_training_loss and series_index < len(self._loss_chart.data_series):
            training_data = self._chart_data.get_data_points(LossType.TRAINING, self._current_time_range)
            chart_points = self._convert_to_chart_points(training_data)
            self._loss_chart.data_series[series_index].data_points = chart_points
            series_index += 1

        # Update validation loss series
        if self._config.show_validation_loss and series_index < len(self._loss_chart.data_series):
            validation_data = self._chart_data.get_data_points(LossType.VALIDATION, self._current_time_range)
            chart_points = self._convert_to_chart_points(validation_data)
            self._loss_chart.data_series[series_index].data_points = chart_points
            series_index += 1

        # Update test loss series
        if self._config.show_test_loss and series_index < len(self._loss_chart.data_series):
            test_data = self._chart_data.get_data_points(LossType.TEST, self._current_time_range)
            chart_points = self._convert_to_chart_points(test_data)
            self._loss_chart.data_series[series_index].data_points = chart_points

    def _convert_to_chart_points(self, data_points: List[LossDataPoint]) -> List[ft.LineChartDataPoint]:
        """Convert loss data points to chart data points."""
        chart_points = []

        for i, data_point in enumerate(data_points):
            # Use step number as x-coordinate for real-time view, timestamp for historical
            if self._current_view_mode == ChartViewMode.REAL_TIME:
                x_value = data_point.step
            else:
                # Convert timestamp to minutes since first data point
                if data_points:
                    first_timestamp = data_points[0].timestamp
                    x_value = (data_point.timestamp - first_timestamp).total_seconds() / 60
                else:
                    x_value = i

            chart_point = ft.LineChartDataPoint(
                x=x_value,
                y=data_point.loss_value,
                tooltip=f"Step: {data_point.step}\nLoss: {data_point.loss_value:.4f}\nEpoch: {data_point.epoch}"
            )
            chart_points.append(chart_point)

        return chart_points

    def _update_chart_bounds(self) -> None:
        """Update chart bounds for auto-scaling."""
        all_data_points = []

        # Collect all visible data points
        if self._config.show_training_loss:
            all_data_points.extend(self._chart_data.get_data_points(LossType.TRAINING, self._current_time_range))
        if self._config.show_validation_loss:
            all_data_points.extend(self._chart_data.get_data_points(LossType.VALIDATION, self._current_time_range))
        if self._config.show_test_loss:
            all_data_points.extend(self._chart_data.get_data_points(LossType.TEST, self._current_time_range))

        if not all_data_points:
            return

        # Calculate bounds
        loss_values = [dp.loss_value for dp in all_data_points]
        steps = [dp.step for dp in all_data_points]

        self._chart_bounds = {
            "min_x": min(steps) if steps else 0,
            "max_x": max(steps) if steps else 100,
            "min_y": min(loss_values) if loss_values else 0,
            "max_y": max(loss_values) if loss_values else 1
        }

    def _update_status_indicator(self) -> None:
        """Update the status indicator."""
        # This would be called to refresh the status indicator
        # Implementation depends on how the UI updates are handled
        pass

    def _update_status_bar(self) -> None:
        """Update the status bar with current information."""
        if not self._status_bar:
            return

        try:
            # Count total data points
            total_points = (len(self._chart_data.training_losses) +
                          len(self._chart_data.validation_losses) +
                          len(self._chart_data.test_losses))

            # Format last update time
            last_update = self._last_update_time.strftime("%H:%M:%S")

            # Format zoom level
            zoom_percent = int(self._zoom_level * 100)

            # Update status text (this is a simplified approach)
            status_texts = [
                f"Data Points: {total_points}",
                f"Last Update: {last_update}",
                f"Zoom: {zoom_percent}%"
            ]

            # Update status bar content if it has Row controls
            if hasattr(self._status_bar, 'content') and hasattr(self._status_bar.content, 'controls'):
                for i, text in enumerate(status_texts):
                    if i < len(self._status_bar.content.controls):
                        if hasattr(self._status_bar.content.controls[i], 'value'):
                            self._status_bar.content.controls[i].value = text

        except Exception as ex:
            print(f"Error updating status bar: {ex}")

    # Utility Methods
    def get_chart_statistics(self) -> Dict[str, Any]:
        """Get chart statistics and metadata."""
        with self._data_lock:
            return {
                "total_training_points": len(self._chart_data.training_losses),
                "total_validation_points": len(self._chart_data.validation_losses),
                "total_test_points": len(self._chart_data.test_losses),
                "current_view_mode": self._current_view_mode.value,
                "current_time_range": self._current_time_range.value,
                "is_paused": self._is_paused,
                "zoom_level": self._zoom_level,
                "chart_bounds": self._chart_bounds.copy(),
                "last_update": self._last_update_time.isoformat()
            }

    def export_chart_data(self, format_type: str = "CSV") -> Optional[str]:
        """
        Export chart data in specified format.

        Args:
            format_type: Export format ("CSV", "JSON", "PNG", "SVG")

        Returns:
            Exported data as string or file path
        """
        try:
            with self._data_lock:
                if format_type.upper() == "CSV":
                    return self._export_to_csv()
                elif format_type.upper() == "JSON":
                    return self._export_to_json()
                else:
                    # For image formats, would need additional implementation
                    return None

        except Exception as ex:
            print(f"Error exporting chart data: {ex}")
            return None

    def _export_to_csv(self) -> str:
        """Export data to CSV format."""
        lines = ["timestamp,epoch,step,loss_value,loss_type,learning_rate,gradient_norm"]

        all_data = []
        all_data.extend(self._chart_data.get_data_points(LossType.TRAINING))
        all_data.extend(self._chart_data.get_data_points(LossType.VALIDATION))
        all_data.extend(self._chart_data.get_data_points(LossType.TEST))

        # Sort by timestamp
        all_data.sort(key=lambda x: x.timestamp)

        for dp in all_data:
            line = f"{dp.timestamp.isoformat()},{dp.epoch},{dp.step},{dp.loss_value},{dp.loss_type.value},{dp.learning_rate or ''},{dp.gradient_norm or ''}"
            lines.append(line)

        return "\n".join(lines)

    def _export_to_json(self) -> str:
        """Export data to JSON format."""
        import json

        data = {
            "export_timestamp": datetime.now().isoformat(),
            "chart_config": {
                "view_mode": self._current_view_mode.value,
                "time_range": self._current_time_range.value,
                "zoom_level": self._zoom_level
            },
            "training_losses": [
                {
                    "timestamp": dp.timestamp.isoformat(),
                    "epoch": dp.epoch,
                    "step": dp.step,
                    "loss_value": dp.loss_value,
                    "learning_rate": dp.learning_rate,
                    "gradient_norm": dp.gradient_norm,
                    "metadata": dp.metadata
                }
                for dp in self._chart_data.get_data_points(LossType.TRAINING)
            ],
            "validation_losses": [
                {
                    "timestamp": dp.timestamp.isoformat(),
                    "epoch": dp.epoch,
                    "step": dp.step,
                    "loss_value": dp.loss_value,
                    "learning_rate": dp.learning_rate,
                    "gradient_norm": dp.gradient_norm,
                    "metadata": dp.metadata
                }
                for dp in self._chart_data.get_data_points(LossType.VALIDATION)
            ]
        }

        return json.dumps(data, indent=2)
