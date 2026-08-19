"""
Module: metric_panel_ui
Description: Displays various training metrics in organized panels with comprehensive visualization,
            real-time updates, and interactive analysis capabilities. Features responsive design with
            breakpoint-aware layouts, metric categorization, filtering options, and seamless integration
            with training orchestration system. Includes theme-aware styling, accessibility compliance,
            and cross-platform compatibility for monitoring training metrics during 12-24 hour sessions.
Phase: 4
Location: /src/modules/ui/training_monitor_ui/metric_panel_ui/metric_panel_ui.py
"""

# Standard library imports
import asyncio
import logging
import math
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field

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

# Optional training metrics imports
try:
    from src.modules.logic.training_metrics_lg.base_interfaces import (
        MetricType, MetricResult, AggregatedMetrics
    )
    from src.modules.logic.training_metrics_lg.metric_aggregator_lg.metric_aggregator_lg import (
        MetricAggregator, TrainingMetricsCollector
    )
    TRAINING_METRICS_AVAILABLE = True
except ImportError:
    MetricType = None
    MetricResult = None
    AggregatedMetrics = None
    MetricAggregator = None
    TrainingMetricsCollector = None
    TRAINING_METRICS_AVAILABLE = False

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


class MetricDisplayMode(Enum):
    """Metric panel display modes."""
    COMPACT = "compact"
    DETAILED = "detailed"
    GRID = "grid"
    LIST = "list"
    CHARTS = "charts"


class MetricCategory(Enum):
    """Training metric categories."""
    TRAINING = "training"
    VALIDATION = "validation"
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    CUSTOM = "custom"


@dataclass
class MetricCard:
    """Individual metric card data structure."""
    metric_id: str
    title: str
    value: str
    unit: str = ""
    icon: str = "ANALYTICS"
    category: MetricCategory = MetricCategory.TRAINING
    color: str = "primary"
    trend: Optional[float] = None
    description: str = ""
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class MetricConfiguration:
    """Configuration for metric panel display."""
    display_mode: MetricDisplayMode = MetricDisplayMode.GRID
    refresh_interval_seconds: float = 1.0
    show_trends: bool = True
    show_charts: bool = True
    auto_scale: bool = True
    max_history_points: int = 1000
    categories_enabled: Dict[MetricCategory, bool] = field(default_factory=lambda: {
        MetricCategory.TRAINING: True,
        MetricCategory.VALIDATION: True,
        MetricCategory.PERFORMANCE: True,
        MetricCategory.RESOURCE: True,
        MetricCategory.CUSTOM: True
    })


@dataclass
class TrainingMetricData:
    """Training metric data for display."""
    epoch: int = 0
    step: int = 0
    loss: float = 0.0
    accuracy: Optional[float] = None
    validation_loss: Optional[float] = None
    validation_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    batch_size: int = 32
    processing_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    gpu_utilization: float = 0.0
    cpu_utilization: float = 0.0
    throughput: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    custom_metrics: Dict[str, float] = field(default_factory=dict)


