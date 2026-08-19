"""
Module: progress_indicators_ui
Description: Comprehensive progress visualization components including linear progress bars, circular progress rings,
            stepped progress indicators, and indeterminate progress animations. Provides responsive design with
            breakpoint-aware layouts, theme-aware styling, accessibility compliance, and seamless integration
            with the MikroDok application's theme system and responsive layout manager.
            Features modern UI/UX with smooth animations, customizable styling, and cross-platform compatibility.
Phase: 2
Location: /src/modules/ui/visualization_ui/progress_indicators_ui/progress_indicators_ui.py
"""

# Standard library imports
import asyncio
import time
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, field

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    ColorPalette,
    TypographyScale,
    SpacingSystem,
    IconSystem,
    ResponsiveLayoutManager,
    ScreenSize
)


class ProgressType(Enum):
    """Progress indicator type enumeration."""
    LINEAR = "linear"
    CIRCULAR = "circular"
    STEPPED = "stepped"
    INDETERMINATE = "indeterminate"
    MINI = "mini"
    GAUGE = "gauge"


class ProgressState(Enum):
    """Progress state enumeration."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class ProgressSize(Enum):
    """Progress indicator size enumeration."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


@dataclass
class ProgressConfig:
    """Configuration for progress indicators."""
    progress_type: ProgressType = ProgressType.LINEAR
    size: ProgressSize = ProgressSize.MEDIUM
    show_percentage: bool = True
    show_label: bool = True
    show_time_estimate: bool = False
    show_speed: bool = False
    animated: bool = True
    color_scheme: str = "primary"  # primary, success, warning, error
    thickness: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    enable_pulse: bool = False
    enable_glow: bool = False
    rounded_corners: bool = True
    gradient_fill: bool = False


@dataclass
class ProgressMetrics:
    """Progress metrics and statistics."""
    current_value: float = 0.0
    max_value: float = 100.0
    percentage: float = 0.0
    start_time: Optional[datetime] = None
    elapsed_time: Optional[timedelta] = None
    estimated_completion: Optional[datetime] = None
    speed: float = 0.0  # units per second
    items_processed: int = 0
    total_items: int = 0
    current_step: int = 0
    total_steps: int = 1
    label: str = ""
    description: str = ""


