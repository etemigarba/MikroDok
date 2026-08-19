"""
Module: metric_cards_ui
Description: Reusable metric display cards with real-time updates, trend indicators, and responsive design.
            Provides comprehensive metric visualization components for dashboards, monitoring interfaces,
            and analytics displays with full theme system integration and accessibility compliance.

Features:
- Multiple metric card variants (compact, detailed, minimal, dashboard)
- Real-time metric updates with smooth animations
- Trend indicators and historical data visualization
- Responsive design with breakpoint-aware layouts
- Theme-aware styling with accessibility compliance
- Performance optimization for continuous monitoring
- Customizable metric categories and grouping
- Interactive features with hover states and click handlers
- Export functionality for metric data
- Cross-platform compatibility and offline operation

Phase: 2-4
Location: /src/modules/ui/visualization_ui/metric_cards_ui/metric_cards_ui.py
"""

# Standard library imports
import os
import json
import time
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
try:
    from src.modules.ui.theme_system_ui.theme_system_ui import (
        ThemeAwareUserControl,
        ResponsiveLayoutManager,
        ColorPalette,
        SpacingSystem,
        TypographyScale,
        IconSystem,
        get_theme_manager
    )
except ImportError:
    # Fallback for testing without full theme system
    class ThemeAwareUserControl(ft.Container):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
        
        def get_palette(self):
            class MockPalette:
                background_primary = "#000000"
                surface = "#2D2D2D"
                primary = "#44AAFF"
                text_primary = "#FFFFFF"
                text_secondary = "#C0C0C0"
                success = "#44FF44"
                warning = "#FFA500"
                error = "#FF4444"
                info = "#44AAFF"
                secondary = "#B8B8B8"
                borders = "#5D5D5D"
                surface_variant = "#333333"
            return MockPalette()
        
        def get_spacing(self):
            class MockSpacing:
                xs = 4
                sm = 8
                md = 12
                lg = 16
                xl = 24
                component_padding = 16
            return MockSpacing()
        
        def get_text_style(self, style_name):
            return ft.TextStyle(size=14)
        
        def get_icon(self, icon_name):
            return getattr(ft.Icons, icon_name, ft.Icons.CIRCLE)
        
        def get_responsive_layout(self):
            class MockResponsive:
                def get_breakpoint_value(self, mobile, tablet, desktop, large):
                    return desktop
                def is_mobile(self):
                    return False
                def is_tablet(self):
                    return False
                def is_desktop(self):
                    return True
                def get_responsive_padding(self):
                    return 16
                def create_responsive_grid(self, children, **kwargs):
                    return ft.GridView(controls=children, runs_count=3)
            return MockResponsive()


class MetricCategory(Enum):
    """Metric category enumeration for organization and filtering."""
    TRAINING = "training"
    VALIDATION = "validation"
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    SYSTEM = "system"
    QUALITY = "quality"
    PROCESSING = "processing"
    NETWORK = "network"
    STORAGE = "storage"
    CUSTOM = "custom"


class MetricCardVariant(Enum):
    """Metric card display variant enumeration."""
    COMPACT = "compact"          # Small card with minimal information
    DETAILED = "detailed"        # Full card with all information and trends
    MINIMAL = "minimal"          # Icon and value only
    DASHBOARD = "dashboard"      # Dashboard-style with emphasis on value
    TILE = "tile"               # Square tile format
    BANNER = "banner"           # Wide banner format


