"""
Module: pressure_gauge_ui
Description: Shows memory pressure levels with color-coded indicators (green/yellow/red)
Phase: 4
Location: /src/modules/ui/memory_monitor_ui/pressure_gauge_ui/
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
from src.modules.logic.resource_monitor_lg.memory_monitor_lg.memory_monitor_lg import (
    MemoryMonitor, MemoryMetrics
)
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg.memory_pressure_handler_lg import (
    MemoryPressureHandler
)


class GaugeStyle(Enum):
    """Gauge display styles."""
    CIRCULAR = "circular"
    LINEAR = "linear"
    DIGITAL = "digital"
    COMPACT = "compact"


class AlertLevel(Enum):
    """Alert levels for pressure thresholds."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class PressureThresholds:
    """Memory pressure threshold configuration."""
    low_threshold: float = 0.3      # 30%
    moderate_threshold: float = 0.6  # 60%
    high_threshold: float = 0.8     # 80%
    critical_threshold: float = 0.95 # 95%


@dataclass
class PressureReading:
    """Memory pressure reading data."""
    timestamp: datetime
    pressure_score: float  # 0.0 to 1.0
    pressure_level: Any  # Will be PressureLevel at runtime
    pressure_trend: Any  # Will be PressureTrend at runtime
    memory_usage_percent: float
    swap_usage_percent: float
    allocation_rate_mbps: float
    deallocation_rate_mbps: float
    gc_frequency: float


