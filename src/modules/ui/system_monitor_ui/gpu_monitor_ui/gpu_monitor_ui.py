"""
Module: gpu_monitor_ui
Description: GPU utilization, VRAM usage, and temperature visualization components
Phase: 2
Location: /src/modules/ui/system_monitor_ui/gpu_monitor_ui/
"""

# Standard library imports
import asyncio
import logging
import math
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.resource_monitor_lg.gpu_monitor_lg.gpu_monitor_lg import (
    GPUMonitor, GPUMetrics, GPUInfo, CUDAInfo, ROCmInfo
)


class GPUDisplayMode(Enum):
    """GPU display modes."""
    OVERVIEW = "overview"
    DETAILED = "detailed"
    THERMAL = "thermal"
    MEMORY = "memory"


@dataclass
class GPUMonitorConfiguration:
    """Configuration for GPU monitor."""
    refresh_interval_seconds: float = 1.0
    history_minutes: int = 10
    show_temperature_warnings: bool = True
    show_memory_details: bool = True
    show_power_consumption: bool = True
    temperature_warning_threshold: float = 80.0
    temperature_critical_threshold: float = 90.0
    display_mode: GPUDisplayMode = GPUDisplayMode.OVERVIEW


@dataclass
class GPUAlertThreshold:
    """GPU monitoring alert thresholds."""
    temperature_warning: float = 75.0
    temperature_critical: float = 85.0
    utilization_high: float = 90.0
    memory_warning: float = 80.0
    memory_critical: float = 95.0
    power_warning: float = 90.0


@dataclass
class GPUDataPoint:
    """GPU data point for charts."""
    timestamp: datetime
    utilization: float
    memory_used: float
    memory_total: float
    temperature: Optional[float]
    power_draw: Optional[float]
    fan_speed: Optional[float]


