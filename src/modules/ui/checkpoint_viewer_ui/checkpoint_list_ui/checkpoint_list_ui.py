"""
Module: checkpoint_list_ui
Description: Comprehensive checkpoint listing and management interface with responsive design and theme integration.
            Provides checkpoint visualization, filtering, sorting, selection, and management capabilities
            with modern UI/UX patterns and accessibility compliance.
Phase: 4
Location: /src/modules/ui/checkpoint_viewer_ui/checkpoint_list_ui/checkpoint_list_ui.py
"""

# Standard library imports
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ColorPalette,
    SpacingSystem,
    TypographyScale,
    IconSystem,
    get_theme_manager
)

try:
    from src.modules.logic.checkpoint_management_lg.base_interfaces import (
        CheckpointMetadata,
        CheckpointType,
        CheckpointStatus
    )
except ImportError:
    # Fallback definitions for development
    class CheckpointType(Enum):
        PERIODIC = "periodic"
        BEST = "best"
        MILESTONE = "milestone"
        MANUAL = "manual"
        EMERGENCY = "emergency"
    
    class CheckpointStatus(Enum):
        VALID = "valid"
        CORRUPTED = "corrupted"
        INCOMPLETE = "incomplete"
        VALIDATING = "validating"
        ARCHIVED = "archived"
    
    @dataclass
    class CheckpointMetadata:
        checkpoint_id: str
        checkpoint_type: CheckpointType
        status: CheckpointStatus
        file_path: Path
        created_at: datetime
        model_state_size: int
        optimizer_state_size: int
        total_size: int
        checksum: str
        training_step: int
        epoch: int
        loss_value: float
        metrics: Dict[str, float] = field(default_factory=dict)
        tags: Set[str] = field(default_factory=set)
        description: Optional[str] = None
        parent_checkpoint_id: Optional[str] = None
        is_best: bool = False

try:
    from src.modules.database.checkpoints_db.checkpoint_registry_db.checkpoint_registry_db import CheckpointRegistryDB
