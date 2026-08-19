"""
Module: chat_window_ui
Description: Main chat interface with message history, typing indicators, and real-time conversation display.
            Provides comprehensive chat window functionality with responsive design, theme integration,
            message threading, session management, and accessibility features for the MikroDok application.
Phase: 4
Location: /src/modules/ui/chat_interface_ui/chat_window_ui/chat_window_ui.py
"""

# Standard library imports
import asyncio
import uuid
from datetime import datetime, timezone
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
    ChatMessagesDB, ChatMessage, MessageRole, MessageStatus
)
from src.modules.logic.conversation_management_lg.base_interfaces import (
    ConversationMessage, MessagePriority, ContextWindow
)


class ChatDisplayMode(Enum):
    """Chat display mode enumeration."""
    CONVERSATION = "conversation"
    THREAD = "thread"
    COMPACT = "compact"
    FULL_SCREEN = "full_screen"


class MessageAlignment(Enum):
    """Message alignment enumeration."""
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


@dataclass
class ChatWindowConfig:
    """Configuration for chat window behavior."""
    max_messages_displayed: int = 100
    auto_scroll_enabled: bool = True
    typing_indicator_enabled: bool = True
    message_timestamps_visible: bool = True
    message_avatars_enabled: bool = True
    compact_mode_threshold: int = 768  # px
    animation_duration_ms: int = 300
    scroll_buffer_size: int = 20
    enable_message_threading: bool = True
    enable_context_menu: bool = True
    enable_message_selection: bool = True
    enable_copy_functionality: bool = True
    enable_search_highlighting: bool = True
    auto_save_interval_seconds: int = 30


@dataclass
class MessageDisplayData:
    """Data structure for message display."""
    message: ChatMessage
    is_user: bool
    alignment: MessageAlignment
    show_avatar: bool = True
    show_timestamp: bool = True
    is_highlighted: bool = False
    is_selected: bool = False
    thread_level: int = 0
    animation_delay_ms: int = 0


@dataclass
class TypingIndicatorData:
    """Data structure for typing indicator."""
    is_visible: bool = False
    user_name: Optional[str] = None
    start_time: Optional[datetime] = None
    animation_phase: int = 0


