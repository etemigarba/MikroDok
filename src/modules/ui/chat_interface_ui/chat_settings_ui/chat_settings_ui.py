"""
Module: chat_settings_ui
Description: Comprehensive chat configuration and preferences interface with responsive design.
            Provides tabbed settings interface for chat behavior, display options, conversation
            preferences, and advanced configuration with real-time validation and persistence.
Phase: 4
Location: /src/modules/ui/chat_interface_ui/chat_settings_ui/chat_settings_ui.py
"""

# Standard library imports
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ResponsiveLayoutManager,
    get_theme_manager
)
from src.modules.database.app_state_db.user_preferences_db.user_preferences_db import (
    UserPreferencesDB
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager


class ChatSettingsCategory(Enum):
    """Chat settings category enumeration."""
    GENERAL = "general"
    DISPLAY = "display"
    BEHAVIOR = "behavior"
    ADVANCED = "advanced"
    INTEGRATION = "integration"


class MessageDisplayMode(Enum):
    """Message display mode options."""
    BUBBLES = "bubbles"
    COMPACT = "compact"
    DETAILED = "detailed"
    MINIMAL = "minimal"


class ThemePreference(Enum):
    """Theme preference options."""
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"


class FontSize(Enum):
    """Font size options."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


class AutoSaveInterval(Enum):
    """Auto-save interval options."""
    DISABLED = 0
    EVERY_30_SECONDS = 30
    EVERY_MINUTE = 60
    EVERY_5_MINUTES = 300
    EVERY_10_MINUTES = 600


@dataclass
class ChatSettingsConfig:
    """Comprehensive configuration for chat settings interface."""
    # General settings
    enable_auto_save: bool = True
    auto_save_interval: AutoSaveInterval = AutoSaveInterval.EVERY_MINUTE
    enable_real_time_validation: bool = True
    enable_tooltips: bool = True
    enable_import_export: bool = True
    show_advanced_options: bool = False
    
    # Display settings
    message_display_mode: MessageDisplayMode = MessageDisplayMode.BUBBLES
    show_timestamps: bool = True
    show_avatars: bool = True
    show_typing_indicators: bool = True
    show_message_status: bool = True
    font_size: FontSize = FontSize.MEDIUM
    theme_preference: ThemePreference = ThemePreference.SYSTEM
    enable_animations: bool = True
    compact_mode_threshold: int = 768
    
    # Behavior settings
    send_on_enter: bool = False  # Ctrl+Enter to send
    enable_markdown_preview: bool = True
    enable_code_highlighting: bool = True
    enable_emoji_picker: bool = True
    enable_spell_check: bool = True
    auto_scroll_enabled: bool = True
    enable_message_threading: bool = True
    enable_context_menu: bool = True
    enable_message_selection: bool = True
    enable_copy_functionality: bool = True
    
    # Advanced settings
    max_messages_displayed: int = 100
    max_message_length: int = 4000
    context_window_size: int = 4096
    enable_message_compression: bool = False
    enable_search_highlighting: bool = True
    scroll_buffer_size: int = 20
    animation_duration_ms: int = 300
    
    # Integration settings
    enable_file_attachments: bool = True
    max_attachment_size_mb: int = 10
    allowed_file_types: List[str] = field(default_factory=lambda: [
        '.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml',
        '.pdf', '.docx', '.xlsx', '.pptx', '.png', '.jpg', '.jpeg', '.gif'
    ])
    enable_external_links: bool = True
    enable_notifications: bool = True
    
    # Visible categories
    visible_categories: List[ChatSettingsCategory] = field(
        default_factory=lambda: [
            ChatSettingsCategory.GENERAL,
            ChatSettingsCategory.DISPLAY,
            ChatSettingsCategory.BEHAVIOR,
            ChatSettingsCategory.ADVANCED,
            ChatSettingsCategory.INTEGRATION
        ]
    )


@dataclass
class SettingsValidationResult:
    """Result of settings validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class ChatSettingsUI(ThemeAwareUserControl):
    """
    Comprehensive chat configuration and preferences interface.
    
    Provides tabbed settings interface for chat behavior, display options,
    conversation preferences, and advanced configuration with real-time
    validation, auto-save functionality, and full theme system integration.
    
    Features:
    - Responsive tabbed interface with category-based organization
    - Real-time validation with visual feedback and suggestions
    - Auto-save functionality with configurable intervals
    - Configuration import/export capabilities
    - Preset configurations for common scenarios
    - Full theme system integration with responsive design
    - Accessibility compliance with keyboard navigation
    - Integration with user preferences database
    - Advanced settings for power users
    - File attachment and integration settings
    """
    
    def __init__(
        self,
        config: Optional[ChatSettingsConfig] = None,
        on_settings_change: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_settings_save: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_settings_reset: Optional[Callable[[], None]] = None,
        user_id: str = "default",
        **kwargs
    ):
        """
        Initialize the chat settings interface.
        
        Args:
            config: Chat settings configuration
            on_settings_change: Callback for settings changes
            on_settings_save: Callback for settings save
            on_settings_reset: Callback for settings reset
            user_id: User identifier for preferences
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self.config = config or ChatSettingsConfig()
        self.user_id = user_id
        
        # Callbacks
        self._on_settings_change = on_settings_change
        self._on_settings_save = on_settings_save
        self._on_settings_reset = on_settings_reset
        
        # Database connections
        self._user_preferences_db = UserPreferencesDB()
        self._app_state_manager = AppStateManager()
        
        # State management
        self._current_settings: Dict[str, Any] = {}
        self._original_settings: Dict[str, Any] = {}
        self._validation_result: Optional[SettingsValidationResult] = None
        self._is_loading = False
        self._has_unsaved_changes = False
        self._auto_save_task: Optional[asyncio.Task] = None
        
        # UI components
        self._tabs_container: Optional[ft.Container] = None
        self._validation_panel: Optional[ft.Container] = None
        self._action_bar: Optional[ft.Container] = None
        self._status_text: Optional[ft.Text] = None
        
        # Logger
        self._logger = logging.getLogger(__name__)
        
        # Load initial settings
        self._load_settings()
        
        # Build UI
        self._build_ui()
        
        # Start auto-save if enabled
        if self.config.enable_auto_save and self.config.auto_save_interval != AutoSaveInterval.DISABLED:
            self._start_auto_save()
    
    def _load_settings(self) -> None:
        """Load settings from user preferences."""
        try:
            preferences = self._user_preferences_db.get_user_preferences(self.user_id)
            if preferences and 'chat_settings' in preferences:
                self._current_settings = preferences['chat_settings'].copy()
                self._original_settings = preferences['chat_settings'].copy()
            else:
                # Use default settings
                self._current_settings = self._get_default_settings()
                self._original_settings = self._current_settings.copy()
        except Exception as e:
            self._logger.error(f"Failed to load settings: {e}")
            self._current_settings = self._get_default_settings()
            self._original_settings = self._current_settings.copy()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings dictionary."""
        return {
            # General settings
            'enable_auto_save': self.config.enable_auto_save,
            'auto_save_interval': self.config.auto_save_interval.value,
            'enable_real_time_validation': self.config.enable_real_time_validation,
            'enable_tooltips': self.config.enable_tooltips,
            'show_advanced_options': self.config.show_advanced_options,
            
            # Display settings
            'message_display_mode': self.config.message_display_mode.value,
            'show_timestamps': self.config.show_timestamps,
            'show_avatars': self.config.show_avatars,
            'show_typing_indicators': self.config.show_typing_indicators,
            'show_message_status': self.config.show_message_status,
            'font_size': self.config.font_size.value,
            'theme_preference': self.config.theme_preference.value,
            'enable_animations': self.config.enable_animations,
            'compact_mode_threshold': self.config.compact_mode_threshold,
            
            # Behavior settings
            'send_on_enter': self.config.send_on_enter,
            'enable_markdown_preview': self.config.enable_markdown_preview,
            'enable_code_highlighting': self.config.enable_code_highlighting,
            'enable_emoji_picker': self.config.enable_emoji_picker,
            'enable_spell_check': self.config.enable_spell_check,
            'auto_scroll_enabled': self.config.auto_scroll_enabled,
            'enable_message_threading': self.config.enable_message_threading,
            'enable_context_menu': self.config.enable_context_menu,
            'enable_message_selection': self.config.enable_message_selection,
            'enable_copy_functionality': self.config.enable_copy_functionality,
            
            # Advanced settings
            'max_messages_displayed': self.config.max_messages_displayed,
            'max_message_length': self.config.max_message_length,
            'context_window_size': self.config.context_window_size,
            'enable_message_compression': self.config.enable_message_compression,
            'enable_search_highlighting': self.config.enable_search_highlighting,
            'scroll_buffer_size': self.config.scroll_buffer_size,
            'animation_duration_ms': self.config.animation_duration_ms,
            
            # Integration settings
            'enable_file_attachments': self.config.enable_file_attachments,
            'max_attachment_size_mb': self.config.max_attachment_size_mb,
            'allowed_file_types': self.config.allowed_file_types.copy(),
            'enable_external_links': self.config.enable_external_links,
            'enable_notifications': self.config.enable_notifications
        }

    def _build_ui(self) -> None:
        """Build the chat settings interface."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Main container with responsive design
        self.content = ft.Column(
            controls=[
                self._create_header(),
                self._create_tabs(),
                self._create_validation_panel(),
                self._create_action_bar()
            ],
            spacing=spacing.md,
            expand=True
        )

        # Apply theme-aware styling
        self.bgcolor = palette.surface
        self.border_radius = self.get_breakpoint_value(8, 10, 12, 14)
        self.padding = self.get_breakpoint_value(
            spacing.md,
            spacing.lg,
            spacing.xl,
            spacing.xl
        )

        # Initial validation
        if self.config.enable_real_time_validation:
            self._schedule_validation()

    def _create_header(self) -> ft.Container:
        """Create the settings header."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Title and description
        title = ft.Text(
            "Chat Settings",
            style=self.get_text_style("h2"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_600
        )

        description = ft.Text(
            "Configure chat behavior, display options, and preferences",
            style=self.get_text_style("body_medium"),
            color=palette.text_secondary,
            opacity=0.8
        )

        # Status indicator
        self._status_text = ft.Text(
            "Settings loaded",
            style=self.get_text_style("body_small"),
            color=palette.primary,
            visible=False
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[title, description],
                                spacing=spacing.xs,
                                expand=True
                            ),
                            self._create_header_actions()
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.START
                    ),
                    self._status_text
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.only(bottom=spacing.md)
        )

    def _create_header_actions(self) -> ft.Row:
        """Create header action buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Import button
        import_button = self.create_themed_component(
            "button",
            variant="secondary",
            text="Import",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._handle_import_settings,
            tooltip="Import settings from file"
        )

        # Export button
        export_button = self.create_themed_component(
            "button",
            variant="secondary",
            text="Export",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._handle_export_settings,
            tooltip="Export settings to file"
        )

        # Reset button
        reset_button = self.create_themed_component(
            "button",
            variant="destructive",
            text="Reset",
            icon=ft.Icons.RESTORE,
            on_click=self._handle_reset_settings,
            tooltip="Reset to default settings"
        )

        return ft.Row(
            controls=[import_button, export_button, reset_button],
            spacing=spacing.sm,
            tight=True
        )

    def _create_tabs(self) -> ft.Container:
        """Create the main tabs interface."""
        palette = self.get_palette()

        # Create tabs based on visible categories
        tab_controls = []

        if ChatSettingsCategory.GENERAL in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="General",
                    icon=ft.Icons.SETTINGS,
                    content=self._create_general_settings_tab()
                )
            )

        if ChatSettingsCategory.DISPLAY in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Display",
                    icon=ft.Icons.DISPLAY_SETTINGS,
                    content=self._create_display_settings_tab()
                )
            )

        if ChatSettingsCategory.BEHAVIOR in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Behavior",
                    icon=ft.Icons.PSYCHOLOGY,
                    content=self._create_behavior_settings_tab()
                )
            )

        if ChatSettingsCategory.ADVANCED in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Advanced",
                    icon=ft.Icons.TUNE,
                    content=self._create_advanced_settings_tab()
                )
            )

        if ChatSettingsCategory.INTEGRATION in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Integration",
                    icon=ft.Icons.INTEGRATION_INSTRUCTIONS,
                    content=self._create_integration_settings_tab()
                )
            )

        # Create tabs container
        tabs = ft.Tabs(
            selected_index=0,
            tabs=tab_controls,
            expand=True,
            animation_duration=300
        )

        self._tabs_container = ft.Container(
            content=tabs,
            expand=True,
            bgcolor=palette.surface_variant,
            border_radius=self.get_breakpoint_value(8, 10, 12, 14),
            padding=self.get_breakpoint_value(
                self.get_spacing().sm,
                self.get_spacing().md,
                self.get_spacing().lg,
                self.get_spacing().lg
            )
        )

        return self._tabs_container

    def _create_general_settings_tab(self) -> ft.Container:
        """Create the general settings tab."""
        spacing = self.get_spacing()

        # Auto-save settings
        auto_save_section = self._create_settings_section(
            "Auto-Save",
            [
                self._create_switch_setting(
                    "enable_auto_save",
                    "Enable Auto-Save",
                    "Automatically save settings changes",
                    self._current_settings.get('enable_auto_save', True)
                ),
                self._create_dropdown_setting(
                    "auto_save_interval",
                    "Auto-Save Interval",
                    "How often to save settings automatically",
                    [
                        ("Disabled", 0),
                        ("Every 30 seconds", 30),
                        ("Every minute", 60),
                        ("Every 5 minutes", 300),
                        ("Every 10 minutes", 600)
                    ],
                    self._current_settings.get('auto_save_interval', 60)
                )
            ]
        )

        # Validation settings
        validation_section = self._create_settings_section(
            "Validation & Feedback",
            [
                self._create_switch_setting(
                    "enable_real_time_validation",
                    "Real-time Validation",
                    "Validate settings as you type",
                    self._current_settings.get('enable_real_time_validation', True)
                ),
                self._create_switch_setting(
                    "enable_tooltips",
                    "Show Tooltips",
                    "Display helpful tooltips for settings",
                    self._current_settings.get('enable_tooltips', True)
                )
            ]
        )

        # Advanced options
        advanced_section = self._create_settings_section(
            "Interface Options",
            [
                self._create_switch_setting(
                    "show_advanced_options",
                    "Show Advanced Options",
                    "Display advanced configuration options",
                    self._current_settings.get('show_advanced_options', False)
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[auto_save_section, validation_section, advanced_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_display_settings_tab(self) -> ft.Container:
        """Create the display settings tab."""
        spacing = self.get_spacing()

        # Message display settings
        message_display_section = self._create_settings_section(
            "Message Display",
            [
                self._create_dropdown_setting(
                    "message_display_mode",
                    "Display Mode",
                    "How messages are displayed in the chat",
                    [
                        ("Bubbles", "bubbles"),
                        ("Compact", "compact"),
                        ("Detailed", "detailed"),
                        ("Minimal", "minimal")
                    ],
                    self._current_settings.get('message_display_mode', 'bubbles')
                ),
                self._create_switch_setting(
                    "show_timestamps",
                    "Show Timestamps",
                    "Display message timestamps",
                    self._current_settings.get('show_timestamps', True)
                ),
                self._create_switch_setting(
                    "show_avatars",
                    "Show Avatars",
                    "Display user avatars in messages",
                    self._current_settings.get('show_avatars', True)
                ),
                self._create_switch_setting(
                    "show_typing_indicators",
                    "Typing Indicators",
                    "Show when someone is typing",
                    self._current_settings.get('show_typing_indicators', True)
                ),
                self._create_switch_setting(
                    "show_message_status",
                    "Message Status",
                    "Show message delivery status",
                    self._current_settings.get('show_message_status', True)
                )
            ]
        )

        # Appearance settings
        appearance_section = self._create_settings_section(
            "Appearance",
            [
                self._create_dropdown_setting(
                    "font_size",
                    "Font Size",
                    "Text size in the chat interface",
                    [
                        ("Small", "small"),
                        ("Medium", "medium"),
                        ("Large", "large"),
                        ("Extra Large", "extra_large")
                    ],
                    self._current_settings.get('font_size', 'medium')
                ),
                self._create_dropdown_setting(
                    "theme_preference",
                    "Theme",
                    "Color theme for the chat interface",
                    [
                        ("System", "system"),
                        ("Light", "light"),
                        ("Dark", "dark"),
                        ("High Contrast", "high_contrast")
                    ],
                    self._current_settings.get('theme_preference', 'system')
                ),
                self._create_switch_setting(
                    "enable_animations",
                    "Enable Animations",
                    "Use smooth animations in the interface",
                    self._current_settings.get('enable_animations', True)
                ),
                self._create_slider_setting(
                    "compact_mode_threshold",
                    "Compact Mode Threshold",
                    "Screen width below which compact mode is used (pixels)",
                    400, 1200, 768,
                    self._current_settings.get('compact_mode_threshold', 768)
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[message_display_section, appearance_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_behavior_settings_tab(self) -> ft.Container:
        """Create the behavior settings tab."""
        spacing = self.get_spacing()

        # Input behavior settings
        input_behavior_section = self._create_settings_section(
            "Input Behavior",
            [
                self._create_switch_setting(
                    "send_on_enter",
                    "Send on Enter",
                    "Send message when Enter is pressed (otherwise Ctrl+Enter)",
                    self._current_settings.get('send_on_enter', False)
                ),
                self._create_switch_setting(
                    "enable_markdown_preview",
                    "Markdown Preview",
                    "Show markdown preview while typing",
                    self._current_settings.get('enable_markdown_preview', True)
                ),
                self._create_switch_setting(
                    "enable_code_highlighting",
                    "Code Highlighting",
                    "Highlight code blocks in messages",
                    self._current_settings.get('enable_code_highlighting', True)
                ),
                self._create_switch_setting(
                    "enable_emoji_picker",
                    "Emoji Picker",
                    "Show emoji picker in message input",
                    self._current_settings.get('enable_emoji_picker', True)
                ),
                self._create_switch_setting(
                    "enable_spell_check",
                    "Spell Check",
                    "Check spelling while typing",
                    self._current_settings.get('enable_spell_check', True)
                )
            ]
        )

        # Chat behavior settings
        chat_behavior_section = self._create_settings_section(
            "Chat Behavior",
            [
                self._create_switch_setting(
                    "auto_scroll_enabled",
                    "Auto-Scroll",
                    "Automatically scroll to new messages",
                    self._current_settings.get('auto_scroll_enabled', True)
                ),
                self._create_switch_setting(
                    "enable_message_threading",
                    "Message Threading",
                    "Enable threaded conversations",
                    self._current_settings.get('enable_message_threading', True)
                ),
                self._create_switch_setting(
                    "enable_context_menu",
                    "Context Menu",
                    "Show right-click context menu on messages",
                    self._current_settings.get('enable_context_menu', True)
                ),
                self._create_switch_setting(
                    "enable_message_selection",
                    "Message Selection",
                    "Allow selecting multiple messages",
                    self._current_settings.get('enable_message_selection', True)
                ),
                self._create_switch_setting(
                    "enable_copy_functionality",
                    "Copy Functionality",
                    "Enable copying messages to clipboard",
                    self._current_settings.get('enable_copy_functionality', True)
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[input_behavior_section, chat_behavior_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_advanced_settings_tab(self) -> ft.Container:
        """Create the advanced settings tab."""
        spacing = self.get_spacing()

        # Performance settings
        performance_section = self._create_settings_section(
            "Performance",
            [
                self._create_slider_setting(
                    "max_messages_displayed",
                    "Max Messages Displayed",
                    "Maximum number of messages to show at once",
                    50, 500, 100,
                    self._current_settings.get('max_messages_displayed', 100)
                ),
                self._create_slider_setting(
                    "max_message_length",
                    "Max Message Length",
                    "Maximum characters allowed per message",
                    1000, 10000, 4000,
                    self._current_settings.get('max_message_length', 4000)
                ),
                self._create_slider_setting(
                    "context_window_size",
                    "Context Window Size",
                    "Number of tokens in conversation context",
                    1024, 8192, 4096,
                    self._current_settings.get('context_window_size', 4096)
                ),
                self._create_switch_setting(
                    "enable_message_compression",
                    "Message Compression",
                    "Compress old messages to save memory",
                    self._current_settings.get('enable_message_compression', False)
                )
            ]
        )

        # UI performance settings
        ui_performance_section = self._create_settings_section(
            "UI Performance",
            [
                self._create_switch_setting(
                    "enable_search_highlighting",
                    "Search Highlighting",
                    "Highlight search terms in messages",
                    self._current_settings.get('enable_search_highlighting', True)
                ),
                self._create_slider_setting(
                    "scroll_buffer_size",
                    "Scroll Buffer Size",
                    "Number of messages to keep in scroll buffer",
                    10, 100, 20,
                    self._current_settings.get('scroll_buffer_size', 20)
                ),
                self._create_slider_setting(
                    "animation_duration_ms",
                    "Animation Duration",
                    "Duration of UI animations in milliseconds",
                    100, 1000, 300,
                    self._current_settings.get('animation_duration_ms', 300)
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[performance_section, ui_performance_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_integration_settings_tab(self) -> ft.Container:
        """Create the integration settings tab."""
        spacing = self.get_spacing()

        # File attachment settings
        file_attachment_section = self._create_settings_section(
            "File Attachments",
            [
                self._create_switch_setting(
                    "enable_file_attachments",
                    "Enable File Attachments",
                    "Allow attaching files to messages",
                    self._current_settings.get('enable_file_attachments', True)
                ),
                self._create_slider_setting(
                    "max_attachment_size_mb",
                    "Max Attachment Size (MB)",
                    "Maximum file size for attachments",
                    1, 100, 10,
                    self._current_settings.get('max_attachment_size_mb', 10)
                ),
                self._create_text_setting(
                    "allowed_file_types",
                    "Allowed File Types",
                    "Comma-separated list of allowed file extensions",
                    ", ".join(self._current_settings.get('allowed_file_types', ['.txt', '.md', '.py']))
                )
            ]
        )

        # External integration settings
        external_integration_section = self._create_settings_section(
            "External Integration",
            [
                self._create_switch_setting(
                    "enable_external_links",
                    "External Links",
                    "Allow opening external links from messages",
                    self._current_settings.get('enable_external_links', True)
                ),
                self._create_switch_setting(
                    "enable_notifications",
                    "Notifications",
                    "Show system notifications for new messages",
                    self._current_settings.get('enable_notifications', True)
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[file_attachment_section, external_integration_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            expand=True
        )

    def _create_settings_section(self, title: str, controls: List[ft.Control]) -> ft.Container:
        """Create a settings section with title and controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        section_title = ft.Text(
            title,
            style=self.get_text_style("h3"),
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Divider(height=1, color=palette.outline),
                    *controls
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.surface_variant,
            border_radius=self.get_breakpoint_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline)
        )

    def _create_switch_setting(self, key: str, title: str, description: str, value: bool) -> ft.Container:
        """Create a switch setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        switch = ft.Switch(
            value=value,
            active_color=palette.primary,
            on_change=lambda e: self._handle_setting_change(key, e.control.value)
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                title,
                                style=self.get_text_style("body_large"),
                                color=palette.text_primary,
                                weight=ft.FontWeight.W_500
                            ),
                            ft.Text(
                                description,
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary,
                                opacity=0.8
                            )
                        ],
                        spacing=spacing.xs,
                        expand=True
                    ),
                    switch
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=ft.padding.symmetric(vertical=spacing.sm)
        )

    def _create_dropdown_setting(self, key: str, title: str, description: str,
                                options: List[Tuple[str, Any]], value: Any) -> ft.Container:
        """Create a dropdown setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Find current option
        current_option = next((opt[0] for opt in options if opt[1] == value), options[0][0] if options else "")

        dropdown = ft.Dropdown(
            value=current_option,
            options=[ft.dropdown.Option(text=opt[0], key=str(opt[1])) for opt in options],
            on_change=lambda e: self._handle_setting_change(key, e.control.value),
            bgcolor=palette.surface,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary),
            width=200
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                title,
                                style=self.get_text_style("body_large"),
                                color=palette.text_primary,
                                weight=ft.FontWeight.W_500
                            ),
                            ft.Text(
                                description,
                                style=self.get_text_style("body_small"),
                                color=palette.text_secondary,
                                opacity=0.8
                            )
                        ],
                        spacing=spacing.xs,
                        expand=True
                    ),
                    dropdown
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=ft.padding.symmetric(vertical=spacing.sm)
        )

    def _create_slider_setting(self, key: str, title: str, description: str,
                              min_value: int, max_value: int, divisions: int, value: int) -> ft.Container:
        """Create a slider setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Value display
        value_text = ft.Text(
            str(value),
            style=self.get_text_style("body_medium"),
            color=palette.primary,
            weight=ft.FontWeight.W_500
        )

        slider = ft.Slider(
            min=min_value,
            max=max_value,
            divisions=divisions,
            value=value,
            active_color=palette.primary,
            inactive_color=palette.outline,
            thumb_color=palette.primary,
            on_change=lambda e: self._handle_slider_change(key, e.control.value, value_text),
            width=200
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        title,
                                        style=self.get_text_style("body_large"),
                                        color=palette.text_primary,
                                        weight=ft.FontWeight.W_500
                                    ),
                                    ft.Text(
                                        description,
                                        style=self.get_text_style("body_small"),
                                        color=palette.text_secondary,
                                        opacity=0.8
                                    )
                                ],
                                spacing=spacing.xs,
                                expand=True
                            ),
                            value_text
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    ft.Row(
                        controls=[
                            ft.Text(str(min_value), style=self.get_text_style("body_small"), color=palette.text_secondary),
                            slider,
                            ft.Text(str(max_value), style=self.get_text_style("body_small"), color=palette.text_secondary)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    )
                ],
                spacing=spacing.xs
            ),
            padding=ft.padding.symmetric(vertical=spacing.sm)
        )

    def _create_text_setting(self, key: str, title: str, description: str, value: str) -> ft.Container:
        """Create a text input setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        text_field = ft.TextField(
            value=value,
            on_change=lambda e: self._handle_setting_change(key, e.control.value),
            bgcolor=palette.surface,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            text_style=ft.TextStyle(color=palette.text_primary),
            multiline=False,
            width=300
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title,
                        style=self.get_text_style("body_large"),
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        description,
                        style=self.get_text_style("body_small"),
                        color=palette.text_secondary,
                        opacity=0.8
                    ),
                    text_field
                ],
                spacing=spacing.xs
            ),
            padding=ft.padding.symmetric(vertical=spacing.sm)
        )

    def _create_validation_panel(self) -> ft.Container:
        """Create the validation feedback panel."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        self._validation_panel = ft.Container(
            content=ft.Column(
                controls=[],
                spacing=spacing.xs
            ),
            visible=False,
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.error_container,
            border_radius=self.get_breakpoint_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.error)
        )

        return self._validation_panel

    def _create_action_bar(self) -> ft.Container:
        """Create the action bar with save/cancel buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Save button
        save_button = self.create_themed_component(
            "button",
            variant="primary",
            text="Save Settings",
            icon=ft.Icons.SAVE,
            on_click=self._handle_save_settings,
            disabled=not self._has_unsaved_changes
        )

        # Cancel button
        cancel_button = self.create_themed_component(
            "button",
            variant="secondary",
            text="Cancel",
            icon=ft.Icons.CANCEL,
            on_click=self._handle_cancel_changes,
            disabled=not self._has_unsaved_changes
        )

        # Apply button
        apply_button = self.create_themed_component(
            "button",
            variant="secondary",
            text="Apply",
            icon=ft.Icons.CHECK,
            on_click=self._handle_apply_settings,
            disabled=not self._has_unsaved_changes
        )

        self._action_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),  # Spacer
                    cancel_button,
                    apply_button,
                    save_button
                ],
                spacing=spacing.sm,
                alignment=ft.MainAxisAlignment.END
            ),
            padding=ft.padding.only(top=spacing.md),
            border=ft.border.only(top=ft.BorderSide(1, palette.outline))
        )

        return self._action_bar

    def _handle_setting_change(self, key: str, value: Any) -> None:
        """Handle setting value change."""
        try:
            # Update current settings
            self._current_settings[key] = value
            self._has_unsaved_changes = True

            # Update action bar state
            self._update_action_bar_state()

            # Trigger validation if enabled
            if self.config.enable_real_time_validation:
                self._schedule_validation()

            # Notify callback
            if self._on_settings_change:
                self._on_settings_change(self._current_settings.copy())

            # Update status
            self._update_status("Settings modified")

        except Exception as e:
            self._logger.error(f"Failed to handle setting change: {e}")
            self._show_error(f"Failed to update setting: {str(e)}")

    def _handle_slider_change(self, key: str, value: float, value_text: ft.Text) -> None:
        """Handle slider value change."""
        int_value = int(value)
        value_text.value = str(int_value)
        if self.page:
            value_text.update()
        self._handle_setting_change(key, int_value)

    def _handle_save_settings(self, e) -> None:
        """Handle save settings action."""
        try:
            # Validate settings
            validation_result = self._validate_settings()
            if not validation_result.is_valid:
                self._show_validation_errors(validation_result)
                return

            # Save to database
            preferences = self._user_preferences_db.get_user_preferences(self.user_id) or {}
            preferences['chat_settings'] = self._current_settings.copy()
            self._user_preferences_db.save_user_preferences(preferences, self.user_id)

            # Update original settings
            self._original_settings = self._current_settings.copy()
            self._has_unsaved_changes = False

            # Update action bar state
            self._update_action_bar_state()

            # Notify callback
            if self._on_settings_save:
                self._on_settings_save(self._current_settings.copy())

            # Update status
            self._update_status("Settings saved successfully", success=True)

        except Exception as e:
            self._logger.error(f"Failed to save settings: {e}")
            self._show_error(f"Failed to save settings: {str(e)}")

    def _handle_cancel_changes(self, e) -> None:
        """Handle cancel changes action."""
        try:
            # Restore original settings
            self._current_settings = self._original_settings.copy()
            self._has_unsaved_changes = False

            # Rebuild UI to reflect restored settings
            self._rebuild_settings_ui()

            # Update action bar state
            self._update_action_bar_state()

            # Update status
            self._update_status("Changes cancelled")

        except Exception as e:
            self._logger.error(f"Failed to cancel changes: {e}")
            self._show_error(f"Failed to cancel changes: {str(e)}")

    def _handle_apply_settings(self, e) -> None:
        """Handle apply settings action."""
        try:
            # Validate settings
            validation_result = self._validate_settings()
            if not validation_result.is_valid:
                self._show_validation_errors(validation_result)
                return

            # Apply settings without saving
            if self._on_settings_change:
                self._on_settings_change(self._current_settings.copy())

            # Update status
            self._update_status("Settings applied")

        except Exception as e:
            self._logger.error(f"Failed to apply settings: {e}")
            self._show_error(f"Failed to apply settings: {str(e)}")

    def _handle_reset_settings(self, e) -> None:
        """Handle reset settings action."""
        try:
            # Reset to default settings
            self._current_settings = self._get_default_settings()
            self._has_unsaved_changes = True

            # Rebuild UI to reflect reset settings
            self._rebuild_settings_ui()

            # Update action bar state
            self._update_action_bar_state()

            # Notify callback
            if self._on_settings_reset:
                self._on_settings_reset()

            # Update status
            self._update_status("Settings reset to defaults")

        except Exception as e:
            self._logger.error(f"Failed to reset settings: {e}")
            self._show_error(f"Failed to reset settings: {str(e)}")

    def _handle_import_settings(self, e) -> None:
        """Handle import settings action."""
        try:
            # TODO: Implement file picker for importing settings
            self._update_status("Import functionality not yet implemented")
        except Exception as e:
            self._logger.error(f"Failed to import settings: {e}")
            self._show_error(f"Failed to import settings: {str(e)}")

    def _handle_export_settings(self, e) -> None:
        """Handle export settings action."""
        try:
            # TODO: Implement file picker for exporting settings
            self._update_status("Export functionality not yet implemented")
        except Exception as e:
            self._logger.error(f"Failed to export settings: {e}")
            self._show_error(f"Failed to export settings: {str(e)}")

    def _validate_settings(self) -> SettingsValidationResult:
        """Validate current settings."""
        result = SettingsValidationResult(is_valid=True)

        try:
            # Validate numeric ranges
            if self._current_settings.get('max_messages_displayed', 0) < 10:
                result.errors.append("Max messages displayed must be at least 10")
                result.is_valid = False

            if self._current_settings.get('max_message_length', 0) < 100:
                result.errors.append("Max message length must be at least 100 characters")
                result.is_valid = False

            if self._current_settings.get('context_window_size', 0) < 512:
                result.errors.append("Context window size must be at least 512 tokens")
                result.is_valid = False

            if self._current_settings.get('max_attachment_size_mb', 0) < 1:
                result.errors.append("Max attachment size must be at least 1 MB")
                result.is_valid = False

            # Validate file types
            file_types = self._current_settings.get('allowed_file_types', [])
            if isinstance(file_types, str):
                file_types = [ft.strip() for ft in file_types.split(',') if ft.strip()]
                self._current_settings['allowed_file_types'] = file_types

            if not file_types:
                result.warnings.append("No file types allowed - file attachments will be disabled")

            # Performance warnings
            if self._current_settings.get('max_messages_displayed', 0) > 200:
                result.warnings.append("High message display limit may impact performance")

            if self._current_settings.get('animation_duration_ms', 0) > 500:
                result.warnings.append("Long animation duration may feel sluggish")

        except Exception as e:
            result.errors.append(f"Validation error: {str(e)}")
            result.is_valid = False

        return result

    def _schedule_validation(self) -> None:
        """Schedule validation with debouncing."""
        if hasattr(self, '_validation_timer'):
            self._validation_timer.cancel()

        # Debounce validation by 500ms
        import threading
        self._validation_timer = threading.Timer(0.5, self._perform_validation)
        self._validation_timer.start()

    def _perform_validation(self) -> None:
        """Perform validation and update UI."""
        try:
            validation_result = self._validate_settings()
            self._validation_result = validation_result

            if validation_result.errors or validation_result.warnings:
                self._show_validation_feedback(validation_result)
            else:
                self._hide_validation_panel()

        except Exception as e:
            self._logger.error(f"Validation failed: {e}")

    def _show_validation_feedback(self, result: SettingsValidationResult) -> None:
        """Show validation feedback in the panel."""
        if not self._validation_panel:
            return

        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        controls = []

        # Add errors
        for error in result.errors:
            controls.append(
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ERROR, color=palette.error, size=16),
                        ft.Text(error, style=self.get_text_style("body_small"), color=palette.text_primary)
                    ],
                    spacing=spacing.xs
                )
            )

        # Add warnings
        for warning in result.warnings:
            controls.append(
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.WARNING, color=palette.tertiary, size=16),
                        ft.Text(warning, style=self.get_text_style("body_small"), color=palette.text_primary)
                    ],
                    spacing=spacing.xs
                )
            )

        self._validation_panel.content.controls = controls
        self._validation_panel.visible = True
        if self.page:
            self._validation_panel.update()

    def _show_validation_errors(self, result: SettingsValidationResult) -> None:
        """Show validation errors and prevent saving."""
        self._show_validation_feedback(result)
        self._update_status("Please fix validation errors before saving", error=True)

    def _hide_validation_panel(self) -> None:
        """Hide the validation panel."""
        if self._validation_panel:
            self._validation_panel.visible = False
            if self.page:
                self._validation_panel.update()

    def _update_action_bar_state(self) -> None:
        """Update action bar button states."""
        if not self._action_bar:
            return

        # Find buttons in action bar
        for control in self._action_bar.content.controls:
            if isinstance(control, ft.ElevatedButton):
                if "Save" in control.text:
                    control.disabled = not self._has_unsaved_changes
                elif "Cancel" in control.text or "Apply" in control.text:
                    control.disabled = not self._has_unsaved_changes

        # Only update if we have a page context
        if self.page:
            self._action_bar.update()

    def _rebuild_settings_ui(self) -> None:
        """Rebuild settings UI with current values."""
        # This would require rebuilding the entire tabs content
        # For now, just update the page if available
        if self.page:
            self.page.update()

    def _update_status(self, message: str, success: bool = False, error: bool = False) -> None:
        """Update status message."""
        if not self._status_text:
            return

        palette = self.get_palette()

        self._status_text.value = message
        if error:
            self._status_text.color = palette.error
        elif success:
            self._status_text.color = palette.primary
        else:
            self._status_text.color = palette.text_secondary

        self._status_text.visible = True
        if self.page:
            self._status_text.update()

        # Auto-hide after 3 seconds
        import threading
        threading.Timer(3.0, lambda: self._hide_status()).start()

    def _hide_status(self) -> None:
        """Hide status message."""
        if self._status_text:
            self._status_text.visible = False
            if self.page:
                self._status_text.update()

    def _show_error(self, message: str) -> None:
        """Show error message."""
        self._update_status(message, error=True)

    def _start_auto_save(self) -> None:
        """Start auto-save timer."""
        if self._auto_save_task:
            self._auto_save_task.cancel()

        try:
            async def auto_save_loop():
                while True:
                    await asyncio.sleep(self.config.auto_save_interval.value)
                    if self._has_unsaved_changes:
                        try:
                            # Auto-save settings
                            preferences = self._user_preferences_db.get_user_preferences(self.user_id) or {}
                            preferences['chat_settings'] = self._current_settings.copy()
                            self._user_preferences_db.save_user_preferences(preferences, self.user_id)

                            self._original_settings = self._current_settings.copy()
                            self._has_unsaved_changes = False
                            self._update_action_bar_state()
                            self._update_status("Settings auto-saved", success=True)

                        except Exception as e:
                            self._logger.error(f"Auto-save failed: {e}")

            self._auto_save_task = asyncio.create_task(auto_save_loop())
        except RuntimeError as e:
            # No event loop available - auto-save will be disabled
            self._logger.warning(f"Auto-save disabled: {e}")
            self._auto_save_task = None

    def get_current_settings(self) -> Dict[str, Any]:
        """Get current settings dictionary."""
        return self._current_settings.copy()

    def apply_settings(self, settings: Dict[str, Any]) -> None:
        """Apply settings from external source."""
        self._current_settings.update(settings)
        self._has_unsaved_changes = True
        self._update_action_bar_state()
        self._rebuild_settings_ui()

    def cleanup(self) -> None:
        """Cleanup resources."""
        if self._auto_save_task:
            self._auto_save_task.cancel()

        if hasattr(self, '_validation_timer'):
            self._validation_timer.cancel()
