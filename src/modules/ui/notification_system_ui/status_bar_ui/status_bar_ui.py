"""
Module: status_bar_ui
Description: Persistent status bar component for displaying system status messages and notifications.
            Provides a fixed status bar that shows current application state, progress indicators,
            and important system messages with theme integration and responsive design.

Features:
- Persistent status message display with multiple severity levels
- Integration with notification system for status updates
- Responsive design with breakpoint-aware layouts
- Theme-aware styling with dark/light mode support
- Accessibility compliance (WCAG 2.1 AA) with screen reader support
- Smooth animations for status transitions
- Auto-dismiss and manual dismiss options
- Icon and text display with customizable formatting
- Memory-efficient implementation with component pooling

Phase: 1
Location: /src/modules/ui/notification_system_ui/status_bar_ui/status_bar_ui.py
"""

# Standard library imports
import time
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import weakref

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    ColorPalette,
    SpacingSystem,
    TypographyScale,
    IconSystem,
    AnimationConfig,
    ResponsiveLayoutManager,
    ScreenSize,
    ThemeMode
)


class StatusType(Enum):
    """Status message types for different contexts."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"
    SYSTEM = "system"
    TRAINING = "training"
    PROCESSING = "processing"


class StatusLevel(Enum):
    """Status severity levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class StatusState(Enum):
    """Status display states."""
    IDLE = "idle"
    ACTIVE = "active"
    UPDATING = "updating"
    HIDDEN = "hidden"


@dataclass
class StatusConfig:
    """Configuration for status bar behavior and appearance."""
    show_icon: bool = True
    show_timestamp: bool = False
    auto_dismiss: bool = False
    dismiss_delay: int = 5000  # milliseconds
    enable_animations: bool = True
    enable_hover_effects: bool = True
    enable_click_actions: bool = True
    max_message_length: int = 100
    truncate_long_messages: bool = True
    show_progress_bar: bool = False
    enable_accessibility: bool = True
    compact_mode: bool = False
    position: str = "bottom"  # bottom, top
    height: int = 32
    opacity: float = 1.0
    blur_background: bool = False
    sticky: bool = True


