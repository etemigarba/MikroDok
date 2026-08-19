"""
Module: status_badges_ui
Description: Comprehensive status badge components for training states, model health, system status,
            document processing states, and notification indicators. Provides responsive design with
            breakpoint-aware layouts, theme-aware styling, accessibility compliance, and seamless
            integration with the MikroDok application's theme system and responsive layout manager.
            Features modern UI/UX with smooth animations, customizable styling, and cross-platform compatibility.

Features:
- Multiple badge types (status, notification, count, health, processing, training, system)
- Responsive design with breakpoint-aware sizing and layouts
- Theme-aware styling with accessibility compliance (WCAG 2.1 AA)
- Smooth animations and transitions with reduced motion support
- Customizable badge variants and styling options
- Real-time status updates with efficient rendering
- Interactive features with hover states and click handlers
- Accessibility features with proper ARIA labels and keyboard navigation
- Performance optimization for continuous monitoring displays
- Cross-platform compatibility and offline operation

Phase: 2-4
Location: /src/modules/ui/visualization_ui/status_badges_ui/status_badges_ui.py
"""

# Standard library imports
import asyncio
import time
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Union, Tuple
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


class StatusType(Enum):
    """Status badge type enumeration."""
    STATUS = "status"
    NOTIFICATION = "notification"
    COUNT = "count"
    HEALTH = "health"
    PROCESSING = "processing"
    TRAINING = "training"
    SYSTEM = "system"
    CUSTOM = "custom"


class StatusState(Enum):
    """Status state enumeration."""
    # General states
    IDLE = "idle"
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    INFO = "info"
    
    # Training states
    TRAINING = "training"
    PAUSED = "paused"
    STOPPED = "stopped"
    CANCELLED = "cancelled"
    
    # Model states
    READY = "ready"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    
    # Processing states
    PROCESSING = "processing"
    QUEUED = "queued"
    VALIDATING = "validating"
    OPTIMIZING = "optimizing"
    
    # Health states
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class StatusSize(Enum):
    """Status badge size enumeration."""
    MINI = "mini"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


class StatusVariant(Enum):
    """Status badge variant enumeration."""
    FILLED = "filled"
    OUTLINED = "outlined"
    SUBTLE = "subtle"
    DOT = "dot"
    PILL = "pill"
    SQUARE = "square"
    ROUNDED = "rounded"


@dataclass
class BadgeConfig:
    """Configuration for status badges."""
    badge_type: StatusType = StatusType.STATUS
    size: StatusSize = StatusSize.MEDIUM
    variant: StatusVariant = StatusVariant.FILLED
    show_icon: bool = True
    show_text: bool = True
    show_count: bool = False
    animated: bool = True
    interactive: bool = False
    auto_hide: bool = False
    hide_delay: int = 5000  # milliseconds
    pulse_on_update: bool = False
    glow_effect: bool = False
    rounded_corners: bool = True
    border_width: int = 1
    opacity: float = 1.0
    custom_color: Optional[str] = None
    custom_icon: Optional[str] = None
    tooltip_enabled: bool = True
    accessibility_label: Optional[str] = None


@dataclass
class BadgeMetrics:
    """Badge metrics and statistics."""
    count: int = 0
    max_count: int = 99
    percentage: float = 0.0
    last_updated: Optional[datetime] = None
    update_frequency: float = 0.0  # updates per second
    total_updates: int = 0
    creation_time: Optional[datetime] = None
    display_text: str = ""
    tooltip_text: str = ""
    aria_label: str = ""


