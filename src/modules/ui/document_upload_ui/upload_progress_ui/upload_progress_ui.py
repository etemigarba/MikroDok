"""
Module: upload_progress_ui
Description: Real-time upload progress visualization with pause/resume functionality and comprehensive
            progress tracking. Provides responsive progress interface with file-by-file monitoring,
            batch operations, speed metrics, and seamless integration with document processing pipeline.
            Features modern UI/UX with theme-aware styling, accessibility compliance, and cross-platform compatibility.
Phase: 3
Location: /src/modules/ui/document_upload_ui/upload_progress_ui/upload_progress_ui.py
"""

# Standard library imports
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
import time

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class ProgressStatus(Enum):
    """Upload progress status states."""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressMetrics:
    """Progress metrics for upload tracking."""
    bytes_uploaded: int = 0
    total_bytes: int = 0
    upload_speed: float = 0.0  # bytes per second
    time_elapsed: float = 0.0  # seconds
    time_remaining: float = 0.0  # seconds
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class ProgressItem:
    """Individual file progress tracking item."""
    file_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_name: str = ""
    file_path: str = ""
    file_size: int = 0
    status: ProgressStatus = ProgressStatus.PENDING
    progress_percent: float = 0.0
    error_message: Optional[str] = None
    metrics: ProgressMetrics = field(default_factory=ProgressMetrics)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def update_progress(self, bytes_uploaded: int, upload_speed: float = 0.0) -> None:
        """Update progress metrics."""
        self.metrics.bytes_uploaded = bytes_uploaded
        self.metrics.upload_speed = upload_speed
        self.progress_percent = (bytes_uploaded / self.file_size * 100) if self.file_size > 0 else 0.0
        self.updated_at = datetime.now(timezone.utc)
        
        if self.metrics.start_time:
            self.metrics.time_elapsed = (self.updated_at - self.metrics.start_time).total_seconds()
            
            if upload_speed > 0:
                remaining_bytes = self.file_size - bytes_uploaded
                self.metrics.time_remaining = remaining_bytes / upload_speed


@dataclass
class ProgressConfig:
    """Configuration for upload progress tracking."""
    show_individual_files: bool = True
    show_overall_progress: bool = True
    show_speed_metrics: bool = True
    show_time_estimates: bool = True
    enable_pause_resume: bool = True
    enable_cancel: bool = True
    auto_remove_completed: bool = False
    max_concurrent_uploads: int = 3
    update_interval_ms: int = 100