class PressureGaugeUI(ThemeAwareUserControl):
    """
    Pressure gauge UI component.
    
    Provides comprehensive memory pressure visualization with:
    - Color-coded pressure indicators (green/yellow/red) based on memory usage
    - Real-time pressure level monitoring with trend analysis
    - Configurable threshold settings for warning and critical levels
    - Multiple gauge display styles (circular, linear, digital, compact)
    - Historical pressure tracking with trend visualization
    - Alert notifications for threshold breaches
    - Theme-aware styling and accessibility compliance
    - Performance optimization for real-time updates
    - Interactive threshold configuration interface
    """

    def __init__(self, style: GaugeStyle = GaugeStyle.CIRCULAR):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        
        # Configuration
        self._gauge_style = style
        self._thresholds = PressureThresholds()
        self._is_monitoring = False
        self._refresh_interval = 1.0  # seconds
        self._history_retention_minutes = 60
        
        # Core components
        self._memory_monitor: Optional[MemoryMonitor] = None
        self._pressure_handler: Optional[MemoryPressureHandler] = None
        
        # Data storage
        self._current_reading: Optional[PressureReading] = None
        self._pressure_history: List[PressureReading] = []
        self._alert_callbacks: List[Callable[[AlertLevel, PressureReading], None]] = []
        
        # UI components
        self._gauge_container: Optional[ft.Container] = None
        self._pressure_text: Optional[ft.Text] = None
        self._level_indicator: Optional[ft.Container] = None
        self._trend_indicator: Optional[ft.Icon] = None
        self._metrics_display: Optional[ft.Container] = None
        self._threshold_controls: Optional[ft.Container] = None
        self._alert_panel: Optional[ft.Container] = None
        
        # Animation state
        self._monitoring_task: Optional[asyncio.Task] = None
        self._animation_frame = 0
        self._pulse_animation = False
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize memory monitoring components."""
        try:
            # Initialize memory monitor
            self._memory_monitor = MemoryMonitor()
            
            # Initialize pressure handler
            self._pressure_handler = MemoryPressureHandler()
            
            # Initialize with default reading
            self._current_reading = PressureReading(
                timestamp=datetime.now(timezone.utc),
                pressure_score=0.0,
                pressure_level=PressureLevel.LOW,
                pressure_trend=PressureTrend.STABLE,
                memory_usage_percent=0.0,
                swap_usage_percent=0.0,
                allocation_rate_mbps=0.0,
                deallocation_rate_mbps=0.0,
                gc_frequency=0.0
            )
            
        except Exception as e:
            self._logger.error(f"Failed to initialize components: {str(e)}")
    
    def build(self) -> ft.Control:
        """Build the pressure gauge UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create main gauge display
        gauge_display = self._create_gauge_display()
        
        # Create metrics panel
        metrics_panel = self._create_metrics_panel()
        
        # Create controls panel
        controls_panel = self._create_controls_panel()
        
        # Create alert panel
        alert_panel = self._create_alert_panel()
        
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Container(
                    content=ft.Row([
                        ft.Text(
                            "Memory Pressure Monitor",
                            style=self.get_text_style('h3'),
                            color=palette.text_primary
                        ),
                        ft.Container(expand=True),
                        self._create_status_indicator()
                    ]),
                    padding=ft.padding.all(spacing.md)
                ),
                
                # Main content
                ft.Row([
                    # Gauge display
                    ft.Container(
                        content=gauge_display,
                        expand=True
                    ),
                    ft.Container(width=spacing.lg),
                    # Side panels
                    ft.Container(
                        content=ft.Column([
                            metrics_panel,
                            ft.Container(height=spacing.md),
                            alert_panel
                        ]),
                        width=250
                    )
                ], expand=True),
                
                ft.Container(height=spacing.md),
                
                # Controls
                controls_panel
            ], expand=True),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )
    
    def _create_status_indicator(self) -> ft.Control:
        """Create monitoring status indicator."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        status_color = palette.success if self._is_monitoring else palette.text_tertiary
        status_text = "Active" if self._is_monitoring else "Inactive"
        
        return ft.Row([
            ft.Icon(self.get_icon('CIRCLE'), color=status_color, size=12),
            ft.Text(
                status_text,
                style=self.get_text_style('body_small'),
                color=status_color
            )
        ], spacing=spacing.xs)
    
    def _create_gauge_display(self) -> ft.Control:
        """Create main gauge display based on style."""
        if self._gauge_style == GaugeStyle.CIRCULAR:
            return self._create_circular_gauge()
        elif self._gauge_style == GaugeStyle.LINEAR:
            return self._create_linear_gauge()
        elif self._gauge_style == GaugeStyle.DIGITAL:
            return self._create_digital_gauge()
        elif self._gauge_style == GaugeStyle.COMPACT:
            return self._create_compact_gauge()
        else:
            return self._create_circular_gauge()
    
    def _create_circular_gauge(self) -> ft.Control:
        """Create circular pressure gauge."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Get current pressure
        pressure = self._current_reading.pressure_score if self._current_reading else 0.0
        
        # Determine gauge color based on pressure level
        gauge_color = self._get_pressure_color(pressure)
        
        # Calculate gauge angle (0-360 degrees)
        gauge_angle = pressure * 270  # 270 degrees for 0-100%
        
        # Create gauge visualization using progress ring
        gauge_ring = ft.ProgressRing(
            value=pressure,
            color=gauge_color,
            bgcolor=palette.surface_variant,
            stroke_width=12,
            width=200,
            height=200
        )
        
        # Center text showing pressure percentage
        center_text = ft.Text(
            f"{pressure * 100:.0f}%",
            style=self.get_text_style('h1'),
            color=gauge_color,
            text_align=ft.TextAlign.CENTER
        )
        
        # Pressure level text
        level_text = ft.Text(
            self._current_reading.pressure_level.value.title() if self._current_reading else "Unknown",
            style=self.get_text_style('body_medium'),
            color=palette.text_secondary,
            text_align=ft.TextAlign.CENTER
        )
        
        return ft.Container(
            content=ft.Stack([
                # Background gauge
                ft.Container(
                    content=gauge_ring,
                    alignment=ft.alignment.center
                ),
                # Center content
                ft.Container(
                    content=ft.Column([
                        center_text,
                        level_text,
                        self._create_trend_indicator()
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=spacing.xs),
                    alignment=ft.alignment.center
                )
            ]),
            bgcolor=palette.background_secondary,
            border_radius=ft.border_radius.all(12),
            padding=ft.padding.all(spacing.lg),
            alignment=ft.alignment.center
        )

    def _create_linear_gauge(self) -> ft.Control:
        """Create linear pressure gauge."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        pressure = self._current_reading.pressure_score if self._current_reading else 0.0
        gauge_color = self._get_pressure_color(pressure)

        # Create horizontal progress bar
        progress_bar = ft.ProgressBar(
            value=pressure,
            color=gauge_color,
            bgcolor=palette.surface_variant,
            height=30
        )

        # Threshold markers
        threshold_markers = self._create_threshold_markers()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    f"Memory Pressure: {pressure * 100:.1f}%",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.Stack([
                    progress_bar,
                    threshold_markers
                ]),
                ft.Container(height=spacing.sm),
                ft.Row([
                    ft.Text(
                        self._current_reading.pressure_level.value.title() if self._current_reading else "Unknown",
                        style=self.get_text_style('body_medium'),
                        color=gauge_color
                    ),
                    ft.Container(expand=True),
                    self._create_trend_indicator()
                ])
            ]),
            bgcolor=palette.background_secondary,
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg)
        )

    def _create_digital_gauge(self) -> ft.Control:
        """Create digital pressure display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        pressure = self._current_reading.pressure_score if self._current_reading else 0.0
        gauge_color = self._get_pressure_color(pressure)

        return ft.Container(
            content=ft.Column([
                # Large digital display
                ft.Text(
                    f"{pressure * 100:.1f}",
                    style=ft.TextStyle(size=72, weight=ft.FontWeight.BOLD),
                    color=gauge_color,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    "PRESSURE %",
                    style=self.get_text_style('h4'),
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=spacing.md),
                ft.Text(
                    self._current_reading.pressure_level.value.upper() if self._current_reading else "UNKNOWN",
                    style=self.get_text_style('h3'),
                    color=gauge_color,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=spacing.sm),
                self._create_trend_indicator()
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.background_secondary,
            border=ft.border.all(2, gauge_color),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg),
            alignment=ft.alignment.center
        )

    def _create_compact_gauge(self) -> ft.Control:
        """Create compact pressure gauge."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        pressure = self._current_reading.pressure_score if self._current_reading else 0.0
        gauge_color = self._get_pressure_color(pressure)

        return ft.Container(
            content=ft.Row([
                ft.Icon(self.get_icon('CPU'), color=gauge_color, size=24),
                ft.Container(width=spacing.sm),
                ft.Column([
                    ft.Text(
                        f"{pressure * 100:.0f}%",
                        style=self.get_text_style('h4'),
                        color=gauge_color
                    ),
                    ft.Text(
                        self._current_reading.pressure_level.value.title() if self._current_reading else "Unknown",
                        style=self.get_text_style('caption'),
                        color=palette.text_secondary
                    )
                ], spacing=0),
                ft.Container(width=spacing.md),
                ft.Container(
                    content=ft.ProgressBar(
                        value=pressure,
                        color=gauge_color,
                        bgcolor=palette.surface_variant,
                        height=8
                    ),
                    width=100
                ),
                ft.Container(width=spacing.sm),
                self._create_trend_indicator()
            ], alignment=ft.MainAxisAlignment.START),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline),
            border_radius=ft.border_radius.all(6),
            padding=ft.padding.all(spacing.md)
        )

    def _create_trend_indicator(self) -> ft.Control:
        """Create pressure trend indicator."""
        palette = self.get_palette()

        if not self._current_reading:
            return ft.Container()

        trend = self._current_reading.pressure_trend

        if trend == PressureTrend.INCREASING:
            icon = self.get_icon('FORWARD')  # Use forward arrow for increasing trend
            color = palette.error
        elif trend == PressureTrend.DECREASING:
            icon = self.get_icon('BACK')  # Use back arrow for decreasing trend
            color = palette.success
        else:
            icon = self.get_icon('MINIMIZE')  # Use minimize for flat trend
            color = palette.text_tertiary

        return ft.Icon(icon, color=color, size=20)

    def _create_threshold_markers(self) -> ft.Control:
        """Create threshold markers for linear gauge."""
        palette = self.get_palette()

        markers = []
        thresholds = [
            (self._thresholds.low_threshold, palette.success),
            (self._thresholds.moderate_threshold, palette.warning),
            (self._thresholds.high_threshold, palette.error),
            (self._thresholds.critical_threshold, palette.error)
        ]

        for threshold, color in thresholds:
            marker = ft.Container(
                bgcolor=color,
                width=2,
                height=30,
                left=threshold * 100,  # Position as percentage
                top=0
            )
            markers.append(marker)

        return ft.Stack(markers)

    def _create_metrics_panel(self) -> ft.Control:
        """Create metrics display panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        if not self._current_reading:
            return ft.Container()

        metrics_items = [
            ("Memory Usage", f"{self._current_reading.memory_usage_percent:.1f}%"),
            ("Swap Usage", f"{self._current_reading.swap_usage_percent:.1f}%"),
            ("Allocation Rate", f"{self._current_reading.allocation_rate_mbps:.1f} MB/s"),
            ("Deallocation Rate", f"{self._current_reading.deallocation_rate_mbps:.1f} MB/s"),
            ("GC Frequency", f"{self._current_reading.gc_frequency:.2f} Hz")
        ]

        metric_widgets = []
        for label, value in metrics_items:
            metric_widgets.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(
                            label,
                            style=self.get_text_style('body_small'),
                            color=palette.text_secondary
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            value,
                            style=self.get_text_style('body_small'),
                            color=palette.text_primary
                        )
                    ]),
                    padding=ft.padding.symmetric(vertical=spacing.xs)
                )
            )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Pressure Metrics",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                ft.Column(metric_widgets, spacing=0)
            ]),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.md)
        )

    def _create_alert_panel(self) -> ft.Control:
        """Create alert notifications panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Get current alert level
        alert_level = self._get_current_alert_level()

        if alert_level == AlertLevel.NORMAL:
            return ft.Container()

        # Determine alert styling
        if alert_level == AlertLevel.WARNING:
            alert_color = palette.warning
            alert_icon = self.get_icon('WARNING')
            alert_text = "Memory pressure is elevated"
        elif alert_level == AlertLevel.CRITICAL:
            alert_color = palette.error
            alert_icon = self.get_icon('ERROR')
            alert_text = "Memory pressure is critical"
        else:  # EMERGENCY
            alert_color = palette.error
            alert_icon = self.get_icon('ERROR')
            alert_text = "Emergency: Memory exhaustion imminent"

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(alert_icon, color=alert_color, size=20),
                    ft.Text(
                        "Alert",
                        style=self.get_text_style('h4'),
                        color=alert_color
                    )
                ], spacing=spacing.sm),
                ft.Container(height=spacing.xs),
                ft.Text(
                    alert_text,
                    style=self.get_text_style('body_small'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.sm),
                ft.ElevatedButton(
                    text="Acknowledge",
                    on_click=self._acknowledge_alert,
                    bgcolor=alert_color,
                    color=palette.text_primary
                )
            ]),
            bgcolor=palette.surface_variant,
            border=ft.border.all(2, alert_color),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.md)
        )

    def _create_controls_panel(self) -> ft.Control:
        """Create controls panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Monitor toggle button
        monitor_button = ft.ElevatedButton(
            text="Stop Monitoring" if self._is_monitoring else "Start Monitoring",
            icon=self.get_icon('STOP') if self._is_monitoring else self.get_icon('PLAY'),
            on_click=self._toggle_monitoring,
            bgcolor=palette.error if self._is_monitoring else palette.success,
            color=palette.text_primary
        )

        # Style selector
        style_dropdown = ft.Dropdown(
            label="Gauge Style",
            options=[
                ft.dropdown.Option("circular", "Circular"),
                ft.dropdown.Option("linear", "Linear"),
                ft.dropdown.Option("digital", "Digital"),
                ft.dropdown.Option("compact", "Compact")
            ],
            value=self._gauge_style.value,
            on_change=self._on_style_change,
            width=150,
            bgcolor=palette.surface,
            color=palette.text_primary
        )

        # Threshold configuration button
        config_button = ft.ElevatedButton(
            text="Configure Thresholds",
            icon=self.get_icon('SETTINGS'),
            on_click=self._show_threshold_config,
            bgcolor=palette.secondary,
            color=palette.text_primary
        )

        return ft.Container(
            content=ft.Row([
                monitor_button,
                ft.Container(width=spacing.md),
                style_dropdown,
                ft.Container(width=spacing.md),
                config_button,
                ft.Container(expand=True),
                ft.Text(
                    f"Refresh: {self._refresh_interval:.1f}s",
                    style=self.get_text_style('body_small'),
                    color=palette.text_secondary
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.all(spacing.md)
        )

    def _get_pressure_color(self, pressure: float) -> str:
        """Get color based on pressure level."""
        palette = self.get_palette()

        if pressure < self._thresholds.low_threshold:
            return palette.success
        elif pressure < self._thresholds.moderate_threshold:
            return palette.info
        elif pressure < self._thresholds.high_threshold:
            return palette.warning
        else:
            return palette.error

    def _get_current_alert_level(self) -> AlertLevel:
        """Get current alert level based on pressure."""
        if not self._current_reading:
            return AlertLevel.NORMAL

        pressure = self._current_reading.pressure_score

        if pressure >= self._thresholds.critical_threshold:
            return AlertLevel.EMERGENCY
        elif pressure >= self._thresholds.high_threshold:
            return AlertLevel.CRITICAL
        elif pressure >= self._thresholds.moderate_threshold:
            return AlertLevel.WARNING
        else:
            return AlertLevel.NORMAL

    def _toggle_monitoring(self, e) -> None:
        """Toggle pressure monitoring."""
        try:
            if self._is_monitoring:
                asyncio.create_task(self.stop_monitoring())
            else:
                asyncio.create_task(self.start_monitoring())
        except Exception as ex:
            self._logger.error(f"Error toggling monitoring: {str(ex)}")

    def _on_style_change(self, e) -> None:
        """Handle gauge style change."""
        try:
            self._gauge_style = GaugeStyle(e.control.value)
            self.update()
        except Exception as ex:
            self._logger.error(f"Error changing gauge style: {str(ex)}")

    def _show_threshold_config(self, e) -> None:
        """Show threshold configuration dialog."""
        # This would open a configuration dialog
        # Implementation depends on the dialog system
        pass

    def _acknowledge_alert(self, e) -> None:
        """Acknowledge current alert."""
        # Reset alert state or log acknowledgment
        self.update()

    async def start_monitoring(self) -> None:
        """Start pressure monitoring."""
        try:
            if self._is_monitoring:
                return

            self._is_monitoring = True

            # Start memory monitor
            if self._memory_monitor:
                await self._memory_monitor.start_monitoring(self._refresh_interval)

            # Start monitoring task
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

            self.update()
            self._logger.info("Memory pressure monitoring started")

        except Exception as e:
            self._logger.error(f"Failed to start monitoring: {str(e)}")
            self._is_monitoring = False

    async def stop_monitoring(self) -> None:
        """Stop pressure monitoring."""
        try:
            if not self._is_monitoring:
                return

            self._is_monitoring = False

            # Stop monitoring task
            if self._monitoring_task:
                self._monitoring_task.cancel()
                self._monitoring_task = None

            # Stop memory monitor
            if self._memory_monitor:
                await self._memory_monitor.stop_monitoring()

            self.update()
            self._logger.info("Memory pressure monitoring stopped")

        except Exception as e:
            self._logger.error(f"Failed to stop monitoring: {str(e)}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._is_monitoring:
                await self._update_pressure_reading()
                self._check_alerts()
                self.update()
                await asyncio.sleep(self._refresh_interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in monitoring loop: {str(e)}")

    async def _update_pressure_reading(self) -> None:
        """Update current pressure reading."""
        try:
            if not self._memory_monitor:
                return

            # Get current memory metrics
            metrics = self._memory_monitor.get_current_metrics()
            if not metrics:
                return

            # Calculate pressure trend
            trend = self._calculate_pressure_trend()

            # Create new reading
            self._current_reading = PressureReading(
                timestamp=datetime.now(timezone.utc),
                pressure_score=metrics.memory_pressure_score,
                pressure_level=self._calculate_pressure_level(metrics.memory_pressure_score),
                pressure_trend=trend,
                memory_usage_percent=metrics.usage_percent,
                swap_usage_percent=metrics.swap_info.usage_percent,
                allocation_rate_mbps=metrics.allocation_rate_mb_per_sec,
                deallocation_rate_mbps=metrics.deallocation_rate_mb_per_sec,
                gc_frequency=self._calculate_gc_frequency(metrics)
            )

            # Add to history
            self._pressure_history.append(self._current_reading)

            # Cleanup old history
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=self._history_retention_minutes)
            self._pressure_history = [r for r in self._pressure_history if r.timestamp >= cutoff_time]

        except Exception as e:
            self._logger.error(f"Error updating pressure reading: {str(e)}")

    def _calculate_pressure_level(self, pressure_score: float) -> 'PressureLevel':
        """Calculate pressure level from score."""
        if pressure_score < self._thresholds.low_threshold:
            return PressureLevel.LOW
        elif pressure_score < self._thresholds.high_threshold:
            return PressureLevel.MODERATE
        elif pressure_score < self._thresholds.critical_threshold:
            return PressureLevel.HIGH
        else:
            return PressureLevel.CRITICAL

    def _calculate_pressure_trend(self) -> 'PressureTrend':
        """Calculate pressure trend from history."""
        if len(self._pressure_history) < 3:
            return PressureTrend.STABLE

        recent_scores = [r.pressure_score for r in self._pressure_history[-3:]]

        if recent_scores[-1] > recent_scores[0] + 0.05:
            return PressureTrend.INCREASING
        elif recent_scores[-1] < recent_scores[0] - 0.05:
            return PressureTrend.DECREASING
        else:
            return PressureTrend.STABLE

    def _calculate_gc_frequency(self, metrics) -> float:
        """Calculate garbage collection frequency."""
        # Simplified calculation - in real implementation, track GC events over time
        total_collections = sum(metrics.gc_collections.values()) if metrics.gc_collections else 0
        return total_collections / 60.0  # Collections per minute converted to Hz

    def _check_alerts(self) -> None:
        """Check for alert conditions and notify callbacks."""
        alert_level = self._get_current_alert_level()

        if alert_level != AlertLevel.NORMAL and self._current_reading:
            for callback in self._alert_callbacks:
                try:
                    callback(alert_level, self._current_reading)
                except Exception as e:
                    self._logger.error(f"Error in alert callback: {str(e)}")

    def add_alert_callback(self, callback: Callable[[AlertLevel, PressureReading], None]) -> None:
        """Add alert notification callback."""
        self._alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable[[AlertLevel, PressureReading], None]) -> None:
        """Remove alert notification callback."""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)

    def configure_thresholds(self, thresholds: PressureThresholds) -> None:
        """Configure pressure thresholds."""
        self._thresholds = thresholds
        self.update()

    def will_unmount(self) -> None:
        """Clean up when component is unmounted."""
        try:
            if self._is_monitoring:
                asyncio.create_task(self.stop_monitoring())
        except Exception as e:
            self._logger.error(f"Error during unmount: {str(e)}")
        finally:
            super().will_unmount()
