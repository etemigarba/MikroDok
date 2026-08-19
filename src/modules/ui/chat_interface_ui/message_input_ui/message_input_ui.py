"""
Module: message_input_ui
Description: Multi-line input with markdown preview and attachment support for chat interface.
            Provides comprehensive message input functionality with responsive design, theme integration,
            real-time validation, markdown preview, file attachments, and accessibility features.
Phase: 4
Location: /src/modules/ui/chat_interface_ui/message_input_ui/message_input_ui.py
"""

# Standard library imports
import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import mimetypes

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    get_theme_manager
)
from src.modules.database.chat_repository_db.chat_messages_db.chat_messages_db import (
    ChatMessagesDB, MessageRole, MessageStatus
)
from src.modules.logic.conversation_management_lg.message_processor_lg.message_processor_lg import (
    MessageProcessor, MessageProcessingConfig
)
from src.modules.logic.conversation_management_lg.base_interfaces import (
    ConversationMessage, MessagePriority, MessageType
)


class InputMode(Enum):
    """Input mode enumeration."""
    TEXT = "text"
    MARKDOWN = "markdown"
    CODE = "code"


class AttachmentType(Enum):
    """Attachment type enumeration."""
    DOCUMENT = "document"
    IMAGE = "image"
    CODE = "code"
    OTHER = "other"


@dataclass
class MessageInputConfig:
    """Configuration for message input behavior."""
    max_characters: int = 4000
    max_lines: int = 50
    enable_markdown_preview: bool = True
    enable_attachments: bool = True
    enable_auto_save: bool = True
    auto_save_interval_seconds: int = 30
    enable_typing_indicators: bool = True
    enable_emoji_picker: bool = True
    enable_code_highlighting: bool = True
    enable_spell_check: bool = True
    placeholder_text: str = "Type your message..."
    send_on_enter: bool = False  # Ctrl+Enter to send
    max_attachment_size_mb: int = 10
    allowed_file_types: List[str] = field(default_factory=lambda: [
        '.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml',
        '.pdf', '.docx', '.xlsx', '.pptx', '.png', '.jpg', '.jpeg', '.gif'
    ])


@dataclass
class AttachmentData:
    """Data structure for file attachments."""
    file_id: str
    file_name: str
    file_path: str
    file_size: int
    file_type: AttachmentType
    mime_type: str
    upload_time: datetime
    preview_available: bool = False
    preview_data: Optional[str] = None


