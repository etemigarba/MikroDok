"""
Module: result_list_ui
Description: Displays search results with highlighted snippets, relevance scores, pagination, and advanced filtering.
            Provides comprehensive search results interface with responsive design, theme integration,
            and modern UI/UX for optimal search experience in MikroDok application.
Phase: 4
Location: /src/modules/ui/search_results_ui/result_list_ui/result_list_ui.py
"""

# Standard library imports
import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
import re
import math

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class ResultDisplayMode(Enum):
    """Display modes for search results."""
    LIST = "list"
    GRID = "grid"
    COMPACT = "compact"


class SortOption(Enum):
    """Sorting options for search results."""
    RELEVANCE = "relevance"
    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"
    TITLE = "title"
    FILE_SIZE = "file_size"


class FilterOption(Enum):
    """Filter options for search results."""
    ALL = "all"
    DOCUMENTS = "documents"
    IMAGES = "images"
    RECENT = "recent"
    HIGH_RELEVANCE = "high_relevance"


@dataclass
class SearchResult:
    """Search result data structure."""
    id: str
    title: str
    content: str
    snippet: str
    relevance_score: float
    document_type: str
    file_path: str
    file_size: int
    created_date: datetime
    modified_date: datetime
    highlighted_terms: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    thumbnail_url: Optional[str] = None
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None


