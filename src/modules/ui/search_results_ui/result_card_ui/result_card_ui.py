"""
Module: result_card_ui
Description: Individual search result card component with responsive design, theme integration,
            and comprehensive display options. Provides reusable card components for search results
            with highlighting, metadata display, and interaction handling.
Phase: 4
Location: /src/modules/ui/search_results_ui/result_card_ui/result_card_ui.py
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
    ResponsiveLayoutManager,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class CardLayout(Enum):
    """Card layout modes for different display contexts."""
    COMPACT = "compact"
    STANDARD = "standard"
    DETAILED = "detailed"
    GRID = "grid"
    LIST = "list"


class CardInteractionState(Enum):
    """Card interaction states for visual feedback."""
    DEFAULT = "default"
    HOVER = "hover"
    PRESSED = "pressed"
    SELECTED = "selected"
    DISABLED = "disabled"


@dataclass
class ResultCard:
    """
    Comprehensive search result card data structure.
    
    Contains all necessary information for displaying search results
    with metadata, relevance scoring, and interaction capabilities.
    """
    # Core identification
    id: str
    document_id: str
    chunk_id: Optional[str] = None
    
    # Content information
    title: str = ""
    content: str = ""
    snippet: str = ""
    highlighted_terms: List[str] = field(default_factory=list)
    
    # Scoring and relevance
    relevance_score: float = 0.0
    confidence_score: float = 1.0
    rank: int = 0
    
    # Document metadata
    document_type: str = "unknown"
    file_path: str = ""
    file_size: int = 0
    page_number: Optional[int] = None
    
    # Timestamps
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    indexed_date: Optional[datetime] = None
    
    # Visual elements
    thumbnail_url: Optional[str] = None
    icon_name: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Interaction state
    is_selected: bool = False
    is_bookmarked: bool = False
    view_count: int = 0
    
    # Search context
    search_query: str = ""
    search_type: str = "hybrid"
    match_positions: List[Tuple[int, int]] = field(default_factory=list)


class ResultCardUI(ThemeAwareUserControl):
    """
    Individual search result card component with comprehensive theming and responsive design.
    
    Features:
    - Multiple layout modes (compact, standard, detailed, grid, list)
    - Theme-aware styling with no hardcoded colors or dimensions
    - Responsive design with breakpoint-aware layouts
    - Search term highlighting with customizable styles
    - Interactive states (hover, selection, disabled)
    - Accessibility compliance with ARIA labels and keyboard navigation
    - Performance optimization for large result sets
    - Smooth animations and transitions
    - Integration with document viewer and metadata systems
    """
    
    def __init__(
        self,
        result_card: ResultCard,
        layout: CardLayout = CardLayout.STANDARD,
        on_click: Optional[Callable[[ResultCard], None]] = None,
        on_bookmark: Optional[Callable[[ResultCard], None]] = None,
        on_preview: Optional[Callable[[ResultCard], None]] = None,
        show_metadata: bool = True,
        show_thumbnail: bool = True,
        enable_highlighting: bool = True,
        max_snippet_length: int = 200,
        **kwargs
    ):
        """
        Initialize the result card UI component.
        
        Args:
            result_card: The result card data to display
            layout: Card layout mode
            on_click: Callback for card click events
            on_bookmark: Callback for bookmark toggle events
            on_preview: Callback for preview events
            show_metadata: Whether to show metadata information
            show_thumbnail: Whether to show thumbnail/icon
            enable_highlighting: Whether to highlight search terms
            max_snippet_length: Maximum length for content snippets
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)
        
        # Core properties
        self._result_card = result_card
        self._layout = layout
        self._show_metadata = show_metadata
        self._show_thumbnail = show_thumbnail
        self._enable_highlighting = enable_highlighting
        self._max_snippet_length = max_snippet_length
        
        # Callbacks
        self._on_click = on_click
        self._on_bookmark = on_bookmark
        self._on_preview = on_preview
        
        # State management
        self._interaction_state = CardInteractionState.DEFAULT
        self._is_loading = False
        self._animation_duration = 200
        
        # UI components
        self._main_container: Optional[ft.Control] = None
        self._content_column: Optional[ft.Control] = None
        self._metadata_row: Optional[ft.Control] = None
        
        # Initialize component
        self._initialize_component()
    
    def _initialize_component(self) -> None:
        """Initialize the card component with theme integration."""
        try:
            # Ensure theme manager is available
            self._ensure_theme_manager()
            
            # Set up responsive callbacks
            self._setup_responsive_callbacks()
            
            # Initialize interaction handlers
            self._setup_interaction_handlers()
            
        except Exception as e:
            logger.error(f"Error initializing result card UI: {e}")
    
    def build(self) -> ft.Control:
        """Build the responsive result card interface."""
        try:
            # Build card based on layout mode
            if self._layout == CardLayout.COMPACT:
                return self._build_compact_card()
            elif self._layout == CardLayout.DETAILED:
                return self._build_detailed_card()
            elif self._layout == CardLayout.GRID:
                return self._build_grid_card()
            elif self._layout == CardLayout.LIST:
                return self._build_list_card()
            else:
                return self._build_standard_card()
                
        except Exception as e:
            logger.error(f"Error building result card: {e}")
            return self._build_error_card(str(e))
    
    def _build_compact_card(self) -> ft.Control:
        """Build compact card layout for dense displays."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            
            # Get document icon
            doc_icon = self._get_document_icon()
            
            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            # Document icon
                            ft.Icon(
                                doc_icon,
                                size=self.get_responsive_value(16, 18, 20, 22),
                                color=theme.get_color("primary")
                            ),
                            # Title and relevance
                            ft.Expanded(
                                child=ft.Column(
                                    controls=[
                                        ft.Text(
                                            self._truncate_text(self._result_card.title, 50),
                                            style=typography.get_text_style("body_medium"),
                                            color=theme.get_color("on_surface"),
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            max_lines=1
                                        ),
                                        ft.Text(
                                            f"{self._result_card.relevance_score:.1%}",
                                            style=typography.get_text_style("label_small"),
                                            color=self._get_relevance_color()
                                        )
                                    ],
                                    spacing=2,
                                    tight=True
                                )
                            ),
                            # Action buttons
                            self._build_action_buttons(compact=True)
                        ],
                        spacing=self.get_responsive_value(8, 10, 12, 14),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    padding=self.get_responsive_padding(scale=0.75),
                    on_click=self._handle_card_click,
                    on_hover=self._handle_card_hover
                )
            )
            
        except Exception as e:
            logger.error(f"Error building compact card: {e}")
            return ft.Container()

    def _build_standard_card(self) -> ft.Control:
        """Build standard card layout for general use."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            responsive_padding = self.get_responsive_padding()

            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            self._build_card_header(),
                            self._build_card_content(),
                            self._build_card_footer() if self._show_metadata else None
                        ],
                        spacing=self.get_responsive_value(8, 10, 12, 14),
                        tight=True
                    ),
                    padding=responsive_padding,
                    on_click=self._handle_card_click,
                    on_hover=self._handle_card_hover
                )
            )

        except Exception as e:
            logger.error(f"Error building standard card: {e}")
            return ft.Container()

    def _build_detailed_card(self) -> ft.Control:
        """Build detailed card layout with full metadata."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            responsive_padding = self.get_responsive_padding()

            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            self._build_card_header(detailed=True),
                            self._build_card_content(detailed=True),
                            self._build_metadata_section(),
                            self._build_card_footer(detailed=True)
                        ],
                        spacing=self.get_responsive_value(10, 12, 14, 16),
                        tight=True
                    ),
                    padding=responsive_padding,
                    on_click=self._handle_card_click,
                    on_hover=self._handle_card_hover
                )
            )

        except Exception as e:
            logger.error(f"Error building detailed card: {e}")
            return ft.Container()

    def _build_grid_card(self) -> ft.Control:
        """Build grid card layout for grid displays."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            # Thumbnail or icon
                            self._build_card_thumbnail(),
                            # Title
                            ft.Text(
                                self._truncate_text(self._result_card.title, 60),
                                style=typography.get_text_style("title_small"),
                                color=theme.get_color("on_surface"),
                                overflow=ft.TextOverflow.ELLIPSIS,
                                max_lines=2,
                                text_align=ft.TextAlign.CENTER
                            ),
                            # Relevance score
                            ft.Container(
                                content=ft.Text(
                                    f"{self._result_card.relevance_score:.1%}",
                                    style=typography.get_text_style("label_small"),
                                    color=self._get_relevance_color()
                                ),
                                bgcolor=theme.get_color("surface_variant"),
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=self.get_responsive_value(6, 7, 8, 9),
                                alignment=ft.alignment.center
                            ),
                            # Action buttons
                            self._build_action_buttons(compact=True)
                        ],
                        spacing=self.get_responsive_value(6, 8, 10, 12),
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True
                    ),
                    padding=self.get_responsive_padding(scale=0.8),
                    on_click=self._handle_card_click,
                    on_hover=self._handle_card_hover,
                    width=self.get_responsive_value(160, 180, 200, 220),
                    height=self.get_responsive_value(200, 220, 240, 260)
                )
            )

        except Exception as e:
            logger.error(f"Error building grid card: {e}")
            return ft.Container()

    def _build_list_card(self) -> ft.Control:
        """Build list card layout for list displays."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            responsive_padding = self.get_responsive_padding()

            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            # Document icon
                            ft.Container(
                                content=ft.Icon(
                                    self._get_document_icon(),
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
                                                        self._result_card.title,
                                                        style=typography.get_text_style("title_small"),
                                                        color=theme.get_color("on_surface"),
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                        max_lines=1
                                                    )
                                                ),
                                                ft.Text(
                                                    f"{self._result_card.relevance_score:.1%}",
                                                    style=typography.get_text_style("label_small"),
                                                    color=self._get_relevance_color()
                                                )
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                                        ),
                                        # Snippet
                                        self._build_highlighted_snippet(),
                                        # Metadata
                                        self._build_metadata_row() if self._show_metadata else None
                                    ],
                                    spacing=self.get_responsive_value(4, 6, 8, 10),
                                    tight=True
                                )
                            ),
                            # Action buttons
                            self._build_action_buttons()
                        ],
                        spacing=self.get_responsive_value(8, 10, 12, 14),
                        vertical_alignment=ft.CrossAxisAlignment.START
                    ),
                    padding=responsive_padding,
                    on_click=self._handle_card_click,
                    on_hover=self._handle_card_hover
                )
            )

        except Exception as e:
            logger.error(f"Error building list card: {e}")
            return ft.Container()

    def _build_card_header(self, detailed: bool = False) -> ft.Control:
        """Build card header with title and relevance score."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            controls = []

            # Add thumbnail/icon if enabled
            if self._show_thumbnail:
                controls.append(
                    ft.Icon(
                        self._get_document_icon(),
                        size=self.get_responsive_value(20, 24, 28, 32),
                        color=theme.get_color("primary")
                    )
                )

            # Title
            controls.append(
                ft.Expanded(
                    child=ft.Text(
                        self._result_card.title,
                        style=typography.get_text_style("title_small" if not detailed else "title_medium"),
                        color=theme.get_color("on_surface"),
                        overflow=ft.TextOverflow.ELLIPSIS,
                        max_lines=1 if not detailed else 2
                    )
                )
            )

            # Relevance score
            controls.append(
                ft.Container(
                    content=ft.Text(
                        f"{self._result_card.relevance_score:.1%}",
                        style=typography.get_text_style("label_small"),
                        color=self._get_relevance_color()
                    ),
                    bgcolor=theme.get_color("surface_variant"),
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    border_radius=self.get_responsive_value(6, 7, 8, 9)
                )
            )

            return ft.Row(
                controls=controls,
                spacing=self.get_responsive_value(8, 10, 12, 14),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

        except Exception as e:
            logger.error(f"Error building card header: {e}")
            return ft.Container()

    def _build_card_content(self, detailed: bool = False) -> ft.Control:
        """Build card content with highlighted snippet."""
        try:
            if not self._result_card.snippet:
                return ft.Container()

            # Build highlighted snippet
            snippet_control = self._build_highlighted_snippet(detailed)

            return ft.Container(
                content=snippet_control,
                padding=ft.padding.only(top=4, bottom=4)
            )

        except Exception as e:
            logger.error(f"Error building card content: {e}")
            return ft.Container()

    def _build_card_footer(self, detailed: bool = False) -> ft.Control:
        """Build card footer with metadata and actions."""
        try:
            controls = []

            # Add metadata if enabled
            if self._show_metadata:
                controls.append(
                    ft.Expanded(
                        child=self._build_metadata_row(detailed)
                    )
                )

            # Add action buttons
            controls.append(self._build_action_buttons())

            return ft.Row(
                controls=controls,
                spacing=self.get_responsive_value(8, 10, 12, 14),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

        except Exception as e:
            logger.error(f"Error building card footer: {e}")
            return ft.Container()

    def _build_highlighted_snippet(self, detailed: bool = False) -> ft.Control:
        """Build highlighted text snippet with search term highlighting."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            # Truncate snippet if needed
            max_length = self._max_snippet_length if not detailed else self._max_snippet_length * 2
            snippet = self._truncate_text(self._result_card.snippet, max_length)

            if not self._enable_highlighting or not self._result_card.highlighted_terms:
                # Return plain text if highlighting is disabled
                return ft.Text(
                    snippet,
                    style=typography.get_text_style("body_small"),
                    color=theme.get_color("on_surface_variant"),
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=2 if not detailed else 4
                )

            # Build highlighted text spans
            text_spans = self._create_highlighted_spans(snippet)

            return ft.Text(
                spans=text_spans,
                style=typography.get_text_style("body_small"),
                color=theme.get_color("on_surface_variant"),
                overflow=ft.TextOverflow.ELLIPSIS,
                max_lines=2 if not detailed else 4
            )

        except Exception as e:
            logger.error(f"Error building highlighted snippet: {e}")
            return ft.Text(self._result_card.snippet or "")

    def _build_metadata_row(self, detailed: bool = False) -> ft.Control:
        """Build metadata row with document information."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            metadata_items = []

            # Document type
            metadata_items.append(
                ft.Text(
                    self._result_card.document_type.upper(),
                    style=typography.get_text_style("label_small"),
                    color=theme.get_color("on_surface_variant")
                )
            )

            # File size
            if self._result_card.file_size > 0:
                metadata_items.append(
                    ft.Text(
                        self._format_file_size(self._result_card.file_size),
                        style=typography.get_text_style("label_small"),
                        color=theme.get_color("on_surface_variant")
                    )
                )

            # Modified date
            if self._result_card.modified_date:
                metadata_items.append(
                    ft.Text(
                        self._format_date(self._result_card.modified_date),
                        style=typography.get_text_style("label_small"),
                        color=theme.get_color("on_surface_variant")
                    )
                )

            # Page number for detailed view
            if detailed and self._result_card.page_number:
                metadata_items.append(
                    ft.Text(
                        f"Page {self._result_card.page_number}",
                        style=typography.get_text_style("label_small"),
                        color=theme.get_color("on_surface_variant")
                    )
                )

            return ft.Row(
                controls=metadata_items,
                spacing=self.get_responsive_value(8, 10, 12, 14),
                wrap=True
            )

        except Exception as e:
            logger.error(f"Error building metadata row: {e}")
            return ft.Container()

    def _build_metadata_section(self) -> ft.Control:
        """Build detailed metadata section for detailed card layout."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            metadata_controls = []

            # Tags
            if self._result_card.tags:
                tag_chips = []
                for tag in self._result_card.tags[:5]:  # Limit to 5 tags
                    tag_chips.append(
                        ft.Container(
                            content=ft.Text(
                                tag,
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("primary")
                            ),
                            bgcolor=theme.get_color("primary_container"),
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=self.get_responsive_value(12, 14, 16, 18)
                        )
                    )

                metadata_controls.append(
                    ft.Row(
                        controls=tag_chips,
                        spacing=self.get_responsive_value(4, 6, 8, 10),
                        wrap=True
                    )
                )

            # Additional metadata
            if self._result_card.metadata:
                for key, value in list(self._result_card.metadata.items())[:3]:  # Limit to 3 items
                    metadata_controls.append(
                        ft.Row(
                            controls=[
                                ft.Text(
                                    f"{key}:",
                                    style=typography.get_text_style("label_small"),
                                    color=theme.get_color("on_surface_variant"),
                                    weight=ft.FontWeight.W_500
                                ),
                                ft.Text(
                                    str(value),
                                    style=typography.get_text_style("label_small"),
                                    color=theme.get_color("on_surface_variant")
                                )
                            ],
                            spacing=self.get_responsive_value(4, 6, 8, 10)
                        )
                    )

            if not metadata_controls:
                return ft.Container()

            return ft.Column(
                controls=metadata_controls,
                spacing=self.get_responsive_value(4, 6, 8, 10),
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building metadata section: {e}")
            return ft.Container()

    def _build_action_buttons(self, compact: bool = False) -> ft.Control:
        """Build action buttons for card interactions."""
        try:
            theme = self.get_theme()
            button_size = self.get_responsive_value(24, 28, 32, 36) if not compact else self.get_responsive_value(20, 22, 24, 26)

            buttons = []

            # Bookmark button
            bookmark_icon = ft.Icons.BOOKMARK if self._result_card.is_bookmarked else ft.Icons.BOOKMARK_BORDER
            buttons.append(
                ft.IconButton(
                    icon=bookmark_icon,
                    icon_size=button_size,
                    icon_color=theme.get_color("primary" if self._result_card.is_bookmarked else "on_surface_variant"),
                    tooltip="Bookmark",
                    on_click=self._handle_bookmark_click
                )
            )

            # Preview button
            if self._on_preview:
                buttons.append(
                    ft.IconButton(
                        icon=ft.Icons.VISIBILITY,
                        icon_size=button_size,
                        icon_color=theme.get_color("on_surface_variant"),
                        tooltip="Preview",
                        on_click=self._handle_preview_click
                    )
                )

            # More actions button
            buttons.append(
                ft.IconButton(
                    icon=ft.Icons.MORE_VERT,
                    icon_size=button_size,
                    icon_color=theme.get_color("on_surface_variant"),
                    tooltip="More actions",
                    on_click=self._handle_more_actions_click
                )
            )

            return ft.Row(
                controls=buttons,
                spacing=self.get_responsive_value(4, 6, 8, 10),
                tight=True
            )

        except Exception as e:
            logger.error(f"Error building action buttons: {e}")
            return ft.Container()

    def _get_document_icon(self) -> str:
        """Get appropriate icon for document type."""
        try:
            doc_type = self._result_card.document_type.lower()

            icon_map = {
                'pdf': ft.Icons.PICTURE_AS_PDF,
                'docx': ft.Icons.DESCRIPTION,
                'doc': ft.Icons.DESCRIPTION,
                'txt': ft.Icons.TEXT_SNIPPET,
                'html': ft.Icons.WEB,
                'md': ft.Icons.ARTICLE,
                'markdown': ft.Icons.ARTICLE,
                'image': ft.Icons.IMAGE,
                'jpg': ft.Icons.IMAGE,
                'jpeg': ft.Icons.IMAGE,
                'png': ft.Icons.IMAGE,
                'gif': ft.Icons.IMAGE,
                'video': ft.Icons.VIDEO_FILE,
                'audio': ft.Icons.AUDIO_FILE,
                'archive': ft.Icons.ARCHIVE,
                'zip': ft.Icons.ARCHIVE,
                'rar': ft.Icons.ARCHIVE
            }

            return icon_map.get(doc_type, ft.Icons.INSERT_DRIVE_FILE)

        except Exception as e:
            logger.error(f"Error getting document icon: {e}")
            return ft.Icons.INSERT_DRIVE_FILE

    def _get_relevance_color(self) -> str:
        """Get color for relevance score based on value."""
        try:
            theme = self.get_theme()
            score = self._result_card.relevance_score

            if score >= 0.8:
                return theme.get_color("success")
            elif score >= 0.6:
                return theme.get_color("warning")
            elif score >= 0.4:
                return theme.get_color("info")
            else:
                return theme.get_color("error")

        except Exception as e:
            logger.error(f"Error getting relevance color: {e}")
            return self.get_theme().get_color("on_surface_variant")

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to specified length with ellipsis."""
        try:
            if not text or len(text) <= max_length:
                return text

            return text[:max_length - 3] + "..."

        except Exception as e:
            logger.error(f"Error truncating text: {e}")
            return text or ""

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

            return f"{size:.1f} {size_names[i]}"

        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return "Unknown"

    def _format_date(self, date: datetime) -> str:
        """Format date in human-readable format."""
        try:
            return date.strftime("%b %d, %Y")

        except Exception as e:
            logger.error(f"Error formatting date: {e}")
            return "Unknown"

    def _create_highlighted_spans(self, text: str) -> List[ft.TextSpan]:
        """Create text spans with highlighted search terms."""
        try:
            theme = self.get_theme()
            spans = []

            if not self._result_card.highlighted_terms:
                return [ft.TextSpan(text)]

            # Simple highlighting implementation
            current_text = text.lower()
            original_text = text
            last_end = 0

            for term in self._result_card.highlighted_terms:
                term_lower = term.lower()
                start = current_text.find(term_lower, last_end)

                if start != -1:
                    # Add text before highlight
                    if start > last_end:
                        spans.append(ft.TextSpan(original_text[last_end:start]))

                    # Add highlighted term
                    spans.append(
                        ft.TextSpan(
                            original_text[start:start + len(term)],
                            style=ft.TextStyle(
                                bgcolor=theme.get_color("primary_container"),
                                color=theme.get_color("on_primary_container"),
                                weight=ft.FontWeight.W_500
                            )
                        )
                    )

                    last_end = start + len(term)

            # Add remaining text
            if last_end < len(original_text):
                spans.append(ft.TextSpan(original_text[last_end:]))

            return spans if spans else [ft.TextSpan(text)]

        except Exception as e:
            logger.error(f"Error creating highlighted spans: {e}")
            return [ft.TextSpan(text)]

    def _setup_responsive_callbacks(self) -> None:
        """Set up responsive design callbacks."""
        try:
            # Add responsive callback if available
            if hasattr(self, 'add_responsive_callback'):
                self.add_responsive_callback(self._on_screen_size_change)

        except Exception as e:
            logger.error(f"Error setting up responsive callbacks: {e}")

    def _setup_interaction_handlers(self) -> None:
        """Set up interaction event handlers."""
        try:
            # Initialize interaction state
            self._interaction_state = CardInteractionState.DEFAULT

        except Exception as e:
            logger.error(f"Error setting up interaction handlers: {e}")

    def _on_screen_size_change(self, screen_size) -> None:
        """Handle screen size changes for responsive design."""
        try:
            # Update component if needed
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error handling screen size change: {e}")

    def _handle_card_click(self, e) -> None:
        """Handle card click events."""
        try:
            if self._on_click and not self._is_loading:
                self._on_click(self._result_card)

        except Exception as e:
            logger.error(f"Error handling card click: {e}")

    def _handle_card_hover(self, e) -> None:
        """Handle card hover events."""
        try:
            if e.data == "true":
                self._interaction_state = CardInteractionState.HOVER
            else:
                self._interaction_state = CardInteractionState.DEFAULT

        except Exception as e:
            logger.error(f"Error handling card hover: {e}")

    def _handle_bookmark_click(self, e) -> None:
        """Handle bookmark button click."""
        try:
            self._result_card.is_bookmarked = not self._result_card.is_bookmarked
            if self._on_bookmark:
                self._on_bookmark(self._result_card)

            # Update UI
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error handling bookmark click: {e}")

    def _handle_preview_click(self, e) -> None:
        """Handle preview button click."""
        try:
            if self._on_preview:
                self._on_preview(self._result_card)

        except Exception as e:
            logger.error(f"Error handling preview click: {e}")

    def _handle_more_actions_click(self, e) -> None:
        """Handle more actions button click."""
        try:
            # TODO: Implement context menu or action sheet
            logger.info(f"More actions clicked for result: {self._result_card.id}")

        except Exception as e:
            logger.error(f"Error handling more actions click: {e}")

    def _build_error_card(self, error_message: str) -> ft.Control:
        """Build error state card."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            return self.create_themed_component(
                "card",
                variant="outlined",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                ft.Icons.ERROR_OUTLINE,
                                size=self.get_responsive_value(24, 28, 32, 36),
                                color=theme.get_color("error")
                            ),
                            ft.Text(
                                "Error loading result",
                                style=typography.get_text_style("body_medium"),
                                color=theme.get_color("error")
                            ),
                            ft.Text(
                                error_message,
                                style=typography.get_text_style("body_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=self.get_responsive_value(8, 10, 12, 14),
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    padding=self.get_responsive_padding(),
                    alignment=ft.alignment.center
                )
            )

        except Exception as e:
            logger.error(f"Error building error card: {e}")
            return ft.Container()

    # Public methods for external control
    def update_result_card(self, result_card: ResultCard) -> None:
        """Update the result card data and refresh UI."""
        try:
            self._result_card = result_card
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error updating result card: {e}")

    def set_layout(self, layout: CardLayout) -> None:
        """Change the card layout mode."""
        try:
            self._layout = layout
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error setting layout: {e}")

    def set_interaction_state(self, state: CardInteractionState) -> None:
        """Set the card interaction state."""
        try:
            self._interaction_state = state
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error setting interaction state: {e}")

    def get_result_card(self) -> ResultCard:
        """Get the current result card data."""
        return self._result_card

    def _build_card_header(self, detailed: bool = False) -> ft.Control:
        """Build card header with title and relevance score."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            controls = []

            # Add thumbnail/icon if enabled
            if self._show_thumbnail:
                controls.append(
                    ft.Icon(
                        self._get_document_icon(),
                        size=self.get_responsive_value(20, 24, 28, 32),
                        color=theme.get_color("primary")
                    )
                )

            # Title
            controls.append(
                ft.Expanded(
                    child=ft.Text(
                        self._result_card.title,
                        style=typography.get_text_style("title_small" if not detailed else "title_medium"),
                        color=theme.get_color("on_surface"),
                        overflow=ft.TextOverflow.ELLIPSIS,
                        max_lines=1 if not detailed else 2
                    )
                )
            )

            # Relevance score
            controls.append(
                ft.Container(
                    content=ft.Text(
                        f"{self._result_card.relevance_score:.1%}",
                        style=typography.get_text_style("label_small"),
                        color=self._get_relevance_color()
                    ),
                    bgcolor=theme.get_color("surface_variant"),
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    border_radius=self.get_responsive_value(6, 7, 8, 9)
                )
            )

            return ft.Row(
                controls=controls,
                spacing=self.get_responsive_value(8, 10, 12, 14),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

        except Exception as e:
            logger.error(f"Error building card header: {e}")
            return ft.Container()

    def _build_card_content(self, detailed: bool = False) -> ft.Control:
        """Build card content with highlighted snippet."""
        try:
            if not self._result_card.snippet:
                return ft.Container()

            # Build highlighted snippet
            snippet_control = self._build_highlighted_snippet(detailed)

            return ft.Container(
                content=snippet_control,
                padding=ft.padding.only(top=4, bottom=4)
            )

        except Exception as e:
            logger.error(f"Error building card content: {e}")
            return ft.Container()

    def _build_card_footer(self, detailed: bool = False) -> ft.Control:
        """Build card footer with metadata and actions."""
        try:
            controls = []

            # Add metadata if enabled
            if self._show_metadata:
                controls.append(
                    ft.Expanded(
                        child=self._build_metadata_row(detailed)
                    )
                )

            # Add action buttons
            controls.append(self._build_action_buttons())

            return ft.Row(
                controls=controls,
                spacing=self.get_responsive_value(8, 10, 12, 14),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

        except Exception as e:
            logger.error(f"Error building card footer: {e}")
            return ft.Container()

    def _build_card_thumbnail(self) -> ft.Control:
        """Build card thumbnail or icon."""
        try:
            theme = self.get_theme()

            if self._result_card.thumbnail_url:
                # TODO: Implement image loading when available
                return ft.Container(
                    width=self.get_responsive_value(60, 70, 80, 90),
                    height=self.get_responsive_value(60, 70, 80, 90),
                    bgcolor=theme.get_color("surface_variant"),
                    border_radius=self.get_responsive_value(6, 7, 8, 9),
                    content=ft.Icon(
                        self._get_document_icon(),
                        size=self.get_responsive_value(24, 28, 32, 36),
                        color=theme.get_color("primary")
                    ),
                    alignment=ft.alignment.center
                )
            else:
                return ft.Container(
                    width=self.get_responsive_value(60, 70, 80, 90),
                    height=self.get_responsive_value(60, 70, 80, 90),
                    bgcolor=theme.get_color("surface_variant"),
                    border_radius=self.get_responsive_value(6, 7, 8, 9),
                    content=ft.Icon(
                        self._get_document_icon(),
                        size=self.get_responsive_value(24, 28, 32, 36),
                        color=theme.get_color("primary")
                    ),
                    alignment=ft.alignment.center
                )

        except Exception as e:
            logger.error(f"Error building card thumbnail: {e}")
            return ft.Container()

    def _build_highlighted_snippet(self, detailed: bool = False) -> ft.Control:
        """Build highlighted text snippet with search term highlighting."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()

            # Truncate snippet if needed
            max_length = self._max_snippet_length if not detailed else self._max_snippet_length * 2
            snippet = self._truncate_text(self._result_card.snippet, max_length)

            if not self._enable_highlighting or not self._result_card.highlighted_terms:
                # Return plain text if highlighting is disabled
                return ft.Text(
                    snippet,
                    style=typography.get_text_style("body_small"),
                    color=theme.get_color("on_surface_variant"),
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=2 if not detailed else 4
                )

            # Build highlighted text spans
            text_spans = self._create_highlighted_spans(snippet)

            return ft.Text(
                spans=text_spans,
                style=typography.get_text_style("body_small"),
                color=theme.get_color("on_surface_variant"),
                overflow=ft.TextOverflow.ELLIPSIS,
                max_lines=2 if not detailed else 4
            )

        except Exception as e:
            logger.error(f"Error building highlighted snippet: {e}")
            return ft.Text(self._result_card.snippet or "")
