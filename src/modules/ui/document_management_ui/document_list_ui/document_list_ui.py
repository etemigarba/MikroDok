"""
Module: document_list_ui
Description: Comprehensive document listing interface with responsive design, filtering, sorting, and search capabilities.
            Provides grid/list view of processed documents with batch operations, quality indicators, and modern UI/UX.
            Fully integrated with theme system and responsive layout management for optimal user experience.

Phase: 4
Location: /src/modules/ui/document_management_ui/document_list_ui/document_list_ui.py

Features:
- Responsive document list/grid view with adaptive layouts
- Advanced filtering and sorting capabilities
- Real-time search with debounced input
- Batch selection and operations
- Document status indicators and quality metrics
- Pagination with infinite scroll support
- Theme-aware styling with accessibility compliance
- Integration with document database and processing pipeline
- Modern UI/UX with smooth animations and transitions
"""

# Standard library imports
import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    ScreenSize
)

# Configure logging
logger = logging.getLogger(__name__)


class DocumentStatus(Enum):
    """Document processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class SortOption(Enum):
    """Document sorting options."""
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


class FilterOption(Enum):
    """Document filtering options."""
    ALL = "all"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    MARKDOWN = "md"


class ViewMode(Enum):
    """Document view mode options."""
    LIST = "list"
    GRID = "grid"
    COMPACT = "compact"


@dataclass
class DocumentItem:
    """Document item data structure."""
    document_id: str
    filename: str
    file_path: str
    file_size: int
    file_hash: str
    mime_type: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    chunk_count: int = 0
    is_selected: bool = False


class DocumentListUI(ThemeAwareUserControl):
    """
    Comprehensive document listing interface with responsive design and theme integration.
    
    Features:
    - Responsive document list/grid view with breakpoint-aware layouts
    - Advanced filtering and sorting with real-time updates
    - Search functionality with debounced input
    - Batch selection and operations
    - Document status indicators and quality metrics
    - Pagination with infinite scroll support
    - Theme-aware styling with accessibility compliance
    - Integration with document database and processing pipeline
    - Modern UI/UX with smooth animations and transitions
    """

    def __init__(self,
                 documents: Optional[List[DocumentItem]] = None,
                 on_document_select: Optional[Callable[[DocumentItem], None]] = None,
                 on_document_action: Optional[Callable[[str, DocumentItem], None]] = None,
                 on_batch_action: Optional[Callable[[str, List[DocumentItem]], None]] = None,
                 on_filter_change: Optional[Callable[[FilterOption], None]] = None,
                 on_sort_change: Optional[Callable[[SortOption], None]] = None,
                 on_search: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize document list UI component.

        Args:
            documents: List of document items to display
            on_document_select: Callback for document selection
            on_document_action: Callback for document actions (view, edit, delete)
            on_batch_action: Callback for batch operations
            on_filter_change: Callback for filter changes
            on_sort_change: Callback for sort changes
            on_search: Callback for search queries
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Data and state
        self._documents = documents or []
        self._filtered_documents = self._documents.copy()
        self._selected_documents: List[DocumentItem] = []
        self._current_filter = FilterOption.ALL
        self._current_sort = SortOption.DATE_DESC
        self._current_view = ViewMode.LIST
        self._search_query = ""
        self._is_loading = False
        self._page_size = 20
        self._current_page = 0
        
        # Callbacks
        self._on_document_select = on_document_select
        self._on_document_action = on_document_action
        self._on_batch_action = on_batch_action
        self._on_filter_change = on_filter_change
        self._on_sort_change = on_sort_change
        self._on_search = on_search
        
        # UI components
        self._search_field: Optional[ft.TextField] = None
        self._filter_dropdown: Optional[ft.Dropdown] = None
        self._sort_dropdown: Optional[ft.Dropdown] = None
        self._view_toggle: Optional[ft.SegmentedButton] = None
        self._document_container: Optional[ft.Container] = None
        self._pagination_controls: Optional[ft.Container] = None
        self._batch_controls: Optional[ft.Container] = None
        self._status_bar: Optional[ft.Container] = None
        
        # Search debouncing
        self._search_timer: Optional[asyncio.Task] = None
        self._search_delay = 0.5  # 500ms delay

    def build(self) -> ft.Control:
        """Build the responsive document list interface."""
        try:
            # Get responsive values
            responsive_padding = self.get_responsive_padding()
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)
            
            # Create main layout
            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        self._build_header_section(),
                        self._build_toolbar_section(),
                        self._build_batch_controls_section(),
                        self._build_document_list_section(),
                        self._build_pagination_section(),
                        self._build_status_bar_section()
                    ],
                    spacing=responsive_spacing,
                    expand=True
                ),
                padding=responsive_padding
            )
            
        except Exception as e:
            logger.error(f"Error building document list UI: {e}")
            return self._build_error_state(str(e))

    def _build_header_section(self) -> ft.Control:
        """Build the header section with title and summary."""
        try:
            responsive_title_size = self.get_responsive_size(20, 22, 24, 26)
            responsive_subtitle_size = self.get_responsive_size(14, 15, 16, 16)
            
            total_docs = len(self._documents)
            selected_count = len(self._selected_documents)
            
            title_text = "Document Library"
            if selected_count > 0:
                title_text += f" ({selected_count} selected)"
            
            subtitle_text = f"{total_docs} documents"
            if self._search_query:
                filtered_count = len(self._filtered_documents)
                subtitle_text = f"{filtered_count} of {total_docs} documents"
            
            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                title_text,
                                size=responsive_title_size,
                                weight=ft.FontWeight.W_600
                            ),
                            ft.Text(
                                subtitle_text,
                                size=responsive_subtitle_size,
                                opacity=0.7
                            )
                        ],
                        spacing=4,
                        tight=True
                    ),
                    padding=self.get_responsive_padding()
                )
            )
            
        except Exception as e:
            logger.error(f"Error building header section: {e}")
            return ft.Container()

    def _build_toolbar_section(self) -> ft.Control:
        """Build the toolbar with search, filters, and view controls."""
        try:
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)
            
            # Search field
            self._search_field = self.create_themed_component(
                "input",
                variant="outlined",
                label="Search documents...",
                prefix_icon=ft.Icons.SEARCH,
                on_change=self._on_search_change,
                expand=True
            )
            
            # Filter dropdown
            self._filter_dropdown = self.create_themed_component(
                "dropdown",
                variant="outlined",
                label="Filter",
                options=[
                    ft.dropdown.Option(key=option.value, text=option.value.title())
                    for option in FilterOption
                ],
                value=self._current_filter.value,
                on_change=self._on_filter_change_handler
            )
            
            # Sort dropdown
            self._sort_dropdown = self.create_themed_component(
                "dropdown",
                variant="outlined",
                label="Sort",
                options=[
                    ft.dropdown.Option(key=option.value, text=self._get_sort_label(option))
                    for option in SortOption
                ],
                value=self._current_sort.value,
                on_change=self._on_sort_change_handler
            )
            
            # View mode toggle
            self._view_toggle = ft.SegmentedButton(
                segments=[
                    ft.Segment(
                        value=ViewMode.LIST.value,
                        icon=ft.Icons.LIST,
                        label=ft.Text("List") if not self.is_mobile() else None
                    ),
                    ft.Segment(
                        value=ViewMode.GRID.value,
                        icon=ft.Icons.GRID_VIEW,
                        label=ft.Text("Grid") if not self.is_mobile() else None
                    ),
                    ft.Segment(
                        value=ViewMode.COMPACT.value,
                        icon=ft.Icons.VIEW_COMPACT,
                        label=ft.Text("Compact") if not self.is_mobile() else None
                    )
                ],
                selected={self._current_view.value},
                on_change=self._on_view_change
            )
            
            # Responsive layout
            if self.is_mobile():
                return ft.Column(
                    controls=[
                        self._search_field,
                        ft.Row(
                            controls=[
                                ft.Container(self._filter_dropdown, expand=1),
                                ft.Container(self._sort_dropdown, expand=1)
                            ],
                            spacing=responsive_spacing
                        ),
                        self._view_toggle
                    ],
                    spacing=responsive_spacing
                )
            else:
                return ft.Row(
                    controls=[
                        ft.Container(self._search_field, expand=2),
                        self._filter_dropdown,
                        self._sort_dropdown,
                        self._view_toggle
                    ],
                    spacing=responsive_spacing,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
                
        except Exception as e:
            logger.error(f"Error building toolbar section: {e}")
            return ft.Container()

    def _build_batch_controls_section(self) -> ft.Control:
        """Build batch controls section for selected documents."""
        try:
            if not self._selected_documents:
                return ft.Container(height=0)

            selected_count = len(self._selected_documents)
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            # Batch action buttons
            batch_buttons = [
                self.create_themed_component(
                    "button",
                    variant="outlined",
                    text="View Selected",
                    icon=ft.Icons.VISIBILITY,
                    on_click=lambda _: self._handle_batch_action("view")
                ),
                self.create_themed_component(
                    "button",
                    variant="outlined",
                    text="Download",
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda _: self._handle_batch_action("download")
                ),
                self.create_themed_component(
                    "button",
                    variant="outlined",
                    text="Reprocess",
                    icon=ft.Icons.REFRESH,
                    on_click=lambda _: self._handle_batch_action("reprocess")
                ),
                self.create_themed_component(
                    "button",
                    variant="error",
                    text="Delete",
                    icon=ft.Icons.DELETE,
                    on_click=lambda _: self._handle_batch_action("delete")
                )
            ]

            # Clear selection button
            clear_button = self.create_themed_component(
                "button",
                variant="text",
                text="Clear Selection",
                icon=ft.Icons.CLEAR,
                on_click=lambda _: self._clear_selection()
            )

            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                f"{selected_count} document{'s' if selected_count != 1 else ''} selected",
                                weight=ft.FontWeight.W_500
                            ),
                            ft.Row(
                                controls=batch_buttons + [clear_button],
                                spacing=responsive_spacing,
                                wrap=True
                            )
                        ],
                        spacing=responsive_spacing,
                        tight=True
                    ),
                    padding=self.get_responsive_padding()
                )
            )

        except Exception as e:
            logger.error(f"Error building batch controls section: {e}")
            return ft.Container()

    def _build_document_list_section(self) -> ft.Control:
        """Build the main document list/grid section."""
        try:
            if self._is_loading:
                return self._build_loading_state()

            if not self._filtered_documents:
                return self._build_empty_state()

            # Get current page documents
            start_idx = self._current_page * self._page_size
            end_idx = start_idx + self._page_size
            page_documents = self._filtered_documents[start_idx:end_idx]

            if self._current_view == ViewMode.GRID:
                return self._build_grid_view(page_documents)
            elif self._current_view == ViewMode.COMPACT:
                return self._build_compact_view(page_documents)
            else:
                return self._build_list_view(page_documents)

        except Exception as e:
            logger.error(f"Error building document list section: {e}")
            return self._build_error_state(str(e))

    def _build_list_view(self, documents: List[DocumentItem]) -> ft.Control:
        """Build list view of documents."""
        try:
            responsive_spacing = self.get_responsive_value(4, 6, 8, 10)

            document_cards = []
            for doc in documents:
                card = self._build_document_card(doc, ViewMode.LIST)
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
            logger.error(f"Error building list view: {e}")
            return ft.Container()

    def _build_grid_view(self, documents: List[DocumentItem]) -> ft.Control:
        """Build grid view of documents."""
        try:
            responsive_cols = self.get_responsive_columns()
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            document_cards = []
            for doc in documents:
                card = self._build_document_card(doc, ViewMode.GRID)
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
            logger.error(f"Error building grid view: {e}")
            return ft.Container()

    def _build_compact_view(self, documents: List[DocumentItem]) -> ft.Control:
        """Build compact view of documents."""
        try:
            responsive_spacing = self.get_responsive_value(2, 3, 4, 5)

            document_rows = []
            for doc in documents:
                row = self._build_document_row(doc)
                document_rows.append(row)

            return ft.Container(
                content=ft.Column(
                    controls=[
                        self._build_compact_header(),
                        ft.Container(
                            content=ft.Column(
                                controls=document_rows,
                                spacing=responsive_spacing,
                                scroll=ft.ScrollMode.AUTO
                            ),
                            expand=True
                        )
                    ],
                    spacing=responsive_spacing
                ),
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building compact view: {e}")
            return ft.Container()

    def _build_document_card(self, document: DocumentItem, view_mode: ViewMode) -> ft.Control:
        """Build a document card for list or grid view."""
        try:
            responsive_padding = self.get_responsive_padding()
            responsive_spacing = self.get_responsive_value(8, 10, 12, 14)

            # Status indicator
            status_color = self._get_status_color(document.status)
            status_icon = self._get_status_icon(document.status)

            # File size formatting
            file_size_text = self._format_file_size(document.file_size)

            # Quality score indicator
            quality_indicator = self._build_quality_indicator(document.quality_score)

            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=document.is_selected,
                on_change=lambda e: self._toggle_document_selection(document)
            )

            # Document info
            if view_mode == ViewMode.GRID:
                content = ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                selection_checkbox,
                                ft.Icon(status_icon, color=status_color, size=16),
                                quality_indicator
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        ft.Text(
                            document.filename,
                            size=14,
                            weight=ft.FontWeight.W_500,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS
                        ),
                        ft.Text(
                            f"{file_size_text} • {document.status.value.title()}",
                            size=12,
                            opacity=0.7
                        ),
                        ft.Text(
                            document.created_at.strftime("%Y-%m-%d %H:%M"),
                            size=11,
                            opacity=0.5
                        ),
                        self._build_document_actions(document, compact=True)
                    ],
                    spacing=responsive_spacing,
                    tight=True
                )
            else:  # List view
                content = ft.Row(
                    controls=[
                        selection_checkbox,
                        ft.Icon(status_icon, color=status_color, size=20),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    document.filename,
                                    size=14,
                                    weight=ft.FontWeight.W_500,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS
                                ),
                                ft.Text(
                                    f"{file_size_text} • {document.mime_type} • {document.created_at.strftime('%Y-%m-%d %H:%M')}",
                                    size=12,
                                    opacity=0.7
                                )
                            ],
                            spacing=2,
                            expand=True
                        ),
                        quality_indicator,
                        self._build_document_actions(document, compact=False)
                    ],
                    spacing=responsive_spacing,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )

            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=content,
                    padding=responsive_padding,
                    on_click=lambda _: self._handle_document_select(document)
                )
            )

        except Exception as e:
            logger.error(f"Error building document card: {e}")
            return ft.Container()

    def _build_document_row(self, document: DocumentItem) -> ft.Control:
        """Build a compact document row."""
        try:
            responsive_padding = self.get_responsive_value(8, 10, 12, 14)

            # Status indicator
            status_color = self._get_status_color(document.status)
            status_icon = self._get_status_icon(document.status)

            # File size formatting
            file_size_text = self._format_file_size(document.file_size)

            # Selection checkbox
            selection_checkbox = ft.Checkbox(
                value=document.is_selected,
                on_change=lambda e: self._toggle_document_selection(document),
                scale=0.8
            )

            return ft.Container(
                content=ft.Row(
                    controls=[
                        selection_checkbox,
                        ft.Icon(status_icon, color=status_color, size=16),
                        ft.Container(
                            content=ft.Text(
                                document.filename,
                                size=13,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS
                            ),
                            expand=True
                        ),
                        ft.Text(file_size_text, size=11, opacity=0.7),
                        ft.Text(
                            document.created_at.strftime("%m/%d"),
                            size=11,
                            opacity=0.7
                        ),
                        self._build_quality_indicator(document.quality_score, compact=True),
                        ft.IconButton(
                            icon=ft.Icons.MORE_VERT,
                            icon_size=16,
                            on_click=lambda _: self._show_document_menu(document)
                        )
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.symmetric(horizontal=responsive_padding, vertical=4),
                on_click=lambda _: self._handle_document_select(document)
            )

        except Exception as e:
            logger.error(f"Error building document row: {e}")
            return ft.Container()

    def _build_compact_header(self) -> ft.Control:
        """Build header for compact view."""
        try:
            responsive_padding = self.get_responsive_value(8, 10, 12, 14)

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Checkbox(
                            value=self._all_selected(),
                            tristate=self._some_selected(),
                            on_change=self._toggle_select_all
                        ),
                        ft.Text("Status", size=12, weight=ft.FontWeight.W_500, expand=False),
                        ft.Container(
                            content=ft.Text("Name", size=12, weight=ft.FontWeight.W_500),
                            expand=True
                        ),
                        ft.Text("Size", size=12, weight=ft.FontWeight.W_500),
                        ft.Text("Date", size=12, weight=ft.FontWeight.W_500),
                        ft.Text("Quality", size=12, weight=ft.FontWeight.W_500),
                        ft.Container(width=40)  # Space for menu button
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=ft.padding.symmetric(horizontal=responsive_padding, vertical=8),
                bgcolor=self.get_theme_manager().get_color("surface_variant") if self.get_theme_manager() else None
            )

        except Exception as e:
            logger.error(f"Error building compact header: {e}")
            return ft.Container()

    def _build_document_actions(self, document: DocumentItem, compact: bool = False) -> ft.Control:
        """Build document action buttons."""
        try:
            if compact:
                return ft.IconButton(
                    icon=ft.Icons.MORE_VERT,
                    icon_size=16,
                    on_click=lambda _: self._show_document_menu(document)
                )
            else:
                return ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.VISIBILITY,
                            tooltip="View Document",
                            on_click=lambda _: self._handle_document_action("view", document)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            tooltip="Edit Metadata",
                            on_click=lambda _: self._handle_document_action("edit", document)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DOWNLOAD,
                            tooltip="Download",
                            on_click=lambda _: self._handle_document_action("download", document)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE,
                            tooltip="Delete",
                            on_click=lambda _: self._handle_document_action("delete", document)
                        )
                    ],
                    spacing=4,
                    tight=True
                )

        except Exception as e:
            logger.error(f"Error building document actions: {e}")
            return ft.Container()

    def _build_quality_indicator(self, quality_score: float, compact: bool = False) -> ft.Control:
        """Build quality score indicator."""
        try:
            if quality_score == 0:
                return ft.Container(width=20 if compact else 40)

            # Determine quality level and color
            if quality_score >= 80:
                color = self.get_theme_manager().get_color("success") if self.get_theme_manager() else ft.Colors.GREEN
                icon = ft.Icons.CHECK_CIRCLE
            elif quality_score >= 60:
                color = self.get_theme_manager().get_color("warning") if self.get_theme_manager() else ft.Colors.ORANGE
                icon = ft.Icons.WARNING
            else:
                color = self.get_theme_manager().get_color("error") if self.get_theme_manager() else ft.Colors.RED
                icon = ft.Icons.ERROR

            if compact:
                return ft.Icon(icon, color=color, size=16)
            else:
                return ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon, color=color, size=16),
                            ft.Text(f"{quality_score:.0f}%", size=12, color=color)
                        ],
                        spacing=4,
                        tight=True
                    )
                )

        except Exception as e:
            logger.error(f"Error building quality indicator: {e}")
            return ft.Container()

    def _build_pagination_section(self) -> ft.Control:
        """Build pagination controls."""
        try:
            if not self._filtered_documents:
                return ft.Container(height=0)

            total_docs = len(self._filtered_documents)
            total_pages = (total_docs + self._page_size - 1) // self._page_size

            if total_pages <= 1:
                return ft.Container(height=0)

            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            # Page info
            start_idx = self._current_page * self._page_size + 1
            end_idx = min((self._current_page + 1) * self._page_size, total_docs)
            page_info = f"Showing {start_idx}-{end_idx} of {total_docs}"

            # Navigation buttons
            prev_button = self.create_themed_component(
                "button",
                variant="outlined",
                text="Previous",
                icon=ft.Icons.CHEVRON_LEFT,
                disabled=self._current_page == 0,
                on_click=lambda _: self._go_to_page(self._current_page - 1)
            )

            next_button = self.create_themed_component(
                "button",
                variant="outlined",
                text="Next",
                icon=ft.Icons.CHEVRON_RIGHT,
                disabled=self._current_page >= total_pages - 1,
                on_click=lambda _: self._go_to_page(self._current_page + 1)
            )

            # Page selector (for desktop)
            page_controls = [prev_button]

            if not self.is_mobile():
                # Add page numbers for desktop
                start_page = max(0, self._current_page - 2)
                end_page = min(total_pages, start_page + 5)

                for page_num in range(start_page, end_page):
                    page_button = self.create_themed_component(
                        "button",
                        variant="filled" if page_num == self._current_page else "text",
                        text=str(page_num + 1),
                        on_click=lambda _, p=page_num: self._go_to_page(p)
                    )
                    page_controls.append(page_button)

            page_controls.append(next_button)

            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(page_info, size=14, opacity=0.7),
                            ft.Row(
                                controls=page_controls,
                                spacing=responsive_spacing,
                                tight=True
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    padding=self.get_responsive_padding()
                )
            )

        except Exception as e:
            logger.error(f"Error building pagination section: {e}")
            return ft.Container()

    def _build_status_bar_section(self) -> ft.Control:
        """Build status bar with document statistics."""
        try:
            if not self._documents:
                return ft.Container(height=0)

            # Calculate statistics
            total_docs = len(self._documents)
            status_counts = {}
            total_size = 0

            for doc in self._documents:
                status_counts[doc.status] = status_counts.get(doc.status, 0) + 1
                total_size += doc.file_size

            # Format total size
            total_size_text = self._format_file_size(total_size)

            # Status indicators
            status_indicators = []
            for status in DocumentStatus:
                count = status_counts.get(status, 0)
                if count > 0:
                    color = self._get_status_color(status)
                    indicator = ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    self._get_status_icon(status),
                                    color=color,
                                    size=14
                                ),
                                ft.Text(
                                    f"{status.value.title()}: {count}",
                                    size=12,
                                    color=color
                                )
                            ],
                            spacing=4,
                            tight=True
                        )
                    )
                    status_indicators.append(indicator)

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(
                            f"Total: {total_docs} documents ({total_size_text})",
                            size=12,
                            opacity=0.7
                        ),
                        ft.Row(
                            controls=status_indicators,
                            spacing=16,
                            wrap=True
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True
                ),
                padding=self.get_responsive_padding()
            )

        except Exception as e:
            logger.error(f"Error building status bar section: {e}")
            return ft.Container()

    def _build_loading_state(self) -> ft.Control:
        """Build loading state indicator."""
        try:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(),
                        ft.Text(
                            "Loading documents...",
                            size=16,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16
                ),
                alignment=ft.alignment.center,
                expand=True,
                padding=self.get_responsive_padding()
            )

        except Exception as e:
            logger.error(f"Error building loading state: {e}")
            return ft.Container()

    def _build_empty_state(self) -> ft.Control:
        """Build empty state when no documents are found."""
        try:
            if self._search_query or self._current_filter != FilterOption.ALL:
                # No results for current filter/search
                message = "No documents match your current filters."
                if self._search_query:
                    message = f"No documents found for '{self._search_query}'."

                return ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                ft.Icons.SEARCH_OFF,
                                size=64,
                                opacity=0.5
                            ),
                            ft.Text(
                                message,
                                size=18,
                                text_align=ft.TextAlign.CENTER,
                                opacity=0.7
                            ),
                            ft.Text(
                                "Try adjusting your search terms or filters.",
                                size=14,
                                text_align=ft.TextAlign.CENTER,
                                opacity=0.5
                            ),
                            self.create_themed_component(
                                "button",
                                variant="outlined",
                                text="Clear Filters",
                                icon=ft.Icons.CLEAR,
                                on_click=lambda _: self._clear_filters()
                            )
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=16
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                    padding=self.get_responsive_padding()
                )
            else:
                # No documents at all
                return ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                ft.Icons.FOLDER_OPEN,
                                size=64,
                                opacity=0.5
                            ),
                            ft.Text(
                                "No documents yet",
                                size=18,
                                text_align=ft.TextAlign.CENTER,
                                opacity=0.7
                            ),
                            ft.Text(
                                "Upload your first document to get started.",
                                size=14,
                                text_align=ft.TextAlign.CENTER,
                                opacity=0.5
                            ),
                            self.create_themed_component(
                                "button",
                                variant="filled",
                                text="Upload Documents",
                                icon=ft.Icons.UPLOAD_FILE,
                                on_click=lambda _: self._handle_upload_action()
                            )
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=16
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                    padding=self.get_responsive_padding()
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
                            color=self.get_theme_manager().get_color("error") if self.get_theme_manager() else ft.Colors.RED
                        ),
                        ft.Text(
                            "Error loading documents",
                            size=18,
                            text_align=ft.TextAlign.CENTER,
                            color=self.get_theme_manager().get_color("error") if self.get_theme_manager() else ft.Colors.RED
                        ),
                        ft.Text(
                            error_message,
                            size=14,
                            text_align=ft.TextAlign.CENTER,
                            opacity=0.7
                        ),
                        self.create_themed_component(
                            "button",
                            variant="outlined",
                            text="Retry",
                            icon=ft.Icons.REFRESH,
                            on_click=lambda _: self._refresh_documents()
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16
                ),
                alignment=ft.alignment.center,
                expand=True,
                padding=self.get_responsive_padding()
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    # Event handlers
    def _on_search_change(self, e):
        """Handle search input changes with debouncing."""
        try:
            search_query = e.control.value

            # Cancel previous timer
            if self._search_timer:
                self._search_timer.cancel()

            # Start new timer
            self._search_timer = asyncio.create_task(
                self._debounced_search(search_query)
            )

        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    async def _debounced_search(self, query: str):
        """Perform debounced search."""
        try:
            await asyncio.sleep(self._search_delay)
            self._search_query = query
            self._apply_filters()
            self._current_page = 0

            if self._on_search:
                self._on_search(query)

            self.update()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in debounced search: {e}")

    def _on_filter_change_handler(self, e):
        """Handle filter dropdown changes."""
        try:
            filter_value = e.control.value
            self._current_filter = FilterOption(filter_value)
            self._apply_filters()
            self._current_page = 0

            if self._on_filter_change:
                self._on_filter_change(self._current_filter)

            self.update()

        except Exception as ex:
            logger.error(f"Error handling filter change: {ex}")

    def _on_sort_change_handler(self, e):
        """Handle sort dropdown changes."""
        try:
            sort_value = e.control.value
            self._current_sort = SortOption(sort_value)
            self._apply_sorting()
            self._current_page = 0

            if self._on_sort_change:
                self._on_sort_change(self._current_sort)

            self.update()

        except Exception as ex:
            logger.error(f"Error handling sort change: {ex}")

    def _on_view_change(self, e):
        """Handle view mode changes."""
        try:
            view_value = list(e.control.selected)[0]
            self._current_view = ViewMode(view_value)
            self.update()

        except Exception as ex:
            logger.error(f"Error handling view change: {ex}")

    def _toggle_document_selection(self, document: DocumentItem):
        """Toggle document selection state."""
        try:
            document.is_selected = not document.is_selected

            if document.is_selected:
                if document not in self._selected_documents:
                    self._selected_documents.append(document)
            else:
                if document in self._selected_documents:
                    self._selected_documents.remove(document)

            self.update()

        except Exception as e:
            logger.error(f"Error toggling document selection: {e}")

    def _toggle_select_all(self, e):
        """Toggle select all documents."""
        try:
            select_all = e.control.value

            for document in self._filtered_documents:
                document.is_selected = select_all

            if select_all:
                self._selected_documents = self._filtered_documents.copy()
            else:
                self._selected_documents.clear()

            self.update()

        except Exception as ex:
            logger.error(f"Error toggling select all: {ex}")

    def _handle_document_select(self, document: DocumentItem):
        """Handle document selection."""
        try:
            if self._on_document_select:
                self._on_document_select(document)

        except Exception as e:
            logger.error(f"Error handling document select: {e}")

    def _handle_document_action(self, action: str, document: DocumentItem):
        """Handle document actions."""
        try:
            if self._on_document_action:
                self._on_document_action(action, document)

        except Exception as e:
            logger.error(f"Error handling document action: {e}")

    def _handle_batch_action(self, action: str):
        """Handle batch actions on selected documents."""
        try:
            if self._selected_documents and self._on_batch_action:
                self._on_batch_action(action, self._selected_documents.copy())

        except Exception as e:
            logger.error(f"Error handling batch action: {e}")

    def _show_document_menu(self, document: DocumentItem):
        """Show context menu for document."""
        try:
            # This would typically show a context menu
            # For now, we'll just trigger the document action handler
            if self._on_document_action:
                self._on_document_action("menu", document)

        except Exception as e:
            logger.error(f"Error showing document menu: {e}")

    def _go_to_page(self, page: int):
        """Navigate to specific page."""
        try:
            total_pages = (len(self._filtered_documents) + self._page_size - 1) // self._page_size

            if 0 <= page < total_pages:
                self._current_page = page
                self.update()

        except Exception as e:
            logger.error(f"Error navigating to page: {e}")

    def _clear_selection(self):
        """Clear all document selections."""
        try:
            for document in self._selected_documents:
                document.is_selected = False

            self._selected_documents.clear()
            self.update()

        except Exception as e:
            logger.error(f"Error clearing selection: {e}")

    def _clear_filters(self):
        """Clear all filters and search."""
        try:
            self._search_query = ""
            self._current_filter = FilterOption.ALL
            self._current_page = 0

            if self._search_field:
                self._search_field.value = ""

            if self._filter_dropdown:
                self._filter_dropdown.value = FilterOption.ALL.value

            self._apply_filters()
            self.update()

        except Exception as e:
            logger.error(f"Error clearing filters: {e}")

    def _handle_upload_action(self):
        """Handle upload action from empty state."""
        try:
            # This would typically trigger the upload dialog
            # For now, we'll just log the action
            logger.info("Upload action triggered from empty state")

        except Exception as e:
            logger.error(f"Error handling upload action: {e}")

    def _refresh_documents(self):
        """Refresh document list."""
        try:
            self._is_loading = True
            self.update()

            # This would typically reload documents from the database
            # For now, we'll just reset the loading state
            self._is_loading = False
            self.update()

        except Exception as e:
            logger.error(f"Error refreshing documents: {e}")

    # Utility methods
    def _apply_filters(self):
        """Apply current filters to document list."""
        try:
            filtered_docs = self._documents.copy()

            # Apply search filter
            if self._search_query:
                query_lower = self._search_query.lower()
                filtered_docs = [
                    doc for doc in filtered_docs
                    if query_lower in doc.filename.lower() or
                       query_lower in doc.mime_type.lower()
                ]

            # Apply status filter
            if self._current_filter != FilterOption.ALL:
                if self._current_filter in [FilterOption.PENDING, FilterOption.PROCESSING,
                                          FilterOption.COMPLETED, FilterOption.FAILED, FilterOption.ARCHIVED]:
                    status = DocumentStatus(self._current_filter.value)
                    filtered_docs = [doc for doc in filtered_docs if doc.status == status]
                elif self._current_filter in [FilterOption.PDF, FilterOption.DOCX, FilterOption.TXT,
                                             FilterOption.HTML, FilterOption.MARKDOWN]:
                    mime_filter = self._get_mime_type_filter(self._current_filter)
                    filtered_docs = [doc for doc in filtered_docs if mime_filter in doc.mime_type.lower()]

            self._filtered_documents = filtered_docs
            self._apply_sorting()

        except Exception as e:
            logger.error(f"Error applying filters: {e}")

    def _apply_sorting(self):
        """Apply current sorting to filtered documents."""
        try:
            if self._current_sort == SortOption.NAME_ASC:
                self._filtered_documents.sort(key=lambda x: x.filename.lower())
            elif self._current_sort == SortOption.NAME_DESC:
                self._filtered_documents.sort(key=lambda x: x.filename.lower(), reverse=True)
            elif self._current_sort == SortOption.DATE_ASC:
                self._filtered_documents.sort(key=lambda x: x.created_at)
            elif self._current_sort == SortOption.DATE_DESC:
                self._filtered_documents.sort(key=lambda x: x.created_at, reverse=True)
            elif self._current_sort == SortOption.SIZE_ASC:
                self._filtered_documents.sort(key=lambda x: x.file_size)
            elif self._current_sort == SortOption.SIZE_DESC:
                self._filtered_documents.sort(key=lambda x: x.file_size, reverse=True)
            elif self._current_sort == SortOption.STATUS_ASC:
                self._filtered_documents.sort(key=lambda x: x.status.value)
            elif self._current_sort == SortOption.STATUS_DESC:
                self._filtered_documents.sort(key=lambda x: x.status.value, reverse=True)
            elif self._current_sort == SortOption.QUALITY_ASC:
                self._filtered_documents.sort(key=lambda x: x.quality_score)
            elif self._current_sort == SortOption.QUALITY_DESC:
                self._filtered_documents.sort(key=lambda x: x.quality_score, reverse=True)

        except Exception as e:
            logger.error(f"Error applying sorting: {e}")

    def _all_selected(self) -> bool:
        """Check if all documents are selected."""
        try:
            return len(self._filtered_documents) > 0 and len(self._selected_documents) == len(self._filtered_documents)
        except Exception as e:
            logger.error(f"Error checking all selected: {e}")
            return False

    def _some_selected(self) -> bool:
        """Check if some but not all documents are selected."""
        try:
            selected_count = len(self._selected_documents)
            total_count = len(self._filtered_documents)
            return 0 < selected_count < total_count
        except Exception as e:
            logger.error(f"Error checking some selected: {e}")
            return False

    def _get_status_color(self, status: DocumentStatus) -> str:
        """Get color for document status."""
        try:
            theme_manager = self.get_theme_manager()
            if not theme_manager:
                # Fallback colors
                status_colors = {
                    DocumentStatus.PENDING: ft.Colors.ORANGE,
                    DocumentStatus.PROCESSING: ft.Colors.BLUE,
                    DocumentStatus.COMPLETED: ft.Colors.GREEN,
                    DocumentStatus.FAILED: ft.Colors.RED,
                    DocumentStatus.ARCHIVED: ft.Colors.GREY
                }
                return status_colors.get(status, ft.Colors.GREY)

            # Theme-aware colors
            if status == DocumentStatus.PENDING:
                return theme_manager.get_color("warning")
            elif status == DocumentStatus.PROCESSING:
                return theme_manager.get_color("primary")
            elif status == DocumentStatus.COMPLETED:
                return theme_manager.get_color("success")
            elif status == DocumentStatus.FAILED:
                return theme_manager.get_color("error")
            else:  # ARCHIVED
                return theme_manager.get_color("outline")

        except Exception as e:
            logger.error(f"Error getting status color: {e}")
            return ft.Colors.GREY

    def _get_status_icon(self, status: DocumentStatus) -> str:
        """Get icon for document status."""
        try:
            status_icons = {
                DocumentStatus.PENDING: ft.Icons.SCHEDULE,
                DocumentStatus.PROCESSING: ft.Icons.SYNC,
                DocumentStatus.COMPLETED: ft.Icons.CHECK_CIRCLE,
                DocumentStatus.FAILED: ft.Icons.ERROR,
                DocumentStatus.ARCHIVED: ft.Icons.ARCHIVE
            }
            return status_icons.get(status, ft.Icons.HELP)

        except Exception as e:
            logger.error(f"Error getting status icon: {e}")
            return ft.Icons.HELP

    def _get_sort_label(self, sort_option: SortOption) -> str:
        """Get human-readable label for sort option."""
        try:
            sort_labels = {
                SortOption.NAME_ASC: "Name (A-Z)",
                SortOption.NAME_DESC: "Name (Z-A)",
                SortOption.DATE_ASC: "Date (Oldest)",
                SortOption.DATE_DESC: "Date (Newest)",
                SortOption.SIZE_ASC: "Size (Smallest)",
                SortOption.SIZE_DESC: "Size (Largest)",
                SortOption.STATUS_ASC: "Status (A-Z)",
                SortOption.STATUS_DESC: "Status (Z-A)",
                SortOption.QUALITY_ASC: "Quality (Lowest)",
                SortOption.QUALITY_DESC: "Quality (Highest)"
            }
            return sort_labels.get(sort_option, sort_option.value)

        except Exception as e:
            logger.error(f"Error getting sort label: {e}")
            return sort_option.value

    def _get_mime_type_filter(self, filter_option: FilterOption) -> str:
        """Get mime type filter string."""
        try:
            mime_filters = {
                FilterOption.PDF: "pdf",
                FilterOption.DOCX: "word",
                FilterOption.TXT: "text",
                FilterOption.HTML: "html",
                FilterOption.MARKDOWN: "markdown"
            }
            return mime_filters.get(filter_option, "")

        except Exception as e:
            logger.error(f"Error getting mime type filter: {e}")
            return ""

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        try:
            if size_bytes == 0:
                return "0 B"

            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            size = float(size_bytes)

            while size >= 1024.0 and i < len(size_names) - 1:
                size /= 1024.0
                i += 1

            if i == 0:
                return f"{int(size)} {size_names[i]}"
            else:
                return f"{size:.1f} {size_names[i]}"

        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return "Unknown"

    # Public API methods
    def set_documents(self, documents: List[DocumentItem]):
        """Set the list of documents to display."""
        try:
            self._documents = documents or []
            self._apply_filters()
            self._current_page = 0
            self._clear_selection()
            self.update()

        except Exception as e:
            logger.error(f"Error setting documents: {e}")

    def add_document(self, document: DocumentItem):
        """Add a new document to the list."""
        try:
            self._documents.append(document)
            self._apply_filters()
            self.update()

        except Exception as e:
            logger.error(f"Error adding document: {e}")

    def update_document(self, document_id: str, updated_document: DocumentItem):
        """Update an existing document in the list."""
        try:
            for i, doc in enumerate(self._documents):
                if doc.document_id == document_id:
                    self._documents[i] = updated_document
                    break

            self._apply_filters()
            self.update()

        except Exception as e:
            logger.error(f"Error updating document: {e}")

    def remove_document(self, document_id: str):
        """Remove a document from the list."""
        try:
            self._documents = [doc for doc in self._documents if doc.document_id != document_id]
            self._selected_documents = [doc for doc in self._selected_documents if doc.document_id != document_id]
            self._apply_filters()
            self.update()

        except Exception as e:
            logger.error(f"Error removing document: {e}")

    def get_selected_documents(self) -> List[DocumentItem]:
        """Get list of currently selected documents."""
        try:
            return self._selected_documents.copy()
        except Exception as e:
            logger.error(f"Error getting selected documents: {e}")
            return []

    def set_loading(self, loading: bool):
        """Set loading state."""
        try:
            self._is_loading = loading
            self.update()

        except Exception as e:
            logger.error(f"Error setting loading state: {e}")

    def refresh(self):
        """Refresh the document list display."""
        try:
            self._apply_filters()
            self.update()

        except Exception as e:
            logger.error(f"Error refreshing document list: {e}")
