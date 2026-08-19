"""
Module: document_upload_ui
Description: Comprehensive document upload interface that integrates dropzone, file browser, and progress tracking.
            Provides unified upload experience with multiple input methods, real-time progress monitoring,
            and seamless integration with document processing pipeline. Features modern UI/UX with
            theme-aware styling, accessibility compliance, and responsive design.
Phase: 3
Location: /src/modules/ui/document_manager_ui/document_upload_ui/document_upload_ui.py
"""

# Standard library imports
import asyncio
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

# Import upload components
from src.modules.ui.document_upload_ui.upload_dropzone_ui.upload_dropzone_ui import (
    UploadDropzoneUI,
    DropzoneConfig,
    FileUploadItem,
    UploadStatus
)
from src.modules.ui.document_upload_ui.file_browser_ui.file_browser_ui import (
    FileBrowserUI,
    FileFilterConfig,
    BrowserMode,
    FileItem
)
from src.modules.ui.document_upload_ui.upload_progress_ui.upload_progress_ui import (
    UploadProgressUI,
    ProgressConfig,
    ProgressItem,
    ProgressStatus
)

# Import logic components
from src.modules.logic.document_ingestion_lg.format_detector_lg.format_detector_lg import (
    FormatDetector, DocumentFormat
)
from src.modules.logic.document_ingestion_lg.file_validator_lg.file_validator_lg import (
    FileValidator, FileValidationResult
)


class UploadMode(Enum):
    """Document upload modes."""
    DROPZONE = "dropzone"
    FILE_BROWSER = "file_browser"
    COMBINED = "combined"


class UploadState(Enum):
    """Upload interface states."""
    IDLE = "idle"
    SELECTING = "selecting"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class UploadConfig:
    """Configuration for document upload interface."""
    mode: UploadMode = UploadMode.COMBINED
    max_file_size_mb: int = 100
    max_files: int = 50
    allowed_formats: List[DocumentFormat] = field(default_factory=lambda: [
        DocumentFormat.PDF, DocumentFormat.DOCX, DocumentFormat.TXT,
        DocumentFormat.HTML, DocumentFormat.MARKDOWN
    ])
    enable_drag_drop: bool = True
    enable_file_browser: bool = True
    enable_progress_tracking: bool = True
    auto_start_upload: bool = False
    show_file_preview: bool = True
    enable_batch_operations: bool = True


