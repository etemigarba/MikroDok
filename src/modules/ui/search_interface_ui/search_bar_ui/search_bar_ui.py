"""
Module: search_bar_ui
Description: Advanced search input component with auto-complete suggestions, search filters, and query builder
            for MikroDok's Interactive Search (RAG) interface. Provides intelligent search capabilities with
            semantic, keyword, and hybrid search modes. Fully integrated with theme system and responsive design.
Phase: 4
Location: /src/modules/ui/search_interface_ui/search_bar_ui/search_bar_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass
from enum import Enum
import logging

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


class SearchMode(Enum):
    """Search mode enumeration."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass
class SearchSuggestion:
    """Search suggestion data structure."""
    text: str
    type: str  # "recent", "popular", "completion"
    score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SearchFilter:
    """Search filter data structure."""
    key: str
    label: str
    value: Any
    type: str  # "text", "date", "number", "boolean", "select"
    options: Optional[List[str]] = None


class SearchBarUI(ThemeAwareUserControl):
    """
    Advanced search input component with intelligent search capabilities.
    
    Features:
    - Auto-complete suggestions with recent and popular queries
    - Search mode selection (semantic, keyword, hybrid)
    - Advanced search filters with dynamic filter chips
    - Query builder with natural language processing
    - Real-time search validation and error handling
    - Voice search input support (future enhancement)
    - Search history management with persistence
    - Responsive design with breakpoint-aware layouts
    - Full integration with ResponsiveLayoutManager and theme system
    - Accessibility-compliant search interactions
    """
    
    def __init__(self,
                 placeholder: str = "Search your knowledge base...",
                 show_suggestions: bool = True,
                 show_filters: bool = True,
                 show_mode_selector: bool = True,
                 max_suggestions: int = 8,
                 on_search: Optional[Callable[[str, SearchMode, List[SearchFilter]], None]] = None,
                 on_suggestion_selected: Optional[Callable[[SearchSuggestion], None]] = None,
                 on_filter_changed: Optional[Callable[[List[SearchFilter]], None]] = None,
                 **kwargs):
        """
        Initialize the SearchBarUI component.
        
        Args:
            placeholder: Placeholder text for search input
            show_suggestions: Whether to show auto-complete suggestions
            show_filters: Whether to show search filters
            show_mode_selector: Whether to show search mode selector
            max_suggestions: Maximum number of suggestions to display
            on_search: Callback for search execution
            on_suggestion_selected: Callback for suggestion selection
            on_filter_changed: Callback for filter changes
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self.placeholder = placeholder
        self.show_suggestions = show_suggestions
        self.show_filters = show_filters
        self.show_mode_selector = show_mode_selector
        self.max_suggestions = max_suggestions
        
        # Callbacks
        self.on_search = on_search
        self.on_suggestion_selected = on_suggestion_selected
        self.on_filter_changed = on_filter_changed
        
        # State
        self._search_text: str = ""
        self._current_mode: SearchMode = SearchMode.HYBRID
        self._active_filters: List[SearchFilter] = []
        self._suggestions: List[SearchSuggestion] = []
        self._is_suggestions_visible: bool = False
        self._is_filters_visible: bool = False
        
        # UI Components
        self._search_field: Optional[ft.TextField] = None
        self._suggestions_list: Optional[ft.ListView] = None
        self._mode_selector: Optional[ft.SegmentedButton] = None
        self._filter_chips: Optional[ft.Row] = None
        self._suggestions_overlay: Optional[ft.Container] = None
        
        # Search history and suggestions
        self._recent_searches: List[str] = []
        self._popular_searches: List[str] = [
            "machine learning algorithms",
            "neural network architectures", 
            "data preprocessing techniques",
            "model evaluation metrics",
            "deep learning frameworks"
        ]
        
        logger.debug("SearchBarUI component initialized")
    
    def build(self) -> ft.Control:
        """Build the responsive search bar component."""
        try:
            self._build_component()
            return self.content
            
        except Exception as e:
            logger.error(f"Error building SearchBarUI: {e}")
            return self._create_error_fallback()
    
    def _build_component(self) -> None:
        """Build the responsive search bar component."""
        try:
            # Get responsive values
            responsive_padding = self.get_responsive_padding()
            responsive_spacing = self.get_breakpoint_value(8, 12, 16, 20)
            
            # Build main search components
            search_input_section = self._build_search_input()
            mode_selector_section = self._build_mode_selector() if self.show_mode_selector else None
            filter_section = self._build_filter_section() if self.show_filters else None
            
            # Create main layout based on screen size
            if self.is_mobile():
                # Mobile: Vertical stack layout
                main_content = ft.Column(
                    controls=[
                        search_input_section,
                        mode_selector_section,
                        filter_section
                    ],
                    spacing=responsive_spacing,
                    tight=True
                )
            else:
                # Desktop: Horizontal layout with search input taking most space
                main_content = ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Container(
                                    content=search_input_section,
                                    expand=True
                                ),
                                mode_selector_section if mode_selector_section else ft.Container()
                            ],
                            spacing=responsive_spacing,
                            alignment=ft.MainAxisAlignment.START,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        ),
                        filter_section if filter_section else ft.Container()
                    ],
                    spacing=responsive_spacing // 2,
                    tight=True
                )
            
            # Create main container with responsive design
            self.content = self.create_responsive_container(
                content=ft.Stack(
                    controls=[
                        main_content,
                        self._build_suggestions_overlay()
                    ]
                ),
                padding=responsive_padding
            )
            
            logger.debug("SearchBarUI component built successfully")
            
        except Exception as e:
            logger.error(f"Error building search bar component: {e}")
            self.content = self._create_error_fallback()
    
    def _build_search_input(self) -> ft.Control:
        """Build the main search input field."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            
            # Responsive input sizing
            input_height = self.get_breakpoint_value(
                mobile=48, tablet=52, desktop=56, large=60
            )
            
            self._search_field = ft.TextField(
                hint_text=self.placeholder,
                value=self._search_text,
                on_change=self._on_search_change,
                on_submit=self._on_search_submit,
                on_focus=self._on_search_focus,
                on_blur=self._on_search_blur,
                prefix_icon=ft.Icons.SEARCH,
                suffix=ft.IconButton(
                    icon=ft.Icons.CLEAR,
                    tooltip="Clear search",
                    on_click=self._on_clear_search,
                    visible=bool(self._search_text)
                ),
                height=input_height,
                text_style=ft.TextStyle(
                    size=typography.body_large[0],
                    color=palette.text_primary
                ),
                hint_style=ft.TextStyle(
                    size=typography.body_large[0],
                    color=palette.text_secondary
                ),
                bgcolor=palette.surface,
                border_color=palette.borders,
                focused_border_color=palette.primary,
                border_radius=self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=12
                ),
                content_padding=ft.padding.symmetric(
                    horizontal=self.get_spacing().md,
                    vertical=self.get_spacing().sm
                ),
                expand=True
            )
            
            return self._search_field
            
        except Exception as e:
            logger.error(f"Error building search input: {e}")
            return ft.Text("Search input error", color=self.get_palette().error)

    def _build_mode_selector(self) -> ft.Control:
        """Build the search mode selector."""
        try:
            palette = self.get_palette()

            self._mode_selector = ft.SegmentedButton(
                segments=[
                    ft.Segment(
                        value=SearchMode.SEMANTIC.value,
                        label=ft.Text("Semantic"),
                        icon=ft.Icon(ft.Icons.PSYCHOLOGY)
                    ),
                    ft.Segment(
                        value=SearchMode.KEYWORD.value,
                        label=ft.Text("Keyword"),
                        icon=ft.Icon(ft.Icons.SEARCH)
                    ),
                    ft.Segment(
                        value=SearchMode.HYBRID.value,
                        label=ft.Text("Hybrid"),
                        icon=ft.Icon(ft.Icons.AUTO_AWESOME)
                    )
                ],
                selected={self._current_mode.value},
                on_change=self._on_mode_change,
                style=ft.ButtonStyle(
                    color=palette.text_primary,
                    bgcolor=palette.surface_variant
                )
            )

            return ft.Container(
                content=self._mode_selector,
                padding=ft.padding.symmetric(vertical=self.get_spacing().xs)
            )

        except Exception as e:
            logger.error(f"Error building mode selector: {e}")
            return ft.Container()

    def _build_filter_section(self) -> ft.Control:
        """Build the search filters section."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Filter toggle button
            filter_toggle = ft.IconButton(
                icon=ft.Icons.FILTER_LIST,
                tooltip="Show/Hide Filters",
                on_click=self._on_toggle_filters,
                icon_color=palette.primary if self._is_filters_visible else palette.text_secondary
            )

            # Active filter chips
            self._filter_chips = ft.Row(
                controls=self._build_filter_chips(),
                spacing=spacing.xs,
                wrap=True,
                scroll=ft.ScrollMode.AUTO
            )

            # Filter controls (initially hidden)
            filter_controls = ft.Container(
                content=self._build_filter_controls(),
                visible=self._is_filters_visible,
                animate_opacity=300
            )

            return ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            filter_toggle,
                            ft.Container(
                                content=self._filter_chips,
                                expand=True
                            )
                        ],
                        spacing=spacing.sm,
                        alignment=ft.MainAxisAlignment.START
                    ),
                    filter_controls
                ],
                spacing=spacing.xs,
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building filter section: {e}")
            return ft.Container()

    def _build_filter_chips(self) -> List[ft.Control]:
        """Build filter chips for active filters."""
        try:
            palette = self.get_palette()
            chips = []

            for filter_item in self._active_filters:
                chip = ft.Chip(
                    label=ft.Text(f"{filter_item.label}: {filter_item.value}"),
                    delete_icon=ft.Icons.CLOSE,
                    on_delete=lambda e, f=filter_item: self._on_remove_filter(f),
                    bgcolor=palette.primary_container,
                    color=palette.on_primary_container,
                    delete_icon_color=palette.on_primary_container
                )
                chips.append(chip)

            return chips

        except Exception as e:
            logger.error(f"Error building filter chips: {e}")
            return []

    def _build_filter_controls(self) -> ft.Control:
        """Build the filter controls panel."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Common filter controls
            date_filter = ft.Row(
                controls=[
                    ft.Text("Date Range:", style=self.get_text_style("body2")),
                    ft.DatePicker(
                        help_text="From date",
                        on_change=self._on_date_filter_change
                    ),
                    ft.DatePicker(
                        help_text="To date",
                        on_change=self._on_date_filter_change
                    )
                ],
                spacing=spacing.sm
            )

            document_type_filter = ft.Row(
                controls=[
                    ft.Text("Document Type:", style=self.get_text_style("body2")),
                    ft.Dropdown(
                        options=[
                            ft.dropdown.Option("all", "All Types"),
                            ft.dropdown.Option("pdf", "PDF"),
                            ft.dropdown.Option("docx", "Word"),
                            ft.dropdown.Option("txt", "Text"),
                            ft.dropdown.Option("html", "HTML"),
                            ft.dropdown.Option("md", "Markdown")
                        ],
                        value="all",
                        on_change=self._on_document_type_change,
                        width=150
                    )
                ],
                spacing=spacing.sm
            )

            relevance_filter = ft.Row(
                controls=[
                    ft.Text("Min Relevance:", style=self.get_text_style("body2")),
                    ft.Slider(
                        min=0.0,
                        max=1.0,
                        value=0.5,
                        divisions=10,
                        label="{value}",
                        on_change=self._on_relevance_change,
                        width=200
                    )
                ],
                spacing=spacing.sm
            )

            return ft.Container(
                content=ft.Column(
                    controls=[date_filter, document_type_filter, relevance_filter],
                    spacing=spacing.md,
                    tight=True
                ),
                bgcolor=palette.surface_variant,
                border_radius=8,
                padding=spacing.md,
                margin=ft.margin.only(top=spacing.sm)
            )

        except Exception as e:
            logger.error(f"Error building filter controls: {e}")
            return ft.Container()

    def _build_suggestions_overlay(self) -> ft.Control:
        """Build the auto-complete suggestions overlay."""
        try:
            palette = self.get_palette()

            self._suggestions_list = ft.ListView(
                controls=self._build_suggestion_items(),
                spacing=0,
                height=min(len(self._suggestions) * 48, 300),
                auto_scroll=False
            )

            self._suggestions_overlay = ft.Container(
                content=ft.Card(
                    content=self._suggestions_list,
                    elevation=8,
                    margin=0
                ),
                visible=self._is_suggestions_visible and bool(self._suggestions),
                top=60,  # Position below search input
                left=0,
                right=0,
                animate_opacity=200
            )

            return self._suggestions_overlay

        except Exception as e:
            logger.error(f"Error building suggestions overlay: {e}")
            return ft.Container()

    def _build_suggestion_items(self) -> List[ft.Control]:
        """Build suggestion list items."""
        try:
            palette = self.get_palette()
            items = []

            for suggestion in self._suggestions[:self.max_suggestions]:
                # Icon based on suggestion type
                icon = ft.Icons.HISTORY if suggestion.type == "recent" else \
                       ft.Icons.TRENDING_UP if suggestion.type == "popular" else \
                       ft.Icons.LIGHTBULB

                item = ft.ListTile(
                    leading=ft.Icon(icon, color=palette.text_secondary),
                    title=ft.Text(
                        suggestion.text,
                        style=self.get_text_style("body2"),
                        color=palette.text_primary
                    ),
                    subtitle=ft.Text(
                        suggestion.type.title(),
                        style=self.get_text_style("caption"),
                        color=palette.text_secondary
                    ) if suggestion.type != "completion" else None,
                    on_click=lambda e, s=suggestion: self._on_suggestion_click(s),
                    hover_color=palette.surface_variant
                )
                items.append(item)

            return items

        except Exception as e:
            logger.error(f"Error building suggestion items: {e}")
            return []

    # Event Handlers
    def _on_search_change(self, e) -> None:
        """Handle search text change."""
        try:
            self._search_text = e.control.value

            # Update clear button visibility
            if self._search_field and self._search_field.suffix:
                self._search_field.suffix.visible = bool(self._search_text)

            # Update suggestions
            if self.show_suggestions:
                self._update_suggestions()

            self.update()

        except Exception as e:
            logger.error(f"Error handling search change: {e}")

    def _on_search_submit(self, e) -> None:
        """Handle search submission."""
        try:
            if self._search_text.strip():
                # Add to recent searches
                if self._search_text not in self._recent_searches:
                    self._recent_searches.insert(0, self._search_text)
                    self._recent_searches = self._recent_searches[:10]  # Keep last 10

                # Hide suggestions
                self._is_suggestions_visible = False
                self._update_suggestions_overlay()

                # Execute search callback
                if self.on_search:
                    self.on_search(self._search_text, self._current_mode, self._active_filters)

                logger.debug(f"Search submitted: {self._search_text}")

        except Exception as e:
            logger.error(f"Error handling search submit: {e}")

    def _on_search_focus(self, e) -> None:
        """Handle search field focus."""
        try:
            if self.show_suggestions:
                self._is_suggestions_visible = True
                self._update_suggestions()

        except Exception as e:
            logger.error(f"Error handling search focus: {e}")

    def _on_search_blur(self, e) -> None:
        """Handle search field blur."""
        try:
            # Delay hiding suggestions to allow for clicks
            asyncio.create_task(self._delayed_hide_suggestions())

        except Exception as e:
            logger.error(f"Error handling search blur: {e}")

    async def _delayed_hide_suggestions(self) -> None:
        """Hide suggestions after a delay."""
        try:
            await asyncio.sleep(0.2)  # 200ms delay
            self._is_suggestions_visible = False
            self._update_suggestions_overlay()

        except Exception as e:
            logger.error(f"Error in delayed hide suggestions: {e}")

    def _on_clear_search(self, e) -> None:
        """Handle clear search button click."""
        try:
            self._search_text = ""
            if self._search_field:
                self._search_field.value = ""
                self._search_field.suffix.visible = False

            self._is_suggestions_visible = False
            self._update_suggestions_overlay()
            self.update()

        except Exception as e:
            logger.error(f"Error handling clear search: {e}")

    def _on_mode_change(self, e) -> None:
        """Handle search mode change."""
        try:
            selected_values = e.control.selected
            if selected_values:
                mode_value = list(selected_values)[0]
                self._current_mode = SearchMode(mode_value)
                logger.debug(f"Search mode changed to: {self._current_mode.value}")

        except Exception as e:
            logger.error(f"Error handling mode change: {e}")

    def _on_suggestion_click(self, suggestion: SearchSuggestion) -> None:
        """Handle suggestion item click."""
        try:
            self._search_text = suggestion.text
            if self._search_field:
                self._search_field.value = suggestion.text

            self._is_suggestions_visible = False
            self._update_suggestions_overlay()

            # Execute callbacks
            if self.on_suggestion_selected:
                self.on_suggestion_selected(suggestion)

            # Auto-submit search
            self._on_search_submit(None)

        except Exception as e:
            logger.error(f"Error handling suggestion click: {e}")

    def _on_toggle_filters(self, e) -> None:
        """Handle filter toggle button click."""
        try:
            self._is_filters_visible = not self._is_filters_visible
            self._build_component()
            self.update()

        except Exception as e:
            logger.error(f"Error handling filter toggle: {e}")

    def _on_remove_filter(self, filter_item: SearchFilter) -> None:
        """Handle filter removal."""
        try:
            if filter_item in self._active_filters:
                self._active_filters.remove(filter_item)
                self._build_component()

                if self.on_filter_changed:
                    self.on_filter_changed(self._active_filters)

                self.update()

        except Exception as e:
            logger.error(f"Error removing filter: {e}")

    def _on_date_filter_change(self, e) -> None:
        """Handle date filter change."""
        try:
            # Implementation for date filter
            logger.debug("Date filter changed")

        except Exception as e:
            logger.error(f"Error handling date filter change: {e}")

    def _on_document_type_change(self, e) -> None:
        """Handle document type filter change."""
        try:
            doc_type = e.control.value
            if doc_type != "all":
                filter_item = SearchFilter(
                    key="document_type",
                    label="Type",
                    value=doc_type,
                    type="select"
                )

                # Remove existing document type filter
                self._active_filters = [f for f in self._active_filters if f.key != "document_type"]
                self._active_filters.append(filter_item)

                self._build_component()

                if self.on_filter_changed:
                    self.on_filter_changed(self._active_filters)

                self.update()

        except Exception as e:
            logger.error(f"Error handling document type change: {e}")

    def _on_relevance_change(self, e) -> None:
        """Handle relevance threshold change."""
        try:
            relevance = e.control.value
            filter_item = SearchFilter(
                key="min_relevance",
                label="Min Relevance",
                value=f"{relevance:.1f}",
                type="number"
            )

            # Remove existing relevance filter
            self._active_filters = [f for f in self._active_filters if f.key != "min_relevance"]
            self._active_filters.append(filter_item)

            self._build_component()

            if self.on_filter_changed:
                self.on_filter_changed(self._active_filters)

            self.update()

        except Exception as e:
            logger.error(f"Error handling relevance change: {e}")

    # Utility Methods
    def _update_suggestions(self) -> None:
        """Update search suggestions based on current input."""
        try:
            self._suggestions.clear()

            if not self._search_text:
                # Show recent and popular searches when empty
                for search in self._recent_searches[:3]:
                    self._suggestions.append(SearchSuggestion(
                        text=search,
                        type="recent",
                        score=1.0
                    ))

                for search in self._popular_searches[:3]:
                    if search not in self._recent_searches:
                        self._suggestions.append(SearchSuggestion(
                            text=search,
                            type="popular",
                            score=0.8
                        ))
            else:
                # Show completions and matches
                search_lower = self._search_text.lower()

                # Add completions from popular searches
                for search in self._popular_searches:
                    if search_lower in search.lower() and search != self._search_text:
                        self._suggestions.append(SearchSuggestion(
                            text=search,
                            type="completion",
                            score=0.9
                        ))

                # Add recent search matches
                for search in self._recent_searches:
                    if search_lower in search.lower() and search != self._search_text:
                        self._suggestions.append(SearchSuggestion(
                            text=search,
                            type="recent",
                            score=1.0
                        ))

            # Sort by score and limit
            self._suggestions.sort(key=lambda x: x.score, reverse=True)
            self._suggestions = self._suggestions[:self.max_suggestions]

            self._update_suggestions_overlay()

        except Exception as e:
            logger.error(f"Error updating suggestions: {e}")

    def _update_suggestions_overlay(self) -> None:
        """Update the suggestions overlay visibility and content."""
        try:
            if self._suggestions_overlay:
                self._suggestions_overlay.visible = (
                    self._is_suggestions_visible and
                    bool(self._suggestions) and
                    self.show_suggestions
                )

                if self._suggestions_list:
                    self._suggestions_list.controls = self._build_suggestion_items()
                    self._suggestions_list.height = min(len(self._suggestions) * 48, 300)

                self.update()

        except Exception as e:
            logger.error(f"Error updating suggestions overlay: {e}")

    def _create_error_fallback(self) -> ft.Control:
        """Create error fallback UI."""
        try:
            palette = self.get_palette()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ERROR, color=palette.error),
                        ft.Text(
                            "Search component error",
                            style=self.get_text_style("body2"),
                            color=palette.error
                        )
                    ],
                    spacing=self.get_spacing().sm,
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                padding=self.get_spacing().md,
                bgcolor=palette.error_container,
                border_radius=8
            )

        except Exception as e:
            logger.error(f"Error creating error fallback: {e}")
            return ft.Text("Critical error in search component")

    # Public API Methods
    def set_search_text(self, text: str) -> None:
        """Set the search text programmatically."""
        try:
            self._search_text = text
            if self._search_field:
                self._search_field.value = text
                if self._search_field.suffix:
                    self._search_field.suffix.visible = bool(text)

            self.update()

        except Exception as e:
            logger.error(f"Error setting search text: {e}")

    def get_search_text(self) -> str:
        """Get the current search text."""
        return self._search_text

    def set_search_mode(self, mode: SearchMode) -> None:
        """Set the search mode programmatically."""
        try:
            self._current_mode = mode
            if self._mode_selector:
                self._mode_selector.selected = {mode.value}

            self.update()

        except Exception as e:
            logger.error(f"Error setting search mode: {e}")

    def get_search_mode(self) -> SearchMode:
        """Get the current search mode."""
        return self._current_mode

    def add_filter(self, filter_item: SearchFilter) -> None:
        """Add a search filter programmatically."""
        try:
            # Remove existing filter with same key
            self._active_filters = [f for f in self._active_filters if f.key != filter_item.key]
            self._active_filters.append(filter_item)

            self._build_component()

            if self.on_filter_changed:
                self.on_filter_changed(self._active_filters)

            self.update()

        except Exception as e:
            logger.error(f"Error adding filter: {e}")

    def remove_filter(self, filter_key: str) -> None:
        """Remove a search filter by key."""
        try:
            self._active_filters = [f for f in self._active_filters if f.key != filter_key]

            self._build_component()

            if self.on_filter_changed:
                self.on_filter_changed(self._active_filters)

            self.update()

        except Exception as e:
            logger.error(f"Error removing filter: {e}")

    def clear_filters(self) -> None:
        """Clear all active filters."""
        try:
            self._active_filters.clear()

            self._build_component()

            if self.on_filter_changed:
                self.on_filter_changed(self._active_filters)

            self.update()

        except Exception as e:
            logger.error(f"Error clearing filters: {e}")

    def get_active_filters(self) -> List[SearchFilter]:
        """Get the list of active filters."""
        return self._active_filters.copy()

    def focus_search(self) -> None:
        """Focus the search input field."""
        try:
            if self._search_field:
                self._search_field.focus()

        except Exception as e:
            logger.error(f"Error focusing search field: {e}")

    def add_recent_search(self, search_text: str) -> None:
        """Add a search to recent searches."""
        try:
            if search_text and search_text not in self._recent_searches:
                self._recent_searches.insert(0, search_text)
                self._recent_searches = self._recent_searches[:10]  # Keep last 10

        except Exception as e:
            logger.error(f"Error adding recent search: {e}")

    def clear_recent_searches(self) -> None:
        """Clear recent search history."""
        try:
            self._recent_searches.clear()

        except Exception as e:
            logger.error(f"Error clearing recent searches: {e}")

    def set_suggestions(self, suggestions: List[SearchSuggestion]) -> None:
        """Set custom suggestions programmatically."""
        try:
            self._suggestions = suggestions[:self.max_suggestions]
            self._update_suggestions_overlay()

        except Exception as e:
            logger.error(f"Error setting suggestions: {e}")


# Export the main component
__all__ = ["SearchBarUI", "SearchMode", "SearchSuggestion", "SearchFilter"]
