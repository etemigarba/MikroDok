"""
Module: general_settings_ui
Description: Comprehensive general settings interface for MikroDok application with full theme system integration.
            Provides settings for theme preferences, language selection, window configuration, system preferences,
            and application behavior. Features responsive design, accessibility compliance, and real-time validation.

Features:
- Theme and appearance settings with live preview
- Language and localization preferences
- Window and display configuration
- System and performance settings
- Auto-save and backup preferences
- Accessibility options and compliance
- Import/export settings functionality
- Real-time validation and error handling
- Responsive design with breakpoint-aware components
- Full integration with theme system and responsive layout manager

Phase: 1
Location: /src/modules/ui/settings_panel_ui/general_settings_ui/general_settings_ui.py
"""

# Standard library imports
import os
import json
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl, 
    ResponsiveLayoutManager,
    ColorPalette,
    TypographyScale,
    SpacingSystem,
    IconSystem,
    ThemeMode,
    ScreenSize
)


class SettingsCategory(Enum):
    """Settings categories for organization."""
    GENERAL = "general"
    APPEARANCE = "appearance"
    LANGUAGE = "language"
    WINDOW = "window"
    SYSTEM = "system"
    ACCESSIBILITY = "accessibility"
    ADVANCED = "advanced"


class ThemePreference(Enum):
    """Theme preference options."""
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"


class LanguageOption(Enum):
    """Supported language options."""
    ENGLISH = ("en", "English")
    SPANISH = ("es", "Español")
    FRENCH = ("fr", "Français")
    GERMAN = ("de", "Deutsch")
    ITALIAN = ("it", "Italiano")
    PORTUGUESE = ("pt", "Português")
    RUSSIAN = ("ru", "Русский")
    CHINESE = ("zh", "中文")
    JAPANESE = ("ja", "日本語")
    KOREAN = ("ko", "한국어")

    def __init__(self, code: str, display_name: str):
        self.code = code
        self.display_name = display_name


class FontSizeOption(Enum):
    """Font size options."""
    SMALL = ("small", "Small (12px)")
    MEDIUM = ("medium", "Medium (14px)")
    LARGE = ("large", "Large (16px)")
    EXTRA_LARGE = ("extra_large", "Extra Large (18px)")

    def __init__(self, size_value: str, display_name: str):
        self.size_value = size_value
        self.display_name = display_name


@dataclass
class GeneralSettingsConfig:
    """Configuration for general settings interface."""
    # Display settings
    show_advanced_options: bool = False
    enable_real_time_validation: bool = True
    enable_auto_save: bool = True
    auto_save_interval: int = 30  # seconds
    enable_tooltips: bool = True
    enable_import_export: bool = True
    
    # Categories to show
    visible_categories: List[SettingsCategory] = None
    
    # Validation settings
    validate_on_change: bool = True
    show_validation_errors: bool = True
    
    # Performance settings
    debounce_delay: int = 300  # milliseconds
    max_history_entries: int = 50

    def __post_init__(self):
        if self.visible_categories is None:
            self.visible_categories = [
                SettingsCategory.GENERAL,
                SettingsCategory.APPEARANCE,
                SettingsCategory.LANGUAGE,
                SettingsCategory.WINDOW,
                SettingsCategory.SYSTEM,
                SettingsCategory.ACCESSIBILITY
            ]


@dataclass
class SettingsData:
    """Data structure for general settings."""
    # General settings
    app_name: str = "MikroDok"
    app_version: str = "1.0.0"
    enable_auto_save: bool = True
    auto_save_interval: int = 30
    enable_notifications: bool = True
    enable_sound_effects: bool = True
    
    # Appearance settings
    theme_preference: str = "system"
    font_size: str = "medium"
    enable_animations: bool = True
    enable_transparency: bool = True
    compact_mode: bool = False
    
    # Language settings
    language: str = "en"
    date_format: str = "MM/DD/YYYY"
    time_format: str = "12h"
    number_format: str = "1,234.56"
    
    # Window settings
    window_width: int = 1280
    window_height: int = 720
    remember_window_position: bool = True
    start_maximized: bool = False
    minimize_to_tray: bool = True
    close_to_tray: bool = False
    
    # System settings
    debug_mode: bool = False
    log_level: str = "INFO"
    enable_telemetry: bool = False
    check_for_updates: bool = True
    data_directory: str = "./data"
    temp_directory: str = "./temp"
    
    # Accessibility settings
    high_contrast_mode: bool = False
    reduce_motion: bool = False
    screen_reader_support: bool = False
    keyboard_navigation: bool = True
    focus_indicators: bool = True
    large_cursor: bool = False


