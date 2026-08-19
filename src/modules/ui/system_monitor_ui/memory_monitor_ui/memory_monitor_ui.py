"""
Module: memory_monitor_ui
Description: Memory usage monitoring with real-time charts, pressure indicators, and allocation tracking
Phase: 2
Location: /src/modules/ui/system_monitor_ui/memory_monitor_ui/
"""

# Standard library imports
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.resource_monitor_lg.memory_monitor_lg.memory_monitor_lg import (
    MemoryMonitor, MemoryMetrics, MemoryType, AllocationPattern
)


class MemoryDisplayMode(Enum):
    """Memory display modes."""
    OVERVIEW = "overview"
    DETAILED = "detailed"
    PRESSURE = "pressure"
    ALLOCATION = "allocation"


@dataclass
class MemoryAlertThreshold:
    """Memory alert thresholds."""
    warning_percent: float = 80.0
    critical_percent: float = 90.0
    pressure_warning: float = 0.7
    pressure_critical: float = 0.9
    allocation_rate_warning: float = 100.0  # MB/s
    allocation_rate_critical: float = 500.0  # MB/s


@dataclass
class MemoryMonitorConfiguration:
    """Configuration for memory monitor."""
    refresh_interval_seconds: float = 1.0
    history_minutes: int = 10
    show_swap_usage: bool = True
    show_process_memory: bool = True
    show_pressure_indicators: bool = True
    show_allocation_patterns: bool = True
    display_mode: MemoryDisplayMode = MemoryDisplayMode.OVERVIEW
    alert_thresholds: MemoryAlertThreshold = None

    def __post_init__(self):
        if self.alert_thresholds is None:
            self.alert_thresholds = MemoryAlertThreshold()


@dataclass
class MemoryDataPoint:
    """Memory data point for charts."""
    timestamp: datetime
    total_ram_mb: int
    used_ram_mb: int
    available_ram_mb: int
    cached_mb: int
    buffers_mb: int
    usage_percent: float
    swap_used_mb: int
    swap_total_mb: int
    swap_percent: float
    pressure_score: float
    allocation_rate: float
    deallocation_rate: float


