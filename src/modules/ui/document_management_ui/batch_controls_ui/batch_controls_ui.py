"""
Module: batch_controls_ui
Description: Interface for batch operations including select all, bulk delete, and reprocess
Phase: 4
Location: /src/modules/ui/document_management_ui/batch_controls_ui/
"""

# Standard library imports
import asyncio
from enum import Enum
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)
from src.modules.logic.logging_infrastructure_lg import get_logger


# Initialize logger
logger = get_logger(__name__)


class BatchOperation(Enum):
    """Batch operations available for document management."""
    SELECT_ALL = "select_all"
    DESELECT_ALL = "deselect_all"
    DELETE = "delete"
    REPROCESS = "reprocess"
    EXPORT = "export"
    ARCHIVE = "archive"
    MOVE_TO_FOLDER = "move_to_folder"
    ADD_TAGS = "add_tags"
    REMOVE_TAGS = "remove_tags"
    CHANGE_STATUS = "change_status"
    DUPLICATE = "duplicate"
    VALIDATE = "validate"


class BatchStatus(Enum):
    """Status of batch operations."""
    IDLE = "idle"
    PREPARING = "preparing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class BatchOperationConfig:
    """Configuration for batch operations."""
    operation: BatchOperation
    enabled: bool = True
    requires_confirmation: bool = False
    icon: str = ""
    tooltip: str = ""
    variant: str = "default"


@dataclass
class BatchProgress:
    """Progress tracking for batch operations."""
    operation: BatchOperation
    status: BatchStatus
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100.0
    
    @property
    def is_active(self) -> bool:
        """Check if operation is currently active."""
        return self.status in [BatchStatus.PREPARING, BatchStatus.PROCESSING]


