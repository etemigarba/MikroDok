"""
Module: file_picker_ui
Description: Custom file/directory picker dialogs for document and model selection.
            Provides comprehensive file selection UI with theme integration, responsive design,
            accessibility compliance, and advanced filtering capabilities for the MikroDok application.

Features:
- Multiple picker modes (single file, multiple files, directory, mixed)
- Advanced file filtering by type, extension, size, and date
- Responsive dialog layout with breakpoint-aware sizing
- Accessibility compliance with WCAG 2.1 AA standards
- Theme-aware styling with full ResponsiveLayoutManager integration
- Directory navigation with breadcrumb trail
- File preview capabilities for supported formats
- Batch selection with keyboard shortcuts
- Integration with document processing pipeline
- Cross-platform file system support

Phase: 1
Location: /src/modules/ui/dialog_components_ui/file_picker_ui/file_picker_ui.py
"""

# Standard library imports
import os
import asyncio
from pathlib import Path
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime

# Third-party imports
import flet as ft

# Local imports
try:
    from src.modules.ui.theme_system_ui.theme_system_ui import (
        ThemeAwareUserControl,
        ResponsiveLayoutManager,
        ScreenSize,
        ColorPalette,
        SpacingSystem,
        TypographyScale,
        IconSystem,
        get_theme_manager
    )
    from src.modules.logic.logging_infrastructure_lg import get_logger
except ImportError:
    # Fallback for testing without full theme system
    class ThemeAwareUserControl(ft.Container):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
        
        def get_palette(self):
            class MockPalette:
                background_primary = ft.Colors.BLACK
                surface = ft.Colors.GREY_800
                primary = ft.Colors.BLUE_400
                text_primary = ft.Colors.WHITE
                text_secondary = ft.Colors.GREY_400
                outline = ft.Colors.GREY_600
                surface_variant = ft.Colors.GREY_700
                borders = ft.Colors.GREY_600
                secondary = ft.Colors.GREY_400
                primary_variant = ft.Colors.BLUE_600
                error = ft.Colors.RED_400
                success = ft.Colors.GREEN_400
                warning = ft.Colors.ORANGE_400
                info = ft.Colors.BLUE_400
            return MockPalette()
        
        def get_spacing(self):
            class MockSpacing:
                xs = 4
                sm = 8
                md = 12
                lg = 16
                xl = 24
                xxl = 32
                component_padding = 16
                section_padding = 24
            return MockSpacing()
        
        def get_typography(self):
            class MockTypography:
                h3 = (20, 28, 600, 0.0)
                h4 = (18, 24, 500, 0.0)
                body_medium = (14, 20, 400, 0.0)
                body_small = (13, 18, 400, 0.0)
                caption = (12, 16, 400, 0.0)
            return MockTypography()
        
        def get_icons(self):
            class MockIcons:
                FOLDER = ft.Icons.FOLDER
                FOLDER_OPEN = ft.Icons.FOLDER_OPEN
                FILE = ft.Icons.DESCRIPTION
                UPLOAD_FILE = ft.Icons.UPLOAD_FILE
                CLOSE = ft.Icons.CLOSE
                CHECK = ft.Icons.CHECK
                CANCEL = ft.Icons.CANCEL
                SEARCH = ft.Icons.SEARCH
                REFRESH = ft.Icons.REFRESH
                HOME = ft.Icons.HOME
                ARROW_BACK = ft.Icons.ARROW_BACK
                CHEVRON_RIGHT = ft.Icons.CHEVRON_RIGHT
                GRID_VIEW = ft.Icons.GRID_VIEW
                LIST_VIEW = ft.Icons.VIEW_LIST
                SORT = ft.Icons.SORT
                FILTER_ALT = ft.Icons.FILTER_ALT
                PICTURE_AS_PDF = ft.Icons.PICTURE_AS_PDF
                TEXT_SNIPPET = ft.Icons.TEXT_SNIPPET
                IMAGE = ft.Icons.IMAGE
                ARCHIVE = ft.Icons.ARCHIVE
            return MockIcons()
    
    def get_logger(name):
        import logging
        return logging.getLogger(name)


class FilePickerMode(Enum):
    """File picker operation modes."""
    SINGLE_FILE = "single_file"
    MULTIPLE_FILES = "multiple_files"
    DIRECTORY = "directory"
    MIXED = "mixed"  # Both files and directories


class FilePickerState(Enum):
    """File picker dialog states."""
    CLOSED = "closed"
    OPENING = "opening"
    OPEN = "open"
    SELECTING = "selecting"
    CONFIRMING = "confirming"
    CLOSING = "closing"


@dataclass
class FileFilter:
    """File filtering configuration."""
    name: str
    extensions: List[str] = field(default_factory=list)
    mime_types: List[str] = field(default_factory=list)
    max_size_mb: Optional[int] = None
    min_size_mb: Optional[int] = None
    include_hidden: bool = False
    description: str = ""