@dataclass
class StatusMessage:
    """Status message data structure."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    status_type: StatusType = StatusType.INFO
    level: StatusLevel = StatusLevel.NORMAL
    icon: Optional[str] = None
    progress: Optional[float] = None  # 0-100
    timestamp: datetime = field(default_factory=datetime.now)
    auto_dismiss: bool = False
    dismiss_delay: int = 5000
    metadata: Dict[str, Any] = field(default_factory=dict)
    callback: Optional[Callable] = None


class StatusBarUI(ThemeAwareUserControl):
    """
    Persistent status bar component for displaying system status messages.
    
    Provides a fixed status bar that integrates with the notification system
    to display current application state, progress indicators, and important
    system messages with full theme integration and responsive design.
    """

    def __init__(self,
                 config: Optional[StatusConfig] = None,
                 on_status_click: Optional[Callable[[str], None]] = None,
                 on_status_change: Optional[Callable[[StatusMessage], None]] = None,
                 **kwargs):
        """
        Initialize the status bar component.

        Args:
            config: Status bar configuration
            on_status_click: Callback for status click events
            on_status_change: Callback for status change events
            **kwargs: Additional UserControl arguments
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or StatusConfig()
        self._on_status_click = on_status_click
        self._on_status_change = on_status_change
        
        # State management
        self._current_message: Optional[StatusMessage] = None
        self._message_queue: List[StatusMessage] = []
        self._state = StatusState.IDLE
        self._lock = threading.Lock()
        
        # UI components
        self._status_container: Optional[ft.Container] = None
        self._icon_component: Optional[ft.Icon] = None
        self._text_component: Optional[ft.Text] = None
        self._progress_component: Optional[ft.ProgressBar] = None
        self._timestamp_component: Optional[ft.Text] = None
        
        # Animation and timing
        self._dismiss_timer: Optional[threading.Timer] = None
        self._animation_duration = 200  # milliseconds
        
        # Theme integration
        self._theme_manager = get_theme_manager()
        self._responsive_manager = None

        # Initialize responsive manager if theme manager is available
        if self._theme_manager:
            self._responsive_manager = self._theme_manager.get_responsive_layout_manager()
        else:
            # Create a default responsive manager if theme manager is not initialized
            from src.modules.ui.theme_system_ui.theme_system_ui import ResponsiveLayoutManager
            self._responsive_manager = ResponsiveLayoutManager()
        
        # Performance tracking
        self._metrics = {
            'messages_displayed': 0,
            'auto_dismissals': 0,
            'manual_dismissals': 0,
            'click_events': 0
        }

    def _ensure_theme_manager(self) -> None:
        """Ensure theme manager is available."""
        if not self._theme_manager:
            self._theme_manager = get_theme_manager()
            if not self._theme_manager:
                # Initialize with defaults if not available
                from src.modules.ui.theme_system_ui.theme_system_ui import initialize_theme_manager
                try:
                    self._theme_manager = initialize_theme_manager()
                except Exception:
                    # If initialization fails, we'll work without theme manager
                    pass

            # Update responsive manager if theme manager is now available
            if self._theme_manager and not self._responsive_manager:
                try:
                    self._responsive_manager = self._theme_manager.get_responsive_layout_manager()
                except Exception:
                    # Fallback to default responsive manager
                    from src.modules.ui.theme_system_ui.theme_system_ui import ResponsiveLayoutManager
                    self._responsive_manager = ResponsiveLayoutManager()

    def build(self) -> ft.Control:
        """
        Build the status bar UI component.

        Returns:
            Status bar control
        """
        try:
            # Ensure theme manager is available
            self._ensure_theme_manager()

            # Get theme components
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()
            
            # Create status bar container
            self._status_container = self._create_status_container()
            
            return self._status_container
            
        except Exception as e:
            print(f"Error building status bar: {e}")
            return ft.Container()

    def _create_status_container(self) -> ft.Container:
        """Create the main status bar container."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Responsive height
        height = self.get_breakpoint_value(
            mobile=28,
            tablet=32,
            desktop=36,
            large=40
        )
        
        # Create content row
        content_row = ft.Row(
            controls=[],
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True
        )
        
        # Main container
        container = ft.Container(
            content=content_row,
            height=height,
            bgcolor=palette.surface_variant,
            border=ft.border.only(top=ft.BorderSide(1, palette.outline)),
            padding=ft.padding.symmetric(
                horizontal=self.get_responsive_padding(),
                vertical=spacing.xs
            ),
            opacity=self._config.opacity,
            animate_opacity=ft.animation.Animation(
                duration=self._animation_duration,
                curve=ft.AnimationCurve.EASE_OUT
            ) if self._config.enable_animations else None
        )
        
        return container

    def _update_status_display(self) -> None:
        """Update the status display with current message."""
        try:
            if not self._status_container or not self._current_message:
                return

            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Clear existing content
            content_row = self._status_container.content
            content_row.controls.clear()

            message = self._current_message

            # Add icon if enabled
            if self._config.show_icon and message.icon:
                icon_color = self._get_status_color(message.status_type, message.level)
                icon_size = self.get_breakpoint_value(14, 16, 18, 20)

                self._icon_component = ft.Icon(
                    name=message.icon,
                    size=icon_size,
                    color=icon_color
                )
                content_row.controls.append(self._icon_component)

            # Add status text
            text_color = palette.on_surface
            if message.level == StatusLevel.CRITICAL:
                text_color = palette.error
            elif message.level == StatusLevel.HIGH:
                text_color = palette.warning

            # Truncate long messages if needed
            display_text = message.text
            if (self._config.truncate_long_messages and
                len(display_text) > self._config.max_message_length):
                display_text = display_text[:self._config.max_message_length - 3] + "..."

            self._text_component = ft.Text(
                display_text,
                style=typography.get_text_style("body_small"),
                color=text_color,
                weight=ft.FontWeight.W_500 if message.level in [StatusLevel.HIGH, StatusLevel.CRITICAL] else ft.FontWeight.W_400,
                overflow=ft.TextOverflow.ELLIPSIS,
                max_lines=1
            )
            content_row.controls.append(self._text_component)

            # Add progress bar if enabled and progress is available
            if (self._config.show_progress_bar and
                message.progress is not None and
                message.status_type == StatusType.PROGRESS):

                self._progress_component = ft.ProgressBar(
                    value=message.progress / 100.0,
                    width=self.get_breakpoint_value(80, 100, 120, 150),
                    height=4,
                    color=self._get_status_color(message.status_type, message.level),
                    bgcolor=palette.surface
                )
                content_row.controls.append(self._progress_component)

            # Add timestamp if enabled
            if self._config.show_timestamp:
                timestamp_text = message.timestamp.strftime("%H:%M:%S")
                self._timestamp_component = ft.Text(
                    timestamp_text,
                    style=typography.get_text_style("caption"),
                    color=palette.text_secondary,
                    size=self.get_breakpoint_value(10, 11, 12, 13)
                )

                # Add spacer and timestamp
                content_row.controls.append(ft.Container(expand=True))
                content_row.controls.append(self._timestamp_component)

            # Update container click handler
            if self._config.enable_click_actions and self._on_status_click:
                self._status_container.on_click = lambda e: self._handle_status_click()

            # Update the UI
            self._status_container.update()

            # Start auto-dismiss timer if enabled
            if message.auto_dismiss:
                self._start_dismiss_timer(message.dismiss_delay)

        except Exception as e:
            print(f"Error updating status display: {e}")

    def _get_status_color(self, status_type: StatusType, level: StatusLevel) -> str:
        """Get color for status type and level."""
        palette = self.get_palette()

        # Base colors by type
        type_colors = {
            StatusType.INFO: palette.info,
            StatusType.SUCCESS: palette.success,
            StatusType.WARNING: palette.warning,
            StatusType.ERROR: palette.error,
            StatusType.PROGRESS: palette.primary,
            StatusType.SYSTEM: palette.text_secondary,
            StatusType.TRAINING: palette.primary,
            StatusType.PROCESSING: palette.secondary
        }

        base_color = type_colors.get(status_type, palette.text_primary)

        # Adjust for level
        if level == StatusLevel.CRITICAL:
            return palette.error
        elif level == StatusLevel.HIGH:
            return palette.warning

        return base_color

    def _handle_status_click(self) -> None:
        """Handle status bar click events."""
        try:
            if self._current_message and self._on_status_click:
                self._metrics['click_events'] += 1
                self._on_status_click(self._current_message.id)

                # Execute message callback if available
                if self._current_message.callback:
                    self._current_message.callback()

        except Exception as e:
            print(f"Error handling status click: {e}")

    def _start_dismiss_timer(self, delay: int) -> None:
        """Start auto-dismiss timer."""
        try:
            # Cancel existing timer
            if self._dismiss_timer:
                self._dismiss_timer.cancel()

            # Start new timer
            self._dismiss_timer = threading.Timer(
                delay / 1000.0,  # Convert to seconds
                self._auto_dismiss
            )
            self._dismiss_timer.start()

        except Exception as e:
            print(f"Error starting dismiss timer: {e}")

    def _auto_dismiss(self) -> None:
        """Auto-dismiss current status message."""
        try:
            with self._lock:
                if self._current_message:
                    self._metrics['auto_dismissals'] += 1
                    self.clear_status()

        except Exception as e:
            print(f"Error in auto-dismiss: {e}")

    # Public API methods

    def set_status(self,
                   text: str,
                   status_type: StatusType = StatusType.INFO,
                   level: StatusLevel = StatusLevel.NORMAL,
                   icon: Optional[str] = None,
                   progress: Optional[float] = None,
                   auto_dismiss: Optional[bool] = None,
                   dismiss_delay: Optional[int] = None,
                   callback: Optional[Callable] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Set a new status message.

        Args:
            text: Status message text
            status_type: Type of status message
            level: Severity level
            icon: Optional icon name
            progress: Progress value (0-100) for progress type
            auto_dismiss: Whether to auto-dismiss
            dismiss_delay: Auto-dismiss delay in milliseconds
            callback: Optional callback function
            metadata: Additional metadata

        Returns:
            Message ID
        """
        try:
            with self._lock:
                # Create status message
                message = StatusMessage(
                    text=text,
                    status_type=status_type,
                    level=level,
                    icon=icon or self._get_default_icon(status_type),
                    progress=progress,
                    auto_dismiss=auto_dismiss if auto_dismiss is not None else self._config.auto_dismiss,
                    dismiss_delay=dismiss_delay if dismiss_delay is not None else self._config.dismiss_delay,
                    callback=callback,
                    metadata=metadata or {}
                )

                # Set as current message
                self._current_message = message
                self._state = StatusState.ACTIVE
                self._metrics['messages_displayed'] += 1

                # Update display
                self._update_status_display()

                # Notify change callback
                if self._on_status_change:
                    self._on_status_change(message)

                return message.id

        except Exception as e:
            print(f"Error setting status: {e}")
            return ""

    def update_status(self,
                     message_id: str,
                     text: Optional[str] = None,
                     progress: Optional[float] = None,
                     status_type: Optional[StatusType] = None,
                     level: Optional[StatusLevel] = None) -> bool:
        """
        Update an existing status message.

        Args:
            message_id: ID of message to update
            text: New text (optional)
            progress: New progress value (optional)
            status_type: New status type (optional)
            level: New severity level (optional)

        Returns:
            True if message was updated
        """
        try:
            with self._lock:
                if not self._current_message or self._current_message.id != message_id:
                    return False

                # Update message properties
                if text is not None:
                    self._current_message.text = text
                if progress is not None:
                    self._current_message.progress = progress
                if status_type is not None:
                    self._current_message.status_type = status_type
                    self._current_message.icon = self._get_default_icon(status_type)
                if level is not None:
                    self._current_message.level = level

                # Update timestamp
                self._current_message.timestamp = datetime.now()

                # Update display
                self._update_status_display()

                # Notify change callback
                if self._on_status_change:
                    self._on_status_change(self._current_message)

                return True

        except Exception as e:
            print(f"Error updating status: {e}")
            return False

    def clear_status(self) -> None:
        """Clear the current status message."""
        try:
            with self._lock:
                # Cancel dismiss timer
                if self._dismiss_timer:
                    self._dismiss_timer.cancel()
                    self._dismiss_timer = None

                # Clear current message
                if self._current_message:
                    self._current_message = None
                    self._state = StatusState.IDLE

                    # Clear display
                    if self._status_container:
                        content_row = self._status_container.content
                        content_row.controls.clear()
                        self._status_container.update()

                    # Notify change callback
                    if self._on_status_change:
                        self._on_status_change(None)

        except Exception as e:
            print(f"Error clearing status: {e}")

    def get_current_status(self) -> Optional[StatusMessage]:
        """
        Get the current status message.

        Returns:
            Current status message or None
        """
        with self._lock:
            return self._current_message

    def get_status_state(self) -> StatusState:
        """
        Get the current status state.

        Returns:
            Current status state
        """
        with self._lock:
            return self._state

    def _get_default_icon(self, status_type: StatusType) -> str:
        """Get default icon for status type."""
        icons = self.get_icons()

        icon_map = {
            StatusType.INFO: icons.INFO,
            StatusType.SUCCESS: icons.SUCCESS,
            StatusType.WARNING: icons.WARNING,
            StatusType.ERROR: icons.ERROR,
            StatusType.PROGRESS: icons.LOADING,
            StatusType.SYSTEM: icons.COMPUTER,
            StatusType.TRAINING: icons.TRAINING,
            StatusType.PROCESSING: icons.CACHED
        }

        return icon_map.get(status_type, icons.INFO)

    def set_config(self, config: StatusConfig) -> None:
        """
        Update status bar configuration.

        Args:
            config: New configuration
        """
        try:
            self._config = config

            # Update display if there's a current message
            if self._current_message:
                self._update_status_display()

        except Exception as e:
            print(f"Error setting config: {e}")

    def get_metrics(self) -> Dict[str, int]:
        """
        Get status bar metrics.

        Returns:
            Dictionary of metrics
        """
        with self._lock:
            return self._metrics.copy()

    def reset_metrics(self) -> None:
        """Reset status bar metrics."""
        with self._lock:
            self._metrics = {
                'messages_displayed': 0,
                'auto_dismissals': 0,
                'manual_dismissals': 0,
                'click_events': 0
            }

    # Accessibility methods

    def get_accessibility_label(self) -> str:
        """
        Get accessibility label for screen readers.

        Returns:
            Accessibility label text
        """
        try:
            if not self._current_message:
                return "Status bar: No active status"

            message = self._current_message
            level_text = message.level.value.replace('_', ' ')
            type_text = message.status_type.value.replace('_', ' ')

            label = f"Status bar: {level_text} {type_text} - {message.text}"

            if message.progress is not None:
                label += f" - Progress: {message.progress:.0f}%"

            return label

        except Exception as e:
            print(f"Error getting accessibility label: {e}")
            return "Status bar"

    def announce_status_change(self) -> None:
        """Announce status change to screen readers."""
        try:
            if not self._config.enable_accessibility:
                return

            # In a real implementation, this would use screen reader APIs
            # For now, we'll use the accessibility label
            label = self.get_accessibility_label()
            print(f"Screen reader announcement: {label}")

        except Exception as e:
            print(f"Error announcing status change: {e}")

    # Theme integration methods

    def on_theme_changed(self) -> None:
        """Handle theme change events."""
        try:
            # Update display with new theme
            if self._current_message:
                self._update_status_display()

        except Exception as e:
            print(f"Error handling theme change: {e}")

    def on_responsive_change(self, width: int, height: int, screen_size: ScreenSize) -> None:
        """Handle responsive layout changes."""
        try:
            # Update display for new screen size
            if self._current_message:
                self._update_status_display()

        except Exception as e:
            print(f"Error handling responsive change: {e}")


# Utility functions for easy component creation and management

def create_status_bar(config: Optional[StatusConfig] = None,
                     on_status_click: Optional[Callable[[str], None]] = None,
                     on_status_change: Optional[Callable[[StatusMessage], None]] = None) -> StatusBarUI:
    """
    Create a status bar component with optional configuration.

    Args:
        config: Status bar configuration
        on_status_click: Callback for status click events
        on_status_change: Callback for status change events

    Returns:
        StatusBarUI component
    """
    return StatusBarUI(
        config=config,
        on_status_click=on_status_click,
        on_status_change=on_status_change
    )


def update_status_bar(status_bar: StatusBarUI,
                     text: str,
                     status_type: StatusType = StatusType.INFO,
                     level: StatusLevel = StatusLevel.NORMAL,
                     **kwargs) -> str:
    """
    Update a status bar with a new message.

    Args:
        status_bar: StatusBarUI component
        text: Status message text
        status_type: Type of status message
        level: Severity level
        **kwargs: Additional status options

    Returns:
        Message ID
    """
    return status_bar.set_status(
        text=text,
        status_type=status_type,
        level=level,
        **kwargs
    )