class UploadProgressUI(ThemeAwareUserControl):
    """
    Comprehensive upload progress tracking interface with real-time visualization.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time progress tracking with speed metrics
    - Individual file progress monitoring
    - Batch operations (pause all, resume all, cancel all)
    - Pause/resume functionality for individual files
    - Time estimates and completion predictions
    - Theme-aware styling with accessibility compliance
    - Error handling and retry mechanisms
    - Integration with document processing pipeline
    """
    
    def __init__(self,
                 config: Optional[ProgressConfig] = None,
                 on_progress_update: Optional[Callable[[ProgressItem], None]] = None,
                 on_upload_complete: Optional[Callable[[ProgressItem], None]] = None,
                 on_upload_error: Optional[Callable[[ProgressItem, str], None]] = None,
                 on_upload_cancelled: Optional[Callable[[ProgressItem], None]] = None,
                 on_all_complete: Optional[Callable[[List[ProgressItem]], None]] = None,
                 **kwargs):
        """
        Initialize the UploadProgressUI component.
        
        Args:
            config: Progress tracking configuration
            on_progress_update: Callback for progress updates
            on_upload_complete: Callback when upload completes
            on_upload_error: Callback when upload fails
            on_upload_cancelled: Callback when upload is cancelled
            on_all_complete: Callback when all uploads complete
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration and callbacks
        self._config = config or ProgressConfig()
        self._on_progress_update = on_progress_update
        self._on_upload_complete = on_upload_complete
        self._on_upload_error = on_upload_error
        self._on_upload_cancelled = on_upload_cancelled
        self._on_all_complete = on_all_complete
        
        # Component state
        self._progress_items: Dict[str, ProgressItem] = {}
        self._is_built = False
        self._update_timer: Optional[asyncio.Task] = None
        
        # Core components
        self._logger = get_logger(__name__)
        
        # UI components
        self._main_container: Optional[ft.Container] = None
        self._header_container: Optional[ft.Container] = None
        self._progress_list: Optional[ft.Column] = None
        self._overall_progress: Optional[ft.ProgressBar] = None
        self._status_text: Optional[ft.Text] = None
        self._batch_controls: Optional[ft.Row] = None
        
        # Progress tracking
        self._total_files = 0
        self._completed_files = 0
        self._failed_files = 0
        self._total_bytes = 0
        self._uploaded_bytes = 0
        
    def build(self) -> ft.Control:
        """Build the upload progress interface."""
        if not self._is_built:
            self._build_component()
            self._is_built = True
        return self._main_container
    
    def _build_component(self) -> None:
        """Build the main progress component."""
        # Get responsive layout manager
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        
        # Create header section
        self._header_container = self._create_header_section()
        
        # Create progress list
        self._progress_list = ft.Column(
            controls=[],
            spacing=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=14
            ),
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
        
        # Create main layout
        main_content = ft.Column(
            controls=[
                self._header_container,
                ft.Divider(color=palette.outline, height=1),
                self._progress_list
            ],
            spacing=responsive_manager.get_breakpoint_value(
                mobile=16, tablet=20, desktop=24, large=28
            ),
            expand=True
        )
        
        # Create main container
        self._main_container = ft.Container(
            content=main_content,
            padding=responsive_manager.get_breakpoint_value(
                mobile=12, tablet=16, desktop=20, large=24
            ),
            bgcolor=palette.surface,
            border_radius=spacing.medium,
            expand=True
        )
    
    def _create_header_section(self) -> ft.Container:
        """Create the header section with overall progress and controls."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()
        
        # Overall progress bar
        self._overall_progress = ft.ProgressBar(
            value=0.0,
            color=palette.primary,
            bgcolor=palette.surface_variant,
            height=responsive_manager.get_breakpoint_value(
                mobile=6, tablet=8, desktop=10, large=12
            )
        )
        
        # Status text
        self._status_text = ft.Text(
            value="No uploads in progress",
            size=typography.body_medium[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary
        )
        
        # Batch control buttons
        self._batch_controls = self._create_batch_controls()
        
        # Header layout
        header_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            value="Upload Progress",
                            size=typography.headline_small[0],
                            weight=ft.FontWeight.W_600,
                            color=palette.text_primary
                        ),
                        self._batch_controls
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                self._status_text,
                self._overall_progress
            ],
            spacing=spacing.small
        )
        
        return ft.Container(
            content=header_content,
            padding=spacing.medium
        )

    def _create_batch_controls(self) -> ft.Row:
        """Create batch control buttons."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Button size
        button_size = responsive_manager.get_breakpoint_value(
            mobile=32, tablet=36, desktop=40, large=44
        )

        # Pause all button
        pause_all_btn = ft.IconButton(
            icon=icons.PAUSE,
            icon_size=responsive_manager.get_breakpoint_value(
                mobile=16, tablet=18, desktop=20, large=22
            ),
            icon_color=palette.text_secondary,
            bgcolor=palette.surface_variant,
            width=button_size,
            height=button_size,
            tooltip="Pause all uploads",
            on_click=self._handle_pause_all
        )

        # Resume all button
        resume_all_btn = ft.IconButton(
            icon=icons.PLAY,
            icon_size=responsive_manager.get_breakpoint_value(
                mobile=16, tablet=18, desktop=20, large=22
            ),
            icon_color=palette.text_secondary,
            bgcolor=palette.surface_variant,
            width=button_size,
            height=button_size,
            tooltip="Resume all uploads",
            on_click=self._handle_resume_all
        )

        # Cancel all button
        cancel_all_btn = ft.IconButton(
            icon=icons.CANCEL,
            icon_size=responsive_manager.get_breakpoint_value(
                mobile=16, tablet=18, desktop=20, large=22
            ),
            icon_color=palette.error,
            bgcolor=palette.error_container,
            width=button_size,
            height=button_size,
            tooltip="Cancel all uploads",
            on_click=self._handle_cancel_all
        )

        # Clear completed button
        clear_btn = ft.IconButton(
            icon=icons.CLEAR_ALL,
            icon_size=responsive_manager.get_breakpoint_value(
                mobile=16, tablet=18, desktop=20, large=22
            ),
            icon_color=palette.text_secondary,
            bgcolor=palette.surface_variant,
            width=button_size,
            height=button_size,
            tooltip="Clear completed uploads",
            on_click=self._handle_clear_completed
        )

        return ft.Row(
            controls=[pause_all_btn, resume_all_btn, cancel_all_btn, clear_btn],
            spacing=spacing.small
        )

    def add_upload_item(self, item: ProgressItem) -> None:
        """Add a new upload item to track."""
        try:
            self._progress_items[item.file_id] = item
            self._total_files += 1
            self._total_bytes += item.file_size

            # Create UI for the item
            if self._is_built:
                item_ui = self._create_progress_item_ui(item)
                self._progress_list.controls.append(item_ui)
                self._update_overall_progress()
                self.update()

            self._logger.info(f"Added upload item: {item.file_name}")

        except Exception as e:
            self._logger.error(f"Failed to add upload item {item.file_name}: {e}")

    def update_item_progress(self, file_id: str, bytes_uploaded: int, upload_speed: float = 0.0) -> None:
        """Update progress for a specific upload item."""
        try:
            if file_id in self._progress_items:
                item = self._progress_items[file_id]
                old_bytes = item.metrics.bytes_uploaded

                item.update_progress(bytes_uploaded, upload_speed)

                # Update overall progress
                self._uploaded_bytes += (bytes_uploaded - old_bytes)

                if self._is_built:
                    self._update_progress_item_ui(item)
                    self._update_overall_progress()
                    self.update()

                # Trigger callback
                if self._on_progress_update:
                    self._on_progress_update(item)

        except Exception as e:
            self._logger.error(f"Failed to update progress for {file_id}: {e}")

    def set_item_status(self, file_id: str, status: ProgressStatus, error_message: Optional[str] = None) -> None:
        """Set status for a specific upload item."""
        try:
            if file_id in self._progress_items:
                item = self._progress_items[file_id]
                old_status = item.status

                item.status = status
                item.error_message = error_message
                item.updated_at = datetime.now(timezone.utc)

                # Update counters
                if old_status != ProgressStatus.COMPLETED and status == ProgressStatus.COMPLETED:
                    self._completed_files += 1
                    item.metrics.end_time = datetime.now(timezone.utc)
                    if self._on_upload_complete:
                        self._on_upload_complete(item)

                elif old_status != ProgressStatus.FAILED and status == ProgressStatus.FAILED:
                    self._failed_files += 1
                    if self._on_upload_error:
                        self._on_upload_error(item, error_message or "Unknown error")

                elif status == ProgressStatus.CANCELLED:
                    if self._on_upload_cancelled:
                        self._on_upload_cancelled(item)

                if self._is_built:
                    self._update_progress_item_ui(item)
                    self._update_overall_progress()
                    self.update()

                # Check if all uploads are complete
                self._check_all_complete()

        except Exception as e:
            self._logger.error(f"Failed to set status for {file_id}: {e}")

    def _create_progress_item_ui(self, item: ProgressItem) -> ft.Container:
        """Create UI for individual progress item."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # File info
        file_info = self._create_file_info_section(item)

        # Progress section
        progress_section = self._create_progress_section(item)

        # Control buttons
        control_buttons = self._create_item_controls(item)

        # Main row
        main_row = ft.Row(
            controls=[
                file_info,
                progress_section,
                control_buttons
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.medium
        )

        # Status indicator
        status_color = self._get_status_color(item.status)
        status_indicator = ft.Container(
            width=4,
            height=responsive_manager.get_breakpoint_value(
                mobile=60, tablet=65, desktop=70, large=75
            ),
            bgcolor=status_color,
            border_radius=2
        )

        # Item container
        item_container = ft.Row(
            controls=[status_indicator, main_row],
            spacing=spacing.small,
            expand=True
        )

        return ft.Container(
            content=item_container,
            padding=spacing.medium,
            bgcolor=palette.surface_variant,
            border_radius=spacing.small,
            border=ft.border.all(1, palette.outline) if item.status == ProgressStatus.FAILED else None
        )

    def _create_file_info_section(self, item: ProgressItem) -> ft.Column:
        """Create file information section."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()
        icons = self.get_icons()

        # File icon based on extension
        file_icon = self._get_file_icon(item.file_name)

        # File name
        file_name_text = ft.Text(
            value=item.file_name,
            size=typography.body_medium[0],
            weight=ft.FontWeight.W_500,
            color=palette.text_primary,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # File size
        file_size_text = ft.Text(
            value=self._format_file_size(item.file_size),
            size=typography.body_small[0],
            color=palette.text_secondary
        )

        # File info row
        file_info_row = ft.Row(
            controls=[
                ft.Icon(
                    name=file_icon,
                    size=responsive_manager.get_breakpoint_value(
                        mobile=20, tablet=22, desktop=24, large=26
                    ),
                    color=palette.text_secondary
                ),
                ft.Column(
                    controls=[file_name_text, file_size_text],
                    spacing=2,
                    expand=True
                )
            ],
            spacing=8,
            expand=True
        )

        return file_info_row

    def _create_progress_section(self, item: ProgressItem) -> ft.Column:
        """Create progress visualization section."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()

        # Progress bar
        progress_bar = ft.ProgressBar(
            value=item.progress_percent / 100.0,
            width=responsive_manager.get_breakpoint_value(
                mobile=120, tablet=140, desktop=160, large=180
            ),
            height=responsive_manager.get_breakpoint_value(
                mobile=6, tablet=7, desktop=8, large=9
            ),
            color=self._get_progress_color(item.status),
            bgcolor=palette.surface_variant
        )

        # Progress text
        progress_text = ft.Text(
            value=f"{item.progress_percent:.1f}%",
            size=typography.body_small[0],
            color=palette.text_primary,
            text_align=ft.TextAlign.CENTER
        )

        # Speed and time info
        speed_time_info = self._create_speed_time_info(item)

        return ft.Column(
            controls=[progress_bar, progress_text, speed_time_info],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _create_speed_time_info(self, item: ProgressItem) -> ft.Text:
        """Create speed and time information text."""
        palette = self.get_palette()
        typography = self.get_typography()

        if not self._config.show_speed_metrics and not self._config.show_time_estimates:
            return ft.Container(height=0)

        info_parts = []

        if self._config.show_speed_metrics and item.metrics.upload_speed > 0:
            speed_text = self._format_speed(item.metrics.upload_speed)
            info_parts.append(f"⚡ {speed_text}")

        if self._config.show_time_estimates and item.metrics.time_remaining > 0:
            time_text = self._format_time(item.metrics.time_remaining)
            info_parts.append(f"⏱ {time_text}")

        info_text = " • ".join(info_parts) if info_parts else ""

        return ft.Text(
            value=info_text,
            size=typography.body_small[0],
            color=palette.text_tertiary,
            text_align=ft.TextAlign.CENTER
        )

    def _create_item_controls(self, item: ProgressItem) -> ft.Row:
        """Create control buttons for individual item."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        icons = self.get_icons()

        button_size = responsive_manager.get_breakpoint_value(
            mobile=28, tablet=30, desktop=32, large=34
        )
        icon_size = responsive_manager.get_breakpoint_value(
            mobile=14, tablet=15, desktop=16, large=17
        )

        controls = []

        # Pause/Resume button
        if item.status == ProgressStatus.UPLOADING and self._config.enable_pause_resume:
            pause_btn = ft.IconButton(
                icon=icons.PAUSE,
                icon_size=icon_size,
                icon_color=palette.text_secondary,
                bgcolor=palette.surface,
                width=button_size,
                height=button_size,
                tooltip="Pause upload",
                on_click=lambda e, fid=item.file_id: self._handle_pause_item(fid)
            )
            controls.append(pause_btn)

        elif item.status == ProgressStatus.PAUSED and self._config.enable_pause_resume:
            resume_btn = ft.IconButton(
                icon=icons.PLAY,
                icon_size=icon_size,
                icon_color=palette.success,
                bgcolor=palette.surface,
                width=button_size,
                height=button_size,
                tooltip="Resume upload",
                on_click=lambda e, fid=item.file_id: self._handle_resume_item(fid)
            )
            controls.append(resume_btn)

        # Cancel button
        if item.status in [ProgressStatus.PENDING, ProgressStatus.UPLOADING, ProgressStatus.PAUSED] and self._config.enable_cancel:
            cancel_btn = ft.IconButton(
                icon=icons.CANCEL,
                icon_size=icon_size,
                icon_color=palette.error,
                bgcolor=palette.surface,
                width=button_size,
                height=button_size,
                tooltip="Cancel upload",
                on_click=lambda e, fid=item.file_id: self._handle_cancel_item(fid)
            )
            controls.append(cancel_btn)

        # Retry button for failed uploads
        if item.status == ProgressStatus.FAILED:
            retry_btn = ft.IconButton(
                icon=icons.REFRESH,
                icon_size=icon_size,
                icon_color=palette.warning,
                bgcolor=palette.surface,
                width=button_size,
                height=button_size,
                tooltip="Retry upload",
                on_click=lambda e, fid=item.file_id: self._handle_retry_item(fid)
            )
            controls.append(retry_btn)

        # Remove button for completed/failed uploads
        if item.status in [ProgressStatus.COMPLETED, ProgressStatus.FAILED, ProgressStatus.CANCELLED]:
            remove_btn = ft.IconButton(
                icon=icons.DELETE,
                icon_size=icon_size,
                icon_color=palette.text_tertiary,
                bgcolor=palette.surface,
                width=button_size,
                height=button_size,
                tooltip="Remove from list",
                on_click=lambda e, fid=item.file_id: self._handle_remove_item(fid)
            )
            controls.append(remove_btn)

        return ft.Row(
            controls=controls,
            spacing=4
        )

    def _update_progress_item_ui(self, item: ProgressItem) -> None:
        """Update UI for specific progress item."""
        try:
            # Find and update the item in the progress list
            for i, control in enumerate(self._progress_list.controls):
                if hasattr(control, 'data') and control.data == item.file_id:
                    # Replace with updated UI
                    self._progress_list.controls[i] = self._create_progress_item_ui(item)
                    break
            else:
                # Item not found, add it
                item_ui = self._create_progress_item_ui(item)
                item_ui.data = item.file_id
                self._progress_list.controls.append(item_ui)

        except Exception as e:
            self._logger.error(f"Failed to update progress item UI: {e}")

    def _update_overall_progress(self) -> None:
        """Update overall progress indicators."""
        try:
            if self._total_bytes > 0:
                overall_percent = (self._uploaded_bytes / self._total_bytes) * 100
                self._overall_progress.value = overall_percent / 100.0
            else:
                self._overall_progress.value = 0.0

            # Update status text
            active_uploads = len([item for item in self._progress_items.values()
                                if item.status == ProgressStatus.UPLOADING])

            if active_uploads > 0:
                status = f"Uploading {active_uploads} file{'s' if active_uploads != 1 else ''}"
                if self._completed_files > 0:
                    status += f" • {self._completed_files} completed"
                if self._failed_files > 0:
                    status += f" • {self._failed_files} failed"
            elif self._completed_files > 0:
                status = f"Completed {self._completed_files} file{'s' if self._completed_files != 1 else ''}"
                if self._failed_files > 0:
                    status += f" • {self._failed_files} failed"
            elif self._failed_files > 0:
                status = f"Failed {self._failed_files} file{'s' if self._failed_files != 1 else ''}"
            else:
                status = "No uploads in progress"

            self._status_text.value = status

        except Exception as e:
            self._logger.error(f"Failed to update overall progress: {e}")

    def _check_all_complete(self) -> None:
        """Check if all uploads are complete and trigger callback."""
        try:
            active_items = [item for item in self._progress_items.values()
                          if item.status in [ProgressStatus.PENDING, ProgressStatus.UPLOADING, ProgressStatus.PAUSED]]

            if not active_items and self._progress_items and self._on_all_complete:
                completed_items = [item for item in self._progress_items.values()
                                 if item.status == ProgressStatus.COMPLETED]
                self._on_all_complete(completed_items)

        except Exception as e:
            self._logger.error(f"Failed to check completion status: {e}")

    # Event Handlers
    def _handle_pause_all(self, e) -> None:
        """Handle pause all uploads."""
        try:
            for item in self._progress_items.values():
                if item.status == ProgressStatus.UPLOADING:
                    self.set_item_status(item.file_id, ProgressStatus.PAUSED)
            self._logger.info("Paused all active uploads")
        except Exception as ex:
            self._logger.error(f"Failed to pause all uploads: {ex}")

    def _handle_resume_all(self, e) -> None:
        """Handle resume all uploads."""
        try:
            for item in self._progress_items.values():
                if item.status == ProgressStatus.PAUSED:
                    self.set_item_status(item.file_id, ProgressStatus.UPLOADING)
            self._logger.info("Resumed all paused uploads")
        except Exception as ex:
            self._logger.error(f"Failed to resume all uploads: {ex}")

    def _handle_cancel_all(self, e) -> None:
        """Handle cancel all uploads."""
        try:
            for item in self._progress_items.values():
                if item.status in [ProgressStatus.PENDING, ProgressStatus.UPLOADING, ProgressStatus.PAUSED]:
                    self.set_item_status(item.file_id, ProgressStatus.CANCELLED)
            self._logger.info("Cancelled all active uploads")
        except Exception as ex:
            self._logger.error(f"Failed to cancel all uploads: {ex}")

    def _handle_clear_completed(self, e) -> None:
        """Handle clear completed uploads."""
        try:
            completed_ids = [item.file_id for item in self._progress_items.values()
                           if item.status in [ProgressStatus.COMPLETED, ProgressStatus.FAILED, ProgressStatus.CANCELLED]]

            for file_id in completed_ids:
                self._handle_remove_item(file_id)

            self._logger.info(f"Cleared {len(completed_ids)} completed uploads")
        except Exception as ex:
            self._logger.error(f"Failed to clear completed uploads: {ex}")

    def _handle_pause_item(self, file_id: str) -> None:
        """Handle pause individual upload."""
        try:
            self.set_item_status(file_id, ProgressStatus.PAUSED)
            self._logger.info(f"Paused upload: {file_id}")
        except Exception as e:
            self._logger.error(f"Failed to pause upload {file_id}: {e}")

    def _handle_resume_item(self, file_id: str) -> None:
        """Handle resume individual upload."""
        try:
            self.set_item_status(file_id, ProgressStatus.UPLOADING)
            self._logger.info(f"Resumed upload: {file_id}")
        except Exception as e:
            self._logger.error(f"Failed to resume upload {file_id}: {e}")

    def _handle_cancel_item(self, file_id: str) -> None:
        """Handle cancel individual upload."""
        try:
            self.set_item_status(file_id, ProgressStatus.CANCELLED)
            self._logger.info(f"Cancelled upload: {file_id}")
        except Exception as e:
            self._logger.error(f"Failed to cancel upload {file_id}: {e}")

    def _handle_retry_item(self, file_id: str) -> None:
        """Handle retry individual upload."""
        try:
            if file_id in self._progress_items:
                item = self._progress_items[file_id]
                item.progress_percent = 0.0
                item.metrics = ProgressMetrics()
                item.error_message = None
                self.set_item_status(file_id, ProgressStatus.PENDING)
                self._logger.info(f"Retrying upload: {file_id}")
        except Exception as e:
            self._logger.error(f"Failed to retry upload {file_id}: {e}")

    def _handle_remove_item(self, file_id: str) -> None:
        """Handle remove individual upload from list."""
        try:
            if file_id in self._progress_items:
                item = self._progress_items[file_id]

                # Update counters
                if item.status == ProgressStatus.COMPLETED:
                    self._completed_files -= 1
                elif item.status == ProgressStatus.FAILED:
                    self._failed_files -= 1

                self._total_files -= 1
                self._total_bytes -= item.file_size
                self._uploaded_bytes -= item.metrics.bytes_uploaded

                # Remove from tracking
                del self._progress_items[file_id]

                # Remove from UI
                for i, control in enumerate(self._progress_list.controls):
                    if hasattr(control, 'data') and control.data == file_id:
                        self._progress_list.controls.pop(i)
                        break

                self._update_overall_progress()
                self.update()

                self._logger.info(f"Removed upload: {file_id}")

        except Exception as e:
            self._logger.error(f"Failed to remove upload {file_id}: {e}")

    # Utility Methods
    def _get_status_color(self, status: ProgressStatus) -> str:
        """Get color for upload status."""
        palette = self.get_palette()

        status_colors = {
            ProgressStatus.PENDING: palette.text_tertiary,
            ProgressStatus.UPLOADING: palette.primary,
            ProgressStatus.PROCESSING: palette.info,
            ProgressStatus.PAUSED: palette.warning,
            ProgressStatus.COMPLETED: palette.success,
            ProgressStatus.FAILED: palette.error,
            ProgressStatus.CANCELLED: palette.text_disabled
        }

        return status_colors.get(status, palette.text_secondary)

    def _get_progress_color(self, status: ProgressStatus) -> str:
        """Get progress bar color for upload status."""
        palette = self.get_palette()

        if status == ProgressStatus.FAILED:
            return palette.error
        elif status == ProgressStatus.PAUSED:
            return palette.warning
        elif status == ProgressStatus.COMPLETED:
            return palette.success
        else:
            return palette.primary

    def _get_file_icon(self, filename: str) -> str:
        """Get appropriate icon for file type."""
        icons = self.get_icons()

        extension = Path(filename).suffix.lower()

        icon_map = {
            '.pdf': icons.PICTURE_AS_PDF,
            '.doc': icons.DESCRIPTION,
            '.docx': icons.DESCRIPTION,
            '.txt': icons.TEXT_SNIPPET,
            '.html': icons.CODE,
            '.htm': icons.CODE,
            '.md': icons.TEXT_SNIPPET,
            '.markdown': icons.TEXT_SNIPPET,
            '.rtf': icons.DESCRIPTION,
            '.odt': icons.DESCRIPTION
        }

        return icon_map.get(extension, icons.INSERT_DRIVE_FILE)

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

        if i == 0:
            return f"{int(size)} {size_names[i]}"
        else:
            return f"{size:.1f} {size_names[i]}"

    def _format_speed(self, bytes_per_second: float) -> str:
        """Format upload speed in human readable format."""
        if bytes_per_second == 0:
            return "0 B/s"

        speed_names = ["B/s", "KB/s", "MB/s", "GB/s"]
        i = 0
        speed = float(bytes_per_second)

        while speed >= 1024.0 and i < len(speed_names) - 1:
            speed /= 1024.0
            i += 1

        if i == 0:
            return f"{int(speed)} {speed_names[i]}"
        else:
            return f"{speed:.1f} {speed_names[i]}"

    def _format_time(self, seconds: float) -> str:
        """Format time duration in human readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    # Public API Methods
    def clear_all_items(self) -> None:
        """Clear all upload items from the list."""
        try:
            self._progress_items.clear()
            self._progress_list.controls.clear()

            # Reset counters
            self._total_files = 0
            self._completed_files = 0
            self._failed_files = 0
            self._total_bytes = 0
            self._uploaded_bytes = 0

            self._update_overall_progress()
            self.update()

            self._logger.info("Cleared all upload items")

        except Exception as e:
            self._logger.error(f"Failed to clear all items: {e}")

    def get_upload_summary(self) -> Dict[str, Any]:
        """Get summary of upload progress."""
        try:
            active_uploads = len([item for item in self._progress_items.values()
                                if item.status == ProgressStatus.UPLOADING])
            paused_uploads = len([item for item in self._progress_items.values()
                                if item.status == ProgressStatus.PAUSED])

            overall_percent = (self._uploaded_bytes / self._total_bytes * 100) if self._total_bytes > 0 else 0.0

            return {
                'total_files': self._total_files,
                'completed_files': self._completed_files,
                'failed_files': self._failed_files,
                'active_uploads': active_uploads,
                'paused_uploads': paused_uploads,
                'total_bytes': self._total_bytes,
                'uploaded_bytes': self._uploaded_bytes,
                'overall_progress_percent': overall_percent,
                'upload_items': list(self._progress_items.values())
            }

        except Exception as e:
            self._logger.error(f"Failed to get upload summary: {e}")
            return {}

    def pause_all_uploads(self) -> None:
        """Pause all active uploads."""
        self._handle_pause_all(None)

    def resume_all_uploads(self) -> None:
        """Resume all paused uploads."""
        self._handle_resume_all(None)

    def cancel_all_uploads(self) -> None:
        """Cancel all active uploads."""
        self._handle_cancel_all(None)

    def clear_completed_uploads(self) -> None:
        """Clear all completed uploads from the list."""
        self._handle_clear_completed(None)