class MetricPanelUI(ThemeAwareUserControl):
    """
    Comprehensive training metrics panel UI component.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time training metrics visualization with interactive displays
    - Metric categorization and filtering capabilities
    - Multiple display modes (compact, detailed, grid, list, charts)
    - Theme-aware styling with accessibility compliance
    - Integration with training orchestration and metrics systems
    - Performance optimization for continuous monitoring
    - Historical data visualization and trend analysis
    - Export functionality for metrics data
    - Cross-platform compatibility and offline operation
    """

    def __init__(self,
                 config: Optional[MetricConfiguration] = None,
                 session_manager: Optional[SessionManager] = None,
                 metric_aggregator: Optional[MetricAggregator] = None,
                 hardware_monitor: Optional[HardwareMonitor] = None,
                 on_metric_click: Optional[Callable[[str], None]] = None,
                 on_export_metrics: Optional[Callable[[], None]] = None,
                 **kwargs):
        """
        Initialize the metric panel UI.
        
        Args:
            config: Metric panel configuration
            session_manager: Training session manager instance
            metric_aggregator: Metrics aggregation system
            hardware_monitor: Hardware monitoring system
            on_metric_click: Callback for metric card clicks
            on_export_metrics: Callback for metrics export
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration and dependencies
        self._config = config or MetricConfiguration()
        self._session_manager = session_manager
        self._metric_aggregator = metric_aggregator
        self._hardware_monitor = hardware_monitor
        self._on_metric_click = on_metric_click
        self._on_export_metrics = on_export_metrics
        
        # State management
        self._current_metrics = TrainingMetricData()
        self._metric_cards: Dict[str, MetricCard] = {}
        self._metric_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._is_monitoring = False
        self._last_update = datetime.now()
        
        # UI components
        self._header_container = None
        self._filter_controls = None
        self._metrics_grid = None
        self._charts_container = None
        self._export_button = None
        self._refresh_indicator = None
        
        # Monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Logger
        self._logger = logging.getLogger(__name__)
        
        # Initialize metric cards
        self._initialize_metric_cards()

    def _initialize_metric_cards(self) -> None:
        """Initialize default metric cards."""
        default_metrics = [
            MetricCard("epoch", "Epoch", "0", "", "TIMELINE", MetricCategory.TRAINING, "primary"),
            MetricCard("step", "Step", "0", "", "PLAY_ARROW", MetricCategory.TRAINING, "primary"),
            MetricCard("loss", "Training Loss", "0.0000", "", "TRENDING_DOWN", MetricCategory.TRAINING, "error"),
            MetricCard("accuracy", "Accuracy", "0.00", "%", "TARGET", MetricCategory.TRAINING, "success"),
            MetricCard("val_loss", "Validation Loss", "0.0000", "", "TRENDING_DOWN", MetricCategory.VALIDATION, "warning"),
            MetricCard("val_accuracy", "Val Accuracy", "0.00", "%", "TARGET", MetricCategory.VALIDATION, "success"),
            MetricCard("learning_rate", "Learning Rate", "0.001", "", "TUNE", MetricCategory.TRAINING, "info"),
            MetricCard("batch_size", "Batch Size", "32", "", "GRID_VIEW", MetricCategory.TRAINING, "secondary"),
            MetricCard("processing_time", "Processing Time", "0", "ms", "TIMER", MetricCategory.PERFORMANCE, "info"),
            MetricCard("memory_usage", "Memory Usage", "0", "MB", "MEMORY", MetricCategory.RESOURCE, "warning"),
            MetricCard("gpu_utilization", "GPU Usage", "0", "%", "DEVELOPER_BOARD", MetricCategory.RESOURCE, "primary"),
            MetricCard("cpu_utilization", "CPU Usage", "0", "%", "CPU", MetricCategory.RESOURCE, "secondary"),
            MetricCard("throughput", "Throughput", "0.0", "steps/s", "SPEED", MetricCategory.PERFORMANCE, "success")
        ]
        
        for card in default_metrics:
            self._metric_cards[card.metric_id] = card

    def build(self) -> ft.Control:
        """Build the metric panel UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header
        header = self._create_header()
        
        # Create filter controls
        filter_controls = self._create_filter_controls()
        
        # Create main content based on display mode
        main_content = self._create_main_content()
        
        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=spacing.sm),
                filter_controls,
                ft.Container(height=spacing.md),
                main_content
            ], scroll=ft.ScrollMode.AUTO),
            bgcolor=palette.background_primary,
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_header(self) -> ft.Control:
        """Create the metric panel header."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Title and status
        title = ft.Text(
            "Training Metrics",
            style=self.get_text_style('h2'),
            color=palette.text_primary
        )

        # Last update indicator
        last_update_text = ft.Text(
            f"Last updated: {self._last_update.strftime('%H:%M:%S')}",
            style=self.get_text_style('body_small'),
            color=palette.text_secondary
        )

        # Refresh indicator
        self._refresh_indicator = ft.ProgressRing(
            width=rlm.get_breakpoint_value(16, 18, 20, 22),
            height=rlm.get_breakpoint_value(16, 18, 20, 22),
            stroke_width=2,
            color=palette.primary,
            visible=False
        )

        # Export button
        self._export_button = ft.IconButton(
            icon=self.get_icon('DOWNLOAD'),
            icon_color=palette.text_secondary,
            icon_size=rlm.get_breakpoint_value(18, 20, 22, 24),
            tooltip="Export Metrics",
            on_click=self._handle_export_click
        )

        # Settings button
        settings_button = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            icon_color=palette.text_secondary,
            icon_size=rlm.get_breakpoint_value(18, 20, 22, 24),
            tooltip="Metric Settings",
            on_click=self._handle_settings_click
        )

        return ft.Container(
            content=ft.Row([
                ft.Column([
                    title,
                    last_update_text
                ], spacing=spacing.xs),
                ft.Row([
                    self._refresh_indicator,
                    self._export_button,
                    settings_button
                ], spacing=spacing.sm)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders)
        )

    def _create_filter_controls(self) -> ft.Control:
        """Create metric filtering and display mode controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Display mode selector
        mode_buttons = []
        for mode in MetricDisplayMode:
            is_selected = mode == self._config.display_mode
            button = ft.Container(
                content=ft.Text(
                    mode.value.title(),
                    style=self.get_text_style('body_small'),
                    color=palette.text_primary if is_selected else palette.text_secondary
                ),
                padding=ft.padding.symmetric(
                    horizontal=spacing.sm,
                    vertical=spacing.xs
                ),
                bgcolor=palette.primary if is_selected else palette.surface,
                border_radius=ft.border_radius.all(spacing.xs),
                border=ft.border.all(1, palette.primary if is_selected else palette.borders),
                on_click=lambda e, m=mode: self._handle_mode_change(m)
            )
            mode_buttons.append(button)

        # Category filters
        category_chips = []
        for category in MetricCategory:
            is_enabled = self._config.categories_enabled.get(category, True)
            chip = ft.Container(
                content=ft.Row([
                    ft.Icon(
                        self.get_icon('CHECK_CIRCLE' if is_enabled else 'RADIO_BUTTON_UNCHECKED'),
                        size=rlm.get_breakpoint_value(14, 16, 18, 20),
                        color=palette.success if is_enabled else palette.text_secondary
                    ),
                    ft.Text(
                        category.value.title(),
                        style=self.get_text_style('body_small'),
                        color=palette.text_primary if is_enabled else palette.text_secondary
                    )
                ], spacing=spacing.xs),
                padding=ft.padding.symmetric(
                    horizontal=spacing.sm,
                    vertical=spacing.xs
                ),
                bgcolor=palette.surface,
                border_radius=ft.border_radius.all(spacing.xs),
                border=ft.border.all(1, palette.success if is_enabled else palette.borders),
                on_click=lambda e, c=category: self._handle_category_toggle(c)
            )
            category_chips.append(chip)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        "Display Mode:",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary
                    ),
                    *mode_buttons
                ], spacing=spacing.sm, wrap=True),
                ft.Container(height=spacing.sm),
                ft.Row([
                    ft.Text(
                        "Categories:",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary
                    ),
                    *category_chips
                ], spacing=spacing.sm, wrap=True)
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders)
        )

    def _create_main_content(self) -> ft.Control:
        """Create main content based on display mode."""
        if self._config.display_mode == MetricDisplayMode.GRID:
            return self._create_metrics_grid()
        elif self._config.display_mode == MetricDisplayMode.LIST:
            return self._create_metrics_list()
        elif self._config.display_mode == MetricDisplayMode.CHARTS:
            return self._create_metrics_charts()
        elif self._config.display_mode == MetricDisplayMode.COMPACT:
            return self._create_compact_view()
        else:  # DETAILED
            return self._create_detailed_view()

    def _create_metrics_grid(self) -> ft.Control:
        """Create metrics display in grid layout."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Filter enabled metrics by category
        enabled_metrics = [
            card for card in self._metric_cards.values()
            if self._config.categories_enabled.get(card.category, True)
        ]

        # Create metric cards
        metric_controls = []
        for card in enabled_metrics:
            metric_control = self._create_metric_card_widget(card)
            metric_controls.append(metric_control)

        # Create responsive grid
        cols = rlm.get_breakpoint_value(1, 2, 3, 4)

        self._metrics_grid = ft.GridView(
            controls=metric_controls,
            runs_count=cols,
            spacing=spacing.md,
            run_spacing=spacing.md,
            child_aspect_ratio=1.5,
            expand=True
        )

        return ft.Container(
            content=self._metrics_grid,
            bgcolor=palette.background_primary,
            expand=True
        )

    def _create_metric_card_widget(self, card: MetricCard) -> ft.Control:
        """Create a metric card widget."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on card color
        card_color = getattr(palette, card.color, palette.primary)

        # Icon
        icon = ft.Icon(
            self.get_icon(card.icon),
            color=card_color,
            size=rlm.get_breakpoint_value(20, 24, 28, 32)
        )

        # Title
        title = ft.Text(
            card.title,
            style=self.get_text_style('body_small'),
            color=palette.text_secondary,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # Value with unit
        value_text = f"{card.value}{card.unit}"
        value = ft.Text(
            value_text,
            style=self.get_text_style('h3'),
            color=palette.text_primary,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # Trend indicator (if available)
        trend_widget = None
        if card.trend is not None and self._config.show_trends:
            trend_icon = "TRENDING_UP" if card.trend > 0 else "TRENDING_DOWN" if card.trend < 0 else "TRENDING_FLAT"
            trend_color = palette.success if card.trend > 0 else palette.error if card.trend < 0 else palette.text_secondary

            trend_widget = ft.Row([
                ft.Icon(
                    self.get_icon(trend_icon),
                    color=trend_color,
                    size=rlm.get_breakpoint_value(12, 14, 16, 18)
                ),
                ft.Text(
                    f"{abs(card.trend):.1f}%",
                    style=self.get_text_style('caption'),
                    color=trend_color
                )
            ], spacing=spacing.xs)

        # Card content
        content_column = [
            ft.Row([icon, title], spacing=spacing.sm),
            value
        ]

        if trend_widget:
            content_column.append(trend_widget)

        return ft.Container(
            content=ft.Column(
                content_column,
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            on_click=lambda e: self._handle_metric_click(card.metric_id),
            tooltip=card.description if card.description else card.title,
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT)
        )

    def _create_metrics_list(self) -> ft.Control:
        """Create metrics display in list layout."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Filter enabled metrics by category
        enabled_metrics = [
            card for card in self._metric_cards.values()
            if self._config.categories_enabled.get(card.category, True)
        ]

        # Group metrics by category
        categorized_metrics = {}
        for card in enabled_metrics:
            if card.category not in categorized_metrics:
                categorized_metrics[card.category] = []
            categorized_metrics[card.category].append(card)

        # Create list sections
        list_sections = []
        for category, cards in categorized_metrics.items():
            # Category header
            header = ft.Container(
                content=ft.Text(
                    category.value.title(),
                    style=self.get_text_style('h4'),
                    color=palette.text_primary
                ),
                padding=ft.padding.symmetric(vertical=spacing.sm),
                bgcolor=palette.background_secondary,
                border_radius=ft.border_radius.all(spacing.xs)
            )

            # Metric rows
            metric_rows = []
            for card in cards:
                row = self._create_metric_list_row(card)
                metric_rows.append(row)

            list_sections.extend([header] + metric_rows)

        return ft.Container(
            content=ft.Column(
                list_sections,
                spacing=spacing.sm,
                scroll=ft.ScrollMode.AUTO
            ),
            bgcolor=palette.background_primary,
            expand=True
        )

    def _create_metric_list_row(self, card: MetricCard) -> ft.Control:
        """Create a metric row for list view."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on card color
        card_color = getattr(palette, card.color, palette.primary)

        # Icon
        icon = ft.Icon(
            self.get_icon(card.icon),
            color=card_color,
            size=rlm.get_breakpoint_value(18, 20, 22, 24)
        )

        # Title and description
        title_column = ft.Column([
            ft.Text(
                card.title,
                style=self.get_text_style('body_medium'),
                color=palette.text_primary
            )
        ], spacing=spacing.xs)

        if card.description:
            title_column.controls.append(
                ft.Text(
                    card.description,
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                )
            )

        # Value with trend
        value_text = f"{card.value}{card.unit}"
        value_controls = [
            ft.Text(
                value_text,
                style=self.get_text_style('h4'),
                color=palette.text_primary
            )
        ]

        # Add trend if available
        if card.trend is not None and self._config.show_trends:
            trend_icon = "TRENDING_UP" if card.trend > 0 else "TRENDING_DOWN" if card.trend < 0 else "TRENDING_FLAT"
            trend_color = palette.success if card.trend > 0 else palette.error if card.trend < 0 else palette.text_secondary

            value_controls.append(
                ft.Row([
                    ft.Icon(
                        self.get_icon(trend_icon),
                        color=trend_color,
                        size=rlm.get_breakpoint_value(12, 14, 16, 18)
                    ),
                    ft.Text(
                        f"{abs(card.trend):.1f}%",
                        style=self.get_text_style('caption'),
                        color=trend_color
                    )
                ], spacing=spacing.xs)
            )

        return ft.Container(
            content=ft.Row([
                icon,
                ft.Container(content=title_column, expand=True),
                ft.Column(
                    value_controls,
                    spacing=spacing.xs,
                    horizontal_alignment=ft.CrossAxisAlignment.END
                )
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            on_click=lambda e: self._handle_metric_click(card.metric_id),
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT)
        )

    def _create_metrics_charts(self) -> ft.Control:
        """Create metrics display with charts."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create chart containers for different metric types
        chart_containers = []

        # Training metrics chart
        training_chart = self._create_metric_chart(
            "Training Metrics",
            ["loss", "accuracy"],
            [palette.error, palette.success]
        )
        chart_containers.append(training_chart)

        # Validation metrics chart
        validation_chart = self._create_metric_chart(
            "Validation Metrics",
            ["val_loss", "val_accuracy"],
            [palette.warning, palette.success]
        )
        chart_containers.append(validation_chart)

        # Resource metrics chart
        resource_chart = self._create_metric_chart(
            "Resource Utilization",
            ["memory_usage", "gpu_utilization", "cpu_utilization"],
            [palette.warning, palette.primary, palette.secondary]
        )
        chart_containers.append(resource_chart)

        # Performance metrics chart
        performance_chart = self._create_metric_chart(
            "Performance Metrics",
            ["throughput", "processing_time"],
            [palette.success, palette.info]
        )
        chart_containers.append(performance_chart)

        # Arrange charts in responsive grid
        cols = rlm.get_breakpoint_value(1, 1, 2, 2)

        return ft.Container(
            content=ft.GridView(
                controls=chart_containers,
                runs_count=cols,
                spacing=spacing.lg,
                run_spacing=spacing.lg,
                child_aspect_ratio=1.8,
                expand=True
            ),
            bgcolor=palette.background_primary,
            expand=True
        )

    def _create_metric_chart(self, title: str, metric_ids: List[str], colors: List[str]) -> ft.Control:
        """Create a chart for specific metrics."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Chart title
        chart_title = ft.Text(
            title,
            style=self.get_text_style('h4'),
            color=palette.text_primary
        )

        # Create line chart data points
        data_series = []
        for i, metric_id in enumerate(metric_ids):
            if metric_id in self._metric_history:
                history = self._metric_history[metric_id]
                if history:
                    # Convert history to chart data points
                    points = []
                    for j, (timestamp, value) in enumerate(history[-50:]):  # Last 50 points
                        points.append(ft.LineChartDataPoint(j, value))

                    color = colors[i] if i < len(colors) else palette.primary
                    data_series.append(
                        ft.LineChartData(
                            data_points=points,
                            stroke_width=rlm.get_breakpoint_value(2, 2, 3, 3),
                            color=color,
                            curved=True,
                            stroke_cap_round=True
                        )
                    )

        # Create chart or placeholder
        if data_series:
            chart = ft.LineChart(
                data_series=data_series,
                border=ft.border.all(1, palette.borders),
                horizontal_grid_lines=ft.ChartGridLines(
                    color=palette.borders,
                    width=1,
                    dash_pattern=[3, 3]
                ),
                vertical_grid_lines=ft.ChartGridLines(
                    color=palette.borders,
                    width=1,
                    dash_pattern=[3, 3]
                ),
                left_axis=ft.ChartAxis(
                    labels_size=rlm.get_breakpoint_value(28, 32, 36, 40),
                    title=ft.Text(
                        "Value",
                        style=self.get_text_style('caption'),
                        color=palette.text_secondary
                    )
                ),
                bottom_axis=ft.ChartAxis(
                    labels_size=rlm.get_breakpoint_value(28, 32, 36, 40),
                    title=ft.Text(
                        "Time",
                        style=self.get_text_style('caption'),
                        color=palette.text_secondary
                    )
                ),
                tooltip_bgcolor=palette.surface,
                expand=True
            )
        else:
            chart = ft.Container(
                content=ft.Column([
                    ft.Icon(
                        self.get_icon('SHOW_CHART'),
                        size=rlm.get_breakpoint_value(32, 40, 48, 56),
                        color=palette.text_secondary
                    ),
                    ft.Text(
                        "No data available",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], alignment=ft.MainAxisAlignment.CENTER,
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                expand=True
            )

        # Legend
        legend_items = []
        for i, metric_id in enumerate(metric_ids):
            if metric_id in self._metric_cards:
                card = self._metric_cards[metric_id]
                color = colors[i] if i < len(colors) else palette.primary
                legend_items.append(
                    ft.Row([
                        ft.Container(
                            width=rlm.get_breakpoint_value(12, 14, 16, 18),
                            height=rlm.get_breakpoint_value(12, 14, 16, 18),
                            bgcolor=color,
                            border_radius=ft.border_radius.all(2)
                        ),
                        ft.Text(
                            card.title,
                            style=self.get_text_style('caption'),
                            color=palette.text_secondary
                        )
                    ], spacing=spacing.xs)
                )

        legend = ft.Row(
            legend_items,
            spacing=spacing.md,
            wrap=True
        ) if legend_items else None

        # Combine components
        content_controls = [chart_title, chart]
        if legend:
            content_controls.append(legend)

        return ft.Container(
            content=ft.Column(
                content_controls,
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            expand=True
        )

    def _create_compact_view(self) -> ft.Control:
        """Create compact metrics view."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Key metrics for compact view
        key_metrics = ["epoch", "step", "loss", "accuracy", "gpu_utilization", "memory_usage"]

        # Create compact metric widgets
        compact_widgets = []
        for metric_id in key_metrics:
            if metric_id in self._metric_cards:
                card = self._metric_cards[metric_id]
                if self._config.categories_enabled.get(card.category, True):
                    widget = self._create_compact_metric_widget(card)
                    compact_widgets.append(widget)

        return ft.Container(
            content=ft.Row(
                compact_widgets,
                spacing=spacing.sm,
                wrap=True,
                alignment=ft.MainAxisAlignment.SPACE_AROUND
            ),
            bgcolor=palette.background_primary,
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _create_compact_metric_widget(self, card: MetricCard) -> ft.Control:
        """Create a compact metric widget."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on card color
        card_color = getattr(palette, card.color, palette.primary)

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    self.get_icon(card.icon),
                    color=card_color,
                    size=rlm.get_breakpoint_value(16, 18, 20, 22)
                ),
                ft.Text(
                    f"{card.value}{card.unit}",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_primary,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    card.title,
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                )
            ], spacing=spacing.xs,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.sm),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(4, 6, 8, 10)),
            border=ft.border.all(1, palette.borders),
            on_click=lambda e: self._handle_metric_click(card.metric_id),
            tooltip=card.title
        )

    def _create_detailed_view(self) -> ft.Control:
        """Create detailed metrics view with additional information."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Combine grid and charts
        grid_view = self._create_metrics_grid()
        charts_view = self._create_metrics_charts()

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=grid_view,
                    height=300,
                    expand=False
                ),
                ft.Container(height=spacing.lg),
                ft.Container(
                    content=charts_view,
                    expand=True
                )
            ]),
            bgcolor=palette.background_primary,
            expand=True
        )

    # Event handlers
    def _handle_mode_change(self, mode: MetricDisplayMode) -> None:
        """Handle display mode change."""
        self._config.display_mode = mode
        self.update()

    def _handle_category_toggle(self, category: MetricCategory) -> None:
        """Handle category filter toggle."""
        current_state = self._config.categories_enabled.get(category, True)
        self._config.categories_enabled[category] = not current_state
        self.update()

    def _handle_metric_click(self, metric_id: str) -> None:
        """Handle metric card click."""
        if self._on_metric_click:
            self._on_metric_click(metric_id)

    def _handle_export_click(self, e) -> None:
        """Handle export button click."""
        if self._on_export_metrics:
            self._on_export_metrics()

    def _handle_settings_click(self, e) -> None:
        """Handle settings button click."""
        # TODO: Implement settings dialog
        pass

    # Real-time updates
    async def start_monitoring(self) -> None:
        """Start real-time metric monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._logger.info("Started metric monitoring")

    async def stop_monitoring(self) -> None:
        """Stop real-time metric monitoring."""
        if not self._is_monitoring:
            return

        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self._logger.info("Stopped metric monitoring")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for real-time updates."""
        try:
            while self._is_monitoring:
                await self._update_metrics()
                await asyncio.sleep(self._config.refresh_interval_seconds)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in monitoring loop: {e}")

    async def _update_metrics(self) -> None:
        """Update metrics from various sources."""
        try:
            # Show refresh indicator
            if self._refresh_indicator:
                self._refresh_indicator.visible = True
                self.update()

            # Update from training session
            if self._session_manager and TRAINING_ORCHESTRATION_AVAILABLE:
                await self._update_training_metrics()

            # Update from resource monitoring
            if self._hardware_monitor and RESOURCE_MONITORING_AVAILABLE:
                await self._update_resource_metrics()

            # Update from metric aggregator
            if self._metric_aggregator and TRAINING_METRICS_AVAILABLE:
                await self._update_aggregated_metrics()

            # Update timestamp
            self._last_update = datetime.now()

            # Update UI
            self._update_metric_cards()
            self._update_metric_history()

            # Hide refresh indicator
            if self._refresh_indicator:
                self._refresh_indicator.visible = False
                self.update()

        except Exception as e:
            self._logger.error(f"Error updating metrics: {e}")
            if self._refresh_indicator:
                self._refresh_indicator.visible = False
                self.update()

    async def _update_training_metrics(self) -> None:
        """Update metrics from training session."""
        try:
            # Get current session
            current_session = await self._session_manager.get_current_session()
            if not current_session:
                return

            # Update training metrics
            if current_session.metrics_history:
                latest_metrics = current_session.metrics_history[-1]
                self._current_metrics.epoch = latest_metrics.epoch
                self._current_metrics.step = latest_metrics.step
                self._current_metrics.loss = latest_metrics.loss
                self._current_metrics.accuracy = latest_metrics.accuracy
                self._current_metrics.validation_loss = latest_metrics.validation_loss
                self._current_metrics.validation_accuracy = latest_metrics.validation_accuracy
                self._current_metrics.learning_rate = latest_metrics.learning_rate
                self._current_metrics.batch_size = latest_metrics.batch_size
                self._current_metrics.processing_time_ms = latest_metrics.processing_time_ms
                self._current_metrics.memory_usage_mb = latest_metrics.memory_usage_mb
                self._current_metrics.gpu_utilization = latest_metrics.gpu_utilization
                self._current_metrics.custom_metrics = latest_metrics.custom_metrics.copy()

        except Exception as e:
            self._logger.error(f"Error updating training metrics: {e}")

    async def _update_resource_metrics(self) -> None:
        """Update metrics from resource monitoring."""
        try:
            # Get current resource metrics
            resource_metrics = await self._hardware_monitor.get_current_metrics()
            if resource_metrics:
                self._current_metrics.memory_usage_mb = resource_metrics.memory_usage_mb
                self._current_metrics.gpu_utilization = resource_metrics.gpu_usage_percent or 0.0
                self._current_metrics.cpu_utilization = resource_metrics.cpu_usage_percent

        except Exception as e:
            self._logger.error(f"Error updating resource metrics: {e}")

    async def _update_aggregated_metrics(self) -> None:
        """Update metrics from metric aggregator."""
        try:
            # Get aggregated metrics for different types
            for metric_type in ["loss", "accuracy", "learning_rate"]:
                if hasattr(MetricType, metric_type.upper()):
                    history = self._metric_aggregator.get_metric_history(
                        getattr(MetricType, metric_type.upper()),
                        window_size=100
                    )
                    if history:
                        # Store in history for charts
                        if metric_type not in self._metric_history:
                            self._metric_history[metric_type] = []

                        # Add recent points
                        for metric_result in history[-10:]:  # Last 10 points
                            self._metric_history[metric_type].append(
                                (metric_result.timestamp, metric_result.metric_value)
                            )

                        # Limit history size
                        if len(self._metric_history[metric_type]) > self._config.max_history_points:
                            self._metric_history[metric_type] = self._metric_history[metric_type][-self._config.max_history_points:]

        except Exception as e:
            self._logger.error(f"Error updating aggregated metrics: {e}")

    def _update_metric_cards(self) -> None:
        """Update metric card values from current metrics."""
        # Update training metrics
        self._update_card_value("epoch", str(self._current_metrics.epoch))
        self._update_card_value("step", str(self._current_metrics.step))
        self._update_card_value("loss", f"{self._current_metrics.loss:.4f}")

        if self._current_metrics.accuracy is not None:
            self._update_card_value("accuracy", f"{self._current_metrics.accuracy:.2f}")

        if self._current_metrics.validation_loss is not None:
            self._update_card_value("val_loss", f"{self._current_metrics.validation_loss:.4f}")

        if self._current_metrics.validation_accuracy is not None:
            self._update_card_value("val_accuracy", f"{self._current_metrics.validation_accuracy:.2f}")

        self._update_card_value("learning_rate", f"{self._current_metrics.learning_rate:.6f}")
        self._update_card_value("batch_size", str(self._current_metrics.batch_size))

        # Update performance metrics
        self._update_card_value("processing_time", f"{self._current_metrics.processing_time_ms:.1f}")
        self._update_card_value("throughput", f"{self._current_metrics.throughput:.2f}")

        # Update resource metrics
        self._update_card_value("memory_usage", f"{self._current_metrics.memory_usage_mb:.0f}")
        self._update_card_value("gpu_utilization", f"{self._current_metrics.gpu_utilization:.1f}")
        self._update_card_value("cpu_utilization", f"{self._current_metrics.cpu_utilization:.1f}")

        # Update custom metrics
        for metric_name, value in self._current_metrics.custom_metrics.items():
            if metric_name in self._metric_cards:
                self._update_card_value(metric_name, f"{value:.4f}")

    def _update_card_value(self, metric_id: str, new_value: str) -> None:
        """Update a specific metric card value."""
        if metric_id in self._metric_cards:
            card = self._metric_cards[metric_id]
            old_value = card.value
            card.value = new_value
            card.last_updated = datetime.now()

            # Calculate trend if we have previous value
            try:
                if old_value and old_value != "0" and old_value != "0.0000":
                    old_float = float(old_value)
                    new_float = float(new_value)
                    if old_float != 0:
                        trend = ((new_float - old_float) / old_float) * 100
                        card.trend = trend
            except (ValueError, ZeroDivisionError):
                card.trend = None

    def _update_metric_history(self) -> None:
        """Update metric history for charts."""
        current_time = datetime.now()

        # Add current values to history
        metrics_to_track = {
            "loss": self._current_metrics.loss,
            "accuracy": self._current_metrics.accuracy,
            "val_loss": self._current_metrics.validation_loss,
            "val_accuracy": self._current_metrics.validation_accuracy,
            "learning_rate": self._current_metrics.learning_rate,
            "memory_usage": self._current_metrics.memory_usage_mb,
            "gpu_utilization": self._current_metrics.gpu_utilization,
            "cpu_utilization": self._current_metrics.cpu_utilization,
            "throughput": self._current_metrics.throughput,
            "processing_time": self._current_metrics.processing_time_ms
        }

        for metric_id, value in metrics_to_track.items():
            if value is not None:
                if metric_id not in self._metric_history:
                    self._metric_history[metric_id] = []

                self._metric_history[metric_id].append((current_time, float(value)))

                # Limit history size
                if len(self._metric_history[metric_id]) > self._config.max_history_points:
                    self._metric_history[metric_id] = self._metric_history[metric_id][-self._config.max_history_points:]

    # Public API methods
    def update_metric(self, metric_id: str, value: Union[str, float], unit: str = "") -> None:
        """Update a specific metric value."""
        if metric_id in self._metric_cards:
            card = self._metric_cards[metric_id]
            old_value = card.value
            card.value = str(value)
            card.unit = unit
            card.last_updated = datetime.now()

            # Calculate trend
            try:
                if old_value and old_value != "0":
                    old_float = float(old_value)
                    new_float = float(value)
                    if old_float != 0:
                        trend = ((new_float - old_float) / old_float) * 100
                        card.trend = trend
            except (ValueError, ZeroDivisionError):
                card.trend = None

            self.update()

    def add_custom_metric(self, metric_id: str, title: str, value: str,
                         unit: str = "", icon: str = "ANALYTICS",
                         category: MetricCategory = MetricCategory.CUSTOM,
                         color: str = "primary", description: str = "") -> None:
        """Add a custom metric card."""
        card = MetricCard(
            metric_id=metric_id,
            title=title,
            value=value,
            unit=unit,
            icon=icon,
            category=category,
            color=color,
            description=description
        )
        self._metric_cards[metric_id] = card
        self.update()

    def remove_metric(self, metric_id: str) -> None:
        """Remove a metric card."""
        if metric_id in self._metric_cards:
            del self._metric_cards[metric_id]
            if metric_id in self._metric_history:
                del self._metric_history[metric_id]
            self.update()

    def set_configuration(self, config: MetricConfiguration) -> None:
        """Update metric panel configuration."""
        self._config = config
        self.update()

    def get_metric_value(self, metric_id: str) -> Optional[str]:
        """Get current value of a metric."""
        if metric_id in self._metric_cards:
            return self._metric_cards[metric_id].value
        return None

    def get_metric_history(self, metric_id: str) -> List[Tuple[datetime, float]]:
        """Get history for a specific metric."""
        return self._metric_history.get(metric_id, []).copy()

    def export_metrics_data(self) -> Dict[str, Any]:
        """Export current metrics data."""
        return {
            "timestamp": datetime.now().isoformat(),
            "current_metrics": {
                "epoch": self._current_metrics.epoch,
                "step": self._current_metrics.step,
                "loss": self._current_metrics.loss,
                "accuracy": self._current_metrics.accuracy,
                "validation_loss": self._current_metrics.validation_loss,
                "validation_accuracy": self._current_metrics.validation_accuracy,
                "learning_rate": self._current_metrics.learning_rate,
                "batch_size": self._current_metrics.batch_size,
                "processing_time_ms": self._current_metrics.processing_time_ms,
                "memory_usage_mb": self._current_metrics.memory_usage_mb,
                "gpu_utilization": self._current_metrics.gpu_utilization,
                "cpu_utilization": self._current_metrics.cpu_utilization,
                "throughput": self._current_metrics.throughput,
                "custom_metrics": self._current_metrics.custom_metrics
            },
            "metric_cards": {
                metric_id: {
                    "title": card.title,
                    "value": card.value,
                    "unit": card.unit,
                    "category": card.category.value,
                    "trend": card.trend,
                    "last_updated": card.last_updated.isoformat()
                }
                for metric_id, card in self._metric_cards.items()
            },
            "metric_history": {
                metric_id: [
                    {"timestamp": timestamp.isoformat(), "value": value}
                    for timestamp, value in history
                ]
                for metric_id, history in self._metric_history.items()
            },
            "configuration": {
                "display_mode": self._config.display_mode.value,
                "refresh_interval_seconds": self._config.refresh_interval_seconds,
                "show_trends": self._config.show_trends,
                "show_charts": self._config.show_charts,
                "categories_enabled": {
                    category.value: enabled
                    for category, enabled in self._config.categories_enabled.items()
                }
            }
        }

    def clear_history(self) -> None:
        """Clear all metric history."""
        self._metric_history.clear()
        self.update()

    def reset_metrics(self) -> None:
        """Reset all metrics to default values."""
        self._current_metrics = TrainingMetricData()
        for card in self._metric_cards.values():
            card.value = "0"
            card.trend = None
            card.last_updated = datetime.now()
        self.clear_history()
        self.update()

    # Lifecycle methods
    def did_mount(self) -> None:
        """Called when component is mounted."""
        super().did_mount()
        # Start monitoring if configured
        if self._session_manager or self._hardware_monitor:
            asyncio.create_task(self.start_monitoring())

    def will_unmount(self) -> None:
        """Called when component will be unmounted."""
        super().will_unmount()
        # Stop monitoring
        if self._is_monitoring:
            asyncio.create_task(self.stop_monitoring())
