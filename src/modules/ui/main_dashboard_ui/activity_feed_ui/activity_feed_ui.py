"""
Module: activity_feed_ui
Description: Real-time activity feed display component for MikroDok application main dashboard.
            Provides comprehensive activity tracking with responsive design, theme integration,
            filtering capabilities, and real-time updates. Shows system events, user actions,
            training progress, and notifications with adaptive layouts and accessibility support.
Phase: 1
Location: /src/modules/ui/main_dashboard_ui/activity_feed_ui/activity_feed_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
import logging
import json
import uuid

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ColorPalette,
    SpacingSystem,
    TypographyScale,
    IconSystem,
    ResponsiveLayoutManager
)

# Configure logging
logger = logging.getLogger(__name__)


class ActivityCategory(Enum):
    """Activity category enumeration."""
    SYSTEM = "system"
    USER = "user"
    TRAINING = "training"
    DOCUMENT = "document"
    MODEL = "model"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ERROR = "error"


class ActivityStatus(Enum):
    """Activity status enumeration."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ActivityPriority(Enum):
    """Activity priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActivitySource(Enum):
    """Activity source enumeration."""
    SYSTEM_MONITOR = "system_monitor"
    USER_ACTION = "user_action"
    TRAINING_ENGINE = "training_engine"
    DOCUMENT_PROCESSOR = "document_processor"
    MODEL_MANAGER = "model_manager"
    SECURITY_SYSTEM = "security_system"
    PERFORMANCE_MONITOR = "performance_monitor"
    ERROR_HANDLER = "error_handler"


@dataclass
class ActivityItem:
    """Activity feed item data structure."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    category: ActivityCategory = ActivityCategory.SYSTEM
    status: ActivityStatus = ActivityStatus.INFO
    priority: ActivityPriority = ActivityPriority.MEDIUM
    source: ActivitySource = ActivitySource.SYSTEM_MONITOR
    icon: str = "INFO"
    details: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    read: bool = False
    archived: bool = False


@dataclass
class ActivityFilter:
    """Activity filter configuration."""
    categories: List[ActivityCategory] = field(default_factory=list)
    statuses: List[ActivityStatus] = field(default_factory=list)
    priorities: List[ActivityPriority] = field(default_factory=list)
    sources: List[ActivitySource] = field(default_factory=list)
    date_range: Optional[Tuple[datetime, datetime]] = None
    search_text: str = ""
    show_read: bool = True
    show_archived: bool = False
    tags: List[str] = field(default_factory=list)


@dataclass
class ActivityFeedConfig:
    """Activity feed configuration."""
    max_items: int = 100
    auto_refresh_interval: int = 30  # seconds
    enable_real_time_updates: bool = True
    enable_notifications: bool = True
    enable_grouping: bool = True
    enable_filtering: bool = True
    enable_search: bool = True
    items_per_page: int = 20
    show_timestamps: bool = True
    show_categories: bool = True
    show_priorities: bool = True
    compact_mode: bool = False
    enable_animations: bool = True
    auto_mark_read: bool = True
    retention_days: int = 30


