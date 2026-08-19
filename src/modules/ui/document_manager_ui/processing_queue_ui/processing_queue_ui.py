"""
Module: processing_queue_ui
Description: Comprehensive document processing queue management interface with real-time monitoring and control.
            Provides interactive queue visualization, job status tracking, priority management, and batch operations
            with modern UI/UX design, theme-aware styling, and responsive layout. Integrates seamlessly with
            document processing service for live updates and queue management capabilities.
Phase: 3
Location: /src/modules/ui/document_manager_ui/processing_queue_ui/processing_queue_ui.py
"""

# Standard library imports
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union, Tuple

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)
from src.modules.logic.logging_infrastructure_lg import get_logger

# Import processing service components
try:
    from src.modules.logic.document_processing_service_lg.document_processing_service_lg import (
        DocumentProcessingService,
        ProcessingJob,
        ProcessingStage,
        ProcessingPriority,
        ProcessingResult
    )
except ImportError:
    # Fallback for development
    class ProcessingJob:
        pass
    class ProcessingStage:
        pass
    class ProcessingPriority:
        pass
    class ProcessingResult:
        pass
    class DocumentProcessingService:
        pass

# Import database components
try:
    from src.modules.database.document_queue_db.processing_queue_db.processing_queue_db import (
        ProcessingQueueDB,
        QueuePriority,
        QueueStatus as DBQueueStatus,
        OperationType
    )
except ImportError:
    # Fallback for development
    class ProcessingQueueDB:
        pass
    class QueuePriority:
        URGENT = 1
        HIGH = 2
        NORMAL = 3
        LOW = 4
        BACKGROUND = 5
    class DBQueueStatus:
        pass
    class OperationType:
        pass


class QueueStatus(Enum):
    """Processing queue status for UI display."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RETRY = "retry"


class ProcessingState(Enum):
    """Processing state for detailed status tracking."""
    IDLE = "idle"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    ANALYZING = "analyzing"
    STORING = "storing"
    COMPLETED = "completed"
    ERROR = "error"


class QueueViewMode(Enum):
    """Queue view display modes."""
    LIST = "list"
    GRID = "grid"
    COMPACT = "compact"
    DETAILED = "detailed"


class QueueSortOption(Enum):
    """Queue sorting options."""
    CREATED_ASC = "created_asc"
    CREATED_DESC = "created_desc"
    PRIORITY_ASC = "priority_asc"
    PRIORITY_DESC = "priority_desc"
    STATUS_ASC = "status_asc"
    STATUS_DESC = "status_desc"
    PROGRESS_ASC = "progress_asc"
    PROGRESS_DESC = "progress_desc"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"


class QueueFilterOption(Enum):
    """Queue filtering options."""
    ALL = "all"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    HIGH_PRIORITY = "high_priority"
    TODAY = "today"
    THIS_WEEK = "this_week"


@dataclass
class QueueItem:
    """Individual queue item for UI display."""
    item_id: str
    document_name: str
    file_path: Path
    status: QueueStatus
    processing_state: ProcessingState
    priority: int = 3  # Default normal priority
    operation: str = "INGEST"
    progress: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    file_size: int = 0
    processing_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate processing duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return datetime.now(timezone.utc) - self.started_at
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if item is actively processing."""
        return self.status in [QueueStatus.PROCESSING, QueueStatus.QUEUED]
    
    @property
    def can_retry(self) -> bool:
        """Check if item can be retried."""
        return (self.status == QueueStatus.FAILED and 
                self.retry_count < self.max_retries)
    
    @property
    def can_cancel(self) -> bool:
        """Check if item can be cancelled."""
        return self.status in [QueueStatus.PENDING, QueueStatus.QUEUED, QueueStatus.PROCESSING]


@dataclass
class QueueConfig:
    """Configuration for processing queue UI."""
    view_mode: QueueViewMode = QueueViewMode.LIST
    auto_refresh: bool = True
    refresh_interval_seconds: float = 2.0
    show_completed: bool = True
    show_failed: bool = True
    max_items_display: int = 100
    enable_batch_operations: bool = True
    enable_priority_management: bool = True
    enable_real_time_updates: bool = True
    show_progress_details: bool = True
    show_time_estimates: bool = True
    enable_notifications: bool = True
    compact_mode_threshold: int = 768  # Breakpoint for compact mode


