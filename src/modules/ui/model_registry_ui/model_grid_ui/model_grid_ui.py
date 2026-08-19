"""
Module: model_grid_ui
Description: Responsive model grid interface with comprehensive model management capabilities.
            Provides modern grid view of trained models with performance metrics, status indicators,
            version information, and batch operations. Features theme-aware styling, accessibility
            compliance, and responsive design that adapts to different screen sizes and device capabilities.
Phase: 4
Location: /src/modules/ui/model_registry_ui/model_grid_ui/model_grid_ui.py
"""

# Standard library imports
import asyncio
import logging
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
from dataclasses import dataclass, field

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl

# Database imports
try:
    from src.modules.database.model_repository_db.model_dao_db.model_dao_db import (
        ModelDAODB,
        ModelMetadata,
        ModelArchitecture,
        ModelStatus,
        QuantizationType
    )
    from src.modules.database.model_repository_db.model_versions_db.model_versions_db import (
        ModelVersionsDB,
        ModelVersion
    )
    from src.modules.database.model_repository_db.checkpoint_storage_db.checkpoint_storage_db import (
        CheckpointStorageDB,
        CheckpointMetadata
    )
    DATABASE_AVAILABLE = True
except ImportError:
    ModelDAODB = None
    ModelMetadata = None
    ModelArchitecture = None
    ModelStatus = None
    QuantizationType = None
    ModelVersionsDB = None
    ModelVersion = None
    CheckpointStorageDB = None
    CheckpointMetadata = None
    DATABASE_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


class GridViewMode(Enum):
    """Model grid view modes."""
    THUMBNAIL = "thumbnail"
    COMPACT = "compact"
    DETAILED = "detailed"
    LIST = "list"


class GridSortOption(Enum):
    """Model grid sorting options."""
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"
    PERFORMANCE_ASC = "performance_asc"
    PERFORMANCE_DESC = "performance_desc"
    SIZE_ASC = "size_asc"
    SIZE_DESC = "size_desc"
    STATUS_ASC = "status_asc"
    STATUS_DESC = "status_desc"


class GridFilterOption(Enum):
    """Model grid filtering options."""
    ALL = "all"
    TRAINING = "training"
    COMPLETED = "completed"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ARCHIVED = "archived"
    RECENT = "recent"
    HIGH_PERFORMANCE = "high_performance"


class GridSelectionMode(Enum):
    """Model grid selection modes."""
    NONE = "none"
    SINGLE = "single"
    MULTIPLE = "multiple"


@dataclass
class ModelGridItem:
    """Model grid item data structure."""
    model_id: str
    name: str
    version: str
    architecture: str
    status: str
    performance_score: Optional[float] = None
    model_size_mb: Optional[float] = None
    parameters_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    thumbnail_path: Optional[str] = None
    is_selected: bool = False
    is_favorite: bool = False
    deployment_status: Optional[str] = None
    training_progress: Optional[float] = None
    last_checkpoint: Optional[str] = None
    performance_metrics: Optional[Dict[str, Any]] = None


@dataclass
class GridConfig:
    """Configuration for model grid display."""
    view_mode: GridViewMode = GridViewMode.DETAILED
    sort_option: GridSortOption = GridSortOption.DATE_DESC
    filter_option: GridFilterOption = GridFilterOption.ALL
    selection_mode: GridSelectionMode = GridSelectionMode.MULTIPLE
    show_thumbnails: bool = True
    show_performance_metrics: bool = True
    show_status_indicators: bool = True
    show_version_info: bool = True
    show_deployment_status: bool = True
    show_training_progress: bool = True
    enable_drag_drop: bool = True
    enable_context_menu: bool = True
    enable_keyboard_navigation: bool = True
    auto_refresh: bool = True
    refresh_interval: int = 30  # seconds
    page_size: int = 24
    enable_search: bool = True
    enable_bulk_operations: bool = True
    card_aspect_ratio: float = 1.3
    enable_favorites: bool = True
    enable_quick_actions: bool = True
    show_performance_charts: bool = True
    enable_model_comparison: bool = True


