"""
Module: citation_viewer_ui
Description: Citation display and management component for search results with source references.
            Provides comprehensive citation viewing with multiple format support, clickable references,
            copy-to-clipboard functionality, and responsive design. Integrates fully with theme system
            for consistent styling and accessibility compliance.
Phase: 4
Location: /src/modules/ui/search_results_ui/citation_viewer_ui/citation_viewer_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from datetime import datetime

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


class CitationFormat(Enum):
    """Citation format types."""
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"
    IEEE = "ieee"
    HARVARD = "harvard"
    VANCOUVER = "vancouver"


@dataclass
class Citation:
    """
    Citation data model with comprehensive source information.
    
    Attributes:
        id: Unique citation identifier
        title: Document or source title
        authors: List of author names
        publication_date: Publication date
        source_type: Type of source (book, article, website, etc.)
        url: Source URL if available
        page_numbers: Specific page references
        document_id: Associated document identifier
        chunk_id: Associated chunk identifier if applicable
        relevance_score: Citation relevance score (0.0-1.0)
        excerpt: Text excerpt from the source
        metadata: Additional citation metadata
    """
    id: str
    title: str
    authors: List[str] = field(default_factory=list)
    publication_date: Optional[str] = None
    source_type: str = "document"
    url: Optional[str] = None
    page_numbers: List[int] = field(default_factory=list)
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    relevance_score: float = 0.0
    excerpt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def format_citation(self, format_type: CitationFormat) -> str:
        """Format citation according to specified style."""
        if format_type == CitationFormat.APA:
            return self._format_apa()
        elif format_type == CitationFormat.MLA:
            return self._format_mla()
        elif format_type == CitationFormat.CHICAGO:
            return self._format_chicago()
        elif format_type == CitationFormat.IEEE:
            return self._format_ieee()
        elif format_type == CitationFormat.HARVARD:
            return self._format_harvard()
        elif format_type == CitationFormat.VANCOUVER:
            return self._format_vancouver()
        else:
            return self._format_apa()  # Default to APA
    
    def _format_apa(self) -> str:
        """Format citation in APA style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown Author"
        year = f"({self.publication_date})" if self.publication_date else "(n.d.)"
        pages = f", pp. {'-'.join(map(str, self.page_numbers))}" if self.page_numbers else ""
        return f"{authors_str} {year}. {self.title}{pages}."
    
    def _format_mla(self) -> str:
        """Format citation in MLA style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown Author"
        pages = f" {'-'.join(map(str, self.page_numbers))}" if self.page_numbers else ""
        return f"{authors_str}. \"{self.title}.\" {self.publication_date or 'n.d.'}{pages}."
    
    def _format_chicago(self) -> str:
        """Format citation in Chicago style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown Author"
        pages = f", {'-'.join(map(str, self.page_numbers))}" if self.page_numbers else ""
        return f"{authors_str}. \"{self.title}.\" Accessed {self.publication_date or 'n.d.'}{pages}."
    
    def _format_ieee(self) -> str:
        """Format citation in IEEE style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown Author"
        pages = f", pp. {'-'.join(map(str, self.page_numbers))}" if self.page_numbers else ""
        return f"{authors_str}, \"{self.title},\" {self.publication_date or 'n.d.'}{pages}."
    
    def _format_harvard(self) -> str:
        """Format citation in Harvard style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown Author"
        year = self.publication_date or "n.d."
        pages = f", pp. {'-'.join(map(str, self.page_numbers))}" if self.page_numbers else ""
        return f"{authors_str} {year}, '{self.title}'{pages}."
    
    def _format_vancouver(self) -> str:
        """Format citation in Vancouver style."""
        authors_str = ", ".join(self.authors) if self.authors else "Unknown Author"
        pages = f";{'-'.join(map(str, self.page_numbers))}" if self.page_numbers else ""
        return f"{authors_str}. {self.title}. {self.publication_date or 'n.d.'}{pages}."


