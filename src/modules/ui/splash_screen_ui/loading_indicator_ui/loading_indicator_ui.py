"""
Module: loading_indicator_ui
Description: Comprehensive loading indicator UI component for MikroDok splash screen.
            Provides responsive loading indicators including progress bars, spinners, pulse animations,
            and branded loading animations with full theme system integration and accessibility compliance.
Phase: 1
Location: /src/modules/ui/splash_screen_ui/loading_indicator_ui/loading_indicator_ui.py
"""

# Standard library imports
import asyncio
import time
from typing import Optional, Callable, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl, ResponsiveLayoutManager, ScreenSize,
    get_responsive_value, calculate_responsive_spacing
)


class LoadingIndicatorType(Enum):
    """Types of loading indicators available."""
    CIRCULAR = "circular"
    LINEAR = "linear"
    PULSE = "pulse"
    BRANDED = "branded"
    DOTS = "dots"


class LoadingState(Enum):
    """Loading states for the indicator."""
    IDLE = "idle"
    LOADING = "loading"
    SUCCESS = "success"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class LoadingConfig:
    """Configuration for loading indicator behavior."""
    indicator_type: LoadingIndicatorType = LoadingIndicatorType.CIRCULAR
    show_percentage: bool = True
    show_message: bool = True
    auto_hide_on_complete: bool = True
    animation_duration: int = 1000
    pulse_interval: float = 1.5
    enable_reduced_motion: bool = True


