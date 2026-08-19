"""
Module: chunk_visualizer_ui
Description: Shows document chunks with boundaries, overlap regions, and token counts for RAG processing visualization.
            Provides comprehensive chunk visualization with interactive features, theme integration,
            responsive design, and real-time chunk analysis capabilities.
Phase: 3
Location: /src/modules/ui/document_viewer_ui/chunk_visualizer_ui/chunk_visualizer_ui.py
"""

# Standard library imports
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl
from src.modules.logic.document_chunking_lg.base_interfaces import (
    DocumentChunk, ChunkConfig, ChunkMetadata
)


class ChunkDisplayMode(Enum):
    """Display modes for chunk visualization."""
    OVERVIEW = "overview"
    DETAILED = "detailed"
    BOUNDARIES_ONLY = "boundaries_only"
    OVERLAP_FOCUS = "overlap_focus"
    TOKEN_ANALYSIS = "token_analysis"


class ChunkHighlightStyle(Enum):
    """Highlight styles for chunks."""
    BORDER = "border"
    BACKGROUND = "background"
    UNDERLINE = "underline"
    GRADIENT = "gradient"


@dataclass
class ChunkBoundary:
    """Represents a chunk boundary visualization."""
    start_position: int
    end_position: int
    chunk_id: str
    boundary_type: str = "semantic"
    confidence: float = 1.0
    is_overlap: bool = False


@dataclass
class OverlapRegion:
    """Represents an overlap region between chunks."""
    start_position: int
    end_position: int
    chunk_ids: List[str]
    overlap_type: str = "sentence"
    token_count: int = 0


@dataclass
class ChunkVisualizationConfig:
    """Configuration for chunk visualization."""
    display_mode: ChunkDisplayMode = ChunkDisplayMode.OVERVIEW
    highlight_style: ChunkHighlightStyle = ChunkHighlightStyle.BORDER
    show_token_counts: bool = True
    show_overlap_regions: bool = True
    show_chunk_boundaries: bool = True
    show_metadata: bool = True
    enable_interactive_selection: bool = True
    max_visible_chunks: int = 50
    chunk_preview_length: int = 100
    enable_search_highlighting: bool = True
    auto_scroll_to_selection: bool = True


