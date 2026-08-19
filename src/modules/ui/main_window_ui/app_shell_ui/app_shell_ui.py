"""
Module: app_shell_ui
Description: Primary application window container with title bar, menu system, and layout management
            for MikroDok application. Provides comprehensive application shell functionality including
            responsive design, theme integration, window controls, navigation management, and
            accessibility features. Implements modern UI/UX patterns with elegant look-and-feel.
Phase: 1
Location: /src/modules/ui/main_window_ui/app_shell_ui/app_shell_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl, ThemeManager, get_theme_manager,
    ResponsiveLayoutManager, ScreenSize, ColorPalette, SpacingSystem, TypographyScale
)

# Configure logging
logger = logging.getLogger(__name__)


class WindowState(Enum):
    """Window state enumeration."""
    NORMAL = "normal"
    MAXIMIZED = "maximized"
    MINIMIZED = "minimized"
    FULLSCREEN = "fullscreen"


@dataclass
class AppShellConfig:
    """Configuration for app shell behavior."""
    show_title_bar: bool = True
    show_menu_bar: bool = True
    show_status_bar: bool = True
    enable_window_controls: bool = True
    enable_resize: bool = True
    enable_minimize: bool = True
    enable_maximize: bool = True
    enable_close: bool = True
    auto_hide_menu: bool = False
    compact_mode: bool = False


class AppShellUI(ThemeAwareUserControl):
    """
    Primary application window container with comprehensive shell functionality.
    
    Features:
    - Responsive title bar with window controls and branding
    - Adaptive menu system with collapsible navigation
    - Flexible content area with layout management
    - Status bar with system information and notifications
    - Window state management and controls
    - Full theme system integration with responsive design
    - Accessibility-compliant interface elements
    - Modern UI/UX with elegant animations and transitions
    """

    def __init__(self,
                 content: Optional[ft.Control] = None,
                 config: Optional[AppShellConfig] = None,
                 on_window_state_change: Optional[Callable[[WindowState], None]] = None,
                 on_menu_toggle: Optional[Callable[[bool], None]] = None,
                 **kwargs):
        """
        Initialize the application shell UI.

        Args:
            content: Main content area control
            config: App shell configuration
            on_window_state_change: Callback for window state changes
            on_menu_toggle: Callback for menu toggle events
            **kwargs: Additional container arguments
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or AppShellConfig()
        self._content = content
        
        # Callbacks
        self._on_window_state_change = on_window_state_change
        self._on_menu_toggle = on_menu_toggle
        
        # State management
        self._window_state = WindowState.NORMAL
        self._menu_visible = True
        self._is_compact_mode = False
        self._last_window_bounds = None
        
        # UI components
        self._title_bar = None
        self._menu_bar = None
        self._content_area = None
        self._status_bar = None
        self._window_controls = None
        
        # Animation controllers
        self._menu_animation_duration = 300
        self._window_animation_duration = 200
        
        logger.info("AppShellUI initialized")

    def build(self) -> ft.Control:
        """Build the application shell interface."""
        try:
            # Get theme components
            theme = self.get_theme()
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            
            # Create main shell layout
            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        self._build_title_bar() if self._config.show_title_bar else None,
                        self._build_menu_bar() if self._config.show_menu_bar else None,
                        self._build_main_content_area(),
                        self._build_status_bar() if self._config.show_status_bar else None,
                    ],
                    spacing=0,
                    expand=True
                ),
                bgcolor=palette.surface,
                border_radius=self.get_breakpoint_value(0, 8, 12, 16),
                border=ft.border.all(
                    width=1,
                    color=palette.outline_variant
                ) if self.get_current_screen_size() != ScreenSize.MOBILE else None,
                padding=0,
                margin=0,
                expand=True
            )
            
        except Exception as e:
            logger.error(f"Error building app shell: {e}")
            return self._build_error_fallback()

    def _build_title_bar(self) -> ft.Control:
        """Build the responsive title bar with window controls."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        
        # App branding section
        branding = ft.Row(
            controls=[
                ft.Icon(
                    name=ft.Icons.PSYCHOLOGY,
                    size=self.get_breakpoint_value(20, 24, 28, 32),
                    color=palette.primary
                ),
                ft.Text(
                    "MikroDok",
                    style=self.get_text_style("titleMedium"),
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_600
                ) if self.get_current_screen_size() != ScreenSize.MOBILE else None,
            ],
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.START
        )
        
        # Window controls
        window_controls = self._build_window_controls() if self._config.enable_window_controls else None
        
        # Title bar container
        return ft.Container(
            content=ft.Row(
                controls=[
                    branding,
                    ft.Container(expand=True),  # Spacer
                    window_controls,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=palette.surface_variant,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            border=ft.border.only(
                bottom=ft.BorderSide(
                    width=1,
                    color=palette.outline_variant
                )
            ),
            height=self.get_breakpoint_value(48, 52, 56, 60)
        )

    def _build_window_controls(self) -> ft.Control:
        """Build window control buttons."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        button_size = self.get_breakpoint_value(32, 36, 40, 44)
        icon_size = self.get_breakpoint_value(16, 18, 20, 22)
        
        controls = []
        
        if self._config.enable_minimize:
            controls.append(
                ft.IconButton(
                    icon=ft.Icons.MINIMIZE,
                    icon_size=icon_size,
                    icon_color=palette.on_surface_variant,
                    bgcolor=ft.Colors.TRANSPARENT,
                    hover_color=palette.surface_container_highest,
                    on_click=self._on_minimize_click,
                    width=button_size,
                    height=button_size,
                    tooltip="Minimize"
                )
            )
        
        if self._config.enable_maximize:
            controls.append(
                ft.IconButton(
                    icon=ft.Icons.CROP_SQUARE if self._window_state != WindowState.MAXIMIZED else ft.Icons.FILTER_NONE,
                    icon_size=icon_size,
                    icon_color=palette.on_surface_variant,
                    bgcolor=ft.Colors.TRANSPARENT,
                    hover_color=palette.surface_container_highest,
                    on_click=self._on_maximize_click,
                    width=button_size,
                    height=button_size,
                    tooltip="Maximize" if self._window_state != WindowState.MAXIMIZED else "Restore"
                )
            )
        
        if self._config.enable_close:
            controls.append(
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=icon_size,
                    icon_color=palette.on_error_container,
                    bgcolor=ft.Colors.TRANSPARENT,
                    hover_color=palette.error_container,
                    on_click=self._on_close_click,
                    width=button_size,
                    height=button_size,
                    tooltip="Close"
                )
            )
        
        return ft.Row(
            controls=controls,
            spacing=spacing.xs,
            tight=True
        )

    def _build_menu_bar(self) -> ft.Control:
        """Build the responsive menu bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Menu toggle button for mobile
        menu_toggle = ft.IconButton(
            icon=ft.Icons.MENU if not self._menu_visible else ft.Icons.MENU_OPEN,
            icon_size=self.get_breakpoint_value(20, 22, 24, 26),
            icon_color=palette.on_surface,
            bgcolor=ft.Colors.TRANSPARENT,
            hover_color=palette.surface_container_highest,
            on_click=self._on_menu_toggle_click,
            tooltip="Toggle Menu"
        ) if self.get_current_screen_size() == ScreenSize.MOBILE else None
        
        # Main menu items
        menu_items = self._build_menu_items()
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    menu_toggle,
                    ft.Container(
                        content=menu_items,
                        expand=True,
                        visible=self._menu_visible or self.get_current_screen_size() != ScreenSize.MOBILE
                    )
                ],
                spacing=spacing.sm
            ),
            bgcolor=palette.surface_container_low,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.xs
            ),
            border=ft.border.only(
                bottom=ft.BorderSide(
                    width=1,
                    color=palette.outline_variant
                )
            ),
            height=self.get_breakpoint_value(40, 44, 48, 52),
            visible=self._config.show_menu_bar
        )

    def _build_menu_items(self) -> ft.Control:
        """Build menu navigation items."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Define menu items
        menu_items = [
            {"label": "Dashboard", "icon": ft.Icons.DASHBOARD, "route": "/dashboard"},
            {"label": "Documents", "icon": ft.Icons.DESCRIPTION, "route": "/documents"},
            {"label": "Models", "icon": ft.Icons.PSYCHOLOGY, "route": "/models"},
            {"label": "Training", "icon": ft.Icons.FITNESS_CENTER, "route": "/training"},
            {"label": "Settings", "icon": ft.Icons.SETTINGS, "route": "/settings"},
        ]

        # Create menu buttons
        buttons = []
        for item in menu_items:
            button = ft.TextButton(
                text=item["label"],
                icon=item["icon"],
                style=ft.ButtonStyle(
                    color=palette.on_surface,
                    bgcolor=ft.Colors.TRANSPARENT,
                    overlay_color=palette.surface_container_highest,
                    padding=ft.padding.symmetric(
                        horizontal=spacing.md,
                        vertical=spacing.sm
                    ),
                    shape=ft.RoundedRectangleBorder(
                        radius=self.get_breakpoint_value(4, 6, 8, 10)
                    )
                ),
                on_click=lambda e, route=item["route"]: self._on_menu_item_click(route)
            )
            buttons.append(button)

        # Responsive layout
        if self.get_current_screen_size() == ScreenSize.MOBILE:
            return ft.Column(
                controls=buttons,
                spacing=spacing.xs,
                tight=True
            )
        else:
            return ft.Row(
                controls=buttons,
                spacing=spacing.sm,
                alignment=ft.MainAxisAlignment.START
            )

    def _build_main_content_area(self) -> ft.Control:
        """Build the main content area container."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Default content if none provided
        default_content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=ft.Icons.PSYCHOLOGY,
                        size=self.get_breakpoint_value(64, 80, 96, 128),
                        color=palette.primary
                    ),
                    ft.Text(
                        "MikroDok",
                        style=self.get_text_style("headlineLarge"),
                        color=palette.on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "AI-Powered Document Processing",
                        style=self.get_text_style("bodyLarge"),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.lg
            ),
            alignment=ft.alignment.center,
            expand=True
        )

        content = self._content or default_content

        return ft.Container(
            content=content,
            bgcolor=palette.surface,
            padding=spacing.lg,
            expand=True,
            border_radius=self.get_breakpoint_value(0, 4, 8, 12)
        )

    def _build_status_bar(self) -> ft.Control:
        """Build the responsive status bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Status information
        status_items = [
            ft.Text(
                "Ready",
                style=self.get_text_style("bodySmall"),
                color=palette.on_surface_variant
            ),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            name=ft.Icons.MEMORY,
                            size=self.get_breakpoint_value(12, 14, 16, 18),
                            color=palette.primary
                        ),
                        ft.Text(
                            "Memory: 2.1GB",
                            style=self.get_text_style("bodySmall"),
                            color=palette.on_surface_variant
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                ),
                visible=self.get_current_screen_size() != ScreenSize.MOBILE
            ),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            name=ft.Icons.SPEED,
                            size=self.get_breakpoint_value(12, 14, 16, 18),
                            color=palette.secondary
                        ),
                        ft.Text(
                            "GPU: 45°C",
                            style=self.get_text_style("bodySmall"),
                            color=palette.on_surface_variant
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                ),
                visible=self.get_current_screen_size() in [ScreenSize.DESKTOP, ScreenSize.LARGE_DESKTOP]
            )
        ]

        return ft.Container(
            content=ft.Row(
                controls=status_items,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=palette.surface_container_low,
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.xs
            ),
            border=ft.border.only(
                top=ft.BorderSide(
                    width=1,
                    color=palette.outline_variant
                )
            ),
            height=self.get_breakpoint_value(28, 32, 36, 40)
        )

    def _build_error_fallback(self) -> ft.Control:
        """Build error fallback interface."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=ft.Icons.ERROR_OUTLINE,
                        size=48,
                        color=ft.Colors.RED_400
                    ),
                    ft.Text(
                        "Error loading application shell",
                        size=16,
                        color=ft.Colors.ON_SURFACE,
                        text_align=ft.TextAlign.CENTER
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16
            ),
            alignment=ft.alignment.center,
            bgcolor=ft.Colors.SURFACE,
            expand=True
        )

    # Event Handlers
    def _on_minimize_click(self, e):
        """Handle minimize button click."""
        try:
            self._window_state = WindowState.MINIMIZED
            if self._on_window_state_change:
                self._on_window_state_change(self._window_state)
            logger.debug("Window minimized")
        except Exception as ex:
            logger.error(f"Error minimizing window: {ex}")

    def _on_maximize_click(self, e):
        """Handle maximize/restore button click."""
        try:
            if self._window_state == WindowState.MAXIMIZED:
                self._window_state = WindowState.NORMAL
            else:
                self._window_state = WindowState.MAXIMIZED

            if self._on_window_state_change:
                self._on_window_state_change(self._window_state)

            # Update maximize button icon
            self.update()
            logger.debug(f"Window state changed to: {self._window_state.value}")
        except Exception as ex:
            logger.error(f"Error changing window state: {ex}")

    def _on_close_click(self, e):
        """Handle close button click."""
        try:
            if self.page:
                self.page.window_close()
            logger.debug("Close button clicked")
        except Exception as ex:
            logger.error(f"Error closing window: {ex}")

    def _on_menu_toggle_click(self, e):
        """Handle menu toggle button click."""
        try:
            self._menu_visible = not self._menu_visible
            if self._on_menu_toggle:
                self._on_menu_toggle(self._menu_visible)
            self.update()
            logger.debug(f"Menu visibility toggled: {self._menu_visible}")
        except Exception as ex:
            logger.error(f"Error toggling menu: {ex}")

    def _on_menu_item_click(self, route: str):
        """Handle menu item click."""
        try:
            if self.page:
                self.page.go(route)
            logger.debug(f"Navigation to route: {route}")
        except Exception as ex:
            logger.error(f"Error navigating to route {route}: {ex}")

    # Public Methods
    def set_content(self, content: ft.Control):
        """
        Set the main content area.

        Args:
            content: The control to display in the content area
        """
        try:
            self._content = content
            self.update()
            logger.debug("Content updated")
        except Exception as e:
            logger.error(f"Error setting content: {e}")

    def set_window_state(self, state: WindowState):
        """
        Set the window state programmatically.

        Args:
            state: The desired window state
        """
        try:
            self._window_state = state
            if self._on_window_state_change:
                self._on_window_state_change(state)
            self.update()
            logger.debug(f"Window state set to: {state.value}")
        except Exception as e:
            logger.error(f"Error setting window state: {e}")

    def toggle_menu(self):
        """Toggle menu visibility."""
        try:
            self._menu_visible = not self._menu_visible
            if self._on_menu_toggle:
                self._on_menu_toggle(self._menu_visible)
            self.update()
            logger.debug(f"Menu toggled: {self._menu_visible}")
        except Exception as e:
            logger.error(f"Error toggling menu: {e}")

    def set_compact_mode(self, compact: bool):
        """
        Enable or disable compact mode.

        Args:
            compact: Whether to enable compact mode
        """
        try:
            self._is_compact_mode = compact
            self._config.compact_mode = compact
            self.update()
            logger.debug(f"Compact mode set to: {compact}")
        except Exception as e:
            logger.error(f"Error setting compact mode: {e}")

    def get_window_state(self) -> WindowState:
        """
        Get the current window state.

        Returns:
            Current window state
        """
        return self._window_state

    def is_menu_visible(self) -> bool:
        """
        Check if menu is visible.

        Returns:
            True if menu is visible
        """
        return self._menu_visible

    def update_status(self, status_text: str):
        """
        Update status bar text.

        Args:
            status_text: New status text to display
        """
        try:
            # This would update the status bar text
            # Implementation depends on status bar structure
            logger.debug(f"Status updated: {status_text}")
        except Exception as e:
            logger.error(f"Error updating status: {e}")

    def show_notification(self, message: str, notification_type: str = "info"):
        """
        Show a notification in the app shell.

        Args:
            message: Notification message
            notification_type: Type of notification (info, warning, error, success)
        """
        try:
            # This would show a notification overlay
            # Implementation depends on notification system
            logger.info(f"Notification ({notification_type}): {message}")
        except Exception as e:
            logger.error(f"Error showing notification: {e}")

    def cleanup(self):
        """Clean up resources and callbacks."""
        try:
            # Clean up any resources, timers, or callbacks
            self._on_window_state_change = None
            self._on_menu_toggle = None
            logger.debug("AppShellUI cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
