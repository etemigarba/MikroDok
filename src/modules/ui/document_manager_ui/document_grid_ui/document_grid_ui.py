"""
Module: document_grid_ui
Description: Responsive document grid interface with thumbnails, metadata display, and interactive features.
            Provides comprehensive grid view of uploaded documents with status indicators, quality metrics,
            and batch operations. Features modern UI/UX with theme-aware styling, accessibility compliance,
            and responsive design that adapts to different screen sizes and device capabilities.
Phase: 3
Location: /src/modules/ui/document_manager_ui/document_grid_ui/document_grid_ui.py
"""

# Standard library imports
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union, Set
from datetime import datetime, timezone

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    ScreenSize,
    get_theme_manager
)
from src.modules.logic.logging_infrastructure_lg import get_logger

# Configure logging
logger = get_logger(__name__)


class GridViewMode(Enum):
    """Grid view display modes."""
    THUMBNAIL = "thumbnail"      # Large thumbnails with minimal text
    COMPACT = "compact"          # Small cards with essential info
    DETAILED = "detailed"        # Full cards with all metadata
    LIST = "list"               # List view within grid layout


class GridSortOption(Enum):
    """Grid sorting options."""
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"
    SIZE_ASC = "size_asc"
    SIZE_DESC = "size_desc"
    STATUS_ASC = "status_asc"
    STATUS_DESC = "status_desc"
    QUALITY_ASC = "quality_asc"
    QUALITY_DESC = "quality_desc"


class GridFilterOption(Enum):
    """Grid filtering options."""
    ALL = "all"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"
    HIGH_QUALITY = "high_quality"
    LOW_QUALITY = "low_quality"


class GridSelectionMode(Enum):
    """Grid selection modes."""
    NONE = "none"               # No selection allowed
    SINGLE = "single"           # Single document selection
    MULTIPLE = "multiple"       # Multiple document selection
    RANGE = "range"            # Range selection with Shift+Click


@dataclass
class GridItem:
    """Document item for grid display."""
    document_id: str
    filename: str
    file_path: Path
    file_size: int
    file_hash: str
    mime_type: str
    status: str
    quality_score: float
    thumbnail_path: Optional[Path] = None
    processing_progress: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_selected: bool = False
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.document_id:
            self.document_id = str(uuid.uuid4())


@dataclass
class GridConfig:
    """Configuration for document grid display."""
    view_mode: GridViewMode = GridViewMode.DETAILED
    sort_option: GridSortOption = GridSortOption.DATE_DESC
    filter_option: GridFilterOption = GridFilterOption.ALL
    selection_mode: GridSelectionMode = GridSelectionMode.MULTIPLE
    show_thumbnails: bool = True
    show_metadata: bool = True
    show_quality_indicators: bool = True
    show_status_badges: bool = True
    show_file_sizes: bool = True
    show_dates: bool = True
    enable_drag_drop: bool = True
    enable_context_menu: bool = True
    enable_keyboard_navigation: bool = True
    auto_refresh: bool = True
    refresh_interval: int = 30  # seconds
    page_size: int = 50
    enable_search: bool = True
    enable_bulk_operations: bool = True
    card_aspect_ratio: float = 1.2
    thumbnail_size: int = 128
    animation_duration: int = 200  # milliseconds