class ChatWindowUI(ThemeAwareUserControl):
    """
    Main chat interface with comprehensive conversation display and management.

    Features:
    - Responsive message display with adaptive layouts and breakpoint-aware design
    - Real-time message streaming with typing indicators and status updates
    - Message threading and conversation history with context window management
    - Session management integration with persistent chat storage
    - Theme-aware styling with full ResponsiveLayoutManager integration
    - Accessibility compliance with keyboard navigation and screen reader support
    - Performance optimization for large conversation histories
    - Message search and highlighting capabilities
    - Context menu support with copy, reply, and thread actions
    - Auto-scroll management with smart scroll behavior
    - Message status indicators (pending, sent, delivered, error)
    - Avatar and timestamp display with configurable visibility
    - Compact and full-screen display modes
    - Message selection and bulk operations support
    """

    def __init__(self,
                 session_id: Optional[str] = None,
                 config: Optional[ChatWindowConfig] = None,
                 on_message_send: Optional[Callable[[str], None]] = None,
                 on_message_select: Optional[Callable[[List[str]], None]] = None,
                 on_session_change: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the chat window UI.

        Args:
            session_id: Current chat session ID
            config: Chat window configuration
            on_message_send: Callback for sending messages
            on_message_select: Callback for message selection
            on_session_change: Callback for session changes
            **kwargs: Additional container arguments
        """
        super().__init__(**kwargs)

        # Configuration
        self._config = config or ChatWindowConfig()
        self._session_id = session_id

        # Callbacks
        self._on_message_send = on_message_send
        self._on_message_select = on_message_select
        self._on_session_change = on_session_change

        # Database connections
        self._session_db = ChatSessionDB()
        self._messages_db = ChatMessagesDB()

        # State management
        self._current_session: Optional[ChatSession] = None
        self._messages: List[MessageDisplayData] = []
        self._selected_messages: List[str] = []
        self._display_mode = ChatDisplayMode.CONVERSATION
        self._typing_indicator = TypingIndicatorData()
        self._search_query: Optional[str] = None
        self._is_loading = False
        self._auto_scroll_enabled = self._config.auto_scroll_enabled

        # UI components
        self._message_container: Optional[ft.Column] = None
        self._scroll_view: Optional[ft.ListView] = None
        self._typing_indicator_widget: Optional[ft.Control] = None
        self._status_bar: Optional[ft.Control] = None
        self._context_menu: Optional[ft.Control] = None

        # Performance tracking
        self._last_message_count = 0
        self._scroll_position = 0.0
        self._render_start_index = 0
        self._render_end_index = 0

        # Animation and timing
        self._animation_timer: Optional[asyncio.Task] = None
        self._auto_save_timer: Optional[asyncio.Task] = None

        # Logger
        self._logger = logging.getLogger(__name__)

        # Initialize session if provided
        if self._session_id:
            asyncio.create_task(self._load_session(self._session_id))

    def build(self) -> None:
        """Build the chat window UI with responsive design and theme integration."""
        try:
            self._logger.debug("Building ChatWindowUI component")

            # Get theme components
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            # Responsive padding and sizing
            responsive_padding = self.get_responsive_padding()

            # Build main chat container
            main_content = self._build_main_chat_area()

            # Build status bar if enabled
            status_bar = self._build_status_bar() if self._config.message_timestamps_visible else None

            # Create main layout
            chat_layout = ft.Column(
                controls=[
                    main_content,
                    status_bar
                ] if status_bar else [main_content],
                spacing=0,
                expand=True
            )

            # Create main container with responsive design
            self.content = self.create_responsive_container(
                content=chat_layout,
                padding=responsive_padding
            )

            self._logger.debug("ChatWindowUI component built successfully")

        except Exception as e:
            self._logger.error(f"Error building chat window component: {e}")
            self.content = self._create_error_fallback()

    def _build_main_chat_area(self) -> ft.Control:
        """Build the main chat message area with scrolling and message display."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Create message container
            self._message_container = ft.Column(
                controls=[],
                spacing=spacing.sm,
                scroll=ft.ScrollMode.AUTO,
                auto_scroll=self._auto_scroll_enabled
            )

            # Create scroll view with responsive sizing
            scroll_height = self.get_breakpoint_value(
                mobile=400, tablet=500, desktop=600, large=700
            )

            self._scroll_view = ft.Container(
                content=self._message_container,
                height=scroll_height,
                bgcolor=palette.surface,
                border_radius=self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=12
                ),
                border=ft.border.all(1, palette.outline_variant),
                padding=ft.padding.all(spacing.md),
                expand=True
            )

            # Add typing indicator placeholder
            if self._config.typing_indicator_enabled:
                self._typing_indicator_widget = self._build_typing_indicator()

            # Create chat area with typing indicator
            chat_area = ft.Column(
                controls=[
                    self._scroll_view,
                    self._typing_indicator_widget
                ] if self._typing_indicator_widget else [self._scroll_view],
                spacing=spacing.sm,
                expand=True
            )

            # Load messages if session exists
            if self._session_id:
                asyncio.create_task(self._load_messages())

            return chat_area

        except Exception as e:
            self._logger.error(f"Error building main chat area: {e}")
            return self._create_error_fallback()

    def _build_typing_indicator(self) -> ft.Control:
        """Build the typing indicator widget."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            # Typing dots animation
            typing_dots = ft.Row(
                controls=[
                    ft.Container(
                        width=8,
                        height=8,
                        bgcolor=palette.primary,
                        border_radius=ft.border_radius.all(4)
                    ) for _ in range(3)
                ],
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.CENTER
            )

            # Typing indicator container
            indicator_container = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.EDIT,
                            size=16,
                            color=palette.on_surface_variant
                        ),
                        ft.Text(
                            "AI is typing",
                            style=typography.body_small,
                            color=palette.on_surface_variant,
                            italic=True
                        ),
                        typing_dots
                    ],
                    spacing=spacing.sm,
                    alignment=ft.MainAxisAlignment.START
                ),
                padding=ft.padding.symmetric(
                    horizontal=spacing.md,
                    vertical=spacing.sm
                ),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(8),
                visible=False
            )

            return indicator_container

        except Exception as e:
            self._logger.error(f"Error building typing indicator: {e}")
            return ft.Container()

    def _build_status_bar(self) -> ft.Control:
        """Build the status bar with session information."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            # Session info
            session_info = ft.Text(
                self._get_session_status_text(),
                style=typography.body_small,
                color=palette.on_surface_variant
            )

            # Message count
            message_count = ft.Text(
                f"{len(self._messages)} messages",
                style=typography.body_small,
                color=palette.on_surface_variant
            )

            # Status bar container
            self._status_bar = ft.Container(
                content=ft.Row(
                    controls=[
                        session_info,
                        ft.VerticalDivider(width=1, color=palette.outline_variant),
                        message_count
                    ],
                    spacing=spacing.sm,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=ft.padding.symmetric(
                    horizontal=spacing.md,
                    vertical=spacing.sm
                ),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.only(
                    bottom_left=8, bottom_right=8
                )
            )

            return self._status_bar

        except Exception as e:
            self._logger.error(f"Error building status bar: {e}")
            return ft.Container()

    def _build_message_bubble(self, message_data: MessageDisplayData) -> ft.Control:
        """Build a message bubble for display."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            message = message_data.message
            is_user = message_data.is_user

            # Message content
            content_text = ft.Text(
                message.content,
                style=typography.body_medium,
                color=palette.on_surface if not is_user else palette.on_primary,
                selectable=True
            )

            # Timestamp
            timestamp_text = None
            if message_data.show_timestamp and self._config.message_timestamps_visible:
                timestamp_str = message.timestamp.strftime("%H:%M")
                timestamp_text = ft.Text(
                    timestamp_str,
                    style=typography.body_small,
                    color=palette.on_surface_variant,
                    size=10
                )

            # Message status indicator
            status_icon = None
            if is_user and message.status != MessageStatus.COMPLETED:
                status_icons = {
                    MessageStatus.PENDING: ft.Icons.SCHEDULE,
                    MessageStatus.PROCESSING: ft.Icons.SYNC,
                    MessageStatus.ERROR: ft.Icons.ERROR,
                    MessageStatus.CANCELLED: ft.Icons.CANCEL
                }
                status_icon = ft.Icon(
                    status_icons.get(message.status, ft.Icons.HELP),
                    size=12,
                    color=palette.on_surface_variant
                )

            # Build message content
            message_content = ft.Column(
                controls=[
                    content_text,
                    ft.Row(
                        controls=[
                            timestamp_text,
                            status_icon
                        ] if timestamp_text and status_icon else [timestamp_text] if timestamp_text else [status_icon] if status_icon else [],
                        spacing=spacing.xs,
                        alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
                    )
                ] if timestamp_text or status_icon else [content_text],
                spacing=spacing.xs,
                tight=True
            )

            # Message bubble container
            bubble_bgcolor = palette.primary if is_user else palette.surface_variant
            bubble_alignment = ft.alignment.center_right if is_user else ft.alignment.center_left

            bubble = ft.Container(
                content=message_content,
                bgcolor=bubble_bgcolor,
                border_radius=ft.border_radius.all(
                    self.get_breakpoint_value(
                        mobile=12, tablet=14, desktop=16, large=16
                    )
                ),
                padding=ft.padding.all(spacing.md),
                margin=ft.margin.only(
                    left=spacing.xl if is_user else 0,
                    right=0 if is_user else spacing.xl
                ),
                alignment=bubble_alignment,
                on_click=lambda e: self._on_message_click(message.message_id),
                on_long_press=lambda e: self._on_message_long_press(message.message_id)
            )

            # Avatar (if enabled)
            avatar = None
            if message_data.show_avatar and self._config.message_avatars_enabled:
                avatar_icon = ft.Icons.PERSON if is_user else ft.Icons.SMART_TOY
                avatar = ft.CircleAvatar(
                    content=ft.Icon(
                        avatar_icon,
                        size=20,
                        color=palette.on_primary
                    ),
                    bgcolor=palette.primary if is_user else palette.secondary,
                    radius=16
                )

            # Message row with avatar
            message_row = ft.Row(
                controls=[
                    avatar if avatar and not is_user else ft.Container(width=32),
                    bubble,
                    avatar if avatar and is_user else ft.Container(width=32)
                ],
                spacing=spacing.sm,
                alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
            )

            return message_row

        except Exception as e:
            self._logger.error(f"Error building message bubble: {e}")
            return ft.Container()

    async def _load_session(self, session_id: str) -> None:
        """Load chat session and initialize UI."""
        try:
            self._logger.debug(f"Loading chat session: {session_id}")
            self._is_loading = True

            # Load session from database
            self._current_session = self._session_db.get_session(session_id)
            if not self._current_session:
                self._logger.warning(f"Session not found: {session_id}")
                return

            self._session_id = session_id

            # Load messages
            await self._load_messages()

            # Update UI
            if self._status_bar:
                self._update_status_bar()

            # Notify session change
            if self._on_session_change:
                self._on_session_change(session_id)

            self._is_loading = False
            self._logger.debug(f"Session loaded successfully: {session_id}")

        except Exception as e:
            self._logger.error(f"Error loading session {session_id}: {e}")
            self._is_loading = False

    async def _load_messages(self) -> None:
        """Load messages for the current session."""
        try:
            if not self._session_id:
                return

            self._logger.debug(f"Loading messages for session: {self._session_id}")

            # Get messages from database
            messages = self._messages_db.get_session_messages(
                self._session_id,
                limit=self._config.max_messages_displayed
            )

            # Convert to display data
            self._messages = []
            for message in messages:
                is_user = message.role == MessageRole.USER
                alignment = MessageAlignment.RIGHT if is_user else MessageAlignment.LEFT

                display_data = MessageDisplayData(
                    message=message,
                    is_user=is_user,
                    alignment=alignment,
                    show_avatar=self._config.message_avatars_enabled,
                    show_timestamp=self._config.message_timestamps_visible
                )
                self._messages.append(display_data)

            # Update message display
            await self._update_message_display()

            self._logger.debug(f"Loaded {len(self._messages)} messages")

        except Exception as e:
            self._logger.error(f"Error loading messages: {e}")

    async def _update_message_display(self) -> None:
        """Update the message display with current messages."""
        try:
            if not self._message_container:
                return

            # Clear existing messages
            self._message_container.controls.clear()

            # Add message bubbles
            for message_data in self._messages:
                bubble = self._build_message_bubble(message_data)
                self._message_container.controls.append(bubble)

            # Update UI
            if self.page:
                self._message_container.update()

                # Auto-scroll to bottom if enabled
                if self._auto_scroll_enabled:
                    await asyncio.sleep(0.1)  # Allow UI to update
                    self._scroll_to_bottom()

        except Exception as e:
            self._logger.error(f"Error updating message display: {e}")

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the message list."""
        try:
            if self._message_container and self.page:
                self._message_container.scroll_to(
                    offset=self._message_container.height,
                    duration=self._config.animation_duration_ms
                )
        except Exception as e:
            self._logger.error(f"Error scrolling to bottom: {e}")

    def _get_session_status_text(self) -> str:
        """Get session status text for display."""
        if not self._current_session:
            return "No active session"

        status_text = {
            SessionStatus.ACTIVE: "Active",
            SessionStatus.PAUSED: "Paused",
            SessionStatus.TERMINATED: "Ended"
        }.get(self._current_session.status, "Unknown")

        return f"Session: {status_text}"

    def _update_status_bar(self) -> None:
        """Update the status bar with current information."""
        try:
            if not self._status_bar:
                return

            # Update session info and message count
            session_text = self._get_session_status_text()
            message_count_text = f"{len(self._messages)} messages"

            # Update status bar controls
            if hasattr(self._status_bar, 'content') and hasattr(self._status_bar.content, 'controls'):
                controls = self._status_bar.content.controls
                if len(controls) >= 3:
                    controls[0].value = session_text
                    controls[2].value = message_count_text

                    if self.page:
                        self._status_bar.update()

        except Exception as e:
            self._logger.error(f"Error updating status bar: {e}")

    def _on_message_click(self, message_id: str) -> None:
        """Handle message click events."""
        try:
            if not self._config.enable_message_selection:
                return

            # Toggle message selection
            if message_id in self._selected_messages:
                self._selected_messages.remove(message_id)
            else:
                self._selected_messages.append(message_id)

            # Notify selection change
            if self._on_message_select:
                self._on_message_select(self._selected_messages.copy())

            # Update visual selection (would need to rebuild affected messages)
            asyncio.create_task(self._update_message_selection())

        except Exception as e:
            self._logger.error(f"Error handling message click: {e}")

    def _on_message_long_press(self, message_id: str) -> None:
        """Handle message long press events for context menu."""
        try:
            if not self._config.enable_context_menu:
                return

            # Show context menu for message
            self._show_message_context_menu(message_id)

        except Exception as e:
            self._logger.error(f"Error handling message long press: {e}")

    def _show_message_context_menu(self, message_id: str) -> None:
        """Show context menu for a message."""
        try:
            # Find the message
            message_data = next(
                (m for m in self._messages if m.message.message_id == message_id),
                None
            )

            if not message_data:
                return

            # Context menu options
            menu_items = []

            if self._config.enable_copy_functionality:
                menu_items.append(
                    ft.MenuItemButton(
                        content=ft.Text("Copy"),
                        leading=ft.Icon(ft.Icons.COPY),
                        on_click=lambda e: self._copy_message(message_id)
                    )
                )

            if self._config.enable_message_threading:
                menu_items.append(
                    ft.MenuItemButton(
                        content=ft.Text("Reply"),
                        leading=ft.Icon(ft.Icons.REPLY),
                        on_click=lambda e: self._reply_to_message(message_id)
                    )
                )

            # Show menu (implementation would depend on Flet's context menu support)
            # For now, we'll log the action
            self._logger.debug(f"Context menu requested for message: {message_id}")

        except Exception as e:
            self._logger.error(f"Error showing context menu: {e}")

    def _copy_message(self, message_id: str) -> None:
        """Copy message content to clipboard."""
        try:
            message_data = next(
                (m for m in self._messages if m.message.message_id == message_id),
                None
            )

            if message_data and self.page:
                self.page.set_clipboard(message_data.message.content)
                self._logger.debug(f"Message copied to clipboard: {message_id}")

        except Exception as e:
            self._logger.error(f"Error copying message: {e}")

    def _reply_to_message(self, message_id: str) -> None:
        """Reply to a specific message."""
        try:
            # This would typically trigger the message input to show a reply context
            self._logger.debug(f"Reply to message: {message_id}")

        except Exception as e:
            self._logger.error(f"Error replying to message: {e}")

    async def _update_message_selection(self) -> None:
        """Update visual selection state of messages."""
        try:
            # Update selection state in message data
            for message_data in self._messages:
                message_data.is_selected = message_data.message.message_id in self._selected_messages

            # Rebuild message display to show selection
            await self._update_message_display()

        except Exception as e:
            self._logger.error(f"Error updating message selection: {e}")

    def _create_error_fallback(self) -> ft.Control:
        """Create error fallback UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE,
                        size=48,
                        color=palette.error
                    ),
                    ft.Text(
                        "Error loading chat window",
                        style=self.get_text_style("headlineSmall"),
                        color=palette.on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Please try refreshing or contact support",
                        style=self.get_text_style("bodyMedium"),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.md
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.all(spacing.xl),
            expand=True
        )

    # Public API Methods

    async def set_session(self, session_id: str) -> None:
        """
        Set the current chat session.

        Args:
            session_id: Session identifier to load
        """
        try:
            if session_id != self._session_id:
                await self._load_session(session_id)
        except Exception as e:
            self._logger.error(f"Error setting session: {e}")

    async def add_message(self, content: str, role: MessageRole,
                         message_id: Optional[str] = None) -> str:
        """
        Add a new message to the chat.

        Args:
            content: Message content
            role: Message role (USER, ASSISTANT, etc.)
            message_id: Optional message ID (generated if not provided)

        Returns:
            Message ID
        """
        try:
            if not self._session_id:
                raise ValueError("No active session")

            # Generate message ID if not provided
            if not message_id:
                message_id = str(uuid.uuid4())

            # Add message to database
            self._messages_db.add_message(
                session_id=self._session_id,
                role=role,
                content=content,
                token_count=len(content.split())  # Simple token estimation
            )

            # Reload messages to update display
            await self._load_messages()

            return message_id

        except Exception as e:
            self._logger.error(f"Error adding message: {e}")
            raise

    def show_typing_indicator(self, user_name: Optional[str] = None) -> None:
        """
        Show typing indicator.

        Args:
            user_name: Optional name of typing user
        """
        try:
            if self._typing_indicator_widget and self._config.typing_indicator_enabled:
                self._typing_indicator.is_visible = True
                self._typing_indicator.user_name = user_name
                self._typing_indicator.start_time = datetime.now(timezone.utc)

                self._typing_indicator_widget.visible = True
                if self.page:
                    self._typing_indicator_widget.update()

        except Exception as e:
            self._logger.error(f"Error showing typing indicator: {e}")

    def hide_typing_indicator(self) -> None:
        """Hide typing indicator."""
        try:
            if self._typing_indicator_widget:
                self._typing_indicator.is_visible = False
                self._typing_indicator_widget.visible = False
                if self.page:
                    self._typing_indicator_widget.update()

        except Exception as e:
            self._logger.error(f"Error hiding typing indicator: {e}")

    def clear_messages(self) -> None:
        """Clear all messages from display."""
        try:
            self._messages.clear()
            self._selected_messages.clear()

            if self._message_container:
                self._message_container.controls.clear()
                if self.page:
                    self._message_container.update()

            self._update_status_bar()

        except Exception as e:
            self._logger.error(f"Error clearing messages: {e}")

    def set_display_mode(self, mode: ChatDisplayMode) -> None:
        """
        Set chat display mode.

        Args:
            mode: Display mode to set
        """
        try:
            if mode != self._display_mode:
                self._display_mode = mode
                # Rebuild UI with new mode
                asyncio.create_task(self._update_message_display())

        except Exception as e:
            self._logger.error(f"Error setting display mode: {e}")

    def get_selected_messages(self) -> List[str]:
        """
        Get list of selected message IDs.

        Returns:
            List of selected message IDs
        """
        return self._selected_messages.copy()

    def clear_selection(self) -> None:
        """Clear message selection."""
        try:
            self._selected_messages.clear()
            asyncio.create_task(self._update_message_selection())
        except Exception as e:
            self._logger.error(f"Error clearing selection: {e}")

    def scroll_to_message(self, message_id: str) -> None:
        """
        Scroll to a specific message.

        Args:
            message_id: ID of message to scroll to
        """
        try:
            # Find message index
            message_index = next(
                (i for i, m in enumerate(self._messages)
                 if m.message.message_id == message_id),
                None
            )

            if message_index is not None and self._message_container:
                # Calculate scroll position (approximate)
                scroll_position = message_index * 100  # Approximate message height
                self._message_container.scroll_to(
                    offset=scroll_position,
                    duration=self._config.animation_duration_ms
                )

        except Exception as e:
            self._logger.error(f"Error scrolling to message: {e}")

    def set_auto_scroll(self, enabled: bool) -> None:
        """
        Enable or disable auto-scroll.

        Args:
            enabled: Whether to enable auto-scroll
        """
        self._auto_scroll_enabled = enabled
        if self._message_container:
            self._message_container.auto_scroll = enabled

    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current session information.

        Returns:
            Session information dictionary or None
        """
        if not self._current_session:
            return None

        return {
            "session_id": self._current_session.session_id,
            "model_id": self._current_session.model_id,
            "status": self._current_session.status.value,
            "created_at": self._current_session.created_at.isoformat(),
            "message_count": len(self._messages),
            "total_tokens": self._current_session.total_tokens
        }

    def will_unmount(self) -> None:
        """Clean up resources when component is unmounted."""
        try:
            # Cancel any running timers
            if self._animation_timer and not self._animation_timer.done():
                self._animation_timer.cancel()

            if self._auto_save_timer and not self._auto_save_timer.done():
                self._auto_save_timer.cancel()

            # Call parent cleanup
            super().will_unmount()

        except Exception as e:
            self._logger.error(f"Error during cleanup: {e}")

    def __init__(self,
                 session_id: Optional[str] = None,
                 config: Optional[ChatWindowConfig] = None,
                 on_message_send: Optional[Callable[[str], None]] = None,
                 on_message_select: Optional[Callable[[List[str]], None]] = None,
                 on_session_change: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the chat window UI.

        Args:
            session_id: Current chat session ID
            config: Chat window configuration
            on_message_send: Callback for sending messages
            on_message_select: Callback for message selection
            on_session_change: Callback for session changes
            **kwargs: Additional container arguments
        """
        super().__init__(**kwargs)

        # Configuration
        self._config = config or ChatWindowConfig()
        self._session_id = session_id

        # Callbacks
        self._on_message_send = on_message_send
        self._on_message_select = on_message_select
        self._on_session_change = on_session_change

        # Database connections
        self._session_db = ChatSessionDB()
        self._messages_db = ChatMessagesDB()

        # State management
        self._current_session: Optional[ChatSession] = None
        self._messages: List[MessageDisplayData] = []
        self._selected_messages: List[str] = []
        self._display_mode = ChatDisplayMode.CONVERSATION
        self._typing_indicator = TypingIndicatorData()
        self._search_query: Optional[str] = None
        self._is_loading = False
        self._auto_scroll_enabled = self._config.auto_scroll_enabled

        # UI components
        self._message_container: Optional[ft.Column] = None
        self._scroll_view: Optional[ft.ListView] = None
        self._typing_indicator_widget: Optional[ft.Control] = None
        self._status_bar: Optional[ft.Control] = None
        self._context_menu: Optional[ft.Control] = None

        # Performance tracking
        self._last_message_count = 0
        self._scroll_position = 0.0
        self._render_start_index = 0
        self._render_end_index = 0

        # Animation and timing
        self._animation_timer: Optional[asyncio.Task] = None
        self._auto_save_timer: Optional[asyncio.Task] = None

        # Logger
        self._logger = logging.getLogger(__name__)

        # Initialize session if provided
        if self._session_id:
            asyncio.create_task(self._load_session(self._session_id))
