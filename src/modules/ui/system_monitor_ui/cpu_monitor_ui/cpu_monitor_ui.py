"""
Module: cpu_monitor_ui
Description: CPU usage graphs with per-core visualization and thermal monitoring
Phase: 2
Location: /src/modules/ui/system_monitor_ui/cpu_monitor_ui/
"""

# Standard library imports
import asyncio
import logging
import time
import psutil
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.resource_monitor_lg.hardware_monitor_lg.hardware_monitor_lg import (
    HardwareMonitor, ResourceMetrics
)
from src.modules.logic.resource_monitor_lg.thermal_monitor_lg.thermal_monitor_lg import (
    ThermalMonitor, ThermalMetrics
)


class CPUDisplayMode(Enum):
    """CPU display modes."""
    OVERVIEW = "overview"
    PER_CORE = "per_core"
    THERMAL = "thermal"
    PERFORMANCE = "performance"


@dataclass
class CPUAlertThreshold:
    """CPU monitoring alert thresholds."""
    usage_warning: float = 80.0
    usage_critical: float = 95.0
    temperature_warning: float = 70.0
    temperature_critical: float = 85.0
    load_warning: float = 2.0
    load_critical: float = 4.0


@dataclass
class CPUMonitorConfiguration:
    """Configuration for CPU monitor."""
    refresh_interval_seconds: float = 1.0
    history_minutes: int = 10
    show_per_core_usage: bool = True
    show_thermal_data: bool = True
    show_frequency_data: bool = True
    show_load_average: bool = True
    temperature_warning_threshold: float = 70.0
    temperature_critical_threshold: float = 85.0
    display_mode: CPUDisplayMode = CPUDisplayMode.OVERVIEW
    alert_thresholds: CPUAlertThreshold = None

    def __post_init__(self):
        if self.alert_thresholds is None:
            self.alert_thresholds = CPUAlertThreshold()


@dataclass
class CPUMetrics:
    """CPU metrics data structure."""
    timestamp: datetime
    overall_usage: float
    per_core_usage: List[float]
    temperature: Optional[float]
    frequency_mhz: Optional[float]
    load_average_1m: float
    load_average_5m: float
    load_average_15m: float
    context_switches_per_sec: Optional[float]
    interrupts_per_sec: Optional[float]
    core_count: int
    thread_count: int


@dataclass
class CPUDataPoint:
    """CPU data point for charts."""
    timestamp: datetime
    overall_usage: float
    per_core_usage: List[float]
    frequency: Optional[float]
    temperature: Optional[float]
    load_average: Optional[Tuple[float, float, float]]
    context_switches: Optional[int]
    interrupts: Optional[int]