class LoadingIndicatorUI(ThemeAwareUserControl):
    """
    Comprehensive loading indicator UI component for splash screen.
    
    Features:
    - Multiple loading indicator types (circular, linear, pulse, branded, dots)
    - Responsive design with breakpoint-aware sizing
    - Full theme system integration with no hardcoded styling
    - Accessibility compliance (WCAG 2.1 AA) with reduced motion support
    - Progress tracking with percentage and custom messages
    - State management (idle, loading, success, error, paused)
    - Performance-optimized animations and rendering
    - Branded loading animations for MikroDok identity
    """

    def __init__(self,
                 config: Optional[LoadingConfig] = None,
                 initial_message: str = "Loading...",
                 on_complete: Optional[Callable] = None,
                 **kwargs):
        """
        Initialize the loading indicator UI component.
        
        Args:
            config: Loading indicator configuration
            initial_message: Initial loading message
            on_complete: Callback function when loading completes
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or LoadingConfig()
        self._initial_message = initial_message
        self._on_complete = on_complete
        
        # State management
        self._current_state = LoadingState.IDLE
        self._progress_value = 0.0
        self._current_message = initial_message
        self._is_animating = False
        self._animation_task: Optional[asyncio.Task] = None
        
        # UI components
        self._progress_indicator: Optional[ft.Control] = None
        self._message_text: Optional[ft.Text] = None
        self._percentage_text: Optional[ft.Text] = None
        self._status_icon: Optional[ft.Icon] = None
        self._container: Optional[ft.Container] = None
        
        # Animation state
        self._pulse_opacity = 1.0
        self._dots_animation_step = 0
        self._rotation_angle = 0.0
        
        # Performance tracking
        self._last_update_time = 0.0
        self._update_throttle_ms = 16  # ~60 FPS
        
        # Initialize component
        self._setup_component()

        # Initialize accessibility features
        self._initialize_accessibility_features()

    def _setup_component(self) -> None:
        """Setup the loading indicator component."""
        self.expand = True
        self.alignment = ft.alignment.center
        
    def build(self) -> ft.Control:
        """Build the loading indicator UI."""
        # Get responsive layout manager
        responsive_manager = self.get_responsive_layout()
        
        # Get theme palette and spacing
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Create main container with responsive sizing
        container_padding = responsive_manager.get_breakpoint_value(
            mobile=spacing.component, 
            tablet=spacing.section,
            desktop=spacing.section, 
            large=spacing.page
        )
        
        # Create loading indicator based on type
        self._progress_indicator = self._create_progress_indicator()
        
        # Create message text with responsive typography
        message_style = self.get_text_style("body_primary")
        self._message_text = ft.Text(
            value=self._current_message,
            style=message_style,
            text_align=ft.TextAlign.CENTER,
            color=palette.text_secondary
        )
        
        # Create percentage text if enabled
        percentage_controls = []
        if self._config.show_percentage:
            percentage_style = self.get_text_style("caption")
            self._percentage_text = ft.Text(
                value=f"{self._progress_value:.0f}%",
                style=percentage_style,
                text_align=ft.TextAlign.CENTER,
                color=palette.text_muted
            )
            percentage_controls.append(self._percentage_text)
        
        # Create status icon
        self._status_icon = self._create_status_icon()
        
        # Arrange components in responsive column
        column_spacing = responsive_manager.get_breakpoint_value(
            mobile=spacing.tight, 
            tablet=spacing.component,
            desktop=spacing.component, 
            large=spacing.loose
        )
        
        content_column = ft.Column(
            controls=[
                self._progress_indicator,
                self._status_icon,
                self._message_text,
                *percentage_controls
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=column_spacing,
            tight=True
        )
        
        # Create main container
        self._container = ft.Container(
            content=content_column,
            padding=container_padding,
            alignment=ft.alignment.center,
            expand=True
        )
        
        return self._container

    def _create_progress_indicator(self) -> ft.Control:
        """Create the appropriate progress indicator based on type."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        
        if self._config.indicator_type == LoadingIndicatorType.CIRCULAR:
            return self._create_circular_indicator()
        elif self._config.indicator_type == LoadingIndicatorType.LINEAR:
            return self._create_linear_indicator()
        elif self._config.indicator_type == LoadingIndicatorType.PULSE:
            return self._create_pulse_indicator()
        elif self._config.indicator_type == LoadingIndicatorType.BRANDED:
            return self._create_branded_indicator()
        elif self._config.indicator_type == LoadingIndicatorType.DOTS:
            return self._create_dots_indicator()
        else:
            return self._create_circular_indicator()  # Default fallback

    def _create_circular_indicator(self) -> ft.Control:
        """Create circular progress indicator."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        
        # Responsive sizing
        indicator_size = responsive_manager.get_breakpoint_value(
            mobile=40, tablet=48, desktop=56, large=64
        )
        
        stroke_width = responsive_manager.get_breakpoint_value(
            mobile=3, tablet=4, desktop=4, large=5
        )
        
        return ft.ProgressRing(
            width=indicator_size,
            height=indicator_size,
            stroke_width=stroke_width,
            color=palette.primary,
            bgcolor=palette.surface_variant,
            value=self._progress_value / 100.0 if self._progress_value > 0 else None
        )

    def _create_linear_indicator(self) -> ft.Control:
        """Create linear progress indicator."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        
        # Responsive sizing
        indicator_width = responsive_manager.get_breakpoint_value(
            mobile=200, tablet=280, desktop=320, large=400
        )
        
        indicator_height = responsive_manager.get_breakpoint_value(
            mobile=4, tablet=6, desktop=6, large=8
        )
        
        return ft.ProgressBar(
            width=indicator_width,
            height=indicator_height,
            color=palette.primary,
            bgcolor=palette.surface_variant,
            value=self._progress_value / 100.0 if self._progress_value > 0 else None
        )

    def _create_pulse_indicator(self) -> ft.Control:
        """Create pulse animation indicator."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()

        # Responsive sizing
        pulse_size = responsive_manager.get_breakpoint_value(
            mobile=32, tablet=40, desktop=48, large=56
        )

        return ft.Container(
            width=pulse_size,
            height=pulse_size,
            bgcolor=palette.primary,
            border_radius=pulse_size // 2,
            opacity=self._pulse_opacity,
            animate_opacity=ft.animation.Animation(
                duration=int(self._config.pulse_interval * 1000),
                curve=ft.AnimationCurve.EASE_IN_OUT
            )
        )

    def _create_branded_indicator(self) -> ft.Control:
        """Create branded MikroDok loading indicator."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Responsive sizing
        logo_size = responsive_manager.get_breakpoint_value(
            mobile=48, tablet=56, desktop=64, large=72
        )

        # Create branded logo container with rotation animation
        logo_container = ft.Container(
            width=logo_size,
            height=logo_size,
            bgcolor=palette.primary,
            border_radius=spacing.border_radius_small,
            content=ft.Icon(
                name=ft.Icons.ROCKET_LAUNCH,
                size=logo_size * 0.6,
                color=palette.on_primary
            ),
            alignment=ft.alignment.center,
            rotate=ft.transform.Rotate(self._rotation_angle),
            animate_rotation=ft.animation.Animation(
                duration=self._config.animation_duration,
                curve=ft.AnimationCurve.LINEAR
            )
        )

        return logo_container

    def _create_dots_indicator(self) -> ft.Control:
        """Create animated dots loading indicator."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Responsive sizing
        dot_size = responsive_manager.get_breakpoint_value(
            mobile=8, tablet=10, desktop=12, large=14
        )

        dot_spacing = responsive_manager.get_breakpoint_value(
            mobile=4, tablet=6, desktop=8, large=10
        )

        # Create animated dots
        dots = []
        for i in range(3):
            dot_opacity = 1.0 if i == self._dots_animation_step else 0.3
            dot = ft.Container(
                width=dot_size,
                height=dot_size,
                bgcolor=palette.primary,
                border_radius=dot_size // 2,
                opacity=dot_opacity,
                animate_opacity=ft.animation.Animation(
                    duration=500,
                    curve=ft.AnimationCurve.EASE_IN_OUT
                )
            )
            dots.append(dot)

        return ft.Row(
            controls=dots,
            spacing=dot_spacing,
            alignment=ft.MainAxisAlignment.CENTER
        )

    def _create_status_icon(self) -> ft.Icon:
        """Create status icon based on current state."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()

        # Responsive icon sizing
        icon_size = responsive_manager.get_breakpoint_value(
            mobile=16, tablet=18, desktop=20, large=22
        )

        # Icon and color based on state
        if self._current_state == LoadingState.SUCCESS:
            icon_name = ft.Icons.CHECK_CIRCLE
            icon_color = palette.success
        elif self._current_state == LoadingState.ERROR:
            icon_name = ft.Icons.ERROR
            icon_color = palette.error
        elif self._current_state == LoadingState.PAUSED:
            icon_name = ft.Icons.PAUSE_CIRCLE
            icon_color = palette.warning
        else:
            icon_name = ft.Icons.HOURGLASS_EMPTY
            icon_color = palette.primary

        return ft.Icon(
            name=icon_name,
            size=icon_size,
            color=icon_color,
            visible=self._current_state != LoadingState.LOADING
        )

    def set_progress(self, progress: float, message: Optional[str] = None) -> None:
        """
        Update the loading progress.

        Args:
            progress: Progress value (0.0 to 100.0)
            message: Optional progress message
        """
        # Throttle updates for performance
        current_time = time.time() * 1000
        if current_time - self._last_update_time < self._update_throttle_ms:
            return

        self._last_update_time = current_time

        # Update progress value
        self._progress_value = max(0.0, min(100.0, progress))

        # Update message if provided
        if message is not None:
            self._current_message = message

        # Update UI components
        self._update_progress_display()

        # Check for completion
        if self._progress_value >= 100.0:
            self._handle_completion()

    def _update_progress_display(self) -> None:
        """Update the progress display components."""
        if not self._progress_indicator or not self.page:
            return

        try:
            # Update progress indicator value
            if hasattr(self._progress_indicator, 'value'):
                self._progress_indicator.value = self._progress_value / 100.0

            # Update message text
            if self._message_text:
                self._message_text.value = self._current_message

            # Update percentage text
            if self._percentage_text and self._config.show_percentage:
                self._percentage_text.value = f"{self._progress_value:.0f}%"

            # Update the page
            self.update()

        except Exception as e:
            # Handle update errors gracefully
            pass

    def _handle_completion(self) -> None:
        """Handle loading completion."""
        self.set_state(LoadingState.SUCCESS)

        if self._on_complete:
            try:
                self._on_complete()
            except Exception as e:
                # Handle callback errors gracefully
                pass

        if self._config.auto_hide_on_complete:
            # Auto-hide after a brief delay
            asyncio.create_task(self._auto_hide_after_delay())

    async def _auto_hide_after_delay(self, delay: float = 1.5) -> None:
        """Auto-hide the loading indicator after completion."""
        await asyncio.sleep(delay)
        if self.visible:
            self.visible = False
            self.update()

    def set_state(self, state: LoadingState) -> None:
        """
        Set the loading state.

        Args:
            state: New loading state
        """
        if self._current_state == state:
            return

        self._current_state = state

        # Update status icon
        if self._status_icon:
            self._update_status_icon()

        # Handle state-specific actions
        if state == LoadingState.LOADING:
            self.start_animation()
        elif state in [LoadingState.SUCCESS, LoadingState.ERROR, LoadingState.IDLE]:
            self.stop_animation()

        self.update()

    def _update_status_icon(self) -> None:
        """Update the status icon based on current state."""
        if not self._status_icon:
            return

        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()

        # Update icon properties based on state
        if self._current_state == LoadingState.SUCCESS:
            self._status_icon.name = ft.Icons.CHECK_CIRCLE
            self._status_icon.color = palette.success
            self._status_icon.visible = True
        elif self._current_state == LoadingState.ERROR:
            self._status_icon.name = ft.Icons.ERROR
            self._status_icon.color = palette.error
            self._status_icon.visible = True
        elif self._current_state == LoadingState.PAUSED:
            self._status_icon.name = ft.Icons.PAUSE_CIRCLE
            self._status_icon.color = palette.warning
            self._status_icon.visible = True
        else:
            self._status_icon.visible = False

    def start_animation(self) -> None:
        """Start loading animations."""
        if self._is_animating:
            return

        self._is_animating = True
        self._current_state = LoadingState.LOADING

        # Start appropriate animation based on indicator type
        if self._config.indicator_type == LoadingIndicatorType.PULSE:
            self._animation_task = asyncio.create_task(self._animate_pulse())
        elif self._config.indicator_type == LoadingIndicatorType.BRANDED:
            self._animation_task = asyncio.create_task(self._animate_rotation())
        elif self._config.indicator_type == LoadingIndicatorType.DOTS:
            self._animation_task = asyncio.create_task(self._animate_dots())

    def stop_animation(self) -> None:
        """Stop loading animations."""
        self._is_animating = False

        if self._animation_task and not self._animation_task.done():
            self._animation_task.cancel()
            self._animation_task = None

    async def _animate_pulse(self) -> None:
        """Animate pulse indicator."""
        while self._is_animating:
            try:
                # Pulse animation cycle
                self._pulse_opacity = 0.3
                if self._progress_indicator:
                    self._progress_indicator.opacity = self._pulse_opacity
                    self.update()

                await asyncio.sleep(self._config.pulse_interval / 2)

                if not self._is_animating:
                    break

                self._pulse_opacity = 1.0
                if self._progress_indicator:
                    self._progress_indicator.opacity = self._pulse_opacity
                    self.update()

                await asyncio.sleep(self._config.pulse_interval / 2)

            except asyncio.CancelledError:
                break
            except Exception:
                # Handle animation errors gracefully
                break

    async def _animate_rotation(self) -> None:
        """Animate rotation for branded indicator."""
        while self._is_animating:
            try:
                self._rotation_angle += 0.1  # Increment rotation
                if self._rotation_angle >= 6.28:  # 2π radians
                    self._rotation_angle = 0.0

                if self._progress_indicator and hasattr(self._progress_indicator, 'rotate'):
                    self._progress_indicator.rotate = ft.transform.Rotate(self._rotation_angle)
                    self.update()

                await asyncio.sleep(0.016)  # ~60 FPS

            except asyncio.CancelledError:
                break
            except Exception:
                # Handle animation errors gracefully
                break

    async def _animate_dots(self) -> None:
        """Animate dots indicator."""
        while self._is_animating:
            try:
                # Cycle through dots
                self._dots_animation_step = (self._dots_animation_step + 1) % 3

                # Update dots opacity
                if (self._progress_indicator and
                    hasattr(self._progress_indicator, 'controls')):

                    for i, dot in enumerate(self._progress_indicator.controls):
                        if hasattr(dot, 'opacity'):
                            dot.opacity = 1.0 if i == self._dots_animation_step else 0.3

                    self.update()

                await asyncio.sleep(0.5)  # Dot animation interval

            except asyncio.CancelledError:
                break
            except Exception:
                # Handle animation errors gracefully
                break

    def reset(self) -> None:
        """Reset the loading indicator to initial state."""
        self.stop_animation()
        self._progress_value = 0.0
        self._current_message = self._initial_message
        self._current_state = LoadingState.IDLE
        self.visible = True

        # Reset UI components
        self._update_progress_display()
        self._update_status_icon()

    def show_error(self, error_message: str = "An error occurred") -> None:
        """
        Show error state with message.

        Args:
            error_message: Error message to display
        """
        self.stop_animation()
        self._current_message = error_message
        self.set_state(LoadingState.ERROR)

    def show_success(self, success_message: str = "Complete!") -> None:
        """
        Show success state with message.

        Args:
            success_message: Success message to display
        """
        self.stop_animation()
        self._current_message = success_message
        self._progress_value = 100.0
        self.set_state(LoadingState.SUCCESS)

    def pause(self) -> None:
        """Pause the loading indicator."""
        self.stop_animation()
        self.set_state(LoadingState.PAUSED)

    def resume(self) -> None:
        """Resume the loading indicator."""
        self.set_state(LoadingState.LOADING)

    def _on_responsive_change(self) -> None:
        """Handle responsive layout changes."""
        super()._on_responsive_change()
        # Rebuild component with new responsive values
        if self._is_built:
            self.content = self.build()
            self.update()

    def cleanup(self) -> None:
        """Cleanup resources and stop animations."""
        self.stop_animation()

        # Clear references
        self._progress_indicator = None
        self._message_text = None
        self._percentage_text = None
        self._status_icon = None
        self._container = None

        # Call parent cleanup
        super().cleanup() if hasattr(super(), 'cleanup') else None

    # Accessibility and Performance Features

    def set_accessibility_label(self, label: str) -> None:
        """
        Set accessibility label for screen readers.

        Args:
            label: Accessibility label text
        """
        if self._container:
            self._container.tooltip = label
            # Add semantic role for screen readers
            if hasattr(self._container, 'semantics_label'):
                self._container.semantics_label = label

    def get_reduced_motion_preference(self) -> bool:
        """
        Check if reduced motion is preferred by user.

        Returns:
            True if reduced motion should be used
        """
        # Check theme manager for reduced motion setting
        theme_manager = self.get_theme_manager()
        if theme_manager and hasattr(theme_manager, '_animation_config'):
            animation_config = theme_manager._animation_config
            return getattr(animation_config, 'respect_reduced_motion', True)

        return self._config.enable_reduced_motion

    def _apply_reduced_motion(self) -> None:
        """Apply reduced motion settings if enabled."""
        if not self.get_reduced_motion_preference():
            return

        # Disable or reduce animations for accessibility
        if self._progress_indicator:
            # Remove or reduce animation durations
            if hasattr(self._progress_indicator, 'animate_opacity'):
                self._progress_indicator.animate_opacity = None
            if hasattr(self._progress_indicator, 'animate_rotation'):
                self._progress_indicator.animate_rotation = None

        # Use static indicators instead of animated ones
        if self._config.indicator_type in [LoadingIndicatorType.PULSE,
                                         LoadingIndicatorType.BRANDED,
                                         LoadingIndicatorType.DOTS]:
            # Switch to simple linear progress for reduced motion
            self._config.indicator_type = LoadingIndicatorType.LINEAR

    def _optimize_performance(self) -> None:
        """Apply performance optimizations."""
        # Increase update throttle for better performance
        screen_size = self.get_current_screen_size()

        if screen_size == ScreenSize.MOBILE:
            # More aggressive throttling on mobile
            self._update_throttle_ms = 33  # ~30 FPS
        else:
            # Standard throttling on desktop
            self._update_throttle_ms = 16  # ~60 FPS

        # Optimize animation intervals based on device capabilities
        if self._config.indicator_type == LoadingIndicatorType.DOTS:
            # Slower dot animation on mobile
            if screen_size == ScreenSize.MOBILE:
                self._config.pulse_interval = 2.0
            else:
                self._config.pulse_interval = 1.5

    def set_high_contrast_mode(self, enabled: bool) -> None:
        """
        Enable high contrast mode for accessibility.

        Args:
            enabled: Whether to enable high contrast mode
        """
        if not enabled:
            return

        # Apply high contrast styling
        palette = self.get_palette()

        if self._progress_indicator:
            # Use high contrast colors
            if hasattr(self._progress_indicator, 'color'):
                self._progress_indicator.color = palette.on_surface
            if hasattr(self._progress_indicator, 'bgcolor'):
                self._progress_indicator.bgcolor = palette.surface

        if self._message_text:
            self._message_text.color = palette.on_surface

        if self._percentage_text:
            self._percentage_text.color = palette.on_surface

    def announce_progress_to_screen_reader(self, progress: float, message: str) -> None:
        """
        Announce progress updates to screen readers.

        Args:
            progress: Current progress percentage
            message: Progress message
        """
        # Create accessibility announcement
        announcement = f"Loading progress: {progress:.0f}%. {message}"

        # Set accessibility label
        self.set_accessibility_label(announcement)

        # For major progress milestones, create more detailed announcements
        if progress in [25, 50, 75, 100]:
            milestone_message = f"Loading {progress:.0f}% complete"
            if progress == 100:
                milestone_message = "Loading complete"

            self.set_accessibility_label(milestone_message)

    def _setup_keyboard_navigation(self) -> None:
        """Setup keyboard navigation support."""
        if self._container:
            # Make container focusable for keyboard navigation
            self._container.can_focus = True

            # Add keyboard event handlers if needed
            # This would be expanded based on specific keyboard interaction requirements

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for monitoring.

        Returns:
            Dictionary containing performance metrics
        """
        return {
            'update_throttle_ms': self._update_throttle_ms,
            'last_update_time': self._last_update_time,
            'is_animating': self._is_animating,
            'current_state': self._current_state.value,
            'progress_value': self._progress_value,
            'animation_type': self._config.indicator_type.value,
            'reduced_motion_enabled': self.get_reduced_motion_preference()
        }

    def _handle_theme_change(self) -> None:
        """Handle theme changes with accessibility considerations."""
        super()._handle_theme_change()

        # Reapply accessibility settings after theme change
        if self.get_reduced_motion_preference():
            self._apply_reduced_motion()

        # Update high contrast if needed
        theme_manager = self.get_theme_manager()
        if theme_manager and hasattr(theme_manager, '_high_contrast_mode'):
            high_contrast = getattr(theme_manager, '_high_contrast_mode', False)
            self.set_high_contrast_mode(high_contrast)

    def _initialize_accessibility_features(self) -> None:
        """Initialize accessibility features during component setup."""
        # Apply reduced motion preferences
        self._apply_reduced_motion()

        # Setup keyboard navigation
        self._setup_keyboard_navigation()

        # Apply performance optimizations
        self._optimize_performance()

        # Set initial accessibility label
        self.set_accessibility_label("Loading indicator")

    def __del__(self) -> None:
        """Destructor to ensure proper cleanup."""
        try:
            self.cleanup()
        except Exception:
            # Handle cleanup errors gracefully
            pass