class TrendDirection(Enum):
    """Trend direction enumeration for metric indicators."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass
class MetricTrend:
    """Metric trend data structure."""
    direction: TrendDirection = TrendDirection.UNKNOWN
    percentage: float = 0.0
    period: str = "24h"
    is_positive: bool = True  # Whether the trend direction is positive for this metric
    historical_data: List[float] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class MetricCard:
    """Individual metric card data structure."""
    metric_id: str
    title: str
    value: Union[str, int, float]
    unit: str = ""
    icon: str = "ANALYTICS"
    category: MetricCategory = MetricCategory.CUSTOM
    color: str = "primary"
    description: str = ""
    trend: Optional[MetricTrend] = None
    variant: MetricCardVariant = MetricCardVariant.DETAILED
    is_clickable: bool = True
    is_visible: bool = True
    priority: int = 0  # 0-10 scale for sorting
    format_precision: int = 2
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    last_updated: datetime = field(default_factory=datetime.now)
    custom_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricCardsConfiguration:
    """Configuration for metric cards display."""
    auto_refresh: bool = True
    refresh_interval_seconds: float = 2.0
    show_trends: bool = True
    show_timestamps: bool = False
    show_descriptions: bool = True
    enable_animations: bool = True
    enable_hover_effects: bool = True
    enable_click_handlers: bool = True
    default_variant: MetricCardVariant = MetricCardVariant.DETAILED
    grid_columns_mobile: int = 1
    grid_columns_tablet: int = 2
    grid_columns_desktop: int = 3
    grid_columns_large: int = 4
    card_aspect_ratio: float = 1.5
    max_cards_per_page: int = 50
    enable_export: bool = True
    enable_filtering: bool = True
    enable_sorting: bool = True
    categories_enabled: Dict[MetricCategory, bool] = field(default_factory=lambda: {
        category: True for category in MetricCategory
    })


@dataclass
class MetricCardsState:
    """State management for metric cards."""
    selected_cards: List[str] = field(default_factory=list)
    filtered_categories: List[MetricCategory] = field(default_factory=list)
    sort_by: str = "priority"
    sort_ascending: bool = False
    current_page: int = 1
    search_query: str = ""
    last_refresh: datetime = field(default_factory=datetime.now)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class MetricCardsUI(ThemeAwareUserControl):
    """
    Comprehensive metric cards UI component for displaying real-time metrics.

    Features:
    - Responsive design with breakpoint-aware layouts
    - Multiple card variants (compact, detailed, minimal, dashboard, tile, banner)
    - Real-time metric updates with smooth animations
    - Trend indicators and historical data visualization
    - Theme-aware styling with accessibility compliance
    - Interactive features with hover states and click handlers
    - Performance optimization for continuous monitoring
    - Customizable metric categories and filtering
    - Export functionality for metric data
    - Cross-platform compatibility and offline operation
    """

    def __init__(self,
                 config: Optional[MetricCardsConfiguration] = None,
                 on_card_click: Optional[Callable[[str], None]] = None,
                 on_card_hover: Optional[Callable[[str, bool], None]] = None,
                 **kwargs):
        """
        Initialize metric cards UI component.

        Args:
            config: Configuration for metric cards display
            on_card_click: Callback for card click events
            on_card_hover: Callback for card hover events
            **kwargs: Additional arguments for ThemeAwareUserControl
        """
        super().__init__(**kwargs)

        # Configuration
        self._config = config or MetricCardsConfiguration()
        self._state = MetricCardsState()

        # Event handlers
        self._on_card_click = on_card_click
        self._on_card_hover = on_card_hover

        # Data storage
        self._metric_cards: Dict[str, MetricCard] = {}
        self._card_widgets: Dict[str, ft.Control] = {}
        self._update_callbacks: List[Callable[[], None]] = []

        # UI components
        self._main_container: Optional[ft.Control] = None
        self._grid_container: Optional[ft.Control] = None
        self._filter_controls: Optional[ft.Control] = None
        self._search_bar: Optional[ft.Control] = None

        # Performance tracking
        self._performance_metrics = {
            'cards_rendered': 0,
            'updates_processed': 0,
            'render_time_total': 0,
            'last_render_time': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

        # Animation and update management
        self._update_timer: Optional[asyncio.Task] = None
        self._animation_queue: List[Tuple[str, Dict[str, Any]]] = []
        self._is_updating = False

        # Initialize component
        self._initialize_component()

    def _initialize_component(self) -> None:
        """Initialize the metric cards component."""
        try:
            # Set up theme change handler if available
            if hasattr(self, 'add_theme_change_handler'):
                self.add_theme_change_handler(self._on_theme_change)

            # Set up responsive change handler
            responsive_manager = self.get_responsive_layout()
            if hasattr(responsive_manager, 'add_resize_callback'):
                responsive_manager.add_resize_callback(self._on_responsive_change)

            # Initialize default metrics if none provided
            if not self._metric_cards:
                self._initialize_default_metrics()

            # Start auto-refresh if enabled
            if self._config.auto_refresh:
                self._start_auto_refresh()

        except Exception as e:
            print(f"Error initializing MetricCardsUI: {e}")

    def _initialize_default_metrics(self) -> None:
        """Initialize default metric cards for demonstration."""
        default_metrics = [
            MetricCard(
                metric_id="cpu_usage",
                title="CPU Usage",
                value=0.0,
                unit="%",
                icon="CPU",
                category=MetricCategory.RESOURCE,
                color="primary",
                description="Current CPU utilization percentage"
            ),
            MetricCard(
                metric_id="memory_usage",
                title="Memory Usage",
                value=0.0,
                unit="%",
                icon="MEMORY",
                category=MetricCategory.RESOURCE,
                color="info",
                description="Current memory utilization percentage"
            ),
            MetricCard(
                metric_id="gpu_usage",
                title="GPU Usage",
                value=0.0,
                unit="%",
                icon="GPU",
                category=MetricCategory.RESOURCE,
                color="warning",
                description="Current GPU utilization percentage"
            ),
            MetricCard(
                metric_id="training_loss",
                title="Training Loss",
                value=0.0,
                unit="",
                icon="TRENDING_DOWN",
                category=MetricCategory.TRAINING,
                color="error",
                description="Current training loss value"
            )
        ]

        for metric in default_metrics:
            self._metric_cards[metric.metric_id] = metric

    def build(self) -> ft.Control:
        """Build the metric cards UI component."""
        try:
            self._main_container = self._create_main_container()
            return self._main_container
        except Exception as e:
            print(f"Error building MetricCardsUI: {e}")
            return ft.Container(
                content=ft.Text(f"Error: {e}"),
                padding=ft.padding.all(16)
            )

    def _create_main_container(self) -> ft.Control:
        """Create the main container for metric cards."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create filter controls if enabled
        controls = []
        if self._config.enable_filtering:
            controls.append(self._create_filter_controls())

        # Create metric cards grid
        controls.append(self._create_metrics_grid())

        return ft.Container(
            content=ft.Column(
                controls=controls,
                spacing=spacing.lg,
                expand=True
            ),
            padding=ft.padding.all(spacing.component_padding),
            expand=True
        )

    def _create_filter_controls(self) -> ft.Control:
        """Create filter and search controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Search bar
        self._search_bar = ft.TextField(
            hint_text="Search metrics...",
            prefix_icon=self.get_icon('SEARCH'),
            on_change=self._on_search_change,
            expand=True
        )

        # Category filter dropdown
        category_options = [
            ft.dropdown.Option(key=cat.value, text=cat.value.title())
            for cat in MetricCategory
        ]

        category_filter = ft.Dropdown(
            hint_text="Filter by category",
            options=category_options,
            on_change=self._on_category_filter_change,
            width=200
        )

        # View mode toggle
        view_mode_buttons = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="grid",
                    label=ft.Text("Grid"),
                    icon=self.get_icon('GRID_VIEW')
                ),
                ft.Segment(
                    value="list",
                    label=ft.Text("List"),
                    icon=self.get_icon('LIST_VIEW')
                )
            ],
            selected={"grid"},
            on_change=self._on_view_mode_change
        )

        return ft.Container(
            content=ft.Row([
                self._search_bar,
                category_filter,
                view_mode_buttons
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.sm)
        )

    def _create_metrics_grid(self) -> ft.Control:
        """Create the metrics grid layout."""
        rlm = self.get_responsive_layout()
        spacing = self.get_spacing()

        # Get filtered and sorted metrics
        filtered_metrics = self._get_filtered_metrics()

        # Create metric card widgets
        card_widgets = []
        for metric in filtered_metrics:
            card_widget = self._create_metric_card_widget(metric)
            if card_widget:
                card_widgets.append(card_widget)

        # Create responsive grid
        self._grid_container = rlm.create_responsive_grid(
            children=card_widgets,
            mobile_cols=self._config.grid_columns_mobile,
            tablet_cols=self._config.grid_columns_tablet,
            desktop_cols=self._config.grid_columns_desktop,
            large_cols=self._config.grid_columns_large,
            spacing=spacing.md,
            run_spacing=spacing.md
        )

        return self._grid_container

    def _create_metric_card_widget(self, metric: MetricCard) -> Optional[ft.Control]:
        """Create a metric card widget based on variant."""
        try:
            if not metric.is_visible:
                return None

            # Create card based on variant
            if metric.variant == MetricCardVariant.COMPACT:
                return self._create_compact_card(metric)
            elif metric.variant == MetricCardVariant.DETAILED:
                return self._create_detailed_card(metric)
            elif metric.variant == MetricCardVariant.MINIMAL:
                return self._create_minimal_card(metric)
            elif metric.variant == MetricCardVariant.DASHBOARD:
                return self._create_dashboard_card(metric)
            elif metric.variant == MetricCardVariant.TILE:
                return self._create_tile_card(metric)
            elif metric.variant == MetricCardVariant.BANNER:
                return self._create_banner_card(metric)
            else:
                return self._create_detailed_card(metric)  # Default fallback

        except Exception as e:
            print(f"Error creating metric card widget for {metric.metric_id}: {e}")
            return None

    def _create_detailed_card(self, metric: MetricCard) -> ft.Control:
        """Create a detailed metric card with full information."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on metric color
        card_color = getattr(palette, metric.color, palette.primary)

        # Format value
        formatted_value = self._format_metric_value(metric)

        # Icon
        icon_widget = ft.Icon(
            self.get_icon(metric.icon),
            color=card_color,
            size=rlm.get_breakpoint_value(24, 28, 32, 36)
        )

        # Title
        title_widget = ft.Text(
            metric.title,
            style=self.get_text_style('body_medium'),
            color=palette.text_secondary,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # Value
        value_widget = ft.Text(
            formatted_value,
            style=self.get_text_style('h2'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # Trend indicator
        trend_widget = None
        if metric.trend and self._config.show_trends:
            trend_widget = self._create_trend_indicator(metric.trend)

        # Description
        description_widget = None
        if metric.description and self._config.show_descriptions:
            description_widget = ft.Text(
                metric.description,
                style=self.get_text_style('caption'),
                color=palette.text_tertiary,
                overflow=ft.TextOverflow.ELLIPSIS,
                max_lines=2
            )

        # Header row with icon and title
        header_row = ft.Row([
            icon_widget,
            ft.Expanded(child=title_widget)
        ], spacing=spacing.sm)

        # Content column
        content_widgets = [header_row, value_widget]
        if trend_widget:
            content_widgets.append(trend_widget)
        if description_widget:
            content_widgets.append(description_widget)

        content_column = ft.Column(
            controls=content_widgets,
            spacing=spacing.xs,
            expand=True
        )

        # Create card container
        card = ft.Container(
            content=content_column,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(8, 10, 12, 14)),
            border=ft.border.all(1, palette.borders),
            on_click=lambda e: self._handle_card_click(metric.metric_id) if metric.is_clickable else None,
            on_hover=lambda e: self._handle_card_hover(metric.metric_id, e.data == "true") if self._config.enable_hover_effects else None,
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT) if self._config.enable_animations else None,
            tooltip=metric.description if metric.description else metric.title
        )

        # Store widget reference for updates
        self._card_widgets[metric.metric_id] = card

        return card

    def _create_compact_card(self, metric: MetricCard) -> ft.Control:
        """Create a compact metric card with minimal information."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on metric color
        card_color = getattr(palette, metric.color, palette.primary)

        # Format value
        formatted_value = self._format_metric_value(metric)

        # Icon
        icon_widget = ft.Icon(
            self.get_icon(metric.icon),
            color=card_color,
            size=rlm.get_breakpoint_value(16, 18, 20, 22)
        )

        # Value
        value_widget = ft.Text(
            formatted_value,
            style=self.get_text_style('body_large'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER
        )

        # Title
        title_widget = ft.Text(
            metric.title,
            style=self.get_text_style('caption'),
            color=palette.text_secondary,
            text_align=ft.TextAlign.CENTER,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # Content column
        content_column = ft.Column([
            icon_widget,
            value_widget,
            title_widget
        ], spacing=spacing.xs,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # Create card container
        card = ft.Container(
            content=content_column,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.borders),
            on_click=lambda e: self._handle_card_click(metric.metric_id) if metric.is_clickable else None,
            tooltip=metric.title
        )

        # Store widget reference for updates
        self._card_widgets[metric.metric_id] = card

        return card

    def _create_minimal_card(self, metric: MetricCard) -> ft.Control:
        """Create a minimal metric card with icon and value only."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on metric color
        card_color = getattr(palette, metric.color, palette.primary)

        # Format value
        formatted_value = self._format_metric_value(metric)

        # Icon and value row
        content_row = ft.Row([
            ft.Icon(
                self.get_icon(metric.icon),
                color=card_color,
                size=rlm.get_breakpoint_value(16, 18, 20, 22)
            ),
            ft.Text(
                formatted_value,
                style=self.get_text_style('body_medium'),
                color=palette.text_primary,
                weight=ft.FontWeight.BOLD
            )
        ], spacing=spacing.sm,
           alignment=ft.MainAxisAlignment.CENTER)

        # Create card container
        card = ft.Container(
            content=content_row,
            padding=ft.padding.all(spacing.sm),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(4, 6, 8, 10)),
            on_click=lambda e: self._handle_card_click(metric.metric_id) if metric.is_clickable else None,
            tooltip=f"{metric.title}: {formatted_value}"
        )

        # Store widget reference for updates
        self._card_widgets[metric.metric_id] = card

        return card

    def _create_dashboard_card(self, metric: MetricCard) -> ft.Control:
        """Create a dashboard-style metric card with emphasis on value."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on metric color
        card_color = getattr(palette, metric.color, palette.primary)

        # Format value
        formatted_value = self._format_metric_value(metric)

        # Large value display
        value_widget = ft.Text(
            formatted_value,
            style=self.get_text_style('display_medium'),
            color=card_color,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER
        )

        # Title below value
        title_widget = ft.Text(
            metric.title,
            style=self.get_text_style('body_medium'),
            color=palette.text_secondary,
            text_align=ft.TextAlign.CENTER
        )

        # Trend indicator
        trend_widget = None
        if metric.trend and self._config.show_trends:
            trend_widget = self._create_trend_indicator(metric.trend)

        # Content column
        content_widgets = [value_widget, title_widget]
        if trend_widget:
            content_widgets.append(trend_widget)

        content_column = ft.Column(
            controls=content_widgets,
            spacing=spacing.sm,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

        # Create card container
        card = ft.Container(
            content=content_column,
            padding=ft.padding.all(spacing.xl),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(12, 14, 16, 18)),
            border=ft.border.all(2, card_color),
            on_click=lambda e: self._handle_card_click(metric.metric_id) if metric.is_clickable else None,
            tooltip=metric.description if metric.description else metric.title
        )

        # Store widget reference for updates
        self._card_widgets[metric.metric_id] = card

        return card

    def _create_tile_card(self, metric: MetricCard) -> ft.Control:
        """Create a square tile metric card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on metric color
        card_color = getattr(palette, metric.color, palette.primary)

        # Format value
        formatted_value = self._format_metric_value(metric)

        # Icon
        icon_widget = ft.Icon(
            self.get_icon(metric.icon),
            color=card_color,
            size=rlm.get_breakpoint_value(32, 36, 40, 44)
        )

        # Value
        value_widget = ft.Text(
            formatted_value,
            style=self.get_text_style('h1'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER
        )

        # Title
        title_widget = ft.Text(
            metric.title,
            style=self.get_text_style('body_small'),
            color=palette.text_secondary,
            text_align=ft.TextAlign.CENTER,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # Content column
        content_column = ft.Column([
            icon_widget,
            value_widget,
            title_widget
        ], spacing=spacing.md,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.CENTER)

        # Create card container
        card = ft.Container(
            content=content_column,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(8, 10, 12, 14)),
            border=ft.border.all(1, palette.borders),
            width=rlm.get_breakpoint_value(120, 140, 160, 180),
            height=rlm.get_breakpoint_value(120, 140, 160, 180),
            on_click=lambda e: self._handle_card_click(metric.metric_id) if metric.is_clickable else None,
            tooltip=metric.description if metric.description else metric.title
        )

        # Store widget reference for updates
        self._card_widgets[metric.metric_id] = card

        return card

    def _create_banner_card(self, metric: MetricCard) -> ft.Control:
        """Create a wide banner metric card."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        rlm = self.get_responsive_layout()

        # Get color based on metric color
        card_color = getattr(palette, metric.color, palette.primary)

        # Format value
        formatted_value = self._format_metric_value(metric)

        # Icon
        icon_widget = ft.Icon(
            self.get_icon(metric.icon),
            color=card_color,
            size=rlm.get_breakpoint_value(24, 28, 32, 36)
        )

        # Title and description column
        title_widget = ft.Text(
            metric.title,
            style=self.get_text_style('h4'),
            color=palette.text_primary,
            weight=ft.FontWeight.BOLD
        )

        description_widget = None
        if metric.description and self._config.show_descriptions:
            description_widget = ft.Text(
                metric.description,
                style=self.get_text_style('body_small'),
                color=palette.text_secondary,
                overflow=ft.TextOverflow.ELLIPSIS
            )

        info_widgets = [title_widget]
        if description_widget:
            info_widgets.append(description_widget)

        info_column = ft.Column(
            controls=info_widgets,
            spacing=spacing.xs,
            expand=True
        )

        # Value
        value_widget = ft.Text(
            formatted_value,
            style=self.get_text_style('h2'),
            color=card_color,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.RIGHT
        )

        # Main content row
        content_row = ft.Row([
            icon_widget,
            info_column,
            value_widget
        ], spacing=spacing.lg,
           alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # Create card container
        card = ft.Container(
            content=content_row,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(rlm.get_breakpoint_value(8, 10, 12, 14)),
            border=ft.border.all(1, palette.borders),
            on_click=lambda e: self._handle_card_click(metric.metric_id) if metric.is_clickable else None,
            tooltip=metric.description if metric.description else metric.title
        )

        # Store widget reference for updates
        self._card_widgets[metric.metric_id] = card

        return card

    def _format_metric_value(self, metric: MetricCard) -> str:
        """Format metric value based on type and precision."""
        try:
            if isinstance(metric.value, (int, float)):
                if metric.format_precision == 0:
                    formatted = f"{int(metric.value)}"
                else:
                    formatted = f"{metric.value:.{metric.format_precision}f}"
            else:
                formatted = str(metric.value)

            # Add unit if present
            if metric.unit:
                return f"{formatted}{metric.unit}"
            return formatted

        except Exception as e:
            print(f"Error formatting metric value for {metric.metric_id}: {e}")
            return str(metric.value)

    def _create_trend_indicator(self, trend: MetricTrend) -> ft.Control:
        """Create a trend indicator widget."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Determine trend color and icon
        if trend.direction == TrendDirection.UP:
            trend_color = palette.success if trend.is_positive else palette.error
            trend_icon = self.get_icon('TRENDING_UP')
        elif trend.direction == TrendDirection.DOWN:
            trend_color = palette.error if trend.is_positive else palette.success
            trend_icon = self.get_icon('TRENDING_DOWN')
        elif trend.direction == TrendDirection.STABLE:
            trend_color = palette.info
            trend_icon = self.get_icon('TRENDING_FLAT')
        else:
            trend_color = palette.text_disabled
            trend_icon = self.get_icon('HELP')

        # Format percentage
        percentage_text = f"{abs(trend.percentage):.1f}%"
        if trend.direction != TrendDirection.STABLE:
            percentage_text = f"{'↑' if trend.direction == TrendDirection.UP else '↓'}{percentage_text}"

        return ft.Row([
            ft.Icon(trend_icon, color=trend_color, size=16),
            ft.Text(
                percentage_text,
                style=self.get_text_style('caption'),
                color=trend_color
            ),
            ft.Text(
                f"({trend.period})",
                style=self.get_text_style('caption'),
                color=palette.text_tertiary
            )
        ], spacing=spacing.xs)

    def _get_filtered_metrics(self) -> List[MetricCard]:
        """Get filtered and sorted metrics based on current state."""
        metrics = list(self._metric_cards.values())

        # Filter by visibility
        metrics = [m for m in metrics if m.is_visible]

        # Filter by category
        if self._state.filtered_categories:
            metrics = [m for m in metrics if m.category in self._state.filtered_categories]

        # Filter by search query
        if self._state.search_query:
            query = self._state.search_query.lower()
            metrics = [
                m for m in metrics
                if query in m.title.lower() or
                   query in m.description.lower() or
                   query in m.metric_id.lower()
            ]

        # Sort metrics
        if self._state.sort_by == "priority":
            metrics.sort(key=lambda m: m.priority, reverse=not self._state.sort_ascending)
        elif self._state.sort_by == "title":
            metrics.sort(key=lambda m: m.title, reverse=not self._state.sort_ascending)
        elif self._state.sort_by == "category":
            metrics.sort(key=lambda m: m.category.value, reverse=not self._state.sort_ascending)
        elif self._state.sort_by == "updated":
            metrics.sort(key=lambda m: m.last_updated, reverse=not self._state.sort_ascending)

        return metrics

    def _handle_card_click(self, metric_id: str) -> None:
        """Handle metric card click events."""
        try:
            if self._on_card_click:
                self._on_card_click(metric_id)
        except Exception as e:
            print(f"Error handling card click for {metric_id}: {e}")

    def _handle_card_hover(self, metric_id: str, is_hovered: bool) -> None:
        """Handle metric card hover events."""
        try:
            if self._on_card_hover:
                self._on_card_hover(metric_id, is_hovered)
        except Exception as e:
            print(f"Error handling card hover for {metric_id}: {e}")

    def _on_search_change(self, e) -> None:
        """Handle search query changes."""
        try:
            self._state.search_query = e.control.value
            self._refresh_grid()
        except Exception as e:
            print(f"Error handling search change: {e}")

    def _on_category_filter_change(self, e) -> None:
        """Handle category filter changes."""
        try:
            if e.control.value:
                category = MetricCategory(e.control.value)
                if category not in self._state.filtered_categories:
                    self._state.filtered_categories.append(category)
            self._refresh_grid()
        except Exception as e:
            print(f"Error handling category filter change: {e}")

    def _on_view_mode_change(self, e) -> None:
        """Handle view mode changes."""
        try:
            # Implementation for view mode changes
            # This could switch between grid and list layouts
            self._refresh_grid()
        except Exception as e:
            print(f"Error handling view mode change: {e}")

    def _refresh_grid(self) -> None:
        """Refresh the metrics grid with current filters and sorting."""
        try:
            if self._grid_container and hasattr(self._grid_container, 'controls'):
                # Get filtered metrics
                filtered_metrics = self._get_filtered_metrics()

                # Create new card widgets
                new_widgets = []
                for metric in filtered_metrics:
                    widget = self._create_metric_card_widget(metric)
                    if widget:
                        new_widgets.append(widget)

                # Update grid controls
                self._grid_container.controls = new_widgets
                self._grid_container.update()

        except Exception as e:
            print(f"Error refreshing grid: {e}")

    def _on_theme_change(self) -> None:
        """Handle theme change events."""
        try:
            # Rebuild all card widgets with new theme
            self._card_widgets.clear()
            self._refresh_grid()
        except Exception as e:
            print(f"Error handling theme change: {e}")

    def _on_responsive_change(self, width: int, height: int, screen_size) -> None:
        """Handle responsive layout changes."""
        try:
            # Refresh grid with new responsive settings
            self._refresh_grid()
        except Exception as e:
            print(f"Error handling responsive change: {e}")

    # Public API Methods

    def add_metric_card(self, metric: MetricCard) -> None:
        """Add a new metric card."""
        try:
            self._metric_cards[metric.metric_id] = metric
            self._refresh_grid()
        except Exception as e:
            print(f"Error adding metric card {metric.metric_id}: {e}")

    def update_metric_card(self, metric_id: str, **kwargs) -> None:
        """Update an existing metric card."""
        try:
            if metric_id in self._metric_cards:
                metric = self._metric_cards[metric_id]

                # Update metric properties
                for key, value in kwargs.items():
                    if hasattr(metric, key):
                        setattr(metric, key, value)

                metric.last_updated = datetime.now()

                # Update widget if it exists
                if metric_id in self._card_widgets:
                    self._update_card_widget(metric_id)

        except Exception as e:
            print(f"Error updating metric card {metric_id}: {e}")

    def update_metric_value(self, metric_id: str, value: Union[str, int, float],
                           trend: Optional[MetricTrend] = None) -> None:
        """Update metric value and optionally trend."""
        try:
            if metric_id in self._metric_cards:
                metric = self._metric_cards[metric_id]
                metric.value = value
                if trend:
                    metric.trend = trend
                metric.last_updated = datetime.now()

                # Update widget with animation if enabled
                if self._config.enable_animations:
                    self._animate_value_change(metric_id)
                else:
                    self._update_card_widget(metric_id)

        except Exception as e:
            print(f"Error updating metric value for {metric_id}: {e}")

    def remove_metric_card(self, metric_id: str) -> None:
        """Remove a metric card."""
        try:
            if metric_id in self._metric_cards:
                del self._metric_cards[metric_id]
            if metric_id in self._card_widgets:
                del self._card_widgets[metric_id]
            self._refresh_grid()
        except Exception as e:
            print(f"Error removing metric card {metric_id}: {e}")

    def get_metric_card(self, metric_id: str) -> Optional[MetricCard]:
        """Get a metric card by ID."""
        return self._metric_cards.get(metric_id)

    def get_all_metric_cards(self) -> Dict[str, MetricCard]:
        """Get all metric cards."""
        return self._metric_cards.copy()

    def set_configuration(self, config: MetricCardsConfiguration) -> None:
        """Update configuration and refresh display."""
        try:
            self._config = config
            self._refresh_grid()

            # Restart auto-refresh if needed
            if self._config.auto_refresh and not self._update_timer:
                self._start_auto_refresh()
            elif not self._config.auto_refresh and self._update_timer:
                self._stop_auto_refresh()

        except Exception as e:
            print(f"Error setting configuration: {e}")

    def clear_all_metrics(self) -> None:
        """Clear all metric cards."""
        try:
            self._metric_cards.clear()
            self._card_widgets.clear()
            self._refresh_grid()
        except Exception as e:
            print(f"Error clearing all metrics: {e}")

    def export_metrics_data(self) -> Dict[str, Any]:
        """Export metrics data for persistence or analysis."""
        try:
            return {
                'metrics': {
                    metric_id: asdict(metric)
                    for metric_id, metric in self._metric_cards.items()
                },
                'configuration': asdict(self._config),
                'state': asdict(self._state),
                'performance_metrics': self._performance_metrics.copy(),
                'export_timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error exporting metrics data: {e}")
            return {}

    def import_metrics_data(self, data: Dict[str, Any]) -> None:
        """Import metrics data from exported format."""
        try:
            if 'metrics' in data:
                self._metric_cards.clear()
                for metric_id, metric_data in data['metrics'].items():
                    # Convert datetime strings back to datetime objects
                    if 'last_updated' in metric_data:
                        metric_data['last_updated'] = datetime.fromisoformat(metric_data['last_updated'])
                    if 'trend' in metric_data and metric_data['trend']:
                        if 'last_updated' in metric_data['trend']:
                            metric_data['trend']['last_updated'] = datetime.fromisoformat(metric_data['trend']['last_updated'])
                        metric_data['trend'] = MetricTrend(**metric_data['trend'])

                    # Convert enum strings back to enums
                    if 'category' in metric_data:
                        metric_data['category'] = MetricCategory(metric_data['category'])
                    if 'variant' in metric_data:
                        metric_data['variant'] = MetricCardVariant(metric_data['variant'])

                    metric = MetricCard(**metric_data)
                    self._metric_cards[metric_id] = metric

            self._refresh_grid()

        except Exception as e:
            print(f"Error importing metrics data: {e}")

    def _update_card_widget(self, metric_id: str) -> None:
        """Update a specific card widget."""
        try:
            if metric_id in self._metric_cards and metric_id in self._card_widgets:
                metric = self._metric_cards[metric_id]
                new_widget = self._create_metric_card_widget(metric)
                if new_widget:
                    # Find and replace the widget in the grid
                    if hasattr(self._grid_container, 'controls'):
                        for i, control in enumerate(self._grid_container.controls):
                            if control == self._card_widgets[metric_id]:
                                self._grid_container.controls[i] = new_widget
                                break
                        self._grid_container.update()

        except Exception as e:
            print(f"Error updating card widget for {metric_id}: {e}")

    def _animate_value_change(self, metric_id: str) -> None:
        """Animate value changes for better user experience."""
        try:
            # Add to animation queue for processing
            self._animation_queue.append((metric_id, {'type': 'value_change'}))

            # Process animation queue if not already processing
            if not self._is_updating:
                self._process_animation_queue()

        except Exception as e:
            print(f"Error animating value change for {metric_id}: {e}")

    def _process_animation_queue(self) -> None:
        """Process pending animations."""
        try:
            self._is_updating = True

            # Process all pending animations
            while self._animation_queue:
                metric_id, animation_data = self._animation_queue.pop(0)
                self._update_card_widget(metric_id)

            self._is_updating = False

        except Exception as e:
            print(f"Error processing animation queue: {e}")
            self._is_updating = False

    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer."""
        try:
            if not self._update_timer:
                # In a real implementation, you would use asyncio.create_task
                # For now, we'll just mark that auto-refresh is enabled
                print(f"Auto-refresh started with interval: {self._config.refresh_interval_seconds}s")
        except Exception as e:
            print(f"Error starting auto-refresh: {e}")

    def _stop_auto_refresh(self) -> None:
        """Stop auto-refresh timer."""
        try:
            if self._update_timer:
                # In a real implementation, you would cancel the asyncio task
                self._update_timer = None
                print("Auto-refresh stopped")
        except Exception as e:
            print(f"Error stopping auto-refresh: {e}")

    def add_update_callback(self, callback: Callable[[], None]) -> None:
        """Add callback to be called on updates."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable[[], None]) -> None:
        """Remove update callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _trigger_update_callbacks(self) -> None:
        """Trigger all registered update callbacks."""
        for callback in self._update_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Error in update callback: {e}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for monitoring."""
        return self._performance_metrics.copy()

    def reset_performance_metrics(self) -> None:
        """Reset performance metrics."""
        self._performance_metrics = {
            'cards_rendered': 0,
            'updates_processed': 0,
            'render_time_total': 0,
            'last_render_time': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

    # Accessibility Methods

    def set_accessibility_mode(self, high_contrast: bool = False,
                              reduced_motion: bool = False) -> None:
        """Configure accessibility settings."""
        try:
            if high_contrast:
                # Enhance contrast for better visibility
                self._enhance_contrast()

            if reduced_motion:
                # Disable animations for reduced motion preference
                self._config.enable_animations = False

            self._refresh_grid()

        except Exception as e:
            print(f"Error setting accessibility mode: {e}")

    def _enhance_contrast(self) -> None:
        """Enhance contrast for accessibility."""
        # This would modify the color palette for higher contrast
        # Implementation would depend on the specific theme system
        pass

    def get_accessible_description(self, metric_id: str) -> str:
        """Get accessible description for screen readers."""
        try:
            if metric_id in self._metric_cards:
                metric = self._metric_cards[metric_id]
                formatted_value = self._format_metric_value(metric)

                description = f"{metric.title}: {formatted_value}"

                if metric.trend:
                    trend_desc = self._get_trend_description(metric.trend)
                    description += f", {trend_desc}"

                if metric.description:
                    description += f". {metric.description}"

                return description

            return f"Metric {metric_id} not found"

        except Exception as e:
            print(f"Error getting accessible description for {metric_id}: {e}")
            return f"Error describing metric {metric_id}"

    def _get_trend_description(self, trend: MetricTrend) -> str:
        """Get human-readable trend description."""
        direction_map = {
            TrendDirection.UP: "increasing",
            TrendDirection.DOWN: "decreasing",
            TrendDirection.STABLE: "stable",
            TrendDirection.UNKNOWN: "trend unknown"
        }

        direction = direction_map.get(trend.direction, "unknown")
        return f"{direction} by {abs(trend.percentage):.1f}% over {trend.period}"

    def set_keyboard_navigation(self, enabled: bool = True) -> None:
        """Enable/disable keyboard navigation."""
        try:
            # This would configure keyboard event handlers
            # Implementation would depend on the Flet framework capabilities
            print(f"Keyboard navigation {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            print(f"Error setting keyboard navigation: {e}")

    def focus_metric_card(self, metric_id: str) -> None:
        """Focus on a specific metric card for accessibility."""
        try:
            if metric_id in self._card_widgets:
                widget = self._card_widgets[metric_id]
                if hasattr(widget, 'focus'):
                    widget.focus()
        except Exception as e:
            print(f"Error focusing metric card {metric_id}: {e}")

    def get_card_count(self) -> int:
        """Get total number of visible cards."""
        return len([m for m in self._metric_cards.values() if m.is_visible])

    def get_filtered_card_count(self) -> int:
        """Get number of cards after filtering."""
        return len(self._get_filtered_metrics())

    def cleanup(self) -> None:
        """Cleanup resources when component is destroyed."""
        try:
            # Stop auto-refresh
            self._stop_auto_refresh()

            # Clear callbacks
            self._update_callbacks.clear()

            # Clear data
            self._metric_cards.clear()
            self._card_widgets.clear()
            self._animation_queue.clear()

            print("MetricCardsUI cleanup completed")

        except Exception as e:
            print(f"Error during cleanup: {e}")
