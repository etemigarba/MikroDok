"""
Module: monitoring_dashboard_ui
Description: Main monitoring interface displaying real-time resource utilization graphs and system health status.
            Provides comprehensive system monitoring with interactive charts, real-time metrics display,
            and theme-aware visualization components for CPU, memory, GPU, disk, and network resources.
Phase: 2
Location: /src/modules/ui/resource_dashboard_ui/monitoring_dashboard_ui/monitoring_dashboard_ui.py
"""

# Standard library imports
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl

# Optional resource monitoring imports
try:
    from src.modules.logic.resource_monitor_lg.hardware_monitor_lg.hardware_monitor_lg import (
        HardwareMonitor, ResourceMetrics, MonitoringConfiguration, MonitoringThresholds
    )
    from src.modules.logic.resource_monitor_lg.gpu_monitor_lg.gpu_monitor_lg import GPUMonitor
    from src.modules.logic.resource_monitor_lg.memory_monitor_lg.memory_monitor_lg import MemoryMonitor
    RESOURCE_MONITORING_AVAILABLE = True
except ImportError:
    # Define placeholder types if resource monitoring is not available
    HardwareMonitor = None
    ResourceMetrics = None
    MonitoringConfiguration = None
    MonitoringThresholds = None
    GPUMonitor = None
    MemoryMonitor = None
    RESOURCE_MONITORING_AVAILABLE = False


@dataclass
class DashboardConfiguration:
    """Configuration for monitoring dashboard."""
    refresh_interval_seconds: float = 1.0
    history_minutes: int = 10
    show_gpu_metrics: bool = True
    show_memory_details: bool = True
    show_network_metrics: bool = True
    auto_scale_charts: bool = True
    enable_alerts: bool = True


