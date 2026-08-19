"""
Module: chart_components_ui
Description: Reusable chart components for metrics, performance graphs, and resource usage visualization.
            Provides comprehensive charting capabilities with interactive features, real-time updates,
            theme-aware styling, and responsive design for the MikroDok application.
            
Features:
- Multiple chart types: Line, Bar, Area, Pie, Gauge, Sparkline, Heatmap, Scatter
- Real-time data updates with smooth animations
- Interactive tooltips and data exploration
- Responsive design with breakpoint-aware layouts
- Theme-aware styling with accessibility compliance
- Performance optimization for large datasets
- Export functionality and data management
- Customizable styling and configuration options

Phase: 2-4
Location: /src/modules/ui/visualization_ui/chart_components_ui/chart_components_ui.py
"""

# Standard library imports
import asyncio
import json
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ColorPalette,
    SpacingSystem,
    TypographyScale,
    IconSystem,
    ResponsiveLayoutManager,
    ScreenSize
)


class ChartType(Enum):
    """Chart type enumeration for different visualization types."""
    LINE = "line"
    BAR = "bar"
    AREA = "area"
    PIE = "pie"
    GAUGE = "gauge"
    SPARKLINE = "sparkline"
    HEATMAP = "heatmap"
    SCATTER = "scatter"
    STACKED_BAR = "stacked_bar"
    STACKED_AREA = "stacked_area"


class ChartTheme(Enum):
    """Chart theme enumeration for different color schemes."""
    DEFAULT = "default"
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    STATUS = "status"
    GRADIENT = "gradient"
    MONOCHROME = "monochrome"


@dataclass
class ChartDataPoint:
    """Data point for chart visualization."""
    x: Union[float, str, datetime]
    y: float
    label: Optional[str] = None
    color: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ChartSeries:
    """Chart data series configuration."""
    name: str
    data: List[ChartDataPoint]
    color: Optional[str] = None
    line_width: Optional[float] = None
    fill_opacity: Optional[float] = None
    visible: bool = True
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ChartConfig:
    """Configuration for chart display and behavior."""
    # Chart appearance
    title: Optional[str] = None
    subtitle: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    theme: ChartTheme = ChartTheme.DEFAULT
    
    # Axes configuration
    x_axis_title: Optional[str] = None
    y_axis_title: Optional[str] = None
    show_x_axis: bool = True
    show_y_axis: bool = True
    show_grid: bool = True
    show_legend: bool = True
    
    # Interactive features
    enable_zoom: bool = True
    enable_pan: bool = True
    enable_tooltips: bool = True
    enable_crosshair: bool = False
    
    # Animation settings
    enable_animations: bool = True
    animation_duration: int = 300
    
    # Data management
    max_data_points: int = 1000
    auto_refresh: bool = False
    refresh_interval_ms: int = 1000
    
    # Export options
    enable_export: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["PNG", "SVG", "CSV"])
    
    # Performance
    enable_data_compression: bool = True
    enable_lazy_loading: bool = True