class ResultListUI(ThemeAwareUserControl):
    """
    Comprehensive search results listing interface with responsive design and theme integration.
    
    Features:
    - Responsive search results display with breakpoint-aware layouts
    - Advanced sorting and filtering with real-time updates
    - Highlighted search terms and relevance scoring
    - Pagination with infinite scroll support
    - Multiple display modes (list, grid, compact)
    - Theme-aware styling with accessibility compliance
    - Integration with search engine and document database
    - Modern UI/UX with smooth animations and transitions
    - Performance optimization for large result sets
    """

    def __init__(self,
                 on_result_click: Optional[Callable[[SearchResult], None]] = None,
                 on_filter_change: Optional[Callable[[FilterOption], None]] = None,
                 on_sort_change: Optional[Callable[[SortOption], None]] = None,
                 page_size: int = 20,
                 **kwargs):
        super().__init__(**kwargs)
        
        # Callbacks
        self._on_result_click = on_result_click
        self._on_filter_change = on_filter_change
        self._on_sort_change = on_sort_change
        
        # Configuration
        self._page_size = page_size
        self._current_page = 0
        self._total_results = 0
        
        # State
        self._search_results: List[SearchResult] = []
        self._filtered_results: List[SearchResult] = []
        self._current_display_mode = ResultDisplayMode.LIST
        self._current_sort = SortOption.RELEVANCE
        self._current_filter = FilterOption.ALL
        self._search_query = ""
        self._is_loading = False
        
        # UI components
        self._header_section: Optional[ft.Container] = None
        self._toolbar_section: Optional[ft.Container] = None
        self._results_container: Optional[ft.Container] = None
        self._pagination_section: Optional[ft.Container] = None
        self._status_bar: Optional[ft.Container] = None
        
        # Search highlighting
        self._highlight_terms: List[str] = []

    def build(self) -> ft.Control:
        """Build the responsive search results interface."""
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
                        self._build_results_section(),
                        self._build_pagination_section(),
                        self._build_status_bar_section()
                    ],
                    spacing=responsive_spacing,
                    expand=True
                ),
                padding=responsive_padding
            )
            
        except Exception as e:
            logger.error(f"Error building result list UI: {e}")
            return self._build_error_state(str(e))

    def _build_header_section(self) -> ft.Control:
        """Build the header section with results summary."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)
            
            # Results summary
            if self._total_results > 0:
                summary_text = f"Found {self._total_results:,} results"
                if self._search_query:
                    summary_text += f' for "{self._search_query}"'
            else:
                summary_text = "No results found"
            
            # Search time (placeholder for now)
            time_text = "(0.23 seconds)"
            
            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        summary_text,
                                        style=typography.get_text_style("heading_small"),
                                        color=theme.get_color("on_surface")
                                    ),
                                    ft.Text(
                                        time_text,
                                        style=typography.get_text_style("body_small"),
                                        color=theme.get_color("on_surface_variant")
                                    )
                                ],
                                spacing=4,
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
            logger.error(f"Error building header section: {e}")
            return ft.Container()

    def _build_toolbar_section(self) -> ft.Control:
        """Build the toolbar with sorting, filtering, and display mode controls."""
        try:
            theme = self.get_theme()
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)
            
            # Sort dropdown
            sort_dropdown = ft.Dropdown(
                label="Sort by",
                value=self._current_sort.value,
                options=[
                    ft.dropdown.Option("relevance", "Relevance"),
                    ft.dropdown.Option("date_desc", "Date (Newest)"),
                    ft.dropdown.Option("date_asc", "Date (Oldest)"),
                    ft.dropdown.Option("title", "Title"),
                    ft.dropdown.Option("file_size", "File Size")
                ],
                on_change=self._on_sort_changed,
                width=self.get_responsive_value(120, 140, 160, 180),
                bgcolor=theme.get_color("surface"),
                color=theme.get_color("on_surface")
            )
            
            # Filter dropdown
            filter_dropdown = ft.Dropdown(
                label="Filter",
                value=self._current_filter.value,
                options=[
                    ft.dropdown.Option("all", "All Results"),
                    ft.dropdown.Option("documents", "Documents"),
                    ft.dropdown.Option("images", "Images"),
                    ft.dropdown.Option("recent", "Recent"),
                    ft.dropdown.Option("high_relevance", "High Relevance")
                ],
                on_change=self._on_filter_changed,
                width=self.get_responsive_value(120, 140, 160, 180),
                bgcolor=theme.get_color("surface"),
                color=theme.get_color("on_surface")
            )
            
            # Display mode toggle
            display_mode_toggle = ft.SegmentedButton(
                selected={self._current_display_mode.value},
                segments=[
                    ft.Segment(
                        value="list",
                        label=ft.Text("List"),
                        icon=ft.Icon(ft.Icons.LIST)
                    ),
                    ft.Segment(
                        value="grid",
                        label=ft.Text("Grid"),
                        icon=ft.Icon(ft.Icons.GRID_VIEW)
                    ),
                    ft.Segment(
                        value="compact",
                        label=ft.Text("Compact"),
                        icon=ft.Icon(ft.Icons.VIEW_COMPACT)
                    )
                ],
                on_change=self._on_display_mode_changed
            )
            
            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Row(
                                controls=[sort_dropdown, filter_dropdown],
                                spacing=responsive_spacing,
                                tight=True
                            ),
                            display_mode_toggle
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    padding=self.get_responsive_padding()
                )
            )
            
        except Exception as e:
            logger.error(f"Error building toolbar section: {e}")
            return ft.Container()

    def _build_results_section(self) -> ft.Control:
        """Build the main results display section."""
        try:
            if self._is_loading:
                return self._build_loading_state()

            if not self._filtered_results:
                return self._build_empty_state()

            # Get current page results
            start_idx = self._current_page * self._page_size
            end_idx = start_idx + self._page_size
            page_results = self._filtered_results[start_idx:end_idx]

            if self._current_display_mode == ResultDisplayMode.GRID:
                return self._build_grid_view(page_results)
            elif self._current_display_mode == ResultDisplayMode.COMPACT:
                return self._build_compact_view(page_results)
            else:
                return self._build_list_view(page_results)

        except Exception as e:
            logger.error(f"Error building results section: {e}")
            return self._build_error_state(str(e))

    def _build_list_view(self, results: List[SearchResult]) -> ft.Control:
        """Build list view of search results."""
        try:
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            result_cards = []
            for result in results:
                card = self._build_result_card(result, ResultDisplayMode.LIST)
                result_cards.append(card)

            return ft.Container(
                content=ft.Column(
                    controls=result_cards,
                    spacing=responsive_spacing,
                    scroll=ft.ScrollMode.AUTO
                ),
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building list view: {e}")
            return ft.Container()

    def _build_grid_view(self, results: List[SearchResult]) -> ft.Control:
        """Build grid view of search results."""
        try:
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            result_cards = []
            for result in results:
                card = self._build_result_card(result, ResultDisplayMode.GRID)
                result_cards.append(card)

            return self.create_responsive_grid(
                children=result_cards,
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

    def _build_compact_view(self, results: List[SearchResult]) -> ft.Control:
        """Build compact view of search results."""
        try:
            responsive_spacing = self.get_responsive_value(4, 6, 8, 10)

            result_cards = []
            for result in results:
                card = self._build_result_card(result, ResultDisplayMode.COMPACT)
                result_cards.append(card)

            return ft.Container(
                content=ft.Column(
                    controls=result_cards,
                    spacing=responsive_spacing,
                    scroll=ft.ScrollMode.AUTO
                ),
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building compact view: {e}")
            return ft.Container()

    def _build_result_card(self, result: SearchResult, mode: ResultDisplayMode) -> ft.Control:
        """Build individual result card."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            # Highlight search terms in snippet
            highlighted_snippet = self._highlight_text(result.snippet, self._highlight_terms)

            # Format relevance score
            relevance_color = self._get_relevance_color(result.relevance_score)
            relevance_text = f"{result.relevance_score:.1%}"

            # Format file size
            file_size_text = self._format_file_size(result.file_size)

            # Format date
            date_text = result.modified_date.strftime("%b %d, %Y")

            if mode == ResultDisplayMode.COMPACT:
                return self._build_compact_card(result, highlighted_snippet, relevance_text, relevance_color)
            elif mode == ResultDisplayMode.GRID:
                return self._build_grid_card(result, highlighted_snippet, relevance_text, relevance_color)
            else:
                return self._build_list_card(result, highlighted_snippet, relevance_text, relevance_color, file_size_text, date_text)

        except Exception as e:
            logger.error(f"Error building result card: {e}")
            return ft.Container()

    def _build_list_card(self, result: SearchResult, highlighted_snippet: ft.Control,
                        relevance_text: str, relevance_color: str, file_size_text: str, date_text: str) -> ft.Control:
        """Build list mode result card."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            responsive_padding = self.get_responsive_padding()

            # Document type icon
            doc_icon = self._get_document_icon(result.document_type)

            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            # Document icon
                            ft.Container(
                                content=ft.Icon(
                                    doc_icon,
                                    size=self.get_responsive_value(24, 28, 32, 36),
                                    color=theme.get_color("primary")
                                ),
                                width=self.get_responsive_value(40, 48, 56, 64),
                                alignment=ft.alignment.center
                            ),
                            # Content
                            ft.Expanded(
                                child=ft.Column(
                                    controls=[
                                        # Title and relevance
                                        ft.Row(
                                            controls=[
                                                ft.Expanded(
                                                    child=ft.Text(
                                                        result.title,
                                                        style=typography.get_text_style("title_medium"),
                                                        color=theme.get_color("on_surface"),
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                        max_lines=1
                                                    )
                                                ),
                                                ft.Container(
                                                    content=ft.Text(
                                                        relevance_text,
                                                        style=typography.get_text_style("label_small"),
                                                        color=relevance_color
                                                    ),
                                                    bgcolor=theme.get_color("surface_variant"),
                                                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                                    border_radius=12
                                                )
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                                        ),
                                        # Snippet
                                        highlighted_snippet,
                                        # Metadata
                                        ft.Row(
                                            controls=[
                                                ft.Text(
                                                    f"{result.document_type.upper()} • {file_size_text} • {date_text}",
                                                    style=typography.get_text_style("body_small"),
                                                    color=theme.get_color("on_surface_variant")
                                                )
                                            ]
                                        )
                                    ],
                                    spacing=8,
                                    tight=True
                                )
                            )
                        ],
                        spacing=16
                    ),
                    padding=responsive_padding,
                    on_click=lambda _: self._handle_result_click(result)
                )
            )

        except Exception as e:
            logger.error(f"Error building list card: {e}")
            return ft.Container()

    def _build_grid_card(self, result: SearchResult, highlighted_snippet: ft.Control,
                        relevance_text: str, relevance_color: str) -> ft.Control:
        """Build grid mode result card."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            responsive_padding = self.get_responsive_padding()

            # Document type icon
            doc_icon = self._get_document_icon(result.document_type)

            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            # Header with icon and relevance
                            ft.Row(
                                controls=[
                                    ft.Icon(
                                        doc_icon,
                                        size=self.get_responsive_value(20, 24, 28, 32),
                                        color=theme.get_color("primary")
                                    ),
                                    ft.Expanded(
                                        child=ft.Text(
                                            result.title,
                                            style=typography.get_text_style("title_small"),
                                            color=theme.get_color("on_surface"),
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            max_lines=2
                                        )
                                    ),
                                    ft.Container(
                                        content=ft.Text(
                                            relevance_text,
                                            style=typography.get_text_style("label_small"),
                                            color=relevance_color
                                        ),
                                        bgcolor=theme.get_color("surface_variant"),
                                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=8
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            ),
                            # Snippet
                            highlighted_snippet,
                            # Metadata
                            ft.Text(
                                f"{result.document_type.upper()}",
                                style=typography.get_text_style("body_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=8,
                        tight=True
                    ),
                    padding=responsive_padding,
                    on_click=lambda _: self._handle_result_click(result),
                    height=self.get_responsive_value(120, 140, 160, 180)
                )
            )

        except Exception as e:
            logger.error(f"Error building grid card: {e}")
            return ft.Container()

    def _build_compact_card(self, result: SearchResult, highlighted_snippet: ft.Control,
                           relevance_text: str, relevance_color: str) -> ft.Control:
        """Build compact mode result card."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            # Document type icon
            doc_icon = self._get_document_icon(result.document_type)

            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                doc_icon,
                                size=16,
                                color=theme.get_color("primary")
                            ),
                            ft.Expanded(
                                child=ft.Text(
                                    result.title,
                                    style=typography.get_text_style("body_medium"),
                                    color=theme.get_color("on_surface"),
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1
                                )
                            ),
                            ft.Text(
                                relevance_text,
                                style=typography.get_text_style("label_small"),
                                color=relevance_color
                            )
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    on_click=lambda _: self._handle_result_click(result)
                )
            )

        except Exception as e:
            logger.error(f"Error building compact card: {e}")
            return ft.Container()

    def _build_pagination_section(self) -> ft.Control:
        """Build pagination controls."""
        try:
            if not self._filtered_results:
                return ft.Container(height=0)

            total_results = len(self._filtered_results)
            total_pages = math.ceil(total_results / self._page_size)

            if total_pages <= 1:
                return ft.Container(height=0)

            theme = self.get_theme()
            typography = self.get_typography()
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            # Page info
            start_result = self._current_page * self._page_size + 1
            end_result = min((self._current_page + 1) * self._page_size, total_results)
            page_info = f"Showing {start_result}-{end_result} of {total_results:,} results"

            # Navigation buttons
            page_controls = []

            # Previous button
            prev_button = ft.IconButton(
                icon=ft.Icons.CHEVRON_LEFT,
                disabled=self._current_page == 0,
                on_click=self._go_to_previous_page,
                tooltip="Previous page"
            )
            page_controls.append(prev_button)

            # Page numbers (show current and nearby pages)
            start_page = max(0, self._current_page - 2)
            end_page = min(total_pages, self._current_page + 3)

            for page_num in range(start_page, end_page):
                is_current = page_num == self._current_page

                page_button = ft.TextButton(
                    text=str(page_num + 1),
                    on_click=lambda _, p=page_num: self._go_to_page(p),
                    style=ft.ButtonStyle(
                        bgcolor=theme.get_color("primary") if is_current else None,
                        color=theme.get_color("on_primary") if is_current else theme.get_color("on_surface")
                    )
                )
                page_controls.append(page_button)

            # Next button
            next_button = ft.IconButton(
                icon=ft.Icons.CHEVRON_RIGHT,
                disabled=self._current_page >= total_pages - 1,
                on_click=self._go_to_next_page,
                tooltip="Next page"
            )
            page_controls.append(next_button)

            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                page_info,
                                style=typography.get_text_style("body_medium"),
                                color=theme.get_color("on_surface_variant")
                            ),
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
        """Build status bar with additional information."""
        try:
            if not self._filtered_results:
                return ft.Container(height=0)

            theme = self.get_theme()
            typography = self.get_typography()

            # Calculate statistics
            avg_relevance = sum(r.relevance_score for r in self._filtered_results) / len(self._filtered_results)
            high_relevance_count = sum(1 for r in self._filtered_results if r.relevance_score > 0.8)

            status_text = f"Average relevance: {avg_relevance:.1%} • {high_relevance_count} high-relevance results"

            return ft.Container(
                content=ft.Text(
                    status_text,
                    style=typography.get_text_style("body_small"),
                    color=theme.get_color("on_surface_variant")
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=8)
            )

        except Exception as e:
            logger.error(f"Error building status bar section: {e}")
            return ft.Container()

    def _build_loading_state(self) -> ft.Control:
        """Build loading state display."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(),
                        ft.Text(
                            "Searching...",
                            style=typography.get_text_style("body_large"),
                            color=theme.get_color("on_surface")
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16
                ),
                alignment=ft.alignment.center,
                height=200
            )

        except Exception as e:
            logger.error(f"Error building loading state: {e}")
            return ft.Container()

    def _build_empty_state(self) -> ft.Control:
        """Build empty state display."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.SEARCH_OFF,
                            size=64,
                            color=theme.get_color("on_surface_variant")
                        ),
                        ft.Text(
                            "No results found",
                            style=typography.get_text_style("heading_small"),
                            color=theme.get_color("on_surface")
                        ),
                        ft.Text(
                            "Try adjusting your search terms or filters",
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant")
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16
                ),
                alignment=ft.alignment.center,
                height=200
            )

        except Exception as e:
            logger.error(f"Error building empty state: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state display."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.ERROR_OUTLINE,
                            size=64,
                            color=theme.get_color("error")
                        ),
                        ft.Text(
                            "Error loading results",
                            style=typography.get_text_style("heading_small"),
                            color=theme.get_color("on_surface")
                        ),
                        ft.Text(
                            error_message,
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant")
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16
                ),
                alignment=ft.alignment.center,
                height=200
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    def _highlight_text(self, text: str, terms: List[str]) -> ft.Control:
        """Highlight search terms in text."""
        try:
            if not terms or not text:
                theme = self.get_theme()
                typography = self.get_typography()
                return ft.Text(
                    text,
                    style=typography.get_text_style("body_medium"),
                    color=theme.get_color("on_surface"),
                    max_lines=3,
                    overflow=ft.TextOverflow.ELLIPSIS
                )

            # Create highlighted text spans
            highlighted_spans = []
            current_text = text
            theme = self.get_theme()
            typography = self.get_typography()

            # Simple highlighting - in production, use more sophisticated text processing
            for term in terms:
                if term.lower() in current_text.lower():
                    parts = re.split(f'({re.escape(term)})', current_text, flags=re.IGNORECASE)
                    spans = []
                    for part in parts:
                        if part.lower() == term.lower():
                            spans.append(ft.TextSpan(
                                text=part,
                                style=ft.TextStyle(
                                    bgcolor=theme.get_color("primary_container"),
                                    color=theme.get_color("on_primary_container"),
                                    weight=ft.FontWeight.BOLD
                                )
                            ))
                        else:
                            spans.append(ft.TextSpan(text=part))

                    return ft.Text(
                        spans=spans,
                        style=typography.get_text_style("body_medium"),
                        color=theme.get_color("on_surface"),
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS
                    )

            # Fallback to regular text
            return ft.Text(
                text,
                style=typography.get_text_style("body_medium"),
                color=theme.get_color("on_surface"),
                max_lines=3,
                overflow=ft.TextOverflow.ELLIPSIS
            )

        except Exception as e:
            logger.error(f"Error highlighting text: {e}")
            theme = self.get_theme()
            typography = self.get_typography()
            return ft.Text(
                text,
                style=typography.get_text_style("body_medium"),
                color=theme.get_color("on_surface")
            )

    def _get_relevance_color(self, score: float) -> str:
        """Get color for relevance score."""
        try:
            theme = self.get_theme()

            if score >= 0.8:
                return theme.get_color("success")
            elif score >= 0.6:
                return theme.get_color("warning")
            else:
                return theme.get_color("error")

        except Exception as e:
            logger.error(f"Error getting relevance color: {e}")
            return "#666666"

    def _get_document_icon(self, doc_type: str) -> str:
        """Get icon for document type."""
        try:
            icon_map = {
                "pdf": ft.Icons.PICTURE_AS_PDF,
                "docx": ft.Icons.DESCRIPTION,
                "txt": ft.Icons.TEXT_SNIPPET,
                "html": ft.Icons.WEB,
                "md": ft.Icons.ARTICLE,
                "image": ft.Icons.IMAGE,
                "video": ft.Icons.VIDEO_FILE,
                "audio": ft.Icons.AUDIO_FILE
            }

            return icon_map.get(doc_type.lower(), ft.Icons.INSERT_DRIVE_FILE)

        except Exception as e:
            logger.error(f"Error getting document icon: {e}")
            return ft.Icons.INSERT_DRIVE_FILE

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        try:
            if size_bytes == 0:
                return "0 B"

            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = int(math.floor(math.log(size_bytes, 1024)))
            p = math.pow(1024, i)
            s = round(size_bytes / p, 2)

            return f"{s} {size_names[i]}"

        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return "Unknown"

    # Event handlers
    def _on_sort_changed(self, e):
        """Handle sort option change."""
        try:
            self._current_sort = SortOption(e.control.value)
            self._apply_sorting()
            self._current_page = 0  # Reset to first page

            if self._on_sort_change:
                self._on_sort_change(self._current_sort)

            self.update()

        except Exception as ex:
            logger.error(f"Error handling sort change: {ex}")

    def _on_filter_changed(self, e):
        """Handle filter option change."""
        try:
            self._current_filter = FilterOption(e.control.value)
            self._apply_filtering()
            self._current_page = 0  # Reset to first page

            if self._on_filter_change:
                self._on_filter_change(self._current_filter)

            self.update()

        except Exception as ex:
            logger.error(f"Error handling filter change: {ex}")

    def _on_display_mode_changed(self, e):
        """Handle display mode change."""
        try:
            selected_mode = list(e.control.selected)[0] if e.control.selected else "list"
            self._current_display_mode = ResultDisplayMode(selected_mode)
            self.update()

        except Exception as ex:
            logger.error(f"Error handling display mode change: {ex}")

    def _handle_result_click(self, result: SearchResult):
        """Handle result click."""
        try:
            if self._on_result_click:
                self._on_result_click(result)

        except Exception as e:
            logger.error(f"Error handling result click: {e}")

    def _go_to_page(self, page_num: int):
        """Navigate to specific page."""
        try:
            total_pages = math.ceil(len(self._filtered_results) / self._page_size)
            if 0 <= page_num < total_pages:
                self._current_page = page_num
                self.update()

        except Exception as e:
            logger.error(f"Error navigating to page: {e}")

    def _go_to_previous_page(self, e):
        """Navigate to previous page."""
        try:
            if self._current_page > 0:
                self._current_page -= 1
                self.update()

        except Exception as ex:
            logger.error(f"Error navigating to previous page: {ex}")

    def _go_to_next_page(self, e):
        """Navigate to next page."""
        try:
            total_pages = math.ceil(len(self._filtered_results) / self._page_size)
            if self._current_page < total_pages - 1:
                self._current_page += 1
                self.update()

        except Exception as ex:
            logger.error(f"Error navigating to next page: {ex}")

    def _apply_sorting(self):
        """Apply current sorting to filtered results."""
        try:
            if self._current_sort == SortOption.RELEVANCE:
                self._filtered_results.sort(key=lambda x: x.relevance_score, reverse=True)
            elif self._current_sort == SortOption.DATE_DESC:
                self._filtered_results.sort(key=lambda x: x.modified_date, reverse=True)
            elif self._current_sort == SortOption.DATE_ASC:
                self._filtered_results.sort(key=lambda x: x.modified_date)
            elif self._current_sort == SortOption.TITLE:
                self._filtered_results.sort(key=lambda x: x.title.lower())
            elif self._current_sort == SortOption.FILE_SIZE:
                self._filtered_results.sort(key=lambda x: x.file_size, reverse=True)

        except Exception as e:
            logger.error(f"Error applying sorting: {e}")

    def _apply_filtering(self):
        """Apply current filter to search results."""
        try:
            if self._current_filter == FilterOption.ALL:
                self._filtered_results = self._search_results.copy()
            elif self._current_filter == FilterOption.DOCUMENTS:
                self._filtered_results = [r for r in self._search_results
                                        if r.document_type in ["pdf", "docx", "txt", "html", "md"]]
            elif self._current_filter == FilterOption.IMAGES:
                self._filtered_results = [r for r in self._search_results
                                        if r.document_type in ["jpg", "png", "gif", "bmp", "svg"]]
            elif self._current_filter == FilterOption.RECENT:
                # Filter results from last 30 days
                cutoff_date = datetime.now() - timedelta(days=30)
                self._filtered_results = [r for r in self._search_results
                                        if r.modified_date >= cutoff_date]
            elif self._current_filter == FilterOption.HIGH_RELEVANCE:
                self._filtered_results = [r for r in self._search_results
                                        if r.relevance_score >= 0.8]

            self._apply_sorting()

        except Exception as e:
            logger.error(f"Error applying filtering: {e}")

    # Public methods
    def set_search_results(self, results: List[SearchResult], query: str = "", highlight_terms: List[str] = None):
        """Set search results to display."""
        try:
            self._search_results = results
            self._search_query = query
            self._highlight_terms = highlight_terms or []
            self._total_results = len(results)
            self._current_page = 0

            self._apply_filtering()
            self.update()

        except Exception as e:
            logger.error(f"Error setting search results: {e}")

    def set_loading(self, loading: bool):
        """Set loading state."""
        try:
            self._is_loading = loading
            self.update()

        except Exception as e:
            logger.error(f"Error setting loading state: {e}")

    def clear_results(self):
        """Clear all search results."""
        try:
            self._search_results.clear()
            self._filtered_results.clear()
            self._total_results = 0
            self._current_page = 0
            self._search_query = ""
            self._highlight_terms.clear()
            self.update()

        except Exception as e:
            logger.error(f"Error clearing results: {e}")

    def get_current_results(self) -> List[SearchResult]:
        """Get currently displayed results."""
        try:
            start_idx = self._current_page * self._page_size
            end_idx = start_idx + self._page_size
            return self._filtered_results[start_idx:end_idx]

        except Exception as e:
            logger.error(f"Error getting current results: {e}")
            return []
