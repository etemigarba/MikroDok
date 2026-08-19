"""
Module: document_preview_ui
Description: Displays document content with syntax highlighting and formatting preservation.
            Provides comprehensive document preview functionality with multi-format support,
            responsive design, theme integration, and advanced viewing capabilities including
            zoom controls, search highlighting, and metadata display.
Phase: 3
Location: /src/modules/ui/document_viewer_ui/document_preview_ui/document_preview_ui.py
"""

# Standard library imports
import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_ingestion_lg.format_detector_lg.format_detector_lg import (
    FormatDetector, DocumentFormat
)


class PreviewMode(Enum):
    """Document preview display modes."""
    TEXT = "text"
    FORMATTED = "formatted"
    RAW = "raw"
    SYNTAX_HIGHLIGHTED = "syntax_highlighted"
    METADATA = "metadata"


class PreviewState(Enum):
    """Document preview states."""
    IDLE = "idle"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"
    EMPTY = "empty"


@dataclass
class DocumentViewerConfig:
    """Configuration for document viewer."""
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    supported_formats: List[str] = field(default_factory=lambda: [
        'pdf', 'docx', 'txt', 'html', 'md', 'py', 'js', 'css', 'json', 'xml'
    ])
    enable_syntax_highlighting: bool = True
    enable_line_numbers: bool = True
    enable_word_wrap: bool = True
    default_zoom_level: float = 1.0
    max_zoom_level: float = 3.0
    min_zoom_level: float = 0.5
    search_highlight_color: str = "yellow"
    enable_metadata_display: bool = True


class SyntaxHighlighter:
    """Handles syntax highlighting for different file types."""
    
    def __init__(self):
        self._logger = get_logger(__name__)
        self._language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.xml': 'xml',
            '.md': 'markdown',
            '.sql': 'sql',
            '.yaml': 'yaml',
            '.yml': 'yaml'
        }
    
    def detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        suffix = file_path.suffix.lower()
        return self._language_map.get(suffix, 'text')
    
    def highlight_content(self, content: str, language: str) -> str:
        """Apply syntax highlighting to content."""
        # For now, return content as-is
        # In a full implementation, this would use a syntax highlighting library
        return content


class DocumentRenderer:
    """Renders different document formats for preview."""
    
    def __init__(self, config: DocumentViewerConfig):
        self._config = config
        self._logger = get_logger(__name__)
        self._format_detector = FormatDetector()
    
    async def render_document(self, file_path: Path, mode: PreviewMode) -> Tuple[str, Dict[str, Any]]:
        """Render document content based on format and mode."""
        try:
            # Detect format
            format_result = self._format_detector.detect_format(file_path)
            
            # Read file content
            content = await self._read_file_content(file_path)
            metadata = {
                'format': format_result.format.value,
                'size': file_path.stat().st_size,
                'path': str(file_path)
            }
            
            # Apply rendering based on mode
            if mode == PreviewMode.RAW:
                return content, metadata
            elif mode == PreviewMode.SYNTAX_HIGHLIGHTED:
                highlighter = SyntaxHighlighter()
                language = highlighter.detect_language(file_path)
                highlighted = highlighter.highlight_content(content, language)
                return highlighted, metadata
            else:
                return content, metadata
                
        except Exception as e:
            self._logger.error(f"Error rendering document: {e}")
            raise
    
    async def _read_file_content(self, file_path: Path) -> str:
        """Read file content with encoding detection."""
        try:
            # Try UTF-8 first
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                self._logger.warning(f"Failed to read file with latin-1: {e}")
                return f"Error reading file: {e}"


