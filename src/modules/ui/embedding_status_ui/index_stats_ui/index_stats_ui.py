"""
Module: index_stats_ui
Description: Comprehensive vector index statistics monitoring interface with real-time performance tracking,
            health monitoring, and optimization recommendations. Provides responsive dashboard components
            for displaying index metrics, search performance, memory usage, and actionable insights.
            Features modern UI/UX with theme-aware styling, accessibility compliance, and cross-platform compatibility.
Phase: 4
Location: /src/modules/ui/embedding_status_ui/index_stats_ui/index_stats_ui.py
"""

# Standard library imports
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
import time
import threading

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)


class IndexHealth(Enum):
    """Index health status enumeration."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class IndexType(Enum):
    """Vector index type enumeration."""
    FLAT = "flat"
    IVF = "ivf"
    HNSW = "hnsw"
    LSH = "lsh"


class OptimizationType(Enum):
    """Index optimization type enumeration."""
    REBUILD = "rebuild"
    REBALANCE = "rebalance"
    COMPRESS = "compress"
    UPGRADE = "upgrade"
    TUNE_PARAMETERS = "tune_parameters"


@dataclass
class IndexStatistics:
    """Comprehensive index statistics data structure."""
    index_id: str
    index_name: str
    index_type: IndexType
    total_vectors: int
    index_size_bytes: int
    build_time_ms: float
    average_search_time_ms: float
    memory_usage_mb: float
    accuracy_score: float = 1.0
    last_optimized: Optional[datetime] = None
    health_status: IndexHealth = IndexHealth.UNKNOWN
    search_count: int = 0
    cache_hit_rate: float = 0.0
    fragmentation_ratio: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexOptimizationSuggestion:
    """Index optimization suggestion data structure."""
    suggestion_id: str
    index_id: str
    optimization_type: OptimizationType
    priority: str  # "high", "medium", "low"
    title: str
    description: str
    expected_improvement: str
    estimated_time: str
    impact_score: float
    complexity: str  # "simple", "moderate", "complex"
    prerequisites: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None


class IndexStatsUI(ThemeAwareUserControl):
    """
    Comprehensive vector index statistics monitoring interface.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time index performance monitoring and health tracking
    - Interactive statistics dashboard with visual metrics
    - Index optimization recommendations and actionable insights
    - Memory usage tracking and search performance analytics
    - Theme-aware styling with accessibility compliance
    - Multi-index comparison and trend analysis
    - Integration with vector search and optimization systems
    """

    def __init__(self,
                 on_optimize_index: Optional[Callable[[str, OptimizationType], None]] = None,
                 on_rebuild_index: Optional[Callable[[str], None]] = None,
                 on_refresh_stats: Optional[Callable[[], None]] = None,
                 auto_refresh: bool = True,
                 refresh_interval: int = 5000,
                 show_optimization_suggestions: bool = True,
                 show_health_indicators: bool = True,
                 **kwargs):
        """
        Initialize IndexStatsUI component.
        
        Args:
            on_optimize_index: Callback for index optimization requests
            on_rebuild_index: Callback for index rebuild requests
            on_refresh_stats: Callback for manual statistics refresh
            auto_refresh: Enable automatic statistics refresh
            refresh_interval: Auto-refresh interval in milliseconds
            show_optimization_suggestions: Show optimization recommendations
            show_health_indicators: Show health status indicators
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)
        
        # Callbacks
        self._on_optimize_index = on_optimize_index
        self._on_rebuild_index = on_rebuild_index
        self._on_refresh_stats = on_refresh_stats
        
        # Configuration
        self._auto_refresh = auto_refresh
        self._refresh_interval = refresh_interval
        self._show_optimization_suggestions = show_optimization_suggestions
        self._show_health_indicators = show_health_indicators
        
        # State management
        self._index_statistics: Dict[str, IndexStatistics] = {}
        self._optimization_suggestions: Dict[str, List[IndexOptimizationSuggestion]] = {}
        self._selected_index_id: Optional[str] = None
        self._is_refreshing = False
        self._last_refresh = datetime.now()
        
        # UI components
        self._stats_container: Optional[ft.Container] = None
        self._health_indicators: Optional[ft.Row] = None
        self._metrics_grid: Optional[ft.GridView] = None
        self._suggestions_list: Optional[ft.ListView] = None
        self._refresh_button: Optional[ft.IconButton] = None
        self._index_selector: Optional[ft.Dropdown] = None
        
        # Threading
        self._lock = threading.RLock()
        self._refresh_timer: Optional[threading.Timer] = None

    def did_mount(self) -> None:
        """Component mounted - start auto-refresh if enabled."""
        super().did_mount()
        if self._auto_refresh:
            self._start_auto_refresh()

    def will_unmount(self) -> None:
        """Component will unmount - cleanup resources."""
        super().will_unmount()
        self._stop_auto_refresh()

    def update_statistics(self, statistics: Dict[str, IndexStatistics]) -> None:
        """
        Update index statistics data.
        
        Args:
            statistics: Dictionary of index statistics by index ID
        """
        try:
            with self._lock:
                self._index_statistics = statistics.copy()
                self._last_refresh = datetime.now()
                
                # Update UI if mounted
                if self.page:
                    self._refresh_ui_components()
                    
        except Exception as e:
            self._handle_error(f"Failed to update statistics: {e}")

    def update_optimization_suggestions(self, suggestions: Dict[str, List[IndexOptimizationSuggestion]]) -> None:
        """
        Update optimization suggestions.
        
        Args:
            suggestions: Dictionary of suggestions by index ID
        """
        try:
            with self._lock:
                self._optimization_suggestions = suggestions.copy()
                
                # Update UI if mounted
                if self.page and self._show_optimization_suggestions:
                    self._refresh_suggestions_ui()
                    
        except Exception as e:
            self._handle_error(f"Failed to update suggestions: {e}")

    def set_selected_index(self, index_id: Optional[str]) -> None:
        """
        Set the selected index for detailed view.
        
        Args:
            index_id: Index ID to select, None for overview
        """
        try:
            with self._lock:
                self._selected_index_id = index_id
                
                # Update UI if mounted
                if self.page:
                    self._refresh_ui_components()
                    
        except Exception as e:
            self._handle_error(f"Failed to set selected index: {e}")

    def refresh_statistics(self) -> None:
        """Manually refresh statistics."""
        try:
            if self._is_refreshing:
                return
                
            self._is_refreshing = True
            
            # Update refresh button state
            if self._refresh_button:
                self._refresh_button.disabled = True
                self._refresh_button.update()
            
            # Trigger refresh callback
            if self._on_refresh_stats:
                self._on_refresh_stats()
                
        except Exception as e:
            self._handle_error(f"Failed to refresh statistics: {e}")
        finally:
            self._is_refreshing = False
            if self._refresh_button:
                self._refresh_button.disabled = False
                self._refresh_button.update()

    def build(self) -> ft.Control:
        """Build the index statistics interface."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            rlm = self.get_responsive_layout()
            
            # Main dashboard layout
            return ft.Container(
                content=ft.Column([
                    self._create_dashboard_header(),
                    ft.Container(height=spacing.md),
                    self._create_health_overview() if self._show_health_indicators else ft.Container(),
                    ft.Container(height=spacing.lg),
                    self._create_statistics_dashboard(),
                    ft.Container(height=spacing.lg),
                    self._create_optimization_panel() if self._show_optimization_suggestions else ft.Container()
                ], scroll=ft.ScrollMode.AUTO),
                bgcolor=palette.background,
                padding=ft.padding.all(rlm.get_breakpoint_value(12, 16, 20, 24)),
                expand=True
            )
            
        except Exception as e:
            return self._create_error_display(str(e))

    def _create_dashboard_header(self) -> ft.Container:
        """Create dashboard header with controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Index selector dropdown
        self._index_selector = ft.Dropdown(
            label="Select Index",
            options=[ft.dropdown.Option("overview", "Overview")] + [
                ft.dropdown.Option(idx_id, stats.index_name)
                for idx_id, stats in self._index_statistics.items()
            ],
            value=self._selected_index_id or "overview",
            on_change=self._on_index_selection_changed,
            width=rlm.get_breakpoint_value(200, 250, 300, 350),
            bgcolor=palette.surface,
            color=palette.on_surface
        )

        # Refresh button
        self._refresh_button = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Refresh Statistics",
            on_click=lambda _: self.refresh_statistics(),
            disabled=self._is_refreshing,
            icon_color=palette.primary,
            bgcolor=palette.surface
        )

        # Auto-refresh toggle
        auto_refresh_switch = ft.Switch(
            label="Auto Refresh",
            value=self._auto_refresh,
            on_change=self._on_auto_refresh_changed,
            active_color=palette.primary
        )

        # Last refresh indicator
        last_refresh_text = ft.Text(
            f"Last updated: {self._last_refresh.strftime('%H:%M:%S')}",
            style=typography.body_small,
            color=palette.on_surface_variant
        )

        return ft.Container(
            content=ft.Row([
                ft.Text(
                    "Index Statistics",
                    style=typography.headline_medium,
                    color=palette.on_surface
                ),
                ft.Container(expand=True),
                self._index_selector,
                ft.Container(width=spacing.md),
                auto_refresh_switch,
                ft.Container(width=spacing.sm),
                self._refresh_button,
                ft.Container(width=spacing.md),
                last_refresh_text
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14)
        )

    def _create_health_overview(self) -> ft.Container:
        """Create health status overview."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Health indicators for each index
        health_cards = []
        for idx_id, stats in self._index_statistics.items():
            health_color = self._get_health_color(stats.health_status)

            health_card = ft.Container(
                content=ft.Column([
                    ft.Text(
                        stats.index_name,
                        style=typography.title_small,
                        color=palette.on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Container(height=spacing.xs),
                    ft.Icon(
                        self._get_health_icon(stats.health_status),
                        color=health_color,
                        size=rlm.get_breakpoint_value(24, 28, 32, 36)
                    ),
                    ft.Container(height=spacing.xs),
                    ft.Text(
                        stats.health_status.value.title(),
                        style=typography.body_small,
                        color=health_color,
                        text_align=ft.TextAlign.CENTER
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface,
                border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
                width=rlm.get_breakpoint_value(120, 140, 160, 180)
            )
            health_cards.append(health_card)

        self._health_indicators = ft.Row(
            controls=health_cards,
            alignment=ft.MainAxisAlignment.START,
            spacing=spacing.md,
            scroll=ft.ScrollMode.AUTO
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Index Health Overview",
                    style=typography.title_medium,
                    color=palette.on_surface
                ),
                ft.Container(height=spacing.sm),
                self._health_indicators
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14)
        )

    def _create_statistics_dashboard(self) -> ft.Container:
        """Create main statistics dashboard."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        if self._selected_index_id and self._selected_index_id != "overview":
            # Detailed view for selected index
            return self._create_detailed_index_view()
        else:
            # Overview of all indexes
            return self._create_overview_dashboard()

    def _create_overview_dashboard(self) -> ft.Container:
        """Create overview dashboard for all indexes."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Summary metrics
        total_vectors = sum(stats.total_vectors for stats in self._index_statistics.values())
        total_size_mb = sum(stats.index_size_bytes / (1024 * 1024) for stats in self._index_statistics.values())
        avg_search_time = (
            sum(stats.average_search_time_ms for stats in self._index_statistics.values()) /
            len(self._index_statistics) if self._index_statistics else 0
        )
        total_memory_mb = sum(stats.memory_usage_mb for stats in self._index_statistics.values())

        # Create metric cards
        metric_cards = [
            self._create_metric_card("Total Vectors", f"{total_vectors:,}", palette.primary),
            self._create_metric_card("Total Size", f"{total_size_mb:.1f} MB", palette.secondary),
            self._create_metric_card("Avg Search Time", f"{avg_search_time:.2f} ms", palette.tertiary),
            self._create_metric_card("Memory Usage", f"{total_memory_mb:.1f} MB", palette.success)
        ]

        metrics_row = ft.Row(
            controls=metric_cards,
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            spacing=spacing.md,
            wrap=True
        )

        # Index comparison table
        index_table = self._create_index_comparison_table()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Overview Dashboard",
                    style=typography.title_medium,
                    color=palette.on_surface
                ),
                ft.Container(height=spacing.md),
                metrics_row,
                ft.Container(height=spacing.lg),
                index_table
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14)
        )

    def _create_detailed_index_view(self) -> ft.Container:
        """Create detailed view for selected index."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        if not self._selected_index_id or self._selected_index_id not in self._index_statistics:
            return ft.Container(
                content=ft.Text("Index not found", color=palette.error),
                padding=ft.padding.all(spacing.md)
            )

        stats = self._index_statistics[self._selected_index_id]

        # Detailed metrics
        detailed_metrics = [
            self._create_metric_card("Vectors", f"{stats.total_vectors:,}", palette.primary),
            self._create_metric_card("Size", f"{stats.index_size_bytes / (1024 * 1024):.1f} MB", palette.secondary),
            self._create_metric_card("Search Time", f"{stats.average_search_time_ms:.2f} ms", palette.tertiary),
            self._create_metric_card("Memory", f"{stats.memory_usage_mb:.1f} MB", palette.success),
            self._create_metric_card("Accuracy", f"{stats.accuracy_score:.3f}", palette.warning),
            self._create_metric_card("Cache Hit Rate", f"{stats.cache_hit_rate:.1%}", palette.info)
        ]

        metrics_grid = ft.GridView(
            controls=detailed_metrics,
            runs_count=rlm.get_breakpoint_value(2, 3, 4, 6),
            spacing=spacing.md,
            run_spacing=spacing.md,
            child_aspect_ratio=1.5,
            height=rlm.get_breakpoint_value(200, 250, 300, 350)
        )

        # Performance chart placeholder
        performance_chart = self._create_performance_chart(stats)

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    f"Index Details: {stats.index_name}",
                    style=typography.title_medium,
                    color=palette.on_surface
                ),
                ft.Container(height=spacing.md),
                metrics_grid,
                ft.Container(height=spacing.lg),
                performance_chart
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14)
        )

    def _create_optimization_panel(self) -> ft.Container:
        """Create optimization recommendations panel."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get suggestions for selected index or all indexes
        suggestions = []
        if self._selected_index_id and self._selected_index_id != "overview":
            suggestions = self._optimization_suggestions.get(self._selected_index_id, [])
        else:
            # Combine all suggestions
            for idx_suggestions in self._optimization_suggestions.values():
                suggestions.extend(idx_suggestions)

        # Sort by priority and impact
        suggestions.sort(key=lambda s: (
            {"high": 0, "medium": 1, "low": 2}.get(s.priority, 3),
            -s.impact_score
        ))

        # Create suggestion cards
        suggestion_cards = []
        for suggestion in suggestions[:5]:  # Show top 5 suggestions
            suggestion_card = self._create_suggestion_card(suggestion)
            suggestion_cards.append(suggestion_card)

        if not suggestion_cards:
            suggestion_cards = [
                ft.Container(
                    content=ft.Text(
                        "No optimization suggestions available",
                        style=typography.body_medium,
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    padding=ft.padding.all(spacing.lg),
                    alignment=ft.alignment.center
                )
            ]

        self._suggestions_list = ft.ListView(
            controls=suggestion_cards,
            spacing=spacing.md,
            height=rlm.get_breakpoint_value(300, 350, 400, 450)
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Optimization Recommendations",
                    style=typography.title_medium,
                    color=palette.on_surface
                ),
                ft.Container(height=spacing.md),
                self._suggestions_list
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14)
        )

    def _create_metric_card(self, title: str, value: str, color: str) -> ft.Container:
        """Create a metric display card."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    title,
                    style=typography.body_small,
                    color=palette.on_surface_variant,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=spacing.xs),
                ft.Text(
                    value,
                    style=typography.headline_small,
                    color=color,
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.BOLD
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=rlm.get_breakpoint_value(6, 8, 10, 12),
            width=rlm.get_breakpoint_value(120, 140, 160, 180),
            height=rlm.get_breakpoint_value(80, 90, 100, 110)
        )

    def _create_suggestion_card(self, suggestion: IndexOptimizationSuggestion) -> ft.Container:
        """Create optimization suggestion card."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Priority color
        priority_colors = {
            "high": palette.error,
            "medium": palette.warning,
            "low": palette.info
        }
        priority_color = priority_colors.get(suggestion.priority, palette.on_surface_variant)

        # Action buttons
        action_buttons = ft.Row([
            ft.TextButton(
                text="Apply",
                on_click=lambda _: self._apply_optimization(suggestion),
                style=ft.ButtonStyle(color=palette.primary)
            ),
            ft.TextButton(
                text="Details",
                on_click=lambda _: self._show_suggestion_details(suggestion),
                style=ft.ButtonStyle(color=palette.on_surface_variant)
            )
        ], spacing=spacing.sm)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        suggestion.title,
                        style=typography.title_small,
                        color=palette.on_surface,
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Text(
                            suggestion.priority.upper(),
                            style=typography.label_small,
                            color=priority_color,
                            weight=ft.FontWeight.BOLD
                        ),
                        padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
                        bgcolor=f"{priority_color}20",
                        border_radius=4
                    )
                ]),
                ft.Container(height=spacing.xs),
                ft.Text(
                    suggestion.description,
                    style=typography.body_small,
                    color=palette.on_surface_variant
                ),
                ft.Container(height=spacing.sm),
                ft.Row([
                    ft.Text(
                        f"Impact: {suggestion.impact_score:.1f}",
                        style=typography.label_small,
                        color=palette.on_surface_variant
                    ),
                    ft.Container(width=spacing.md),
                    ft.Text(
                        f"Time: {suggestion.estimated_time}",
                        style=typography.label_small,
                        color=palette.on_surface_variant
                    ),
                    ft.Container(expand=True),
                    action_buttons
                ])
            ]),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
            border=ft.border.all(1, palette.outline_variant)
        )

    def _create_index_comparison_table(self) -> ft.Container:
        """Create index comparison table."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Table headers
        headers = [
            ft.Text("Index", style=typography.title_small, color=palette.on_surface),
            ft.Text("Type", style=typography.title_small, color=palette.on_surface),
            ft.Text("Vectors", style=typography.title_small, color=palette.on_surface),
            ft.Text("Size (MB)", style=typography.title_small, color=palette.on_surface),
            ft.Text("Search (ms)", style=typography.title_small, color=palette.on_surface),
            ft.Text("Health", style=typography.title_small, color=palette.on_surface)
        ]

        # Table rows
        rows = []
        for idx_id, stats in self._index_statistics.items():
            health_color = self._get_health_color(stats.health_status)

            row = ft.Row([
                ft.Text(stats.index_name, style=typography.body_medium, color=palette.on_surface),
                ft.Text(stats.index_type.value.upper(), style=typography.body_medium, color=palette.on_surface_variant),
                ft.Text(f"{stats.total_vectors:,}", style=typography.body_medium, color=palette.on_surface),
                ft.Text(f"{stats.index_size_bytes / (1024 * 1024):.1f}", style=typography.body_medium, color=palette.on_surface),
                ft.Text(f"{stats.average_search_time_ms:.2f}", style=typography.body_medium, color=palette.on_surface),
                ft.Container(
                    content=ft.Text(
                        stats.health_status.value.title(),
                        style=typography.label_small,
                        color=health_color
                    ),
                    padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
                    bgcolor=f"{health_color}20",
                    border_radius=4
                )
            ], spacing=spacing.md)
            rows.append(row)

        # Create table
        table_content = ft.Column([
            ft.Row(headers, spacing=spacing.md),
            ft.Divider(color=palette.outline_variant),
            *rows
        ], spacing=spacing.sm)

        return ft.Container(
            content=table_content,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14)
        )

    def _create_performance_chart(self, stats: IndexStatistics) -> ft.Container:
        """Create performance chart placeholder."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Performance metrics visualization placeholder
        chart_placeholder = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Performance Trends",
                    style=typography.title_small,
                    color=palette.on_surface,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=spacing.md),
                ft.Text(
                    "Chart visualization would be implemented here",
                    style=typography.body_medium,
                    color=palette.on_surface_variant,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=spacing.sm),
                ft.Text(
                    f"Search Performance: {stats.average_search_time_ms:.2f}ms avg",
                    style=typography.body_small,
                    color=palette.on_surface_variant,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface_variant,
            border_radius=rlm.get_breakpoint_value(8, 10, 12, 14),
            height=rlm.get_breakpoint_value(200, 250, 300, 350),
            alignment=ft.alignment.center
        )

        return chart_placeholder

    def _get_health_color(self, health: IndexHealth) -> str:
        """Get color for health status."""
        palette = self.get_palette()

        health_colors = {
            IndexHealth.EXCELLENT: palette.success,
            IndexHealth.GOOD: palette.success,
            IndexHealth.FAIR: palette.warning,
            IndexHealth.POOR: palette.error,
            IndexHealth.CRITICAL: palette.error,
            IndexHealth.UNKNOWN: palette.on_surface_variant
        }
        return health_colors.get(health, palette.on_surface_variant)

    def _get_health_icon(self, health: IndexHealth) -> str:
        """Get icon for health status."""
        health_icons = {
            IndexHealth.EXCELLENT: ft.Icons.CHECK_CIRCLE,
            IndexHealth.GOOD: ft.Icons.CHECK_CIRCLE_OUTLINE,
            IndexHealth.FAIR: ft.Icons.WARNING,
            IndexHealth.POOR: ft.Icons.ERROR_OUTLINE,
            IndexHealth.CRITICAL: ft.Icons.ERROR,
            IndexHealth.UNKNOWN: ft.Icons.HELP_OUTLINE
        }
        return health_icons.get(health, ft.Icons.HELP_OUTLINE)

    def _on_index_selection_changed(self, e) -> None:
        """Handle index selection change."""
        try:
            selected_value = e.control.value
            self.set_selected_index(selected_value if selected_value != "overview" else None)
        except Exception as ex:
            self._handle_error(f"Failed to change index selection: {ex}")

    def _on_auto_refresh_changed(self, e) -> None:
        """Handle auto-refresh toggle change."""
        try:
            self._auto_refresh = e.control.value
            if self._auto_refresh:
                self._start_auto_refresh()
            else:
                self._stop_auto_refresh()
        except Exception as ex:
            self._handle_error(f"Failed to toggle auto-refresh: {ex}")

    def _apply_optimization(self, suggestion: IndexOptimizationSuggestion) -> None:
        """Apply optimization suggestion."""
        try:
            if self._on_optimize_index:
                self._on_optimize_index(suggestion.index_id, suggestion.optimization_type)
        except Exception as e:
            self._handle_error(f"Failed to apply optimization: {e}")

    def _show_suggestion_details(self, suggestion: IndexOptimizationSuggestion) -> None:
        """Show detailed suggestion information."""
        try:
            # This would typically open a detailed dialog
            # For now, we'll just log the suggestion details
            details = f"Suggestion: {suggestion.title}\n"
            details += f"Description: {suggestion.description}\n"
            details += f"Expected Improvement: {suggestion.expected_improvement}\n"
            details += f"Estimated Time: {suggestion.estimated_time}\n"
            details += f"Complexity: {suggestion.complexity}\n"

            if suggestion.prerequisites:
                details += f"Prerequisites: {', '.join(suggestion.prerequisites)}\n"

            if suggestion.risks:
                details += f"Risks: {', '.join(suggestion.risks)}\n"

            print(f"Suggestion Details:\n{details}")

        except Exception as e:
            self._handle_error(f"Failed to show suggestion details: {e}")

    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer."""
        try:
            self._stop_auto_refresh()  # Stop existing timer

            if self._auto_refresh and self._refresh_interval > 0:
                self._refresh_timer = threading.Timer(
                    self._refresh_interval / 1000.0,
                    self._auto_refresh_callback
                )
                self._refresh_timer.daemon = True
                self._refresh_timer.start()

        except Exception as e:
            self._handle_error(f"Failed to start auto-refresh: {e}")

    def _stop_auto_refresh(self) -> None:
        """Stop auto-refresh timer."""
        try:
            if self._refresh_timer:
                self._refresh_timer.cancel()
                self._refresh_timer = None
        except Exception as e:
            self._handle_error(f"Failed to stop auto-refresh: {e}")

    def _auto_refresh_callback(self) -> None:
        """Auto-refresh callback."""
        try:
            if self._auto_refresh:
                self.refresh_statistics()
                self._start_auto_refresh()  # Schedule next refresh
        except Exception as e:
            self._handle_error(f"Auto-refresh failed: {e}")

    def _refresh_ui_components(self) -> None:
        """Refresh UI components with current data."""
        try:
            if self.page:
                # Update index selector options
                if self._index_selector:
                    self._index_selector.options = [ft.dropdown.Option("overview", "Overview")] + [
                        ft.dropdown.Option(idx_id, stats.index_name)
                        for idx_id, stats in self._index_statistics.items()
                    ]
                    self._index_selector.update()

                # Trigger full rebuild
                self.update()

        except Exception as e:
            self._handle_error(f"Failed to refresh UI components: {e}")

    def _refresh_suggestions_ui(self) -> None:
        """Refresh suggestions UI components."""
        try:
            if self.page and self._suggestions_list:
                # This would update the suggestions list
                self.update()
        except Exception as e:
            self._handle_error(f"Failed to refresh suggestions UI: {e}")

    def _create_error_display(self, error_message: str) -> ft.Container:
        """Create error display component."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column([
                ft.Icon(
                    ft.Icons.ERROR_OUTLINE,
                    color=palette.error,
                    size=48
                ),
                ft.Container(height=spacing.md),
                ft.Text(
                    "Error Loading Index Statistics",
                    style=typography.title_medium,
                    color=palette.error,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=spacing.sm),
                ft.Text(
                    error_message,
                    style=typography.body_medium,
                    color=palette.on_surface_variant,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(spacing.xl),
            alignment=ft.alignment.center,
            expand=True
        )

    def _handle_error(self, error_message: str) -> None:
        """Handle and log errors."""
        try:
            print(f"IndexStatsUI Error: {error_message}")
            # In a real implementation, this would use proper logging
        except Exception:
            pass  # Avoid recursive errors