class MemoryMetricsPanel(ThemeAwareUserControl):
    """Memory metrics display panel."""
    
    def __init__(self, metrics: Optional[MemoryMetrics] = None):
        super().__init__()
        self._metrics = metrics
        
    def build(self) -> ft.Control:
        """Build the metrics panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        
        if not self._metrics:
            return ft.Container(
                content=ft.Text(
                    "No memory data available",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface_variant
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(spacing.sm)
            )
        
        # Create metric cards
        ram_card = self._create_metric_card(
            "RAM Usage",
            f"{self._metrics.used_ram_mb:,} MB",
            f"{self._metrics.usage_percent:.1f}%",
            f"of {self._metrics.total_ram_mb:,} MB",
            self._get_usage_color(self._metrics.usage_percent)
        )
        
        swap_card = self._create_metric_card(
            "Swap Usage",
            f"{self._metrics.swap_info.used_mb:,} MB",
            f"{self._metrics.swap_info.usage_percent:.1f}%",
            f"of {self._metrics.swap_info.total_mb:,} MB",
            self._get_usage_color(self._metrics.swap_info.usage_percent)
        )
        
        pressure_card = self._create_metric_card(
            "Memory Pressure",
            f"{self._metrics.memory_pressure_score:.2f}",
            self._get_pressure_level(self._metrics.memory_pressure_score),
            "Pressure Score",
            self._get_pressure_color(self._metrics.memory_pressure_score)
        )
        
        allocation_card = self._create_metric_card(
            "Allocation Rate",
            f"{self._metrics.allocation_rate_mb_per_sec:.1f} MB/s",
            f"↓ {self._metrics.deallocation_rate_mb_per_sec:.1f} MB/s",
            "Alloc / Dealloc",
            palette.primary
        )
        
        return ft.Container(
            content=ft.ResponsiveRow([
                ft.Col(ram_card, xs=12, sm=6, md=3, lg=3),
                ft.Col(swap_card, xs=12, sm=6, md=3, lg=3),
                ft.Col(pressure_card, xs=12, sm=6, md=3, lg=3),
                ft.Col(allocation_card, xs=12, sm=6, md=3, lg=3)
            ]),
            padding=ft.padding.all(spacing.md)
        )
    
    def _create_metric_card(self, title: str, value: str, 
                           secondary: str, subtitle: str, 
                           accent_color: str) -> ft.Container:
        """Create a metric card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        title,
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    ),
                    ft.Container(
                        width=4,
                        height=20,
                        bgcolor=accent_color,
                        border_radius=ft.border_radius.all(2)
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(
                    value,
                    style=self.get_text_style('h3'),
                    color=palette.on_surface,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text(
                    secondary,
                    style=self.get_text_style('body_medium'),
                    color=accent_color,
                    weight=ft.FontWeight.W_500
                ),
                ft.Text(
                    subtitle,
                    style=self.get_text_style('caption'),
                    color=palette.on_surface_variant
                )
            ], spacing=spacing.xs, tight=True),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.outline_variant)
        )
    
    def _get_usage_color(self, percent: float) -> str:
        """Get color based on usage percentage."""
        palette = self.get_palette()
        if percent >= 90:
            return palette.error
        elif percent >= 80:
            return palette.warning
        else:
            return palette.primary
    
    def _get_pressure_color(self, pressure: float) -> str:
        """Get color based on pressure score."""
        palette = self.get_palette()
        if pressure >= 0.9:
            return palette.error
        elif pressure >= 0.7:
            return palette.warning
        else:
            return palette.success
    
    def _get_pressure_level(self, pressure: float) -> str:
        """Get pressure level description."""
        if pressure >= 0.9:
            return "Critical"
        elif pressure >= 0.7:
            return "High"
        elif pressure >= 0.4:
            return "Medium"
        else:
            return "Low"
    
    def update_metrics(self, metrics: MemoryMetrics):
        """Update displayed metrics."""
        self._metrics = metrics
        self.update()


class MemoryUsageChart(ThemeAwareUserControl):
    """Memory usage chart component."""
    
    def __init__(self, data_points: List[MemoryDataPoint]):
        super().__init__()
        self._data_points = data_points
        self._chart_height = 300
        
    def build(self) -> ft.Control:
        """Build the usage chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        if not self._data_points:
            return ft.Container(
                content=ft.Text(
                    "No chart data available",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface_variant
                ),
                height=self._chart_height,
                alignment=ft.alignment.center,
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(spacing.sm)
            )
        
        # Create chart placeholder (would use actual charting library in production)
        chart_content = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Memory Usage Chart",
                    style=self.get_text_style('h4'),
                    color=palette.on_surface
                ),
                ft.Text(
                    f"Showing {len(self._data_points)} data points",
                    style=self.get_text_style('body_small'),
                    color=palette.on_surface_variant
                ),
                ft.Container(
                    content=ft.Text(
                        "📊 Chart visualization would be rendered here",
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant
                    ),
                    expand=True,
                    alignment=ft.alignment.center
                )
            ], spacing=spacing.sm),
            height=self._chart_height,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.outline_variant)
        )
        
        return chart_content
    
    def update_data(self, data_points: List[MemoryDataPoint]):
        """Update chart data."""
        self._data_points = data_points
        self.update()


class MemoryPressureGauge(ThemeAwareUserControl):
    """Memory pressure gauge component."""
    
    def __init__(self, pressure_score: float = 0.0):
        super().__init__()
        self._pressure_score = pressure_score
        
    def build(self) -> ft.Control:
        """Build the pressure gauge."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Determine gauge color and level
        if self._pressure_score >= 0.9:
            gauge_color = palette.error
            level_text = "CRITICAL"
        elif self._pressure_score >= 0.7:
            gauge_color = palette.warning
            level_text = "HIGH"
        elif self._pressure_score >= 0.4:
            gauge_color = palette.warning
            level_text = "MEDIUM"
        else:
            gauge_color = palette.success
            level_text = "LOW"
        
        # Create gauge visualization
        gauge_size = self.get_breakpoint_value(120, 140, 160, 180)
        
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Memory Pressure",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            f"{self._pressure_score:.2f}",
                            style=self.get_text_style('h2'),
                            color=gauge_color,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            level_text,
                            style=self.get_text_style('caption'),
                            color=gauge_color,
                            text_align=ft.TextAlign.CENTER
                        )
                    ], spacing=spacing.xs, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=gauge_size,
                    height=gauge_size,
                    bgcolor=palette.surface_variant,
                    border_radius=ft.border_radius.all(gauge_size // 2),
                    border=ft.border.all(3, gauge_color),
                    alignment=ft.alignment.center
                )
            ], spacing=spacing.sm, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.md)
        )
    
    def update_pressure(self, pressure_score: float):
        """Update pressure score."""
        self._pressure_score = pressure_score
        self.update()