class DocumentUploadUI(ThemeAwareUserControl):
    """
    Comprehensive document upload interface with multiple input methods.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Multiple upload methods (drag-drop, file browser)
    - Integrated progress tracking and monitoring
    - File validation and format detection
    - Batch upload operations with queue management
    - Theme-aware styling with accessibility compliance
    - Real-time upload status and error handling
    - Integration with document processing pipeline
    """
    
    def __init__(self,
                 config: Optional[UploadConfig] = None,
                 on_files_selected: Optional[Callable[[List[FileUploadItem]], None]] = None,
                 on_upload_started: Optional[Callable[[List[FileUploadItem]], None]] = None,
                 on_upload_progress: Optional[Callable[[str, float], None]] = None,
                 on_upload_complete: Optional[Callable[[List[FileUploadItem]], None]] = None,
                 on_upload_error: Optional[Callable[[FileUploadItem, str], None]] = None,
                 **kwargs):
        """
        Initialize the DocumentUploadUI component.
        
        Args:
            config: Upload configuration
            on_files_selected: Callback when files are selected
            on_upload_started: Callback when upload starts
            on_upload_progress: Callback for upload progress updates
            on_upload_complete: Callback when all uploads complete
            on_upload_error: Callback when upload fails
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or UploadConfig()
        
        # Callbacks
        self._on_files_selected = on_files_selected
        self._on_upload_started = on_upload_started
        self._on_upload_progress = on_upload_progress
        self._on_upload_complete = on_upload_complete
        self._on_upload_error = on_upload_error
        
        # State
        self._current_state = UploadState.IDLE
        self._selected_files: List[FileUploadItem] = []
        self._upload_queue: List[FileUploadItem] = []
        self._completed_uploads: List[FileUploadItem] = []
        self._failed_uploads: List[FileUploadItem] = []
        
        # Components
        self._dropzone_ui: Optional[UploadDropzoneUI] = None
        self._file_browser_ui: Optional[FileBrowserUI] = None
        self._progress_ui: Optional[UploadProgressUI] = None
        
        # Utilities
        self._format_detector = FormatDetector()
        self._file_validator = FileValidator()
        self._logger = get_logger(__name__)
        
        # UI Controls
        self._mode_tabs: Optional[ft.Tabs] = None
        self._upload_button: Optional[ft.ElevatedButton] = None
        self._clear_button: Optional[ft.TextButton] = None
        self._status_text: Optional[ft.Text] = None
        self._file_count_text: Optional[ft.Text] = None
        
        self._logger.info("DocumentUploadUI initialized")

    def build(self) -> ft.Control:
        """Build the document upload UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create main layout based on mode
        if self._config.mode == UploadMode.DROPZONE:
            return self._create_dropzone_layout()
        elif self._config.mode == UploadMode.FILE_BROWSER:
            return self._create_file_browser_layout()
        else:  # COMBINED mode
            return self._create_combined_layout()

    def _create_combined_layout(self) -> ft.Control:
        """Create combined upload interface with tabs."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create mode tabs
        self._mode_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Drag & Drop",
                    icon=self.get_icon('CLOUD_UPLOAD'),
                    content=self._create_dropzone_content()
                ),
                ft.Tab(
                    text="Browse Files",
                    icon=self.get_icon('FOLDER_OPEN'),
                    content=self.create_themed_component(
                        "container",
                        content=self._create_file_browser_content(),
                        padding=spacing.md
                    )
                )
            ],
            on_change=self._on_tab_changed
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_header(),
                    ft.Divider(height=spacing.xs, color=palette.borders),
                    ft.Container(
                        content=self._mode_tabs,
                        expand=True
                    ),
                    self._create_footer()
                ],
                spacing=0,
                expand=True
            ),
            bgcolor=palette.surface,
            border=ft.border.all(spacing.xs, palette.borders),
            border_radius=self.get_responsive_size(12),
            padding=ft.padding.all(0),
            expand=True
        )

    def _create_dropzone_layout(self) -> ft.Control:
        """Create dropzone-only layout."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_header(),
                    ft.Divider(height=spacing.xs, color=palette.borders),
                    ft.Container(
                        content=self._create_dropzone_content(),
                        expand=True,
                        padding=spacing.lg
                    ),
                    self._create_footer()
                ],
                spacing=0,
                expand=True
            ),
            bgcolor=palette.surface,
            border=ft.border.all(spacing.xs, palette.borders),
            border_radius=self.get_responsive_size(12),
            padding=ft.padding.all(0),
            expand=True
        )

    def _create_file_browser_layout(self) -> ft.Control:
        """Create file browser-only layout."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._create_header(),
                    ft.Divider(height=spacing.xs, color=palette.borders),
                    ft.Container(
                        content=self._create_file_browser_content(),
                        expand=True,
                        padding=spacing.md
                    ),
                    self._create_footer()
                ],
                spacing=0,
                expand=True
            ),
            bgcolor=palette.surface,
            border=ft.border.all(spacing.xs, palette.borders),
            border_radius=self.get_responsive_size(12),
            padding=ft.padding.all(0),
            expand=True
        )

    def _create_header(self) -> ft.Control:
        """Create upload interface header."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Status text
        self._status_text = ft.Text(
            value="Ready to upload documents",
            style=typography.body_medium,
            color=palette.on_surface_variant
        )

        # File count text
        self._file_count_text = ft.Text(
            value="No files selected",
            style=typography.body_small,
            color=palette.on_surface_variant
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value="Document Upload",
                                style=typography.headline_small,
                                color=palette.on_surface,
                                weight=ft.FontWeight.W_600
                            ),
                            self._status_text
                        ],
                        spacing=spacing.xs,
                        expand=True
                    ),
                    ft.Column(
                        controls=[
                            self._file_count_text,
                            self._create_action_buttons()
                        ],
                        spacing=spacing.xs,
                        horizontal_alignment=ft.CrossAxisAlignment.END
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.START
            ),
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(
                horizontal=spacing.lg,
                vertical=spacing.md
            ),
            border_radius=ft.border_radius.only(
                top_left=self.get_responsive_size(12),
                top_right=self.get_responsive_size(12)
            )
        )

    def _create_action_buttons(self) -> ft.Control:
        """Create action buttons for upload operations."""
        spacing = self.get_spacing()

        # Upload button
        self._upload_button = self.create_themed_component(
            "button",
            variant="primary",
            text="Upload Files",
            icon=self.get_icon('UPLOAD'),
            disabled=True,
            on_click=self._on_upload_clicked
        )

        # Clear button
        self._clear_button = self.create_themed_component(
            "button",
            variant="secondary",
            text="Clear",
            icon=self.get_icon('CLEAR'),
            disabled=True,
            on_click=self._on_clear_clicked
        )

        return ft.Row(
            controls=[self._clear_button, self._upload_button],
            spacing=spacing.sm
        )

    def _create_footer(self) -> ft.Control:
        """Create upload interface footer with progress tracking."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create progress UI if enabled
        if self._config.enable_progress_tracking:
            self._progress_ui = UploadProgressUI(
                config=ProgressConfig(
                    show_individual_progress=True,
                    show_overall_progress=True,
                    enable_pause_resume=True,
                    enable_cancel=True
                ),
                on_progress_update=self._on_progress_update,
                on_upload_complete=self._on_progress_complete,
                on_upload_error=self._on_progress_error
            )

            return ft.Container(
                content=self._progress_ui,
                bgcolor=palette.surface_variant,
                padding=spacing.md,
                border_radius=ft.border_radius.only(
                    bottom_left=self.get_responsive_size(12),
                    bottom_right=self.get_responsive_size(12)
                )
            )

        return ft.Container(height=spacing.none)

    def _create_dropzone_content(self) -> ft.Control:
        """Create dropzone upload content."""
        # Create dropzone UI
        self._dropzone_ui = UploadDropzoneUI(
            config=DropzoneConfig(
                max_file_size_mb=self._config.max_file_size_mb,
                allowed_formats=self._config.allowed_formats,
                max_files=self._config.max_files,
                enable_multiple_files=True,
                auto_upload=self._config.auto_start_upload,
                show_file_preview=self._config.show_file_preview,
                enable_drag_drop=self._config.enable_drag_drop
            ),
            on_files_selected=self._on_dropzone_files_selected,
            on_upload_progress=self._on_dropzone_progress,
            on_upload_complete=self._on_dropzone_complete,
            on_upload_error=self._on_dropzone_error
        )

        return self._dropzone_ui

    def _create_file_browser_content(self) -> ft.Control:
        """Create file browser upload content."""
        # Create file browser UI
        self._file_browser_ui = FileBrowserUI(
            mode=BrowserMode.MULTIPLE_FILES,
            filter_config=FileFilterConfig(
                allowed_extensions=self._get_allowed_extensions(),
                max_file_size=self._config.max_file_size_mb * 1024 * 1024,
                show_hidden_files=False,
                enable_size_filter=True
            ),
            on_files_selected=self._on_browser_files_selected,
            on_selection_changed=self._on_browser_selection_changed
        )

        return self._file_browser_ui

    def _get_allowed_extensions(self) -> List[str]:
        """Get allowed file extensions from configured formats."""
        extensions = []
        for fmt in self._config.allowed_formats:
            if fmt == DocumentFormat.PDF:
                extensions.append("pdf")
            elif fmt == DocumentFormat.DOCX:
                extensions.extend(["docx", "doc"])
            elif fmt == DocumentFormat.TXT:
                extensions.append("txt")
            elif fmt == DocumentFormat.HTML:
                extensions.extend(["html", "htm"])
            elif fmt == DocumentFormat.MARKDOWN:
                extensions.extend(["md", "markdown"])
        return extensions

    # Event Handlers
    def _on_tab_changed(self, e: ft.ControlEvent) -> None:
        """Handle tab change event."""
        try:
            tab_index = e.control.selected_index
            self._logger.debug(f"Tab changed to index: {tab_index}")

            # Clear current selection when switching tabs
            self._clear_selection()

        except Exception as ex:
            self._logger.error(f"Error handling tab change: {ex}")

    def _on_upload_clicked(self, e: ft.ControlEvent) -> None:
        """Handle upload button click."""
        try:
            if not self._selected_files:
                return

            self._start_upload()

        except Exception as ex:
            self._logger.error(f"Error starting upload: {ex}")
            self._show_error_message(f"Failed to start upload: {ex}")

    def _on_clear_clicked(self, e: ft.ControlEvent) -> None:
        """Handle clear button click."""
        try:
            self._clear_selection()

        except Exception as ex:
            self._logger.error(f"Error clearing selection: {ex}")

    def _on_dropzone_files_selected(self, files: List[FileUploadItem]) -> None:
        """Handle files selected from dropzone."""
        try:
            self._process_selected_files(files)

        except Exception as ex:
            self._logger.error(f"Error processing dropzone files: {ex}")

    def _on_browser_files_selected(self, files: List[FileItem]) -> None:
        """Handle files selected from browser."""
        try:
            # Convert FileItem to FileUploadItem
            upload_items = []
            for file_item in files:
                upload_item = FileUploadItem(
                    id=str(uuid.uuid4()),
                    file_path=file_item.path,
                    file_name=file_item.name,
                    file_size=file_item.size,
                    file_type=file_item.file_type,
                    status=UploadStatus.PENDING,
                    created_at=datetime.now(timezone.utc)
                )
                upload_items.append(upload_item)

            self._process_selected_files(upload_items)

        except Exception as ex:
            self._logger.error(f"Error processing browser files: {ex}")

    def _on_browser_selection_changed(self, files: List[FileItem]) -> None:
        """Handle browser selection change."""
        try:
            # Update UI to reflect current selection
            self._update_selection_display(len(files))

        except Exception as ex:
            self._logger.error(f"Error handling selection change: {ex}")

    def _on_dropzone_progress(self, file_id: str, progress: float) -> None:
        """Handle dropzone upload progress."""
        try:
            if self._on_upload_progress:
                self._on_upload_progress(file_id, progress)

            # Update progress UI
            if self._progress_ui:
                # Convert progress to bytes for update_item_progress
                # This is a simplified approach - in real implementation,
                # you'd track actual bytes uploaded
                self._progress_ui.update_item_progress(file_id, int(progress * 100), 0.0)

        except Exception as ex:
            self._logger.error(f"Error handling dropzone progress: {ex}")

    def _on_dropzone_complete(self, file_item: FileUploadItem) -> None:
        """Handle dropzone upload completion."""
        try:
            self._completed_uploads.append(file_item)
            self._update_upload_status()

            # Check if all uploads are complete
            if len(self._completed_uploads) + len(self._failed_uploads) >= len(self._upload_queue):
                self._finalize_upload()

        except Exception as ex:
            self._logger.error(f"Error handling dropzone completion: {ex}")

    def _on_dropzone_error(self, file_item: FileUploadItem, error: str) -> None:
        """Handle dropzone upload error."""
        try:
            self._failed_uploads.append(file_item)
            self._update_upload_status()

            if self._on_upload_error:
                self._on_upload_error(file_item, error)

            # Check if all uploads are complete (including failures)
            if len(self._completed_uploads) + len(self._failed_uploads) >= len(self._upload_queue):
                self._finalize_upload()

        except Exception as ex:
            self._logger.error(f"Error handling dropzone error: {ex}")

    def _on_progress_update(self, file_id: str, progress: float) -> None:
        """Handle progress UI updates."""
        try:
            if self._on_upload_progress:
                self._on_upload_progress(file_id, progress)

        except Exception as ex:
            self._logger.error(f"Error handling progress update: {ex}")

    def _on_progress_complete(self, file_item: ProgressItem) -> None:
        """Handle progress UI completion."""
        try:
            # Find corresponding upload item and mark as complete
            for upload_item in self._upload_queue:
                if upload_item.id == file_item.id:
                    upload_item.status = UploadStatus.COMPLETED
                    self._completed_uploads.append(upload_item)
                    break

            self._update_upload_status()

        except Exception as ex:
            self._logger.error(f"Error handling progress completion: {ex}")

    def _on_progress_error(self, file_item: ProgressItem, error: str) -> None:
        """Handle progress UI errors."""
        try:
            # Find corresponding upload item and mark as failed
            for upload_item in self._upload_queue:
                if upload_item.id == file_item.id:
                    upload_item.status = UploadStatus.FAILED
                    upload_item.error_message = error
                    self._failed_uploads.append(upload_item)
                    break

            self._update_upload_status()

            if self._on_upload_error:
                # Convert ProgressItem back to FileUploadItem for callback
                upload_item = next((item for item in self._upload_queue if item.id == file_item.id), None)
                if upload_item:
                    self._on_upload_error(upload_item, error)

        except Exception as ex:
            self._logger.error(f"Error handling progress error: {ex}")

    # Core Methods
    def _process_selected_files(self, files: List[FileUploadItem]) -> None:
        """Process and validate selected files."""
        try:
            # Clear previous selection
            self._selected_files.clear()

            # Validate and add files
            for file_item in files:
                if self._validate_file(file_item):
                    self._selected_files.append(file_item)
                else:
                    self._logger.warning(f"File validation failed: {file_item.file_name}")

            # Update UI
            self._update_selection_display(len(self._selected_files))

            # Trigger callback
            if self._on_files_selected and self._selected_files:
                self._on_files_selected(self._selected_files)

        except Exception as ex:
            self._logger.error(f"Error processing selected files: {ex}")

    def _validate_file(self, file_item: FileUploadItem) -> bool:
        """Validate a single file."""
        try:
            # Check file size
            if file_item.file_size > self._config.max_file_size_mb * 1024 * 1024:
                return False

            # Check format
            try:
                detected_format = self._format_detector.detect_format(file_item.file_path)
                if detected_format not in self._config.allowed_formats:
                    return False
            except Exception:
                return False

            # Additional validation using file validator
            validation_result = self._file_validator.validate_file(file_item.file_path)
            return validation_result.is_valid

        except Exception as ex:
            self._logger.error(f"Error validating file {file_item.file_name}: {ex}")
            return False

    def _start_upload(self) -> None:
        """Start the upload process."""
        try:
            if not self._selected_files:
                return

            # Update state
            self._current_state = UploadState.UPLOADING
            self._upload_queue = self._selected_files.copy()
            self._completed_uploads.clear()
            self._failed_uploads.clear()

            # Update UI
            self._update_upload_status()

            # Trigger callback
            if self._on_upload_started:
                self._on_upload_started(self._upload_queue)

            # Start upload in dropzone if available
            if self._dropzone_ui and self._config.mode in [UploadMode.DROPZONE, UploadMode.COMBINED]:
                # Dropzone handles its own uploads
                pass
            else:
                # Handle upload manually for file browser mode
                self._process_upload_queue()

        except Exception as ex:
            self._logger.error(f"Error starting upload: {ex}")
            self._current_state = UploadState.ERROR
            self._update_upload_status()

    async def _process_upload_queue(self) -> None:
        """Process the upload queue manually."""
        try:
            for file_item in self._upload_queue:
                try:
                    file_item.status = UploadStatus.UPLOADING

                    # Simulate upload progress (replace with actual upload logic)
                    for progress in range(0, 101, 10):
                        await asyncio.sleep(0.1)  # Simulate upload time
                        if self._on_upload_progress:
                            self._on_upload_progress(file_item.id, progress / 100.0)

                    # Mark as completed
                    file_item.status = UploadStatus.COMPLETED
                    self._completed_uploads.append(file_item)

                except Exception as ex:
                    file_item.status = UploadStatus.FAILED
                    file_item.error_message = str(ex)
                    self._failed_uploads.append(file_item)

                    if self._on_upload_error:
                        self._on_upload_error(file_item, str(ex))

            # Finalize upload
            self._finalize_upload()

        except Exception as ex:
            self._logger.error(f"Error processing upload queue: {ex}")
            self._current_state = UploadState.ERROR
            self._update_upload_status()

    def _finalize_upload(self) -> None:
        """Finalize the upload process."""
        try:
            # Update state
            if self._failed_uploads and not self._completed_uploads:
                self._current_state = UploadState.ERROR
            elif self._failed_uploads:
                self._current_state = UploadState.COMPLETED  # Partial success
            else:
                self._current_state = UploadState.COMPLETED

            # Update UI
            self._update_upload_status()

            # Trigger completion callback
            if self._on_upload_complete and self._completed_uploads:
                self._on_upload_complete(self._completed_uploads)

        except Exception as ex:
            self._logger.error(f"Error finalizing upload: {ex}")

    def _clear_selection(self) -> None:
        """Clear current file selection."""
        try:
            self._selected_files.clear()
            self._upload_queue.clear()
            self._completed_uploads.clear()
            self._failed_uploads.clear()

            # Reset state
            self._current_state = UploadState.IDLE

            # Update UI
            self._update_selection_display(0)

            # Clear component selections
            if self._dropzone_ui:
                self._dropzone_ui.clear_uploads()

            if self._file_browser_ui:
                self._file_browser_ui.clear_selection()

        except Exception as ex:
            self._logger.error(f"Error clearing selection: {ex}")

    def _update_selection_display(self, file_count: int) -> None:
        """Update the selection display."""
        try:
            # Update file count text
            if self._file_count_text:
                if file_count == 0:
                    self._file_count_text.value = "No files selected"
                elif file_count == 1:
                    self._file_count_text.value = "1 file selected"
                else:
                    self._file_count_text.value = f"{file_count} files selected"

            # Update button states
            if self._upload_button:
                self._upload_button.disabled = file_count == 0

            if self._clear_button:
                self._clear_button.disabled = file_count == 0

            # Update status text
            if self._status_text:
                if file_count == 0:
                    self._status_text.value = "Ready to upload documents"
                else:
                    self._status_text.value = f"Ready to upload {file_count} file{'s' if file_count != 1 else ''}"

            # Update UI
            if self.page:
                self.update()

        except Exception as ex:
            self._logger.error(f"Error updating selection display: {ex}")

    def _update_upload_status(self) -> None:
        """Update the upload status display."""
        try:
            if not self._status_text:
                return

            if self._current_state == UploadState.IDLE:
                self._status_text.value = "Ready to upload documents"
            elif self._current_state == UploadState.UPLOADING:
                total = len(self._upload_queue)
                completed = len(self._completed_uploads)
                failed = len(self._failed_uploads)
                remaining = total - completed - failed
                self._status_text.value = f"Uploading... {completed}/{total} completed"
            elif self._current_state == UploadState.COMPLETED:
                completed = len(self._completed_uploads)
                failed = len(self._failed_uploads)
                if failed > 0:
                    self._status_text.value = f"Upload completed: {completed} successful, {failed} failed"
                else:
                    self._status_text.value = f"Upload completed successfully: {completed} files"
            elif self._current_state == UploadState.ERROR:
                self._status_text.value = "Upload failed"

            # Update UI
            if self.page:
                self.update()

        except Exception as ex:
            self._logger.error(f"Error updating upload status: {ex}")

    def _show_error_message(self, message: str) -> None:
        """Show error message to user."""
        try:
            if self.page:
                # Create error snackbar
                snackbar = ft.SnackBar(
                    content=ft.Text(
                        value=message,
                        color=self.get_palette().on_error
                    ),
                    bgcolor=self.get_palette().error,
                    action="Dismiss",
                    action_color=self.get_palette().on_error
                )

                self.page.snack_bar = snackbar
                snackbar.open = True
                self.page.update()

        except Exception as ex:
            self._logger.error(f"Error showing error message: {ex}")

    # Public API Methods
    def get_selected_files(self) -> List[FileUploadItem]:
        """Get currently selected files."""
        return self._selected_files.copy()

    def get_upload_queue(self) -> List[FileUploadItem]:
        """Get current upload queue."""
        return self._upload_queue.copy()

    def get_completed_uploads(self) -> List[FileUploadItem]:
        """Get completed uploads."""
        return self._completed_uploads.copy()

    def get_failed_uploads(self) -> List[FileUploadItem]:
        """Get failed uploads."""
        return self._failed_uploads.copy()

    def get_current_state(self) -> UploadState:
        """Get current upload state."""
        return self._current_state

    def set_config(self, config: UploadConfig) -> None:
        """Update upload configuration."""
        self._config = config

        # Update component configurations
        if self._dropzone_ui:
            # UploadDropzoneUI doesn't have set_config method, recreate if needed
            # For now, just update internal config - component will use new config on rebuild
            pass

        if self._file_browser_ui:
            self._file_browser_ui.set_filter_config(FileFilterConfig(
                allowed_extensions=self._get_allowed_extensions(),
                max_file_size=config.max_file_size_mb * 1024 * 1024,
                show_hidden_files=False,
                enable_size_filter=True
            ))

    def clear_all(self) -> None:
        """Clear all files and reset interface."""
        self._clear_selection()

    def start_upload_manually(self) -> None:
        """Manually start upload process."""
        if self._selected_files:
            self._start_upload()

    def cancel_upload(self) -> None:
        """Cancel current upload process."""
        try:
            if self._current_state == UploadState.UPLOADING:
                # Cancel uploads in progress
                for file_item in self._upload_queue:
                    if file_item.status == UploadStatus.UPLOADING:
                        file_item.status = UploadStatus.CANCELLED

                # Update state
                self._current_state = UploadState.IDLE
                self._update_upload_status()

                # Cancel in components
                if self._dropzone_ui:
                    # UploadDropzoneUI doesn't have cancel_uploads method, use clear_uploads
                    self._dropzone_ui.clear_uploads()

                if self._progress_ui:
                    self._progress_ui.cancel_all_uploads()

        except Exception as ex:
            self._logger.error(f"Error canceling upload: {ex}")

    def retry_failed_uploads(self) -> None:
        """Retry failed uploads."""
        try:
            if self._failed_uploads:
                # Reset failed uploads to pending
                for file_item in self._failed_uploads:
                    file_item.status = UploadStatus.PENDING
                    file_item.error_message = None

                # Move back to upload queue
                self._upload_queue.extend(self._failed_uploads)
                self._failed_uploads.clear()

                # Start upload
                self._start_upload()

        except Exception as ex:
            self._logger.error(f"Error retrying failed uploads: {ex}")

    def add_files(self, files: List[FileUploadItem]) -> None:
        """Add files to current selection."""
        try:
            for file_item in files:
                if self._validate_file(file_item) and file_item not in self._selected_files:
                    self._selected_files.append(file_item)

            self._update_selection_display(len(self._selected_files))

            if self._on_files_selected:
                self._on_files_selected(self._selected_files)

        except Exception as ex:
            self._logger.error(f"Error adding files: {ex}")

    def remove_file(self, file_id: str) -> None:
        """Remove a file from selection."""
        try:
            self._selected_files = [f for f in self._selected_files if f.id != file_id]
            self._update_selection_display(len(self._selected_files))

        except Exception as ex:
            self._logger.error(f"Error removing file: {ex}")

    def get_upload_statistics(self) -> Dict[str, Any]:
        """Get upload statistics."""
        return {
            'total_selected': len(self._selected_files),
            'total_queued': len(self._upload_queue),
            'completed': len(self._completed_uploads),
            'failed': len(self._failed_uploads),
            'current_state': self._current_state.value,
            'success_rate': (len(self._completed_uploads) / len(self._upload_queue) * 100) if self._upload_queue else 0
        }