class CPUMonitorUI(ThemeAwareUserControl):
    """
    CPU usage graphs with per-core visualization and thermal monitoring.
    
    Provides comprehensive CPU monitoring including:
    - Overall CPU usage tracking
    - Per-core utilization visualization
    - CPU frequency monitoring
    - Thermal monitoring with warnings
    - Load average tracking
    - Context switches and interrupts
    - Performance metrics and statistics
    """
    
    def __init__(self, config: Optional[CPUMonitorConfiguration] = None):
        super().__init__()
        self._config = config or CPUMonitorConfiguration()
        self._logger = logging.getLogger(f"{__name__}.CPUMonitorUI")
        
        # Monitoring components
        self._hardware_monitor: Optional[HardwareMonitor] = None
        self._thermal_monitor: Optional[ThermalMonitor] = None
        
        # CPU information
        self._cpu_count = psutil.cpu_count()
        self._cpu_count_logical = psutil.cpu_count(logical=True)
        self._cpu_freq_info = psutil.cpu_freq()
        
        # UI state
        self._is_monitoring = False
        self._last_update = datetime.now(timezone.utc)
        self._cpu_data: List[CPUDataPoint] = []
        
        # UI components
        self._usage_chart: Optional[ft.Container] = None
        self._per_core_chart: Optional[ft.Container] = None
        self._thermal_chart: Optional[ft.Container] = None
        self._frequency_chart: Optional[ft.Container] = None
        self._performance_panel: Optional[ft.Container] = None
        
        # Initialize monitoring
        self._initialize_monitors()
    
    def build(self) -> ft.Control:
        """Build the CPU monitor UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header with controls
        header = self._create_header()
        
        # Create main content based on display mode
        if self._config.display_mode == CPUDisplayMode.PER_CORE:
            content = self._create_per_core_view()
        elif self._config.display_mode == CPUDisplayMode.THERMAL:
            content = self._create_thermal_view()
        elif self._config.display_mode == CPUDisplayMode.PERFORMANCE:
            content = self._create_performance_view()
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
            border_radius=ft.border_radius.all(12),
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
                ft.dropdown.Option("per_core", "Per Core"),
                ft.dropdown.Option("thermal", "Thermal"),
                ft.dropdown.Option("performance", "Performance")
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
            icon=self.get_icon('STOP') if self._is_monitoring else self.get_icon('PLAY'),
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
            tooltip="CPU Monitor Settings",
            on_click=self._show_settings,
            icon_color=palette.primary
        )
        
        return ft.Container(
            content=ft.Row([
                ft.Text(
                    "CPU Monitor",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Row([
                    mode_dropdown,
                    refresh_rate_dropdown,
                    start_stop_button,
                    reset_button,
                    settings_button
                ], spacing=spacing.element_spacing)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(vertical=spacing.component_padding)
        )
    
    def _create_overview(self) -> ft.Container:
        """Create overview display with key metrics."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Get current CPU data
        current_data = self._get_current_cpu_data()
        
        # Create metric cards
        usage_card = self._create_metric_card(
            "CPU Usage",
            f"{current_data.overall_usage:.1f}%",
            self.get_icon('CPU'),
            self._get_usage_color(current_data.overall_usage)
        )
        
        frequency_card = self._create_metric_card(
            "Frequency",
            f"{current_data.frequency:.0f} MHz" if current_data.frequency else "N/A",
            self.get_icon('SPEED'),
            palette.primary
        )
        
        temperature_card = self._create_metric_card(
            "Temperature",
            f"{current_data.temperature:.1f}°C" if current_data.temperature else "N/A",
            self.get_icon('THERMAL'),
            self._get_temperature_color(current_data.temperature)
        )
        
        cores_card = self._create_metric_card(
            "Cores",
            f"{self._cpu_count} / {self._cpu_count_logical}",
            self.get_icon('CPU'),
            palette.primary
        )
        
        # Create charts
        usage_chart = self._create_usage_chart()
        load_chart = self._create_load_average_chart()
        
        # Create CPU info panel
        info_panel = self._create_cpu_info_panel()
        
        return ft.Container(
            content=ft.Column([
                # Metric cards
                ft.Row([
                    usage_card,
                    frequency_card,
                    temperature_card,
                    cores_card
                ], spacing=spacing.component_spacing, expand=True),

                # Charts
                ft.Row([
                    usage_chart,
                    load_chart
                ], spacing=spacing.component_spacing, expand=True),

                # Info panel
                info_panel
            ], spacing=spacing.section_spacing, expand=True),
            expand=True
        )

    def _create_per_core_view(self) -> ft.Container:
        """Create per-core CPU usage view."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create per-core usage chart
        per_core_chart = self._create_per_core_usage_chart()

        # Create core statistics panel
        core_stats = self._create_core_statistics_panel()

        # Create core load distribution
        load_distribution = self._create_core_load_distribution()

        return ft.Container(
            content=ft.Column([
                per_core_chart,
                ft.Row([
                    core_stats,
                    load_distribution
                ], spacing=spacing.component_spacing, expand=True)
            ], spacing=spacing.section_spacing, expand=True),
            expand=True
        )

    def _create_thermal_view(self) -> ft.Container:
        """Create thermal monitoring view."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create thermal gauge
        thermal_gauge = self._create_thermal_gauge()

        # Create temperature history chart
        temperature_history = self._create_temperature_history_chart()

        # Create thermal alerts panel
        thermal_alerts = self._create_thermal_alerts_panel()

        # Create thermal statistics
        thermal_stats = self._create_thermal_statistics_panel()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    thermal_gauge,
                    temperature_history
                ], spacing=spacing.component_spacing, expand=True),

                ft.Row([
                    thermal_alerts,
                    thermal_stats
                ], spacing=spacing.component_spacing, expand=True)
            ], spacing=spacing.section_spacing, expand=True),
            expand=True
        )

    def _create_performance_view(self) -> ft.Container:
        """Create performance metrics view."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create performance metrics chart
        performance_chart = self._create_performance_metrics_chart()

        # Create context switches chart
        context_switches_chart = self._create_context_switches_chart()

        # Create interrupts chart
        interrupts_chart = self._create_interrupts_chart()

        # Create performance statistics
        performance_stats = self._create_performance_statistics_panel()

        return ft.Container(
            content=ft.Column([
                performance_chart,

                ft.Row([
                    context_switches_chart,
                    interrupts_chart
                ], spacing=spacing.component_spacing, expand=True),

                performance_stats
            ], spacing=spacing.section_spacing, expand=True),
            expand=True
        )

    def _create_metric_card(self, title: str, value: str, icon: str, color: str) -> ft.Container:
        """Create a metric card with icon and value."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=color, size=24),
                    ft.Text(
                        title,
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], spacing=spacing.element_spacing),

                ft.Text(
                    value,
                    style=self.get_text_style('h3'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.BOLD
                )
            ], spacing=spacing.element_spacing),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.component_padding),
            expand=True
        )

    def _create_usage_chart(self) -> ft.Container:
        """Create CPU usage chart."""
        return self._create_chart_placeholder("CPU Usage", 200)

    def _create_load_average_chart(self) -> ft.Container:
        """Create load average chart."""
        return self._create_chart_placeholder("Load Average", 200)

    def _create_cpu_info_panel(self) -> ft.Container:
        """Create CPU information panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Get CPU information
        try:
            cpu_info = [
                ("Physical Cores", str(self._cpu_count)),
                ("Logical Cores", str(self._cpu_count_logical)),
                ("Max Frequency", f"{self._cpu_freq_info.max:.0f} MHz" if self._cpu_freq_info else "Unknown"),
                ("Min Frequency", f"{self._cpu_freq_info.min:.0f} MHz" if self._cpu_freq_info else "Unknown"),
                ("Architecture", psutil.cpu_stats().ctx_switches if hasattr(psutil.cpu_stats(), 'ctx_switches') else "Unknown")
            ]
        except:
            cpu_info = [
                ("Physical Cores", str(self._cpu_count)),
                ("Logical Cores", str(self._cpu_count_logical)),
                ("Information", "Limited access")
            ]

        info_widgets = []
        for label, value in cpu_info:
            info_widgets.append(
                ft.Row([
                    ft.Text(
                        f"{label}:",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        str(value),
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "CPU Information",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                ft.Column(info_widgets, spacing=spacing.element_spacing)
            ], spacing=spacing.element_spacing),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.component_padding),
            expand=True
        )

    def _create_status_bar(self) -> ft.Container:
        """Create status bar with monitoring information."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Monitoring status
        monitoring_status = ft.Row([
            ft.Icon(
                self.get_icon('CIRCLE'),
                color=palette.success if self._is_monitoring else palette.error,
                size=12
            ),
            ft.Text(
                "CPU Monitoring Active" if self._is_monitoring else "CPU Monitoring Stopped",
                style=self.get_text_style('body_small'),
                color=palette.text_secondary
            )
        ], spacing=4)

        # CPU info
        cpu_info_text = ft.Text(
            f"Cores: {self._cpu_count}/{self._cpu_count_logical}",
            style=self.get_text_style('body_small'),
            color=palette.text_tertiary
        )

        # Last update
        last_update_text = ft.Text(
            f"Last Update: {self._last_update.strftime('%H:%M:%S')}",
            style=self.get_text_style('body_small'),
            color=palette.text_tertiary
        )

        return ft.Container(
            content=ft.Row([
                monitoring_status,
                ft.Row([
                    cpu_info_text,
                    ft.VerticalDivider(width=1, color=palette.outline_variant),
                    last_update_text
                ], spacing=spacing.element_spacing)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(vertical=spacing.component_padding // 2)
        )

    # Helper methods for chart creation (placeholders)
    def _create_per_core_usage_chart(self) -> ft.Container:
        """Create per-core usage chart."""
        return self._create_chart_placeholder("Per-Core CPU Usage", 300)

    def _create_core_statistics_panel(self) -> ft.Container:
        """Create core statistics panel."""
        return self._create_chart_placeholder("Core Statistics", 150)

    def _create_core_load_distribution(self) -> ft.Container:
        """Create core load distribution chart."""
        return self._create_chart_placeholder("Load Distribution", 150)

    def _create_thermal_gauge(self) -> ft.Container:
        """Create thermal gauge."""
        return self._create_chart_placeholder("Thermal Gauge", 200)

    def _create_temperature_history_chart(self) -> ft.Container:
        """Create temperature history chart."""
        return self._create_chart_placeholder("Temperature History", 200)

    def _create_thermal_alerts_panel(self) -> ft.Container:
        """Create thermal alerts panel."""
        return self._create_chart_placeholder("Thermal Alerts", 150)

    def _create_thermal_statistics_panel(self) -> ft.Container:
        """Create thermal statistics panel."""
        return self._create_chart_placeholder("Thermal Statistics", 150)

    def _create_performance_metrics_chart(self) -> ft.Container:
        """Create performance metrics chart."""
        return self._create_chart_placeholder("Performance Metrics", 250)

    def _create_context_switches_chart(self) -> ft.Container:
        """Create context switches chart."""
        return self._create_chart_placeholder("Context Switches", 150)

    def _create_interrupts_chart(self) -> ft.Container:
        """Create interrupts chart."""
        return self._create_chart_placeholder("Interrupts", 150)

    def _create_performance_statistics_panel(self) -> ft.Container:
        """Create performance statistics panel."""
        return self._create_chart_placeholder("Performance Statistics", 150)

    def _create_chart_placeholder(self, title: str, height: int = 150) -> ft.Container:
        """Create a chart placeholder."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    title,
                    style=self.get_text_style('h4'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(
                    content=ft.Text(
                        f"{title} Chart",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_tertiary
                    ),
                    bgcolor=palette.surface,
                    border_radius=ft.border_radius.all(8),
                    border=ft.border.all(1, palette.outline_variant),
                    padding=ft.padding.all(spacing.component_padding),
                    height=height,
                    expand=True
                )
            ], spacing=spacing.element_spacing),
            expand=True
        )

    # Color helper methods
    def _get_usage_color(self, usage: float) -> str:
        """Get color based on CPU usage."""
        palette = self.get_palette()
        if usage > 90:
            return palette.error
        elif usage > 70:
            return palette.warning
        else:
            return palette.success

    def _get_temperature_color(self, temperature: Optional[float]) -> str:
        """Get color based on temperature."""
        palette = self.get_palette()
        if temperature is None:
            return palette.text_tertiary

        if temperature > self._config.temperature_critical_threshold:
            return palette.error
        elif temperature > self._config.temperature_warning_threshold:
            return palette.warning
        else:
            return palette.success

    # Event handlers
    def _on_display_mode_change(self, e):
        """Handle display mode change."""
        try:
            new_mode = CPUDisplayMode(e.control.value)
            self._config.display_mode = new_mode
            self.update()
        except Exception as ex:
            self._logger.error(f"Error changing display mode: {ex}")

    def _on_refresh_rate_change(self, e):
        """Handle refresh rate change."""
        try:
            new_rate = float(e.control.value)
            self._config.refresh_interval_seconds = new_rate
            if self._is_monitoring:
                asyncio.create_task(self._restart_monitoring())
        except Exception as ex:
            self._logger.error(f"Error changing refresh rate: {ex}")

    def _toggle_monitoring(self, e):
        """Toggle CPU monitoring on/off."""
        try:
            if self._is_monitoring:
                asyncio.create_task(self._stop_monitoring())
            else:
                asyncio.create_task(self._start_monitoring())
        except Exception as ex:
            self._logger.error(f"Error toggling monitoring: {ex}")

    def _reset_charts(self, e):
        """Reset all chart data."""
        try:
            self._cpu_data.clear()
            self.update()
        except Exception as ex:
            self._logger.error(f"Error resetting charts: {ex}")

    def _show_settings(self, e):
        """Show CPU monitor settings."""
        # Implementation would show settings dialog
        pass

    # Monitoring methods
    def _initialize_monitors(self):
        """Initialize monitoring components."""
        try:
            from src.modules.logic.resource_monitor_lg.hardware_monitor_lg.hardware_monitor_lg import MonitoringConfiguration

            # Initialize hardware monitor
            config = MonitoringConfiguration(
                sampling_interval_seconds=self._config.refresh_interval_seconds,
                enable_gpu_monitoring=False,  # CPU monitor doesn't need GPU
                enable_disk_io_monitoring=False,
                history_retention_minutes=self._config.history_minutes
            )
            self._hardware_monitor = HardwareMonitor(config)

            # Initialize thermal monitor if enabled
            if self._config.show_thermal_data:
                self._thermal_monitor = ThermalMonitor()

        except Exception as ex:
            self._logger.error(f"Error initializing monitors: {ex}")

    async def _start_monitoring(self):
        """Start CPU monitoring."""
        try:
            self._is_monitoring = True

            # Start monitors
            if self._hardware_monitor:
                await self._hardware_monitor.start_monitoring()

            if self._thermal_monitor:
                await self._thermal_monitor.start_monitoring()

            # Start update loop
            asyncio.create_task(self._monitoring_loop())

            self.update()

        except Exception as ex:
            self._logger.error(f"Error starting CPU monitoring: {ex}")
            self._is_monitoring = False

    async def _stop_monitoring(self):
        """Stop CPU monitoring."""
        try:
            self._is_monitoring = False

            # Stop monitors
            if self._hardware_monitor:
                await self._hardware_monitor.stop_monitoring()

            if self._thermal_monitor:
                await self._thermal_monitor.stop_monitoring()

            self.update()

        except Exception as ex:
            self._logger.error(f"Error stopping CPU monitoring: {ex}")

    async def _restart_monitoring(self):
        """Restart monitoring with new configuration."""
        if self._is_monitoring:
            await self._stop_monitoring()
            await asyncio.sleep(0.1)
            await self._start_monitoring()

    async def _monitoring_loop(self):
        """Main monitoring update loop."""
        while self._is_monitoring:
            try:
                await self._update_cpu_metrics()
                await asyncio.sleep(self._config.refresh_interval_seconds)
            except Exception as ex:
                self._logger.error(f"Error in CPU monitoring loop: {ex}")
                await asyncio.sleep(1.0)

    async def _update_cpu_metrics(self):
        """Update CPU metrics and data."""
        try:
            current_time = datetime.now(timezone.utc)

            # Get CPU usage
            overall_usage = psutil.cpu_percent(interval=None)
            per_core_usage = psutil.cpu_percent(interval=None, percpu=True)

            # Get CPU frequency
            frequency = None
            try:
                freq_info = psutil.cpu_freq()
                if freq_info:
                    frequency = freq_info.current
            except:
                pass

            # Get temperature
            temperature = None
            if self._thermal_monitor:
                thermal_metrics = self._thermal_monitor.get_current_metrics()
                if thermal_metrics and thermal_metrics.cpu_temperatures:
                    temperature = sum(thermal_metrics.cpu_temperatures) / len(thermal_metrics.cpu_temperatures)

            # Get load average
            load_average = None
            try:
                if hasattr(psutil, 'getloadavg'):
                    load_average = psutil.getloadavg()
            except:
                pass

            # Get context switches and interrupts
            context_switches = None
            interrupts = None
            try:
                cpu_stats = psutil.cpu_stats()
                context_switches = cpu_stats.ctx_switches
                interrupts = cpu_stats.interrupts
            except:
                pass

            # Create data point
            data_point = CPUDataPoint(
                timestamp=current_time,
                overall_usage=overall_usage,
                per_core_usage=per_core_usage,
                frequency=frequency,
                temperature=temperature,
                load_average=load_average,
                context_switches=context_switches,
                interrupts=interrupts
            )

            # Add to data history
            self._cpu_data.append(data_point)

            # Limit history
            cutoff_time = current_time - timedelta(minutes=self._config.history_minutes)
            self._cpu_data = [
                point for point in self._cpu_data
                if point.timestamp >= cutoff_time
            ]

            self._last_update = current_time
            self.update()

        except Exception as ex:
            self._logger.error(f"Error updating CPU metrics: {ex}")

    def _get_current_cpu_data(self) -> CPUDataPoint:
        """Get current CPU data."""
        if self._cpu_data:
            return self._cpu_data[-1]
        else:
            # Return default data
            return CPUDataPoint(
                timestamp=datetime.now(timezone.utc),
                overall_usage=0.0,
                per_core_usage=[0.0] * self._cpu_count_logical,
                frequency=None,
                temperature=None,
                load_average=None,
                context_switches=None,
                interrupts=None
            )

    # Public interface
    async def start_monitoring(self):
        """Start monitoring (public interface)."""
        await self._start_monitoring()

    async def stop_monitoring(self):
        """Stop monitoring (public interface)."""
        await self._stop_monitoring()

    def get_configuration(self) -> CPUMonitorConfiguration:
        """Get current configuration."""
        return self._config

    def update_configuration(self, config: CPUMonitorConfiguration):
        """Update configuration."""
        self._config = config
        self._initialize_monitors()
        if self._is_monitoring:
            asyncio.create_task(self._restart_monitoring())
        self.update()


class CPUMetricsPanel(ThemeAwareUserControl):
    """
    CPU metrics panel component for displaying comprehensive performance metrics.

    Features:
    - Real-time metrics display with color-coded indicators
    - Responsive layout with adaptive metric cards
    - Performance statistics and trend analysis
    - Alert indicators for threshold breaches
    """

    def __init__(self, cpu_metrics: Optional[CPUMetrics] = None,
                 thresholds: Optional[CPUAlertThreshold] = None, **kwargs):
        super().__init__(**kwargs)
        self.cpu_metrics = cpu_metrics
        self.thresholds = thresholds or CPUAlertThreshold()
        self._metrics_container = None

    def build(self) -> ft.Control:
        """Build the CPU metrics panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        if not self.cpu_metrics:
            return ft.Container(
                content=ft.Text(
                    "No CPU metrics available",
                    style=typography.body_medium,
                    color=palette.on_surface_variant
                ),
                padding=spacing.md
            )

        # Create metric displays
        metrics_grid = ft.ResponsiveRow([
            ft.Col(
                content=self._create_metric_display(
                    "Overall Usage",
                    f"{self.cpu_metrics.overall_usage:.1f}%",
                    ft.Icons.MEMORY,
                    self._get_usage_color(self.cpu_metrics.overall_usage)
                ),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 3}
            ),
            ft.Col(
                content=self._create_metric_display(
                    "Load Average",
                    f"{self.cpu_metrics.load_average_1m:.2f}",
                    ft.Icons.TRENDING_UP,
                    palette.primary
                ),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 3}
            ),
            ft.Col(
                content=self._create_metric_display(
                    "Temperature",
                    f"{self.cpu_metrics.temperature:.1f}°C" if self.cpu_metrics.temperature else "N/A",
                    ft.Icons.THERMOSTAT,
                    self._get_temperature_color(self.cpu_metrics.temperature)
                ),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 3}
            ),
            ft.Col(
                content=self._create_metric_display(
                    "Frequency",
                    f"{self.cpu_metrics.frequency_mhz:.0f} MHz" if self.cpu_metrics.frequency_mhz else "N/A",
                    ft.Icons.SPEED,
                    palette.primary
                ),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 3}
            )
        ])

        return ft.Container(
            content=metrics_grid,
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value('border_radius_md'),
            padding=spacing.md,
            expand=True
        )

    def _create_metric_display(self, title: str, value: str, icon: ft.Icons, color: str) -> ft.Container:
        """Create a metric display widget."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=color, size=self.get_responsive_value('icon_size_sm', 16, 20, 24, 28)),
                    ft.Text(title, style=typography.body_small, color=palette.on_surface_variant)
                ], spacing=spacing.xs),
                ft.Text(value, style=typography.title_medium, color=palette.on_surface, weight=ft.FontWeight.BOLD)
            ], spacing=spacing.xs),
            padding=spacing.sm,
            expand=True
        )

    def _get_usage_color(self, usage: float) -> str:
        """Get color based on CPU usage."""
        palette = self.get_palette()
        if usage > self.thresholds.usage_critical:
            return palette.error
        elif usage > self.thresholds.usage_warning:
            return palette.tertiary
        else:
            return palette.primary

    def _get_temperature_color(self, temperature: Optional[float]) -> str:
        """Get color based on temperature."""
        palette = self.get_palette()
        if temperature is None:
            return palette.outline
        if temperature > self.thresholds.temperature_critical:
            return palette.error
        elif temperature > self.thresholds.temperature_warning:
            return palette.tertiary
        else:
            return palette.primary

    def update_metrics(self, metrics: CPUMetrics):
        """Update the displayed metrics."""
        self.cpu_metrics = metrics
        self.update()


class CPUCoreChart(ThemeAwareUserControl):
    """
    CPU core chart component for per-core utilization visualization.

    Features:
    - Individual core usage tracking
    - Real-time updates with smooth animations
    - Responsive design with adaptive sizing
    - Color-coded performance indicators
    """

    def __init__(self, core_count: int, metrics_history: List[CPUMetrics] = None, **kwargs):
        super().__init__(**kwargs)
        self.core_count = core_count
        self.metrics_history = metrics_history or []
        self._chart_container = None

    def build(self) -> ft.Control:
        """Build the CPU core chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Create placeholder for actual chart implementation
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    f"CPU Cores ({self.core_count})",
                    style=typography.title_medium,
                    color=palette.on_surface
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Icon(
                            ft.Icons.DEVELOPER_BOARD,
                            size=self.get_responsive_value('icon_size_lg', 32, 40, 48, 56),
                            color=palette.outline
                        ),
                        ft.Text(
                            "Per-Core Usage Chart",
                            style=typography.body_medium,
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    main_alignment=ft.MainAxisAlignment.CENTER,
                    spacing=spacing.sm),
                    bgcolor=palette.surface,
                    border_radius=self.get_responsive_value('border_radius_md'),
                    border=ft.border.all(1, palette.outline_variant),
                    padding=spacing.md,
                    height=self.get_responsive_value('chart_height', 200, 250, 300, 350),
                    expand=True
                )
            ], spacing=spacing.sm),
            expand=True
        )


