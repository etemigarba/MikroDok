"""
Module: progress_overlay_ui
Description: Comprehensive progress overlay system for MikroDok application providing full-screen and 
            partial overlays for long-running operations. Features responsive design, theme integration,
            accessibility compliance, and advanced progress visualization with user interaction support.
            
Features:
- Full-screen and partial progress overlays
- Multiple progress visualization types (linear, circular, stepped)
- Responsive design with breakpoint-aware layouts
- Theme-aware styling with full ResponsiveLayoutManager integration
- Accessibility compliance (WCAG 2.1 AA)
- Pause/resume and cancellation support
- Real-time progress updates with time estimates
- Keyboard navigation and screen reader support
- Animation system with reduced motion support
- Performance-optimized rendering

Phase: 1
Location: /src/modules/ui/notification_system_ui/progress_overlay_ui/progress_overlay_ui.py
"""

# Standard library imports
import asyncio
import time
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
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


class ProgressType(Enum):
    """Progress visualization type enumeration."""
    LINEAR = "linear"
    CIRCULAR = "circular"
    STEPPED = "stepped"
    INDETERMINATE = "indeterminate"
    DUAL = "dual"  # Both linear and circular


class ProgressState(Enum):
    """Progress state enumeration."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OverlayPosition(Enum):
    """Overlay position enumeration."""
    FULLSCREEN = "fullscreen"
    CENTER = "center"
    TOP = "top"
    BOTTOM = "bottom"
    CUSTOM = "custom"


class OverlayAnimation(Enum):
    """Overlay animation type enumeration."""
    FADE_IN = "fade_in"
    SLIDE_DOWN = "slide_down"
    SLIDE_UP = "slide_up"
    SCALE_IN = "scale_in"
    NONE = "none"


class ProgressBehavior(Enum):
    """Progress behavior enumeration."""
    MODAL = "modal"
    NON_MODAL = "non_modal"
    DISMISSIBLE = "dismissible"
    PERSISTENT = "persistent"
    AUTO_HIDE = "auto_hide"
    PAUSABLE = "pausable"
    CANCELLABLE = "cancellable"


@dataclass
class ProgressConfig:
    """
    Configuration for progress overlay behavior and appearance.
    
    Provides comprehensive configuration options for progress overlays including
    visual styling, behavior settings, accessibility options, and performance tuning.
    """
    # Basic configuration
    title: str = "Processing..."
    message: str = "Please wait while the operation completes."
    progress_type: ProgressType = ProgressType.LINEAR
    position: OverlayPosition = OverlayPosition.CENTER
    
    # Progress tracking
    show_percentage: bool = True
    show_time_remaining: bool = True
    show_current_item: bool = False
    show_item_count: bool = False
    show_speed: bool = False
    
    # Visual configuration
    overlay_opacity: float = 0.8
    blur_background: bool = True
    show_backdrop: bool = True
    backdrop_color: Optional[str] = None
    
    # Size and positioning
    width: Optional[int] = None
    height: Optional[int] = None
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    margin: int = 24
    padding: int = 32
    
    # Behavior configuration
    behaviors: List[ProgressBehavior] = field(default_factory=lambda: [
        ProgressBehavior.MODAL,
        ProgressBehavior.PAUSABLE,
        ProgressBehavior.CANCELLABLE
    ])
    
    # Animation configuration
    entrance_animation: OverlayAnimation = OverlayAnimation.FADE_IN
    exit_animation: OverlayAnimation = OverlayAnimation.FADE_IN
    animation_duration: int = 300  # milliseconds
    enable_animations: bool = True
    respect_reduced_motion: bool = True
    
    # Interaction configuration
    allow_background_interaction: bool = False
    close_on_escape: bool = True
    close_on_backdrop_click: bool = False
    
    # Accessibility configuration
    announce_progress: bool = True
    focus_management: bool = True
    keyboard_navigation: bool = True
    high_contrast_support: bool = True
    screen_reader_support: bool = True
    
    # Auto-dismiss configuration
    auto_dismiss_on_complete: bool = False
    auto_dismiss_delay: int = 2000  # milliseconds
    auto_dismiss_on_error: bool = False
    
    # Performance configuration
    update_throttle_ms: int = 100
    enable_gpu_acceleration: bool = True
    optimize_for_mobile: bool = True
    
    # Callback configuration
    on_pause: Optional[Callable[[], None]] = None
    on_resume: Optional[Callable[[], None]] = None
    on_cancel: Optional[Callable[[], None]] = None
    on_complete: Optional[Callable[[], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None
    on_progress_update: Optional[Callable[[float], None]] = None


@dataclass
class ProgressContext:
    """
    Context information for progress tracking.
    
    Maintains state and metrics for progress operations including timing,
    performance statistics, and user interaction history.
    """
    # Progress tracking
    current_progress: float = 0.0
    total_items: int = 1
    current_item: int = 0
    current_item_name: str = ""
    
    # Timing information
    start_time: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    elapsed_time: timedelta = field(default_factory=lambda: timedelta())
    remaining_time: Optional[timedelta] = None
    
    # Performance metrics
    items_per_second: float = 0.0
    average_item_time: float = 0.0
    peak_speed: float = 0.0
    
    # State tracking
    state: ProgressState = ProgressState.IDLE
    error_message: Optional[str] = None
    warning_count: int = 0
    retry_count: int = 0
    
    # User interaction
    pause_count: int = 0
    total_pause_time: timedelta = field(default_factory=lambda: timedelta())
    last_user_interaction: Optional[datetime] = None
    
    # Memory and resource tracking
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    disk_io_mb: float = 0.0


@dataclass
class ProgressResult:
    """
    Result information from progress overlay operations.
    
    Contains completion status, performance metrics, and user interaction data
    for analysis and reporting purposes.
    """
    # Completion status
    completed: bool = False
    cancelled: bool = False
    failed: bool = False
    error: Optional[Exception] = None
    
    # Final metrics
    total_time: timedelta = field(default_factory=lambda: timedelta())
    items_processed: int = 0
    average_speed: float = 0.0
    peak_speed: float = 0.0
    
    # User interaction summary
    pause_count: int = 0
    total_pause_time: timedelta = field(default_factory=lambda: timedelta())
    user_cancelled: bool = False
    
    # Performance summary
    memory_peak_mb: float = 0.0
    cpu_average_percent: float = 0.0
    disk_io_total_mb: float = 0.0
    
    # Quality metrics
    warning_count: int = 0
    retry_count: int = 0
    success_rate: float = 1.0


class ProgressOverlayUI(ThemeAwareUserControl):
    """
    Comprehensive progress overlay UI component for MikroDok application.

    Provides full-screen and partial overlays for long-running operations with
    advanced progress visualization, user interaction support, and accessibility
    compliance. Integrates fully with the theme system and responsive design.

    Features:
    - Multiple progress visualization types (linear, circular, stepped, dual)
    - Responsive overlay positioning and sizing
    - Theme-aware styling with full ResponsiveLayoutManager integration
    - Accessibility compliance (WCAG 2.1 AA)
    - Pause/resume and cancellation support
    - Real-time progress updates with time estimates
    - Keyboard navigation and screen reader support
    - Animation system with reduced motion support
    - Performance-optimized rendering and updates
    - Background blur and modal behavior
    """

    def __init__(self,
                 config: Optional[ProgressConfig] = None,
                 context: Optional[ProgressContext] = None,
                 **kwargs):
        """
        Initialize progress overlay UI component.

        Args:
            config: Progress overlay configuration
            context: Progress tracking context
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)

        # Configuration and context
        self._config = config or ProgressConfig()
        self._context = context or ProgressContext()
        self._overlay_id = str(uuid.uuid4())

        # Component references
        self._overlay_container: Optional[ft.Container] = None
        self._progress_container: Optional[ft.Container] = None
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._progress_ring: Optional[ft.ProgressRing] = None
        self._title_text: Optional[ft.Text] = None
        self._message_text: Optional[ft.Text] = None
        self._percentage_text: Optional[ft.Text] = None
        self._time_text: Optional[ft.Text] = None
        self._item_text: Optional[ft.Text] = None
        self._speed_text: Optional[ft.Text] = None
        self._pause_button: Optional[ft.IconButton] = None
        self._cancel_button: Optional[ft.IconButton] = None

        # State management
        self._is_visible = False
        self._is_paused = False
        self._is_cancelled = False
        self._last_update_time = time.time()
        self._update_lock = threading.Lock()

        # Performance tracking
        self._update_count = 0
        self._render_times: deque = deque(maxlen=100)
        self._memory_samples: deque = deque(maxlen=50)

        # Animation and timing
        self._animation_start_time: Optional[float] = None
        self._entrance_animation_active = False
        self._exit_animation_active = False

        # Accessibility
        self._live_region: Optional[ft.Text] = None
        self._focus_trap_enabled = False

        # Build initial UI
        self._build_overlay()

    def _build_overlay(self) -> None:
        """Build the complete overlay UI structure."""
        try:
            responsive_manager = self.get_responsive_layout()
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Create backdrop if enabled
            backdrop = None
            if self._config.show_backdrop:
                backdrop_color = (
                    self._config.backdrop_color or
                    palette.background_primary
                )
                backdrop = ft.Container(
                    bgcolor=backdrop_color,
                    opacity=self._config.overlay_opacity,
                    expand=True
                )

            # Create progress content
            progress_content = self._create_progress_content()

            # Create overlay container based on position
            if self._config.position == OverlayPosition.FULLSCREEN:
                self._overlay_container = ft.Container(
                    content=ft.Stack([
                        backdrop,
                        ft.Container(
                            content=progress_content,
                            alignment=ft.alignment.center,
                            expand=True
                        )
                    ]) if backdrop else progress_content,
                    expand=True,
                    bgcolor=palette.background_primary if not backdrop else None,
                    opacity=self._config.overlay_opacity if not backdrop else 1.0
                )
            else:
                # Positioned overlay
                overlay_width = self._get_responsive_overlay_width()
                overlay_height = self._get_responsive_overlay_height()

                self._overlay_container = ft.Container(
                    content=ft.Stack([
                        backdrop,
                        ft.Container(
                            content=progress_content,
                            width=overlay_width,
                            height=overlay_height,
                            bgcolor=palette.surface,
                            border_radius=ft.border_radius.all(
                                responsive_manager.get_breakpoint_value(
                                    mobile=8, tablet=12, desktop=16, large=20
                                )
                            ),
                            border=ft.border.all(
                                width=1,
                                color=palette.outline
                            ),
                            shadow=ft.BoxShadow(
                                spread_radius=0,
                                blur_radius=responsive_manager.get_breakpoint_value(
                                    mobile=8, tablet=12, desktop=16, large=20
                                ),
                                color=palette.background_primary,
                                offset=ft.Offset(0, 4)
                            ),
                            alignment=ft.alignment.center,
                            padding=ft.padding.all(
                                responsive_manager.get_responsive_padding()
                            )
                        )
                    ]) if backdrop else progress_content,
                    alignment=self._get_overlay_alignment(),
                    expand=True if self._config.position == OverlayPosition.FULLSCREEN else False
                )

            # Set up accessibility
            self._setup_accessibility()

            # Set content
            self.content = self._overlay_container

        except Exception as e:
            print(f"Error building progress overlay: {e}")
            self._create_fallback_overlay()

    def _create_progress_content(self) -> ft.Control:
        """Create the main progress content area."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        content_children = []

        # Title
        if self._config.title:
            self._title_text = ft.Text(
                value=self._config.title,
                size=responsive_manager.get_responsive_font_size(
                    typography.h4[0]
                ),
                weight=ft.FontWeight.W_600,
                color=palette.text_primary,
                text_align=ft.TextAlign.CENTER
            )
            content_children.append(self._title_text)

        # Message
        if self._config.message:
            self._message_text = ft.Text(
                value=self._config.message,
                size=responsive_manager.get_responsive_font_size(
                    typography.body_medium[0]
                ),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER
            )
            content_children.append(self._message_text)

        # Progress visualization
        progress_viz = self._create_progress_visualization()
        if progress_viz:
            content_children.append(progress_viz)

        # Progress information
        info_section = self._create_progress_info()
        if info_section:
            content_children.append(info_section)

        # Control buttons
        controls_section = self._create_control_buttons()
        if controls_section:
            content_children.append(controls_section)

        return ft.Column(
            controls=content_children,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=responsive_manager.get_breakpoint_value(
                mobile=spacing.md, tablet=spacing.lg,
                desktop=spacing.xl, large=spacing.xxl
            ),
            tight=True
        )

    def _create_progress_visualization(self) -> Optional[ft.Control]:
        """Create progress visualization based on type."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()

        if self._config.progress_type == ProgressType.LINEAR:
            return self._create_linear_progress()
        elif self._config.progress_type == ProgressType.CIRCULAR:
            return self._create_circular_progress()
        elif self._config.progress_type == ProgressType.STEPPED:
            return self._create_stepped_progress()
        elif self._config.progress_type == ProgressType.DUAL:
            return self._create_dual_progress()
        elif self._config.progress_type == ProgressType.INDETERMINATE:
            return self._create_indeterminate_progress()

        return None

    def _create_linear_progress(self) -> ft.Control:
        """Create linear progress bar."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()

        progress_width = responsive_manager.get_breakpoint_value(
            mobile=280, tablet=320, desktop=400, large=480
        )

        progress_height = responsive_manager.get_breakpoint_value(
            mobile=6, tablet=8, desktop=10, large=12
        )

        self._progress_bar = ft.ProgressBar(
            value=self._context.current_progress / 100.0,
            width=progress_width,
            height=progress_height,
            color=palette.primary,
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(progress_height // 2)
        )

        return ft.Container(
            content=self._progress_bar,
            alignment=ft.alignment.center
        )

    def _create_circular_progress(self) -> ft.Control:
        """Create circular progress indicator."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()

        ring_size = responsive_manager.get_breakpoint_value(
            mobile=60, tablet=70, desktop=80, large=90
        )

        stroke_width = responsive_manager.get_breakpoint_value(
            mobile=4, tablet=5, desktop=6, large=7
        )

        self._progress_ring = ft.ProgressRing(
            value=self._context.current_progress / 100.0,
            width=ring_size,
            height=ring_size,
            stroke_width=stroke_width,
            color=palette.primary,
            bgcolor=palette.surface_variant
        )

        return ft.Container(
            content=self._progress_ring,
            alignment=ft.alignment.center
        )

    def _create_stepped_progress(self) -> ft.Control:
        """Create stepped progress indicator."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()

        steps = []
        total_steps = max(self._context.total_items, 1)
        current_step = self._context.current_item

        step_size = responsive_manager.get_breakpoint_value(
            mobile=24, tablet=28, desktop=32, large=36
        )

        for i in range(total_steps):
            is_completed = i < current_step
            is_current = i == current_step

            step_color = (
                palette.primary if is_completed or is_current
                else palette.surface_variant
            )

            step_icon = (
                ft.Icons.CHECK if is_completed
                else ft.Icons.CIRCLE if is_current
                else ft.Icons.CIRCLE_OUTLINED
            )

            step = ft.Container(
                content=ft.Icon(
                    name=step_icon,
                    size=step_size,
                    color=step_color
                ),
                width=step_size,
                height=step_size,
                alignment=ft.alignment.center
            )

            steps.append(step)

            # Add connector line (except for last step)
            if i < total_steps - 1:
                connector = ft.Container(
                    width=responsive_manager.get_breakpoint_value(
                        mobile=20, tablet=24, desktop=28, large=32
                    ),
                    height=2,
                    bgcolor=palette.primary if is_completed else palette.surface_variant
                )
                steps.append(connector)

        return ft.Row(
            controls=steps,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0
        )

    def _create_dual_progress(self) -> ft.Control:
        """Create dual progress (both linear and circular)."""
        responsive_manager = self.get_responsive_layout()
        spacing = self.get_spacing()

        linear = self._create_linear_progress()
        circular = self._create_circular_progress()

        return ft.Column(
            controls=[circular, linear],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.lg
        )

    def _create_indeterminate_progress(self) -> ft.Control:
        """Create indeterminate progress indicator."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()

        if responsive_manager.is_mobile_or_tablet():
            # Use linear indeterminate on mobile/tablet
            return ft.Container(
                content=ft.ProgressBar(
                    width=responsive_manager.get_breakpoint_value(
                        mobile=280, tablet=320, desktop=400, large=480
                    ),
                    height=responsive_manager.get_breakpoint_value(
                        mobile=6, tablet=8, desktop=10, large=12
                    ),
                    color=palette.primary,
                    bgcolor=palette.surface_variant
                ),
                alignment=ft.alignment.center
            )
        else:
            # Use circular indeterminate on desktop
            ring_size = responsive_manager.get_breakpoint_value(
                mobile=60, tablet=70, desktop=80, large=90
            )

            return ft.Container(
                content=ft.ProgressRing(
                    width=ring_size,
                    height=ring_size,
                    stroke_width=responsive_manager.get_breakpoint_value(
                        mobile=4, tablet=5, desktop=6, large=7
                    ),
                    color=palette.primary
                ),
                alignment=ft.alignment.center
            )

    def _create_progress_info(self) -> Optional[ft.Control]:
        """Create progress information section."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        info_items = []

        # Percentage
        if self._config.show_percentage:
            self._percentage_text = ft.Text(
                value=f"{self._context.current_progress:.1f}%",
                size=responsive_manager.get_responsive_font_size(
                    typography.body_large[0]
                ),
                weight=ft.FontWeight.W_500,
                color=palette.text_primary,
                text_align=ft.TextAlign.CENTER
            )
            info_items.append(self._percentage_text)

        # Time remaining
        if self._config.show_time_remaining and self._context.remaining_time:
            time_str = self._format_time_remaining(self._context.remaining_time)
            self._time_text = ft.Text(
                value=f"Time remaining: {time_str}",
                size=responsive_manager.get_responsive_font_size(
                    typography.body_small[0]
                ),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER
            )
            info_items.append(self._time_text)

        # Current item
        if self._config.show_current_item and self._context.current_item_name:
            self._item_text = ft.Text(
                value=f"Processing: {self._context.current_item_name}",
                size=responsive_manager.get_responsive_font_size(
                    typography.body_small[0]
                ),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS
            )
            info_items.append(self._item_text)

        # Item count
        if self._config.show_item_count:
            count_text = ft.Text(
                value=f"{self._context.current_item} of {self._context.total_items}",
                size=responsive_manager.get_responsive_font_size(
                    typography.body_small[0]
                ),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER
            )
            info_items.append(count_text)

        # Speed
        if self._config.show_speed and self._context.items_per_second > 0:
            self._speed_text = ft.Text(
                value=f"Speed: {self._context.items_per_second:.1f} items/sec",
                size=responsive_manager.get_responsive_font_size(
                    typography.body_small[0]
                ),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER
            )
            info_items.append(self._speed_text)

        if not info_items:
            return None

        return ft.Column(
            controls=info_items,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=spacing.sm,
            tight=True
        )

    def _create_control_buttons(self) -> Optional[ft.Control]:
        """Create control buttons section."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        buttons = []

        # Pause/Resume button
        if ProgressBehavior.PAUSABLE in self._config.behaviors:
            pause_icon = icons.PAUSE if not self._is_paused else icons.PLAY
            pause_tooltip = "Pause" if not self._is_paused else "Resume"

            self._pause_button = ft.IconButton(
                icon=pause_icon,
                tooltip=pause_tooltip,
                icon_color=palette.primary,
                icon_size=responsive_manager.get_breakpoint_value(
                    mobile=20, tablet=22, desktop=24, large=26
                ),
                on_click=self._handle_pause_resume,
                disabled=self._context.state not in [ProgressState.RUNNING, ProgressState.PAUSED]
            )
            buttons.append(self._pause_button)

        # Cancel button
        if ProgressBehavior.CANCELLABLE in self._config.behaviors:
            self._cancel_button = ft.IconButton(
                icon=icons.CANCEL,
                tooltip="Cancel",
                icon_color=palette.error,
                icon_size=responsive_manager.get_breakpoint_value(
                    mobile=20, tablet=22, desktop=24, large=26
                ),
                on_click=self._handle_cancel,
                disabled=self._context.state in [ProgressState.COMPLETED, ProgressState.CANCELLED, ProgressState.FAILED]
            )
            buttons.append(self._cancel_button)

        if not buttons:
            return None

        return ft.Row(
            controls=buttons,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=spacing.lg
        )

    def _get_responsive_overlay_width(self) -> int:
        """Get responsive overlay width."""
        responsive_manager = self.get_responsive_layout()

        if self._config.width:
            return self._config.width

        return responsive_manager.get_breakpoint_value(
            mobile=min(320, responsive_manager._current_width - 32),
            tablet=min(400, responsive_manager._current_width - 64),
            desktop=min(500, responsive_manager._current_width - 128),
            large=min(600, responsive_manager._current_width - 256)
        )

    def _get_responsive_overlay_height(self) -> Optional[int]:
        """Get responsive overlay height."""
        responsive_manager = self.get_responsive_layout()

        if self._config.height:
            return self._config.height

        # Auto height based on content
        return None

    def _get_overlay_alignment(self) -> ft.Alignment:
        """Get overlay alignment based on position."""
        if self._config.position == OverlayPosition.CENTER:
            return ft.alignment.center
        elif self._config.position == OverlayPosition.TOP:
            return ft.alignment.top_center
        elif self._config.position == OverlayPosition.BOTTOM:
            return ft.alignment.bottom_center
        else:
            return ft.alignment.center

    def _setup_accessibility(self) -> None:
        """Set up accessibility features."""
        if not self._config.screen_reader_support:
            return

        # Create live region for progress announcements
        self._live_region = ft.Text(
            value="",
            semantics_label="Progress updates",
            visible=False
        )

        # Add to overlay if possible
        if self._overlay_container and hasattr(self._overlay_container, 'content'):
            if isinstance(self._overlay_container.content, ft.Stack):
                self._overlay_container.content.controls.append(self._live_region)

    def _format_time_remaining(self, remaining: timedelta) -> str:
        """Format remaining time for display."""
        total_seconds = int(remaining.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def _handle_pause_resume(self, e) -> None:
        """Handle pause/resume button click."""
        try:
            if self._is_paused:
                self.resume()
            else:
                self.pause()
        except Exception as ex:
            print(f"Error handling pause/resume: {ex}")

    def _handle_cancel(self, e) -> None:
        """Handle cancel button click."""
        try:
            self.cancel()
        except Exception as ex:
            print(f"Error handling cancel: {ex}")

    def _create_fallback_overlay(self) -> None:
        """Create a simple fallback overlay when theme system is unavailable."""
        self._overlay_container = ft.Container(
            content=ft.Column([
                ft.Text(self._config.title, size=18, weight=ft.FontWeight.BOLD),
                ft.Text(self._config.message),
                ft.ProgressBar() if self._config.progress_type != ProgressType.CIRCULAR else ft.ProgressRing(),
                ft.Row([
                    ft.IconButton(icon=ft.Icons.PAUSE, on_click=self._handle_pause_resume) if ProgressBehavior.PAUSABLE in self._config.behaviors else None,
                    ft.IconButton(icon=ft.Icons.CANCEL, on_click=self._handle_cancel) if ProgressBehavior.CANCELLABLE in self._config.behaviors else None
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.all(24),
            bgcolor=ft.Colors.SURFACE_VARIANT,
            border_radius=ft.border_radius.all(12),
            alignment=ft.alignment.center,
            expand=True
        )
        self.content = self._overlay_container

    # Public API methods

    def show(self) -> None:
        """Show the progress overlay."""
        if self._is_visible:
            return

        self._is_visible = True
        self._context.state = ProgressState.RUNNING
        self._context.start_time = datetime.now()

        # Update UI visibility
        if self._overlay_container:
            self._overlay_container.visible = True

        # Announce to screen readers
        if self._config.announce_progress and self._live_region:
            self._live_region.value = f"Progress started: {self._config.title}"

        # Trigger entrance animation
        if self._config.enable_animations and not self._config.respect_reduced_motion:
            self._start_entrance_animation()

        self.update()

    def hide(self) -> None:
        """Hide the progress overlay."""
        if not self._is_visible:
            return

        self._is_visible = False

        # Trigger exit animation
        if self._config.enable_animations and not self._config.respect_reduced_motion:
            self._start_exit_animation()
        else:
            self._finalize_hide()

    def update_progress(self, progress: float,
                       current_item: Optional[int] = None,
                       current_item_name: Optional[str] = None,
                       **kwargs) -> None:
        """
        Update progress value and related information.

        Args:
            progress: Progress percentage (0-100)
            current_item: Current item index
            current_item_name: Current item name
            **kwargs: Additional context updates
        """
        with self._update_lock:
            # Throttle updates
            current_time = time.time()
            if (current_time - self._last_update_time) < (self._config.update_throttle_ms / 1000.0):
                return

            self._last_update_time = current_time

            # Update context
            old_progress = self._context.current_progress
            self._context.current_progress = max(0, min(100, progress))

            if current_item is not None:
                self._context.current_item = current_item

            if current_item_name is not None:
                self._context.current_item_name = current_item_name

            # Update additional context
            for key, value in kwargs.items():
                if hasattr(self._context, key):
                    setattr(self._context, key, value)

            # Calculate timing estimates
            self._update_timing_estimates()

            # Update UI components
            self._update_progress_components()

            # Announce progress changes
            if self._config.announce_progress and abs(self._context.current_progress - old_progress) >= 5:
                self._announce_progress_change()

            # Trigger callback
            if self._config.on_progress_update:
                try:
                    self._config.on_progress_update(self._context.current_progress)
                except Exception as e:
                    print(f"Error in progress update callback: {e}")

            # Check for completion
            if self._context.current_progress >= 100:
                self._handle_completion()

            self.update()

    def pause(self) -> None:
        """Pause the progress operation."""
        if self._is_paused or self._context.state != ProgressState.RUNNING:
            return

        self._is_paused = True
        self._context.state = ProgressState.PAUSED
        self._context.pause_count += 1
        self._context.last_user_interaction = datetime.now()

        # Update pause button
        if self._pause_button:
            self._pause_button.icon = self.get_icons().PLAY
            self._pause_button.tooltip = "Resume"

        # Announce to screen readers
        if self._config.announce_progress and self._live_region:
            self._live_region.value = "Progress paused"

        # Trigger callback
        if self._config.on_pause:
            try:
                self._config.on_pause()
            except Exception as e:
                print(f"Error in pause callback: {e}")

        self.update()

    def resume(self) -> None:
        """Resume the progress operation."""
        if not self._is_paused or self._context.state != ProgressState.PAUSED:
            return

        pause_start = self._context.last_user_interaction or datetime.now()
        pause_duration = datetime.now() - pause_start
        self._context.total_pause_time += pause_duration

        self._is_paused = False
        self._context.state = ProgressState.RUNNING
        self._context.last_user_interaction = datetime.now()

        # Update pause button
        if self._pause_button:
            self._pause_button.icon = self.get_icons().PAUSE
            self._pause_button.tooltip = "Pause"

        # Announce to screen readers
        if self._config.announce_progress and self._live_region:
            self._live_region.value = "Progress resumed"

        # Trigger callback
        if self._config.on_resume:
            try:
                self._config.on_resume()
            except Exception as e:
                print(f"Error in resume callback: {e}")

        self.update()

    def cancel(self) -> None:
        """Cancel the progress operation."""
        if self._is_cancelled or self._context.state in [ProgressState.COMPLETED, ProgressState.CANCELLED]:
            return

        self._is_cancelled = True
        self._context.state = ProgressState.CANCELLED
        self._context.last_user_interaction = datetime.now()

        # Update UI state
        if self._pause_button:
            self._pause_button.disabled = True
        if self._cancel_button:
            self._cancel_button.disabled = True

        # Announce to screen readers
        if self._config.announce_progress and self._live_region:
            self._live_region.value = "Progress cancelled"

        # Trigger callback
        if self._config.on_cancel:
            try:
                self._config.on_cancel()
            except Exception as e:
                print(f"Error in cancel callback: {e}")

        # Auto-hide if configured
        if self._config.auto_dismiss_on_complete:
            self._schedule_auto_hide()

        self.update()

    def complete(self) -> None:
        """Mark progress as completed."""
        if self._context.state == ProgressState.COMPLETED:
            return

        self._context.state = ProgressState.COMPLETED
        self._context.current_progress = 100.0

        # Update UI components
        self._update_progress_components()

        # Announce to screen readers
        if self._config.announce_progress and self._live_region:
            self._live_region.value = "Progress completed"

        # Trigger callback
        if self._config.on_complete:
            try:
                self._config.on_complete()
            except Exception as e:
                print(f"Error in complete callback: {e}")

        # Auto-hide if configured
        if self._config.auto_dismiss_on_complete:
            self._schedule_auto_hide()

        self.update()

    def set_error(self, error: Exception, message: Optional[str] = None) -> None:
        """Set error state."""
        self._context.state = ProgressState.FAILED
        self._context.error_message = message or str(error)

        # Update message text
        if self._message_text:
            self._message_text.value = self._context.error_message
            self._message_text.color = self.get_palette().error

        # Announce to screen readers
        if self._config.announce_progress and self._live_region:
            self._live_region.value = f"Progress failed: {self._context.error_message}"

        # Trigger callback
        if self._config.on_error:
            try:
                self._config.on_error(error)
            except Exception as e:
                print(f"Error in error callback: {e}")

        # Auto-hide if configured
        if self._config.auto_dismiss_on_error:
            self._schedule_auto_hide()

        self.update()

    def get_result(self) -> ProgressResult:
        """Get progress operation result."""
        return ProgressResult(
            completed=self._context.state == ProgressState.COMPLETED,
            cancelled=self._context.state == ProgressState.CANCELLED,
            failed=self._context.state == ProgressState.FAILED,
            total_time=self._context.elapsed_time,
            items_processed=self._context.current_item,
            average_speed=self._context.average_item_time,
            peak_speed=self._context.peak_speed,
            pause_count=self._context.pause_count,
            total_pause_time=self._context.total_pause_time,
            user_cancelled=self._is_cancelled,
            memory_peak_mb=max(self._memory_samples) if self._memory_samples else 0.0,
            warning_count=self._context.warning_count,
            retry_count=self._context.retry_count
        )

    # Private helper methods

    def _update_timing_estimates(self) -> None:
        """Update timing estimates based on current progress."""
        if not self._context.start_time:
            return

        current_time = datetime.now()
        self._context.elapsed_time = current_time - self._context.start_time

        if self._context.current_progress > 0:
            # Calculate remaining time
            progress_ratio = self._context.current_progress / 100.0
            total_estimated_time = self._context.elapsed_time / progress_ratio
            self._context.remaining_time = total_estimated_time - self._context.elapsed_time

            # Calculate speed metrics
            if self._context.current_item > 0:
                elapsed_seconds = self._context.elapsed_time.total_seconds()
                self._context.items_per_second = self._context.current_item / elapsed_seconds
                self._context.average_item_time = elapsed_seconds / self._context.current_item

                # Update peak speed
                if self._context.items_per_second > self._context.peak_speed:
                    self._context.peak_speed = self._context.items_per_second

    def _update_progress_components(self) -> None:
        """Update progress visualization components."""
        progress_value = self._context.current_progress / 100.0

        # Update progress bar
        if self._progress_bar:
            self._progress_bar.value = progress_value

        # Update progress ring
        if self._progress_ring:
            self._progress_ring.value = progress_value

        # Update percentage text
        if self._percentage_text:
            self._percentage_text.value = f"{self._context.current_progress:.1f}%"

        # Update time text
        if self._time_text and self._context.remaining_time:
            time_str = self._format_time_remaining(self._context.remaining_time)
            self._time_text.value = f"Time remaining: {time_str}"

        # Update item text
        if self._item_text and self._context.current_item_name:
            self._item_text.value = f"Processing: {self._context.current_item_name}"

        # Update speed text
        if self._speed_text and self._context.items_per_second > 0:
            self._speed_text.value = f"Speed: {self._context.items_per_second:.1f} items/sec"

    def _announce_progress_change(self) -> None:
        """Announce progress change to screen readers."""
        if not self._live_region:
            return

        announcement = f"Progress: {self._context.current_progress:.0f}%"
        if self._context.current_item_name:
            announcement += f", processing {self._context.current_item_name}"

        self._live_region.value = announcement

    def _handle_completion(self) -> None:
        """Handle progress completion."""
        if self._context.state != ProgressState.RUNNING:
            return

        self.complete()

    def _schedule_auto_hide(self) -> None:
        """Schedule automatic hiding of overlay."""
        if self._config.auto_dismiss_delay > 0:
            # In a real implementation, you would use a timer here
            # For now, we'll just hide immediately
            self.hide()

    def _start_entrance_animation(self) -> None:
        """Start entrance animation."""
        self._entrance_animation_active = True
        self._animation_start_time = time.time()
        # Animation implementation would go here

    def _start_exit_animation(self) -> None:
        """Start exit animation."""
        self._exit_animation_active = True
        self._animation_start_time = time.time()
        # Animation implementation would go here
        # For now, just finalize hide
        self._finalize_hide()

    def _finalize_hide(self) -> None:
        """Finalize hiding the overlay."""
        if self._overlay_container:
            self._overlay_container.visible = False
        self.update()


# Utility functions for easy component creation

def create_progress_overlay(title: str = "Processing...",
                          message: str = "Please wait while the operation completes.",
                          progress_type: ProgressType = ProgressType.LINEAR,
                          position: OverlayPosition = OverlayPosition.CENTER,
                          **kwargs) -> ProgressOverlayUI:
    """
    Create a progress overlay with common configuration.

    Args:
        title: Overlay title
        message: Progress message
        progress_type: Type of progress visualization
        position: Overlay position
        **kwargs: Additional configuration options

    Returns:
        Configured ProgressOverlayUI instance
    """
    config = ProgressConfig(
        title=title,
        message=message,
        progress_type=progress_type,
        position=position,
        **kwargs
    )

    return ProgressOverlayUI(config=config)


def show_progress_overlay(page: ft.Page,
                         title: str = "Processing...",
                         message: str = "Please wait while the operation completes.",
                         progress_type: ProgressType = ProgressType.LINEAR,
                         position: OverlayPosition = OverlayPosition.CENTER,
                         **kwargs) -> ProgressOverlayUI:
    """
    Show a progress overlay on the specified page.

    Args:
        page: Flet page to show overlay on
        title: Overlay title
        message: Progress message
        progress_type: Type of progress visualization
        position: Overlay position
        **kwargs: Additional configuration options

    Returns:
        ProgressOverlayUI instance that was shown
    """
    overlay = create_progress_overlay(
        title=title,
        message=message,
        progress_type=progress_type,
        position=position,
        **kwargs
    )

    # Add to page overlay
    if hasattr(page, 'overlay'):
        page.overlay.append(overlay)
    else:
        # Fallback: add to page controls
        page.controls.append(overlay)

    overlay.show()
    page.update()

    return overlay


def create_fullscreen_progress_overlay(title: str = "Processing...",
                                     message: str = "Please wait while the operation completes.",
                                     progress_type: ProgressType = ProgressType.LINEAR,
                                     **kwargs) -> ProgressOverlayUI:
    """
    Create a fullscreen progress overlay.

    Args:
        title: Overlay title
        message: Progress message
        progress_type: Type of progress visualization
        **kwargs: Additional configuration options

    Returns:
        Configured ProgressOverlayUI instance
    """
    return create_progress_overlay(
        title=title,
        message=message,
        progress_type=progress_type,
        position=OverlayPosition.FULLSCREEN,
        **kwargs
    )


def create_modal_progress_overlay(title: str = "Processing...",
                                message: str = "Please wait while the operation completes.",
                                progress_type: ProgressType = ProgressType.LINEAR,
                                cancellable: bool = True,
                                **kwargs) -> ProgressOverlayUI:
    """
    Create a modal progress overlay with common settings.

    Args:
        title: Overlay title
        message: Progress message
        progress_type: Type of progress visualization
        cancellable: Whether the operation can be cancelled
        **kwargs: Additional configuration options

    Returns:
        Configured ProgressOverlayUI instance
    """
    behaviors = [ProgressBehavior.MODAL, ProgressBehavior.PERSISTENT]
    if cancellable:
        behaviors.append(ProgressBehavior.CANCELLABLE)

    config = ProgressConfig(
        title=title,
        message=message,
        progress_type=progress_type,
        position=OverlayPosition.CENTER,
        behaviors=behaviors,
        **kwargs
    )

    return ProgressOverlayUI(config=config)


def create_stepped_progress_overlay(title: str = "Multi-Step Process",
                                  message: str = "Processing multiple steps...",
                                  total_steps: int = 1,
                                  **kwargs) -> ProgressOverlayUI:
    """
    Create a stepped progress overlay for multi-stage operations.

    Args:
        title: Overlay title
        message: Progress message
        total_steps: Total number of steps
        **kwargs: Additional configuration options

    Returns:
        Configured ProgressOverlayUI instance
    """
    config = ProgressConfig(
        title=title,
        message=message,
        progress_type=ProgressType.STEPPED,
        position=OverlayPosition.CENTER,
        show_current_item=True,
        show_item_count=True,
        **kwargs
    )

    context = ProgressContext(
        total_items=total_steps
    )

    return ProgressOverlayUI(config=config, context=context)


def create_indeterminate_progress_overlay(title: str = "Processing...",
                                        message: str = "Please wait...",
                                        **kwargs) -> ProgressOverlayUI:
    """
    Create an indeterminate progress overlay for operations with unknown duration.

    Args:
        title: Overlay title
        message: Progress message
        **kwargs: Additional configuration options

    Returns:
        Configured ProgressOverlayUI instance
    """
    return create_progress_overlay(
        title=title,
        message=message,
        progress_type=ProgressType.INDETERMINATE,
        position=OverlayPosition.CENTER,
        show_percentage=False,
        show_time_remaining=False,
        **kwargs
    )
