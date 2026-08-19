"""
Module: gpu_utilization_chart_ui
Description: Real-time GPU usage visualization with VRAM allocation, compute percentage, and temperature displays.
            Provides comprehensive GPU monitoring with interactive charts, thermal monitoring, memory allocation
            tracking, and multi-GPU support with theme-aware visualization components.
Phase: 2
Location: /src/modules/ui/resource_dashboard_ui/gpu_utilization_chart_ui/gpu_utilization_chart_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl


@dataclass
class GPUMetrics:
    """GPU performance metrics data structure."""
    timestamp: datetime
    gpu_utilization_percent: float
    memory_used_mb: float
    memory_total_mb: float
    temperature_celsius: Optional[float] = None
    power_draw_watts: Optional[float] = None
    core_clock_mhz: Optional[int] = None
    memory_clock_mhz: Optional[int] = None
    fan_speed_percent: Optional[float] = None


@dataclass
class GPUInfo:
    """GPU device information."""
    name: str
    device_id: int
    memory_total_mb: float
    driver_version: str
    cuda_version: Optional[str] = None


class GPUMonitor:
    """Mock GPU monitor for demonstration purposes."""

    def __init__(self):
        self._gpu_infos = [
            GPUInfo(
                name="NVIDIA GeForce RTX 4080",
                device_id=0,
                memory_total_mb=16384,
                driver_version="531.61",
                cuda_version="12.1"
            )
        ]

    def get_gpu_info(self) -> List[GPUInfo]:
        """Get available GPU information."""
        return self._gpu_infos

    def get_current_metrics(self, gpu_id: int = 0) -> Optional[GPUMetrics]:
        """Get current GPU metrics (mock implementation)."""
        import random

        if gpu_id >= len(self._gpu_infos):
            return None

        # Generate realistic mock data
        base_usage = 45 + 30 * random.random()
        gpu_usage = max(0, min(100, base_usage + 10 * (random.random() - 0.5)))

        vram_used = 6000 + 2000 * random.random()
        temp = 65 + (gpu_usage / 100) * 20 + 5 * (random.random() - 0.5)
        power = 150 + (gpu_usage / 100) * 100 + 20 * (random.random() - 0.5)

        return GPUMetrics(
            timestamp=datetime.now(),
            gpu_utilization_percent=gpu_usage,
            memory_used_mb=vram_used,
            memory_total_mb=self._gpu_infos[gpu_id].memory_total_mb,
            temperature_celsius=temp,
            power_draw_watts=power,
            core_clock_mhz=1500 + int(200 * random.random()),
            memory_clock_mhz=1750 + int(50 * random.random()),
            fan_speed_percent=40 + (temp - 60) * 2
        )


class GPUMetricType(Enum):
    """GPU metric types for visualization."""
    UTILIZATION = "utilization"
    MEMORY = "memory"
    TEMPERATURE = "temperature"
    POWER = "power"
    CLOCK_SPEED = "clock_speed"


@dataclass
class GPUChartConfiguration:
    """Configuration for GPU utilization chart."""
    update_interval_seconds: float = 1.0
    history_minutes: int = 5
    show_temperature: bool = True
    show_power_usage: bool = True
    show_memory_details: bool = True
    show_clock_speeds: bool = False
    temperature_unit: str = "celsius"  # "celsius" or "fahrenheit"
    auto_scale: bool = True
    max_temperature_threshold: float = 85.0
    critical_temperature_threshold: float = 95.0


class GPUUtilizationChartUI(ThemeAwareUserControl):
    """
    GPU utilization chart UI component.
    
    Provides comprehensive real-time GPU monitoring with:
    - Real-time GPU compute utilization visualization
    - VRAM allocation and usage tracking
    - Temperature monitoring with thermal throttling indicators
    - Power consumption tracking
    - Clock speed monitoring (optional)
    - Multi-GPU support with individual charts
    - Interactive tooltips and data point selection
    - Theme-aware styling and color coding
    """
    
    def __init__(
        self,
        gpu_monitor: Optional[GPUMonitor] = None,
        gpu_id: int = 0,
        config: Optional[GPUChartConfiguration] = None,
        on_gpu_select: Optional[Callable[[int], None]] = None,
        on_threshold_exceeded: Optional[Callable[[str, float], None]] = None
    ):
        """
        Initialize GPU utilization chart.
        
        Args:
            gpu_monitor: GPU monitoring service
            gpu_id: GPU device ID to monitor
            config: Chart configuration
            on_gpu_select: Callback for GPU selection
            on_threshold_exceeded: Callback for threshold violations
        """
        super().__init__()
        self._gpu_monitor = gpu_monitor
        self._gpu_id = gpu_id
        self._config = config or GPUChartConfiguration()
        self._on_gpu_select = on_gpu_select
        self._on_threshold_exceeded = on_threshold_exceeded
        
        # GPU information
        self._gpu_info: Optional[GPUInfo] = None
        self._current_metrics: Optional[GPUMetrics] = None
        self._metrics_history: List[GPUMetrics] = []
        
        # UI state
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._selected_metric = GPUMetricType.UTILIZATION
        
        # Chart components
        self._utilization_chart: Optional[ft.LineChart] = None
        self._memory_chart: Optional[ft.LineChart] = None
        self._temperature_chart: Optional[ft.LineChart] = None
        self._power_chart: Optional[ft.LineChart] = None
        
        # Metric displays
        self._utilization_text: Optional[ft.Text] = None
        self._memory_text: Optional[ft.Text] = None
        self._temperature_text: Optional[ft.Text] = None
        self._power_text: Optional[ft.Text] = None
        self._clock_text: Optional[ft.Text] = None
        
        # Status indicators
        self._thermal_status: Optional[ft.Container] = None
        self._memory_status: Optional[ft.Container] = None
        
        # Controls
        self._gpu_selector: Optional[ft.Dropdown] = None
        self._metric_tabs: Optional[ft.Tabs] = None
    
    def build(self) -> ft.Control:
        """Build the GPU utilization chart UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header with GPU info
        header = self._create_header()
        
        # Create metrics overview
        metrics_overview = self._create_metrics_overview()
        
        # Create main chart area
        chart_area = self._create_chart_area()
        
        # Create status indicators
        status_section = self._create_status_section()
        
        # Create controls
        controls = self._create_controls()
        
        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=spacing.md),
                metrics_overview,
                ft.Container(height=spacing.lg),
                chart_area,
                ft.Container(height=spacing.md),
                status_section,
                ft.Container(height=spacing.md),
                controls
            ], scroll=ft.ScrollMode.AUTO),
            bgcolor=palette.background_primary,
            padding=ft.padding.all(spacing.lg),
            expand=True
        )
    
    def _create_header(self) -> ft.Control:
        """Create header with GPU information."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # GPU name and status
        gpu_name = f"GPU {self._gpu_id}"
        if self._gpu_info:
            gpu_name = f"{self._gpu_info.name} (GPU {self._gpu_id})"
        
        status_color = palette.success if self._is_monitoring else palette.text_tertiary
        status_text = "Active" if self._is_monitoring else "Inactive"
        
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(
                        gpu_name,
                        style=self.get_text_style('h2'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "Real-time GPU utilization monitoring",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], expand=True),
                ft.Column([
                    ft.Row([
                        ft.Icon(self.get_icon('CIRCLE'), color=status_color, size=self.get_responsive_layout().get_breakpoint_value(10, 12, 14, 16)),
                        ft.Text(
                            status_text,
                            style=self.get_text_style('body_small'),
                            color=status_color
                        )
                    ], spacing=spacing.xs),
                    ft.Text(
                        datetime.now().strftime("%H:%M:%S"),
                        style=self.get_text_style('caption'),
                        color=palette.text_tertiary
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.END)
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.lg),
            border_radius=ft.border_radius.all(self.get_spacing().md),
            border=ft.border.all(1, palette.borders)
        )
    
    def _create_metrics_overview(self) -> ft.Control:
        """Create metrics overview cards."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # GPU Utilization card
        utilization_card = self._create_metric_card(
            "GPU Utilization",
            "0%",
            self.get_icon('CPU'),
            palette.primary,
            "utilization_text"
        )
        
        # Memory Usage card
        memory_card = self._create_metric_card(
            "VRAM Usage",
            "0 MB / 0 MB",
            self.get_icon('MEMORY'),
            palette.info,
            "memory_text"
        )
        
        # Temperature card
        temperature_card = self._create_metric_card(
            "Temperature",
            "0°C",
            self.get_icon('THERMAL'),
            palette.warning,
            "temperature_text"
        )
        
        # Power Usage card (if enabled)
        power_card = None
        if self._config.show_power_usage:
            power_card = self._create_metric_card(
                "Power Usage",
                "0W",
                self.get_icon('POWER'),
                palette.secondary,
                "power_text"
            )
        
        # Clock Speed card (if enabled)
        clock_card = None
        if self._config.show_clock_speeds:
            clock_card = self._create_metric_card(
                "Clock Speed",
                "0 MHz",
                self.get_icon('SPEED'),
                palette.success,
                "clock_text"
            )
        
        # Arrange cards
        cards = [utilization_card, memory_card, temperature_card]
        if power_card:
            cards.append(power_card)
        if clock_card:
            cards.append(clock_card)
        
        return ft.ResponsiveRow([
            ft.Container(
                content=card,
                col={"sm": 6, "md": 4, "lg": 3} if len(cards) > 3 else {"sm": 6, "md": 6, "lg": 4}
            ) for card in cards
        ])
    
    def _create_metric_card(self, title: str, value: str, icon: str, color: str, ref_key: str) -> ft.Control:
        """Create a metric display card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create text reference for updates
        value_text = ft.Text(
            value,
            style=self.get_text_style('metric_medium'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD
        )
        
        # Store reference for updates
        if ref_key == "utilization_text":
            self._utilization_text = value_text
        elif ref_key == "memory_text":
            self._memory_text = value_text
        elif ref_key == "temperature_text":
            self._temperature_text = value_text
        elif ref_key == "power_text":
            self._power_text = value_text
        elif ref_key == "clock_text":
            self._clock_text = value_text
        
        rlm = self.get_responsive_layout()
        icon_size = rlm.get_breakpoint_value(16, 18, 20, 24)
        bar_height = rlm.get_breakpoint_value(2, 3, 4, 5)
        bar_width = rlm.get_breakpoint_value(40, 48, 56, 64)
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icon, color=color, size=icon_size),
                        ft.Text(
                            title,
                            style=self.get_text_style('body_small'),
                            color=palette.text_secondary
                        )
                    ], spacing=spacing.sm),
                    ft.Container(height=spacing.xs),
                    value_text,
                    ft.Container(height=spacing.xs),
                    ft.Container(
                        height=bar_height,
                        bgcolor=color,
                        border_radius=ft.border_radius.all(self.get_spacing().xs),
                        width=bar_width
                    )
                ]),
                padding=ft.padding.all(spacing.md)
            ),
            color=palette.surface,
            elevation=1
        )

    def _create_chart_area(self) -> ft.Control:
        """Create main chart area with metric tabs."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create metric selection tabs
        self._metric_tabs = ft.Tabs(
            selected_index=0,
            on_change=self._on_metric_tab_change,
            tabs=[
                ft.Tab(
                    text="Utilization",
                    icon=self.get_icon('CPU'),
                    content=self._create_utilization_chart()
                ),
                ft.Tab(
                    text="Memory",
                    icon=self.get_icon('MEMORY'),
                    content=self._create_memory_chart()
                ),
                ft.Tab(
                    text="Temperature",
                    icon=self.get_icon('THERMAL'),
                    content=self._create_temperature_chart()
                )
            ]
        )

        # Add power tab if enabled
        if self._config.show_power_usage:
            self._metric_tabs.tabs.append(
                ft.Tab(
                    text="Power",
                    icon=self.get_icon('POWER'),
                    content=self._create_power_chart()
                )
            )

        rlm = self.get_responsive_layout()
        container_height = rlm.get_breakpoint_value(320, 360, 420, 480)
        return ft.Container(
            content=self._metric_tabs,
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(self.get_spacing().md),
            border=ft.border.all(1, palette.borders),
            padding=ft.padding.all(spacing.md),
            height=container_height
        )

    def _create_utilization_chart(self) -> ft.Control:
        """Create GPU utilization chart."""
        palette = self.get_palette()

        rlm = self.get_responsive_layout()
        title_font = rlm.get_breakpoint_value(10, 12, 14, 16)
        axis_space = rlm.get_breakpoint_value(28, 36, 44, 52)
        stroke = rlm.get_breakpoint_value(2, 3, 3, 4)
        self._utilization_chart = ft.LineChart(
            data_series=[
                ft.LineChartData(
                    data_points=[],
                    stroke_width=stroke,
                    color=palette.primary,
                    curved=True,
                    stroke_cap_round=True,
                    below_line_bgcolor=f"{palette.primary}20"
                )
            ],
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5]
            ),
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5]
            ),
            left_axis=ft.ChartAxis(
                title=ft.Text("GPU Usage (%)", size=title_font, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Time", size=title_font, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            tooltip_bgcolor=palette.surface,
            min_y=0,
            max_y=100,
            min_x=0,
            max_x=self._config.history_minutes * 60,
            expand=True
        )

        return ft.Container(
            content=self._utilization_chart,
            bgcolor=palette.background_secondary,
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            padding=ft.padding.all(self.get_spacing().sm),
            expand=True
        )

    def _create_memory_chart(self) -> ft.Control:
        """Create VRAM usage chart."""
        palette = self.get_palette()

        rlm = self.get_responsive_layout()
        title_font = rlm.get_breakpoint_value(10, 12, 14, 16)
        axis_space = rlm.get_breakpoint_value(28, 36, 44, 52)
        stroke = rlm.get_breakpoint_value(2, 3, 3, 4)
        self._memory_chart = ft.LineChart(
            data_series=[
                ft.LineChartData(
                    data_points=[],
                    stroke_width=stroke,
                    color=palette.info,
                    curved=True,
                    stroke_cap_round=True,
                    below_line_bgcolor=f"{palette.info}20"
                )
            ],
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5]
            ),
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5]
            ),
            left_axis=ft.ChartAxis(
                title=ft.Text("VRAM Usage (%)", size=title_font, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Time", size=title_font, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            tooltip_bgcolor=palette.surface,
            min_y=0,
            max_y=100,
            min_x=0,
            max_x=self._config.history_minutes * 60,
            expand=True
        )

        return ft.Container(
            content=self._memory_chart,
            bgcolor=palette.background_secondary,
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            padding=ft.padding.all(self.get_spacing().sm),
            expand=True
        )

    def _create_temperature_chart(self) -> ft.Control:
        """Create temperature monitoring chart."""
        palette = self.get_palette()

        rlm = self.get_responsive_layout()
        title_font = rlm.get_breakpoint_value(10, 12, 14, 16)
        axis_space = rlm.get_breakpoint_value(28, 36, 44, 52)
        stroke = rlm.get_breakpoint_value(2, 3, 3, 4)
        self._temperature_chart = ft.LineChart(
            data_series=[
                ft.LineChartData(
                    data_points=[],
                    stroke_width=stroke,
                    color=palette.warning,
                    curved=True,
                    stroke_cap_round=True,
                    below_line_bgcolor=f"{palette.warning}20"
                )
            ],
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5]
            ),
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5]
            ),
            left_axis=ft.ChartAxis(
                title=ft.Text("Temperature (°C)", size=title_font, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Time", size=title_font, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            tooltip_bgcolor=palette.surface,
            min_y=0,
            max_y=100,
            min_x=0,
            max_x=self._config.history_minutes * 60,
            expand=True
        )

        return ft.Container(
            content=self._temperature_chart,
            bgcolor=palette.background_secondary,
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            padding=ft.padding.all(self.get_spacing().sm),
            expand=True
        )

    def _create_power_chart(self) -> ft.Control:
        """Create power consumption chart."""
        palette = self.get_palette()

        rlm = self.get_responsive_layout()
        title_font = rlm.get_breakpoint_value(10, 12, 14, 16)
        axis_space = rlm.get_breakpoint_value(28, 36, 44, 52)
        stroke = rlm.get_breakpoint_value(2, 3, 3, 4)
        self._power_chart = ft.LineChart(
            data_series=[
                ft.LineChartData(
                    data_points=[],
                    stroke_width=stroke,
                    color=palette.secondary,
                    curved=True,
                    stroke_cap_round=True,
                    below_line_bgcolor=f"{palette.secondary}20"
                )
            ],
            border=ft.border.all(1, palette.borders),
            horizontal_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5]
            ),
            vertical_grid_lines=ft.ChartGridLines(
                color=palette.borders,
                width=1,
                dash_pattern=[5, 5]
            ),
            left_axis=ft.ChartAxis(
                title=ft.Text("Power (W)", size=title_font, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Time", size=title_font, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            tooltip_bgcolor=palette.surface,
            min_y=0,
            max_y=300,  # Typical GPU power limit
            min_x=0,
            max_x=self._config.history_minutes * 60,
            expand=True
        )

        return ft.Container(
            content=self._power_chart,
            bgcolor=palette.background_secondary,
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            padding=ft.padding.all(self.get_spacing().sm),
            expand=True
        )

    def _create_status_section(self) -> ft.Control:
        """Create status indicators section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Thermal status indicator
        rlm = self.get_responsive_layout()
        thermal_icon_size = rlm.get_breakpoint_value(12, 14, 16, 18)
        self._thermal_status = ft.Container(
            content=ft.Row([
                ft.Icon(self.get_icon('THERMAL'), color=palette.success, size=thermal_icon_size),
                ft.Text(
                    "Normal Temperature",
                    style=self.get_text_style('body_small'),
                    color=palette.success
                )
            ], spacing=spacing.xs),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            border=ft.border.all(1, palette.success)
        )

        # Memory status indicator
        memory_icon_size = self.get_responsive_layout().get_breakpoint_value(12, 14, 16, 18)
        self._memory_status = ft.Container(
            content=ft.Row([
                ft.Icon(self.get_icon('MEMORY'), color=palette.info, size=memory_icon_size),
                ft.Text(
                    "Memory Available",
                    style=self.get_text_style('body_small'),
                    color=palette.info
                )
            ], spacing=spacing.xs),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            border=ft.border.all(1, palette.info)
        )

        return ft.ResponsiveRow([
            ft.Container(
                content=self._thermal_status,
                col={"sm": 12, "md": 6}
            ),
            ft.Container(
                content=self._memory_status,
                col={"sm": 12, "md": 6}
            )
        ])

    def _create_controls(self) -> ft.Control:
        """Create control section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # GPU selector (if multiple GPUs available)
        self._gpu_selector = ft.Dropdown(
            label="GPU Device",
            value=str(self._gpu_id),
            options=[
                ft.dropdown.Option(str(self._gpu_id), f"GPU {self._gpu_id}")
            ],
            on_change=self._on_gpu_select,
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders
        )

        # Refresh controls
        refresh_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh GPU Info",
            on_click=self._refresh_gpu_info,
            icon_color=palette.text_secondary
        )

        # Settings button
        settings_button = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            tooltip="Chart Settings",
            on_click=self._show_settings,
            icon_color=palette.text_secondary
        )

        return ft.Container(
            content=ft.Row([
                self._gpu_selector,
                ft.Container(width=spacing.lg),
                refresh_button,
                settings_button
            ], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders)
        )

    async def start_monitoring(self) -> None:
        """Start GPU monitoring."""
        if self._is_monitoring or not self._gpu_monitor:
            return

        self._is_monitoring = True

        # Get GPU info
        gpu_infos = self._gpu_monitor.get_gpu_info()
        if gpu_infos and self._gpu_id < len(gpu_infos):
            self._gpu_info = gpu_infos[self._gpu_id]

        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.update()

    async def stop_monitoring(self) -> None:
        """Stop GPU monitoring."""
        if not self._is_monitoring:
            return

        self._is_monitoring = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        self.update()

    async def _monitoring_loop(self) -> None:
        """Main monitoring update loop."""
        try:
            while self._is_monitoring:
                # Get current metrics
                if self._gpu_monitor:
                    metrics = self._gpu_monitor.get_current_metrics(self._gpu_id)
                    if metrics:
                        self._current_metrics = metrics
                        self._metrics_history.append(metrics)

                        # Limit history size
                        max_history = int(self._config.history_minutes * 60 / self._config.update_interval_seconds)
                        if len(self._metrics_history) > max_history:
                            self._metrics_history = self._metrics_history[-max_history:]

                        # Update UI
                        self._update_metrics_display()
                        self._update_charts()
                        self._update_status_indicators()
                        self._check_thresholds()

                # Wait for next update
                await asyncio.sleep(self._config.update_interval_seconds)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            # Log error but continue monitoring
            pass

    def _update_metrics_display(self) -> None:
        """Update metric display cards with current values."""
        if not self._current_metrics:
            return

        metrics = self._current_metrics

        # Update utilization
        if self._utilization_text:
            self._utilization_text.value = f"{metrics.gpu_utilization_percent:.1f}%"

        # Update memory
        if self._memory_text:
            used_mb = metrics.memory_used_mb
            total_mb = metrics.memory_total_mb
            self._memory_text.value = f"{used_mb:.0f} MB / {total_mb:.0f} MB"

        # Update temperature
        if self._temperature_text and metrics.temperature_celsius is not None:
            temp = metrics.temperature_celsius
            if self._config.temperature_unit == "fahrenheit":
                temp = temp * 9/5 + 32
                unit = "°F"
            else:
                unit = "°C"
            self._temperature_text.value = f"{temp:.1f}{unit}"

        # Update power
        if self._power_text and metrics.power_draw_watts is not None:
            self._power_text.value = f"{metrics.power_draw_watts:.1f}W"

        # Update clock speed
        if self._clock_text and metrics.core_clock_mhz is not None:
            self._clock_text.value = f"{metrics.core_clock_mhz:.0f} MHz"

        self.update()

    def _update_charts(self) -> None:
        """Update charts with latest metrics data."""
        if not self._metrics_history:
            return

        current_time = datetime.now()
        time_window = timedelta(minutes=self._config.history_minutes)

        # Filter recent metrics
        recent_metrics = [
            m for m in self._metrics_history
            if current_time - m.timestamp <= time_window
        ]

        if not recent_metrics:
            return

        # Update utilization chart
        if self._utilization_chart:
            util_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.gpu_utilization_percent
                ) for m in recent_metrics
            ]
            self._utilization_chart.data_series[0].data_points = util_points

        # Update memory chart
        if self._memory_chart:
            memory_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=(m.memory_used_mb / m.memory_total_mb * 100) if m.memory_total_mb > 0 else 0
                ) for m in recent_metrics
            ]
            self._memory_chart.data_series[0].data_points = memory_points

        # Update temperature chart
        if self._temperature_chart:
            temp_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.temperature_celsius or 0
                ) for m in recent_metrics
            ]
            self._temperature_chart.data_series[0].data_points = temp_points

        # Update power chart
        if self._power_chart:
            power_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.power_draw_watts or 0
                ) for m in recent_metrics
            ]
            self._power_chart.data_series[0].data_points = power_points

        self.update()

    def _update_status_indicators(self) -> None:
        """Update status indicators based on current metrics."""
        if not self._current_metrics:
            return

        palette = self.get_palette()
        spacing = self.get_spacing()
        metrics = self._current_metrics

        # Update thermal status
        if self._thermal_status and metrics.temperature_celsius is not None:
            temp = metrics.temperature_celsius
            if temp >= self._config.critical_temperature_threshold:
                icon_color = palette.error
                text_color = palette.error
                border_color = palette.error
                status_text = "Critical Temperature"
                icon = self.get_icon('WARNING')
            elif temp >= self._config.max_temperature_threshold:
                icon_color = palette.warning
                text_color = palette.warning
                border_color = palette.warning
                status_text = "High Temperature"
                icon = self.get_icon('THERMAL')
            else:
                icon_color = palette.success
                text_color = palette.success
                border_color = palette.success
                status_text = "Normal Temperature"
                icon = self.get_icon('THERMAL')

            self._thermal_status.content = ft.Row([
                ft.Icon(icon, color=icon_color, size=16),
                ft.Text(
                    status_text,
                    style=self.get_text_style('body_small'),
                    color=text_color
                )
            ], spacing=spacing.xs)
            self._thermal_status.border = ft.border.all(1, border_color)

        # Update memory status
        if self._memory_status:
            memory_percent = (metrics.memory_used_mb / metrics.memory_total_mb * 100) if metrics.memory_total_mb > 0 else 0

            if memory_percent >= 95:
                icon_color = palette.error
                text_color = palette.error
                border_color = palette.error
                status_text = "Memory Critical"
                icon = self.get_icon('ERROR')
            elif memory_percent >= 85:
                icon_color = palette.warning
                text_color = palette.warning
                border_color = palette.warning
                status_text = "Memory High"
                icon = self.get_icon('WARNING')
            else:
                icon_color = palette.info
                text_color = palette.info
                border_color = palette.info
                status_text = "Memory Available"
                icon = self.get_icon('MEMORY')

            self._memory_status.content = ft.Row([
                ft.Icon(icon, color=icon_color, size=16),
                ft.Text(
                    status_text,
                    style=self.get_text_style('body_small'),
                    color=text_color
                )
            ], spacing=spacing.xs)
            self._memory_status.border = ft.border.all(1, border_color)

        self.update()

    def _check_thresholds(self) -> None:
        """Check for threshold violations and trigger callbacks."""
        if not self._current_metrics or not self._on_threshold_exceeded:
            return

        metrics = self._current_metrics

        # Check temperature thresholds
        if metrics.temperature_celsius is not None:
            if metrics.temperature_celsius >= self._config.critical_temperature_threshold:
                self._on_threshold_exceeded("temperature_critical", metrics.temperature_celsius)
            elif metrics.temperature_celsius >= self._config.max_temperature_threshold:
                self._on_threshold_exceeded("temperature_warning", metrics.temperature_celsius)

        # Check memory thresholds
        memory_percent = (metrics.memory_used_mb / metrics.memory_total_mb * 100) if metrics.memory_total_mb > 0 else 0
        if memory_percent >= 95:
            self._on_threshold_exceeded("memory_critical", memory_percent)
        elif memory_percent >= 85:
            self._on_threshold_exceeded("memory_warning", memory_percent)

    def _on_metric_tab_change(self, e) -> None:
        """Handle metric tab change."""
        tab_index = e.control.selected_index
        if tab_index == 0:
            self._selected_metric = GPUMetricType.UTILIZATION
        elif tab_index == 1:
            self._selected_metric = GPUMetricType.MEMORY
        elif tab_index == 2:
            self._selected_metric = GPUMetricType.TEMPERATURE
        elif tab_index == 3:
            self._selected_metric = GPUMetricType.POWER

    def _on_gpu_select(self, e) -> None:
        """Handle GPU selection change."""
        try:
            new_gpu_id = int(e.control.value)
            if new_gpu_id != self._gpu_id:
                self._gpu_id = new_gpu_id
                if self._on_gpu_select:
                    self._on_gpu_select(new_gpu_id)

                # Restart monitoring for new GPU
                if self._is_monitoring:
                    asyncio.create_task(self._restart_monitoring())
        except ValueError:
            pass

    async def _restart_monitoring(self) -> None:
        """Restart monitoring for new GPU."""
        await self.stop_monitoring()
        await asyncio.sleep(0.1)
        await self.start_monitoring()

    def _refresh_gpu_info(self, e) -> None:
        """Refresh GPU information."""
        if self._gpu_monitor:
            # Force refresh of GPU info
            gpu_infos = self._gpu_monitor.get_gpu_info()
            if gpu_infos and self._gpu_id < len(gpu_infos):
                self._gpu_info = gpu_infos[self._gpu_id]
                self.update()

    def _show_settings(self, e) -> None:
        """Show chart settings dialog."""
        # Placeholder for settings dialog
        pass

    def configure_chart(self, config: GPUChartConfiguration) -> None:
        """Update chart configuration."""
        self._config = config
        self.update()

    def get_current_metrics(self) -> Optional[GPUMetrics]:
        """Get current GPU metrics."""
        return self._current_metrics

    def get_metrics_history(self) -> List[GPUMetrics]:
        """Get metrics history."""
        return self._metrics_history.copy()

    def is_monitoring_active(self) -> bool:
        """Check if monitoring is currently active."""
        return self._is_monitoring

    def will_unmount(self) -> None:
        """Clean up when component is unmounted."""
        if self._is_monitoring:
            asyncio.create_task(self.stop_monitoring())
        super().will_unmount()
