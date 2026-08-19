"""
Module: tray_icon_ui
Description: System tray icon UI component with context menu, notification integration, and application controls.
            Provides comprehensive system tray functionality including icon state management, context menu system,
            notification display, and desktop integration for the MikroDok application. Implements responsive design
            principles and full theme system integration with accessibility compliance.

Features:
- System tray icon with dynamic state indicators
- Comprehensive context menu with application controls
- Notification system integration for training progress and alerts
- Cross-platform compatibility with Flet framework
- Full theme system integration with responsive design
- Accessibility-compliant interface elements
- Resource monitoring quick access
- Training status indicators and controls

Phase: 1
Location: /src/modules/ui/system_tray_ui/tray_icon_ui/tray_icon_ui.py
"""

# Standard library imports
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import threading
import platform

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    ScreenSize,
    ColorPalette,
    SpacingSystem,
    TypographyScale,
    IconSystem
)

# Configure logging
logger = logging.getLogger(__name__)


class TrayIconState(Enum):
    """System tray icon states."""
    IDLE = "idle"
    TRAINING = "training"
    PROCESSING = "processing"
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    OFFLINE = "offline"


class TrayMenuAction(Enum):
    """System tray context menu actions."""
    SHOW_WINDOW = "show_window"
    HIDE_WINDOW = "hide_window"
    OPEN_DASHBOARD = "open_dashboard"
    OPEN_SETTINGS = "open_settings"
    PAUSE_TRAINING = "pause_training"
    RESUME_TRAINING = "resume_training"
    STOP_TRAINING = "stop_training"
    VIEW_LOGS = "view_logs"
    ABOUT = "about"
    EXIT = "exit"


@dataclass
class TrayNotification:
    """System tray notification configuration."""
    title: str
    message: str
    notification_type: str = "info"  # info, warning, error, success
    duration: int = 5000  # milliseconds
    show_progress: bool = False
    progress_value: float = 0.0
    action_text: Optional[str] = None
    action_callback: Optional[Callable] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TrayIconConfig:
    """System tray icon configuration."""
    enable_notifications: bool = True
    enable_context_menu: bool = True
    enable_double_click: bool = True
    auto_hide_window: bool = False
    show_training_progress: bool = True
    notification_position: str = "bottom_right"  # bottom_right, top_right, etc.
    icon_tooltip: str = "MikroDok - Document Language Model Builder"
    update_interval_ms: int = 1000