class BatchControlsUI(ThemeAwareUserControl):
    """
    Comprehensive batch controls UI component with responsive design and theme integration.
    
    Features:
    - Responsive batch operation buttons with breakpoint-aware layouts
    - Multiple batch operations (select, delete, reprocess, export, etc.)
    - Progress tracking and status indicators
    - Confirmation dialogs for destructive operations
    - Theme-aware styling with accessibility compliance
    - Integration with document selection system
    - Real-time batch operation feedback
    - Keyboard navigation support
    """

    def __init__(self,
                 selected_count: int = 0,
                 total_count: int = 0,
                 on_batch_operation: Optional[Callable[[BatchOperation, List[Any]], None]] = None,
                 on_selection_change: Optional[Callable[[BatchOperation], None]] = None,
                 enabled_operations: Optional[List[BatchOperation]] = None,
                 **kwargs):
        """
        Initialize batch controls UI.
        
        Args:
            selected_count: Number of currently selected documents
            total_count: Total number of documents available
            on_batch_operation: Callback for batch operations
            on_selection_change: Callback for selection changes
            enabled_operations: List of enabled batch operations
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # State management
        self._selected_count = selected_count
        self._total_count = total_count
        self._on_batch_operation = on_batch_operation
        self._on_selection_change = on_selection_change
        
        # Operation configuration
        self._enabled_operations = enabled_operations or [
            BatchOperation.SELECT_ALL,
            BatchOperation.DESELECT_ALL,
            BatchOperation.DELETE,
            BatchOperation.REPROCESS,
            BatchOperation.EXPORT,
            BatchOperation.ARCHIVE
        ]
        
        # Progress tracking
        self._current_progress: Optional[BatchProgress] = None
        self._operation_configs = self._initialize_operation_configs()
        
        # UI components
        self._controls_container: Optional[ft.Container] = None
        self._progress_container: Optional[ft.Container] = None
        self._confirmation_dialog: Optional[ft.AlertDialog] = None
        
        # Build UI
        self._build_ui()

    def _initialize_operation_configs(self) -> Dict[BatchOperation, BatchOperationConfig]:
        """Initialize operation configurations."""
        return {
            BatchOperation.SELECT_ALL: BatchOperationConfig(
                operation=BatchOperation.SELECT_ALL,
                icon=ft.Icons.SELECT_ALL,
                tooltip="Select all documents",
                variant="text"
            ),
            BatchOperation.DESELECT_ALL: BatchOperationConfig(
                operation=BatchOperation.DESELECT_ALL,
                icon=ft.Icons.DESELECT,
                tooltip="Deselect all documents",
                variant="text"
            ),
            BatchOperation.DELETE: BatchOperationConfig(
                operation=BatchOperation.DELETE,
                icon=ft.Icons.DELETE,
                tooltip="Delete selected documents",
                variant="error",
                requires_confirmation=True
            ),
            BatchOperation.REPROCESS: BatchOperationConfig(
                operation=BatchOperation.REPROCESS,
                icon=ft.Icons.REFRESH,
                tooltip="Reprocess selected documents",
                variant="primary"
            ),
            BatchOperation.EXPORT: BatchOperationConfig(
                operation=BatchOperation.EXPORT,
                icon=ft.Icons.DOWNLOAD,
                tooltip="Export selected documents",
                variant="secondary"
            ),
            BatchOperation.ARCHIVE: BatchOperationConfig(
                operation=BatchOperation.ARCHIVE,
                icon=ft.Icons.ARCHIVE,
                tooltip="Archive selected documents",
                variant="secondary"
            ),
            BatchOperation.ADD_TAGS: BatchOperationConfig(
                operation=BatchOperation.ADD_TAGS,
                icon=ft.Icons.TAG,
                tooltip="Add tags to selected documents",
                variant="secondary"
            ),
            BatchOperation.MOVE_TO_FOLDER: BatchOperationConfig(
                operation=BatchOperation.MOVE_TO_FOLDER,
                icon=ft.Icons.FOLDER_OPEN,
                tooltip="Move selected documents to folder",
                variant="secondary"
            )
        }

    def _build_ui(self):
        """Build the batch controls UI."""
        try:
            # Main container with responsive layout
            self._controls_container = self._build_controls_section()
            self._progress_container = self._build_progress_section()
            
            # Main layout
            main_content = ft.Column(
                controls=[
                    self._controls_container,
                    self._progress_container
                ],
                spacing=self.get_responsive_value(8, 10, 12, 14),
                tight=True
            )
            
            self.content = main_content
            
        except Exception as e:
            logger.error(f"Error building batch controls UI: {e}")
            self.content = ft.Container()

    def _build_controls_section(self) -> ft.Container:
        """Build the main controls section."""
        try:
            responsive_manager = self.get_responsive_layout()
            palette = self.get_palette()
            spacing = self.get_spacing()
            
            # Selection info
            selection_info = self._build_selection_info()
            
            # Operation buttons
            operation_buttons = self._build_operation_buttons()
            
            # Responsive button layout
            buttons_container = ft.Container(
                content=ft.Row(
                    controls=operation_buttons,
                    spacing=spacing.sm,
                    wrap=True,
                    alignment=ft.MainAxisAlignment.START
                ),
                padding=ft.padding.only(top=spacing.xs)
            )
            
            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            selection_info,
                            buttons_container
                        ],
                        spacing=spacing.sm,
                        tight=True
                    ),
                    padding=self.get_responsive_padding()
                )
            )
            
        except Exception as e:
            logger.error(f"Error building controls section: {e}")
            return ft.Container()

    def _build_selection_info(self) -> ft.Container:
        """Build selection information display."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            
            # Selection text
            if self._selected_count == 0:
                selection_text = "No documents selected"
                text_color = palette.text_secondary
            elif self._selected_count == self._total_count and self._total_count > 0:
                selection_text = f"All {self._total_count} documents selected"
                text_color = palette.primary
            else:
                selection_text = f"{self._selected_count} of {self._total_count} documents selected"
                text_color = palette.text_primary
            
            return ft.Container(
                content=ft.Text(
                    selection_text,
                    size=typography.body_medium.size,
                    weight=ft.FontWeight.W_500,
                    color=text_color
                )
            )
            
        except Exception as e:
            logger.error(f"Error building selection info: {e}")
            return ft.Container()

    def _build_operation_buttons(self) -> List[ft.Control]:
        """Build operation buttons based on enabled operations."""
        try:
            buttons = []
            responsive_manager = self.get_responsive_layout()

            # Button size based on breakpoint
            button_height = responsive_manager.get_breakpoint_value(
                mobile=36, tablet=40, desktop=44, large=48
            )

            for operation in self._enabled_operations:
                config = self._operation_configs.get(operation)
                if not config or not config.enabled:
                    continue

                # Determine if button should be enabled
                is_enabled = self._is_operation_enabled(operation)

                # Create button
                button = self.create_themed_component(
                    "button",
                    variant=config.variant,
                    text=self._get_operation_text(operation),
                    icon=config.icon,
                    height=button_height,
                    disabled=not is_enabled,
                    tooltip=config.tooltip,
                    on_click=lambda e, op=operation: self._handle_operation_click(op)
                )

                buttons.append(button)

            return buttons

        except Exception as e:
            logger.error(f"Error building operation buttons: {e}")
            return []

    def _build_progress_section(self) -> ft.Container:
        """Build progress tracking section."""
        try:
            if not self._current_progress or not self._current_progress.is_active:
                return ft.Container(visible=False)

            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            # Progress bar
            progress_bar = ft.ProgressBar(
                value=self._current_progress.progress_percentage / 100.0,
                color=palette.primary,
                bgcolor=palette.surface_variant
            )

            # Progress text
            progress_text = ft.Text(
                f"Processing {self._current_progress.operation.value}: "
                f"{self._current_progress.processed_items}/{self._current_progress.total_items}",
                size=typography.body_small.size,
                color=palette.text_secondary
            )

            # Cancel button
            cancel_button = self.create_themed_component(
                "button",
                variant="text",
                text="Cancel",
                icon=ft.Icons.CANCEL,
                on_click=lambda _: self._cancel_operation()
            )

            return self.create_themed_component(
                "card",
                variant="surface",
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[progress_text, cancel_button],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            ),
                            progress_bar
                        ],
                        spacing=spacing.xs,
                        tight=True
                    ),
                    padding=self.get_responsive_padding()
                )
            )

        except Exception as e:
            logger.error(f"Error building progress section: {e}")
            return ft.Container(visible=False)

    def _is_operation_enabled(self, operation: BatchOperation) -> bool:
        """Check if operation should be enabled."""
        try:
            if operation == BatchOperation.SELECT_ALL:
                return self._selected_count < self._total_count
            elif operation == BatchOperation.DESELECT_ALL:
                return self._selected_count > 0
            else:
                return self._selected_count > 0

        except Exception as e:
            logger.error(f"Error checking operation enabled state: {e}")
            return False

    def _get_operation_text(self, operation: BatchOperation) -> str:
        """Get display text for operation."""
        text_map = {
            BatchOperation.SELECT_ALL: "Select All",
            BatchOperation.DESELECT_ALL: "Deselect All",
            BatchOperation.DELETE: "Delete",
            BatchOperation.REPROCESS: "Reprocess",
            BatchOperation.EXPORT: "Export",
            BatchOperation.ARCHIVE: "Archive",
            BatchOperation.ADD_TAGS: "Add Tags",
            BatchOperation.MOVE_TO_FOLDER: "Move",
            BatchOperation.REMOVE_TAGS: "Remove Tags",
            BatchOperation.CHANGE_STATUS: "Change Status",
            BatchOperation.DUPLICATE: "Duplicate",
            BatchOperation.VALIDATE: "Validate"
        }
        return text_map.get(operation, operation.value.replace("_", " ").title())

    def _handle_operation_click(self, operation: BatchOperation):
        """Handle operation button click."""
        try:
            config = self._operation_configs.get(operation)

            if config and config.requires_confirmation:
                self._show_confirmation_dialog(operation)
            else:
                self._execute_operation(operation)

        except Exception as e:
            logger.error(f"Error handling operation click: {e}")

    def _show_confirmation_dialog(self, operation: BatchOperation):
        """Show confirmation dialog for destructive operations."""
        try:
            palette = self.get_palette()

            operation_text = self._get_operation_text(operation)

            self._confirmation_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Confirm {operation_text}"),
                content=ft.Text(
                    f"Are you sure you want to {operation_text.lower()} "
                    f"{self._selected_count} selected document{'s' if self._selected_count != 1 else ''}?\n\n"
                    f"This action cannot be undone."
                ),
                actions=[
                    self.create_themed_component(
                        "button",
                        variant="text",
                        text="Cancel",
                        on_click=lambda _: self._close_confirmation_dialog()
                    ),
                    self.create_themed_component(
                        "button",
                        variant="error",
                        text=operation_text,
                        on_click=lambda _: self._confirm_operation(operation)
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )

            if self.page:
                self.page.dialog = self._confirmation_dialog
                self._confirmation_dialog.open = True
                self.page.update()

        except Exception as e:
            logger.error(f"Error showing confirmation dialog: {e}")

    def _close_confirmation_dialog(self):
        """Close confirmation dialog."""
        try:
            if self._confirmation_dialog and self.page:
                self._confirmation_dialog.open = False
                self.page.update()

        except Exception as e:
            logger.error(f"Error closing confirmation dialog: {e}")

    def _confirm_operation(self, operation: BatchOperation):
        """Confirm and execute operation."""
        try:
            self._close_confirmation_dialog()
            self._execute_operation(operation)

        except Exception as e:
            logger.error(f"Error confirming operation: {e}")

    def _execute_operation(self, operation: BatchOperation):
        """Execute batch operation."""
        try:
            # Handle selection operations locally
            if operation in [BatchOperation.SELECT_ALL, BatchOperation.DESELECT_ALL]:
                if self._on_selection_change:
                    self._on_selection_change(operation)
                return

            # For other operations, delegate to callback
            if self._on_batch_operation:
                self._on_batch_operation(operation, [])

        except Exception as e:
            logger.error(f"Error executing operation: {e}")

    def _cancel_operation(self):
        """Cancel current batch operation."""
        try:
            if self._current_progress and self._current_progress.is_active:
                self._current_progress.status = BatchStatus.CANCELLED
                self._current_progress.end_time = datetime.now()
                self._update_progress_display()

        except Exception as e:
            logger.error(f"Error cancelling operation: {e}")

    def _update_progress_display(self):
        """Update progress display."""
        try:
            self._progress_container = self._build_progress_section()
            self.update()

        except Exception as e:
            logger.error(f"Error updating progress display: {e}")

    # Public methods for external control

    def update_selection(self, selected_count: int, total_count: int):
        """Update selection counts and refresh UI."""
        try:
            self._selected_count = selected_count
            self._total_count = total_count
            self._build_ui()
            self.update()

        except Exception as e:
            logger.error(f"Error updating selection: {e}")

    def start_batch_operation(self, operation: BatchOperation, total_items: int):
        """Start tracking a batch operation."""
        try:
            self._current_progress = BatchProgress(
                operation=operation,
                status=BatchStatus.PREPARING,
                total_items=total_items,
                start_time=datetime.now()
            )
            self._update_progress_display()

        except Exception as e:
            logger.error(f"Error starting batch operation: {e}")

    def update_batch_progress(self, processed_items: int, failed_items: int = 0):
        """Update batch operation progress."""
        try:
            if self._current_progress:
                self._current_progress.processed_items = processed_items
                self._current_progress.failed_items = failed_items
                self._current_progress.status = BatchStatus.PROCESSING
                self._update_progress_display()

        except Exception as e:
            logger.error(f"Error updating batch progress: {e}")

    def complete_batch_operation(self, success: bool = True, error_message: Optional[str] = None):
        """Complete batch operation."""
        try:
            if self._current_progress:
                self._current_progress.status = BatchStatus.COMPLETED if success else BatchStatus.FAILED
                self._current_progress.end_time = datetime.now()
                self._current_progress.error_message = error_message

                # Hide progress after a delay
                asyncio.create_task(self._hide_progress_after_delay())

        except Exception as e:
            logger.error(f"Error completing batch operation: {e}")

    async def _hide_progress_after_delay(self, delay_seconds: float = 3.0):
        """Hide progress display after delay."""
        try:
            await asyncio.sleep(delay_seconds)
            self._current_progress = None
            self._update_progress_display()

        except Exception as e:
            logger.error(f"Error hiding progress after delay: {e}")

    def set_operation_enabled(self, operation: BatchOperation, enabled: bool):
        """Enable or disable specific operation."""
        try:
            config = self._operation_configs.get(operation)
            if config:
                config.enabled = enabled
                self._build_ui()
                self.update()

        except Exception as e:
            logger.error(f"Error setting operation enabled state: {e}")

    def get_enabled_operations(self) -> List[BatchOperation]:
        """Get list of currently enabled operations."""
        return [op for op in self._enabled_operations
                if self._operation_configs.get(op, BatchOperationConfig(op)).enabled]

    def get_current_progress(self) -> Optional[BatchProgress]:
        """Get current batch operation progress."""
        return self._current_progress

    def build(self) -> ft.Control:
        """Build the batch controls UI component."""
        return self.content if self.content else ft.Container()

    def did_mount(self):
        """Called when component is mounted."""
        super().did_mount()
        try:
            # Register for theme changes
            self._register_theme_callbacks()

        except Exception as e:
            logger.error(f"Error in did_mount: {e}")

    def will_unmount(self):
        """Called when component will be unmounted."""
        try:
            # Clean up resources
            if self._confirmation_dialog and self.page:
                self._confirmation_dialog.open = False

            super().will_unmount()

        except Exception as e:
            logger.error(f"Error in will_unmount: {e}")