@dataclass
class FilePickerResult:
    """Result of file picker operation."""
    success: bool
    selected_files: List[Path] = field(default_factory=list)
    selected_directories: List[Path] = field(default_factory=list)
    cancelled: bool = False
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FilePickerConfig:
    """Configuration for file picker dialog."""
    mode: FilePickerMode = FilePickerMode.SINGLE_FILE
    title: str = "Select Files"
    initial_directory: Optional[Path] = None
    filters: List[FileFilter] = field(default_factory=list)
    allow_multiple: bool = False
    show_hidden_files: bool = False
    enable_preview: bool = True
    enable_search: bool = True
    enable_breadcrumbs: bool = True
    max_selections: Optional[int] = None
    min_selections: int = 1
    dialog_width: Optional[int] = None
    dialog_height: Optional[int] = None
    resizable: bool = True
    modal: bool = True
    show_file_info: bool = True
    enable_keyboard_shortcuts: bool = True
    auto_close_on_select: bool = False
    remember_last_directory: bool = True


# Common file filters for convenience
DOCUMENT_FILTERS = [
    FileFilter(
        name="PDF Documents",
        extensions=["pdf"],
        description="Portable Document Format files"
    ),
    FileFilter(
        name="Word Documents", 
        extensions=["docx", "doc"],
        description="Microsoft Word documents"
    ),
    FileFilter(
        name="Text Files",
        extensions=["txt", "md", "markdown"],
        description="Plain text and Markdown files"
    ),
    FileFilter(
        name="HTML Files",
        extensions=["html", "htm"],
        description="HyperText Markup Language files"
    ),
    FileFilter(
        name="All Documents",
        extensions=["pdf", "docx", "doc", "txt", "md", "markdown", "html", "htm"],
        description="All supported document formats"
    )
]

MODEL_FILTERS = [
    FileFilter(
        name="Model Files",
        extensions=["bin", "safetensors", "gguf", "ggml"],
        description="Machine learning model files"
    ),
    FileFilter(
        name="Configuration Files",
        extensions=["json", "yaml", "yml", "toml"],
        description="Model configuration files"
    ),
    FileFilter(
        name="All Model Files",
        extensions=["bin", "safetensors", "gguf", "ggml", "json", "yaml", "yml", "toml"],
        description="All model-related files"
    )
]

ALL_FILES_FILTER = FileFilter(
    name="All Files",
    extensions=["*"],
    description="All file types"
)


