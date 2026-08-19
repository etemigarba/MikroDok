"""
Module: checkpoint_list_ui
Description: Training checkpoint management interface for model builder workflow with responsive design and theme integration.
            Provides checkpoint visualization, filtering, sorting, selection, and restore capabilities
            specifically tailored for training sessions with modern UI/UX patterns.
Phase: 4
Location: /src/modules/ui/model_builder_ui/checkpoint_list_ui/checkpoint_list_ui.py
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
        description: str = ""
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


class TrainingCheckpointSortMode(Enum):
    """Training checkpoint sorting modes."""
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


class TrainingCheckpointFilterMode(Enum):
    """Training checkpoint filter modes."""
    ALL = "all"
    VALID = "valid"
    BEST = "best"
    RECENT = "recent"
    MILESTONE = "milestone"
    MANUAL = "manual"
    CORRUPTED = "corrupted"


class TrainingCheckpointDisplayMode(Enum):
    """Training checkpoint display modes."""
    LIST = "list"
    COMPACT = "compact"
    GRID = "grid"


class TrainingCheckpointSelectionMode(Enum):
    """Training checkpoint selection modes."""
    SINGLE = "single"
    MULTIPLE = "multiple"
    NONE = "none"


@dataclass
class TrainingCheckpointListConfig:
    """Configuration for training checkpoint list display."""
    display_mode: TrainingCheckpointDisplayMode = TrainingCheckpointDisplayMode.LIST
    sort_mode: TrainingCheckpointSortMode = TrainingCheckpointSortMode.CREATED_DESC
    filter_mode: TrainingCheckpointFilterMode = TrainingCheckpointFilterMode.ALL
    selection_mode: TrainingCheckpointSelectionMode = TrainingCheckpointSelectionMode.SINGLE
    show_metrics: bool = True
    show_file_sizes: bool = True
    show_restore_button: bool = True
    show_tags: bool = True
    auto_refresh: bool = True
    refresh_interval: int = 30  # seconds
    page_size: int = 20
    enable_search: bool = True
    enable_bulk_operations: bool = False
    compact_view: bool = False


@dataclass
class TrainingCheckpointItem:
    """Wrapper for training checkpoint metadata with UI state."""
    metadata: CheckpointMetadata
    is_selected: bool = False
    is_highlighted: bool = False
    is_expanded: bool = False
    last_accessed: Optional[datetime] = None
    can_restore: bool = True


@dataclass
class TrainingCheckpointListState:
    """State management for training checkpoint list."""
    checkpoints: List[TrainingCheckpointItem] = field(default_factory=list)
    filtered_checkpoints: List[TrainingCheckpointItem] = field(default_factory=list)
    selected_checkpoints: Set[str] = field(default_factory=set)
    search_query: str = ""
    current_page: int = 0
    total_pages: int = 0
    is_loading: bool = False
    last_refresh: Optional[datetime] = None
    error_message: Optional[str] = None
    current_training_session: Optional[str] = None


class CheckpointListUI(ThemeAwareUserControl):
    """
    Training checkpoint management interface for model builder workflow.
    
    Features:
    - Responsive checkpoint list/grid view with breakpoint-aware layouts
    - Training-specific filtering and sorting with real-time updates
    - Search functionality with debounced input
    - Checkpoint restore capabilities with validation
    - Training session integration and status indicators
    - Theme-aware styling with accessibility compliance
    - Integration with training orchestration system
    - Modern UI/UX with smooth animations and transitions
    - Checkpoint validation and integrity checking
    - Training progress correlation and metrics display
    """
    
    def __init__(
        self,
        config: Optional[TrainingCheckpointListConfig] = None,
        on_checkpoint_selected: Optional[Callable[[CheckpointMetadata], None]] = None,
        on_checkpoint_restore: Optional[Callable[[CheckpointMetadata], None]] = None,
        on_checkpoint_delete: Optional[Callable[[CheckpointMetadata], None]] = None,
        training_session_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self.config = config or TrainingCheckpointListConfig()
        
        # Callbacks
        self._on_checkpoint_selected = on_checkpoint_selected
        self._on_checkpoint_restore = on_checkpoint_restore
        self._on_checkpoint_delete = on_checkpoint_delete
        
        # State
        self._state = TrainingCheckpointListState()
        self._state.current_training_session = training_session_id
        
        # Database connection
        self._checkpoint_db = CheckpointRegistryDB()
        
        # UI components
        self._search_field = None
        self._filter_dropdown = None
        self._sort_dropdown = None
        self._checkpoint_list = None
        self._status_text = None
        self._refresh_button = None
        self._main_container = None
        
        # Timers
        self._refresh_timer = None
        self._search_debounce_timer = None
        
        # Initialize UI
        self._initialize_ui()
        
        # Load initial data
        asyncio.create_task(self._initialize_data())
    
    def _initialize_ui(self) -> None:
        """Initialize UI components."""
        try:
            self._create_search_controls()
            self._create_filter_controls()
            self._create_main_content_area()
            self._create_status_bar()
            self._setup_auto_refresh()
            
        except Exception as e:
            logger.error(f"Error initializing checkpoint list UI: {e}")
    
    async def _initialize_data(self) -> None:
        """Initialize checkpoint data."""
        try:
            self._state.is_loading = True
            self.update()
            
            await self._load_checkpoints()
            self._apply_filters()
            self._apply_sorting()
            
            self._state.is_loading = False
            self._state.last_refresh = datetime.now()
            self.update()
            
        except Exception as e:
            logger.error(f"Error initializing checkpoint data: {e}")
            self._state.error_message = str(e)
            self._state.is_loading = False
            self.update()

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

    def _create_toolbar(self) -> ft.Control:
        """Create the toolbar with search and controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # Search field
        self._search_field = ft.TextField(
            hint_text="Search checkpoints...",
            prefix_icon=icons.search,
            border_radius=self.get_responsive_size(8),
            text_size=typography.body_medium.size,
            on_change=self._on_search_change,
            expand=True
        )

        # Filter dropdown
        self._filter_dropdown = ft.Dropdown(
            label="Filter",
            options=[
                ft.dropdown.Option("all", "All Checkpoints"),
                ft.dropdown.Option("valid", "Valid Only"),
                ft.dropdown.Option("best", "Best Checkpoints"),
                ft.dropdown.Option("recent", "Recent"),
                ft.dropdown.Option("milestone", "Milestones"),
                ft.dropdown.Option("manual", "Manual Saves"),
            ],
            value=self.config.filter_mode.value,
            on_change=self._on_filter_change,
            width=self.get_responsive_size(150)
        )

        # Sort dropdown
        self._sort_dropdown = ft.Dropdown(
            label="Sort",
            options=[
                ft.dropdown.Option("created_desc", "Newest First"),
                ft.dropdown.Option("created_asc", "Oldest First"),
                ft.dropdown.Option("epoch_desc", "Latest Epoch"),
                ft.dropdown.Option("epoch_asc", "Earliest Epoch"),
                ft.dropdown.Option("loss_asc", "Best Loss"),
                ft.dropdown.Option("loss_desc", "Worst Loss"),
            ],
            value=self.config.sort_mode.value,
            on_change=self._on_sort_change,
            width=self.get_responsive_size(150)
        )

        # Refresh button
        self._refresh_button = ft.IconButton(
            icon=icons.refresh,
            tooltip="Refresh checkpoints",
            on_click=self._on_refresh_click
        )

        # View mode toggle
        view_mode_button = ft.IconButton(
            icon=icons.view_list if self.config.display_mode == TrainingCheckpointDisplayMode.LIST else icons.grid_view,
            tooltip="Toggle view mode",
            on_click=self._on_view_mode_toggle
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Expanded(child=self._search_field),
                    self._filter_dropdown,
                    self._sort_dropdown,
                    self._refresh_button,
                    view_mode_button
                ],
                spacing=spacing.small,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
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
            if self.config.display_mode == TrainingCheckpointDisplayMode.GRID:
                return self._create_grid_view()
            elif self.config.display_mode == TrainingCheckpointDisplayMode.COMPACT:
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

    def _create_checkpoint_list_item(self, checkpoint_item: TrainingCheckpointItem) -> ft.Control:
        """Create a list item for a checkpoint."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        checkpoint = checkpoint_item.metadata

        # Status indicator
        status_color = palette.success if checkpoint.status == CheckpointStatus.VALID else palette.error
        status_icon = icons.check_circle if checkpoint.status == CheckpointStatus.VALID else icons.error

        # Checkpoint type badge
        type_color = {
            CheckpointType.BEST: palette.primary,
            CheckpointType.MILESTONE: palette.secondary,
            CheckpointType.MANUAL: palette.tertiary,
            CheckpointType.PERIODIC: palette.outline,
            CheckpointType.EMERGENCY: palette.error
        }.get(checkpoint.checkpoint_type, palette.outline)

        # Main content
        main_content = ft.Column(
            controls=[
                # Header row
                ft.Row(
                    controls=[
                        ft.Icon(status_icon, color=status_color, size=self.get_responsive_size(16)),
                        ft.Text(
                            f"Epoch {checkpoint.epoch} - Step {checkpoint.training_step}",
                            style=typography.title_small,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_600
                        ),
                        ft.Container(
                            content=ft.Text(
                                checkpoint.checkpoint_type.value.title(),
                                style=typography.label_small,
                                color=palette.surface,
                                weight=ft.FontWeight.W_500
                            ),
                            bgcolor=type_color,
                            padding=ft.padding.symmetric(horizontal=spacing.xs, vertical=spacing.xs//2),
                            border_radius=self.get_responsive_size(4)
                        ),
                        ft.Spacer(),
                        ft.Text(
                            checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                            style=typography.body_small,
                            color=palette.text_secondary
                        )
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=spacing.small
                ),
                # Metrics row
                ft.Row(
                    controls=[
                        ft.Text(
                            f"Loss: {checkpoint.loss_value:.4f}",
                            style=typography.body_small,
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            f"Size: {self._format_file_size(checkpoint.total_size)}",
                            style=typography.body_small,
                            color=palette.text_secondary
                        ),
                        ft.Spacer(),
                        # Restore button
                        ft.ElevatedButton(
                            text="Restore",
                            icon=icons.restore,
                            on_click=lambda e, cp=checkpoint: self._on_restore_click(cp),
                            disabled=not checkpoint_item.can_restore,
                            style=ft.ButtonStyle(
                                color=palette.primary,
                                bgcolor=palette.primary_container
                            )
                        ) if self.config.show_restore_button else ft.Container()
                    ],
                    spacing=spacing.medium
                )
            ],
            spacing=spacing.xs,
            tight=True
        )

        return ft.Container(
            content=main_content,
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

    def _create_checkpoint_compact_item(self, checkpoint_item: TrainingCheckpointItem) -> ft.Control:
        """Create a compact item for a checkpoint."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        checkpoint = checkpoint_item.metadata

        # Status indicator
        status_color = palette.success if checkpoint.status == CheckpointStatus.VALID else palette.error

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        icons.check_circle if checkpoint.status == CheckpointStatus.VALID else icons.error,
                        color=status_color,
                        size=self.get_responsive_size(14)
                    ),
                    ft.Text(
                        f"E{checkpoint.epoch}",
                        style=typography.label_medium,
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_600
                    ),
                    ft.Text(
                        f"Loss: {checkpoint.loss_value:.3f}",
                        style=typography.body_small,
                        color=palette.text_secondary
                    ),
                    ft.Spacer(),
                    ft.Text(
                        checkpoint.created_at.strftime("%m/%d %H:%M"),
                        style=typography.body_small,
                        color=palette.text_secondary
                    ),
                    ft.IconButton(
                        icon=icons.restore,
                        tooltip="Restore checkpoint",
                        on_click=lambda e, cp=checkpoint: self._on_restore_click(cp),
                        disabled=not checkpoint_item.can_restore,
                        icon_size=self.get_responsive_size(16)
                    ) if self.config.show_restore_button else ft.Container()
                ],
                spacing=spacing.small,
                alignment=ft.MainAxisAlignment.START
            ),
            padding=ft.padding.symmetric(horizontal=spacing.medium, vertical=spacing.small),
            bgcolor=palette.primary_container if checkpoint_item.is_selected else palette.surface,
            border=ft.border.all(
                1,
                palette.primary if checkpoint_item.is_selected else palette.outline_variant
            ),
            border_radius=self.get_responsive_size(6),
            on_click=lambda e, cid=checkpoint.checkpoint_id: self._on_checkpoint_click(cid),
            ink=True
        )

    def _create_grid_view(self) -> ft.Control:
        """Create the grid view for checkpoints."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Calculate pagination
        start_idx = self._state.current_page * self.config.page_size
        end_idx = start_idx + self.config.page_size
        page_checkpoints = self._state.filtered_checkpoints[start_idx:end_idx]

        # Create grid items
        grid_items = []
        for checkpoint_item in page_checkpoints:
            grid_items.append(self._create_checkpoint_grid_item(checkpoint_item))

        # Calculate responsive columns
        columns = self.get_responsive_columns(min_width=280, max_columns=4)

        self._checkpoint_list = ft.GridView(
            controls=grid_items,
            runs_count=columns,
            spacing=spacing.small,
            run_spacing=spacing.small,
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

    def _create_checkpoint_grid_item(self, checkpoint_item: TrainingCheckpointItem) -> ft.Control:
        """Create a grid item for a checkpoint."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        checkpoint = checkpoint_item.metadata

        # Status indicator
        status_color = palette.success if checkpoint.status == CheckpointStatus.VALID else palette.error
        status_icon = icons.check_circle if checkpoint.status == CheckpointStatus.VALID else icons.error

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        # Header
                        ft.Row(
                            controls=[
                                ft.Icon(status_icon, color=status_color, size=self.get_responsive_size(16)),
                                ft.Spacer(),
                                ft.Text(
                                    checkpoint.checkpoint_type.value.title(),
                                    style=typography.label_small,
                                    color=palette.text_secondary
                                )
                            ]
                        ),
                        # Title
                        ft.Text(
                            f"Epoch {checkpoint.epoch}",
                            style=typography.title_medium,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_600
                        ),
                        # Metrics
                        ft.Text(
                            f"Step {checkpoint.training_step}",
                            style=typography.body_small,
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            f"Loss: {checkpoint.loss_value:.4f}",
                            style=typography.body_small,
                            color=palette.text_secondary
                        ),
                        ft.Spacer(),
                        # Actions
                        ft.Row(
                            controls=[
                                ft.TextButton(
                                    text="Restore",
                                    icon=icons.restore,
                                    on_click=lambda e, cp=checkpoint: self._on_restore_click(cp),
                                    disabled=not checkpoint_item.can_restore
                                ) if self.config.show_restore_button else ft.Container(),
                                ft.Spacer(),
                                ft.Text(
                                    checkpoint.created_at.strftime("%m/%d"),
                                    style=typography.body_small,
                                    color=palette.text_secondary
                                )
                            ]
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                ),
                padding=spacing.medium,
                bgcolor=palette.primary_container if checkpoint_item.is_selected else None,
                border=ft.border.all(
                    1,
                    palette.primary if checkpoint_item.is_selected else palette.outline_variant
                ),
                border_radius=self.get_responsive_size(8),
                on_click=lambda e, cid=checkpoint.checkpoint_id: self._on_checkpoint_click(cid),
                ink=True
            )
        )

    def _create_pagination_controls(self) -> ft.Control:
        """Create pagination controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        if self._state.total_pages <= 1:
            return ft.Container()

        # Previous button
        prev_button = ft.IconButton(
            icon=icons.chevron_left,
            disabled=self._state.current_page == 0,
            on_click=self._on_previous_page
        )

        # Next button
        next_button = ft.IconButton(
            icon=icons.chevron_right,
            disabled=self._state.current_page >= self._state.total_pages - 1,
            on_click=self._on_next_page
        )

        # Page info
        page_info = ft.Text(
            f"Page {self._state.current_page + 1} of {self._state.total_pages}",
            style=typography.body_small,
            color=palette.text_secondary
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    prev_button,
                    ft.Spacer(),
                    page_info,
                    ft.Spacer(),
                    next_button
                ],
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )

    def _create_status_bar(self) -> ft.Control:
        """Create the status bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Status text
        self._status_text = ft.Text(
            value=self._get_status_text(),
            style=typography.body_small,
            color=palette.text_secondary
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    self._status_text,
                    ft.Spacer()
                ]
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )

    def _create_loading_state(self) -> ft.Control:
        """Create loading state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(),
                    ft.Text(
                        "Loading checkpoints...",
                        style=typography.body_medium,
                        color=palette.text_secondary
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
        typography = self.get_typography()
        icons = self.get_icons()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        icons.folder_open,
                        size=self.get_responsive_size(64),
                        color=palette.text_disabled
                    ),
                    ft.Text(
                        "No checkpoints found",
                        style=typography.title_medium,
                        color=palette.text_secondary
                    ),
                    ft.Text(
                        "Checkpoints will appear here as training progresses",
                        style=typography.body_medium,
                        color=palette.text_disabled,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_error_state(self, error_message: str) -> ft.Control:
        """Create error state display."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        icons.error,
                        size=self.get_responsive_size(64),
                        color=palette.error
                    ),
                    ft.Text(
                        "Error loading checkpoints",
                        style=typography.title_medium,
                        color=palette.error
                    ),
                    ft.Text(
                        error_message,
                        style=typography.body_medium,
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.ElevatedButton(
                        text="Retry",
                        icon=icons.refresh,
                        on_click=self._on_refresh_click
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.medium
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    # Event Handlers
    def _on_search_change(self, e) -> None:
        """Handle search input change."""
        try:
            self._state.search_query = e.control.value

            # Debounce search
            if self._search_debounce_timer:
                self._search_debounce_timer.cancel()

            self._search_debounce_timer = asyncio.create_task(
                self._debounced_search()
            )

        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    async def _debounced_search(self) -> None:
        """Debounced search implementation."""
        try:
            await asyncio.sleep(0.3)  # 300ms debounce
            self._apply_filters()
            self._state.current_page = 0
            self.update()

        except asyncio.CancelledError:
            pass
        except Exception as ex:
            logger.error(f"Error in debounced search: {ex}")

    def _on_filter_change(self, e) -> None:
        """Handle filter change."""
        try:
            self.config.filter_mode = TrainingCheckpointFilterMode(e.control.value)
            self._apply_filters()
            self._state.current_page = 0
            self.update()

        except Exception as ex:
            logger.error(f"Error handling filter change: {ex}")

    def _on_sort_change(self, e) -> None:
        """Handle sort change."""
        try:
            self.config.sort_mode = TrainingCheckpointSortMode(e.control.value)
            self._apply_sorting()
            self.update()

        except Exception as ex:
            logger.error(f"Error handling sort change: {ex}")

    def _on_refresh_click(self, e) -> None:
        """Handle refresh button click."""
        try:
            asyncio.create_task(self._initialize_data())

        except Exception as ex:
            logger.error(f"Error handling refresh click: {ex}")

    def _on_view_mode_toggle(self, e) -> None:
        """Handle view mode toggle."""
        try:
            if self.config.display_mode == TrainingCheckpointDisplayMode.LIST:
                self.config.display_mode = TrainingCheckpointDisplayMode.GRID
            else:
                self.config.display_mode = TrainingCheckpointDisplayMode.LIST

            # Update button icon
            icons = self.get_icons()
            e.control.icon = icons.view_list if self.config.display_mode == TrainingCheckpointDisplayMode.LIST else icons.grid_view

            self.update()

        except Exception as ex:
            logger.error(f"Error handling view mode toggle: {ex}")

    def _on_checkpoint_click(self, checkpoint_id: str) -> None:
        """Handle checkpoint click."""
        try:
            # Find checkpoint
            checkpoint_item = next(
                (item for item in self._state.checkpoints if item.metadata.checkpoint_id == checkpoint_id),
                None
            )

            if not checkpoint_item:
                return

            # Handle selection
            if self.config.selection_mode == TrainingCheckpointSelectionMode.SINGLE:
                # Clear previous selections
                for item in self._state.checkpoints:
                    item.is_selected = False
                self._state.selected_checkpoints.clear()

                # Select current
                checkpoint_item.is_selected = True
                self._state.selected_checkpoints.add(checkpoint_id)

            elif self.config.selection_mode == TrainingCheckpointSelectionMode.MULTIPLE:
                # Toggle selection
                checkpoint_item.is_selected = not checkpoint_item.is_selected
                if checkpoint_item.is_selected:
                    self._state.selected_checkpoints.add(checkpoint_id)
                else:
                    self._state.selected_checkpoints.discard(checkpoint_id)

            # Trigger callback
            if self._on_checkpoint_selected:
                self._on_checkpoint_selected(checkpoint_item.metadata)

            self.update()

        except Exception as ex:
            logger.error(f"Error handling checkpoint click: {ex}")

    def _on_restore_click(self, checkpoint: CheckpointMetadata) -> None:
        """Handle restore button click."""
        try:
            if self._on_checkpoint_restore:
                self._on_checkpoint_restore(checkpoint)

        except Exception as ex:
            logger.error(f"Error handling restore click: {ex}")

    def _on_previous_page(self, e) -> None:
        """Handle previous page button click."""
        try:
            if self._state.current_page > 0:
                self._state.current_page -= 1
                self.update()

        except Exception as ex:
            logger.error(f"Error handling previous page: {ex}")

    def _on_next_page(self, e) -> None:
        """Handle next page button click."""
        try:
            if self._state.current_page < self._state.total_pages - 1:
                self._state.current_page += 1
                self.update()

        except Exception as ex:
            logger.error(f"Error handling next page: {ex}")

    # Data Management Methods
    async def _load_checkpoints(self) -> None:
        """Load checkpoints from database."""
        try:
            # Get all checkpoints
            checkpoints = self._checkpoint_db.get_all_checkpoints()

            # Filter by training session if specified
            if self._state.current_training_session:
                checkpoints = [
                    cp for cp in checkpoints
                    if getattr(cp, 'training_session_id', None) == self._state.current_training_session
                ]

            # Convert to UI items
            self._state.checkpoints = [
                TrainingCheckpointItem(
                    metadata=cp,
                    can_restore=cp.status == CheckpointStatus.VALID
                )
                for cp in checkpoints
            ]

            logger.info(f"Loaded {len(self._state.checkpoints)} checkpoints")

        except Exception as e:
            logger.error(f"Error loading checkpoints: {e}")
            raise

    def _apply_filters(self) -> None:
        """Apply current filters to checkpoint list."""
        try:
            filtered = self._state.checkpoints.copy()

            # Apply search filter
            if self._state.search_query:
                query = self._state.search_query.lower()
                filtered = [
                    item for item in filtered
                    if (query in item.metadata.description.lower() or
                        query in str(item.metadata.epoch) or
                        query in str(item.metadata.training_step) or
                        any(query in tag.lower() for tag in item.metadata.tags))
                ]

            # Apply status filter
            if self.config.filter_mode == TrainingCheckpointFilterMode.VALID:
                filtered = [item for item in filtered if item.metadata.status == CheckpointStatus.VALID]
            elif self.config.filter_mode == TrainingCheckpointFilterMode.BEST:
                filtered = [item for item in filtered if item.metadata.is_best]
            elif self.config.filter_mode == TrainingCheckpointFilterMode.RECENT:
                # Last 24 hours
                cutoff = datetime.now() - timedelta(hours=24)
                filtered = [item for item in filtered if item.metadata.created_at > cutoff]
            elif self.config.filter_mode == TrainingCheckpointFilterMode.MILESTONE:
                filtered = [item for item in filtered if item.metadata.checkpoint_type == CheckpointType.MILESTONE]
            elif self.config.filter_mode == TrainingCheckpointFilterMode.MANUAL:
                filtered = [item for item in filtered if item.metadata.checkpoint_type == CheckpointType.MANUAL]
            elif self.config.filter_mode == TrainingCheckpointFilterMode.CORRUPTED:
                filtered = [item for item in filtered if item.metadata.status == CheckpointStatus.CORRUPTED]

            self._state.filtered_checkpoints = filtered
            self._calculate_pagination()

        except Exception as e:
            logger.error(f"Error applying filters: {e}")

    def _apply_sorting(self) -> None:
        """Apply current sorting to filtered checkpoint list."""
        try:
            if self.config.sort_mode == TrainingCheckpointSortMode.CREATED_DESC:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.created_at, reverse=True)
            elif self.config.sort_mode == TrainingCheckpointSortMode.CREATED_ASC:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.created_at)
            elif self.config.sort_mode == TrainingCheckpointSortMode.EPOCH_DESC:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.epoch, reverse=True)
            elif self.config.sort_mode == TrainingCheckpointSortMode.EPOCH_ASC:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.epoch)
            elif self.config.sort_mode == TrainingCheckpointSortMode.LOSS_ASC:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.loss_value)
            elif self.config.sort_mode == TrainingCheckpointSortMode.LOSS_DESC:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.loss_value, reverse=True)
            elif self.config.sort_mode == TrainingCheckpointSortMode.SIZE_DESC:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.total_size, reverse=True)
            elif self.config.sort_mode == TrainingCheckpointSortMode.SIZE_ASC:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.total_size)
            elif self.config.sort_mode == TrainingCheckpointSortMode.TYPE:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.checkpoint_type.value)
            elif self.config.sort_mode == TrainingCheckpointSortMode.STATUS:
                self._state.filtered_checkpoints.sort(key=lambda x: x.metadata.status.value)

        except Exception as e:
            logger.error(f"Error applying sorting: {e}")

    def _calculate_pagination(self) -> None:
        """Calculate pagination parameters."""
        try:
            total_items = len(self._state.filtered_checkpoints)
            self._state.total_pages = max(1, (total_items + self.config.page_size - 1) // self.config.page_size)

            # Ensure current page is valid
            if self._state.current_page >= self._state.total_pages:
                self._state.current_page = max(0, self._state.total_pages - 1)

        except Exception as e:
            logger.error(f"Error calculating pagination: {e}")

    # Utility Methods
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        try:
            if size_bytes == 0:
                return "0 B"

            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            while size_bytes >= 1024 and i < len(size_names) - 1:
                size_bytes /= 1024.0
                i += 1

            return f"{size_bytes:.1f} {size_names[i]}"

        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return "Unknown"

    def _get_status_text(self) -> str:
        """Get status bar text."""
        try:
            total = len(self._state.checkpoints)
            filtered = len(self._state.filtered_checkpoints)
            selected = len(self._state.selected_checkpoints)

            if self._state.is_loading:
                return "Loading checkpoints..."
            elif self._state.error_message:
                return f"Error: {self._state.error_message}"
            elif total == 0:
                return "No checkpoints available"
            elif filtered != total:
                status = f"Showing {filtered} of {total} checkpoints"
            else:
                status = f"{total} checkpoint{'s' if total != 1 else ''}"

            if selected > 0:
                status += f" ({selected} selected)"

            if self._state.last_refresh:
                refresh_time = self._state.last_refresh.strftime("%H:%M:%S")
                status += f" • Last updated: {refresh_time}"

            return status

        except Exception as e:
            logger.error(f"Error getting status text: {e}")
            return "Status unavailable"

    def _setup_auto_refresh(self) -> None:
        """Setup auto-refresh timer."""
        try:
            if self.config.auto_refresh and self.config.refresh_interval > 0:
                self._refresh_timer = asyncio.create_task(self._auto_refresh_loop())

        except Exception as e:
            logger.error(f"Error setting up auto-refresh: {e}")

    async def _auto_refresh_loop(self) -> None:
        """Auto-refresh loop."""
        try:
            while self.config.auto_refresh:
                await asyncio.sleep(self.config.refresh_interval)
                if not self._state.is_loading:
                    await self._initialize_data()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in auto-refresh loop: {e}")

    def _create_search_controls(self) -> None:
        """Create search control components."""
        # Search controls are created in _create_toolbar
        pass

    def _create_filter_controls(self) -> None:
        """Create filter control components."""
        # Filter controls are created in _create_toolbar
        pass

    def _create_main_content_area(self) -> None:
        """Create main content area components."""
        # Main content area is created in _create_main_content
        pass

    # Public API Methods
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
        try:
            checkpoint_item = next(
                (item for item in self._state.checkpoints if item.metadata.checkpoint_id == checkpoint_id),
                None
            )

            if checkpoint_item:
                if self.config.selection_mode == TrainingCheckpointSelectionMode.SINGLE:
                    self.clear_selection()

                checkpoint_item.is_selected = True
                self._state.selected_checkpoints.add(checkpoint_id)
                self.update()

        except Exception as e:
            logger.error(f"Error selecting checkpoint: {e}")

    def set_training_session(self, session_id: Optional[str]) -> None:
        """Set the current training session filter."""
        try:
            self._state.current_training_session = session_id
            asyncio.create_task(self._initialize_data())

        except Exception as e:
            logger.error(f"Error setting training session: {e}")

    def update_checkpoint_status(self, checkpoint_id: str, status: CheckpointStatus) -> None:
        """Update checkpoint status."""
        try:
            checkpoint_item = next(
                (item for item in self._state.checkpoints if item.metadata.checkpoint_id == checkpoint_id),
                None
            )

            if checkpoint_item:
                checkpoint_item.metadata.status = status
                checkpoint_item.can_restore = status == CheckpointStatus.VALID
                self.update()

        except Exception as e:
            logger.error(f"Error updating checkpoint status: {e}")

    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            if self._refresh_timer:
                self._refresh_timer.cancel()

            if self._search_debounce_timer:
                self._search_debounce_timer.cancel()

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