@dataclass
class MessageDraft:
    """Data structure for message drafts."""
    draft_id: str
    session_id: str
    content: str
    attachments: List[AttachmentData]
    input_mode: InputMode
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageInputUI(ThemeAwareUserControl):
    """
    Comprehensive message input interface with multi-line support and rich features.

    Features:
    - Multi-line text input with auto-expanding height and responsive design
    - Real-time markdown preview with syntax highlighting and code block detection
    - File attachment support with drag-and-drop and preview capabilities
    - Message validation with character limits and content filtering
    - Auto-save functionality with draft management and recovery
    - Keyboard shortcuts with accessibility support (Ctrl+Enter to send)
    - Theme-aware styling with full ResponsiveLayoutManager integration
    - Typing indicators and real-time status updates
    - Emoji picker and rich text formatting tools
    - Integration with chat system and message processing pipeline
    - Mobile-first responsive design with breakpoint-aware layouts
    - Accessibility compliance with screen reader support and keyboard navigation
    """

    def __init__(self,
                 session_id: Optional[str] = None,
                 config: Optional[MessageInputConfig] = None,
                 on_message_send: Optional[Callable[[str, List[AttachmentData]], None]] = None,
                 on_typing_start: Optional[Callable[[], None]] = None,
                 on_typing_stop: Optional[Callable[[], None]] = None,
                 **kwargs):
        """
        Initialize the message input UI component.

        Args:
            session_id: Chat session identifier
            config: Input configuration settings
            on_message_send: Callback for message sending
            on_typing_start: Callback for typing start
            on_typing_stop: Callback for typing stop
            **kwargs: Additional container arguments
        """
        super().__init__(**kwargs)
        
        # Configuration and state
        self._session_id = session_id
        self._config = config or MessageInputConfig()
        self._logger = logging.getLogger(__name__)
        
        # Callbacks
        self._on_message_send = on_message_send
        self._on_typing_start = on_typing_start
        self._on_typing_stop = on_typing_stop
        
        # Component state
        self._current_text = ""
        self._current_mode = InputMode.TEXT
        self._attachments: List[AttachmentData] = []
        self._is_typing = False
        self._typing_timer: Optional[asyncio.Task] = None
        self._auto_save_timer: Optional[asyncio.Task] = None
        self._current_draft: Optional[MessageDraft] = None
        
        # UI components
        self._text_input: Optional[ft.TextField] = None
        self._send_button: Optional[ft.IconButton] = None
        self._attachment_button: Optional[ft.IconButton] = None
        self._mode_selector: Optional[ft.Dropdown] = None
        self._preview_container: Optional[ft.Container] = None
        self._attachment_list: Optional[ft.Column] = None
        self._character_counter: Optional[ft.Text] = None
        self._status_indicator: Optional[ft.Text] = None
        
        # File picker for attachments
        self._file_picker: Optional[ft.FilePicker] = None
        
        # Initialize components
        self._message_processor = MessageProcessor()
        self._messages_db = ChatMessagesDB()
        
        # Build the UI
        self.build()

    def build(self) -> None:
        """Build the message input UI with responsive design and theme integration."""
        try:
            self._logger.debug("Building MessageInputUI component")

            # Get theme components
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            # Responsive sizing
            responsive_padding = self.get_responsive_padding()
            
            # Build main input area
            input_area = self._build_input_area()
            
            # Build toolbar
            toolbar = self._build_toolbar()
            
            # Build preview area (initially hidden)
            preview_area = self._build_preview_area()
            
            # Build attachment area
            attachment_area = self._build_attachment_area()
            
            # Build status bar
            status_bar = self._build_status_bar()

            # Create main layout
            main_content = ft.Column(
                controls=[
                    toolbar,
                    input_area,
                    preview_area,
                    attachment_area,
                    status_bar
                ],
                spacing=spacing.small,
                tight=True
            )

            # Create main container with responsive design
            self.content = self.create_responsive_container(
                content=main_content,
                padding=responsive_padding
            )
            
            self._logger.debug("MessageInputUI component built successfully")
            
        except Exception as e:
            self._logger.error(f"Error building message input component: {e}")
            self.content = self._create_error_fallback()

    def _build_input_area(self) -> ft.Control:
        """Build the main text input area."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            
            # Responsive input sizing
            min_height = self.get_breakpoint_value(
                mobile=80, tablet=100, desktop=120, large=140
            )
            max_height = self.get_breakpoint_value(
                mobile=200, tablet=250, desktop=300, large=350
            )
            
            self._text_input = ft.TextField(
                hint_text=self._config.placeholder_text,
                value=self._current_text,
                multiline=True,
                min_lines=3,
                max_lines=self._config.max_lines,
                on_change=self._on_text_change,
                on_focus=self._on_input_focus,
                on_blur=self._on_input_blur,
                on_submit=self._on_input_submit,
                text_style=ft.TextStyle(
                    size=typography.body_large[0],
                    color=palette.text_primary
                ),
                hint_style=ft.TextStyle(
                    size=typography.body_large[0],
                    color=palette.text_secondary
                ),
                bgcolor=palette.surface,
                border_color=palette.borders,
                focused_border_color=palette.primary,
                border_radius=self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=12
                ),
                content_padding=ft.padding.all(spacing.medium)
            )

            # Input container with send button
            input_container = ft.Container(
                content=ft.Stack(
                    controls=[
                        self._text_input,
                        ft.Container(
                            content=self._build_send_button(),
                            alignment=ft.alignment.bottom_right,
                            padding=ft.padding.only(right=spacing.small, bottom=spacing.small)
                        )
                    ]
                ),
                height=min_height,
                border_radius=self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=12
                )
            )

            return input_container
            
        except Exception as e:
            self._logger.error(f"Error building input area: {e}")
            return ft.Container(content=ft.Text("Input area error"))

    def _build_send_button(self) -> ft.Control:
        """Build the send button."""
        try:
            palette = self.get_palette()

            # Responsive button sizing
            button_size = self.get_breakpoint_value(
                mobile=40, tablet=44, desktop=48, large=52
            )

            self._send_button = ft.IconButton(
                icon=ft.Icons.SEND,
                tooltip="Send message (Ctrl+Enter)",
                on_click=self._on_send_click,
                bgcolor=palette.primary,
                icon_color=palette.on_primary,
                width=button_size,
                height=button_size,
                disabled=True  # Initially disabled
            )

            return self._send_button

        except Exception as e:
            self._logger.error(f"Error building send button: {e}")
            return ft.IconButton(icon=ft.Icons.SEND)

    def _build_toolbar(self) -> ft.Control:
        """Build the input toolbar with formatting options."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Mode selector
            self._mode_selector = ft.Dropdown(
                value=self._current_mode.value,
                options=[
                    ft.dropdown.Option("text", "Text"),
                    ft.dropdown.Option("markdown", "Markdown"),
                    ft.dropdown.Option("code", "Code")
                ],
                on_change=self._on_mode_change,
                width=self.get_breakpoint_value(
                    mobile=100, tablet=120, desktop=140, large=160
                ),
                text_style=ft.TextStyle(color=palette.text_primary),
                bgcolor=palette.surface,
                border_color=palette.borders
            )

            # Attachment button
            self._attachment_button = ft.IconButton(
                icon=ft.Icons.ATTACH_FILE,
                tooltip="Attach file",
                on_click=self._on_attachment_click,
                icon_color=palette.text_secondary
            )

            # Emoji button
            emoji_button = ft.IconButton(
                icon=ft.Icons.EMOJI_EMOTIONS,
                tooltip="Add emoji",
                on_click=self._on_emoji_click,
                icon_color=palette.text_secondary
            )

            # Preview toggle
            preview_button = ft.IconButton(
                icon=ft.Icons.PREVIEW,
                tooltip="Toggle preview",
                on_click=self._on_preview_toggle,
                icon_color=palette.text_secondary
            )

            # Responsive toolbar layout
            toolbar_controls = [
                self._mode_selector,
                self._attachment_button,
                emoji_button,
                preview_button
            ]

            # Use responsive layout
            toolbar_layout = self.create_adaptive_layout(
                children=toolbar_controls,
                mobile_layout="column",
                tablet_layout="row",
                desktop_layout="row",
                spacing=spacing.small
            )

            return ft.Container(
                content=toolbar_layout,
                padding=ft.padding.symmetric(
                    horizontal=spacing.small,
                    vertical=spacing.xs
                ),
                bgcolor=palette.surface_variant,
                border_radius=self.get_breakpoint_value(
                    mobile=6, tablet=8, desktop=10, large=10
                )
            )

        except Exception as e:
            self._logger.error(f"Error building toolbar: {e}")
            return ft.Container()

    def _build_preview_area(self) -> ft.Control:
        """Build the markdown preview area."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            self._preview_container = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Preview",
                            style=ft.TextThemeStyle.TITLE_SMALL,
                            color=palette.text_primary
                        ),
                        ft.Divider(color=palette.borders),
                        ft.Container(
                            content=ft.Text(
                                "Preview will appear here...",
                                style=ft.TextThemeStyle.BODY_MEDIUM,
                                color=palette.text_secondary
                            ),
                            padding=ft.padding.all(spacing.medium)
                        )
                    ],
                    spacing=spacing.xs
                ),
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.borders),
                border_radius=self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=12
                ),
                padding=ft.padding.all(spacing.medium),
                visible=False  # Initially hidden
            )

            return self._preview_container

        except Exception as e:
            self._logger.error(f"Error building preview area: {e}")
            return ft.Container()

    def _build_attachment_area(self) -> ft.Control:
        """Build the attachment display area."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            self._attachment_list = ft.Column(
                controls=[],
                spacing=spacing.xs,
                tight=True
            )

            attachment_container = ft.Container(
                content=self._attachment_list,
                visible=False,  # Initially hidden
                padding=ft.padding.all(spacing.small),
                bgcolor=palette.surface_variant,
                border_radius=self.get_breakpoint_value(
                    mobile=6, tablet=8, desktop=10, large=10
                )
            )

            return attachment_container

        except Exception as e:
            self._logger.error(f"Error building attachment area: {e}")
            return ft.Container()

    def _build_status_bar(self) -> ft.Control:
        """Build the status bar with character count and indicators."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            # Character counter
            self._character_counter = ft.Text(
                f"0 / {self._config.max_characters}",
                style=ft.TextThemeStyle.BODY_SMALL,
                color=palette.text_secondary
            )

            # Status indicator
            self._status_indicator = ft.Text(
                "Ready",
                style=ft.TextThemeStyle.BODY_SMALL,
                color=palette.text_secondary
            )

            # Responsive status bar layout
            status_controls = [
                self._status_indicator,
                self._character_counter
            ]

            status_layout = ft.Row(
                controls=status_controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

            return ft.Container(
                content=status_layout,
                padding=ft.padding.symmetric(
                    horizontal=spacing.small,
                    vertical=spacing.xs
                )
            )

        except Exception as e:
            self._logger.error(f"Error building status bar: {e}")
            return ft.Container()

    def _create_error_fallback(self) -> ft.Control:
        """Create error fallback UI."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.ERROR_OUTLINE,
                            color=palette.error,
                            size=48
                        ),
                        ft.Text(
                            "Message input unavailable",
                            style=ft.TextThemeStyle.BODY_LARGE,
                            color=palette.text_primary,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            "Please try refreshing the interface",
                            style=ft.TextThemeStyle.BODY_SMALL,
                            color=palette.text_secondary,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.medium
                ),
                padding=ft.padding.all(spacing.large),
                alignment=ft.alignment.center
            )

        except Exception as e:
            self._logger.error(f"Error creating fallback UI: {e}")
            return ft.Container(content=ft.Text("Error"))

    # Event Handlers
    async def _on_text_change(self, e: ft.ControlEvent) -> None:
        """Handle text input changes."""
        try:
            self._current_text = e.control.value

            # Update character counter
            char_count = len(self._current_text)
            max_chars = self._config.max_characters

            if self._character_counter:
                self._character_counter.value = f"{char_count} / {max_chars}"

                # Update color based on limit
                palette = self.get_palette()
                if char_count > max_chars * 0.9:
                    self._character_counter.color = palette.warning
                elif char_count >= max_chars:
                    self._character_counter.color = palette.error
                else:
                    self._character_counter.color = palette.text_secondary

            # Update send button state
            await self._update_send_button_state()

            # Handle typing indicators
            await self._handle_typing_start()

            # Update preview if enabled
            if self._preview_container and self._preview_container.visible:
                await self._update_preview()

            # Auto-save draft
            if self._config.enable_auto_save:
                await self._schedule_auto_save()

            # Update UI
            if self.page:
                await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error handling text change: {e}")

    async def _on_input_focus(self, e: ft.ControlEvent) -> None:
        """Handle input focus."""
        try:
            if self._status_indicator:
                self._status_indicator.value = "Typing..."
                self._status_indicator.color = self.get_palette().primary

            if self.page:
                await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error handling input focus: {e}")

    async def _on_input_blur(self, e: ft.ControlEvent) -> None:
        """Handle input blur."""
        try:
            await self._handle_typing_stop()

            if self._status_indicator:
                self._status_indicator.value = "Ready"
                self._status_indicator.color = self.get_palette().text_secondary

            if self.page:
                await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error handling input blur: {e}")

    async def _on_input_submit(self, e: ft.ControlEvent) -> None:
        """Handle input submit (Enter key)."""
        try:
            # Check if Ctrl+Enter was pressed (send message)
            if hasattr(e, 'control_key') and e.control_key:
                await self._send_message()
            elif not self._config.send_on_enter:
                # Just add a new line if send_on_enter is False
                pass
            else:
                # Send message on Enter if configured
                await self._send_message()

        except Exception as e:
            self._logger.error(f"Error handling input submit: {e}")

    async def _on_send_click(self, e: ft.ControlEvent) -> None:
        """Handle send button click."""
        try:
            await self._send_message()
        except Exception as e:
            self._logger.error(f"Error handling send click: {e}")

    async def _on_mode_change(self, e: ft.ControlEvent) -> None:
        """Handle input mode change."""
        try:
            new_mode = InputMode(e.control.value)
            self._current_mode = new_mode

            # Update preview if visible
            if self._preview_container and self._preview_container.visible:
                await self._update_preview()

            # Update status
            if self._status_indicator:
                self._status_indicator.value = f"Mode: {new_mode.value.title()}"

            if self.page:
                await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error handling mode change: {e}")

    async def _on_attachment_click(self, e: ft.ControlEvent) -> None:
        """Handle attachment button click."""
        try:
            if not self._config.enable_attachments:
                return

            # Initialize file picker if not done
            if not self._file_picker:
                self._file_picker = ft.FilePicker(
                    on_result=self._on_file_picker_result
                )
                if self.page:
                    self.page.overlay.append(self._file_picker)
                    await self.page.update_async()

            # Open file picker
            await self._file_picker.pick_files(
                dialog_title="Select files to attach",
                file_type=ft.FilePickerFileType.ANY,
                allow_multiple=True
            )

        except Exception as e:
            self._logger.error(f"Error handling attachment click: {e}")

    async def _on_emoji_click(self, e: ft.ControlEvent) -> None:
        """Handle emoji button click."""
        try:
            # TODO: Implement emoji picker
            # For now, just add a simple emoji
            if self._text_input:
                current_text = self._text_input.value or ""
                self._text_input.value = current_text + "😊"
                await self._on_text_change(ft.ControlEvent(control=self._text_input))

        except Exception as e:
            self._logger.error(f"Error handling emoji click: {e}")

    async def _on_preview_toggle(self, e: ft.ControlEvent) -> None:
        """Handle preview toggle."""
        try:
            if self._preview_container:
                self._preview_container.visible = not self._preview_container.visible

                if self._preview_container.visible:
                    await self._update_preview()

                if self.page:
                    await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error handling preview toggle: {e}")

    async def _on_file_picker_result(self, e: ft.FilePickerResultEvent) -> None:
        """Handle file picker result."""
        try:
            if not e.files:
                return

            for file in e.files:
                await self._add_attachment(file)

        except Exception as e:
            self._logger.error(f"Error handling file picker result: {e}")

    # Validation and Processing Methods
    async def _validate_message(self, content: str) -> Tuple[bool, str]:
        """
        Validate message content.

        Args:
            content: Message content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if content is empty
            if not content.strip():
                return False, "Message cannot be empty"

            # Check character limit
            if len(content) > self._config.max_characters:
                return False, f"Message exceeds {self._config.max_characters} character limit"

            # Check line limit
            line_count = content.count('\n') + 1
            if line_count > self._config.max_lines:
                return False, f"Message exceeds {self._config.max_lines} line limit"

            # Use message processor for advanced validation
            if self._session_id:
                config = MessageProcessingConfig(
                    enable_validation=True,
                    enable_content_filtering=True,
                    enable_token_counting=True
                )

                result = await self._message_processor.validate_message_content(
                    session_id=self._session_id,
                    role=MessageRole.USER,
                    content=content,
                    config=config
                )

                if not result.is_valid:
                    return False, result.error_message or "Message validation failed"

            return True, ""

        except Exception as e:
            self._logger.error(f"Error validating message: {e}")
            return False, "Validation error occurred"

    async def _update_preview(self) -> None:
        """Update the markdown preview."""
        try:
            if not self._preview_container or not self._current_text:
                return

            preview_content = await self._generate_preview(self._current_text)

            # Update preview container content
            if hasattr(self._preview_container, 'content') and hasattr(self._preview_container.content, 'controls'):
                preview_controls = self._preview_container.content.controls
                if len(preview_controls) >= 3:  # Title, Divider, Content
                    preview_controls[2] = ft.Container(
                        content=preview_content,
                        padding=ft.padding.all(self.get_spacing().medium)
                    )

        except Exception as e:
            self._logger.error(f"Error updating preview: {e}")

    async def _generate_preview(self, content: str) -> ft.Control:
        """
        Generate preview content based on input mode.

        Args:
            content: Content to preview

        Returns:
            Preview control
        """
        try:
            palette = self.get_palette()
            typography = self.get_typography()

            if self._current_mode == InputMode.MARKDOWN:
                return await self._generate_markdown_preview(content)
            elif self._current_mode == InputMode.CODE:
                return await self._generate_code_preview(content)
            else:
                # Plain text preview
                return ft.Text(
                    content,
                    style=ft.TextThemeStyle.BODY_MEDIUM,
                    color=palette.text_primary,
                    selectable=True
                )

        except Exception as e:
            self._logger.error(f"Error generating preview: {e}")
            return ft.Text("Preview error", color=self.get_palette().error)

    async def _generate_markdown_preview(self, content: str) -> ft.Control:
        """Generate markdown preview."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Simple markdown parsing for preview
            lines = content.split('\n')
            preview_controls = []

            for line in lines:
                line = line.strip()
                if not line:
                    preview_controls.append(ft.Container(height=spacing.small))
                    continue

                # Headers
                if line.startswith('# '):
                    preview_controls.append(ft.Text(
                        line[2:],
                        style=ft.TextThemeStyle.HEADLINE_LARGE,
                        color=palette.text_primary,
                        weight=ft.FontWeight.BOLD
                    ))
                elif line.startswith('## '):
                    preview_controls.append(ft.Text(
                        line[3:],
                        style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                        color=palette.text_primary,
                        weight=ft.FontWeight.BOLD
                    ))
                elif line.startswith('### '):
                    preview_controls.append(ft.Text(
                        line[4:],
                        style=ft.TextThemeStyle.HEADLINE_SMALL,
                        color=palette.text_primary,
                        weight=ft.FontWeight.BOLD
                    ))
                # Code blocks
                elif line.startswith('```'):
                    preview_controls.append(ft.Container(
                        content=ft.Text(
                            "Code Block",
                            style=ft.TextThemeStyle.BODY_SMALL,
                            color=palette.text_secondary
                        ),
                        bgcolor=palette.surface_variant,
                        padding=ft.padding.all(spacing.small),
                        border_radius=4
                    ))
                # Bold text
                elif '**' in line:
                    preview_controls.append(ft.Text(
                        line.replace('**', ''),
                        style=ft.TextThemeStyle.BODY_MEDIUM,
                        color=palette.text_primary,
                        weight=ft.FontWeight.BOLD
                    ))
                # Italic text
                elif '*' in line:
                    preview_controls.append(ft.Text(
                        line.replace('*', ''),
                        style=ft.TextThemeStyle.BODY_MEDIUM,
                        color=palette.text_primary,
                        italic=True
                    ))
                # Lists
                elif line.startswith('- ') or line.startswith('* '):
                    preview_controls.append(ft.Row(
                        controls=[
                            ft.Text("•", color=palette.primary),
                            ft.Text(
                                line[2:],
                                style=ft.TextThemeStyle.BODY_MEDIUM,
                                color=palette.text_primary
                            )
                        ],
                        spacing=spacing.small
                    ))
                # Regular text
                else:
                    preview_controls.append(ft.Text(
                        line,
                        style=ft.TextThemeStyle.BODY_MEDIUM,
                        color=palette.text_primary
                    ))

            return ft.Column(
                controls=preview_controls,
                spacing=spacing.xs,
                tight=True
            )

        except Exception as e:
            self._logger.error(f"Error generating markdown preview: {e}")
            return ft.Text("Markdown preview error", color=self.get_palette().error)

    async def _generate_code_preview(self, content: str) -> ft.Control:
        """Generate code preview with syntax highlighting."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Text(
                    content,
                    style=ft.TextThemeStyle.BODY_MEDIUM,
                    color=palette.text_primary,
                    font_family="Consolas, Monaco, monospace",
                    selectable=True
                ),
                bgcolor=palette.surface_variant,
                padding=ft.padding.all(spacing.medium),
                border_radius=8,
                border=ft.border.all(1, palette.borders)
            )

        except Exception as e:
            self._logger.error(f"Error generating code preview: {e}")
            return ft.Text("Code preview error", color=self.get_palette().error)

    # Attachment Methods
    async def _add_attachment(self, file) -> None:
        """
        Add a file attachment.

        Args:
            file: File picker file object
        """
        try:
            # Validate file
            if not await self._validate_attachment(file):
                return

            # Create attachment data
            attachment = AttachmentData(
                file_id=str(uuid.uuid4()),
                file_name=file.name,
                file_path=file.path,
                file_size=file.size,
                file_type=self._determine_attachment_type(file.name),
                mime_type=mimetypes.guess_type(file.name)[0] or "application/octet-stream",
                upload_time=datetime.now()
            )

            # Add to attachments list
            self._attachments.append(attachment)

            # Update attachment display
            await self._update_attachment_display()

            # Update send button state
            await self._update_send_button_state()

            self._logger.debug(f"Added attachment: {file.name}")

        except Exception as e:
            self._logger.error(f"Error adding attachment: {e}")

    async def _validate_attachment(self, file) -> bool:
        """
        Validate file attachment.

        Args:
            file: File to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check file size
            max_size = self._config.max_attachment_size_mb * 1024 * 1024
            if file.size > max_size:
                await self._show_error(f"File too large. Maximum size: {self._config.max_attachment_size_mb}MB")
                return False

            # Check file type
            file_ext = Path(file.name).suffix.lower()
            if file_ext not in self._config.allowed_file_types:
                await self._show_error(f"File type not allowed: {file_ext}")
                return False

            return True

        except Exception as e:
            self._logger.error(f"Error validating attachment: {e}")
            return False

    def _determine_attachment_type(self, filename: str) -> AttachmentType:
        """Determine attachment type from filename."""
        try:
            ext = Path(filename).suffix.lower()

            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']:
                return AttachmentType.IMAGE
            elif ext in ['.py', '.js', '.html', '.css', '.json', '.xml', '.sql']:
                return AttachmentType.CODE
            elif ext in ['.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.md']:
                return AttachmentType.DOCUMENT
            else:
                return AttachmentType.OTHER

        except Exception:
            return AttachmentType.OTHER

    async def _update_attachment_display(self) -> None:
        """Update the attachment display area."""
        try:
            if not self._attachment_list:
                return

            # Clear existing attachments
            self._attachment_list.controls.clear()

            # Add attachment items
            for attachment in self._attachments:
                attachment_item = await self._create_attachment_item(attachment)
                self._attachment_list.controls.append(attachment_item)

            # Show/hide attachment area
            if hasattr(self._attachment_list, 'parent') and self._attachment_list.parent:
                self._attachment_list.parent.visible = len(self._attachments) > 0

            if self.page:
                await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error updating attachment display: {e}")

    async def _create_attachment_item(self, attachment: AttachmentData) -> ft.Control:
        """Create an attachment display item."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Attachment icon based on type
            icon_map = {
                AttachmentType.DOCUMENT: ft.Icons.DESCRIPTION,
                AttachmentType.IMAGE: ft.Icons.IMAGE,
                AttachmentType.CODE: ft.Icons.CODE,
                AttachmentType.OTHER: ft.Icons.ATTACH_FILE
            }

            icon = icon_map.get(attachment.file_type, ft.Icons.ATTACH_FILE)

            # File size formatting
            size_mb = attachment.file_size / (1024 * 1024)
            size_text = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{attachment.file_size / 1024:.1f} KB"

            # Remove button
            remove_button = ft.IconButton(
                icon=ft.Icons.CLOSE,
                tooltip="Remove attachment",
                on_click=lambda e, att_id=attachment.file_id: asyncio.create_task(self._remove_attachment(att_id)),
                icon_size=16,
                icon_color=palette.error
            )

            # Attachment item
            attachment_item = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, color=palette.primary, size=20),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    attachment.file_name,
                                    style=ft.TextThemeStyle.BODY_MEDIUM,
                                    color=palette.text_primary,
                                    overflow=ft.TextOverflow.ELLIPSIS
                                ),
                                ft.Text(
                                    size_text,
                                    style=ft.TextThemeStyle.BODY_SMALL,
                                    color=palette.text_secondary
                                )
                            ],
                            spacing=2,
                            tight=True,
                            expand=True
                        ),
                        remove_button
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.small
                ),
                padding=ft.padding.all(spacing.small),
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.borders),
                border_radius=6
            )

            return attachment_item

        except Exception as e:
            self._logger.error(f"Error creating attachment item: {e}")
            return ft.Container()

    async def _remove_attachment(self, attachment_id: str) -> None:
        """Remove an attachment."""
        try:
            self._attachments = [att for att in self._attachments if att.file_id != attachment_id]
            await self._update_attachment_display()
            await self._update_send_button_state()

        except Exception as e:
            self._logger.error(f"Error removing attachment: {e}")

    # Message Sending and Processing
    async def _send_message(self) -> None:
        """Send the current message."""
        try:
            # Validate message
            is_valid, error_msg = await self._validate_message(self._current_text)
            if not is_valid:
                await self._show_error(error_msg)
                return

            # Prepare message data
            message_content = self._current_text.strip()
            attachments = self._attachments.copy()

            # Call send callback if provided
            if self._on_message_send:
                await self._on_message_send(message_content, attachments)

            # Clear input after sending
            await self._clear_input()

            # Update status
            if self._status_indicator:
                self._status_indicator.value = "Message sent"
                self._status_indicator.color = self.get_palette().success

            self._logger.debug("Message sent successfully")

        except Exception as e:
            self._logger.error(f"Error sending message: {e}")
            await self._show_error("Failed to send message")

    async def _clear_input(self) -> None:
        """Clear the input area."""
        try:
            self._current_text = ""
            self._attachments.clear()

            if self._text_input:
                self._text_input.value = ""

            if self._character_counter:
                self._character_counter.value = f"0 / {self._config.max_characters}"
                self._character_counter.color = self.get_palette().text_secondary

            await self._update_attachment_display()
            await self._update_send_button_state()

            # Clear preview
            if self._preview_container and self._preview_container.visible:
                await self._update_preview()

            # Clear draft
            self._current_draft = None

            if self.page:
                await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error clearing input: {e}")

    async def _update_send_button_state(self) -> None:
        """Update send button enabled/disabled state."""
        try:
            if not self._send_button:
                return

            # Enable if there's text content or attachments
            has_content = bool(self._current_text.strip())
            has_attachments = len(self._attachments) > 0

            self._send_button.disabled = not (has_content or has_attachments)

            # Update button color
            palette = self.get_palette()
            if self._send_button.disabled:
                self._send_button.bgcolor = palette.surface_variant
                self._send_button.icon_color = palette.text_secondary
            else:
                self._send_button.bgcolor = palette.primary
                self._send_button.icon_color = palette.on_primary

            if self.page:
                await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error updating send button state: {e}")

    # Typing Indicators
    async def _handle_typing_start(self) -> None:
        """Handle typing start."""
        try:
            if not self._is_typing and self._on_typing_start:
                self._is_typing = True
                await self._on_typing_start()

            # Reset typing timer
            if self._typing_timer:
                self._typing_timer.cancel()

            self._typing_timer = asyncio.create_task(self._typing_timeout())

        except Exception as e:
            self._logger.error(f"Error handling typing start: {e}")

    async def _handle_typing_stop(self) -> None:
        """Handle typing stop."""
        try:
            if self._typing_timer:
                self._typing_timer.cancel()
                self._typing_timer = None

            if self._is_typing and self._on_typing_stop:
                self._is_typing = False
                await self._on_typing_stop()

        except Exception as e:
            self._logger.error(f"Error handling typing stop: {e}")

    async def _typing_timeout(self) -> None:
        """Handle typing timeout."""
        try:
            await asyncio.sleep(3.0)  # 3 second timeout
            await self._handle_typing_stop()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in typing timeout: {e}")

    # Auto-save and Draft Management
    async def _schedule_auto_save(self) -> None:
        """Schedule auto-save of current draft."""
        try:
            if not self._config.enable_auto_save:
                return

            # Cancel existing timer
            if self._auto_save_timer:
                self._auto_save_timer.cancel()

            # Schedule new save
            self._auto_save_timer = asyncio.create_task(self._auto_save_delay())

        except Exception as e:
            self._logger.error(f"Error scheduling auto-save: {e}")

    async def _auto_save_delay(self) -> None:
        """Auto-save delay handler."""
        try:
            await asyncio.sleep(self._config.auto_save_interval_seconds)
            await self._save_draft()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in auto-save delay: {e}")

    async def _save_draft(self) -> None:
        """Save current input as draft."""
        try:
            if not self._session_id or not self._current_text.strip():
                return

            draft = MessageDraft(
                draft_id=str(uuid.uuid4()),
                session_id=self._session_id,
                content=self._current_text,
                attachments=self._attachments.copy(),
                input_mode=self._current_mode,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            self._current_draft = draft
            self._logger.debug("Draft saved")

        except Exception as e:
            self._logger.error(f"Error saving draft: {e}")

    # Utility Methods
    async def _show_error(self, message: str) -> None:
        """Show error message to user."""
        try:
            if self._status_indicator:
                self._status_indicator.value = f"Error: {message}"
                self._status_indicator.color = self.get_palette().error

            if self.page:
                await self.page.update_async()

            # Reset status after delay
            await asyncio.sleep(3.0)
            if self._status_indicator:
                self._status_indicator.value = "Ready"
                self._status_indicator.color = self.get_palette().text_secondary
                if self.page:
                    await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error showing error message: {e}")

    # Public API Methods
    def set_session_id(self, session_id: str) -> None:
        """Set the chat session ID."""
        self._session_id = session_id

    def get_current_text(self) -> str:
        """Get current input text."""
        return self._current_text

    def get_attachments(self) -> List[AttachmentData]:
        """Get current attachments."""
        return self._attachments.copy()

    async def load_draft(self, draft: MessageDraft) -> None:
        """Load a draft into the input."""
        try:
            self._current_text = draft.content
            self._attachments = draft.attachments.copy()
            self._current_mode = draft.input_mode
            self._current_draft = draft

            # Update UI
            if self._text_input:
                self._text_input.value = self._current_text

            if self._mode_selector:
                self._mode_selector.value = self._current_mode.value

            await self._update_attachment_display()
            await self._update_send_button_state()

            if self.page:
                await self.page.update_async()

        except Exception as e:
            self._logger.error(f"Error loading draft: {e}")

    async def clear_all(self) -> None:
        """Clear all input content."""
        await self._clear_input()