class TrayIconUI(ThemeAwareUserControl):
    """
    System tray icon UI component with comprehensive desktop integration.
    
    Features:
    - Dynamic system tray icon with state indicators
    - Context menu with application controls and quick actions
    - Notification system integration for training progress and alerts
    - Cross-platform compatibility with proper fallbacks
    - Full theme system integration with responsive design
    - Accessibility-compliant interface elements
    - Resource monitoring integration and quick access
    - Training status indicators and control actions
    """

    def __init__(
        self,
        config: Optional[TrayIconConfig] = None,
        on_action: Optional[Callable[[TrayMenuAction], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or TrayIconConfig()
        self._on_action = on_action
        
        # State management
        self._current_state = TrayIconState.IDLE
        self._is_window_visible = True
        self._training_progress = 0.0
        self._last_notification: Optional[TrayNotification] = None
        
        # System tray components
        self._system_tray: Optional[ft.SystemTray] = None
        self._context_menu: Optional[ft.MenuBar] = None
        self._notification_queue: List[TrayNotification] = []
        
        # Threading and updates
        self._update_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        
        # Callbacks
        self._state_change_callbacks: List[Callable[[TrayIconState], None]] = []
        self._notification_callbacks: List[Callable[[TrayNotification], None]] = []
        
        # Platform-specific settings
        self._platform = platform.system()
        self._supports_system_tray = self._check_system_tray_support()
        
        logger.debug(f"TrayIconUI initialized with config: {self._config}")

    def build(self) -> ft.Control:
        """Build the system tray UI component."""
        try:
            # Initialize system tray if supported
            if self._supports_system_tray:
                self._initialize_system_tray()
            else:
                logger.warning("System tray not supported on this platform")
                return self._build_fallback_ui()
            
            # Start update timer
            self._start_update_timer()
            
            # Return invisible container as system tray is handled by the OS
            return ft.Container(
                visible=False,
                data="system_tray_container"
            )
            
        except Exception as e:
            logger.error(f"Error building TrayIconUI: {e}")
            return self._build_error_ui()

    def _check_system_tray_support(self) -> bool:
        """Check if system tray is supported on current platform."""
        try:
            # System tray support varies by platform and desktop environment
            if self._platform == "Windows":
                return True
            elif self._platform == "Darwin":  # macOS
                return True
            elif self._platform == "Linux":
                # Linux support depends on desktop environment
                # Most modern DEs support system tray
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error checking system tray support: {e}")
            return False

    def _initialize_system_tray(self) -> None:
        """Initialize the system tray icon and menu."""
        try:
            # Get theme components
            palette = self.get_palette()
            icons = self.get_icons()
            
            # Create system tray icon
            self._system_tray = ft.SystemTray(
                icon=self._get_state_icon(),
                tooltip=self._config.icon_tooltip,
                menu=self._build_context_menu(),
                on_click=self._on_tray_click,
                on_double_click=self._on_tray_double_click if self._config.enable_double_click else None
            )
            
            logger.debug("System tray initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing system tray: {e}")
            self._supports_system_tray = False

    def _build_context_menu(self) -> ft.MenuBar:
        """Build the system tray context menu."""
        try:
            palette = self.get_palette()
            icons = self.get_icons()
            
            menu_items = []
            
            # Window controls
            if self._is_window_visible:
                menu_items.append(
                    ft.MenuItemButton(
                        content=ft.Row([
                            ft.Icon(icons.MINIMIZE, size=16),
                            ft.Text("Hide Window")
                        ]),
                        on_click=lambda _: self._handle_menu_action(TrayMenuAction.HIDE_WINDOW)
                    )
                )
            else:
                menu_items.append(
                    ft.MenuItemButton(
                        content=ft.Row([
                            ft.Icon(icons.MONITOR, size=16),
                            ft.Text("Show Window")
                        ]),
                        on_click=lambda _: self._handle_menu_action(TrayMenuAction.SHOW_WINDOW)
                    )
                )
            
            # Separator
            menu_items.append(ft.Divider())
            
            # Quick actions
            menu_items.extend([
                ft.MenuItemButton(
                    content=ft.Row([
                        ft.Icon(icons.GRID_VIEW, size=16),
                        ft.Text("Open Dashboard")
                    ]),
                    on_click=lambda _: self._handle_menu_action(TrayMenuAction.OPEN_DASHBOARD)
                ),
                ft.MenuItemButton(
                    content=ft.Row([
                        ft.Icon(icons.SETTINGS, size=16),
                        ft.Text("Settings")
                    ]),
                    on_click=lambda _: self._handle_menu_action(TrayMenuAction.OPEN_SETTINGS)
                )
            ])
            
            # Training controls (if training is active)
            if self._current_state == TrayIconState.TRAINING:
                menu_items.extend([
                    ft.Divider(),
                    ft.MenuItemButton(
                        content=ft.Row([
                            ft.Icon(icons.PAUSE, size=16),
                            ft.Text("Pause Training")
                        ]),
                        on_click=lambda _: self._handle_menu_action(TrayMenuAction.PAUSE_TRAINING)
                    ),
                    ft.MenuItemButton(
                        content=ft.Row([
                            ft.Icon(icons.STOP, size=16),
                            ft.Text("Stop Training")
                        ]),
                        on_click=lambda _: self._handle_menu_action(TrayMenuAction.STOP_TRAINING)
                    )
                ])
            
            # System actions
            menu_items.extend([
                ft.Divider(),
                ft.MenuItemButton(
                    content=ft.Row([
                        ft.Icon(icons.DESCRIPTION, size=16),
                        ft.Text("View Logs")
                    ]),
                    on_click=lambda _: self._handle_menu_action(TrayMenuAction.VIEW_LOGS)
                ),
                ft.MenuItemButton(
                    content=ft.Row([
                        ft.Icon(icons.INFO, size=16),
                        ft.Text("About")
                    ]),
                    on_click=lambda _: self._handle_menu_action(TrayMenuAction.ABOUT)
                ),
                ft.Divider(),
                ft.MenuItemButton(
                    content=ft.Row([
                        ft.Icon(icons.LOGOUT, size=16),
                        ft.Text("Exit")
                    ]),
                    on_click=lambda _: self._handle_menu_action(TrayMenuAction.EXIT)
                )
            ])
            
            return ft.MenuBar(controls=menu_items)

        except Exception as e:
            logger.error(f"Error building context menu: {e}")
            return ft.MenuBar(controls=[])

    def _get_state_icon(self) -> str:
        """Get icon based on current state."""
        try:
            icons = self.get_icons()

            state_icons = {
                TrayIconState.IDLE: icons.PSYCHOLOGY,
                TrayIconState.TRAINING: icons.TRAINING,
                TrayIconState.PROCESSING: icons.LOADING,
                TrayIconState.ERROR: icons.ERROR,
                TrayIconState.WARNING: icons.WARNING,
                TrayIconState.SUCCESS: icons.CHECK_CIRCLE,
                TrayIconState.OFFLINE: icons.VISIBILITY_OFF
            }

            return state_icons.get(self._current_state, icons.PSYCHOLOGY)

        except Exception as e:
            logger.error(f"Error getting state icon: {e}")
            return ft.Icons.PSYCHOLOGY

    def _handle_menu_action(self, action: TrayMenuAction) -> None:
        """Handle context menu action."""
        try:
            logger.debug(f"Handling tray menu action: {action}")

            # Update window visibility state for show/hide actions
            if action == TrayMenuAction.SHOW_WINDOW:
                self._is_window_visible = True
            elif action == TrayMenuAction.HIDE_WINDOW:
                self._is_window_visible = False

            # Call external action handler
            if self._on_action:
                self._on_action(action)

            # Update context menu if window visibility changed
            if action in [TrayMenuAction.SHOW_WINDOW, TrayMenuAction.HIDE_WINDOW]:
                self._update_context_menu()

        except Exception as e:
            logger.error(f"Error handling menu action {action}: {e}")

    def _on_tray_click(self, e) -> None:
        """Handle system tray icon click."""
        try:
            logger.debug("System tray icon clicked")

            # Default click behavior - toggle window visibility
            if self._is_window_visible:
                self._handle_menu_action(TrayMenuAction.HIDE_WINDOW)
            else:
                self._handle_menu_action(TrayMenuAction.SHOW_WINDOW)

        except Exception as e:
            logger.error(f"Error handling tray click: {e}")

    def _on_tray_double_click(self, e) -> None:
        """Handle system tray icon double-click."""
        try:
            logger.debug("System tray icon double-clicked")

            # Double-click behavior - open dashboard
            self._handle_menu_action(TrayMenuAction.OPEN_DASHBOARD)

        except Exception as e:
            logger.error(f"Error handling tray double-click: {e}")

    def _start_update_timer(self) -> None:
        """Start the update timer for periodic updates."""
        try:
            if self._update_timer:
                self._update_timer.cancel()

            self._update_timer = threading.Timer(
                self._config.update_interval_ms / 1000.0,
                self._update_tray_icon
            )
            self._update_timer.daemon = True
            self._update_timer.start()

        except Exception as e:
            logger.error(f"Error starting update timer: {e}")

    def _update_tray_icon(self) -> None:
        """Update system tray icon and tooltip."""
        try:
            with self._lock:
                if self._system_tray and self._supports_system_tray:
                    # Update icon based on current state
                    self._system_tray.icon = self._get_state_icon()

                    # Update tooltip with current status
                    tooltip = self._build_dynamic_tooltip()
                    self._system_tray.tooltip = tooltip

                    # Process notification queue
                    self._process_notification_queue()

            # Schedule next update
            self._start_update_timer()

        except Exception as e:
            logger.error(f"Error updating tray icon: {e}")

    def _build_dynamic_tooltip(self) -> str:
        """Build dynamic tooltip based on current state."""
        try:
            base_tooltip = self._config.icon_tooltip

            if self._current_state == TrayIconState.TRAINING:
                return f"{base_tooltip}\nTraining in progress: {self._training_progress:.1f}%"
            elif self._current_state == TrayIconState.PROCESSING:
                return f"{base_tooltip}\nProcessing documents..."
            elif self._current_state == TrayIconState.ERROR:
                return f"{base_tooltip}\nError occurred - check logs"
            elif self._current_state == TrayIconState.WARNING:
                return f"{base_tooltip}\nWarning - attention required"
            elif self._current_state == TrayIconState.SUCCESS:
                return f"{base_tooltip}\nOperation completed successfully"
            elif self._current_state == TrayIconState.OFFLINE:
                return f"{base_tooltip}\nOffline mode"
            else:
                return base_tooltip

        except Exception as e:
            logger.error(f"Error building dynamic tooltip: {e}")
            return self._config.icon_tooltip

    def _update_context_menu(self) -> None:
        """Update the context menu."""
        try:
            if self._system_tray and self._supports_system_tray:
                self._system_tray.menu = self._build_context_menu()

        except Exception as e:
            logger.error(f"Error updating context menu: {e}")

    def _process_notification_queue(self) -> None:
        """Process pending notifications."""
        try:
            if not self._config.enable_notifications or not self._notification_queue:
                return

            # Process one notification at a time
            if self._notification_queue:
                notification = self._notification_queue.pop(0)
                self._show_system_notification(notification)

        except Exception as e:
            logger.error(f"Error processing notification queue: {e}")

    def _show_system_notification(self, notification: TrayNotification) -> None:
        """Show system notification."""
        try:
            if not self._supports_system_tray:
                logger.warning("System notifications not supported")
                return

            # Use system notification if available
            # Note: Flet's system notification support may vary by platform
            logger.info(f"Notification: {notification.title} - {notification.message}")

            # Call notification callbacks
            for callback in self._notification_callbacks:
                try:
                    callback(notification)
                except Exception as e:
                    logger.error(f"Error in notification callback: {e}")

        except Exception as e:
            logger.error(f"Error showing system notification: {e}")

    def _build_fallback_ui(self) -> ft.Control:
        """Build fallback UI when system tray is not supported."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=ft.Icons.INFO,
                            size=48,
                            color=palette.primary
                        ),
                        ft.Text(
                            "System Tray Not Supported",
                            style=self.get_text_style("headlineSmall"),
                            color=palette.on_surface,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            "System tray functionality is not available on this platform.",
                            style=self.get_text_style("bodyMedium"),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.md
                ),
                padding=ft.padding.all(spacing.lg),
                bgcolor=palette.surface_container_low,
                border_radius=self.get_breakpoint_value(8, 10, 12, 14),
                border=ft.border.all(1, palette.outline_variant)
            )

        except Exception as e:
            logger.error(f"Error building fallback UI: {e}")
            return ft.Container()

    def _build_error_ui(self) -> ft.Control:
        """Build error UI when initialization fails."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            name=ft.Icons.ERROR,
                            size=48,
                            color=palette.error
                        ),
                        ft.Text(
                            "System Tray Error",
                            style=self.get_text_style("headlineSmall"),
                            color=palette.on_surface,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            "Failed to initialize system tray functionality.",
                            style=self.get_text_style("bodyMedium"),
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.md
                ),
                padding=ft.padding.all(spacing.lg),
                bgcolor=palette.error_container,
                border_radius=self.get_breakpoint_value(8, 10, 12, 14),
                border=ft.border.all(1, palette.error)
            )

        except Exception as e:
            logger.error(f"Error building error UI: {e}")
            return ft.Container()

    # Public Interface Methods

    def set_state(self, state: TrayIconState) -> None:
        """
        Set the current tray icon state.

        Args:
            state: New tray icon state
        """
        try:
            with self._lock:
                if self._current_state != state:
                    old_state = self._current_state
                    self._current_state = state

                    logger.debug(f"Tray icon state changed: {old_state} -> {state}")

                    # Update icon immediately
                    if self._system_tray and self._supports_system_tray:
                        self._system_tray.icon = self._get_state_icon()
                        self._system_tray.tooltip = self._build_dynamic_tooltip()
                        self._update_context_menu()

                    # Notify state change callbacks
                    for callback in self._state_change_callbacks:
                        try:
                            callback(state)
                        except Exception as e:
                            logger.error(f"Error in state change callback: {e}")

        except Exception as e:
            logger.error(f"Error setting tray icon state: {e}")

    def get_state(self) -> TrayIconState:
        """
        Get the current tray icon state.

        Returns:
            Current tray icon state
        """
        with self._lock:
            return self._current_state

    def set_training_progress(self, progress: float) -> None:
        """
        Set training progress percentage.

        Args:
            progress: Progress percentage (0.0 to 100.0)
        """
        try:
            with self._lock:
                self._training_progress = max(0.0, min(100.0, progress))

                # Update tooltip if in training state
                if self._current_state == TrayIconState.TRAINING:
                    if self._system_tray and self._supports_system_tray:
                        self._system_tray.tooltip = self._build_dynamic_tooltip()

        except Exception as e:
            logger.error(f"Error setting training progress: {e}")

    def get_training_progress(self) -> float:
        """
        Get current training progress.

        Returns:
            Training progress percentage
        """
        with self._lock:
            return self._training_progress

    def show_notification(self, notification: TrayNotification) -> None:
        """
        Show a system tray notification.

        Args:
            notification: Notification to display
        """
        try:
            if not self._config.enable_notifications:
                logger.debug("Notifications disabled, skipping notification")
                return

            with self._lock:
                self._notification_queue.append(notification)
                self._last_notification = notification

            logger.debug(f"Notification queued: {notification.title}")

        except Exception as e:
            logger.error(f"Error showing notification: {e}")

    def show_training_notification(self, progress: float, message: str = "") -> None:
        """
        Show training progress notification.

        Args:
            progress: Training progress percentage
            message: Optional custom message
        """
        try:
            if not message:
                message = f"Training progress: {progress:.1f}%"

            notification = TrayNotification(
                title="Training Update",
                message=message,
                notification_type="info",
                show_progress=True,
                progress_value=progress,
                duration=3000
            )

            self.show_notification(notification)
            self.set_training_progress(progress)

        except Exception as e:
            logger.error(f"Error showing training notification: {e}")

    def show_error_notification(self, title: str, message: str) -> None:
        """
        Show error notification.

        Args:
            title: Error title
            message: Error message
        """
        try:
            notification = TrayNotification(
                title=title,
                message=message,
                notification_type="error",
                duration=8000
            )

            self.show_notification(notification)
            self.set_state(TrayIconState.ERROR)

        except Exception as e:
            logger.error(f"Error showing error notification: {e}")

    def show_success_notification(self, title: str, message: str) -> None:
        """
        Show success notification.

        Args:
            title: Success title
            message: Success message
        """
        try:
            notification = TrayNotification(
                title=title,
                message=message,
                notification_type="success",
                duration=5000
            )

            self.show_notification(notification)
            self.set_state(TrayIconState.SUCCESS)

        except Exception as e:
            logger.error(f"Error showing success notification: {e}")

    def set_window_visibility(self, visible: bool) -> None:
        """
        Set window visibility state.

        Args:
            visible: True if window is visible
        """
        try:
            with self._lock:
                if self._is_window_visible != visible:
                    self._is_window_visible = visible
                    self._update_context_menu()

        except Exception as e:
            logger.error(f"Error setting window visibility: {e}")

    def is_window_visible(self) -> bool:
        """
        Check if window is visible.

        Returns:
            True if window is visible
        """
        with self._lock:
            return self._is_window_visible

    def add_state_change_callback(self, callback: Callable[[TrayIconState], None]) -> None:
        """
        Add state change callback.

        Args:
            callback: Callback function to call on state changes
        """
        try:
            if callback not in self._state_change_callbacks:
                self._state_change_callbacks.append(callback)

        except Exception as e:
            logger.error(f"Error adding state change callback: {e}")

    def remove_state_change_callback(self, callback: Callable[[TrayIconState], None]) -> None:
        """
        Remove state change callback.

        Args:
            callback: Callback function to remove
        """
        try:
            if callback in self._state_change_callbacks:
                self._state_change_callbacks.remove(callback)

        except Exception as e:
            logger.error(f"Error removing state change callback: {e}")

    def add_notification_callback(self, callback: Callable[[TrayNotification], None]) -> None:
        """
        Add notification callback.

        Args:
            callback: Callback function to call on notifications
        """
        try:
            if callback not in self._notification_callbacks:
                self._notification_callbacks.append(callback)

        except Exception as e:
            logger.error(f"Error adding notification callback: {e}")

    def remove_notification_callback(self, callback: Callable[[TrayNotification], None]) -> None:
        """
        Remove notification callback.

        Args:
            callback: Callback function to remove
        """
        try:
            if callback in self._notification_callbacks:
                self._notification_callbacks.remove(callback)

        except Exception as e:
            logger.error(f"Error removing notification callback: {e}")

    def is_supported(self) -> bool:
        """
        Check if system tray is supported.

        Returns:
            True if system tray is supported
        """
        return self._supports_system_tray

    def get_config(self) -> TrayIconConfig:
        """
        Get current configuration.

        Returns:
            Current tray icon configuration
        """
        return self._config

    def update_config(self, config: TrayIconConfig) -> None:
        """
        Update configuration.

        Args:
            config: New configuration
        """
        try:
            with self._lock:
                self._config = config

                # Update system tray tooltip
                if self._system_tray and self._supports_system_tray:
                    self._system_tray.tooltip = self._build_dynamic_tooltip()

        except Exception as e:
            logger.error(f"Error updating config: {e}")

    def cleanup(self) -> None:
        """Clean up resources and stop timers."""
        try:
            logger.debug("Cleaning up TrayIconUI")

            # Stop update timer
            if self._update_timer:
                self._update_timer.cancel()
                self._update_timer = None

            # Clear callbacks
            self._state_change_callbacks.clear()
            self._notification_callbacks.clear()

            # Clear notification queue
            with self._lock:
                self._notification_queue.clear()

            # Clean up system tray
            if self._system_tray:
                self._system_tray = None

            logger.debug("TrayIconUI cleanup completed")

        except Exception as e:
            logger.error(f"Error during TrayIconUI cleanup: {e}")


# Utility functions for creating tray icon instances

def create_tray_icon(
    config: Optional[TrayIconConfig] = None,
    on_action: Optional[Callable[[TrayMenuAction], None]] = None
) -> TrayIconUI:
    """
    Create a new TrayIconUI instance with default configuration.

    Args:
        config: Optional configuration
        on_action: Optional action handler

    Returns:
        Configured TrayIconUI instance
    """
    return TrayIconUI(config=config, on_action=on_action)


def create_default_config() -> TrayIconConfig:
    """
    Create default tray icon configuration.

    Returns:
        Default TrayIconConfig instance
    """
    return TrayIconConfig()


def create_minimal_config() -> TrayIconConfig:
    """
    Create minimal tray icon configuration.

    Returns:
        Minimal TrayIconConfig instance
    """
    return TrayIconConfig(
        enable_notifications=False,
        enable_context_menu=True,
        enable_double_click=False,
        show_training_progress=False
    )