class BaseChart(ThemeAwareUserControl):
    """
    Base chart component with common functionality.

    Provides foundation for all chart types with:
    - Theme-aware styling and responsive design
    - Common chart operations and data management
    - Interactive features and event handling
    - Performance optimization and caching
    - Export functionality and accessibility
    """

    def __init__(self,
                 chart_type: ChartType,
                 config: Optional[ChartConfig] = None,
                 series: Optional[List[ChartSeries]] = None,
                 on_data_point_click: Optional[Callable] = None,
                 on_data_point_hover: Optional[Callable] = None,
                 **kwargs):
        """
        Initialize base chart component.

        Args:
            chart_type: Type of chart to create
            config: Chart configuration options
            series: Initial data series
            on_data_point_click: Callback for data point clicks
            on_data_point_hover: Callback for data point hover
            **kwargs: Additional arguments for ThemeAwareUserControl
        """
        super().__init__(**kwargs)

        self._chart_type = chart_type
        self._config = config or ChartConfig()
        self._series = series or []
        self._on_data_point_click = on_data_point_click
        self._on_data_point_hover = on_data_point_hover

        # Chart state
        self._is_loading = False
        self._is_updating = False
        self._last_update = None
        self._data_cache = {}
        self._render_cache = {}

        # Interactive state
        self._selected_point = None
        self._hovered_point = None
        self._zoom_level = 1.0
        self._pan_offset = (0, 0)

        # Performance tracking
        self._render_count = 0
        self._last_render_time = 0

        # Chart components
        self._chart_container = None
        self._legend_container = None
        self._tooltip_container = None
        self._toolbar_container = None

        # Auto-refresh timer
        self._refresh_timer = None

    def build(self) -> ft.Control:
        """Build the chart component."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Responsive chart dimensions
        chart_width = self._config.width or rlm.get_breakpoint_value(300, 400, 500, 600)
        chart_height = self._config.height or rlm.get_breakpoint_value(200, 250, 300, 350)

        # Main chart container
        self._chart_container = ft.Container(
            content=self._create_chart_content(),
            width=chart_width,
            height=chart_height,
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders),
            padding=ft.padding.all(spacing.sm)
        )

        # Chart components
        components = [self._chart_container]

        # Add legend if enabled
        if self._config.show_legend and len(self._series) > 1:
            self._legend_container = self._create_legend()
            components.append(self._legend_container)

        # Add toolbar if export is enabled
        if self._config.enable_export:
            self._toolbar_container = self._create_toolbar()
            components.insert(0, self._toolbar_container)

        return ft.Column(
            controls=components,
            spacing=spacing.sm,
            tight=True
        )

    def _create_chart_content(self) -> ft.Control:
        """Create the main chart content - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _create_chart_content")

    def _create_legend(self) -> ft.Control:
        """Create chart legend."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        legend_items = []

        for series in self._series:
            if not series.visible:
                continue

            # Series color indicator
            color_indicator = ft.Container(
                width=12,
                height=12,
                bgcolor=series.color or palette.primary,
                border_radius=ft.border_radius.all(2)
            )

            # Series name
            series_name = ft.Text(
                series.name,
                size=typography.body_small[0],
                color=palette.text_secondary,
                weight=ft.FontWeight.W_400
            )

            # Legend item
            legend_item = ft.Row([
                color_indicator,
                series_name
            ], spacing=spacing.xs, tight=True)

            legend_items.append(legend_item)

        return ft.Container(
            content=ft.Row(
                controls=legend_items,
                spacing=spacing.md,
                wrap=True
            ),
            padding=ft.padding.all(spacing.xs)
        )

    def _create_toolbar(self) -> ft.Control:
        """Create chart toolbar with export and control options."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icon_system()

        toolbar_buttons = []

        # Export button
        if self._config.enable_export:
            export_button = ft.IconButton(
                icon=icons.DOWNLOAD,
                tooltip="Export Chart",
                on_click=self._on_export_click,
                icon_color=palette.text_secondary
            )
            toolbar_buttons.append(export_button)

        # Refresh button for auto-refresh charts
        if self._config.auto_refresh:
            refresh_button = ft.IconButton(
                icon=icons.REFRESH,
                tooltip="Refresh Data",
                on_click=self._on_refresh_click,
                icon_color=palette.text_secondary
            )
            toolbar_buttons.append(refresh_button)

        # Zoom controls for interactive charts
        if self._config.enable_zoom:
            zoom_in_button = ft.IconButton(
                icon=icons.ZOOM_IN,
                tooltip="Zoom In",
                on_click=self._on_zoom_in,
                icon_color=palette.text_secondary
            )
            zoom_out_button = ft.IconButton(
                icon=icons.ZOOM_OUT,
                tooltip="Zoom Out",
                on_click=self._on_zoom_out,
                icon_color=palette.text_secondary
            )
            toolbar_buttons.extend([zoom_in_button, zoom_out_button])

        return ft.Container(
            content=ft.Row(
                controls=toolbar_buttons,
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.END
            ),
            padding=ft.padding.all(spacing.xs)
        )

    def _get_chart_colors(self) -> List[str]:
        """Get color palette for chart series based on theme."""
        palette = self.get_palette()

        if self._config.theme == ChartTheme.PERFORMANCE:
            return [
                palette.success,    # Green for good performance
                palette.warning,    # Yellow for moderate
                palette.error,      # Red for poor performance
                palette.info,       # Blue for neutral
                palette.primary     # Primary for highlights
            ]
        elif self._config.theme == ChartTheme.RESOURCE:
            return [
                "#00C853",  # GPU Green
                "#2196F3",  # CPU Blue
                "#FF9800",  # Memory Orange
                "#9C27B0",  # Disk Purple
                "#F44336"   # Network Red
            ]
        elif self._config.theme == ChartTheme.STATUS:
            return [
                palette.success,    # Success
                palette.warning,    # Warning
                palette.error,      # Error
                palette.info,       # Info
                palette.text_secondary  # Neutral
            ]
        else:  # DEFAULT and others
            return [
                palette.primary,
                palette.secondary,
                palette.success,
                palette.warning,
                palette.error,
                palette.info
            ]

    def _on_export_click(self, e) -> None:
        """Handle export button click."""
        # Implementation would show export dialog
        print(f"Exporting {self._chart_type.value} chart")

    def _on_refresh_click(self, e) -> None:
        """Handle refresh button click."""
        self.refresh_data()

    def _on_zoom_in(self, e) -> None:
        """Handle zoom in action."""
        self._zoom_level = min(self._zoom_level * 1.2, 5.0)
        self._update_chart_display()

    def _on_zoom_out(self, e) -> None:
        """Handle zoom out action."""
        self._zoom_level = max(self._zoom_level / 1.2, 0.2)
        self._update_chart_display()

    def _update_chart_display(self) -> None:
        """Update chart display with current state."""
        if self._chart_container and hasattr(self._chart_container, 'update'):
            self._chart_container.update()

    # Public API methods
    def add_series(self, series: ChartSeries) -> None:
        """Add a new data series to the chart."""
        self._series.append(series)
        self._invalidate_cache()
        self._update_chart_display()

    def remove_series(self, series_name: str) -> bool:
        """Remove a data series by name."""
        for i, series in enumerate(self._series):
            if series.name == series_name:
                del self._series[i]
                self._invalidate_cache()
                self._update_chart_display()
                return True
        return False

    def update_series_data(self, series_name: str, data: List[ChartDataPoint]) -> bool:
        """Update data for an existing series."""
        for series in self._series:
            if series.name == series_name:
                series.data = data
                self._invalidate_cache()
                self._update_chart_display()
                return True
        return False

    def add_data_point(self, series_name: str, data_point: ChartDataPoint) -> bool:
        """Add a single data point to an existing series."""
        for series in self._series:
            if series.name == series_name:
                series.data.append(data_point)

                # Limit data points if configured
                if len(series.data) > self._config.max_data_points:
                    series.data = series.data[-self._config.max_data_points:]

                self._invalidate_cache()
                self._update_chart_display()
                return True
        return False

    def clear_data(self) -> None:
        """Clear all chart data."""
        for series in self._series:
            series.data.clear()
        self._invalidate_cache()
        self._update_chart_display()

    def refresh_data(self) -> None:
        """Refresh chart data - can be overridden by subclasses."""
        self._last_update = datetime.now()
        self._update_chart_display()

    def _invalidate_cache(self) -> None:
        """Invalidate render cache."""
        self._data_cache.clear()
        self._render_cache.clear()