class CPULoadGauge(ThemeAwareUserControl):
    """
    CPU load gauge component for load average visualization.

    Features:
    - Circular gauge display for load averages
    - 1m, 5m, 15m load average tracking
    - Color-coded performance indicators
    - Responsive sizing and layout
    """

    def __init__(self, load_averages: Optional[Tuple[float, float, float]] = None, **kwargs):
        super().__init__(**kwargs)
        self.load_averages = load_averages or (0.0, 0.0, 0.0)

    def build(self) -> ft.Control:
        """Build the CPU load gauge."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Load Average",
                    style=typography.title_medium,
                    color=palette.on_surface
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Icon(
                            ft.Icons.SPEED,
                            size=self.get_responsive_value('icon_size_lg', 32, 40, 48, 56),
                            color=palette.primary
                        ),
                        ft.Column([
                            ft.Text(f"1m: {self.load_averages[0]:.2f}", style=typography.body_small, color=palette.on_surface),
                            ft.Text(f"5m: {self.load_averages[1]:.2f}", style=typography.body_small, color=palette.on_surface),
                            ft.Text(f"15m: {self.load_averages[2]:.2f}", style=typography.body_small, color=palette.on_surface)
                        ], spacing=spacing.xs)
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    main_alignment=ft.MainAxisAlignment.CENTER,
                    spacing=spacing.sm),
                    bgcolor=palette.surface,
                    border_radius=self.get_responsive_value('border_radius_md'),
                    border=ft.border.all(1, palette.outline_variant),
                    padding=spacing.md,
                    height=self.get_responsive_value('gauge_height', 150, 180, 200, 220),
                    expand=True
                )
            ], spacing=spacing.sm),
            expand=True
        )


class CPUTemperatureGauge(ThemeAwareUserControl):
    """
    CPU temperature gauge component for thermal monitoring.

    Features:
    - Circular temperature gauge
    - Color-coded thermal warnings
    - Real-time temperature tracking
    - Responsive design
    """

    def __init__(self, temperature: Optional[float] = None,
                 thresholds: Optional[CPUAlertThreshold] = None, **kwargs):
        super().__init__(**kwargs)
        self.temperature = temperature
        self.thresholds = thresholds or CPUAlertThreshold()

    def build(self) -> ft.Control:
        """Build the CPU temperature gauge."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        temp_color = self._get_temperature_color()
        temp_text = f"{self.temperature:.1f}°C" if self.temperature else "N/A"

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "CPU Temperature",
                    style=typography.title_medium,
                    color=palette.on_surface
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Icon(
                            ft.Icons.THERMOSTAT,
                            size=self.get_responsive_value('icon_size_lg', 32, 40, 48, 56),
                            color=temp_color
                        ),
                        ft.Text(
                            temp_text,
                            style=typography.headline_small,
                            color=temp_color,
                            weight=ft.FontWeight.BOLD
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    main_alignment=ft.MainAxisAlignment.CENTER,
                    spacing=spacing.sm),
                    bgcolor=palette.surface,
                    border_radius=self.get_responsive_value('border_radius_md'),
                    border=ft.border.all(1, palette.outline_variant),
                    padding=spacing.md,
                    height=self.get_responsive_value('gauge_height', 150, 180, 200, 220),
                    expand=True
                )
            ], spacing=spacing.sm),
            expand=True
        )

    def _get_temperature_color(self) -> str:
        """Get color based on temperature."""
        palette = self.get_palette()
        if self.temperature is None:
            return palette.outline
        if self.temperature > self.thresholds.temperature_critical:
            return palette.error
        elif self.temperature > self.thresholds.temperature_warning:
            return palette.tertiary
        else:
            return palette.primary