class MonitoringDashboardUI(ThemeAwareUserControl):
    """
    Main monitoring dashboard UI component.
    
    Provides comprehensive real-time system monitoring with:
    - Interactive resource utilization charts
    - Real-time metrics display with automatic updates
    - System health status indicators
    - Configurable monitoring parameters
    - Theme-aware visualization components
    - Performance optimization recommendations
    """
    
    def __init__(
        self,
        hardware_monitor: Optional[Any] = None,
        gpu_monitor: Optional[Any] = None,
        memory_monitor: Optional[Any] = None,
        config: Optional[DashboardConfiguration] = None,
        on_alert_click: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize monitoring dashboard.
        
        Args:
            hardware_monitor: Hardware monitoring service
            gpu_monitor: GPU monitoring service
            memory_monitor: Memory monitoring service
            config: Dashboard configuration
            on_alert_click: Callback for alert interactions
        """
        super().__init__()
        self._hardware_monitor = hardware_monitor
        self._gpu_monitor = gpu_monitor
        self._memory_monitor = memory_monitor
        self._config = config or DashboardConfiguration()
        self._on_alert_click = on_alert_click
        
        # UI state
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._current_metrics: Optional[Any] = None
        self._metrics_history: List[Any] = []
        
        # UI components
        self._cpu_chart: Optional[ft.LineChart] = None
        self._memory_chart: Optional[ft.LineChart] = None
        self._gpu_chart: Optional[ft.LineChart] = None
        self._disk_chart: Optional[ft.LineChart] = None
        self._network_chart: Optional[ft.LineChart] = None
        
        # Status indicators
        self._cpu_indicator: Optional[ft.Container] = None
        self._memory_indicator: Optional[ft.Container] = None
        self._gpu_indicator: Optional[ft.Container] = None
        self._disk_indicator: Optional[ft.Container] = None
        self._system_health_indicator: Optional[ft.Container] = None
        
        # Metric displays
        self._cpu_usage_text: Optional[ft.Text] = None
        self._memory_usage_text: Optional[ft.Text] = None
        self._gpu_usage_text: Optional[ft.Text] = None
        self._disk_usage_text: Optional[ft.Text] = None
        self._network_usage_text: Optional[ft.Text] = None
        
        # Control buttons
        self._start_stop_button: Optional[ft.ElevatedButton] = None
        self._refresh_rate_dropdown: Optional[ft.Dropdown] = None
        self._settings_button: Optional[ft.IconButton] = None
    
    def build(self) -> ft.Control:
        """Build the monitoring dashboard UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header section
        header = self._create_header()
        
        # Create metrics overview cards
        metrics_overview = self._create_metrics_overview()
        
        # Create charts section
        charts_section = self._create_charts_section()
        
        # Create system health section
        health_section = self._create_health_section()
        
        # Create controls section
        controls_section = self._create_controls_section()
        
        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=spacing.md),
                metrics_overview,
                ft.Container(height=spacing.lg),
                charts_section,
                ft.Container(height=spacing.lg),
                health_section,
                ft.Container(height=spacing.md),
                controls_section
            ], scroll=ft.ScrollMode.AUTO),
            bgcolor=palette.background_primary,
            padding=ft.padding.all(spacing.lg),
            expand=True
        )
    
    def _create_header(self) -> ft.Control:
        """Create dashboard header with title and status."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        status_color = palette.success if self._is_monitoring else palette.text_tertiary
        status_text = "Monitoring Active" if self._is_monitoring else "Monitoring Stopped"
        status_icon_size = rlm.get_breakpoint_value(10, 12, 14, 16)
        
        # Use responsive padding values
        header_padding = rlm.get_breakpoint_value(12, 16, 20, 24)
        border_radius = rlm.get_breakpoint_value(6, 8, 10, 12)

        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(
                        "System Resource Monitor",
                        style=self.get_text_style('h1'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "Real-time system performance monitoring and analysis",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], expand=True),
                ft.Column([
                    ft.Row([
                        ft.Icon(
                            self.get_icon('CIRCLE'),
                            color=status_color,
                            size=status_icon_size
                        ),
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
            padding=ft.padding.all(header_padding),
            border_radius=ft.border_radius.all(border_radius),
            border=ft.border.all(1, palette.borders)
        )
    
    def _create_metrics_overview(self) -> ft.Control:
        """Create metrics overview cards."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # CPU card
        cpu_card = self._create_metric_card(
            "CPU Usage",
            "0%",
            self.get_icon('CPU'),
            palette.primary,
            ref_key="cpu_usage_text"
        )
        
        # Memory card
        memory_card = self._create_metric_card(
            "Memory Usage", 
            "0%",
            self.get_icon('MEMORY'),
            palette.info,
            ref_key="memory_usage_text"
        )
        
        # GPU card (if enabled)
        gpu_card = None
        if self._config.show_gpu_metrics:
            gpu_card = self._create_metric_card(
                "GPU Usage",
                "0%", 
                self.get_icon('GPU'),
                palette.warning,
                ref_key="gpu_usage_text"
            )
        
        # Disk card
        disk_card = self._create_metric_card(
            "Disk I/O",
            "0 MB/s",
            self.get_icon('MEMORY'),
            palette.secondary,
            ref_key="disk_usage_text"
        )
        
        # Network card (if enabled)
        network_card = None
        if self._config.show_network_metrics:
            network_card = self._create_metric_card(
                "Network",
                "0 MB/s",
                self.get_icon('NETWORK'),
                palette.success,
                ref_key="network_usage_text"
            )
        
        # Arrange cards in responsive grid
        cards = [cpu_card, memory_card, disk_card]
        if gpu_card:
            cards.insert(2, gpu_card)
        if network_card:
            cards.append(network_card)
        
        return ft.ResponsiveRow([
            ft.Container(
                content=card,
                col={"sm": 6, "md": 4, "lg": 3} if len(cards) > 4 else {"sm": 6, "md": 6, "lg": 4}
            ) for card in cards
        ])

    def _create_metric_card(self, title: str, value: str, icon: str, color: str, ref_key: str) -> ft.Control:
        """Create a metric display card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create text reference for updates
        value_text = ft.Text(
            value,
            style=self.get_text_style('metric_large'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD
        )

        # Store reference for updates
        if ref_key == "cpu_usage_text":
            self._cpu_usage_text = value_text
        elif ref_key == "memory_usage_text":
            self._memory_usage_text = value_text
        elif ref_key == "gpu_usage_text":
            self._gpu_usage_text = value_text
        elif ref_key == "disk_usage_text":
            self._disk_usage_text = value_text
        elif ref_key == "network_usage_text":
            self._network_usage_text = value_text

        # Use responsive values for all dimensions
        icon_size = rlm.get_breakpoint_value(20, 22, 24, 26)
        progress_height = rlm.get_breakpoint_value(3, 4, 4, 5)
        progress_width = rlm.get_breakpoint_value(50, 55, 60, 65)
        card_padding = rlm.get_breakpoint_value(12, 14, 16, 18)
        progress_border_radius = rlm.get_breakpoint_value(1, 2, 2, 3)

        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icon, color=color, size=icon_size),
                        ft.Text(
                            title,
                            style=self.get_text_style('body_medium'),
                            color=palette.text_secondary
                        )
                    ], spacing=spacing.sm),
                    ft.Container(height=spacing.sm),
                    value_text,
                    ft.Container(height=spacing.xs),
                    ft.Container(
                        height=progress_height,
                        bgcolor=color,
                        border_radius=ft.border_radius.all(progress_border_radius),
                        width=progress_width
                    )
                ]),
                padding=ft.padding.all(card_padding)
            ),
            color=palette.surface,
            elevation=1
        )

    def _create_charts_section(self) -> ft.Control:
        """Create charts section with resource utilization graphs."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Create individual charts
        cpu_chart = self._create_line_chart("CPU Usage (%)", palette.primary, "cpu")
        memory_chart = self._create_line_chart("Memory Usage (%)", palette.info, "memory")
        disk_chart = self._create_line_chart("Disk I/O (MB/s)", palette.secondary, "disk")

        charts = [
            ft.Container(
                content=ft.Column([
                    ft.Text(
                        "CPU Usage",
                        style=self.get_text_style('h4'),
                        color=palette.text_primary
                    ),
                    cpu_chart
                ]),
                col={"sm": 12, "md": 6, "lg": 4}
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Memory Usage",
                        style=self.get_text_style('h4'),
                        color=palette.text_primary
                    ),
                    memory_chart
                ]),
                col={"sm": 12, "md": 6, "lg": 4}
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Disk I/O",
                        style=self.get_text_style('h4'),
                        color=palette.text_primary
                    ),
                    disk_chart
                ]),
                col={"sm": 12, "md": 6, "lg": 4}
            )
        ]

        # Add GPU chart if enabled
        if self._config.show_gpu_metrics:
            gpu_chart = self._create_line_chart("GPU Usage (%)", palette.warning, "gpu")
            charts.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "GPU Usage",
                            style=self.get_text_style('h4'),
                            color=palette.text_primary
                        ),
                        gpu_chart
                    ]),
                    col={"sm": 12, "md": 6, "lg": 4}
                )
            )

        # Add network chart if enabled
        if self._config.show_network_metrics:
            network_chart = self._create_line_chart("Network (MB/s)", palette.success, "network")
            charts.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "Network I/O",
                            style=self.get_text_style('h4'),
                            color=palette.text_primary
                        ),
                        network_chart
                    ]),
                    col={"sm": 12, "md": 6, "lg": 4}
                )
            )

        # Use responsive values for section styling
        section_padding = rlm.get_breakpoint_value(12, 16, 20, 24)
        section_border_radius = rlm.get_breakpoint_value(6, 8, 10, 12)

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Resource Utilization Charts",
                    style=self.get_text_style('h2'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.ResponsiveRow(charts)
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(section_padding),
            border_radius=ft.border_radius.all(section_border_radius),
            border=ft.border.all(1, palette.borders)
        )

    def _create_line_chart(self, title: str, color: str, chart_type: str) -> ft.Control:
        """Create a line chart for resource metrics."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        title_font_size = rlm.get_breakpoint_value(10, 12, 14, 16)
        axis_space = rlm.get_breakpoint_value(28, 36, 44, 52)
        stroke_width = rlm.get_breakpoint_value(2, 2, 3, 3)
        chart_height = rlm.get_breakpoint_value(160, 200, 240, 280)
        corner_radius = spacing.sm
        padding_val = spacing.sm

        # Create chart with initial empty data
        chart = ft.LineChart(
            data_series=[
                ft.LineChartData(
                    data_points=[],
                    stroke_width=stroke_width,
                    color=color,
                    curved=True,
                    stroke_cap_round=True
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
                title=ft.Text(title, size=title_font_size, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Time", size=title_font_size, color=palette.text_secondary),
                title_size=axis_space,
                labels_size=axis_space
            ),
            tooltip_bgcolor=palette.surface,
            min_y=0,
            max_y=100 if "%" in title else 1000,
            min_x=0,
            max_x=self._config.history_minutes * 60,
            expand=True
        )

        # Store chart reference
        if chart_type == "cpu":
            self._cpu_chart = chart
        elif chart_type == "memory":
            self._memory_chart = chart
        elif chart_type == "gpu":
            self._gpu_chart = chart
        elif chart_type == "disk":
            self._disk_chart = chart
        elif chart_type == "network":
            self._network_chart = chart

        return ft.Container(
            content=chart,
            height=chart_height,
            bgcolor=palette.background_secondary,
            border_radius=ft.border_radius.all(corner_radius),
            padding=ft.padding.all(padding_val)
        )

    def _create_health_section(self) -> ft.Control:
        """Create system health status section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # System health indicator
        health_indicator = ft.Container(
            content=ft.Row([
                ft.Icon(self.get_icon('HEALTH'), color=palette.success, size=20),
                ft.Text(
                    "System Healthy",
                    style=self.get_text_style('body_medium'),
                    color=palette.success
                )
            ], spacing=spacing.sm),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(4),
            border=ft.border.all(1, palette.success)
        )
        self._system_health_indicator = health_indicator

        # Performance recommendations
        recommendations = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Performance Recommendations",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text(
                    "• System running optimally\n• No performance issues detected\n• All resources within normal ranges",
                    style=self.get_text_style('body_small'),
                    color=palette.text_secondary
                )
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(4),
            border=ft.border.all(1, palette.borders)
        )

        # Use responsive column layout
        health_col_config = rlm.get_breakpoint_value(
            {"sm": 12, "md": 12, "lg": 6},  # Mobile: full width
            {"sm": 12, "md": 6, "lg": 6},   # Tablet: half width
            {"sm": 12, "md": 6, "lg": 6},   # Desktop: half width
            {"sm": 12, "md": 6, "lg": 6}    # Large: half width
        )

        return ft.ResponsiveRow([
            ft.Container(
                content=health_indicator,
                col=health_col_config
            ),
            ft.Container(
                content=recommendations,
                col=health_col_config
            )
        ])

    def _create_controls_section(self) -> ft.Control:
        """Create monitoring controls section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Start/Stop monitoring button
        self._start_stop_button = ft.ElevatedButton(
            text="Start Monitoring" if not self._is_monitoring else "Stop Monitoring",
            icon=self.get_icon('PLAY') if not self._is_monitoring else self.get_icon('STOP'),
            on_click=self._toggle_monitoring,
            bgcolor=palette.primary,
            color=palette.text_primary
        )

        # Refresh rate dropdown
        self._refresh_rate_dropdown = ft.Dropdown(
            label="Refresh Rate",
            value=str(self._config.refresh_interval_seconds),
            options=[
                ft.dropdown.Option("0.5", "0.5 seconds"),
                ft.dropdown.Option("1.0", "1 second"),
                ft.dropdown.Option("2.0", "2 seconds"),
                ft.dropdown.Option("5.0", "5 seconds")
            ],
            on_change=self._on_refresh_rate_change,
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.borders
        )

        # Settings button
        self._settings_button = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            tooltip="Dashboard Settings",
            on_click=self._show_settings,
            icon_color=palette.text_secondary
        )

        # Use responsive values for controls section
        controls_padding = rlm.get_breakpoint_value(12, 16, 20, 24)
        controls_border_radius = rlm.get_breakpoint_value(6, 8, 10, 12)
        button_spacing = rlm.get_breakpoint_value(8, 12, 16, 20)

        return ft.Container(
            content=ft.Row([
                self._start_stop_button,
                ft.Container(width=button_spacing),
                self._refresh_rate_dropdown,
                ft.Container(width=button_spacing),
                self._settings_button
            ], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=palette.surface,
            padding=ft.padding.all(controls_padding),
            border_radius=ft.border_radius.all(controls_border_radius),
            border=ft.border.all(1, palette.borders)
        )

    async def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True

        # Start monitoring services
        if self._hardware_monitor:
            await self._hardware_monitor.start_monitoring(self._config.refresh_interval_seconds)
        if self._gpu_monitor:
            await self._gpu_monitor.start_monitoring(self._config.refresh_interval_seconds)
        if self._memory_monitor:
            await self._memory_monitor.start_monitoring(self._config.refresh_interval_seconds)

        # Start UI update task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        # Update UI
        if self._start_stop_button:
            self._start_stop_button.text = "Stop Monitoring"
            self._start_stop_button.icon = self.get_icon('STOP')

        self.update()

    async def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
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

        # Stop monitoring services
        if self._hardware_monitor:
            await self._hardware_monitor.stop_monitoring()
        if self._gpu_monitor:
            await self._gpu_monitor.stop_monitoring()
        if self._memory_monitor:
            await self._memory_monitor.stop_monitoring()

        # Update UI
        if self._start_stop_button:
            self._start_stop_button.text = "Start Monitoring"
            self._start_stop_button.icon = self.get_icon('PLAY')

        self.update()

    async def _monitoring_loop(self) -> None:
        """Main monitoring update loop."""
        try:
            while self._is_monitoring:
                # Collect current metrics
                if self._hardware_monitor:
                    metrics = self._hardware_monitor.get_current_metrics()
                    if metrics:
                        self._current_metrics = metrics
                        self._metrics_history.append(metrics)

                        # Limit history size
                        max_history = int(self._config.history_minutes * 60 / self._config.refresh_interval_seconds)
                        if len(self._metrics_history) > max_history:
                            self._metrics_history = self._metrics_history[-max_history:]

                        # Update UI
                        self._update_metrics_display()
                        self._update_charts()
                        self._update_health_status()

                # Wait for next update
                await asyncio.sleep(self._config.refresh_interval_seconds)

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

        # Update CPU usage
        if self._cpu_usage_text:
            self._cpu_usage_text.value = f"{metrics.cpu_usage_percent:.1f}%"

        # Update memory usage
        if self._memory_usage_text:
            self._memory_usage_text.value = f"{metrics.memory_usage_percent:.1f}%"

        # Update GPU usage
        if self._gpu_usage_text and metrics.gpu_usage_percent is not None:
            self._gpu_usage_text.value = f"{metrics.gpu_usage_percent:.1f}%"

        # Update disk I/O
        if self._disk_usage_text:
            total_io = metrics.disk_read_mb_per_sec + metrics.disk_write_mb_per_sec
            self._disk_usage_text.value = f"{total_io:.1f} MB/s"

        # Update network I/O
        if self._network_usage_text:
            total_network = metrics.network_sent_mb_per_sec + metrics.network_recv_mb_per_sec
            self._network_usage_text.value = f"{total_network:.1f} MB/s"

        self.update()

    def _update_charts(self) -> None:
        """Update charts with latest metrics data."""
        if not self._metrics_history:
            return

        # Prepare time-based data points
        current_time = datetime.now()
        time_window = timedelta(minutes=self._config.history_minutes)

        # Filter metrics within time window
        recent_metrics = [
            m for m in self._metrics_history
            if current_time - m.timestamp <= time_window
        ]

        if not recent_metrics:
            return

        # Update CPU chart
        if self._cpu_chart:
            cpu_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.cpu_usage_percent
                ) for m in recent_metrics
            ]
            self._cpu_chart.data_series[0].data_points = cpu_points

        # Update memory chart
        if self._memory_chart:
            memory_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.memory_usage_percent
                ) for m in recent_metrics
            ]
            self._memory_chart.data_series[0].data_points = memory_points

        # Update GPU chart
        if self._gpu_chart:
            gpu_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.gpu_usage_percent or 0.0
                ) for m in recent_metrics
            ]
            self._gpu_chart.data_series[0].data_points = gpu_points

        # Update disk chart
        if self._disk_chart:
            disk_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.disk_read_mb_per_sec + m.disk_write_mb_per_sec
                ) for m in recent_metrics
            ]
            self._disk_chart.data_series[0].data_points = disk_points

        # Update network chart
        if self._network_chart:
            network_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.network_sent_mb_per_sec + m.network_recv_mb_per_sec
                ) for m in recent_metrics
            ]
            self._network_chart.data_series[0].data_points = network_points

        self.update()

    def _update_health_status(self) -> None:
        """Update system health status indicator."""
        if not self._current_metrics or not self._system_health_indicator:
            return

        palette = self.get_palette()
        metrics = self._current_metrics

        # Determine health status based on thresholds
        is_healthy = True
        health_issues = []

        if metrics.cpu_usage_percent > 90:
            is_healthy = False
            health_issues.append("High CPU usage")

        if metrics.memory_usage_percent > 90:
            is_healthy = False
            health_issues.append("High memory usage")

        if metrics.gpu_usage_percent and metrics.gpu_usage_percent > 95:
            is_healthy = False
            health_issues.append("High GPU usage")

        # Update health indicator
        if is_healthy:
            icon_color = palette.success
            text_color = palette.success
            border_color = palette.success
            status_text = "System Healthy"
            icon = self.get_icon('HEALTH')
        else:
            icon_color = palette.warning if len(health_issues) <= 2 else palette.error
            text_color = icon_color
            border_color = icon_color
            status_text = f"Issues Detected ({len(health_issues)})"
            icon = self.get_icon('WARNING') if len(health_issues) <= 2 else self.get_icon('ERROR')

        # Update indicator content
        rlm = self.get_responsive_layout()
        status_icon_size = rlm.get_breakpoint_value(14, 16, 18, 20)
        self._system_health_indicator.content = ft.Row([
            ft.Icon(icon, color=icon_color, size=status_icon_size),
            ft.Text(
                status_text,
                style=self.get_text_style('body_medium'),
                color=text_color
            )
        ], spacing=self.get_spacing().sm)

        self._system_health_indicator.border = ft.border.all(1, border_color)
        self.update()

    def _toggle_monitoring(self, e) -> None:
        """Toggle monitoring on/off."""
        if self._is_monitoring:
            asyncio.create_task(self.stop_monitoring())
        else:
            asyncio.create_task(self.start_monitoring())

    def _on_refresh_rate_change(self, e) -> None:
        """Handle refresh rate change."""
        try:
            new_rate = float(e.control.value)
            self._config.refresh_interval_seconds = new_rate

            # Restart monitoring with new rate if currently active
            if self._is_monitoring:
                asyncio.create_task(self._restart_monitoring())
        except ValueError:
            pass

    async def _restart_monitoring(self) -> None:
        """Restart monitoring with new configuration."""
        await self.stop_monitoring()
        await asyncio.sleep(0.1)  # Brief pause
        await self.start_monitoring()

    def _show_settings(self, e) -> None:
        """Show dashboard settings dialog."""
        # Placeholder for settings dialog
        if self._on_alert_click:
            self._on_alert_click("settings")

    def configure_dashboard(self, config: DashboardConfiguration) -> None:
        """Update dashboard configuration."""
        self._config = config

        # Update refresh rate dropdown if it exists
        if self._refresh_rate_dropdown:
            self._refresh_rate_dropdown.value = str(config.refresh_interval_seconds)

        self.update()

    def get_current_metrics(self) -> Optional[Any]:
        """Get current resource metrics."""
        return self._current_metrics

    def get_metrics_history(self) -> List[Any]:
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