class LineChart(BaseChart):
    """
    Line chart component for time series and continuous data visualization.

    Features:
    - Smooth line rendering with customizable stroke width
    - Multiple series support with different colors
    - Interactive tooltips and data point selection
    - Zoom and pan capabilities for data exploration
    - Real-time data updates with smooth animations
    """

    def __init__(self, **kwargs):
        """Initialize line chart component."""
        super().__init__(chart_type=ChartType.LINE, **kwargs)

    def _create_chart_content(self) -> ft.Control:
        """Create line chart visualization."""
        palette = self.get_palette()
        colors = self._get_chart_colors()

        # Create line chart data series
        chart_data_series = []

        for i, series in enumerate(self._series):
            if not series.visible or not series.data:
                continue

            # Convert data points to Flet format
            data_points = []
            for point in series.data:
                if isinstance(point.x, datetime):
                    x_val = point.x.timestamp()
                else:
                    x_val = float(point.x) if isinstance(point.x, (int, float)) else i

                data_points.append(ft.LineChartDataPoint(x_val, point.y))

            # Create line chart data series
            line_series = ft.LineChartData(
                data_points=data_points,
                stroke_width=series.line_width or 2,
                color=series.color or colors[i % len(colors)],
                curved=True,
                stroke_cap_round=True
            )

            chart_data_series.append(line_series)

        # Create line chart
        line_chart = ft.LineChart(
            data_series=chart_data_series,
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[3, 3]
            ) if self._config.show_grid else None,
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[3, 3]
            ) if self._config.show_grid else None,
            left_axis=ft.ChartAxis(
                title=ft.Text(self._config.y_axis_title or ""),
                title_size=12,
                labels_size=10
            ) if self._config.show_y_axis else None,
            bottom_axis=ft.ChartAxis(
                title=ft.Text(self._config.x_axis_title or ""),
                title_size=12,
                labels_size=10
            ) if self._config.show_x_axis else None,
            tooltip_bgcolor=palette.surface_variant,
            min_y=0,
            max_y=None,  # Auto-scale
            expand=True
        )

        return line_chart


class BarChart(BaseChart):
    """
    Bar chart component for categorical data visualization.

    Features:
    - Vertical and horizontal bar orientations
    - Grouped and stacked bar configurations
    - Customizable bar colors and spacing
    - Interactive tooltips and selection
    - Responsive bar width based on screen size
    """

    def __init__(self, horizontal: bool = False, stacked: bool = False, **kwargs):
        """
        Initialize bar chart component.

        Args:
            horizontal: Whether to display bars horizontally
            stacked: Whether to stack multiple series
            **kwargs: Additional arguments for BaseChart
        """
        chart_type = ChartType.STACKED_BAR if stacked else ChartType.BAR
        super().__init__(chart_type=chart_type, **kwargs)
        self._horizontal = horizontal
        self._stacked = stacked

    def _create_chart_content(self) -> ft.Control:
        """Create bar chart visualization."""
        palette = self.get_palette()
        colors = self._get_chart_colors()
        rlm = self.get_responsive_layout()

        # Responsive bar width
        bar_width = rlm.get_breakpoint_value(20, 25, 30, 35)

        # Create bar chart data
        bar_groups = []

        if not self._series or not any(series.data for series in self._series):
            # Empty state
            return ft.Container(
                content=ft.Text(
                    "No data available",
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        # Group data by x-axis values
        x_values = set()
        for series in self._series:
            for point in series.data:
                x_values.add(str(point.x))

        x_values = sorted(list(x_values))

        for i, x_val in enumerate(x_values):
            bars = []

            for j, series in enumerate(self._series):
                if not series.visible:
                    continue

                # Find data point for this x value
                y_val = 0
                for point in series.data:
                    if str(point.x) == x_val:
                        y_val = point.y
                        break

                bar = ft.BarChartRod(
                    from_y=0,
                    to_y=y_val,
                    width=bar_width,
                    color=series.color or colors[j % len(colors)],
                    tooltip=f"{series.name}: {y_val}",
                    border_radius=ft.border_radius.vertical(top=4)
                )
                bars.append(bar)

            bar_group = ft.BarChartGroup(
                x=i,
                bar_rods=bars
            )
            bar_groups.append(bar_group)

        # Create bar chart
        bar_chart = ft.BarChart(
            bar_groups=bar_groups,
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[3, 3]
            ) if self._config.show_grid else None,
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[3, 3]
            ) if self._config.show_grid else None,
            left_axis=ft.ChartAxis(
                title=ft.Text(self._config.y_axis_title or ""),
                title_size=12,
                labels_size=10
            ) if self._config.show_y_axis else None,
            bottom_axis=ft.ChartAxis(
                title=ft.Text(self._config.x_axis_title or ""),
                title_size=12,
                labels_size=10,
                labels=[ft.ChartAxisLabel(value=i, label=ft.Text(x_val))
                       for i, x_val in enumerate(x_values)]
            ) if self._config.show_x_axis else None,
            tooltip_bgcolor=palette.surface_variant,
            min_y=0,
            max_y=None,  # Auto-scale
            expand=True
        )

        return bar_chart


class AreaChart(BaseChart):
    """
    Area chart component for filled area visualization.

    Features:
    - Filled area rendering with gradient support
    - Stacked area charts for multiple series
    - Smooth curve interpolation
    - Interactive tooltips and data exploration
    - Transparency control for overlapping areas
    """

    def __init__(self, stacked: bool = False, **kwargs):
        """
        Initialize area chart component.

        Args:
            stacked: Whether to stack multiple series
            **kwargs: Additional arguments for BaseChart
        """
        chart_type = ChartType.STACKED_AREA if stacked else ChartType.AREA
        super().__init__(chart_type=chart_type, **kwargs)
        self._stacked = stacked

    def _create_chart_content(self) -> ft.Control:
        """Create area chart visualization."""
        palette = self.get_palette()
        colors = self._get_chart_colors()

        # Create line chart with filled areas
        chart_data_series = []

        for i, series in enumerate(self._series):
            if not series.visible or not series.data:
                continue

            # Convert data points to Flet format
            data_points = []
            for point in series.data:
                if isinstance(point.x, datetime):
                    x_val = point.x.timestamp()
                else:
                    x_val = float(point.x) if isinstance(point.x, (int, float)) else i

                data_points.append(ft.LineChartDataPoint(x_val, point.y))

            # Create area chart data series
            area_series = ft.LineChartData(
                data_points=data_points,
                stroke_width=series.line_width or 1,
                color=series.color or colors[i % len(colors)],
                curved=True,
                stroke_cap_round=True,
                below_line_bgcolor=f"{series.color or colors[i % len(colors)]}40",  # 25% opacity
                below_line_cutoff_y=0,
                is_stroke_cap_round=True
            )

            chart_data_series.append(area_series)

        # Create area chart (using LineChart with fill)
        area_chart = ft.LineChart(
            data_series=chart_data_series,
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[3, 3]
            ) if self._config.show_grid else None,
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[3, 3]
            ) if self._config.show_grid else None,
            left_axis=ft.ChartAxis(
                title=ft.Text(self._config.y_axis_title or ""),
                title_size=12,
                labels_size=10
            ) if self._config.show_y_axis else None,
            bottom_axis=ft.ChartAxis(
                title=ft.Text(self._config.x_axis_title or ""),
                title_size=12,
                labels_size=10
            ) if self._config.show_x_axis else None,
            tooltip_bgcolor=palette.surface_variant,
            min_y=0,
            max_y=None,  # Auto-scale
            expand=True
        )

        return area_chart


