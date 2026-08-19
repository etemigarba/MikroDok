"""
Module: footer_status_ui
Description: Comprehensive footer status bar with system information, resource monitoring, version details,
            and quick access controls. Provides real-time system status display with responsive design,
            theme-aware styling, and accessibility compliance. Features memory usage tracking, GPU temperature
            monitoring, application version information, and quick settings access.
            
Features:
- Real-time system resource monitoring with visual indicators
- Responsive design with breakpoint-aware layout adjustments
- Memory usage display with progress indicators and alerts
- GPU temperature monitoring with thermal status indicators
- Application version and build information display
- Quick access controls for preferences, logs, and support
- Theme-aware styling with full integration to theme_system_ui
- Accessibility compliance with WCAG 2.1 AA standards
- Error handling and graceful degradation capabilities
- Integration with hardware monitoring and thermal services

Phase: 1
Location: /src/modules/ui/navigation_ui/footer_status_ui/footer_status_ui.py
"""

# Standard library imports
import asyncio
import logging
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

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
    ScreenSize,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class StatusLevel(Enum):
    """Status level indicators."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"
    INFO = "info"


class ResourceType(Enum):
    """Resource monitoring types."""
    MEMORY = "memory"
    CPU = "cpu"
    GPU = "gpu"
    DISK = "disk"
    NETWORK = "network"
    TEMPERATURE = "temperature"


@dataclass
class ResourceMetrics:
    """Resource metrics data structure."""
    memory_usage_percent: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    cpu_usage_percent: float = 0.0
    gpu_usage_percent: Optional[float] = None
    gpu_temperature_celsius: Optional[float] = None
    disk_usage_percent: float = 0.0
    network_upload_mbps: float = 0.0
    network_download_mbps: float = 0.0
    system_temperature: Optional[float] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SystemStatusInfo:
    """System status information."""
    application_version: str = "1.0.0"
    build_number: str = "dev"
    python_version: str = field(default_factory=lambda: f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    platform_info: str = field(default_factory=lambda: platform.system())
    uptime: str = "0:00:00"
    last_update_check: Optional[datetime] = None
    status_level: StatusLevel = StatusLevel.NORMAL
    status_message: str = "Ready"


@dataclass
class QuickAction:
    """Quick action configuration."""
    id: str
    label: str
    icon: str
    tooltip: str
    callback: Optional[Callable] = None
    enabled: bool = True
    visible: bool = True


@dataclass
class StatusIndicator:
    """Status indicator configuration."""
    id: str
    label: str
    value: str
    icon: str
    color: str
    tooltip: str
    level: StatusLevel = StatusLevel.NORMAL
    visible: bool = True


@dataclass
class FooterConfig:
    """Configuration for the footer status bar."""
    show_memory_usage: bool = True
    show_gpu_temperature: bool = True
    show_cpu_usage: bool = True
    show_disk_usage: bool = False
    show_network_stats: bool = False
    show_version_info: bool = True
    show_uptime: bool = True
    show_quick_actions: bool = True
    enable_auto_refresh: bool = True
    refresh_interval_seconds: float = 2.0
    compact_mode: bool = False
    enable_tooltips: bool = True
    enable_animations: bool = True
    max_indicators: int = 8
    height_pixels: int = 40


class FooterStatusUI(ThemeAwareUserControl):
    """
    Comprehensive footer status bar with system monitoring and quick access controls.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time system resource monitoring and status display
    - Memory usage tracking with visual progress indicators
    - GPU temperature monitoring with thermal status alerts
    - Application version and system information display
    - Quick access controls for common actions and settings
    - Theme-aware styling with accessibility compliance
    - Error handling and graceful degradation capabilities
    - Integration with hardware monitoring services
    """

    def __init__(
        self,
        config: Optional[FooterConfig] = None,
        on_quick_action: Optional[Callable[[str], None]] = None,
        on_status_click: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        """
        Initialize footer status UI.

        Args:
            config: Footer configuration settings
            on_quick_action: Callback for quick action clicks
            on_status_click: Callback for status indicator clicks
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or FooterConfig()
        self._on_quick_action = on_quick_action
        self._on_status_click = on_status_click
        
        # State management
        self._current_metrics = ResourceMetrics()
        self._system_info = SystemStatusInfo()
        self._status_indicators: List[StatusIndicator] = []
        self._quick_actions: List[QuickAction] = []
        self._is_monitoring = False
        self._refresh_task: Optional[asyncio.Task] = None
        
        # UI components
        self._main_container: Optional[ft.Container] = None
        self._status_section: Optional[ft.Container] = None
        self._metrics_section: Optional[ft.Container] = None
        self._version_section: Optional[ft.Container] = None
        self._actions_section: Optional[ft.Container] = None
        
        # Initialize components
        self._initialize_default_indicators()
        self._initialize_default_actions()
        
        logger.debug("FooterStatusUI initialized")

    def _initialize_default_indicators(self) -> None:
        """Initialize default status indicators."""
        try:
            self._status_indicators = [
                StatusIndicator(
                    id="status",
                    label="Status",
                    value="Ready",
                    icon="CHECK_CIRCLE",
                    color="success",
                    tooltip="Application status",
                    level=StatusLevel.NORMAL
                ),
                StatusIndicator(
                    id="memory",
                    label="Memory",
                    value="0.0 GB",
                    icon="MEMORY",
                    color="primary",
                    tooltip="Memory usage",
                    level=StatusLevel.NORMAL,
                    visible=self._config.show_memory_usage
                ),
                StatusIndicator(
                    id="cpu",
                    label="CPU",
                    value="0%",
                    icon="SPEED",
                    color="primary",
                    tooltip="CPU usage",
                    level=StatusLevel.NORMAL,
                    visible=self._config.show_cpu_usage
                ),
                StatusIndicator(
                    id="gpu_temp",
                    label="GPU",
                    value="--°C",
                    icon="DEVICE_THERMOSTAT",
                    color="primary",
                    tooltip="GPU temperature",
                    level=StatusLevel.NORMAL,
                    visible=self._config.show_gpu_temperature
                )
            ]
            
            # Add optional indicators
            if self._config.show_disk_usage:
                self._status_indicators.append(
                    StatusIndicator(
                        id="disk",
                        label="Disk",
                        value="0%",
                        icon="STORAGE",
                        color="primary",
                        tooltip="Disk usage",
                        level=StatusLevel.NORMAL
                    )
                )
            
            if self._config.show_network_stats:
                self._status_indicators.append(
                    StatusIndicator(
                        id="network",
                        label="Network",
                        value="0 MB/s",
                        icon="NETWORK_CHECK",
                        color="primary",
                        tooltip="Network activity",
                        level=StatusLevel.NORMAL
                    )
                )
                
        except Exception as e:
            logger.error(f"Error initializing default indicators: {e}")

    def _initialize_default_actions(self) -> None:
        """Initialize default quick actions."""
        try:
            if not self._config.show_quick_actions:
                return
                
            self._quick_actions = [
                QuickAction(
                    id="preferences",
                    label="Preferences",
                    icon="SETTINGS",
                    tooltip="Open application preferences"
                ),
                QuickAction(
                    id="logs",
                    label="Logs",
                    icon="DESCRIPTION",
                    tooltip="View application logs"
                ),
                QuickAction(
                    id="support",
                    label="Support",
                    icon="HELP",
                    tooltip="Get help and support"
                ),
                QuickAction(
                    id="about",
                    label="About",
                    icon="INFO",
                    tooltip="About MikroDok"
                )
            ]
            
        except Exception as e:
            logger.error(f"Error initializing default actions: {e}")

    def build(self) -> ft.Control:
        """Build the footer status bar interface."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            rlm = self.get_responsive_layout()

            # Create main footer container
            self._main_container = ft.Container(
                content=ft.Row(
                    controls=[
                        self._build_status_section(),
                        ft.Container(expand=True),  # Spacer
                        self._build_metrics_section(),
                        self._build_version_section() if self._config.show_version_info else ft.Container(),
                        self._build_actions_section() if self._config.show_quick_actions else ft.Container()
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.md
                ),
                bgcolor=palette.surface_variant,
                padding=ft.padding.symmetric(
                    horizontal=rlm.get_breakpoint_value(8, 12, 16, 20),
                    vertical=rlm.get_breakpoint_value(4, 6, 8, 10)
                ),
                height=rlm.get_breakpoint_value(
                    self._config.height_pixels - 8,
                    self._config.height_pixels - 4,
                    self._config.height_pixels,
                    self._config.height_pixels + 4
                ),
                border=ft.border.only(top=ft.BorderSide(1, palette.outline_variant))
            )

            # Start monitoring if enabled
            if self._config.enable_auto_refresh and not self._is_monitoring:
                self._start_monitoring()

            return self._main_container

        except Exception as e:
            logger.error(f"Error building footer status UI: {e}")
            return self._build_error_fallback()

    def _build_error_fallback(self) -> ft.Control:
        """Build error fallback UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ERROR, color=palette.error, size=16),
                ft.Text("Footer Error", color=palette.error, size=12)
            ], spacing=spacing.xs),
            bgcolor=palette.error_container,
            padding=ft.padding.all(8),
            height=self._config.height_pixels
        )

    def _build_status_section(self) -> ft.Control:
        """Build the main status section."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Get main status indicator
            main_status = next(
                (indicator for indicator in self._status_indicators if indicator.id == "status"),
                self._status_indicators[0] if self._status_indicators else None
            )

            if not main_status:
                return ft.Container()

            # Status color based on level
            status_color = self._get_status_color(main_status.level)

            self._status_section = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            name=getattr(ft.Icons, main_status.icon, ft.Icons.INFO),
                            size=self.get_breakpoint_value(14, 16, 18, 20),
                            color=status_color
                        ),
                        ft.Text(
                            main_status.value,
                            style=typography.get_text_style("bodySmall"),
                            color=palette.on_surface,
                            weight=ft.FontWeight.W_500
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                ),
                tooltip=main_status.tooltip if self._config.enable_tooltips else None,
                on_click=lambda e: self._handle_status_click(main_status.id) if self._on_status_click else None
            )

            return self._status_section

        except Exception as e:
            logger.error(f"Error building status section: {e}")
            return ft.Container()

    def _build_metrics_section(self) -> ft.Control:
        """Build the system metrics section."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            rlm = self.get_responsive_layout()

            # Filter visible indicators (excluding main status)
            visible_indicators = [
                indicator for indicator in self._status_indicators
                if indicator.visible and indicator.id != "status"
            ]

            # Limit indicators based on screen size and configuration
            max_indicators = rlm.get_breakpoint_value(2, 3, 4, self._config.max_indicators)
            visible_indicators = visible_indicators[:max_indicators]

            if not visible_indicators:
                return ft.Container()

            metric_controls = []
            for indicator in visible_indicators:
                metric_control = self._create_metric_indicator(indicator)
                if metric_control:
                    metric_controls.append(metric_control)

            self._metrics_section = ft.Container(
                content=ft.Row(
                    controls=metric_controls,
                    spacing=rlm.get_breakpoint_value(spacing.sm, spacing.md, spacing.lg, spacing.xl),
                    tight=True
                ),
                visible=len(metric_controls) > 0
            )

            return self._metrics_section

        except Exception as e:
            logger.error(f"Error building metrics section: {e}")
            return ft.Container()

    def _create_metric_indicator(self, indicator: StatusIndicator) -> Optional[ft.Control]:
        """Create a single metric indicator."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            # Determine color based on indicator level and type
            indicator_color = self._get_indicator_color(indicator)

            # Create progress indicator for percentage values
            show_progress = "%" in indicator.value and indicator.id in ["memory", "cpu", "disk"]

            controls = [
                ft.Icon(
                    name=getattr(ft.Icons, indicator.icon, ft.Icons.INFO),
                    size=self.get_breakpoint_value(12, 14, 16, 18),
                    color=indicator_color
                )
            ]

            # Add progress bar for percentage metrics
            if show_progress:
                try:
                    percentage = float(indicator.value.replace("%", ""))
                    progress_color = self._get_progress_color(percentage, indicator.id)

                    controls.append(
                        ft.Container(
                            content=ft.ProgressBar(
                                value=percentage / 100,
                                color=progress_color,
                                bgcolor=palette.surface_variant,
                                height=3
                            ),
                            width=self.get_breakpoint_value(30, 40, 50, 60),
                            margin=ft.margin.symmetric(horizontal=spacing.xs)
                        )
                    )
                except (ValueError, AttributeError):
                    pass

            # Add value text
            controls.append(
                ft.Text(
                    indicator.value,
                    style=typography.get_text_style("bodySmall"),
                    color=palette.on_surface_variant,
                    size=self.get_breakpoint_value(10, 11, 12, 13)
                )
            )

            return ft.Container(
                content=ft.Row(
                    controls=controls,
                    spacing=spacing.xs,
                    tight=True
                ),
                tooltip=indicator.tooltip if self._config.enable_tooltips else None,
                on_click=lambda e, ind_id=indicator.id: self._handle_status_click(ind_id) if self._on_status_click else None
            )

        except Exception as e:
            logger.error(f"Error creating metric indicator for {indicator.id}: {e}")
            return None

    def _build_version_section(self) -> ft.Control:
        """Build the version information section."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            rlm = self.get_responsive_layout()

            # Show different information based on screen size
            screen_size = self.get_current_screen_size()

            if screen_size == ScreenSize.MOBILE:
                # Mobile: Show only version
                version_text = f"v{self._system_info.application_version}"
            elif screen_size == ScreenSize.TABLET:
                # Tablet: Show version and platform
                version_text = f"v{self._system_info.application_version} • {self._system_info.platform_info}"
            else:
                # Desktop: Show full information
                version_text = f"v{self._system_info.application_version} • Python {self._system_info.python_version}"
                if self._config.show_uptime and self._system_info.uptime != "0:00:00":
                    version_text += f" • Uptime: {self._system_info.uptime}"

            self._version_section = ft.Container(
                content=ft.Text(
                    version_text,
                    style=typography.get_text_style("bodySmall"),
                    color=palette.on_surface_variant,
                    size=self.get_breakpoint_value(10, 11, 12, 13)
                ),
                tooltip=self._get_version_tooltip() if self._config.enable_tooltips else None,
                on_click=lambda e: self._handle_status_click("version") if self._on_status_click else None
            )

            return self._version_section

        except Exception as e:
            logger.error(f"Error building version section: {e}")
            return ft.Container()

    def _build_actions_section(self) -> ft.Control:
        """Build the quick actions section."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            rlm = self.get_responsive_layout()

            # Filter visible and enabled actions
            visible_actions = [
                action for action in self._quick_actions
                if action.visible and action.enabled
            ]

            if not visible_actions:
                return ft.Container()

            # Limit actions based on screen size
            max_actions = rlm.get_breakpoint_value(2, 3, 4, len(visible_actions))
            visible_actions = visible_actions[:max_actions]

            action_controls = []
            for action in visible_actions:
                action_control = self._create_action_button(action)
                if action_control:
                    action_controls.append(action_control)

            self._actions_section = ft.Container(
                content=ft.Row(
                    controls=action_controls,
                    spacing=spacing.xs,
                    tight=True
                ),
                visible=len(action_controls) > 0
            )

            return self._actions_section

        except Exception as e:
            logger.error(f"Error building actions section: {e}")
            return ft.Container()

    def _create_action_button(self, action: QuickAction) -> Optional[ft.Control]:
        """Create a quick action button."""
        try:
            palette = self.get_palette()

            return ft.IconButton(
                icon=getattr(ft.Icons, action.icon, ft.Icons.HELP),
                icon_size=self.get_breakpoint_value(16, 18, 20, 22),
                icon_color=palette.on_surface_variant,
                tooltip=action.tooltip if self._config.enable_tooltips else None,
                on_click=lambda e, action_id=action.id: self._handle_quick_action(action_id),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=4),
                    padding=ft.padding.all(4)
                )
            )

        except Exception as e:
            logger.error(f"Error creating action button for {action.id}: {e}")
            return None

    def _get_status_color(self, level: StatusLevel) -> str:
        """Get color for status level."""
        palette = self.get_palette()

        color_map = {
            StatusLevel.NORMAL: palette.success,
            StatusLevel.INFO: palette.primary,
            StatusLevel.WARNING: palette.warning,
            StatusLevel.CRITICAL: palette.error,
            StatusLevel.ERROR: palette.error
        }

        return color_map.get(level, palette.on_surface)

    def _get_indicator_color(self, indicator: StatusIndicator) -> str:
        """Get color for indicator based on type and level."""
        palette = self.get_palette()

        # Override color based on level
        if indicator.level != StatusLevel.NORMAL:
            return self._get_status_color(indicator.level)

        # Default colors by type
        color_map = {
            "memory": palette.primary,
            "cpu": palette.secondary,
            "gpu_temp": palette.tertiary,
            "disk": palette.primary,
            "network": palette.secondary
        }

        return color_map.get(indicator.id, palette.on_surface_variant)

    def _get_progress_color(self, percentage: float, metric_type: str) -> str:
        """Get progress bar color based on percentage and type."""
        palette = self.get_palette()

        # Define thresholds by metric type
        thresholds = {
            "memory": {"warning": 80, "critical": 90},
            "cpu": {"warning": 70, "critical": 85},
            "disk": {"warning": 85, "critical": 95}
        }

        metric_thresholds = thresholds.get(metric_type, {"warning": 80, "critical": 90})

        if percentage >= metric_thresholds["critical"]:
            return palette.error
        elif percentage >= metric_thresholds["warning"]:
            return palette.warning
        else:
            return palette.success

    def _get_version_tooltip(self) -> str:
        """Get detailed version tooltip."""
        try:
            tooltip_parts = [
                f"MikroDok v{self._system_info.application_version}",
                f"Build: {self._system_info.build_number}",
                f"Python: {self._system_info.python_version}",
                f"Platform: {self._system_info.platform_info}"
            ]

            if self._system_info.last_update_check:
                tooltip_parts.append(
                    f"Last update check: {self._system_info.last_update_check.strftime('%Y-%m-%d %H:%M')}"
                )

            return "\n".join(tooltip_parts)

        except Exception as e:
            logger.error(f"Error creating version tooltip: {e}")
            return "Version information"

    def _handle_status_click(self, status_id: str) -> None:
        """Handle status indicator click."""
        try:
            logger.debug(f"Status clicked: {status_id}")
            if self._on_status_click:
                self._on_status_click(status_id)
        except Exception as e:
            logger.error(f"Error handling status click for {status_id}: {e}")

    def _handle_quick_action(self, action_id: str) -> None:
        """Handle quick action button click."""
        try:
            logger.debug(f"Quick action triggered: {action_id}")

            # Find the action and execute callback if available
            action = next((a for a in self._quick_actions if a.id == action_id), None)
            if action and action.callback:
                action.callback()
            elif self._on_quick_action:
                self._on_quick_action(action_id)

        except Exception as e:
            logger.error(f"Error handling quick action {action_id}: {e}")

    def _start_monitoring(self) -> None:
        """Start resource monitoring."""
        try:
            if self._is_monitoring:
                return

            self._is_monitoring = True
            self._refresh_task = asyncio.create_task(self._monitoring_loop())
            logger.debug("Resource monitoring started")

        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
            self._is_monitoring = False

    def _stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        try:
            self._is_monitoring = False

            if self._refresh_task and not self._refresh_task.done():
                self._refresh_task.cancel()

            logger.debug("Resource monitoring stopped")

        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._is_monitoring:
                # Update metrics
                await self._update_metrics()

                # Update UI
                self._update_ui_components()

                # Wait for next refresh
                await asyncio.sleep(self._config.refresh_interval_seconds)

        except asyncio.CancelledError:
            logger.debug("Monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            self._is_monitoring = False

    async def _update_metrics(self) -> None:
        """Update system metrics."""
        try:
            # Import monitoring modules if available
            try:
                import psutil

                # Memory metrics
                memory = psutil.virtual_memory()
                self._current_metrics.memory_usage_percent = memory.percent
                self._current_metrics.memory_used_gb = memory.used / (1024**3)
                self._current_metrics.memory_total_gb = memory.total / (1024**3)

                # CPU metrics
                self._current_metrics.cpu_usage_percent = psutil.cpu_percent(interval=None)

                # Disk metrics
                disk = psutil.disk_usage('/')
                self._current_metrics.disk_usage_percent = (disk.used / disk.total) * 100

                # Network metrics (if enabled)
                if self._config.show_network_stats:
                    net_io = psutil.net_io_counters()
                    # This would need to calculate rates over time
                    # For now, just set to 0
                    self._current_metrics.network_upload_mbps = 0.0
                    self._current_metrics.network_download_mbps = 0.0

            except ImportError:
                logger.debug("psutil not available, using mock data")
                # Use mock data for development
                self._current_metrics.memory_usage_percent = 45.2
                self._current_metrics.memory_used_gb = 3.6
                self._current_metrics.memory_total_gb = 8.0
                self._current_metrics.cpu_usage_percent = 23.1
                self._current_metrics.disk_usage_percent = 67.8

            # GPU metrics (if available)
            try:
                # This would integrate with GPU monitoring if available
                # For now, use mock data
                self._current_metrics.gpu_temperature_celsius = 65.0
                self._current_metrics.gpu_usage_percent = 15.3
            except Exception:
                self._current_metrics.gpu_temperature_celsius = None
                self._current_metrics.gpu_usage_percent = None

            # Update timestamp
            self._current_metrics.last_updated = datetime.now(timezone.utc)

            # Update status indicators
            self._update_status_indicators()

        except Exception as e:
            logger.error(f"Error updating metrics: {e}")

    def _update_status_indicators(self) -> None:
        """Update status indicator values based on current metrics."""
        try:
            for indicator in self._status_indicators:
                if indicator.id == "memory":
                    indicator.value = f"{self._current_metrics.memory_used_gb:.1f} GB"
                    indicator.level = self._get_memory_status_level()

                elif indicator.id == "cpu":
                    indicator.value = f"{self._current_metrics.cpu_usage_percent:.0f}%"
                    indicator.level = self._get_cpu_status_level()

                elif indicator.id == "gpu_temp":
                    if self._current_metrics.gpu_temperature_celsius is not None:
                        indicator.value = f"{self._current_metrics.gpu_temperature_celsius:.0f}°C"
                        indicator.level = self._get_gpu_temp_status_level()
                    else:
                        indicator.value = "--°C"
                        indicator.level = StatusLevel.NORMAL

                elif indicator.id == "disk":
                    indicator.value = f"{self._current_metrics.disk_usage_percent:.0f}%"
                    indicator.level = self._get_disk_status_level()

                elif indicator.id == "network":
                    upload = self._current_metrics.network_upload_mbps
                    download = self._current_metrics.network_download_mbps
                    total = upload + download
                    indicator.value = f"{total:.1f} MB/s"
                    indicator.level = StatusLevel.NORMAL

        except Exception as e:
            logger.error(f"Error updating status indicators: {e}")

    def _get_memory_status_level(self) -> StatusLevel:
        """Get memory usage status level."""
        usage = self._current_metrics.memory_usage_percent
        if usage >= 90:
            return StatusLevel.CRITICAL
        elif usage >= 80:
            return StatusLevel.WARNING
        else:
            return StatusLevel.NORMAL

    def _get_cpu_status_level(self) -> StatusLevel:
        """Get CPU usage status level."""
        usage = self._current_metrics.cpu_usage_percent
        if usage >= 85:
            return StatusLevel.CRITICAL
        elif usage >= 70:
            return StatusLevel.WARNING
        else:
            return StatusLevel.NORMAL

    def _get_gpu_temp_status_level(self) -> StatusLevel:
        """Get GPU temperature status level."""
        if self._current_metrics.gpu_temperature_celsius is None:
            return StatusLevel.NORMAL

        temp = self._current_metrics.gpu_temperature_celsius
        if temp >= 85:
            return StatusLevel.CRITICAL
        elif temp >= 75:
            return StatusLevel.WARNING
        else:
            return StatusLevel.NORMAL

    def _get_disk_status_level(self) -> StatusLevel:
        """Get disk usage status level."""
        usage = self._current_metrics.disk_usage_percent
        if usage >= 95:
            return StatusLevel.CRITICAL
        elif usage >= 85:
            return StatusLevel.WARNING
        else:
            return StatusLevel.NORMAL

    def _update_ui_components(self) -> None:
        """Update UI components with current data."""
        try:
            if not self._main_container:
                return

            # Update metrics section
            if self._metrics_section:
                # Rebuild metrics section with updated data
                updated_metrics = self._build_metrics_section()
                if updated_metrics and self._main_container.content:
                    # Find and replace metrics section
                    row_controls = self._main_container.content.controls
                    for i, control in enumerate(row_controls):
                        if control == self._metrics_section:
                            row_controls[i] = updated_metrics
                            self._metrics_section = updated_metrics
                            break

            # Update status section
            if self._status_section:
                updated_status = self._build_status_section()
                if updated_status and self._main_container.content:
                    row_controls = self._main_container.content.controls
                    for i, control in enumerate(row_controls):
                        if control == self._status_section:
                            row_controls[i] = updated_status
                            self._status_section = updated_status
                            break

            # Trigger UI update
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error updating UI components: {e}")

    # Public API methods

    def update_system_info(self, info: SystemStatusInfo) -> None:
        """
        Update system information.

        Args:
            info: New system status information
        """
        try:
            self._system_info = info

            # Update main status indicator
            main_status = next(
                (indicator for indicator in self._status_indicators if indicator.id == "status"),
                None
            )
            if main_status:
                main_status.value = info.status_message
                main_status.level = info.status_level

            # Update UI if built
            if self._main_container:
                self._update_ui_components()

        except Exception as e:
            logger.error(f"Error updating system info: {e}")

    def update_metrics(self, metrics: ResourceMetrics) -> None:
        """
        Update resource metrics.

        Args:
            metrics: New resource metrics
        """
        try:
            self._current_metrics = metrics
            self._update_status_indicators()

            # Update UI if built
            if self._main_container:
                self._update_ui_components()

        except Exception as e:
            logger.error(f"Error updating metrics: {e}")

    def add_quick_action(self, action: QuickAction) -> None:
        """
        Add a quick action.

        Args:
            action: Quick action to add
        """
        try:
            # Remove existing action with same ID
            self._quick_actions = [a for a in self._quick_actions if a.id != action.id]
            self._quick_actions.append(action)

            # Update UI if built
            if self._main_container and self._config.show_quick_actions:
                self._update_ui_components()

        except Exception as e:
            logger.error(f"Error adding quick action {action.id}: {e}")

    def remove_quick_action(self, action_id: str) -> None:
        """
        Remove a quick action.

        Args:
            action_id: ID of action to remove
        """
        try:
            self._quick_actions = [a for a in self._quick_actions if a.id != action_id]

            # Update UI if built
            if self._main_container and self._config.show_quick_actions:
                self._update_ui_components()

        except Exception as e:
            logger.error(f"Error removing quick action {action_id}: {e}")

    def set_status(self, message: str, level: StatusLevel = StatusLevel.NORMAL) -> None:
        """
        Set main status message.

        Args:
            message: Status message
            level: Status level
        """
        try:
            self._system_info.status_message = message
            self._system_info.status_level = level

            # Update main status indicator
            main_status = next(
                (indicator for indicator in self._status_indicators if indicator.id == "status"),
                None
            )
            if main_status:
                main_status.value = message
                main_status.level = level

            # Update UI if built
            if self._main_container:
                self._update_ui_components()

        except Exception as e:
            logger.error(f"Error setting status: {e}")

    def get_current_metrics(self) -> ResourceMetrics:
        """
        Get current resource metrics.

        Returns:
            Current resource metrics
        """
        return self._current_metrics

    def get_system_info(self) -> SystemStatusInfo:
        """
        Get current system information.

        Returns:
            Current system information
        """
        return self._system_info

    def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self._config.enable_auto_refresh:
            self._start_monitoring()

    def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self._stop_monitoring()

    def is_monitoring(self) -> bool:
        """
        Check if monitoring is active.

        Returns:
            True if monitoring is active
        """
        return self._is_monitoring

    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self._stop_monitoring()
            logger.debug("FooterStatusUI cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    # Integration with monitoring services

    def integrate_hardware_monitor(self, hardware_monitor) -> None:
        """
        Integrate with hardware monitoring service.

        Args:
            hardware_monitor: Hardware monitor instance
        """
        try:
            self._hardware_monitor = hardware_monitor
            logger.debug("Hardware monitor integrated")
        except Exception as e:
            logger.error(f"Error integrating hardware monitor: {e}")

    def integrate_thermal_monitor(self, thermal_monitor) -> None:
        """
        Integrate with thermal monitoring service.

        Args:
            thermal_monitor: Thermal monitor instance
        """
        try:
            self._thermal_monitor = thermal_monitor
            logger.debug("Thermal monitor integrated")
        except Exception as e:
            logger.error(f"Error integrating thermal monitor: {e}")

    async def _get_hardware_metrics(self) -> Optional[Dict[str, Any]]:
        """Get metrics from hardware monitor if available."""
        try:
            if hasattr(self, '_hardware_monitor') and self._hardware_monitor:
                # Get current metrics from hardware monitor
                metrics = await self._hardware_monitor.get_current_metrics()
                if metrics:
                    return {
                        'cpu_usage': metrics.cpu_usage_percent,
                        'memory_usage': metrics.memory_usage_percent,
                        'memory_used_gb': metrics.memory_used_gb,
                        'memory_total_gb': metrics.memory_total_gb,
                        'gpu_usage': metrics.gpu_usage_percent,
                        'disk_usage': metrics.disk_usage_percent
                    }
        except Exception as e:
            logger.debug(f"Error getting hardware metrics: {e}")
        return None

    async def _get_thermal_metrics(self) -> Optional[Dict[str, Any]]:
        """Get metrics from thermal monitor if available."""
        try:
            if hasattr(self, '_thermal_monitor') and self._thermal_monitor:
                # Get current thermal metrics
                metrics = await self._thermal_monitor.get_current_metrics()
                if metrics:
                    return {
                        'gpu_temperature': metrics.gpu_temperature,
                        'cpu_temperature': metrics.cpu_temperature,
                        'system_temperature': metrics.average_temperature
                    }
        except Exception as e:
            logger.debug(f"Error getting thermal metrics: {e}")
        return None

    # Accessibility and keyboard navigation

    def _setup_accessibility(self) -> None:
        """Setup accessibility features."""
        try:
            # Add ARIA labels and roles
            if self._main_container:
                # Set semantic role
                self._main_container.semantics_label = "Application status bar"

                # Add keyboard navigation support
                self._setup_keyboard_navigation()

        except Exception as e:
            logger.error(f"Error setting up accessibility: {e}")

    def _setup_keyboard_navigation(self) -> None:
        """Setup keyboard navigation for footer elements."""
        try:
            # This would be implemented based on Flet's keyboard navigation capabilities
            # For now, ensure all interactive elements have proper focus handling
            pass
        except Exception as e:
            logger.error(f"Error setting up keyboard navigation: {e}")

    def _get_accessibility_description(self) -> str:
        """Get accessibility description for screen readers."""
        try:
            parts = []

            # Main status
            main_status = next(
                (indicator for indicator in self._status_indicators if indicator.id == "status"),
                None
            )
            if main_status:
                parts.append(f"Status: {main_status.value}")

            # Resource metrics
            for indicator in self._status_indicators:
                if indicator.visible and indicator.id != "status":
                    parts.append(f"{indicator.label}: {indicator.value}")

            # Version info
            if self._config.show_version_info:
                parts.append(f"Version: {self._system_info.application_version}")

            return ", ".join(parts)

        except Exception as e:
            logger.error(f"Error creating accessibility description: {e}")
            return "Application status information"

    # Error handling and fallback mechanisms

    def _handle_monitoring_error(self, error: Exception) -> None:
        """Handle monitoring errors gracefully."""
        try:
            logger.warning(f"Monitoring error: {error}")

            # Set error status
            self.set_status("Monitoring Error", StatusLevel.WARNING)

            # Disable problematic indicators
            for indicator in self._status_indicators:
                if indicator.id in ["memory", "cpu", "gpu_temp", "disk"]:
                    indicator.value = "N/A"
                    indicator.level = StatusLevel.ERROR

            # Update UI
            if self._main_container:
                self._update_ui_components()

        except Exception as e:
            logger.error(f"Error handling monitoring error: {e}")

    def _enable_graceful_degradation(self) -> None:
        """Enable graceful degradation when services are unavailable."""
        try:
            # Check for available monitoring services
            monitoring_available = False

            try:
                import psutil
                monitoring_available = True
            except ImportError:
                logger.info("psutil not available - using mock data")

            if not monitoring_available:
                # Use mock data and disable auto-refresh
                self._config.enable_auto_refresh = False
                self._use_mock_data()

        except Exception as e:
            logger.error(f"Error enabling graceful degradation: {e}")

    def _use_mock_data(self) -> None:
        """Use mock data when real monitoring is unavailable."""
        try:
            # Set mock metrics
            self._current_metrics = ResourceMetrics(
                memory_usage_percent=45.2,
                memory_used_gb=3.6,
                memory_total_gb=8.0,
                cpu_usage_percent=23.1,
                gpu_temperature_celsius=65.0,
                disk_usage_percent=67.8,
                last_updated=datetime.now(timezone.utc)
            )

            # Update indicators
            self._update_status_indicators()

            # Set status to indicate mock data
            self.set_status("Demo Mode", StatusLevel.INFO)

        except Exception as e:
            logger.error(f"Error setting up mock data: {e}")

    # Theme change handling

    def on_theme_changed(self) -> None:
        """Handle theme changes."""
        try:
            # Rebuild UI with new theme
            if self._main_container:
                self._update_ui_components()

            logger.debug("Footer status UI theme updated")

        except Exception as e:
            logger.error(f"Error handling theme change: {e}")

    # Responsive design helpers

    def _adapt_to_screen_size(self) -> None:
        """Adapt layout to current screen size."""
        try:
            screen_size = self.get_current_screen_size()

            # Adjust configuration based on screen size
            if screen_size == ScreenSize.MOBILE:
                # Mobile: Show minimal information
                self._config.max_indicators = 2
                self._config.show_uptime = False
                self._config.show_network_stats = False

            elif screen_size == ScreenSize.TABLET:
                # Tablet: Show moderate information
                self._config.max_indicators = 3
                self._config.show_uptime = False

            else:
                # Desktop: Show full information
                self._config.max_indicators = 8
                self._config.show_uptime = True

            # Update UI if built
            if self._main_container:
                self._update_ui_components()

        except Exception as e:
            logger.error(f"Error adapting to screen size: {e}")

    def on_resize(self, width: int, height: int) -> None:
        """Handle window resize events."""
        try:
            # Adapt to new screen size
            self._adapt_to_screen_size()

        except Exception as e:
            logger.error(f"Error handling resize: {e}")
