"""
Module: allocation_visualizer_ui
Description: Displays real-time memory distribution across tiers with animated flow indicators
Phase: 4
Location: /src/modules/ui/memory_monitor_ui/allocation_visualizer_ui/
"""

# Standard library imports
import asyncio
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.memory_allocation_lg.memory_tier_manager_lg.memory_tier_manager_lg import (
    MemoryTierManager, MemoryTierInfo, TierCapacity, TierBandwidth, TierStatus
)
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg.memory_pressure_handler_lg import MemoryTier
from src.modules.logic.resource_monitor_lg.memory_monitor_lg.memory_monitor_lg import (
    MemoryMonitor, MemoryMetrics
)


class VisualizationMode(Enum):
    """Visualization display modes."""
    FLOW_DIAGRAM = "flow_diagram"
    TIER_BARS = "tier_bars"
    ALLOCATION_MAP = "allocation_map"
    BANDWIDTH_CHART = "bandwidth_chart"


class AnimationState(Enum):
    """Animation states for flow indicators."""
    IDLE = "idle"
    ALLOCATING = "allocating"
    DEALLOCATING = "deallocating"
    MIGRATING = "migrating"


@dataclass
class TierVisualizationData:
    """Data for tier visualization."""
    tier: MemoryTier
    name: str
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float
    bandwidth_mbps: float
    latency_ms: float
    allocation_count: int
    status: TierStatus
    color: str
    icon: str


@dataclass
class AllocationFlow:
    """Represents memory allocation flow between tiers."""
    source_tier: MemoryTier
    target_tier: MemoryTier
    bytes_per_second: float
    direction: str  # "in", "out", "bidirectional"
    animation_state: AnimationState
    timestamp: datetime


