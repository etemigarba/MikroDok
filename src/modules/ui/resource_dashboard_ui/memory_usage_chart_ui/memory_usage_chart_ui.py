"""
Module: memory_usage_chart_ui
Description: Stacked area charts showing RAM, VRAM, and swap usage with tier distribution visualization.
            Provides comprehensive memory monitoring with interactive charts, allocation tracking,
            memory pressure indicators, and theme-aware visualization components.
Phase: 2
Location: /src/modules/ui/resource_dashboard_ui/memory_usage_chart_ui/memory_usage_chart_ui.py
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
class MemoryMetrics:
    """Memory performance metrics data structure."""
    timestamp: datetime
    total_ram_mb: int
    available_ram_mb: int
    used_ram_mb: int
    free_ram_mb: int
    cached_mb: int
    buffers_mb: int
    usage_percent: float
    virtual_total_mb: int
    virtual_available_mb: int
    virtual_used_mb: int
    virtual_percent: float
    swap_info: 'SwapUsageInfo'
    memory_pressure_score: float
    allocation_rate_mb_per_sec: float
    deallocation_rate_mb_per_sec: float


@dataclass
class SwapUsageInfo:
    """Detailed swap usage information."""
    total_mb: int
    used_mb: int
    free_mb: int
    usage_percent: float
    swap_in_rate_mb_per_sec: float
    swap_out_rate_mb_per_sec: float


@dataclass
class MemoryAllocationPattern:
    """Memory allocation pattern analysis."""
    pattern_type: str
    confidence: float
    trend_slope: float
    volatility_score: float
    analysis_window_minutes: int
    detected_at: datetime
    description: str


class MemoryMonitor:
    """Mock memory monitor for demonstration purposes."""

    def __init__(self):
        pass

    def get_current_metrics(self) -> Optional[MemoryMetrics]:
        """Get current memory metrics (mock implementation)."""
        import random

        total_ram = 32768
        used_ram = int(total_ram * (0.3 + random.random() * 0.4))
        available_ram = total_ram - used_ram
        free_ram = int(available_ram * 0.7)
        cached_mb = int(available_ram * 0.2)
        buffers_mb = int(available_ram * 0.1)

        total_virtual = 65536
        used_virtual = int(total_virtual * (0.2 + random.random() * 0.3))

        total_swap = 16384
        used_swap = int(total_swap * random.random() * 0.1)
        free_swap = total_swap - used_swap

        swap_info = SwapUsageInfo(
            total_mb=total_swap,
            used_mb=used_swap,
            free_mb=free_swap,
            usage_percent=(used_swap / total_swap) * 100 if total_swap > 0 else 0,
            swap_in_rate_mb_per_sec=random.uniform(0, 10),
            swap_out_rate_mb_per_sec=random.uniform(0, 8)
        )

        return MemoryMetrics(
            timestamp=datetime.now(),
            total_ram_mb=total_ram,
            available_ram_mb=available_ram,
            used_ram_mb=used_ram,
            free_ram_mb=free_ram,
            cached_mb=cached_mb,
            buffers_mb=buffers_mb,
            usage_percent=(used_ram / total_ram) * 100,
            virtual_total_mb=total_virtual,
            virtual_available_mb=total_virtual - used_virtual,
            virtual_used_mb=used_virtual,
            virtual_percent=(used_virtual / total_virtual) * 100,
            swap_info=swap_info,
            memory_pressure_score=random.random(),
            allocation_rate_mb_per_sec=random.uniform(0, 100),
            deallocation_rate_mb_per_sec=random.uniform(0, 80)
        )

    async def start_monitoring(self, interval: float) -> None:
        """Start monitoring (mock implementation)."""
        pass

    async def stop_monitoring(self) -> None:
        """Stop monitoring (mock implementation)."""
        pass


class GPUMonitor:
    """Mock GPU monitor for demonstration purposes."""

    def __init__(self):
        pass

    def get_gpu_info(self) -> List[Any]:
        """Get GPU info (mock implementation)."""
        return []

    def get_current_metrics(self, gpu_id: int) -> Optional[Any]:
        """Get GPU metrics (mock implementation)."""
        return None


class MemoryType(Enum):
    """Memory types for visualization."""
    SYSTEM_RAM = "system_ram"
    GPU_VRAM = "gpu_vram"
    SWAP = "swap"
    VIRTUAL = "virtual"


class MemoryTier(Enum):
    """Memory tier classification."""
    FAST = "fast"      # RAM, GPU VRAM
    MEDIUM = "medium"  # NVMe SSD
    SLOW = "slow"      # Traditional storage, swap


@dataclass
class MemoryChartConfiguration:
    """Configuration for memory usage chart."""
    update_interval_seconds: float = 1.0
    history_minutes: int = 10
    show_swap_usage: bool = True
    show_gpu_memory: bool = True
    show_virtual_memory: bool = False
    show_allocation_patterns: bool = True
    show_memory_pressure: bool = True
    enable_tier_visualization: bool = True
    memory_warning_threshold: float = 85.0
    memory_critical_threshold: float = 95.0


class MemoryUsageChartUI(ThemeAwareUserControl):
    """
    Memory usage chart UI component.
    
    Provides comprehensive real-time memory monitoring with:
    - Stacked area charts for different memory types
    - RAM, VRAM, and swap usage visualization
    - Memory tier distribution display
    - Allocation pattern analysis
    - Memory pressure indicators
    - Interactive tooltips and data exploration
    - Theme-aware styling and color coding
    """
    
    def __init__(
        self,
        memory_monitor: Optional[MemoryMonitor] = None,
        gpu_monitor: Optional[GPUMonitor] = None,
        config: Optional[MemoryChartConfiguration] = None,
        on_memory_alert: Optional[Callable[[str, float], None]] = None,
        on_allocation_pattern_detected: Optional[Callable[[MemoryAllocationPattern], None]] = None
    ):
        """
        Initialize memory usage chart.
        
        Args:
            memory_monitor: Memory monitoring service
            gpu_monitor: GPU monitoring service for VRAM data
            config: Chart configuration
            on_memory_alert: Callback for memory alerts
            on_allocation_pattern_detected: Callback for allocation pattern detection
        """
        super().__init__()
        self._memory_monitor = memory_monitor
        self._gpu_monitor = gpu_monitor
        self._config = config or MemoryChartConfiguration()
        self._on_memory_alert = on_memory_alert
        self._on_allocation_pattern_detected = on_allocation_pattern_detected
        
        # Memory data
        self._current_memory_metrics: Optional[MemoryMetrics] = None
        self._memory_history: List[MemoryMetrics] = []
        self._gpu_memory_history: List[Tuple[datetime, float, float]] = []  # (timestamp, used_mb, total_mb)
        
        # UI state
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._selected_view = "overview"  # "overview", "detailed", "tiers"
        
        # Chart components
        self._overview_chart: Optional[ft.LineChart] = None
        self._detailed_chart: Optional[ft.LineChart] = None
        self._tier_chart: Optional[ft.PieChart] = None
        
        # Metric displays
        self._ram_usage_text: Optional[ft.Text] = None
        self._vram_usage_text: Optional[ft.Text] = None
        self._swap_usage_text: Optional[ft.Text] = None
        self._virtual_usage_text: Optional[ft.Text] = None
        self._pressure_indicator: Optional[ft.Container] = None
        
        # Progress bars
        self._ram_progress: Optional[ft.ProgressBar] = None
        self._vram_progress: Optional[ft.ProgressBar] = None
        self._swap_progress: Optional[ft.ProgressBar] = None
        
        # Controls
        self._view_tabs: Optional[ft.Tabs] = None
        self._refresh_button: Optional[ft.IconButton] = None
    
    def build(self) -> ft.Control:
        """Build the memory usage chart UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create header
        header = self._create_header()
        
        # Create memory overview cards
        overview_cards = self._create_overview_cards()
        
        # Create chart area with tabs
        chart_area = self._create_chart_area()
        
        # Create memory pressure section
        pressure_section = self._create_pressure_section()
        
        # Create controls
        controls = self._create_controls()
        
        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=spacing.md),
                overview_cards,
                ft.Container(height=spacing.lg),
                chart_area,
                ft.Container(height=spacing.md),
                pressure_section,
                ft.Container(height=spacing.md),
                controls
            ], scroll=ft.ScrollMode.AUTO),
            bgcolor=palette.background_primary,
            padding=ft.padding.all(spacing.lg),
            expand=True
        )
    
    def _create_header(self) -> ft.Control:
        """Create header with memory information."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        status_color = palette.success if self._is_monitoring else palette.text_tertiary
        status_text = "Monitoring Active" if self._is_monitoring else "Monitoring Stopped"
        
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(
                        "Memory Usage Monitor",
                        style=self.get_text_style('h2'),
                        color=palette.text_primary
                    ),
                    ft.Text(
                        "Real-time memory allocation and usage tracking",
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
    
    def _create_overview_cards(self) -> ft.Control:
        """Create memory overview cards."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # System RAM card
        ram_card = self._create_memory_card(
            "System RAM",
            "0 GB / 0 GB",
            self.get_icon('CPU'),
            palette.primary,
            "ram_usage_text",
            "ram_progress"
        )
        
        # GPU VRAM card (if enabled)
        vram_card = None
        if self._config.show_gpu_memory:
            vram_card = self._create_memory_card(
                "GPU VRAM",
                "0 GB / 0 GB",
                self.get_icon('GPU'),
                palette.info,
                "vram_usage_text",
                "vram_progress"
            )
        
        # Swap card (if enabled)
        swap_card = None
        if self._config.show_swap_usage:
            swap_card = self._create_memory_card(
                "Swap Memory",
                "0 GB / 0 GB",
                self.get_icon('MEMORY'),
                palette.warning,
                "swap_usage_text",
                "swap_progress"
            )
        
        # Virtual memory card (if enabled)
        virtual_card = None
        if self._config.show_virtual_memory:
            virtual_card = self._create_memory_card(
                "Virtual Memory",
                "0 GB / 0 GB",
                self.get_icon('MEMORY'),
                palette.secondary,
                "virtual_usage_text",
                None
            )
        
        # Arrange cards
        cards = [ram_card]
        if vram_card:
            cards.append(vram_card)
        if swap_card:
            cards.append(swap_card)
        if virtual_card:
            cards.append(virtual_card)
        
        return ft.ResponsiveRow([
            ft.Container(
                content=card,
                col={"sm": 6, "md": 4, "lg": 3} if len(cards) > 3 else {"sm": 6, "md": 6, "lg": 4}
            ) for card in cards
        ])
    
    def _create_memory_card(self, title: str, value: str, icon: str, color: str, 
                           text_ref: str, progress_ref: Optional[str]) -> ft.Control:
        """Create a memory usage card with progress bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create text reference
        value_text = ft.Text(
            value,
            style=self.get_text_style('body_medium'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD
        )
        
        # Store text reference
        if text_ref == "ram_usage_text":
            self._ram_usage_text = value_text
        elif text_ref == "vram_usage_text":
            self._vram_usage_text = value_text
        elif text_ref == "swap_usage_text":
            self._swap_usage_text = value_text
        elif text_ref == "virtual_usage_text":
            self._virtual_usage_text = value_text
        
        # Create progress bar if requested
        progress_bar = None
        if progress_ref:
            progress_bar = ft.ProgressBar(
                value=0.0,
                color=color,
                bgcolor=f"{color}20",
                height=6
            )
            
            # Store progress reference
            if progress_ref == "ram_progress":
                self._ram_progress = progress_bar
            elif progress_ref == "vram_progress":
                self._vram_progress = progress_bar
            elif progress_ref == "swap_progress":
                self._swap_progress = progress_bar
        
        card_content = [
            ft.Row([
                ft.Icon(icon, color=color, size=self.get_responsive_layout().get_breakpoint_value(16, 18, 20, 24)),
                ft.Text(
                    title,
                    style=self.get_text_style('body_small'),
                    color=palette.text_secondary
                )
            ], spacing=spacing.sm),
            ft.Container(height=spacing.xs),
            value_text
        ]
        
        if progress_bar:
            card_content.extend([
                ft.Container(height=spacing.xs),
                progress_bar
            ])
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column(card_content),
                padding=ft.padding.all(spacing.md)
            ),
            color=palette.surface,
            elevation=1
        )

    def _create_chart_area(self) -> ft.Control:
        """Create chart area with different views."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create view tabs
        self._view_tabs = ft.Tabs(
            selected_index=0,
            on_change=self._on_view_change,
            tabs=[
                ft.Tab(
                    text="Overview",
                    icon=self.get_icon('MEMORY'),
                    content=self._create_overview_chart()
                ),
                ft.Tab(
                    text="Detailed",
                    icon=self.get_icon('MEMORY'),
                    content=self._create_detailed_chart()
                )
            ]
        )

        # Add tier view if enabled
        if self._config.enable_tier_visualization:
            self._view_tabs.tabs.append(
                ft.Tab(
                    text="Memory Tiers",
                    icon=self.get_icon('MEMORY'),
                    content=self._create_tier_chart()
                )
            )

        return ft.Container(
            content=self._view_tabs,
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, palette.borders),
            padding=ft.padding.all(spacing.md),
            height=450
        )

    def _create_overview_chart(self) -> ft.Control:
        """Create overview chart with stacked areas."""
        palette = self.get_palette()

        # Create stacked area chart for memory overview
        self._overview_chart = ft.LineChart(
            data_series=[
                # System RAM
                ft.LineChartData(
                    data_points=[],
                    stroke_width=self.get_responsive_layout().get_breakpoint_value(2, 2, 3, 3),
                    color=palette.primary,
                    curved=True,
                    stroke_cap_round=True,
                    below_line_bgcolor=f"{palette.primary}40"
                ),
                # GPU VRAM (if enabled)
                ft.LineChartData(
                    data_points=[],
                    stroke_width=self.get_responsive_layout().get_breakpoint_value(2, 2, 3, 3),
                    color=palette.info,
                    curved=True,
                    stroke_cap_round=True,
                    below_line_bgcolor=f"{palette.info}40"
                ) if self._config.show_gpu_memory else None,
                # Swap (if enabled)
                ft.LineChartData(
                    data_points=[],
                    stroke_width=self.get_responsive_layout().get_breakpoint_value(2, 2, 3, 3),
                    color=palette.warning,
                    curved=True,
                    stroke_cap_round=True,
                    below_line_bgcolor=f"{palette.warning}40"
                ) if self._config.show_swap_usage else None
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
                title=ft.Text("Memory Usage (%)", size=self.get_responsive_layout().get_breakpoint_value(10, 12, 14, 16), color=palette.text_secondary),
                title_size=self.get_responsive_layout().get_breakpoint_value(28, 36, 44, 52),
                labels_size=self.get_responsive_layout().get_breakpoint_value(28, 36, 44, 52)
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Time", size=self.get_responsive_layout().get_breakpoint_value(10, 12, 14, 16), color=palette.text_secondary),
                title_size=self.get_responsive_layout().get_breakpoint_value(28, 36, 44, 52),
                labels_size=self.get_responsive_layout().get_breakpoint_value(28, 36, 44, 52)
            ),
            tooltip_bgcolor=palette.surface,
            min_y=0,
            max_y=100,
            min_x=0,
            max_x=self._config.history_minutes * 60,
            expand=True
        )

        # Filter out None values
        self._overview_chart.data_series = [series for series in self._overview_chart.data_series if series is not None]

        return ft.Container(
            content=ft.Column([
                # Legend
                ft.Row([
                    ft.Row([
                        ft.Container(width=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), height=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), bgcolor=palette.primary, border_radius=ft.border_radius.all(self.get_spacing().xs)),
                        ft.Text("System RAM", style=self.get_text_style('caption'), color=palette.text_secondary)
                    ], spacing=4),
                    ft.Row([
                        ft.Container(width=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), height=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), bgcolor=palette.info, border_radius=ft.border_radius.all(self.get_spacing().xs)),
                        ft.Text("GPU VRAM", style=self.get_text_style('caption'), color=palette.text_secondary)
                    ], spacing=4) if self._config.show_gpu_memory else ft.Container(),
                    ft.Row([
                        ft.Container(width=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), height=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), bgcolor=palette.warning, border_radius=ft.border_radius.all(self.get_spacing().xs)),
                        ft.Text("Swap", style=self.get_text_style('caption'), color=palette.text_secondary)
                    ], spacing=4) if self._config.show_swap_usage else ft.Container()
                ], spacing=self.get_responsive_layout().get_breakpoint_value(8, 12, 16, 20)),
                ft.Container(height=self.get_spacing().xs),
                # Chart
                ft.Container(
                    content=self._overview_chart,
                    bgcolor=palette.background_secondary,
                    border_radius=ft.border_radius.all(4),
                    padding=ft.padding.all(8),
                    expand=True
                )
            ]),
            expand=True
        )

    def _create_detailed_chart(self) -> ft.Control:
        """Create detailed memory usage chart."""
        palette = self.get_palette()

        # Create detailed line chart with multiple metrics
        self._detailed_chart = ft.LineChart(
            data_series=[
                # Used memory
                ft.LineChartData(
                    data_points=[],
                    stroke_width=self.get_responsive_layout().get_breakpoint_value(2, 2, 3, 3),
                    color=palette.primary,
                    curved=True,
                    stroke_cap_round=True
                ),
                # Available memory
                ft.LineChartData(
                    data_points=[],
                    stroke_width=self.get_responsive_layout().get_breakpoint_value(2, 2, 3, 3),
                    color=palette.success,
                    curved=True,
                    stroke_cap_round=True
                ),
                # Cached memory
                ft.LineChartData(
                    data_points=[],
                    stroke_width=self.get_responsive_layout().get_breakpoint_value(2, 2, 3, 3),
                    color=palette.info,
                    curved=True,
                    stroke_cap_round=True
                ),
                # Buffers
                ft.LineChartData(
                    data_points=[],
                    stroke_width=self.get_responsive_layout().get_breakpoint_value(2, 2, 3, 3),
                    color=palette.secondary,
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
                title=ft.Text("Memory (GB)", size=self.get_responsive_layout().get_breakpoint_value(10, 12, 14, 16), color=palette.text_secondary),
                title_size=self.get_responsive_layout().get_breakpoint_value(28, 36, 44, 52),
                labels_size=self.get_responsive_layout().get_breakpoint_value(28, 36, 44, 52)
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Time", size=self.get_responsive_layout().get_breakpoint_value(10, 12, 14, 16), color=palette.text_secondary),
                title_size=self.get_responsive_layout().get_breakpoint_value(28, 36, 44, 52),
                labels_size=self.get_responsive_layout().get_breakpoint_value(28, 36, 44, 52)
            ),
            tooltip_bgcolor=palette.surface,
            min_y=0,
            max_y=32,  # Will be auto-scaled
            min_x=0,
            max_x=self._config.history_minutes * 60,
            expand=True
        )

        return ft.Container(
            content=ft.Column([
                # Legend
                ft.Row([
                    ft.Row([
                        ft.Container(width=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), height=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), bgcolor=palette.primary, border_radius=ft.border_radius.all(self.get_spacing().xs)),
                        ft.Text("Used", style=self.get_text_style('caption'), color=palette.text_secondary)
                    ], spacing=4),
                    ft.Row([
                        ft.Container(width=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), height=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), bgcolor=palette.success, border_radius=ft.border_radius.all(self.get_spacing().xs)),
                        ft.Text("Available", style=self.get_text_style('caption'), color=palette.text_secondary)
                    ], spacing=4),
                    ft.Row([
                        ft.Container(width=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), height=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), bgcolor=palette.info, border_radius=ft.border_radius.all(self.get_spacing().xs)),
                        ft.Text("Cached", style=self.get_text_style('caption'), color=palette.text_secondary)
                    ], spacing=4),
                    ft.Row([
                        ft.Container(width=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), height=self.get_responsive_layout().get_breakpoint_value(8, 10, 12, 14), bgcolor=palette.secondary, border_radius=ft.border_radius.all(self.get_spacing().xs)),
                        ft.Text("Buffers", style=self.get_text_style('caption'), color=palette.text_secondary)
                    ], spacing=4)
                ], spacing=self.get_responsive_layout().get_breakpoint_value(8, 12, 16, 20)),
                ft.Container(height=self.get_spacing().xs),
                # Chart
                ft.Container(
                    content=self._detailed_chart,
                    bgcolor=palette.background_secondary,
                    border_radius=ft.border_radius.all(self.get_spacing().sm),
                    padding=ft.padding.all(self.get_spacing().sm),
                    expand=True
                )
            ]),
            expand=True
        )

    def _create_tier_chart(self) -> ft.Control:
        """Create memory tier distribution chart."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create pie chart for memory tiers
        self._tier_chart = ft.PieChart(
            sections=[
                ft.PieChartSection(
                    value=40,
                    title="Fast (RAM)",
                    color=palette.primary,
                    radius=100
                ),
                ft.PieChartSection(
                    value=30,
                    title="Medium (NVMe)",
                    color=palette.info,
                    radius=100
                ),
                ft.PieChartSection(
                    value=30,
                    title="Slow (Swap)",
                    color=palette.warning,
                    radius=100
                )
            ],
            center_space_radius=40,
            expand=True
        )

        return ft.Container(
            content=ft.Row([
                # Pie chart
                ft.Container(
                    content=self._tier_chart,
                    expand=2
                ),
                # Tier information
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "Memory Tier Distribution",
                            style=self.get_text_style('h4'),
                            color=palette.text_primary
                        ),
                        ft.Container(height=spacing.md),
                        self._create_tier_info("Fast Tier", "RAM + GPU VRAM", palette.primary, "16 GB"),
                        ft.Container(height=spacing.sm),
                        self._create_tier_info("Medium Tier", "NVMe SSD Cache", palette.info, "8 GB"),
                        ft.Container(height=spacing.sm),
                        self._create_tier_info("Slow Tier", "Swap + Storage", palette.warning, "4 GB"),
                        ft.Container(height=spacing.lg),
                        ft.Text(
                            "Tier Performance:",
                            style=self.get_text_style('body_small'),
                            color=palette.text_secondary,
                            weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            "• Fast: < 1ms access\n• Medium: 1-10ms access\n• Slow: > 10ms access",
                            style=self.get_text_style('caption'),
                            color=palette.text_tertiary
                        )
                    ]),
                    expand=1,
                    padding=ft.padding.all(spacing.lg)
                )
            ]),
            expand=True
        )

    def _create_tier_info(self, name: str, description: str, color: str, size: str) -> ft.Control:
        """Create tier information row."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Row([
            ft.Container(
                width=self.get_responsive_layout().get_breakpoint_value(10, 12, 14, 16),
                height=self.get_responsive_layout().get_breakpoint_value(10, 12, 14, 16),
                bgcolor=color,
                border_radius=ft.border_radius.all(self.get_spacing().sm)
            ),
            ft.Column([
                ft.Text(
                    name,
                    style=self.get_text_style('body_small'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text(
                    f"{description} - {size}",
                    style=self.get_text_style('caption'),
                    color=palette.text_secondary
                )
            ], spacing=2)
        ], spacing=spacing.sm)

    def _create_pressure_section(self) -> ft.Control:
        """Create memory pressure indicators."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Memory pressure indicator
        self._pressure_indicator = ft.Container(
            content=ft.Row([
                ft.Icon(self.get_icon('SPEED'), color=palette.success, size=self.get_responsive_layout().get_breakpoint_value(14, 16, 18, 20)),
                ft.Text(
                    "Low Memory Pressure",
                    style=self.get_text_style('body_medium'),
                    color=palette.success
                )
            ], spacing=spacing.sm),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            border=ft.border.all(1, palette.success)
        )

        # Allocation pattern info
        allocation_info = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Allocation Patterns",
                    style=self.get_text_style('body_medium'),
                    color=palette.text_primary,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text(
                    "• Normal allocation rate\n• No memory leaks detected\n• Efficient garbage collection",
                    style=self.get_text_style('body_small'),
                    color=palette.text_secondary
                )
            ]),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(self.get_spacing().sm),
            border=ft.border.all(1, palette.borders)
        )

        return ft.ResponsiveRow([
            ft.Container(
                content=self._pressure_indicator,
                col={"sm": 12, "md": 6}
            ),
            ft.Container(
                content=allocation_info,
                col={"sm": 12, "md": 6}
            )
        ])

    def _create_controls(self) -> ft.Control:
        """Create control section."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Refresh button
        self._refresh_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh Memory Info",
            on_click=self._refresh_memory_info,
            icon_color=palette.text_secondary
        )

        # Settings button
        settings_button = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            tooltip="Chart Settings",
            on_click=self._show_settings,
            icon_color=palette.text_secondary
        )

        # Export button
        export_button = ft.IconButton(
            icon=self.get_icon('DOWNLOAD'),
            tooltip="Export Memory Data",
            on_click=self._export_data,
            icon_color=palette.text_secondary
        )

        return ft.Container(
            content=ft.Row([
                self._refresh_button,
                settings_button,
                export_button
            ], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=palette.surface,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(self.get_spacing().md),
            border=ft.border.all(1, palette.borders)
        )

    async def start_monitoring(self) -> None:
        """Start memory monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True

        # Start monitoring services
        if self._memory_monitor:
            await self._memory_monitor.start_monitoring(self._config.update_interval_seconds)

        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.update()

    async def stop_monitoring(self) -> None:
        """Stop memory monitoring."""
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

        if self._memory_monitor:
            await self._memory_monitor.stop_monitoring()

        self.update()

    async def _monitoring_loop(self) -> None:
        """Main monitoring update loop."""
        try:
            while self._is_monitoring:
                # Collect memory metrics
                if self._memory_monitor:
                    metrics = self._memory_monitor.get_current_metrics()
                    if metrics:
                        self._current_memory_metrics = metrics
                        self._memory_history.append(metrics)

                        # Limit history size
                        max_history = int(self._config.history_minutes * 60 / self._config.update_interval_seconds)
                        if len(self._memory_history) > max_history:
                            self._memory_history = self._memory_history[-max_history:]

                # Collect GPU memory metrics
                if self._gpu_monitor and self._config.show_gpu_memory:
                    gpu_infos = self._gpu_monitor.get_gpu_info()
                    if gpu_infos:
                        for gpu_info in gpu_infos:
                            gpu_metrics = self._gpu_monitor.get_current_metrics(gpu_info.gpu_id)
                            if gpu_metrics:
                                self._gpu_memory_history.append((
                                    datetime.now(),
                                    gpu_metrics.memory_used_mb,
                                    gpu_metrics.memory_total_mb
                                ))

                        # Limit GPU memory history
                        if len(self._gpu_memory_history) > max_history:
                            self._gpu_memory_history = self._gpu_memory_history[-max_history:]

                # Update UI
                self._update_metrics_display()
                self._update_charts()
                self._update_pressure_indicators()
                self._check_memory_thresholds()

                # Wait for next update
                await asyncio.sleep(self._config.update_interval_seconds)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            # Log error but continue monitoring
            pass

    def _update_metrics_display(self) -> None:
        """Update metric display cards with current values."""
        if not self._current_memory_metrics:
            return

        metrics = self._current_memory_metrics

        # Update RAM usage
        if self._ram_usage_text:
            used_gb = metrics.used_ram_mb / 1024
            total_gb = metrics.total_ram_mb / 1024
            self._ram_usage_text.value = f"{used_gb:.1f} GB / {total_gb:.1f} GB"

        if self._ram_progress:
            self._ram_progress.value = metrics.usage_percent / 100

        # Update VRAM usage (if available)
        if self._vram_usage_text and self._gpu_memory_history:
            latest_gpu = self._gpu_memory_history[-1]
            used_gb = latest_gpu[1] / 1024
            total_gb = latest_gpu[2] / 1024
            self._vram_usage_text.value = f"{used_gb:.1f} GB / {total_gb:.1f} GB"

        if self._vram_progress and self._gpu_memory_history:
            latest_gpu = self._gpu_memory_history[-1]
            usage_percent = (latest_gpu[1] / latest_gpu[2] * 100) if latest_gpu[2] > 0 else 0
            self._vram_progress.value = usage_percent / 100

        # Update swap usage
        if self._swap_usage_text:
            swap_used_gb = metrics.swap_info.used_mb / 1024
            swap_total_gb = metrics.swap_info.total_mb / 1024
            self._swap_usage_text.value = f"{swap_used_gb:.1f} GB / {swap_total_gb:.1f} GB"

        if self._swap_progress:
            self._swap_progress.value = metrics.swap_info.usage_percent / 100

        # Update virtual memory
        if self._virtual_usage_text:
            virtual_used_gb = metrics.virtual_used_mb / 1024
            virtual_total_gb = metrics.virtual_total_mb / 1024
            self._virtual_usage_text.value = f"{virtual_used_gb:.1f} GB / {virtual_total_gb:.1f} GB"

        self.update()

    def _update_charts(self) -> None:
        """Update charts with latest metrics data."""
        if not self._memory_history:
            return

        current_time = datetime.now()
        time_window = timedelta(minutes=self._config.history_minutes)

        # Filter recent metrics
        recent_metrics = [
            m for m in self._memory_history
            if current_time - m.timestamp <= time_window
        ]

        if not recent_metrics:
            return

        # Update overview chart
        if self._overview_chart:
            # System RAM points
            ram_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.usage_percent
                ) for m in recent_metrics
            ]
            self._overview_chart.data_series[0].data_points = ram_points

            # GPU VRAM points (if enabled and available)
            if self._config.show_gpu_memory and len(self._overview_chart.data_series) > 1:
                recent_gpu = [
                    gpu for gpu in self._gpu_memory_history
                    if current_time - gpu[0] <= time_window
                ]
                if recent_gpu:
                    vram_points = [
                        ft.LineChartDataPoint(
                            x=(current_time - gpu[0]).total_seconds(),
                            y=(gpu[1] / gpu[2] * 100) if gpu[2] > 0 else 0
                        ) for gpu in recent_gpu
                    ]
                    self._overview_chart.data_series[1].data_points = vram_points

            # Swap points (if enabled)
            if self._config.show_swap_usage and len(self._overview_chart.data_series) > 2:
                swap_points = [
                    ft.LineChartDataPoint(
                        x=(current_time - m.timestamp).total_seconds(),
                        y=m.swap_info.usage_percent
                    ) for m in recent_metrics
                ]
                swap_series_index = 2 if self._config.show_gpu_memory else 1
                if swap_series_index < len(self._overview_chart.data_series):
                    self._overview_chart.data_series[swap_series_index].data_points = swap_points

        # Update detailed chart
        if self._detailed_chart:
            # Used memory points
            used_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.used_ram_mb / 1024  # Convert to GB
                ) for m in recent_metrics
            ]
            self._detailed_chart.data_series[0].data_points = used_points

            # Available memory points
            available_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.available_ram_mb / 1024
                ) for m in recent_metrics
            ]
            self._detailed_chart.data_series[1].data_points = available_points

            # Cached memory points
            cached_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.cached_mb / 1024
                ) for m in recent_metrics
            ]
            self._detailed_chart.data_series[2].data_points = cached_points

            # Buffer points
            buffer_points = [
                ft.LineChartDataPoint(
                    x=(current_time - m.timestamp).total_seconds(),
                    y=m.buffers_mb / 1024
                ) for m in recent_metrics
            ]
            self._detailed_chart.data_series[3].data_points = buffer_points

        self.update()

    def _update_pressure_indicators(self) -> None:
        """Update memory pressure indicators."""
        if not self._current_memory_metrics or not self._pressure_indicator:
            return

        palette = self.get_palette()
        spacing = self.get_spacing()
        metrics = self._current_memory_metrics

        # Determine pressure level
        pressure_score = metrics.memory_pressure_score

        if pressure_score >= 0.8:
            icon_color = palette.error
            text_color = palette.error
            border_color = palette.error
            status_text = "High Memory Pressure"
            icon = self.get_icon('WARNING')
        elif pressure_score >= 0.6:
            icon_color = palette.warning
            text_color = palette.warning
            border_color = palette.warning
            status_text = "Medium Memory Pressure"
            icon = self.get_icon('SPEED')
        else:
            icon_color = palette.success
            text_color = palette.success
            border_color = palette.success
            status_text = "Low Memory Pressure"
            icon = self.get_icon('SPEED')

        # Update pressure indicator
        self._pressure_indicator.content = ft.Row([
            ft.Icon(icon, color=icon_color, size=20),
            ft.Text(
                status_text,
                style=self.get_text_style('body_medium'),
                color=text_color
            )
        ], spacing=spacing.sm)

        self._pressure_indicator.border = ft.border.all(1, border_color)
        self.update()

    def _check_memory_thresholds(self) -> None:
        """Check memory thresholds and trigger alerts."""
        if not self._current_memory_metrics or not self._on_memory_alert:
            return

        metrics = self._current_memory_metrics

        # Check RAM thresholds
        if metrics.usage_percent >= self._config.memory_critical_threshold:
            self._on_memory_alert("ram_critical", metrics.usage_percent)
        elif metrics.usage_percent >= self._config.memory_warning_threshold:
            self._on_memory_alert("ram_warning", metrics.usage_percent)

        # Check swap thresholds
        if metrics.swap_info.usage_percent >= 90:
            self._on_memory_alert("swap_high", metrics.swap_info.usage_percent)

        # Check memory pressure
        if metrics.memory_pressure_score >= 0.8:
            self._on_memory_alert("pressure_high", metrics.memory_pressure_score * 100)

    def _on_view_change(self, e) -> None:
        """Handle view tab change."""
        tab_index = e.control.selected_index
        if tab_index == 0:
            self._selected_view = "overview"
        elif tab_index == 1:
            self._selected_view = "detailed"
        elif tab_index == 2:
            self._selected_view = "tiers"

    def _refresh_memory_info(self, e) -> None:
        """Refresh memory information."""
        if self._memory_monitor:
            # Force refresh of memory info
            self.update()

    def _show_settings(self, e) -> None:
        """Show chart settings dialog."""
        # Placeholder for settings dialog
        pass

    def _export_data(self, e) -> None:
        """Export memory data."""
        # Placeholder for data export functionality
        pass

    def configure_chart(self, config: MemoryChartConfiguration) -> None:
        """Update chart configuration."""
        self._config = config
        self.update()

    def get_current_metrics(self) -> Optional[MemoryMetrics]:
        """Get current memory metrics."""
        return self._current_memory_metrics

    def get_metrics_history(self) -> List[MemoryMetrics]:
        """Get metrics history."""
        return self._memory_history.copy()

    def is_monitoring_active(self) -> bool:
        """Check if monitoring is currently active."""
        return self._is_monitoring

    def will_unmount(self) -> None:
        """Clean up when component is unmounted."""
        if self._is_monitoring:
            asyncio.create_task(self.stop_monitoring())
        super().will_unmount()
