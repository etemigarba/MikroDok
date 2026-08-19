"""
Module: file_browser_ui
Description: Comprehensive file system browser interface for document selection and upload.
            Provides responsive file browsing with directory navigation, file filtering, multi-select
            capabilities, and seamless integration with document processing pipeline. Features modern
            UI/UX with theme-aware styling, accessibility compliance, and cross-platform compatibility.
Phase: 3
Location: /src/modules/ui/document_upload_ui/file_browser_ui/file_browser_ui.py
"""

# Standard library imports
import asyncio
import os
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set, Union
from datetime import datetime

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
from src.modules.logic.document_ingestion_lg.file_validator_lg.file_validator_lg import (
    FileValidator, FileValidationResult
)


class BrowserMode(Enum):
    """File browser operation modes."""
    SINGLE_FILE = "single_file"
    MULTIPLE_FILES = "multiple_files"
    DIRECTORY = "directory"
    MIXED = "mixed"


class BrowserState(Enum):
    """File browser states."""
    LOADING = "loading"
    READY = "ready"
    NAVIGATING = "navigating"
    SELECTING = "selecting"
    ERROR = "error"


@dataclass
class FileItem:
    """Represents a file in the browser."""
    path: Path
    name: str
    size: int
    modified: datetime
    is_directory: bool = False
    is_selected: bool = False
    is_valid: bool = True
    format_type: Optional[DocumentFormat] = None
    icon: str = ""
    size_display: str = ""
    modified_display: str = ""


@dataclass
class DirectoryItem:
    """Represents a directory in the browser."""
    path: Path
    name: str
    item_count: int
    modified: datetime
    is_accessible: bool = True
    is_selected: bool = False


@dataclass
class FileFilterConfig:
    """Configuration for file filtering."""
    allowed_formats: List[DocumentFormat] = field(default_factory=lambda: [
        DocumentFormat.PDF, DocumentFormat.DOCX, DocumentFormat.TXT,
        DocumentFormat.HTML, DocumentFormat.MARKDOWN
    ])
    max_file_size_mb: int = 100
    show_hidden_files: bool = False
    show_system_files: bool = False
    file_extensions: Set[str] = field(default_factory=set)
    name_filter: str = ""
    date_filter_start: Optional[datetime] = None
    date_filter_end: Optional[datetime] = None


