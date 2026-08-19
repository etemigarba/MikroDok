"""
Module: performance_gauge_ui
Description: Circular gauge components for displaying CPU usage, disk I/O rates, and thermal status.
            Provides interactive performance gauges with real-time updates, threshold indicators,
            and theme-aware styling for comprehensive system monitoring.
Phase: 2
Location: /src/modules/ui/resource_dashboard_ui/performance_gauge_ui/performance_gauge_ui.py
"""

# Standard library imports
import asyncio
import math
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from enum import Enum

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


class GaugeType(Enum):
    """Types of performance gauges."""
    CPU_USAGE = "cpu_usage"
    DISK_IO = "disk_io"
    THERMAL = "thermal"
    NETWORK_IO = "network_io"
    MEMORY_USAGE = "memory_usage"


class GaugeStyle(Enum):
    """Gauge visual styles."""
    CIRCULAR = "circular"
    SEMI_CIRCULAR = "semi_circular"
    LINEAR = "linear"


@dataclass
class GaugeConfiguration:
    """Configuration for performance gauge."""
    gauge_type: GaugeType
    gauge_style: GaugeStyle = GaugeStyle.CIRCULAR
    title: str = ""
    min_value: float = 0.0
    max_value: float = 100.0
    warning_threshold: float = 75.0
    critical_threshold: float = 90.0
    show_value_text: bool = True
    show_threshold_markers: bool = True
    show_trend_indicator: bool = True
    animate_transitions: bool = True
    update_interval_seconds: float = 1.0
    gauge_size: int = 120
    stroke_width: int = 8