except ImportError:
    # Mock for development
    class CheckpointRegistryDB:
        def get_all_checkpoints(self) -> List[CheckpointMetadata]:
            return []
        
        def get_checkpoint_by_id(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
            return None

# Configure logging
logger = logging.getLogger(__name__)


class CheckpointSortMode(Enum):
    """Checkpoint sorting modes."""
    CREATED_DESC = "created_desc"
    CREATED_ASC = "created_asc"
    EPOCH_DESC = "epoch_desc"
    EPOCH_ASC = "epoch_asc"
    LOSS_ASC = "loss_asc"
    LOSS_DESC = "loss_desc"
    SIZE_DESC = "size_desc"
    SIZE_ASC = "size_asc"
    TYPE = "type"
    STATUS = "status"


class CheckpointFilterMode(Enum):
    """Checkpoint filtering modes."""
    ALL = "all"
    BEST_ONLY = "best_only"
    VALID_ONLY = "valid_only"
    BY_TYPE = "by_type"
    BY_STATUS = "by_status"
    BY_DATE_RANGE = "by_date_range"
    BY_EPOCH_RANGE = "by_epoch_range"


class CheckpointDisplayMode(Enum):
    """Checkpoint display modes."""
    LIST = "list"
    GRID = "grid"
    COMPACT = "compact"
    DETAILED = "detailed"


class CheckpointSelectionMode(Enum):
    """Checkpoint selection modes."""
    SINGLE = "single"
    MULTIPLE = "multiple"
    NONE = "none"


@dataclass
class CheckpointListConfig:
    """Configuration for checkpoint list display."""
    display_mode: CheckpointDisplayMode = CheckpointDisplayMode.LIST
    sort_mode: CheckpointSortMode = CheckpointSortMode.CREATED_DESC
    filter_mode: CheckpointFilterMode = CheckpointFilterMode.ALL
    selection_mode: CheckpointSelectionMode = CheckpointSelectionMode.SINGLE
    show_metrics: bool = True
    show_file_sizes: bool = True
    show_checksums: bool = False
    show_tags: bool = True
    auto_refresh: bool = True
    refresh_interval: int = 30  # seconds
    page_size: int = 50
    enable_search: bool = True
    enable_bulk_operations: bool = True


@dataclass
class CheckpointItem:
    """Wrapper for checkpoint metadata with UI state."""
    metadata: CheckpointMetadata
    is_selected: bool = False
    is_highlighted: bool = False
    is_expanded: bool = False
    last_accessed: Optional[datetime] = None


@dataclass
class CheckpointListState:
    """State management for checkpoint list."""
    checkpoints: List[CheckpointItem] = field(default_factory=list)
    filtered_checkpoints: List[CheckpointItem] = field(default_factory=list)
    selected_checkpoints: Set[str] = field(default_factory=set)
    search_query: str = ""
    current_page: int = 0
    total_pages: int = 0
    is_loading: bool = False
    last_refresh: Optional[datetime] = None
    error_message: Optional[str] = None


class CheckpointListUI(ThemeAwareUserControl):
    """
    Comprehensive checkpoint listing and management interface.
    
    Features:
    - Responsive checkpoint list/grid view with breakpoint-aware layouts
    - Advanced filtering and sorting with real-time updates
    - Search functionality with debounced input
    - Batch selection and operations
    - Checkpoint status indicators and metrics display
    - Pagination with infinite scroll support
    - Theme-aware styling with accessibility compliance
    - Integration with checkpoint database and management system
    - Modern UI/UX with smooth animations and transitions
    - Checkpoint validation and integrity checking
    - Export and backup operations
    """
    
    def __init__(
        self,
        config: Optional[CheckpointListConfig] = None,
        on_checkpoint_selected: Optional[Callable[[CheckpointMetadata], None]] = None,
        on_checkpoint_double_click: Optional[Callable[[CheckpointMetadata], None]] = None,
        on_bulk_operation: Optional[Callable[[str, List[CheckpointMetadata]], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self.config = config or CheckpointListConfig()
        
        # Callbacks
        self._on_checkpoint_selected = on_checkpoint_selected
        self._on_checkpoint_double_click = on_checkpoint_double_click
        self._on_bulk_operation = on_bulk_operation
        
        # State
        self._state = CheckpointListState()
        
        # Database connection
        self._checkpoint_db = CheckpointRegistryDB()
        
        # UI components
        self._search_field: Optional[ft.TextField] = None
        self._sort_dropdown: Optional[ft.Dropdown] = None
        self._filter_dropdown: Optional[ft.Dropdown] = None
        self._display_mode_buttons: List[ft.IconButton] = []
        self._checkpoint_list: Optional[ft.ListView] = None
        self._checkpoint_grid: Optional[ft.GridView] = None
        self._pagination_controls: Optional[ft.Row] = None
        self._status_bar: Optional[ft.Container] = None
        self._bulk_actions_bar: Optional[ft.Container] = None
        
        # Refresh timer
        self._refresh_timer: Optional[asyncio.Task] = None
        
        # Search debounce
        self._search_debounce_timer: Optional[asyncio.Task] = None
        
        logger.info("CheckpointListUI initialized")
    
    def build(self) -> ft.Control:
        """Build the checkpoint list interface."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            
            return ft.Container(
                content=ft.Column(
                    controls=[
                        self._create_toolbar(),
                        ft.Divider(height=1, color=palette.borders),
                        ft.Expanded(
                            child=self._create_main_content()
                        ),
                        ft.Divider(height=1, color=palette.borders),
                        self._create_status_bar()
                    ],
                    spacing=0,
                    expand=True
                ),
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.borders),
                border_radius=self.get_responsive_size(8),
                padding=0,
                expand=True
            )
            
        except Exception as e:
            logger.error(f"Error building checkpoint list UI: {e}")
            return self._create_error_state(str(e))
    
    def did_mount(self) -> None:
        """Called when control is mounted."""
        super().did_mount()
        asyncio.create_task(self._initialize_data())
        
        if self.config.auto_refresh:
            self._start_auto_refresh()
    
    def will_unmount(self) -> None:
        """Called when control is unmounted."""
        if self._refresh_timer:
            self._refresh_timer.cancel()
        
        if self._search_debounce_timer:
            self._search_debounce_timer.cancel()
    
    async def _initialize_data(self) -> None:
        """Initialize checkpoint data."""
        try:
            self._state.is_loading = True
            self.update()
            
            # Load checkpoints from database
            checkpoints_metadata = self._checkpoint_db.get_all_checkpoints()
            
            # Convert to CheckpointItem objects
            self._state.checkpoints = [
                CheckpointItem(metadata=checkpoint)
                for checkpoint in checkpoints_metadata
            ]
            
            # Apply initial filtering and sorting
            await self._apply_filters_and_sorting()
            
            self._state.is_loading = False
            self._state.last_refresh = datetime.now()
            self.update()
            
            logger.info(f"Loaded {len(self._state.checkpoints)} checkpoints")
            
        except Exception as e:
            logger.error(f"Error initializing checkpoint data: {e}")
            self._state.error_message = str(e)
            self._state.is_loading = False
            self.update()

    def _create_toolbar(self) -> ft.Container:
        """Create the toolbar with search, filters, and controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Search field
        self._search_field = ft.TextField(
            hint_text="Search checkpoints...",
            prefix_icon=self.get_icon('SEARCH'),
            border_radius=self.get_responsive_size(8),
            bgcolor=palette.surface_variant,
            border_color=palette.outline_variant,
            focused_border_color=palette.primary,
            text_style=self.get_text_style('body_medium'),
            hint_style=self.get_text_style('body_medium'),
            on_change=self._on_search_change,
            expand=True
        )

        # Sort dropdown
        self._sort_dropdown = ft.Dropdown(
            label="Sort by",
            options=[
                ft.dropdown.Option("created_desc", "Newest First"),
                ft.dropdown.Option("created_asc", "Oldest First"),
                ft.dropdown.Option("epoch_desc", "Epoch (High to Low)"),
                ft.dropdown.Option("epoch_asc", "Epoch (Low to High)"),
                ft.dropdown.Option("loss_asc", "Best Loss First"),
                ft.dropdown.Option("loss_desc", "Worst Loss First"),
                ft.dropdown.Option("size_desc", "Largest First"),
                ft.dropdown.Option("size_asc", "Smallest First"),
                ft.dropdown.Option("type", "By Type"),
                ft.dropdown.Option("status", "By Status")
            ],
            value=self.config.sort_mode.value,
            width=self.get_responsive_size(180),
            bgcolor=palette.surface_variant,
            border_color=palette.outline_variant,
            focused_border_color=palette.primary,
            text_style=self.get_text_style('body_medium'),
            on_change=self._on_sort_change
        )

        # Filter dropdown
        self._filter_dropdown = ft.Dropdown(
            label="Filter",
            options=[
                ft.dropdown.Option("all", "All Checkpoints"),
                ft.dropdown.Option("best_only", "Best Only"),
                ft.dropdown.Option("valid_only", "Valid Only"),
                ft.dropdown.Option("by_type", "By Type"),
                ft.dropdown.Option("by_status", "By Status")
            ],
            value=self.config.filter_mode.value,
            width=self.get_responsive_size(160),
            bgcolor=palette.surface_variant,
            border_color=palette.outline_variant,
            focused_border_color=palette.primary,
            text_style=self.get_text_style('body_medium'),
            on_change=self._on_filter_change
        )

        # Display mode buttons
        self._display_mode_buttons = [
            ft.IconButton(
                icon=self.get_icon('LIST'),
                tooltip="List View",
                selected=self.config.display_mode == CheckpointDisplayMode.LIST,
                on_click=lambda e: self._set_display_mode(CheckpointDisplayMode.LIST)
            ),
            ft.IconButton(
                icon=self.get_icon('GRID_VIEW'),
                tooltip="Grid View",
                selected=self.config.display_mode == CheckpointDisplayMode.GRID,
                on_click=lambda e: self._set_display_mode(CheckpointDisplayMode.GRID)
            ),
            ft.IconButton(
                icon=self.get_icon('VIEW_COMPACT'),
                tooltip="Compact View",
                selected=self.config.display_mode == CheckpointDisplayMode.COMPACT,
                on_click=lambda e: self._set_display_mode(CheckpointDisplayMode.COMPACT)
            )
        ]

        # Refresh button
        refresh_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh Checkpoints",
            on_click=self._on_refresh_click
        )

        # Settings button
        settings_button = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            tooltip="Checkpoint Settings",
            on_click=self._on_settings_click
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Expanded(
                        flex=3,
                        child=self._search_field
                    ),
                    ft.Container(width=spacing.small),
                    self._sort_dropdown,
                    ft.Container(width=spacing.xs),
                    self._filter_dropdown,
                    ft.Container(width=spacing.small),
                    ft.Row(
                        controls=self._display_mode_buttons,
                        spacing=spacing.xs
                    ),
                    ft.Container(width=spacing.xs),
                    refresh_button,
                    settings_button
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )

    def _create_main_content(self) -> ft.Control:
        """Create the main content area."""
        try:
            if self._state.is_loading:
                return self._create_loading_state()

            if self._state.error_message:
                return self._create_error_state(self._state.error_message)

            if not self._state.filtered_checkpoints:
                return self._create_empty_state()

            # Create content based on display mode
            if self.config.display_mode == CheckpointDisplayMode.GRID:
                return self._create_grid_view()
            elif self.config.display_mode == CheckpointDisplayMode.COMPACT:
                return self._create_compact_view()
            else:
                return self._create_list_view()

        except Exception as e:
            logger.error(f"Error creating main content: {e}")
            return self._create_error_state(str(e))

    def _create_list_view(self) -> ft.Control:
        """Create the list view for checkpoints."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate pagination
        start_idx = self._state.current_page * self.config.page_size
        end_idx = start_idx + self.config.page_size
        page_checkpoints = self._state.filtered_checkpoints[start_idx:end_idx]

        # Create list items
        list_items = []
        for checkpoint_item in page_checkpoints:
            list_items.append(self._create_checkpoint_list_item(checkpoint_item))

        self._checkpoint_list = ft.ListView(
            controls=list_items,
            spacing=spacing.xs,
            padding=spacing.medium,
            expand=True
        )

        return ft.Column(
            controls=[
                ft.Expanded(child=self._checkpoint_list),
                self._create_pagination_controls()
            ],
            spacing=0,
            expand=True
        )

    def _create_checkpoint_list_item(self, checkpoint_item: CheckpointItem) -> ft.Control:
        """Create a list item for a checkpoint."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        checkpoint = checkpoint_item.metadata

        # Status indicator
        status_color = self._get_status_color(checkpoint.status)
        status_icon = self._get_status_icon(checkpoint.status)

        # Type badge
        type_badge = ft.Container(
            content=ft.Text(
                checkpoint.checkpoint_type.value.upper(),
                style=self.get_text_style('label_small'),
                color=palette.on_primary_container
            ),
            bgcolor=self._get_type_color(checkpoint.checkpoint_type),
            padding=ft.padding.symmetric(horizontal=spacing.xs, vertical=2),
            border_radius=self.get_responsive_size(4)
        )

        # Best indicator
        best_indicator = ft.Icon(
            self.get_icon('STAR'),
            color=palette.warning,
            size=self.get_responsive_size(16)
        ) if checkpoint.is_best else ft.Container()

        # Metrics display
        metrics_text = ""
        if self.config.show_metrics and checkpoint.metrics:
            metrics_list = [f"{k}: {v:.4f}" for k, v in list(checkpoint.metrics.items())[:3]]
            metrics_text = " | ".join(metrics_list)

        # File size display
        size_text = self._format_file_size(checkpoint.total_size) if self.config.show_file_sizes else ""

        # Main content
        main_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            status_icon,
                            color=status_color,
                            size=self.get_responsive_size(16)
                        ),
                        ft.Text(
                            f"Checkpoint {checkpoint.checkpoint_id[:8]}",
                            style=self.get_text_style('title_small'),
                            color=palette.on_surface,
                            weight=ft.FontWeight.W_600
                        ),
                        best_indicator,
                        ft.Container(expand=True),
                        type_badge,
                        ft.Text(
                            checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                            style=self.get_text_style('body_small'),
                            color=palette.on_surface_variant
                        )
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                ft.Row(
                    controls=[
                        ft.Text(
                            f"Epoch {checkpoint.epoch} | Step {checkpoint.training_step} | Loss: {checkpoint.loss_value:.4f}",
                            style=self.get_text_style('body_medium'),
                            color=palette.on_surface_variant
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            size_text,
                            style=self.get_text_style('body_small'),
                            color=palette.on_surface_variant
                        ) if size_text else ft.Container()
                    ]
                ),
                ft.Text(
                    metrics_text,
                    style=self.get_text_style('body_small'),
                    color=palette.on_surface_variant,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS
                ) if metrics_text else ft.Container()
            ],
            spacing=spacing.xs
        )

        # Selection checkbox
        selection_checkbox = ft.Checkbox(
            value=checkpoint_item.is_selected,
            on_change=lambda e: self._on_checkpoint_selection_change(checkpoint.checkpoint_id, e.control.value)
        ) if self.config.selection_mode == CheckpointSelectionMode.MULTIPLE else ft.Container()

        return ft.Container(
            content=ft.Row(
                controls=[
                    selection_checkbox,
                    ft.Expanded(child=main_content)
                ],
                spacing=spacing.small
            ),
            padding=spacing.medium,
            bgcolor=palette.primary_container if checkpoint_item.is_selected else palette.surface,
            border=ft.border.all(
                1,
                palette.primary if checkpoint_item.is_selected else palette.outline_variant
            ),
            border_radius=self.get_responsive_size(8),
            on_click=lambda e, cid=checkpoint.checkpoint_id: self._on_checkpoint_click(cid),
            ink=True
        )

    def _create_grid_view(self) -> ft.Control:
        """Create the grid view for checkpoints."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate responsive columns
        columns = self.get_responsive_columns()

        # Calculate pagination
        start_idx = self._state.current_page * self.config.page_size
        end_idx = start_idx + self.config.page_size
        page_checkpoints = self._state.filtered_checkpoints[start_idx:end_idx]

        # Create grid items
        grid_items = []
        for checkpoint_item in page_checkpoints:
            grid_items.append(self._create_checkpoint_grid_item(checkpoint_item))

        self._checkpoint_grid = ft.GridView(
            controls=grid_items,
            runs_count=columns,
            max_extent=self.get_responsive_size(300),
            child_aspect_ratio=1.2,
            spacing=spacing.medium,
            run_spacing=spacing.medium,
            padding=spacing.medium,
            expand=True
        )

        return ft.Column(
            controls=[
                ft.Expanded(child=self._checkpoint_grid),
                self._create_pagination_controls()
            ],
            spacing=0,
            expand=True
        )

    def _create_checkpoint_grid_item(self, checkpoint_item: CheckpointItem) -> ft.Control:
        """Create a grid item for a checkpoint."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        checkpoint = checkpoint_item.metadata

        # Status indicator
        status_color = self._get_status_color(checkpoint.status)
        status_icon = self._get_status_icon(checkpoint.status)

        # Type badge
        type_badge = ft.Container(
            content=ft.Text(
                checkpoint.checkpoint_type.value[:4].upper(),
                style=self.get_text_style('label_small'),
                color=palette.on_primary_container
            ),
            bgcolor=self._get_type_color(checkpoint.checkpoint_type),
            padding=ft.padding.symmetric(horizontal=spacing.xs, vertical=2),
            border_radius=self.get_responsive_size(4)
        )

        # Best indicator
        best_indicator = ft.Icon(
            self.get_icon('STAR'),
            color=palette.warning,
            size=self.get_responsive_size(20)
        ) if checkpoint.is_best else ft.Container()

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    status_icon,
                                    color=status_color,
                                    size=self.get_responsive_size(20)
                                ),
                                ft.Container(expand=True),
                                best_indicator,
                                type_badge
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        ft.Container(height=spacing.small),
                        ft.Text(
                            f"Checkpoint {checkpoint.checkpoint_id[:8]}",
                            style=self.get_text_style('title_small'),
                            color=palette.on_surface,
                            weight=ft.FontWeight.W_600,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            f"Epoch {checkpoint.epoch}",
                            style=self.get_text_style('body_medium'),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            f"Loss: {checkpoint.loss_value:.4f}",
                            style=self.get_text_style('body_small'),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            checkpoint.created_at.strftime("%m/%d %H:%M"),
                            style=self.get_text_style('body_small'),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    spacing=spacing.xs,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True
                ),
                padding=spacing.medium,
                bgcolor=palette.primary_container if checkpoint_item.is_selected else palette.surface,
                border=ft.border.all(
                    1,
                    palette.primary if checkpoint_item.is_selected else palette.outline_variant
                ),
                border_radius=self.get_responsive_size(8),
                on_click=lambda e, cid=checkpoint.checkpoint_id: self._on_checkpoint_click(cid),
                ink=True
            ),
            elevation=2 if checkpoint_item.is_selected else 1
        )

    def _create_compact_view(self) -> ft.Control:
        """Create the compact view for checkpoints."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate pagination
        start_idx = self._state.current_page * self.config.page_size
        end_idx = start_idx + self.config.page_size
        page_checkpoints = self._state.filtered_checkpoints[start_idx:end_idx]

        # Create compact items
        compact_items = []
        for checkpoint_item in page_checkpoints:
            compact_items.append(self._create_checkpoint_compact_item(checkpoint_item))

        self._checkpoint_list = ft.ListView(
            controls=compact_items,
            spacing=spacing.xs,
            padding=spacing.medium,
            expand=True
        )

        return ft.Column(
            controls=[
                ft.Expanded(child=self._checkpoint_list),
                self._create_pagination_controls()
            ],
            spacing=0,
            expand=True
        )

    def _create_checkpoint_compact_item(self, checkpoint_item: CheckpointItem) -> ft.Control:
        """Create a compact item for a checkpoint."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        checkpoint = checkpoint_item.metadata

        # Status indicator
        status_color = self._get_status_color(checkpoint.status)
        status_icon = self._get_status_icon(checkpoint.status)

        # Best indicator
        best_indicator = "★" if checkpoint.is_best else ""

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        status_icon,
                        color=status_color,
                        size=self.get_responsive_size(16)
                    ),
                    ft.Text(
                        f"{checkpoint.checkpoint_id[:8]} {best_indicator}",
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        f"E{checkpoint.epoch}",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    ),
                    ft.Text(
                        f"{checkpoint.loss_value:.3f}",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    ),
                    ft.Text(
                        checkpoint.created_at.strftime("%m/%d"),
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    )
                ],
                spacing=spacing.small,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            padding=ft.padding.symmetric(horizontal=spacing.medium, vertical=spacing.small),
            bgcolor=palette.primary_container if checkpoint_item.is_selected else palette.surface,
            border=ft.border.all(
                1,
                palette.primary if checkpoint_item.is_selected else palette.outline_variant
            ),
            border_radius=self.get_responsive_size(4),
            on_click=lambda e, cid=checkpoint.checkpoint_id: self._on_checkpoint_click(cid),
            ink=True
        )

    def _create_pagination_controls(self) -> ft.Control:
        """Create pagination controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate total pages
        total_items = len(self._state.filtered_checkpoints)
        self._state.total_pages = max(1, (total_items + self.config.page_size - 1) // self.config.page_size)

        # Previous button
        prev_button = ft.IconButton(
            icon=self.get_icon('CHEVRON_LEFT'),
            tooltip="Previous Page",
            disabled=self._state.current_page == 0,
            on_click=self._on_prev_page
        )

        # Next button
        next_button = ft.IconButton(
            icon=self.get_icon('CHEVRON_RIGHT'),
            tooltip="Next Page",
            disabled=self._state.current_page >= self._state.total_pages - 1,
            on_click=self._on_next_page
        )

        # Page info
        page_info = ft.Text(
            f"Page {self._state.current_page + 1} of {self._state.total_pages}",
            style=self.get_text_style('body_medium'),
            color=palette.on_surface_variant
        )

        # Items info
        start_item = self._state.current_page * self.config.page_size + 1
        end_item = min(start_item + self.config.page_size - 1, total_items)
        items_info = ft.Text(
            f"Showing {start_item}-{end_item} of {total_items} checkpoints",
            style=self.get_text_style('body_small'),
            color=palette.on_surface_variant
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    items_info,
                    ft.Container(expand=True),
                    prev_button,
                    page_info,
                    next_button
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )

    def _create_status_bar(self) -> ft.Control:
        """Create the status bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Status text
        status_text = "Ready"
        if self._state.is_loading:
            status_text = "Loading checkpoints..."
        elif self._state.error_message:
            status_text = f"Error: {self._state.error_message}"
        elif self._state.last_refresh:
            status_text = f"Last updated: {self._state.last_refresh.strftime('%H:%M:%S')}"

        # Selection info
        selection_count = len(self._state.selected_checkpoints)
        selection_text = f"{selection_count} selected" if selection_count > 0 else ""

        # Bulk actions
        bulk_actions = ft.Row(
            controls=[
                ft.ElevatedButton(
                    text="Delete Selected",
                    icon=self.get_icon('DELETE'),
                    on_click=self._on_bulk_delete,
                    disabled=selection_count == 0
                ),
                ft.ElevatedButton(
                    text="Export Selected",
                    icon=self.get_icon('DOWNLOAD'),
                    on_click=self._on_bulk_export,
                    disabled=selection_count == 0
                ),
                ft.ElevatedButton(
                    text="Validate Selected",
                    icon=self.get_icon('CHECK_CIRCLE'),
                    on_click=self._on_bulk_validate,
                    disabled=selection_count == 0
                )
            ],
            spacing=spacing.small
        ) if self.config.enable_bulk_operations and selection_count > 0 else ft.Container()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        status_text,
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        selection_text,
                        style=self.get_text_style('body_small'),
                        color=palette.primary
                    ) if selection_text else ft.Container(),
                    bulk_actions
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )

    def _create_loading_state(self) -> ft.Control:
        """Create loading state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(
                        width=self.get_responsive_size(48),
                        height=self.get_responsive_size(48),
                        color=palette.primary
                    ),
                    ft.Container(height=spacing.medium),
                    ft.Text(
                        "Loading checkpoints...",
                        style=self.get_text_style('body_large'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_empty_state(self) -> ft.Control:
        """Create empty state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        self.get_icon('FOLDER_OPEN'),
                        size=self.get_responsive_size(64),
                        color=palette.on_surface_variant
                    ),
                    ft.Container(height=spacing.medium),
                    ft.Text(
                        "No checkpoints found",
                        style=self.get_text_style('headline_small'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Checkpoints will appear here once training begins",
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Container(height=spacing.large),
                    ft.ElevatedButton(
                        text="Refresh",
                        icon=self.get_icon('REFRESH'),
                        on_click=self._on_refresh_click
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.small
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_error_state(self, error_message: str) -> ft.Control:
        """Create error state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        self.get_icon('ERROR'),
                        size=self.get_responsive_size(64),
                        color=palette.error
                    ),
                    ft.Container(height=spacing.medium),
                    ft.Text(
                        "Error Loading Checkpoints",
                        style=self.get_text_style('headline_small'),
                        color=palette.error,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        error_message,
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Container(height=spacing.large),
                    ft.ElevatedButton(
                        text="Retry",
                        icon=self.get_icon('REFRESH'),
                        on_click=self._on_refresh_click
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.small
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    # Utility methods
    def _get_status_color(self, status: CheckpointStatus) -> str:
        """Get color for checkpoint status."""
        palette = self.get_palette()

        status_colors = {
            CheckpointStatus.VALID: palette.success,
            CheckpointStatus.CORRUPTED: palette.error,
            CheckpointStatus.INCOMPLETE: palette.warning,
            CheckpointStatus.VALIDATING: palette.info,
            CheckpointStatus.ARCHIVED: palette.on_surface_variant
        }

        return status_colors.get(status, palette.on_surface_variant)

    def _get_status_icon(self, status: CheckpointStatus) -> str:
        """Get icon for checkpoint status."""
        status_icons = {
            CheckpointStatus.VALID: self.get_icon('CHECK_CIRCLE'),
            CheckpointStatus.CORRUPTED: self.get_icon('ERROR'),
            CheckpointStatus.INCOMPLETE: self.get_icon('WARNING'),
            CheckpointStatus.VALIDATING: self.get_icon('HOURGLASS_EMPTY'),
            CheckpointStatus.ARCHIVED: self.get_icon('ARCHIVE')
        }

        return status_icons.get(status, self.get_icon('HELP_OUTLINE'))

    def _get_type_color(self, checkpoint_type: CheckpointType) -> str:
        """Get color for checkpoint type."""
        palette = self.get_palette()

        type_colors = {
            CheckpointType.PERIODIC: palette.primary,
            CheckpointType.BEST: palette.warning,
            CheckpointType.MILESTONE: palette.success,
            CheckpointType.MANUAL: palette.info,
            CheckpointType.EMERGENCY: palette.error
        }

        return type_colors.get(checkpoint_type, palette.primary)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"

    # Event handlers
    async def _on_search_change(self, e: ft.ControlEvent) -> None:
        """Handle search input change with debouncing."""
        if self._search_debounce_timer:
            self._search_debounce_timer.cancel()

        self._search_debounce_timer = asyncio.create_task(
            self._debounced_search(e.control.value)
        )

    async def _debounced_search(self, query: str) -> None:
        """Perform debounced search."""
        await asyncio.sleep(0.3)  # Debounce delay

        self._state.search_query = query.lower()
        self._state.current_page = 0
        await self._apply_filters_and_sorting()
        self.update()

    async def _on_sort_change(self, e: ft.ControlEvent) -> None:
        """Handle sort mode change."""
        try:
            self.config.sort_mode = CheckpointSortMode(e.control.value)
            await self._apply_filters_and_sorting()
            self.update()
        except Exception as ex:
            logger.error(f"Error changing sort mode: {ex}")

    async def _on_filter_change(self, e: ft.ControlEvent) -> None:
        """Handle filter mode change."""
        try:
            self.config.filter_mode = CheckpointFilterMode(e.control.value)
            self._state.current_page = 0
            await self._apply_filters_and_sorting()
            self.update()
        except Exception as ex:
            logger.error(f"Error changing filter mode: {ex}")

    def _set_display_mode(self, mode: CheckpointDisplayMode) -> None:
        """Set display mode."""
        self.config.display_mode = mode

        # Update button states
        for i, button in enumerate(self._display_mode_buttons):
            button.selected = (i == mode.value)

        self.update()

    async def _on_refresh_click(self, e: ft.ControlEvent) -> None:
        """Handle refresh button click."""
        await self._initialize_data()

    def _on_settings_click(self, e: ft.ControlEvent) -> None:
        """Handle settings button click."""
        # TODO: Implement settings dialog
        logger.info("Settings clicked")

    def _on_checkpoint_click(self, checkpoint_id: str) -> None:
        """Handle checkpoint item click."""
        try:
            # Find checkpoint
            checkpoint_item = next(
                (item for item in self._state.checkpoints if item.metadata.checkpoint_id == checkpoint_id),
                None
            )

            if not checkpoint_item:
                return

            # Handle selection based on mode
            if self.config.selection_mode == CheckpointSelectionMode.SINGLE:
                # Clear previous selections
                for item in self._state.checkpoints:
                    item.is_selected = False
                self._state.selected_checkpoints.clear()

                # Select current item
                checkpoint_item.is_selected = True
                self._state.selected_checkpoints.add(checkpoint_id)

                # Notify callback
                if self._on_checkpoint_selected:
                    self._on_checkpoint_selected(checkpoint_item.metadata)

            elif self.config.selection_mode == CheckpointSelectionMode.MULTIPLE:
                # Toggle selection
                checkpoint_item.is_selected = not checkpoint_item.is_selected

                if checkpoint_item.is_selected:
                    self._state.selected_checkpoints.add(checkpoint_id)
                else:
                    self._state.selected_checkpoints.discard(checkpoint_id)

            self.update()

        except Exception as ex:
            logger.error(f"Error handling checkpoint click: {ex}")

    def _on_checkpoint_selection_change(self, checkpoint_id: str, selected: bool) -> None:
        """Handle checkbox selection change."""
        try:
            checkpoint_item = next(
                (item for item in self._state.checkpoints if item.metadata.checkpoint_id == checkpoint_id),
                None
            )

            if checkpoint_item:
                checkpoint_item.is_selected = selected

                if selected:
                    self._state.selected_checkpoints.add(checkpoint_id)
                else:
                    self._state.selected_checkpoints.discard(checkpoint_id)

                self.update()

        except Exception as ex:
            logger.error(f"Error handling selection change: {ex}")

    def _on_prev_page(self, e: ft.ControlEvent) -> None:
        """Handle previous page button click."""
        if self._state.current_page > 0:
            self._state.current_page -= 1
            self.update()

    def _on_next_page(self, e: ft.ControlEvent) -> None:
        """Handle next page button click."""
        if self._state.current_page < self._state.total_pages - 1:
            self._state.current_page += 1
            self.update()

    def _on_bulk_delete(self, e: ft.ControlEvent) -> None:
        """Handle bulk delete operation."""
        if self._on_bulk_operation:
            selected_checkpoints = [
                item.metadata for item in self._state.checkpoints
                if item.metadata.checkpoint_id in self._state.selected_checkpoints
            ]
            self._on_bulk_operation("delete", selected_checkpoints)

    def _on_bulk_export(self, e: ft.ControlEvent) -> None:
        """Handle bulk export operation."""
        if self._on_bulk_operation:
            selected_checkpoints = [
                item.metadata for item in self._state.checkpoints
                if item.metadata.checkpoint_id in self._state.selected_checkpoints
            ]
            self._on_bulk_operation("export", selected_checkpoints)

    def _on_bulk_validate(self, e: ft.ControlEvent) -> None:
        """Handle bulk validate operation."""
        if self._on_bulk_operation:
            selected_checkpoints = [
                item.metadata for item in self._state.checkpoints
                if item.metadata.checkpoint_id in self._state.selected_checkpoints
            ]
            self._on_bulk_operation("validate", selected_checkpoints)

    # Data management methods
    async def _apply_filters_and_sorting(self) -> None:
        """Apply current filters and sorting to checkpoint list."""
        try:
            # Start with all checkpoints
            filtered_checkpoints = self._state.checkpoints.copy()

            # Apply search filter
            if self._state.search_query:
                filtered_checkpoints = [
                    item for item in filtered_checkpoints
                    if (
                        self._state.search_query in item.metadata.checkpoint_id.lower() or
                        self._state.search_query in item.metadata.checkpoint_type.value.lower() or
                        self._state.search_query in item.metadata.status.value.lower() or
                        (item.metadata.description and self._state.search_query in item.metadata.description.lower()) or
                        any(self._state.search_query in tag.lower() for tag in item.metadata.tags)
                    )
                ]

            # Apply filters
            if self.config.filter_mode == CheckpointFilterMode.BEST_ONLY:
                filtered_checkpoints = [item for item in filtered_checkpoints if item.metadata.is_best]
            elif self.config.filter_mode == CheckpointFilterMode.VALID_ONLY:
                filtered_checkpoints = [item for item in filtered_checkpoints if item.metadata.status == CheckpointStatus.VALID]

            # Apply sorting
            if self.config.sort_mode == CheckpointSortMode.CREATED_DESC:
                filtered_checkpoints.sort(key=lambda x: x.metadata.created_at, reverse=True)
            elif self.config.sort_mode == CheckpointSortMode.CREATED_ASC:
                filtered_checkpoints.sort(key=lambda x: x.metadata.created_at)
            elif self.config.sort_mode == CheckpointSortMode.EPOCH_DESC:
                filtered_checkpoints.sort(key=lambda x: x.metadata.epoch, reverse=True)
            elif self.config.sort_mode == CheckpointSortMode.EPOCH_ASC:
                filtered_checkpoints.sort(key=lambda x: x.metadata.epoch)
            elif self.config.sort_mode == CheckpointSortMode.LOSS_ASC:
                filtered_checkpoints.sort(key=lambda x: x.metadata.loss_value)
            elif self.config.sort_mode == CheckpointSortMode.LOSS_DESC:
                filtered_checkpoints.sort(key=lambda x: x.metadata.loss_value, reverse=True)
            elif self.config.sort_mode == CheckpointSortMode.SIZE_DESC:
                filtered_checkpoints.sort(key=lambda x: x.metadata.total_size, reverse=True)
            elif self.config.sort_mode == CheckpointSortMode.SIZE_ASC:
                filtered_checkpoints.sort(key=lambda x: x.metadata.total_size)
            elif self.config.sort_mode == CheckpointSortMode.TYPE:
                filtered_checkpoints.sort(key=lambda x: x.metadata.checkpoint_type.value)
            elif self.config.sort_mode == CheckpointSortMode.STATUS:
                filtered_checkpoints.sort(key=lambda x: x.metadata.status.value)

            self._state.filtered_checkpoints = filtered_checkpoints

        except Exception as e:
            logger.error(f"Error applying filters and sorting: {e}")
            self._state.filtered_checkpoints = self._state.checkpoints.copy()

    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer."""
        if self.config.auto_refresh and not self._refresh_timer:
            self._refresh_timer = asyncio.create_task(self._auto_refresh_loop())

    async def _auto_refresh_loop(self) -> None:
        """Auto-refresh loop."""
        try:
            while True:
                await asyncio.sleep(self.config.refresh_interval)
                if not self._state.is_loading:
                    await self._initialize_data()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in auto-refresh loop: {e}")

    # Public API methods
    def refresh_checkpoints(self) -> None:
        """Refresh checkpoint list."""
        asyncio.create_task(self._initialize_data())

    def get_selected_checkpoints(self) -> List[CheckpointMetadata]:
        """Get currently selected checkpoints."""
        return [
            item.metadata for item in self._state.checkpoints
            if item.metadata.checkpoint_id in self._state.selected_checkpoints
        ]

    def clear_selection(self) -> None:
        """Clear all selections."""
        for item in self._state.checkpoints:
            item.is_selected = False
        self._state.selected_checkpoints.clear()
        self.update()

    def select_checkpoint(self, checkpoint_id: str) -> None:
        """Select a specific checkpoint."""
        checkpoint_item = next(
            (item for item in self._state.checkpoints if item.metadata.checkpoint_id == checkpoint_id),
            None
        )

        if checkpoint_item:
            if self.config.selection_mode == CheckpointSelectionMode.SINGLE:
                self.clear_selection()

            checkpoint_item.is_selected = True
            self._state.selected_checkpoints.add(checkpoint_id)
            self.update()

    def set_search_query(self, query: str) -> None:
        """Set search query programmatically."""
        self._state.search_query = query.lower()
        if self._search_field:
            self._search_field.value = query
        asyncio.create_task(self._apply_filters_and_sorting())
        self.update()

    def set_filter_mode(self, mode: CheckpointFilterMode) -> None:
        """Set filter mode programmatically."""
        self.config.filter_mode = mode
        if self._filter_dropdown:
            self._filter_dropdown.value = mode.value
        asyncio.create_task(self._apply_filters_and_sorting())
        self.update()

    def set_sort_mode(self, mode: CheckpointSortMode) -> None:
        """Set sort mode programmatically."""
        self.config.sort_mode = mode
        if self._sort_dropdown:
            self._sort_dropdown.value = mode.value
        asyncio.create_task(self._apply_filters_and_sorting())
        self.update()

    def get_checkpoint_count(self) -> int:
        """Get total checkpoint count."""
        return len(self._state.checkpoints)

    def get_filtered_checkpoint_count(self) -> int:
        """Get filtered checkpoint count."""
        return len(self._state.filtered_checkpoints)

    def get_checkpoint_by_id(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        """Get checkpoint by ID."""
        checkpoint_item = next(
            (item for item in self._state.checkpoints if item.metadata.checkpoint_id == checkpoint_id),
            None
        )
        return checkpoint_item.metadata if checkpoint_item else None