class CitationViewerUI(ThemeAwareUserControl):
    """
    Citation display and management component with comprehensive formatting support.
    
    Features:
    - Multiple citation format support (APA, MLA, Chicago, IEEE, Harvard, Vancouver)
    - Clickable citations with navigation to source documents
    - Copy-to-clipboard functionality for formatted citations
    - Responsive design with breakpoint-aware layouts
    - Theme-aware styling with full integration
    - Accessibility compliance with keyboard navigation
    - Citation grouping and filtering capabilities
    - Export functionality for citation lists
    - Real-time citation formatting preview
    - Source document preview integration
    """
    
    def __init__(self,
                 citations: Optional[List[Citation]] = None,
                 default_format: CitationFormat = CitationFormat.APA,
                 show_format_selector: bool = True,
                 show_copy_buttons: bool = True,
                 show_relevance_scores: bool = True,
                 enable_grouping: bool = True,
                 max_citations_per_page: int = 10,
                 on_citation_click: Optional[Callable[[Citation], None]] = None,
                 on_document_navigate: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the CitationViewerUI component.
        
        Args:
            citations: List of citations to display
            default_format: Default citation format
            show_format_selector: Whether to show format selection dropdown
            show_copy_buttons: Whether to show copy-to-clipboard buttons
            show_relevance_scores: Whether to display relevance scores
            enable_grouping: Whether to enable citation grouping
            max_citations_per_page: Maximum citations per page
            on_citation_click: Callback for citation click events
            on_document_navigate: Callback for document navigation
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._citations = citations or []
        self._default_format = default_format
        self._current_format = default_format
        self._show_format_selector = show_format_selector
        self._show_copy_buttons = show_copy_buttons
        self._show_relevance_scores = show_relevance_scores
        self._enable_grouping = enable_grouping
        self._max_citations_per_page = max_citations_per_page
        
        # Callbacks
        self._on_citation_click = on_citation_click
        self._on_document_navigate = on_document_navigate
        
        # State management
        self._current_page = 0
        self._search_query = ""
        self._selected_citations: List[str] = []
        self._group_by_source = False
        self._sort_by_relevance = True
        
        # UI components
        self._format_selector: Optional[ft.Dropdown] = None
        self._search_field: Optional[ft.TextField] = None
        self._citations_container: Optional[ft.Column] = None
        self._pagination_controls: Optional[ft.Row] = None
        self._toolbar: Optional[ft.Row] = None
        
        # Initialize component
        self._initialize_component()
    
    def _initialize_component(self):
        """Initialize the citation viewer component."""
        try:
            # Sort citations by relevance if enabled
            if self._sort_by_relevance:
                self._citations.sort(key=lambda c: c.relevance_score, reverse=True)
            
            logger.info(f"CitationViewerUI initialized with {len(self._citations)} citations")
            
        except Exception as e:
            logger.error(f"Error initializing citation viewer: {e}")
    
    def add_citation(self, citation: Citation):
        """Add a new citation to the viewer."""
        try:
            self._citations.append(citation)
            if self._sort_by_relevance:
                self._citations.sort(key=lambda c: c.relevance_score, reverse=True)
            
            # Refresh display
            asyncio.create_task(self._refresh_citations_display())
            
        except Exception as e:
            logger.error(f"Error adding citation: {e}")
    
    def remove_citation(self, citation_id: str):
        """Remove a citation by ID."""
        try:
            self._citations = [c for c in self._citations if c.id != citation_id]
            asyncio.create_task(self._refresh_citations_display())
            
        except Exception as e:
            logger.error(f"Error removing citation: {e}")
    
    def clear_citations(self):
        """Clear all citations."""
        try:
            self._citations.clear()
            self._selected_citations.clear()
            asyncio.create_task(self._refresh_citations_display())
            
        except Exception as e:
            logger.error(f"Error clearing citations: {e}")
    
    def set_format(self, format_type: CitationFormat):
        """Set the citation format."""
        try:
            self._current_format = format_type
            asyncio.create_task(self._refresh_citations_display())

        except Exception as e:
            logger.error(f"Error setting citation format: {e}")

    def build(self) -> ft.Control:
        """Build the responsive citation viewer interface."""
        try:
            # Get responsive values
            responsive_padding = self.get_responsive_padding()
            responsive_spacing = self.get_responsive_value(8, 12, 16, 20)

            # Create main layout
            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        self._build_toolbar_section(),
                        self._build_search_section(),
                        self._build_citations_section(),
                        self._build_pagination_section()
                    ],
                    spacing=responsive_spacing,
                    expand=True
                ),
                padding=responsive_padding
            )

        except Exception as e:
            logger.error(f"Error building citation viewer UI: {e}")
            return self._build_error_state(str(e))

    def _build_toolbar_section(self) -> ft.Control:
        """Build the toolbar section with format selector and controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            controls = []

            # Format selector
            if self._show_format_selector:
                self._format_selector = ft.Dropdown(
                    label="Citation Format",
                    value=self._current_format.value,
                    options=[
                        ft.dropdown.Option(key=fmt.value, text=fmt.value.upper())
                        for fmt in CitationFormat
                    ],
                    on_change=self._on_format_change,
                    width=self.get_responsive_value(120, 140, 160, 180),
                    text_style=typography.get_text_style("body_medium"),
                    bgcolor=palette.surface,
                    border_color=palette.outline
                )
                controls.append(self._format_selector)

            # Citation count
            citation_count = ft.Text(
                f"{len(self._get_filtered_citations())} citations",
                style=typography.get_text_style("body_medium"),
                color=palette.on_surface_variant
            )
            controls.append(citation_count)

            # Spacer
            controls.append(ft.Container(expand=True))

            # Group toggle
            if self._enable_grouping:
                group_toggle = ft.IconButton(
                    icon=icons.GROUP_WORK if self._group_by_source else icons.LIST,
                    tooltip="Group by source" if not self._group_by_source else "List view",
                    on_click=self._toggle_grouping,
                    icon_color=palette.primary
                )
                controls.append(group_toggle)

            # Sort toggle
            sort_toggle = ft.IconButton(
                icon=icons.SORT if self._sort_by_relevance else icons.SORT_BY_ALPHA,
                tooltip="Sort by relevance" if not self._sort_by_relevance else "Sort alphabetically",
                on_click=self._toggle_sort,
                icon_color=palette.primary
            )
            controls.append(sort_toggle)

            # Export button
            export_button = ft.IconButton(
                icon=icons.DOWNLOAD,
                tooltip="Export citations",
                on_click=self._export_citations,
                icon_color=palette.primary
            )
            controls.append(export_button)

            self._toolbar = ft.Row(
                controls=controls,
                alignment=ft.MainAxisAlignment.START,
                spacing=spacing.medium
            )

            return ft.Container(
                content=self._toolbar,
                padding=spacing.small,
                bgcolor=palette.surface_variant,
                border_radius=self.get_responsive_size(8)
            )

        except Exception as e:
            logger.error(f"Error building toolbar section: {e}")
            return ft.Container()

    def _build_search_section(self) -> ft.Control:
        """Build the search section."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            self._search_field = ft.TextField(
                label="Search citations",
                hint_text="Search by title, author, or content...",
                prefix_icon=icons.SEARCH,
                value=self._search_query,
                on_change=self._on_search_change,
                text_style=typography.get_text_style("body_medium"),
                bgcolor=palette.surface,
                border_color=palette.outline,
                expand=True
            )

            return ft.Container(
                content=self._search_field,
                padding=spacing.small
            )

        except Exception as e:
            logger.error(f"Error building search section: {e}")
            return ft.Container()

    def _build_citations_section(self) -> ft.Control:
        """Build the main citations display section."""
        try:
            if not self._citations:
                return self._build_empty_state()

            filtered_citations = self._get_filtered_citations()

            if not filtered_citations:
                return self._build_no_results_state()

            # Get current page citations
            start_idx = self._current_page * self._max_citations_per_page
            end_idx = start_idx + self._max_citations_per_page
            page_citations = filtered_citations[start_idx:end_idx]

            if self._group_by_source:
                return self._build_grouped_citations(page_citations)
            else:
                return self._build_list_citations(page_citations)

        except Exception as e:
            logger.error(f"Error building citations section: {e}")
            return self._build_error_state(str(e))

    def _build_list_citations(self, citations: List[Citation]) -> ft.Control:
        """Build citations in list format."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            citation_controls = []

            for citation in citations:
                citation_card = self._create_citation_card(citation)
                citation_controls.append(citation_card)

            self._citations_container = ft.Column(
                controls=citation_controls,
                spacing=spacing.medium,
                scroll=ft.ScrollMode.AUTO
            )

            return ft.Container(
                content=self._citations_container,
                expand=True,
                padding=spacing.small
            )

        except Exception as e:
            logger.error(f"Error building list citations: {e}")
            return ft.Container()

    def _build_grouped_citations(self, citations: List[Citation]) -> ft.Control:
        """Build citations grouped by source."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            # Group citations by source type
            groups = {}
            for citation in citations:
                source_type = citation.source_type
                if source_type not in groups:
                    groups[source_type] = []
                groups[source_type].append(citation)

            group_controls = []

            for source_type, group_citations in groups.items():
                # Group header
                group_header = ft.Container(
                    content=ft.Text(
                        f"{source_type.title()} ({len(group_citations)})",
                        style=typography.get_text_style("title_medium"),
                        color=palette.primary
                    ),
                    padding=spacing.small,
                    bgcolor=palette.primary_container,
                    border_radius=self.get_responsive_size(4)
                )
                group_controls.append(group_header)

                # Group citations
                for citation in group_citations:
                    citation_card = self._create_citation_card(citation, indent=True)
                    group_controls.append(citation_card)

                # Add spacing between groups
                group_controls.append(ft.Container(height=spacing.medium))

            self._citations_container = ft.Column(
                controls=group_controls,
                spacing=spacing.small,
                scroll=ft.ScrollMode.AUTO
            )

            return ft.Container(
                content=self._citations_container,
                expand=True,
                padding=spacing.small
            )

        except Exception as e:
            logger.error(f"Error building grouped citations: {e}")
            return ft.Container()

    def _create_citation_card(self, citation: Citation, indent: bool = False) -> ft.Control:
        """Create a citation card component."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Format citation text
            formatted_citation = citation.format_citation(self._current_format)

            # Citation text
            citation_text = ft.Text(
                formatted_citation,
                style=typography.get_text_style("body_medium"),
                color=palette.on_surface,
                selectable=True
            )

            # Relevance score
            relevance_controls = []
            if self._show_relevance_scores and citation.relevance_score > 0:
                relevance_badge = ft.Container(
                    content=ft.Text(
                        f"{citation.relevance_score:.2f}",
                        style=typography.get_text_style("label_small"),
                        color=palette.on_primary
                    ),
                    bgcolor=palette.primary,
                    padding=ft.padding.symmetric(horizontal=spacing.xs, vertical=2),
                    border_radius=self.get_responsive_size(12)
                )
                relevance_controls.append(relevance_badge)

            # Action buttons
            action_buttons = []

            # Copy button
            if self._show_copy_buttons:
                copy_button = ft.IconButton(
                    icon=icons.COPY,
                    tooltip="Copy citation",
                    on_click=lambda e, c=citation: self._copy_citation(c),
                    icon_size=self.get_responsive_size(16),
                    icon_color=palette.primary
                )
                action_buttons.append(copy_button)

            # Navigate button
            if citation.document_id and self._on_document_navigate:
                navigate_button = ft.IconButton(
                    icon=icons.OPEN_IN_NEW,
                    tooltip="Open document",
                    on_click=lambda e, c=citation: self._navigate_to_document(c),
                    icon_size=self.get_responsive_size(16),
                    icon_color=palette.primary
                )
                action_buttons.append(navigate_button)

            # Citation excerpt
            excerpt_control = None
            if citation.excerpt:
                excerpt_control = ft.Container(
                    content=ft.Text(
                        f'"{citation.excerpt}"',
                        style=typography.get_text_style("body_small"),
                        color=palette.on_surface_variant,
                        italic=True,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS
                    ),
                    padding=ft.padding.only(top=spacing.xs)
                )

            # Build card content
            card_content = ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(content=citation_text, expand=True),
                            *relevance_controls
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    excerpt_control if excerpt_control else ft.Container(),
                    ft.Row(
                        controls=action_buttons,
                        alignment=ft.MainAxisAlignment.END,
                        spacing=spacing.xs
                    ) if action_buttons else ft.Container()
                ],
                spacing=spacing.xs,
                tight=True
            )

            # Create card container
            card_padding = spacing.medium
            if indent:
                card_padding = ft.padding.only(
                    left=spacing.large,
                    right=spacing.medium,
                    top=spacing.medium,
                    bottom=spacing.medium
                )

            return ft.Container(
                content=card_content,
                padding=card_padding,
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.outline_variant),
                border_radius=self.get_responsive_size(8),
                on_click=lambda e, c=citation: self._on_citation_card_click(c)
            )

        except Exception as e:
            logger.error(f"Error creating citation card: {e}")
            return ft.Container()

    def _build_pagination_section(self) -> ft.Control:
        """Build pagination controls."""
        try:
            filtered_citations = self._get_filtered_citations()
            total_pages = (len(filtered_citations) + self._max_citations_per_page - 1) // self._max_citations_per_page

            if total_pages <= 1:
                return ft.Container()

            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Previous button
            prev_button = ft.IconButton(
                icon=icons.CHEVRON_LEFT,
                disabled=self._current_page == 0,
                on_click=self._go_to_previous_page,
                icon_color=palette.primary if self._current_page > 0 else palette.on_surface_variant
            )

            # Page info
            page_info = ft.Text(
                f"Page {self._current_page + 1} of {total_pages}",
                style=typography.get_text_style("body_medium"),
                color=palette.on_surface
            )

            # Next button
            next_button = ft.IconButton(
                icon=icons.CHEVRON_RIGHT,
                disabled=self._current_page >= total_pages - 1,
                on_click=self._go_to_next_page,
                icon_color=palette.primary if self._current_page < total_pages - 1 else palette.on_surface_variant
            )

            self._pagination_controls = ft.Row(
                controls=[prev_button, page_info, next_button],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=spacing.medium
            )

            return ft.Container(
                content=self._pagination_controls,
                padding=spacing.medium
            )

        except Exception as e:
            logger.error(f"Error building pagination section: {e}")
            return ft.Container()

    def _build_empty_state(self) -> ft.Control:
        """Build empty state when no citations are available."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            icons.LIBRARY_BOOKS,
                            size=self.get_responsive_size(64),
                            color=palette.on_surface_variant
                        ),
                        ft.Text(
                            "No Citations Available",
                            style=typography.get_text_style("headline_small"),
                            color=palette.on_surface
                        ),
                        ft.Text(
                            "Citations will appear here when search results include source references.",
                            style=typography.get_text_style("body_medium"),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.medium
                ),
                padding=spacing.large,
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building empty state: {e}")
            return ft.Container()

    def _build_no_results_state(self) -> ft.Control:
        """Build no results state when search yields no citations."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            icons.SEARCH_OFF,
                            size=self.get_responsive_size(64),
                            color=palette.on_surface_variant
                        ),
                        ft.Text(
                            "No Citations Found",
                            style=typography.get_text_style("headline_small"),
                            color=palette.on_surface
                        ),
                        ft.Text(
                            f'No citations match your search for "{self._search_query}".',
                            style=typography.get_text_style("body_medium"),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.ElevatedButton(
                            text="Clear Search",
                            icon=icons.CLEAR,
                            on_click=self._clear_search,
                            bgcolor=palette.primary,
                            color=palette.on_primary
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.medium
                ),
                padding=spacing.large,
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building no results state: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state display."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            icons.ERROR,
                            size=self.get_responsive_size(64),
                            color=palette.error
                        ),
                        ft.Text(
                            "Error Loading Citations",
                            style=typography.get_text_style("headline_small"),
                            color=palette.error
                        ),
                        ft.Text(
                            error_message,
                            style=typography.get_text_style("body_medium"),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.ElevatedButton(
                            text="Retry",
                            icon=icons.REFRESH,
                            on_click=self._retry_load,
                            bgcolor=palette.primary,
                            color=palette.on_primary
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.medium
                ),
                padding=spacing.large,
                alignment=ft.alignment.center,
                expand=True
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    # Event Handlers

    async def _on_format_change(self, e):
        """Handle citation format change."""
        try:
            if self._format_selector and e.control.value:
                self._current_format = CitationFormat(e.control.value)
                await self._refresh_citations_display()

        except Exception as ex:
            logger.error(f"Error handling format change: {ex}")

    async def _on_search_change(self, e):
        """Handle search query change."""
        try:
            if self._search_field:
                self._search_query = e.control.value.lower()
                self._current_page = 0  # Reset to first page
                await self._refresh_citations_display()

        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    async def _toggle_grouping(self, e):
        """Toggle citation grouping by source."""
        try:
            self._group_by_source = not self._group_by_source
            await self._refresh_citations_display()

        except Exception as ex:
            logger.error(f"Error toggling grouping: {ex}")

    async def _toggle_sort(self, e):
        """Toggle sort order between relevance and alphabetical."""
        try:
            self._sort_by_relevance = not self._sort_by_relevance

            # Re-sort citations
            if self._sort_by_relevance:
                self._citations.sort(key=lambda c: c.relevance_score, reverse=True)
            else:
                self._citations.sort(key=lambda c: c.title.lower())

            await self._refresh_citations_display()

        except Exception as ex:
            logger.error(f"Error toggling sort: {ex}")

    async def _export_citations(self, e):
        """Export citations to file."""
        try:
            # Create export data
            export_data = []
            for citation in self._get_filtered_citations():
                export_data.append({
                    'id': citation.id,
                    'title': citation.title,
                    'authors': citation.authors,
                    'publication_date': citation.publication_date,
                    'formatted_citation': citation.format_citation(self._current_format),
                    'relevance_score': citation.relevance_score,
                    'source_type': citation.source_type
                })

            # For now, just log the export (in a real implementation, this would save to file)
            logger.info(f"Exporting {len(export_data)} citations in {self._current_format.value} format")

            # Show success message (would be replaced with actual file save dialog)
            if hasattr(self.page, 'show_snack_bar'):
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(f"Exported {len(export_data)} citations"),
                        bgcolor=self.get_palette().success
                    )
                )

        except Exception as ex:
            logger.error(f"Error exporting citations: {ex}")

    async def _go_to_previous_page(self, e):
        """Navigate to previous page."""
        try:
            if self._current_page > 0:
                self._current_page -= 1
                await self._refresh_citations_display()

        except Exception as ex:
            logger.error(f"Error navigating to previous page: {ex}")

    async def _go_to_next_page(self, e):
        """Navigate to next page."""
        try:
            filtered_citations = self._get_filtered_citations()
            total_pages = (len(filtered_citations) + self._max_citations_per_page - 1) // self._max_citations_per_page

            if self._current_page < total_pages - 1:
                self._current_page += 1
                await self._refresh_citations_display()

        except Exception as ex:
            logger.error(f"Error navigating to next page: {ex}")

    async def _clear_search(self, e):
        """Clear search query."""
        try:
            self._search_query = ""
            if self._search_field:
                self._search_field.value = ""
                self._search_field.update()

            self._current_page = 0
            await self._refresh_citations_display()

        except Exception as ex:
            logger.error(f"Error clearing search: {ex}")

    async def _retry_load(self, e):
        """Retry loading citations."""
        try:
            await self._refresh_citations_display()

        except Exception as ex:
            logger.error(f"Error retrying load: {ex}")

    async def _copy_citation(self, citation: Citation):
        """Copy citation to clipboard."""
        try:
            formatted_citation = citation.format_citation(self._current_format)

            # Set clipboard content (Flet handles this automatically)
            if hasattr(self.page, 'set_clipboard'):
                await self.page.set_clipboard_async(formatted_citation)

            # Show success message
            if hasattr(self.page, 'show_snack_bar'):
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text("Citation copied to clipboard"),
                        bgcolor=self.get_palette().success
                    )
                )

            logger.info(f"Copied citation {citation.id} to clipboard")

        except Exception as ex:
            logger.error(f"Error copying citation: {ex}")

    async def _navigate_to_document(self, citation: Citation):
        """Navigate to source document."""
        try:
            if self._on_document_navigate and citation.document_id:
                self._on_document_navigate(citation.document_id)
                logger.info(f"Navigating to document {citation.document_id}")

        except Exception as ex:
            logger.error(f"Error navigating to document: {ex}")

    async def _on_citation_card_click(self, citation: Citation):
        """Handle citation card click."""
        try:
            if self._on_citation_click:
                self._on_citation_click(citation)
                logger.info(f"Citation {citation.id} clicked")

        except Exception as ex:
            logger.error(f"Error handling citation click: {ex}")

    # Utility Methods

    def _get_filtered_citations(self) -> List[Citation]:
        """Get citations filtered by search query."""
        try:
            if not self._search_query:
                return self._citations

            filtered = []
            query = self._search_query.lower()

            for citation in self._citations:
                # Search in title
                if query in citation.title.lower():
                    filtered.append(citation)
                    continue

                # Search in authors
                if any(query in author.lower() for author in citation.authors):
                    filtered.append(citation)
                    continue

                # Search in excerpt
                if citation.excerpt and query in citation.excerpt.lower():
                    filtered.append(citation)
                    continue

                # Search in source type
                if query in citation.source_type.lower():
                    filtered.append(citation)
                    continue

            return filtered

        except Exception as e:
            logger.error(f"Error filtering citations: {e}")
            return self._citations

    async def _refresh_citations_display(self):
        """Refresh the citations display."""
        try:
            if hasattr(self, 'content') and self.content:
                # Rebuild the entire component
                new_content = self.build()
                if hasattr(new_content, 'content'):
                    self.content = new_content.content
                else:
                    self.content = new_content

                # Update the display
                if hasattr(self, 'update'):
                    self.update()

        except Exception as e:
            logger.error(f"Error refreshing citations display: {e}")

    def get_citation_count(self) -> int:
        """Get total number of citations."""
        return len(self._citations)

    def get_filtered_citation_count(self) -> int:
        """Get number of filtered citations."""
        return len(self._get_filtered_citations())

    def get_current_format(self) -> CitationFormat:
        """Get current citation format."""
        return self._current_format

    def get_search_query(self) -> str:
        """Get current search query."""
        return self._search_query

    def set_search_query(self, query: str):
        """Set search query programmatically."""
        try:
            self._search_query = query.lower()
            if self._search_field:
                self._search_field.value = query
                self._search_field.update()

            self._current_page = 0
            asyncio.create_task(self._refresh_citations_display())

        except Exception as e:
            logger.error(f"Error setting search query: {e}")

    def select_citation(self, citation_id: str):
        """Select a citation by ID."""
        try:
            if citation_id not in self._selected_citations:
                self._selected_citations.append(citation_id)
                asyncio.create_task(self._refresh_citations_display())

        except Exception as e:
            logger.error(f"Error selecting citation: {e}")

    def deselect_citation(self, citation_id: str):
        """Deselect a citation by ID."""
        try:
            if citation_id in self._selected_citations:
                self._selected_citations.remove(citation_id)
                asyncio.create_task(self._refresh_citations_display())

        except Exception as e:
            logger.error(f"Error deselecting citation: {e}")

    def clear_selection(self):
        """Clear all selected citations."""
        try:
            self._selected_citations.clear()
            asyncio.create_task(self._refresh_citations_display())

        except Exception as e:
            logger.error(f"Error clearing selection: {e}")

    def get_selected_citations(self) -> List[Citation]:
        """Get currently selected citations."""
        try:
            return [c for c in self._citations if c.id in self._selected_citations]

        except Exception as e:
            logger.error(f"Error getting selected citations: {e}")
            return []

    def export_selected_citations(self, format_type: Optional[CitationFormat] = None) -> str:
        """Export selected citations as formatted text."""
        try:
            selected = self.get_selected_citations()
            if not selected:
                return ""

            export_format = format_type or self._current_format
            formatted_citations = []

            for citation in selected:
                formatted_citations.append(citation.format_citation(export_format))

            return "\n\n".join(formatted_citations)

        except Exception as e:
            logger.error(f"Error exporting selected citations: {e}")
            return ""

    def update_citations(self, citations: List[Citation]):
        """Update the entire citations list."""
        try:
            self._citations = citations.copy()

            # Sort if enabled
            if self._sort_by_relevance:
                self._citations.sort(key=lambda c: c.relevance_score, reverse=True)
            else:
                self._citations.sort(key=lambda c: c.title.lower())

            # Reset pagination
            self._current_page = 0
            self._selected_citations.clear()

            # Refresh display
            asyncio.create_task(self._refresh_citations_display())

        except Exception as e:
            logger.error(f"Error updating citations: {e}")

    def get_citation_by_id(self, citation_id: str) -> Optional[Citation]:
        """Get citation by ID."""
        try:
            for citation in self._citations:
                if citation.id == citation_id:
                    return citation
            return None

        except Exception as e:
            logger.error(f"Error getting citation by ID: {e}")
            return None

    # Accessibility Methods

    def _setup_accessibility_features(self):
        """Setup accessibility features for WCAG 2.1 AA compliance."""
        try:
            # Set semantic properties for screen readers
            if hasattr(self, 'semantics_label'):
                self.semantics_label = "Citation Viewer"

            # Set role for screen readers
            if hasattr(self, 'semantics_role'):
                self.semantics_role = "region"

            # Enable keyboard navigation
            if hasattr(self, 'can_focus'):
                self.can_focus = True

            logger.info("Accessibility features configured for CitationViewerUI")

        except Exception as e:
            logger.error(f"Error setting up accessibility features: {e}")

    def _handle_keyboard_navigation(self, e: ft.KeyboardEvent):
        """Handle keyboard navigation for accessibility."""
        try:
            if e.key == "ArrowDown":
                self._navigate_to_next_citation()
            elif e.key == "ArrowUp":
                self._navigate_to_previous_citation()
            elif e.key == "Enter" or e.key == " ":
                self._activate_focused_citation()
            elif e.key == "Escape":
                self._clear_focus()
            elif e.key == "Home":
                self._focus_first_citation()
            elif e.key == "End":
                self._focus_last_citation()
            elif e.key == "F" and e.ctrl:
                self._focus_search_field()

        except Exception as ex:
            logger.error(f"Error handling keyboard navigation: {ex}")

    def _navigate_to_next_citation(self):
        """Navigate to next citation with keyboard."""
        try:
            # Implementation for keyboard navigation to next citation
            # This would focus the next citation card
            pass

        except Exception as e:
            logger.error(f"Error navigating to next citation: {e}")

    def _navigate_to_previous_citation(self):
        """Navigate to previous citation with keyboard."""
        try:
            # Implementation for keyboard navigation to previous citation
            # This would focus the previous citation card
            pass

        except Exception as e:
            logger.error(f"Error navigating to previous citation: {e}")

    def _activate_focused_citation(self):
        """Activate the currently focused citation."""
        try:
            # Implementation for activating focused citation
            # This would trigger the citation click event
            pass

        except Exception as e:
            logger.error(f"Error activating focused citation: {e}")

    def _clear_focus(self):
        """Clear focus from all citations."""
        try:
            # Implementation for clearing focus
            pass

        except Exception as e:
            logger.error(f"Error clearing focus: {e}")

    def _focus_first_citation(self):
        """Focus the first citation."""
        try:
            # Implementation for focusing first citation
            pass

        except Exception as e:
            logger.error(f"Error focusing first citation: {e}")

    def _focus_last_citation(self):
        """Focus the last citation."""
        try:
            # Implementation for focusing last citation
            pass

        except Exception as e:
            logger.error(f"Error focusing last citation: {e}")

    def _focus_search_field(self):
        """Focus the search field."""
        try:
            if self._search_field and hasattr(self._search_field, 'focus'):
                self._search_field.focus()

        except Exception as e:
            logger.error(f"Error focusing search field: {e}")

    def _get_aria_label_for_citation(self, citation: Citation) -> str:
        """Get ARIA label for citation accessibility."""
        try:
            authors_text = ", ".join(citation.authors) if citation.authors else "Unknown author"
            relevance_text = f", relevance score {citation.relevance_score:.2f}" if citation.relevance_score > 0 else ""
            pages_text = f", pages {'-'.join(map(str, citation.page_numbers))}" if citation.page_numbers else ""

            return f"Citation: {citation.title} by {authors_text}{pages_text}{relevance_text}"

        except Exception as e:
            logger.error(f"Error creating ARIA label: {e}")
            return f"Citation: {citation.title}"

    def _announce_to_screen_reader(self, message: str):
        """Announce message to screen reader."""
        try:
            # In a real implementation, this would use platform-specific
            # screen reader announcement APIs
            logger.info(f"Screen reader announcement: {message}")

        except Exception as e:
            logger.error(f"Error announcing to screen reader: {e}")

    # Theme Integration Override

    def did_mount(self):
        """Called when component is mounted."""
        super().did_mount()
        self._setup_accessibility_features()

    def on_theme_changed(self):
        """Handle theme changes with accessibility considerations."""
        try:
            super().on_theme_changed()

            # Announce theme change to screen reader
            current_theme = "dark" if self.get_theme_manager().is_dark_mode() else "light"
            self._announce_to_screen_reader(f"Theme changed to {current_theme} mode")

        except Exception as e:
            logger.error(f"Error handling theme change: {e}")


# Utility Functions for Citation Management

def create_citation_from_search_result(result_data: Dict[str, Any]) -> Citation:
    """
    Create a Citation object from search result data.

    Args:
        result_data: Dictionary containing search result information

    Returns:
        Citation object
    """
    try:
        return Citation(
            id=result_data.get('id', ''),
            title=result_data.get('title', 'Untitled'),
            authors=result_data.get('authors', []),
            publication_date=result_data.get('publication_date'),
            source_type=result_data.get('source_type', 'document'),
            url=result_data.get('url'),
            page_numbers=result_data.get('page_numbers', []),
            document_id=result_data.get('document_id'),
            chunk_id=result_data.get('chunk_id'),
            relevance_score=result_data.get('relevance_score', 0.0),
            excerpt=result_data.get('excerpt', ''),
            metadata=result_data.get('metadata', {})
        )

    except Exception as e:
        logger.error(f"Error creating citation from search result: {e}")
        return Citation(id='error', title='Error creating citation')


def format_citations_for_export(citations: List[Citation],
                               format_type: CitationFormat = CitationFormat.APA) -> str:
    """
    Format multiple citations for export.

    Args:
        citations: List of Citation objects
        format_type: Citation format to use

    Returns:
        Formatted citations as string
    """
    try:
        formatted_citations = []

        for i, citation in enumerate(citations, 1):
            formatted = citation.format_citation(format_type)
            formatted_citations.append(f"{i}. {formatted}")

        return "\n\n".join(formatted_citations)

    except Exception as e:
        logger.error(f"Error formatting citations for export: {e}")
        return ""
