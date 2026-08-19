"""
Module: upload_dropzone_ui
Description: Drag-and-drop interface for document upload with visual feedback and progress indicators.
            Provides responsive upload zone with file validation, format detection, progress tracking,
            and seamless integration with document processing pipeline. Features modern UI/UX with
            theme-aware styling, accessibility compliance, and cross-platform compatibility.
Phase: 3
Location: /src/modules/ui/document_upload_ui/upload_dropzone_ui/upload_dropzone_ui.py
"""

# Standard library imports
import asyncio
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from datetime import datetime, timezone

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


class DropzoneState(Enum):
    """Upload dropzone states."""
    IDLE = "idle"
    DRAG_OVER = "drag_over"
    UPLOADING = "uploading"
    SUCCESS = "success"
    ERROR = "error"
    DISABLED = "disabled"


class UploadStatus(Enum):
    """File upload status."""
    PENDING = "pending"
    VALIDATING = "validating"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FileUploadItem:
    """Represents a file being uploaded."""
    file_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: Optional[Path] = None
    filename: str = ""
    file_size: int = 0
    mime_type: str = ""
    format_type: Optional[DocumentFormat] = None
    status: UploadStatus = UploadStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    validation_result: Optional[FileValidationResult] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DropzoneConfig:
    """Configuration for upload dropzone."""
    max_file_size_mb: int = 100
    allowed_formats: List[DocumentFormat] = field(default_factory=lambda: [
        DocumentFormat.PDF, DocumentFormat.DOCX, DocumentFormat.TXT,
        DocumentFormat.HTML, DocumentFormat.MARKDOWN
    ])
    max_files: int = 10
    enable_multiple_files: bool = True
    auto_upload: bool = True
    show_file_preview: bool = True
    enable_drag_drop: bool = True