class PieChart(BaseChart):
    """
    Pie chart component for proportional data visualization.

    Features:
    - Circular pie chart with customizable segments
    - Donut chart variant with center hole
    - Interactive segment selection and highlighting
    - Percentage labels and value tooltips
    - Responsive sizing and legend integration
    """

    def __init__(self, donut: bool = False, **kwargs):
        """
        Initialize pie chart component.

        Args:
            donut: Whether to display as donut chart
            **kwargs: Additional arguments for BaseChart
        """
        super().__init__(chart_type=ChartType.PIE, **kwargs)
        self._donut = donut

    def _create_chart_content(self) -> ft.Control:
        """Create pie chart visualization."""
        palette = self.get_palette()
        colors = self._get_chart_colors()
        rlm = self.get_responsive_layout()

        if not self._series or not any(series.data for series in self._series):
            # Empty state
            return ft.Container(
                content=ft.Text(
                    "No data available",
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        # Use first series for pie chart data
        series = next((s for s in self._series if s.visible and s.data), None)
        if not series:
            return ft.Container()

        # Calculate total for percentages
        total = sum(point.y for point in series.data)

        # Create pie chart sections
        sections = []
        for i, point in enumerate(series.data):
            percentage = (point.y / total) * 100 if total > 0 else 0

            section = ft.PieChartSection(
                value=point.y,
                title=f"{percentage:.1f}%",
                title_style=ft.TextStyle(
                    size=12,
                    color=palette.text_primary,
                    weight=ft.FontWeight.BOLD
                ),
                color=point.color or colors[i % len(colors)],
                radius=rlm.get_breakpoint_value(60, 70, 80, 90),
                title_position_percentage_offset=0.55
            )
            sections.append(section)

        # Create pie chart
        pie_chart = ft.PieChart(
            sections=sections,
            sections_space=2,
            center_space_radius=30 if self._donut else 0,
            expand=True
        )

        return ft.Container(
            content=pie_chart,
            alignment=ft.alignment.center,
            expand=True
        )


class GaugeChart(BaseChart):
    """
    Gauge chart component for single value visualization with thresholds.

    Features:
    - Circular gauge with customizable ranges
    - Color-coded threshold zones
    - Animated needle movement
    - Value display with units
    - Configurable min/max ranges
    """

    def __init__(self,
                 min_value: float = 0,
                 max_value: float = 100,
                 current_value: float = 0,
                 unit: str = "",
                 thresholds: Optional[List[Tuple[float, str]]] = None,
                 **kwargs):
        """
        Initialize gauge chart component.

        Args:
            min_value: Minimum gauge value
            max_value: Maximum gauge value
            current_value: Current gauge value
            unit: Value unit (e.g., "%", "MB/s")
            thresholds: List of (value, color) threshold tuples
            **kwargs: Additional arguments for BaseChart
        """
        super().__init__(chart_type=ChartType.GAUGE, **kwargs)
        self._min_value = min_value
        self._max_value = max_value
        self._current_value = current_value
        self._unit = unit
        self._thresholds = thresholds or []

    def _create_chart_content(self) -> ft.Control:
        """Create gauge chart visualization."""
        palette = self.get_palette()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        # Calculate value ratio
        value_ratio = (self._current_value - self._min_value) / (self._max_value - self._min_value)
        value_ratio = max(0, min(1, value_ratio))

        # Determine gauge color based on thresholds
        gauge_color = palette.primary
        for threshold_value, threshold_color in self._thresholds:
            if self._current_value >= threshold_value:
                gauge_color = threshold_color

        # Responsive gauge size
        gauge_size = rlm.get_breakpoint_value(120, 140, 160, 180)

        # Create circular progress indicator
        progress_ring = ft.ProgressRing(
            value=value_ratio,
            color=gauge_color,
            bgcolor=f"{palette.borders}40",
            stroke_width=rlm.get_breakpoint_value(8, 10, 12, 14),
            width=gauge_size,
            height=gauge_size
        )

        # Value display
        value_text = ft.Text(
            f"{self._current_value:.1f}{self._unit}",
            size=typography.h4[0],
            weight=ft.FontWeight.BOLD,
            color=palette.text_primary,
            text_align=ft.TextAlign.CENTER
        )

        # Min/Max labels
        min_label = ft.Text(
            f"{self._min_value}{self._unit}",
            size=typography.caption[0],
            color=palette.text_secondary
        )

        max_label = ft.Text(
            f"{self._max_value}{self._unit}",
            size=typography.caption[0],
            color=palette.text_secondary
        )

        # Stack components
        gauge_stack = ft.Stack([
            progress_ring,
            ft.Container(
                content=value_text,
                alignment=ft.alignment.center,
                width=gauge_size,
                height=gauge_size
            )
        ])

        # Labels row
        labels_row = ft.Row([
            min_label,
            max_label
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        return ft.Column([
            ft.Container(
                content=gauge_stack,
                alignment=ft.alignment.center
            ),
            labels_row
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)

    def update_value(self, value: float) -> None:
        """Update gauge value."""
        self._current_value = max(self._min_value, min(self._max_value, value))
        self._update_chart_display()


class SparklineChart(BaseChart):
    """
    Sparkline chart component for compact trend visualization.

    Features:
    - Minimal line chart without axes or labels
    - Compact size for embedding in cards or tables
    - Trend indication with color coding
    - Optional final value display
    - Responsive sizing for different contexts
    """

    def __init__(self, show_final_value: bool = True, **kwargs):
        """
        Initialize sparkline chart component.

        Args:
            show_final_value: Whether to show the final value
            **kwargs: Additional arguments for BaseChart
        """
        super().__init__(chart_type=ChartType.SPARKLINE, **kwargs)
        self._show_final_value = show_final_value

        # Override config for sparkline
        self._config.show_x_axis = False
        self._config.show_y_axis = False
        self._config.show_grid = False
        self._config.show_legend = False
        self._config.enable_zoom = False
        self._config.enable_export = False

    def _create_chart_content(self) -> ft.Control:
        """Create sparkline chart visualization."""
        palette = self.get_palette()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        if not self._series or not any(series.data for series in self._series):
            return ft.Container(
                width=rlm.get_breakpoint_value(60, 80, 100, 120),
                height=rlm.get_breakpoint_value(20, 25, 30, 35)
            )

        # Use first series
        series = next((s for s in self._series if s.visible and s.data), None)
        if not series:
            return ft.Container()

        # Convert data points
        data_points = []
        for i, point in enumerate(series.data):
            data_points.append(ft.LineChartDataPoint(i, point.y))

        # Determine trend color
        if len(series.data) >= 2:
            trend = series.data[-1].y - series.data[0].y
            line_color = palette.success if trend >= 0 else palette.error
        else:
            line_color = palette.primary

        # Create minimal line chart
        sparkline = ft.LineChart(
            data_series=[ft.LineChartData(
                data_points=data_points,
                stroke_width=2,
                color=line_color,
                curved=True,
                prevent_curve_over_shooting=True
            )],
            border=ft.border.all(0, ft.Colors.TRANSPARENT),
            horizontal_grid_lines=None,
            vertical_grid_lines=None,
            left_axis=None,
            bottom_axis=None,
            tooltip_bgcolor=palette.surface_variant,
            min_y=None,  # Auto-scale
            max_y=None,  # Auto-scale
            expand=True
        )

        components = [sparkline]

        # Add final value if enabled
        if self._show_final_value and series.data:
            final_value = ft.Text(
                f"{series.data[-1].y:.1f}",
                size=typography.caption[0],
                color=line_color,
                weight=ft.FontWeight.W_500
            )
            components.append(final_value)

        return ft.Column(
            controls=components,
            spacing=2,
            tight=True
        )


class HeatmapChart(BaseChart):
    """
    Heatmap chart component for matrix data visualization.

    Features:
    - Color-coded matrix visualization
    - Customizable color scales and ranges
    - Interactive cell selection and tooltips
    - Responsive grid sizing
    - Value labels and color legend
    """

    def __init__(self,
                 rows: List[str],
                 columns: List[str],
                 values: List[List[float]],
                 **kwargs):
        """
        Initialize heatmap chart component.

        Args:
            rows: Row labels
            columns: Column labels
            values: 2D array of values
            **kwargs: Additional arguments for BaseChart
        """
        super().__init__(chart_type=ChartType.HEATMAP, **kwargs)
        self._rows = rows
        self._columns = columns
        self._values = values

    def _create_chart_content(self) -> ft.Control:
        """Create heatmap chart visualization."""
        palette = self.get_palette()
        typography = self.get_typography()
        rlm = self.get_responsive_layout()

        if not self._values or not self._rows or not self._columns:
            return ft.Container(
                content=ft.Text(
                    "No data available",
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        # Calculate value range for color mapping
        all_values = [val for row in self._values for val in row]
        min_val = min(all_values) if all_values else 0
        max_val = max(all_values) if all_values else 1
        value_range = max_val - min_val if max_val != min_val else 1

        # Responsive cell size
        cell_size = rlm.get_breakpoint_value(30, 35, 40, 45)

        # Create heatmap grid
        grid_rows = []

        for i, row_label in enumerate(self._rows):
            grid_cells = []

            # Row label
            row_label_cell = ft.Container(
                content=ft.Text(
                    row_label,
                    size=typography.caption[0],
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.RIGHT
                ),
                width=cell_size * 2,
                height=cell_size,
                alignment=ft.alignment.center_right,
                padding=ft.padding.only(right=8)
            )
            grid_cells.append(row_label_cell)

            # Data cells
            for j, col_label in enumerate(self._columns):
                if i < len(self._values) and j < len(self._values[i]):
                    value = self._values[i][j]

                    # Calculate color intensity
                    intensity = (value - min_val) / value_range

                    # Create color based on intensity
                    if intensity < 0.5:
                        # Blue to white
                        alpha = int(255 * (1 - intensity * 2))
                        cell_color = f"rgba(33, 150, 243, {alpha/255:.2f})"
                    else:
                        # White to red
                        alpha = int(255 * ((intensity - 0.5) * 2))
                        cell_color = f"rgba(244, 67, 54, {alpha/255:.2f})"

                    cell = ft.Container(
                        content=ft.Text(
                            f"{value:.1f}",
                            size=typography.caption[0],
                            color=palette.text_primary,
                            text_align=ft.TextAlign.CENTER
                        ),
                        width=cell_size,
                        height=cell_size,
                        bgcolor=cell_color,
                        border=ft.border.all(1, palette.borders),
                        alignment=ft.alignment.center,
                        tooltip=f"{row_label} - {col_label}: {value:.2f}"
                    )
                else:
                    cell = ft.Container(
                        width=cell_size,
                        height=cell_size,
                        bgcolor=palette.surface_variant,
                        border=ft.border.all(1, palette.borders)
                    )

                grid_cells.append(cell)

            grid_row = ft.Row(controls=grid_cells, spacing=0)
            grid_rows.append(grid_row)

        # Column headers
        header_cells = [ft.Container(width=cell_size * 2, height=cell_size)]  # Empty corner
        for col_label in self._columns:
            header_cell = ft.Container(
                content=ft.Text(
                    col_label,
                    size=typography.caption[0],
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                ),
                width=cell_size,
                height=cell_size,
                alignment=ft.alignment.center,
                padding=ft.padding.all(4)
            )
            header_cells.append(header_cell)

        header_row = ft.Row(controls=header_cells, spacing=0)

        return ft.Column([
            header_row,
            *grid_rows
        ], spacing=0)


class ScatterChart(BaseChart):
    """
    Scatter chart component for correlation and distribution visualization.

    Features:
    - Point-based data visualization
    - Customizable point sizes and colors
    - Trend line overlay options
    - Interactive point selection
    - Zoom and pan capabilities
    """

    def __init__(self, **kwargs):
        """Initialize scatter chart component."""
        super().__init__(chart_type=ChartType.SCATTER, **kwargs)

    def _create_chart_content(self) -> ft.Control:
        """Create scatter chart visualization."""
        palette = self.get_palette()
        colors = self._get_chart_colors()

        # Create scatter plot using line chart with points only
        chart_data_series = []

        for i, series in enumerate(self._series):
            if not series.visible or not series.data:
                continue

            # Convert data points to Flet format
            data_points = []
            for point in series.data:
                if isinstance(point.x, datetime):
                    x_val = point.x.timestamp()
                else:
                    x_val = float(point.x) if isinstance(point.x, (int, float)) else i

                data_points.append(ft.LineChartDataPoint(x_val, point.y))

            # Create scatter series (line chart with dots only)
            scatter_series = ft.LineChartData(
                data_points=data_points,
                stroke_width=0,  # No line
                color=series.color or colors[i % len(colors)],
                dotted_line=False,
                show_dots=True,
                dot_data=ft.LineChartDotData(
                    show=True,
                    dot_size=6,
                    dot_color=series.color or colors[i % len(colors)],
                    stroke_width=2,
                    stroke_color=palette.surface
                )
            )

            chart_data_series.append(scatter_series)

        # Create scatter chart
        scatter_chart = ft.LineChart(
            data_series=chart_data_series,
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[3, 3]
            ) if self._config.show_grid else None,
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[3, 3]
            ) if self._config.show_grid else None,
            left_axis=ft.ChartAxis(
                title=ft.Text(self._config.y_axis_title or ""),
                title_size=12,
                labels_size=10
            ) if self._config.show_y_axis else None,
            bottom_axis=ft.ChartAxis(
                title=ft.Text(self._config.x_axis_title or ""),
                title_size=12,
                labels_size=10
            ) if self._config.show_x_axis else None,
            tooltip_bgcolor=palette.surface_variant,
            min_y=None,  # Auto-scale
            max_y=None,  # Auto-scale
            expand=True
        )

        return scatter_chart


class ChartComponentsUI(ThemeAwareUserControl):
    """
    Main chart components UI manager.

    Provides a unified interface for creating and managing different chart types
    with consistent theming, responsive design, and interactive features.

    Features:
    - Factory methods for all chart types
    - Centralized theme and configuration management
    - Chart collection and dashboard creation
    - Performance monitoring and optimization
    - Export and data management utilities
    """

    def __init__(self, **kwargs):
        """Initialize chart components UI manager."""
        super().__init__(**kwargs)

        self._charts: Dict[str, BaseChart] = {}
        self._default_config = ChartConfig()
        self._performance_metrics = {
            'charts_created': 0,
            'charts_updated': 0,
            'render_time_total': 0,
            'last_render_time': 0
        }

    def build(self) -> ft.Control:
        """Build the chart components UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Chart components showcase/demo
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Chart Components",
                    size=typography.h2[0],
                    weight=ft.FontWeight.BOLD,
                    color=palette.text_primary
                ),
                ft.Text(
                    "Reusable chart components for metrics and visualization",
                    size=typography.body_medium[0],
                    color=palette.text_secondary
                ),
                ft.Divider(color=palette.borders),
                self._create_chart_gallery()
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.lg)
        )

    def _create_chart_gallery(self) -> ft.Control:
        """Create a gallery of chart examples."""
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Sample data for demonstrations
        sample_data = [
            ChartDataPoint(x=i, y=50 + 30 * math.sin(i * 0.5) + 10 * math.cos(i * 0.3))
            for i in range(20)
        ]

        sample_series = ChartSeries(name="Sample Data", data=sample_data)

        # Create example charts
        charts = []

        # Line chart example
        line_chart = self.create_line_chart(
            series=[sample_series],
            config=ChartConfig(
                title="Line Chart Example",
                width=rlm.get_breakpoint_value(300, 350, 400, 450),
                height=200
            )
        )
        charts.append(line_chart)

        # Bar chart example
        bar_data = [
            ChartDataPoint(x="A", y=25),
            ChartDataPoint(x="B", y=45),
            ChartDataPoint(x="C", y=35),
            ChartDataPoint(x="D", y=55)
        ]
        bar_series = ChartSeries(name="Categories", data=bar_data)
        bar_chart = self.create_bar_chart(
            series=[bar_series],
            config=ChartConfig(
                title="Bar Chart Example",
                width=rlm.get_breakpoint_value(300, 350, 400, 450),
                height=200
            )
        )
        charts.append(bar_chart)

        # Gauge chart example
        gauge_chart = self.create_gauge_chart(
            current_value=75,
            min_value=0,
            max_value=100,
            unit="%",
            thresholds=[(60, "#4CAF50"), (80, "#FF9800"), (90, "#F44336")]
        )
        charts.append(gauge_chart)

        # Sparkline example
        sparkline = self.create_sparkline_chart(
            series=[sample_series]
        )
        charts.append(sparkline)

        # Responsive grid layout
        columns = rlm.get_breakpoint_value(1, 2, 2, 3)

        return ft.GridView(
            controls=charts,
            runs_count=columns,
            max_extent=rlm.get_breakpoint_value(350, 400, 450, 500),
            child_aspect_ratio=1.2,
            spacing=spacing.md,
            run_spacing=spacing.md,
            expand=True
        )

    # Factory methods for creating charts
    def create_line_chart(self,
                         series: List[ChartSeries],
                         config: Optional[ChartConfig] = None,
                         chart_id: Optional[str] = None,
                         **kwargs) -> LineChart:
        """
        Create a line chart component.

        Args:
            series: Data series for the chart
            config: Chart configuration
            chart_id: Unique identifier for the chart
            **kwargs: Additional arguments

        Returns:
            LineChart component
        """
        chart_config = config or self._default_config
        chart = LineChart(config=chart_config, series=series, **kwargs)

        if chart_id:
            self._charts[chart_id] = chart

        self._performance_metrics['charts_created'] += 1
        return chart

    def create_bar_chart(self,
                        series: List[ChartSeries],
                        config: Optional[ChartConfig] = None,
                        chart_id: Optional[str] = None,
                        horizontal: bool = False,
                        stacked: bool = False,
                        **kwargs) -> BarChart:
        """
        Create a bar chart component.

        Args:
            series: Data series for the chart
            config: Chart configuration
            chart_id: Unique identifier for the chart
            horizontal: Whether to display bars horizontally
            stacked: Whether to stack multiple series
            **kwargs: Additional arguments

        Returns:
            BarChart component
        """
        chart_config = config or self._default_config
        chart = BarChart(
            config=chart_config,
            series=series,
            horizontal=horizontal,
            stacked=stacked,
            **kwargs
        )

        if chart_id:
            self._charts[chart_id] = chart

        self._performance_metrics['charts_created'] += 1
        return chart

    def create_area_chart(self,
                         series: List[ChartSeries],
                         config: Optional[ChartConfig] = None,
                         chart_id: Optional[str] = None,
                         stacked: bool = False,
                         **kwargs) -> AreaChart:
        """
        Create an area chart component.

        Args:
            series: Data series for the chart
            config: Chart configuration
            chart_id: Unique identifier for the chart
            stacked: Whether to stack multiple series
            **kwargs: Additional arguments

        Returns:
            AreaChart component
        """
        chart_config = config or self._default_config
        chart = AreaChart(
            config=chart_config,
            series=series,
            stacked=stacked,
            **kwargs
        )

        if chart_id:
            self._charts[chart_id] = chart

        self._performance_metrics['charts_created'] += 1
        return chart

    def create_pie_chart(self,
                        series: List[ChartSeries],
                        config: Optional[ChartConfig] = None,
                        chart_id: Optional[str] = None,
                        donut: bool = False,
                        **kwargs) -> PieChart:
        """
        Create a pie chart component.

        Args:
            series: Data series for the chart
            config: Chart configuration
            chart_id: Unique identifier for the chart
            donut: Whether to display as donut chart
            **kwargs: Additional arguments

        Returns:
            PieChart component
        """
        chart_config = config or self._default_config
        chart = PieChart(
            config=chart_config,
            series=series,
            donut=donut,
            **kwargs
        )

        if chart_id:
            self._charts[chart_id] = chart

        self._performance_metrics['charts_created'] += 1
        return chart

    def create_gauge_chart(self,
                          current_value: float,
                          min_value: float = 0,
                          max_value: float = 100,
                          unit: str = "",
                          thresholds: Optional[List[Tuple[float, str]]] = None,
                          config: Optional[ChartConfig] = None,
                          chart_id: Optional[str] = None,
                          **kwargs) -> GaugeChart:
        """
        Create a gauge chart component.

        Args:
            current_value: Current gauge value
            min_value: Minimum gauge value
            max_value: Maximum gauge value
            unit: Value unit
            thresholds: List of (value, color) threshold tuples
            config: Chart configuration
            chart_id: Unique identifier for the chart
            **kwargs: Additional arguments

        Returns:
            GaugeChart component
        """
        chart_config = config or self._default_config
        chart = GaugeChart(
            config=chart_config,
            min_value=min_value,
            max_value=max_value,
            current_value=current_value,
            unit=unit,
            thresholds=thresholds,
            **kwargs
        )

        if chart_id:
            self._charts[chart_id] = chart

        self._performance_metrics['charts_created'] += 1
        return chart

    def create_sparkline_chart(self,
                              series: List[ChartSeries],
                              config: Optional[ChartConfig] = None,
                              chart_id: Optional[str] = None,
                              show_final_value: bool = True,
                              **kwargs) -> SparklineChart:
        """
        Create a sparkline chart component.

        Args:
            series: Data series for the chart
            config: Chart configuration
            chart_id: Unique identifier for the chart
            show_final_value: Whether to show the final value
            **kwargs: Additional arguments

        Returns:
            SparklineChart component
        """
        chart_config = config or self._default_config
        chart = SparklineChart(
            config=chart_config,
            series=series,
            show_final_value=show_final_value,
            **kwargs
        )

        if chart_id:
            self._charts[chart_id] = chart

        self._performance_metrics['charts_created'] += 1
        return chart

    def create_heatmap_chart(self,
                            rows: List[str],
                            columns: List[str],
                            values: List[List[float]],
                            config: Optional[ChartConfig] = None,
                            chart_id: Optional[str] = None,
                            **kwargs) -> HeatmapChart:
        """
        Create a heatmap chart component.

        Args:
            rows: Row labels
            columns: Column labels
            values: 2D array of values
            config: Chart configuration
            chart_id: Unique identifier for the chart
            **kwargs: Additional arguments

        Returns:
            HeatmapChart component
        """
        chart_config = config or self._default_config
        chart = HeatmapChart(
            config=chart_config,
            rows=rows,
            columns=columns,
            values=values,
            **kwargs
        )

        if chart_id:
            self._charts[chart_id] = chart

        self._performance_metrics['charts_created'] += 1
        return chart

    def create_scatter_chart(self,
                            series: List[ChartSeries],
                            config: Optional[ChartConfig] = None,
                            chart_id: Optional[str] = None,
                            **kwargs) -> ScatterChart:
        """
        Create a scatter chart component.

        Args:
            series: Data series for the chart
            config: Chart configuration
            chart_id: Unique identifier for the chart
            **kwargs: Additional arguments

        Returns:
            ScatterChart component
        """
        chart_config = config or self._default_config
        chart = ScatterChart(
            config=chart_config,
            series=series,
            **kwargs
        )

        if chart_id:
            self._charts[chart_id] = chart

        self._performance_metrics['charts_created'] += 1
        return chart

    # Chart management methods
    def get_chart(self, chart_id: str) -> Optional[BaseChart]:
        """Get a chart by ID."""
        return self._charts.get(chart_id)

    def remove_chart(self, chart_id: str) -> bool:
        """Remove a chart by ID."""
        if chart_id in self._charts:
            del self._charts[chart_id]
            return True
        return False

    def clear_charts(self) -> None:
        """Clear all managed charts."""
        self._charts.clear()

    def get_chart_count(self) -> int:
        """Get the number of managed charts."""
        return len(self._charts)

    def update_all_charts(self) -> None:
        """Update all managed charts."""
        for chart in self._charts.values():
            chart.refresh_data()
        self._performance_metrics['charts_updated'] += len(self._charts)

    # Configuration management
    def set_default_config(self, config: ChartConfig) -> None:
        """Set the default configuration for new charts."""
        self._default_config = config

    def get_default_config(self) -> ChartConfig:
        """Get the default configuration."""
        return self._default_config

    def apply_theme_to_all_charts(self, theme: ChartTheme) -> None:
        """Apply a theme to all managed charts."""
        for chart in self._charts.values():
            chart._config.theme = theme
            chart._update_chart_display()

    # Performance and analytics
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for chart operations."""
        return self._performance_metrics.copy()

    def reset_performance_metrics(self) -> None:
        """Reset performance metrics."""
        self._performance_metrics = {
            'charts_created': 0,
            'charts_updated': 0,
            'render_time_total': 0,
            'last_render_time': 0
        }

    # Utility methods
    @staticmethod
    def create_sample_data(count: int = 20,
                          trend: str = "random",
                          base_value: float = 50,
                          amplitude: float = 30) -> List[ChartDataPoint]:
        """
        Create sample data for testing and demonstrations.

        Args:
            count: Number of data points
            trend: Trend type ("random", "increasing", "decreasing", "sine")
            base_value: Base value for data points
            amplitude: Amplitude for variations

        Returns:
            List of sample data points
        """
        import random

        data_points = []

        for i in range(count):
            if trend == "increasing":
                y = base_value + (i * amplitude / count) + random.uniform(-5, 5)
            elif trend == "decreasing":
                y = base_value - (i * amplitude / count) + random.uniform(-5, 5)
            elif trend == "sine":
                y = base_value + amplitude * math.sin(i * 0.5) + random.uniform(-5, 5)
            else:  # random
                y = base_value + random.uniform(-amplitude, amplitude)

            data_points.append(ChartDataPoint(x=i, y=max(0, y)))

        return data_points

    @staticmethod
    def create_time_series_data(start_time: datetime,
                               duration_hours: int = 24,
                               interval_minutes: int = 60,
                               trend: str = "random",
                               base_value: float = 50,
                               amplitude: float = 30) -> List[ChartDataPoint]:
        """
        Create time series sample data.

        Args:
            start_time: Start time for the series
            duration_hours: Duration in hours
            interval_minutes: Interval between points in minutes
            trend: Trend type
            base_value: Base value for data points
            amplitude: Amplitude for variations

        Returns:
            List of time series data points
        """
        import random

        data_points = []
        current_time = start_time
        end_time = start_time + timedelta(hours=duration_hours)
        point_count = 0

        while current_time <= end_time:
            if trend == "increasing":
                y = base_value + (point_count * amplitude / 100) + random.uniform(-5, 5)
            elif trend == "decreasing":
                y = base_value - (point_count * amplitude / 100) + random.uniform(-5, 5)
            elif trend == "sine":
                y = base_value + amplitude * math.sin(point_count * 0.1) + random.uniform(-5, 5)
            else:  # random
                y = base_value + random.uniform(-amplitude, amplitude)

            data_points.append(ChartDataPoint(x=current_time, y=max(0, y)))
            current_time += timedelta(minutes=interval_minutes)
            point_count += 1

        return data_points

    def export_chart_data(self, chart_id: str, format: str = "CSV") -> Optional[str]:
        """
        Export chart data in specified format.

        Args:
            chart_id: ID of the chart to export
            format: Export format ("CSV", "JSON")

        Returns:
            Exported data as string or None if chart not found
        """
        chart = self.get_chart(chart_id)
        if not chart:
            return None

        if format.upper() == "CSV":
            lines = ["Series,X,Y,Label"]
            for series in chart._series:
                for point in series.data:
                    lines.append(f"{series.name},{point.x},{point.y},{point.label or ''}")
            return "\n".join(lines)

        elif format.upper() == "JSON":
            data = {
                "chart_type": chart._chart_type.value,
                "series": []
            }
            for series in chart._series:
                series_data = {
                    "name": series.name,
                    "data": [
                        {
                            "x": str(point.x),
                            "y": point.y,
                            "label": point.label,
                            "metadata": point.metadata
                        }
                        for point in series.data
                    ],
                    "color": series.color,
                    "visible": series.visible,
                    "metadata": series.metadata
                }
                data["series"].append(series_data)

            return json.dumps(data, indent=2)

        return None