class FileBrowserUI(ThemeAwareUserControl):
    """
    Comprehensive file system browser with responsive design and theme integration.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Directory navigation with breadcrumb trail
    - File filtering and format validation
    - Multi-select capabilities with batch operations
    - Real-time file system monitoring
    - Theme-aware styling with accessibility compliance
    - Cross-platform file system support
    - Integration with document processing pipeline
    """
    
    def __init__(self,
                 mode: BrowserMode = BrowserMode.MULTIPLE_FILES,
                 filter_config: Optional[FileFilterConfig] = None,
                 initial_path: Optional[Path] = None,
                 on_files_selected: Optional[Callable[[List[FileItem]], None]] = None,
                 on_directory_changed: Optional[Callable[[Path], None]] = None,
                 on_selection_changed: Optional[Callable[[List[FileItem]], None]] = None,
                 **kwargs):
        """
        Initialize the FileBrowserUI component.
        
        Args:
            mode: Browser operation mode
            filter_config: File filtering configuration
            initial_path: Initial directory path
            on_files_selected: Callback when files are selected
            on_directory_changed: Callback when directory changes
            on_selection_changed: Callback when selection changes
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._mode = mode
        self._filter_config = filter_config or FileFilterConfig()
        self._initial_path = initial_path or Path.home()
        
        # Callbacks
        self._on_files_selected = on_files_selected
        self._on_directory_changed = on_directory_changed
        self._on_selection_changed = on_selection_changed
        
        # State
        self._current_path = self._initial_path
        self._state = BrowserState.LOADING
        self._selected_items: Set[Path] = set()
        self._file_items: List[FileItem] = []
        self._directory_items: List[DirectoryItem] = []
        self._navigation_history: List[Path] = [self._initial_path]
        self._history_index = 0
        
        # Components
        self._breadcrumb_bar: Optional[ft.Control] = None
        self._toolbar: Optional[ft.Control] = None
        self._file_list: Optional[ft.Control] = None
        self._status_bar: Optional[ft.Control] = None
        self._loading_indicator: Optional[ft.Control] = None
        
        # Services
        self._logger = get_logger(__name__)
        self._format_detector = FormatDetector()
        self._file_validator = FileValidator()

        # Initialize directory loading will be done when component is mounted

    def did_mount(self) -> None:
        """Called when control is mounted to the page."""
        super().did_mount()
        # Load directory when component is properly mounted with event loop
        self._load_directory_async()

    def build(self) -> ft.Control:
        """Build the file browser UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create main layout
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_toolbar(),
                    self._create_breadcrumb_bar(),
                    ft.Divider(
                        height=1,
                        color=palette.borders
                    ),
                    self._create_file_list_container(),
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
        """Create the toolbar with navigation and action buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Navigation buttons
        back_button = ft.IconButton(
            icon=self.get_icon('ARROW_BACK'),
            tooltip="Go Back",
            on_click=self._go_back,
            disabled=self._history_index <= 0,
            icon_color=palette.text_secondary
        )
        
        forward_button = ft.IconButton(
            icon=self.get_icon('ARROW_FORWARD'),
            tooltip="Go Forward", 
            on_click=self._go_forward,
            disabled=self._history_index >= len(self._navigation_history) - 1,
            icon_color=palette.text_secondary
        )
        
        up_button = ft.IconButton(
            icon=self.get_icon('ARROW_UPWARD'),
            tooltip="Go Up",
            on_click=self._go_up,
            disabled=self._current_path == self._current_path.parent,
            icon_color=palette.text_secondary
        )
        
        home_button = ft.IconButton(
            icon=self.get_icon('HOME'),
            tooltip="Go Home",
            on_click=self._go_home,
            icon_color=palette.text_secondary
        )
        
        # Refresh button
        refresh_button = ft.IconButton(
            icon=self.get_icon('REFRESH'),
            tooltip="Refresh",
            on_click=self._refresh_directory,
            icon_color=palette.text_secondary
        )
        
        # View mode toggle
        view_toggle = ft.IconButton(
            icon=self.get_icon('VIEW_LIST'),
            tooltip="Toggle View",
            on_click=self._toggle_view_mode,
            icon_color=palette.text_secondary
        )
        
        # Filter button
        filter_button = ft.IconButton(
            icon=self.get_icon('FILTER_LIST'),
            tooltip="Filter Options",
            on_click=self._show_filter_dialog,
            icon_color=palette.text_secondary
        )
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    # Navigation group
                    ft.Row(
                        controls=[back_button, forward_button, up_button, home_button],
                        spacing=spacing.xs
                    ),
                    ft.VerticalDivider(width=1, color=palette.borders),
                    # Action group
                    ft.Row(
                        controls=[refresh_button, view_toggle, filter_button],
                        spacing=spacing.xs
                    ),
                    # Spacer
                    ft.Container(expand=True),
                    # Selection info
                    self._create_selection_info()
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
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

    def _create_selection_info(self) -> ft.Control:
        """Create selection information display."""
        palette = self.get_palette()
        typography = self.get_typography()

        selected_count = len(self._selected_items)
        if selected_count == 0:
            return ft.Container()

        return ft.Container(
            content=ft.Text(
                f"{selected_count} selected",
                size=typography.body_small[0],
                color=palette.text_secondary,
                weight=ft.FontWeight.W_500
            ),
            bgcolor=palette.primary_variant,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=4
        )

    def _create_breadcrumb_bar(self) -> ft.Control:
        """Create breadcrumb navigation bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Build breadcrumb items
        breadcrumb_items = []
        path_parts = list(self._current_path.parts)

        for i, part in enumerate(path_parts):
            # Create path up to this part
            partial_path = Path(*path_parts[:i+1])

            # Create breadcrumb button
            if i == len(path_parts) - 1:
                # Current directory - not clickable
                breadcrumb_items.append(
                    ft.Text(
                        part,
                        size=typography.body_medium[0],
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_500
                    )
                )
            else:
                # Parent directory - clickable
                breadcrumb_items.append(
                    ft.TextButton(
                        text=part,
                        style=ft.ButtonStyle(
                            color=palette.text_secondary,
                            bgcolor=ft.Colors.TRANSPARENT,
                            overlay_color=palette.surface_variant,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4)
                        ),
                        on_click=lambda e, path=partial_path: self._navigate_to_path(path)
                    )
                )

            # Add separator
            if i < len(path_parts) - 1:
                breadcrumb_items.append(
                    ft.Icon(
                        self.get_icon('CHEVRON_RIGHT'),
                        size=16,
                        color=palette.text_tertiary
                    )
                )

        return ft.Container(
            content=ft.Row(
                controls=breadcrumb_items,
                spacing=spacing.xs,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            bgcolor=palette.background_secondary
        )

    def _create_file_list_container(self) -> ft.Control:
        """Create the main file list container."""
        palette = self.get_palette()

        if self._state == BrowserState.LOADING:
            return self._create_loading_indicator()
        elif self._state == BrowserState.ERROR:
            return self._create_error_display()
        else:
            return ft.Container(
                content=self._create_file_list(),
                expand=True,
                bgcolor=palette.background_primary
            )

    def _create_loading_indicator(self) -> ft.Control:
        """Create loading indicator."""
        palette = self.get_palette()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(
                        width=40,
                        height=40,
                        color=palette.primary
                    ),
                    ft.Text(
                        "Loading directory...",
                        size=typography.body_medium[0],
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_error_display(self) -> ft.Control:
        """Create error display."""
        palette = self.get_palette()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        self.get_icon('ERROR'),
                        size=48,
                        color=palette.error
                    ),
                    ft.Text(
                        "Error loading directory",
                        size=typography.body_large[0],
                        color=palette.text_primary,
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        "Unable to access the selected directory",
                        size=typography.body_medium[0],
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.ElevatedButton(
                        text="Retry",
                        icon=self.get_icon('REFRESH'),
                        on_click=self._refresh_directory,
                        style=ft.ButtonStyle(
                            bgcolor=palette.primary,
                            color=palette.text_primary
                        )
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_file_list(self) -> ft.Control:
        """Create the file and directory list."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Combine directories and files
        all_items = []

        # Add directories first
        for dir_item in self._directory_items:
            all_items.append(self._create_directory_item(dir_item))

        # Add files
        for file_item in self._file_items:
            all_items.append(self._create_file_item(file_item))

        if not all_items:
            return self._create_empty_directory_display()

        return ft.ListView(
            controls=all_items,
            spacing=1,
            padding=ft.padding.all(spacing.sm),
            expand=True
        )

    def _create_empty_directory_display(self) -> ft.Control:
        """Create display for empty directory."""
        palette = self.get_palette()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        self.get_icon('FOLDER_OPEN'),
                        size=64,
                        color=palette.text_tertiary
                    ),
                    ft.Text(
                        "This directory is empty",
                        size=typography.body_large[0],
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _create_directory_item(self, dir_item: DirectoryItem) -> ft.Control:
        """Create a directory list item."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Directory icon
        icon = ft.Icon(
            self.get_icon('FOLDER'),
            size=self.get_responsive_size(24),
            color=palette.primary if dir_item.is_accessible else palette.text_disabled
        )

        # Directory info
        name_text = ft.Text(
            dir_item.name,
            size=typography.body_medium[0],
            color=palette.text_primary if dir_item.is_accessible else palette.text_disabled,
            weight=ft.FontWeight.W_500,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True
        )

        item_count_text = ft.Text(
            f"{dir_item.item_count} items",
            size=typography.body_small[0],
            color=palette.text_secondary,
            width=80
        )

        modified_text = ft.Text(
            dir_item.modified_display,
            size=typography.body_small[0],
            color=palette.text_secondary,
            width=120
        )

        # Create container
        return ft.Container(
            content=ft.Row(
                controls=[
                    icon,
                    name_text,
                    item_count_text,
                    modified_text
                ],
                spacing=spacing.md,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=palette.surface_variant if dir_item.is_selected else ft.Colors.TRANSPARENT,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            border_radius=4,
            on_click=lambda e, path=dir_item.path: self._on_directory_click(path),
            on_long_press=lambda e, item=dir_item: self._on_item_long_press(item)
        )

    def _create_file_item(self, file_item: FileItem) -> ft.Control:
        """Create a file list item."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # File icon based on format
        icon_name = self._get_file_icon(file_item)
        icon_color = palette.primary if file_item.is_valid else palette.error

        icon = ft.Icon(
            icon_name,
            size=self.get_responsive_size(24),
            color=icon_color
        )

        # File info
        name_text = ft.Text(
            file_item.name,
            size=typography.body_medium[0],
            color=palette.text_primary if file_item.is_valid else palette.text_disabled,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True
        )

        size_text = ft.Text(
            file_item.size_display,
            size=typography.body_small[0],
            color=palette.text_secondary,
            width=80
        )

        modified_text = ft.Text(
            file_item.modified_display,
            size=typography.body_small[0],
            color=palette.text_secondary,
            width=120
        )

        # Selection checkbox for multi-select mode
        checkbox = None
        if self._mode in [BrowserMode.MULTIPLE_FILES, BrowserMode.MIXED]:
            checkbox = ft.Checkbox(
                value=file_item.is_selected,
                on_change=lambda e, item=file_item: self._on_file_selection_change(item, e.control.value)
            )

        # Create row controls
        row_controls = [icon, name_text, size_text, modified_text]
        if checkbox:
            row_controls.insert(-1, checkbox)

        # Create container
        return ft.Container(
            content=ft.Row(
                controls=row_controls,
                spacing=spacing.md,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=palette.surface_variant if file_item.is_selected else ft.Colors.TRANSPARENT,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            border_radius=4,
            on_click=lambda e, item=file_item: self._on_file_click(item),
            on_long_press=lambda e, item=file_item: self._on_item_long_press(item)
        )

    def _create_status_bar(self) -> ft.Control:
        """Create status bar with directory information."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Count items
        total_files = len(self._file_items)
        total_dirs = len(self._directory_items)
        selected_count = len(self._selected_items)

        # Status text
        status_parts = []
        if total_dirs > 0:
            status_parts.append(f"{total_dirs} folders")
        if total_files > 0:
            status_parts.append(f"{total_files} files")
        if selected_count > 0:
            status_parts.append(f"{selected_count} selected")

        status_text = ", ".join(status_parts) if status_parts else "Empty directory"

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        status_text,
                        size=typography.body_small[0],
                        color=palette.text_secondary
                    ),
                    ft.Container(expand=True),
                    # Action buttons for selected items
                    self._create_action_buttons() if selected_count > 0 else ft.Container()
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            border_radius=ft.border_radius.only(
                bottom_left=self.get_responsive_size(8),
                bottom_right=self.get_responsive_size(8)
            )
        )

    def _create_action_buttons(self) -> ft.Control:
        """Create action buttons for selected items."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        select_button = ft.ElevatedButton(
            text="Select Files",
            icon=self.get_icon('CHECK'),
            on_click=self._confirm_selection,
            style=ft.ButtonStyle(
                bgcolor=palette.primary,
                color=palette.text_primary
            )
        )

        clear_button = ft.TextButton(
            text="Clear",
            icon=self.get_icon('CLEAR'),
            on_click=self._clear_selection,
            style=ft.ButtonStyle(
                color=palette.text_secondary
            )
        )

        return ft.Row(
            controls=[clear_button, select_button],
            spacing=spacing.sm
        )

    # Event Handlers
    def _on_directory_click(self, path: Path) -> None:
        """Handle directory click."""
        try:
            self._navigate_to_path(path)
        except Exception as e:
            self._logger.error(f"Error navigating to directory {path}: {e}")
            self._show_error_message(f"Cannot access directory: {e}")

    def _on_file_click(self, file_item: FileItem) -> None:
        """Handle file click."""
        if self._mode == BrowserMode.SINGLE_FILE:
            # Single file mode - select this file only
            self._selected_items.clear()
            self._selected_items.add(file_item.path)
            file_item.is_selected = True
            self._update_file_selection_display()
            self._confirm_selection()
        else:
            # Multi-select mode - toggle selection
            self._toggle_file_selection(file_item)

    def _on_file_selection_change(self, file_item: FileItem, selected: bool) -> None:
        """Handle file selection checkbox change."""
        if selected:
            self._selected_items.add(file_item.path)
            file_item.is_selected = True
        else:
            self._selected_items.discard(file_item.path)
            file_item.is_selected = False

        self._update_file_selection_display()

        # Notify selection change
        if self._on_selection_changed:
            selected_files = [item for item in self._file_items if item.is_selected]
            self._on_selection_changed(selected_files)

    def _on_item_long_press(self, item: Union[FileItem, DirectoryItem]) -> None:
        """Handle item long press for context menu."""
        # TODO: Implement context menu
        pass

    def _toggle_file_selection(self, file_item: FileItem) -> None:
        """Toggle file selection state."""
        if file_item.path in self._selected_items:
            self._selected_items.discard(file_item.path)
            file_item.is_selected = False
        else:
            self._selected_items.add(file_item.path)
            file_item.is_selected = True

        self._update_file_selection_display()

        # Notify selection change
        if self._on_selection_changed:
            selected_files = [item for item in self._file_items if item.is_selected]
            self._on_selection_changed(selected_files)

    def _update_file_selection_display(self) -> None:
        """Update the display to reflect current selection."""
        # Update file items selection state
        for file_item in self._file_items:
            file_item.is_selected = file_item.path in self._selected_items

        # Rebuild the UI to reflect changes
        if self._is_built:
            self.content = self.build()
            self.update()

    # Navigation Methods
    def _navigate_to_path(self, path: Path) -> None:
        """Navigate to specified path."""
        try:
            if not path.exists() or not path.is_dir():
                raise FileNotFoundError(f"Directory not found: {path}")

            # Update navigation history
            if self._history_index < len(self._navigation_history) - 1:
                # Remove forward history if we're navigating from middle
                self._navigation_history = self._navigation_history[:self._history_index + 1]

            self._navigation_history.append(path)
            self._history_index = len(self._navigation_history) - 1

            # Update current path
            self._current_path = path

            # Clear selection
            self._selected_items.clear()

            # Load directory
            self._load_directory_async()

            # Notify directory change
            if self._on_directory_changed:
                self._on_directory_changed(path)

        except Exception as e:
            self._logger.error(f"Error navigating to {path}: {e}")
            self._show_error_message(f"Cannot access directory: {e}")

    def _go_back(self, e=None) -> None:
        """Navigate back in history."""
        if self._history_index > 0:
            self._history_index -= 1
            path = self._navigation_history[self._history_index]
            self._current_path = path
            self._selected_items.clear()
            self._load_directory_async()

            if self._on_directory_changed:
                self._on_directory_changed(path)

    def _go_forward(self, e=None) -> None:
        """Navigate forward in history."""
        if self._history_index < len(self._navigation_history) - 1:
            self._history_index += 1
            path = self._navigation_history[self._history_index]
            self._current_path = path
            self._selected_items.clear()
            self._load_directory_async()

            if self._on_directory_changed:
                self._on_directory_changed(path)

    def _go_up(self, e=None) -> None:
        """Navigate to parent directory."""
        parent = self._current_path.parent
        if parent != self._current_path:
            self._navigate_to_path(parent)

    def _go_home(self, e=None) -> None:
        """Navigate to home directory."""
        self._navigate_to_path(Path.home())

    def _refresh_directory(self, e=None) -> None:
        """Refresh current directory."""
        self._selected_items.clear()
        self._load_directory_async()

    # Action Methods
    def _confirm_selection(self, e=None) -> None:
        """Confirm file selection."""
        selected_files = [item for item in self._file_items if item.is_selected]

        if selected_files and self._on_files_selected:
            self._on_files_selected(selected_files)

    def _clear_selection(self, e=None) -> None:
        """Clear all selections."""
        self._selected_items.clear()
        for file_item in self._file_items:
            file_item.is_selected = False

        self._update_file_selection_display()

        if self._on_selection_changed:
            self._on_selection_changed([])

    def _toggle_view_mode(self, e=None) -> None:
        """Toggle between list and grid view modes."""
        # TODO: Implement grid view mode
        pass

    def _show_filter_dialog(self, e=None) -> None:
        """Show filter options dialog."""
        # TODO: Implement filter dialog
        pass

    # Directory Loading Methods
    def _load_directory_async(self) -> None:
        """Load directory contents asynchronously."""
        try:
            # Check if there's an event loop running
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._load_directory())
        except RuntimeError:
            # No event loop running, skip async loading
            # This can happen during testing or initialization
            self._logger.debug("No event loop available for async directory loading")
            pass

    async def _load_directory(self) -> None:
        """Load directory contents."""
        try:
            self._state = BrowserState.LOADING
            if self._is_built:
                self.content = self.build()
                self.update()

            # Load directory contents
            await self._scan_directory()

            self._state = BrowserState.READY
            if self._is_built:
                self.content = self.build()
                self.update()

        except Exception as e:
            self._logger.error(f"Error loading directory {self._current_path}: {e}")
            self._state = BrowserState.ERROR
            if self._is_built:
                self.content = self.build()
                self.update()

    async def _scan_directory(self) -> None:
        """Scan directory for files and subdirectories."""
        self._file_items.clear()
        self._directory_items.clear()

        try:
            # Get directory entries
            entries = list(self._current_path.iterdir())

            for entry in entries:
                try:
                    # Skip hidden files if not configured to show them
                    if not self._filter_config.show_hidden_files and entry.name.startswith('.'):
                        continue

                    # Get file stats
                    stat_info = entry.stat()
                    modified = datetime.fromtimestamp(stat_info.st_mtime)

                    if entry.is_dir():
                        # Process directory
                        try:
                            item_count = len(list(entry.iterdir()))
                        except PermissionError:
                            item_count = 0

                        dir_item = DirectoryItem(
                            path=entry,
                            name=entry.name,
                            item_count=item_count,
                            modified=modified,
                            is_accessible=os.access(entry, os.R_OK),
                            modified_display=self._format_date(modified)
                        )
                        self._directory_items.append(dir_item)

                    elif entry.is_file():
                        # Process file
                        file_size = stat_info.st_size

                        # Check if file passes filters
                        if not self._passes_file_filter(entry, file_size):
                            continue

                        # Detect format
                        format_type = None
                        is_valid = True
                        try:
                            format_type = self._format_detector.detect_format(entry)[0]
                            # Validate file
                            validation_result = self._file_validator.validate_file(entry)
                            is_valid = validation_result.is_valid
                        except Exception:
                            is_valid = False

                        file_item = FileItem(
                            path=entry,
                            name=entry.name,
                            size=file_size,
                            modified=modified,
                            is_valid=is_valid,
                            format_type=format_type,
                            icon=self._get_file_icon_name(entry),
                            size_display=self._format_file_size(file_size),
                            modified_display=self._format_date(modified)
                        )
                        self._file_items.append(file_item)

                except (PermissionError, OSError) as e:
                    self._logger.warning(f"Cannot access {entry}: {e}")
                    continue

            # Sort items
            self._directory_items.sort(key=lambda x: x.name.lower())
            self._file_items.sort(key=lambda x: x.name.lower())

        except Exception as e:
            self._logger.error(f"Error scanning directory {self._current_path}: {e}")
            raise

    def _passes_file_filter(self, file_path: Path, file_size: int) -> bool:
        """Check if file passes current filters."""
        # Size filter
        max_size_bytes = self._filter_config.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return False

        # Extension filter
        if self._filter_config.file_extensions:
            if file_path.suffix.lower() not in self._filter_config.file_extensions:
                return False

        # Name filter
        if self._filter_config.name_filter:
            if self._filter_config.name_filter.lower() not in file_path.name.lower():
                return False

        # Date filter
        if self._filter_config.date_filter_start or self._filter_config.date_filter_end:
            try:
                file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
                if self._filter_config.date_filter_start and file_modified < self._filter_config.date_filter_start:
                    return False
                if self._filter_config.date_filter_end and file_modified > self._filter_config.date_filter_end:
                    return False
            except OSError:
                return False

        return True

    # Utility Methods
    def _get_file_icon(self, file_item: FileItem) -> str:
        """Get appropriate icon for file item."""
        if file_item.format_type == DocumentFormat.PDF:
            return self.get_icon('PICTURE_AS_PDF')
        elif file_item.format_type == DocumentFormat.DOCX:
            return self.get_icon('DESCRIPTION')
        elif file_item.format_type == DocumentFormat.TXT:
            return self.get_icon('TEXT_SNIPPET')
        elif file_item.format_type == DocumentFormat.HTML:
            return self.get_icon('WEB')
        elif file_item.format_type == DocumentFormat.MARKDOWN:
            return self.get_icon('ARTICLE')
        else:
            return self.get_icon('INSERT_DRIVE_FILE')

    def _get_file_icon_name(self, file_path: Path) -> str:
        """Get icon name for file based on extension."""
        ext = file_path.suffix.lower()
        if ext == '.pdf':
            return 'PICTURE_AS_PDF'
        elif ext in ['.docx', '.doc']:
            return 'DESCRIPTION'
        elif ext == '.txt':
            return 'TEXT_SNIPPET'
        elif ext in ['.html', '.htm']:
            return 'WEB'
        elif ext in ['.md', '.markdown']:
            return 'ARTICLE'
        else:
            return 'INSERT_DRIVE_FILE'

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        if i == 0:
            return f"{int(size)} {size_names[i]}"
        else:
            return f"{size:.1f} {size_names[i]}"

    def _format_date(self, date: datetime) -> str:
        """Format date for display."""
        now = datetime.now()
        diff = now - date

        if diff.days == 0:
            # Today - show time
            return date.strftime("%H:%M")
        elif diff.days == 1:
            # Yesterday
            return "Yesterday"
        elif diff.days < 7:
            # This week - show day name
            return date.strftime("%A")
        elif diff.days < 365:
            # This year - show month and day
            return date.strftime("%b %d")
        else:
            # Older - show year
            return date.strftime("%b %d, %Y")

    def _show_error_message(self, message: str) -> None:
        """Show error message to user."""
        # TODO: Implement error dialog or toast notification
        self._logger.error(message)

    # Public API Methods
    def get_selected_files(self) -> List[FileItem]:
        """Get currently selected files."""
        return [item for item in self._file_items if item.is_selected]

    def get_current_path(self) -> Path:
        """Get current directory path."""
        return self._current_path

    def set_filter_config(self, config: FileFilterConfig) -> None:
        """Update filter configuration."""
        self._filter_config = config
        self._refresh_directory()

    def navigate_to(self, path: Path) -> None:
        """Navigate to specified path."""
        self._navigate_to_path(path)

    def refresh(self) -> None:
        """Refresh current directory."""
        self._refresh_directory()

    def clear_selection(self) -> None:
        """Clear all file selections."""
        self._clear_selection()

    def select_all_files(self) -> None:
        """Select all valid files in current directory."""
        for file_item in self._file_items:
            if file_item.is_valid:
                self._selected_items.add(file_item.path)
                file_item.is_selected = True

        self._update_file_selection_display()

        if self._on_selection_changed:
            selected_files = [item for item in self._file_items if item.is_selected]
            self._on_selection_changed(selected_files)

    def get_directory_stats(self) -> Dict[str, Any]:
        """Get statistics about current directory."""
        return {
            'total_files': len(self._file_items),
            'total_directories': len(self._directory_items),
            'selected_files': len(self._selected_items),
            'valid_files': len([item for item in self._file_items if item.is_valid]),
            'current_path': str(self._current_path),
            'state': self._state.value
        }