class ProcessingQueueUI(ThemeAwareUserControl):
    """
    Comprehensive processing queue management interface.
    
    Features:
    - Real-time queue monitoring with live updates
    - Interactive queue item management and controls
    - Responsive design with breakpoint-aware layouts
    - Theme-aware styling with accessibility compliance
    - Batch operations and priority management
    - Progress tracking and time estimation
    - Error handling and retry mechanisms
    - Integration with document processing service
    - Performance optimization with virtual scrolling
    - Keyboard navigation and screen reader support
    """
    
    def __init__(self,
                 config: Optional[QueueConfig] = None,
                 processing_service: Optional[DocumentProcessingService] = None,
                 on_item_selected: Optional[Callable[[QueueItem], None]] = None,
                 on_item_action: Optional[Callable[[str, QueueItem], None]] = None,
                 on_batch_action: Optional[Callable[[str, List[QueueItem]], None]] = None,
                 on_queue_updated: Optional[Callable[[List[QueueItem]], None]] = None,
                 **kwargs):
        """
        Initialize the ProcessingQueueUI component.
        
        Args:
            config: Queue configuration
            processing_service: Document processing service instance
            on_item_selected: Callback when queue item is selected
            on_item_action: Callback for individual item actions
            on_batch_action: Callback for batch operations
            on_queue_updated: Callback when queue is updated
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or QueueConfig()
        self._processing_service = processing_service
        
        # Callbacks
        self._on_item_selected = on_item_selected
        self._on_item_action = on_item_action
        self._on_batch_action = on_batch_action
        self._on_queue_updated = on_queue_updated
        
        # State
        self._queue_items: List[QueueItem] = []
        self._selected_items: List[str] = []
        self._current_filter = QueueFilterOption.ALL
        self._current_sort = QueueSortOption.CREATED_DESC
        self._search_query = ""
        self._is_refreshing = False
        self._refresh_timer: Optional[asyncio.Task] = None
        
        # UI Components
        self._header_container: Optional[ft.Container] = None
        self._toolbar_container: Optional[ft.Container] = None
        self._queue_list_container: Optional[ft.Container] = None
        self._status_bar_container: Optional[ft.Container] = None
        self._queue_list: Optional[ft.ListView] = None
        self._search_field: Optional[ft.TextField] = None
        self._filter_dropdown: Optional[ft.Dropdown] = None
        self._sort_dropdown: Optional[ft.Dropdown] = None
        self._view_mode_buttons: Optional[ft.Row] = None
        self._batch_controls: Optional[ft.Row] = None
        
        # Logger
        self._logger = get_logger(__name__)
        
        # Initialize UI
        self._build_ui()
        
        # Start auto-refresh if enabled
        if self._config.auto_refresh and self._config.enable_real_time_updates:
            self._start_auto_refresh()
    
    def _build_ui(self):
        """Build the complete queue interface."""
        try:
            # Get theme manager and responsive layout
            theme_manager = get_theme_manager()
            palette = self.get_palette()
            spacing = self.get_spacing()
            
            # Build header
            self._build_header()
            
            # Build toolbar
            self._build_toolbar()
            
            # Build queue list
            self._build_queue_list()
            
            # Build status bar
            self._build_status_bar()
            
            # Main layout
            self.content = ft.Column(
                controls=[
                    self._header_container,
                    self._toolbar_container,
                    ft.Divider(height=1, color=palette.outline),
                    self._queue_list_container,
                    self._status_bar_container
                ],
                spacing=0,
                expand=True
            )
            
        except Exception as e:
            self._logger.error(f"Failed to build queue UI: {e}")
            self._show_error_state(str(e))

    def _build_header(self):
        """Build the queue header with title and summary."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            responsive_manager = self.get_responsive_layout_manager()

            # Title
            title = ft.Text(
                "Processing Queue",
                style=self.get_text_style("heading_large"),
                color=palette.text_primary
            )

            # Queue summary
            summary = ft.Text(
                "0 items in queue",
                style=self.get_text_style("body_medium"),
                color=palette.text_secondary
            )

            # Refresh button
            refresh_button = ft.IconButton(
                icon=ft.Icons.REFRESH,
                icon_color=palette.primary,
                tooltip="Refresh queue",
                on_click=self._handle_refresh_click
            )

            # Auto-refresh toggle
            auto_refresh_toggle = ft.Switch(
                value=self._config.auto_refresh,
                active_color=palette.primary,
                on_change=self._handle_auto_refresh_toggle
            )

            auto_refresh_label = ft.Text(
                "Auto-refresh",
                style=self.get_text_style("body_small"),
                color=palette.text_secondary
            )

            # Header layout
            header_content = ft.Row(
                controls=[
                    ft.Column(
                        controls=[title, summary],
                        spacing=spacing.xs,
                        expand=True
                    ),
                    ft.Row(
                        controls=[
                            auto_refresh_label,
                            auto_refresh_toggle,
                            refresh_button
                        ],
                        spacing=spacing.sm,
                        alignment=ft.MainAxisAlignment.END
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )

            self._header_container = ft.Container(
                content=header_content,
                padding=ft.padding.all(spacing.lg),
                bgcolor=palette.surface
            )

        except Exception as e:
            self._logger.error(f"Failed to build header: {e}")

    def _build_toolbar(self):
        """Build the queue toolbar with controls and filters."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            responsive_manager = self.get_responsive_layout()

            # Search field
            self._search_field = ft.TextField(
                hint_text="Search queue items...",
                prefix_icon=ft.Icons.SEARCH,
                border_color=palette.outline,
                focused_border_color=palette.primary,
                on_change=self._handle_search_change,
                expand=True
            )

            # Filter dropdown
            self._filter_dropdown = ft.Dropdown(
                label="Filter",
                options=[
                    ft.dropdown.Option(key=option.value, text=option.value.replace("_", " ").title())
                    for option in QueueFilterOption
                ],
                value=self._current_filter.value,
                on_change=self._handle_filter_change,
                width=responsive_manager.get_breakpoint_value(120, 140, 160, 180)
            )

            # Sort dropdown
            self._sort_dropdown = ft.Dropdown(
                label="Sort",
                options=[
                    ft.dropdown.Option(key=option.value, text=option.value.replace("_", " ").title())
                    for option in QueueSortOption
                ],
                value=self._current_sort.value,
                on_change=self._handle_sort_change,
                width=responsive_manager.get_breakpoint_value(120, 140, 160, 180)
            )

            # View mode buttons
            self._build_view_mode_buttons()

            # Batch controls
            self._build_batch_controls()

            # Toolbar layout
            toolbar_content = ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self._search_field,
                            self._filter_dropdown,
                            self._sort_dropdown
                        ],
                        spacing=spacing.sm,
                        alignment=ft.MainAxisAlignment.START
                    ),
                    ft.Row(
                        controls=[
                            self._view_mode_buttons,
                            ft.VerticalDivider(width=1, color=palette.outline),
                            self._batch_controls
                        ],
                        spacing=spacing.sm,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ],
                spacing=spacing.sm
            )

            self._toolbar_container = ft.Container(
                content=toolbar_content,
                padding=ft.padding.all(spacing.lg),
                bgcolor=palette.surface_variant
            )

        except Exception as e:
            self._logger.error(f"Failed to build toolbar: {e}")

    def _build_view_mode_buttons(self):
        """Build view mode toggle buttons."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # View mode buttons
            list_button = ft.IconButton(
                icon=ft.Icons.LIST,
                selected=self._config.view_mode == QueueViewMode.LIST,
                selected_icon_color=palette.primary,
                icon_color=palette.text_secondary,
                tooltip="List view",
                on_click=lambda _: self._handle_view_mode_change(QueueViewMode.LIST)
            )

            grid_button = ft.IconButton(
                icon=ft.Icons.GRID_VIEW,
                selected=self._config.view_mode == QueueViewMode.GRID,
                selected_icon_color=palette.primary,
                icon_color=palette.text_secondary,
                tooltip="Grid view",
                on_click=lambda _: self._handle_view_mode_change(QueueViewMode.GRID)
            )

            compact_button = ft.IconButton(
                icon=ft.Icons.VIEW_COMPACT,
                selected=self._config.view_mode == QueueViewMode.COMPACT,
                selected_icon_color=palette.primary,
                icon_color=palette.text_secondary,
                tooltip="Compact view",
                on_click=lambda _: self._handle_view_mode_change(QueueViewMode.COMPACT)
            )

            self._view_mode_buttons = ft.Row(
                controls=[list_button, grid_button, compact_button],
                spacing=spacing.xs
            )

        except Exception as e:
            self._logger.error(f"Failed to build view mode buttons: {e}")

    def _build_batch_controls(self):
        """Build batch operation controls."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Batch action buttons
            pause_all_button = ft.ElevatedButton(
                text="Pause All",
                icon=ft.Icons.PAUSE,
                on_click=lambda _: self._handle_batch_action("pause"),
                disabled=True
            )

            resume_all_button = ft.ElevatedButton(
                text="Resume All",
                icon=ft.Icons.PLAY_ARROW,
                on_click=lambda _: self._handle_batch_action("resume"),
                disabled=True
            )

            cancel_all_button = ft.ElevatedButton(
                text="Cancel All",
                icon=ft.Icons.CANCEL,
                on_click=lambda _: self._handle_batch_action("cancel"),
                disabled=True,
                bgcolor=palette.error,
                color=palette.text_primary
            )

            clear_completed_button = ft.ElevatedButton(
                text="Clear Completed",
                icon=ft.Icons.CLEAR_ALL,
                on_click=lambda _: self._handle_batch_action("clear_completed"),
                disabled=True
            )

            self._batch_controls = ft.Row(
                controls=[
                    pause_all_button,
                    resume_all_button,
                    cancel_all_button,
                    clear_completed_button
                ],
                spacing=spacing.sm
            )

        except Exception as e:
            self._logger.error(f"Failed to build batch controls: {e}")

    def _build_queue_list(self):
        """Build the main queue list container."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Queue list view
            self._queue_list = ft.ListView(
                controls=[],
                spacing=spacing.xs,
                padding=ft.padding.all(spacing.sm),
                expand=True,
                auto_scroll=False
            )

            # Empty state
            empty_state = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.QUEUE,
                            size=64,
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            "No items in queue",
                            style=self.get_text_style("heading_small"),
                            color=palette.text_secondary
                        ),
                        ft.Text(
                            "Upload documents to start processing",
                            style=self.get_text_style("body_medium"),
                            color=palette.text_secondary
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.lg
                ),
                alignment=ft.alignment.center,
                expand=True
            )

            # Stack for list and empty state
            queue_stack = ft.Stack(
                controls=[
                    self._queue_list,
                    empty_state
                ],
                expand=True
            )

            self._queue_list_container = ft.Container(
                content=queue_stack,
                bgcolor=palette.surface,
                expand=True
            )

        except Exception as e:
            self._logger.error(f"Failed to build queue list: {e}")

    def _build_status_bar(self):
        """Build the status bar with queue statistics."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Status indicators
            total_items = ft.Text(
                "Total: 0",
                style=self.get_text_style("body_small"),
                color=palette.text_secondary
            )

            processing_items = ft.Text(
                "Processing: 0",
                style=self.get_text_style("body_small"),
                color=palette.primary
            )

            completed_items = ft.Text(
                "Completed: 0",
                style=self.get_text_style("body_small"),
                color=palette.success if hasattr(palette, 'success') else palette.primary
            )

            failed_items = ft.Text(
                "Failed: 0",
                style=self.get_text_style("body_small"),
                color=palette.error
            )

            # Last updated indicator
            last_updated = ft.Text(
                "Last updated: Never",
                style=self.get_text_style("body_small"),
                color=palette.text_secondary
            )

            # Status bar layout
            status_content = ft.Row(
                controls=[
                    total_items,
                    ft.VerticalDivider(width=1, color=palette.outline),
                    processing_items,
                    ft.VerticalDivider(width=1, color=palette.outline),
                    completed_items,
                    ft.VerticalDivider(width=1, color=palette.outline),
                    failed_items,
                    ft.Container(expand=True),  # Spacer
                    last_updated
                ],
                spacing=spacing.sm,
                alignment=ft.MainAxisAlignment.START
            )

            self._status_bar_container = ft.Container(
                content=status_content,
                padding=ft.padding.all(spacing.sm),
                bgcolor=palette.surface_variant,
                border=ft.border.only(top=ft.BorderSide(1, palette.outline))
            )

        except Exception as e:
            self._logger.error(f"Failed to build status bar: {e}")

    def _create_queue_item_widget(self, item: QueueItem) -> ft.Container:
        """Create a widget for a queue item."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            responsive_manager = self.get_responsive_layout()

            # Status icon and color
            status_icon, status_color = self._get_status_icon_and_color(item.status)

            # Priority indicator
            priority_color = self._get_priority_color(item.priority)
            priority_indicator = ft.Container(
                width=4,
                height=responsive_manager.get_breakpoint_value(40, 50, 60, 70),
                bgcolor=priority_color
            )

            # Document name and path
            document_name = ft.Text(
                item.document_name,
                style=self.get_text_style("body_large"),
                color=palette.text_primary,
                weight=ft.FontWeight.W_500,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            file_path_text = ft.Text(
                str(item.file_path),
                style=self.get_text_style("body_small"),
                color=palette.text_secondary,
                overflow=ft.TextOverflow.ELLIPSIS
            )

            # Status and progress
            status_text = ft.Text(
                item.status.value.title(),
                style=self.get_text_style("body_medium"),
                color=status_color,
                weight=ft.FontWeight.W_500
            )

            # Progress bar
            progress_bar = ft.ProgressBar(
                value=item.progress / 100.0 if item.progress > 0 else None,
                color=palette.primary,
                bgcolor=palette.surface_variant,
                height=4
            )

            progress_text = ft.Text(
                f"{item.progress:.1f}%" if item.progress > 0 else "Waiting...",
                style=self.get_text_style("body_small"),
                color=palette.text_secondary
            )

            # Time information
            time_info = self._get_time_info_text(item)

            # Action buttons
            action_buttons = self._create_item_action_buttons(item)

            # Main content layout
            if self._config.view_mode == QueueViewMode.COMPACT:
                content = self._create_compact_item_layout(
                    item, priority_indicator, document_name, status_text,
                    progress_bar, action_buttons
                )
            else:
                content = self._create_detailed_item_layout(
                    item, priority_indicator, document_name, file_path_text,
                    status_text, progress_bar, progress_text, time_info, action_buttons
                )

            # Item container
            item_container = ft.Container(
                content=content,
                padding=ft.padding.all(spacing.lg),
                margin=ft.margin.only(bottom=spacing.xs),
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.outline),
                border_radius=8,
                on_click=lambda _: self._handle_item_click(item),
                ink=True
            )

            return item_container

        except Exception as e:
            self._logger.error(f"Failed to create queue item widget: {e}")
            return ft.Container()  # Return empty container on error

    def _create_compact_item_layout(self, item: QueueItem, priority_indicator: ft.Container,
                                   document_name: ft.Text, status_text: ft.Text,
                                   progress_bar: ft.ProgressBar, action_buttons: ft.Row) -> ft.Row:
        """Create compact layout for queue item."""
        return ft.Row(
            controls=[
                priority_indicator,
                ft.Container(width=self.get_spacing().small),
                ft.Column(
                    controls=[document_name, progress_bar],
                    spacing=self.get_spacing().xs,
                    expand=True
                ),
                status_text,
                action_buttons
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _create_detailed_item_layout(self, item: QueueItem, priority_indicator: ft.Container,
                                    document_name: ft.Text, file_path_text: ft.Text,
                                    status_text: ft.Text, progress_bar: ft.ProgressBar,
                                    progress_text: ft.Text, time_info: ft.Text,
                                    action_buttons: ft.Row) -> ft.Row:
        """Create detailed layout for queue item."""
        return ft.Row(
            controls=[
                priority_indicator,
                ft.Container(width=self.get_spacing().small),
                ft.Column(
                    controls=[
                        document_name,
                        file_path_text,
                        ft.Row(
                            controls=[progress_bar, progress_text],
                            spacing=self.get_spacing().small
                        ),
                        time_info
                    ],
                    spacing=self.get_spacing().xs,
                    expand=True
                ),
                ft.Column(
                    controls=[status_text, action_buttons],
                    spacing=self.get_spacing().small,
                    horizontal_alignment=ft.CrossAxisAlignment.END
                )
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START
        )

    def _create_item_action_buttons(self, item: QueueItem) -> ft.Row:
        """Create action buttons for queue item."""
        try:
            palette = self.get_palette()
            buttons = []

            if item.can_cancel:
                cancel_button = ft.IconButton(
                    icon=ft.Icons.CANCEL,
                    icon_color=palette.error,
                    tooltip="Cancel",
                    on_click=lambda _: self._handle_item_action("cancel", item)
                )
                buttons.append(cancel_button)

            if item.status == QueueStatus.PAUSED:
                resume_button = ft.IconButton(
                    icon=ft.Icons.PLAY_ARROW,
                    icon_color=palette.primary,
                    tooltip="Resume",
                    on_click=lambda _: self._handle_item_action("resume", item)
                )
                buttons.append(resume_button)
            elif item.is_active:
                pause_button = ft.IconButton(
                    icon=ft.Icons.PAUSE,
                    icon_color=palette.primary,
                    tooltip="Pause",
                    on_click=lambda _: self._handle_item_action("pause", item)
                )
                buttons.append(pause_button)

            if item.can_retry:
                retry_button = ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color=palette.primary,
                    tooltip="Retry",
                    on_click=lambda _: self._handle_item_action("retry", item)
                )
                buttons.append(retry_button)

            if item.status in [QueueStatus.COMPLETED, QueueStatus.FAILED, QueueStatus.CANCELLED]:
                remove_button = ft.IconButton(
                    icon=ft.Icons.DELETE,
                    icon_color=palette.error,
                    tooltip="Remove",
                    on_click=lambda _: self._handle_item_action("remove", item)
                )
                buttons.append(remove_button)

            return ft.Row(controls=buttons, spacing=self.get_spacing().xs)

        except Exception as e:
            self._logger.error(f"Failed to create action buttons: {e}")
            return ft.Row()

    def _get_status_icon_and_color(self, status: QueueStatus) -> Tuple[str, str]:
        """Get status icon and color for queue item."""
        palette = self.get_palette()

        status_map = {
            QueueStatus.PENDING: (ft.Icons.SCHEDULE, palette.text_secondary),
            QueueStatus.QUEUED: (ft.Icons.QUEUE, palette.primary),
            QueueStatus.PROCESSING: (ft.Icons.SYNC, palette.primary),
            QueueStatus.COMPLETED: (ft.Icons.CHECK_CIRCLE, getattr(palette, 'success', palette.primary)),
            QueueStatus.FAILED: (ft.Icons.ERROR, palette.error),
            QueueStatus.CANCELLED: (ft.Icons.CANCEL, palette.text_secondary),
            QueueStatus.PAUSED: (ft.Icons.PAUSE_CIRCLE, getattr(palette, 'warning', palette.primary)),
            QueueStatus.RETRY: (ft.Icons.REFRESH, palette.primary)
        }

        return status_map.get(status, (ft.Icons.HELP, palette.text_secondary))

    def _get_priority_color(self, priority: int) -> str:
        """Get color for priority indicator."""
        palette = self.get_palette()

        if priority <= 1:  # Urgent
            return palette.error
        elif priority == 2:  # High
            return getattr(palette, 'warning', palette.primary)
        elif priority == 3:  # Normal
            return palette.primary
        elif priority == 4:  # Low
            return palette.text_secondary
        else:  # Background
            return palette.outline

    def _get_time_info_text(self, item: QueueItem) -> ft.Text:
        """Get time information text for queue item."""
        palette = self.get_palette()

        if item.completed_at:
            duration = item.duration
            if duration:
                time_text = f"Completed in {self._format_duration(duration)}"
            else:
                time_text = "Completed"
        elif item.started_at:
            duration = item.duration
            if duration:
                time_text = f"Running for {self._format_duration(duration)}"
            else:
                time_text = "Just started"
        elif item.estimated_completion:
            eta = item.estimated_completion - datetime.now(timezone.utc)
            if eta.total_seconds() > 0:
                time_text = f"ETA: {self._format_duration(eta)}"
            else:
                time_text = "Starting soon"
        else:
            time_text = f"Created {self._format_relative_time(item.created_at)}"

        return ft.Text(
            time_text,
            style=self.get_text_style("body_small"),
            color=palette.text_secondary
        )

    def _format_duration(self, duration: timedelta) -> str:
        """Format duration for display."""
        total_seconds = int(duration.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def _format_relative_time(self, timestamp: datetime) -> str:
        """Format relative time for display."""
        now = datetime.now(timezone.utc)
        diff = now - timestamp

        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

    # Event Handlers
    def _handle_refresh_click(self, e):
        """Handle refresh button click."""
        asyncio.create_task(self.refresh_queue())

    def _handle_auto_refresh_toggle(self, e):
        """Handle auto-refresh toggle."""
        self._config.auto_refresh = e.control.value
        if self._config.auto_refresh:
            self._start_auto_refresh()
        else:
            self._stop_auto_refresh()

    def _handle_search_change(self, e):
        """Handle search query change."""
        self._search_query = e.control.value
        self._apply_filters_and_sort()

    def _handle_filter_change(self, e):
        """Handle filter dropdown change."""
        try:
            self._current_filter = QueueFilterOption(e.control.value)
            self._apply_filters_and_sort()
        except ValueError:
            self._logger.warning(f"Invalid filter option: {e.control.value}")

    def _handle_sort_change(self, e):
        """Handle sort dropdown change."""
        try:
            self._current_sort = QueueSortOption(e.control.value)
            self._apply_filters_and_sort()
        except ValueError:
            self._logger.warning(f"Invalid sort option: {e.control.value}")

    def _handle_view_mode_change(self, mode: QueueViewMode):
        """Handle view mode change."""
        self._config.view_mode = mode
        self._update_view_mode_buttons()
        self._refresh_queue_display()

    def _handle_item_click(self, item: QueueItem):
        """Handle queue item click."""
        if self._on_item_selected:
            self._on_item_selected(item)

    def _handle_item_action(self, action: str, item: QueueItem):
        """Handle individual item action."""
        if self._on_item_action:
            self._on_item_action(action, item)

        # Handle common actions
        if action == "cancel":
            self._cancel_item(item)
        elif action == "pause":
            self._pause_item(item)
        elif action == "resume":
            self._resume_item(item)
        elif action == "retry":
            self._retry_item(item)
        elif action == "remove":
            self._remove_item(item)

    def _handle_batch_action(self, action: str):
        """Handle batch operation."""
        selected_items = [item for item in self._queue_items if item.item_id in self._selected_items]

        if self._on_batch_action:
            self._on_batch_action(action, selected_items)

        # Handle common batch actions
        if action == "pause":
            for item in selected_items:
                if item.is_active:
                    self._pause_item(item)
        elif action == "resume":
            for item in selected_items:
                if item.status == QueueStatus.PAUSED:
                    self._resume_item(item)
        elif action == "cancel":
            for item in selected_items:
                if item.can_cancel:
                    self._cancel_item(item)
        elif action == "clear_completed":
            completed_items = [item for item in self._queue_items
                             if item.status in [QueueStatus.COMPLETED, QueueStatus.FAILED, QueueStatus.CANCELLED]]
            for item in completed_items:
                self._remove_item(item)

    # Queue Management Methods
    def _cancel_item(self, item: QueueItem):
        """Cancel a queue item."""
        try:
            if self._processing_service:
                # Cancel through processing service
                self._processing_service.cancel_job(item.item_id)

            # Update item status
            item.status = QueueStatus.CANCELLED
            self._refresh_queue_display()

            self._logger.info(f"Cancelled queue item: {item.item_id}")

        except Exception as e:
            self._logger.error(f"Failed to cancel item {item.item_id}: {e}")

    def _pause_item(self, item: QueueItem):
        """Pause a queue item."""
        try:
            if self._processing_service:
                # Pause through processing service
                self._processing_service.pause_job(item.item_id)

            # Update item status
            item.status = QueueStatus.PAUSED
            self._refresh_queue_display()

            self._logger.info(f"Paused queue item: {item.item_id}")

        except Exception as e:
            self._logger.error(f"Failed to pause item {item.item_id}: {e}")

    def _resume_item(self, item: QueueItem):
        """Resume a queue item."""
        try:
            if self._processing_service:
                # Resume through processing service
                self._processing_service.resume_job(item.item_id)

            # Update item status
            item.status = QueueStatus.QUEUED
            self._refresh_queue_display()

            self._logger.info(f"Resumed queue item: {item.item_id}")

        except Exception as e:
            self._logger.error(f"Failed to resume item {item.item_id}: {e}")

    def _retry_item(self, item: QueueItem):
        """Retry a failed queue item."""
        try:
            if self._processing_service:
                # Retry through processing service
                self._processing_service.retry_job(item.item_id)

            # Update item status
            item.status = QueueStatus.QUEUED
            item.retry_count += 1
            item.error_message = None
            self._refresh_queue_display()

            self._logger.info(f"Retrying queue item: {item.item_id}")

        except Exception as e:
            self._logger.error(f"Failed to retry item {item.item_id}: {e}")

    def _remove_item(self, item: QueueItem):
        """Remove a queue item."""
        try:
            # Remove from queue
            self._queue_items = [qi for qi in self._queue_items if qi.item_id != item.item_id]

            # Remove from selected items
            if item.item_id in self._selected_items:
                self._selected_items.remove(item.item_id)

            self._refresh_queue_display()

            self._logger.info(f"Removed queue item: {item.item_id}")

        except Exception as e:
            self._logger.error(f"Failed to remove item {item.item_id}: {e}")

    # Queue Update Methods
    async def refresh_queue(self):
        """Refresh the queue from processing service."""
        if self._is_refreshing:
            return

        try:
            self._is_refreshing = True

            if self._processing_service:
                # Get queue items from processing service
                jobs = self._processing_service.get_active_jobs()

                # Convert to queue items
                queue_items = []
                for job_id, job in jobs.items():
                    queue_item = self._convert_job_to_queue_item(job)
                    queue_items.append(queue_item)

                self._queue_items = queue_items

            # Apply filters and sorting
            self._apply_filters_and_sort()

            # Update display
            self._refresh_queue_display()

            # Update status bar
            self._update_status_bar()

            # Notify callback
            if self._on_queue_updated:
                self._on_queue_updated(self._queue_items)

            self._logger.debug(f"Queue refreshed with {len(self._queue_items)} items")

        except Exception as e:
            self._logger.error(f"Failed to refresh queue: {e}")
        finally:
            self._is_refreshing = False

    def _convert_job_to_queue_item(self, job) -> QueueItem:
        """Convert processing job to queue item."""
        try:
            # Map processing stage to processing state
            state_map = {
                "QUEUED": ProcessingState.IDLE,
                "VALIDATING": ProcessingState.VALIDATING,
                "EXTRACTING": ProcessingState.EXTRACTING,
                "CHUNKING": ProcessingState.CHUNKING,
                "ANALYZING": ProcessingState.ANALYZING,
                "STORING": ProcessingState.STORING,
                "COMPLETED": ProcessingState.COMPLETED,
                "FAILED": ProcessingState.ERROR
            }

            # Map processing stage to queue status
            status_map = {
                "QUEUED": QueueStatus.QUEUED,
                "VALIDATING": QueueStatus.PROCESSING,
                "EXTRACTING": QueueStatus.PROCESSING,
                "CHUNKING": QueueStatus.PROCESSING,
                "ANALYZING": QueueStatus.PROCESSING,
                "STORING": QueueStatus.PROCESSING,
                "COMPLETED": QueueStatus.COMPLETED,
                "FAILED": QueueStatus.FAILED
            }

            processing_state = state_map.get(str(job.stage), ProcessingState.IDLE)
            queue_status = status_map.get(str(job.stage), QueueStatus.PENDING)

            return QueueItem(
                item_id=job.job_id,
                document_name=job.file_path.name,
                file_path=job.file_path,
                status=queue_status,
                processing_state=processing_state,
                priority=getattr(job, 'priority', 3),
                operation="INGEST",
                progress=getattr(job, 'progress', 0.0),
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_message=job.error_message,
                retry_count=getattr(job, 'retry_count', 0),
                metadata=getattr(job, 'metadata', {})
            )

        except Exception as e:
            self._logger.error(f"Failed to convert job to queue item: {e}")
            return QueueItem(
                item_id=str(uuid.uuid4()),
                document_name="Unknown",
                file_path=Path("unknown"),
                status=QueueStatus.FAILED,
                processing_state=ProcessingState.ERROR
            )

    def _apply_filters_and_sort(self):
        """Apply current filters and sorting to queue items."""
        try:
            filtered_items = self._queue_items.copy()

            # Apply search filter
            if self._search_query:
                query = self._search_query.lower()
                filtered_items = [
                    item for item in filtered_items
                    if query in item.document_name.lower() or
                       query in str(item.file_path).lower()
                ]

            # Apply status filter
            if self._current_filter != QueueFilterOption.ALL:
                if self._current_filter == QueueFilterOption.PENDING:
                    filtered_items = [item for item in filtered_items if item.status == QueueStatus.PENDING]
                elif self._current_filter == QueueFilterOption.PROCESSING:
                    filtered_items = [item for item in filtered_items if item.status == QueueStatus.PROCESSING]
                elif self._current_filter == QueueFilterOption.COMPLETED:
                    filtered_items = [item for item in filtered_items if item.status == QueueStatus.COMPLETED]
                elif self._current_filter == QueueFilterOption.FAILED:
                    filtered_items = [item for item in filtered_items if item.status == QueueStatus.FAILED]
                elif self._current_filter == QueueFilterOption.HIGH_PRIORITY:
                    filtered_items = [item for item in filtered_items if item.priority <= 2]
                elif self._current_filter == QueueFilterOption.TODAY:
                    today = datetime.now(timezone.utc).date()
                    filtered_items = [item for item in filtered_items if item.created_at.date() == today]
                elif self._current_filter == QueueFilterOption.THIS_WEEK:
                    week_start = datetime.now(timezone.utc) - timedelta(days=7)
                    filtered_items = [item for item in filtered_items if item.created_at >= week_start]

            # Apply sorting
            if self._current_sort == QueueSortOption.CREATED_ASC:
                filtered_items.sort(key=lambda x: x.created_at)
            elif self._current_sort == QueueSortOption.CREATED_DESC:
                filtered_items.sort(key=lambda x: x.created_at, reverse=True)
            elif self._current_sort == QueueSortOption.PRIORITY_ASC:
                filtered_items.sort(key=lambda x: x.priority)
            elif self._current_sort == QueueSortOption.PRIORITY_DESC:
                filtered_items.sort(key=lambda x: x.priority, reverse=True)
            elif self._current_sort == QueueSortOption.STATUS_ASC:
                filtered_items.sort(key=lambda x: x.status.value)
            elif self._current_sort == QueueSortOption.STATUS_DESC:
                filtered_items.sort(key=lambda x: x.status.value, reverse=True)
            elif self._current_sort == QueueSortOption.PROGRESS_ASC:
                filtered_items.sort(key=lambda x: x.progress)
            elif self._current_sort == QueueSortOption.PROGRESS_DESC:
                filtered_items.sort(key=lambda x: x.progress, reverse=True)
            elif self._current_sort == QueueSortOption.NAME_ASC:
                filtered_items.sort(key=lambda x: x.document_name.lower())
            elif self._current_sort == QueueSortOption.NAME_DESC:
                filtered_items.sort(key=lambda x: x.document_name.lower(), reverse=True)

            # Limit items if configured
            if self._config.max_items_display > 0:
                filtered_items = filtered_items[:self._config.max_items_display]

            self._filtered_queue_items = filtered_items

        except Exception as e:
            self._logger.error(f"Failed to apply filters and sort: {e}")
            self._filtered_queue_items = self._queue_items.copy()

    def _refresh_queue_display(self):
        """Refresh the queue display with current items."""
        try:
            if not self._queue_list:
                return

            # Clear current items
            self._queue_list.controls.clear()

            # Add filtered items
            if hasattr(self, '_filtered_queue_items'):
                items_to_display = self._filtered_queue_items
            else:
                items_to_display = self._queue_items

            for item in items_to_display:
                item_widget = self._create_queue_item_widget(item)
                self._queue_list.controls.append(item_widget)

            # Update empty state visibility
            if self._queue_list_container and hasattr(self._queue_list_container.content, 'controls'):
                stack_controls = self._queue_list_container.content.controls
                if len(stack_controls) >= 2:
                    # Show/hide empty state
                    empty_state = stack_controls[1]
                    empty_state.visible = len(items_to_display) == 0

            # Update the page
            if self.page:
                self.page.update()

        except Exception as e:
            self._logger.error(f"Failed to refresh queue display: {e}")

    def _update_status_bar(self):
        """Update the status bar with current statistics."""
        try:
            if not self._status_bar_container:
                return

            # Calculate statistics
            total_count = len(self._queue_items)
            processing_count = len([item for item in self._queue_items if item.status == QueueStatus.PROCESSING])
            completed_count = len([item for item in self._queue_items if item.status == QueueStatus.COMPLETED])
            failed_count = len([item for item in self._queue_items if item.status == QueueStatus.FAILED])

            # Update status texts
            status_row = self._status_bar_container.content
            if isinstance(status_row, ft.Row) and len(status_row.controls) >= 8:
                # Update text controls
                status_row.controls[0].value = f"Total: {total_count}"
                status_row.controls[2].value = f"Processing: {processing_count}"
                status_row.controls[4].value = f"Completed: {completed_count}"
                status_row.controls[6].value = f"Failed: {failed_count}"
                status_row.controls[-1].value = f"Last updated: {datetime.now().strftime('%H:%M:%S')}"

            # Update the page
            if self.page:
                self.page.update()

        except Exception as e:
            self._logger.error(f"Failed to update status bar: {e}")

    def _update_view_mode_buttons(self):
        """Update view mode button states."""
        try:
            if not self._view_mode_buttons:
                return

            # Update button states
            for i, button in enumerate(self._view_mode_buttons.controls):
                if isinstance(button, ft.IconButton):
                    if i == 0:  # List button
                        button.selected = self._config.view_mode == QueueViewMode.LIST
                    elif i == 1:  # Grid button
                        button.selected = self._config.view_mode == QueueViewMode.GRID
                    elif i == 2:  # Compact button
                        button.selected = self._config.view_mode == QueueViewMode.COMPACT

            # Update the page
            if self.page:
                self.page.update()

        except Exception as e:
            self._logger.error(f"Failed to update view mode buttons: {e}")

    def _start_auto_refresh(self):
        """Start auto-refresh timer."""
        try:
            if self._refresh_timer:
                self._refresh_timer.cancel()

            if self._config.auto_refresh and self._config.enable_real_time_updates:
                self._refresh_timer = asyncio.create_task(self._auto_refresh_loop())

        except Exception as e:
            self._logger.error(f"Failed to start auto-refresh: {e}")

    def _stop_auto_refresh(self):
        """Stop auto-refresh timer."""
        try:
            if self._refresh_timer:
                self._refresh_timer.cancel()
                self._refresh_timer = None

        except Exception as e:
            self._logger.error(f"Failed to stop auto-refresh: {e}")

    async def _auto_refresh_loop(self):
        """Auto-refresh loop."""
        try:
            while self._config.auto_refresh and self._config.enable_real_time_updates:
                await asyncio.sleep(self._config.refresh_interval_seconds)
                await self.refresh_queue()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Auto-refresh loop error: {e}")

    def _show_error_state(self, error_message: str):
        """Show error state in the UI."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            error_content = ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE,
                        size=64,
                        color=palette.error
                    ),
                    ft.Text(
                        "Error Loading Queue",
                        style=self.get_text_style("heading_small"),
                        color=palette.error
                    ),
                    ft.Text(
                        error_message,
                        style=self.get_text_style("body_medium"),
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.ElevatedButton(
                        text="Retry",
                        icon=ft.Icons.REFRESH,
                        on_click=lambda _: asyncio.create_task(self.refresh_queue())
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.lg
            )

            self.content = ft.Container(
                content=error_content,
                alignment=ft.alignment.center,
                expand=True
            )

            if self.page:
                self.page.update()

        except Exception as e:
            self._logger.error(f"Failed to show error state: {e}")

    # Public API Methods
    def add_queue_item(self, item: QueueItem):
        """Add a new item to the queue."""
        try:
            self._queue_items.append(item)
            self._apply_filters_and_sort()
            self._refresh_queue_display()
            self._update_status_bar()

            self._logger.info(f"Added queue item: {item.item_id}")

        except Exception as e:
            self._logger.error(f"Failed to add queue item: {e}")

    def update_queue_item(self, item_id: str, **updates):
        """Update a queue item."""
        try:
            for item in self._queue_items:
                if item.item_id == item_id:
                    for key, value in updates.items():
                        if hasattr(item, key):
                            setattr(item, key, value)
                    break

            self._apply_filters_and_sort()
            self._refresh_queue_display()
            self._update_status_bar()

            self._logger.debug(f"Updated queue item: {item_id}")

        except Exception as e:
            self._logger.error(f"Failed to update queue item {item_id}: {e}")

    def remove_queue_item(self, item_id: str):
        """Remove a queue item."""
        try:
            self._queue_items = [item for item in self._queue_items if item.item_id != item_id]

            if item_id in self._selected_items:
                self._selected_items.remove(item_id)

            self._apply_filters_and_sort()
            self._refresh_queue_display()
            self._update_status_bar()

            self._logger.info(f"Removed queue item: {item_id}")

        except Exception as e:
            self._logger.error(f"Failed to remove queue item {item_id}: {e}")

    def clear_queue(self):
        """Clear all queue items."""
        try:
            self._queue_items.clear()
            self._selected_items.clear()
            self._refresh_queue_display()
            self._update_status_bar()

            self._logger.info("Cleared queue")

        except Exception as e:
            self._logger.error(f"Failed to clear queue: {e}")

    def get_queue_statistics(self) -> Dict[str, int]:
        """Get queue statistics."""
        try:
            stats = {
                'total': len(self._queue_items),
                'pending': len([item for item in self._queue_items if item.status == QueueStatus.PENDING]),
                'queued': len([item for item in self._queue_items if item.status == QueueStatus.QUEUED]),
                'processing': len([item for item in self._queue_items if item.status == QueueStatus.PROCESSING]),
                'completed': len([item for item in self._queue_items if item.status == QueueStatus.COMPLETED]),
                'failed': len([item for item in self._queue_items if item.status == QueueStatus.FAILED]),
                'cancelled': len([item for item in self._queue_items if item.status == QueueStatus.CANCELLED]),
                'paused': len([item for item in self._queue_items if item.status == QueueStatus.PAUSED])
            }
            return stats

        except Exception as e:
            self._logger.error(f"Failed to get queue statistics: {e}")
            return {}

    def cleanup(self):
        """Cleanup resources."""
        try:
            self._stop_auto_refresh()
            self._logger.info("ProcessingQueueUI cleanup completed")

        except Exception as e:
            self._logger.error(f"Failed to cleanup ProcessingQueueUI: {e}")


# Accessibility and Responsive Enhancement Functions
def create_accessible_queue_item(item: QueueItem, theme_manager) -> ft.Container:
    """
    Create an accessible queue item with proper ARIA labels and keyboard navigation.

    Args:
        item: Queue item data
        theme_manager: Theme manager instance

    Returns:
        Accessible container with proper semantics
    """
    try:
        palette = theme_manager.get_palette()
        spacing = theme_manager.get_spacing()

        # Create semantic container with proper ARIA attributes
        container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        item.document_name,
                        style=theme_manager.get_text_style("body_large"),
                        color=palette.text_primary,
                        semantics_label=f"Document: {item.document_name}"
                    ),
                    ft.Text(
                        f"Status: {item.status.value.title()}",
                        style=theme_manager.get_text_style("body_medium"),
                        color=palette.text_secondary,
                        semantics_label=f"Processing status: {item.status.value}"
                    ),
                    ft.ProgressBar(
                        value=item.progress / 100.0 if item.progress > 0 else None,
                        color=palette.primary,
                        semantics_label=f"Progress: {item.progress:.1f} percent complete"
                    )
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.lg),
            border=ft.border.all(1, palette.outline),
            border_radius=8,
            # Accessibility enhancements
            tooltip=f"{item.document_name} - {item.status.value.title()} ({item.progress:.1f}%)",
            # Focus and keyboard navigation
            on_click=lambda _: None,  # Will be set by parent
            ink=True,
            # Ensure minimum touch target size (44x44 dp)
            height=max(44, spacing.xl * 3)
        )

        return container

    except Exception as e:
        # Return minimal accessible container on error
        return ft.Container(
            content=ft.Text("Error loading item"),
            padding=ft.padding.all(spacing.lg),
            height=44  # Minimum touch target
        )


def get_responsive_queue_layout(screen_width: float, items: List[QueueItem], theme_manager) -> ft.Control:
    """
    Create responsive queue layout based on screen width.

    Args:
        screen_width: Current screen width in pixels
        items: List of queue items to display
        theme_manager: Theme manager instance

    Returns:
        Responsive layout control
    """
    try:
        # Breakpoint-based layout decisions
        if screen_width < 576:  # Mobile
            return _create_mobile_queue_layout(items, theme_manager)
        elif screen_width < 992:  # Tablet
            return _create_tablet_queue_layout(items, theme_manager)
        else:  # Desktop
            return _create_desktop_queue_layout(items, theme_manager)

    except Exception:
        # Fallback to simple list
        return ft.ListView(
            controls=[
                create_accessible_queue_item(item, theme_manager)
                for item in items
            ],
            spacing=theme_manager.get_spacing().small
        )


def _create_mobile_queue_layout(items: List[QueueItem], theme_manager) -> ft.ListView:
    """Create mobile-optimized queue layout."""
    spacing = theme_manager.get_spacing()

    return ft.ListView(
        controls=[
            create_accessible_queue_item(item, theme_manager)
            for item in items
        ],
        spacing=spacing.sm,
        padding=ft.padding.all(spacing.sm)
    )


def _create_tablet_queue_layout(items: List[QueueItem], theme_manager) -> ft.GridView:
    """Create tablet-optimized queue layout."""
    spacing = theme_manager.get_spacing()

    return ft.GridView(
        controls=[
            create_accessible_queue_item(item, theme_manager)
            for item in items
        ],
        runs_count=2,  # 2 columns for tablet
        spacing=spacing.sm,
        run_spacing=spacing.sm,
        padding=ft.padding.all(spacing.lg)
    )


def _create_desktop_queue_layout(items: List[QueueItem], theme_manager) -> ft.GridView:
    """Create desktop-optimized queue layout."""
    spacing = theme_manager.get_spacing()

    return ft.GridView(
        controls=[
            create_accessible_queue_item(item, theme_manager)
            for item in items
        ],
        runs_count=3,  # 3 columns for desktop
        spacing=spacing.lg,
        run_spacing=spacing.lg,
        padding=ft.padding.all(spacing.xl)
    )


# Utility functions for queue management
def format_file_size(size_bytes: int) -> str:
    """Format file size for display."""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def get_queue_item_priority_text(priority: int) -> str:
    """Get human-readable priority text."""
    priority_map = {
        1: "Urgent",
        2: "High",
        3: "Normal",
        4: "Low",
        5: "Background"
    }
    return priority_map.get(priority, "Normal")


def validate_queue_config(config: QueueConfig) -> QueueConfig:
    """Validate and sanitize queue configuration."""
    # Ensure refresh interval is reasonable
    if config.refresh_interval_seconds < 0.5:
        config.refresh_interval_seconds = 0.5
    elif config.refresh_interval_seconds > 60:
        config.refresh_interval_seconds = 60

    # Ensure max items is reasonable
    if config.max_items_display < 1:
        config.max_items_display = 100
    elif config.max_items_display > 1000:
        config.max_items_display = 1000

    return config