class ModelGridUI(ThemeAwareUserControl):
    """
    Responsive model grid interface for comprehensive model management.

    Provides modern grid view of trained models with performance metrics, status indicators,
    version information, and batch operations. Features theme-aware styling, accessibility
    compliance, and responsive design.

    Features:
    - Responsive grid layout with breakpoint-aware columns and spacing
    - Multiple view modes (thumbnail, compact, detailed, list)
    - Advanced sorting and filtering with real-time updates
    - Model selection with multiple selection modes
    - Drag-and-drop support for model operations
    - Context menus with batch operations
    - Keyboard navigation and accessibility compliance
    - Theme-aware styling with smooth animations
    - Integration with model database and training pipeline
    - Real-time status updates and progress indicators
    - Performance metrics and benchmark results
    - Version management and deployment tracking
    - Search functionality with highlighting
    - Pagination with infinite scroll support
    """

    def __init__(self,
                 config: Optional[GridConfig] = None,
                 on_model_selected: Optional[Callable[[List[ModelGridItem]], None]] = None,
                 on_model_double_click: Optional[Callable[[ModelGridItem], None]] = None,
                 on_model_context_menu: Optional[Callable[[ModelGridItem, ft.TapEvent], None]] = None,
                 on_bulk_operation: Optional[Callable[[str, List[ModelGridItem]], None]] = None,
                 **kwargs):
        """
        Initialize the model grid UI.

        Args:
            config: Grid configuration settings
            on_model_selected: Callback for model selection changes
            on_model_double_click: Callback for model double-click
            on_model_context_menu: Callback for model context menu
            on_bulk_operation: Callback for bulk operations
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)

        # Configuration and callbacks
        self._config = config or GridConfig()
        self._on_model_selected = on_model_selected
        self._on_model_double_click = on_model_double_click
        self._on_model_context_menu = on_model_context_menu
        self._on_bulk_operation = on_bulk_operation

        # Data management
        self._models: List[ModelGridItem] = []
        self._filtered_models: List[ModelGridItem] = []
        self._selected_models: Set[str] = set()
        self._current_page = 0
        self._total_pages = 0
        self._search_query = ""
        self._is_loading = False

        # Database connections
        self._model_dao = None
        self._versions_db = None
        self._checkpoint_db = None

        # UI components
        self._search_bar = None
        self._view_mode_selector = None
        self._sort_selector = None
        self._filter_selector = None
        self._grid_container = None
        self._pagination_controls = None
        self._selection_toolbar = None
        self._loading_indicator = None

        # State management
        self._refresh_timer = None
        self._debounce_timer = None
        self._last_refresh = None

        # Performance optimization
        self._visible_items_cache: Dict[str, ft.Control] = {}
        self._thumbnail_cache: Dict[str, str] = {}

        self._initialize_database()
        self._build_ui()

    def _initialize_database(self) -> None:
        """Initialize database connections."""
        try:
            if DATABASE_AVAILABLE:
                self._model_dao = ModelDAODB()
                self._versions_db = ModelVersionsDB()
                self._checkpoint_db = CheckpointStorageDB()
                logger.info("Model grid database connections initialized")
            else:
                logger.warning("Model database not available, using mock data")
        except Exception as e:
            logger.error(f"Failed to initialize model grid database: {e}")
            self._model_dao = None
            self._versions_db = None
            self._checkpoint_db = None

    def _build_ui(self) -> None:
        """Build the model grid user interface."""
        try:
            # Main container with responsive layout
            self.content = ft.Column(
                controls=[
                    self._build_header_section(),
                    self._build_toolbar_section(),
                    self._build_grid_section(),
                    self._build_footer_section()
                ],
                spacing=self.get_spacing("md"),
                expand=True
            )

            # Start auto-refresh if enabled
            if self._config.auto_refresh:
                self._start_auto_refresh()

        except Exception as e:
            logger.error(f"Error building model grid UI: {e}")
            self.content = self._build_error_state(str(e))

    def _build_header_section(self) -> ft.Control:
        """Build the header section with title and quick stats."""
        try:
            # Get responsive breakpoint
            breakpoint = self.get_responsive_breakpoint()

            # Title and stats
            title_text = self.create_themed_component(
                "text",
                "heading",
                text="Model Registry",
                size=self.get_text_style("heading_large").size,
                weight=self.get_text_style("heading_large").weight
            )

            stats_container = ft.Row(
                controls=[
                    self._build_stat_chip("Total Models", len(self._models)),
                    self._build_stat_chip("Training", self._count_models_by_status("training")),
                    self._build_stat_chip("Deployed", self._count_models_by_status("deployed")),
                    self._build_stat_chip("Selected", len(self._selected_models))
                ],
                spacing=self.get_spacing("sm"),
                wrap=True
            )

            # Responsive layout
            if breakpoint.is_mobile:
                return ft.Column(
                    controls=[title_text, stats_container],
                    spacing=self.get_spacing("sm")
                )
            else:
                return ft.Row(
                    controls=[
                        ft.Container(content=title_text, expand=True),
                        stats_container
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )

        except Exception as e:
            logger.error(f"Error building header section: {e}")
            return ft.Container()

    def _build_stat_chip(self, label: str, value: int) -> ft.Control:
        """Build a statistics chip."""
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        label,
                        size=self.get_text_style("body_small").size,
                        color=self.get_color("on_surface_variant")
                    ),
                    ft.Text(
                        str(value),
                        size=self.get_text_style("body_medium").size,
                        weight=ft.FontWeight.BOLD,
                        color=self.get_color("primary")
                    )
                ],
                spacing=self.get_spacing("xs"),
                tight=True
            ),
            padding=ft.padding.symmetric(
                horizontal=self.get_spacing("sm"),
                vertical=self.get_spacing("xs")
            ),
            bgcolor=self.get_color("surface_variant"),
            border_radius=self.get_border_radius("sm"),
            border=ft.border.all(1, self.get_color("outline_variant"))
        )

    def _count_models_by_status(self, status: str) -> int:
        """Count models by status."""
        return sum(1 for model in self._models if model.status.lower() == status.lower())

    def _build_toolbar_section(self) -> ft.Control:
        """Build the toolbar section with search, filters, and view controls."""
        try:
            # Search bar
            self._search_bar = ft.TextField(
                hint_text="Search models...",
                prefix_icon=ft.Icons.SEARCH,
                on_change=self._on_search_changed,
                expand=True,
                bgcolor=self.get_color("surface"),
                border_color=self.get_color("outline_variant"),
                focused_border_color=self.get_color("primary")
            )

            # View mode selector
            self._view_mode_selector = ft.Dropdown(
                options=[
                    ft.dropdown.Option("thumbnail", "Thumbnail"),
                    ft.dropdown.Option("compact", "Compact"),
                    ft.dropdown.Option("detailed", "Detailed"),
                    ft.dropdown.Option("list", "List")
                ],
                value=self._config.view_mode.value,
                on_change=self._on_view_mode_changed,
                width=120,
                bgcolor=self.get_color("surface"),
                border_color=self.get_color("outline_variant")
            )

            # Sort selector
            self._sort_selector = ft.Dropdown(
                options=[
                    ft.dropdown.Option("date_desc", "Newest First"),
                    ft.dropdown.Option("date_asc", "Oldest First"),
                    ft.dropdown.Option("name_asc", "Name A-Z"),
                    ft.dropdown.Option("name_desc", "Name Z-A"),
                    ft.dropdown.Option("performance_desc", "Best Performance"),
                    ft.dropdown.Option("size_asc", "Smallest First")
                ],
                value=self._config.sort_option.value,
                on_change=self._on_sort_changed,
                width=150,
                bgcolor=self.get_color("surface"),
                border_color=self.get_color("outline_variant")
            )

            # Filter selector
            self._filter_selector = ft.Dropdown(
                options=[
                    ft.dropdown.Option("all", "All Models"),
                    ft.dropdown.Option("training", "Training"),
                    ft.dropdown.Option("completed", "Completed"),
                    ft.dropdown.Option("deployed", "Deployed"),
                    ft.dropdown.Option("failed", "Failed"),
                    ft.dropdown.Option("recent", "Recent")
                ],
                value=self._config.filter_option.value,
                on_change=self._on_filter_changed,
                width=130,
                bgcolor=self.get_color("surface"),
                border_color=self.get_color("outline_variant")
            )

            # Responsive toolbar layout
            breakpoint = self.get_responsive_breakpoint()

            if breakpoint.is_mobile:
                return ft.Column(
                    controls=[
                        self._search_bar,
                        ft.Row(
                            controls=[
                                self._view_mode_selector,
                                self._sort_selector,
                                self._filter_selector
                            ],
                            spacing=self.get_spacing("sm")
                        )
                    ],
                    spacing=self.get_spacing("sm")
                )
            else:
                return ft.Row(
                    controls=[
                        self._search_bar,
                        self._view_mode_selector,
                        self._sort_selector,
                        self._filter_selector
                    ],
                    spacing=self.get_spacing("sm")
                )

        except Exception as e:
            logger.error(f"Error building toolbar section: {e}")
            return ft.Container()

    def _build_grid_section(self) -> ft.Control:
        """Build the main grid section with models."""
        try:
            # Loading indicator
            self._loading_indicator = ft.ProgressRing(
                visible=False,
                width=40,
                height=40,
                color=self.get_color("primary")
            )

            # Grid container
            self._grid_container = ft.Container(
                content=self._build_grid_content(),
                expand=True,
                padding=self.get_spacing("sm")
            )

            # Selection toolbar (shown when models are selected)
            self._selection_toolbar = ft.Container(
                content=self._build_selection_toolbar(),
                visible=False,
                bgcolor=self.get_color("primary_container"),
                padding=self.get_spacing("md"),
                border_radius=self.get_border_radius("md")
            )

            return ft.Column(
                controls=[
                    self._selection_toolbar,
                    ft.Stack(
                        controls=[
                            self._grid_container,
                            ft.Container(
                                content=self._loading_indicator,
                                alignment=ft.alignment.center
                            )
                        ],
                        expand=True
                    )
                ],
                spacing=self.get_spacing("sm"),
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building grid section: {e}")
            return ft.Container()

    def _build_grid_content(self) -> ft.Control:
        """Build the grid content based on current view mode."""
        try:
            if not self._filtered_models:
                return self._build_empty_state()

            # Get current page models
            start_idx = self._current_page * self._config.page_size
            end_idx = start_idx + self._config.page_size
            page_models = self._filtered_models[start_idx:end_idx]

            # Build grid based on view mode
            if self._config.view_mode == GridViewMode.THUMBNAIL:
                return self._build_thumbnail_grid(page_models)
            elif self._config.view_mode == GridViewMode.COMPACT:
                return self._build_compact_grid(page_models)
            elif self._config.view_mode == GridViewMode.LIST:
                return self._build_list_grid(page_models)
            else:  # DETAILED
                return self._build_detailed_grid(page_models)

        except Exception as e:
            logger.error(f"Error building grid content: {e}")
            return self._build_error_state(str(e))

    def _build_thumbnail_grid(self, models: List[ModelGridItem]) -> ft.Control:
        """Build thumbnail grid layout."""
        try:
            breakpoint = self.get_responsive_breakpoint()

            # Determine columns based on breakpoint
            if breakpoint.is_mobile:
                columns = 2
            elif breakpoint.is_tablet:
                columns = 3
            elif breakpoint.is_desktop:
                columns = 4
            else:  # large desktop
                columns = 6

            # Build grid rows
            rows = []
            for i in range(0, len(models), columns):
                row_models = models[i:i + columns]
                row_controls = []

                for model in row_models:
                    card = self._build_thumbnail_card(model)
                    row_controls.append(ft.Container(content=card, expand=True))

                # Fill remaining columns with empty containers
                while len(row_controls) < columns:
                    row_controls.append(ft.Container(expand=True))

                rows.append(ft.Row(
                    controls=row_controls,
                    spacing=self.get_spacing("sm")
                ))

            return ft.Column(
                controls=rows,
                spacing=self.get_spacing("sm"),
                scroll=ft.ScrollMode.AUTO
            )

        except Exception as e:
            logger.error(f"Error building thumbnail grid: {e}")
            return ft.Container()

    def _build_detailed_grid(self, models: List[ModelGridItem]) -> ft.Control:
        """Build detailed grid layout."""
        try:
            breakpoint = self.get_responsive_breakpoint()

            # Determine columns based on breakpoint
            if breakpoint.is_mobile:
                columns = 1
            elif breakpoint.is_tablet:
                columns = 2
            else:  # desktop and large desktop
                columns = 3

            # Build grid rows
            rows = []
            for i in range(0, len(models), columns):
                row_models = models[i:i + columns]
                row_controls = []

                for model in row_models:
                    card = self._build_detailed_card(model)
                    row_controls.append(ft.Container(content=card, expand=True))

                # Fill remaining columns with empty containers
                while len(row_controls) < columns:
                    row_controls.append(ft.Container(expand=True))

                rows.append(ft.Row(
                    controls=row_controls,
                    spacing=self.get_spacing("md")
                ))

            return ft.Column(
                controls=rows,
                spacing=self.get_spacing("md"),
                scroll=ft.ScrollMode.AUTO
            )

        except Exception as e:
            logger.error(f"Error building detailed grid: {e}")
            return ft.Container()

    def _build_compact_grid(self, models: List[ModelGridItem]) -> ft.Control:
        """Build compact grid layout."""
        try:
            breakpoint = self.get_responsive_breakpoint()

            # Determine columns based on breakpoint
            if breakpoint.is_mobile:
                columns = 1
            elif breakpoint.is_tablet:
                columns = 2
            else:  # desktop and large desktop
                columns = 4

            # Build grid rows
            rows = []
            for i in range(0, len(models), columns):
                row_models = models[i:i + columns]
                row_controls = []

                for model in row_models:
                    card = self._build_compact_card(model)
                    row_controls.append(ft.Container(content=card, expand=True))

                # Fill remaining columns with empty containers
                while len(row_controls) < columns:
                    row_controls.append(ft.Container(expand=True))

                rows.append(ft.Row(
                    controls=row_controls,
                    spacing=self.get_spacing("sm")
                ))

            return ft.Column(
                controls=rows,
                spacing=self.get_spacing("sm"),
                scroll=ft.ScrollMode.AUTO
            )

        except Exception as e:
            logger.error(f"Error building compact grid: {e}")
            return ft.Container()

    def _build_list_grid(self, models: List[ModelGridItem]) -> ft.Control:
        """Build list grid layout."""
        try:
            list_items = []

            for model in models:
                list_item = self._build_list_item(model)
                list_items.append(list_item)

            return ft.Column(
                controls=list_items,
                spacing=self.get_spacing("xs"),
                scroll=ft.ScrollMode.AUTO
            )

        except Exception as e:
            logger.error(f"Error building list grid: {e}")
            return ft.Container()

    def _build_thumbnail_card(self, model: ModelGridItem) -> ft.Control:
        """Build thumbnail model card."""
        try:
            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=model.is_selected,
                on_change=lambda e: self._on_model_selection_changed(model.model_id, e.control.value),
                visible=self._config.selection_mode != GridSelectionMode.NONE
            )

            # Model thumbnail or icon
            thumbnail = ft.Container(
                content=ft.Icon(
                    ft.Icons.SMART_TOY,
                    size=48,
                    color=self.get_color("primary")
                ),
                width=80,
                height=80,
                bgcolor=self.get_color("surface_variant"),
                border_radius=self.get_border_radius("md"),
                alignment=ft.alignment.center
            )

            # Model name and version
            name_text = ft.Text(
                model.name,
                size=self.get_text_style("body_medium").size,
                weight=ft.FontWeight.BOLD,
                color=self.get_color("on_surface"),
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            version_text = ft.Text(
                f"v{model.version}",
                size=self.get_text_style("body_small").size,
                color=self.get_color("on_surface_variant"),
                max_lines=1
            )

            # Status indicator
            status_chip = self._build_status_chip(model.status)

            # Performance score
            performance_text = ft.Text(
                f"{model.performance_score:.1f}%" if model.performance_score else "N/A",
                size=self.get_text_style("body_small").size,
                color=self.get_color("primary"),
                weight=ft.FontWeight.BOLD
            )

            # Card content
            card_content = ft.Column(
                controls=[
                    ft.Stack(
                        controls=[
                            thumbnail,
                            ft.Container(
                                content=selection_checkbox,
                                top=5,
                                right=5
                            )
                        ]
                    ),
                    ft.Container(height=self.get_spacing("xs")),
                    name_text,
                    version_text,
                    ft.Container(height=self.get_spacing("xs")),
                    status_chip,
                    performance_text
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=self.get_spacing("xs")
            )

            # Interactive card
            return ft.Card(
                content=ft.Container(
                    content=card_content,
                    padding=self.get_spacing("md"),
                    on_click=lambda e: self._on_model_clicked(model),
                    on_long_press=lambda e: self._on_model_context_menu_triggered(model, e)
                ),
                elevation=2,
                surface_tint_color=self.get_color("surface_tint")
            )

        except Exception as e:
            logger.error(f"Error building thumbnail card for model {model.model_id}: {e}")
            return ft.Container()

    def _build_detailed_card(self, model: ModelGridItem) -> ft.Control:
        """Build detailed model card."""
        try:
            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=model.is_selected,
                on_change=lambda e: self._on_model_selection_changed(model.model_id, e.control.value),
                visible=self._config.selection_mode != GridSelectionMode.NONE
            )

            # Model thumbnail
            thumbnail = ft.Container(
                content=ft.Icon(
                    ft.Icons.SMART_TOY,
                    size=64,
                    color=self.get_color("primary")
                ),
                width=100,
                height=100,
                bgcolor=self.get_color("surface_variant"),
                border_radius=self.get_border_radius("md"),
                alignment=ft.alignment.center
            )

            # Header with name, version, and actions
            header_row = ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                model.name,
                                size=self.get_text_style("title_medium").size,
                                weight=ft.FontWeight.BOLD,
                                color=self.get_color("on_surface")
                            ),
                            ft.Text(
                                f"Version {model.version}",
                                size=self.get_text_style("body_medium").size,
                                color=self.get_color("on_surface_variant")
                            )
                        ],
                        expand=True,
                        spacing=self.get_spacing("xs")
                    ),
                    ft.Row(
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.FAVORITE_BORDER if not model.is_favorite else ft.Icons.FAVORITE,
                                icon_color=self.get_color("primary") if model.is_favorite else self.get_color("on_surface_variant"),
                                on_click=lambda e: self._on_favorite_toggled(model.model_id)
                            ),
                            ft.IconButton(
                                icon=ft.Icons.MORE_VERT,
                                icon_color=self.get_color("on_surface_variant"),
                                on_click=lambda e: self._on_model_context_menu_triggered(model, e)
                            )
                        ],
                        spacing=self.get_spacing("xs")
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )

            # Status and metrics row
            status_metrics_row = ft.Row(
                controls=[
                    self._build_status_chip(model.status),
                    ft.Container(
                        content=ft.Text(
                            model.architecture,
                            size=self.get_text_style("body_small").size,
                            color=self.get_color("on_surface_variant")
                        ),
                        bgcolor=self.get_color("surface_variant"),
                        padding=ft.padding.symmetric(
                            horizontal=self.get_spacing("sm"),
                            vertical=self.get_spacing("xs")
                        ),
                        border_radius=self.get_border_radius("sm")
                    )
                ],
                spacing=self.get_spacing("sm"),
                wrap=True
            )

            # Performance metrics
            metrics_row = ft.Row(
                controls=[
                    self._build_metric_item("Performance", f"{model.performance_score:.1f}%" if model.performance_score else "N/A"),
                    self._build_metric_item("Size", f"{model.model_size_mb:.1f} MB" if model.model_size_mb else "N/A"),
                    self._build_metric_item("Parameters", f"{model.parameters_count:,}" if model.parameters_count else "N/A")
                ],
                spacing=self.get_spacing("md"),
                wrap=True
            )

            # Description
            description_text = ft.Text(
                model.description or "No description available",
                size=self.get_text_style("body_small").size,
                color=self.get_color("on_surface_variant"),
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            # Tags
            tags_row = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            tag,
                            size=self.get_text_style("label_small").size,
                            color=self.get_color("on_primary_container")
                        ),
                        bgcolor=self.get_color("primary_container"),
                        padding=ft.padding.symmetric(
                            horizontal=self.get_spacing("sm"),
                            vertical=self.get_spacing("xs")
                        ),
                        border_radius=self.get_border_radius("sm")
                    )
                    for tag in (model.tags or [])[:3]  # Show max 3 tags
                ],
                spacing=self.get_spacing("xs"),
                wrap=True
            )

            # Card layout
            card_content = ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            thumbnail,
                            ft.Column(
                                controls=[
                                    header_row,
                                    status_metrics_row,
                                    metrics_row,
                                    description_text,
                                    tags_row
                                ],
                                expand=True,
                                spacing=self.get_spacing("sm")
                            )
                        ],
                        spacing=self.get_spacing("md"),
                        cross_axis_alignment=ft.CrossAxisAlignment.START
                    )
                ],
                spacing=self.get_spacing("sm")
            )

            # Interactive card with selection overlay
            return ft.Stack(
                controls=[
                    ft.Card(
                        content=ft.Container(
                            content=card_content,
                            padding=self.get_spacing("md"),
                            on_click=lambda e: self._on_model_clicked(model),
                            on_long_press=lambda e: self._on_model_context_menu_triggered(model, e)
                        ),
                        elevation=2,
                        surface_tint_color=self.get_color("surface_tint")
                    ),
                    ft.Container(
                        content=selection_checkbox,
                        top=self.get_spacing("sm"),
                        right=self.get_spacing("sm")
                    )
                ]
            )

        except Exception as e:
            logger.error(f"Error building detailed card for model {model.model_id}: {e}")
            return ft.Container()

    def _build_compact_card(self, model: ModelGridItem) -> ft.Control:
        """Build compact model card."""
        try:
            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=model.is_selected,
                on_change=lambda e: self._on_model_selection_changed(model.model_id, e.control.value),
                visible=self._config.selection_mode != GridSelectionMode.NONE
            )

            # Model icon
            model_icon = ft.Icon(
                ft.Icons.SMART_TOY,
                size=32,
                color=self.get_color("primary")
            )

            # Model info
            info_column = ft.Column(
                controls=[
                    ft.Text(
                        model.name,
                        size=self.get_text_style("body_medium").size,
                        weight=ft.FontWeight.BOLD,
                        color=self.get_color("on_surface"),
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS
                    ),
                    ft.Row(
                        controls=[
                            ft.Text(
                                f"v{model.version}",
                                size=self.get_text_style("body_small").size,
                                color=self.get_color("on_surface_variant")
                            ),
                            self._build_status_chip(model.status, compact=True)
                        ],
                        spacing=self.get_spacing("sm")
                    )
                ],
                expand=True,
                spacing=self.get_spacing("xs")
            )

            # Performance indicator
            performance_indicator = ft.Container(
                content=ft.Text(
                    f"{model.performance_score:.0f}%" if model.performance_score else "N/A",
                    size=self.get_text_style("body_small").size,
                    color=self.get_color("primary"),
                    weight=ft.FontWeight.BOLD
                ),
                alignment=ft.alignment.center
            )

            # Card content
            card_content = ft.Row(
                controls=[
                    model_icon,
                    info_column,
                    performance_indicator
                ],
                spacing=self.get_spacing("sm"),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )

            # Interactive card with selection overlay
            return ft.Stack(
                controls=[
                    ft.Card(
                        content=ft.Container(
                            content=card_content,
                            padding=self.get_spacing("sm"),
                            on_click=lambda e: self._on_model_clicked(model),
                            on_long_press=lambda e: self._on_model_context_menu_triggered(model, e)
                        ),
                        elevation=1,
                        surface_tint_color=self.get_color("surface_tint")
                    ),
                    ft.Container(
                        content=selection_checkbox,
                        top=5,
                        right=5
                    )
                ]
            )

        except Exception as e:
            logger.error(f"Error building compact card for model {model.model_id}: {e}")
            return ft.Container()

    def _build_list_item(self, model: ModelGridItem) -> ft.Control:
        """Build list item for model."""
        try:
            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=model.is_selected,
                on_change=lambda e: self._on_model_selection_changed(model.model_id, e.control.value),
                visible=self._config.selection_mode != GridSelectionMode.NONE
            )

            # Model icon
            model_icon = ft.Icon(
                ft.Icons.SMART_TOY,
                size=24,
                color=self.get_color("primary")
            )

            # Model name and version
            name_version = ft.Column(
                controls=[
                    ft.Text(
                        model.name,
                        size=self.get_text_style("body_medium").size,
                        weight=ft.FontWeight.BOLD,
                        color=self.get_color("on_surface")
                    ),
                    ft.Text(
                        f"Version {model.version}",
                        size=self.get_text_style("body_small").size,
                        color=self.get_color("on_surface_variant")
                    )
                ],
                spacing=2
            )

            # Architecture
            architecture_text = ft.Text(
                model.architecture,
                size=self.get_text_style("body_small").size,
                color=self.get_color("on_surface_variant")
            )

            # Status
            status_chip = self._build_status_chip(model.status, compact=True)

            # Performance
            performance_text = ft.Text(
                f"{model.performance_score:.1f}%" if model.performance_score else "N/A",
                size=self.get_text_style("body_small").size,
                color=self.get_color("primary"),
                weight=ft.FontWeight.BOLD
            )

            # Created date
            created_text = ft.Text(
                model.created_at.strftime("%Y-%m-%d") if model.created_at else "Unknown",
                size=self.get_text_style("body_small").size,
                color=self.get_color("on_surface_variant")
            )

            # Actions
            actions_row = ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.FAVORITE_BORDER if not model.is_favorite else ft.Icons.FAVORITE,
                        icon_color=self.get_color("primary") if model.is_favorite else self.get_color("on_surface_variant"),
                        icon_size=20,
                        on_click=lambda e: self._on_favorite_toggled(model.model_id)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.MORE_VERT,
                        icon_color=self.get_color("on_surface_variant"),
                        icon_size=20,
                        on_click=lambda e: self._on_model_context_menu_triggered(model, e)
                    )
                ],
                spacing=0
            )

            # List item content
            list_content = ft.Row(
                controls=[
                    selection_checkbox,
                    model_icon,
                    ft.Container(content=name_version, width=200),
                    ft.Container(content=architecture_text, width=120),
                    status_chip,
                    ft.Container(content=performance_text, width=80),
                    ft.Container(content=created_text, width=100),
                    actions_row
                ],
                spacing=self.get_spacing("md"),
                alignment=ft.MainAxisAlignment.START
            )

            # Interactive container
            return ft.Container(
                content=list_content,
                padding=self.get_spacing("sm"),
                border=ft.border.only(bottom=ft.BorderSide(1, self.get_color("outline_variant"))),
                on_click=lambda e: self._on_model_clicked(model),
                on_long_press=lambda e: self._on_model_context_menu_triggered(model, e)
            )

        except Exception as e:
            logger.error(f"Error building list item for model {model.model_id}: {e}")
            return ft.Container()

    def _build_status_chip(self, status: str, compact: bool = False) -> ft.Control:
        """Build status indicator chip."""
        try:
            # Status color mapping
            status_colors = {
                "training": (self.get_color("warning"), self.get_color("on_warning")),
                "completed": (self.get_color("success"), self.get_color("on_success")),
                "deployed": (self.get_color("primary"), self.get_color("on_primary")),
                "failed": (self.get_color("error"), self.get_color("on_error")),
                "archived": (self.get_color("surface_variant"), self.get_color("on_surface_variant"))
            }

            bg_color, text_color = status_colors.get(status.lower(),
                                                   (self.get_color("surface_variant"), self.get_color("on_surface_variant")))

            # Status icon mapping
            status_icons = {
                "training": ft.Icons.HOURGLASS_EMPTY,
                "completed": ft.Icons.CHECK_CIRCLE,
                "deployed": ft.Icons.CLOUD_DONE,
                "failed": ft.Icons.ERROR,
                "archived": ft.Icons.ARCHIVE
            }

            icon = status_icons.get(status.lower(), ft.Icons.HELP)

            if compact:
                return ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon, size=12, color=text_color),
                            ft.Text(
                                status.title(),
                                size=self.get_text_style("label_small").size,
                                color=text_color
                            )
                        ],
                        spacing=4,
                        tight=True
                    ),
                    bgcolor=bg_color,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    border_radius=self.get_border_radius("sm")
                )
            else:
                return ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon, size=16, color=text_color),
                            ft.Text(
                                status.title(),
                                size=self.get_text_style("body_small").size,
                                color=text_color
                            )
                        ],
                        spacing=self.get_spacing("xs"),
                        tight=True
                    ),
                    bgcolor=bg_color,
                    padding=ft.padding.symmetric(
                        horizontal=self.get_spacing("sm"),
                        vertical=self.get_spacing("xs")
                    ),
                    border_radius=self.get_border_radius("sm")
                )

        except Exception as e:
            logger.error(f"Error building status chip: {e}")
            return ft.Container()

    def _build_metric_item(self, label: str, value: str) -> ft.Control:
        """Build metric display item."""
        return ft.Column(
            controls=[
                ft.Text(
                    label,
                    size=self.get_text_style("label_small").size,
                    color=self.get_color("on_surface_variant")
                ),
                ft.Text(
                    value,
                    size=self.get_text_style("body_small").size,
                    weight=ft.FontWeight.BOLD,
                    color=self.get_color("on_surface")
                )
            ],
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    # Event handlers
    def _on_search_changed(self, e: ft.ControlEvent) -> None:
        """Handle search query changes."""
        try:
            self._search_query = e.control.value.lower()
            self._debounce_search()
        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    def _debounce_search(self) -> None:
        """Debounce search to avoid excessive filtering."""
        try:
            if self._debounce_timer:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(0.3, self._apply_filters_and_sort)
            self._debounce_timer.start()
        except Exception as e:
            logger.error(f"Error debouncing search: {e}")

    def _on_view_mode_changed(self, e: ft.ControlEvent) -> None:
        """Handle view mode changes."""
        try:
            self._config.view_mode = GridViewMode(e.control.value)
            self._refresh_grid()
        except Exception as ex:
            logger.error(f"Error handling view mode change: {ex}")

    def _on_sort_changed(self, e: ft.ControlEvent) -> None:
        """Handle sort option changes."""
        try:
            self._config.sort_option = GridSortOption(e.control.value)
            self._apply_filters_and_sort()
        except Exception as ex:
            logger.error(f"Error handling sort change: {ex}")

    def _on_filter_changed(self, e: ft.ControlEvent) -> None:
        """Handle filter option changes."""
        try:
            self._config.filter_option = GridFilterOption(e.control.value)
            self._apply_filters_and_sort()
        except Exception as ex:
            logger.error(f"Error handling filter change: {ex}")

    def _on_model_clicked(self, model: ModelGridItem) -> None:
        """Handle model click events."""
        try:
            if self._config.selection_mode == GridSelectionMode.SINGLE:
                # Clear previous selections
                for m in self._models:
                    m.is_selected = False
                self._selected_models.clear()

                # Select clicked model
                model.is_selected = True
                self._selected_models.add(model.model_id)

                self._refresh_grid()

                if self._on_model_selected:
                    self._on_model_selected([model])

        except Exception as e:
            logger.error(f"Error handling model click: {e}")

    def _on_model_selection_changed(self, model_id: str, selected: bool) -> None:
        """Handle model selection changes."""
        try:
            # Find and update model
            for model in self._models:
                if model.model_id == model_id:
                    model.is_selected = selected
                    break

            # Update selected set
            if selected:
                self._selected_models.add(model_id)
            else:
                self._selected_models.discard(model_id)

            # Update selection toolbar visibility
            self._update_selection_toolbar()

            # Notify callback
            if self._on_model_selected:
                selected_models = [m for m in self._models if m.is_selected]
                self._on_model_selected(selected_models)

        except Exception as e:
            logger.error(f"Error handling model selection change: {e}")

    def _on_model_context_menu_triggered(self, model: ModelGridItem, e: ft.TapEvent) -> None:
        """Handle model context menu events."""
        try:
            if self._on_model_context_menu:
                self._on_model_context_menu(model, e)
        except Exception as ex:
            logger.error(f"Error handling model context menu: {ex}")

    def _on_favorite_toggled(self, model_id: str) -> None:
        """Handle favorite toggle events."""
        try:
            # Find and update model
            for model in self._models:
                if model.model_id == model_id:
                    model.is_favorite = not model.is_favorite
                    break

            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error handling favorite toggle: {e}")

    # Filtering and sorting methods
    def _apply_filters_and_sort(self) -> None:
        """Apply current filters and sorting to models."""
        try:
            # Start with all models
            filtered_models = self._models.copy()

            # Apply search filter
            if self._search_query:
                filtered_models = [
                    model for model in filtered_models
                    if (self._search_query in model.name.lower() or
                        self._search_query in model.description.lower() if model.description else False or
                        any(self._search_query in tag.lower() for tag in (model.tags or [])))
                ]

            # Apply status filter
            if self._config.filter_option != GridFilterOption.ALL:
                if self._config.filter_option == GridFilterOption.TRAINING:
                    filtered_models = [m for m in filtered_models if m.status.lower() == "training"]
                elif self._config.filter_option == GridFilterOption.COMPLETED:
                    filtered_models = [m for m in filtered_models if m.status.lower() == "completed"]
                elif self._config.filter_option == GridFilterOption.DEPLOYED:
                    filtered_models = [m for m in filtered_models if m.status.lower() == "deployed"]
                elif self._config.filter_option == GridFilterOption.FAILED:
                    filtered_models = [m for m in filtered_models if m.status.lower() == "failed"]
                elif self._config.filter_option == GridFilterOption.ARCHIVED:
                    filtered_models = [m for m in filtered_models if m.status.lower() == "archived"]
                elif self._config.filter_option == GridFilterOption.RECENT:
                    # Models created in last 7 days
                    from datetime import timedelta
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
                    filtered_models = [m for m in filtered_models
                                     if m.created_at and m.created_at > cutoff_date]
                elif self._config.filter_option == GridFilterOption.HIGH_PERFORMANCE:
                    # Models with performance > 80%
                    filtered_models = [m for m in filtered_models
                                     if m.performance_score and m.performance_score > 80.0]

            # Apply sorting
            if self._config.sort_option == GridSortOption.NAME_ASC:
                filtered_models.sort(key=lambda m: m.name.lower())
            elif self._config.sort_option == GridSortOption.NAME_DESC:
                filtered_models.sort(key=lambda m: m.name.lower(), reverse=True)
            elif self._config.sort_option == GridSortOption.DATE_ASC:
                filtered_models.sort(key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc))
            elif self._config.sort_option == GridSortOption.DATE_DESC:
                filtered_models.sort(key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            elif self._config.sort_option == GridSortOption.PERFORMANCE_ASC:
                filtered_models.sort(key=lambda m: m.performance_score or 0.0)
            elif self._config.sort_option == GridSortOption.PERFORMANCE_DESC:
                filtered_models.sort(key=lambda m: m.performance_score or 0.0, reverse=True)
            elif self._config.sort_option == GridSortOption.SIZE_ASC:
                filtered_models.sort(key=lambda m: m.model_size_mb or 0.0)
            elif self._config.sort_option == GridSortOption.SIZE_DESC:
                filtered_models.sort(key=lambda m: m.model_size_mb or 0.0, reverse=True)
            elif self._config.sort_option == GridSortOption.STATUS_ASC:
                filtered_models.sort(key=lambda m: m.status.lower())
            elif self._config.sort_option == GridSortOption.STATUS_DESC:
                filtered_models.sort(key=lambda m: m.status.lower(), reverse=True)

            # Update filtered models and pagination
            self._filtered_models = filtered_models
            self._current_page = 0
            self._total_pages = (len(self._filtered_models) + self._config.page_size - 1) // self._config.page_size

            # Refresh grid display
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error applying filters and sort: {e}")

    def _refresh_grid(self) -> None:
        """Refresh the grid display."""
        try:
            if self._grid_container:
                self._grid_container.content = self._build_grid_content()
                self._grid_container.update()

            # Update pagination controls
            if self._pagination_controls:
                self._update_pagination_controls()

        except Exception as e:
            logger.error(f"Error refreshing grid: {e}")

    # Selection and batch operations
    def _build_selection_toolbar(self) -> ft.Control:
        """Build selection toolbar for batch operations."""
        try:
            # Selection count
            selection_count = ft.Text(
                f"{len(self._selected_models)} selected",
                size=self.get_text_style("body_medium").size,
                weight=ft.FontWeight.BOLD,
                color=self.get_color("on_primary_container")
            )

            # Batch action buttons
            action_buttons = ft.Row(
                controls=[
                    ft.ElevatedButton(
                        text="Deploy",
                        icon=ft.Icons.CLOUD_UPLOAD,
                        on_click=lambda e: self._on_batch_operation("deploy"),
                        bgcolor=self.get_color("primary"),
                        color=self.get_color("on_primary")
                    ),
                    ft.ElevatedButton(
                        text="Archive",
                        icon=ft.Icons.ARCHIVE,
                        on_click=lambda e: self._on_batch_operation("archive"),
                        bgcolor=self.get_color("secondary"),
                        color=self.get_color("on_secondary")
                    ),
                    ft.ElevatedButton(
                        text="Delete",
                        icon=ft.Icons.DELETE,
                        on_click=lambda e: self._on_batch_operation("delete"),
                        bgcolor=self.get_color("error"),
                        color=self.get_color("on_error")
                    ),
                    ft.TextButton(
                        text="Clear Selection",
                        on_click=lambda e: self._clear_selection(),
                        style=ft.ButtonStyle(
                            color=self.get_color("on_primary_container")
                        )
                    )
                ],
                spacing=self.get_spacing("sm")
            )

            return ft.Row(
                controls=[
                    selection_count,
                    action_buttons
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

        except Exception as e:
            logger.error(f"Error building selection toolbar: {e}")
            return ft.Container()

    def _update_selection_toolbar(self) -> None:
        """Update selection toolbar visibility and content."""
        try:
            if self._selection_toolbar:
                has_selection = len(self._selected_models) > 0
                self._selection_toolbar.visible = has_selection

                if has_selection:
                    self._selection_toolbar.content = self._build_selection_toolbar()

                self._selection_toolbar.update()

        except Exception as e:
            logger.error(f"Error updating selection toolbar: {e}")

    def _on_batch_operation(self, operation: str) -> None:
        """Handle batch operations on selected models."""
        try:
            selected_models = [m for m in self._models if m.is_selected]

            if self._on_bulk_operation:
                self._on_bulk_operation(operation, selected_models)

            # Clear selection after operation
            self._clear_selection()

        except Exception as e:
            logger.error(f"Error handling batch operation {operation}: {e}")

    def _clear_selection(self) -> None:
        """Clear all model selections."""
        try:
            for model in self._models:
                model.is_selected = False

            self._selected_models.clear()
            self._update_selection_toolbar()
            self._refresh_grid()

            if self._on_model_selected:
                self._on_model_selected([])

        except Exception as e:
            logger.error(f"Error clearing selection: {e}")

    # Database integration
    async def load_models(self, project_id: Optional[str] = None) -> None:
        """Load models from database."""
        try:
            self._is_loading = True
            self._show_loading(True)

            if not self._model_dao:
                # Use mock data if database not available
                self._models = self._generate_mock_models()
            else:
                # Load from database
                if project_id:
                    models_metadata = await asyncio.to_thread(
                        self._model_dao.get_models_by_project, project_id
                    )
                else:
                    models_metadata = await asyncio.to_thread(
                        self._model_dao.get_all_models
                    )

                # Convert to grid items
                self._models = []
                for metadata in models_metadata:
                    grid_item = await self._convert_metadata_to_grid_item(metadata)
                    self._models.append(grid_item)

            # Apply initial filters and sort
            self._apply_filters_and_sort()
            self._last_refresh = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            self._models = []
        finally:
            self._is_loading = False
            self._show_loading(False)

    async def _convert_metadata_to_grid_item(self, metadata: 'ModelMetadata') -> ModelGridItem:
        """Convert model metadata to grid item."""
        try:
            # Get latest version info
            latest_version = None
            if self._versions_db:
                try:
                    latest_version = await asyncio.to_thread(
                        self._versions_db.get_latest_version, metadata.model_id, "main"
                    )
                except Exception:
                    pass

            # Get checkpoint info
            last_checkpoint = None
            if self._checkpoint_db:
                try:
                    checkpoints = await asyncio.to_thread(
                        self._checkpoint_db.get_checkpoints_by_model, metadata.model_id
                    )
                    if checkpoints:
                        last_checkpoint = checkpoints[0].checkpoint_id
                except Exception:
                    pass

            return ModelGridItem(
                model_id=metadata.model_id,
                name=metadata.name,
                version=latest_version.version_number if latest_version else metadata.version,
                architecture=metadata.architecture.value if hasattr(metadata.architecture, 'value') else str(metadata.architecture),
                status=metadata.status.value if hasattr(metadata.status, 'value') else str(metadata.status),
                performance_score=self._extract_performance_score(metadata.performance_metrics),
                model_size_mb=metadata.model_size_mb,
                parameters_count=metadata.parameters_count,
                created_at=metadata.created_at,
                updated_at=metadata.updated_at,
                created_by=metadata.created_by,
                description=metadata.description,
                tags=metadata.tags or [],
                last_checkpoint=last_checkpoint,
                performance_metrics=metadata.performance_metrics
            )

        except Exception as e:
            logger.error(f"Error converting metadata to grid item: {e}")
            return ModelGridItem(
                model_id=metadata.model_id,
                name=metadata.name,
                version=metadata.version,
                architecture="Unknown",
                status="Unknown"
            )

    def _extract_performance_score(self, metrics: Optional[Dict[str, Any]]) -> Optional[float]:
        """Extract performance score from metrics."""
        try:
            if not metrics:
                return None

            # Look for common performance metrics
            for key in ["accuracy", "f1_score", "performance", "score"]:
                if key in metrics:
                    value = metrics[key]
                    if isinstance(value, (int, float)):
                        return float(value) * 100 if value <= 1.0 else float(value)

            return None

        except Exception as e:
            logger.error(f"Error extracting performance score: {e}")
            return None

    def _generate_mock_models(self) -> List[ModelGridItem]:
        """Generate mock model data for testing."""
        try:
            mock_models = []

            for i in range(12):
                model = ModelGridItem(
                    model_id=f"model_{i+1}",
                    name=f"Model {i+1}",
                    version=f"1.{i}",
                    architecture=["GPT-3", "BERT", "T5", "LLaMA"][i % 4],
                    status=["training", "completed", "deployed", "failed"][i % 4],
                    performance_score=85.5 + (i * 2.3) % 15,
                    model_size_mb=1024.0 + (i * 512),
                    parameters_count=1000000 * (i + 1),
                    created_at=datetime.now(timezone.utc) - timedelta(days=i),
                    description=f"Description for model {i+1}",
                    tags=[f"tag{j}" for j in range(1, (i % 3) + 2)]
                )
                mock_models.append(model)

            return mock_models

        except Exception as e:
            logger.error(f"Error generating mock models: {e}")
            return []

    # Pagination and footer
    def _build_footer_section(self) -> ft.Control:
        """Build footer section with pagination controls."""
        try:
            self._pagination_controls = ft.Row(
                controls=self._build_pagination_controls(),
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=self.get_spacing("sm")
            )

            # Model count info
            count_info = ft.Text(
                self._get_count_info_text(),
                size=self.get_text_style("body_small").size,
                color=self.get_color("on_surface_variant")
            )

            return ft.Row(
                controls=[
                    count_info,
                    self._pagination_controls
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

        except Exception as e:
            logger.error(f"Error building footer section: {e}")
            return ft.Container()

    def _build_pagination_controls(self) -> List[ft.Control]:
        """Build pagination control buttons."""
        try:
            controls = []

            # Previous button
            prev_button = ft.IconButton(
                icon=ft.Icons.CHEVRON_LEFT,
                disabled=self._current_page == 0,
                on_click=lambda e: self._go_to_page(self._current_page - 1),
                icon_color=self.get_color("primary") if self._current_page > 0 else self.get_color("on_surface_variant")
            )
            controls.append(prev_button)

            # Page numbers
            start_page = max(0, self._current_page - 2)
            end_page = min(self._total_pages, start_page + 5)

            for page in range(start_page, end_page):
                if page == self._current_page:
                    # Current page
                    page_button = ft.Container(
                        content=ft.Text(
                            str(page + 1),
                            size=self.get_text_style("body_medium").size,
                            weight=ft.FontWeight.BOLD,
                            color=self.get_color("on_primary")
                        ),
                        width=32,
                        height=32,
                        bgcolor=self.get_color("primary"),
                        border_radius=self.get_border_radius("sm"),
                        alignment=ft.alignment.center
                    )
                else:
                    # Other pages
                    page_button = ft.TextButton(
                        text=str(page + 1),
                        on_click=lambda e, p=page: self._go_to_page(p),
                        style=ft.ButtonStyle(
                            color=self.get_color("on_surface"),
                            padding=ft.padding.all(8)
                        )
                    )
                controls.append(page_button)

            # Next button
            next_button = ft.IconButton(
                icon=ft.Icons.CHEVRON_RIGHT,
                disabled=self._current_page >= self._total_pages - 1,
                on_click=lambda e: self._go_to_page(self._current_page + 1),
                icon_color=self.get_color("primary") if self._current_page < self._total_pages - 1 else self.get_color("on_surface_variant")
            )
            controls.append(next_button)

            return controls

        except Exception as e:
            logger.error(f"Error building pagination controls: {e}")
            return []

    def _go_to_page(self, page: int) -> None:
        """Navigate to specific page."""
        try:
            if 0 <= page < self._total_pages:
                self._current_page = page
                self._refresh_grid()
                self._update_pagination_controls()
        except Exception as e:
            logger.error(f"Error navigating to page {page}: {e}")

    def _update_pagination_controls(self) -> None:
        """Update pagination controls."""
        try:
            if self._pagination_controls:
                self._pagination_controls.controls = self._build_pagination_controls()
                self._pagination_controls.update()
        except Exception as e:
            logger.error(f"Error updating pagination controls: {e}")

    def _get_count_info_text(self) -> str:
        """Get count information text."""
        try:
            start = self._current_page * self._config.page_size + 1
            end = min(start + self._config.page_size - 1, len(self._filtered_models))
            total = len(self._filtered_models)

            if total == 0:
                return "No models found"
            else:
                return f"Showing {start}-{end} of {total} models"

        except Exception as e:
            logger.error(f"Error getting count info text: {e}")
            return "Models"

    # Utility methods
    def _build_empty_state(self) -> ft.Control:
        """Build empty state display."""
        try:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.SMART_TOY_OUTLINED,
                            size=64,
                            color=self.get_color("on_surface_variant")
                        ),
                        ft.Text(
                            "No models found",
                            size=self.get_text_style("title_medium").size,
                            color=self.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            "Try adjusting your search or filters",
                            size=self.get_text_style("body_medium").size,
                            color=self.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=self.get_spacing("md")
                ),
                alignment=ft.alignment.center,
                expand=True
            )
        except Exception as e:
            logger.error(f"Error building empty state: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state display."""
        try:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.ERROR_OUTLINE,
                            size=64,
                            color=self.get_color("error")
                        ),
                        ft.Text(
                            "Error loading models",
                            size=self.get_text_style("title_medium").size,
                            color=self.get_color("error"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            error_message,
                            size=self.get_text_style("body_medium").size,
                            color=self.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.ElevatedButton(
                            text="Retry",
                            icon=ft.Icons.REFRESH,
                            on_click=lambda e: asyncio.create_task(self.load_models()),
                            bgcolor=self.get_color("primary"),
                            color=self.get_color("on_primary")
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=self.get_spacing("md")
                ),
                alignment=ft.alignment.center,
                expand=True
            )
        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    def _show_loading(self, show: bool) -> None:
        """Show or hide loading indicator."""
        try:
            if self._loading_indicator:
                self._loading_indicator.visible = show
                self._loading_indicator.update()
        except Exception as e:
            logger.error(f"Error showing loading indicator: {e}")

    # Auto-refresh functionality
    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer."""
        try:
            if self._config.auto_refresh and self._config.refresh_interval > 0:
                self._refresh_timer = threading.Timer(
                    self._config.refresh_interval,
                    self._auto_refresh_callback
                )
                self._refresh_timer.start()
        except Exception as e:
            logger.error(f"Error starting auto-refresh: {e}")

    def _auto_refresh_callback(self) -> None:
        """Auto-refresh callback."""
        try:
            if not self._is_loading:
                asyncio.create_task(self.load_models())

            # Schedule next refresh
            self._start_auto_refresh()

        except Exception as e:
            logger.error(f"Error in auto-refresh callback: {e}")

    def stop_auto_refresh(self) -> None:
        """Stop auto-refresh timer."""
        try:
            if self._refresh_timer:
                self._refresh_timer.cancel()
                self._refresh_timer = None
        except Exception as e:
            logger.error(f"Error stopping auto-refresh: {e}")

    # Public API methods
    def get_selected_models(self) -> List[ModelGridItem]:
        """Get currently selected models."""
        return [model for model in self._models if model.is_selected]

    def select_model(self, model_id: str) -> None:
        """Select a specific model."""
        try:
            for model in self._models:
                if model.model_id == model_id:
                    model.is_selected = True
                    self._selected_models.add(model_id)
                    break

            self._update_selection_toolbar()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error selecting model {model_id}: {e}")

    def deselect_model(self, model_id: str) -> None:
        """Deselect a specific model."""
        try:
            for model in self._models:
                if model.model_id == model_id:
                    model.is_selected = False
                    self._selected_models.discard(model_id)
                    break

            self._update_selection_toolbar()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error deselecting model {model_id}: {e}")

    def refresh_models(self) -> None:
        """Manually refresh models."""
        asyncio.create_task(self.load_models())

    def set_search_query(self, query: str) -> None:
        """Set search query programmatically."""
        try:
            self._search_query = query.lower()
            if self._search_bar:
                self._search_bar.value = query
                self._search_bar.update()
            self._apply_filters_and_sort()
        except Exception as e:
            logger.error(f"Error setting search query: {e}")

    def get_model_count(self) -> Tuple[int, int]:
        """Get total and filtered model counts."""
        return len(self._models), len(self._filtered_models)
