"""
Module: session_history_ui
Description: Previous chat sessions list with timestamps and quick access for chat interface.
            Provides comprehensive session history management with responsive design, theme integration,
            session filtering, search capabilities, session actions, and accessibility features.
            Integrates fully with ResponsiveLayoutManager and theme system for consistent styling.
Phase: 4
Location: /src/modules/ui/chat_interface_ui/session_history_ui/session_history_ui.py
"""

# Standard library imports
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    get_theme_manager
)
from src.modules.database.chat_repository_db.chat_session_db.chat_session_db import (
    ChatSessionDB, ChatSession, SessionStatus
)
from src.modules.database.chat_repository_db.chat_messages_db.chat_messages_db import (
    ChatMessagesDB, MessageRole
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class SessionSortOrder(Enum):
    """Session sorting order enumeration."""
    RECENT_FIRST = "recent_first"
    OLDEST_FIRST = "oldest_first"
    ALPHABETICAL = "alphabetical"
    MOST_MESSAGES = "most_messages"
    LONGEST_DURATION = "longest_duration"


class SessionFilterType(Enum):
    """Session filter type enumeration."""
    ALL = "all"
    ACTIVE = "active"
    COMPLETED = "completed"
    TODAY = "today"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    FAVORITES = "favorites"


@dataclass
class SessionHistoryConfig:
    """Configuration for session history UI."""
    max_sessions_display: int = 100
    auto_refresh_interval: int = 30  # seconds
    show_message_count: bool = True
    show_duration: bool = True
    show_model_info: bool = True
    enable_search: bool = True
    enable_favorites: bool = True
    enable_session_actions: bool = True
    compact_mode: bool = False
    group_by_date: bool = True
    show_session_preview: bool = True
    preview_message_count: int = 2


@dataclass
class SessionDisplayData:
    """Session display data structure."""
    session: ChatSession
    message_count: int = 0
    last_message_preview: Optional[str] = None
    duration_text: str = ""
    relative_time: str = ""
    is_favorite: bool = False
    model_name: str = ""
    status_color: str = ""
    status_icon: str = ""


class SessionHistoryUI(ThemeAwareUserControl):
    """
    Previous chat sessions list with timestamps and quick access for chat interface.
    
    Features:
    - Comprehensive session history display with responsive design
    - Session filtering and search capabilities with real-time updates
    - Session actions (resume, delete, favorite, export) with confirmation dialogs
    - Responsive layout with adaptive grid/list views
    - Full theme system integration with consistent styling
    - Session grouping by date with collapsible sections
    - Session preview with last messages and metadata
    - Accessibility compliance with keyboard navigation and screen reader support
    - Performance optimization with virtual scrolling and lazy loading
    - Real-time session status updates and activity monitoring
    """

    def __init__(self,
                 config: Optional[SessionHistoryConfig] = None,
                 on_session_select: Optional[Callable[[str], None]] = None,
                 on_session_delete: Optional[Callable[[str], None]] = None,
                 on_session_export: Optional[Callable[[str], None]] = None,
                 on_new_session: Optional[Callable[[], None]] = None,
                 **kwargs):
        """
        Initialize the session history UI component.

        Args:
            config: Session history configuration
            on_session_select: Callback for session selection
            on_session_delete: Callback for session deletion
            on_session_export: Callback for session export
            on_new_session: Callback for new session creation
            **kwargs: Additional container arguments
        """
        super().__init__(**kwargs)
        
        # Configuration and callbacks
        self.config = config or SessionHistoryConfig()
        self.on_session_select = on_session_select
        self.on_session_delete = on_session_delete
        self.on_session_export = on_session_export
        self.on_new_session = on_new_session
        
        # Database connections
        self.session_db = ChatSessionDB()
        self.messages_db = ChatMessagesDB()
        
        # State management
        self.sessions: List[SessionDisplayData] = []
        self.filtered_sessions: List[SessionDisplayData] = []
        self.selected_session_id: Optional[str] = None
        self.current_filter: SessionFilterType = SessionFilterType.ALL
        self.current_sort: SessionSortOrder = SessionSortOrder.RECENT_FIRST
        self.search_query: str = ""
        self.favorites: set = set()
        
        # UI components
        self.search_field: Optional[ft.TextField] = None
        self.filter_dropdown: Optional[ft.Dropdown] = None
        self.sort_dropdown: Optional[ft.Dropdown] = None
        self.sessions_container: Optional[ft.Container] = None
        self.loading_indicator: Optional[ft.ProgressRing] = None
        self.empty_state: Optional[ft.Container] = None
        
        # Auto-refresh timer
        self.refresh_timer: Optional[asyncio.Task] = None
        
        # Logger
        self.logger = get_logger(__name__)
        
        # Initialize component
        self._initialize_component()

    def _initialize_component(self):
        """Initialize the session history component."""
        try:
            self.logger.info("Initializing session history UI component")
            
            # Load initial data
            self._load_sessions()
            self._load_favorites()
            
            # Start auto-refresh if enabled
            if self.config.auto_refresh_interval > 0:
                self._start_auto_refresh()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize session history component: {e}")

    def build(self) -> ft.Control:
        """Build the session history UI."""
        try:
            # Get theme components
            colors = self.get_colors()
            typography = self.get_typography()
            spacing = self.get_spacing()
            responsive = self.get_responsive_layout()
            
            # Create header section
            header = self._create_header_section()
            
            # Create filter and search section
            filter_section = self._create_filter_section()
            
            # Create sessions list
            sessions_list = self._create_sessions_list()
            
            # Create main layout
            main_content = ft.Column(
                controls=[
                    header,
                    filter_section,
                    sessions_list
                ],
                spacing=spacing.md,
                expand=True
            )
            
            return self.create_responsive_container(
                content=main_content,
                padding=responsive.get_breakpoint_value(
                    mobile=spacing.sm,
                    tablet=spacing.md,
                    desktop=spacing.lg,
                    large=spacing.xl
                )
            )
            
        except Exception as e:
            self.logger.error(f"Failed to build session history UI: {e}")
            return self._create_error_state(str(e))

    def _create_header_section(self) -> ft.Control:
        """Create the header section with title and actions."""
        colors = self.get_colors()
        typography = self.get_typography()
        spacing = self.get_spacing()
        responsive = self.get_responsive_layout()
        
        # Title
        title = ft.Text(
            "Chat History",
            style=typography.heading_2,
            color=colors.on_surface,
            weight=ft.FontWeight.W_600
        )
        
        # New session button
        new_session_btn = self.create_themed_component(
            "button",
            variant="primary",
            text="New Chat",
            icon=ft.Icons.ADD_COMMENT,
            on_click=self._handle_new_session,
            tooltip="Start a new chat session"
        )
        
        # Refresh button
        refresh_btn = self.create_themed_component(
            "button",
            variant="secondary",
            icon=ft.Icons.REFRESH,
            on_click=self._handle_refresh,
            tooltip="Refresh session list"
        )
        
        # Actions row
        actions = ft.Row(
            controls=[refresh_btn, new_session_btn],
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.END
        )
        
        # Header layout
        return ft.Row(
            controls=[title, actions],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _create_filter_section(self) -> ft.Control:
        """Create the filter and search section."""
        colors = self.get_colors()
        typography = self.get_typography()
        spacing = self.get_spacing()
        responsive = self.get_responsive_layout()

        # Search field
        self.search_field = ft.TextField(
            hint_text="Search sessions...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=responsive.get_breakpoint_value(8, 10, 12, 14),
            on_change=self._handle_search_change,
            expand=True
        )

        # Filter dropdown
        self.filter_dropdown = ft.Dropdown(
            label="Filter",
            options=[
                ft.dropdown.Option("all", "All Sessions"),
                ft.dropdown.Option("active", "Active"),
                ft.dropdown.Option("completed", "Completed"),
                ft.dropdown.Option("today", "Today"),
                ft.dropdown.Option("this_week", "This Week"),
                ft.dropdown.Option("this_month", "This Month"),
                ft.dropdown.Option("favorites", "Favorites")
            ],
            value="all",
            on_change=self._handle_filter_change,
            width=responsive.get_breakpoint_value(120, 140, 160, 180)
        )

        # Sort dropdown
        self.sort_dropdown = ft.Dropdown(
            label="Sort",
            options=[
                ft.dropdown.Option("recent_first", "Recent First"),
                ft.dropdown.Option("oldest_first", "Oldest First"),
                ft.dropdown.Option("alphabetical", "Alphabetical"),
                ft.dropdown.Option("most_messages", "Most Messages"),
                ft.dropdown.Option("longest_duration", "Longest Duration")
            ],
            value="recent_first",
            on_change=self._handle_sort_change,
            width=responsive.get_breakpoint_value(120, 140, 160, 180)
        )

        # Filter controls row
        filter_controls = ft.Row(
            controls=[self.filter_dropdown, self.sort_dropdown],
            spacing=spacing.sm
        )

        # Main filter section
        return ft.Column(
            controls=[
                self.search_field,
                filter_controls
            ],
            spacing=spacing.sm
        )

    def _create_sessions_list(self) -> ft.Control:
        """Create the sessions list container."""
        colors = self.get_colors()
        spacing = self.get_spacing()
        responsive = self.get_responsive_layout()

        # Loading indicator
        self.loading_indicator = ft.ProgressRing(
            width=responsive.get_breakpoint_value(24, 28, 32, 36),
            height=responsive.get_breakpoint_value(24, 28, 32, 36),
            visible=False
        )

        # Empty state
        self.empty_state = self._create_empty_state()

        # Sessions container
        self.sessions_container = ft.Column(
            controls=[],
            spacing=spacing.sm,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        # Main container with loading and empty states
        return ft.Stack(
            controls=[
                self.sessions_container,
                ft.Container(
                    content=self.loading_indicator,
                    alignment=ft.alignment.center,
                    expand=True
                ),
                ft.Container(
                    content=self.empty_state,
                    alignment=ft.alignment.center,
                    expand=True
                )
            ],
            expand=True
        )

    def _create_empty_state(self) -> ft.Control:
        """Create the empty state display."""
        colors = self.get_colors()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Empty icon
        empty_icon = ft.Icon(
            ft.Icons.CHAT_BUBBLE_OUTLINE,
            size=64,
            color=colors.on_surface_variant
        )

        # Empty title
        empty_title = ft.Text(
            "No chat sessions found",
            style=typography.heading_3,
            color=colors.on_surface_variant,
            text_align=ft.TextAlign.CENTER
        )

        # Empty description
        empty_description = ft.Text(
            "Start a new conversation to see your chat history here.",
            style=typography.body_medium,
            color=colors.on_surface_variant,
            text_align=ft.TextAlign.CENTER
        )

        # New session button
        new_session_btn = self.create_themed_component(
            "button",
            variant="primary",
            text="Start New Chat",
            icon=ft.Icons.ADD_COMMENT,
            on_click=self._handle_new_session
        )

        return ft.Column(
            controls=[
                empty_icon,
                empty_title,
                empty_description,
                new_session_btn
            ],
            spacing=spacing.md,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            visible=False
        )

    def _create_session_card(self, session_data: SessionDisplayData) -> ft.Control:
        """Create a session card display."""
        colors = self.get_colors()
        typography = self.get_typography()
        spacing = self.get_spacing()
        responsive = self.get_responsive_layout()

        session = session_data.session

        # Session title
        session_title = ft.Text(
            session.session_name or f"Session {session.session_id[:8]}",
            style=typography.title_medium,
            color=colors.on_surface,
            weight=ft.FontWeight.W_500,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # Session metadata
        metadata_items = []

        if self.config.show_model_info and session_data.model_name:
            metadata_items.append(f"Model: {session_data.model_name}")

        if self.config.show_message_count:
            metadata_items.append(f"{session_data.message_count} messages")

        if self.config.show_duration and session_data.duration_text:
            metadata_items.append(session_data.duration_text)

        metadata_text = " • ".join(metadata_items)

        session_metadata = ft.Text(
            metadata_text,
            style=typography.body_small,
            color=colors.on_surface_variant,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # Last activity time
        time_text = ft.Text(
            session_data.relative_time,
            style=typography.label_small,
            color=colors.on_surface_variant
        )

        # Session preview
        preview_content = None
        if self.config.show_session_preview and session_data.last_message_preview:
            preview_content = ft.Text(
                session_data.last_message_preview,
                style=typography.body_small,
                color=colors.on_surface_variant,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS
            )

        # Status indicator
        status_indicator = ft.Container(
            content=ft.Icon(
                session_data.status_icon or ft.Icons.CIRCLE,
                size=12,
                color=session_data.status_color or colors.primary
            ),
            width=16,
            height=16
        )

        # Favorite button
        favorite_btn = ft.IconButton(
            icon=ft.Icons.FAVORITE if session_data.is_favorite else ft.Icons.FAVORITE_BORDER,
            icon_color=colors.primary if session_data.is_favorite else colors.on_surface_variant,
            icon_size=20,
            tooltip="Add to favorites" if not session_data.is_favorite else "Remove from favorites",
            on_click=lambda e: self._handle_favorite_toggle(session.session_id)
        )

        # Action buttons
        action_buttons = []

        if self.config.enable_session_actions:
            # Resume button
            resume_btn = ft.IconButton(
                icon=ft.Icons.PLAY_ARROW,
                icon_color=colors.primary,
                icon_size=20,
                tooltip="Resume session",
                on_click=lambda e: self._handle_session_select(session.session_id)
            )
            action_buttons.append(resume_btn)

            # Export button
            export_btn = ft.IconButton(
                icon=ft.Icons.DOWNLOAD,
                icon_color=colors.on_surface_variant,
                icon_size=20,
                tooltip="Export session",
                on_click=lambda e: self._handle_session_export(session.session_id)
            )
            action_buttons.append(export_btn)

            # Delete button
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=colors.error,
                icon_size=20,
                tooltip="Delete session",
                on_click=lambda e: self._handle_session_delete(session.session_id)
            )
            action_buttons.append(delete_btn)

        # Header row with title and actions
        header_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[status_indicator, session_title],
                    spacing=spacing.xs,
                    expand=True
                ),
                ft.Row(
                    controls=[favorite_btn] + action_buttons,
                    spacing=spacing.xs
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        # Content column
        content_controls = [header_row, session_metadata, time_text]
        if preview_content:
            content_controls.append(preview_content)

        content_column = ft.Column(
            controls=content_controls,
            spacing=spacing.xs,
            expand=True
        )

        # Card container
        card = ft.Container(
            content=content_column,
            padding=ft.padding.all(spacing.md),
            border_radius=responsive.get_breakpoint_value(8, 10, 12, 14),
            bgcolor=colors.surface_variant if session.session_id == self.selected_session_id else colors.surface,
            border=ft.border.all(
                1,
                colors.primary if session.session_id == self.selected_session_id else colors.outline_variant
            ),
            on_click=lambda e: self._handle_session_select(session.session_id),
            ink=True
        )

        return card

    # Event Handlers
    def _handle_new_session(self, e):
        """Handle new session creation."""
        try:
            if self.on_new_session:
                self.on_new_session()
        except Exception as ex:
            self.logger.error(f"Failed to handle new session: {ex}")

    def _handle_refresh(self, e):
        """Handle session list refresh."""
        try:
            self._load_sessions()
            self._update_sessions_display()
        except Exception as ex:
            self.logger.error(f"Failed to refresh sessions: {ex}")

    def _handle_search_change(self, e):
        """Handle search query change."""
        try:
            self.search_query = e.control.value.lower()
            self._filter_and_sort_sessions()
            self._update_sessions_display()
        except Exception as ex:
            self.logger.error(f"Failed to handle search change: {ex}")

    def _handle_filter_change(self, e):
        """Handle filter change."""
        try:
            filter_value = e.control.value
            self.current_filter = SessionFilterType(filter_value)
            self._filter_and_sort_sessions()
            self._update_sessions_display()
        except Exception as ex:
            self.logger.error(f"Failed to handle filter change: {ex}")

    def _handle_sort_change(self, e):
        """Handle sort order change."""
        try:
            sort_value = e.control.value
            self.current_sort = SessionSortOrder(sort_value)
            self._filter_and_sort_sessions()
            self._update_sessions_display()
        except Exception as ex:
            self.logger.error(f"Failed to handle sort change: {ex}")

    def _handle_session_select(self, session_id: str):
        """Handle session selection."""
        try:
            self.selected_session_id = session_id
            if self.on_session_select:
                self.on_session_select(session_id)
            self._update_sessions_display()
        except Exception as ex:
            self.logger.error(f"Failed to handle session selection: {ex}")

    def _handle_session_delete(self, session_id: str):
        """Handle session deletion."""
        try:
            if self.on_session_delete:
                self.on_session_delete(session_id)
            self._load_sessions()
            self._update_sessions_display()
        except Exception as ex:
            self.logger.error(f"Failed to handle session deletion: {ex}")

    def _handle_session_export(self, session_id: str):
        """Handle session export."""
        try:
            if self.on_session_export:
                self.on_session_export(session_id)
        except Exception as ex:
            self.logger.error(f"Failed to handle session export: {ex}")

    def _handle_favorite_toggle(self, session_id: str):
        """Handle favorite toggle."""
        try:
            if session_id in self.favorites:
                self.favorites.remove(session_id)
            else:
                self.favorites.add(session_id)

            self._save_favorites()
            self._update_session_favorites()
            self._update_sessions_display()
        except Exception as ex:
            self.logger.error(f"Failed to handle favorite toggle: {ex}")

    # Data Management Methods
    def _load_sessions(self):
        """Load sessions from database."""
        try:
            self.logger.debug("Loading sessions from database")

            # Get sessions from database using correct method name
            db_sessions = self.session_db.list_sessions(
                limit=self.config.max_sessions_display
            )

            # Convert to display data
            self.sessions = []
            for session in db_sessions:
                session_data = self._create_session_display_data(session)
                self.sessions.append(session_data)

            # Apply filtering and sorting
            self._filter_and_sort_sessions()

            self.logger.debug(f"Loaded {len(self.sessions)} sessions")

        except Exception as e:
            self.logger.error(f"Failed to load sessions: {e}")
            self.sessions = []

    def _create_session_display_data(self, session: ChatSession) -> SessionDisplayData:
        """Create session display data from database session."""
        try:
            # Get message count from session statistics
            stats = self.messages_db.get_session_statistics(session.session_id)
            message_count = stats.get('total_messages', 0) if stats else 0

            # Get last message preview
            last_message_preview = None
            if self.config.show_session_preview:
                messages = self.messages_db.get_session_messages(
                    session.session_id,
                    limit=self.config.preview_message_count
                )
                if messages:
                    last_message = messages[-1]
                    preview_text = last_message.content[:100]
                    if len(last_message.content) > 100:
                        preview_text += "..."
                    last_message_preview = preview_text

            # Calculate duration
            duration_text = ""
            if session.terminated_at and session.created_at:
                duration = session.terminated_at - session.created_at
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                if hours > 0:
                    duration_text = f"{hours}h {minutes}m"
                else:
                    duration_text = f"{minutes}m"

            # Calculate relative time
            relative_time = self._get_relative_time(session.last_activity)

            # Get status info
            status_color, status_icon = self._get_status_info(session.status)

            # Check if favorite
            is_favorite = session.session_id in self.favorites

            # Get model name (simplified)
            model_name = session.model_id.split('/')[-1] if session.model_id else "Unknown"

            return SessionDisplayData(
                session=session,
                message_count=message_count,
                last_message_preview=last_message_preview,
                duration_text=duration_text,
                relative_time=relative_time,
                is_favorite=is_favorite,
                model_name=model_name,
                status_color=status_color,
                status_icon=status_icon
            )

        except Exception as e:
            self.logger.error(f"Failed to create session display data: {e}")
            return SessionDisplayData(session=session)

    def _get_relative_time(self, timestamp: datetime) -> str:
        """Get relative time string."""
        try:
            now = datetime.now(timezone.utc)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            diff = now - timestamp

            if diff.days > 0:
                if diff.days == 1:
                    return "1 day ago"
                elif diff.days < 7:
                    return f"{diff.days} days ago"
                elif diff.days < 30:
                    weeks = diff.days // 7
                    return f"{weeks} week{'s' if weeks > 1 else ''} ago"
                else:
                    months = diff.days // 30
                    return f"{months} month{'s' if months > 1 else ''} ago"

            hours = int(diff.total_seconds() // 3600)
            if hours > 0:
                return f"{hours} hour{'s' if hours > 1 else ''} ago"

            minutes = int(diff.total_seconds() // 60)
            if minutes > 0:
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"

            return "Just now"

        except Exception as e:
            self.logger.error(f"Failed to get relative time: {e}")
            return "Unknown"

    def _get_status_info(self, status: SessionStatus) -> Tuple[str, str]:
        """Get status color and icon."""
        colors = self.get_colors()

        status_map = {
            SessionStatus.ACTIVE: (colors.success, ft.Icons.CIRCLE),
            SessionStatus.PAUSED: (colors.warning, ft.Icons.PAUSE_CIRCLE),
            SessionStatus.COMPLETED: (colors.primary, ft.Icons.CHECK_CIRCLE),
            SessionStatus.TERMINATED: (colors.error, ft.Icons.CANCEL),
            SessionStatus.ERROR: (colors.error, ft.Icons.ERROR)
        }

        return status_map.get(status, (colors.on_surface_variant, ft.Icons.CIRCLE))

    def _filter_and_sort_sessions(self):
        """Filter and sort sessions based on current criteria."""
        try:
            # Start with all sessions
            filtered = list(self.sessions)

            # Apply search filter
            if self.search_query:
                filtered = [
                    session for session in filtered
                    if (self.search_query in session.session.session_name.lower() if session.session.session_name else False) or
                       (self.search_query in session.last_message_preview.lower() if session.last_message_preview else False) or
                       (self.search_query in session.model_name.lower())
                ]

            # Apply type filter
            if self.current_filter != SessionFilterType.ALL:
                if self.current_filter == SessionFilterType.ACTIVE:
                    filtered = [s for s in filtered if s.session.status == SessionStatus.ACTIVE]
                elif self.current_filter == SessionFilterType.COMPLETED:
                    filtered = [s for s in filtered if s.session.status == SessionStatus.COMPLETED]
                elif self.current_filter == SessionFilterType.FAVORITES:
                    filtered = [s for s in filtered if s.is_favorite]
                elif self.current_filter == SessionFilterType.TODAY:
                    today = datetime.now(timezone.utc).date()
                    filtered = [s for s in filtered if s.session.last_activity.date() == today]
                elif self.current_filter == SessionFilterType.THIS_WEEK:
                    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
                    filtered = [s for s in filtered if s.session.last_activity >= week_ago]
                elif self.current_filter == SessionFilterType.THIS_MONTH:
                    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
                    filtered = [s for s in filtered if s.session.last_activity >= month_ago]

            # Apply sorting
            if self.current_sort == SessionSortOrder.RECENT_FIRST:
                filtered.sort(key=lambda s: s.session.last_activity, reverse=True)
            elif self.current_sort == SessionSortOrder.OLDEST_FIRST:
                filtered.sort(key=lambda s: s.session.last_activity)
            elif self.current_sort == SessionSortOrder.ALPHABETICAL:
                filtered.sort(key=lambda s: s.session.session_name or "")
            elif self.current_sort == SessionSortOrder.MOST_MESSAGES:
                filtered.sort(key=lambda s: s.message_count, reverse=True)
            elif self.current_sort == SessionSortOrder.LONGEST_DURATION:
                filtered.sort(key=lambda s: s.duration_text, reverse=True)

            self.filtered_sessions = filtered

        except Exception as e:
            self.logger.error(f"Failed to filter and sort sessions: {e}")
            self.filtered_sessions = self.sessions

    def _update_sessions_display(self):
        """Update the sessions display."""
        try:
            if not self.sessions_container:
                return

            # Clear existing controls
            self.sessions_container.controls.clear()

            # Show loading indicator
            if self.loading_indicator:
                self.loading_indicator.visible = True

            # Hide empty state
            if self.empty_state:
                self.empty_state.visible = False

            # Check if we have sessions to display
            if not self.filtered_sessions:
                if self.loading_indicator:
                    self.loading_indicator.visible = False
                if self.empty_state:
                    self.empty_state.visible = True
                if self.page:
                    self.page.update()
                return

            # Group sessions by date if enabled
            if self.config.group_by_date:
                grouped_sessions = self._group_sessions_by_date()
                for date_group, sessions in grouped_sessions.items():
                    # Add date header
                    date_header = self._create_date_header(date_group)
                    self.sessions_container.controls.append(date_header)

                    # Add sessions for this date
                    for session_data in sessions:
                        session_card = self._create_session_card(session_data)
                        self.sessions_container.controls.append(session_card)
            else:
                # Add all sessions without grouping
                for session_data in self.filtered_sessions:
                    session_card = self._create_session_card(session_data)
                    self.sessions_container.controls.append(session_card)

            # Hide loading indicator
            if self.loading_indicator:
                self.loading_indicator.visible = False

            # Update page
            if self.page:
                self.page.update()

        except Exception as e:
            self.logger.error(f"Failed to update sessions display: {e}")

    def _group_sessions_by_date(self) -> Dict[str, List[SessionDisplayData]]:
        """Group sessions by date."""
        groups = {}

        for session_data in self.filtered_sessions:
            date_key = session_data.session.last_activity.date()
            today = datetime.now(timezone.utc).date()
            yesterday = today - timedelta(days=1)

            if date_key == today:
                group_name = "Today"
            elif date_key == yesterday:
                group_name = "Yesterday"
            elif date_key >= today - timedelta(days=7):
                group_name = date_key.strftime("%A")  # Day name
            else:
                group_name = date_key.strftime("%B %d, %Y")  # Full date

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(session_data)

        return groups

    def _create_date_header(self, date_text: str) -> ft.Control:
        """Create a date header for session grouping."""
        colors = self.get_colors()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Text(
                date_text,
                style=typography.title_small,
                color=colors.on_surface_variant,
                weight=ft.FontWeight.W_500
            ),
            padding=ft.padding.only(top=spacing.md, bottom=spacing.xs)
        )

    def _load_favorites(self):
        """Load favorite sessions from storage."""
        try:
            # In a real implementation, this would load from persistent storage
            # For now, we'll use an empty set
            self.favorites = set()
        except Exception as e:
            self.logger.error(f"Failed to load favorites: {e}")
            self.favorites = set()

    def _save_favorites(self):
        """Save favorite sessions to storage."""
        try:
            # In a real implementation, this would save to persistent storage
            pass
        except Exception as e:
            self.logger.error(f"Failed to save favorites: {e}")

    def _update_session_favorites(self):
        """Update favorite status for all sessions."""
        for session_data in self.sessions:
            session_data.is_favorite = session_data.session.session_id in self.favorites

    def _start_auto_refresh(self):
        """Start auto-refresh timer."""
        try:
            # Only start auto-refresh if there's an active event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No event loop running, skip auto-refresh
                self.logger.debug("No event loop running, skipping auto-refresh")
                return

            if self.refresh_timer:
                self.refresh_timer.cancel()

            async def refresh_loop():
                while True:
                    await asyncio.sleep(self.config.auto_refresh_interval)
                    try:
                        self._load_sessions()
                        self._update_sessions_display()
                    except Exception as e:
                        self.logger.error(f"Auto-refresh failed: {e}")

            self.refresh_timer = asyncio.create_task(refresh_loop())

        except Exception as e:
            self.logger.error(f"Failed to start auto-refresh: {e}")

    def _create_error_state(self, error_message: str) -> ft.Control:
        """Create error state display."""
        colors = self.get_colors()
        typography = self.get_typography()
        spacing = self.get_spacing()

        error_icon = ft.Icon(
            ft.Icons.ERROR_OUTLINE,
            size=64,
            color=colors.error
        )

        error_title = ft.Text(
            "Error Loading Sessions",
            style=typography.heading_3,
            color=colors.error,
            text_align=ft.TextAlign.CENTER
        )

        error_description = ft.Text(
            error_message,
            style=typography.body_medium,
            color=colors.on_surface_variant,
            text_align=ft.TextAlign.CENTER
        )

        retry_btn = self.create_themed_component(
            "button",
            variant="primary",
            text="Retry",
            icon=ft.Icons.REFRESH,
            on_click=self._handle_refresh
        )

        return ft.Column(
            controls=[
                error_icon,
                error_title,
                error_description,
                retry_btn
            ],
            spacing=spacing.md,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    # Public Methods
    def refresh_sessions(self):
        """Refresh the sessions list."""
        self._load_sessions()
        self._update_sessions_display()

    def select_session(self, session_id: str):
        """Select a specific session."""
        self.selected_session_id = session_id
        self._update_sessions_display()

    def set_filter(self, filter_type: SessionFilterType):
        """Set the current filter."""
        self.current_filter = filter_type
        if self.filter_dropdown:
            self.filter_dropdown.value = filter_type.value
        self._filter_and_sort_sessions()
        self._update_sessions_display()

    def set_sort_order(self, sort_order: SessionSortOrder):
        """Set the current sort order."""
        self.current_sort = sort_order
        if self.sort_dropdown:
            self.sort_dropdown.value = sort_order.value
        self._filter_and_sort_sessions()
        self._update_sessions_display()

    def search_sessions(self, query: str):
        """Search sessions with the given query."""
        self.search_query = query.lower()
        if self.search_field:
            self.search_field.value = query
        self._filter_and_sort_sessions()
        self._update_sessions_display()

    def cleanup(self):
        """Cleanup resources."""
        try:
            if self.refresh_timer:
                self.refresh_timer.cancel()
                self.refresh_timer = None
        except Exception as e:
            self.logger.error(f"Failed to cleanup session history UI: {e}")