class GPUMonitorUI(ThemeAwareUserControl):
    """
    GPU utilization, VRAM usage, and temperature visualization components.
    
    Provides comprehensive GPU monitoring including:
    - Real-time utilization graphs
    - VRAM usage and allocation tracking
    - Temperature monitoring with thermal warnings
    - Power consumption tracking
    - CUDA/ROCm compatibility information
    - Multi-GPU support
    - Performance metrics and statistics
    """
    
    def __init__(self, config: Optional[GPUMonitorConfiguration] = None):
        super().__init__()
        self._config = config or GPUMonitorConfiguration()
        self._logger = logging.getLogger(f"{__name__}.GPUMonitorUI")
        
        # GPU monitoring
        self._gpu_monitor: Optional[GPUMonitor] = None
        self._gpu_info: Dict[int, GPUInfo] = {}
        self._cuda_info: Optional[CUDAInfo] = None
        self._rocm_info: Optional[ROCmInfo] = None
        
        # UI state
        self._is_monitoring = False
        self._selected_gpu = 0
        self._last_update = datetime.now(timezone.utc)
        self._gpu_data: Dict[int, List[GPUDataPoint]] = {}
        
        # UI components
        self._gpu_selector: Optional[ft.Dropdown] = None
        self._utilization_chart: Optional[ft.Container] = None
        self._memory_chart: Optional[ft.Container] = None
        self._temperature_gauge: Optional[ft.Container] = None
        self._power_meter: Optional[ft.Container] = None
        self._info_panel: Optional[ft.Container] = None
        self._alerts_panel: Optional[ft.Container] = None
        
        # Initialize GPU monitor
        self._initialize_gpu_monitor()
    
    def build(self) -> ft.Control:
        """Build the GPU monitor UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header with GPU selector and controls
        header = self._create_header()
        
        # Create main content based on display mode
        if self._config.display_mode == GPUDisplayMode.THERMAL:
            content = self._create_thermal_view()
        elif self._config.display_mode == GPUDisplayMode.MEMORY:
            content = self._create_memory_view()
        elif self._config.display_mode == GPUDisplayMode.DETAILED:
            content = self._create_detailed_view()
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
            border_radius=ft.border_radius.all(self.get_breakpoint_value(8, 10, 12, 12)),
            border=ft.border.all(self.get_breakpoint_value(1, 1, 1, 1), palette.outline_variant),
            padding=ft.padding.all(self.get_breakpoint_value(int(spacing.component_padding*0.7), int(spacing.component_padding*0.85), spacing.component_padding, spacing.component_padding)),
            expand=True
        )
    
    def _create_header(self) -> ft.Container:
        """Create header with GPU selector and controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # GPU selector dropdown
        gpu_options = []
        for gpu_id, gpu_info in self._gpu_info.items():
            gpu_options.append(
                ft.dropdown.Option(
                    str(gpu_id),
                    f"GPU {gpu_id}: {gpu_info.name[:30]}..."
                )
            )
        
        if not gpu_options:
            gpu_options.append(ft.dropdown.Option("0", "No GPUs detected"))
        
        self._gpu_selector = ft.Dropdown(
            label="Select GPU",
            value=str(self._selected_gpu),
            options=gpu_options,
            on_change=self._on_gpu_selection_change,
            width=self.get_breakpoint_value(180, 220, 250, 280),
            text_style=self.get_text_style('body_medium'),
            bgcolor=palette.surface_variant
        )
        
        # Display mode selector
        mode_dropdown = ft.Dropdown(
            label="Display Mode",
            value=self._config.display_mode.value,
            options=[
                ft.dropdown.Option("overview", "Overview"),
                ft.dropdown.Option("detailed", "Detailed"),
                ft.dropdown.Option("thermal", "Thermal"),
                ft.dropdown.Option("memory", "Memory")
            ],
            on_change=self._on_display_mode_change,
            width=self.get_breakpoint_value(120, 140, 160, 180),
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
        
        refresh_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh GPU Info",
            on_click=self._refresh_gpu_info,
            icon_color=palette.primary
        )
        
        settings_button = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            tooltip="GPU Monitor Settings",
            on_click=self._show_settings,
            icon_color=palette.primary
        )
        
        return ft.Container(
            content=ft.Row([
                ft.Text(
                    "GPU Monitor",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Row([
                    self._gpu_selector,
                    mode_dropdown,
                    start_stop_button,
                    refresh_button,
                    settings_button
                ], spacing=spacing.element_spacing)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(vertical=spacing.component_padding)
        )
    
    def _create_overview(self) -> ft.Container:
        """Create overview display with key metrics."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Get current GPU data
        current_data = self._get_current_gpu_data()
        
        # Create metric cards
        utilization_card = self._create_metric_card(
            "GPU Utilization",
            f"{current_data.utilization:.1f}%",
            self.get_icon('CPU'),
            self._get_utilization_color(current_data.utilization)
        )
        
        memory_card = self._create_metric_card(
            "VRAM Usage",
            f"{current_data.memory_used:.1f} / {current_data.memory_total:.1f} GB",
            self.get_icon('MEMORY'),
            self._get_memory_color(current_data.memory_used, current_data.memory_total)
        )
        
        temperature_card = self._create_metric_card(
            "Temperature",
            f"{current_data.temperature:.1f}°C" if current_data.temperature else "N/A",
            self.get_icon('THERMAL'),
            self._get_temperature_color(current_data.temperature)
        )
        
        power_card = self._create_metric_card(
            "Power Draw",
            f"{current_data.power_draw:.1f}W" if current_data.power_draw else "N/A",
            self.get_icon('POWER'),
            palette.primary
        )
        
        # Create charts
        utilization_chart = self._create_utilization_chart()
        memory_chart = self._create_memory_chart()
        
        # Create GPU info panel
        info_panel = self._create_gpu_info_panel()
        
        return ft.Container(
            content=ft.Column([
                # Metric cards
                ft.Row([
                    utilization_card,
                    memory_card,
                    temperature_card,
                    power_card
                ], spacing=spacing.component_spacing, expand=True),

                # Charts
                ft.Row([
                    utilization_chart,
                    memory_chart
                ], spacing=spacing.component_spacing, expand=True),

                # Info panel
                info_panel
            ], spacing=spacing.section_spacing, expand=True),
            expand=True
        )

    def _create_detailed_view(self) -> ft.Container:
        """Create detailed view with comprehensive metrics."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create detailed charts
        utilization_chart = self._create_detailed_utilization_chart()
        memory_chart = self._create_detailed_memory_chart()
        temperature_chart = self._create_temperature_chart()
        power_chart = self._create_power_chart()

        # Create performance metrics panel
        performance_panel = self._create_performance_metrics_panel()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    utilization_chart,
                    memory_chart
                ], spacing=spacing.component_spacing, expand=True),

                ft.Row([
                    temperature_chart,
                    power_chart
                ], spacing=spacing.component_spacing, expand=True),

                performance_panel
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

        # Create fan control panel
        fan_control = self._create_fan_control_panel()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    thermal_gauge,
                    temperature_history
                ], spacing=spacing.component_spacing, expand=True),

                ft.Row([
                    thermal_alerts,
                    fan_control
                ], spacing=spacing.component_spacing, expand=True)
            ], spacing=spacing.section_spacing, expand=True),
            expand=True
        )

    def _create_memory_view(self) -> ft.Container:
        """Create memory-focused view."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create memory allocation chart
        allocation_chart = self._create_memory_allocation_chart()

        # Create memory usage breakdown
        usage_breakdown = self._create_memory_usage_breakdown()

        # Create memory bandwidth chart
        bandwidth_chart = self._create_memory_bandwidth_chart()

        # Create memory statistics panel
        memory_stats = self._create_memory_statistics_panel()

        return ft.Container(
            content=ft.Column([
                allocation_chart,

                ft.Row([
                    usage_breakdown,
                    bandwidth_chart
                ], spacing=spacing.component_spacing, expand=True),

                memory_stats
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

    def _create_utilization_chart(self) -> ft.Container:
        """Create GPU utilization chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Chart placeholder (would be replaced with actual chart implementation)
        chart_content = ft.Container(
            content=ft.Text(
                "GPU Utilization Chart",
                style=self.get_text_style('body_medium'),
                color=palette.text_tertiary
            ),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.outline_variant),
            padding=ft.padding.all(spacing.component_padding),
            height=200,
            expand=True
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "GPU Utilization",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                chart_content
            ], spacing=spacing.element_spacing),
            expand=True
        )

    def _create_memory_chart(self) -> ft.Container:
        """Create VRAM usage chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Chart placeholder
        chart_content = ft.Container(
            content=ft.Text(
                "VRAM Usage Chart",
                style=self.get_text_style('body_medium'),
                color=palette.text_tertiary
            ),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.outline_variant),
            padding=ft.padding.all(spacing.component_padding),
            height=200,
            expand=True
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "VRAM Usage",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.W_500
                ),
                chart_content
            ], spacing=spacing.element_spacing),
            expand=True
        )

    def _create_gpu_info_panel(self) -> ft.Container:
        """Create GPU information panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Get GPU info for selected GPU
        gpu_info = self._gpu_info.get(self._selected_gpu)
        if not gpu_info:
            return ft.Container(
                content=ft.Text(
                    "No GPU information available",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_tertiary
                ),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(8),
                padding=ft.padding.all(spacing.component_padding)
            )

        # Create info items
        info_items = [
            ("Name", gpu_info.name),
            ("Driver Version", gpu_info.driver_version or "Unknown"),
            ("Memory", f"{gpu_info.memory_total_mb / 1024:.1f} GB"),
            ("Compute Capability", f"{gpu_info.compute_capability_major}.{gpu_info.compute_capability_minor}" if gpu_info.compute_capability_major else "Unknown"),
            ("Multi-Processor Count", str(gpu_info.multiprocessor_count) if gpu_info.multiprocessor_count else "Unknown")
        ]

        info_widgets = []
        for label, value in info_items:
            info_widgets.append(
                ft.Row([
                    ft.Text(
                        f"{label}:",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        value,
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

        # Add CUDA/ROCm info
        if self._cuda_info and self._cuda_info.available:
            info_widgets.append(
                ft.Row([
                    ft.Text(
                        "CUDA Version:",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        self._cuda_info.version,
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

        if self._rocm_info and self._rocm_info.available:
            info_widgets.append(
                ft.Row([
                    ft.Text(
                        "ROCm Version:",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        self._rocm_info.version,
                        style=self.get_text_style('body_medium'),
                        color=palette.text_primary
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "GPU Information",
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
                "GPU Monitoring Active" if self._is_monitoring else "GPU Monitoring Stopped",
                style=self.get_text_style('body_small'),
                color=palette.text_secondary
            )
        ], spacing=4)

        # GPU count
        gpu_count_text = ft.Text(
            f"GPUs Detected: {len(self._gpu_info)}",
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
                    gpu_count_text,
                    ft.VerticalDivider(width=self.get_breakpoint_value(1, 1, 1, 1), color=palette.outline_variant),
                    last_update_text
                ], spacing=spacing.element_spacing)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(vertical=spacing.component_padding // 2)
        )

    # Helper methods for chart creation (placeholders)
    def _create_detailed_utilization_chart(self) -> ft.Container:
        """Create detailed utilization chart."""
        return self._create_chart_placeholder("Detailed GPU Utilization")

    def _create_detailed_memory_chart(self) -> ft.Container:
        """Create detailed memory chart."""
        return self._create_chart_placeholder("Detailed VRAM Usage")

    def _create_temperature_chart(self) -> ft.Container:
        """Create temperature chart."""
        return self._create_chart_placeholder("GPU Temperature")

    def _create_power_chart(self) -> ft.Container:
        """Create power consumption chart."""
        return self._create_chart_placeholder("Power Consumption")

    def _create_performance_metrics_panel(self) -> ft.Container:
        """Create performance metrics panel."""
        return self._create_chart_placeholder("Performance Metrics")

    def _create_thermal_gauge(self) -> ft.Container:
        """Create thermal gauge."""
        return self._create_chart_placeholder("Thermal Gauge")

    def _create_temperature_history_chart(self) -> ft.Container:
        """Create temperature history chart."""
        return self._create_chart_placeholder("Temperature History")

    def _create_thermal_alerts_panel(self) -> ft.Container:
        """Create thermal alerts panel."""
        return self._create_chart_placeholder("Thermal Alerts")

    def _create_fan_control_panel(self) -> ft.Container:
        """Create fan control panel."""
        return self._create_chart_placeholder("Fan Control")

    def _create_memory_allocation_chart(self) -> ft.Container:
        """Create memory allocation chart."""
        return self._create_chart_placeholder("Memory Allocation")

    def _create_memory_usage_breakdown(self) -> ft.Container:
        """Create memory usage breakdown."""
        return self._create_chart_placeholder("Memory Usage Breakdown")

    def _create_memory_bandwidth_chart(self) -> ft.Container:
        """Create memory bandwidth chart."""
        return self._create_chart_placeholder("Memory Bandwidth")

    def _create_memory_statistics_panel(self) -> ft.Container:
        """Create memory statistics panel."""
        return self._create_chart_placeholder("Memory Statistics")

    def _create_chart_placeholder(self, title: str) -> ft.Container:
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
                    border_radius=ft.border_radius.all(self.get_breakpoint_value(6, 8, 10, 12)),
                    border=ft.border.all(self.get_breakpoint_value(1, 1, 1, 1), palette.outline),
                    padding=ft.padding.all(self.get_breakpoint_value(int(spacing.component_padding*0.7), int(spacing.component_padding*0.85), spacing.component_padding, spacing.component_padding)),
                    height=self.get_breakpoint_value(110, 130, 150, 150),
                    expand=True
                )
            ], spacing=spacing.element_spacing),
            expand=True
        )

    # Color helper methods
    def _get_utilization_color(self, utilization: float) -> str:
        """Get color based on GPU utilization."""
        palette = self.get_palette()
        if utilization > 90:
            return palette.error
        elif utilization > 70:
            return palette.warning
        else:
            return palette.success

    def _get_memory_color(self, used: float, total: float) -> str:
        """Get color based on memory usage."""
        palette = self.get_palette()
        if total == 0:
            return palette.text_tertiary

        usage_percent = (used / total) * 100
        if usage_percent > 90:
            return palette.error
        elif usage_percent > 70:
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
    def _on_gpu_selection_change(self, e):
        """Handle GPU selection change."""
        try:
            self._selected_gpu = int(e.control.value)
            self.update()
        except Exception as ex:
            self._logger.error(f"Error changing GPU selection: {ex}")

    def _on_display_mode_change(self, e):
        """Handle display mode change."""
        try:
            new_mode = GPUDisplayMode(e.control.value)
            self._config.display_mode = new_mode
            self.update()
        except Exception as ex:
            self._logger.error(f"Error changing display mode: {ex}")

    def _toggle_monitoring(self, e):
        """Toggle GPU monitoring on/off."""
        try:
            if self._is_monitoring:
                asyncio.create_task(self._stop_monitoring())
            else:
                asyncio.create_task(self._start_monitoring())
        except Exception as ex:
            self._logger.error(f"Error toggling monitoring: {ex}")

    def _refresh_gpu_info(self, e):
        """Refresh GPU information."""
        try:
            self._initialize_gpu_monitor()
            self._update_gpu_selector()
            self.update()
        except Exception as ex:
            self._logger.error(f"Error refreshing GPU info: {ex}")

    def _show_settings(self, e):
        """Show GPU monitor settings."""
        # Implementation would show settings dialog
        pass

    # Monitoring methods
    def _initialize_gpu_monitor(self):
        """Initialize GPU monitor and detect GPUs."""
        try:
            self._gpu_monitor = GPUMonitor()

            # Get GPU information
            if self._gpu_monitor:
                self._gpu_info = self._gpu_monitor.get_gpu_info()
                self._cuda_info = self._gpu_monitor.get_cuda_info()
                self._rocm_info = self._gpu_monitor.get_rocm_info()

                # Initialize data storage for each GPU
                for gpu_id in self._gpu_info.keys():
                    self._gpu_data[gpu_id] = []

        except Exception as ex:
            self._logger.error(f"Error initializing GPU monitor: {ex}")

    def _update_gpu_selector(self):
        """Update GPU selector dropdown options."""
        if self._gpu_selector:
            gpu_options = []
            for gpu_id, gpu_info in self._gpu_info.items():
                gpu_options.append(
                    ft.dropdown.Option(
                        str(gpu_id),
                        f"GPU {gpu_id}: {gpu_info.name[:30]}..."
                    )
                )

            if not gpu_options:
                gpu_options.append(ft.dropdown.Option("0", "No GPUs detected"))

            self._gpu_selector.options = gpu_options

    async def _start_monitoring(self):
        """Start GPU monitoring."""
        try:
            self._is_monitoring = True

            if self._gpu_monitor:
                await self._gpu_monitor.start_monitoring()

                # Start update loop
                asyncio.create_task(self._monitoring_loop())

            self.update()

        except Exception as ex:
            self._logger.error(f"Error starting GPU monitoring: {ex}")
            self._is_monitoring = False

    async def _stop_monitoring(self):
        """Stop GPU monitoring."""
        try:
            self._is_monitoring = False

            if self._gpu_monitor:
                await self._gpu_monitor.stop_monitoring()

            self.update()

        except Exception as ex:
            self._logger.error(f"Error stopping GPU monitoring: {ex}")

    async def _monitoring_loop(self):
        """Main monitoring update loop."""
        while self._is_monitoring:
            try:
                await self._update_gpu_metrics()
                await asyncio.sleep(self._config.refresh_interval_seconds)
            except Exception as ex:
                self._logger.error(f"Error in GPU monitoring loop: {ex}")
                await asyncio.sleep(1.0)

    async def _update_gpu_metrics(self):
        """Update GPU metrics and data."""
        try:
            if not self._gpu_monitor:
                return

            current_time = datetime.now(timezone.utc)
            gpu_metrics = self._gpu_monitor.get_current_metrics()

            for gpu_id, metrics in gpu_metrics.items():
                if metrics:
                    data_point = GPUDataPoint(
                        timestamp=current_time,
                        utilization=metrics.utilization_percent,
                        memory_used=metrics.memory_used_mb / 1024,  # Convert to GB
                        memory_total=metrics.memory_total_mb / 1024,  # Convert to GB
                        temperature=metrics.temperature_celsius,
                        power_draw=metrics.power_draw_watts,
                        fan_speed=metrics.fan_speed_percent
                    )

                    # Add to data history
                    if gpu_id not in self._gpu_data:
                        self._gpu_data[gpu_id] = []

                    self._gpu_data[gpu_id].append(data_point)

                    # Limit history
                    cutoff_time = current_time - timedelta(minutes=self._config.history_minutes)
                    self._gpu_data[gpu_id] = [
                        point for point in self._gpu_data[gpu_id]
                        if point.timestamp >= cutoff_time
                    ]

            self._last_update = current_time
            self.update()

        except Exception as ex:
            self._logger.error(f"Error updating GPU metrics: {ex}")

    def _get_current_gpu_data(self) -> GPUDataPoint:
        """Get current data for selected GPU."""
        gpu_data = self._gpu_data.get(self._selected_gpu, [])
        if gpu_data:
            return gpu_data[-1]
        else:
            # Return default data
            return GPUDataPoint(
                timestamp=datetime.now(timezone.utc),
                utilization=0.0,
                memory_used=0.0,
                memory_total=0.0,
                temperature=None,
                power_draw=None,
                fan_speed=None
            )

    # Public interface
    async def start_monitoring(self):
        """Start monitoring (public interface)."""
        await self._start_monitoring()

    async def stop_monitoring(self):
        """Stop monitoring (public interface)."""
        await self._stop_monitoring()

    def get_configuration(self) -> GPUMonitorConfiguration:
        """Get current configuration."""
        return self._config

    def update_configuration(self, config: GPUMonitorConfiguration):
        """Update configuration."""
        self._config = config
        if self._is_monitoring:
            asyncio.create_task(self._stop_monitoring())
            asyncio.create_task(self._start_monitoring())
        self.update()


class UtilizationChart(ThemeAwareUserControl):
    """
    GPU utilization chart component for real-time performance monitoring.

    Displays GPU and memory utilization as interactive line charts with:
    - Real-time data updates with smooth animations
    - Historical trend visualization with configurable time windows
    - Interactive tooltips with detailed metrics
    - Responsive design with adaptive chart sizing
    """

    def __init__(self, gpu_id: int, metrics_history: List[GPUMetrics] = None, **kwargs):
        super().__init__(**kwargs)
        self.gpu_id = gpu_id
        self.metrics_history = metrics_history or []
        self._chart_container = None
        self._max_data_points = 60  # 1 minute at 1Hz

    def update_metrics(self, metrics_history: List[GPUMetrics]):
        """Update the chart with new metrics data."""
        self.metrics_history = metrics_history[-self._max_data_points:]
        if self._chart_container and self.page:
            self._update_chart_display()
            self.update()

    def _create_chart_display(self) -> ft.Control:
        """Create the utilization chart display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        if not self.metrics_history:
            return ft.Container(
                content=ft.Text(
                    "No data available",
                    style=self.get_text_style('body1'),
                    color=palette.text_secondary
                ),
                alignment=ft.alignment.center,
                height=200
            )

        # Responsive chart height
        chart_height = self.get_breakpoint_value(
            mobile=150, tablet=200, desktop=250, large=300
        )

        # Prepare chart data
        gpu_data = []
        memory_data = []

        for i, metrics in enumerate(self.metrics_history):
            gpu_data.append(ft.LineChartDataPoint(i, metrics.utilization_percent))
            memory_data.append(ft.LineChartDataPoint(i, metrics.memory_utilization_percent))

        return ft.Container(
            content=ft.LineChart(
                data_series=[
                    ft.LineChartData(
                        data_points=gpu_data,
                        stroke_width=2,
                        color=palette.primary,
                        curved=True,
                        stroke_cap_round=True
                    ),
                    ft.LineChartData(
                        data_points=memory_data,
                        stroke_width=2,
                        color=palette.secondary,
                        curved=True,
                        stroke_cap_round=True
                    )
                ],
                border=ft.border.all(1, palette.outline),
                horizontal_grid_lines=ft.ChartGridLines(
                    color=palette.outline,
                    width=0.5,
                    dash_pattern=[5, 5]
                ),
                vertical_grid_lines=ft.ChartGridLines(
                    color=palette.outline,
                    width=0.5,
                    dash_pattern=[5, 5]
                ),
                left_axis=ft.ChartAxis(
                    title=ft.Text("Utilization %", style=self.get_text_style('caption')),
                    title_size=40,
                    labels_size=30
                ),
                bottom_axis=ft.ChartAxis(
                    title=ft.Text("Time", style=self.get_text_style('caption')),
                    title_size=40,
                    labels_size=30
                ),
                tooltip_bgcolor=palette.surface,
                min_y=0,
                max_y=100,
                animate=ft.Animation(1000, ft.AnimationCurve.EASE_OUT_CUBIC)
            ),
            height=chart_height,
            padding=ft.padding.all(spacing.md)
        )

    def _update_chart_display(self):
        """Update the chart display with current metrics."""
        if self._chart_container:
            self._chart_container.content = self._create_chart_display()

    def build(self) -> ft.Control:
        """Build the utilization chart component."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Chart legend
        legend = ft.Row([
            ft.Row([
                ft.Container(
                    width=12,
                    height=12,
                    bgcolor=palette.primary,
                    border_radius=2
                ),
                ft.Text(
                    "GPU Utilization",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs),
            ft.Row([
                ft.Container(
                    width=12,
                    height=12,
                    bgcolor=palette.secondary,
                    border_radius=2
                ),
                ft.Text(
                    "Memory Utilization",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                )
            ], spacing=spacing.xs)
        ], spacing=spacing.md)

        self._chart_container = ft.Container(
            content=self._create_chart_display()
        )

        return ft.Column([
            ft.Text(
                f"GPU {self.gpu_id} Utilization",
                style=self.get_text_style('h6'),
                color=palette.text_primary
            ),
            legend,
            self._chart_container
        ], spacing=spacing.sm)


class TemperatureGauge(ThemeAwareUserControl):
    """
    Temperature gauge component for GPU thermal monitoring.

    Provides visual temperature indication with color-coded zones:
    - Green: Normal operating temperature (< 75°C)
    - Yellow: Warning zone (75-85°C)
    - Red: Critical zone (> 85°C)
    """

    def __init__(self, gpu_id: int, temperature: Optional[float] = None,
                 thresholds: Optional[GPUAlertThreshold] = None, **kwargs):
        super().__init__(**kwargs)
        self.gpu_id = gpu_id
        self.temperature = temperature or 0.0
        self.thresholds = thresholds or GPUAlertThreshold()
        self._gauge_container = None

    def update_temperature(self, temperature: Optional[float]):
        """Update the temperature display."""
        self.temperature = temperature or 0.0
        if self._gauge_container and self.page:
            self._update_gauge_display()
            self.update()

    def _get_temperature_color(self) -> str:
        """Get color based on temperature thresholds."""
        palette = self.get_palette()

        if self.temperature >= self.thresholds.temperature_critical:
            return palette.error
        elif self.temperature >= self.thresholds.temperature_warning:
            return palette.warning
        else:
            return palette.success

    def _create_gauge_display(self) -> ft.Control:
        """Create the temperature gauge display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate gauge percentage (0-100°C scale)
        percentage = min(self.temperature / 100.0, 1.0)
        color = self._get_temperature_color()

        # Responsive gauge size
        gauge_size = self.get_breakpoint_value(
            mobile=80, tablet=100, desktop=120, large=140
        )

        return ft.Container(
            content=ft.Stack([
                # Background circle
                ft.Container(
                    width=gauge_size,
                    height=gauge_size,
                    border_radius=gauge_size // 2,
                    border=ft.border.all(2, palette.outline),
                    bgcolor=palette.surface_variant
                ),
                # Temperature arc
                ft.Container(
                    width=gauge_size,
                    height=gauge_size,
                    content=ft.Canvas(
                        width=gauge_size,
                        height=gauge_size,
                        shapes=[
                            ft.canvas.Arc(
                                x=gauge_size // 2,
                                y=gauge_size // 2,
                                width=gauge_size - 10,
                                height=gauge_size - 10,
                                start_angle=math.pi * 0.75,
                                sweep_angle=math.pi * 1.5 * percentage,
                                stroke_width=6,
                                stroke_color=color
                            )
                        ]
                    )
                ),
                # Temperature text
                ft.Container(
                    width=gauge_size,
                    height=gauge_size,
                    content=ft.Column([
                        ft.Text(
                            f"{self.temperature:.0f}°C",
                            style=self.get_text_style('h4'),
                            color=palette.text_primary,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            f"GPU {self.gpu_id}",
                            style=self.get_text_style('caption'),
                            color=palette.text_secondary,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0)
                )
            ]),
            alignment=ft.alignment.center
        )

    def _update_gauge_display(self):
        """Update the gauge display with current temperature."""
        if self._gauge_container:
            self._gauge_container.content = self._create_gauge_display()

    def build(self) -> ft.Control:
        """Build the temperature gauge component."""
        self._gauge_container = ft.Container(
            content=self._create_gauge_display(),
            alignment=ft.alignment.center
        )
        return self._gauge_container


class GPUMetricsPanel(ThemeAwareUserControl):
    """
    GPU metrics panel component for displaying comprehensive performance metrics.

    Features:
    - Real-time metrics display with color-coded indicators
    - Responsive layout with adaptive metric cards
    - Performance statistics and trend analysis
    - Alert indicators for threshold breaches
    """

    def __init__(self, gpu_info: GPUInfo, current_metrics: Optional[GPUMetrics] = None,
                 thresholds: Optional[GPUAlertThreshold] = None, **kwargs):
        super().__init__(**kwargs)
        self.gpu_info = gpu_info
        self.current_metrics = current_metrics
        self.thresholds = thresholds or GPUAlertThreshold()
        self._metrics_container = None

    def update_metrics(self, metrics: GPUMetrics):
        """Update the metrics display."""
        self.current_metrics = metrics
        if self._metrics_container and self.page:
            self._update_metrics_display()
            self.update()

    def _create_metric_card(self, title: str, value: str, icon: str,
                           color: str, subtitle: str = None) -> ft.Container:
        """Create a metric card with responsive design."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Responsive card dimensions
        card_padding = self.get_breakpoint_value(
            mobile=spacing.sm, tablet=spacing.md, desktop=spacing.lg, large=spacing.lg
        )

        content_items = [
            ft.Row([
                ft.Icon(icon, color=color, size=self.get_breakpoint_value(20, 22, 24, 26)),
                ft.Text(
                    title,
                    style=self.get_text_style('body_medium'),
                    color=palette.text_secondary,
                    weight=ft.FontWeight.W_500
                )
            ], spacing=spacing.xs),
            ft.Text(
                value,
                style=self.get_text_style('h4'),
                color=palette.text_primary,
                weight=ft.FontWeight.BOLD
            )
        ]

        if subtitle:
            content_items.append(
                ft.Text(
                    subtitle,
                    style=self.get_text_style('caption'),
                    color=palette.text_tertiary
                )
            )

        return ft.Container(
            content=ft.Column(content_items, spacing=spacing.xs),
            bgcolor=palette.surface_variant,
            border_radius=self.get_breakpoint_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline_variant),
            padding=ft.padding.all(card_padding),
            expand=True
        )

    def _get_utilization_color(self, utilization: float) -> str:
        """Get color based on utilization level."""
        palette = self.get_palette()
        if utilization >= self.thresholds.utilization_high:
            return palette.error
        elif utilization >= 70.0:
            return palette.warning
        else:
            return palette.success

    def _get_memory_color(self, used_mb: int, total_mb: int) -> str:
        """Get color based on memory usage."""
        palette = self.get_palette()
        if total_mb == 0:
            return palette.text_tertiary

        usage_percent = (used_mb / total_mb) * 100
        if usage_percent >= self.thresholds.memory_critical:
            return palette.error
        elif usage_percent >= self.thresholds.memory_warning:
            return palette.warning
        else:
            return palette.success

    def _get_temperature_color(self, temperature: Optional[float]) -> str:
        """Get color based on temperature."""
        palette = self.get_palette()
        if temperature is None:
            return palette.text_tertiary

        if temperature >= self.thresholds.temperature_critical:
            return palette.error
        elif temperature >= self.thresholds.temperature_warning:
            return palette.warning
        else:
            return palette.success

    def _create_metrics_display(self) -> ft.Control:
        """Create the metrics display."""
        if not self.current_metrics:
            return ft.Container(
                content=ft.Text(
                    "No metrics available",
                    style=self.get_text_style('body1'),
                    color=self.get_palette().text_secondary
                ),
                alignment=ft.alignment.center
            )

        metrics = self.current_metrics

        # Create metric cards
        utilization_card = self._create_metric_card(
            "GPU Utilization",
            f"{metrics.utilization_percent:.1f}%",
            self.get_icon('CPU'),
            self._get_utilization_color(metrics.utilization_percent)
        )

        memory_used_gb = metrics.memory_used_mb / 1024
        memory_total_gb = self.gpu_info.memory_total_mb / 1024
        memory_card = self._create_metric_card(
            "VRAM Usage",
            f"{memory_used_gb:.1f} GB",
            self.get_icon('MEMORY'),
            self._get_memory_color(metrics.memory_used_mb, self.gpu_info.memory_total_mb),
            f"of {memory_total_gb:.1f} GB ({metrics.memory_utilization_percent:.1f}%)"
        )

        temperature_card = self._create_metric_card(
            "Temperature",
            f"{metrics.temperature_celsius:.1f}°C" if metrics.temperature_celsius else "N/A",
            self.get_icon('THERMAL'),
            self._get_temperature_color(metrics.temperature_celsius)
        )

        power_card = self._create_metric_card(
            "Power Draw",
            f"{metrics.power_draw_watts:.1f}W" if metrics.power_draw_watts else "N/A",
            self.get_icon('POWER'),
            self.get_palette().primary,
            f"Clock: {metrics.clock_speed_mhz}MHz" if metrics.clock_speed_mhz else None
        )

        # Responsive grid layout
        if self.is_mobile():
            return ft.Column([
                utilization_card,
                memory_card,
                temperature_card,
                power_card
            ], spacing=self.get_spacing().sm)
        else:
            return ft.Row([
                utilization_card,
                memory_card,
                temperature_card,
                power_card
            ], spacing=self.get_spacing().md)

    def _update_metrics_display(self):
        """Update the metrics display."""
        if self._metrics_container:
            self._metrics_container.content = self._create_metrics_display()

    def build(self) -> ft.Control:
        """Build the metrics panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._metrics_container = ft.Container(
            content=self._create_metrics_display()
        )

        return ft.Column([
            ft.Text(
                f"GPU {self.gpu_info.gpu_id} Metrics",
                style=self.get_text_style('h5'),
                color=palette.text_primary,
                weight=ft.FontWeight.W_600
            ),
            self._metrics_container
        ], spacing=spacing.sm)


class GPUInfoPanel(ThemeAwareUserControl):
    """
    GPU information panel component for displaying hardware details.

    Features:
    - Comprehensive GPU hardware information display
    - CUDA/ROCm compatibility information
    - Driver version and compute capability details
    - Responsive layout with adaptive information cards
    """

    def __init__(self, gpu_info: GPUInfo, cuda_info: Optional[CUDAInfo] = None,
                 rocm_info: Optional[ROCmInfo] = None, **kwargs):
        super().__init__(**kwargs)
        self.gpu_info = gpu_info
        self.cuda_info = cuda_info
        self.rocm_info = rocm_info

    def _create_info_row(self, label: str, value: str, icon: str = None) -> ft.Container:
        """Create an information row with responsive design."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        content_items = []

        if icon:
            content_items.append(
                ft.Icon(icon, size=self.get_breakpoint_value(16, 18, 20, 22),
                       color=palette.primary)
            )

        content_items.extend([
            ft.Text(
                f"{label}:",
                style=self.get_text_style('body_medium'),
                color=palette.text_secondary,
                weight=ft.FontWeight.W_500,
                expand=True
            ),
            ft.Text(
                value,
                style=self.get_text_style('body_medium'),
                color=palette.text_primary,
                text_align=ft.TextAlign.RIGHT
            )
        ])

        return ft.Container(
            content=ft.Row(content_items, spacing=spacing.xs),
            padding=ft.padding.symmetric(vertical=spacing.xs)
        )

    def _create_section(self, title: str, items: List[ft.Control],
                       icon: str = None) -> ft.Container:
        """Create an information section with responsive design."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        header_items = []
        if icon:
            header_items.append(
                ft.Icon(icon, size=self.get_breakpoint_value(20, 22, 24, 26),
                       color=palette.primary)
            )

        header_items.append(
            ft.Text(
                title,
                style=self.get_text_style('h6'),
                color=palette.text_primary,
                weight=ft.FontWeight.W_600
            )
        )

        return ft.Container(
            content=ft.Column([
                ft.Row(header_items, spacing=spacing.xs),
                ft.Divider(height=1, color=palette.outline_variant),
                ft.Column(items, spacing=spacing.xs)
            ], spacing=spacing.sm),
            bgcolor=palette.surface_variant,
            border_radius=self.get_breakpoint_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline_variant),
            padding=ft.padding.all(self.get_breakpoint_value(
                int(spacing.md*0.8), spacing.md, spacing.lg, spacing.lg
            )),
            expand=True
        )

    def _format_memory_size(self, mb: int) -> str:
        """Format memory size in human-readable format."""
        if mb >= 1024:
            return f"{mb / 1024:.1f} GB"
        else:
            return f"{mb} MB"

    def build(self) -> ft.Control:
        """Build the GPU info panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Hardware information section
        hardware_items = [
            self._create_info_row("Name", self.gpu_info.name, self.get_icon('CHIP')),
            self._create_info_row("Vendor", self.gpu_info.vendor.value),
            self._create_info_row("Memory", self._format_memory_size(self.gpu_info.memory_total_mb)),
            self._create_info_row("Driver Version", self.gpu_info.driver_version or "Unknown"),
            self._create_info_row("Compute Capability", self.gpu_info.compute_capability or "Unknown"),
            self._create_info_row("PCI Bus ID", self.gpu_info.pci_bus_id or "Unknown"),
        ]

        if self.gpu_info.uuid:
            hardware_items.append(
                self._create_info_row("UUID", self.gpu_info.uuid[:16] + "..." if len(self.gpu_info.uuid) > 16 else self.gpu_info.uuid)
            )

        hardware_section = self._create_section(
            "Hardware Information",
            hardware_items,
            self.get_icon('HARDWARE')
        )

        # Compute platform information
        compute_items = []

        if self.cuda_info and self.cuda_info.available:
            compute_items.extend([
                self._create_info_row("CUDA Available", "Yes", self.get_icon('CHECK')),
                self._create_info_row("CUDA Version", self.cuda_info.version or "Unknown"),
                self._create_info_row("CUDA Driver", self.cuda_info.driver_version or "Unknown"),
                self._create_info_row("CUDA Devices", str(self.cuda_info.device_count))
            ])
        else:
            compute_items.append(
                self._create_info_row("CUDA Available", "No", self.get_icon('CLOSE'))
            )

        if self.rocm_info and self.rocm_info.available:
            compute_items.extend([
                self._create_info_row("ROCm Available", "Yes", self.get_icon('CHECK')),
                self._create_info_row("ROCm Version", self.rocm_info.version or "Unknown"),
                self._create_info_row("ROCm Devices", str(self.rocm_info.device_count))
            ])
        else:
            compute_items.append(
                self._create_info_row("ROCm Available", "No", self.get_icon('CLOSE'))
            )

        compute_section = self._create_section(
            "Compute Platforms",
            compute_items,
            self.get_icon('COMPUTE')
        )

        # Performance characteristics
        performance_items = [
            self._create_info_row("Base Clock", f"{self.gpu_info.clock_speed_mhz} MHz" if self.gpu_info.clock_speed_mhz else "Unknown"),
            self._create_info_row("Memory Clock", f"{self.gpu_info.memory_clock_mhz} MHz" if self.gpu_info.memory_clock_mhz else "Unknown"),
            self._create_info_row("Power Limit", f"{self.gpu_info.power_limit_watts} W" if self.gpu_info.power_limit_watts else "Unknown"),
            self._create_info_row("Current Utilization", f"{self.gpu_info.utilization_percent:.1f}%"),
            self._create_info_row("Memory Utilization", f"{self.gpu_info.memory_utilization_percent:.1f}%")
        ]

        if self.gpu_info.temperature_celsius:
            performance_items.append(
                self._create_info_row("Temperature", f"{self.gpu_info.temperature_celsius:.1f}°C")
            )

        performance_section = self._create_section(
            "Performance",
            performance_items,
            self.get_icon('PERFORMANCE')
        )

        # Responsive layout
        if self.is_mobile():
            return ft.Column([
                hardware_section,
                compute_section,
                performance_section
            ], spacing=spacing.md)
        else:
            return ft.Row([
                ft.Column([hardware_section, compute_section], spacing=spacing.md, expand=True),
                performance_section
            ], spacing=spacing.md)