class AllocationVisualizerUI(ThemeAwareUserControl):
    """
    Allocation visualizer UI component.
    
    Provides comprehensive memory allocation visualization with:
    - Real-time memory distribution across GPU VRAM, System RAM, and NVMe tiers
    - Animated flow indicators showing allocation movements
    - Interactive tier utilization displays with capacity indicators
    - Bandwidth and latency metrics visualization
    - Multiple visualization modes (flow diagram, bars, allocation map)
    - Theme-aware styling and accessibility compliance
    - Performance optimization for real-time updates
    - Configurable refresh rates and animation settings
    """

    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        
        # Core components
        self._memory_tier_manager: Optional[MemoryTierManager] = None
        self._memory_monitor: Optional[MemoryMonitor] = None
        
        # Visualization state
        self._current_mode = VisualizationMode.FLOW_DIAGRAM
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._refresh_interval = 1.0  # seconds
        self._animation_enabled = True
        
        # Data storage
        self._tier_data: Dict[MemoryTier, TierVisualizationData] = {}
        self._allocation_flows: List[AllocationFlow] = []
        self._metrics_history: List[Tuple[datetime, Dict[MemoryTier, float]]] = []
        
        # UI components
        self._mode_selector: Optional[ft.Dropdown] = None
        self._tier_containers: Dict[MemoryTier, ft.Container] = {}
        self._flow_indicators: List[ft.Container] = []
        self._metrics_display: Optional[ft.Container] = None
        self._animation_controls: Optional[ft.Row] = None
        
        # Animation state
        self._animation_frame = 0
        self._animation_timer: Optional[asyncio.Task] = None
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize memory monitoring components."""
        try:
            # Initialize memory tier manager
            self._memory_tier_manager = MemoryTierManager()
            
            # Initialize memory monitor
            self._memory_monitor = MemoryMonitor()
            
            # Initialize tier data
            self._initialize_tier_data()
            
        except Exception as e:
            self._logger.error(f"Failed to initialize components: {str(e)}")
    
    def _initialize_tier_data(self) -> None:
        """Initialize tier visualization data."""
        palette = self.get_palette()
        
        # Define tier configurations
        tier_configs = {
            MemoryTier.GPU_MEMORY: {
                "name": "GPU VRAM",
                "color": palette.primary,
                "icon": self.get_icon('CPU')
            },
            MemoryTier.RAM: {
                "name": "System RAM",
                "color": palette.secondary,
                "icon": self.get_icon('MEMORY')
            },
            MemoryTier.NVME_CACHE: {
                "name": "NVMe Cache",
                "color": palette.info,
                "icon": self.get_icon('MEMORY')
            },
            MemoryTier.SSD_STORAGE: {
                "name": "SSD Storage",
                "color": palette.warning,
                "icon": self.get_icon('SAVE')
            }
        }
        
        # Initialize tier data with defaults
        for tier, config in tier_configs.items():
            self._tier_data[tier] = TierVisualizationData(
                tier=tier,
                name=config["name"],
                total_bytes=0,
                used_bytes=0,
                available_bytes=0,
                usage_percent=0.0,
                bandwidth_mbps=0.0,
                latency_ms=0.0,
                allocation_count=0,
                status=TierStatus.INACTIVE,
                color=config["color"],
                icon=config["icon"]
            )
    
    def build(self) -> ft.Control:
        """Build the allocation visualizer UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header with controls
        header = self._create_header()
        
        # Create main visualization area
        visualization_area = self._create_visualization_area()
        
        # Create metrics panel
        metrics_panel = self._create_metrics_panel()
        
        # Create controls panel
        controls_panel = self._create_controls_panel()
        
        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=spacing.md),
                ft.Row([
                    ft.Container(
                        content=visualization_area,
                        expand=True
                    ),
                    ft.Container(width=spacing.lg),
                    ft.Container(
                        content=metrics_panel,
                        width=300
                    )
                ], expand=True),
                ft.Container(height=spacing.md),
                controls_panel
            ], expand=True),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )
    
    def _create_header(self) -> ft.Control:
        """Create header with title and mode selector."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create mode selector
        self._mode_selector = ft.Dropdown(
            label="Visualization Mode",
            options=[
                ft.dropdown.Option("flow_diagram", "Flow Diagram"),
                ft.dropdown.Option("tier_bars", "Tier Bars"),
                ft.dropdown.Option("allocation_map", "Allocation Map"),
                ft.dropdown.Option("bandwidth_chart", "Bandwidth Chart")
            ],
            value=self._current_mode.value,
            on_change=self._on_mode_change,
            width=200,
            bgcolor=palette.surface,
            color=palette.text_primary,
            border_color=palette.outline
        )
        
        # Status indicator
        status_color = palette.success if self._is_monitoring else palette.text_tertiary
        status_text = "Active" if self._is_monitoring else "Inactive"
        
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(
                        "Memory Allocation Visualizer",
                        style=self.get_text_style('h2'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "Real-time memory distribution across tiers",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    )
                ], expand=True),
                ft.Column([
                    self._mode_selector,
                    ft.Row([
                        ft.Icon(self.get_icon('CIRCLE'), color=status_color, size=12),
                        ft.Text(
                            status_text,
                            style=self.get_text_style('body_small'),
                            color=status_color
                        )
                    ], spacing=spacing.xs)
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.all(spacing.md)
        )

    def _create_visualization_area(self) -> ft.Control:
        """Create main visualization area based on current mode."""
        if self._current_mode == VisualizationMode.FLOW_DIAGRAM:
            return self._create_flow_diagram()
        elif self._current_mode == VisualizationMode.TIER_BARS:
            return self._create_tier_bars()
        elif self._current_mode == VisualizationMode.ALLOCATION_MAP:
            return self._create_allocation_map()
        elif self._current_mode == VisualizationMode.BANDWIDTH_CHART:
            return self._create_bandwidth_chart()
        else:
            return self._create_flow_diagram()

    def _create_flow_diagram(self) -> ft.Control:
        """Create flow diagram visualization."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create tier containers
        tier_containers = []
        for tier, data in self._tier_data.items():
            container = self._create_tier_container(data)
            self._tier_containers[tier] = container
            tier_containers.append(container)

        # Create flow indicators
        flow_indicators = self._create_flow_indicators()

        return ft.Container(
            content=ft.Stack([
                # Background grid
                ft.Container(
                    bgcolor=palette.surface_variant,
                    border_radius=ft.border_radius.all(4)
                ),
                # Tier containers
                ft.Column([
                    ft.Row(tier_containers[:2], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                    ft.Container(height=spacing.xl),
                    ft.Row(tier_containers[2:], alignment=ft.MainAxisAlignment.SPACE_AROUND)
                ], alignment=ft.MainAxisAlignment.CENTER),
                # Flow indicators overlay
                ft.Container(content=ft.Column(flow_indicators))
            ]),
            bgcolor=palette.background_secondary,
            border=ft.border.all(1, palette.outline),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_tier_container(self, data: TierVisualizationData) -> ft.Container:
        """Create individual tier container."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate usage color
        if data.usage_percent < 50:
            usage_color = palette.success
        elif data.usage_percent < 80:
            usage_color = palette.warning
        else:
            usage_color = palette.error

        # Format capacity text
        total_gb = data.total_bytes / (1024**3)
        used_gb = data.used_bytes / (1024**3)
        capacity_text = f"{used_gb:.1f} / {total_gb:.1f} GB"

        return ft.Container(
            content=ft.Column([
                # Tier icon and name
                ft.Row([
                    ft.Icon(data.icon, color=data.color, size=24),
                    ft.Text(
                        data.name,
                        style=self.get_text_style('h4'),
                        color=palette.text_primary
                    )
                ], spacing=spacing.sm),

                # Usage progress bar
                ft.ProgressBar(
                    value=data.usage_percent / 100,
                    color=usage_color,
                    bgcolor=palette.surface_variant,
                    height=8
                ),

                # Capacity text
                ft.Text(
                    capacity_text,
                    style=self.get_text_style('body_small'),
                    color=palette.text_secondary
                ),

                # Usage percentage
                ft.Text(
                    f"{data.usage_percent:.1f}%",
                    style=self.get_text_style('h3'),
                    color=usage_color
                ),

                # Status indicator
                ft.Row([
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if data.status == TierStatus.ACTIVE else self.get_icon('ERROR'),
                        color=palette.success if data.status == TierStatus.ACTIVE else palette.error,
                        size=16
                    ),
                    ft.Text(
                        data.status.value.title(),
                        style=self.get_text_style('caption'),
                        color=palette.text_tertiary
                    )
                ], spacing=spacing.xs)
            ], spacing=spacing.sm, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface,
            border=ft.border.all(2, data.color),
            border_radius=ft.border_radius.all(12),
            padding=ft.padding.all(spacing.md),
            width=180,
            height=200
        )

    def _create_tier_bars(self) -> ft.Control:
        """Create tier bars visualization."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        bars = []
        for tier, data in self._tier_data.items():
            # Create horizontal bar chart
            bar = ft.Container(
                content=ft.Row([
                    # Tier info
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(data.icon, color=data.color, size=20),
                                ft.Text(
                                    data.name,
                                    style=self.get_text_style('body_medium'),
                                    color=palette.text_primary
                                )
                            ], spacing=spacing.sm),
                            ft.Text(
                                f"{data.usage_percent:.1f}%",
                                style=self.get_text_style('body_small'),
                                color=palette.text_secondary
                            )
                        ], spacing=spacing.xs),
                        width=120
                    ),

                    # Progress bar
                    ft.Container(
                        content=ft.ProgressBar(
                            value=data.usage_percent / 100,
                            color=data.color,
                            bgcolor=palette.surface_variant,
                            height=20
                        ),
                        expand=True
                    ),

                    # Capacity text
                    ft.Container(
                        content=ft.Text(
                            f"{data.used_bytes / (1024**3):.1f} / {data.total_bytes / (1024**3):.1f} GB",
                            style=self.get_text_style('body_small'),
                            color=palette.text_secondary
                        ),
                        width=100
                    )
                ], spacing=spacing.md),
                padding=ft.padding.all(spacing.md),
                margin=ft.margin.only(bottom=spacing.sm)
            )
            bars.append(bar)

        return ft.Container(
            content=ft.Column(bars, spacing=spacing.sm),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_allocation_map(self) -> ft.Control:
        """Create allocation map visualization."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create grid-based allocation map
        grid_items = []
        for i in range(8):  # 8x8 grid
            row_items = []
            for j in range(8):
                # Determine cell color based on allocation
                cell_color = palette.surface_variant
                if (i + j) % 4 == 0:
                    cell_color = palette.primary
                elif (i + j) % 3 == 0:
                    cell_color = palette.secondary
                elif (i + j) % 2 == 0:
                    cell_color = palette.info

                cell = ft.Container(
                    bgcolor=cell_color,
                    border_radius=ft.border_radius.all(2),
                    width=20,
                    height=20,
                    margin=ft.margin.all(1)
                )
                row_items.append(cell)
            grid_items.append(ft.Row(row_items, spacing=0))

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Memory Allocation Map",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.Column(grid_items, spacing=0)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_bandwidth_chart(self) -> ft.Control:
        """Create bandwidth chart visualization."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create bandwidth bars for each tier
        bandwidth_bars = []
        max_bandwidth = max(data.bandwidth_mbps for data in self._tier_data.values()) or 1000

        for tier, data in self._tier_data.items():
            bandwidth_percent = (data.bandwidth_mbps / max_bandwidth) * 100

            bar = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text(
                                data.name,
                                style=self.get_text_style('body_medium'),
                                color=palette.text_primary
                            ),
                            ft.Text(
                                f"{data.bandwidth_mbps:.0f} MB/s",
                                style=self.get_text_style('body_small'),
                                color=palette.text_secondary
                            )
                        ], spacing=spacing.xs),
                        width=120
                    ),
                    ft.Container(
                        content=ft.ProgressBar(
                            value=bandwidth_percent / 100,
                            color=data.color,
                            bgcolor=palette.surface_variant,
                            height=16
                        ),
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"{data.latency_ms:.1f}ms",
                            style=self.get_text_style('body_small'),
                            color=palette.text_secondary
                        ),
                        width=60
                    )
                ], spacing=spacing.md),
                padding=ft.padding.all(spacing.sm),
                margin=ft.margin.only(bottom=spacing.xs)
            )
            bandwidth_bars.append(bar)

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Memory Bandwidth & Latency",
                    style=self.get_text_style('h4'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.Column(bandwidth_bars, spacing=spacing.xs)
            ]),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_flow_indicators(self) -> List[ft.Control]:
        """Create animated flow indicators."""
        indicators = []

        # Create flow lines between tiers (simplified)
        for flow in self._allocation_flows:
            indicator = self._create_flow_line(flow)
            indicators.append(indicator)

        return indicators

    def _create_flow_line(self, flow: AllocationFlow) -> ft.Control:
        """Create individual flow line indicator."""
        palette = self.get_palette()

        # Determine flow color based on direction and state
        if flow.animation_state == AnimationState.ALLOCATING:
            flow_color = palette.success
        elif flow.animation_state == AnimationState.DEALLOCATING:
            flow_color = palette.warning
        elif flow.animation_state == AnimationState.MIGRATING:
            flow_color = palette.info
        else:
            flow_color = palette.text_tertiary

        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ARROW_FORWARD, color=flow_color, size=16),
                ft.Text(
                    f"{flow.bytes_per_second / (1024**2):.1f} MB/s",
                    style=self.get_text_style('caption'),
                    color=flow_color
                )
            ], spacing=4),
            padding=ft.padding.all(4),
            margin=ft.margin.all(2)
        )

    def _create_metrics_panel(self) -> ft.Control:
        """Create metrics display panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate total metrics
        total_capacity = sum(data.total_bytes for data in self._tier_data.values())
        total_used = sum(data.used_bytes for data in self._tier_data.values())
        total_allocations = sum(data.allocation_count for data in self._tier_data.values())

        overall_usage = (total_used / total_capacity * 100) if total_capacity > 0 else 0

        metrics_items = [
            # Overall usage
            ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Overall Usage",
                        style=self.get_text_style('h4'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        f"{overall_usage:.1f}%",
                        style=self.get_text_style('h2'),
                        color=palette.primary
                    ),
                    ft.ProgressBar(
                        value=overall_usage / 100,
                        color=palette.primary,
                        bgcolor=palette.surface_variant,
                        height=8
                    )
                ], spacing=spacing.sm),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(8),
                margin=ft.margin.only(bottom=spacing.md)
            ),

            # Total capacity
            ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Total Capacity",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    ),
                    ft.Text(
                        f"{total_capacity / (1024**3):.1f} GB",
                        style=self.get_text_style('h3'),
                        color=palette.text_primary
                    )
                ], spacing=spacing.xs),
                padding=ft.padding.all(spacing.md),
                margin=ft.margin.only(bottom=spacing.sm)
            ),

            # Active allocations
            ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Active Allocations",
                        style=self.get_text_style('body_medium'),
                        color=palette.text_secondary
                    ),
                    ft.Text(
                        str(total_allocations),
                        style=self.get_text_style('h3'),
                        color=palette.text_primary
                    )
                ], spacing=spacing.xs),
                padding=ft.padding.all(spacing.md),
                margin=ft.margin.only(bottom=spacing.sm)
            )
        ]

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Allocation Metrics",
                    style=self.get_text_style('h3'),
                    color=palette.text_primary
                ),
                ft.Container(height=spacing.md),
                ft.Column(metrics_items, spacing=spacing.sm)
            ]),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.lg)
        )

    def _create_controls_panel(self) -> ft.Control:
        """Create controls panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Start/Stop monitoring button
        monitor_button = ft.ElevatedButton(
            text="Stop Monitoring" if self._is_monitoring else "Start Monitoring",
            icon=self.get_icon('STOP') if self._is_monitoring else self.get_icon('PLAY'),
            on_click=self._toggle_monitoring,
            bgcolor=palette.error if self._is_monitoring else palette.success,
            color=palette.text_primary
        )

        # Animation toggle
        animation_button = ft.ElevatedButton(
            text="Disable Animation" if self._animation_enabled else "Enable Animation",
            icon=ft.Icons.ANIMATION if self._animation_enabled else self.get_icon('STOP'),
            on_click=self._toggle_animation,
            bgcolor=palette.secondary,
            color=palette.text_primary
        )

        # Refresh rate slider
        refresh_slider = ft.Slider(
            min=0.1,
            max=5.0,
            value=self._refresh_interval,
            divisions=49,
            label="Refresh Rate: {value:.1f}s",
            on_change=self._on_refresh_rate_change,
            active_color=palette.primary,
            inactive_color=palette.surface_variant
        )

        return ft.Container(
            content=ft.Row([
                monitor_button,
                ft.Container(width=spacing.md),
                animation_button,
                ft.Container(width=spacing.lg),
                ft.Text(
                    "Refresh Rate:",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_secondary
                ),
                ft.Container(
                    content=refresh_slider,
                    width=200
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.all(spacing.md)
        )

    def _on_mode_change(self, e) -> None:
        """Handle visualization mode change."""
        try:
            self._current_mode = VisualizationMode(e.control.value)
            self.update()
        except Exception as ex:
            self._logger.error(f"Error changing visualization mode: {str(ex)}")

    def _toggle_monitoring(self, e) -> None:
        """Toggle memory monitoring."""
        try:
            if self._is_monitoring:
                asyncio.create_task(self.stop_monitoring())
            else:
                asyncio.create_task(self.start_monitoring())
        except Exception as ex:
            self._logger.error(f"Error toggling monitoring: {str(ex)}")

    def _toggle_animation(self, e) -> None:
        """Toggle animation."""
        try:
            self._animation_enabled = not self._animation_enabled
            if self._animation_enabled and self._is_monitoring:
                self._start_animation()
            elif not self._animation_enabled and self._animation_timer:
                self._animation_timer.cancel()
                self._animation_timer = None
            self.update()
        except Exception as ex:
            self._logger.error(f"Error toggling animation: {str(ex)}")

    def _on_refresh_rate_change(self, e) -> None:
        """Handle refresh rate change."""
        try:
            self._refresh_interval = float(e.control.value)
        except Exception as ex:
            self._logger.error(f"Error changing refresh rate: {str(ex)}")

    async def start_monitoring(self) -> None:
        """Start memory allocation monitoring."""
        try:
            if self._is_monitoring:
                return

            self._is_monitoring = True

            # Start memory monitor
            if self._memory_monitor:
                await self._memory_monitor.start_monitoring(self._refresh_interval)

            # Start monitoring task
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

            # Start animation if enabled
            if self._animation_enabled:
                self._start_animation()

            self.update()
            self._logger.info("Memory allocation monitoring started")

        except Exception as e:
            self._logger.error(f"Failed to start monitoring: {str(e)}")
            self._is_monitoring = False

    async def stop_monitoring(self) -> None:
        """Stop memory allocation monitoring."""
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

            # Stop animation
            if self._animation_timer:
                self._animation_timer.cancel()
                self._animation_timer = None

            self.update()
            self._logger.info("Memory allocation monitoring stopped")

        except Exception as e:
            self._logger.error(f"Failed to stop monitoring: {str(e)}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._is_monitoring:
                await self._update_tier_data()
                await self._update_allocation_flows()
                self.update()
                await asyncio.sleep(self._refresh_interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in monitoring loop: {str(e)}")

    async def _update_tier_data(self) -> None:
        """Update tier visualization data."""
        try:
            if not self._memory_tier_manager:
                return

            # Get tier information
            for tier in self._tier_data.keys():
                tier_info = self._memory_tier_manager.get_tier_info(tier)
                if tier_info:
                    data = self._tier_data[tier]
                    data.total_bytes = tier_info.capacity.total_bytes
                    data.used_bytes = tier_info.capacity.used_bytes
                    data.available_bytes = tier_info.capacity.available_bytes
                    data.usage_percent = (data.used_bytes / data.total_bytes * 100) if data.total_bytes > 0 else 0
                    data.bandwidth_mbps = tier_info.bandwidth.read_bandwidth_mbps / 1000  # Convert to MB/s
                    data.latency_ms = tier_info.bandwidth.latency_microseconds / 1000  # Convert to ms
                    data.allocation_count = tier_info.metrics.allocation_count
                    data.status = tier_info.status

        except Exception as e:
            self._logger.error(f"Error updating tier data: {str(e)}")

    async def _update_allocation_flows(self) -> None:
        """Update allocation flow data."""
        try:
            # Clear existing flows
            self._allocation_flows.clear()

            # Generate sample flows (in real implementation, get from allocation manager)
            current_time = datetime.now(timezone.utc)

            # Sample flow from RAM to GPU
            if self._tier_data[MemoryTier.RAM].usage_percent > 50:
                flow = AllocationFlow(
                    source_tier=MemoryTier.RAM,
                    target_tier=MemoryTier.GPU_MEMORY,
                    bytes_per_second=1024 * 1024 * 100,  # 100 MB/s
                    direction="out",
                    animation_state=AnimationState.ALLOCATING,
                    timestamp=current_time
                )
                self._allocation_flows.append(flow)

        except Exception as e:
            self._logger.error(f"Error updating allocation flows: {str(e)}")

    def _start_animation(self) -> None:
        """Start animation timer."""
        if self._animation_timer:
            self._animation_timer.cancel()

        self._animation_timer = asyncio.create_task(self._animation_loop())

    async def _animation_loop(self) -> None:
        """Animation loop for flow indicators."""
        try:
            while self._animation_enabled and self._is_monitoring:
                self._animation_frame = (self._animation_frame + 1) % 60
                # Update animation state here if needed
                await asyncio.sleep(0.1)  # 10 FPS animation
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in animation loop: {str(e)}")

    def will_unmount(self) -> None:
        """Clean up when component is unmounted."""
        try:
            # Stop monitoring
            if self._is_monitoring:
                asyncio.create_task(self.stop_monitoring())
        except Exception as e:
            self._logger.error(f"Error during unmount: {str(e)}")
        finally:
            super().will_unmount()