class ChunkVisualizerUI(ThemeAwareUserControl):
    """
    Comprehensive chunk visualization UI component for document processing.
    
    Features:
    - Interactive chunk boundary visualization with color coding
    - Overlap region highlighting and analysis
    - Token count displays and statistics
    - Multiple display modes (overview, detailed, boundaries, overlap focus)
    - Real-time chunk selection and preview
    - Search and filtering capabilities
    - Responsive design with theme integration
    - Export and analysis tools
    """
    
    def __init__(
        self,
        config: Optional[ChunkVisualizationConfig] = None,
        on_chunk_selected: Optional[Callable[[DocumentChunk], None]] = None,
        on_overlap_selected: Optional[Callable[[OverlapRegion], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self.config = config or ChunkVisualizationConfig()
        
        # Callbacks
        self.on_chunk_selected = on_chunk_selected
        self.on_overlap_selected = on_overlap_selected
        
        # State
        self._chunks: List[DocumentChunk] = []
        self._boundaries: List[ChunkBoundary] = []
        self._overlap_regions: List[OverlapRegion] = []
        self._selected_chunk: Optional[DocumentChunk] = None
        self._selected_overlap: Optional[OverlapRegion] = None
        self._document_content: str = ""
        self._search_query: str = ""
        self._filter_criteria: Dict[str, Any] = {}
        
        # UI Components
        self._toolbar: Optional[ft.Container] = None
        self._display_mode_dropdown: Optional[ft.Dropdown] = None
        self._search_field: Optional[ft.TextField] = None
        self._chunk_list: Optional[ft.ListView] = None
        self._content_viewer: Optional[ft.Container] = None
        self._statistics_panel: Optional[ft.Container] = None
        self._chunk_details: Optional[ft.Container] = None
        
        # Performance tracking
        self._render_cache: Dict[str, ft.Control] = {}
        self._last_update_time: float = 0
    
    def build(self) -> ft.Control:
        """Build the chunk visualizer UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_toolbar(),
                    ft.Divider(height=1, color=palette.borders),
                    ft.Expanded(
                        child=ft.Row(
                            controls=[
                                ft.Expanded(
                                    flex=2,
                                    child=self._create_chunk_list_panel()
                                ),
                                ft.VerticalDivider(width=1, color=palette.borders),
                                ft.Expanded(
                                    flex=3,
                                    child=self._create_content_viewer()
                                ),
                                ft.VerticalDivider(width=1, color=palette.borders),
                                ft.Expanded(
                                    flex=1,
                                    child=self._create_details_panel()
                                )
                            ],
                            spacing=0,
                            expand=True
                        )
                    ),
                    ft.Divider(height=1, color=palette.borders),
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
    
    def _create_toolbar(self) -> ft.Container:
        """Create the main toolbar with controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Display mode dropdown
        self._display_mode_dropdown = ft.Dropdown(
            label="Display Mode",
            value=self.config.display_mode.value,
            options=[
                ft.dropdown.Option(mode.value, mode.value.replace("_", " ").title())
                for mode in ChunkDisplayMode
            ],
            on_change=self._on_display_mode_change,
            width=self.get_responsive_size(150)
        )
        
        # Search field
        self._search_field = ft.TextField(
            label="Search chunks",
            hint_text="Enter search terms...",
            prefix_icon=self.get_icon('SEARCH'),
            on_change=self._on_search_change,
            width=self.get_responsive_size(200)
        )
        
        # Action buttons
        refresh_btn = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh visualization",
            on_click=self._on_refresh_click
        )
        
        export_btn = ft.IconButton(
            icon=self.get_icon('DOWNLOAD'),
            tooltip="Export chunk data",
            on_click=self._on_export_click
        )
        
        settings_btn = ft.IconButton(
            icon=self.get_icon('SETTINGS'),
            tooltip="Visualization settings",
            on_click=self._on_settings_click
        )
        
        self._toolbar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "Chunk Visualizer",
                        style=self.get_text_style('heading_small'),
                        color=palette.on_surface
                    ),
                    ft.Container(expand=True),  # Spacer
                    self._display_mode_dropdown,
                    self._search_field,
                    refresh_btn,
                    export_btn,
                    settings_btn
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=spacing.medium,
            bgcolor=palette.surface_variant
        )
        
        return self._toolbar
    
    def _create_chunk_list_panel(self) -> ft.Container:
        """Create the chunk list panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Header
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "Document Chunks",
                        style=self.get_text_style('title_small'),
                        color=palette.on_surface
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        f"{len(self._chunks)} chunks",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    )
                ]
            ),
            padding=spacing.small,
            bgcolor=palette.surface_variant
        )
        
        # Chunk list
        self._chunk_list = ft.ListView(
            controls=[],
            spacing=spacing.xs,
            padding=spacing.small,
            expand=True
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    header,
                    ft.Divider(height=1, color=palette.borders),
                    ft.Expanded(child=self._chunk_list)
                ],
                spacing=0
            ),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.borders),
            border_radius=self.get_responsive_size(4)
        )

    def _create_content_viewer(self) -> ft.Container:
        """Create the main content viewer with chunk visualization."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Header
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "Document Content",
                        style=self.get_text_style('title_small'),
                        color=palette.on_surface
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=self.get_icon('ZOOM_IN'),
                        tooltip="Zoom in",
                        on_click=self._on_zoom_in
                    ),
                    ft.IconButton(
                        icon=self.get_icon('ZOOM_OUT'),
                        tooltip="Zoom out",
                        on_click=self._on_zoom_out
                    )
                ]
            ),
            padding=spacing.small,
            bgcolor=palette.surface_variant
        )

        # Content area
        self._content_viewer = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "No document loaded",
                        style=self.get_text_style('body_medium'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            ),
            padding=spacing.medium,
            expand=True
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    header,
                    ft.Divider(height=1, color=palette.borders),
                    ft.Expanded(child=self._content_viewer)
                ],
                spacing=0
            ),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.borders),
            border_radius=self.get_responsive_size(4)
        )

    def _create_details_panel(self) -> ft.Container:
        """Create the chunk details panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Header
        header = ft.Container(
            content=ft.Text(
                "Chunk Details",
                style=self.get_text_style('title_small'),
                color=palette.on_surface
            ),
            padding=spacing.small,
            bgcolor=palette.surface_variant
        )

        # Details content
        self._chunk_details = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Select a chunk to view details",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True
            ),
            padding=spacing.medium,
            expand=True
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    header,
                    ft.Divider(height=1, color=palette.borders),
                    ft.Expanded(child=self._chunk_details)
                ],
                spacing=0
            ),
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.borders),
            border_radius=self.get_responsive_size(4)
        )

    def _create_status_bar(self) -> ft.Container:
        """Create the status bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "Ready",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        f"Mode: {self.config.display_mode.value.replace('_', ' ').title()}",
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    )
                ]
            ),
            padding=spacing.small,
            bgcolor=palette.surface_variant
        )

    # Event Handlers
    async def _on_display_mode_change(self, e):
        """Handle display mode change."""
        try:
            new_mode = ChunkDisplayMode(e.control.value)
            self.config.display_mode = new_mode
            await self._refresh_visualization()
        except Exception as ex:
            print(f"Error changing display mode: {ex}")

    async def _on_search_change(self, e):
        """Handle search query change."""
        try:
            self._search_query = e.control.value
            await self._filter_chunks()
        except Exception as ex:
            print(f"Error in search: {ex}")

    async def _on_refresh_click(self, e):
        """Handle refresh button click."""
        await self._refresh_visualization()

    async def _on_export_click(self, e):
        """Handle export button click."""
        await self._export_chunk_data()

    async def _on_settings_click(self, e):
        """Handle settings button click."""
        await self._show_settings_dialog()

    async def _on_zoom_in(self, e):
        """Handle zoom in."""
        # Implementation for zoom functionality
        pass

    async def _on_zoom_out(self, e):
        """Handle zoom out."""
        # Implementation for zoom functionality
        pass

    async def _on_chunk_click(self, chunk: DocumentChunk):
        """Handle chunk selection."""
        try:
            self._selected_chunk = chunk
            await self._update_chunk_details()
            if self.on_chunk_selected:
                self.on_chunk_selected(chunk)
        except Exception as ex:
            print(f"Error selecting chunk: {ex}")

    # Core Methods
    async def load_document_chunks(self, chunks: List[DocumentChunk], content: str = ""):
        """Load document chunks for visualization."""
        try:
            self._chunks = chunks
            self._document_content = content
            self._boundaries = self._extract_boundaries(chunks)
            self._overlap_regions = self._extract_overlap_regions(chunks)
            await self._refresh_visualization()
        except Exception as ex:
            print(f"Error loading chunks: {ex}")

    def _extract_boundaries(self, chunks: List[DocumentChunk]) -> List[ChunkBoundary]:
        """Extract chunk boundaries from chunks."""
        boundaries = []
        for chunk in chunks:
            boundary = ChunkBoundary(
                start_position=chunk.metadata.start_char,
                end_position=chunk.metadata.end_char,
                chunk_id=chunk.chunk_id,
                boundary_type=chunk.metadata.break_type.value if chunk.metadata.break_type else "semantic"
            )
            boundaries.append(boundary)
        return boundaries

    def _extract_overlap_regions(self, chunks: List[DocumentChunk]) -> List[OverlapRegion]:
        """Extract overlap regions between chunks."""
        overlap_regions = []
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]
            next_chunk = chunks[i + 1]

            # Check for overlap
            if current_chunk.metadata.end_char > next_chunk.metadata.start_char:
                overlap = OverlapRegion(
                    start_position=next_chunk.metadata.start_char,
                    end_position=current_chunk.metadata.end_char,
                    chunk_ids=[current_chunk.chunk_id, next_chunk.chunk_id],
                    overlap_type="sentence",
                    token_count=0  # Calculate based on overlap content
                )
                overlap_regions.append(overlap)

        return overlap_regions

    async def _refresh_visualization(self):
        """Refresh the chunk visualization."""
        try:
            await self._update_chunk_list()
            await self._update_content_viewer()
            await self._update_statistics()
            if self.page:
                self.page.update()
        except Exception as ex:
            print(f"Error refreshing visualization: {ex}")

    async def _update_chunk_list(self):
        """Update the chunk list display."""
        if not self._chunk_list:
            return

        palette = self.get_palette()
        spacing = self.get_spacing()

        # Clear existing items
        self._chunk_list.controls.clear()

        # Filter chunks based on search
        filtered_chunks = self._filter_chunks_by_search()

        # Create chunk items
        for i, chunk in enumerate(filtered_chunks[:self.config.max_visible_chunks]):
            chunk_item = self._create_chunk_item(chunk, i)
            self._chunk_list.controls.append(chunk_item)

    def _filter_chunks_by_search(self) -> List[DocumentChunk]:
        """Filter chunks based on search query."""
        if not self._search_query:
            return self._chunks

        query = self._search_query.lower()
        filtered = []

        for chunk in self._chunks:
            if (query in chunk.content.lower() or
                query in chunk.chunk_id.lower()):
                filtered.append(chunk)

        return filtered

    def _create_chunk_item(self, chunk: DocumentChunk, index: int) -> ft.Container:
        """Create a chunk list item."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Chunk preview
        preview_text = chunk.content[:self.config.chunk_preview_length]
        if len(chunk.content) > self.config.chunk_preview_length:
            preview_text += "..."

        # Token count badge
        token_badge = ft.Container(
            content=ft.Text(
                f"{chunk.metadata.token_count}",
                style=self.get_text_style('label_small'),
                color=palette.on_primary
            ),
            bgcolor=palette.primary,
            padding=ft.padding.symmetric(horizontal=spacing.xs, vertical=2),
            border_radius=self.get_responsive_size(12)
        )

        # Chunk item
        is_selected = self._selected_chunk and self._selected_chunk.chunk_id == chunk.chunk_id

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                f"Chunk {index + 1}",
                                style=self.get_text_style('title_small'),
                                color=palette.on_surface
                            ),
                            ft.Container(expand=True),
                            token_badge if self.config.show_token_counts else ft.Container()
                        ]
                    ),
                    ft.Text(
                        preview_text,
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS
                    )
                ],
                spacing=spacing.xs
            ),
            padding=spacing.small,
            bgcolor=palette.primary_container if is_selected else palette.surface,
            border=ft.border.all(
                1,
                palette.primary if is_selected else palette.outline_variant
            ),
            border_radius=self.get_responsive_size(4),
            on_click=lambda e, c=chunk: asyncio.create_task(self._on_chunk_click(c))
        )

    async def _update_content_viewer(self):
        """Update the content viewer with chunk visualization."""
        if not self._content_viewer or not self._document_content:
            return

        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create content with chunk highlighting
        content_controls = []

        if self.config.display_mode == ChunkDisplayMode.OVERVIEW:
            content_controls = self._create_overview_content()
        elif self.config.display_mode == ChunkDisplayMode.DETAILED:
            content_controls = self._create_detailed_content()
        elif self.config.display_mode == ChunkDisplayMode.BOUNDARIES_ONLY:
            content_controls = self._create_boundaries_content()
        elif self.config.display_mode == ChunkDisplayMode.OVERLAP_FOCUS:
            content_controls = self._create_overlap_content()
        elif self.config.display_mode == ChunkDisplayMode.TOKEN_ANALYSIS:
            content_controls = self._create_token_analysis_content()

        # Update content viewer
        self._content_viewer.content = ft.Column(
            controls=content_controls,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

    def _create_overview_content(self) -> List[ft.Control]:
        """Create overview content display."""
        palette = self.get_palette()
        controls = []

        # Summary statistics
        stats_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Document Statistics",
                            style=self.get_text_style('title_medium'),
                            color=palette.on_surface
                        ),
                        ft.Row(
                            controls=[
                                self._create_stat_item("Total Chunks", str(len(self._chunks))),
                                self._create_stat_item("Overlap Regions", str(len(self._overlap_regions))),
                                self._create_stat_item("Avg Tokens",
                                    str(int(sum(c.metadata.token_count for c in self._chunks) / len(self._chunks)) if self._chunks else 0))
                            ]
                        )
                    ]
                ),
                padding=self.get_spacing().medium
            )
        )
        controls.append(stats_card)

        return controls

    def _create_stat_item(self, label: str, value: str) -> ft.Container:
        """Create a statistics item."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value,
                        style=self.get_text_style('headline_small'),
                        color=palette.primary
                    ),
                    ft.Text(
                        label,
                        style=self.get_text_style('body_small'),
                        color=palette.on_surface_variant
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.xs
            ),
            padding=spacing.small,
            expand=True
        )

    def _create_detailed_content(self) -> List[ft.Control]:
        """Create detailed content display."""
        controls = []
        # Implementation for detailed view
        controls.append(ft.Text("Detailed view - Implementation pending"))
        return controls

    def _create_boundaries_content(self) -> List[ft.Control]:
        """Create boundaries-only content display."""
        controls = []
        # Implementation for boundaries view
        controls.append(ft.Text("Boundaries view - Implementation pending"))
        return controls

    def _create_overlap_content(self) -> List[ft.Control]:
        """Create overlap-focused content display."""
        controls = []
        # Implementation for overlap view
        controls.append(ft.Text("Overlap view - Implementation pending"))
        return controls

    def _create_token_analysis_content(self) -> List[ft.Control]:
        """Create token analysis content display."""
        controls = []
        # Implementation for token analysis view
        controls.append(ft.Text("Token analysis view - Implementation pending"))
        return controls

    async def _update_chunk_details(self):
        """Update the chunk details panel."""
        if not self._chunk_details or not self._selected_chunk:
            return

        palette = self.get_palette()
        spacing = self.get_spacing()
        chunk = self._selected_chunk

        # Create details content
        details_controls = [
            ft.Text(
                f"Chunk ID: {chunk.chunk_id[:8]}...",
                style=self.get_text_style('title_small'),
                color=palette.on_surface
            ),
            ft.Divider(height=1, color=palette.outline_variant),

            # Metadata section
            ft.Text(
                "Metadata",
                style=self.get_text_style('title_small'),
                color=palette.on_surface
            ),
            self._create_detail_row("Token Count", str(chunk.metadata.token_count)),
            self._create_detail_row("Start Position", str(chunk.metadata.start_char)),
            self._create_detail_row("End Position", str(chunk.metadata.end_char)),
            self._create_detail_row("Length", str(len(chunk.content))),

            ft.Divider(height=1, color=palette.outline_variant),

            # Content preview
            ft.Text(
                "Content Preview",
                style=self.get_text_style('title_small'),
                color=palette.on_surface
            ),
            ft.Container(
                content=ft.Text(
                    chunk.content[:200] + ("..." if len(chunk.content) > 200 else ""),
                    style=self.get_text_style('body_small'),
                    color=palette.on_surface_variant
                ),
                padding=spacing.small,
                bgcolor=palette.surface_variant,
                border_radius=self.get_responsive_size(4)
            )
        ]

        self._chunk_details.content = ft.Column(
            controls=details_controls,
            spacing=spacing.small,
            scroll=ft.ScrollMode.AUTO
        )

    def _create_detail_row(self, label: str, value: str) -> ft.Row:
        """Create a detail row."""
        palette = self.get_palette()

        return ft.Row(
            controls=[
                ft.Text(
                    f"{label}:",
                    style=self.get_text_style('body_small'),
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(expand=True),
                ft.Text(
                    value,
                    style=self.get_text_style('body_small'),
                    color=palette.on_surface_variant
                )
            ]
        )

    async def _update_statistics(self):
        """Update visualization statistics."""
        # Implementation for statistics updates
        pass

    async def _filter_chunks(self):
        """Filter chunks based on current criteria."""
        await self._update_chunk_list()

    async def _export_chunk_data(self):
        """Export chunk data to file."""
        # Implementation for data export
        pass

    async def _show_settings_dialog(self):
        """Show settings configuration dialog."""
        # Implementation for settings dialog
        pass

    # Public API Methods
    def set_chunks(self, chunks: List[DocumentChunk], content: str = ""):
        """Set the chunks to visualize."""
        asyncio.create_task(self.load_document_chunks(chunks, content))

    def get_selected_chunk(self) -> Optional[DocumentChunk]:
        """Get the currently selected chunk."""
        return self._selected_chunk

    def set_display_mode(self, mode: ChunkDisplayMode):
        """Set the display mode."""
        self.config.display_mode = mode
        asyncio.create_task(self._refresh_visualization())

    def clear_visualization(self):
        """Clear the current visualization."""
        self._chunks.clear()
        self._boundaries.clear()
        self._overlap_regions.clear()
        self._selected_chunk = None
        self._selected_overlap = None
        self._document_content = ""
        asyncio.create_task(self._refresh_visualization())