class UploadDropzoneUI(ThemeAwareUserControl):
    """
    Responsive drag-and-drop upload zone with comprehensive file handling.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Drag-and-drop file upload with visual feedback
    - File validation and format detection
    - Real-time upload progress tracking
    - Multi-file upload support with queue management
    - Theme-aware styling with accessibility compliance
    - Error handling and user feedback
    - Integration with document processing pipeline
    """
    
    def __init__(self,
                 config: Optional[DropzoneConfig] = None,
                 on_files_selected: Optional[Callable[[List[FileUploadItem]], None]] = None,
                 on_upload_progress: Optional[Callable[[str, float], None]] = None,
                 on_upload_complete: Optional[Callable[[FileUploadItem], None]] = None,
                 on_upload_error: Optional[Callable[[FileUploadItem, str], None]] = None,
                 **kwargs):
        """
        Initialize the UploadDropzoneUI component.
        
        Args:
            config: Dropzone configuration
            on_files_selected: Callback when files are selected
            on_upload_progress: Callback for upload progress updates
            on_upload_complete: Callback when upload completes
            on_upload_error: Callback when upload fails
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration and callbacks
        self._config = config or DropzoneConfig()
        self._on_files_selected = on_files_selected
        self._on_upload_progress = on_upload_progress
        self._on_upload_complete = on_upload_complete
        self._on_upload_error = on_upload_error
        
        # Component state
        self._state = DropzoneState.IDLE
        self._upload_items: Dict[str, FileUploadItem] = {}
        self._is_built = False
        
        # Core components
        self._logger = get_logger(__name__)
        self._format_detector = FormatDetector()
        self._file_validator = FileValidator()
        
        # UI components
        self._dropzone_container: Optional[ft.Container] = None
        self._upload_list_container: Optional[ft.Container] = None
        self._status_text: Optional[ft.Text] = None
        self._progress_ring: Optional[ft.ProgressRing] = None
        
        self._logger.debug("UploadDropzoneUI initialized")
    
    def build(self) -> ft.Control:
        """Build the responsive upload dropzone component."""
        if self._is_built:
            return self.content
            
        try:
            self._build_component()
            self._is_built = True
            self._logger.debug("UploadDropzoneUI built successfully")
            return self.content
            
        except Exception as e:
            self._logger.error(f"Failed to build UploadDropzoneUI: {e}")
            return self._build_error_state()
    
    def _build_component(self) -> None:
        """Build the main dropzone component."""
        # Get responsive layout manager
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()
        
        # Create dropzone area
        self._dropzone_container = self._create_dropzone_area()
        
        # Create upload list
        self._upload_list_container = self._create_upload_list()
        
        # Create main layout
        main_content = ft.Column(
            controls=[
                self._dropzone_container,
                self._upload_list_container
            ],
            spacing=responsive_manager.get_breakpoint_value(
                mobile=16, tablet=20, desktop=24, large=28
            ),
            expand=True
        )
        
        # Create responsive container
        self.content = self.create_responsive_container(
            content=main_content,
            padding=responsive_manager.get_breakpoint_value(
                mobile=16, tablet=20, desktop=24, large=32
            )
        )
    
    def _create_dropzone_area(self) -> ft.Container:
        """Create the main dropzone area."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()
        
        # Responsive dimensions
        dropzone_height = responsive_manager.get_breakpoint_value(
            mobile=200, tablet=250, desktop=300, large=350
        )
        
        # Create upload icon
        upload_icon = ft.Icon(
            name=icons.UPLOAD,
            size=responsive_manager.get_breakpoint_value(
                mobile=48, tablet=56, desktop=64, large=72
            ),
            color=palette.text_secondary
        )
        
        # Create status text
        self._status_text = ft.Text(
            value=self._get_status_text(),
            size=typography.body_large[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary,
            text_align=ft.TextAlign.CENTER
        )
        
        # Create subtitle text
        subtitle_text = ft.Text(
            value=self._get_subtitle_text(),
            size=typography.body_medium[0],
            color=palette.text_secondary,
            text_align=ft.TextAlign.CENTER
        )
        
        # Create progress ring (initially hidden)
        self._progress_ring = ft.ProgressRing(
            visible=False,
            width=responsive_manager.get_breakpoint_value(
                mobile=32, tablet=36, desktop=40, large=44
            ),
            height=responsive_manager.get_breakpoint_value(
                mobile=32, tablet=36, desktop=40, large=44
            ),
            color=palette.primary
        )
        
        # Create dropzone content
        dropzone_content = ft.Column(
            controls=[
                upload_icon,
                self._status_text,
                subtitle_text,
                self._progress_ring
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.medium
        )
        
        # Create dropzone container
        return ft.Container(
            content=dropzone_content,
            height=dropzone_height,
            border=ft.border.all(
                width=2,
                color=self._get_border_color()
            ),
            border_radius=spacing.medium,
            bgcolor=self._get_background_color(),
            padding=spacing.large,
            alignment=ft.alignment.center,
            on_click=self._handle_click_upload,
            animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT)
        )

    def _create_upload_list(self) -> ft.Container:
        """Create the upload list container."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[],
                spacing=spacing.small
            ),
            visible=False,
            padding=spacing.medium,
            border_radius=spacing.small,
            bgcolor=palette.surface_variant
        )

    def _get_status_text(self) -> str:
        """Get status text based on current state."""
        if self._state == DropzoneState.IDLE:
            return "Drop files here or click to browse"
        elif self._state == DropzoneState.DRAG_OVER:
            return "Drop files to upload"
        elif self._state == DropzoneState.UPLOADING:
            return "Uploading files..."
        elif self._state == DropzoneState.SUCCESS:
            return "Upload completed successfully"
        elif self._state == DropzoneState.ERROR:
            return "Upload failed"
        elif self._state == DropzoneState.DISABLED:
            return "Upload disabled"
        return "Ready to upload"

    def _get_subtitle_text(self) -> str:
        """Get subtitle text with format and size information."""
        formats = ", ".join([fmt.value.upper() for fmt in self._config.allowed_formats])
        max_size = self._config.max_file_size_mb
        return f"Supported formats: {formats} • Max size: {max_size}MB"

    def _get_border_color(self) -> str:
        """Get border color based on current state."""
        palette = self.get_palette()

        if self._state == DropzoneState.IDLE:
            return palette.outline
        elif self._state == DropzoneState.DRAG_OVER:
            return palette.primary
        elif self._state == DropzoneState.UPLOADING:
            return palette.primary
        elif self._state == DropzoneState.SUCCESS:
            return palette.success
        elif self._state == DropzoneState.ERROR:
            return palette.error
        elif self._state == DropzoneState.DISABLED:
            return palette.text_disabled
        return palette.outline

    def _get_background_color(self) -> str:
        """Get background color based on current state."""
        palette = self.get_palette()

        if self._state == DropzoneState.IDLE:
            return palette.surface
        elif self._state == DropzoneState.DRAG_OVER:
            return palette.primary + "10"  # 10% opacity
        elif self._state == DropzoneState.UPLOADING:
            return palette.surface
        elif self._state == DropzoneState.SUCCESS:
            return palette.success + "10"  # 10% opacity
        elif self._state == DropzoneState.ERROR:
            return palette.error + "10"  # 10% opacity
        elif self._state == DropzoneState.DISABLED:
            return palette.surface_variant
        return palette.surface

    def _build_error_state(self) -> ft.Control:
        """Build error state when component fails to initialize."""
        palette = self.get_palette()
        typography = self.get_typography()
        icons = self.get_icons()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=icons.ERROR,
                        size=48,
                        color=palette.error
                    ),
                    ft.Text(
                        value="Upload component failed to load",
                        size=typography.body_large[0],
                        color=palette.error,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16
            ),
            padding=32,
            alignment=ft.alignment.center
        )

    async def _handle_click_upload(self, e) -> None:
        """Handle click to open file picker."""
        if self._state == DropzoneState.DISABLED:
            return

        try:
            # Create file picker
            file_picker = ft.FilePicker(
                on_result=self._handle_file_picker_result
            )

            # Add to page and open
            if self.page:
                self.page.overlay.append(file_picker)
                self.page.update()

                # Configure file picker
                allowed_extensions = []
                for fmt in self._config.allowed_formats:
                    if fmt == DocumentFormat.PDF:
                        allowed_extensions.append("pdf")
                    elif fmt == DocumentFormat.DOCX:
                        allowed_extensions.extend(["docx", "doc"])
                    elif fmt == DocumentFormat.TXT:
                        allowed_extensions.append("txt")
                    elif fmt == DocumentFormat.HTML:
                        allowed_extensions.extend(["html", "htm"])
                    elif fmt == DocumentFormat.MARKDOWN:
                        allowed_extensions.extend(["md", "markdown"])

                # Open file picker
                await file_picker.pick_files(
                    allow_multiple=self._config.enable_multiple_files,
                    allowed_extensions=allowed_extensions
                )

        except Exception as ex:
            self._logger.error(f"Failed to open file picker: {ex}")
            self._show_error("Failed to open file browser")

    def _handle_file_picker_result(self, e: ft.FilePickerResultEvent) -> None:
        """Handle file picker result."""
        if not e.files:
            return

        try:
            # Convert picked files to upload items
            upload_items = []
            for file in e.files:
                if len(self._upload_items) >= self._config.max_files:
                    self._show_error(f"Maximum {self._config.max_files} files allowed")
                    break

                upload_item = FileUploadItem(
                    file_path=Path(file.path) if file.path else None,
                    filename=file.name,
                    file_size=file.size or 0
                )

                upload_items.append(upload_item)
                self._upload_items[upload_item.file_id] = upload_item

            # Process selected files
            if upload_items:
                self._process_selected_files(upload_items)

        except Exception as ex:
            self._logger.error(f"Failed to process selected files: {ex}")
            self._show_error("Failed to process selected files")

    def _process_selected_files(self, upload_items: List[FileUploadItem]) -> None:
        """Process selected files for upload."""
        try:
            # Update UI state
            self._update_state(DropzoneState.UPLOADING)
            self._update_upload_list()

            # Notify callback
            if self._on_files_selected:
                self._on_files_selected(upload_items)

            # Start validation and upload process
            if self._config.auto_upload:
                asyncio.create_task(self._start_upload_process(upload_items))

        except Exception as e:
            self._logger.error(f"Failed to process selected files: {e}")
            self._show_error("Failed to process files")

    async def _start_upload_process(self, upload_items: List[FileUploadItem]) -> None:
        """Start the upload process for selected files."""
        try:
            for item in upload_items:
                await self._process_upload_item(item)

        except Exception as e:
            self._logger.error(f"Upload process failed: {e}")
            self._update_state(DropzoneState.ERROR)

    async def _process_upload_item(self, item: FileUploadItem) -> None:
        """Process individual upload item."""
        try:
            # Update item status
            item.status = UploadStatus.VALIDATING
            item.updated_at = datetime.now(timezone.utc)
            self._update_upload_item_ui(item)

            # Validate file
            if item.file_path and item.file_path.exists():
                validation_result = self._file_validator.validate_file(
                    item.file_path, check_integrity=True
                )
                item.validation_result = validation_result

                if not validation_result.is_valid:
                    item.status = UploadStatus.FAILED
                    item.error_message = "File validation failed"
                    self._update_upload_item_ui(item)
                    if self._on_upload_error:
                        self._on_upload_error(item, item.error_message)
                    return

                # Detect format
                format_result = self._format_detector.detect_format(item.file_path)
                item.format_type = format_result.format_type
                item.mime_type = getattr(format_result, 'mime_type', 'application/octet-stream')

                # Check file size
                if item.file_size > self._config.max_file_size_mb * 1024 * 1024:
                    item.status = UploadStatus.FAILED
                    item.error_message = f"File size exceeds {self._config.max_file_size_mb}MB limit"
                    self._update_upload_item_ui(item)
                    if self._on_upload_error:
                        self._on_upload_error(item, item.error_message)
                    return

                # Check format
                if item.format_type not in self._config.allowed_formats:
                    item.status = UploadStatus.FAILED
                    item.error_message = "Unsupported file format"
                    self._update_upload_item_ui(item)
                    if self._on_upload_error:
                        self._on_upload_error(item, item.error_message)
                    return

            # Start upload
            item.status = UploadStatus.UPLOADING
            self._update_upload_item_ui(item)

            # Simulate upload progress
            await self._simulate_upload_progress(item)

            # Complete upload
            item.status = UploadStatus.COMPLETED
            item.progress = 100.0
            item.updated_at = datetime.now(timezone.utc)
            self._update_upload_item_ui(item)

            if self._on_upload_complete:
                self._on_upload_complete(item)

        except Exception as e:
            self._logger.error(f"Failed to process upload item {item.file_id}: {e}")
            item.status = UploadStatus.FAILED
            item.error_message = str(e)
            self._update_upload_item_ui(item)
            if self._on_upload_error:
                self._on_upload_error(item, str(e))

    async def _simulate_upload_progress(self, item: FileUploadItem) -> None:
        """Simulate upload progress for demonstration."""
        try:
            # Simulate upload progress in chunks
            for progress in range(0, 101, 10):
                item.progress = float(progress)
                self._update_upload_item_ui(item)

                if self._on_upload_progress:
                    self._on_upload_progress(item.file_id, item.progress)

                # Simulate processing time
                await asyncio.sleep(0.1)

        except Exception as e:
            self._logger.error(f"Upload progress simulation failed: {e}")

    def _update_state(self, new_state: DropzoneState) -> None:
        """Update dropzone state and refresh UI."""
        if self._state != new_state:
            self._state = new_state
            self._update_dropzone_ui()

    def _update_dropzone_ui(self) -> None:
        """Update dropzone UI based on current state."""
        if not self._dropzone_container or not self._status_text or not self._progress_ring:
            return

        try:
            # Update status text
            self._status_text.value = self._get_status_text()
            self._status_text.color = self._get_text_color()

            # Update border and background
            self._dropzone_container.border = ft.border.all(
                width=2,
                color=self._get_border_color()
            )
            self._dropzone_container.bgcolor = self._get_background_color()

            # Update progress ring visibility
            self._progress_ring.visible = (self._state == DropzoneState.UPLOADING)

            # Update the UI
            if self.page:
                self.update()

        except Exception as e:
            self._logger.error(f"Failed to update dropzone UI: {e}")

    def _get_text_color(self) -> str:
        """Get text color based on current state."""
        palette = self.get_palette()

        if self._state == DropzoneState.ERROR:
            return palette.error
        elif self._state == DropzoneState.SUCCESS:
            return palette.success
        elif self._state == DropzoneState.DISABLED:
            return palette.text_disabled
        return palette.text_primary

    def _update_upload_list(self) -> None:
        """Update the upload list display."""
        if not self._upload_list_container:
            return

        try:
            # Show upload list if there are items
            has_items = len(self._upload_items) > 0
            self._upload_list_container.visible = has_items

            if has_items:
                # Create upload item controls
                upload_controls = []
                for item in self._upload_items.values():
                    upload_control = self._create_upload_item_control(item)
                    upload_controls.append(upload_control)

                # Update container content
                self._upload_list_container.content = ft.Column(
                    controls=upload_controls,
                    spacing=self.get_spacing().small
                )

            # Update the UI
            if self.page:
                self.update()

        except Exception as e:
            self._logger.error(f"Failed to update upload list: {e}")

    def _create_upload_item_control(self, item: FileUploadItem) -> ft.Control:
        """Create control for individual upload item."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # Status icon
        status_icon = self._get_status_icon(item.status)
        status_color = self._get_status_color(item.status)

        # File info
        file_info = ft.Column(
            controls=[
                ft.Text(
                    value=item.filename,
                    size=typography.body_medium[0],
                    weight=ft.FontWeight.W_500,
                    color=palette.text_primary,
                    overflow=ft.TextOverflow.ELLIPSIS
                ),
                ft.Text(
                    value=self._format_file_size(item.file_size),
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ],
            spacing=spacing.xs,
            expand=True
        )

        # Progress indicator
        progress_control = self._create_progress_control(item)

        # Action buttons
        action_buttons = self._create_action_buttons(item)

        # Main row
        main_row = ft.Row(
            controls=[
                ft.Icon(
                    name=status_icon,
                    size=responsive_manager.get_breakpoint_value(
                        mobile=20, tablet=22, desktop=24, large=26
                    ),
                    color=status_color
                ),
                file_info,
                progress_control,
                action_buttons
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.medium
        )

        # Error message (if any)
        error_message = None
        if item.error_message:
            error_message = ft.Text(
                value=item.error_message,
                size=typography.body_small[0],
                color=palette.error,
                italic=True
            )

        # Container content
        container_content = ft.Column(
            controls=[main_row] + ([error_message] if error_message else []),
            spacing=spacing.xs
        )

        return ft.Container(
            content=container_content,
            padding=spacing.medium,
            border_radius=spacing.small,
            bgcolor=palette.surface,
            border=ft.border.all(1, palette.outline)
        )

    def _get_status_icon(self, status: UploadStatus) -> str:
        """Get icon for upload status."""
        icons = self.get_icons()

        if status == UploadStatus.PENDING:
            return icons.SCHEDULE
        elif status == UploadStatus.VALIDATING:
            return icons.SEARCH
        elif status == UploadStatus.UPLOADING:
            return icons.UPLOAD
        elif status == UploadStatus.PROCESSING:
            return icons.SETTINGS
        elif status == UploadStatus.COMPLETED:
            return icons.CHECK_CIRCLE
        elif status == UploadStatus.FAILED:
            return icons.ERROR
        elif status == UploadStatus.CANCELLED:
            return icons.CANCEL
        return icons.DESCRIPTION

    def _get_status_color(self, status: UploadStatus) -> str:
        """Get color for upload status."""
        palette = self.get_palette()

        if status == UploadStatus.PENDING:
            return palette.text_secondary
        elif status == UploadStatus.VALIDATING:
            return palette.info
        elif status == UploadStatus.UPLOADING:
            return palette.primary
        elif status == UploadStatus.PROCESSING:
            return palette.primary
        elif status == UploadStatus.COMPLETED:
            return palette.success
        elif status == UploadStatus.FAILED:
            return palette.error
        elif status == UploadStatus.CANCELLED:
            return palette.text_disabled
        return palette.text_secondary

    def _create_progress_control(self, item: FileUploadItem) -> ft.Control:
        """Create progress control for upload item."""
        palette = self.get_palette()
        typography = self.get_typography()

        if item.status in [UploadStatus.UPLOADING, UploadStatus.PROCESSING]:
            return ft.Column(
                controls=[
                    ft.ProgressBar(
                        value=item.progress / 100.0,
                        width=100,
                        color=palette.primary,
                        bgcolor=palette.surface_variant
                    ),
                    ft.Text(
                        value=f"{item.progress:.0f}%",
                        size=typography.body_small[0],
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        else:
            return ft.Container(width=100)  # Placeholder for alignment

    def _create_action_buttons(self, item: FileUploadItem) -> ft.Control:
        """Create action buttons for upload item."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        icons = self.get_icons()

        button_size = responsive_manager.get_breakpoint_value(
            mobile=32, tablet=36, desktop=40, large=44
        )

        if item.status == UploadStatus.UPLOADING:
            # Cancel button
            return ft.IconButton(
                icon=icons.CANCEL,
                icon_size=20,
                width=button_size,
                height=button_size,
                on_click=lambda e: self._cancel_upload(item.file_id),
                tooltip="Cancel upload"
            )
        elif item.status == UploadStatus.FAILED:
            # Retry button
            return ft.IconButton(
                icon=icons.REFRESH,
                icon_size=20,
                width=button_size,
                height=button_size,
                on_click=lambda e: self._retry_upload(item.file_id),
                tooltip="Retry upload"
            )
        else:
            # Remove button
            return ft.IconButton(
                icon=icons.DELETE,
                icon_size=20,
                width=button_size,
                height=button_size,
                on_click=lambda e: self._remove_upload_item(item.file_id),
                tooltip="Remove file"
            )

    def _update_upload_item_ui(self, item: FileUploadItem) -> None:
        """Update UI for specific upload item."""
        try:
            item.updated_at = datetime.now(timezone.utc)
            self._update_upload_list()

        except Exception as e:
            self._logger.error(f"Failed to update upload item UI: {e}")

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

    def _cancel_upload(self, file_id: str) -> None:
        """Cancel upload for specific file."""
        try:
            if file_id in self._upload_items:
                item = self._upload_items[file_id]
                item.status = UploadStatus.CANCELLED
                item.updated_at = datetime.now(timezone.utc)
                self._update_upload_item_ui(item)

                self._logger.info(f"Upload cancelled for file: {item.filename}")

        except Exception as e:
            self._logger.error(f"Failed to cancel upload: {e}")

    def _retry_upload(self, file_id: str) -> None:
        """Retry upload for specific file."""
        try:
            if file_id in self._upload_items:
                item = self._upload_items[file_id]
                item.status = UploadStatus.PENDING
                item.progress = 0.0
                item.error_message = None
                item.updated_at = datetime.now(timezone.utc)
                self._update_upload_item_ui(item)

                # Restart upload process
                if self._config.auto_upload:
                    asyncio.create_task(self._process_upload_item(item))

                self._logger.info(f"Upload retried for file: {item.filename}")

        except Exception as e:
            self._logger.error(f"Failed to retry upload: {e}")

    def _remove_upload_item(self, file_id: str) -> None:
        """Remove upload item from list."""
        try:
            if file_id in self._upload_items:
                item = self._upload_items[file_id]
                del self._upload_items[file_id]
                self._update_upload_list()

                self._logger.info(f"Upload item removed: {item.filename}")

                # Update state if no items left
                if not self._upload_items:
                    self._update_state(DropzoneState.IDLE)

        except Exception as e:
            self._logger.error(f"Failed to remove upload item: {e}")

    def _show_error(self, message: str) -> None:
        """Show error message to user."""
        try:
            self._update_state(DropzoneState.ERROR)
            self._logger.error(f"Upload error: {message}")

            # You could add a snackbar or dialog here for user notification
            if self.page:
                # Example: show snackbar
                snackbar = ft.SnackBar(
                    content=ft.Text(message),
                    bgcolor=self.get_palette().error
                )
                self.page.snack_bar = snackbar
                snackbar.open = True
                self.page.update()

        except Exception as e:
            self._logger.error(f"Failed to show error: {e}")

    # Public API methods

    def add_files(self, file_paths: List[Union[str, Path]]) -> List[str]:
        """
        Add files programmatically.

        Args:
            file_paths: List of file paths to add

        Returns:
            List of file IDs for added files
        """
        try:
            upload_items = []
            file_ids = []

            for file_path in file_paths:
                if len(self._upload_items) >= self._config.max_files:
                    break

                path_obj = Path(file_path)
                if not path_obj.exists():
                    continue

                upload_item = FileUploadItem(
                    file_path=path_obj,
                    filename=path_obj.name,
                    file_size=path_obj.stat().st_size
                )

                upload_items.append(upload_item)
                file_ids.append(upload_item.file_id)
                self._upload_items[upload_item.file_id] = upload_item

            if upload_items:
                self._process_selected_files(upload_items)

            return file_ids

        except Exception as e:
            self._logger.error(f"Failed to add files: {e}")
            return []

    def clear_uploads(self) -> None:
        """Clear all upload items."""
        try:
            self._upload_items.clear()
            self._update_upload_list()
            self._update_state(DropzoneState.IDLE)

            self._logger.info("All upload items cleared")

        except Exception as e:
            self._logger.error(f"Failed to clear uploads: {e}")

    def get_upload_items(self) -> List[FileUploadItem]:
        """Get list of current upload items."""
        return list(self._upload_items.values())

    def get_completed_uploads(self) -> List[FileUploadItem]:
        """Get list of completed upload items."""
        return [item for item in self._upload_items.values()
                if item.status == UploadStatus.COMPLETED]

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the upload dropzone."""
        try:
            if enabled:
                if self._state == DropzoneState.DISABLED:
                    self._update_state(DropzoneState.IDLE)
            else:
                self._update_state(DropzoneState.DISABLED)

        except Exception as e:
            self._logger.error(f"Failed to set enabled state: {e}")

    def refresh(self) -> None:
        """Refresh the component display."""
        try:
            self._update_dropzone_ui()
            self._update_upload_list()

        except Exception as e:
            self._logger.error(f"Failed to refresh component: {e}")

    # Drag and Drop Event Handlers

    def _setup_drag_drop_handlers(self) -> None:
        """Setup drag and drop event handlers for the dropzone."""
        if not self._dropzone_container or not self._config.enable_drag_drop:
            return

        try:
            # Note: Flet's drag and drop support is limited
            # This is a placeholder for when full drag-drop support is available
            # For now, we rely on the file picker functionality

            # In a full implementation, you would set up:
            # - on_drag_enter: self._handle_drag_enter
            # - on_drag_over: self._handle_drag_over
            # - on_drag_leave: self._handle_drag_leave
            # - on_drop: self._handle_drop

            self._logger.debug("Drag-drop handlers setup (placeholder)")

        except Exception as e:
            self._logger.error(f"Failed to setup drag-drop handlers: {e}")

    def _handle_drag_enter(self, e) -> None:
        """Handle drag enter event."""
        try:
            if self._state == DropzoneState.DISABLED:
                return

            self._update_state(DropzoneState.DRAG_OVER)
            self._logger.debug("Drag enter detected")

        except Exception as ex:
            self._logger.error(f"Drag enter handler failed: {ex}")

    def _handle_drag_over(self, e) -> None:
        """Handle drag over event."""
        try:
            if self._state == DropzoneState.DISABLED:
                return

            # Prevent default to allow drop
            if hasattr(e, 'prevent_default'):
                e.prevent_default()

            # Maintain drag over state
            if self._state != DropzoneState.DRAG_OVER:
                self._update_state(DropzoneState.DRAG_OVER)

        except Exception as ex:
            self._logger.error(f"Drag over handler failed: {ex}")

    def _handle_drag_leave(self, e) -> None:
        """Handle drag leave event."""
        try:
            if self._state == DropzoneState.DISABLED:
                return

            # Check if we're actually leaving the dropzone
            # (not just moving to a child element)
            self._update_state(DropzoneState.IDLE)
            self._logger.debug("Drag leave detected")

        except Exception as ex:
            self._logger.error(f"Drag leave handler failed: {ex}")

    def _handle_drop(self, e) -> None:
        """Handle file drop event."""
        try:
            if self._state == DropzoneState.DISABLED:
                return

            # Prevent default behavior
            if hasattr(e, 'prevent_default'):
                e.prevent_default()

            # Extract files from drop event
            files = self._extract_files_from_drop_event(e)

            if files:
                # Process dropped files
                upload_items = []
                for file_info in files:
                    if len(self._upload_items) >= self._config.max_files:
                        self._show_error(f"Maximum {self._config.max_files} files allowed")
                        break

                    upload_item = FileUploadItem(
                        file_path=Path(file_info['path']) if file_info.get('path') else None,
                        filename=file_info['name'],
                        file_size=file_info.get('size', 0)
                    )

                    upload_items.append(upload_item)
                    self._upload_items[upload_item.file_id] = upload_item

                if upload_items:
                    self._process_selected_files(upload_items)

            self._update_state(DropzoneState.IDLE)
            self._logger.info(f"Files dropped: {len(files) if files else 0}")

        except Exception as ex:
            self._logger.error(f"Drop handler failed: {ex}")
            self._update_state(DropzoneState.ERROR)

    def _extract_files_from_drop_event(self, e) -> List[Dict[str, Any]]:
        """
        Extract file information from drop event.

        Args:
            e: Drop event object

        Returns:
            List of file information dictionaries
        """
        try:
            files = []

            # Note: This is a placeholder implementation
            # In a real drag-drop implementation, you would extract:
            # - File paths
            # - File names
            # - File sizes
            # - MIME types
            # from the event's dataTransfer.files

            # For now, return empty list since Flet doesn't fully support
            # drag-drop file operations yet

            return files

        except Exception as ex:
            self._logger.error(f"Failed to extract files from drop event: {ex}")
            return []

    def _validate_dropped_files(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate dropped files before processing.

        Args:
            files: List of file information dictionaries

        Returns:
            List of valid file information dictionaries
        """
        try:
            valid_files = []

            for file_info in files:
                # Check file size
                file_size = file_info.get('size', 0)
                max_size_bytes = self._config.max_file_size_mb * 1024 * 1024

                if file_size > max_size_bytes:
                    self._logger.warning(f"File too large: {file_info.get('name', 'unknown')} ({file_size} bytes)")
                    continue

                # Check file extension
                filename = file_info.get('name', '')
                file_ext = Path(filename).suffix.lower()

                # Map extensions to formats
                allowed_extensions = set()
                for fmt in self._config.allowed_formats:
                    if fmt == DocumentFormat.PDF:
                        allowed_extensions.add('.pdf')
                    elif fmt == DocumentFormat.DOCX:
                        allowed_extensions.update(['.docx', '.doc'])
                    elif fmt == DocumentFormat.TXT:
                        allowed_extensions.add('.txt')
                    elif fmt == DocumentFormat.HTML:
                        allowed_extensions.update(['.html', '.htm'])
                    elif fmt == DocumentFormat.MARKDOWN:
                        allowed_extensions.update(['.md', '.markdown'])

                if file_ext not in allowed_extensions:
                    self._logger.warning(f"Unsupported file format: {filename}")
                    continue

                valid_files.append(file_info)

            return valid_files

        except Exception as e:
            self._logger.error(f"Failed to validate dropped files: {e}")
            return []
