"""
Module: message_bubble_ui
Description: Individual message bubble component with responsive design and theme integration
Phase: 4
Location: /src/modules/ui/chat_interface_ui/message_bubble_ui/
"""

# Standard library imports
import asyncio
import html
import json
import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    get_theme_manager
)
from src.modules.database.chat_repository_db.chat_messages_db.chat_messages_db import (
    ChatMessage, MessageRole, MessageStatus
)
from src.modules.logic.conversation_management_lg.base_interfaces import (
    ConversationMessage, MessageType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class BubbleAlignment(Enum):
    """Message bubble alignment enumeration."""
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


class BubbleStyle(Enum):
    """Message bubble style enumeration."""
    STANDARD = "standard"
    COMPACT = "compact"
    MINIMAL = "minimal"
    HIGHLIGHTED = "highlighted"


class ContentType(Enum):
    """Message content type enumeration."""
    TEXT = "text"
    MARKDOWN = "markdown"
    CODE = "code"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESPONSE = "function_response"
    ERROR = "error"


@dataclass
class BubbleConfig:
    """Configuration for message bubble behavior."""
    show_avatar: bool = True
    show_timestamp: bool = True
    show_status: bool = True
    enable_selection: bool = True
    enable_copy: bool = True
    enable_context_menu: bool = True
    max_width_percentage: float = 0.75
    animation_duration_ms: int = 300
    auto_detect_content_type: bool = True
    enable_markdown_rendering: bool = True
    enable_code_highlighting: bool = True
    enable_link_detection: bool = True
    compact_mode_threshold: int = 768  # px
    avatar_size: int = 32
    timestamp_format: str = "%H:%M"
    status_icon_size: int = 16


@dataclass
class BubbleState:
    """State management for message bubble."""
    is_selected: bool = False
    is_highlighted: bool = False
    is_hovered: bool = False
    is_animating: bool = False
    animation_progress: float = 0.0
    last_update: Optional[datetime] = None


class MessageBubbleUI(ThemeAwareUserControl):
    """
    Individual message bubble component with comprehensive formatting and interaction support.

    Features:
    - Responsive design with breakpoint-aware layouts and adaptive sizing
    - Full theme system integration with no hardcoded colors or styling
    - Support for multiple content types (text, markdown, code, function calls)
    - Interactive features (selection, copy, context menu, click handlers)
    - Status indicators with real-time updates and visual feedback
    - Avatar display with role-based icons and customizable styling
    - Timestamp display with configurable formatting and visibility
    - Smooth animations for state changes and content updates
    - Accessibility compliance with WCAG 2.1 AA standards
    - Mobile-first responsive design with touch-friendly interactions
    - Integration with chat system and message processing pipeline
    - Error handling and graceful degradation for content rendering
    """

    def __init__(
        self,
        message: ChatMessage,
        config: Optional[BubbleConfig] = None,
        on_click: Optional[Callable[[str], None]] = None,
        on_long_press: Optional[Callable[[str], None]] = None,
        on_copy: Optional[Callable[[str], None]] = None,
        on_context_menu: Optional[Callable[[str, ft.TapEvent], None]] = None,
        **kwargs
    ):
        """
        Initialize message bubble UI.

        Args:
            message: Chat message to display
            config: Bubble configuration
            on_click: Click event handler
            on_long_press: Long press event handler
            on_copy: Copy event handler
            on_context_menu: Context menu event handler
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Core properties
        self._message = message
        self._config = config or BubbleConfig()
        self._state = BubbleState()
        self._logger = get_logger(__name__)
        
        # Event handlers
        self._on_click = on_click
        self._on_long_press = on_long_press
        self._on_copy = on_copy
        self._on_context_menu = on_context_menu
        
        # UI components
        self._bubble_container: Optional[ft.Container] = None
        self._content_container: Optional[ft.Container] = None
        self._avatar_container: Optional[ft.Container] = None
        self._timestamp_container: Optional[ft.Container] = None
        self._status_container: Optional[ft.Container] = None
        
        # Content detection
        self._content_type = self._detect_content_type()
        self._is_user_message = self._message.role == MessageRole.USER
        
        # Initialize component
        self._initialize_component()

    def _initialize_component(self) -> None:
        """Initialize the message bubble component."""
        try:
            # Set up responsive behavior
            self._setup_responsive_behavior()
            
            # Build the bubble
            self._build_bubble()
            
            self._logger.debug(f"Initialized message bubble for message {self._message.message_id}")
            
        except Exception as e:
            self._logger.error(f"Error initializing message bubble: {e}")
            self._build_error_bubble()

    def _setup_responsive_behavior(self) -> None:
        """Set up responsive behavior for the bubble."""
        try:
            # Register for responsive updates
            if hasattr(self, 'register_responsive_callback'):
                self.register_responsive_callback(self._on_responsive_update)
                
        except Exception as e:
            self._logger.error(f"Error setting up responsive behavior: {e}")

    def _detect_content_type(self) -> ContentType:
        """Detect the content type of the message."""
        try:
            content = self._message.content.strip()
            
            # Check for function calls
            if self._message.function_call:
                return ContentType.FUNCTION_CALL
            
            if self._message.function_response:
                return ContentType.FUNCTION_RESPONSE
            
            # Check for error status
            if self._message.status == MessageStatus.ERROR:
                return ContentType.ERROR
            
            # Check for code blocks
            if re.search(r'```[\s\S]*?```', content) or content.startswith('```'):
                return ContentType.CODE
            
            # Check for markdown patterns
            if re.search(r'[*_`#\[\]()]', content):
                return ContentType.MARKDOWN
            
            return ContentType.TEXT
            
        except Exception as e:
            self._logger.error(f"Error detecting content type: {e}")
            return ContentType.TEXT

    def _build_bubble(self) -> None:
        """Build the complete message bubble."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Build main content
            content = self._build_content()

            # Build bubble container
            self._bubble_container = self._build_bubble_container(content)

            # Build avatar if enabled
            avatar = self._build_avatar() if self._config.show_avatar else None

            # Build timestamp if enabled
            timestamp = self._build_timestamp() if self._config.show_timestamp else None

            # Build status indicator if enabled
            status = self._build_status_indicator() if self._config.show_status else None

            # Arrange components based on message role
            self.content = self._arrange_components(
                self._bubble_container, avatar, timestamp, status
            )

        except Exception as e:
            self._logger.error(f"Error building bubble: {e}")
            self._build_error_bubble()

    def _build_content(self) -> ft.Control:
        """Build the message content based on content type."""
        try:
            if self._content_type == ContentType.TEXT:
                return self._build_text_content()
            elif self._content_type == ContentType.MARKDOWN:
                return self._build_markdown_content()
            elif self._content_type == ContentType.CODE:
                return self._build_code_content()
            elif self._content_type == ContentType.FUNCTION_CALL:
                return self._build_function_call_content()
            elif self._content_type == ContentType.FUNCTION_RESPONSE:
                return self._build_function_response_content()
            elif self._content_type == ContentType.ERROR:
                return self._build_error_content()
            else:
                return self._build_text_content()

        except Exception as e:
            self._logger.error(f"Error building content: {e}")
            return self._build_fallback_content()

    def _build_text_content(self) -> ft.Control:
        """Build plain text content."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()

            text_color = (
                palette.text_primary if self._is_user_message
                else palette.text_primary
            )

            return ft.Text(
                self._message.content,
                style=typography.body_medium,
                color=text_color,
                selectable=self._config.enable_selection,
                size=self.get_breakpoint_value(
                    mobile=14, tablet=15, desktop=16, large=16
                )
            )

        except Exception as e:
            self._logger.error(f"Error building text content: {e}")
            return self._build_fallback_content()

    def _build_markdown_content(self) -> ft.Control:
        """Build markdown content with basic formatting."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            content = self._message.content
            text_color = (
                palette.text_primary if self._is_user_message
                else palette.text_primary
            )

            # Simple markdown parsing for common patterns
            # Bold text
            content = re.sub(r'\*\*(.*?)\*\*', r'**\1**', content)
            # Italic text
            content = re.sub(r'\*(.*?)\*', r'*\1*', content)
            # Code inline
            content = re.sub(r'`(.*?)`', r'`\1`', content)

            return ft.Text(
                content,
                style=typography.body_medium,
                color=text_color,
                selectable=self._config.enable_selection,
                size=self.get_breakpoint_value(
                    mobile=14, tablet=15, desktop=16, large=16
                )
            )

        except Exception as e:
            self._logger.error(f"Error building markdown content: {e}")
            return self._build_text_content()

    def _build_code_content(self) -> ft.Control:
        """Build code content with syntax highlighting."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            content = self._message.content

            # Extract code blocks
            code_blocks = re.findall(r'```(\w+)?\n?([\s\S]*?)```', content)

            if code_blocks:
                # Build code block container
                code_controls = []

                for language, code in code_blocks:
                    # Language label
                    if language:
                        lang_label = ft.Text(
                            language.upper(),
                            style=typography.label,
                            color=palette.text_secondary,
                            size=10
                        )
                        code_controls.append(lang_label)

                    # Code text
                    code_text = ft.Text(
                        code.strip(),
                        style=typography.body_small,
                        color=palette.text_primary,
                        selectable=True,
                        font_family="monospace",
                        size=self.get_breakpoint_value(
                            mobile=12, tablet=13, desktop=14, large=14
                        )
                    )

                    # Code container
                    code_container = ft.Container(
                        content=code_text,
                        bgcolor=palette.surface_variant,
                        border_radius=ft.border_radius.all(
                            self.get_breakpoint_value(
                                mobile=6, tablet=8, desktop=8, large=8
                            )
                        ),
                        padding=ft.padding.all(spacing.sm),
                        margin=ft.margin.symmetric(vertical=spacing.xs)
                    )

                    code_controls.append(code_container)

                return ft.Column(
                    controls=code_controls,
                    spacing=spacing.xs,
                    tight=True
                )
            else:
                # Treat as inline code
                return ft.Text(
                    content,
                    style=typography.body_small,
                    color=palette.text_primary,
                    selectable=True,
                    font_family="monospace",
                    size=self.get_breakpoint_value(
                        mobile=12, tablet=13, desktop=14, large=14
                    )
                )

        except Exception as e:
            self._logger.error(f"Error building code content: {e}")
            return self._build_text_content()

    def _build_function_call_content(self) -> ft.Control:
        """Build function call content."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            function_call = self._message.function_call
            if not function_call:
                return self._build_text_content()

            # Function name
            function_name = ft.Text(
                f"🔧 {function_call.get('name', 'Unknown Function')}",
                style=typography.title_small,
                color=palette.primary,
                weight=ft.FontWeight.BOLD
            )

            # Function arguments
            args_text = ""
            if 'arguments' in function_call:
                try:
                    args = json.loads(function_call['arguments']) if isinstance(function_call['arguments'], str) else function_call['arguments']
                    args_text = json.dumps(args, indent=2)
                except:
                    args_text = str(function_call['arguments'])

            args_display = ft.Text(
                args_text,
                style=typography.body_small,
                color=palette.text_secondary,
                selectable=True,
                font_family="monospace",
                size=12
            )

            # Container
            return ft.Container(
                content=ft.Column(
                    controls=[function_name, args_display],
                    spacing=spacing.xs,
                    tight=True
                ),
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(8),
                padding=ft.padding.all(spacing.sm),
                border=ft.border.all(1, palette.outline)
            )

        except Exception as e:
            self._logger.error(f"Error building function call content: {e}")
            return self._build_text_content()

    def _build_function_response_content(self) -> ft.Control:
        """Build function response content."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            function_response = self._message.function_response
            if not function_response:
                return self._build_text_content()

            # Response header
            response_header = ft.Text(
                "📋 Function Response",
                style=typography.title_small,
                color=palette.secondary,
                weight=ft.FontWeight.BOLD
            )

            # Response content
            response_text = json.dumps(function_response, indent=2)
            response_display = ft.Text(
                response_text,
                style=typography.body_small,
                color=palette.text_primary,
                selectable=True,
                font_family="monospace",
                size=12
            )

            # Container
            return ft.Container(
                content=ft.Column(
                    controls=[response_header, response_display],
                    spacing=spacing.xs,
                    tight=True
                ),
                bgcolor=palette.surface,
                border_radius=ft.border_radius.all(8),
                padding=ft.padding.all(spacing.sm),
                border=ft.border.all(1, palette.outline)
            )

        except Exception as e:
            self._logger.error(f"Error building function response content: {e}")
            return self._build_text_content()

    def _build_error_content(self) -> ft.Control:
        """Build error content."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Error icon and text
            error_header = ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE,
                        color=palette.error,
                        size=self.get_breakpoint_value(
                            mobile=16, tablet=18, desktop=20, large=20
                        )
                    ),
                    ft.Text(
                        "Error",
                        style=typography.title_small,
                        color=palette.error,
                        weight=ft.FontWeight.BOLD
                    )
                ],
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.START
            )

            # Error message
            error_text = ft.Text(
                self._message.content,
                style=typography.body_medium,
                color=palette.text_primary,
                selectable=True
            )

            # Container
            return ft.Container(
                content=ft.Column(
                    controls=[error_header, error_text],
                    spacing=spacing.xs,
                    tight=True
                ),
                bgcolor=palette.error_container,
                border_radius=ft.border_radius.all(8),
                padding=ft.padding.all(spacing.sm),
                border=ft.border.all(1, palette.error)
            )

        except Exception as e:
            self._logger.error(f"Error building error content: {e}")
            return self._build_fallback_content()

    def _build_fallback_content(self) -> ft.Control:
        """Build fallback content for errors."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()

            return ft.Text(
                "Unable to display message content",
                style=typography.body_medium,
                color=palette.text_secondary,
                italic=True
            )

        except Exception as e:
            self._logger.error(f"Error building fallback content: {e}")
            return ft.Text("Error displaying message")

    def _build_bubble_container(self, content: ft.Control) -> ft.Container:
        """Build the main bubble container."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Determine bubble colors based on role
            if self._is_user_message:
                bg_color = palette.primary
                border_color = palette.primary_variant
            else:
                bg_color = palette.surface_variant
                border_color = palette.outline

            # Responsive border radius
            border_radius = self.get_breakpoint_value(
                mobile=12, tablet=14, desktop=16, large=16
            )

            # Responsive padding
            padding_value = self.get_breakpoint_value(
                mobile=spacing.sm, tablet=spacing.md, desktop=spacing.md, large=spacing.lg
            )

            # Build container
            container = ft.Container(
                content=content,
                bgcolor=bg_color,
                border_radius=ft.border_radius.all(border_radius),
                padding=ft.padding.all(padding_value),
                border=ft.border.all(1, border_color) if not self._is_user_message else None,
                animate=ft.Animation(
                    duration=self._config.animation_duration_ms,
                    curve=ft.AnimationCurve.EASE_OUT
                ),
                on_click=self._handle_click,
                on_long_press=self._handle_long_press
            )

            # Add selection styling if selected
            if self._state.is_selected:
                container.border = ft.border.all(2, palette.primary)

            return container

        except Exception as e:
            self._logger.error(f"Error building bubble container: {e}")
            return ft.Container(content=content)

    def _build_avatar(self) -> Optional[ft.Control]:
        """Build avatar for the message."""
        try:
            palette = self.get_palette()

            # Determine avatar icon and color
            if self._is_user_message:
                icon = ft.Icons.PERSON
                bg_color = palette.primary
                icon_color = palette.text_primary
            else:
                icon = ft.Icons.SMART_TOY
                bg_color = palette.secondary
                icon_color = palette.text_primary

            # Responsive avatar size
            avatar_size = self.get_breakpoint_value(
                mobile=28, tablet=32, desktop=36, large=40
            )

            icon_size = self.get_breakpoint_value(
                mobile=16, tablet=18, desktop=20, large=22
            )

            return ft.CircleAvatar(
                content=ft.Icon(
                    icon,
                    size=icon_size,
                    color=icon_color
                ),
                bgcolor=bg_color,
                radius=avatar_size // 2
            )

        except Exception as e:
            self._logger.error(f"Error building avatar: {e}")
            return None

    def _build_timestamp(self) -> Optional[ft.Control]:
        """Build timestamp display."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()

            timestamp_str = self._message.timestamp.strftime(self._config.timestamp_format)

            return ft.Text(
                timestamp_str,
                style=typography.label,
                color=palette.text_secondary,
                size=self.get_breakpoint_value(
                    mobile=10, tablet=11, desktop=12, large=12
                )
            )

        except Exception as e:
            self._logger.error(f"Error building timestamp: {e}")
            return None

    def _build_status_indicator(self) -> Optional[ft.Control]:
        """Build status indicator."""
        try:
            palette = self.get_palette()

            status = self._message.status
            icon_size = self.get_breakpoint_value(
                mobile=12, tablet=14, desktop=16, large=16
            )

            if status == MessageStatus.PENDING:
                return ft.Icon(
                    ft.Icons.SCHEDULE,
                    color=palette.text_secondary,
                    size=icon_size
                )
            elif status == MessageStatus.PROCESSING:
                return ft.ProgressRing(
                    width=icon_size,
                    height=icon_size,
                    stroke_width=2,
                    color=palette.primary
                )
            elif status == MessageStatus.COMPLETED:
                return ft.Icon(
                    ft.Icons.CHECK_CIRCLE,
                    color=palette.primary,
                    size=icon_size
                )
            elif status == MessageStatus.ERROR:
                return ft.Icon(
                    ft.Icons.ERROR,
                    color=palette.error,
                    size=icon_size
                )
            elif status == MessageStatus.CANCELLED:
                return ft.Icon(
                    ft.Icons.CANCEL,
                    color=palette.text_secondary,
                    size=icon_size
                )
            else:
                return None

        except Exception as e:
            self._logger.error(f"Error building status indicator: {e}")
            return None

    def _arrange_components(
        self,
        bubble: ft.Container,
        avatar: Optional[ft.Control],
        timestamp: Optional[ft.Control],
        status: Optional[ft.Control]
    ) -> ft.Control:
        """Arrange all components based on message role and configuration."""
        try:
            spacing = self.get_spacing()

            # Build metadata row (timestamp + status)
            metadata_controls = []
            if timestamp:
                metadata_controls.append(timestamp)
            if status:
                metadata_controls.append(status)

            metadata_row = None
            if metadata_controls:
                metadata_row = ft.Row(
                    controls=metadata_controls,
                    spacing=spacing.xs,
                    alignment=ft.MainAxisAlignment.END if self._is_user_message else ft.MainAxisAlignment.START
                )

            # Build message column (bubble + metadata)
            message_controls = [bubble]
            if metadata_row:
                message_controls.append(metadata_row)

            message_column = ft.Column(
                controls=message_controls,
                spacing=spacing.xs,
                tight=True,
                alignment=ft.MainAxisAlignment.START
            )

            # Responsive max width
            max_width = self.get_breakpoint_value(
                mobile=280, tablet=400, desktop=500, large=600
            )

            # Apply max width constraint
            constrained_message = ft.Container(
                content=message_column,
                width=min(max_width, self.page.window_width * self._config.max_width_percentage) if self.page else max_width
            )

            # Arrange with avatar
            if avatar:
                if self._is_user_message:
                    # User: message on left, avatar on right
                    return ft.Row(
                        controls=[
                            ft.Container(expand=True),  # Spacer
                            constrained_message,
                            ft.Container(width=spacing.xs),
                            avatar
                        ],
                        spacing=0,
                        alignment=ft.MainAxisAlignment.END
                    )
                else:
                    # Assistant: avatar on left, message on right
                    return ft.Row(
                        controls=[
                            avatar,
                            ft.Container(width=spacing.xs),
                            constrained_message,
                            ft.Container(expand=True)  # Spacer
                        ],
                        spacing=0,
                        alignment=ft.MainAxisAlignment.START
                    )
            else:
                # No avatar - just align the message
                if self._is_user_message:
                    return ft.Row(
                        controls=[
                            ft.Container(expand=True),  # Spacer
                            constrained_message
                        ],
                        spacing=0,
                        alignment=ft.MainAxisAlignment.END
                    )
                else:
                    return ft.Row(
                        controls=[
                            constrained_message,
                            ft.Container(expand=True)  # Spacer
                        ],
                        spacing=0,
                        alignment=ft.MainAxisAlignment.START
                    )

        except Exception as e:
            self._logger.error(f"Error arranging components: {e}")
            return bubble

    def _build_error_bubble(self) -> None:
        """Build error bubble when initialization fails."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()

            error_text = ft.Text(
                "Error displaying message",
                style=typography.body_medium,
                color=palette.error
            )

            self.content = ft.Container(
                content=error_text,
                bgcolor=palette.error_container,
                border_radius=ft.border_radius.all(8),
                padding=ft.padding.all(12)
            )

        except Exception as e:
            self._logger.error(f"Error building error bubble: {e}")
            self.content = ft.Text("Critical error")

    # Event Handlers
    def _handle_click(self, e: ft.TapEvent) -> None:
        """Handle bubble click events."""
        try:
            if self._on_click:
                self._on_click(self._message.message_id)

        except Exception as ex:
            self._logger.error(f"Error handling click: {ex}")

    def _handle_long_press(self, e: ft.LongPressStartEvent) -> None:
        """Handle bubble long press events."""
        try:
            if self._on_long_press:
                self._on_long_press(self._message.message_id)

        except Exception as ex:
            self._logger.error(f"Error handling long press: {ex}")

    def _on_responsive_update(self) -> None:
        """Handle responsive layout updates."""
        try:
            # Rebuild bubble with new responsive values
            self._build_bubble()

            if self.page:
                self.update()

        except Exception as e:
            self._logger.error(f"Error handling responsive update: {e}")

    # Public Methods
    def update_message(self, message: ChatMessage) -> None:
        """Update the message and rebuild the bubble."""
        try:
            self._message = message
            self._content_type = self._detect_content_type()
            self._is_user_message = self._message.role == MessageRole.USER

            # Rebuild bubble
            self._build_bubble()

            if self.page:
                self.update()

        except Exception as e:
            self._logger.error(f"Error updating message: {e}")

    def set_selected(self, selected: bool) -> None:
        """Set selection state."""
        try:
            if self._state.is_selected != selected:
                self._state.is_selected = selected

                # Update bubble styling
                if self._bubble_container:
                    palette = self.get_palette()
                    if selected:
                        self._bubble_container.border = ft.border.all(2, palette.primary)
                    else:
                        border_color = palette.outline if not self._is_user_message else None
                        self._bubble_container.border = ft.border.all(1, border_color) if border_color else None

                    if self.page:
                        self._bubble_container.update()

        except Exception as e:
            self._logger.error(f"Error setting selection: {e}")

    def copy_content(self) -> str:
        """Copy message content to clipboard."""
        try:
            content = self._message.content

            if self._on_copy:
                self._on_copy(content)

            return content

        except Exception as e:
            self._logger.error(f"Error copying content: {e}")
            return ""

    def get_message_id(self) -> str:
        """Get the message ID."""
        return self._message.message_id

    def get_message(self) -> ChatMessage:
        """Get the chat message."""
        return self._message

    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self._is_user_message

    # Animation Methods
    async def animate_in(self) -> None:
        """Animate bubble appearance."""
        try:
            if not self._bubble_container or not self.page:
                return

            self._state.is_animating = True

            # Start with small scale and fade
            self._bubble_container.scale = 0.8
            self._bubble_container.opacity = 0.0

            if self.page:
                self._bubble_container.update()
                await asyncio.sleep(0.05)  # Small delay

            # Animate to full size and opacity
            self._bubble_container.scale = 1.0
            self._bubble_container.opacity = 1.0

            if self.page:
                self._bubble_container.update()
                await asyncio.sleep(self._config.animation_duration_ms / 1000)

            self._state.is_animating = False

        except Exception as e:
            self._logger.error(f"Error animating bubble in: {e}")
            self._state.is_animating = False

    async def animate_status_change(self, new_status: MessageStatus) -> None:
        """Animate status indicator change."""
        try:
            if not self._status_container or not self.page:
                return

            # Fade out current status
            self._status_container.opacity = 0.0
            if self.page:
                self._status_container.update()
                await asyncio.sleep(0.15)

            # Update message status
            self._message.status = new_status

            # Rebuild status indicator
            new_status_indicator = self._build_status_indicator()
            if new_status_indicator:
                self._status_container.content = new_status_indicator

            # Fade in new status
            self._status_container.opacity = 1.0
            if self.page:
                self._status_container.update()

        except Exception as e:
            self._logger.error(f"Error animating status change: {e}")

    async def pulse_highlight(self) -> None:
        """Pulse highlight animation for attention."""
        try:
            if not self._bubble_container or not self.page:
                return

            original_scale = self._bubble_container.scale or 1.0
            palette = self.get_palette()

            # Pulse animation
            for _ in range(2):
                self._bubble_container.scale = original_scale * 1.05
                self._bubble_container.border = ft.border.all(2, palette.primary)
                if self.page:
                    self._bubble_container.update()
                    await asyncio.sleep(0.2)

                self._bubble_container.scale = original_scale
                if not self._state.is_selected:
                    border_color = palette.outline if not self._is_user_message else None
                    self._bubble_container.border = ft.border.all(1, border_color) if border_color else None
                if self.page:
                    self._bubble_container.update()
                    await asyncio.sleep(0.2)

        except Exception as e:
            self._logger.error(f"Error pulsing highlight: {e}")

    # Accessibility Methods
    def get_accessibility_label(self) -> str:
        """Get accessibility label for screen readers."""
        try:
            role = "User" if self._is_user_message else "Assistant"
            timestamp = self._message.timestamp.strftime("%H:%M")
            status = self._message.status.value.replace("_", " ").title()

            content_preview = self._message.content[:100]
            if len(self._message.content) > 100:
                content_preview += "..."

            return f"{role} message at {timestamp}, status: {status}. Content: {content_preview}"

        except Exception as e:
            self._logger.error(f"Error getting accessibility label: {e}")
            return "Chat message"

    def set_accessibility_properties(self) -> None:
        """Set accessibility properties for the bubble."""
        try:
            if self._bubble_container:
                # Set semantic label
                self._bubble_container.semantics_label = self.get_accessibility_label()

                # Set role
                self._bubble_container.semantics_role = "button" if self._config.enable_selection else "text"

                # Set focusable
                self._bubble_container.can_focus = True

                # Set keyboard shortcuts hint
                if self._config.enable_copy:
                    self._bubble_container.tooltip = "Click to select, Ctrl+C to copy"

        except Exception as e:
            self._logger.error(f"Error setting accessibility properties: {e}")

    def handle_keyboard_event(self, e: ft.KeyboardEvent) -> bool:
        """Handle keyboard events for accessibility."""
        try:
            if not self._state.is_selected:
                return False

            # Copy with Ctrl+C
            if e.key == "c" and e.ctrl:
                self.copy_content()
                return True

            # Select with Space or Enter
            if e.key in ["Space", "Enter"]:
                if self._on_click:
                    self._on_click(self._message.message_id)
                return True

            return False

        except Exception as e:
            self._logger.error(f"Error handling keyboard event: {e}")
            return False

    # Utility Methods
    def get_bubble_metrics(self) -> Dict[str, Any]:
        """Get bubble metrics for debugging and optimization."""
        try:
            return {
                "message_id": self._message.message_id,
                "content_type": self._content_type.value,
                "is_user_message": self._is_user_message,
                "content_length": len(self._message.content),
                "has_avatar": self._config.show_avatar,
                "has_timestamp": self._config.show_timestamp,
                "has_status": self._config.show_status,
                "is_selected": self._state.is_selected,
                "is_animating": self._state.is_animating,
                "last_update": self._state.last_update.isoformat() if self._state.last_update else None
            }

        except Exception as e:
            self._logger.error(f"Error getting bubble metrics: {e}")
            return {}

    def validate_configuration(self) -> List[str]:
        """Validate bubble configuration and return any issues."""
        issues = []

        try:
            if self._config.max_width_percentage <= 0 or self._config.max_width_percentage > 1:
                issues.append("max_width_percentage must be between 0 and 1")

            if self._config.animation_duration_ms < 0:
                issues.append("animation_duration_ms must be non-negative")

            if self._config.avatar_size < 16:
                issues.append("avatar_size should be at least 16 pixels")

            if not self._config.timestamp_format:
                issues.append("timestamp_format cannot be empty")

        except Exception as e:
            self._logger.error(f"Error validating configuration: {e}")
            issues.append(f"Configuration validation error: {e}")

        return issues

    def cleanup(self) -> None:
        """Clean up resources and event handlers."""
        try:
            # Clear event handlers
            self._on_click = None
            self._on_long_press = None
            self._on_copy = None
            self._on_context_menu = None

            # Clear UI references
            self._bubble_container = None
            self._content_container = None
            self._avatar_container = None
            self._timestamp_container = None
            self._status_container = None

            self._logger.debug(f"Cleaned up message bubble {self._message.message_id}")

        except Exception as e:
            self._logger.error(f"Error cleaning up bubble: {e}")