class LinearProgressBar(ThemeAwareUserControl):
    """
    Linear progress bar component with responsive design and theme integration.
    
    Features:
    - Responsive width and height based on screen size
    - Theme-aware colors and styling
    - Smooth animations and transitions
    - Percentage display and custom labels
    - Multiple color schemes and styles
    - Accessibility compliance with ARIA attributes
    """
    
    def __init__(self,
                 config: Optional[ProgressConfig] = None,
                 metrics: Optional[ProgressMetrics] = None,
                 on_complete: Optional[Callable] = None,
                 **kwargs):
        """
        Initialize linear progress bar.
        
        Args:
            config: Progress configuration
            metrics: Progress metrics
            on_complete: Callback when progress reaches 100%
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        self._config = config or ProgressConfig()
        self._metrics = metrics or ProgressMetrics()
        self._on_complete = on_complete
        
        # Component references
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._percentage_text: Optional[ft.Text] = None
        self._label_text: Optional[ft.Text] = None
        self._time_text: Optional[ft.Text] = None
        self._speed_text: Optional[ft.Text] = None
        
        # Animation state
        self._animation_active = False
        self._last_update_time = time.time()
        
        self._build_component()
    
    def _build_component(self) -> None:
        """Build the linear progress bar component."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        
        # Calculate responsive dimensions
        bar_width = self._get_responsive_width()
        bar_height = self._get_responsive_height()
        
        # Progress bar
        self._progress_bar = ft.ProgressBar(
            value=self._metrics.percentage / 100.0,
            width=bar_width,
            height=bar_height,
            color=self._get_progress_color(),
            bgcolor=palette.surface_variant,
            border_radius=ft.border_radius.all(
                bar_height // 2 if self._config.rounded_corners else 0
            )
        )
        
        # Percentage text
        if self._config.show_percentage:
            self._percentage_text = ft.Text(
                value=f"{self._metrics.percentage:.1f}%",
                size=self._get_responsive_font_size(),
                color=palette.text_primary,
                weight=ft.FontWeight.W_500,
                text_align=ft.TextAlign.CENTER
            )
        
        # Label text
        if self._config.show_label and self._metrics.label:
            self._label_text = ft.Text(
                value=self._metrics.label,
                size=self._get_responsive_font_size() - 1,
                color=palette.text_secondary,
                text_align=ft.TextAlign.LEFT
            )
        
        # Time estimate text
        if self._config.show_time_estimate:
            self._time_text = ft.Text(
                value=self._format_time_estimate(),
                size=self._get_responsive_font_size() - 2,
                color=palette.text_tertiary,
                text_align=ft.TextAlign.RIGHT
            )
        
        # Speed text
        if self._config.show_speed:
            self._speed_text = ft.Text(
                value=self._format_speed(),
                size=self._get_responsive_font_size() - 2,
                color=palette.text_tertiary,
                text_align=ft.TextAlign.RIGHT
            )
        
        # Build layout
        self._build_layout()
    
    def _build_layout(self) -> None:
        """Build the component layout."""
        spacing = self.get_spacing()
        
        # Top row with label and time/speed
        top_row_controls = []
        if self._label_text:
            top_row_controls.append(self._label_text)
        
        if self._time_text or self._speed_text:
            right_info = []
            if self._time_text:
                right_info.append(self._time_text)
            if self._speed_text:
                right_info.append(self._speed_text)
            
            top_row_controls.append(
                ft.Row(
                    controls=right_info,
                    spacing=spacing.sm,
                    alignment=ft.MainAxisAlignment.END
                )
            )
        
        # Progress row with bar and percentage
        progress_row = ft.Row(
            controls=[
                ft.Container(
                    content=self._progress_bar,
                    expand=True
                )
            ] + ([self._percentage_text] if self._percentage_text else []),
            spacing=spacing.md,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        # Main layout
        main_controls = []
        
        if top_row_controls:
            main_controls.append(
                ft.Row(
                    controls=top_row_controls,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
            )
        
        main_controls.append(progress_row)
        
        self.content = ft.Column(
            controls=main_controls,
            spacing=spacing.xs,
            tight=True
        )

    def _get_responsive_width(self) -> int:
        """Get responsive width for progress bar."""
        responsive_manager = self.get_responsive_layout()

        if self._config.width:
            return self._config.width

        return responsive_manager.get_breakpoint_value(
            mobile=200, tablet=250, desktop=300, large=350
        )

    def _get_responsive_height(self) -> int:
        """Get responsive height for progress bar."""
        responsive_manager = self.get_responsive_layout()

        if self._config.height:
            return self._config.height

        size_map = {
            ProgressSize.SMALL: responsive_manager.get_breakpoint_value(
                mobile=4, tablet=5, desktop=6, large=7
            ),
            ProgressSize.MEDIUM: responsive_manager.get_breakpoint_value(
                mobile=6, tablet=7, desktop=8, large=9
            ),
            ProgressSize.LARGE: responsive_manager.get_breakpoint_value(
                mobile=8, tablet=9, desktop=10, large=12
            ),
            ProgressSize.EXTRA_LARGE: responsive_manager.get_breakpoint_value(
                mobile=12, tablet=14, desktop=16, large=18
            )
        }

        return size_map.get(self._config.size, size_map[ProgressSize.MEDIUM])

    def _get_responsive_font_size(self) -> int:
        """Get responsive font size for text elements."""
        responsive_manager = self.get_responsive_layout()
        typography = self.get_typography()

        base_size = typography.body_small[0]
        return responsive_manager.get_responsive_font_size(base_size)

    def _get_progress_color(self) -> str:
        """Get progress bar color based on scheme and state."""
        palette = self.get_palette()

        # State-based colors
        if self._metrics.percentage >= 100:
            return palette.success

        # Scheme-based colors
        color_map = {
            "primary": palette.primary,
            "success": palette.success,
            "warning": palette.warning,
            "error": palette.error
        }

        return color_map.get(self._config.color_scheme, palette.primary)

    def _format_time_estimate(self) -> str:
        """Format time estimate text."""
        if not self._metrics.estimated_completion:
            return "Calculating..."

        now = datetime.now(timezone.utc)
        remaining = self._metrics.estimated_completion - now

        if remaining.total_seconds() <= 0:
            return "Completing..."

        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m remaining"
        elif minutes > 0:
            return f"{minutes}m {seconds}s remaining"
        else:
            return f"{seconds}s remaining"

    def _format_speed(self) -> str:
        """Format speed text."""
        if self._metrics.speed <= 0:
            return "0 items/s"

        if self._metrics.speed >= 1000:
            return f"{self._metrics.speed / 1000:.1f}k items/s"
        elif self._metrics.speed >= 1:
            return f"{self._metrics.speed:.1f} items/s"
        else:
            return f"{self._metrics.speed:.2f} items/s"

    def update_progress(self,
                       value: Optional[float] = None,
                       percentage: Optional[float] = None,
                       metrics: Optional[ProgressMetrics] = None) -> None:
        """
        Update progress bar value and metrics.

        Args:
            value: New progress value
            percentage: New progress percentage (0-100)
            metrics: Updated metrics object
        """
        if metrics:
            self._metrics = metrics
        elif value is not None:
            self._metrics.current_value = value
            self._metrics.percentage = (value / self._metrics.max_value) * 100
        elif percentage is not None:
            self._metrics.percentage = max(0, min(100, percentage))
            self._metrics.current_value = (percentage / 100) * self._metrics.max_value

        # Update UI components
        if self._progress_bar:
            self._progress_bar.value = self._metrics.percentage / 100.0
            self._progress_bar.color = self._get_progress_color()

        if self._percentage_text:
            self._percentage_text.value = f"{self._metrics.percentage:.1f}%"

        if self._label_text and self._metrics.label:
            self._label_text.value = self._metrics.label

        if self._time_text:
            self._time_text.value = self._format_time_estimate()

        if self._speed_text:
            self._speed_text.value = self._format_speed()

        # Check for completion
        if self._metrics.percentage >= 100 and self._on_complete:
            self._on_complete()

        # Update the page if available
        if self.page:
            self.page.update()

    def set_indeterminate(self, indeterminate: bool = True) -> None:
        """Set progress bar to indeterminate mode."""
        if self._progress_bar:
            if indeterminate:
                self._progress_bar.value = None  # Indeterminate mode in Flet
            else:
                self._progress_bar.value = self._metrics.percentage / 100.0

            if self.page:
                self.page.update()

    def reset(self) -> None:
        """Reset progress to initial state."""
        self._metrics.current_value = 0.0
        self._metrics.percentage = 0.0
        self._metrics.start_time = None
        self._metrics.elapsed_time = None
        self._metrics.estimated_completion = None
        self._metrics.speed = 0.0
        self._metrics.items_processed = 0

        self.update_progress(percentage=0.0)


class CircularProgressRing(ThemeAwareUserControl):
    """
    Circular progress ring component with responsive design and theme integration.

    Features:
    - Responsive size based on screen dimensions
    - Theme-aware colors and styling
    - Smooth circular progress animation
    - Center text display for percentage or custom content
    - Multiple stroke widths and styles
    - Accessibility compliance with ARIA attributes
    """

    def __init__(self,
                 config: Optional[ProgressConfig] = None,
                 metrics: Optional[ProgressMetrics] = None,
                 center_content: Optional[ft.Control] = None,
                 on_complete: Optional[Callable] = None,
                 **kwargs):
        """
        Initialize circular progress ring.

        Args:
            config: Progress configuration
            metrics: Progress metrics
            center_content: Custom content for center of ring
            on_complete: Callback when progress reaches 100%
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)

        self._config = config or ProgressConfig(progress_type=ProgressType.CIRCULAR)
        self._metrics = metrics or ProgressMetrics()
        self._center_content = center_content
        self._on_complete = on_complete

        # Component references
        self._progress_ring: Optional[ft.ProgressRing] = None
        self._center_text: Optional[ft.Text] = None
        self._center_container: Optional[ft.Container] = None

        self._build_component()

    def _build_component(self) -> None:
        """Build the circular progress ring component."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()

        # Calculate responsive dimensions
        ring_size = self._get_responsive_size()
        stroke_width = self._get_responsive_stroke_width()

        # Progress ring
        self._progress_ring = ft.ProgressRing(
            value=self._metrics.percentage / 100.0,
            width=ring_size,
            height=ring_size,
            stroke_width=stroke_width,
            color=self._get_progress_color(),
            bgcolor=palette.surface_variant
        )

        # Center content
        if self._center_content:
            center_content = self._center_content
        elif self._config.show_percentage:
            self._center_text = ft.Text(
                value=f"{self._metrics.percentage:.0f}%",
                size=self._get_responsive_center_font_size(),
                color=palette.text_primary,
                weight=ft.FontWeight.W_600,
                text_align=ft.TextAlign.CENTER
            )
            center_content = self._center_text
        else:
            center_content = ft.Container()

        # Center container
        self._center_container = ft.Container(
            content=center_content,
            width=ring_size - (stroke_width * 2),
            height=ring_size - (stroke_width * 2),
            alignment=ft.alignment.center
        )

        # Stack ring and center content
        self.content = ft.Stack(
            controls=[
                self._progress_ring,
                ft.Container(
                    content=self._center_container,
                    alignment=ft.alignment.center,
                    width=ring_size,
                    height=ring_size
                )
            ],
            width=ring_size,
            height=ring_size
        )

    def _get_responsive_size(self) -> int:
        """Get responsive size for progress ring."""
        responsive_manager = self.get_responsive_layout()

        if self._config.width:
            return self._config.width

        size_map = {
            ProgressSize.SMALL: responsive_manager.get_breakpoint_value(
                mobile=40, tablet=45, desktop=50, large=55
            ),
            ProgressSize.MEDIUM: responsive_manager.get_breakpoint_value(
                mobile=60, tablet=70, desktop=80, large=90
            ),
            ProgressSize.LARGE: responsive_manager.get_breakpoint_value(
                mobile=80, tablet=90, desktop=100, large=110
            ),
            ProgressSize.EXTRA_LARGE: responsive_manager.get_breakpoint_value(
                mobile=100, tablet=120, desktop=140, large=160
            )
        }

        return size_map.get(self._config.size, size_map[ProgressSize.MEDIUM])

    def _get_responsive_stroke_width(self) -> int:
        """Get responsive stroke width for progress ring."""
        responsive_manager = self.get_responsive_layout()

        if self._config.thickness:
            return self._config.thickness

        size_map = {
            ProgressSize.SMALL: responsive_manager.get_breakpoint_value(
                mobile=3, tablet=4, desktop=4, large=5
            ),
            ProgressSize.MEDIUM: responsive_manager.get_breakpoint_value(
                mobile=4, tablet=5, desktop=6, large=7
            ),
            ProgressSize.LARGE: responsive_manager.get_breakpoint_value(
                mobile=6, tablet=7, desktop=8, large=9
            ),
            ProgressSize.EXTRA_LARGE: responsive_manager.get_breakpoint_value(
                mobile=8, tablet=9, desktop=10, large=12
            )
        }

        return size_map.get(self._config.size, size_map[ProgressSize.MEDIUM])

    def _get_responsive_center_font_size(self) -> int:
        """Get responsive font size for center text."""
        responsive_manager = self.get_responsive_layout()

        size_map = {
            ProgressSize.SMALL: responsive_manager.get_breakpoint_value(
                mobile=10, tablet=11, desktop=12, large=13
            ),
            ProgressSize.MEDIUM: responsive_manager.get_breakpoint_value(
                mobile=14, tablet=16, desktop=18, large=20
            ),
            ProgressSize.LARGE: responsive_manager.get_breakpoint_value(
                mobile=18, tablet=20, desktop=22, large=24
            ),
            ProgressSize.EXTRA_LARGE: responsive_manager.get_breakpoint_value(
                mobile=22, tablet=24, desktop=26, large=28
            )
        }

        return size_map.get(self._config.size, size_map[ProgressSize.MEDIUM])

    def _get_progress_color(self) -> str:
        """Get progress ring color based on scheme and state."""
        palette = self.get_palette()

        # State-based colors
        if self._metrics.percentage >= 100:
            return palette.success

        # Scheme-based colors
        color_map = {
            "primary": palette.primary,
            "success": palette.success,
            "warning": palette.warning,
            "error": palette.error
        }

        return color_map.get(self._config.color_scheme, palette.primary)

    def update_progress(self,
                       value: Optional[float] = None,
                       percentage: Optional[float] = None,
                       metrics: Optional[ProgressMetrics] = None) -> None:
        """
        Update progress ring value and metrics.

        Args:
            value: New progress value
            percentage: New progress percentage (0-100)
            metrics: Updated metrics object
        """
        if metrics:
            self._metrics = metrics
        elif value is not None:
            self._metrics.current_value = value
            self._metrics.percentage = (value / self._metrics.max_value) * 100
        elif percentage is not None:
            self._metrics.percentage = max(0, min(100, percentage))
            self._metrics.current_value = (percentage / 100) * self._metrics.max_value

        # Update UI components
        if self._progress_ring:
            self._progress_ring.value = self._metrics.percentage / 100.0
            self._progress_ring.color = self._get_progress_color()

        if self._center_text:
            self._center_text.value = f"{self._metrics.percentage:.0f}%"

        # Check for completion
        if self._metrics.percentage >= 100 and self._on_complete:
            self._on_complete()

        # Update the page if available
        if self.page:
            self.page.update()

    def set_indeterminate(self, indeterminate: bool = True) -> None:
        """Set progress ring to indeterminate mode."""
        if self._progress_ring:
            if indeterminate:
                self._progress_ring.value = None  # Indeterminate mode in Flet
            else:
                self._progress_ring.value = self._metrics.percentage / 100.0

            if self.page:
                self.page.update()

    def set_center_content(self, content: ft.Control) -> None:
        """Set custom center content."""
        if self._center_container:
            self._center_container.content = content
            if self.page:
                self.page.update()

    def reset(self) -> None:
        """Reset progress to initial state."""
        self._metrics.current_value = 0.0
        self._metrics.percentage = 0.0
        self.update_progress(percentage=0.0)


class SteppedProgressIndicator(ThemeAwareUserControl):
    """
    Stepped progress indicator component for multi-stage operations.

    Features:
    - Responsive step visualization with connecting lines
    - Theme-aware colors and styling
    - Step labels and descriptions
    - Current step highlighting
    - Completed step indicators
    - Accessibility compliance with ARIA attributes
    """

    def __init__(self,
                 config: Optional[ProgressConfig] = None,
                 metrics: Optional[ProgressMetrics] = None,
                 steps: Optional[List[Dict[str, Any]]] = None,
                 on_step_complete: Optional[Callable] = None,
                 on_complete: Optional[Callable] = None,
                 **kwargs):
        """
        Initialize stepped progress indicator.

        Args:
            config: Progress configuration
            metrics: Progress metrics
            steps: List of step definitions with labels and descriptions
            on_step_complete: Callback when a step is completed
            on_complete: Callback when all steps are completed
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)

        self._config = config or ProgressConfig(progress_type=ProgressType.STEPPED)
        self._metrics = metrics or ProgressMetrics()
        self._steps = steps or []
        self._on_step_complete = on_step_complete
        self._on_complete = on_complete

        # Component references
        self._step_containers: List[ft.Container] = []
        self._step_indicators: List[ft.Container] = []
        self._step_labels: List[ft.Text] = []
        self._step_descriptions: List[ft.Text] = []
        self._connector_lines: List[ft.Container] = []

        # Ensure we have steps
        if not self._steps:
            self._steps = [
                {"label": f"Step {i+1}", "description": f"Step {i+1} description"}
                for i in range(max(1, self._metrics.total_steps))
            ]

        self._build_component()

    def _build_component(self) -> None:
        """Build the stepped progress indicator component."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Calculate responsive dimensions
        indicator_size = self._get_responsive_indicator_size()

        # Build step components
        step_controls = []

        for i, step in enumerate(self._steps):
            step_number = i + 1
            is_current = step_number == self._metrics.current_step
            is_completed = step_number < self._metrics.current_step
            is_future = step_number > self._metrics.current_step

            # Step indicator
            if is_completed:
                indicator_content = ft.Icon(
                    icons.CHECK,
                    size=indicator_size // 2,
                    color=palette.success
                )
                indicator_color = palette.success
            elif is_current:
                indicator_content = ft.Text(
                    value=str(step_number),
                    size=indicator_size // 3,
                    color=palette.primary,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER
                )
                indicator_color = palette.primary
            else:
                indicator_content = ft.Text(
                    value=str(step_number),
                    size=indicator_size // 3,
                    color=palette.text_tertiary,
                    weight=ft.FontWeight.W_400,
                    text_align=ft.TextAlign.CENTER
                )
                indicator_color = palette.surface_variant

            step_indicator = ft.Container(
                content=indicator_content,
                width=indicator_size,
                height=indicator_size,
                border_radius=ft.border_radius.all(indicator_size // 2),
                bgcolor=indicator_color if is_completed else None,
                border=ft.border.all(
                    width=2,
                    color=indicator_color
                ),
                alignment=ft.alignment.center
            )

            # Step label
            step_label = ft.Text(
                value=step.get("label", f"Step {step_number}"),
                size=self._get_responsive_font_size(),
                color=palette.text_primary if (is_current or is_completed) else palette.text_secondary,
                weight=ft.FontWeight.W_500 if is_current else ft.FontWeight.W_400,
                text_align=ft.TextAlign.CENTER
            )

            # Step description
            step_description = None
            if step.get("description") and self._config.show_label:
                step_description = ft.Text(
                    value=step["description"],
                    size=self._get_responsive_font_size() - 2,
                    color=palette.text_tertiary,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS
                )

            # Step container
            step_content = [step_indicator, step_label]
            if step_description:
                step_content.append(step_description)

            step_container = ft.Column(
                controls=step_content,
                spacing=spacing.xs,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True
            )

            step_controls.append(step_container)

            # Store references
            self._step_containers.append(step_container)
            self._step_indicators.append(step_indicator)
            self._step_labels.append(step_label)
            if step_description:
                self._step_descriptions.append(step_description)

            # Add connector line (except for last step)
            if i < len(self._steps) - 1:
                connector_color = palette.primary if is_completed else palette.surface_variant
                connector_line = ft.Container(
                    width=responsive_manager.get_breakpoint_value(
                        mobile=30, tablet=40, desktop=50, large=60
                    ),
                    height=2,
                    bgcolor=connector_color,
                    margin=ft.margin.symmetric(vertical=indicator_size // 2)
                )
                self._connector_lines.append(connector_line)

        # Build layout
        if responsive_manager.is_mobile():
            # Vertical layout for mobile
            self._build_vertical_layout(step_controls)
        else:
            # Horizontal layout for larger screens
            self._build_horizontal_layout(step_controls)

    def _build_horizontal_layout(self, step_controls: List[ft.Control]) -> None:
        """Build horizontal layout for steps."""
        spacing = self.get_spacing()

        # Interleave steps and connectors
        layout_controls = []
        for i, step_control in enumerate(step_controls):
            layout_controls.append(step_control)
            if i < len(self._connector_lines):
                layout_controls.append(self._connector_lines[i])

        self.content = ft.Row(
            controls=layout_controls,
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _build_vertical_layout(self, step_controls: List[ft.Control]) -> None:
        """Build vertical layout for steps."""
        spacing = self.get_spacing()

        # Vertical layout with connectors on the left
        layout_controls = []
        for i, step_control in enumerate(step_controls):
            if i > 0:
                # Add vertical connector
                connector = ft.Container(
                    width=2,
                    height=spacing.lg,
                    bgcolor=self.get_palette().surface_variant,
                    margin=ft.margin.only(left=self._get_responsive_indicator_size() // 2)
                )
                layout_controls.append(connector)

            layout_controls.append(step_control)

        self.content = ft.Column(
            controls=layout_controls,
            spacing=spacing.xs,
            horizontal_alignment=ft.CrossAxisAlignment.START
        )

    def _get_responsive_indicator_size(self) -> int:
        """Get responsive size for step indicators."""
        responsive_manager = self.get_responsive_layout()

        size_map = {
            ProgressSize.SMALL: responsive_manager.get_breakpoint_value(
                mobile=24, tablet=28, desktop=32, large=36
            ),
            ProgressSize.MEDIUM: responsive_manager.get_breakpoint_value(
                mobile=32, tablet=36, desktop=40, large=44
            ),
            ProgressSize.LARGE: responsive_manager.get_breakpoint_value(
                mobile=40, tablet=44, desktop=48, large=52
            ),
            ProgressSize.EXTRA_LARGE: responsive_manager.get_breakpoint_value(
                mobile=48, tablet=52, desktop=56, large=60
            )
        }

        return size_map.get(self._config.size, size_map[ProgressSize.MEDIUM])

    def _get_responsive_font_size(self) -> int:
        """Get responsive font size for step text."""
        responsive_manager = self.get_responsive_layout()
        typography = self.get_typography()

        base_size = typography.body_small[0]
        return responsive_manager.get_responsive_font_size(base_size)

    def update_step(self, step: int) -> None:
        """
        Update current step.

        Args:
            step: New current step (1-based)
        """
        old_step = self._metrics.current_step
        self._metrics.current_step = max(1, min(len(self._steps), step))

        # Trigger step complete callback
        if self._metrics.current_step > old_step and self._on_step_complete:
            self._on_step_complete(old_step)

        # Check for completion
        if self._metrics.current_step >= len(self._steps) and self._on_complete:
            self._on_complete()

        # Rebuild component to update visual state
        self._build_component()

        if self.page:
            self.page.update()

    def next_step(self) -> None:
        """Move to the next step."""
        self.update_step(self._metrics.current_step + 1)

    def previous_step(self) -> None:
        """Move to the previous step."""
        self.update_step(self._metrics.current_step - 1)

    def reset(self) -> None:
        """Reset to first step."""
        self.update_step(1)


class IndeterminateProgress(ThemeAwareUserControl):
    """
    Indeterminate progress indicator for operations with unknown duration.

    Features:
    - Responsive design with adaptive sizing
    - Theme-aware colors and styling
    - Smooth animation effects
    - Multiple animation styles (pulse, spin, wave)
    - Accessibility compliance with reduced motion support
    """

    def __init__(self,
                 config: Optional[ProgressConfig] = None,
                 animation_style: str = "pulse",  # pulse, spin, wave
                 message: str = "Loading...",
                 **kwargs):
        """
        Initialize indeterminate progress indicator.

        Args:
            config: Progress configuration
            animation_style: Animation style (pulse, spin, wave)
            message: Loading message
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)

        self._config = config or ProgressConfig(progress_type=ProgressType.INDETERMINATE)
        self._animation_style = animation_style
        self._message = message

        # Component references
        self._progress_indicator: Optional[ft.Control] = None
        self._message_text: Optional[ft.Text] = None

        # Animation state
        self._is_animating = False

        self._build_component()

    def _build_component(self) -> None:
        """Build the indeterminate progress indicator component."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Create progress indicator based on style
        if self._animation_style == "spin":
            self._progress_indicator = ft.ProgressRing(
                width=self._get_responsive_size(),
                height=self._get_responsive_size(),
                stroke_width=self._get_responsive_stroke_width(),
                color=palette.primary,
                bgcolor=palette.surface_variant
            )
        else:  # pulse or wave
            self._progress_indicator = ft.ProgressBar(
                width=self._get_responsive_width(),
                height=self._get_responsive_height(),
                color=palette.primary,
                bgcolor=palette.surface_variant,
                border_radius=ft.border_radius.all(
                    self._get_responsive_height() // 2 if self._config.rounded_corners else 0
                )
            )

        # Message text
        if self._message and self._config.show_label:
            self._message_text = ft.Text(
                value=self._message,
                size=self._get_responsive_font_size(),
                color=palette.text_secondary,
                text_align=ft.TextAlign.CENTER
            )

        # Build layout
        controls = [self._progress_indicator]
        if self._message_text:
            controls.append(self._message_text)

        self.content = ft.Column(
            controls=controls,
            spacing=spacing.sm,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True
        )

    def _get_responsive_size(self) -> int:
        """Get responsive size for circular indicator."""
        responsive_manager = self.get_responsive_layout()

        size_map = {
            ProgressSize.SMALL: responsive_manager.get_breakpoint_value(
                mobile=24, tablet=28, desktop=32, large=36
            ),
            ProgressSize.MEDIUM: responsive_manager.get_breakpoint_value(
                mobile=32, tablet=36, desktop=40, large=44
            ),
            ProgressSize.LARGE: responsive_manager.get_breakpoint_value(
                mobile=40, tablet=44, desktop=48, large=52
            ),
            ProgressSize.EXTRA_LARGE: responsive_manager.get_breakpoint_value(
                mobile=48, tablet=52, desktop=56, large=60
            )
        }

        return size_map.get(self._config.size, size_map[ProgressSize.MEDIUM])

    def _get_responsive_width(self) -> int:
        """Get responsive width for linear indicator."""
        responsive_manager = self.get_responsive_layout()

        return responsive_manager.get_breakpoint_value(
            mobile=120, tablet=150, desktop=180, large=200
        )

    def _get_responsive_height(self) -> int:
        """Get responsive height for linear indicator."""
        responsive_manager = self.get_responsive_layout()

        size_map = {
            ProgressSize.SMALL: responsive_manager.get_breakpoint_value(
                mobile=3, tablet=4, desktop=4, large=5
            ),
            ProgressSize.MEDIUM: responsive_manager.get_breakpoint_value(
                mobile=4, tablet=5, desktop=6, large=7
            ),
            ProgressSize.LARGE: responsive_manager.get_breakpoint_value(
                mobile=6, tablet=7, desktop=8, large=9
            ),
            ProgressSize.EXTRA_LARGE: responsive_manager.get_breakpoint_value(
                mobile=8, tablet=9, desktop=10, large=12
            )
        }

        return size_map.get(self._config.size, size_map[ProgressSize.MEDIUM])

    def _get_responsive_stroke_width(self) -> int:
        """Get responsive stroke width for circular indicator."""
        responsive_manager = self.get_responsive_layout()

        size_map = {
            ProgressSize.SMALL: responsive_manager.get_breakpoint_value(
                mobile=2, tablet=3, desktop=3, large=4
            ),
            ProgressSize.MEDIUM: responsive_manager.get_breakpoint_value(
                mobile=3, tablet=4, desktop=4, large=5
            ),
            ProgressSize.LARGE: responsive_manager.get_breakpoint_value(
                mobile=4, tablet=5, desktop=5, large=6
            ),
            ProgressSize.EXTRA_LARGE: responsive_manager.get_breakpoint_value(
                mobile=5, tablet=6, desktop=6, large=7
            )
        }

        return size_map.get(self._config.size, size_map[ProgressSize.MEDIUM])

    def _get_responsive_font_size(self) -> int:
        """Get responsive font size for message text."""
        responsive_manager = self.get_responsive_layout()
        typography = self.get_typography()

        base_size = typography.body_small[0]
        return responsive_manager.get_responsive_font_size(base_size)

    def start_animation(self) -> None:
        """Start the indeterminate animation."""
        self._is_animating = True
        if self._progress_indicator:
            # Set to indeterminate mode
            if hasattr(self._progress_indicator, 'value'):
                self._progress_indicator.value = None

            if self.page:
                self.page.update()

    def stop_animation(self) -> None:
        """Stop the indeterminate animation."""
        self._is_animating = False
        if self._progress_indicator:
            # Set to determinate mode with 0 value
            if hasattr(self._progress_indicator, 'value'):
                self._progress_indicator.value = 0.0

            if self.page:
                self.page.update()

    def set_message(self, message: str) -> None:
        """
        Update the loading message.

        Args:
            message: New loading message
        """
        self._message = message
        if self._message_text:
            self._message_text.value = message
            if self.page:
                self.page.update()


class ProgressIndicatorsUI(ThemeAwareUserControl):
    """
    Main progress indicators UI component that provides a unified interface for all progress indicator types.

    Features:
    - Unified API for all progress indicator types
    - Responsive design with breakpoint-aware layouts
    - Theme-aware styling with accessibility compliance
    - Dynamic switching between indicator types
    - Progress metrics tracking and display
    - Event handling and callbacks
    - Cross-platform compatibility and offline operation
    """

    def __init__(self,
                 config: Optional[ProgressConfig] = None,
                 metrics: Optional[ProgressMetrics] = None,
                 steps: Optional[List[Dict[str, Any]]] = None,
                 on_progress_change: Optional[Callable] = None,
                 on_step_complete: Optional[Callable] = None,
                 on_complete: Optional[Callable] = None,
                 **kwargs):
        """
        Initialize progress indicators UI.

        Args:
            config: Progress configuration
            metrics: Progress metrics
            steps: List of step definitions for stepped progress
            on_progress_change: Callback for progress value changes
            on_step_complete: Callback when a step is completed
            on_complete: Callback when progress is completed
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)

        self._config = config or ProgressConfig()
        self._metrics = metrics or ProgressMetrics()
        self._steps = steps or []
        self._on_progress_change = on_progress_change
        self._on_step_complete = on_step_complete
        self._on_complete = on_complete

        # Component references
        self._current_indicator: Optional[ThemeAwareUserControl] = None
        self._container: Optional[ft.Container] = None

        self._build_component()

    def _build_component(self) -> None:
        """Build the progress indicators component."""
        # Create the appropriate progress indicator based on type
        if self._config.progress_type == ProgressType.LINEAR:
            self._current_indicator = LinearProgressBar(
                config=self._config,
                metrics=self._metrics,
                on_complete=self._handle_complete
            )
        elif self._config.progress_type == ProgressType.CIRCULAR:
            self._current_indicator = CircularProgressRing(
                config=self._config,
                metrics=self._metrics,
                on_complete=self._handle_complete
            )
        elif self._config.progress_type == ProgressType.STEPPED:
            self._current_indicator = SteppedProgressIndicator(
                config=self._config,
                metrics=self._metrics,
                steps=self._steps,
                on_step_complete=self._on_step_complete,
                on_complete=self._handle_complete
            )
        elif self._config.progress_type == ProgressType.INDETERMINATE:
            self._current_indicator = IndeterminateProgress(
                config=self._config,
                message=self._metrics.label or "Loading..."
            )
        else:
            # Default to linear
            self._current_indicator = LinearProgressBar(
                config=self._config,
                metrics=self._metrics,
                on_complete=self._handle_complete
            )

        # Container for the indicator
        self._container = ft.Container(
            content=self._current_indicator,
            alignment=ft.alignment.center
        )

        self.content = self._container

    def _handle_complete(self) -> None:
        """Handle progress completion."""
        if self._on_complete:
            self._on_complete()

    def update_progress(self,
                       value: Optional[float] = None,
                       percentage: Optional[float] = None,
                       metrics: Optional[ProgressMetrics] = None) -> None:
        """
        Update progress value and metrics.

        Args:
            value: New progress value
            percentage: New progress percentage (0-100)
            metrics: Updated metrics object
        """
        # Update internal metrics
        if metrics:
            self._metrics = metrics
        elif value is not None:
            self._metrics.current_value = value
            self._metrics.percentage = (value / self._metrics.max_value) * 100
        elif percentage is not None:
            self._metrics.percentage = max(0, min(100, percentage))
            self._metrics.current_value = (percentage / 100) * self._metrics.max_value

        # Update the current indicator
        if self._current_indicator and hasattr(self._current_indicator, 'update_progress'):
            self._current_indicator.update_progress(
                value=value,
                percentage=percentage,
                metrics=metrics
            )

        # Trigger progress change callback
        if self._on_progress_change:
            self._on_progress_change(self._metrics.percentage)

    def update_step(self, step: int) -> None:
        """
        Update current step (for stepped progress).

        Args:
            step: New current step (1-based)
        """
        if (self._config.progress_type == ProgressType.STEPPED and
            self._current_indicator and
            hasattr(self._current_indicator, 'update_step')):
            self._current_indicator.update_step(step)

    def next_step(self) -> None:
        """Move to the next step (for stepped progress)."""
        if (self._config.progress_type == ProgressType.STEPPED and
            self._current_indicator and
            hasattr(self._current_indicator, 'next_step')):
            self._current_indicator.next_step()

    def previous_step(self) -> None:
        """Move to the previous step (for stepped progress)."""
        if (self._config.progress_type == ProgressType.STEPPED and
            self._current_indicator and
            hasattr(self._current_indicator, 'previous_step')):
            self._current_indicator.previous_step()

    def set_indeterminate(self, indeterminate: bool = True) -> None:
        """Set progress to indeterminate mode."""
        if self._current_indicator and hasattr(self._current_indicator, 'set_indeterminate'):
            self._current_indicator.set_indeterminate(indeterminate)
        elif indeterminate and self._config.progress_type != ProgressType.INDETERMINATE:
            # Switch to indeterminate indicator
            self._config.progress_type = ProgressType.INDETERMINATE
            self._build_component()
            if self.page:
                self.page.update()

    def start_animation(self) -> None:
        """Start animation (for indeterminate progress)."""
        if (self._config.progress_type == ProgressType.INDETERMINATE and
            self._current_indicator and
            hasattr(self._current_indicator, 'start_animation')):
            self._current_indicator.start_animation()

    def stop_animation(self) -> None:
        """Stop animation (for indeterminate progress)."""
        if (self._config.progress_type == ProgressType.INDETERMINATE and
            self._current_indicator and
            hasattr(self._current_indicator, 'stop_animation')):
            self._current_indicator.stop_animation()

    def set_message(self, message: str) -> None:
        """
        Set loading message (for indeterminate progress).

        Args:
            message: New loading message
        """
        self._metrics.label = message
        if (self._config.progress_type == ProgressType.INDETERMINATE and
            self._current_indicator and
            hasattr(self._current_indicator, 'set_message')):
            self._current_indicator.set_message(message)

    def switch_type(self, progress_type: ProgressType) -> None:
        """
        Switch to a different progress indicator type.

        Args:
            progress_type: New progress indicator type
        """
        if self._config.progress_type != progress_type:
            self._config.progress_type = progress_type
            self._build_component()
            if self.page:
                self.page.update()

    def reset(self) -> None:
        """Reset progress to initial state."""
        self._metrics.current_value = 0.0
        self._metrics.percentage = 0.0
        self._metrics.current_step = 1

        if self._current_indicator and hasattr(self._current_indicator, 'reset'):
            self._current_indicator.reset()

    def get_current_indicator(self) -> Optional[ThemeAwareUserControl]:
        """
        Get the current progress indicator component.

        Returns:
            Current progress indicator instance
        """
        return self._current_indicator

    def get_metrics(self) -> ProgressMetrics:
        """
        Get current progress metrics.

        Returns:
            Current progress metrics
        """
        return self._metrics

    def get_config(self) -> ProgressConfig:
        """
        Get current progress configuration.

        Returns:
            Current progress configuration
        """
        return self._config


# Convenience Functions

def create_linear_progress(percentage: float = 0.0,
                          size: ProgressSize = ProgressSize.MEDIUM,
                          color_scheme: str = "primary",
                          show_percentage: bool = True,
                          **kwargs) -> LinearProgressBar:
    """
    Create a linear progress bar with common settings.

    Args:
        percentage: Initial progress percentage (0-100)
        size: Progress bar size
        color_scheme: Color scheme (primary, success, warning, error)
        show_percentage: Whether to show percentage text
        **kwargs: Additional configuration options

    Returns:
        Configured LinearProgressBar instance
    """
    config = ProgressConfig(
        progress_type=ProgressType.LINEAR,
        size=size,
        color_scheme=color_scheme,
        show_percentage=show_percentage,
        **kwargs
    )

    metrics = ProgressMetrics(percentage=percentage)

    return LinearProgressBar(config=config, metrics=metrics)


def create_circular_progress(percentage: float = 0.0,
                           size: ProgressSize = ProgressSize.MEDIUM,
                           color_scheme: str = "primary",
                           show_percentage: bool = True,
                           **kwargs) -> CircularProgressRing:
    """
    Create a circular progress ring with common settings.

    Args:
        percentage: Initial progress percentage (0-100)
        size: Progress ring size
        color_scheme: Color scheme (primary, success, warning, error)
        show_percentage: Whether to show percentage text
        **kwargs: Additional configuration options

    Returns:
        Configured CircularProgressRing instance
    """
    config = ProgressConfig(
        progress_type=ProgressType.CIRCULAR,
        size=size,
        color_scheme=color_scheme,
        show_percentage=show_percentage,
        **kwargs
    )

    metrics = ProgressMetrics(percentage=percentage)

    return CircularProgressRing(config=config, metrics=metrics)


def create_stepped_progress(steps: List[Dict[str, Any]],
                          current_step: int = 1,
                          size: ProgressSize = ProgressSize.MEDIUM,
                          **kwargs) -> SteppedProgressIndicator:
    """
    Create a stepped progress indicator with common settings.

    Args:
        steps: List of step definitions
        current_step: Current step (1-based)
        size: Progress indicator size
        **kwargs: Additional configuration options

    Returns:
        Configured SteppedProgressIndicator instance
    """
    config = ProgressConfig(
        progress_type=ProgressType.STEPPED,
        size=size,
        **kwargs
    )

    metrics = ProgressMetrics(
        current_step=current_step,
        total_steps=len(steps)
    )

    return SteppedProgressIndicator(config=config, metrics=metrics, steps=steps)


def create_indeterminate_progress(message: str = "Loading...",
                                size: ProgressSize = ProgressSize.MEDIUM,
                                animation_style: str = "pulse",
                                **kwargs) -> IndeterminateProgress:
    """
    Create an indeterminate progress indicator with common settings.

    Args:
        message: Loading message
        size: Progress indicator size
        animation_style: Animation style (pulse, spin, wave)
        **kwargs: Additional configuration options

    Returns:
        Configured IndeterminateProgress instance
    """
    config = ProgressConfig(
        progress_type=ProgressType.INDETERMINATE,
        size=size,
        **kwargs
    )

    return IndeterminateProgress(
        config=config,
        animation_style=animation_style,
        message=message
    )