class PerformanceGaugeUI(ThemeAwareUserControl):
    """
    Performance gauge UI component.
    
    Provides interactive circular gauges for system monitoring with:
    - Real-time CPU usage visualization
    - Disk I/O rate monitoring with read/write breakdown
    - Thermal status with temperature thresholds
    - Network I/O monitoring
    - Memory usage indicators
    - Customizable thresholds and styling
    - Theme-aware color coding
    - Smooth animations and transitions
    """
    
    def __init__(
        self,
        config: GaugeConfiguration,
        hardware_monitor: Optional[HardwareMonitor] = None,
        thermal_monitor: Optional[ThermalMonitor] = None,
        on_threshold_exceeded: Optional[Callable[[str, float], None]] = None,
        on_gauge_click: Optional[Callable[[GaugeType], None]] = None
    ):
        """
        Initialize performance gauge.
        
        Args:
            config: Gauge configuration
            hardware_monitor: Hardware monitoring service
            thermal_monitor: Thermal monitoring service
            on_threshold_exceeded: Callback for threshold violations
            on_gauge_click: Callback for gauge interactions
        """
        super().__init__()
        self._config = config
        self._hardware_monitor = hardware_monitor
        self._thermal_monitor = thermal_monitor
        self._on_threshold_exceeded = on_threshold_exceeded
        self._on_gauge_click = on_gauge_click
        
        # Gauge state
        self._current_value = 0.0
        self._previous_value = 0.0
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._value_history: List[float] = []
        
        # UI components
        self._gauge_container: Optional[ft.Container] = None
        self._value_text: Optional[ft.Text] = None
        self._label_text: Optional[ft.Text] = None
        self._trend_indicator: Optional[ft.Icon] = None
        self._status_indicator: Optional[ft.Container] = None
        
        # Animation state
        self._animation_progress = 0.0
        self._target_value = 0.0
        self._animation_task: Optional[asyncio.Task] = None
    
    def build(self) -> ft.Control:
        """Build the performance gauge UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create gauge based on style
        if self._config.gauge_style == GaugeStyle.CIRCULAR:
            gauge_widget = self._create_circular_gauge()
        elif self._config.gauge_style == GaugeStyle.SEMI_CIRCULAR:
            gauge_widget = self._create_semi_circular_gauge()
        else:
            gauge_widget = self._create_linear_gauge()
        
        # Create value display
        value_display = self._create_value_display()
        
        # Create status indicator
        status_indicator = self._create_status_indicator()
        
        # Create trend indicator
        trend_indicator = self._create_trend_indicator()
        
        rlm = self.get_responsive_layout()
        card_w = rlm.get_breakpoint_value(self._config.gauge_size + 40, self._config.gauge_size + 60, self._config.gauge_size + 80, self._config.gauge_size + 100)
        card_h = rlm.get_breakpoint_value(self._config.gauge_size + 80, self._config.gauge_size + 120, self._config.gauge_size + 140, self._config.gauge_size + 160)
        return ft.Container(
            content=ft.Column([
                # Gauge widget
                ft.Container(
                    content=gauge_widget,
                    alignment=ft.alignment.center,
                    height=rlm.get_breakpoint_value(self._config.gauge_size, self._config.gauge_size + 10, self._config.gauge_size + 20, self._config.gauge_size + 30)
                ),
                ft.Container(height=spacing.sm),
                # Value and status
                ft.Row([
                    value_display,
                    trend_indicator if self._config.show_trend_indicator else ft.Container()
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=spacing.sm),
                ft.Container(height=spacing.xs),
                # Status indicator
                status_indicator
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(self.get_spacing().md),
            border=ft.border.all(1, palette.borders),
            on_click=self._on_click if self._on_gauge_click else None,
            width=card_w,
            height=card_h
        )
    
    def _create_circular_gauge(self) -> ft.Control:
        """Create circular gauge widget."""
        palette = self.get_palette()
        
        # Calculate gauge parameters
        size = self._config.gauge_size
        center = size / 2
        radius = (size - self._config.stroke_width) / 2
        
        # Calculate current value angle (0-360 degrees)
        value_ratio = (self._current_value - self._config.min_value) / (self._config.max_value - self._config.min_value)
        value_ratio = max(0, min(1, value_ratio))  # Clamp to 0-1
        value_angle = value_ratio * 270  # Use 270 degrees for gauge
        
        # Determine gauge color based on thresholds
        gauge_color = self._get_gauge_color()
        
        # Create gauge using Canvas
        gauge_canvas = ft.Canvas(
            content=ft.Stack([
                # Background arc
                ft.Container(
                    width=size,
                    height=size,
                    border=ft.border.all(
                        self._config.stroke_width,
                        f"{palette.borders}40"
                    ),
                    border_radius=ft.border_radius.all(size / 2)
                ),
                # Value arc (will be drawn with custom paint)
                ft.Container(
                    width=size,
                    height=size
                )
            ]),
            width=size,
            height=size
        )
        
        # Store reference for updates
        self._gauge_container = ft.Container(
            content=gauge_canvas,
            width=size,
            height=size
        )
        
        return self._gauge_container
    
    def _create_semi_circular_gauge(self) -> ft.Control:
        """Create semi-circular gauge widget."""
        palette = self.get_palette()
        
        size = self._config.gauge_size
        gauge_color = self._get_gauge_color()
        
        # Calculate value ratio
        value_ratio = (self._current_value - self._config.min_value) / (self._config.max_value - self._config.min_value)
        value_ratio = max(0, min(1, value_ratio))
        
        # Create semi-circular progress indicator
        progress_indicator = ft.ProgressRing(
            value=value_ratio,
            color=gauge_color,
            bgcolor=f"{palette.borders}40",
            stroke_width=self._config.stroke_width,
            width=size,
            height=size
        )
        
        self._gauge_container = ft.Container(
            content=progress_indicator,
            width=size,
            height=size
        )
        
        return self._gauge_container
    
    def _create_linear_gauge(self) -> ft.Control:
        """Create linear gauge widget."""
        palette = self.get_palette()
        
        gauge_color = self._get_gauge_color()
        
        # Calculate value ratio
        value_ratio = (self._current_value - self._config.min_value) / (self._config.max_value - self._config.min_value)
        value_ratio = max(0, min(1, value_ratio))
        
        # Create linear progress bar
        progress_bar = ft.ProgressBar(
            value=value_ratio,
            color=gauge_color,
            bgcolor=f"{palette.borders}40",
            height=self._config.stroke_width * 2,
            width=self._config.gauge_size
        )
        
        self._gauge_container = ft.Container(
            content=progress_bar,
            width=self._config.gauge_size,
            height=self._config.stroke_width * 2
        )
        
        return self._gauge_container
    
    def _create_value_display(self) -> ft.Control:
        """Create value display text."""
        palette = self.get_palette()
        
        # Format value based on gauge type
        formatted_value = self._format_value(self._current_value)
        
        self._value_text = ft.Text(
            formatted_value,
            style=self.get_text_style('metric_medium'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER
        )
        
        # Create label
        label = self._get_gauge_label()
        self._label_text = ft.Text(
            label,
            style=self.get_text_style('caption'),
            color=palette.text_secondary,
            text_align=ft.TextAlign.CENTER
        )
        
        return ft.Column([
            self._value_text,
            self._label_text
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
    
    def _create_status_indicator(self) -> ft.Control:
        """Create status indicator."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Determine status based on thresholds
        if self._current_value >= self._config.critical_threshold:
            status_color = palette.error
            status_text = "Critical"
            status_icon = self.get_icon('ERROR')
        elif self._current_value >= self._config.warning_threshold:
            status_color = palette.warning
            status_text = "Warning"
            status_icon = self.get_icon('WARNING')
        else:
            status_color = palette.success
            status_text = "Normal"
            status_icon = self.get_icon('SUCCESS')
        
        rlm = self.get_responsive_layout()
        status_icon_size = rlm.get_breakpoint_value(10, 12, 14, 16)
        self._status_indicator = ft.Container(
            content=ft.Row([
                ft.Icon(status_icon, color=status_color, size=status_icon_size),
                ft.Text(
                    status_text,
                    style=self.get_text_style('caption'),
                    color=status_color
                )
            ], spacing=spacing.xs, alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            border=ft.border.all(1, status_color)
        )
        
        return self._status_indicator
    
    def _create_trend_indicator(self) -> ft.Control:
        """Create trend indicator."""
        palette = self.get_palette()
        
        # Calculate trend
        if len(self._value_history) < 2:
            trend_icon = self.get_icon('CIRCLE')
            trend_color = palette.text_tertiary
        else:
            recent_avg = sum(self._value_history[-3:]) / min(3, len(self._value_history))
            older_avg = sum(self._value_history[-6:-3]) / min(3, len(self._value_history[-6:-3])) if len(self._value_history) >= 6 else recent_avg
            
            if recent_avg > older_avg + 1:
                trend_icon = self.get_icon('WARNING')
                trend_color = palette.error if recent_avg > self._config.warning_threshold else palette.warning
            elif recent_avg < older_avg - 1:
                trend_icon = self.get_icon('SUCCESS')
                trend_color = palette.success
            else:
                trend_icon = self.get_icon('CIRCLE')
                trend_color = palette.text_tertiary
        
        rlm = self.get_responsive_layout()
        trend_size = rlm.get_breakpoint_value(12, 14, 16, 18)
        self._trend_indicator = ft.Icon(
            trend_icon,
            color=trend_color,
            size=trend_size
        )
        
        return self._trend_indicator

    def _get_gauge_color(self) -> str:
        """Get gauge color based on current value and thresholds."""
        palette = self.get_palette()

        if self._current_value >= self._config.critical_threshold:
            return palette.error
        elif self._current_value >= self._config.warning_threshold:
            return palette.warning
        else:
            return palette.primary

    def _get_gauge_label(self) -> str:
        """Get gauge label based on type."""
        labels = {
            GaugeType.CPU_USAGE: "CPU Usage",
            GaugeType.DISK_IO: "Disk I/O",
            GaugeType.THERMAL: "Temperature",
            GaugeType.NETWORK_IO: "Network I/O",
            GaugeType.MEMORY_USAGE: "Memory"
        }
        return labels.get(self._config.gauge_type, "Performance")

    def _format_value(self, value: float) -> str:
        """Format value based on gauge type."""
        if self._config.gauge_type == GaugeType.CPU_USAGE:
            return f"{value:.1f}%"
        elif self._config.gauge_type == GaugeType.DISK_IO:
            return f"{value:.1f} MB/s"
        elif self._config.gauge_type == GaugeType.THERMAL:
            return f"{value:.1f}°C"
        elif self._config.gauge_type == GaugeType.NETWORK_IO:
            return f"{value:.1f} MB/s"
        elif self._config.gauge_type == GaugeType.MEMORY_USAGE:
            return f"{value:.1f}%"
        else:
            return f"{value:.1f}"

    async def start_monitoring(self) -> None:
        """Start performance monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self) -> None:
        """Stop performance monitoring."""
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

        if self._animation_task:
            self._animation_task.cancel()
            try:
                await self._animation_task
            except asyncio.CancelledError:
                pass
            self._animation_task = None

    async def _monitoring_loop(self) -> None:
        """Main monitoring update loop."""
        try:
            while self._is_monitoring:
                # Get current metrics
                new_value = await self._get_current_metric_value()

                if new_value is not None:
                    # Update value history
                    self._value_history.append(new_value)
                    if len(self._value_history) > 20:  # Keep last 20 values
                        self._value_history = self._value_history[-20:]

                    # Update gauge value
                    await self._update_gauge_value(new_value)

                    # Check thresholds
                    self._check_thresholds(new_value)

                # Wait for next update
                await asyncio.sleep(self._config.update_interval_seconds)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            # Log error but continue monitoring
            pass

    async def _get_current_metric_value(self) -> Optional[float]:
        """Get current metric value based on gauge type."""
        if not self._hardware_monitor:
            return None

        try:
            metrics = self._hardware_monitor.get_current_metrics()
            if not metrics:
                return None

            if self._config.gauge_type == GaugeType.CPU_USAGE:
                return metrics.cpu_usage_percent
            elif self._config.gauge_type == GaugeType.DISK_IO:
                return metrics.disk_read_mb_per_sec + metrics.disk_write_mb_per_sec
            elif self._config.gauge_type == GaugeType.NETWORK_IO:
                return metrics.network_sent_mb_per_sec + metrics.network_recv_mb_per_sec
            elif self._config.gauge_type == GaugeType.MEMORY_USAGE:
                return metrics.memory_usage_percent
            elif self._config.gauge_type == GaugeType.THERMAL:
                if self._thermal_monitor:
                    thermal_metrics = self._thermal_monitor.get_current_metrics()
                    if thermal_metrics and thermal_metrics.cpu_temperature_celsius:
                        return thermal_metrics.cpu_temperature_celsius
                return metrics.gpu_temperature_celsius or 0.0

        except Exception as e:
            # Log error and return None
            pass

        return None

    async def _update_gauge_value(self, new_value: float) -> None:
        """Update gauge value with animation."""
        self._previous_value = self._current_value
        self._target_value = new_value

        if self._config.animate_transitions:
            # Start animation
            if self._animation_task:
                self._animation_task.cancel()
            self._animation_task = asyncio.create_task(self._animate_to_value())
        else:
            # Direct update
            self._current_value = new_value
            self._update_ui_components()

    async def _animate_to_value(self) -> None:
        """Animate gauge to target value."""
        try:
            start_value = self._current_value
            target_value = self._target_value
            animation_duration = 0.5  # 500ms animation
            steps = 20
            step_duration = animation_duration / steps

            for i in range(steps + 1):
                progress = i / steps
                # Use easing function for smooth animation
                eased_progress = self._ease_in_out(progress)

                self._current_value = start_value + (target_value - start_value) * eased_progress
                self._update_ui_components()

                if i < steps:
                    await asyncio.sleep(step_duration)

        except asyncio.CancelledError:
            # Animation was cancelled, set to target value
            self._current_value = self._target_value
            self._update_ui_components()

    def _ease_in_out(self, t: float) -> float:
        """Easing function for smooth animations."""
        return t * t * (3.0 - 2.0 * t)

    def _update_ui_components(self) -> None:
        """Update UI components with current value."""
        # Update value text
        if self._value_text:
            self._value_text.value = self._format_value(self._current_value)

        # Update gauge visual
        if self._gauge_container:
            # Update gauge color
            new_color = self._get_gauge_color()

            # Update progress for different gauge styles
            if self._config.gauge_style in [GaugeStyle.SEMI_CIRCULAR, GaugeStyle.LINEAR]:
                value_ratio = (self._current_value - self._config.min_value) / (self._config.max_value - self._config.min_value)
                value_ratio = max(0, min(1, value_ratio))

                # Find and update progress component
                if hasattr(self._gauge_container.content, 'value'):
                    self._gauge_container.content.value = value_ratio
                    self._gauge_container.content.color = new_color

        # Update status indicator
        self._update_status_indicator()

        # Update trend indicator
        self._update_trend_indicator()

        # Trigger UI update only if control is added to a page
        try:
            if hasattr(self, 'page') and self.page is not None:
                self.update()
        except (AssertionError, AttributeError):
            # Control not added to page yet, skip UI update
            pass

    def _update_status_indicator(self) -> None:
        """Update status indicator based on current value."""
        if not self._status_indicator:
            return

        palette = self.get_palette()
        spacing = self.get_spacing()

        # Determine status
        if self._current_value >= self._config.critical_threshold:
            status_color = palette.error
            status_text = "Critical"
            status_icon = self.get_icon('ERROR')
        elif self._current_value >= self._config.warning_threshold:
            status_color = palette.warning
            status_text = "Warning"
            status_icon = self.get_icon('WARNING')
        else:
            status_color = palette.success
            status_text = "Normal"
            status_icon = self.get_icon('SUCCESS')

        # Update status indicator content
        self._status_indicator.content = ft.Row([
            ft.Icon(status_icon, color=status_color, size=12),
            ft.Text(
                status_text,
                style=self.get_text_style('caption'),
                color=status_color
            )
        ], spacing=spacing.xs, alignment=ft.MainAxisAlignment.CENTER)

        self._status_indicator.border = ft.border.all(1, status_color)

    def _update_trend_indicator(self) -> None:
        """Update trend indicator based on value history."""
        if not self._trend_indicator or len(self._value_history) < 2:
            return

        palette = self.get_palette()

        # Calculate trend
        recent_avg = sum(self._value_history[-3:]) / min(3, len(self._value_history))
        older_avg = sum(self._value_history[-6:-3]) / min(3, len(self._value_history[-6:-3])) if len(self._value_history) >= 6 else recent_avg

        if recent_avg > older_avg + 1:
            trend_icon = self.get_icon('WARNING')
            trend_color = palette.error if recent_avg > self._config.warning_threshold else palette.warning
        elif recent_avg < older_avg - 1:
            trend_icon = self.get_icon('SUCCESS')
            trend_color = palette.success
        else:
            trend_icon = self.get_icon('CIRCLE')
            trend_color = palette.text_tertiary

        self._trend_indicator.name = trend_icon
        self._trend_indicator.color = trend_color

    def _check_thresholds(self, value: float) -> None:
        """Check thresholds and trigger callbacks."""
        if not self._on_threshold_exceeded:
            return

        gauge_name = self._get_gauge_label().lower().replace(" ", "_")

        if value >= self._config.critical_threshold:
            self._on_threshold_exceeded(f"{gauge_name}_critical", value)
        elif value >= self._config.warning_threshold:
            self._on_threshold_exceeded(f"{gauge_name}_warning", value)

    def _on_click(self, e) -> None:
        """Handle gauge click."""
        if self._on_gauge_click:
            self._on_gauge_click(self._config.gauge_type)

    def update_value(self, value: float) -> None:
        """Update gauge value synchronously."""
        self._previous_value = self._current_value
        self._current_value = max(self._config.min_value, min(self._config.max_value, value))

        # Add to history
        self._value_history.append(self._current_value)
        if len(self._value_history) > 20:  # Keep last 20 values
            self._value_history = self._value_history[-20:]

        # Check thresholds
        self._check_thresholds(self._current_value)

        # Update UI components
        self._update_ui_components()

    def configure_gauge(self, config: GaugeConfiguration) -> None:
        """Update gauge configuration."""
        self._config = config
        self._update_ui_components()

    def get_current_value(self) -> float:
        """Get current gauge value."""
        return self._current_value

    def get_value_history(self) -> List[float]:
        """Get value history."""
        return self._value_history.copy()

    def is_monitoring_active(self) -> bool:
        """Check if monitoring is currently active."""
        return self._is_monitoring

    def will_unmount(self) -> None:
        """Clean up when component is unmounted."""
        if self._is_monitoring:
            asyncio.create_task(self.stop_monitoring())
        super().will_unmount()