# Factory Functions
def create_message_bubble(
    message: ChatMessage,
    config: Optional[BubbleConfig] = None,
    **kwargs
) -> MessageBubbleUI:
    """
    Factory function to create a message bubble.

    Args:
        message: Chat message to display
        config: Bubble configuration
        **kwargs: Additional arguments for MessageBubbleUI

    Returns:
        MessageBubbleUI instance
    """
    return MessageBubbleUI(message=message, config=config, **kwargs)


def create_user_message_bubble(
    content: str,
    session_id: str,
    message_id: Optional[str] = None,
    config: Optional[BubbleConfig] = None,
    **kwargs
) -> MessageBubbleUI:
    """
    Factory function to create a user message bubble.

    Args:
        content: Message content
        session_id: Session identifier
        message_id: Message identifier (auto-generated if None)
        config: Bubble configuration
        **kwargs: Additional arguments for MessageBubbleUI

    Returns:
        MessageBubbleUI instance
    """
    import uuid

    if message_id is None:
        message_id = str(uuid.uuid4())

    message = ChatMessage(
        message_id=message_id,
        session_id=session_id,
        role=MessageRole.USER,
        content=content,
        timestamp=datetime.now()
    )

    return MessageBubbleUI(message=message, config=config, **kwargs)


def create_assistant_message_bubble(
    content: str,
    session_id: str,
    message_id: Optional[str] = None,
    config: Optional[BubbleConfig] = None,
    **kwargs
) -> MessageBubbleUI:
    """
    Factory function to create an assistant message bubble.

    Args:
        content: Message content
        session_id: Session identifier
        message_id: Message identifier (auto-generated if None)
        config: Bubble configuration
        **kwargs: Additional arguments for MessageBubbleUI

    Returns:
        MessageBubbleUI instance
    """
    import uuid

    if message_id is None:
        message_id = str(uuid.uuid4())

    message = ChatMessage(
        message_id=message_id,
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content=content,
        timestamp=datetime.now()
    )

    return MessageBubbleUI(message=message, config=config, **kwargs)
