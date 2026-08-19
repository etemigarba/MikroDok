"""
Module: search_results_ui
Description: Main search results interface coordinator that orchestrates all search result components
            including result lists, cards, citations, and advanced search features. Provides comprehensive
            search result display with responsive design, theme integration, and accessibility compliance.
Phase: 4
Location: /src/modules/ui/search_results_ui/search_results_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from datetime import datetime
import time

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    get_theme_manager
)

try:
    from .result_list_ui.result_list_ui import (
        ResultListUI,
        SearchResult,
        ResultDisplayMode,
        SortOption,
        FilterOption
    )
except ImportError:
    # Fallback for testing
    class ResultListUI:
        pass
    class SearchResult:
        pass
    class ResultDisplayMode(Enum):
        LIST = "list"
        GRID = "grid"
        COMPACT = "compact"
    class SortOption(Enum):
        RELEVANCE = "relevance"
    class FilterOption(Enum):
        ALL = "all"

try:
    from .result_card_ui.result_card_ui import (
        ResultCardUI,
        ResultCard,
        CardLayout
    )
except ImportError:
    # Fallback for testing
    class ResultCardUI:
        pass
    class ResultCard:
        pass
    class CardLayout(Enum):
        STANDARD = "standard"

try:
    from .citation_viewer_ui.citation_viewer_ui import (
        CitationViewerUI,
        Citation,
        CitationFormat
    )
except ImportError:
    # Fallback for testing
    class CitationViewerUI:
        pass
    class Citation:
        pass
    class CitationFormat(Enum):
        APA = "apa"

# Configure logging
logger = logging.getLogger(__name__)


class SearchResultsLayout(Enum):
    """Layout modes for search results display."""
    STANDARD = "standard"
    SPLIT_VIEW = "split_view"
    TABBED = "tabbed"
    COMPACT = "compact"
    DETAILED = "detailed"


class SearchResultsView(Enum):
    """View modes for search results."""
    RESULTS_ONLY = "results_only"
    RESULTS_WITH_CITATIONS = "results_with_citations"
    RESULTS_WITH_PREVIEW = "results_with_preview"
    FULL_VIEW = "full_view"


@dataclass
class SearchResultsConfig:
    """Configuration for search results display."""
    layout: SearchResultsLayout = SearchResultsLayout.STANDARD
    view: SearchResultsView = SearchResultsView.RESULTS_ONLY
    show_citations: bool = True
    show_preview: bool = True
    show_metadata: bool = True
    show_relevance_scores: bool = True
    enable_export: bool = True
    enable_sharing: bool = True
    enable_bookmarking: bool = True
    auto_refresh: bool = False
    refresh_interval_seconds: int = 30
    max_results_per_page: int = 20
    enable_infinite_scroll: bool = False
    highlight_search_terms: bool = True
    show_search_suggestions: bool = True


@dataclass
class SearchResultsState:
    """State management for search results."""
    query: str = ""
    results: List[SearchResult] = field(default_factory=list)
    total_results: int = 0
    current_page: int = 0
    is_loading: bool = False
    has_error: bool = False
    error_message: str = ""
    selected_result: Optional[SearchResult] = None
    search_time_ms: float = 0.0
    last_updated: Optional[datetime] = None
    filters_applied: List[str] = field(default_factory=list)
    sort_order: str = "relevance"


class SearchResultsUI(ThemeAwareUserControl):
    """
    Main search results interface coordinator with comprehensive search result display capabilities.
    
    Features:
    - Orchestrates all search result components (list, cards, citations)
    - Multiple layout modes (standard, split view, tabbed, compact, detailed)
    - Advanced search result management with filtering, sorting, pagination
    - Real-time search updates with auto-refresh capabilities
    - Export and sharing functionality for search results
    - Bookmarking and favorites management
    - Search result preview with document viewer integration
    - Citation management with multiple format support
    - Responsive design with breakpoint-aware layouts
    - Full theme system integration with accessibility compliance
    - Performance optimization for large result sets
    - Advanced search analytics and user behavior tracking
    """

    def __init__(self,
                 config: Optional[SearchResultsConfig] = None,
                 on_result_selected: Optional[Callable[[SearchResult], None]] = None,
                 on_citation_requested: Optional[Callable[[SearchResult], None]] = None,
                 on_export_requested: Optional[Callable[[List[SearchResult]], None]] = None,
                 on_bookmark_added: Optional[Callable[[SearchResult], None]] = None,
                 on_search_refined: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the SearchResultsUI component.
        
        Args:
            config: Search results configuration
            on_result_selected: Callback for result selection
            on_citation_requested: Callback for citation requests
            on_export_requested: Callback for export requests
            on_bookmark_added: Callback for bookmark additions
            on_search_refined: Callback for search refinement
            **kwargs: Additional arguments for ThemeAwareUserControl
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or SearchResultsConfig()
        
        # Callbacks
        self._on_result_selected = on_result_selected
        self._on_citation_requested = on_citation_requested
        self._on_export_requested = on_export_requested
        self._on_bookmark_added = on_bookmark_added
        self._on_search_refined = on_search_refined
        
        # State management
        self._state = SearchResultsState()
        self._search_history: List[str] = []
        self._bookmarked_results: List[str] = []
        self._export_formats = ["PDF", "CSV", "JSON", "TXT"]
        
        # UI components
        self._result_list_ui: Optional[ResultListUI] = None
        self._citation_viewer_ui: Optional[CitationViewerUI] = None
        self._preview_panel: Optional[ft.Container] = None
        self._toolbar: Optional[ft.Container] = None
        self._status_bar: Optional[ft.Container] = None
        self._search_suggestions: Optional[ft.Container] = None
        
        # Layout containers
        self._main_container: Optional[ft.Container] = None
        self._content_area: Optional[ft.Container] = None
        self._sidebar: Optional[ft.Container] = None
        
        # Performance tracking
        self._render_start_time: float = 0.0
        self._last_search_time: float = 0.0
        
        # Initialize components
        self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize child components."""
        try:
            # Initialize result list component
            self._result_list_ui = ResultListUI(
                on_result_click=self._handle_result_click,
                on_filter_change=self._handle_filter_change,
                on_sort_change=self._handle_sort_change,
                page_size=self._config.max_results_per_page
            )
            
            # Initialize citation viewer component
            if self._config.show_citations:
                self._citation_viewer_ui = CitationViewerUI(
                    on_citation_copy=self._handle_citation_copy,
                    on_source_click=self._handle_source_click
                )
            
        except Exception as e:
            logger.error(f"Error initializing search results components: {e}")

    def build(self) -> ft.Control:
        """Build the responsive search results interface."""
        try:
            self._render_start_time = time.time()
            
            # Get responsive values
            responsive_padding = self.get_responsive_padding()
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)
            
            # Build layout based on configuration
            if self._config.layout == SearchResultsLayout.SPLIT_VIEW:
                return self._build_split_view_layout(responsive_padding, responsive_spacing)
            elif self._config.layout == SearchResultsLayout.TABBED:
                return self._build_tabbed_layout(responsive_padding, responsive_spacing)
            elif self._config.layout == SearchResultsLayout.COMPACT:
                return self._build_compact_layout(responsive_padding, responsive_spacing)
            elif self._config.layout == SearchResultsLayout.DETAILED:
                return self._build_detailed_layout(responsive_padding, responsive_spacing)
            else:
                return self._build_standard_layout(responsive_padding, responsive_spacing)
                
        except Exception as e:
            logger.error(f"Error building search results UI: {e}")
            return self._build_error_state(str(e))

    def _build_standard_layout(self, padding: ft.Padding, spacing: float) -> ft.Control:
        """Build standard search results layout."""
        try:
            theme = self.get_theme()

            # Main content column
            content_controls = [
                self._build_toolbar_section(),
                self._build_search_suggestions_section(),
                self._build_results_section(),
                self._build_status_bar_section()
            ]

            # Add citation viewer if enabled
            if self._config.show_citations and self._citation_viewer_ui:
                content_controls.insert(-1, self._build_citation_section())

            return self.create_responsive_container(
                content=ft.Column(
                    controls=content_controls,
                    spacing=spacing,
                    expand=True,
                    scroll=ft.ScrollMode.AUTO
                ),
                padding=padding,
                bgcolor=theme.get_color("surface"),
                border_radius=self.get_responsive_value(8, 10, 12, 14)
            )

        except Exception as e:
            logger.error(f"Error building standard layout: {e}")
            return self._build_error_state(str(e))

    def _build_split_view_layout(self, padding: ft.Padding, spacing: float) -> ft.Control:
        """Build split view layout with results and preview side by side."""
        try:
            theme = self.get_theme()

            # Left panel - search results
            left_panel = ft.Container(
                content=ft.Column(
                    controls=[
                        self._build_toolbar_section(),
                        self._build_search_suggestions_section(),
                        self._build_results_section()
                    ],
                    spacing=spacing,
                    expand=True
                ),
                expand=2,
                bgcolor=theme.get_color("surface"),
                border_radius=self.get_responsive_value(8, 10, 12, 14),
                padding=padding
            )

            # Right panel - preview and citations
            right_panel = ft.Container(
                content=ft.Column(
                    controls=[
                        self._build_preview_section(),
                        self._build_citation_section() if self._config.show_citations else ft.Container()
                    ],
                    spacing=spacing,
                    expand=True
                ),
                expand=1,
                bgcolor=theme.get_color("surface_variant"),
                border_radius=self.get_responsive_value(8, 10, 12, 14),
                padding=padding
            )

            return ft.Row(
                controls=[left_panel, right_panel],
                spacing=spacing,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building split view layout: {e}")
            return self._build_error_state(str(e))

    def _build_tabbed_layout(self, padding: ft.Padding, spacing: float) -> ft.Control:
        """Build tabbed layout with separate tabs for results, citations, and preview."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            # Create tabs
            tabs = [
                ft.Tab(
                    text="Results",
                    icon=ft.Icons.SEARCH,
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_toolbar_section(),
                                self._build_search_suggestions_section(),
                                self._build_results_section()
                            ],
                            spacing=spacing,
                            expand=True
                        ),
                        padding=padding
                    )
                )
            ]

            # Add citations tab if enabled
            if self._config.show_citations:
                tabs.append(
                    ft.Tab(
                        text="Citations",
                        icon=ft.Icons.FORMAT_QUOTE,
                        content=ft.Container(
                            content=self._build_citation_section(),
                            padding=padding
                        )
                    )
                )

            # Add preview tab if enabled
            if self._config.show_preview:
                tabs.append(
                    ft.Tab(
                        text="Preview",
                        icon=ft.Icons.PREVIEW,
                        content=ft.Container(
                            content=self._build_preview_section(),
                            padding=padding
                        )
                    )
                )

            return ft.Tabs(
                tabs=tabs,
                selected_index=0,
                animation_duration=300,
                tab_alignment=ft.TabAlignment.START,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building tabbed layout: {e}")
            return self._build_error_state(str(e))

    def _build_compact_layout(self, padding: ft.Padding, spacing: float) -> ft.Control:
        """Build compact layout optimized for smaller screens."""
        try:
            theme = self.get_theme()

            # Compact toolbar
            compact_toolbar = self._build_compact_toolbar()

            # Results with minimal spacing
            compact_results = ft.Container(
                content=self._result_list_ui if self._result_list_ui else ft.Container(),
                expand=True
            )

            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        compact_toolbar,
                        compact_results,
                        self._build_compact_status_bar()
                    ],
                    spacing=self.get_responsive_value(4, 6, 8, 10),
                    expand=True,
                    tight=True
                ),
                padding=self.get_responsive_value(8, 12, 16, 20),
                bgcolor=theme.get_color("surface")
            )

        except Exception as e:
            logger.error(f"Error building compact layout: {e}")
            return self._build_error_state(str(e))

    def _build_detailed_layout(self, padding: ft.Padding, spacing: float) -> ft.Control:
        """Build detailed layout with all features visible."""
        try:
            theme = self.get_theme()

            # Header with search info and controls
            header = self._build_detailed_header()

            # Main content area with sidebar
            main_content = ft.Row(
                controls=[
                    # Left sidebar with filters and tools
                    ft.Container(
                        content=self._build_sidebar(),
                        width=self.get_responsive_value(200, 250, 300, 350),
                        bgcolor=theme.get_color("surface_variant"),
                        border_radius=self.get_responsive_value(8, 10, 12, 14),
                        padding=padding
                    ),
                    # Main results area
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_results_section(),
                                self._build_citation_section() if self._config.show_citations else ft.Container()
                            ],
                            spacing=spacing,
                            expand=True
                        ),
                        expand=True,
                        bgcolor=theme.get_color("surface"),
                        border_radius=self.get_responsive_value(8, 10, 12, 14),
                        padding=padding
                    )
                ],
                spacing=spacing,
                expand=True
            )

            return ft.Column(
                controls=[
                    header,
                    main_content,
                    self._build_status_bar_section()
                ],
                spacing=spacing,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building detailed layout: {e}")
            return self._build_error_state(str(e))

    # Section builders
    def _build_toolbar_section(self) -> ft.Control:
        """Build the main toolbar with search controls."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Search info
            search_info = ft.Text(
                f"Results for: '{self._state.query}'" if self._state.query else "No search query",
                style=typography.get_text_style("title_medium"),
                color=theme.get_color("on_surface"),
                overflow=ft.TextOverflow.ELLIPSIS
            )

            # Results count
            results_count = ft.Text(
                f"{self._state.total_results:,} results ({self._state.search_time_ms:.0f}ms)" if self._state.total_results > 0 else "No results",
                style=typography.get_text_style("body_small"),
                color=theme.get_color("on_surface_variant")
            )

            # Action buttons
            action_buttons = ft.Row(
                controls=[
                    # Export button
                    ft.IconButton(
                        icon=ft.Icons.DOWNLOAD,
                        tooltip="Export results",
                        on_click=self._handle_export_click,
                        icon_color=theme.get_color("primary"),
                        disabled=not self._config.enable_export or len(self._state.results) == 0
                    ),
                    # Share button
                    ft.IconButton(
                        icon=ft.Icons.SHARE,
                        tooltip="Share results",
                        on_click=self._handle_share_click,
                        icon_color=theme.get_color("primary"),
                        disabled=not self._config.enable_sharing or len(self._state.results) == 0
                    ),
                    # Refresh button
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="Refresh results",
                        on_click=self._handle_refresh_click,
                        icon_color=theme.get_color("primary")
                    ),
                    # Settings button
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS,
                        tooltip="Search settings",
                        on_click=self._handle_settings_click,
                        icon_color=theme.get_color("primary")
                    )
                ],
                spacing=spacing.xs,
                tight=True
            )

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Expanded(
                            child=ft.Column(
                                controls=[search_info, results_count],
                                spacing=spacing.xs,
                                tight=True
                            )
                        ),
                        action_buttons
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=theme.get_color("surface_variant"),
                border_radius=self.get_responsive_value(8, 10, 12, 14),
                border=ft.border.all(1, theme.get_color("outline_variant"))
            )

        except Exception as e:
            logger.error(f"Error building toolbar section: {e}")
            return ft.Container()

    def _build_search_suggestions_section(self) -> ft.Control:
        """Build search suggestions section."""
        try:
            if not self._config.show_search_suggestions or not self._state.query:
                return ft.Container()

            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Generate suggestions based on current query
            suggestions = self._generate_search_suggestions()

            if not suggestions:
                return ft.Container()

            suggestion_chips = []
            for suggestion in suggestions[:5]:  # Limit to 5 suggestions
                chip = ft.Chip(
                    label=ft.Text(
                        suggestion,
                        style=typography.get_text_style("label_medium"),
                        color=theme.get_color("on_surface")
                    ),
                    bgcolor=theme.get_color("surface_variant"),
                    selected_color=theme.get_color("primary_container"),
                    on_click=lambda e, s=suggestion: self._handle_suggestion_click(s)
                )
                suggestion_chips.append(chip)

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Related searches:",
                            style=typography.get_text_style("label_medium"),
                            color=theme.get_color("on_surface_variant")
                        ),
                        ft.Row(
                            controls=suggestion_chips,
                            spacing=spacing.sm,
                            wrap=True
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=theme.get_color("surface"),
                border_radius=self.get_responsive_value(8, 10, 12, 14),
                border=ft.border.all(1, theme.get_color("outline_variant"))
            )

        except Exception as e:
            logger.error(f"Error building search suggestions section: {e}")
            return ft.Container()

    def _build_results_section(self) -> ft.Control:
        """Build the main results display section."""
        try:
            if self._state.is_loading:
                return self._build_loading_state()

            if self._state.has_error:
                return self._build_error_state(self._state.error_message)

            if not self._state.results:
                return self._build_empty_state()

            # Return the result list component
            if self._result_list_ui:
                return ft.Container(
                    content=self._result_list_ui,
                    expand=True
                )
            else:
                return self._build_fallback_results()

        except Exception as e:
            logger.error(f"Error building results section: {e}")
            return self._build_error_state(str(e))

    def _build_citation_section(self) -> ft.Control:
        """Build the citation viewer section."""
        try:
            if not self._config.show_citations or not self._citation_viewer_ui:
                return ft.Container()

            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Citations",
                            style=typography.get_text_style("title_medium"),
                            color=theme.get_color("on_surface")
                        ),
                        ft.Container(
                            content=self._citation_viewer_ui,
                            expand=True
                        )
                    ],
                    spacing=spacing.md,
                    expand=True
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=theme.get_color("surface"),
                border_radius=self.get_responsive_value(8, 10, 12, 14),
                border=ft.border.all(1, theme.get_color("outline_variant"))
            )

        except Exception as e:
            logger.error(f"Error building citation section: {e}")
            return ft.Container()

    def _build_preview_section(self) -> ft.Control:
        """Build the document preview section."""
        try:
            if not self._config.show_preview:
                return ft.Container()

            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            if not self._state.selected_result:
                # No result selected
                return ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                ft.Icons.PREVIEW,
                                size=self.get_responsive_value(48, 56, 64, 72),
                                color=theme.get_color("outline")
                            ),
                            ft.Text(
                                "Select a result to preview",
                                style=typography.get_text_style("body_large"),
                                color=theme.get_color("on_surface_variant"),
                                text_align=ft.TextAlign.CENTER
                            )
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        main_alignment=ft.MainAxisAlignment.CENTER,
                        spacing=spacing.md
                    ),
                    padding=ft.padding.all(spacing.lg),
                    bgcolor=theme.get_color("surface"),
                    border_radius=self.get_responsive_value(8, 10, 12, 14),
                    border=ft.border.all(1, theme.get_color("outline_variant")),
                    expand=True
                )

            # Show preview of selected result
            return self._build_result_preview(self._state.selected_result)

        except Exception as e:
            logger.error(f"Error building preview section: {e}")
            return ft.Container()

    def _build_status_bar_section(self) -> ft.Control:
        """Build the status bar section."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Status indicators
            status_items = []

            # Loading indicator
            if self._state.is_loading:
                status_items.append(
                    ft.Row(
                        controls=[
                            ft.ProgressRing(
                                width=16,
                                height=16,
                                stroke_width=2,
                                color=theme.get_color("primary")
                            ),
                            ft.Text(
                                "Loading...",
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=spacing.xs,
                        tight=True
                    )
                )

            # Last updated
            if self._state.last_updated:
                status_items.append(
                    ft.Text(
                        f"Updated: {self._state.last_updated.strftime('%H:%M:%S')}",
                        style=typography.get_text_style("label_small"),
                        color=theme.get_color("on_surface_variant")
                    )
                )

            # Auto-refresh indicator
            if self._config.auto_refresh:
                status_items.append(
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.AUTORENEW,
                                size=14,
                                color=theme.get_color("primary")
                            ),
                            ft.Text(
                                f"Auto-refresh: {self._config.refresh_interval_seconds}s",
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=spacing.xs,
                        tight=True
                    )
                )

            if not status_items:
                return ft.Container()

            return ft.Container(
                content=ft.Row(
                    controls=status_items,
                    spacing=spacing.md,
                    alignment=ft.MainAxisAlignment.START
                ),
                padding=ft.padding.symmetric(horizontal=spacing.md, vertical=spacing.sm),
                bgcolor=theme.get_color("surface_variant"),
                border_radius=self.get_responsive_value(6, 8, 10, 12)
            )

        except Exception as e:
            logger.error(f"Error building status bar section: {e}")
            return ft.Container()

    # State management methods
    def update_search_results(self, query: str, results: List[SearchResult],
                             total_results: int = 0, search_time_ms: float = 0.0) -> None:
        """Update search results and refresh UI."""
        try:
            self._state.query = query
            self._state.results = results
            self._state.total_results = total_results or len(results)
            self._state.search_time_ms = search_time_ms
            self._state.last_updated = datetime.now()
            self._state.is_loading = False
            self._state.has_error = False
            self._state.error_message = ""

            # Update result list component
            if self._result_list_ui and hasattr(self._result_list_ui, 'update_results'):
                self._result_list_ui.update_results(results)

            # Add to search history
            if query and query not in self._search_history:
                self._search_history.insert(0, query)
                self._search_history = self._search_history[:10]  # Keep last 10 searches

            # Refresh UI
            self.update()

            logger.info(f"Updated search results: {len(results)} results for query '{query}'")

        except Exception as e:
            logger.error(f"Error updating search results: {e}")
            self.set_error_state(f"Failed to update results: {str(e)}")

    def set_loading_state(self, is_loading: bool = True) -> None:
        """Set loading state and refresh UI."""
        try:
            self._state.is_loading = is_loading
            if is_loading:
                self._state.has_error = False
                self._state.error_message = ""

            self.update()

        except Exception as e:
            logger.error(f"Error setting loading state: {e}")

    def set_error_state(self, error_message: str) -> None:
        """Set error state and refresh UI."""
        try:
            self._state.has_error = True
            self._state.error_message = error_message
            self._state.is_loading = False

            self.update()

            logger.error(f"Search results error: {error_message}")

        except Exception as e:
            logger.error(f"Error setting error state: {e}")

    def clear_results(self) -> None:
        """Clear all search results."""
        try:
            self._state.results = []
            self._state.total_results = 0
            self._state.query = ""
            self._state.selected_result = None
            self._state.is_loading = False
            self._state.has_error = False
            self._state.error_message = ""

            # Clear result list component
            if self._result_list_ui and hasattr(self._result_list_ui, 'clear_results'):
                self._result_list_ui.clear_results()

            self.update()

        except Exception as e:
            logger.error(f"Error clearing results: {e}")

    def select_result(self, result: SearchResult) -> None:
        """Select a specific result for preview."""
        try:
            self._state.selected_result = result

            # Trigger callback
            if self._on_result_selected:
                self._on_result_selected(result)

            self.update()

        except Exception as e:
            logger.error(f"Error selecting result: {e}")

    def add_bookmark(self, result: SearchResult) -> None:
        """Add result to bookmarks."""
        try:
            if hasattr(result, 'id') and result.id not in self._bookmarked_results:
                self._bookmarked_results.append(result.id)

                # Trigger callback
                if self._on_bookmark_added:
                    self._on_bookmark_added(result)

                logger.info(f"Added bookmark for result: {result.id}")

        except Exception as e:
            logger.error(f"Error adding bookmark: {e}")

    def remove_bookmark(self, result_id: str) -> None:
        """Remove result from bookmarks."""
        try:
            if result_id in self._bookmarked_results:
                self._bookmarked_results.remove(result_id)
                logger.info(f"Removed bookmark for result: {result_id}")

        except Exception as e:
            logger.error(f"Error removing bookmark: {e}")

    def is_bookmarked(self, result_id: str) -> bool:
        """Check if result is bookmarked."""
        return result_id in self._bookmarked_results

    # Event handlers
    def _handle_result_click(self, result: SearchResult) -> None:
        """Handle result item click."""
        try:
            self.select_result(result)

        except Exception as e:
            logger.error(f"Error handling result click: {e}")

    def _handle_filter_change(self, filter_option: FilterOption) -> None:
        """Handle filter change."""
        try:
            self._state.filters_applied = [filter_option.value] if filter_option != FilterOption.ALL else []

            # Update result list component
            if self._result_list_ui and hasattr(self._result_list_ui, 'apply_filter'):
                self._result_list_ui.apply_filter(filter_option)

            self.update()

        except Exception as e:
            logger.error(f"Error handling filter change: {e}")

    def _handle_sort_change(self, sort_option: SortOption) -> None:
        """Handle sort change."""
        try:
            self._state.sort_order = sort_option.value

            # Update result list component
            if self._result_list_ui and hasattr(self._result_list_ui, 'apply_sort'):
                self._result_list_ui.apply_sort(sort_option)

            self.update()

        except Exception as e:
            logger.error(f"Error handling sort change: {e}")

    def _handle_export_click(self, e) -> None:
        """Handle export button click."""
        try:
            if self._on_export_requested and self._state.results:
                self._on_export_requested(self._state.results)

        except Exception as e:
            logger.error(f"Error handling export click: {e}")

    def _handle_share_click(self, e) -> None:
        """Handle share button click."""
        try:
            # Create shareable search results summary
            if self._state.results:
                share_data = {
                    "query": self._state.query,
                    "total_results": self._state.total_results,
                    "search_time": self._state.search_time_ms,
                    "timestamp": datetime.now().isoformat()
                }

                # For now, just log the share action
                logger.info(f"Share requested for search: {share_data}")

        except Exception as e:
            logger.error(f"Error handling share click: {e}")

    def _handle_refresh_click(self, e) -> None:
        """Handle refresh button click."""
        try:
            if self._state.query:
                self.set_loading_state(True)
                # Trigger search refresh through callback
                if self._on_search_refined:
                    self._on_search_refined(self._state.query)

        except Exception as e:
            logger.error(f"Error handling refresh click: {e}")

    def _handle_settings_click(self, e) -> None:
        """Handle settings button click."""
        try:
            # For now, just log the settings action
            logger.info("Search settings requested")

        except Exception as e:
            logger.error(f"Error handling settings click: {e}")

    def _handle_suggestion_click(self, suggestion: str) -> None:
        """Handle search suggestion click."""
        try:
            if self._on_search_refined:
                self._on_search_refined(suggestion)

        except Exception as e:
            logger.error(f"Error handling suggestion click: {e}")

    def _handle_citation_copy(self, citation: Citation) -> None:
        """Handle citation copy action."""
        try:
            # For now, just log the citation copy action
            logger.info(f"Citation copied: {citation.id if hasattr(citation, 'id') else 'unknown'}")

        except Exception as e:
            logger.error(f"Error handling citation copy: {e}")

    def _handle_source_click(self, citation: Citation) -> None:
        """Handle citation source click."""
        try:
            # For now, just log the source click action
            logger.info(f"Citation source clicked: {citation.id if hasattr(citation, 'id') else 'unknown'}")

        except Exception as e:
            logger.error(f"Error handling source click: {e}")

    # Helper methods
    def _generate_search_suggestions(self) -> List[str]:
        """Generate search suggestions based on current query and history."""
        try:
            suggestions = []

            if not self._state.query:
                # Return recent searches
                return self._search_history[:5]

            query_lower = self._state.query.lower()

            # Add suggestions from search history
            for history_item in self._search_history:
                if query_lower in history_item.lower() and history_item != self._state.query:
                    suggestions.append(history_item)

            # Add common search refinements
            common_refinements = [
                f"{self._state.query} recent",
                f"{self._state.query} detailed",
                f"{self._state.query} summary",
                f"{self._state.query} examples"
            ]

            for refinement in common_refinements:
                if refinement not in suggestions:
                    suggestions.append(refinement)

            return suggestions[:8]  # Limit to 8 suggestions

        except Exception as e:
            logger.error(f"Error generating search suggestions: {e}")
            return []

    def _build_loading_state(self) -> ft.Control:
        """Build loading state UI."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(
                            width=self.get_responsive_value(40, 48, 56, 64),
                            height=self.get_responsive_value(40, 48, 56, 64),
                            stroke_width=4,
                            color=theme.get_color("primary")
                        ),
                        ft.Text(
                            "Searching...",
                            style=typography.get_text_style("title_medium"),
                            color=theme.get_color("on_surface"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            f"Query: {self._state.query}" if self._state.query else "Processing search request",
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    main_alignment=ft.MainAxisAlignment.CENTER,
                    spacing=spacing.lg
                ),
                padding=ft.padding.all(spacing.xl),
                expand=True,
                alignment=ft.alignment.center
            )

        except Exception as e:
            logger.error(f"Error building loading state: {e}")
            return ft.Container()

    def _build_empty_state(self) -> ft.Control:
        """Build empty state UI when no results found."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.SEARCH_OFF,
                            size=self.get_responsive_value(64, 72, 80, 88),
                            color=theme.get_color("outline")
                        ),
                        ft.Text(
                            "No results found",
                            style=typography.get_text_style("title_large"),
                            color=theme.get_color("on_surface"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            f"No results found for '{self._state.query}'" if self._state.query else "Try searching for something",
                            style=typography.get_text_style("body_large"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            "Try different keywords or check your spelling",
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    main_alignment=ft.MainAxisAlignment.CENTER,
                    spacing=spacing.lg
                ),
                padding=ft.padding.all(spacing.xl),
                expand=True,
                alignment=ft.alignment.center
            )

        except Exception as e:
            logger.error(f"Error building empty state: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state UI."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.ERROR_OUTLINE,
                            size=self.get_responsive_value(64, 72, 80, 88),
                            color=theme.get_color("error")
                        ),
                        ft.Text(
                            "Search Error",
                            style=typography.get_text_style("title_large"),
                            color=theme.get_color("error"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            error_message,
                            style=typography.get_text_style("body_large"),
                            color=theme.get_color("on_surface"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.ElevatedButton(
                            text="Try Again",
                            icon=ft.Icons.REFRESH,
                            on_click=self._handle_refresh_click,
                            bgcolor=theme.get_color("primary"),
                            color=theme.get_color("on_primary")
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    main_alignment=ft.MainAxisAlignment.CENTER,
                    spacing=spacing.lg
                ),
                padding=ft.padding.all(spacing.xl),
                expand=True,
                alignment=ft.alignment.center
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    def _build_fallback_results(self) -> ft.Control:
        """Build fallback results display when result list component is not available."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            result_cards = []
            for i, result in enumerate(self._state.results[:10]):  # Show first 10 results
                card = ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    getattr(result, 'title', f'Result {i+1}'),
                                    style=typography.get_text_style("title_small"),
                                    color=theme.get_color("on_surface"),
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=2
                                ),
                                ft.Text(
                                    getattr(result, 'snippet', 'No preview available'),
                                    style=typography.get_text_style("body_medium"),
                                    color=theme.get_color("on_surface_variant"),
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=3
                                )
                            ],
                            spacing=spacing.sm,
                            tight=True
                        ),
                        padding=ft.padding.all(spacing.md),
                        on_click=lambda e, r=result: self._handle_result_click(r)
                    )
                )
                result_cards.append(card)

            return ft.Container(
                content=ft.Column(
                    controls=result_cards,
                    spacing=spacing.md,
                    scroll=ft.ScrollMode.AUTO
                ),
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building fallback results: {e}")
            return ft.Container()

    def _build_compact_toolbar(self) -> ft.Control:
        """Build compact toolbar for mobile layouts."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(
                            f"{self._state.total_results:,}" if self._state.total_results > 0 else "0",
                            style=typography.get_text_style("title_small"),
                            color=theme.get_color("on_surface")
                        ),
                        ft.Expanded(child=ft.Container()),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            icon_size=20,
                            on_click=self._handle_refresh_click,
                            icon_color=theme.get_color("primary")
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DOWNLOAD,
                            icon_size=20,
                            on_click=self._handle_export_click,
                            icon_color=theme.get_color("primary"),
                            disabled=len(self._state.results) == 0
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.symmetric(horizontal=spacing.md, vertical=spacing.sm),
                bgcolor=theme.get_color("surface_variant"),
                border_radius=self.get_responsive_value(6, 8, 10, 12)
            )

        except Exception as e:
            logger.error(f"Error building compact toolbar: {e}")
            return ft.Container()

    def _build_compact_status_bar(self) -> ft.Control:
        """Build compact status bar for mobile layouts."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            if self._state.is_loading:
                return ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.ProgressRing(width=16, height=16, stroke_width=2),
                            ft.Text(
                                "Loading...",
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=spacing.xs,
                        alignment=ft.MainAxisAlignment.CENTER
                    ),
                    padding=ft.padding.all(spacing.sm)
                )

            return ft.Container()

        except Exception as e:
            logger.error(f"Error building compact status bar: {e}")
            return ft.Container()

    def _build_sidebar(self) -> ft.Control:
        """Build sidebar for detailed layout."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Column(
                controls=[
                    ft.Text(
                        "Search Tools",
                        style=typography.get_text_style("title_medium"),
                        color=theme.get_color("on_surface")
                    ),
                    ft.Divider(color=theme.get_color("outline_variant")),
                    # Search history
                    ft.Text(
                        "Recent Searches",
                        style=typography.get_text_style("label_large"),
                        color=theme.get_color("on_surface_variant")
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.TextButton(
                                    text=query,
                                    on_click=lambda e, q=query: self._handle_suggestion_click(q)
                                ) for query in self._search_history[:5]
                            ],
                            spacing=spacing.xs,
                            tight=True
                        ) if self._search_history else ft.Text(
                            "No recent searches",
                            style=typography.get_text_style("body_small"),
                            color=theme.get_color("on_surface_variant")
                        )
                    ),
                    ft.Divider(color=theme.get_color("outline_variant")),
                    # Bookmarks
                    ft.Text(
                        "Bookmarks",
                        style=typography.get_text_style("label_large"),
                        color=theme.get_color("on_surface_variant")
                    ),
                    ft.Text(
                        f"{len(self._bookmarked_results)} bookmarked results",
                        style=typography.get_text_style("body_small"),
                        color=theme.get_color("on_surface_variant")
                    )
                ],
                spacing=spacing.md,
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building sidebar: {e}")
            return ft.Container()

    def _build_detailed_header(self) -> ft.Control:
        """Build detailed header for detailed layout."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "Search Results",
                                    style=typography.get_text_style("headline_medium"),
                                    color=theme.get_color("on_surface")
                                ),
                                ft.Text(
                                    f"Query: '{self._state.query}'" if self._state.query else "No active search",
                                    style=typography.get_text_style("body_large"),
                                    color=theme.get_color("on_surface_variant")
                                )
                            ],
                            spacing=spacing.xs,
                            tight=True
                        ),
                        ft.Expanded(child=ft.Container()),
                        ft.Row(
                            controls=[
                                ft.Text(
                                    f"{self._state.total_results:,} results",
                                    style=typography.get_text_style("title_medium"),
                                    color=theme.get_color("primary")
                                ),
                                ft.Text(
                                    f"({self._state.search_time_ms:.0f}ms)",
                                    style=typography.get_text_style("body_medium"),
                                    color=theme.get_color("on_surface_variant")
                                )
                            ],
                            spacing=spacing.sm,
                            tight=True
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.all(spacing.lg),
                bgcolor=theme.get_color("surface"),
                border_radius=self.get_responsive_value(8, 10, 12, 14),
                border=ft.border.all(1, theme.get_color("outline_variant"))
            )

        except Exception as e:
            logger.error(f"Error building detailed header: {e}")
            return ft.Container()

    def _build_result_preview(self, result: SearchResult) -> ft.Control:
        """Build preview for selected result."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Document Preview",
                            style=typography.get_text_style("title_medium"),
                            color=theme.get_color("on_surface")
                        ),
                        ft.Divider(color=theme.get_color("outline_variant")),
                        ft.Text(
                            getattr(result, 'title', 'Untitled'),
                            style=typography.get_text_style("title_small"),
                            color=theme.get_color("on_surface"),
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=2
                        ),
                        ft.Text(
                            getattr(result, 'content', getattr(result, 'snippet', 'No content available')),
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=10
                        ),
                        ft.Row(
                            controls=[
                                ft.ElevatedButton(
                                    text="Open Document",
                                    icon=ft.Icons.OPEN_IN_NEW,
                                    on_click=lambda e: self._handle_result_click(result)
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.BOOKMARK_ADD if not self.is_bookmarked(getattr(result, 'id', '')) else ft.Icons.BOOKMARK,
                                    tooltip="Bookmark",
                                    on_click=lambda e: self.add_bookmark(result),
                                    icon_color=theme.get_color("primary")
                                )
                            ],
                            spacing=spacing.md
                        )
                    ],
                    spacing=spacing.md,
                    expand=True
                ),
                padding=ft.padding.all(spacing.lg),
                bgcolor=theme.get_color("surface"),
                border_radius=self.get_responsive_value(8, 10, 12, 14),
                border=ft.border.all(1, theme.get_color("outline_variant")),
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building result preview: {e}")
            return ft.Container()

    # Public API methods
    def get_search_state(self) -> SearchResultsState:
        """Get current search state."""
        return self._state

    def get_configuration(self) -> SearchResultsConfig:
        """Get current configuration."""
        return self._config

    def update_configuration(self, config: SearchResultsConfig) -> None:
        """Update configuration and refresh UI."""
        try:
            self._config = config
            self._initialize_components()  # Reinitialize with new config
            self.update()

        except Exception as e:
            logger.error(f"Error updating configuration: {e}")

    def get_search_history(self) -> List[str]:
        """Get search history."""
        return self._search_history.copy()

    def clear_search_history(self) -> None:
        """Clear search history."""
        self._search_history.clear()

    def get_bookmarked_results(self) -> List[str]:
        """Get bookmarked result IDs."""
        return self._bookmarked_results.copy()

    def export_results(self, format_type: str = "JSON") -> Optional[str]:
        """Export search results in specified format."""
        try:
            if not self._state.results:
                return None

            export_data = {
                "query": self._state.query,
                "total_results": self._state.total_results,
                "search_time_ms": self._state.search_time_ms,
                "timestamp": datetime.now().isoformat(),
                "results": [
                    {
                        "title": getattr(result, 'title', ''),
                        "snippet": getattr(result, 'snippet', ''),
                        "relevance_score": getattr(result, 'relevance_score', 0.0),
                        "document_type": getattr(result, 'document_type', ''),
                        "file_path": getattr(result, 'file_path', '')
                    }
                    for result in self._state.results
                ]
            }

            if format_type.upper() == "JSON":
                return json.dumps(export_data, indent=2)
            else:
                # For other formats, return JSON for now
                return json.dumps(export_data, indent=2)

        except Exception as e:
            logger.error(f"Error exporting results: {e}")
            return None