class MemoryAllocationChart(ThemeAwareUserControl):
    """Memory allocation pattern chart component."""

    def __init__(self, allocation_data: List[Tuple[datetime, float, float]]):
        super().__init__()
        self._allocation_data = allocation_data  # (timestamp, allocation_rate, deallocation_rate)
        self._chart_height = 200

    def build(self) -> ft.Control:
        """Build the allocation chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        if not self._allocation_data:
            return ft.Container(
                content=ft.Text(
                    "No allocation data available",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface_variant
                ),
                height=self._chart_height,
                alignment=ft.alignment.center,
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(spacing.sm)
            )

        # Calculate statistics
        alloc_rates = [rate for _, rate, _ in self._allocation_data]
        dealloc_rates = [rate for _, _, rate in self._allocation_data]
        avg_alloc = sum(alloc_rates) / len(alloc_rates) if alloc_rates else 0
        avg_dealloc = sum(dealloc_rates) / len(dealloc_rates) if dealloc_rates else 0

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        "Memory Allocation Patterns",
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        f"{len(self._allocation_data)} samples",
                        style=self.get_text_style('caption'),
                        color=palette.on_surface_variant
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Column([
                        ft.Text(
                            "Allocation",
                            style=self.get_text_style('caption'),
                            color=palette.on_surface_variant
                        ),
                        ft.Text(
                            f"{avg_alloc:.1f} MB/s",
                            style=self.get_text_style('body_medium'),
                            color=palette.primary,
                            weight=ft.FontWeight.W_500
                        )
                    ], spacing=spacing.xs),
                    ft.Column([
                        ft.Text(
                            "Deallocation",
                            style=self.get_text_style('caption'),
                            color=palette.on_surface_variant
                        ),
                        ft.Text(
                            f"{avg_dealloc:.1f} MB/s",
                            style=self.get_text_style('body_medium'),
                            color=palette.secondary,
                            weight=ft.FontWeight.W_500
                        )
                    ], spacing=spacing.xs)
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ft.Container(
                    content=ft.Text(
                        "📈 Allocation pattern chart would be rendered here",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    ),
                    expand=True,
                    alignment=ft.alignment.center,
                    bgcolor=palette.surface_variant,
                    border_radius=ft.border_radius.all(spacing.xs)
                )
            ], spacing=spacing.sm),
            height=self._chart_height,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.outline_variant)
        )

    def update_data(self, allocation_data: List[Tuple[datetime, float, float]]):
        """Update allocation data."""
        self._allocation_data = allocation_data
        self.update()


class MemoryMonitorUI(ThemeAwareUserControl):
    """
    Memory usage monitoring with real-time charts, pressure indicators, and allocation tracking.

    Provides comprehensive memory monitoring including:
    - Real-time RAM and swap usage tracking
    - Memory pressure indicators and alerts
    - Allocation pattern analysis and visualization
    - Process memory monitoring
    - Historical data charts and trends
    - Configurable thresholds and alerts
    - Multiple display modes for different use cases
    """

    def __init__(self, config: Optional[MemoryMonitorConfiguration] = None):
        super().__init__()
        self._config = config or MemoryMonitorConfiguration()
        self._logger = logging.getLogger(f"{__name__}.MemoryMonitorUI")

        # Monitoring components
        self._memory_monitor: Optional[MemoryMonitor] = None

        # UI state
        self._is_monitoring = False
        self._last_update = datetime.now(timezone.utc)
        self._memory_data: List[MemoryDataPoint] = []
        self._allocation_data: List[Tuple[datetime, float, float]] = []

        # UI components
        self._metrics_panel: Optional[MemoryMetricsPanel] = None
        self._usage_chart: Optional[MemoryUsageChart] = None
        self._pressure_gauge: Optional[MemoryPressureGauge] = None
        self._allocation_chart: Optional[MemoryAllocationChart] = None
        self._monitoring_task: Optional[asyncio.Task] = None

        # Initialize monitoring
        self._initialize_monitor()

    def build(self) -> ft.Control:
        """Build the memory monitor UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create header with controls
        header = self._create_header()

        # Create main content based on display mode
        if self._config.display_mode == MemoryDisplayMode.DETAILED:
            content = self._create_detailed_view()
        elif self._config.display_mode == MemoryDisplayMode.PRESSURE:
            content = self._create_pressure_view()
        elif self._config.display_mode == MemoryDisplayMode.ALLOCATION:
            content = self._create_allocation_view()
        else:
            content = self._create_overview()

        # Create status bar
        status_bar = self._create_status_bar()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=1, color=palette.outline_variant),
                content,
                ft.Divider(height=1, color=palette.outline_variant),
                status_bar
            ], spacing=0, expand=True),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(spacing.md),
            border=ft.border.all(1, palette.outline_variant),
            padding=ft.padding.all(spacing.component_padding),
            expand=True
        )

    def _create_header(self) -> ft.Container:
        """Create header with controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Display mode selector
        mode_dropdown = ft.Dropdown(
            label="Display Mode",
            value=self._config.display_mode.value,
            options=[
                ft.dropdown.Option("overview", "Overview"),
                ft.dropdown.Option("detailed", "Detailed"),
                ft.dropdown.Option("pressure", "Pressure"),
                ft.dropdown.Option("allocation", "Allocation")
            ],
            on_change=self._on_display_mode_change,
            width=self.get_breakpoint_value(120, 140, 160, 180),
            text_style=self.get_text_style('body_medium'),
            bgcolor=palette.surface_variant
        )

        # Refresh rate selector
        refresh_rate_dropdown = ft.Dropdown(
            label="Refresh Rate",
            value=str(self._config.refresh_interval_seconds),
            options=[
                ft.dropdown.Option("0.5", "0.5s"),
                ft.dropdown.Option("1.0", "1.0s"),
                ft.dropdown.Option("2.0", "2.0s"),
                ft.dropdown.Option("5.0", "5.0s")
            ],
            on_change=self._on_refresh_rate_change,
            width=self.get_breakpoint_value(100, 120, 140, 160),
            text_style=self.get_text_style('body_medium'),
            bgcolor=palette.surface_variant
        )

        # Control buttons
        start_stop_button = ft.ElevatedButton(
            text="Stop" if self._is_monitoring else "Start",
            icon=self.get_icon('STOP') if self._is_monitoring else self.get_icon('PLAY_ARROW'),
            on_click=self._toggle_monitoring,
            bgcolor=palette.error if self._is_monitoring else palette.primary,
            color=palette.on_error if self._is_monitoring else palette.on_primary
        )

        reset_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Reset Charts",
            on_click=self._reset_charts,
            icon_color=palette.primary
        )

        settings_button = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            tooltip="Memory Monitor Settings",
            on_click=self._show_settings,
            icon_color=palette.primary
        )

        return ft.Container(
            content=ft.ResponsiveRow([
                ft.Col([
                    ft.Text(
                        "Memory Monitor",
                        style=self.get_text_style('h3'),
                        color=palette.on_surface,
                        weight=ft.FontWeight.BOLD
                    )
                ], xs=12, sm=6, md=4, lg=4),
                ft.Col([
                    ft.Row([
                        mode_dropdown,
                        refresh_rate_dropdown
                    ], spacing=spacing.sm)
                ], xs=12, sm=6, md=4, lg=4),
                ft.Col([
                    ft.Row([
                        start_stop_button,
                        reset_button,
                        settings_button
                    ], spacing=spacing.sm, alignment=ft.MainAxisAlignment.END)
                ], xs=12, sm=12, md=4, lg=4)
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(spacing.sm)
        )

    def _create_overview(self) -> ft.Container:
        """Create overview display."""
        spacing = self.get_spacing()

        # Get current metrics
        current_metrics = self._memory_monitor.get_current_metrics() if self._memory_monitor else None

        # Create components
        self._metrics_panel = MemoryMetricsPanel(current_metrics)
        self._usage_chart = MemoryUsageChart(self._memory_data)
        self._pressure_gauge = MemoryPressureGauge(
            current_metrics.memory_pressure_score if current_metrics else 0.0
        )

        return ft.Container(
            content=ft.Column([
                self._metrics_panel,
                ft.ResponsiveRow([
                    ft.Col(self._usage_chart, xs=12, sm=12, md=8, lg=8),
                    ft.Col(self._pressure_gauge, xs=12, sm=12, md=4, lg=4)
                ])
            ], spacing=spacing.md),
            expand=True
        )

    def _create_detailed_view(self) -> ft.Container:
        """Create detailed display."""
        spacing = self.get_spacing()

        # Get current metrics
        current_metrics = self._memory_monitor.get_current_metrics() if self._memory_monitor else None

        # Create components
        self._metrics_panel = MemoryMetricsPanel(current_metrics)
        self._usage_chart = MemoryUsageChart(self._memory_data)
        self._pressure_gauge = MemoryPressureGauge(
            current_metrics.memory_pressure_score if current_metrics else 0.0
        )
        self._allocation_chart = MemoryAllocationChart(self._allocation_data)

        return ft.Container(
            content=ft.Column([
                self._metrics_panel,
                ft.ResponsiveRow([
                    ft.Col(self._usage_chart, xs=12, sm=12, md=6, lg=6),
                    ft.Col(self._allocation_chart, xs=12, sm=12, md=6, lg=6)
                ]),
                ft.ResponsiveRow([
                    ft.Col(self._pressure_gauge, xs=12, sm=6, md=4, lg=4),
                    ft.Col(self._create_process_memory_panel(), xs=12, sm=6, md=8, lg=8)
                ])
            ], spacing=spacing.md),
            expand=True
        )

    def _create_pressure_view(self) -> ft.Container:
        """Create pressure-focused display."""
        spacing = self.get_spacing()

        # Get current metrics
        current_metrics = self._memory_monitor.get_current_metrics() if self._memory_monitor else None

        # Create large pressure gauge
        self._pressure_gauge = MemoryPressureGauge(
            current_metrics.memory_pressure_score if current_metrics else 0.0
        )

        # Create pressure history chart
        pressure_chart = self._create_pressure_history_chart()

        return ft.Container(
            content=ft.ResponsiveRow([
                ft.Col(self._pressure_gauge, xs=12, sm=6, md=4, lg=4),
                ft.Col(pressure_chart, xs=12, sm=6, md=8, lg=8)
            ]),
            expand=True
        )

    def _create_allocation_view(self) -> ft.Container:
        """Create allocation-focused display."""
        spacing = self.get_spacing()

        # Create allocation chart
        self._allocation_chart = MemoryAllocationChart(self._allocation_data)

        # Create allocation statistics panel
        allocation_stats = self._create_allocation_stats_panel()

        return ft.Container(
            content=ft.Column([
                ft.ResponsiveRow([
                    ft.Col(self._allocation_chart, xs=12, sm=12, md=8, lg=8),
                    ft.Col(allocation_stats, xs=12, sm=12, md=4, lg=4)
                ])
            ], spacing=spacing.md),
            expand=True
        )

    def _create_status_bar(self) -> ft.Container:
        """Create status bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Status indicators
        monitoring_status = ft.Row([
            ft.Icon(
                self.get_icon('CIRCLE'),
                color=palette.success if self._is_monitoring else palette.error,
                size=12
            ),
            ft.Text(
                "Monitoring" if self._is_monitoring else "Stopped",
                style=self.get_text_style('caption'),
                color=palette.on_surface_variant
            )
        ], spacing=spacing.xs)

        # Last update time
        last_update_text = ft.Text(
            f"Last update: {self._last_update.strftime('%H:%M:%S')}",
            style=self.get_text_style('caption'),
            color=palette.on_surface_variant
        )

        # Data points count
        data_count_text = ft.Text(
            f"Data points: {len(self._memory_data)}",
            style=self.get_text_style('caption'),
            color=palette.on_surface_variant
        )

        return ft.Container(
            content=ft.Row([
                monitoring_status,
                ft.VerticalDivider(width=1, color=palette.outline_variant),
                last_update_text,
                ft.VerticalDivider(width=1, color=palette.outline_variant),
                data_count_text
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.sm),
            bgcolor=palette.surface_variant
        )

    def _create_process_memory_panel(self) -> ft.Container:
        """Create process memory information panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Get current metrics
        current_metrics = self._memory_monitor.get_current_metrics() if self._memory_monitor else None

        if not current_metrics or not current_metrics.process_memory:
            return ft.Container(
                content=ft.Text(
                    "No process memory data available",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface_variant
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(spacing.sm)
            )

        process_mem = current_metrics.process_memory

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Process Memory",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_500
                ),
                ft.Row([
                    ft.Column([
                        ft.Text(
                            "RSS",
                            style=self.get_text_style('caption'),
                            color=palette.on_surface_variant
                        ),
                        ft.Text(
                            f"{process_mem.memory_rss_mb:.1f} MB",
                            style=self.get_text_style('body_small'),
                            color=palette.on_surface
                        )
                    ], spacing=spacing.xs),
                    ft.Column([
                        ft.Text(
                            "VMS",
                            style=self.get_text_style('caption'),
                            color=palette.on_surface_variant
                        ),
                        ft.Text(
                            f"{process_mem.memory_vms_mb:.1f} MB",
                            style=self.get_text_style('body_small'),
                            color=palette.on_surface
                        )
                    ], spacing=spacing.xs),
                    ft.Column([
                        ft.Text(
                            "Percent",
                            style=self.get_text_style('caption'),
                            color=palette.on_surface_variant
                        ),
                        ft.Text(
                            f"{process_mem.memory_percent:.1f}%",
                            style=self.get_text_style('body_small'),
                            color=palette.on_surface
                        )
                    ], spacing=spacing.xs)
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND)
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_pressure_history_chart(self) -> ft.Container:
        """Create pressure history chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Extract pressure data from memory data
        pressure_data = [(dp.timestamp, dp.pressure_score) for dp in self._memory_data]

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Memory Pressure History",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(
                    content=ft.Text(
                        "📊 Pressure history chart would be rendered here",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    ),
                    expand=True,
                    alignment=ft.alignment.center,
                    bgcolor=palette.surface_variant,
                    border_radius=ft.border_radius.all(spacing.xs)
                )
            ], spacing=spacing.sm),
            height=300,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_allocation_stats_panel(self) -> ft.Container:
        """Create allocation statistics panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        if not self._allocation_data:
            return ft.Container(
                content=ft.Text(
                    "No allocation statistics available",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface_variant
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(spacing.sm)
            )

        # Calculate statistics
        alloc_rates = [rate for _, rate, _ in self._allocation_data]
        dealloc_rates = [rate for _, _, rate in self._allocation_data]

        avg_alloc = sum(alloc_rates) / len(alloc_rates) if alloc_rates else 0
        max_alloc = max(alloc_rates) if alloc_rates else 0
        avg_dealloc = sum(dealloc_rates) / len(dealloc_rates) if dealloc_rates else 0
        max_dealloc = max(dealloc_rates) if dealloc_rates else 0

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Allocation Statistics",
                    style=self.get_text_style('body_medium'),
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_500
                ),
                ft.Column([
                    ft.Row([
                        ft.Text("Avg Allocation:", style=self.get_text_style('caption')),
                        ft.Text(f"{avg_alloc:.1f} MB/s", style=self.get_text_style('body_small'))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.Text("Max Allocation:", style=self.get_text_style('caption')),
                        ft.Text(f"{max_alloc:.1f} MB/s", style=self.get_text_style('body_small'))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.Text("Avg Deallocation:", style=self.get_text_style('caption')),
                        ft.Text(f"{avg_dealloc:.1f} MB/s", style=self.get_text_style('body_small'))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.Text("Max Deallocation:", style=self.get_text_style('caption')),
                        ft.Text(f"{max_dealloc:.1f} MB/s", style=self.get_text_style('body_small'))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=spacing.xs)
            ], spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(spacing.sm),
            border=ft.border.all(1, palette.outline_variant)
        )

    # Event handlers
    def _on_display_mode_change(self, e):
        """Handle display mode change."""
        try:
            new_mode = MemoryDisplayMode(e.control.value)
            self._config.display_mode = new_mode
            self.update()
            self._logger.info(f"Display mode changed to: {new_mode.value}")
        except Exception as ex:
            self._logger.error(f"Error changing display mode: {ex}")

    def _on_refresh_rate_change(self, e):
        """Handle refresh rate change."""
        try:
            new_rate = float(e.control.value)
            self._config.refresh_interval_seconds = new_rate

            # Restart monitoring with new rate if currently monitoring
            if self._is_monitoring:
                asyncio.create_task(self._restart_monitoring())

            self._logger.info(f"Refresh rate changed to: {new_rate}s")
        except Exception as ex:
            self._logger.error(f"Error changing refresh rate: {ex}")

    def _toggle_monitoring(self, e):
        """Toggle monitoring on/off."""
        try:
            if self._is_monitoring:
                asyncio.create_task(self.stop_monitoring())
            else:
                asyncio.create_task(self.start_monitoring())
        except Exception as ex:
            self._logger.error(f"Error toggling monitoring: {ex}")

    def _reset_charts(self, e):
        """Reset chart data."""
        try:
            self._memory_data.clear()
            self._allocation_data.clear()
            self.update()
            self._logger.info("Charts reset")
        except Exception as ex:
            self._logger.error(f"Error resetting charts: {ex}")

    def _show_settings(self, e):
        """Show settings dialog."""
        # This would open a settings dialog in a real implementation
        self._logger.info("Settings dialog requested")

    # Monitoring methods
    def _initialize_monitor(self):
        """Initialize memory monitor."""
        try:
            self._memory_monitor = MemoryMonitor()
            self._logger.info("Memory monitor initialized")
        except Exception as ex:
            self._logger.error(f"Error initializing memory monitor: {ex}")

    async def start_monitoring(self) -> None:
        """Start memory monitoring."""
        try:
            if self._is_monitoring:
                return

            self._is_monitoring = True

            # Start memory monitor
            if self._memory_monitor:
                await self._memory_monitor.start_monitoring(self._config.refresh_interval_seconds)

            # Start monitoring task
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

            self.update()
            self._logger.info("Memory monitoring started")

        except Exception as e:
            self._logger.error(f"Failed to start monitoring: {str(e)}")
            self._is_monitoring = False

    async def stop_monitoring(self) -> None:
        """Stop memory monitoring."""
        try:
            if not self._is_monitoring:
                return

            self._is_monitoring = False

            # Stop monitoring task
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                self._monitoring_task = None

            # Stop memory monitor
            if self._memory_monitor:
                await self._memory_monitor.stop_monitoring()

            self.update()
            self._logger.info("Memory monitoring stopped")

        except Exception as e:
            self._logger.error(f"Failed to stop monitoring: {str(e)}")

    async def _restart_monitoring(self) -> None:
        """Restart monitoring with new settings."""
        if self._is_monitoring:
            await self.stop_monitoring()
            await asyncio.sleep(0.1)  # Brief pause
            await self.start_monitoring()

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._is_monitoring:
                start_time = time.time()

                # Collect memory metrics
                if self._memory_monitor:
                    current_metrics = self._memory_monitor.get_current_metrics()
                    if current_metrics:
                        # Convert to data point
                        data_point = MemoryDataPoint(
                            timestamp=current_metrics.timestamp,
                            total_ram_mb=current_metrics.total_ram_mb,
                            used_ram_mb=current_metrics.used_ram_mb,
                            available_ram_mb=current_metrics.available_ram_mb,
                            cached_mb=current_metrics.cached_mb,
                            buffers_mb=current_metrics.buffers_mb,
                            usage_percent=current_metrics.usage_percent,
                            swap_used_mb=current_metrics.swap_info.used_mb,
                            swap_total_mb=current_metrics.swap_info.total_mb,
                            swap_percent=current_metrics.swap_info.usage_percent,
                            pressure_score=current_metrics.memory_pressure_score,
                            allocation_rate=current_metrics.allocation_rate_mb_per_sec,
                            deallocation_rate=current_metrics.deallocation_rate_mb_per_sec
                        )

                        # Add to data history
                        self._memory_data.append(data_point)

                        # Add allocation data
                        self._allocation_data.append((
                            current_metrics.timestamp,
                            current_metrics.allocation_rate_mb_per_sec,
                            current_metrics.deallocation_rate_mb_per_sec
                        ))

                        # Limit history size
                        max_history = int(self._config.history_minutes * 60 / self._config.refresh_interval_seconds)
                        if len(self._memory_data) > max_history:
                            self._memory_data = self._memory_data[-max_history:]
                        if len(self._allocation_data) > max_history:
                            self._allocation_data = self._allocation_data[-max_history:]

                        # Update UI components
                        self._last_update = datetime.now(timezone.utc)
                        self._update_ui_components(current_metrics)

                # Calculate sleep time to maintain consistent interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self._config.refresh_interval_seconds - elapsed)
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            self._logger.info("Memory monitoring loop cancelled")
        except Exception as e:
            self._logger.error(f"Error in monitoring loop: {str(e)}")
            self._is_monitoring = False

    def _update_ui_components(self, metrics: MemoryMetrics):
        """Update UI components with new metrics."""
        try:
            # Update metrics panel
            if self._metrics_panel:
                self._metrics_panel.update_metrics(metrics)

            # Update usage chart
            if self._usage_chart:
                self._usage_chart.update_data(self._memory_data)

            # Update pressure gauge
            if self._pressure_gauge:
                self._pressure_gauge.update_pressure(metrics.memory_pressure_score)

            # Update allocation chart
            if self._allocation_chart:
                self._allocation_chart.update_data(self._allocation_data)

            # Update main UI
            self.update()

        except Exception as e:
            self._logger.error(f"Error updating UI components: {str(e)}")

    # Public interface methods
    def get_current_metrics(self) -> Optional[MemoryMetrics]:
        """Get current memory metrics."""
        if self._memory_monitor:
            return self._memory_monitor.get_current_metrics()
        return None

    def get_memory_data_history(self) -> List[MemoryDataPoint]:
        """Get memory data history."""
        return self._memory_data.copy()

    def get_allocation_data_history(self) -> List[Tuple[datetime, float, float]]:
        """Get allocation data history."""
        return self._allocation_data.copy()

    def configure_thresholds(self, thresholds: MemoryAlertThreshold):
        """Configure alert thresholds."""
        self._config.alert_thresholds = thresholds
        if self._memory_monitor:
            self._memory_monitor.configure_thresholds(
                thresholds.warning_percent,
                thresholds.critical_percent
            )
        self._logger.info("Memory alert thresholds updated")

    def is_monitoring_active(self) -> bool:
        """Check if monitoring is currently active."""
        return self._is_monitoring

    def get_configuration(self) -> MemoryMonitorConfiguration:
        """Get current configuration."""
        return self._config

    async def cleanup(self):
        """Cleanup resources."""
        try:
            await self.stop_monitoring()
            self._logger.info("Memory monitor UI cleaned up")
        except Exception as e:
            self._logger.error(f"Error during cleanup: {str(e)}")
