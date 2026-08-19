"""
Module: typing_indicator_ui
Description: Real-time typing indicator component with responsive design and theme integration
Phase: 7
Location: /src/modules/ui/chat_interface_ui/typing_indicator_ui/
"""

# Standard library imports
import asyncio
import logging
from datetime import datetime, timezone
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


class TypingState(Enum):
    """Typing indicator state enumeration."""
    IDLE = "idle"
    TYPING = "typing"
    PAUSED = "paused"
    STOPPED = "stopped"


class TypingAnimationType(Enum):
    """Animation type for typing indicator."""
    DOTS = "dots"
    PULSE = "pulse"
    WAVE = "wave"
    BOUNCE = "bounce"


@dataclass
class TypingConfig:
    """Configuration for typing indicator behavior."""
    animation_type: TypingAnimationType = TypingAnimationType.DOTS
    animation_speed_ms: int = 600
    dot_count: int = 3
    dot_size: int = 8
    show_user_name: bool = True
    show_timestamp: bool = False
    auto_hide_timeout_ms: int = 5000
    fade_duration_ms: int = 300
    enable_sound: bool = False
    max_display_time_ms: int = 30000
    enable_accessibility: bool = True
    reduced_motion_support: bool = True


@dataclass
class TypingIndicatorData:
    """Data structure for typing indicator state."""
    user_name: Optional[str] = None
    user_id: Optional[str] = None
    start_time: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    state: TypingState = TypingState.IDLE
    animation_phase: int = 0
    is_visible: bool = False
    message_preview: Optional[str] = None