class DocumentPreviewUI(ThemeAwareUserControl):
    """
    Document preview UI component with comprehensive viewing capabilities.
    
    Features:
    - Multi-format document support (PDF, DOCX, TXT, HTML, MD, code files)
    - Syntax highlighting for code files
    - Responsive design with theme integration
    - Zoom controls and navigation
    - Search functionality with highlighting
    - Metadata display
    - Error handling and loading states
    """
    
    def __init__(
        self,
        config: Optional[DocumentViewerConfig] = None,
        on_document_loaded: Optional[Callable[[Path, Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or DocumentViewerConfig()
        self._logger = get_logger(__name__)
        
        # Callbacks
        self._on_document_loaded = on_document_loaded
        self._on_error = on_error
        
        # State
        self._current_document: Optional[Path] = None
        self._current_content: str = ""
        self._current_metadata: Dict[str, Any] = {}
        self._preview_mode = PreviewMode.FORMATTED
        self._preview_state = PreviewState.IDLE
        self._zoom_level = self._config.default_zoom_level
        self._search_term = ""
        self._search_results: List[Tuple[int, int]] = []
        self._current_search_index = 0
        
        # Components
        self._renderer = DocumentRenderer(self._config)
        self._toolbar_container: Optional[ft.Container] = None
        self._content_container: Optional[ft.Container] = None
        self._status_bar: Optional[ft.Container] = None
        self._search_bar: Optional[ft.Container] = None
        self._content_display: Optional[ft.Container] = None
        
        # Controls
        self._zoom_slider: Optional[ft.Slider] = None
        self._mode_dropdown: Optional[ft.Dropdown] = None
        self._search_field: Optional[ft.TextField] = None
        self._content_text: Optional[ft.Text] = None
        self._loading_indicator: Optional[ft.ProgressRing] = None
    
    def build(self) -> ft.Control:
        """Build the document preview UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_toolbar(),
                    self._create_search_bar(),
                    ft.Divider(
                        height=1,
                        color=palette.borders
                    ),
                    self._create_content_area(),
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
    
    def _create_toolbar(self) -> ft.Control:
        """Create the document preview toolbar."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Mode selection dropdown
        self._mode_dropdown = ft.Dropdown(
            label="View Mode",
            options=[
                ft.dropdown.Option("text", "Text"),
                ft.dropdown.Option("formatted", "Formatted"),
                ft.dropdown.Option("raw", "Raw"),
                ft.dropdown.Option("syntax_highlighted", "Syntax Highlighted"),
                ft.dropdown.Option("metadata", "Metadata")
            ],
            value="formatted",
            on_change=self._on_mode_change,
            width=self.get_breakpoint_value(
                mobile=120, tablet=150, desktop=180, large=200
            ),
            text_style=self.get_text_style("body2"),
            bgcolor=palette.surface_variant,
            border_color=palette.borders
        )
        
        # Zoom controls
        self._zoom_slider = ft.Slider(
            min=self._config.min_zoom_level,
            max=self._config.max_zoom_level,
            value=self._config.default_zoom_level,
            divisions=10,
            label="Zoom: {value}x",
            on_change=self._on_zoom_change,
            width=self.get_breakpoint_value(
                mobile=100, tablet=120, desktop=150, large=180
            )
        )
        
        # Action buttons
        refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Refresh Document",
            on_click=self._on_refresh_click,
            icon_color=palette.primary,
            bgcolor=palette.surface_variant
        )
        
        search_btn = ft.IconButton(
            icon=ft.Icons.SEARCH,
            tooltip="Toggle Search",
            on_click=self._on_search_toggle,
            icon_color=palette.primary,
            bgcolor=palette.surface_variant
        )
        
        self._toolbar_container = ft.Container(
            content=ft.Row(
                controls=[
                    self._mode_dropdown,
                    ft.VerticalDivider(width=1, color=palette.borders),
                    ft.Text("Zoom:", style=self.get_text_style("body2")),
                    self._zoom_slider,
                    ft.VerticalDivider(width=1, color=palette.borders),
                    refresh_btn,
                    search_btn
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.sm
            ),
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            border_radius=ft.border_radius.only(
                top_left=self.get_responsive_size(8),
                top_right=self.get_responsive_size(8)
            )
        )
        
        return self._toolbar_container

    def _create_search_bar(self) -> ft.Control:
        """Create the search bar (initially hidden)."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._search_field = ft.TextField(
            label="Search in document",
            hint_text="Enter search term...",
            on_change=self._on_search_change,
            on_submit=self._on_search_submit,
            width=self.get_breakpoint_value(
                mobile=200, tablet=300, desktop=400, large=500
            ),
            text_style=self.get_text_style("body2"),
            bgcolor=palette.surface_variant,
            border_color=palette.borders
        )

        search_prev_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            tooltip="Previous Result",
            on_click=self._on_search_previous,
            icon_color=palette.primary,
            bgcolor=palette.surface_variant
        )

        search_next_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
            tooltip="Next Result",
            on_click=self._on_search_next,
            icon_color=palette.primary,
            bgcolor=palette.surface_variant
        )

        close_search_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            tooltip="Close Search",
            on_click=self._on_search_close,
            icon_color=palette.error,
            bgcolor=palette.surface_variant
        )

        self._search_bar = ft.Container(
            content=ft.Row(
                controls=[
                    self._search_field,
                    search_prev_btn,
                    search_next_btn,
                    close_search_btn
                ],
                spacing=spacing.sm,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            visible=False
        )

        return self._search_bar

    def _create_content_area(self) -> ft.Control:
        """Create the main content display area."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Loading indicator
        self._loading_indicator = ft.ProgressRing(
            width=self.get_responsive_size(40),
            height=self.get_responsive_size(40),
            stroke_width=4,
            color=palette.primary
        )

        # Content text display
        self._content_text = ft.Text(
            value="No document loaded",
            style=self.get_text_style("body1"),
            color=palette.text_secondary,
            selectable=True,
            expand=True
        )

        # Content display container
        self._content_display = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=self._loading_indicator,
                        alignment=ft.alignment.center,
                        visible=False
                    ),
                    ft.Container(
                        content=self._content_text,
                        padding=spacing.md,
                        expand=True
                    )
                ],
                expand=True
            ),
            bgcolor=palette.surface,
            expand=True
        )

        # Scrollable content area
        self._content_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=self._content_display,
                        expand=True
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True
            ),
            expand=True,
            padding=0
        )

        return self._content_container

    def _create_status_bar(self) -> ft.Control:
        """Create the status bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._status_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "Ready",
                        style=self.get_text_style("caption"),
                        color=palette.text_secondary
                    ),
                    ft.Text(
                        "",
                        style=self.get_text_style("caption"),
                        color=palette.text_secondary
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.xs
            ),
            border_radius=ft.border_radius.only(
                bottom_left=self.get_responsive_size(8),
                bottom_right=self.get_responsive_size(8)
            )
        )

        return self._status_bar

    # Event Handlers
    def _on_mode_change(self, e):
        """Handle preview mode change."""
        try:
            new_mode = PreviewMode(e.control.value)
            if new_mode != self._preview_mode:
                self._preview_mode = new_mode
                if self._current_document:
                    asyncio.create_task(self._reload_document())
        except Exception as ex:
            self._logger.error(f"Error changing preview mode: {ex}")

    def _on_zoom_change(self, e):
        """Handle zoom level change."""
        try:
            self._zoom_level = e.control.value
            self._apply_zoom()
        except Exception as ex:
            self._logger.error(f"Error changing zoom: {ex}")

    def _on_refresh_click(self, e):
        """Handle refresh button click."""
        if self._current_document:
            asyncio.create_task(self._reload_document())

    def _on_search_toggle(self, e):
        """Handle search toggle button click."""
        if self._search_bar:
            self._search_bar.visible = not self._search_bar.visible
            if self._search_bar.visible and self._search_field:
                self._search_field.focus()
            self.update()

    def _on_search_change(self, e):
        """Handle search field change."""
        self._search_term = e.control.value
        if self._search_term:
            self._perform_search()

    def _on_search_submit(self, e):
        """Handle search field submit."""
        if self._search_results:
            self._on_search_next(e)

    def _on_search_previous(self, e):
        """Handle search previous button click."""
        if self._search_results:
            self._current_search_index = (self._current_search_index - 1) % len(self._search_results)
            self._highlight_search_result()

    def _on_search_next(self, e):
        """Handle search next button click."""
        if self._search_results:
            self._current_search_index = (self._current_search_index + 1) % len(self._search_results)
            self._highlight_search_result()

    def _on_search_close(self, e):
        """Handle search close button click."""
        if self._search_bar:
            self._search_bar.visible = False
            self._search_term = ""
            self._search_results = []
            if self._search_field:
                self._search_field.value = ""
            self._clear_search_highlights()
            self.update()

    # Document Loading Methods
    async def load_document(self, file_path: Union[str, Path]) -> bool:
        """
        Load a document for preview.

        Args:
            file_path: Path to the document file

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                self._set_error_state(f"File not found: {file_path}")
                return False

            if file_path.stat().st_size > self._config.max_file_size:
                self._set_error_state(f"File too large: {file_path.stat().st_size} bytes")
                return False

            self._set_loading_state()

            # Render document
            content, metadata = await self._renderer.render_document(file_path, self._preview_mode)

            # Update state
            self._current_document = file_path
            self._current_content = content
            self._current_metadata = metadata

            # Update UI
            self._set_loaded_state()
            self._update_content_display()
            self._update_status_bar()

            # Notify callback
            if self._on_document_loaded:
                self._on_document_loaded(file_path, metadata)

            return True

        except Exception as e:
            self._logger.error(f"Error loading document: {e}")
            self._set_error_state(str(e))
            if self._on_error:
                self._on_error(str(e))
            return False

    async def _reload_document(self):
        """Reload the current document."""
        if self._current_document:
            await self.load_document(self._current_document)

    def _set_loading_state(self):
        """Set UI to loading state."""
        self._preview_state = PreviewState.LOADING
        if self._loading_indicator:
            self._loading_indicator.parent.visible = True
        if self._content_text:
            self._content_text.value = "Loading document..."
            self._content_text.color = self.get_palette().text_secondary
        self._update_status_bar("Loading...")
        self.update()

    def _set_loaded_state(self):
        """Set UI to loaded state."""
        self._preview_state = PreviewState.LOADED
        if self._loading_indicator:
            self._loading_indicator.parent.visible = False
        self.update()

    def _set_error_state(self, error_message: str):
        """Set UI to error state."""
        self._preview_state = PreviewState.ERROR
        if self._loading_indicator:
            self._loading_indicator.parent.visible = False
        if self._content_text:
            self._content_text.value = f"Error: {error_message}"
            self._content_text.color = self.get_palette().error
        self._update_status_bar(f"Error: {error_message}")
        self.update()

    def _update_content_display(self):
        """Update the content display with current document."""
        if not self._content_text:
            return

        if self._preview_mode == PreviewMode.METADATA:
            self._display_metadata()
        else:
            self._content_text.value = self._current_content
            self._content_text.color = self.get_palette().text_primary
            self._apply_zoom()

        self.update()

    def _display_metadata(self):
        """Display document metadata."""
        if not self._current_metadata or not self._content_text:
            return

        metadata_text = "Document Metadata:\n\n"
        for key, value in self._current_metadata.items():
            metadata_text += f"{key.title()}: {value}\n"

        self._content_text.value = metadata_text
        self._content_text.color = self.get_palette().text_primary

    def _apply_zoom(self):
        """Apply current zoom level to content."""
        if not self._content_text:
            return

        base_size = 14
        new_size = int(base_size * self._zoom_level)

        # Update text style with new size
        current_style = self._content_text.style or ft.TextStyle()
        current_style.size = new_size
        self._content_text.style = current_style

        self.update()

    def _update_status_bar(self, message: str = ""):
        """Update status bar with current information."""
        if not self._status_bar:
            return

        status_controls = self._status_bar.content.controls

        if message:
            status_controls[0].value = message
        else:
            if self._current_document:
                file_info = f"File: {self._current_document.name}"
                if self._current_metadata:
                    size = self._current_metadata.get('size', 0)
                    file_info += f" | Size: {self._format_file_size(size)}"
                    file_info += f" | Format: {self._current_metadata.get('format', 'Unknown')}"
                status_controls[0].value = file_info
            else:
                status_controls[0].value = "No document loaded"

        # Search results info
        if self._search_results:
            search_info = f"Search: {len(self._search_results)} results"
            if self._search_results:
                search_info += f" ({self._current_search_index + 1}/{len(self._search_results)})"
            status_controls[1].value = search_info
        else:
            status_controls[1].value = ""

        self.update()

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    # Search Functionality
    def _perform_search(self):
        """Perform search in current document content."""
        if not self._search_term or not self._current_content:
            self._search_results = []
            self._current_search_index = 0
            self._update_status_bar()
            return

        # Find all occurrences
        self._search_results = []
        content_lower = self._current_content.lower()
        search_lower = self._search_term.lower()

        start = 0
        while True:
            pos = content_lower.find(search_lower, start)
            if pos == -1:
                break
            self._search_results.append((pos, pos + len(self._search_term)))
            start = pos + 1

        self._current_search_index = 0
        if self._search_results:
            self._highlight_search_result()

        self._update_status_bar()

    def _highlight_search_result(self):
        """Highlight current search result."""
        if not self._search_results or not self._content_text:
            return

        # For now, just update status bar
        # In a full implementation, this would scroll to and highlight the result
        self._update_status_bar()

    def _clear_search_highlights(self):
        """Clear search highlights from content."""
        # In a full implementation, this would remove highlighting
        self._update_status_bar()

    # Public API Methods
    def get_current_document(self) -> Optional[Path]:
        """Get the currently loaded document path."""
        return self._current_document

    def get_current_content(self) -> str:
        """Get the current document content."""
        return self._current_content

    def get_current_metadata(self) -> Dict[str, Any]:
        """Get the current document metadata."""
        return self._current_metadata.copy()

    def get_preview_mode(self) -> PreviewMode:
        """Get the current preview mode."""
        return self._preview_mode

    def set_preview_mode(self, mode: PreviewMode):
        """Set the preview mode."""
        if self._mode_dropdown:
            self._mode_dropdown.value = mode.value
            self._on_mode_change(type('Event', (), {'control': self._mode_dropdown})())

    def get_zoom_level(self) -> float:
        """Get the current zoom level."""
        return self._zoom_level

    def set_zoom_level(self, zoom: float):
        """Set the zoom level."""
        zoom = max(self._config.min_zoom_level, min(self._config.max_zoom_level, zoom))
        if self._zoom_slider:
            self._zoom_slider.value = zoom
            self._on_zoom_change(type('Event', (), {'control': self._zoom_slider})())

    def clear_document(self):
        """Clear the current document."""
        self._current_document = None
        self._current_content = ""
        self._current_metadata = {}
        self._search_results = []
        self._search_term = ""

        if self._content_text:
            self._content_text.value = "No document loaded"
            self._content_text.color = self.get_palette().text_secondary

        if self._search_field:
            self._search_field.value = ""

        if self._search_bar:
            self._search_bar.visible = False

        self._preview_state = PreviewState.IDLE
        self._update_status_bar()

    def is_document_loaded(self) -> bool:
        """Check if a document is currently loaded."""
        return self._current_document is not None and self._preview_state == PreviewState.LOADED