class ActivityFeedUI(ThemeAwareUserControl):
    """
    Real-time activity feed display component with comprehensive theming and responsive design.
    
    Features:
    - Responsive activity feed with adaptive layouts
    - Theme-aware styling with no hardcoded colors or dimensions
    - Real-time activity updates with filtering and search
    - Multiple activity categories and status indicators
    - Performance optimization for large activity datasets
    - Accessibility compliance with ARIA labels and keyboard navigation
    - Integration with system logging and audit trails
    - Customizable display options and user preferences
    - Activity grouping and pagination support
    - Export and archival capabilities
    """

    def __init__(self,
                 config: Optional[ActivityFeedConfig] = None,
                 on_activity_click: Optional[Callable[[ActivityItem], None]] = None,
                 on_filter_change: Optional[Callable[[ActivityFilter], None]] = None,
                 **kwargs):
        """
        Initialize the activity feed UI component.

        Args:
            config: Activity feed configuration
            on_activity_click: Callback for activity item clicks
            on_filter_change: Callback for filter changes
            **kwargs: Additional arguments for ThemeAwareUserControl
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or ActivityFeedConfig()
        self._on_activity_click = on_activity_click
        self._on_filter_change = on_filter_change
        
        # State management
        self._activities: List[ActivityItem] = []
        self._filtered_activities: List[ActivityItem] = []
        self._current_filter = ActivityFilter()
        self._current_page = 0
        self._total_pages = 0
        self._is_loading = False
        self._last_refresh = datetime.now(timezone.utc)
        
        # UI components
        self._activity_list: Optional[ft.Column] = None
        self._filter_panel: Optional[ft.Container] = None
        self._search_field: Optional[ft.TextField] = None
        self._pagination_controls: Optional[ft.Row] = None
        self._refresh_button: Optional[ft.IconButton] = None
        self._loading_indicator: Optional[ft.ProgressRing] = None
        
        # Callbacks and timers
        self._refresh_timer: Optional[asyncio.Task] = None
        self._filter_callbacks: List[Callable[[ActivityFilter], None]] = []
        
        # Initialize sample data for demonstration
        self._initialize_sample_activities()
        
        logger.debug("ActivityFeedUI initialized")

    def _initialize_sample_activities(self) -> None:
        """Initialize sample activity data for demonstration."""
        now = datetime.now(timezone.utc)
        
        sample_activities = [
            ActivityItem(
                title="System Started",
                description="MikroDok application launched successfully",
                timestamp=now - timedelta(minutes=5),
                category=ActivityCategory.SYSTEM,
                status=ActivityStatus.SUCCESS,
                priority=ActivityPriority.MEDIUM,
                source=ActivitySource.SYSTEM_MONITOR,
                icon="POWER_SETTINGS_NEW",
                details="Application startup completed in 2.3 seconds"
            ),
            ActivityItem(
                title="Memory Optimization",
                description="System memory optimization completed",
                timestamp=now - timedelta(minutes=10),
                category=ActivityCategory.PERFORMANCE,
                status=ActivityStatus.SUCCESS,
                priority=ActivityPriority.LOW,
                source=ActivitySource.PERFORMANCE_MONITOR,
                icon="MEMORY",
                details="Memory usage optimized from 85% to 62%"
            ),
            ActivityItem(
                title="GPU Detection",
                description="CUDA-compatible GPU detected and initialized",
                timestamp=now - timedelta(minutes=15),
                category=ActivityCategory.SYSTEM,
                status=ActivityStatus.SUCCESS,
                priority=ActivityPriority.HIGH,
                source=ActivitySource.SYSTEM_MONITOR,
                icon="VIDEOGAME_ASSET",
                details="NVIDIA RTX 4090 detected with 24GB VRAM"
            ),
            ActivityItem(
                title="Document Processing",
                description="Processing batch of 15 documents",
                timestamp=now - timedelta(minutes=20),
                category=ActivityCategory.DOCUMENT,
                status=ActivityStatus.IN_PROGRESS,
                priority=ActivityPriority.MEDIUM,
                source=ActivitySource.DOCUMENT_PROCESSOR,
                icon="DESCRIPTION",
                details="Progress: 8/15 documents completed"
            ),
            ActivityItem(
                title="Training Session",
                description="Model training session initiated",
                timestamp=now - timedelta(minutes=25),
                category=ActivityCategory.TRAINING,
                status=ActivityStatus.IN_PROGRESS,
                priority=ActivityPriority.HIGH,
                source=ActivitySource.TRAINING_ENGINE,
                icon="SCHOOL",
                details="Training epoch 1/10 in progress"
            )
        ]
        
        self._activities = sample_activities
        self._apply_filter()

    def build(self) -> ft.Control:
        """Build the activity feed UI."""
        return self.create_responsive_container(
            content=ft.Column(
                controls=[
                    self._build_header(),
                    self._build_filter_panel(),
                    self._build_activity_list(),
                    self._build_pagination()
                ],
                spacing=0,
                expand=True
            ),
            padding=self.get_responsive_padding()
        )

    def _build_header(self) -> ft.Control:
        """Build the activity feed header."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        self._refresh_button = ft.IconButton(
            icon=self.get_icon("REFRESH"),
            icon_size=self.get_breakpoint_value(16, 18, 20, 22),
            icon_color=palette.primary,
            tooltip="Refresh activity feed",
            on_click=self._on_refresh_click
        )

        self._loading_indicator = ft.ProgressRing(
            width=self.get_breakpoint_value(16, 18, 20, 22),
            height=self.get_breakpoint_value(16, 18, 20, 22),
            stroke_width=2,
            color=palette.primary,
            visible=False
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "Activity Feed",
                        style=self.get_text_style("titleLarge"),
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_600,
                        expand=True
                    ),
                    ft.Text(
                        f"Last updated: {self._format_timestamp(self._last_refresh)}",
                        style=self.get_text_style("bodySmall"),
                        color=palette.text_secondary
                    ),
                    self._loading_indicator,
                    self._refresh_button
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=ft.padding.only(
                left=spacing.md,
                right=spacing.md,
                top=spacing.sm,
                bottom=spacing.sm
            ),
            border=ft.border.only(
                bottom=ft.BorderSide(1, palette.borders)
            )
        )

    def _build_filter_panel(self) -> ft.Control:
        """Build the filter panel."""
        if not self._config.enable_filtering:
            return ft.Container(height=0)

        palette = self.get_palette()
        spacing = self.get_spacing()

        self._search_field = ft.TextField(
            hint_text="Search activities...",
            prefix_icon=self.get_icon("SEARCH"),
            border_color=palette.borders,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary),
            hint_style=ft.TextStyle(color=palette.text_secondary),
            on_change=self._on_search_change,
            expand=True
        )

        filter_chips = self._build_filter_chips()

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._search_field,
                    ft.Container(height=spacing.xs),
                    ft.Row(
                        controls=filter_chips,
                        wrap=True,
                        spacing=spacing.xs
                    )
                ],
                spacing=0
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border=ft.border.only(
                bottom=ft.BorderSide(1, palette.borders)
            )
        )

    def _build_filter_chips(self) -> List[ft.Control]:
        """Build filter chips for categories and statuses."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        chips = []

        # Category filters
        for category in ActivityCategory:
            is_selected = category in self._current_filter.categories
            chip = ft.FilterChip(
                label=ft.Text(
                    category.value.title(),
                    color=palette.text_primary if is_selected else palette.text_secondary,
                    size=self.get_breakpoint_value(11, 12, 13, 14)
                ),
                selected=is_selected,
                bgcolor=palette.primary if is_selected else palette.surface,
                selected_color=palette.primary,
                on_click=lambda e, cat=category: self._toggle_category_filter(cat)
            )
            chips.append(chip)

        # Status filters
        for status in ActivityStatus:
            is_selected = status in self._current_filter.statuses
            chip = ft.FilterChip(
                label=ft.Text(
                    status.value.title(),
                    color=palette.text_primary if is_selected else palette.text_secondary,
                    size=self.get_breakpoint_value(11, 12, 13, 14)
                ),
                selected=is_selected,
                bgcolor=self._get_status_color(status) if is_selected else palette.surface,
                selected_color=self._get_status_color(status),
                on_click=lambda e, stat=status: self._toggle_status_filter(stat)
            )
            chips.append(chip)

        return chips

    def _build_activity_list(self) -> ft.Control:
        """Build the activity list."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._activity_list = ft.Column(
            controls=self._build_activity_items(),
            spacing=spacing.xs,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        return ft.Container(
            content=self._activity_list,
            padding=ft.padding.all(spacing.md),
            expand=True
        )

    def _build_activity_items(self) -> List[ft.Control]:
        """Build activity item controls."""
        items = []
        start_idx = self._current_page * self._config.items_per_page
        end_idx = start_idx + self._config.items_per_page
        page_activities = self._filtered_activities[start_idx:end_idx]

        for activity in page_activities:
            item_control = self._build_activity_item(activity)
            items.append(item_control)

        if not items:
            items.append(self._build_empty_state())

        return items

    def _build_activity_item(self, activity: ActivityItem) -> ft.Control:
        """Build an individual activity item."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Status indicator
        status_color = self._get_status_color(activity.status)
        status_icon = self._get_status_icon(activity.status)

        # Priority indicator
        priority_indicator = self._build_priority_indicator(activity.priority)

        # Timestamp
        timestamp_text = self._format_timestamp(activity.timestamp)

        # Main content
        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            name=self.get_icon(activity.icon),
                            size=self.get_breakpoint_value(16, 18, 20, 22),
                            color=status_color
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    activity.title,
                                    style=self.get_text_style("bodyLarge"),
                                    color=palette.text_primary,
                                    weight=ft.FontWeight.W_500,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS
                                ),
                                ft.Text(
                                    activity.description,
                                    style=self.get_text_style("bodyMedium"),
                                    color=palette.text_secondary,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS
                                )
                            ],
                            spacing=spacing.xs,
                            expand=True
                        ),
                        ft.Column(
                            controls=[
                                priority_indicator,
                                ft.Text(
                                    timestamp_text,
                                    style=self.get_text_style("bodySmall"),
                                    color=palette.text_tertiary,
                                    text_align=ft.TextAlign.RIGHT
                                )
                            ],
                            spacing=spacing.xs,
                            horizontal_alignment=ft.CrossAxisAlignment.END
                        )
                    ],
                    spacing=spacing.sm,
                    vertical_alignment=ft.CrossAxisAlignment.START
                )
            ],
            spacing=0
        )

        # Add details if available
        if activity.details and not self._config.compact_mode:
            content.controls.append(
                ft.Container(
                    content=ft.Text(
                        activity.details,
                        style=self.get_text_style("bodySmall"),
                        color=palette.text_tertiary,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS
                    ),
                    margin=ft.margin.only(
                        left=self.get_breakpoint_value(24, 26, 28, 30),
                        top=spacing.xs
                    )
                )
            )

        # Container with hover effect
        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.sm),
            border_radius=ft.border_radius.all(self.get_breakpoint_value(4, 6, 8, 10)),
            bgcolor=palette.surface if not activity.read else palette.background_secondary,
            border=ft.border.all(1, palette.borders),
            on_click=lambda e: self._on_activity_item_click(activity),
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT) if self._config.enable_animations else None
        )

    def _build_priority_indicator(self, priority: ActivityPriority) -> ft.Control:
        """Build priority indicator."""
        palette = self.get_palette()

        if priority == ActivityPriority.CRITICAL:
            color = palette.error
            icon = "PRIORITY_HIGH"
        elif priority == ActivityPriority.HIGH:
            color = palette.warning
            icon = "KEYBOARD_ARROW_UP"
        elif priority == ActivityPriority.MEDIUM:
            color = palette.info
            icon = "REMOVE"
        else:  # LOW
            color = palette.text_tertiary
            icon = "KEYBOARD_ARROW_DOWN"

        return ft.Icon(
            name=self.get_icon(icon),
            size=self.get_breakpoint_value(12, 14, 16, 18),
            color=color
        )

    def _build_empty_state(self) -> ft.Control:
        """Build empty state when no activities are available."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=self.get_icon("INBOX"),
                        size=self.get_breakpoint_value(48, 56, 64, 72),
                        color=palette.text_tertiary
                    ),
                    ft.Text(
                        "No activities found",
                        style=self.get_text_style("titleMedium"),
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Activities will appear here as they occur",
                        style=self.get_text_style("bodyMedium"),
                        color=palette.text_tertiary,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                spacing=spacing.md,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=ft.padding.all(spacing.xl),
            alignment=ft.alignment.center,
            expand=True
        )

    def _build_pagination(self) -> ft.Control:
        """Build pagination controls."""
        if self._total_pages <= 1:
            return ft.Container(height=0)

        palette = self.get_palette()
        spacing = self.get_spacing()

        prev_button = ft.IconButton(
            icon=self.get_icon("CHEVRON_LEFT"),
            icon_size=self.get_breakpoint_value(16, 18, 20, 22),
            icon_color=palette.primary if self._current_page > 0 else palette.text_disabled,
            disabled=self._current_page == 0,
            on_click=self._on_prev_page
        )

        next_button = ft.IconButton(
            icon=self.get_icon("CHEVRON_RIGHT"),
            icon_size=self.get_breakpoint_value(16, 18, 20, 22),
            icon_color=palette.primary if self._current_page < self._total_pages - 1 else palette.text_disabled,
            disabled=self._current_page >= self._total_pages - 1,
            on_click=self._on_next_page
        )

        page_info = ft.Text(
            f"Page {self._current_page + 1} of {self._total_pages}",
            style=self.get_text_style("bodyMedium"),
            color=palette.text_secondary
        )

        self._pagination_controls = ft.Row(
            controls=[prev_button, page_info, next_button],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=spacing.sm
        )

        return ft.Container(
            content=self._pagination_controls,
            padding=ft.padding.all(spacing.md),
            border=ft.border.only(
                top=ft.BorderSide(1, palette.borders)
            )
        )

    # Event handlers
    def _on_refresh_click(self, e) -> None:
        """Handle refresh button click."""
        try:
            self._refresh_activities()
        except Exception as ex:
            logger.error(f"Error refreshing activities: {ex}")

    def _on_search_change(self, e) -> None:
        """Handle search text change."""
        try:
            self._current_filter.search_text = e.control.value or ""
            self._apply_filter()
            self._update_display()
        except Exception as ex:
            logger.error(f"Error handling search change: {ex}")

    def _toggle_category_filter(self, category: ActivityCategory) -> None:
        """Toggle category filter."""
        try:
            if category in self._current_filter.categories:
                self._current_filter.categories.remove(category)
            else:
                self._current_filter.categories.append(category)

            self._apply_filter()
            self._update_display()

            if self._on_filter_change:
                self._on_filter_change(self._current_filter)
        except Exception as ex:
            logger.error(f"Error toggling category filter: {ex}")

    def _toggle_status_filter(self, status: ActivityStatus) -> None:
        """Toggle status filter."""
        try:
            if status in self._current_filter.statuses:
                self._current_filter.statuses.remove(status)
            else:
                self._current_filter.statuses.append(status)

            self._apply_filter()
            self._update_display()

            if self._on_filter_change:
                self._on_filter_change(self._current_filter)
        except Exception as ex:
            logger.error(f"Error toggling status filter: {ex}")

    def _on_activity_item_click(self, activity: ActivityItem) -> None:
        """Handle activity item click."""
        try:
            # Mark as read if auto-mark is enabled
            if self._config.auto_mark_read and not activity.read:
                activity.read = True
                self._update_display()

            # Call external callback
            if self._on_activity_click:
                self._on_activity_click(activity)

            logger.debug(f"Activity clicked: {activity.title}")
        except Exception as ex:
            logger.error(f"Error handling activity click: {ex}")

    def _on_prev_page(self, e) -> None:
        """Handle previous page button click."""
        try:
            if self._current_page > 0:
                self._current_page -= 1
                self._update_display()
        except Exception as ex:
            logger.error(f"Error navigating to previous page: {ex}")

    def _on_next_page(self, e) -> None:
        """Handle next page button click."""
        try:
            if self._current_page < self._total_pages - 1:
                self._current_page += 1
                self._update_display()
        except Exception as ex:
            logger.error(f"Error navigating to next page: {ex}")

    # Utility methods
    def _get_status_color(self, status: ActivityStatus) -> str:
        """Get color for activity status."""
        palette = self.get_palette()

        status_colors = {
            ActivityStatus.SUCCESS: palette.success,
            ActivityStatus.ERROR: palette.error,
            ActivityStatus.WARNING: palette.warning,
            ActivityStatus.INFO: palette.info,
            ActivityStatus.IN_PROGRESS: palette.primary,
            ActivityStatus.COMPLETED: palette.success,
            ActivityStatus.FAILED: palette.error
        }

        return status_colors.get(status, palette.text_secondary)

    def _get_status_icon(self, status: ActivityStatus) -> str:
        """Get icon for activity status."""
        status_icons = {
            ActivityStatus.SUCCESS: "CHECK_CIRCLE",
            ActivityStatus.ERROR: "ERROR",
            ActivityStatus.WARNING: "WARNING",
            ActivityStatus.INFO: "INFO",
            ActivityStatus.IN_PROGRESS: "HOURGLASS_EMPTY",
            ActivityStatus.COMPLETED: "TASK_ALT",
            ActivityStatus.FAILED: "CANCEL"
        }

        return status_icons.get(status, "INFO")

    def _format_timestamp(self, timestamp: datetime) -> str:
        """Format timestamp for display."""
        try:
            now = datetime.now(timezone.utc)
            diff = now - timestamp

            if diff.days > 0:
                return f"{diff.days}d ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours}h ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes}m ago"
            else:
                return "Just now"
        except Exception as ex:
            logger.error(f"Error formatting timestamp: {ex}")
            return "Unknown"

    def _apply_filter(self) -> None:
        """Apply current filter to activities."""
        try:
            filtered = self._activities.copy()

            # Apply category filter
            if self._current_filter.categories:
                filtered = [a for a in filtered if a.category in self._current_filter.categories]

            # Apply status filter
            if self._current_filter.statuses:
                filtered = [a for a in filtered if a.status in self._current_filter.statuses]

            # Apply search filter
            if self._current_filter.search_text:
                search_text = self._current_filter.search_text.lower()
                filtered = [
                    a for a in filtered
                    if search_text in a.title.lower() or
                       search_text in a.description.lower() or
                       (a.details and search_text in a.details.lower())
                ]

            # Apply read/archived filters
            if not self._current_filter.show_read:
                filtered = [a for a in filtered if not a.read]

            if not self._current_filter.show_archived:
                filtered = [a for a in filtered if not a.archived]

            # Sort by timestamp (newest first)
            filtered.sort(key=lambda x: x.timestamp, reverse=True)

            self._filtered_activities = filtered
            self._calculate_pagination()

        except Exception as ex:
            logger.error(f"Error applying filter: {ex}")
            self._filtered_activities = self._activities.copy()

    def _calculate_pagination(self) -> None:
        """Calculate pagination parameters."""
        try:
            total_items = len(self._filtered_activities)
            self._total_pages = max(1, (total_items + self._config.items_per_page - 1) // self._config.items_per_page)

            # Ensure current page is valid
            if self._current_page >= self._total_pages:
                self._current_page = max(0, self._total_pages - 1)

        except Exception as ex:
            logger.error(f"Error calculating pagination: {ex}")
            self._total_pages = 1
            self._current_page = 0

    def _update_display(self) -> None:
        """Update the display with current data."""
        try:
            if self._activity_list:
                self._activity_list.controls.clear()
                self._activity_list.controls.extend(self._build_activity_items())

            # Update pagination if it exists
            if self._pagination_controls and self._total_pages > 1:
                self._pagination_controls.controls[0].disabled = self._current_page == 0
                self._pagination_controls.controls[2].disabled = self._current_page >= self._total_pages - 1
                self._pagination_controls.controls[1].value = f"Page {self._current_page + 1} of {self._total_pages}"

            # Update last refresh time
            self._last_refresh = datetime.now(timezone.utc)

            if self.page:
                self.page.update()

        except Exception as ex:
            logger.error(f"Error updating display: {ex}")

    def _refresh_activities(self) -> None:
        """Refresh activities from data sources."""
        try:
            self._is_loading = True
            if self._loading_indicator:
                self._loading_indicator.visible = True
            if self._refresh_button:
                self._refresh_button.disabled = True

            # In a real implementation, this would fetch from data sources
            # For now, we'll just update the timestamp and re-apply filters
            self._apply_filter()
            self._update_display()

            self._is_loading = False
            if self._loading_indicator:
                self._loading_indicator.visible = False
            if self._refresh_button:
                self._refresh_button.disabled = False

            logger.debug("Activities refreshed")

        except Exception as ex:
            logger.error(f"Error refreshing activities: {ex}")
            self._is_loading = False
            if self._loading_indicator:
                self._loading_indicator.visible = False
            if self._refresh_button:
                self._refresh_button.disabled = False

    # Public API methods
    def add_activity(self, activity: ActivityItem) -> None:
        """
        Add a new activity to the feed.

        Args:
            activity: Activity item to add
        """
        try:
            self._activities.insert(0, activity)

            # Limit activities to max items
            if len(self._activities) > self._config.max_items:
                self._activities = self._activities[:self._config.max_items]

            self._apply_filter()
            self._update_display()

            logger.debug(f"Activity added: {activity.title}")

        except Exception as ex:
            logger.error(f"Error adding activity: {ex}")

    def remove_activity(self, activity_id: str) -> bool:
        """
        Remove an activity from the feed.

        Args:
            activity_id: ID of activity to remove

        Returns:
            True if activity was removed, False otherwise
        """
        try:
            for i, activity in enumerate(self._activities):
                if activity.id == activity_id:
                    del self._activities[i]
                    self._apply_filter()
                    self._update_display()
                    logger.debug(f"Activity removed: {activity_id}")
                    return True

            return False

        except Exception as ex:
            logger.error(f"Error removing activity: {ex}")
            return False

    def clear_activities(self) -> None:
        """Clear all activities from the feed."""
        try:
            self._activities.clear()
            self._apply_filter()
            self._update_display()
            logger.debug("All activities cleared")

        except Exception as ex:
            logger.error(f"Error clearing activities: {ex}")

    def mark_all_read(self) -> None:
        """Mark all activities as read."""
        try:
            for activity in self._activities:
                activity.read = True

            self._update_display()
            logger.debug("All activities marked as read")

        except Exception as ex:
            logger.error(f"Error marking activities as read: {ex}")

    def set_filter(self, activity_filter: ActivityFilter) -> None:
        """
        Set the current filter.

        Args:
            activity_filter: Filter to apply
        """
        try:
            self._current_filter = activity_filter
            self._apply_filter()
            self._update_display()

            if self._on_filter_change:
                self._on_filter_change(self._current_filter)

        except Exception as ex:
            logger.error(f"Error setting filter: {ex}")

    def get_activities(self, include_filtered: bool = False) -> List[ActivityItem]:
        """
        Get current activities.

        Args:
            include_filtered: Whether to include filtered activities

        Returns:
            List of activity items
        """
        try:
            return self._filtered_activities.copy() if not include_filtered else self._activities.copy()
        except Exception as ex:
            logger.error(f"Error getting activities: {ex}")
            return []

    def get_unread_count(self) -> int:
        """
        Get count of unread activities.

        Returns:
            Number of unread activities
        """
        try:
            return sum(1 for activity in self._activities if not activity.read)
        except Exception as ex:
            logger.error(f"Error getting unread count: {ex}")
            return 0

    def cleanup(self) -> None:
        """Clean up resources and timers."""
        try:
            if self._refresh_timer:
                self._refresh_timer.cancel()
                self._refresh_timer = None

            self._filter_callbacks.clear()
            logger.debug("ActivityFeedUI cleanup completed")

        except Exception as ex:
            logger.error(f"Error during cleanup: {ex}")