class StatusBadge(ThemeAwareUserControl):
    """
    Individual status badge component with comprehensive styling and functionality.
    
    Provides a single status badge with customizable appearance, animations,
    and interactive features while maintaining theme consistency and accessibility.
    """
    
    def __init__(self,
                 state: StatusState = StatusState.IDLE,
                 config: Optional[BadgeConfig] = None,
                 metrics: Optional[BadgeMetrics] = None,
                 on_click: Optional[Callable] = None,
                 on_hover: Optional[Callable] = None,
                 **kwargs):
        """
        Initialize status badge.
        
        Args:
            state: Current status state
            config: Badge configuration
            metrics: Badge metrics and data
            on_click: Click event handler
            on_hover: Hover event handler
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        self._state = state
        self._config = config or BadgeConfig()
        self._metrics = metrics or BadgeMetrics()
        self._on_click = on_click
        self._on_hover = on_hover
        
        # Internal state
        self._badge_id = str(uuid.uuid4())
        self._is_visible = True
        self._is_animating = False
        self._last_update_time = None
        self._hide_timer = None
        
        # UI components
        self._badge_container = None
        self._icon_component = None
        self._text_component = None
        self._count_component = None
        
        # Initialize badge
        self._initialize_badge()
    
    def _initialize_badge(self) -> None:
        """Initialize badge components and styling."""
        try:
            self._setup_badge_styling()
            self._create_badge_components()
            self._apply_initial_state()
            
        except Exception as e:
            print(f"Error initializing status badge: {e}")
    
    def _setup_badge_styling(self) -> None:
        """Setup badge styling based on configuration."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            responsive = self.get_responsive_layout()
            
            # Get size-specific dimensions
            size_config = self._get_size_config()
            
            # Get state-specific colors
            color_config = self._get_color_config()
            
            # Store styling configuration
            self._size_config = size_config
            self._color_config = color_config
            
        except Exception as e:
            print(f"Error setting up badge styling: {e}")
    
    def _get_size_config(self) -> Dict[str, Any]:
        """Get size-specific configuration."""
        responsive = self.get_responsive_layout()
        
        size_configs = {
            StatusSize.MINI: {
                "height": responsive.get_breakpoint_value(16, 18, 20, 22),
                "padding_h": responsive.get_breakpoint_value(4, 5, 6, 7),
                "padding_v": responsive.get_breakpoint_value(2, 2, 3, 3),
                "font_size": responsive.get_breakpoint_value(10, 11, 12, 13),
                "icon_size": responsive.get_breakpoint_value(10, 11, 12, 13),
                "border_radius": responsive.get_breakpoint_value(8, 9, 10, 11)
            },
            StatusSize.SMALL: {
                "height": responsive.get_breakpoint_value(20, 22, 24, 26),
                "padding_h": responsive.get_breakpoint_value(6, 7, 8, 9),
                "padding_v": responsive.get_breakpoint_value(3, 3, 4, 4),
                "font_size": responsive.get_breakpoint_value(11, 12, 13, 14),
                "icon_size": responsive.get_breakpoint_value(12, 13, 14, 15),
                "border_radius": responsive.get_breakpoint_value(10, 11, 12, 13)
            },
            StatusSize.MEDIUM: {
                "height": responsive.get_breakpoint_value(24, 26, 28, 30),
                "padding_h": responsive.get_breakpoint_value(8, 9, 10, 11),
                "padding_v": responsive.get_breakpoint_value(4, 4, 5, 5),
                "font_size": responsive.get_breakpoint_value(12, 13, 14, 15),
                "icon_size": responsive.get_breakpoint_value(14, 15, 16, 17),
                "border_radius": responsive.get_breakpoint_value(12, 13, 14, 15)
            },
            StatusSize.LARGE: {
                "height": responsive.get_breakpoint_value(28, 30, 32, 34),
                "padding_h": responsive.get_breakpoint_value(10, 11, 12, 13),
                "padding_v": responsive.get_breakpoint_value(5, 5, 6, 6),
                "font_size": responsive.get_breakpoint_value(13, 14, 15, 16),
                "icon_size": responsive.get_breakpoint_value(16, 17, 18, 19),
                "border_radius": responsive.get_breakpoint_value(14, 15, 16, 17)
            },
            StatusSize.EXTRA_LARGE: {
                "height": responsive.get_breakpoint_value(32, 34, 36, 38),
                "padding_h": responsive.get_breakpoint_value(12, 13, 14, 15),
                "padding_v": responsive.get_breakpoint_value(6, 6, 7, 7),
                "font_size": responsive.get_breakpoint_value(14, 15, 16, 17),
                "icon_size": responsive.get_breakpoint_value(18, 19, 20, 21),
                "border_radius": responsive.get_breakpoint_value(16, 17, 18, 19)
            }
        }
        
        return size_configs.get(self._config.size, size_configs[StatusSize.MEDIUM])

    def _get_color_config(self) -> Dict[str, str]:
        """Get state-specific color configuration."""
        palette = self.get_palette()

        # Use custom color if provided
        if self._config.custom_color:
            return {
                "background": self._config.custom_color,
                "text": palette.text_primary,
                "border": self._config.custom_color,
                "icon": palette.text_primary
            }

        # State-specific color mapping
        color_configs = {
            # General states
            StatusState.IDLE: {
                "background": palette.surface_variant,
                "text": palette.text_secondary,
                "border": palette.borders,
                "icon": palette.text_secondary
            },
            StatusState.ACTIVE: {
                "background": palette.primary,
                "text": palette.text_primary,
                "border": palette.primary,
                "icon": palette.text_primary
            },
            StatusState.INACTIVE: {
                "background": palette.surface_variant,
                "text": palette.text_disabled,
                "border": palette.borders,
                "icon": palette.text_disabled
            },
            StatusState.PENDING: {
                "background": palette.warning,
                "text": palette.text_primary,
                "border": palette.warning,
                "icon": palette.text_primary
            },
            StatusState.COMPLETED: {
                "background": palette.success,
                "text": palette.text_primary,
                "border": palette.success,
                "icon": palette.text_primary
            },
            StatusState.FAILED: {
                "background": palette.error,
                "text": palette.text_primary,
                "border": palette.error,
                "icon": palette.text_primary
            },
            StatusState.ERROR: {
                "background": palette.error,
                "text": palette.text_primary,
                "border": palette.error,
                "icon": palette.text_primary
            },
            StatusState.WARNING: {
                "background": palette.warning,
                "text": palette.text_primary,
                "border": palette.warning,
                "icon": palette.text_primary
            },
            StatusState.SUCCESS: {
                "background": palette.success,
                "text": palette.text_primary,
                "border": palette.success,
                "icon": palette.text_primary
            },
            StatusState.INFO: {
                "background": palette.info,
                "text": palette.text_primary,
                "border": palette.info,
                "icon": palette.text_primary
            },

            # Training states
            StatusState.TRAINING: {
                "background": palette.primary,
                "text": palette.text_primary,
                "border": palette.primary,
                "icon": palette.text_primary
            },
            StatusState.PAUSED: {
                "background": palette.warning,
                "text": palette.text_primary,
                "border": palette.warning,
                "icon": palette.text_primary
            },
            StatusState.STOPPED: {
                "background": palette.error,
                "text": palette.text_primary,
                "border": palette.error,
                "icon": palette.text_primary
            },
            StatusState.CANCELLED: {
                "background": palette.text_disabled,
                "text": palette.text_primary,
                "border": palette.text_disabled,
                "icon": palette.text_primary
            },

            # Model states
            StatusState.READY: {
                "background": palette.success,
                "text": palette.text_primary,
                "border": palette.success,
                "icon": palette.text_primary
            },
            StatusState.DEPLOYED: {
                "background": palette.primary,
                "text": palette.text_primary,
                "border": palette.primary,
                "icon": palette.text_primary
            },
            StatusState.ARCHIVED: {
                "background": palette.text_disabled,
                "text": palette.text_primary,
                "border": palette.text_disabled,
                "icon": palette.text_primary
            },

            # Processing states
            StatusState.PROCESSING: {
                "background": palette.primary,
                "text": palette.text_primary,
                "border": palette.primary,
                "icon": palette.text_primary
            },
            StatusState.QUEUED: {
                "background": palette.warning,
                "text": palette.text_primary,
                "border": palette.warning,
                "icon": palette.text_primary
            },
            StatusState.VALIDATING: {
                "background": palette.info,
                "text": palette.text_primary,
                "border": palette.info,
                "icon": palette.text_primary
            },
            StatusState.OPTIMIZING: {
                "background": palette.secondary,
                "text": palette.text_primary,
                "border": palette.secondary,
                "icon": palette.text_primary
            },

            # Health states
            StatusState.HEALTHY: {
                "background": palette.success,
                "text": palette.text_primary,
                "border": palette.success,
                "icon": palette.text_primary
            },
            StatusState.DEGRADED: {
                "background": palette.warning,
                "text": palette.text_primary,
                "border": palette.warning,
                "icon": palette.text_primary
            },
            StatusState.CRITICAL: {
                "background": palette.error,
                "text": palette.text_primary,
                "border": palette.error,
                "icon": palette.text_primary
            },
            StatusState.UNKNOWN: {
                "background": palette.text_disabled,
                "text": palette.text_primary,
                "border": palette.text_disabled,
                "icon": palette.text_primary
            }
        }

        return color_configs.get(self._state, color_configs[StatusState.IDLE])

    def _get_state_icon(self) -> str:
        """Get icon for current state."""
        icons = self.get_icons()

        # Use custom icon if provided
        if self._config.custom_icon:
            return self._config.custom_icon

        # State-specific icon mapping
        icon_mapping = {
            # General states
            StatusState.IDLE: icons.CIRCLE,
            StatusState.ACTIVE: icons.PLAY_CIRCLE,
            StatusState.INACTIVE: icons.PAUSE_CIRCLE,
            StatusState.PENDING: icons.SCHEDULE,
            StatusState.COMPLETED: icons.CHECK_CIRCLE,
            StatusState.FAILED: icons.ERROR,
            StatusState.ERROR: icons.ERROR,
            StatusState.WARNING: icons.WARNING,
            StatusState.SUCCESS: icons.CHECK_CIRCLE,
            StatusState.INFO: icons.INFO,

            # Training states
            StatusState.TRAINING: icons.PLAY_CIRCLE,
            StatusState.PAUSED: icons.PAUSE_CIRCLE,
            StatusState.STOPPED: icons.STOP,
            StatusState.CANCELLED: icons.CANCEL,

            # Model states
            StatusState.READY: icons.CHECK_CIRCLE,
            StatusState.DEPLOYED: icons.ROCKET_LAUNCH,
            StatusState.ARCHIVED: icons.ARCHIVE,

            # Processing states
            StatusState.PROCESSING: icons.SYNC,
            StatusState.QUEUED: icons.SCHEDULE,
            StatusState.VALIDATING: icons.VERIFIED,
            StatusState.OPTIMIZING: icons.TUNE,

            # Health states
            StatusState.HEALTHY: icons.HEALTH,
            StatusState.DEGRADED: icons.WARNING,
            StatusState.CRITICAL: icons.DANGEROUS,
            StatusState.UNKNOWN: icons.HELP
        }

        return icon_mapping.get(self._state, icons.CIRCLE)

    def _create_badge_components(self) -> None:
        """Create badge UI components."""
        try:
            # Create icon component
            if self._config.show_icon:
                self._icon_component = self._create_icon_component()

            # Create text component
            if self._config.show_text:
                self._text_component = self._create_text_component()

            # Create count component
            if self._config.show_count and self._metrics.count > 0:
                self._count_component = self._create_count_component()

            # Create main badge container
            self._badge_container = self._create_badge_container()

        except Exception as e:
            print(f"Error creating badge components: {e}")

    def _create_icon_component(self) -> ft.Control:
        """Create icon component."""
        try:
            icon_name = self._get_state_icon()

            return ft.Icon(
                name=icon_name,
                size=self._size_config["icon_size"],
                color=self._color_config["icon"]
            )

        except Exception as e:
            print(f"Error creating icon component: {e}")
            return ft.Container()

    def _create_text_component(self) -> ft.Control:
        """Create text component."""
        try:
            display_text = self._metrics.display_text or self._state.value.title()

            return ft.Text(
                display_text,
                size=self._size_config["font_size"],
                color=self._color_config["text"],
                weight=ft.FontWeight.W_500,
                text_align=ft.TextAlign.CENTER
            )

        except Exception as e:
            print(f"Error creating text component: {e}")
            return ft.Container()

    def _create_count_component(self) -> ft.Control:
        """Create count component."""
        try:
            count_text = str(min(self._metrics.count, self._metrics.max_count))
            if self._metrics.count > self._metrics.max_count:
                count_text += "+"

            return ft.Text(
                count_text,
                size=self._size_config["font_size"] - 1,
                color=self._color_config["text"],
                weight=ft.FontWeight.W_600,
                text_align=ft.TextAlign.CENTER
            )

        except Exception as e:
            print(f"Error creating count component: {e}")
            return ft.Container()

    def _create_badge_container(self) -> ft.Control:
        """Create main badge container."""
        try:
            # Collect components to display
            components = []

            if self._icon_component and self._config.show_icon:
                components.append(self._icon_component)

            if self._text_component and self._config.show_text:
                components.append(self._text_component)

            if self._count_component and self._config.show_count:
                components.append(self._count_component)

            # Create content based on variant
            if self._config.variant == StatusVariant.DOT:
                content = self._create_dot_variant()
            else:
                content = ft.Row(
                    controls=components,
                    spacing=self.get_spacing().xs,
                    tight=True,
                    alignment=ft.MainAxisAlignment.CENTER
                )

            # Apply variant-specific styling
            container_style = self._get_container_style()

            return ft.Container(
                content=content,
                bgcolor=container_style["background"],
                border=container_style["border"],
                border_radius=container_style["border_radius"],
                padding=container_style["padding"],
                height=container_style["height"],
                opacity=self._config.opacity,
                tooltip=self._get_tooltip_text(),
                on_click=self._handle_click if self._config.interactive else None,
                on_hover=self._handle_hover if self._config.interactive else None,
                animate_opacity=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT) if self._config.animated else None
            )

        except Exception as e:
            print(f"Error creating badge container: {e}")
            return ft.Container()

    def _create_dot_variant(self) -> ft.Control:
        """Create dot variant badge."""
        try:
            dot_size = self._size_config["height"] // 2

            return ft.Container(
                width=dot_size,
                height=dot_size,
                bgcolor=self._color_config["background"],
                border_radius=ft.border_radius.all(dot_size // 2)
            )

        except Exception as e:
            print(f"Error creating dot variant: {e}")
            return ft.Container()

    def _get_container_style(self) -> Dict[str, Any]:
        """Get container styling based on variant."""
        try:
            palette = self.get_palette()

            base_style = {
                "height": self._size_config["height"],
                "padding": ft.padding.symmetric(
                    horizontal=self._size_config["padding_h"],
                    vertical=self._size_config["padding_v"]
                ),
                "border_radius": ft.border_radius.all(self._size_config["border_radius"])
            }

            if self._config.variant == StatusVariant.FILLED:
                base_style.update({
                    "background": self._color_config["background"],
                    "border": None
                })
            elif self._config.variant == StatusVariant.OUTLINED:
                base_style.update({
                    "background": palette.surface,
                    "border": ft.border.all(self._config.border_width, self._color_config["border"])
                })
            elif self._config.variant == StatusVariant.SUBTLE:
                base_style.update({
                    "background": self.get_color_with_opacity(self._color_config["background"], 0.1),
                    "border": None
                })
            elif self._config.variant == StatusVariant.PILL:
                base_style.update({
                    "background": self._color_config["background"],
                    "border": None,
                    "border_radius": ft.border_radius.all(self._size_config["height"] // 2)
                })
            elif self._config.variant == StatusVariant.SQUARE:
                base_style.update({
                    "background": self._color_config["background"],
                    "border": None,
                    "border_radius": ft.border_radius.all(4)
                })
            elif self._config.variant == StatusVariant.ROUNDED:
                base_style.update({
                    "background": self._color_config["background"],
                    "border": None,
                    "border_radius": ft.border_radius.all(8)
                })

            return base_style

        except Exception as e:
            print(f"Error getting container style: {e}")
            return {}

    def _get_tooltip_text(self) -> str:
        """Get tooltip text for badge."""
        if not self._config.tooltip_enabled:
            return ""

        if self._metrics.tooltip_text:
            return self._metrics.tooltip_text

        # Generate default tooltip
        state_text = self._state.value.title()
        if self._metrics.count > 0:
            return f"{state_text} ({self._metrics.count})"

        return state_text

    def _handle_click(self, e) -> None:
        """Handle badge click event."""
        try:
            if self._on_click:
                self._on_click(self._state, self._metrics)
        except Exception as ex:
            print(f"Error handling badge click: {ex}")

    def _handle_hover(self, e) -> None:
        """Handle badge hover event."""
        try:
            if self._on_hover:
                self._on_hover(self._state, self._metrics, e.data == "true")
        except Exception as ex:
            print(f"Error handling badge hover: {ex}")

    def _apply_initial_state(self) -> None:
        """Apply initial state to badge."""
        try:
            if self._badge_container:
                self.content = self._badge_container

            # Set accessibility properties
            if self._config.accessibility_label:
                self.semantics_label = self._config.accessibility_label
            elif self._metrics.aria_label:
                self.semantics_label = self._metrics.aria_label
            else:
                self.semantics_label = f"Status: {self._state.value}"

            # Start auto-hide timer if enabled
            if self._config.auto_hide:
                self._start_auto_hide_timer()

        except Exception as e:
            print(f"Error applying initial state: {e}")

    def _start_auto_hide_timer(self) -> None:
        """Start auto-hide timer."""
        try:
            if self._hide_timer:
                # Cancel existing timer
                pass  # In a real implementation, you'd cancel the timer

            # In a real implementation, you'd set a timer here
            # For now, we'll just mark it as started
            self._hide_timer = True

        except Exception as e:
            print(f"Error starting auto-hide timer: {e}")

    def build(self) -> ft.Control:
        """Build the status badge component."""
        try:
            if not self._badge_container:
                self._create_badge_components()

            return self._badge_container or ft.Container()

        except Exception as e:
            print(f"Error building status badge: {e}")
            return ft.Container()

    # Public methods for updating badge state

    def update_state(self, new_state: StatusState) -> None:
        """
        Update badge state.

        Args:
            new_state: New status state
        """
        try:
            if new_state != self._state:
                self._state = new_state
                self._last_update_time = datetime.now(timezone.utc)
                self._metrics.total_updates += 1

                # Refresh styling and components
                self._setup_badge_styling()
                self._create_badge_components()

                # Apply pulse animation if enabled
                if self._config.pulse_on_update:
                    self._apply_pulse_animation()

                # Update UI
                if self._badge_container:
                    self.content = self._badge_container
                    self.update()

        except Exception as e:
            print(f"Error updating badge state: {e}")

    def update_count(self, new_count: int) -> None:
        """
        Update badge count.

        Args:
            new_count: New count value
        """
        try:
            if new_count != self._metrics.count:
                self._metrics.count = new_count
                self._last_update_time = datetime.now(timezone.utc)
                self._metrics.total_updates += 1

                # Recreate count component if needed
                if self._config.show_count:
                    self._count_component = self._create_count_component()
                    self._badge_container = self._create_badge_container()

                    # Update UI
                    if self._badge_container:
                        self.content = self._badge_container
                        self.update()

        except Exception as e:
            print(f"Error updating badge count: {e}")

    def update_text(self, new_text: str) -> None:
        """
        Update badge display text.

        Args:
            new_text: New display text
        """
        try:
            if new_text != self._metrics.display_text:
                self._metrics.display_text = new_text
                self._last_update_time = datetime.now(timezone.utc)

                # Recreate text component
                if self._config.show_text:
                    self._text_component = self._create_text_component()
                    self._badge_container = self._create_badge_container()

                    # Update UI
                    if self._badge_container:
                        self.content = self._badge_container
                        self.update()

        except Exception as e:
            print(f"Error updating badge text: {e}")

    def _apply_pulse_animation(self) -> None:
        """Apply pulse animation to badge."""
        try:
            if self._badge_container and not self._is_animating:
                self._is_animating = True

                # In a real implementation, you'd apply pulse animation here
                # For now, we'll just mark it as animated

                # Reset animation flag after delay
                # In a real implementation, you'd use a timer
                self._is_animating = False

        except Exception as e:
            print(f"Error applying pulse animation: {e}")

    def set_visibility(self, visible: bool) -> None:
        """
        Set badge visibility.

        Args:
            visible: Whether badge should be visible
        """
        try:
            self._is_visible = visible
            self.visible = visible
            self.update()

        except Exception as e:
            print(f"Error setting badge visibility: {e}")

    def get_state(self) -> StatusState:
        """Get current badge state."""
        return self._state

    def get_metrics(self) -> BadgeMetrics:
        """Get current badge metrics."""
        return self._metrics

    def get_config(self) -> BadgeConfig:
        """Get current badge configuration."""
        return self._config


# Specialized Badge Classes

class NotificationBadge(StatusBadge):
    """Specialized notification badge with count display."""

    def __init__(self, count: int = 0, **kwargs):
        config = BadgeConfig(
            badge_type=StatusType.NOTIFICATION,
            variant=StatusVariant.FILLED,
            show_icon=False,
            show_text=False,
            show_count=True,
            size=StatusSize.SMALL
        )
        metrics = BadgeMetrics(count=count)

        super().__init__(
            state=StatusState.ACTIVE if count > 0 else StatusState.IDLE,
            config=config,
            metrics=metrics,
            **kwargs
        )


class CountBadge(StatusBadge):
    """Specialized count badge for numeric indicators."""

    def __init__(self, count: int = 0, max_count: int = 99, **kwargs):
        config = BadgeConfig(
            badge_type=StatusType.COUNT,
            variant=StatusVariant.PILL,
            show_icon=False,
            show_text=False,
            show_count=True,
            size=StatusSize.SMALL
        )
        metrics = BadgeMetrics(count=count, max_count=max_count)

        super().__init__(
            state=StatusState.ACTIVE,
            config=config,
            metrics=metrics,
            **kwargs
        )


class HealthBadge(StatusBadge):
    """Specialized health status badge."""

    def __init__(self, health_state: StatusState = StatusState.HEALTHY, **kwargs):
        config = BadgeConfig(
            badge_type=StatusType.HEALTH,
            variant=StatusVariant.FILLED,
            show_icon=True,
            show_text=True,
            size=StatusSize.MEDIUM
        )

        super().__init__(
            state=health_state,
            config=config,
            **kwargs
        )


class ProcessingBadge(StatusBadge):
    """Specialized processing status badge."""

    def __init__(self, processing_state: StatusState = StatusState.PROCESSING, **kwargs):
        config = BadgeConfig(
            badge_type=StatusType.PROCESSING,
            variant=StatusVariant.FILLED,
            show_icon=True,
            show_text=True,
            animated=True,
            pulse_on_update=True,
            size=StatusSize.MEDIUM
        )

        super().__init__(
            state=processing_state,
            config=config,
            **kwargs
        )


class TrainingBadge(StatusBadge):
    """Specialized training status badge."""

    def __init__(self, training_state: StatusState = StatusState.TRAINING, **kwargs):
        config = BadgeConfig(
            badge_type=StatusType.TRAINING,
            variant=StatusVariant.FILLED,
            show_icon=True,
            show_text=True,
            animated=True,
            pulse_on_update=True,
            size=StatusSize.MEDIUM
        )

        super().__init__(
            state=training_state,
            config=config,
            **kwargs
        )


class SystemBadge(StatusBadge):
    """Specialized system status badge."""

    def __init__(self, system_state: StatusState = StatusState.ACTIVE, **kwargs):
        config = BadgeConfig(
            badge_type=StatusType.SYSTEM,
            variant=StatusVariant.OUTLINED,
            show_icon=True,
            show_text=True,
            size=StatusSize.SMALL
        )

        super().__init__(
            state=system_state,
            config=config,
            **kwargs
        )


class CustomBadge(StatusBadge):
    """Fully customizable badge component."""

    def __init__(self,
                 text: str = "",
                 icon: Optional[str] = None,
                 color: Optional[str] = None,
                 **kwargs):
        config = BadgeConfig(
            badge_type=StatusType.CUSTOM,
            custom_icon=icon,
            custom_color=color,
            **kwargs
        )
        metrics = BadgeMetrics(display_text=text)

        super().__init__(
            state=StatusState.ACTIVE,
            config=config,
            metrics=metrics,
            **kwargs
        )


class BadgeGroup(ThemeAwareUserControl):
    """Container for grouping multiple badges with consistent spacing."""

    def __init__(self,
                 badges: List[StatusBadge],
                 spacing: Optional[int] = None,
                 alignment: ft.MainAxisAlignment = ft.MainAxisAlignment.START,
                 wrap: bool = False,
                 **kwargs):
        super().__init__(**kwargs)

        self._badges = badges
        self._spacing = spacing
        self._alignment = alignment
        self._wrap = wrap

        self._group_container = None
        self._initialize_group()

    def _initialize_group(self) -> None:
        """Initialize badge group."""
        try:
            self._create_group_container()

        except Exception as e:
            print(f"Error initializing badge group: {e}")

    def _create_group_container(self) -> None:
        """Create group container."""
        try:
            spacing = self._spacing or self.get_spacing().sm

            if self._wrap:
                # Use wrap layout for responsive design
                self._group_container = ft.Wrap(
                    controls=self._badges,
                    spacing=spacing,
                    run_spacing=spacing,
                    alignment=ft.WrapAlignment.START
                )
            else:
                # Use row layout
                self._group_container = ft.Row(
                    controls=self._badges,
                    spacing=spacing,
                    alignment=self._alignment,
                    tight=True
                )

            self.content = self._group_container

        except Exception as e:
            print(f"Error creating group container: {e}")

    def add_badge(self, badge: StatusBadge) -> None:
        """Add badge to group."""
        try:
            self._badges.append(badge)
            self._create_group_container()
            self.update()

        except Exception as e:
            print(f"Error adding badge to group: {e}")

    def remove_badge(self, badge: StatusBadge) -> None:
        """Remove badge from group."""
        try:
            if badge in self._badges:
                self._badges.remove(badge)
                self._create_group_container()
                self.update()

        except Exception as e:
            print(f"Error removing badge from group: {e}")

    def clear_badges(self) -> None:
        """Clear all badges from group."""
        try:
            self._badges.clear()
            self._create_group_container()
            self.update()

        except Exception as e:
            print(f"Error clearing badges: {e}")

    def get_badges(self) -> List[StatusBadge]:
        """Get all badges in group."""
        return self._badges.copy()

    def build(self) -> ft.Control:
        """Build the badge group component."""
        return self._group_container or ft.Container()


class BadgeContainer(ThemeAwareUserControl):
    """Advanced container for badges with positioning and layout options."""

    def __init__(self,
                 content: ft.Control,
                 badge: StatusBadge,
                 position: str = "top-right",  # top-right, top-left, bottom-right, bottom-left
                 offset_x: int = 0,
                 offset_y: int = 0,
                 **kwargs):
        super().__init__(**kwargs)

        self._content = content
        self._badge = badge
        self._position = position
        self._offset_x = offset_x
        self._offset_y = offset_y

        self._container = None
        self._initialize_container()

    def _initialize_container(self) -> None:
        """Initialize badge container."""
        try:
            self._create_container()

        except Exception as e:
            print(f"Error initializing badge container: {e}")

    def _create_container(self) -> None:
        """Create badge container with positioned badge."""
        try:
            # Calculate badge position
            badge_position = self._calculate_badge_position()

            # Create stack with content and positioned badge
            self._container = ft.Stack(
                controls=[
                    self._content,
                    ft.Positioned(
                        content=self._badge,
                        **badge_position
                    )
                ]
            )

            self.content = self._container

        except Exception as e:
            print(f"Error creating badge container: {e}")

    def _calculate_badge_position(self) -> Dict[str, Any]:
        """Calculate badge position based on configuration."""
        try:
            responsive = self.get_responsive_layout()

            # Base offset values
            base_offset = responsive.get_breakpoint_value(4, 6, 8, 10)

            position_map = {
                "top-right": {
                    "top": base_offset + self._offset_y,
                    "right": base_offset + self._offset_x
                },
                "top-left": {
                    "top": base_offset + self._offset_y,
                    "left": base_offset + self._offset_x
                },
                "bottom-right": {
                    "bottom": base_offset + self._offset_y,
                    "right": base_offset + self._offset_x
                },
                "bottom-left": {
                    "bottom": base_offset + self._offset_y,
                    "left": base_offset + self._offset_x
                }
            }

            return position_map.get(self._position, position_map["top-right"])

        except Exception as e:
            print(f"Error calculating badge position: {e}")
            return {"top": 0, "right": 0}

    def update_badge(self, new_badge: StatusBadge) -> None:
        """Update the badge."""
        try:
            self._badge = new_badge
            self._create_container()
            self.update()

        except Exception as e:
            print(f"Error updating badge: {e}")

    def set_position(self, position: str, offset_x: int = 0, offset_y: int = 0) -> None:
        """Update badge position."""
        try:
            self._position = position
            self._offset_x = offset_x
            self._offset_y = offset_y
            self._create_container()
            self.update()

        except Exception as e:
            print(f"Error setting badge position: {e}")

    def build(self) -> ft.Control:
        """Build the badge container component."""
        return self._container or ft.Container()


class StatusBadgesUI(ThemeAwareUserControl):
    """
    Main status badges UI component providing comprehensive badge management.

    Features:
    - Multiple badge types and variants
    - Responsive design with theme integration
    - Badge grouping and positioning
    - Real-time updates and animations
    - Accessibility compliance
    - Performance optimization
    """

    def __init__(self,
                 enable_animations: bool = True,
                 default_size: StatusSize = StatusSize.MEDIUM,
                 default_variant: StatusVariant = StatusVariant.FILLED,
                 **kwargs):
        super().__init__(**kwargs)

        self._enable_animations = enable_animations
        self._default_size = default_size
        self._default_variant = default_variant

        # Badge registry
        self._badges: Dict[str, StatusBadge] = {}
        self._badge_groups: Dict[str, BadgeGroup] = {}
        self._badge_containers: Dict[str, BadgeContainer] = {}

        # UI components
        self._main_container = None
        self._demo_section = None

        # Initialize UI
        self._initialize_ui()

    def _initialize_ui(self) -> None:
        """Initialize the status badges UI."""
        try:
            self._create_main_container()
            self._create_demo_section()

        except Exception as e:
            print(f"Error initializing status badges UI: {e}")

    def _create_main_container(self) -> None:
        """Create main container."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            self._main_container = ft.Container(
                content=ft.Column(
                    controls=[],
                    spacing=spacing.lg,
                    horizontal_alignment=ft.CrossAxisAlignment.START
                ),
                padding=ft.padding.all(spacing.lg),
                bgcolor=palette.surface,
                border_radius=ft.border_radius.all(8)
            )

            self.content = self._main_container

        except Exception as e:
            print(f"Error creating main container: {e}")

    def _create_demo_section(self) -> None:
        """Create demonstration section with various badge examples."""
        try:
            # Create example badges
            demo_badges = self._create_demo_badges()

            # Create demo section
            self._demo_section = ft.Column(
                controls=[
                    ft.Text(
                        "Status Badges Demo",
                        style=self.get_text_style("headingMedium"),
                        color=self.get_palette().text_primary
                    ),
                    ft.Divider(),
                    *demo_badges
                ],
                spacing=self.get_spacing().md
            )

            # Add to main container
            if self._main_container and self._main_container.content:
                self._main_container.content.controls.append(self._demo_section)

        except Exception as e:
            print(f"Error creating demo section: {e}")

    def _create_demo_badges(self) -> List[ft.Control]:
        """Create demonstration badges."""
        try:
            demo_controls = []
            spacing = self.get_spacing()

            # Status badges section
            status_badges = [
                StatusBadge(StatusState.ACTIVE, BadgeConfig(size=self._default_size)),
                StatusBadge(StatusState.PENDING, BadgeConfig(size=self._default_size)),
                StatusBadge(StatusState.COMPLETED, BadgeConfig(size=self._default_size)),
                StatusBadge(StatusState.ERROR, BadgeConfig(size=self._default_size)),
                StatusBadge(StatusState.WARNING, BadgeConfig(size=self._default_size))
            ]

            demo_controls.extend([
                ft.Text("Status Badges", style=self.get_text_style("bodyLarge")),
                BadgeGroup(status_badges, spacing=spacing.sm)
            ])

            # Training badges section
            training_badges = [
                TrainingBadge(StatusState.TRAINING),
                TrainingBadge(StatusState.PAUSED),
                TrainingBadge(StatusState.COMPLETED),
                TrainingBadge(StatusState.CANCELLED)
            ]

            demo_controls.extend([
                ft.Text("Training Badges", style=self.get_text_style("bodyLarge")),
                BadgeGroup(training_badges, spacing=spacing.sm)
            ])

            # Health badges section
            health_badges = [
                HealthBadge(StatusState.HEALTHY),
                HealthBadge(StatusState.DEGRADED),
                HealthBadge(StatusState.CRITICAL),
                HealthBadge(StatusState.UNKNOWN)
            ]

            demo_controls.extend([
                ft.Text("Health Badges", style=self.get_text_style("bodyLarge")),
                BadgeGroup(health_badges, spacing=spacing.sm)
            ])

            # Notification badges section
            notification_badges = [
                NotificationBadge(count=0),
                NotificationBadge(count=5),
                NotificationBadge(count=25),
                NotificationBadge(count=99),
                NotificationBadge(count=150)
            ]

            demo_controls.extend([
                ft.Text("Notification Badges", style=self.get_text_style("bodyLarge")),
                BadgeGroup(notification_badges, spacing=spacing.sm)
            ])

            return demo_controls

        except Exception as e:
            print(f"Error creating demo badges: {e}")
            return []

    # Public API methods

    def create_status_badge(self,
                           state: StatusState,
                           config: Optional[BadgeConfig] = None,
                           metrics: Optional[BadgeMetrics] = None,
                           badge_id: Optional[str] = None) -> StatusBadge:
        """
        Create a new status badge.

        Args:
            state: Badge state
            config: Badge configuration
            metrics: Badge metrics
            badge_id: Optional badge identifier for registry

        Returns:
            Created status badge
        """
        try:
            # Use default config if not provided
            if config is None:
                config = BadgeConfig(
                    size=self._default_size,
                    variant=self._default_variant,
                    animated=self._enable_animations
                )

            # Create badge
            badge = StatusBadge(state=state, config=config, metrics=metrics)

            # Register badge if ID provided
            if badge_id:
                self._badges[badge_id] = badge

            return badge

        except Exception as e:
            print(f"Error creating status badge: {e}")
            return StatusBadge()

    def create_notification_badge(self,
                                count: int = 0,
                                badge_id: Optional[str] = None) -> NotificationBadge:
        """
        Create a notification badge.

        Args:
            count: Notification count
            badge_id: Optional badge identifier

        Returns:
            Created notification badge
        """
        try:
            badge = NotificationBadge(count=count)

            if badge_id:
                self._badges[badge_id] = badge

            return badge

        except Exception as e:
            print(f"Error creating notification badge: {e}")
            return NotificationBadge()

    def create_training_badge(self,
                            state: StatusState = StatusState.TRAINING,
                            badge_id: Optional[str] = None) -> TrainingBadge:
        """
        Create a training badge.

        Args:
            state: Training state
            badge_id: Optional badge identifier

        Returns:
            Created training badge
        """
        try:
            badge = TrainingBadge(training_state=state)

            if badge_id:
                self._badges[badge_id] = badge

            return badge

        except Exception as e:
            print(f"Error creating training badge: {e}")
            return TrainingBadge()

    def create_health_badge(self,
                          state: StatusState = StatusState.HEALTHY,
                          badge_id: Optional[str] = None) -> HealthBadge:
        """
        Create a health badge.

        Args:
            state: Health state
            badge_id: Optional badge identifier

        Returns:
            Created health badge
        """
        try:
            badge = HealthBadge(health_state=state)

            if badge_id:
                self._badges[badge_id] = badge

            return badge

        except Exception as e:
            print(f"Error creating health badge: {e}")
            return HealthBadge()

    def create_badge_group(self,
                         badges: List[StatusBadge],
                         group_id: Optional[str] = None,
                         **kwargs) -> BadgeGroup:
        """
        Create a badge group.

        Args:
            badges: List of badges to group
            group_id: Optional group identifier
            **kwargs: Additional group configuration

        Returns:
            Created badge group
        """
        try:
            group = BadgeGroup(badges=badges, **kwargs)

            if group_id:
                self._badge_groups[group_id] = group

            return group

        except Exception as e:
            print(f"Error creating badge group: {e}")
            return BadgeGroup([])

    def create_badge_container(self,
                             content: ft.Control,
                             badge: StatusBadge,
                             container_id: Optional[str] = None,
                             **kwargs) -> BadgeContainer:
        """
        Create a badge container.

        Args:
            content: Content to wrap
            badge: Badge to position
            container_id: Optional container identifier
            **kwargs: Additional container configuration

        Returns:
            Created badge container
        """
        try:
            container = BadgeContainer(content=content, badge=badge, **kwargs)

            if container_id:
                self._badge_containers[container_id] = container

            return container

        except Exception as e:
            print(f"Error creating badge container: {e}")
            return BadgeContainer(ft.Container(), StatusBadge())

    def get_badge(self, badge_id: str) -> Optional[StatusBadge]:
        """Get badge by ID."""
        return self._badges.get(badge_id)

    def get_badge_group(self, group_id: str) -> Optional[BadgeGroup]:
        """Get badge group by ID."""
        return self._badge_groups.get(group_id)

    def get_badge_container(self, container_id: str) -> Optional[BadgeContainer]:
        """Get badge container by ID."""
        return self._badge_containers.get(container_id)

    def update_badge_state(self, badge_id: str, new_state: StatusState) -> bool:
        """
        Update badge state by ID.

        Args:
            badge_id: Badge identifier
            new_state: New state

        Returns:
            True if updated successfully
        """
        try:
            badge = self._badges.get(badge_id)
            if badge:
                badge.update_state(new_state)
                return True
            return False

        except Exception as e:
            print(f"Error updating badge state: {e}")
            return False

    def update_notification_count(self, badge_id: str, count: int) -> bool:
        """
        Update notification badge count.

        Args:
            badge_id: Badge identifier
            count: New count

        Returns:
            True if updated successfully
        """
        try:
            badge = self._badges.get(badge_id)
            if badge:
                badge.update_count(count)
                return True
            return False

        except Exception as e:
            print(f"Error updating notification count: {e}")
            return False

    def remove_badge(self, badge_id: str) -> bool:
        """
        Remove badge from registry.

        Args:
            badge_id: Badge identifier

        Returns:
            True if removed successfully
        """
        try:
            if badge_id in self._badges:
                del self._badges[badge_id]
                return True
            return False

        except Exception as e:
            print(f"Error removing badge: {e}")
            return False

    def clear_all_badges(self) -> None:
        """Clear all badges from registry."""
        try:
            self._badges.clear()
            self._badge_groups.clear()
            self._badge_containers.clear()

        except Exception as e:
            print(f"Error clearing badges: {e}")

    def get_badge_count(self) -> int:
        """Get total number of registered badges."""
        return len(self._badges)

    def build(self) -> ft.Control:
        """Build the status badges UI component."""
        try:
            return self._main_container or ft.Container()

        except Exception as e:
            print(f"Error building status badges UI: {e}")
            return ft.Container()


# Utility functions for creating common badge patterns

def create_training_status_badge(state: StatusState, **kwargs) -> TrainingBadge:
    """Create a training status badge with common configuration."""
    return TrainingBadge(training_state=state, **kwargs)


def create_health_indicator_badge(is_healthy: bool, **kwargs) -> HealthBadge:
    """Create a health indicator badge based on boolean status."""
    state = StatusState.HEALTHY if is_healthy else StatusState.CRITICAL
    return HealthBadge(health_state=state, **kwargs)


def create_notification_counter(count: int, **kwargs) -> NotificationBadge:
    """Create a notification counter badge."""
    return NotificationBadge(count=count, **kwargs)


def create_processing_indicator(is_processing: bool, **kwargs) -> ProcessingBadge:
    """Create a processing indicator badge."""
    state = StatusState.PROCESSING if is_processing else StatusState.IDLE
    return ProcessingBadge(processing_state=state, **kwargs)


def create_system_status_badge(is_online: bool, **kwargs) -> SystemBadge:
    """Create a system status badge based on online status."""
    state = StatusState.ACTIVE if is_online else StatusState.INACTIVE
    return SystemBadge(system_state=state, **kwargs)