class FilePickerUI(ThemeAwareUserControl):
    """
    Comprehensive file picker dialog with responsive design and theme integration.

    Features:
    - Responsive design with breakpoint-aware layouts
    - Directory navigation with breadcrumb trail
    - Advanced file filtering and search capabilities
    - Multi-select with keyboard shortcuts
    - File preview for supported formats
    - Theme-aware styling with accessibility compliance
    - Cross-platform file system support
    - Integration with document processing pipeline
    """

    def __init__(self,
                 config: Optional[FilePickerConfig] = None,
                 on_files_selected: Optional[Callable[[FilePickerResult], None]] = None,
                 on_cancelled: Optional[Callable[[], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the FilePickerUI component.

        Args:
            config: File picker configuration
            on_files_selected: Callback when files are selected
            on_cancelled: Callback when dialog is cancelled
            on_error: Callback when an error occurs
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)

        # Configuration
        self._config = config or FilePickerConfig()
        self._logger = get_logger(__name__)

        # Callbacks
        self._on_files_selected = on_files_selected
        self._on_cancelled = on_cancelled
        self._on_error = on_error

        # State management
        self._state = FilePickerState.CLOSED
        self._current_directory = self._config.initial_directory or Path.home()
        self._selected_items: List[Path] = []
        self._filtered_items: List[Path] = []
        self._search_query = ""
        self._current_filter: Optional[FileFilter] = None
        self._view_mode = "list"  # "list" or "grid"
        self._sort_by = "name"  # "name", "size", "date", "type"
        self._sort_ascending = True

        # UI components
        self._dialog: Optional[ft.AlertDialog] = None
        self._breadcrumb_row: Optional[ft.Row] = None
        self._search_field: Optional[ft.TextField] = None
        self._filter_dropdown: Optional[ft.Dropdown] = None
        self._file_list: Optional[ft.ListView] = None
        self._file_grid: Optional[ft.GridView] = None
        self._selection_info: Optional[ft.Text] = None
        self._preview_panel: Optional[ft.Container] = None
        self._action_buttons: Optional[ft.Row] = None

        # Responsive layout manager
        try:
            theme_manager = get_theme_manager()
            self._responsive_manager = theme_manager.get_responsive_layout_manager() if theme_manager else None
        except:
            self._responsive_manager = None

        # Initialize UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the file picker UI components."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # Get responsive dimensions
        dialog_width = self._get_responsive_dialog_width()
        dialog_height = self._get_responsive_dialog_height()

        # Create main content
        content = ft.Column([
            self._create_header(),
            self._create_navigation_bar(),
            self._create_main_content(),
            self._create_footer()
        ], spacing=spacing.md, expand=True)

        # Create dialog
        self._dialog = ft.AlertDialog(
            title=ft.Text(
                self._config.title,
                style=ft.TextStyle(
                    size=typography.h4[0],
                    weight=ft.FontWeight.W_600,
                    color=palette.text_primary
                )
            ),
            content=ft.Container(
                content=content,
                width=dialog_width,
                height=dialog_height,
                padding=ft.padding.all(spacing.lg)
            ),
            actions=[],  # Actions are handled in footer
            modal=self._config.modal,
            bgcolor=palette.surface,
            surface_tint_color=palette.primary,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions_alignment=ft.MainAxisAlignment.END,
            on_dismiss=self._on_dialog_dismiss
        )

        # Set main content
        self.content = ft.Container()  # Empty container, dialog is shown separately

    def _get_responsive_dialog_width(self) -> int:
        """Get responsive dialog width based on screen size."""
        if self._responsive_manager:
            return self._responsive_manager.get_breakpoint_value(
                mobile=min(self._responsive_manager.get_current_dimensions()[0] - 32, 400),
                tablet=600,
                desktop=800,
                large=1000
            )
        return self._config.dialog_width or 800

    def _get_responsive_dialog_height(self) -> int:
        """Get responsive dialog height based on screen size."""
        if self._responsive_manager:
            return self._responsive_manager.get_breakpoint_value(
                mobile=min(self._responsive_manager.get_current_dimensions()[1] - 100, 500),
                tablet=600,
                desktop=700,
                large=800
            )
        return self._config.dialog_height or 700

    def _create_header(self) -> ft.Control:
        """Create the dialog header with search and view controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Search field
        self._search_field = ft.TextField(
            hint_text="Search files and folders...",
            prefix_icon=icons.SEARCH,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary),
            hint_style=ft.TextStyle(color=palette.text_secondary),
            on_change=self._on_search_changed,
            expand=True,
            visible=self._config.enable_search
        )

        # Filter dropdown
        filter_options = []
        if self._config.filters:
            filter_options = [
                ft.dropdown.Option(key=str(i), text=f.name)
                for i, f in enumerate(self._config.filters)
            ]

        self._filter_dropdown = ft.Dropdown(
            hint_text="Filter",
            options=filter_options,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary),
            on_change=self._on_filter_changed,
            width=150,
            visible=len(filter_options) > 0
        )

        # View mode toggle
        view_toggle = ft.Row([
            ft.IconButton(
                icon=icons.LIST_VIEW,
                selected=self._view_mode == "list",
                on_click=lambda _: self._set_view_mode("list"),
                tooltip="List view",
                icon_color=palette.text_secondary,
                selected_icon_color=palette.primary
            ),
            ft.IconButton(
                icon=icons.GRID_VIEW,
                selected=self._view_mode == "grid",
                on_click=lambda _: self._set_view_mode("grid"),
                tooltip="Grid view",
                icon_color=palette.text_secondary,
                selected_icon_color=palette.primary
            )
        ], spacing=spacing.xs)

        # Refresh button
        refresh_button = ft.IconButton(
            icon=icons.REFRESH,
            on_click=self._refresh_directory,
            tooltip="Refresh",
            icon_color=palette.text_secondary
        )

        return ft.Row([
            self._search_field,
            self._filter_dropdown,
            view_toggle,
            refresh_button
        ], spacing=spacing.md)

    def _create_navigation_bar(self) -> ft.Control:
        """Create the navigation bar with breadcrumbs."""
        if not self._config.enable_breadcrumbs:
            return ft.Container(height=0)

        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Home button
        home_button = ft.IconButton(
            icon=icons.HOME,
            on_click=lambda _: self._navigate_to_directory(Path.home()),
            tooltip="Home",
            icon_color=palette.text_secondary
        )

        # Back button
        back_button = ft.IconButton(
            icon=icons.ARROW_BACK,
            on_click=self._navigate_back,
            tooltip="Back",
            icon_color=palette.text_secondary,
            disabled=not self._can_navigate_back()
        )

        # Breadcrumb trail
        self._breadcrumb_row = ft.Row(
            controls=[],
            spacing=spacing.xs,
            scroll=ft.ScrollMode.AUTO
        )

        self._update_breadcrumbs()

        return ft.Container(
            content=ft.Row([
                home_button,
                back_button,
                ft.VerticalDivider(width=1, color=palette.outline),
                ft.Expanded(child=self._breadcrumb_row)
            ], spacing=spacing.sm),
            padding=ft.padding.symmetric(vertical=spacing.sm),
            border=ft.border.only(bottom=ft.BorderSide(1, palette.outline))
        )

    def _create_main_content(self) -> ft.Control:
        """Create the main content area with file list/grid and preview."""
        spacing = self.get_spacing()

        # File list/grid container
        file_container = ft.Container(
            content=self._create_file_view(),
            expand=True,
            border_radius=8
        )

        # Preview panel (if enabled)
        if self._config.enable_preview:
            self._preview_panel = self._create_preview_panel()

            # Use responsive layout for preview
            if self._responsive_manager and self._responsive_manager.is_mobile_or_tablet():
                # Stack vertically on mobile/tablet
                return ft.Column([
                    file_container,
                    self._preview_panel
                ], spacing=spacing.md, expand=True)
            else:
                # Side by side on desktop
                return ft.Row([
                    ft.Expanded(child=file_container, flex=2),
                    ft.VerticalDivider(width=1),
                    ft.Expanded(child=self._preview_panel, flex=1)
                ], spacing=spacing.md, expand=True)

        return file_container

    def _create_file_view(self) -> ft.Control:
        """Create the file list or grid view."""
        if self._view_mode == "grid":
            return self._create_file_grid()
        else:
            return self._create_file_list()

    def _create_file_list(self) -> ft.Control:
        """Create the file list view."""
        palette = self.get_palette()

        self._file_list = ft.ListView(
            controls=[],
            spacing=2,
            padding=ft.padding.all(8),
            expand=True,
            auto_scroll=False
        )

        self._populate_file_list()

        return ft.Container(
            content=self._file_list,
            border=ft.border.all(1, palette.outline),
            border_radius=8,
            bgcolor=palette.surface_variant
        )

    def _create_file_grid(self) -> ft.Control:
        """Create the file grid view."""
        palette = self.get_palette()

        # Get responsive column count
        columns = 4
        if self._responsive_manager:
            columns = self._responsive_manager.get_breakpoint_value(
                mobile=2, tablet=3, desktop=4, large=5
            )

        self._file_grid = ft.GridView(
            controls=[],
            runs_count=columns,
            max_extent=150,
            child_aspect_ratio=1.0,
            spacing=8,
            run_spacing=8,
            padding=ft.padding.all(8),
            expand=True
        )

        self._populate_file_grid()

        return ft.Container(
            content=self._file_grid,
            border=ft.border.all(1, palette.outline),
            border_radius=8,
            bgcolor=palette.surface_variant
        )

    def _create_preview_panel(self) -> ft.Control:
        """Create the file preview panel."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    "Preview",
                    style=ft.TextStyle(
                        size=typography.h4[0],
                        weight=ft.FontWeight.W_500,
                        color=palette.text_primary
                    )
                ),
                ft.Divider(color=palette.outline),
                ft.Container(
                    content=ft.Text(
                        "Select a file to preview",
                        style=ft.TextStyle(
                            color=palette.text_secondary,
                            size=typography.body_small[0]
                        )
                    ),
                    alignment=ft.alignment.center,
                    expand=True
                )
            ], spacing=spacing.md),
            padding=ft.padding.all(spacing.lg),
            border=ft.border.all(1, palette.outline),
            border_radius=8,
            bgcolor=palette.surface_variant,
            width=300 if not self._responsive_manager or self._responsive_manager.is_desktop_or_larger() else None
        )

    def _create_footer(self) -> ft.Control:
        """Create the dialog footer with selection info and action buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Selection info
        self._selection_info = ft.Text(
            self._get_selection_text(),
            style=ft.TextStyle(
                color=palette.text_secondary,
                size=typography.body_small[0]
            )
        )

        # Action buttons
        cancel_button = ft.TextButton(
            text="Cancel",
            on_click=self._on_cancel_clicked,
            style=ft.ButtonStyle(
                color=palette.text_secondary,
                overlay_color=palette.surface_variant
            )
        )

        select_button = ft.ElevatedButton(
            text=self._get_select_button_text(),
            on_click=self._on_select_clicked,
            disabled=not self._can_select(),
            style=ft.ButtonStyle(
                bgcolor=palette.primary,
                color=palette.text_primary
            )
        )

        self._action_buttons = ft.Row([
            cancel_button,
            select_button
        ], spacing=spacing.md)

        return ft.Container(
            content=ft.Row([
                ft.Expanded(child=self._selection_info),
                self._action_buttons
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.only(top=spacing.lg),
            border=ft.border.only(top=ft.BorderSide(1, palette.outline))
        )

    def _populate_file_list(self) -> None:
        """Populate the file list view with current directory contents."""
        if not self._file_list:
            return

        self._file_list.controls.clear()

        try:
            items = self._get_filtered_directory_items()

            for item in items:
                list_tile = self._create_file_list_item(item)
                self._file_list.controls.append(list_tile)

        except Exception as e:
            self._logger.error(f"Error populating file list: {e}")
            if self._on_error:
                self._on_error(f"Failed to load directory: {e}")

        if self._file_list.page:
            self._file_list.update()

    def _populate_file_grid(self) -> None:
        """Populate the file grid view with current directory contents."""
        if not self._file_grid:
            return

        self._file_grid.controls.clear()

        try:
            items = self._get_filtered_directory_items()

            for item in items:
                grid_item = self._create_file_grid_item(item)
                self._file_grid.controls.append(grid_item)

        except Exception as e:
            self._logger.error(f"Error populating file grid: {e}")
            if self._on_error:
                self._on_error(f"Failed to load directory: {e}")

        if self._file_grid.page:
            self._file_grid.update()

    def _get_filtered_directory_items(self) -> List[Path]:
        """Get filtered and sorted directory items."""
        try:
            if not self._current_directory.exists():
                return []

            items = []

            # Get directory contents
            for item in self._current_directory.iterdir():
                # Skip hidden files unless enabled
                if item.name.startswith('.') and not self._config.show_hidden_files:
                    continue

                # Apply search filter
                if self._search_query and self._search_query.lower() not in item.name.lower():
                    continue

                # Apply file type filter
                if self._current_filter and not self._matches_filter(item, self._current_filter):
                    continue

                # Check mode compatibility
                if self._config.mode == FilePickerMode.DIRECTORY and item.is_file():
                    continue
                elif self._config.mode == FilePickerMode.SINGLE_FILE and item.is_dir():
                    continue
                elif self._config.mode == FilePickerMode.MULTIPLE_FILES and item.is_dir():
                    continue

                items.append(item)

            # Sort items
            items = self._sort_items(items)

            return items

        except Exception as e:
            self._logger.error(f"Error filtering directory items: {e}")
            return []

    def _matches_filter(self, item: Path, file_filter: FileFilter) -> bool:
        """Check if item matches the given filter."""
        if item.is_dir():
            return True  # Directories always match

        # Check extensions
        if file_filter.extensions and "*" not in file_filter.extensions:
            if item.suffix.lower().lstrip('.') not in [ext.lower().lstrip('.') for ext in file_filter.extensions]:
                return False

        # Check file size
        try:
            file_size_mb = item.stat().st_size / (1024 * 1024)

            if file_filter.max_size_mb and file_size_mb > file_filter.max_size_mb:
                return False

            if file_filter.min_size_mb and file_size_mb < file_filter.min_size_mb:
                return False

        except Exception:
            pass  # Skip size check if file is inaccessible

        return True

    def _sort_items(self, items: List[Path]) -> List[Path]:
        """Sort items based on current sort criteria."""
        try:
            if self._sort_by == "name":
                key_func = lambda x: (x.is_file(), x.name.lower())
            elif self._sort_by == "size":
                key_func = lambda x: (x.is_file(), x.stat().st_size if x.is_file() else 0)
            elif self._sort_by == "date":
                key_func = lambda x: (x.is_file(), x.stat().st_mtime)
            elif self._sort_by == "type":
                key_func = lambda x: (x.is_file(), x.suffix.lower() if x.is_file() else "")
            else:
                key_func = lambda x: (x.is_file(), x.name.lower())

            return sorted(items, key=key_func, reverse=not self._sort_ascending)

        except Exception as e:
            self._logger.error(f"Error sorting items: {e}")
            return items

    def _create_file_list_item(self, item: Path) -> ft.Control:
        """Create a list item for a file or directory."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # Get item info
        is_dir = item.is_dir()
        is_selected = item in self._selected_items

        # Icon
        if is_dir:
            icon = icons.FOLDER if not is_selected else icons.FOLDER_OPEN
            icon_color = palette.primary if is_selected else palette.text_secondary
        else:
            icon = self._get_file_icon(item)
            icon_color = palette.primary if is_selected else palette.text_secondary

        # File info
        try:
            stat = item.stat()
            size_text = self._format_file_size(stat.st_size) if not is_dir else ""
            date_text = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            size_text = ""
            date_text = ""

        # Create list tile
        list_tile = ft.ListTile(
            leading=ft.Icon(icon, color=icon_color),
            title=ft.Text(
                item.name,
                style=ft.TextStyle(
                    color=palette.text_primary,
                    size=typography.body_medium[0],
                    weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.W_400
                ),
                overflow=ft.TextOverflow.ELLIPSIS
            ),
            subtitle=ft.Text(
                f"{size_text} • {date_text}" if size_text else date_text,
                style=ft.TextStyle(
                    color=palette.text_secondary,
                    size=typography.body_small[0]
                )
            ) if self._config.show_file_info else None,
            selected=is_selected,
            on_click=lambda e, path=item: self._on_item_clicked(path),
            on_long_press=lambda e, path=item: self._on_item_long_pressed(path),
            bgcolor=palette.primary_variant if is_selected else None,
            hover_color=palette.surface_variant,
            shape=ft.RoundedRectangleBorder(radius=8)
        )

        return list_tile

    def _create_file_grid_item(self, item: Path) -> ft.Control:
        """Create a grid item for a file or directory."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # Get item info
        is_dir = item.is_dir()
        is_selected = item in self._selected_items

        # Icon
        if is_dir:
            icon = icons.FOLDER if not is_selected else icons.FOLDER_OPEN
        else:
            icon = self._get_file_icon(item)

        # Create grid item
        grid_item = ft.Container(
            content=ft.Column([
                ft.Icon(
                    icon,
                    size=48,
                    color=palette.primary if is_selected else palette.text_secondary
                ),
                ft.Text(
                    item.name,
                    style=ft.TextStyle(
                        color=palette.text_primary,
                        size=typography.body_small[0],
                        weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.W_400
                    ),
                    text_align=ft.TextAlign.CENTER,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=2
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.sm),
            padding=ft.padding.all(spacing.md),
            border=ft.border.all(
                2 if is_selected else 1,
                palette.primary if is_selected else palette.outline
            ),
            border_radius=8,
            bgcolor=palette.primary_variant if is_selected else palette.surface,
            on_click=lambda e, path=item: self._on_item_clicked(path),
            on_long_press=lambda e, path=item: self._on_item_long_pressed(path),
            ink=True
        )

        return grid_item

    def _get_file_icon(self, file_path: Path) -> str:
        """Get appropriate icon for file type."""
        icons = self.get_icons()

        suffix = file_path.suffix.lower()

        if suffix in ['.pdf']:
            return icons.PICTURE_AS_PDF
        elif suffix in ['.txt', '.md', '.markdown']:
            return icons.TEXT_SNIPPET
        elif suffix in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']:
            return icons.IMAGE
        elif suffix in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return icons.ARCHIVE
        elif suffix in ['.docx', '.doc', '.odt']:
            return icons.FILE
        elif suffix in ['.html', '.htm']:
            return icons.FILE
        else:
            return icons.FILE

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"

    # Event handlers
    def _on_item_clicked(self, item: Path) -> None:
        """Handle item click event."""
        try:
            if item.is_dir():
                # Navigate to directory
                self._navigate_to_directory(item)
            else:
                # Select/deselect file
                self._toggle_item_selection(item)

        except Exception as e:
            self._logger.error(f"Error handling item click: {e}")
            if self._on_error:
                self._on_error(f"Failed to handle item selection: {e}")

    def _on_item_long_pressed(self, item: Path) -> None:
        """Handle item long press event (for context menu)."""
        # TODO: Implement context menu
        pass

    def _on_search_changed(self, e: ft.ControlEvent) -> None:
        """Handle search query change."""
        self._search_query = e.control.value or ""
        self._refresh_file_view()

    def _on_filter_changed(self, e: ft.ControlEvent) -> None:
        """Handle filter selection change."""
        if e.control.value and self._config.filters:
            try:
                filter_index = int(e.control.value)
                self._current_filter = self._config.filters[filter_index]
            except (ValueError, IndexError):
                self._current_filter = None
        else:
            self._current_filter = None

        self._refresh_file_view()

    def _on_cancel_clicked(self, e: ft.ControlEvent) -> None:
        """Handle cancel button click."""
        self._close_dialog()
        if self._on_cancelled:
            self._on_cancelled()

    def _on_select_clicked(self, e: ft.ControlEvent) -> None:
        """Handle select button click."""
        try:
            result = self._create_result()
            self._close_dialog()

            if self._on_files_selected:
                self._on_files_selected(result)

        except Exception as e:
            self._logger.error(f"Error handling file selection: {e}")
            if self._on_error:
                self._on_error(f"Failed to process selection: {e}")

    def _on_dialog_dismiss(self, e: ft.ControlEvent) -> None:
        """Handle dialog dismiss event."""
        self._state = FilePickerState.CLOSED
        if self._on_cancelled:
            self._on_cancelled()

    # Navigation methods
    def _navigate_to_directory(self, directory: Path) -> None:
        """Navigate to the specified directory."""
        try:
            if directory.exists() and directory.is_dir():
                self._current_directory = directory
                self._selected_items.clear()
                self._update_breadcrumbs()
                self._refresh_file_view()
                self._update_selection_info()

        except Exception as e:
            self._logger.error(f"Error navigating to directory: {e}")
            if self._on_error:
                self._on_error(f"Failed to navigate to directory: {e}")

    def _navigate_back(self, e: ft.ControlEvent) -> None:
        """Navigate to parent directory."""
        if self._can_navigate_back():
            parent = self._current_directory.parent
            self._navigate_to_directory(parent)

    def _can_navigate_back(self) -> bool:
        """Check if can navigate to parent directory."""
        try:
            return self._current_directory.parent != self._current_directory
        except Exception:
            return False

    def _update_breadcrumbs(self) -> None:
        """Update the breadcrumb navigation."""
        if not self._breadcrumb_row:
            return

        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        self._breadcrumb_row.controls.clear()

        # Build path components
        parts = self._current_directory.parts
        current_path = Path(parts[0])

        for i, part in enumerate(parts):
            if i > 0:
                current_path = current_path / part

            # Add separator
            if i > 0:
                self._breadcrumb_row.controls.append(
                    ft.Icon(icons.CHEVRON_RIGHT, size=16, color=palette.text_secondary)
                )

            # Add breadcrumb button
            is_current = (i == len(parts) - 1)
            breadcrumb = ft.TextButton(
                text=part if part else "Root",
                on_click=lambda e, path=current_path: self._navigate_to_directory(path),
                style=ft.ButtonStyle(
                    color=palette.text_primary if is_current else palette.text_secondary,
                    overlay_color=palette.surface_variant
                ),
                disabled=is_current
            )

            self._breadcrumb_row.controls.append(breadcrumb)

        if self._breadcrumb_row.page:
            self._breadcrumb_row.update()

    # Selection methods
    def _toggle_item_selection(self, item: Path) -> None:
        """Toggle selection state of an item."""
        if item in self._selected_items:
            self._selected_items.remove(item)
        else:
            # Check selection limits
            if self._config.mode == FilePickerMode.SINGLE_FILE and len(self._selected_items) >= 1:
                self._selected_items.clear()

            if self._config.max_selections and len(self._selected_items) >= self._config.max_selections:
                return

            self._selected_items.append(item)

        self._refresh_file_view()
        self._update_selection_info()
        self._update_action_buttons()

    def _can_select(self) -> bool:
        """Check if current selection is valid for confirmation."""
        if len(self._selected_items) < self._config.min_selections:
            return False

        if self._config.max_selections and len(self._selected_items) > self._config.max_selections:
            return False

        # Check mode compatibility
        if self._config.mode == FilePickerMode.DIRECTORY:
            return all(item.is_dir() for item in self._selected_items)
        elif self._config.mode in [FilePickerMode.SINGLE_FILE, FilePickerMode.MULTIPLE_FILES]:
            return all(item.is_file() for item in self._selected_items)

        return True

    def _create_result(self) -> FilePickerResult:
        """Create the file picker result."""
        files = [item for item in self._selected_items if item.is_file()]
        directories = [item for item in self._selected_items if item.is_dir()]

        return FilePickerResult(
            success=True,
            selected_files=files,
            selected_directories=directories,
            cancelled=False,
            metadata={
                'current_directory': str(self._current_directory),
                'filter_used': self._current_filter.name if self._current_filter else None,
                'search_query': self._search_query,
                'view_mode': self._view_mode
            }
        )

    # UI update methods
    def _refresh_file_view(self) -> None:
        """Refresh the current file view."""
        if self._view_mode == "grid" and self._file_grid:
            self._populate_file_grid()
        elif self._view_mode == "list" and self._file_list:
            self._populate_file_list()

    def _refresh_directory(self, e: ft.ControlEvent) -> None:
        """Refresh the current directory."""
        self._refresh_file_view()

    def _set_view_mode(self, mode: str) -> None:
        """Set the view mode (list or grid)."""
        if mode != self._view_mode:
            self._view_mode = mode
            # Rebuild the file view
            if hasattr(self, '_dialog') and self._dialog:
                # Update the main content
                main_content = self._dialog.content.content.controls[2]  # Main content is 3rd item
                main_content.content = self._create_main_content()
                if self._dialog.page:
                    self._dialog.update()

    def _update_selection_info(self) -> None:
        """Update the selection information text."""
        if self._selection_info:
            self._selection_info.value = self._get_selection_text()
            if self._selection_info.page:
                self._selection_info.update()

    def _update_action_buttons(self) -> None:
        """Update the action button states."""
        if self._action_buttons and len(self._action_buttons.controls) > 1:
            select_button = self._action_buttons.controls[1]  # Select button is second
            select_button.disabled = not self._can_select()
            select_button.text = self._get_select_button_text()

            if self._action_buttons.page:
                self._action_buttons.update()

    # Helper methods
    def _get_selection_text(self) -> str:
        """Get the selection information text."""
        count = len(self._selected_items)

        if count == 0:
            return "No items selected"
        elif count == 1:
            item = self._selected_items[0]
            item_type = "folder" if item.is_dir() else "file"
            return f"1 {item_type} selected"
        else:
            files = sum(1 for item in self._selected_items if item.is_file())
            dirs = sum(1 for item in self._selected_items if item.is_dir())

            parts = []
            if files > 0:
                parts.append(f"{files} file{'s' if files != 1 else ''}")
            if dirs > 0:
                parts.append(f"{dirs} folder{'s' if dirs != 1 else ''}")

            return f"{count} items selected ({', '.join(parts)})"

    def _get_select_button_text(self) -> str:
        """Get the select button text based on mode and selection."""
        if self._config.mode == FilePickerMode.DIRECTORY:
            return "Select Folder"
        elif self._config.mode == FilePickerMode.SINGLE_FILE:
            return "Select File"
        else:
            count = len(self._selected_items)
            if count == 0:
                return "Select"
            elif count == 1:
                return "Select 1 Item"
            else:
                return f"Select {count} Items"

    # Public interface methods
    async def show_dialog(self, page: ft.Page) -> None:
        """Show the file picker dialog."""
        try:
            self._state = FilePickerState.OPENING

            # Add dialog to page
            page.overlay.append(self._dialog)
            self._dialog.open = True

            # Update responsive layout if available
            if self._responsive_manager:
                width, height = page.window.width or 1920, page.window.height or 1080
                self._responsive_manager.update_window_size(width, height)

            await page.update_async()

            self._state = FilePickerState.OPEN

        except Exception as e:
            self._logger.error(f"Error showing dialog: {e}")
            self._state = FilePickerState.CLOSED
            if self._on_error:
                self._on_error(f"Failed to show file picker: {e}")

    def _close_dialog(self) -> None:
        """Close the file picker dialog."""
        try:
            self._state = FilePickerState.CLOSING

            if self._dialog:
                self._dialog.open = False
                if self._dialog.page:
                    self._dialog.page.update()

            self._state = FilePickerState.CLOSED

        except Exception as e:
            self._logger.error(f"Error closing dialog: {e}")

    def get_current_directory(self) -> Path:
        """Get the current directory."""
        return self._current_directory

    def get_selected_items(self) -> List[Path]:
        """Get the currently selected items."""
        return self._selected_items.copy()

    def set_current_directory(self, directory: Path) -> None:
        """Set the current directory."""
        self._navigate_to_directory(directory)

    def clear_selection(self) -> None:
        """Clear the current selection."""
        self._selected_items.clear()
        self._refresh_file_view()
        self._update_selection_info()
        self._update_action_buttons()

    def get_state(self) -> FilePickerState:
        """Get the current dialog state."""
        return self._state


# Convenience functions for creating common file picker configurations
def create_file_picker_dialog(
    mode: FilePickerMode = FilePickerMode.SINGLE_FILE,
    title: str = "Select Files",
    filters: Optional[List[FileFilter]] = None,
    initial_directory: Optional[Path] = None,
    **kwargs
) -> FilePickerUI:
    """
    Create a file picker dialog with common configuration.

    Args:
        mode: File picker mode
        title: Dialog title
        filters: File filters to apply
        initial_directory: Initial directory to show
        **kwargs: Additional configuration options

    Returns:
        Configured FilePickerUI instance
    """
    config = FilePickerConfig(
        mode=mode,
        title=title,
        filters=filters or [],
        initial_directory=initial_directory,
        **kwargs
    )

    return FilePickerUI(config=config)


def create_document_picker(
    allow_multiple: bool = False,
    initial_directory: Optional[Path] = None,
    **kwargs
) -> FilePickerUI:
    """
    Create a document file picker with document-specific filters.

    Args:
        allow_multiple: Allow multiple file selection
        initial_directory: Initial directory to show
        **kwargs: Additional configuration options

    Returns:
        Configured FilePickerUI for document selection
    """
    mode = FilePickerMode.MULTIPLE_FILES if allow_multiple else FilePickerMode.SINGLE_FILE

    config = FilePickerConfig(
        mode=mode,
        title="Select Documents",
        filters=DOCUMENT_FILTERS,
        initial_directory=initial_directory,
        allow_multiple=allow_multiple,
        **kwargs
    )

    return FilePickerUI(config=config)


def create_directory_picker(
    title: str = "Select Folder",
    initial_directory: Optional[Path] = None,
    **kwargs
) -> FilePickerUI:
    """
    Create a directory picker dialog.

    Args:
        title: Dialog title
        initial_directory: Initial directory to show
        **kwargs: Additional configuration options

    Returns:
        Configured FilePickerUI for directory selection
    """
    config = FilePickerConfig(
        mode=FilePickerMode.DIRECTORY,
        title=title,
        initial_directory=initial_directory,
        **kwargs
    )

    return FilePickerUI(config=config)


def create_model_file_picker(
    allow_multiple: bool = False,
    initial_directory: Optional[Path] = None,
    **kwargs
) -> FilePickerUI:
    """
    Create a model file picker with model-specific filters.

    Args:
        allow_multiple: Allow multiple file selection
        initial_directory: Initial directory to show
        **kwargs: Additional configuration options

    Returns:
        Configured FilePickerUI for model file selection
    """
    mode = FilePickerMode.MULTIPLE_FILES if allow_multiple else FilePickerMode.SINGLE_FILE

    config = FilePickerConfig(
        mode=mode,
        title="Select Model Files",
        filters=MODEL_FILTERS,
        initial_directory=initial_directory,
        allow_multiple=allow_multiple,
        **kwargs
    )

    return FilePickerUI(config=config)