class GeneralSettingsUI(ThemeAwareUserControl):
    """
    Comprehensive general settings interface with full theme system integration.
    
    Provides a modern, responsive settings interface with:
    - Tabbed organization of settings categories
    - Real-time validation and error handling
    - Auto-save functionality with debouncing
    - Import/export capabilities
    - Accessibility compliance
    - Responsive design with breakpoint-aware components
    - Full theme system integration
    """

    def __init__(self, 
                 config: Optional[GeneralSettingsConfig] = None,
                 initial_settings: Optional[SettingsData] = None,
                 on_settings_changed: Optional[Callable[[SettingsData], None]] = None,
                 **kwargs):
        """
        Initialize the general settings UI.

        Args:
            config: Configuration for the settings interface
            initial_settings: Initial settings data
            on_settings_changed: Callback for settings changes
            **kwargs: Additional arguments for ThemeAwareUserControl
        """
        super().__init__(**kwargs)
        
        # Configuration
        self.config = config or GeneralSettingsConfig()
        self._current_settings = initial_settings or SettingsData()
        self._on_settings_changed = on_settings_changed
        
        # State management
        self._settings_history: List[SettingsData] = []
        self._current_history_index = -1
        self._has_unsaved_changes = False
        self._validation_errors: Dict[str, str] = {}
        self._auto_save_timer = None
        
        # UI components
        self._tabs: Optional[ft.Tabs] = None
        self._validation_panel: Optional[ft.Container] = None
        self._action_bar: Optional[ft.Container] = None
        self._status_bar: Optional[ft.Container] = None
        
        # Responsive layout manager
        self._responsive_manager: Optional[ResponsiveLayoutManager] = None
        
        # Build UI
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the general settings interface."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Initialize responsive manager
        self._responsive_manager = self.get_responsive_layout_manager()
        
        # Main container with responsive design
        self.content = ft.Column(
            controls=[
                self._create_header(),
                self._create_tabs(),
                self._create_validation_panel(),
                self._create_action_bar(),
                self._create_status_bar()
            ],
            spacing=spacing.md,
            expand=True
        )
        
        # Apply theme-aware styling
        self.bgcolor = palette.surface
        self.border_radius = self.get_responsive_value(8, 10, 12, 14)
        self.padding = self.get_responsive_padding(
            mobile=spacing.md,
            tablet=spacing.lg,
            desktop=spacing.xl
        )
        
        # Initialize settings history
        self._add_to_history(self._current_settings)
        
        # Start auto-save if enabled
        if self.config.enable_auto_save:
            self._start_auto_save()

    def _create_header(self) -> ft.Container:
        """Create the settings header."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()
        
        # Title and description
        title = ft.Text(
            "General Settings",
            style=typography.h2,
            color=palette.text_primary,
            weight=ft.FontWeight.W_600
        )
        
        description = ft.Text(
            "Configure general application preferences, appearance, and system settings",
            style=typography.body_medium,
            color=palette.text_secondary
        )
        
        # Action buttons
        action_buttons = ft.Row(
            controls=[
                self._create_icon_button(
                    icons.REFRESH,
                    "Reset to defaults",
                    self._reset_to_defaults
                ),
                self._create_icon_button(
                    icons.DOWNLOAD,
                    "Import settings",
                    self._import_settings
                ),
                self._create_icon_button(
                    icons.UPLOAD,
                    "Export settings",
                    self._export_settings
                )
            ],
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.END
        )
        
        # Header layout
        header_content = ft.Row(
            controls=[
                ft.Column(
                    controls=[title, description],
                    spacing=spacing.xs,
                    expand=True
                ),
                action_buttons
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.START
        )
        
        return ft.Container(
            content=header_content,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline)
        )

    def _create_tabs(self) -> ft.Container:
        """Create the main tabs interface."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create tabs based on visible categories
        tab_controls = []

        if SettingsCategory.GENERAL in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="General",
                    icon=ft.Icons.SETTINGS,
                    content=self._create_general_tab()
                )
            )

        if SettingsCategory.APPEARANCE in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Appearance",
                    icon=ft.Icons.PALETTE,
                    content=self._create_appearance_tab()
                )
            )

        if SettingsCategory.LANGUAGE in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Language",
                    icon=ft.Icons.LANGUAGE,
                    content=self._create_language_tab()
                )
            )

        if SettingsCategory.WINDOW in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Window",
                    icon=ft.Icons.WINDOW,
                    content=self._create_window_tab()
                )
            )

        if SettingsCategory.SYSTEM in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="System",
                    icon=ft.Icons.COMPUTER,
                    content=self._create_system_tab()
                )
            )

        if SettingsCategory.ACCESSIBILITY in self.config.visible_categories:
            tab_controls.append(
                ft.Tab(
                    text="Accessibility",
                    icon=ft.Icons.ACCESSIBILITY,
                    content=self._create_accessibility_tab()
                )
            )

        # Create tabs control
        self._tabs = ft.Tabs(
            tabs=tab_controls,
            selected_index=0,
            animation_duration=200,
            tab_alignment=ft.TabAlignment.START,
            expand=True
        )

        return ft.Container(
            content=self._tabs,
            bgcolor=palette.surface,
            border_radius=self.get_responsive_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline),
            expand=True
        )

    def _create_general_tab(self) -> ft.Container:
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
                    self._current_settings.enable_auto_save
                ),
                self._create_slider_setting(
                    "auto_save_interval",
                    "Auto-Save Interval (seconds)",
                    "How often to save settings automatically",
                    self._current_settings.auto_save_interval,
                    min_value=10,
                    max_value=300,
                    divisions=29
                )
            ]
        )

        # Notification settings
        notification_section = self._create_settings_section(
            "Notifications",
            [
                self._create_switch_setting(
                    "enable_notifications",
                    "Enable Notifications",
                    "Show system notifications",
                    self._current_settings.enable_notifications
                ),
                self._create_switch_setting(
                    "enable_sound_effects",
                    "Enable Sound Effects",
                    "Play sound effects for notifications",
                    self._current_settings.enable_sound_effects
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[auto_save_section, notification_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_appearance_tab(self) -> ft.Container:
        """Create the appearance settings tab."""
        spacing = self.get_spacing()

        # Theme settings
        theme_section = self._create_settings_section(
            "Theme",
            [
                self._create_dropdown_setting(
                    "theme_preference",
                    "Theme Preference",
                    "Choose your preferred color theme",
                    [
                        ("System", "system"),
                        ("Light", "light"),
                        ("Dark", "dark"),
                        ("High Contrast", "high_contrast")
                    ],
                    self._current_settings.theme_preference
                ),
                self._create_dropdown_setting(
                    "font_size",
                    "Font Size",
                    "Choose your preferred font size",
                    [(font.display_name, font.size_value) for font in FontSizeOption],
                    self._current_settings.font_size
                )
            ]
        )

        # Visual effects settings
        effects_section = self._create_settings_section(
            "Visual Effects",
            [
                self._create_switch_setting(
                    "enable_animations",
                    "Enable Animations",
                    "Use smooth animations in the interface",
                    self._current_settings.enable_animations
                ),
                self._create_switch_setting(
                    "enable_transparency",
                    "Enable Transparency",
                    "Use transparency effects where supported",
                    self._current_settings.enable_transparency
                ),
                self._create_switch_setting(
                    "compact_mode",
                    "Compact Mode",
                    "Use a more compact interface layout",
                    self._current_settings.compact_mode
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[theme_section, effects_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_language_tab(self) -> ft.Container:
        """Create the language settings tab."""
        spacing = self.get_spacing()

        # Language settings
        language_section = self._create_settings_section(
            "Language & Localization",
            [
                self._create_dropdown_setting(
                    "language",
                    "Language",
                    "Choose your preferred language",
                    [(lang.display_name, lang.code) for lang in LanguageOption],
                    self._current_settings.language
                ),
                self._create_dropdown_setting(
                    "date_format",
                    "Date Format",
                    "Choose your preferred date format",
                    [
                        ("MM/DD/YYYY", "MM/DD/YYYY"),
                        ("DD/MM/YYYY", "DD/MM/YYYY"),
                        ("YYYY-MM-DD", "YYYY-MM-DD"),
                        ("DD.MM.YYYY", "DD.MM.YYYY")
                    ],
                    self._current_settings.date_format
                ),
                self._create_dropdown_setting(
                    "time_format",
                    "Time Format",
                    "Choose your preferred time format",
                    [
                        ("12-hour (AM/PM)", "12h"),
                        ("24-hour", "24h")
                    ],
                    self._current_settings.time_format
                ),
                self._create_dropdown_setting(
                    "number_format",
                    "Number Format",
                    "Choose your preferred number format",
                    [
                        ("1,234.56 (US)", "1,234.56"),
                        ("1.234,56 (EU)", "1.234,56"),
                        ("1 234,56 (FR)", "1 234,56"),
                        ("1'234.56 (CH)", "1'234.56")
                    ],
                    self._current_settings.number_format
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[language_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_window_tab(self) -> ft.Container:
        """Create the window settings tab."""
        spacing = self.get_spacing()

        # Window size settings
        size_section = self._create_settings_section(
            "Window Size",
            [
                self._create_number_setting(
                    "window_width",
                    "Window Width (pixels)",
                    "Default window width",
                    self._current_settings.window_width,
                    min_value=800,
                    max_value=3840
                ),
                self._create_number_setting(
                    "window_height",
                    "Window Height (pixels)",
                    "Default window height",
                    self._current_settings.window_height,
                    min_value=600,
                    max_value=2160
                )
            ]
        )

        # Window behavior settings
        behavior_section = self._create_settings_section(
            "Window Behavior",
            [
                self._create_switch_setting(
                    "remember_window_position",
                    "Remember Window Position",
                    "Restore window position on startup",
                    self._current_settings.remember_window_position
                ),
                self._create_switch_setting(
                    "start_maximized",
                    "Start Maximized",
                    "Start the application in maximized window",
                    self._current_settings.start_maximized
                ),
                self._create_switch_setting(
                    "minimize_to_tray",
                    "Minimize to System Tray",
                    "Minimize to system tray instead of taskbar",
                    self._current_settings.minimize_to_tray
                ),
                self._create_switch_setting(
                    "close_to_tray",
                    "Close to System Tray",
                    "Close to system tray instead of exiting",
                    self._current_settings.close_to_tray
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[size_section, behavior_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_system_tab(self) -> ft.Container:
        """Create the system settings tab."""
        spacing = self.get_spacing()

        # Debug and logging settings
        debug_section = self._create_settings_section(
            "Debug & Logging",
            [
                self._create_switch_setting(
                    "debug_mode",
                    "Debug Mode",
                    "Enable debug mode for troubleshooting",
                    self._current_settings.debug_mode
                ),
                self._create_dropdown_setting(
                    "log_level",
                    "Log Level",
                    "Set the logging verbosity level",
                    [
                        ("Critical", "CRITICAL"),
                        ("Error", "ERROR"),
                        ("Warning", "WARNING"),
                        ("Info", "INFO"),
                        ("Debug", "DEBUG")
                    ],
                    self._current_settings.log_level
                )
            ]
        )

        # Privacy and updates settings
        privacy_section = self._create_settings_section(
            "Privacy & Updates",
            [
                self._create_switch_setting(
                    "enable_telemetry",
                    "Enable Telemetry",
                    "Send anonymous usage data to help improve the application",
                    self._current_settings.enable_telemetry
                ),
                self._create_switch_setting(
                    "check_for_updates",
                    "Check for Updates",
                    "Automatically check for application updates",
                    self._current_settings.check_for_updates
                )
            ]
        )

        # Directory settings
        directory_section = self._create_settings_section(
            "Directories",
            [
                self._create_path_setting(
                    "data_directory",
                    "Data Directory",
                    "Directory for storing application data",
                    self._current_settings.data_directory
                ),
                self._create_path_setting(
                    "temp_directory",
                    "Temporary Directory",
                    "Directory for temporary files",
                    self._current_settings.temp_directory
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[debug_section, privacy_section, directory_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_accessibility_tab(self) -> ft.Container:
        """Create the accessibility settings tab."""
        spacing = self.get_spacing()

        # Visual accessibility settings
        visual_section = self._create_settings_section(
            "Visual Accessibility",
            [
                self._create_switch_setting(
                    "high_contrast_mode",
                    "High Contrast Mode",
                    "Use high contrast colors for better visibility",
                    self._current_settings.high_contrast_mode
                ),
                self._create_switch_setting(
                    "reduce_motion",
                    "Reduce Motion",
                    "Reduce or disable animations and transitions",
                    self._current_settings.reduce_motion
                ),
                self._create_switch_setting(
                    "large_cursor",
                    "Large Cursor",
                    "Use a larger cursor for better visibility",
                    self._current_settings.large_cursor
                )
            ]
        )

        # Navigation accessibility settings
        navigation_section = self._create_settings_section(
            "Navigation Accessibility",
            [
                self._create_switch_setting(
                    "screen_reader_support",
                    "Screen Reader Support",
                    "Enable enhanced screen reader compatibility",
                    self._current_settings.screen_reader_support
                ),
                self._create_switch_setting(
                    "keyboard_navigation",
                    "Keyboard Navigation",
                    "Enable full keyboard navigation support",
                    self._current_settings.keyboard_navigation
                ),
                self._create_switch_setting(
                    "focus_indicators",
                    "Focus Indicators",
                    "Show clear focus indicators for keyboard navigation",
                    self._current_settings.focus_indicators
                )
            ]
        )

        return ft.Container(
            content=ft.Column(
                controls=[visual_section, navigation_section],
                spacing=spacing.lg,
                scroll=ft.ScrollMode.AUTO
            ),
            padding=ft.padding.all(spacing.lg),
            expand=True
        )

    def _create_validation_panel(self) -> ft.Container:
        """Create the validation panel for showing errors and warnings."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        self._validation_panel = ft.Container(
            content=ft.Column(
                controls=[],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=palette.error_container,
            border_radius=self.get_responsive_value(6, 8, 10, 12),
            visible=False
        )

        return self._validation_panel

    def _create_action_bar(self) -> ft.Container:
        """Create the action bar with save, reset, and other actions."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Action buttons
        save_button = ft.ElevatedButton(
            text="Save Settings",
            icon=icons.SAVE,
            on_click=self._save_settings,
            style=ft.ButtonStyle(
                bgcolor=palette.primary,
                color=palette.text_primary
            )
        )

        reset_button = ft.OutlinedButton(
            text="Reset",
            icon=icons.REFRESH,
            on_click=self._reset_to_defaults,
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, palette.outline)
            )
        )

        undo_button = ft.IconButton(
            icon=icons.BACK,
            tooltip="Undo last change",
            on_click=self._undo_changes,
            disabled=self._current_history_index <= 0
        )

        redo_button = ft.IconButton(
            icon=icons.FORWARD,
            tooltip="Redo last change",
            on_click=self._redo_changes,
            disabled=self._current_history_index >= len(self._settings_history) - 1
        )

        # Button layout
        button_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[undo_button, redo_button],
                    spacing=spacing.xs
                ),
                ft.Row(
                    controls=[reset_button, save_button],
                    spacing=spacing.sm
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        self._action_bar = ft.Container(
            content=button_row,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline)
        )

        return self._action_bar

    def _create_status_bar(self) -> ft.Container:
        """Create the status bar showing save status and other information."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        status_text = ft.Text(
            "All settings saved",
            style=typography.caption,
            color=palette.text_secondary
        )

        self._status_bar = ft.Container(
            content=status_text,
            padding=ft.padding.symmetric(horizontal=spacing.lg, vertical=spacing.sm),
            bgcolor=palette.surface,
            border_radius=self.get_responsive_value(4, 6, 8, 10)
        )

        return self._status_bar

    def _create_settings_section(self, title: str, controls: List[ft.Control]) -> ft.Container:
        """Create a settings section with title and controls."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        section_title = ft.Text(
            title,
            style=typography.h4,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        section_content = ft.Column(
            controls=[section_title] + controls,
            spacing=spacing.md
        )

        return ft.Container(
            content=section_content,
            padding=ft.padding.all(spacing.lg),
            bgcolor=palette.surface_variant,
            border_radius=self.get_responsive_value(6, 8, 10, 12),
            border=ft.border.all(1, palette.outline)
        )

    def _create_switch_setting(self, key: str, label: str, description: str, value: bool) -> ft.Container:
        """Create a switch setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label and description
        label_text = ft.Text(
            label,
            style=typography.body_medium,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        description_text = ft.Text(
            description,
            style=typography.caption,
            color=palette.text_secondary
        )

        # Switch control
        switch = ft.Switch(
            value=value,
            active_color=palette.primary,
            on_change=lambda e: self._on_setting_changed(key, e.control.value)
        )

        # Layout
        content = ft.Row(
            controls=[
                ft.Column(
                    controls=[label_text, description_text],
                    spacing=spacing.xs,
                    expand=True
                ),
                switch
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            border_radius=self.get_responsive_value(4, 6, 8, 10)
        )

    def _create_dropdown_setting(self, key: str, label: str, description: str,
                                options: List[Tuple[str, str]], value: str) -> ft.Container:
        """Create a dropdown setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label and description
        label_text = ft.Text(
            label,
            style=typography.body_medium,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        description_text = ft.Text(
            description,
            style=typography.caption,
            color=palette.text_secondary
        )

        # Dropdown control
        dropdown = ft.Dropdown(
            value=value,
            options=[ft.dropdown.Option(key=opt[1], text=opt[0]) for opt in options],
            on_change=lambda e: self._on_setting_changed(key, e.control.value),
            bgcolor=palette.surface,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            width=200
        )

        # Layout
        content = ft.Column(
            controls=[
                ft.Column(
                    controls=[label_text, description_text],
                    spacing=spacing.xs
                ),
                dropdown
            ],
            spacing=spacing.sm
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            border_radius=self.get_responsive_value(4, 6, 8, 10)
        )

    def _create_slider_setting(self, key: str, label: str, description: str,
                              value: int, min_value: int, max_value: int, divisions: int) -> ft.Container:
        """Create a slider setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label and description
        label_text = ft.Text(
            label,
            style=typography.body_medium,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        description_text = ft.Text(
            description,
            style=typography.caption,
            color=palette.text_secondary
        )

        # Value display
        value_text = ft.Text(
            str(value),
            style=typography.body_medium,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        # Slider control
        slider = ft.Slider(
            value=value,
            min=min_value,
            max=max_value,
            divisions=divisions,
            label="{value}",
            active_color=palette.primary,
            inactive_color=palette.outline,
            on_change=lambda e: self._on_slider_changed(key, e.control.value, value_text)
        )

        # Layout
        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[label_text, description_text],
                            spacing=spacing.xs,
                            expand=True
                        ),
                        value_text
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                slider
            ],
            spacing=spacing.sm
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            border_radius=self.get_responsive_value(4, 6, 8, 10)
        )

    def _create_number_setting(self, key: str, label: str, description: str,
                              value: int, min_value: int, max_value: int) -> ft.Container:
        """Create a number input setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Label and description
        label_text = ft.Text(
            label,
            style=typography.body_medium,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        description_text = ft.Text(
            description,
            style=typography.caption,
            color=palette.text_secondary
        )

        # Number input
        number_field = ft.TextField(
            value=str(value),
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=lambda e: self._on_number_changed(key, e.control.value, min_value, max_value),
            bgcolor=palette.surface,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            width=120
        )

        # Layout
        content = ft.Column(
            controls=[
                ft.Column(
                    controls=[label_text, description_text],
                    spacing=spacing.xs
                ),
                number_field
            ],
            spacing=spacing.sm
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            border_radius=self.get_responsive_value(4, 6, 8, 10)
        )

    def _create_path_setting(self, key: str, label: str, description: str, value: str) -> ft.Container:
        """Create a path input setting control."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Label and description
        label_text = ft.Text(
            label,
            style=typography.body_medium,
            color=palette.text_primary,
            weight=ft.FontWeight.W_500
        )

        description_text = ft.Text(
            description,
            style=typography.caption,
            color=palette.text_secondary
        )

        # Path input
        path_field = ft.TextField(
            value=value,
            on_change=lambda e: self._on_setting_changed(key, e.control.value),
            bgcolor=palette.surface,
            border_color=palette.outline,
            focused_border_color=palette.primary,
            expand=True
        )

        # Browse button
        browse_button = ft.IconButton(
            icon=icons.FOLDER_OPEN,
            tooltip="Browse for folder",
            on_click=lambda e: self._browse_for_path(key, path_field)
        )

        # Layout
        content = ft.Column(
            controls=[
                ft.Column(
                    controls=[label_text, description_text],
                    spacing=spacing.xs
                ),
                ft.Row(
                    controls=[path_field, browse_button],
                    spacing=spacing.sm
                )
            ],
            spacing=spacing.sm
        )

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            border_radius=self.get_responsive_value(4, 6, 8, 10)
        )

    def _create_icon_button(self, icon: str, tooltip: str, on_click: Callable) -> ft.IconButton:
        """Create a themed icon button."""
        palette = self.get_palette()

        return ft.IconButton(
            icon=icon,
            tooltip=tooltip,
            on_click=on_click,
            icon_color=palette.text_secondary,
            hover_color=palette.primary,
            style=ft.ButtonStyle(
                shape=ft.CircleBorder(),
                padding=ft.padding.all(8)
            )
        )

    # Event handlers
    def _on_setting_changed(self, key: str, value: Any) -> None:
        """Handle setting value changes."""
        # Update current settings
        setattr(self._current_settings, key, value)
        self._has_unsaved_changes = True

        # Add to history
        self._add_to_history(self._current_settings)

        # Validate if enabled
        if self.config.validate_on_change:
            self._validate_setting(key, value)

        # Trigger auto-save if enabled
        if self.config.enable_auto_save:
            self._schedule_auto_save()

        # Update status
        self._update_status("Settings changed")

        # Notify callback
        if self._on_settings_changed:
            self._on_settings_changed(self._current_settings)

    def _on_slider_changed(self, key: str, value: float, value_text: ft.Text) -> None:
        """Handle slider value changes."""
        int_value = int(value)
        value_text.value = str(int_value)
        value_text.update()
        self._on_setting_changed(key, int_value)

    def _on_number_changed(self, key: str, value: str, min_value: int, max_value: int) -> None:
        """Handle number input changes with validation."""
        try:
            int_value = int(value)
            if min_value <= int_value <= max_value:
                self._on_setting_changed(key, int_value)
                self._clear_validation_error(key)
            else:
                self._set_validation_error(key, f"Value must be between {min_value} and {max_value}")
        except ValueError:
            self._set_validation_error(key, "Please enter a valid number")

    def _browse_for_path(self, key: str, path_field: ft.TextField) -> None:
        """Open file browser for path selection."""
        # This would typically open a file dialog
        # For now, we'll just update the field with a placeholder
        # In a real implementation, you'd use ft.FilePicker
        pass

    def _save_settings(self, e) -> None:
        """Save current settings."""
        try:
            # Validate all settings
            if self._validate_all_settings():
                # Save settings (implementation would depend on your storage system)
                self._has_unsaved_changes = False
                self._update_status("Settings saved successfully")

                # Notify callback
                if self._on_settings_changed:
                    self._on_settings_changed(self._current_settings)
            else:
                self._update_status("Please fix validation errors before saving")
        except Exception as ex:
            self._update_status(f"Error saving settings: {str(ex)}")

    def _reset_to_defaults(self, e) -> None:
        """Reset all settings to default values."""
        self._current_settings = SettingsData()
        self._add_to_history(self._current_settings)
        self._has_unsaved_changes = True
        self._update_status("Settings reset to defaults")
        self._refresh_ui()

    def _undo_changes(self, e) -> None:
        """Undo the last change."""
        if self._current_history_index > 0:
            self._current_history_index -= 1
            self._current_settings = self._settings_history[self._current_history_index]
            self._has_unsaved_changes = True
            self._update_status("Change undone")
            self._refresh_ui()

    def _redo_changes(self, e) -> None:
        """Redo the last undone change."""
        if self._current_history_index < len(self._settings_history) - 1:
            self._current_history_index += 1
            self._current_settings = self._settings_history[self._current_history_index]
            self._has_unsaved_changes = True
            self._update_status("Change redone")
            self._refresh_ui()

    def _import_settings(self, e) -> None:
        """Import settings from file."""
        # This would typically open a file dialog
        # For now, we'll show a placeholder message
        self._update_status("Import functionality would open file dialog")

    def _export_settings(self, e) -> None:
        """Export settings to file."""
        # This would typically open a save dialog
        # For now, we'll show a placeholder message
        self._update_status("Export functionality would open save dialog")

    # Validation methods
    def _validate_setting(self, key: str, value: Any) -> bool:
        """Validate a single setting."""
        # Basic validation logic
        if key == "window_width" and (value < 800 or value > 3840):
            self._set_validation_error(key, "Window width must be between 800 and 3840 pixels")
            return False
        elif key == "window_height" and (value < 600 or value > 2160):
            self._set_validation_error(key, "Window height must be between 600 and 2160 pixels")
            return False
        elif key == "auto_save_interval" and (value < 10 or value > 300):
            self._set_validation_error(key, "Auto-save interval must be between 10 and 300 seconds")
            return False
        else:
            self._clear_validation_error(key)
            return True

    def _validate_all_settings(self) -> bool:
        """Validate all current settings."""
        is_valid = True
        settings_dict = asdict(self._current_settings)

        for key, value in settings_dict.items():
            if not self._validate_setting(key, value):
                is_valid = False

        self._update_validation_panel()
        return is_valid

    def _set_validation_error(self, key: str, message: str) -> None:
        """Set a validation error for a setting."""
        self._validation_errors[key] = message
        self._update_validation_panel()

    def _clear_validation_error(self, key: str) -> None:
        """Clear a validation error for a setting."""
        if key in self._validation_errors:
            del self._validation_errors[key]
            self._update_validation_panel()

    def _update_validation_panel(self) -> None:
        """Update the validation panel with current errors."""
        if not self._validation_panel:
            return

        if self._validation_errors:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()

            error_controls = []
            for key, message in self._validation_errors.items():
                error_row = ft.Row(
                    controls=[
                        ft.Icon(icons.ERROR, color=palette.error, size=16),
                        ft.Text(
                            message,
                            style=typography.caption,
                            color=palette.error
                        )
                    ],
                    spacing=spacing.xs
                )
                error_controls.append(error_row)

            self._validation_panel.content.controls = error_controls
            self._validation_panel.visible = True
        else:
            self._validation_panel.visible = False

        if self._validation_panel.page:
            self._validation_panel.update()

    # Auto-save methods
    def _start_auto_save(self) -> None:
        """Start the auto-save timer."""
        if self.config.enable_auto_save:
            self._schedule_auto_save()

    def _schedule_auto_save(self) -> None:
        """Schedule an auto-save operation."""
        # In a real implementation, you'd use a timer
        # For now, we'll just update the status
        self._update_status("Auto-save scheduled")

    def _perform_auto_save(self) -> None:
        """Perform automatic save of settings."""
        if self._has_unsaved_changes and self._validate_all_settings():
            # Save settings
            self._has_unsaved_changes = False
            self._update_status("Settings auto-saved")

    # History management
    def _add_to_history(self, settings: SettingsData) -> None:
        """Add settings to history."""
        # Create a copy of the settings
        settings_copy = SettingsData(**asdict(settings))

        # Remove any history after current index
        self._settings_history = self._settings_history[:self._current_history_index + 1]

        # Add new settings
        self._settings_history.append(settings_copy)
        self._current_history_index = len(self._settings_history) - 1

        # Limit history size
        if len(self._settings_history) > self.config.max_history_entries:
            self._settings_history.pop(0)
            self._current_history_index -= 1

    # UI update methods
    def _update_status(self, message: str) -> None:
        """Update the status bar message."""
        if self._status_bar and self._status_bar.content:
            self._status_bar.content.value = message
            if self._status_bar.page:
                self._status_bar.update()

    def _refresh_ui(self) -> None:
        """Refresh the entire UI with current settings."""
        # This would rebuild the UI with current settings
        # For now, we'll just update the status
        self._update_status("UI refreshed")
        if self.page:
            self.update()

    # Public methods
    def get_current_settings(self) -> SettingsData:
        """Get the current settings data."""
        return self._current_settings

    def set_settings(self, settings: SettingsData) -> None:
        """Set new settings data."""
        self._current_settings = settings
        self._add_to_history(settings)
        self._refresh_ui()

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self._has_unsaved_changes

    def apply_theme_change(self, theme_mode: ThemeMode) -> None:
        """Handle theme changes from the theme system."""
        # Update the theme preference in settings
        self._current_settings.theme_preference = theme_mode.value
        self._refresh_ui()

    def handle_responsive_change(self, width: int, height: int, screen_size: ScreenSize) -> None:
        """Handle responsive layout changes."""
        # Update responsive layout
        if self._responsive_manager:
            self._responsive_manager.update_window_size(width, height)

        # Refresh UI for new screen size
        self._refresh_ui()
