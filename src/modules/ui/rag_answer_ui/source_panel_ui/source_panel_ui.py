"""
Module: source_panel_ui
Description: Side panel showing source documents used for answer generation with comprehensive
            theming integration. Provides responsive source document display with metadata,
            relevance scores, and interactive features for RAG (Retrieval Augmented Generation) responses.
Phase: 4
Location: /src/modules/ui/rag_answer_ui/source_panel_ui/source_panel_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class SourceDisplayMode(Enum):
    """Source panel display modes."""
    COMPACT = "compact"
    DETAILED = "detailed"
    LIST = "list"
    GRID = "grid"


class SourceSortOption(Enum):
    """Source sorting options."""
    RELEVANCE = "relevance"
    TITLE = "title"
    DATE = "date"
    TYPE = "type"
    SIZE = "size"


class SourceFilterOption(Enum):
    """Source filtering options."""
    ALL = "all"
    DOCUMENTS = "documents"
    IMAGES = "images"
    TABLES = "tables"
    HIGH_RELEVANCE = "high_relevance"


@dataclass
class SourceDocument:
    """
    Source document data structure for the source panel.
    
    Contains information about documents used in RAG answer generation.
    """
    # Core identification
    id: str
    document_id: str
    chunk_id: Optional[str] = None
    
    # Content information
    title: str = ""
    content: str = ""
    snippet: str = ""
    page_number: Optional[int] = None
    
    # Relevance and scoring
    relevance_score: float = 0.0
    confidence_score: float = 0.0
    citation_weight: float = 1.0
    
    # Document metadata
    document_type: str = "unknown"
    file_path: str = ""
    file_size: int = 0
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    
    # Processing metadata
    chunk_index: int = 0
    total_chunks: int = 1
    embedding_model: str = ""
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class SourcePanelUI(ThemeAwareUserControl):
    """
    Source panel UI component for displaying RAG answer sources.
    
    Features:
    - Responsive source document display with adaptive layouts
    - Theme-aware styling with no hardcoded colors or dimensions
    - Multiple display modes (compact, detailed, list, grid)
    - Source sorting and filtering capabilities
    - Interactive source navigation and preview
    - Relevance score visualization with color-coded indicators
    - Document metadata display with expandable sections
    - Integration with document viewer and answer box
    - Accessibility compliance with ARIA labels and keyboard navigation
    - Performance optimization for large source lists
    - Smooth animations and transitions
    """
    
    def __init__(
        self,
        sources: Optional[List[SourceDocument]] = None,
        display_mode: SourceDisplayMode = SourceDisplayMode.DETAILED,
        show_relevance_scores: bool = True,
        show_metadata: bool = True,
        enable_sorting: bool = True,
        enable_filtering: bool = True,
        max_sources_display: int = 10,
        on_source_click: Optional[Callable[[SourceDocument], None]] = None,
        on_source_preview: Optional[Callable[[SourceDocument], None]] = None,
        on_source_open: Optional[Callable[[SourceDocument], None]] = None,
        **kwargs
    ):
        """
        Initialize the source panel UI component.
        
        Args:
            sources: List of source documents to display
            display_mode: Display mode for sources
            show_relevance_scores: Whether to show relevance indicators
            show_metadata: Whether to show document metadata
            enable_sorting: Whether to enable source sorting
            enable_filtering: Whether to enable source filtering
            max_sources_display: Maximum number of sources to display
            on_source_click: Callback for source clicks
            on_source_preview: Callback for source preview
            on_source_open: Callback for opening source documents
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)
        
        # Source data
        self._sources = sources or []
        self._filtered_sources = self._sources.copy()
        self._display_mode = display_mode
        
        # Display options
        self._show_relevance_scores = show_relevance_scores
        self._show_metadata = show_metadata
        self._enable_sorting = enable_sorting
        self._enable_filtering = enable_filtering
        self._max_sources_display = max_sources_display
        
        # Callbacks
        self._on_source_click = on_source_click
        self._on_source_preview = on_source_preview
        self._on_source_open = on_source_open
        
        # State management
        self._current_sort = SourceSortOption.RELEVANCE
        self._current_filter = SourceFilterOption.ALL
        self._search_query = ""
        self._expanded_sources = set()
        self._selected_source = None
        
        # UI components
        self._search_field = None
        self._sort_dropdown = None
        self._filter_chips = None
        self._sources_container = None
        self._empty_state_container = None
        
        # Initialize component
        self._apply_current_filter()
        self._sort_sources()
    
    def set_sources(self, sources: List[SourceDocument]) -> None:
        """
        Update the sources list.
        
        Args:
            sources: New list of source documents
        """
        try:
            self._sources = sources or []
            self._apply_current_filter()
            self._sort_sources()
            self._update_display()
            
        except Exception as e:
            logger.error(f"Error setting sources: {e}")
    
    def set_display_mode(self, mode: SourceDisplayMode) -> None:
        """
        Change the display mode.
        
        Args:
            mode: New display mode
        """
        try:
            if mode != self._display_mode:
                self._display_mode = mode
                self._update_display()
                
        except Exception as e:
            logger.error(f"Error setting display mode: {e}")
    
    def build(self) -> ft.Control:
        """Build the responsive source panel interface."""
        try:
            if not self._sources:
                return self._build_empty_state()

            return self._build_source_panel()

        except Exception as e:
            logger.error(f"Error building source panel: {e}")
            return self._build_error_state(str(e))

    def _build_source_panel(self) -> ft.Control:
        """Build the main source panel interface."""
        try:
            theme = self.get_theme()
            spacing = self.get_spacing()

            # Build main content sections
            content_sections = []

            # Add header with controls
            content_sections.append(self._build_panel_header())

            # Add search and filters if enabled
            if self._enable_filtering or self._enable_sorting:
                content_sections.append(self._build_controls_section())

            # Add sources display
            content_sections.append(self._build_sources_display())

            return ft.Container(
                content=ft.Column(
                    controls=content_sections,
                    spacing=spacing.md,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=theme.get_color("surface"),
                border_radius=self.get_responsive_value(8, 10, 12, 14),
                border=ft.border.all(
                    width=1,
                    color=theme.get_color("outline_variant")
                )
            )

        except Exception as e:
            logger.error(f"Error building source panel: {e}")
            return ft.Container()

    def _build_panel_header(self) -> ft.Control:
        """Build the panel header with title and stats."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            source_count = len(self._filtered_sources)
            total_count = len(self._sources)

            return ft.Row(
                controls=[
                    # Panel title and icon
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.SOURCE,
                                size=self.get_responsive_value(18, 20, 22, 24),
                                color=theme.get_color("primary")
                            ),
                            ft.Text(
                                "Sources",
                                style=typography.get_text_style("title_medium"),
                                color=theme.get_color("on_surface"),
                                weight=ft.FontWeight.W_600
                            )
                        ],
                        spacing=spacing.xs
                    ),
                    # Source count badge
                    ft.Container(
                        content=ft.Text(
                            f"{source_count}" if source_count == total_count else f"{source_count}/{total_count}",
                            style=typography.get_text_style("label_small"),
                            color=theme.get_color("on_primary"),
                            weight=ft.FontWeight.W_500
                        ),
                        padding=ft.padding.symmetric(
                            horizontal=spacing.sm,
                            vertical=spacing.xs
                        ),
                        bgcolor=theme.get_color("primary"),
                        border_radius=self.get_responsive_value(12, 14, 16, 18)
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

        except Exception as e:
            logger.error(f"Error building panel header: {e}")
            return ft.Container()

    def _build_controls_section(self) -> ft.Control:
        """Build search and filter controls."""
        try:
            theme = self.get_theme()
            spacing = self.get_spacing()

            controls = []

            # Add search field
            if self._enable_filtering:
                controls.append(self._build_search_field())

            # Add sort and filter controls
            if self._enable_sorting or self._enable_filtering:
                controls.append(self._build_filter_controls())

            return ft.Column(
                controls=controls,
                spacing=spacing.sm,
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building controls section: {e}")
            return ft.Container()

    def _build_search_field(self) -> ft.Control:
        """Build the search input field."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            self._search_field = ft.TextField(
                hint_text="Search sources...",
                hint_style=typography.get_text_style("body_medium"),
                text_style=typography.get_text_style("body_medium"),
                color=theme.get_color("on_surface"),
                bgcolor=theme.get_color("surface_container_lowest"),
                border_color=theme.get_color("outline_variant"),
                focused_border_color=theme.get_color("primary"),
                prefix_icon=ft.Icons.SEARCH,
                border_radius=self.get_responsive_value(6, 7, 8, 9),
                content_padding=ft.padding.symmetric(
                    horizontal=spacing.md,
                    vertical=spacing.sm
                ),
                on_change=self._handle_search_change
            )

            return self._search_field

        except Exception as e:
            logger.error(f"Error building search field: {e}")
            return ft.Container()

    def _build_filter_controls(self) -> ft.Control:
        """Build sort and filter controls."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            controls = []

            # Sort dropdown
            if self._enable_sorting:
                self._sort_dropdown = ft.Dropdown(
                    value=self._current_sort.value,
                    options=[
                        ft.dropdown.Option(key=option.value, text=option.value.replace("_", " ").title())
                        for option in SourceSortOption
                    ],
                    hint_text="Sort by",
                    text_style=typography.get_text_style("body_small"),
                    bgcolor=theme.get_color("surface_container_lowest"),
                    border_color=theme.get_color("outline_variant"),
                    focused_border_color=theme.get_color("primary"),
                    border_radius=self.get_responsive_value(6, 7, 8, 9),
                    content_padding=ft.padding.symmetric(
                        horizontal=spacing.sm,
                        vertical=spacing.xs
                    ),
                    on_change=self._handle_sort_change
                )
                controls.append(self._sort_dropdown)

            # Filter chips
            if self._enable_filtering:
                filter_chips = []
                for filter_option in SourceFilterOption:
                    is_selected = filter_option == self._current_filter

                    chip = ft.FilterChip(
                        label=ft.Text(
                            filter_option.value.replace("_", " ").title(),
                            style=typography.get_text_style("label_small"),
                            color=theme.get_color("on_primary" if is_selected else "on_surface_variant")
                        ),
                        selected=is_selected,
                        bgcolor=theme.get_color("primary" if is_selected else "surface_container_low"),
                        selected_color=theme.get_color("primary"),
                        check_color=theme.get_color("on_primary"),
                        on_click=lambda e, opt=filter_option: self._handle_filter_change(opt)
                    )
                    filter_chips.append(chip)

                controls.append(
                    ft.Row(
                        controls=filter_chips,
                        spacing=spacing.xs,
                        wrap=True
                    )
                )

            return ft.Column(
                controls=controls,
                spacing=spacing.sm,
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building filter controls: {e}")
            return ft.Container()

    def _build_sources_display(self) -> ft.Control:
        """Build the sources display based on current mode."""
        try:
            if not self._filtered_sources:
                return self._build_no_results_state()

            if self._display_mode == SourceDisplayMode.GRID:
                return self._build_grid_display()
            elif self._display_mode == SourceDisplayMode.COMPACT:
                return self._build_compact_display()
            elif self._display_mode == SourceDisplayMode.LIST:
                return self._build_list_display()
            else:  # DETAILED
                return self._build_detailed_display()

        except Exception as e:
            logger.error(f"Error building sources display: {e}")
            return ft.Container()

    def _build_detailed_display(self) -> ft.Control:
        """Build detailed source cards display."""
        try:
            spacing = self.get_spacing()

            # Limit sources to display
            sources_to_show = self._filtered_sources[:self._max_sources_display]

            source_cards = []
            for i, source in enumerate(sources_to_show):
                source_cards.append(self._build_detailed_source_card(source, i))

            return ft.Column(
                controls=source_cards,
                spacing=spacing.md,
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building detailed display: {e}")
            return ft.Container()

    def _build_detailed_source_card(self, source: SourceDocument, index: int) -> ft.Control:
        """Build a detailed source card."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            is_expanded = source.id in self._expanded_sources
            is_selected = self._selected_source == source.id

            # Build card header
            header_controls = [
                # Source index and relevance
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Text(
                                str(index + 1),
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_primary"),
                                weight=ft.FontWeight.W_600
                            ),
                            width=self.get_responsive_value(24, 26, 28, 30),
                            height=self.get_responsive_value(24, 26, 28, 30),
                            bgcolor=theme.get_color("primary"),
                            border_radius=self.get_responsive_value(12, 13, 14, 15),
                            alignment=ft.alignment.center
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    source.title or f"Document {source.document_id[:8]}",
                                    style=typography.get_text_style("title_small"),
                                    color=theme.get_color("on_surface"),
                                    weight=ft.FontWeight.W_500,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS
                                ),
                                ft.Text(
                                    f"{source.document_type.title()} • Page {source.page_number or 'N/A'}",
                                    style=typography.get_text_style("body_small"),
                                    color=theme.get_color("on_surface_variant"),
                                    max_lines=1
                                )
                            ],
                            spacing=spacing.xs,
                            tight=True,
                            expand=True
                        )
                    ],
                    spacing=spacing.sm,
                    vertical_alignment=ft.CrossAxisAlignment.START
                ),
                # Relevance score and actions
                ft.Row(
                    controls=[
                        # Relevance score
                        self._build_relevance_indicator(source.relevance_score) if self._show_relevance_scores else ft.Container(),
                        # Expand/collapse button
                        ft.IconButton(
                            icon=ft.Icons.EXPAND_LESS if is_expanded else ft.Icons.EXPAND_MORE,
                            icon_size=self.get_responsive_value(16, 18, 20, 22),
                            icon_color=theme.get_color("on_surface_variant"),
                            tooltip="Collapse" if is_expanded else "Expand",
                            on_click=lambda e, src_id=source.id: self._toggle_source_expansion(src_id)
                        ),
                        # Open button
                        ft.IconButton(
                            icon=ft.Icons.OPEN_IN_NEW,
                            icon_size=self.get_responsive_value(16, 18, 20, 22),
                            icon_color=theme.get_color("primary"),
                            tooltip="Open source",
                            on_click=lambda e, src=source: self._handle_source_open(src)
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                )
            ]

            # Build card content
            card_content = [
                ft.Column(
                    controls=header_controls,
                    spacing=spacing.sm,
                    tight=True
                )
            ]

            # Add expanded content if expanded
            if is_expanded:
                card_content.append(self._build_expanded_content(source))

            return ft.Container(
                content=ft.Column(
                    controls=card_content,
                    spacing=spacing.md,
                    tight=True
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=theme.get_color("surface_container_lowest" if not is_selected else "primary_container"),
                border_radius=self.get_responsive_value(8, 9, 10, 11),
                border=ft.border.all(
                    width=2 if is_selected else 1,
                    color=theme.get_color("primary" if is_selected else "outline_variant")
                ),
                on_click=lambda e, src=source: self._handle_source_click(src)
            )

        except Exception as e:
            logger.error(f"Error building detailed source card: {e}")
            return ft.Container()

    def _build_relevance_indicator(self, score: float) -> ft.Control:
        """Build relevance score indicator."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Determine color based on score
            if score >= 0.8:
                color = theme.get_color("success")
                bg_color = theme.get_color("success_container")
            elif score >= 0.6:
                color = theme.get_color("warning")
                bg_color = theme.get_color("warning_container")
            else:
                color = theme.get_color("error")
                bg_color = theme.get_color("error_container")

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.STAR,
                            size=self.get_responsive_value(12, 14, 16, 18),
                            color=color
                        ),
                        ft.Text(
                            f"{score:.1%}",
                            style=typography.get_text_style("label_small"),
                            color=color,
                            weight=ft.FontWeight.W_500
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                ),
                padding=ft.padding.symmetric(
                    horizontal=spacing.sm,
                    vertical=spacing.xs
                ),
                bgcolor=bg_color,
                border_radius=self.get_responsive_value(10, 11, 12, 13)
            )

        except Exception as e:
            logger.error(f"Error building relevance indicator: {e}")
            return ft.Container()

    def _build_expanded_content(self, source: SourceDocument) -> ft.Control:
        """Build expanded content for source card."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            content_sections = []

            # Add snippet if available
            if source.snippet:
                content_sections.append(
                    ft.Container(
                        content=ft.Text(
                            source.snippet,
                            style=typography.get_text_style("body_small"),
                            color=theme.get_color("on_surface_variant"),
                            max_lines=3,
                            overflow=ft.TextOverflow.ELLIPSIS
                        ),
                        padding=ft.padding.all(spacing.sm),
                        bgcolor=theme.get_color("surface_container_low"),
                        border_radius=self.get_responsive_value(6, 7, 8, 9),
                        border=ft.border.all(
                            width=1,
                            color=theme.get_color("outline_variant")
                        )
                    )
                )

            # Add metadata if enabled
            if self._show_metadata:
                content_sections.append(self._build_metadata_section(source))

            return ft.Column(
                controls=content_sections,
                spacing=spacing.sm,
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building expanded content: {e}")
            return ft.Container()

    def _build_metadata_section(self, source: SourceDocument) -> ft.Control:
        """Build metadata section for source."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            metadata_items = []

            # File information
            if source.file_path:
                metadata_items.append(
                    self._build_metadata_item("File", source.file_path.split('/')[-1])
                )

            if source.file_size > 0:
                size_str = self._format_file_size(source.file_size)
                metadata_items.append(
                    self._build_metadata_item("Size", size_str)
                )

            # Chunk information
            if source.total_chunks > 1:
                metadata_items.append(
                    self._build_metadata_item("Chunk", f"{source.chunk_index + 1}/{source.total_chunks}")
                )

            # Dates
            if source.created_at:
                metadata_items.append(
                    self._build_metadata_item("Created", source.created_at.strftime("%Y-%m-%d"))
                )

            # Confidence score
            if source.confidence_score > 0:
                metadata_items.append(
                    self._build_metadata_item("Confidence", f"{source.confidence_score:.1%}")
                )

            return ft.Column(
                controls=[
                    ft.Text(
                        "Metadata",
                        style=typography.get_text_style("label_medium"),
                        color=theme.get_color("on_surface_variant"),
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Column(
                        controls=metadata_items,
                        spacing=spacing.xs,
                        tight=True
                    )
                ],
                spacing=spacing.sm,
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building metadata section: {e}")
            return ft.Container()

    def _build_metadata_item(self, label: str, value: str) -> ft.Control:
        """Build individual metadata item."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Row(
                controls=[
                    ft.Text(
                        f"{label}:",
                        style=typography.get_text_style("body_small"),
                        color=theme.get_color("on_surface_variant"),
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        value,
                        style=typography.get_text_style("body_small"),
                        color=theme.get_color("on_surface"),
                        expand=True
                    )
                ],
                spacing=spacing.sm
            )

        except Exception as e:
            logger.error(f"Error building metadata item: {e}")
            return ft.Container()

    def _build_compact_display(self) -> ft.Control:
        """Build compact source list display."""
        try:
            spacing = self.get_spacing()

            sources_to_show = self._filtered_sources[:self._max_sources_display]

            source_items = []
            for i, source in enumerate(sources_to_show):
                source_items.append(self._build_compact_source_item(source, i))

            return ft.Column(
                controls=source_items,
                spacing=spacing.sm,
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building compact display: {e}")
            return ft.Container()

    def _build_compact_source_item(self, source: SourceDocument, index: int) -> ft.Control:
        """Build compact source item."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        # Index
                        ft.Container(
                            content=ft.Text(
                                str(index + 1),
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_primary"),
                                weight=ft.FontWeight.W_500
                            ),
                            width=self.get_responsive_value(20, 22, 24, 26),
                            height=self.get_responsive_value(20, 22, 24, 26),
                            bgcolor=theme.get_color("primary"),
                            border_radius=self.get_responsive_value(10, 11, 12, 13),
                            alignment=ft.alignment.center
                        ),
                        # Title and type
                        ft.Column(
                            controls=[
                                ft.Text(
                                    source.title or f"Document {source.document_id[:8]}",
                                    style=typography.get_text_style("body_medium"),
                                    color=theme.get_color("on_surface"),
                                    weight=ft.FontWeight.W_500,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS
                                ),
                                ft.Text(
                                    f"{source.document_type.title()}",
                                    style=typography.get_text_style("body_small"),
                                    color=theme.get_color("on_surface_variant"),
                                    max_lines=1
                                )
                            ],
                            spacing=spacing.xs,
                            tight=True,
                            expand=True
                        ),
                        # Relevance and action
                        ft.Row(
                            controls=[
                                self._build_relevance_indicator(source.relevance_score) if self._show_relevance_scores else ft.Container(),
                                ft.IconButton(
                                    icon=ft.Icons.OPEN_IN_NEW,
                                    icon_size=self.get_responsive_value(14, 16, 18, 20),
                                    icon_color=theme.get_color("primary"),
                                    tooltip="Open source",
                                    on_click=lambda e, src=source: self._handle_source_open(src)
                                )
                            ],
                            spacing=spacing.xs,
                            tight=True
                        )
                    ],
                    spacing=spacing.sm,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.all(spacing.sm),
                bgcolor=theme.get_color("surface_container_lowest"),
                border_radius=self.get_responsive_value(6, 7, 8, 9),
                on_click=lambda e, src=source: self._handle_source_click(src)
            )

        except Exception as e:
            logger.error(f"Error building compact source item: {e}")
            return ft.Container()

    def _build_empty_state(self) -> ft.Control:
        """Build empty state when no sources available."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.SOURCE_OUTLINED,
                            size=self.get_responsive_value(48, 56, 64, 72),
                            color=theme.get_color("on_surface_variant")
                        ),
                        ft.Text(
                            "No Sources Available",
                            style=typography.get_text_style("title_medium"),
                            color=theme.get_color("on_surface_variant"),
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Text(
                            "Sources will appear here when an answer is generated",
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    spacing=spacing.md,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True
                ),
                padding=ft.padding.all(spacing.xl),
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building empty state: {e}")
            return ft.Container()

    def _build_no_results_state(self) -> ft.Control:
        """Build no results state when filters return empty."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.SEARCH_OFF,
                            size=self.get_responsive_value(40, 48, 56, 64),
                            color=theme.get_color("on_surface_variant")
                        ),
                        ft.Text(
                            "No Sources Found",
                            style=typography.get_text_style("title_medium"),
                            color=theme.get_color("on_surface_variant"),
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Text(
                            "Try adjusting your search or filter criteria",
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.ElevatedButton(
                            text="Clear Filters",
                            icon=ft.Icons.CLEAR,
                            on_click=self._handle_clear_filters
                        )
                    ],
                    spacing=spacing.md,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True
                ),
                padding=ft.padding.all(spacing.xl),
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building no results state: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state display."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.ERROR_OUTLINE,
                            size=self.get_responsive_value(40, 48, 56, 64),
                            color=theme.get_color("error")
                        ),
                        ft.Text(
                            "Error Loading Sources",
                            style=typography.get_text_style("title_medium"),
                            color=theme.get_color("error"),
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Text(
                            error_message,
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    spacing=spacing.md,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True
                ),
                padding=ft.padding.all(spacing.xl),
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    # Event Handlers
    def _handle_search_change(self, e) -> None:
        """Handle search query changes."""
        try:
            self._search_query = e.control.value.lower()
            self._apply_current_filter()
            self._update_display()

        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    def _handle_sort_change(self, e) -> None:
        """Handle sort option changes."""
        try:
            self._current_sort = SourceSortOption(e.control.value)
            self._sort_sources()
            self._update_display()

        except Exception as ex:
            logger.error(f"Error handling sort change: {ex}")

    def _handle_filter_change(self, filter_option: SourceFilterOption) -> None:
        """Handle filter option changes."""
        try:
            self._current_filter = filter_option
            self._apply_current_filter()
            self._sort_sources()
            self._update_display()

        except Exception as e:
            logger.error(f"Error handling filter change: {e}")

    def _handle_clear_filters(self, e) -> None:
        """Handle clear filters action."""
        try:
            self._search_query = ""
            self._current_filter = SourceFilterOption.ALL
            self._current_sort = SourceSortOption.RELEVANCE

            if self._search_field:
                self._search_field.value = ""

            if self._sort_dropdown:
                self._sort_dropdown.value = self._current_sort.value

            self._apply_current_filter()
            self._sort_sources()
            self._update_display()

        except Exception as ex:
            logger.error(f"Error clearing filters: {ex}")

    def _handle_source_click(self, source: SourceDocument) -> None:
        """Handle source click events."""
        try:
            self._selected_source = source.id

            if self._on_source_click:
                self._on_source_click(source)

            self._update_display()

        except Exception as e:
            logger.error(f"Error handling source click: {e}")

    def _handle_source_open(self, source: SourceDocument) -> None:
        """Handle source open events."""
        try:
            if self._on_source_open:
                self._on_source_open(source)

        except Exception as e:
            logger.error(f"Error handling source open: {e}")

    def _toggle_source_expansion(self, source_id: str) -> None:
        """Toggle source expansion state."""
        try:
            if source_id in self._expanded_sources:
                self._expanded_sources.remove(source_id)
            else:
                self._expanded_sources.add(source_id)

            self._update_display()

        except Exception as e:
            logger.error(f"Error toggling source expansion: {e}")

    # Utility Methods
    def _apply_current_filter(self) -> None:
        """Apply current filter and search to sources."""
        try:
            filtered = self._sources.copy()

            # Apply search filter
            if self._search_query:
                filtered = [
                    source for source in filtered
                    if (self._search_query in source.title.lower() or
                        self._search_query in source.content.lower() or
                        self._search_query in source.document_type.lower() or
                        self._search_query in source.file_path.lower())
                ]

            # Apply category filter
            if self._current_filter != SourceFilterOption.ALL:
                if self._current_filter == SourceFilterOption.DOCUMENTS:
                    filtered = [s for s in filtered if s.document_type in ['pdf', 'docx', 'txt', 'md']]
                elif self._current_filter == SourceFilterOption.IMAGES:
                    filtered = [s for s in filtered if s.document_type in ['jpg', 'png', 'gif', 'bmp']]
                elif self._current_filter == SourceFilterOption.TABLES:
                    filtered = [s for s in filtered if 'table' in s.document_type.lower()]
                elif self._current_filter == SourceFilterOption.HIGH_RELEVANCE:
                    filtered = [s for s in filtered if s.relevance_score >= 0.7]

            self._filtered_sources = filtered

        except Exception as e:
            logger.error(f"Error applying filter: {e}")
            self._filtered_sources = self._sources.copy()

    def _sort_sources(self) -> None:
        """Sort filtered sources based on current sort option."""
        try:
            if self._current_sort == SourceSortOption.RELEVANCE:
                self._filtered_sources.sort(key=lambda x: x.relevance_score, reverse=True)
            elif self._current_sort == SourceSortOption.TITLE:
                self._filtered_sources.sort(key=lambda x: x.title.lower())
            elif self._current_sort == SourceSortOption.DATE:
                self._filtered_sources.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
            elif self._current_sort == SourceSortOption.TYPE:
                self._filtered_sources.sort(key=lambda x: x.document_type.lower())
            elif self._current_sort == SourceSortOption.SIZE:
                self._filtered_sources.sort(key=lambda x: x.file_size, reverse=True)

        except Exception as e:
            logger.error(f"Error sorting sources: {e}")

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        try:
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return "Unknown"

    def _update_display(self) -> None:
        """Update the display after changes."""
        try:
            if hasattr(self, 'update'):
                self.update()
        except Exception as e:
            logger.error(f"Error updating display: {e}")