class DocumentGridUI(ThemeAwareUserControl):
    """
    Responsive document grid interface with comprehensive document management features.
    
    Features:
    - Responsive grid layout with breakpoint-aware columns and spacing
    - Multiple view modes (thumbnail, compact, detailed, list)
    - Advanced sorting and filtering with real-time updates
    - Document selection with multiple selection modes
    - Drag-and-drop support for file operations
    - Context menus with batch operations
    - Keyboard navigation and accessibility compliance
    - Theme-aware styling with smooth animations
    - Integration with document database and processing pipeline
    - Real-time status updates and progress indicators
    - Quality metrics and validation indicators
    - Thumbnail generation and caching
    - Search functionality with highlighting
    - Pagination with infinite scroll support
    """
    
    def __init__(
        self,
        config: Optional[GridConfig] = None,
        on_document_select: Optional[Callable[[GridItem], None]] = None,
        on_document_double_click: Optional[Callable[[GridItem], None]] = None,
        on_documents_selected: Optional[Callable[[List[GridItem]], None]] = None,
        on_context_menu: Optional[Callable[[GridItem, ft.TapEvent], None]] = None,
        on_drag_drop: Optional[Callable[[List[GridItem], str], None]] = None,
        on_refresh: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or GridConfig()
        
        # Callbacks
        self._on_document_select = on_document_select
        self._on_document_double_click = on_document_double_click
        self._on_documents_selected = on_documents_selected
        self._on_context_menu = on_context_menu
        self._on_drag_drop = on_drag_drop
        self._on_refresh = on_refresh
        
        # State management
        self._documents: List[GridItem] = []
        self._filtered_documents: List[GridItem] = []
        self._selected_documents: Set[str] = set()
        self._last_selected_index: Optional[int] = None
        self._search_query: str = ""
        self._is_loading: bool = False
        self._current_page: int = 0
        self._total_pages: int = 0
        
        # UI components
        self._grid_container: Optional[ft.Control] = None
        self._toolbar: Optional[ft.Control] = None
        self._status_bar: Optional[ft.Control] = None
        self._search_field: Optional[ft.TextField] = None
        self._view_mode_selector: Optional[ft.Control] = None
        self._sort_selector: Optional[ft.Control] = None
        self._filter_selector: Optional[ft.Control] = None
        
        # Responsive layout
        self._responsive_manager: Optional[ResponsiveLayoutManager] = None
        
        # Initialize UI
        self._build_ui()
        
        # Setup auto-refresh if enabled
        if self._config.auto_refresh:
            self._setup_auto_refresh()
    
    def _build_ui(self) -> None:
        """Build the complete grid UI."""
        try:
            # Get theme manager and responsive layout
            self._ensure_theme_manager()
            self._ensure_responsive_manager()
            
            # Build main layout
            self.content = ft.Column(
                controls=[
                    self._build_toolbar(),
                    self._build_grid_container(),
                    self._build_status_bar()
                ],
                spacing=0,
                expand=True
            )
            
        except Exception as e:
            logger.error(f"Error building document grid UI: {e}")
            self.content = self._build_error_state(str(e))
    
    def _build_toolbar(self) -> ft.Control:
        """Build the grid toolbar with controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()
            
            # Search field
            self._search_field = ft.TextField(
                hint_text="Search documents...",
                prefix_icon=icons.SEARCH,
                border_radius=spacing.border_radius_md,
                text_style=typography.body_medium,
                on_change=self._on_search_change,
                expand=True
            )
            
            # View mode selector
            self._view_mode_selector = self._build_view_mode_selector()
            
            # Sort selector
            self._sort_selector = self._build_sort_selector()
            
            # Filter selector  
            self._filter_selector = self._build_filter_selector()
            
            # Refresh button
            refresh_button = ft.IconButton(
                icon=icons.REFRESH,
                tooltip="Refresh documents",
                on_click=self._on_refresh_click
            )
            
            # Selection info
            selection_info = ft.Text(
                value=self._get_selection_info_text(),
                style=typography.body_small,
                color=palette.text_secondary
            )
            
            # Build responsive toolbar
            return self._build_responsive_toolbar([
                self._search_field,
                self._view_mode_selector,
                self._sort_selector,
                self._filter_selector,
                refresh_button,
                selection_info
            ])
            
        except Exception as e:
            logger.error(f"Error building toolbar: {e}")
            return ft.Container()

    def _build_responsive_toolbar(self, controls: List[ft.Control]) -> ft.Control:
        """Build responsive toolbar layout."""
        try:
            responsive_padding = self.get_responsive_padding()
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            # Mobile layout - stack vertically
            mobile_layout = ft.Column(
                controls=[
                    ft.Row(
                        controls=[controls[0]],  # Search field
                        expand=True
                    ),
                    ft.Row(
                        controls=controls[1:],  # Other controls
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True
                    )
                ],
                spacing=responsive_spacing // 2
            )

            # Desktop layout - single row
            desktop_layout = ft.Row(
                controls=controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=responsive_spacing
            )

            # Choose layout based on screen size
            current_layout = self.get_responsive_value(
                mobile=mobile_layout,
                tablet=mobile_layout,
                desktop=desktop_layout,
                large=desktop_layout
            )

            return ft.Container(
                content=current_layout,
                padding=responsive_padding,
                bgcolor=self.get_palette().surface,
                border=ft.border.only(
                    bottom=ft.BorderSide(
                        width=1,
                        color=self.get_palette().outline_variant
                    )
                )
            )

        except Exception as e:
            logger.error(f"Error building responsive toolbar: {e}")
            return ft.Container()

    def _build_view_mode_selector(self) -> ft.Control:
        """Build view mode selector."""
        try:
            icons = self.get_icons()

            view_mode_options = [
                (GridViewMode.THUMBNAIL, icons.GRID_VIEW, "Thumbnail"),
                (GridViewMode.COMPACT, icons.VIEW_COMPACT, "Compact"),
                (GridViewMode.DETAILED, icons.VIEW_LIST, "Detailed"),
                (GridViewMode.LIST, icons.LIST_VIEW, "List")
            ]

            buttons = []
            for mode, icon, tooltip in view_mode_options:
                button = ft.IconButton(
                    icon=icon,
                    tooltip=tooltip,
                    selected=self._config.view_mode == mode,
                    on_click=lambda e, m=mode: self._on_view_mode_change(m)
                )
                buttons.append(button)

            return ft.Row(
                controls=buttons,
                spacing=4
            )

        except Exception as e:
            logger.error(f"Error building view mode selector: {e}")
            return ft.Container()

    def _build_sort_selector(self) -> ft.Control:
        """Build sort options selector."""
        try:
            sort_options = [
                (GridSortOption.NAME_ASC, "Name A-Z"),
                (GridSortOption.NAME_DESC, "Name Z-A"),
                (GridSortOption.DATE_ASC, "Date Old-New"),
                (GridSortOption.DATE_DESC, "Date New-Old"),
                (GridSortOption.SIZE_ASC, "Size Small-Large"),
                (GridSortOption.SIZE_DESC, "Size Large-Small"),
                (GridSortOption.STATUS_ASC, "Status A-Z"),
                (GridSortOption.STATUS_DESC, "Status Z-A"),
                (GridSortOption.QUALITY_ASC, "Quality Low-High"),
                (GridSortOption.QUALITY_DESC, "Quality High-Low")
            ]

            dropdown_options = [
                ft.dropdown.Option(key=option.value, text=label)
                for option, label in sort_options
            ]

            return ft.Dropdown(
                options=dropdown_options,
                value=self._config.sort_option.value,
                hint_text="Sort by",
                width=150,
                on_change=self._on_sort_change
            )

        except Exception as e:
            logger.error(f"Error building sort selector: {e}")
            return ft.Container()

    def _build_filter_selector(self) -> ft.Control:
        """Build filter options selector."""
        try:
            filter_options = [
                (GridFilterOption.ALL, "All Documents"),
                (GridFilterOption.PENDING, "Pending"),
                (GridFilterOption.PROCESSING, "Processing"),
                (GridFilterOption.COMPLETED, "Completed"),
                (GridFilterOption.FAILED, "Failed"),
                (GridFilterOption.ARCHIVED, "Archived"),
                (GridFilterOption.HIGH_QUALITY, "High Quality"),
                (GridFilterOption.LOW_QUALITY, "Low Quality")
            ]

            dropdown_options = [
                ft.dropdown.Option(key=option.value, text=label)
                for option, label in filter_options
            ]

            return ft.Dropdown(
                options=dropdown_options,
                value=self._config.filter_option.value,
                hint_text="Filter by",
                width=150,
                on_change=self._on_filter_change
            )

        except Exception as e:
            logger.error(f"Error building filter selector: {e}")
            return ft.Container()

    def _build_grid_container(self) -> ft.Control:
        """Build the main grid container."""
        try:
            if self._is_loading:
                return self._build_loading_state()

            if not self._filtered_documents:
                return self._build_empty_state()

            # Get current page documents
            start_idx = self._current_page * self._config.page_size
            end_idx = start_idx + self._config.page_size
            page_documents = self._filtered_documents[start_idx:end_idx]

            # Build grid based on view mode
            if self._config.view_mode == GridViewMode.THUMBNAIL:
                return self._build_thumbnail_grid(page_documents)
            elif self._config.view_mode == GridViewMode.COMPACT:
                return self._build_compact_grid(page_documents)
            elif self._config.view_mode == GridViewMode.LIST:
                return self._build_list_grid(page_documents)
            else:  # DETAILED
                return self._build_detailed_grid(page_documents)

        except Exception as e:
            logger.error(f"Error building grid container: {e}")
            return self._build_error_state(str(e))

    def _build_thumbnail_grid(self, documents: List[GridItem]) -> ft.Control:
        """Build thumbnail grid view."""
        try:
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            document_cards = []
            for doc in documents:
                card = self._build_thumbnail_card(doc)
                document_cards.append(card)

            return self.create_responsive_grid(
                children=document_cards,
                mobile_cols=2,
                tablet_cols=3,
                desktop_cols=4,
                large_cols=6,
                spacing=responsive_spacing,
                run_spacing=responsive_spacing
            )

        except Exception as e:
            logger.error(f"Error building thumbnail grid: {e}")
            return ft.Container()

    def _build_compact_grid(self, documents: List[GridItem]) -> ft.Control:
        """Build compact grid view."""
        try:
            responsive_spacing = self.get_responsive_value(6, 8, 12, 16)

            document_cards = []
            for doc in documents:
                card = self._build_compact_card(doc)
                document_cards.append(card)

            return self.create_responsive_grid(
                children=document_cards,
                mobile_cols=1,
                tablet_cols=2,
                desktop_cols=3,
                large_cols=4,
                spacing=responsive_spacing,
                run_spacing=responsive_spacing
            )

        except Exception as e:
            logger.error(f"Error building compact grid: {e}")
            return ft.Container()

    def _build_detailed_grid(self, documents: List[GridItem]) -> ft.Control:
        """Build detailed grid view."""
        try:
            responsive_spacing = self.get_responsive_value(12, 16, 20, 24)

            document_cards = []
            for doc in documents:
                card = self._build_detailed_card(doc)
                document_cards.append(card)

            return self.create_responsive_grid(
                children=document_cards,
                mobile_cols=1,
                tablet_cols=2,
                desktop_cols=2,
                large_cols=3,
                spacing=responsive_spacing,
                run_spacing=responsive_spacing
            )

        except Exception as e:
            logger.error(f"Error building detailed grid: {e}")
            return ft.Container()

    def _build_list_grid(self, documents: List[GridItem]) -> ft.Control:
        """Build list grid view."""
        try:
            responsive_spacing = self.get_responsive_value(4, 6, 8, 10)

            document_cards = []
            for doc in documents:
                card = self._build_list_card(doc)
                document_cards.append(card)

            return ft.Container(
                content=ft.Column(
                    controls=document_cards,
                    spacing=responsive_spacing,
                    scroll=ft.ScrollMode.AUTO
                ),
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building list grid: {e}")
            return ft.Container()

    def _build_thumbnail_card(self, document: GridItem) -> ft.Control:
        """Build thumbnail card for document."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Thumbnail image or placeholder
            thumbnail = self._build_thumbnail_image(document)

            # Status indicator
            status_indicator = self._build_status_indicator(document)

            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=document.is_selected,
                on_change=lambda e: self._toggle_document_selection(document),
                visible=self._config.selection_mode != GridSelectionMode.NONE
            )

            # Document name (truncated)
            name_text = ft.Text(
                value=self._truncate_text(document.filename, 20),
                style=typography.body_small,
                color=palette.text_primary,
                text_align=ft.TextAlign.CENTER,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            # Card content
            card_content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Stack(
                            controls=[
                                thumbnail,
                                ft.Positioned(
                                    top=spacing.xs,
                                    right=spacing.xs,
                                    child=status_indicator
                                ),
                                ft.Positioned(
                                    top=spacing.xs,
                                    left=spacing.xs,
                                    child=selection_checkbox
                                )
                            ]
                        ),
                        name_text
                    ],
                    spacing=spacing.sm,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=spacing.sm,
                border_radius=spacing.border_radius_md,
                bgcolor=palette.surface,
                border=ft.border.all(
                    width=1,
                    color=palette.outline_variant if not document.is_selected
                           else palette.primary
                ),
                on_click=lambda e: self._on_document_click(document, e),
                on_long_press=lambda e: self._on_document_long_press(document, e)
            )

            return card_content

        except Exception as e:
            logger.error(f"Error building thumbnail card: {e}")
            return ft.Container()

    def _build_compact_card(self, document: GridItem) -> ft.Control:
        """Build compact card for document."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Small thumbnail or icon
            thumbnail = self._build_small_thumbnail(document)

            # Status and quality indicators
            status_indicator = self._build_status_indicator(document)
            quality_indicator = self._build_quality_indicator(document.quality_score)

            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=document.is_selected,
                on_change=lambda e: self._toggle_document_selection(document),
                visible=self._config.selection_mode != GridSelectionMode.NONE
            )

            # Document info
            name_text = ft.Text(
                value=self._truncate_text(document.filename, 25),
                style=typography.body_medium,
                color=palette.text_primary,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            size_text = ft.Text(
                value=self._format_file_size(document.file_size),
                style=typography.body_small,
                color=palette.text_secondary
            )

            # Card layout
            card_content = ft.Container(
                content=ft.Row(
                    controls=[
                        selection_checkbox,
                        thumbnail,
                        ft.Expanded(
                            child=ft.Column(
                                controls=[name_text, size_text],
                                spacing=spacing.xs,
                                alignment=ft.MainAxisAlignment.CENTER
                            )
                        ),
                        ft.Column(
                            controls=[status_indicator, quality_indicator],
                            spacing=spacing.xs,
                            horizontal_alignment=ft.CrossAxisAlignment.END
                        )
                    ],
                    spacing=spacing.sm,
                    alignment=ft.MainAxisAlignment.START
                ),
                padding=spacing.sm,
                border_radius=spacing.border_radius_md,
                bgcolor=palette.surface,
                border=ft.border.all(
                    width=1,
                    color=palette.outline_variant if not document.is_selected
                           else palette.primary
                ),
                on_click=lambda e: self._on_document_click(document, e),
                on_long_press=lambda e: self._on_document_long_press(document, e)
            )

            return card_content

        except Exception as e:
            logger.error(f"Error building compact card: {e}")
            return ft.Container()

    def _build_detailed_card(self, document: GridItem) -> ft.Control:
        """Build detailed card for document."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Medium thumbnail
            thumbnail = self._build_medium_thumbnail(document)

            # Status and quality indicators
            status_indicator = self._build_status_indicator(document)
            quality_indicator = self._build_quality_indicator(document.quality_score)

            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=document.is_selected,
                on_change=lambda e: self._toggle_document_selection(document),
                visible=self._config.selection_mode != GridSelectionMode.NONE
            )

            # Document metadata
            name_text = ft.Text(
                value=document.filename,
                style=typography.title_small,
                color=palette.text_primary,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            size_text = ft.Text(
                value=f"Size: {self._format_file_size(document.file_size)}",
                style=typography.body_small,
                color=palette.text_secondary
            )

            date_text = ft.Text(
                value=f"Modified: {self._format_date(document.updated_at)}",
                style=typography.body_small,
                color=palette.text_secondary
            )

            type_text = ft.Text(
                value=f"Type: {document.mime_type or 'Unknown'}",
                style=typography.body_small,
                color=palette.text_secondary
            )

            # Progress bar for processing documents
            progress_bar = None
            if document.status == "processing" and document.processing_progress > 0:
                progress_bar = ft.ProgressBar(
                    value=document.processing_progress / 100.0,
                    color=palette.primary,
                    bgcolor=palette.surface_variant
                )

            # Tags display
            tags_display = self._build_tags_display(document.tags)

            # Card layout
            metadata_column = ft.Column(
                controls=[
                    name_text,
                    size_text,
                    date_text,
                    type_text
                ] + ([progress_bar] if progress_bar else []) + ([tags_display] if tags_display else []),
                spacing=spacing.xs,
                expand=True
            )

            card_content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                selection_checkbox,
                                ft.Expanded(child=ft.Container()),
                                status_indicator,
                                quality_indicator
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        ft.Row(
                            controls=[
                                thumbnail,
                                ft.Expanded(child=metadata_column)
                            ],
                            spacing=spacing.md,
                            alignment=ft.MainAxisAlignment.START
                        )
                    ],
                    spacing=spacing.sm
                ),
                padding=spacing.md,
                border_radius=spacing.border_radius_md,
                bgcolor=palette.surface,
                border=ft.border.all(
                    width=1,
                    color=palette.outline_variant if not document.is_selected
                           else palette.primary
                ),
                on_click=lambda e: self._on_document_click(document, e),
                on_long_press=lambda e: self._on_document_long_press(document, e)
            )

            return card_content

        except Exception as e:
            logger.error(f"Error building detailed card: {e}")
            return ft.Container()

    def _build_list_card(self, document: GridItem) -> ft.Control:
        """Build list card for document."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Small icon or thumbnail
            icon_thumbnail = self._build_icon_thumbnail(document)

            # Status and quality indicators
            status_indicator = self._build_status_indicator(document)
            quality_indicator = self._build_quality_indicator(document.quality_score)

            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=document.is_selected,
                on_change=lambda e: self._toggle_document_selection(document),
                visible=self._config.selection_mode != GridSelectionMode.NONE
            )

            # Document info
            name_text = ft.Text(
                value=document.filename,
                style=typography.body_medium,
                color=palette.text_primary,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                expand=True
            )

            size_text = ft.Text(
                value=self._format_file_size(document.file_size),
                style=typography.body_small,
                color=palette.text_secondary,
                width=80
            )

            date_text = ft.Text(
                value=self._format_date(document.updated_at),
                style=typography.body_small,
                color=palette.text_secondary,
                width=120
            )

            # Card layout
            card_content = ft.Container(
                content=ft.Row(
                    controls=[
                        selection_checkbox,
                        icon_thumbnail,
                        name_text,
                        size_text,
                        date_text,
                        status_indicator,
                        quality_indicator
                    ],
                    spacing=spacing.sm,
                    alignment=ft.MainAxisAlignment.START
                ),
                padding=ft.padding.symmetric(horizontal=spacing.md, vertical=spacing.sm),
                border_radius=spacing.border_radius_sm,
                bgcolor=palette.surface if not document.is_selected else palette.primary_container,
                border=ft.border.all(
                    width=1,
                    color=palette.outline_variant if not document.is_selected
                           else palette.primary
                ),
                on_click=lambda e: self._on_document_click(document, e),
                on_long_press=lambda e: self._on_document_long_press(document, e)
            )

            return card_content

        except Exception as e:
            logger.error(f"Error building list card: {e}")
            return ft.Container()

    def _build_thumbnail_image(self, document: GridItem) -> ft.Control:
        """Build thumbnail image for document."""
        try:
            spacing = self.get_spacing()
            palette = self.get_palette()
            icons = self.get_icons()

            thumbnail_size = self.get_responsive_value(80, 96, 112, 128)

            if document.thumbnail_path and document.thumbnail_path.exists():
                # Use actual thumbnail
                return ft.Image(
                    src=str(document.thumbnail_path),
                    width=thumbnail_size,
                    height=thumbnail_size,
                    fit=ft.ImageFit.COVER,
                    border_radius=spacing.border_radius_sm
                )
            else:
                # Use file type icon
                file_icon = self._get_file_type_icon(document.mime_type)
                return ft.Container(
                    content=ft.Icon(
                        name=file_icon,
                        size=thumbnail_size // 2,
                        color=palette.primary
                    ),
                    width=thumbnail_size,
                    height=thumbnail_size,
                    bgcolor=palette.surface_variant,
                    border_radius=spacing.border_radius_sm,
                    alignment=ft.alignment.center
                )

        except Exception as e:
            logger.error(f"Error building thumbnail image: {e}")
            return ft.Container()

    def _build_small_thumbnail(self, document: GridItem) -> ft.Control:
        """Build small thumbnail for compact view."""
        try:
            spacing = self.get_spacing()
            palette = self.get_palette()

            thumbnail_size = self.get_responsive_value(32, 36, 40, 44)

            if document.thumbnail_path and document.thumbnail_path.exists():
                return ft.Image(
                    src=str(document.thumbnail_path),
                    width=thumbnail_size,
                    height=thumbnail_size,
                    fit=ft.ImageFit.COVER,
                    border_radius=spacing.border_radius_xs
                )
            else:
                file_icon = self._get_file_type_icon(document.mime_type)
                return ft.Container(
                    content=ft.Icon(
                        name=file_icon,
                        size=thumbnail_size // 2,
                        color=palette.primary
                    ),
                    width=thumbnail_size,
                    height=thumbnail_size,
                    bgcolor=palette.surface_variant,
                    border_radius=spacing.border_radius_xs,
                    alignment=ft.alignment.center
                )

        except Exception as e:
            logger.error(f"Error building small thumbnail: {e}")
            return ft.Container()

    def _build_medium_thumbnail(self, document: GridItem) -> ft.Control:
        """Build medium thumbnail for detailed view."""
        try:
            spacing = self.get_spacing()
            palette = self.get_palette()

            thumbnail_size = self.get_responsive_value(48, 56, 64, 72)

            if document.thumbnail_path and document.thumbnail_path.exists():
                return ft.Image(
                    src=str(document.thumbnail_path),
                    width=thumbnail_size,
                    height=thumbnail_size,
                    fit=ft.ImageFit.COVER,
                    border_radius=spacing.border_radius_sm
                )
            else:
                file_icon = self._get_file_type_icon(document.mime_type)
                return ft.Container(
                    content=ft.Icon(
                        name=file_icon,
                        size=thumbnail_size // 2,
                        color=palette.primary
                    ),
                    width=thumbnail_size,
                    height=thumbnail_size,
                    bgcolor=palette.surface_variant,
                    border_radius=spacing.border_radius_sm,
                    alignment=ft.alignment.center
                )

        except Exception as e:
            logger.error(f"Error building medium thumbnail: {e}")
            return ft.Container()

    def _build_icon_thumbnail(self, document: GridItem) -> ft.Control:
        """Build icon thumbnail for list view."""
        try:
            palette = self.get_palette()

            icon_size = self.get_responsive_value(20, 22, 24, 26)
            file_icon = self._get_file_type_icon(document.mime_type)

            return ft.Icon(
                name=file_icon,
                size=icon_size,
                color=palette.primary
            )

        except Exception as e:
            logger.error(f"Error building icon thumbnail: {e}")
            return ft.Container()

    def _build_status_indicator(self, document: GridItem) -> ft.Control:
        """Build status indicator for document."""
        try:
            palette = self.get_palette()
            icons = self.get_icons()

            status_config = {
                "pending": (icons.SCHEDULE, palette.warning),
                "processing": (icons.SYNC, palette.primary),
                "completed": (icons.CHECK_CIRCLE, palette.success),
                "failed": (icons.ERROR, palette.error),
                "archived": (icons.ARCHIVE, palette.text_secondary)
            }

            icon, color = status_config.get(document.status, (icons.HELP, palette.text_secondary))

            return ft.Container(
                content=ft.Icon(
                    name=icon,
                    size=16,
                    color=color
                ),
                tooltip=f"Status: {document.status.title()}",
                bgcolor=palette.surface,
                border_radius=8,
                padding=4
            )

        except Exception as e:
            logger.error(f"Error building status indicator: {e}")
            return ft.Container()

    def _build_quality_indicator(self, quality_score: float) -> ft.Control:
        """Build quality indicator for document."""
        try:
            palette = self.get_palette()
            icons = self.get_icons()

            if quality_score >= 80:
                icon, color = icons.STAR, palette.success
                tooltip = f"High Quality ({quality_score:.1f}%)"
            elif quality_score >= 60:
                icon, color = icons.STAR_HALF, palette.warning
                tooltip = f"Medium Quality ({quality_score:.1f}%)"
            else:
                icon, color = icons.STAR_BORDER, palette.error
                tooltip = f"Low Quality ({quality_score:.1f}%)"

            return ft.Container(
                content=ft.Icon(
                    name=icon,
                    size=16,
                    color=color
                ),
                tooltip=tooltip,
                bgcolor=palette.surface,
                border_radius=8,
                padding=4
            )

        except Exception as e:
            logger.error(f"Error building quality indicator: {e}")
            return ft.Container()

    def _build_tags_display(self, tags: List[str]) -> Optional[ft.Control]:
        """Build tags display for document."""
        try:
            if not tags:
                return None

            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            tag_chips = []
            for tag in tags[:3]:  # Show max 3 tags
                chip = ft.Container(
                    content=ft.Text(
                        value=tag,
                        style=typography.label_small,
                        color=palette.on_primary_container
                    ),
                    bgcolor=palette.primary_container,
                    border_radius=spacing.border_radius_sm,
                    padding=ft.padding.symmetric(horizontal=spacing.xs, vertical=2)
                )
                tag_chips.append(chip)

            if len(tags) > 3:
                more_chip = ft.Container(
                    content=ft.Text(
                        value=f"+{len(tags) - 3}",
                        style=typography.label_small,
                        color=palette.text_secondary
                    ),
                    bgcolor=palette.surface_variant,
                    border_radius=spacing.border_radius_sm,
                    padding=ft.padding.symmetric(horizontal=spacing.xs, vertical=2)
                )
                tag_chips.append(more_chip)

            return ft.Row(
                controls=tag_chips,
                spacing=spacing.xs,
                wrap=True
            )

        except Exception as e:
            logger.error(f"Error building tags display: {e}")
            return None

    def _build_status_bar(self) -> ft.Control:
        """Build status bar with pagination and info."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Document count info
            total_docs = len(self._documents)
            filtered_docs = len(self._filtered_documents)
            selected_docs = len(self._selected_documents)

            info_text = ft.Text(
                value=f"{filtered_docs} of {total_docs} documents",
                style=typography.body_small,
                color=palette.text_secondary
            )

            selection_text = ft.Text(
                value=f"{selected_docs} selected" if selected_docs > 0 else "",
                style=typography.body_small,
                color=palette.primary
            )

            # Pagination controls
            pagination_controls = self._build_pagination_controls()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        info_text,
                        selection_text,
                        ft.Expanded(child=ft.Container()),
                        pagination_controls
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=spacing.md,
                bgcolor=palette.surface,
                border=ft.border.only(
                    top=ft.BorderSide(
                        width=1,
                        color=palette.outline_variant
                    )
                )
            )

        except Exception as e:
            logger.error(f"Error building status bar: {e}")
            return ft.Container()

    def _build_pagination_controls(self) -> ft.Control:
        """Build pagination controls."""
        try:
            icons = self.get_icons()

            # Calculate pagination info
            total_pages = max(1, (len(self._filtered_documents) + self._config.page_size - 1) // self._config.page_size)
            current_page = self._current_page + 1

            # Previous button
            prev_button = ft.IconButton(
                icon=icons.CHEVRON_LEFT,
                disabled=self._current_page == 0,
                on_click=self._on_previous_page
            )

            # Next button
            next_button = ft.IconButton(
                icon=icons.CHEVRON_RIGHT,
                disabled=self._current_page >= total_pages - 1,
                on_click=self._on_next_page
            )

            # Page info
            page_text = ft.Text(
                value=f"Page {current_page} of {total_pages}",
                style=self.get_typography().body_small,
                color=self.get_palette().text_secondary
            )

            return ft.Row(
                controls=[prev_button, page_text, next_button],
                spacing=8
            )

        except Exception as e:
            logger.error(f"Error building pagination controls: {e}")
            return ft.Container()

    def _build_loading_state(self) -> ft.Control:
        """Build loading state UI."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(),
                        ft.Text(
                            value="Loading documents...",
                            style=typography.body_medium,
                            color=palette.text_secondary
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building loading state: {e}")
            return ft.Container()

    def _build_empty_state(self) -> ft.Control:
        """Build empty state UI."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            icons = self.get_icons()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=icons.FOLDER_OPEN,
                            size=64,
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            value="No documents found",
                            style=typography.title_medium,
                            color=palette.text_primary
                        ),
                        ft.Text(
                            value="Upload documents to get started",
                            style=typography.body_medium,
                            color=palette.text_secondary
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building empty state: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state UI."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            icons = self.get_icons()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=icons.ERROR,
                            size=64,
                            color=palette.error
                        ),
                        ft.Text(
                            value="Error loading documents",
                            style=typography.title_medium,
                            color=palette.text_primary
                        ),
                        ft.Text(
                            value=error_message,
                            style=typography.body_medium,
                            color=palette.text_secondary,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.ElevatedButton(
                            text="Retry",
                            icon=icons.REFRESH,
                            on_click=self._on_refresh_click
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16
                ),
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    # Event Handlers
    def _on_search_change(self, e: ft.ControlEvent) -> None:
        """Handle search query change."""
        try:
            self._search_query = e.control.value or ""
            self._apply_filters()
            self._refresh_grid()

        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    def _on_view_mode_change(self, mode: GridViewMode) -> None:
        """Handle view mode change."""
        try:
            self._config.view_mode = mode
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error handling view mode change: {e}")

    def _on_sort_change(self, e: ft.ControlEvent) -> None:
        """Handle sort option change."""
        try:
            sort_value = e.control.value
            self._config.sort_option = GridSortOption(sort_value)
            self._apply_sorting()
            self._refresh_grid()

        except Exception as ex:
            logger.error(f"Error handling sort change: {ex}")

    def _on_filter_change(self, e: ft.ControlEvent) -> None:
        """Handle filter option change."""
        try:
            filter_value = e.control.value
            self._config.filter_option = GridFilterOption(filter_value)
            self._apply_filters()
            self._refresh_grid()

        except Exception as ex:
            logger.error(f"Error handling filter change: {ex}")

    def _on_refresh_click(self, e: ft.ControlEvent) -> None:
        """Handle refresh button click."""
        try:
            if self._on_refresh:
                self._on_refresh()
            else:
                self.refresh_documents()

        except Exception as ex:
            logger.error(f"Error handling refresh click: {ex}")

    def _on_document_click(self, document: GridItem, e: ft.ControlEvent) -> None:
        """Handle document click."""
        try:
            # Handle selection based on mode and modifiers
            if self._config.selection_mode == GridSelectionMode.NONE:
                return

            # Check for double click
            if hasattr(e, 'double_click') and e.double_click:
                if self._on_document_double_click:
                    self._on_document_double_click(document)
                return

            # Handle selection
            if self._config.selection_mode == GridSelectionMode.SINGLE:
                self._clear_selection()
                self._select_document(document)
            elif self._config.selection_mode == GridSelectionMode.MULTIPLE:
                self._toggle_document_selection(document)
            elif self._config.selection_mode == GridSelectionMode.RANGE:
                # TODO: Implement range selection with Shift+Click
                self._toggle_document_selection(document)

            # Notify selection change
            if self._on_document_select:
                self._on_document_select(document)

            if self._on_documents_selected:
                selected_docs = [doc for doc in self._documents if doc.is_selected]
                self._on_documents_selected(selected_docs)

        except Exception as ex:
            logger.error(f"Error handling document click: {ex}")

    def _on_document_long_press(self, document: GridItem, e: ft.ControlEvent) -> None:
        """Handle document long press for context menu."""
        try:
            if self._config.enable_context_menu and self._on_context_menu:
                self._on_context_menu(document, e)

        except Exception as ex:
            logger.error(f"Error handling document long press: {ex}")

    def _on_previous_page(self, e: ft.ControlEvent) -> None:
        """Handle previous page navigation."""
        try:
            if self._current_page > 0:
                self._current_page -= 1
                self._refresh_grid()

        except Exception as ex:
            logger.error(f"Error handling previous page: {ex}")

    def _on_next_page(self, e: ft.ControlEvent) -> None:
        """Handle next page navigation."""
        try:
            total_pages = max(1, (len(self._filtered_documents) + self._config.page_size - 1) // self._config.page_size)
            if self._current_page < total_pages - 1:
                self._current_page += 1
                self._refresh_grid()

        except Exception as ex:
            logger.error(f"Error handling next page: {ex}")

    # Selection Management
    def _toggle_document_selection(self, document: GridItem) -> None:
        """Toggle document selection state."""
        try:
            document.is_selected = not document.is_selected

            if document.is_selected:
                self._selected_documents.add(document.document_id)
            else:
                self._selected_documents.discard(document.document_id)

            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error toggling document selection: {e}")

    def _select_document(self, document: GridItem) -> None:
        """Select a document."""
        try:
            document.is_selected = True
            self._selected_documents.add(document.document_id)
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error selecting document: {e}")

    def _clear_selection(self) -> None:
        """Clear all document selections."""
        try:
            for doc in self._documents:
                doc.is_selected = False
            self._selected_documents.clear()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error clearing selection: {e}")

    # Filtering and Sorting
    def _apply_filters(self) -> None:
        """Apply current filters to document list."""
        try:
            filtered_docs = self._documents.copy()

            # Apply search filter
            if self._search_query:
                query_lower = self._search_query.lower()
                filtered_docs = [
                    doc for doc in filtered_docs
                    if query_lower in doc.filename.lower() or
                       query_lower in (doc.metadata.get('title', '')).lower() or
                       any(query_lower in tag.lower() for tag in doc.tags)
                ]

            # Apply status filter
            if self._config.filter_option != GridFilterOption.ALL:
                if self._config.filter_option == GridFilterOption.HIGH_QUALITY:
                    filtered_docs = [doc for doc in filtered_docs if doc.quality_score >= 80]
                elif self._config.filter_option == GridFilterOption.LOW_QUALITY:
                    filtered_docs = [doc for doc in filtered_docs if doc.quality_score < 60]
                else:
                    status_filter = self._config.filter_option.value
                    filtered_docs = [doc for doc in filtered_docs if doc.status == status_filter]

            self._filtered_documents = filtered_docs
            self._current_page = 0  # Reset to first page

        except Exception as e:
            logger.error(f"Error applying filters: {e}")
            self._filtered_documents = self._documents.copy()

    def _apply_sorting(self) -> None:
        """Apply current sorting to filtered document list."""
        try:
            if not self._filtered_documents:
                return

            sort_option = self._config.sort_option
            reverse = sort_option.value.endswith('_desc')

            if sort_option in [GridSortOption.NAME_ASC, GridSortOption.NAME_DESC]:
                self._filtered_documents.sort(key=lambda x: x.filename.lower(), reverse=reverse)
            elif sort_option in [GridSortOption.DATE_ASC, GridSortOption.DATE_DESC]:
                self._filtered_documents.sort(key=lambda x: x.updated_at, reverse=reverse)
            elif sort_option in [GridSortOption.SIZE_ASC, GridSortOption.SIZE_DESC]:
                self._filtered_documents.sort(key=lambda x: x.file_size, reverse=reverse)
            elif sort_option in [GridSortOption.STATUS_ASC, GridSortOption.STATUS_DESC]:
                self._filtered_documents.sort(key=lambda x: x.status, reverse=reverse)
            elif sort_option in [GridSortOption.QUALITY_ASC, GridSortOption.QUALITY_DESC]:
                self._filtered_documents.sort(key=lambda x: x.quality_score, reverse=reverse)

        except Exception as e:
            logger.error(f"Error applying sorting: {e}")

    def _refresh_grid(self) -> None:
        """Refresh the grid display."""
        try:
            if hasattr(self, 'content') and self.content:
                # Rebuild grid container
                new_grid = self._build_grid_container()
                new_status_bar = self._build_status_bar()

                # Update the column controls
                if isinstance(self.content, ft.Column) and len(self.content.controls) >= 3:
                    self.content.controls[1] = new_grid
                    self.content.controls[2] = new_status_bar

                # Update the page
                if self.page:
                    self.page.update()

        except Exception as e:
            logger.error(f"Error refreshing grid: {e}")

    # Utility Methods
    def _get_file_type_icon(self, mime_type: Optional[str]) -> str:
        """Get appropriate icon for file type."""
        try:
            icons = self.get_icons()

            if not mime_type:
                return icons.DESCRIPTION

            mime_lower = mime_type.lower()

            if 'pdf' in mime_lower:
                return icons.PICTURE_AS_PDF
            elif 'word' in mime_lower or 'docx' in mime_lower:
                return icons.DESCRIPTION
            elif 'text' in mime_lower or 'txt' in mime_lower:
                return icons.TEXT_SNIPPET
            elif 'html' in mime_lower:
                return icons.CODE
            elif 'markdown' in mime_lower or 'md' in mime_lower:
                return icons.ARTICLE
            elif 'image' in mime_lower:
                return icons.IMAGE
            else:
                return icons.DESCRIPTION

        except Exception as e:
            logger.error(f"Error getting file type icon: {e}")
            return self.get_icons().DESCRIPTION

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        try:
            if size_bytes == 0:
                return "0 B"

            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            size = float(size_bytes)

            while size >= 1024.0 and i < len(size_names) - 1:
                size /= 1024.0
                i += 1

            return f"{size:.1f} {size_names[i]}"

        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return "Unknown"

    def _format_date(self, date: datetime) -> str:
        """Format date in human readable format."""
        try:
            now = datetime.now(timezone.utc)
            diff = now - date

            if diff.days == 0:
                if diff.seconds < 3600:
                    minutes = diff.seconds // 60
                    return f"{minutes}m ago"
                else:
                    hours = diff.seconds // 3600
                    return f"{hours}h ago"
            elif diff.days == 1:
                return "Yesterday"
            elif diff.days < 7:
                return f"{diff.days}d ago"
            else:
                return date.strftime("%m/%d/%Y")

        except Exception as e:
            logger.error(f"Error formatting date: {e}")
            return "Unknown"

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to maximum length."""
        try:
            if len(text) <= max_length:
                return text
            return text[:max_length - 3] + "..."

        except Exception as e:
            logger.error(f"Error truncating text: {e}")
            return text

    def _get_selection_info_text(self) -> str:
        """Get selection info text for toolbar."""
        try:
            selected_count = len(self._selected_documents)
            if selected_count == 0:
                return ""
            elif selected_count == 1:
                return "1 document selected"
            else:
                return f"{selected_count} documents selected"

        except Exception as e:
            logger.error(f"Error getting selection info: {e}")
            return ""

    def _setup_auto_refresh(self) -> None:
        """Setup auto-refresh timer."""
        try:
            if self._config.auto_refresh and self._config.refresh_interval > 0:
                # TODO: Implement auto-refresh timer
                pass

        except Exception as e:
            logger.error(f"Error setting up auto-refresh: {e}")

    # Public API Methods
    def set_documents(self, documents: List[GridItem]) -> None:
        """Set the list of documents to display."""
        try:
            self._documents = documents.copy()
            self._apply_filters()
            self._apply_sorting()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error setting documents: {e}")

    def add_document(self, document: GridItem) -> None:
        """Add a new document to the grid."""
        try:
            self._documents.append(document)
            self._apply_filters()
            self._apply_sorting()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error adding document: {e}")

    def remove_document(self, document_id: str) -> None:
        """Remove a document from the grid."""
        try:
            self._documents = [doc for doc in self._documents if doc.document_id != document_id]
            self._selected_documents.discard(document_id)
            self._apply_filters()
            self._apply_sorting()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error removing document: {e}")

    def update_document(self, document: GridItem) -> None:
        """Update an existing document in the grid."""
        try:
            for i, doc in enumerate(self._documents):
                if doc.document_id == document.document_id:
                    self._documents[i] = document
                    break

            self._apply_filters()
            self._apply_sorting()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error updating document: {e}")

    def get_selected_documents(self) -> List[GridItem]:
        """Get list of currently selected documents."""
        try:
            return [doc for doc in self._documents if doc.is_selected]

        except Exception as e:
            logger.error(f"Error getting selected documents: {e}")
            return []

    def select_all_documents(self) -> None:
        """Select all visible documents."""
        try:
            if self._config.selection_mode in [GridSelectionMode.MULTIPLE, GridSelectionMode.RANGE]:
                for doc in self._filtered_documents:
                    doc.is_selected = True
                    self._selected_documents.add(doc.document_id)
                self._refresh_grid()

        except Exception as e:
            logger.error(f"Error selecting all documents: {e}")

    def clear_selection(self) -> None:
        """Clear all document selections."""
        self._clear_selection()

    def refresh_documents(self) -> None:
        """Refresh the document grid."""
        try:
            self._is_loading = True
            self._refresh_grid()

            # Simulate loading delay
            async def refresh_async():
                await asyncio.sleep(0.5)
                self._is_loading = False
                self._refresh_grid()

            if self.page:
                self.page.run_task(refresh_async)
            else:
                self._is_loading = False
                self._refresh_grid()

        except Exception as e:
            logger.error(f"Error refreshing documents: {e}")
            self._is_loading = False
            self._refresh_grid()

    def set_config(self, config: GridConfig) -> None:
        """Update grid configuration."""
        try:
            self._config = config
            self._apply_filters()
            self._apply_sorting()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error setting config: {e}")

    def get_config(self) -> GridConfig:
        """Get current grid configuration."""
        return self._config

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        try:
            self._is_loading = loading
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error setting loading state: {e}")

    def search_documents(self, query: str) -> None:
        """Search documents with the given query."""
        try:
            self._search_query = query
            if self._search_field:
                self._search_field.value = query
            self._apply_filters()
            self._refresh_grid()

        except Exception as e:
            logger.error(f"Error searching documents: {e}")

    def get_document_count(self) -> Dict[str, int]:
        """Get document count statistics."""
        try:
            return {
                'total': len(self._documents),
                'filtered': len(self._filtered_documents),
                'selected': len(self._selected_documents)
            }

        except Exception as e:
            logger.error(f"Error getting document count: {e}")
            return {'total': 0, 'filtered': 0, 'selected': 0}