class TypingIndicatorUI(ThemeAwareUserControl):
    """
    Real-time typing indicator component with responsive design and theme integration.
    
    Features:
    - Animated typing indicators with multiple animation types (dots, pulse, wave, bounce)
    - Responsive design with breakpoint-aware sizing and spacing
    - Full theme system integration with adaptive colors and typography
    - Accessibility support with reduced motion and screen reader compatibility
    - Configurable timing, animations, and visual appearance
    - Real-time state management with automatic timeout handling
    - Performance-optimized animations with smooth transitions
    - Integration with chat interface and message processing systems
    """

    def __init__(self,
                 config: Optional[TypingConfig] = None,
                 on_timeout: Optional[Callable[[], None]] = None,
                 on_state_change: Optional[Callable[[TypingState], None]] = None,
                 **kwargs):
        """
        Initialize the typing indicator UI component.
        
        Args:
            config: Configuration for typing indicator behavior
            on_timeout: Callback for when typing indicator times out
            on_state_change: Callback for when typing state changes
            **kwargs: Additional arguments for ThemeAwareUserControl
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or TypingConfig()
        self._on_timeout = on_timeout
        self._on_state_change = on_state_change
        
        # State management
        self._typing_data = TypingIndicatorData()
        self._animation_task: Optional[asyncio.Task] = None
        self._timeout_task: Optional[asyncio.Task] = None
        self._is_animating = False
        
        # UI components
        self._indicator_container: Optional[ft.Container] = None
        self._dots_container: Optional[ft.Row] = None
        self._text_label: Optional[ft.Text] = None
        self._timestamp_label: Optional[ft.Text] = None
        self._animation_dots: List[ft.Container] = []
        
        # Logging
        self._logger = logging.getLogger(__name__)
        
        # Initialize component
        self._initialize_component()

    def _initialize_component(self) -> None:
        """Initialize the typing indicator component."""
        try:
            self._logger.debug("Initializing TypingIndicatorUI component")
            
            # Set initial state
            self._typing_data.state = TypingState.IDLE
            self._typing_data.is_visible = False
            
            # Build the UI
            self.build()
            
        except Exception as e:
            self._logger.error(f"Error initializing typing indicator: {e}")
            raise

    def build(self) -> None:
        """Build the typing indicator UI with responsive design and theme integration."""
        try:
            self._logger.debug("Building TypingIndicatorUI component")

            # Get theme components
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            
            # Responsive sizing
            responsive_padding = self.get_responsive_padding()
            dot_size = self.get_breakpoint_value(
                mobile=6, tablet=7, desktop=8, large=8
            )
            
            # Create animation dots
            self._create_animation_dots(dot_size, palette)
            
            # Create text label
            self._text_label = ft.Text(
                "",
                style=typography.body_small,
                color=palette.text_secondary,
                italic=True,
                visible=False
            )

            # Create timestamp label
            self._timestamp_label = ft.Text(
                "",
                style=typography.caption,
                color=palette.text_secondary,
                visible=False
            ) if self._config.show_timestamp else None
            
            # Create dots container
            self._dots_container = ft.Row(
                controls=self._animation_dots,
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True
            )
            
            # Create main content row
            content_controls = []
            
            # Add typing icon
            content_controls.append(
                ft.Icon(
                    ft.Icons.EDIT,
                    size=self.get_breakpoint_value(
                        mobile=14, tablet=15, desktop=16, large=16
                    ),
                    color=palette.text_secondary
                )
            )
            
            # Add text label
            content_controls.append(self._text_label)
            
            # Add dots animation
            content_controls.append(self._dots_container)
            
            # Add timestamp if enabled
            if self._timestamp_label:
                content_controls.append(self._timestamp_label)
            
            # Create main content
            main_content = ft.Row(
                controls=content_controls,
                spacing=spacing.sm,
                alignment=ft.MainAxisAlignment.START,
                tight=True
            )
            
            # Create indicator container
            self._indicator_container = ft.Container(
                content=main_content,
                padding=ft.padding.symmetric(
                    horizontal=responsive_padding,
                    vertical=spacing.sm
                ),
                bgcolor=palette.surface_variant,
                border_radius=self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=12
                ),
                border=ft.border.all(1, palette.outline),
                visible=False,
                opacity=0.0,
                animate_opacity=ft.Animation(
                    duration=self._config.fade_duration_ms,
                    curve=ft.AnimationCurve.EASE_IN_OUT
                )
            )
            
            # Set main content
            self.content = self._indicator_container
            
        except Exception as e:
            self._logger.error(f"Error building typing indicator: {e}")
            self.content = ft.Container()  # Fallback

    def _create_animation_dots(self, dot_size: int, palette) -> None:
        """Create animation dots for the typing indicator."""
        try:
            self._animation_dots.clear()
            
            for i in range(self._config.dot_count):
                dot = ft.Container(
                    width=dot_size,
                    height=dot_size,
                    bgcolor=palette.primary,
                    border_radius=ft.border_radius.all(dot_size // 2),
                    opacity=0.3,
                    animate_opacity=ft.Animation(
                        duration=self._config.animation_speed_ms,
                        curve=ft.AnimationCurve.EASE_IN_OUT
                    )
                )
                self._animation_dots.append(dot)
                
        except Exception as e:
            self._logger.error(f"Error creating animation dots: {e}")

    # Public API Methods

    def show_typing(self,
                   user_name: Optional[str] = None,
                   user_id: Optional[str] = None,
                   message_preview: Optional[str] = None) -> None:
        """
        Show typing indicator for a user.

        Args:
            user_name: Name of the typing user
            user_id: ID of the typing user
            message_preview: Optional preview of the message being typed
        """
        try:
            self._logger.debug(f"Showing typing indicator for user: {user_name}")

            # Update typing data
            self._typing_data.user_name = user_name
            self._typing_data.user_id = user_id
            self._typing_data.message_preview = message_preview
            self._typing_data.start_time = datetime.now(timezone.utc)
            self._typing_data.last_activity = self._typing_data.start_time
            self._typing_data.state = TypingState.TYPING
            self._typing_data.is_visible = True

            # Update UI text
            self._update_text_display()

            # Show indicator with animation
            self._show_indicator()

            # Start animation
            self._start_animation()

            # Set timeout
            self._set_timeout()

            # Notify state change
            if self._on_state_change:
                self._on_state_change(TypingState.TYPING)

        except Exception as e:
            self._logger.error(f"Error showing typing indicator: {e}")

    def hide_typing(self) -> None:
        """Hide typing indicator."""
        try:
            self._logger.debug("Hiding typing indicator")

            # Update state
            self._typing_data.state = TypingState.STOPPED
            self._typing_data.is_visible = False

            # Stop animation
            self._stop_animation()

            # Hide indicator with animation
            self._hide_indicator()

            # Cancel timeout
            self._cancel_timeout()

            # Notify state change
            if self._on_state_change:
                self._on_state_change(TypingState.STOPPED)

        except Exception as e:
            self._logger.error(f"Error hiding typing indicator: {e}")

    def pause_typing(self) -> None:
        """Pause typing indicator animation."""
        try:
            if self._typing_data.state == TypingState.TYPING:
                self._typing_data.state = TypingState.PAUSED
                self._stop_animation()

                if self._on_state_change:
                    self._on_state_change(TypingState.PAUSED)

        except Exception as e:
            self._logger.error(f"Error pausing typing indicator: {e}")

    def resume_typing(self) -> None:
        """Resume typing indicator animation."""
        try:
            if self._typing_data.state == TypingState.PAUSED:
                self._typing_data.state = TypingState.TYPING
                self._typing_data.last_activity = datetime.now(timezone.utc)
                self._start_animation()

                if self._on_state_change:
                    self._on_state_change(TypingState.TYPING)

        except Exception as e:
            self._logger.error(f"Error resuming typing indicator: {e}")

    def update_activity(self) -> None:
        """Update last activity timestamp to prevent timeout."""
        try:
            if self._typing_data.state == TypingState.TYPING:
                self._typing_data.last_activity = datetime.now(timezone.utc)
                self._set_timeout()  # Reset timeout

        except Exception as e:
            self._logger.error(f"Error updating typing activity: {e}")

    # Private UI Methods

    def _update_text_display(self) -> None:
        """Update the text display based on current typing data."""
        try:
            if not self._text_label:
                return

            # Build display text
            if self._config.show_user_name and self._typing_data.user_name:
                display_text = f"{self._typing_data.user_name} is typing"
            else:
                display_text = "Typing"

            # Add message preview if available
            if self._typing_data.message_preview and len(self._typing_data.message_preview) > 0:
                preview = self._typing_data.message_preview[:30]
                if len(self._typing_data.message_preview) > 30:
                    preview += "..."
                display_text += f": {preview}"

            self._text_label.value = display_text
            self._text_label.visible = True

            # Update timestamp if enabled
            if self._timestamp_label and self._config.show_timestamp:
                if self._typing_data.start_time:
                    timestamp = self._typing_data.start_time.strftime("%H:%M")
                    self._timestamp_label.value = timestamp
                    self._timestamp_label.visible = True

            # Update the page
            if self.page:
                self._text_label.update()
                if self._timestamp_label:
                    self._timestamp_label.update()

        except Exception as e:
            self._logger.error(f"Error updating text display: {e}")

    def _show_indicator(self) -> None:
        """Show the typing indicator with fade-in animation."""
        try:
            if self._indicator_container:
                self._indicator_container.visible = True
                self._indicator_container.opacity = 1.0

                if self.page:
                    self._indicator_container.update()

        except Exception as e:
            self._logger.error(f"Error showing indicator: {e}")

    def _hide_indicator(self) -> None:
        """Hide the typing indicator with fade-out animation."""
        try:
            if self._indicator_container:
                self._indicator_container.opacity = 0.0

                # Hide after animation completes
                async def hide_after_fade():
                    await asyncio.sleep(self._config.fade_duration_ms / 1000)
                    if self._indicator_container:
                        self._indicator_container.visible = False
                        if self.page:
                            self._indicator_container.update()

                asyncio.create_task(hide_after_fade())

                if self.page:
                    self._indicator_container.update()

        except Exception as e:
            self._logger.error(f"Error hiding indicator: {e}")

    # Animation Methods

    def _start_animation(self) -> None:
        """Start the typing animation."""
        try:
            if self._is_animating:
                return

            self._is_animating = True

            # Check for reduced motion
            accessibility_manager = self.get_accessibility_manager()
            if accessibility_manager and accessibility_manager.is_reduced_motion_enabled():
                if self._config.reduced_motion_support:
                    self._start_reduced_motion_animation()
                    return

            # Start appropriate animation based on type
            if self._config.animation_type == TypingAnimationType.DOTS:
                self._animation_task = asyncio.create_task(self._animate_dots())
            elif self._config.animation_type == TypingAnimationType.PULSE:
                self._animation_task = asyncio.create_task(self._animate_pulse())
            elif self._config.animation_type == TypingAnimationType.WAVE:
                self._animation_task = asyncio.create_task(self._animate_wave())
            elif self._config.animation_type == TypingAnimationType.BOUNCE:
                self._animation_task = asyncio.create_task(self._animate_bounce())

        except Exception as e:
            self._logger.error(f"Error starting animation: {e}")
            self._is_animating = False

    def _stop_animation(self) -> None:
        """Stop the typing animation."""
        try:
            self._is_animating = False

            if self._animation_task and not self._animation_task.done():
                self._animation_task.cancel()
                self._animation_task = None

            # Reset dots to default state
            self._reset_dots()

        except Exception as e:
            self._logger.error(f"Error stopping animation: {e}")

    def _start_reduced_motion_animation(self) -> None:
        """Start reduced motion animation for accessibility."""
        try:
            # Simple opacity pulse for reduced motion
            for dot in self._animation_dots:
                dot.opacity = 0.8

            if self.page:
                for dot in self._animation_dots:
                    dot.update()

        except Exception as e:
            self._logger.error(f"Error starting reduced motion animation: {e}")

    async def _animate_dots(self) -> None:
        """Animate typing dots with sequential opacity changes."""
        try:
            while self._is_animating and self._typing_data.state == TypingState.TYPING:
                for i, dot in enumerate(self._animation_dots):
                    if not self._is_animating:
                        break

                    # Animate dot
                    dot.opacity = 1.0
                    if self.page:
                        dot.update()

                    await asyncio.sleep(self._config.animation_speed_ms / 1000 / len(self._animation_dots))

                    # Fade out
                    dot.opacity = 0.3
                    if self.page:
                        dot.update()

                # Pause between cycles
                await asyncio.sleep(self._config.animation_speed_ms / 1000 / 2)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in dots animation: {e}")

    async def _animate_pulse(self) -> None:
        """Animate typing dots with synchronized pulsing."""
        try:
            while self._is_animating and self._typing_data.state == TypingState.TYPING:
                # Pulse all dots together
                for dot in self._animation_dots:
                    dot.opacity = 1.0

                if self.page:
                    for dot in self._animation_dots:
                        dot.update()

                await asyncio.sleep(self._config.animation_speed_ms / 1000 / 2)

                # Fade out
                for dot in self._animation_dots:
                    dot.opacity = 0.3

                if self.page:
                    for dot in self._animation_dots:
                        dot.update()

                await asyncio.sleep(self._config.animation_speed_ms / 1000 / 2)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in pulse animation: {e}")

    async def _animate_wave(self) -> None:
        """Animate typing dots with wave effect."""
        try:
            while self._is_animating and self._typing_data.state == TypingState.TYPING:
                # Forward wave
                for i, dot in enumerate(self._animation_dots):
                    if not self._is_animating:
                        break

                    dot.opacity = 1.0
                    if self.page:
                        dot.update()

                    await asyncio.sleep(self._config.animation_speed_ms / 1000 / len(self._animation_dots) / 2)

                # Backward wave
                for i in range(len(self._animation_dots) - 1, -1, -1):
                    if not self._is_animating:
                        break

                    dot = self._animation_dots[i]
                    dot.opacity = 0.3
                    if self.page:
                        dot.update()

                    await asyncio.sleep(self._config.animation_speed_ms / 1000 / len(self._animation_dots) / 2)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in wave animation: {e}")

    async def _animate_bounce(self) -> None:
        """Animate typing dots with bounce effect."""
        try:
            while self._is_animating and self._typing_data.state == TypingState.TYPING:
                for i, dot in enumerate(self._animation_dots):
                    if not self._is_animating:
                        break

                    # Bounce effect with opacity and slight scale simulation
                    dot.opacity = 1.0
                    if self.page:
                        dot.update()

                    await asyncio.sleep(self._config.animation_speed_ms / 1000 / len(self._animation_dots))

                    dot.opacity = 0.5
                    if self.page:
                        dot.update()

                    await asyncio.sleep(self._config.animation_speed_ms / 1000 / len(self._animation_dots) / 2)

                    dot.opacity = 0.3
                    if self.page:
                        dot.update()

                # Pause between cycles
                await asyncio.sleep(self._config.animation_speed_ms / 1000 / 3)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in bounce animation: {e}")

    def _reset_dots(self) -> None:
        """Reset all dots to default state."""
        try:
            for dot in self._animation_dots:
                dot.opacity = 0.3
                if self.page:
                    dot.update()

        except Exception as e:
            self._logger.error(f"Error resetting dots: {e}")

    # Timeout Management

    def _set_timeout(self) -> None:
        """Set or reset the typing timeout."""
        try:
            # Cancel existing timeout
            self._cancel_timeout()

            # Set new timeout
            if self._config.auto_hide_timeout_ms > 0:
                self._timeout_task = asyncio.create_task(self._handle_timeout())

        except Exception as e:
            self._logger.error(f"Error setting timeout: {e}")

    def _cancel_timeout(self) -> None:
        """Cancel the current timeout."""
        try:
            if self._timeout_task and not self._timeout_task.done():
                self._timeout_task.cancel()
                self._timeout_task = None

        except Exception as e:
            self._logger.error(f"Error canceling timeout: {e}")

    async def _handle_timeout(self) -> None:
        """Handle typing timeout."""
        try:
            await asyncio.sleep(self._config.auto_hide_timeout_ms / 1000)

            # Check if still typing and not recently active
            if self._typing_data.state == TypingState.TYPING:
                current_time = datetime.now(timezone.utc)
                if self._typing_data.last_activity:
                    time_since_activity = (current_time - self._typing_data.last_activity).total_seconds() * 1000

                    if time_since_activity >= self._config.auto_hide_timeout_ms:
                        self._logger.debug("Typing indicator timed out")
                        self.hide_typing()

                        if self._on_timeout:
                            self._on_timeout()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error handling timeout: {e}")

    # Property Accessors

    @property
    def is_visible(self) -> bool:
        """Check if typing indicator is currently visible."""
        return self._typing_data.is_visible

    @property
    def current_state(self) -> TypingState:
        """Get current typing state."""
        return self._typing_data.state

    @property
    def typing_user(self) -> Optional[str]:
        """Get name of currently typing user."""
        return self._typing_data.user_name

    @property
    def typing_duration(self) -> Optional[float]:
        """Get duration of current typing session in seconds."""
        if self._typing_data.start_time and self._typing_data.state == TypingState.TYPING:
            return (datetime.now(timezone.utc) - self._typing_data.start_time).total_seconds()
        return None

    # Configuration Methods

    def update_config(self, config: TypingConfig) -> None:
        """
        Update typing indicator configuration.

        Args:
            config: New configuration settings
        """
        try:
            self._config = config

            # Rebuild dots if count changed
            if len(self._animation_dots) != config.dot_count:
                palette = self.get_palette()
                dot_size = self.get_breakpoint_value(
                    mobile=6, tablet=7, desktop=8, large=8
                )
                self._create_animation_dots(dot_size, palette)

                if self._dots_container:
                    self._dots_container.controls = self._animation_dots
                    if self.page:
                        self._dots_container.update()

            # Update text display
            self._update_text_display()

        except Exception as e:
            self._logger.error(f"Error updating config: {e}")

    def set_animation_type(self, animation_type: TypingAnimationType) -> None:
        """
        Set the animation type for typing indicator.

        Args:
            animation_type: New animation type
        """
        try:
            self._config.animation_type = animation_type

            # Restart animation if currently animating
            if self._is_animating:
                self._stop_animation()
                self._start_animation()

        except Exception as e:
            self._logger.error(f"Error setting animation type: {e}")

    # Cleanup Methods

    def cleanup(self) -> None:
        """Clean up resources and stop all animations."""
        try:
            self._logger.debug("Cleaning up TypingIndicatorUI")

            # Stop animation
            self._stop_animation()

            # Cancel timeout
            self._cancel_timeout()

            # Reset state
            self._typing_data.state = TypingState.IDLE
            self._typing_data.is_visible = False

            # Hide indicator
            if self._indicator_container:
                self._indicator_container.visible = False

        except Exception as e:
            self._logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during destruction

    # Integration Methods for Chat Interface

    def integrate_with_chat_window(self, chat_window) -> None:
        """
        Integrate typing indicator with chat window.

        Args:
            chat_window: ChatWindowUI instance to integrate with
        """
        try:
            self._logger.debug("Integrating with chat window")

            # Set up event handlers for chat window
            if hasattr(chat_window, 'on_typing_start'):
                chat_window.on_typing_start = self._handle_chat_typing_start
            if hasattr(chat_window, 'on_typing_stop'):
                chat_window.on_typing_stop = self._handle_chat_typing_stop
            if hasattr(chat_window, 'on_message_sent'):
                chat_window.on_message_sent = self._handle_message_sent

        except Exception as e:
            self._logger.error(f"Error integrating with chat window: {e}")

    def integrate_with_message_input(self, message_input) -> None:
        """
        Integrate typing indicator with message input component.

        Args:
            message_input: MessageInputUI instance to integrate with
        """
        try:
            self._logger.debug("Integrating with message input")

            # Set up event handlers for message input
            if hasattr(message_input, 'on_typing_start'):
                message_input.on_typing_start = self._handle_user_typing_start
            if hasattr(message_input, 'on_typing_stop'):
                message_input.on_typing_stop = self._handle_user_typing_stop
            if hasattr(message_input, 'on_text_change'):
                message_input.on_text_change = self._handle_text_change

        except Exception as e:
            self._logger.error(f"Error integrating with message input: {e}")

    # Event Handlers for Integration

    async def _handle_chat_typing_start(self, user_name: Optional[str] = None) -> None:
        """Handle typing start from chat window."""
        try:
            self.show_typing(user_name=user_name or "AI")
        except Exception as e:
            self._logger.error(f"Error handling chat typing start: {e}")

    async def _handle_chat_typing_stop(self) -> None:
        """Handle typing stop from chat window."""
        try:
            self.hide_typing()
        except Exception as e:
            self._logger.error(f"Error handling chat typing stop: {e}")

    async def _handle_user_typing_start(self, user_name: Optional[str] = None) -> None:
        """Handle user typing start from message input."""
        try:
            self.show_typing(user_name=user_name or "User")
        except Exception as e:
            self._logger.error(f"Error handling user typing start: {e}")

    async def _handle_user_typing_stop(self) -> None:
        """Handle user typing stop from message input."""
        try:
            self.hide_typing()
        except Exception as e:
            self._logger.error(f"Error handling user typing stop: {e}")

    async def _handle_text_change(self, text: str) -> None:
        """Handle text change in message input."""
        try:
            if text and len(text.strip()) > 0:
                # Update activity to prevent timeout
                self.update_activity()

                # Show preview if configured
                if self._config.show_user_name and len(text) > 0:
                    preview = text[:50] if len(text) > 50 else text
                    if self._typing_data.is_visible:
                        self._typing_data.message_preview = preview
                        self._update_text_display()
            else:
                # Hide typing if text is empty
                if self._typing_data.is_visible:
                    self.hide_typing()

        except Exception as e:
            self._logger.error(f"Error handling text change: {e}")

    async def _handle_message_sent(self, message: Any) -> None:
        """Handle message sent event."""
        try:
            # Hide typing indicator when message is sent
            if self._typing_data.is_visible:
                self.hide_typing()

        except Exception as e:
            self._logger.error(f"Error handling message sent: {e}")

    # Utility Methods for Chat Integration

    def create_typing_event_handler(self,
                                  event_type: str,
                                  user_name: Optional[str] = None) -> Callable:
        """
        Create a typing event handler for specific events.

        Args:
            event_type: Type of event ('start', 'stop', 'update')
            user_name: Optional user name for the event

        Returns:
            Event handler function
        """
        try:
            if event_type == 'start':
                return lambda: self.show_typing(user_name=user_name)
            elif event_type == 'stop':
                return lambda: self.hide_typing()
            elif event_type == 'update':
                return lambda: self.update_activity()
            else:
                return lambda: None

        except Exception as e:
            self._logger.error(f"Error creating event handler: {e}")
            return lambda: None

    def get_typing_status(self) -> Dict[str, Any]:
        """
        Get current typing status information.

        Returns:
            Dictionary with typing status details
        """
        try:
            return {
                'is_visible': self._typing_data.is_visible,
                'state': self._typing_data.state.value,
                'user_name': self._typing_data.user_name,
                'user_id': self._typing_data.user_id,
                'start_time': self._typing_data.start_time.isoformat() if self._typing_data.start_time else None,
                'last_activity': self._typing_data.last_activity.isoformat() if self._typing_data.last_activity else None,
                'duration': self.typing_duration,
                'message_preview': self._typing_data.message_preview,
                'animation_type': self._config.animation_type.value,
                'is_animating': self._is_animating
            }

        except Exception as e:
            self._logger.error(f"Error getting typing status: {e}")
            return {}

    def set_typing_callbacks(self,
                           on_timeout: Optional[Callable[[], None]] = None,
                           on_state_change: Optional[Callable[[TypingState], None]] = None) -> None:
        """
        Set callback functions for typing events.

        Args:
            on_timeout: Callback for when typing times out
            on_state_change: Callback for when typing state changes
        """
        try:
            if on_timeout:
                self._on_timeout = on_timeout
            if on_state_change:
                self._on_state_change = on_state_change

        except Exception as e:
            self._logger.error(f"Error setting typing callbacks: {e}")

    # Accessibility Methods

    def set_accessibility_label(self, label: str) -> None:
        """
        Set accessibility label for screen readers.

        Args:
            label: Accessibility label text
        """
        try:
            if self._indicator_container:
                # Set semantic label for screen readers
                self._indicator_container.tooltip = label

                # Update text for screen readers
                if self._text_label:
                    self._text_label.semantics_label = label

        except Exception as e:
            self._logger.error(f"Error setting accessibility label: {e}")

    def announce_typing_status(self, message: str) -> None:
        """
        Announce typing status to screen readers.

        Args:
            message: Message to announce
        """
        try:
            if self._config.enable_accessibility and self.page:
                # Use Flet's accessibility announcement if available
                if hasattr(self.page, 'announce'):
                    self.page.announce(message)
                else:
                    # Fallback: update semantic label
                    self.set_accessibility_label(message)

        except Exception as e:
            self._logger.error(f"Error announcing typing status: {e}")

    def get_accessibility_description(self) -> str:
        """
        Get accessibility description for current state.

        Returns:
            Accessibility description text
        """
        try:
            if not self._typing_data.is_visible:
                return "No one is typing"

            if self._typing_data.user_name:
                return f"{self._typing_data.user_name} is typing a message"
            else:
                return "Someone is typing a message"

        except Exception as e:
            self._logger.error(f"Error getting accessibility description: {e}")
            return "Typing indicator"

    def enable_reduced_motion(self, enabled: bool = True) -> None:
        """
        Enable or disable reduced motion for accessibility.

        Args:
            enabled: Whether to enable reduced motion
        """
        try:
            self._config.reduced_motion_support = enabled

            # Restart animation with new settings if currently animating
            if self._is_animating:
                self._stop_animation()
                self._start_animation()

        except Exception as e:
            self._logger.error(f"Error setting reduced motion: {e}")

    # Performance Optimization Methods

    def optimize_for_performance(self) -> None:
        """Optimize typing indicator for better performance."""
        try:
            # Reduce animation frequency for better performance
            if self._config.animation_speed_ms < 300:
                self._config.animation_speed_ms = 300

            # Limit maximum display time
            if self._config.max_display_time_ms > 60000:
                self._config.max_display_time_ms = 60000

            # Optimize dot count for performance
            if self._config.dot_count > 5:
                self._config.dot_count = 5
                palette = self.get_palette()
                dot_size = self.get_breakpoint_value(
                    mobile=6, tablet=7, desktop=8, large=8
                )
                self._create_animation_dots(dot_size, palette)

        except Exception as e:
            self._logger.error(f"Error optimizing performance: {e}")

    def pause_animations_when_hidden(self) -> None:
        """Pause animations when component is not visible to save resources."""
        try:
            if not self._typing_data.is_visible and self._is_animating:
                self._stop_animation()

        except Exception as e:
            self._logger.error(f"Error pausing hidden animations: {e}")

    def throttle_updates(self, min_interval_ms: int = 100) -> None:
        """
        Throttle UI updates to improve performance.

        Args:
            min_interval_ms: Minimum interval between updates in milliseconds
        """
        try:
            # Store last update time
            if not hasattr(self, '_last_update_time'):
                self._last_update_time = 0

            current_time = datetime.now().timestamp() * 1000
            if current_time - self._last_update_time < min_interval_ms:
                return  # Skip update

            self._last_update_time = current_time

        except Exception as e:
            self._logger.error(f"Error throttling updates: {e}")

    # Memory Management

    def clear_animation_cache(self) -> None:
        """Clear animation cache to free memory."""
        try:
            # Cancel any running tasks
            if self._animation_task and not self._animation_task.done():
                self._animation_task.cancel()
                self._animation_task = None

            if self._timeout_task and not self._timeout_task.done():
                self._timeout_task.cancel()
                self._timeout_task = None

            # Reset animation state
            self._is_animating = False

        except Exception as e:
            self._logger.error(f"Error clearing animation cache: {e}")

    def get_memory_usage_info(self) -> Dict[str, Any]:
        """
        Get memory usage information for debugging.

        Returns:
            Dictionary with memory usage details
        """
        try:
            return {
                'animation_dots_count': len(self._animation_dots),
                'is_animating': self._is_animating,
                'has_animation_task': self._animation_task is not None,
                'has_timeout_task': self._timeout_task is not None,
                'config_dot_count': self._config.dot_count,
                'animation_type': self._config.animation_type.value
            }

        except Exception as e:
            self._logger.error(f"Error getting memory usage info: {e}")
            return {}

    # Theme Integration Enhancements

    def on_theme_changed(self) -> None:
        """Handle theme change events."""
        try:
            # Update colors based on new theme
            palette = self.get_palette()

            # Update dot colors
            for dot in self._animation_dots:
                dot.bgcolor = palette.primary

            # Update container colors
            if self._indicator_container:
                self._indicator_container.bgcolor = palette.surface_variant
                self._indicator_container.border = ft.border.all(1, palette.outline)

            # Update text colors
            if self._text_label:
                self._text_label.color = palette.text_secondary

            if self._timestamp_label:
                self._timestamp_label.color = palette.text_secondary

            # Update the page
            if self.page:
                self.update()

        except Exception as e:
            self._logger.error(f"Error handling theme change: {e}")

    def apply_responsive_updates(self) -> None:
        """Apply responsive design updates based on current screen size."""
        try:
            # Update responsive sizing
            dot_size = self.get_breakpoint_value(
                mobile=6, tablet=7, desktop=8, large=8
            )

            # Update dot sizes
            for dot in self._animation_dots:
                dot.width = dot_size
                dot.height = dot_size
                dot.border_radius = ft.border_radius.all(dot_size // 2)

            # Update container border radius
            if self._indicator_container:
                border_radius = self.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=12
                )
                self._indicator_container.border_radius = ft.border_radius.all(border_radius)

            # Update icon size
            icon_size = self.get_breakpoint_value(
                mobile=14, tablet=15, desktop=16, large=16
            )

            # Update padding
            responsive_padding = self.get_responsive_padding()
            if self._indicator_container:
                spacing = self.get_spacing()
                self._indicator_container.padding = ft.padding.symmetric(
                    horizontal=responsive_padding,
                    vertical=spacing.sm
                )

            # Update the page
            if self.page:
                self.update()

        except Exception as e:
            self._logger.error(f"Error applying responsive updates: {e}")