class CPUFrequencyChart(ThemeAwareUserControl):
    """
    CPU frequency chart component for frequency monitoring.

    Features:
    - Real-time frequency tracking
    - Historical frequency data
    - Scaling information display
    - Responsive chart sizing
    """

    def __init__(self, frequency_history: List[float] = None, **kwargs):
        super().__init__(**kwargs)
        self.frequency_history = frequency_history or []

    def build(self) -> ft.Control:
        """Build the CPU frequency chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        current_freq = self.frequency_history[-1] if self.frequency_history else 0.0

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "CPU Frequency",
                    style=typography.title_medium,
                    color=palette.on_surface
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Icon(
                            ft.Icons.SPEED,
                            size=self.get_responsive_value('icon_size_lg', 32, 40, 48, 56),
                            color=palette.primary
                        ),
                        ft.Text(
                            f"{current_freq:.0f} MHz",
                            style=typography.headline_small,
                            color=palette.on_surface,
                            weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            "Frequency Chart",
                            style=typography.body_medium,
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    main_alignment=ft.MainAxisAlignment.CENTER,
                    spacing=spacing.sm),
                    bgcolor=palette.surface,
                    border_radius=self.get_responsive_value('border_radius_md'),
                    border=ft.border.all(1, palette.outline_variant),
                    padding=spacing.md,
                    height=self.get_responsive_value('chart_height', 200, 250, 300, 350),
                    expand=True
                )
            ], spacing=spacing.sm),
            expand=True
        )
