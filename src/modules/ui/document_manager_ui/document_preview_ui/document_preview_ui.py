"""
Module: document_preview_ui
Description: Document preview panel with search highlighting and metadata display for document manager.
            Provides compact, efficient document preview functionality optimized for document management
            workflows with responsive design, theme integration, and advanced viewing capabilities.
Phase: 3
Location: /src/modules/ui/document_manager_ui/document_preview_ui/document_preview_ui.py
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


class PreviewMode(Enum):
    """Document preview display modes for document manager."""
    CONTENT = "content"
    METADATA = "metadata"
    SEARCH_RESULTS = "search_results"


class PreviewState(Enum):
    """Document preview states."""
    IDLE = "idle"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"
    EMPTY = "empty"


@dataclass
class DocumentManagerPreviewConfig:
    """Configuration for document manager preview panel."""
    max_preview_size: int = 10 * 1024 * 1024  # 10MB for quick preview
    max_content_lines: int = 1000  # Limit content lines for performance
    enable_search_highlighting: bool = True
    enable_metadata_display: bool = True
    enable_quick_actions: bool = True
    default_preview_height: int = 400
    compact_mode: bool = True
    auto_refresh: bool = False
    search_context_lines: int = 3  # Lines before/after search match


@dataclass
class DocumentMetadata:
    """Document metadata structure for preview."""
    filename: str = ""
    file_size: int = 0
    file_type: str = ""
    created_date: str = ""
    modified_date: str = ""
    processing_status: str = ""
    quality_score: float = 0.0
    chunk_count: int = 0
    index_status: str = ""
    extraction_confidence: float = 0.0
    custom_tags: List[str] = field(default_factory=list)


class DocumentManagerPreviewUI(ThemeAwareUserControl):
    """
    Document preview panel optimized for document manager interface.
    
    Features:
    - Compact preview panel design
    - Search term highlighting with navigation
    - Metadata display with processing stats
    - Quick document actions
    - Responsive layout for side panel usage
    - Theme-aware styling
    - Performance optimized for quick browsing
    """
    
    def __init__(
        self,
        config: Optional[DocumentManagerPreviewConfig] = None,
        on_document_action: Optional[Callable[[str, Path], None]] = None,
        on_search_highlight: Optional[Callable[[str, List[Tuple[int, int]]], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or DocumentManagerPreviewConfig()
        self._logger = get_logger(__name__)
        
        # Callbacks
        self._on_document_action = on_document_action
        self._on_search_highlight = on_search_highlight
        
        # State
        self._current_document: Optional[Path] = None
        self._current_content: str = ""
        self._current_metadata: DocumentMetadata = DocumentMetadata()
        self._preview_mode = PreviewMode.CONTENT
        self._preview_state = PreviewState.IDLE
        self._search_term = ""
        self._search_results: List[Tuple[int, int]] = []
        self._current_search_index = 0
        
        # UI Components
        self._header_container: Optional[ft.Container] = None
        self._content_container: Optional[ft.Container] = None
        self._metadata_container: Optional[ft.Container] = None
        self._actions_container: Optional[ft.Container] = None
        self._search_info_container: Optional[ft.Container] = None
        
        # Controls
        self._mode_tabs: Optional[ft.Tabs] = None
        self._content_text: Optional[ft.Text] = None
        self._metadata_column: Optional[ft.Column] = None
        self._loading_indicator: Optional[ft.ProgressRing] = None
        self._search_navigation: Optional[ft.Row] = None
    
    def build(self) -> ft.Control:
        """Build the document manager preview UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_header(),
                    ft.Divider(height=1, color=palette.borders),
                    self._create_content_area(),
                    self._create_actions_bar()
                ],
                spacing=0,
                expand=True
            ),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.borders),
            border_radius=self.get_responsive_size(8),
            padding=0,
            expand=True,
            width=self.get_breakpoint_value(
                mobile=300, tablet=350, desktop=400, large=450
            )
        )
    
    def _create_header(self) -> ft.Control:
        """Create the preview panel header with mode tabs."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Mode tabs
        self._mode_tabs = ft.Tabs(
            selected_index=0,
            on_change=self._on_mode_change,
            tabs=[
                ft.Tab(
                    text="Content",
                    icon=ft.Icons.DESCRIPTION
                ),
                ft.Tab(
                    text="Metadata",
                    icon=ft.Icons.INFO
                ),
                ft.Tab(
                    text="Search",
                    icon=ft.Icons.SEARCH
                )
            ],
            expand=True
        )
        
        self._header_container = ft.Container(
            content=self._mode_tabs,
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(
                horizontal=spacing.sm,
                vertical=spacing.xs
            ),
            border_radius=ft.border_radius.only(
                top_left=self.get_responsive_size(8),
                top_right=self.get_responsive_size(8)
            )
        )
        
        return self._header_container

    def _create_content_area(self) -> ft.Control:
        """Create the main content display area."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Loading indicator
        self._loading_indicator = ft.ProgressRing(
            width=self.get_responsive_size(32),
            height=self.get_responsive_size(32),
            stroke_width=3,
            color=palette.primary
        )

        # Content text display
        self._content_text = ft.Text(
            value="Select a document to preview",
            style=self.get_text_style("body2"),
            color=palette.text_secondary,
            selectable=True,
            expand=True,
            max_lines=self._config.max_content_lines
        )

        # Metadata display
        self._metadata_column = ft.Column(
            controls=[],
            spacing=spacing.sm,
            scroll=ft.ScrollMode.AUTO
        )

        # Search info display
        self._search_info_container = ft.Container(
            content=ft.Text(
                "No search results",
                style=self.get_text_style("caption"),
                color=palette.text_secondary
            ),
            visible=False,
            padding=spacing.sm,
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_size(4)
        )

        # Search navigation
        self._search_navigation = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.KEYBOARD_ARROW_UP,
                    tooltip="Previous Result",
                    on_click=self._on_search_previous,
                    icon_size=self.get_responsive_size(16),
                    icon_color=palette.primary
                ),
                ft.Text(
                    "0/0",
                    style=self.get_text_style("caption"),
                    color=palette.text_secondary
                ),
                ft.IconButton(
                    icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                    tooltip="Next Result",
                    on_click=self._on_search_next,
                    icon_size=self.get_responsive_size(16),
                    icon_color=palette.primary
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=spacing.xs,
            visible=False
        )

        # Content container with tabs
        content_stack = ft.Stack(
            controls=[
                # Content view
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=self._loading_indicator,
                                alignment=ft.alignment.center,
                                visible=False,
                                height=100
                            ),
                            ft.Container(
                                content=self._content_text,
                                padding=spacing.sm,
                                expand=True
                            )
                        ],
                        expand=True
                    ),
                    visible=True
                ),
                # Metadata view
                ft.Container(
                    content=ft.Column(
                        controls=[
                            self._metadata_column
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True
                    ),
                    padding=spacing.sm,
                    visible=False
                ),
                # Search view
                ft.Container(
                    content=ft.Column(
                        controls=[
                            self._search_info_container,
                            self._search_navigation,
                            ft.Container(
                                content=self._content_text,
                                padding=spacing.sm,
                                expand=True
                            )
                        ],
                        expand=True
                    ),
                    visible=False
                )
            ],
            expand=True
        )

        self._content_container = ft.Container(
            content=content_stack,
            expand=True,
            height=self._config.default_preview_height
        )

        return self._content_container

    def _create_actions_bar(self) -> ft.Control:
        """Create the quick actions bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Quick action buttons
        open_btn = ft.IconButton(
            icon=ft.Icons.OPEN_IN_NEW,
            tooltip="Open in Full Viewer",
            on_click=lambda e: self._handle_action("open"),
            icon_size=self.get_responsive_size(16),
            icon_color=palette.primary
        )

        edit_btn = ft.IconButton(
            icon=ft.Icons.EDIT,
            tooltip="Edit Metadata",
            on_click=lambda e: self._handle_action("edit"),
            icon_size=self.get_responsive_size(16),
            icon_color=palette.primary
        )

        reprocess_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Reprocess Document",
            on_click=lambda e: self._handle_action("reprocess"),
            icon_size=self.get_responsive_size(16),
            icon_color=palette.primary
        )

        remove_btn = ft.IconButton(
            icon=ft.Icons.DELETE,
            tooltip="Remove Document",
            on_click=lambda e: self._handle_action("remove"),
            icon_size=self.get_responsive_size(16),
            icon_color=palette.error
        )

        self._actions_container = ft.Container(
            content=ft.Row(
                controls=[
                    open_btn,
                    edit_btn,
                    reprocess_btn,
                    ft.VerticalDivider(width=1, color=palette.borders),
                    remove_btn
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                spacing=spacing.xs
            ),
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(
                horizontal=spacing.sm,
                vertical=spacing.xs
            ),
            border_radius=ft.border_radius.only(
                bottom_left=self.get_responsive_size(8),
                bottom_right=self.get_responsive_size(8)
            ),
            visible=False  # Hidden until document is loaded
        )

        return self._actions_container

    # Event Handlers
    def _on_mode_change(self, e):
        """Handle preview mode tab change."""
        try:
            mode_index = e.control.selected_index
            if mode_index == 0:
                self._preview_mode = PreviewMode.CONTENT
            elif mode_index == 1:
                self._preview_mode = PreviewMode.METADATA
            elif mode_index == 2:
                self._preview_mode = PreviewMode.SEARCH_RESULTS

            self._update_content_visibility()
        except Exception as ex:
            self._logger.error(f"Error changing preview mode: {ex}")

    def _on_search_previous(self, e):
        """Handle search previous button click."""
        if self._search_results:
            self._current_search_index = (self._current_search_index - 1) % len(self._search_results)
            self._update_search_navigation()
            self._scroll_to_search_result()

    def _on_search_next(self, e):
        """Handle search next button click."""
        if self._search_results:
            self._current_search_index = (self._current_search_index + 1) % len(self._search_results)
            self._update_search_navigation()
            self._scroll_to_search_result()

    def _handle_action(self, action: str):
        """Handle quick action button clicks."""
        if self._current_document and self._on_document_action:
            self._on_document_action(action, self._current_document)

    # Search Functionality
    def set_search_term(self, search_term: str):
        """
        Set search term and highlight matches in content.

        Args:
            search_term: Term to search for and highlight
        """
        self._search_term = search_term
        if search_term and self._current_content:
            self._perform_search()
        else:
            self._clear_search_results()

    def _perform_search(self):
        """Perform search in current document content."""
        if not self._search_term or not self._current_content:
            self._clear_search_results()
            return

        # Find all occurrences (case-insensitive)
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
        self._update_search_display()

        # Notify callback
        if self._on_search_highlight:
            self._on_search_highlight(self._search_term, self._search_results)

    def _clear_search_results(self):
        """Clear search results and highlighting."""
        self._search_results = []
        self._current_search_index = 0
        self._search_term = ""
        self._update_search_display()

    def _update_search_display(self):
        """Update search results display and navigation."""
        if not self._search_info_container or not self._search_navigation:
            return

        if self._search_results:
            # Update search info
            result_count = len(self._search_results)
            current_pos = self._current_search_index + 1

            self._search_info_container.content.value = (
                f"Found {result_count} matches for '{self._search_term}'"
            )
            self._search_info_container.visible = True

            # Update navigation
            nav_controls = self._search_navigation.controls
            nav_controls[1].value = f"{current_pos}/{result_count}"
            self._search_navigation.visible = True

            # Highlight content
            self._highlight_search_content()
        else:
            self._search_info_container.content.value = (
                f"No matches found for '{self._search_term}'" if self._search_term
                else "No search results"
            )
            self._search_info_container.visible = bool(self._search_term)
            self._search_navigation.visible = False

        self.update()

    def _highlight_search_content(self):
        """Apply search highlighting to content display."""
        if not self._search_results or not self._content_text:
            return

        # For now, just show the content with search context
        # In a full implementation, this would use rich text highlighting
        if self._config.compact_mode:
            self._show_search_context()
        else:
            # Show full content with highlighting markers
            highlighted_content = self._add_highlight_markers()
            self._content_text.value = highlighted_content

    def _show_search_context(self):
        """Show search results with context lines."""
        if not self._search_results:
            return

        lines = self._current_content.split('\n')
        context_lines = self._config.search_context_lines

        # Build context display
        context_parts = []
        for i, (start_pos, end_pos) in enumerate(self._search_results[:10]):  # Limit to first 10 results
            # Find line containing the match
            char_count = 0
            match_line = 0
            for line_idx, line in enumerate(lines):
                if char_count + len(line) >= start_pos:
                    match_line = line_idx
                    break
                char_count += len(line) + 1  # +1 for newline

            # Get context
            start_line = max(0, match_line - context_lines)
            end_line = min(len(lines), match_line + context_lines + 1)

            context = lines[start_line:end_line]

            # Mark current result
            if i == self._current_search_index:
                context_parts.append(f">>> Result {i+1}/{len(self._search_results)} <<<")
            else:
                context_parts.append(f"--- Result {i+1} ---")

            context_parts.extend(context)
            context_parts.append("")

        self._content_text.value = '\n'.join(context_parts)

    def _add_highlight_markers(self) -> str:
        """Add text markers around search matches."""
        if not self._search_results:
            return self._current_content

        # Add markers in reverse order to maintain positions
        content = self._current_content
        for start_pos, end_pos in reversed(self._search_results):
            content = (
                content[:start_pos] +
                f">>>{content[start_pos:end_pos]}<<<" +
                content[end_pos:]
            )

        return content

    def _update_search_navigation(self):
        """Update search navigation display."""
        if self._search_navigation and self._search_results:
            nav_controls = self._search_navigation.controls
            current_pos = self._current_search_index + 1
            total_results = len(self._search_results)
            nav_controls[1].value = f"{current_pos}/{total_results}"
            self.update()

    def _scroll_to_search_result(self):
        """Scroll to current search result."""
        # In a full implementation, this would scroll the content view
        # to the current search result position
        if self._config.compact_mode:
            self._show_search_context()
        self.update()

    # Metadata Display
    def _update_metadata_display(self):
        """Update the metadata display panel."""
        if not self._metadata_column:
            return

        palette = self.get_palette()
        spacing = self.get_spacing()

        # Clear existing metadata
        self._metadata_column.controls.clear()

        # Document Information Section
        self._metadata_column.controls.append(
            self._create_metadata_section(
                "Document Information",
                [
                    ("Filename", self._current_metadata.filename),
                    ("File Size", self._format_file_size(self._current_metadata.file_size)),
                    ("File Type", self._current_metadata.file_type),
                    ("Created", self._current_metadata.created_date),
                    ("Modified", self._current_metadata.modified_date)
                ]
            )
        )

        # Processing Status Section
        status_color = self._get_status_color(self._current_metadata.processing_status)
        self._metadata_column.controls.append(
            self._create_metadata_section(
                "Processing Status",
                [
                    ("Status", self._current_metadata.processing_status, status_color),
                    ("Quality Score", f"{self._current_metadata.quality_score:.1%}"),
                    ("Extraction Confidence", f"{self._current_metadata.extraction_confidence:.1%}"),
                    ("Chunk Count", str(self._current_metadata.chunk_count)),
                    ("Index Status", self._current_metadata.index_status)
                ]
            )
        )

        # Custom Tags Section
        if self._current_metadata.custom_tags:
            self._metadata_column.controls.append(
                self._create_tags_section("Custom Tags", self._current_metadata.custom_tags)
            )

        self.update()

    def _create_metadata_section(self, title: str, items: List[Tuple[str, str, Optional[str]]]) -> ft.Control:
        """Create a metadata section with title and items."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Section title
        title_text = ft.Text(
            title,
            style=self.get_text_style("subtitle2"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_600
        )

        # Section items
        item_controls = []
        for item in items:
            if len(item) == 2:
                key, value = item
                text_color = palette.text_secondary
            else:
                key, value, text_color = item

            item_row = ft.Row(
                controls=[
                    ft.Text(
                        f"{key}:",
                        style=self.get_text_style("body2"),
                        color=palette.text_secondary,
                        width=self.get_responsive_size(100)
                    ),
                    ft.Text(
                        str(value),
                        style=self.get_text_style("body2"),
                        color=text_color or palette.text_primary,
                        expand=True
                    )
                ],
                spacing=spacing.sm
            )
            item_controls.append(item_row)

        return ft.Container(
            content=ft.Column(
                controls=[title_text] + item_controls,
                spacing=spacing.xs
            ),
            padding=spacing.sm,
            margin=ft.margin.only(bottom=spacing.sm),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_size(6)
        )

    def _create_tags_section(self, title: str, tags: List[str]) -> ft.Control:
        """Create a tags section with chips."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Section title
        title_text = ft.Text(
            title,
            style=self.get_text_style("subtitle2"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_600
        )

        # Tag chips
        tag_chips = []
        for tag in tags:
            chip = ft.Container(
                content=ft.Text(
                    tag,
                    style=self.get_text_style("caption"),
                    color=palette.text_primary
                ),
                padding=ft.padding.symmetric(
                    horizontal=spacing.sm,
                    vertical=spacing.xs
                ),
                bgcolor=palette.primary,
                border_radius=self.get_responsive_size(12)
            )
            tag_chips.append(chip)

        # Wrap tags in rows
        tag_rows = []
        current_row = []
        for chip in tag_chips:
            current_row.append(chip)
            if len(current_row) >= 3:  # Max 3 tags per row
                tag_rows.append(
                    ft.Row(
                        controls=current_row,
                        spacing=spacing.xs,
                        wrap=True
                    )
                )
                current_row = []

        if current_row:
            tag_rows.append(
                ft.Row(
                    controls=current_row,
                    spacing=spacing.xs,
                    wrap=True
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[title_text] + tag_rows,
                spacing=spacing.xs
            ),
            padding=spacing.sm,
            margin=ft.margin.only(bottom=spacing.sm),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_size(6)
        )

    def _get_status_color(self, status: str) -> str:
        """Get color for processing status."""
        palette = self.get_palette()

        status_colors = {
            "completed": palette.success,
            "processing": palette.info,
            "failed": palette.error,
            "pending": palette.warning,
            "indexed": palette.success,
            "error": palette.error
        }

        return status_colors.get(status.lower(), palette.text_primary)

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

    # Document Loading and Display
    async def load_document(self, file_path: Union[str, Path], metadata: Optional[DocumentMetadata] = None) -> bool:
        """
        Load a document for preview.

        Args:
            file_path: Path to the document file
            metadata: Optional document metadata

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                self._set_error_state(f"File not found: {file_path}")
                return False

            if file_path.stat().st_size > self._config.max_preview_size:
                self._set_error_state(f"File too large for preview: {file_path.stat().st_size} bytes")
                return False

            self._set_loading_state()

            # Load content
            content = await self._load_file_content(file_path)

            # Update state
            self._current_document = file_path
            self._current_content = content
            self._current_metadata = metadata or self._create_default_metadata(file_path)

            # Update UI
            self._set_loaded_state()
            self._update_content_display()
            self._update_metadata_display()

            return True

        except Exception as e:
            self._logger.error(f"Error loading document: {e}")
            self._set_error_state(str(e))
            return False

    async def _load_file_content(self, file_path: Path) -> str:
        """Load file content with format-specific handling."""
        try:
            file_extension = file_path.suffix.lower()

            # Text-based formats
            if file_extension in ['.txt', '.md', '.html', '.css', '.js', '.py', '.json', '.xml']:
                return await self._load_text_file(file_path)

            # Binary formats that need special handling
            elif file_extension == '.pdf':
                return await self._load_pdf_preview(file_path)

            elif file_extension == '.docx':
                return await self._load_docx_preview(file_path)

            else:
                # Try as text file
                return await self._load_text_file(file_path)

        except Exception as e:
            self._logger.error(f"Error loading file content: {e}")
            return f"Error loading file: {e}"

    async def _load_text_file(self, file_path: Path) -> str:
        """Load text file with encoding detection."""
        try:
            # Try UTF-8 first
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Limit content for performance
            if len(content.split('\n')) > self._config.max_content_lines:
                lines = content.split('\n')[:self._config.max_content_lines]
                content = '\n'.join(lines) + f"\n\n... (truncated, showing first {self._config.max_content_lines} lines)"

            return content

        except UnicodeDecodeError:
            # Fallback to latin-1
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file: {e}"

    async def _load_pdf_preview(self, file_path: Path) -> str:
        """Load PDF preview (placeholder implementation)."""
        # In a full implementation, this would extract text from PDF
        return f"PDF Document: {file_path.name}\n\nPDF preview not yet implemented.\nFile size: {self._format_file_size(file_path.stat().st_size)}"

    async def _load_docx_preview(self, file_path: Path) -> str:
        """Load DOCX preview (placeholder implementation)."""
        # In a full implementation, this would extract text from DOCX
        return f"Word Document: {file_path.name}\n\nDOCX preview not yet implemented.\nFile size: {self._format_file_size(file_path.stat().st_size)}"

    def _create_default_metadata(self, file_path: Path) -> DocumentMetadata:
        """Create default metadata for a file."""
        import datetime

        stat = file_path.stat()

        return DocumentMetadata(
            filename=file_path.name,
            file_size=stat.st_size,
            file_type=file_path.suffix.upper().lstrip('.') or 'Unknown',
            created_date=datetime.datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
            modified_date=datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            processing_status="Not Processed",
            quality_score=0.0,
            chunk_count=0,
            index_status="Not Indexed",
            extraction_confidence=0.0,
            custom_tags=[]
        )

    def _update_content_display(self):
        """Update the content display based on current mode."""
        if not self._content_text:
            return

        if self._preview_mode == PreviewMode.CONTENT:
            self._content_text.value = self._current_content
            self._content_text.color = self.get_palette().text_primary
        elif self._preview_mode == PreviewMode.SEARCH_RESULTS and self._search_results:
            self._highlight_search_content()

        self.update()

    def _update_content_visibility(self):
        """Update visibility of content containers based on mode."""
        if not self._content_container:
            return

        stack_controls = self._content_container.content.controls

        # Hide all views
        for control in stack_controls:
            control.visible = False

        # Show appropriate view
        if self._preview_mode == PreviewMode.CONTENT:
            stack_controls[0].visible = True  # Content view
        elif self._preview_mode == PreviewMode.METADATA:
            stack_controls[1].visible = True  # Metadata view
        elif self._preview_mode == PreviewMode.SEARCH_RESULTS:
            stack_controls[2].visible = True  # Search view

        self.update()

    # State Management
    def _set_loading_state(self):
        """Set UI to loading state."""
        self._preview_state = PreviewState.LOADING
        if self._loading_indicator:
            self._loading_indicator.parent.visible = True
        if self._content_text:
            self._content_text.value = "Loading document..."
            self._content_text.color = self.get_palette().text_secondary
        if self._actions_container:
            self._actions_container.visible = False
        self.update()

    def _set_loaded_state(self):
        """Set UI to loaded state."""
        self._preview_state = PreviewState.LOADED
        if self._loading_indicator:
            self._loading_indicator.parent.visible = False
        if self._actions_container:
            self._actions_container.visible = True
        self.update()

    def _set_error_state(self, error_message: str):
        """Set UI to error state."""
        self._preview_state = PreviewState.ERROR
        if self._loading_indicator:
            self._loading_indicator.parent.visible = False
        if self._content_text:
            self._content_text.value = f"Error: {error_message}"
            self._content_text.color = self.get_palette().error
        if self._actions_container:
            self._actions_container.visible = False
        self.update()

    # Public API
    def get_current_document(self) -> Optional[Path]:
        """Get the currently loaded document path."""
        return self._current_document

    def get_current_metadata(self) -> DocumentMetadata:
        """Get the current document metadata."""
        return self._current_metadata

    def update_metadata(self, metadata: DocumentMetadata):
        """Update document metadata and refresh display."""
        self._current_metadata = metadata
        self._update_metadata_display()

    def clear_preview(self):
        """Clear the current preview."""
        self._current_document = None
        self._current_content = ""
        self._current_metadata = DocumentMetadata()
        self._clear_search_results()

        if self._content_text:
            self._content_text.value = "Select a document to preview"
            self._content_text.color = self.get_palette().text_secondary

        if self._actions_container:
            self._actions_container.visible = False

        self._preview_state = PreviewState.IDLE
        self.update()

    def is_document_loaded(self) -> bool:
        """Check if a document is currently loaded."""
        return self._current_document is not None and self._preview_state == PreviewState.LOADED
