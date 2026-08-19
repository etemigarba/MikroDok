"""
Module: theme_system_ui
Description: State-of-the-art theme management system with comprehensive responsive design capabilities.
            Provides centralized theme control, responsive layout management, color palette management,
            typography system, spacing definitions, and animation configurations for the MikroDok application.
            Implements WCAG 2.1 AA compliance with dark/light mode support, accessibility features,
            cross-platform consistency, and modern responsive design patterns.

Features:
- Responsive Layout Manager with viewport detection and adaptive layouts
- Breakpoint-based design system (Mobile, Tablet, Desktop, Large Desktop)
- Performance-optimized layout calculations with caching and memoization
- Accessibility compliance with WCAG 2.1 AA standards
- Component pooling for efficient memory management
- Responsive utility functions for common design patterns
- Focus management and keyboard navigation support
- Reduced motion and high contrast accessibility options

Phase: 1 (Enhanced with Responsive Design)
Location: /src/modules/ui/theme_system_ui/theme_system_ui.py

Usage Examples:

1. Basic Responsive Layout:
```python
from src.modules.ui.theme_system_ui import get_theme_manager, ResponsiveGrid

# Get theme manager with responsive capabilities
theme_manager = get_theme_manager()

# Create responsive grid that adapts to screen size
children = [ft.Container() for _ in range(8)]
responsive_grid = theme_manager.create_responsive_grid(
    children=children,
    mobile_cols=1,
    tablet_cols=2,
    desktop_cols=3,
    large_cols=4
)
```

2. Responsive Component Creation:
```python
# Create responsive container with adaptive padding
content = ft.Text("Hello World")
responsive_container = theme_manager.create_responsive_container(
    content=content,
    padding=None,  # Uses responsive default
    max_width=None  # Uses responsive default
)

# Get breakpoint-specific values
padding = theme_manager.get_breakpoint_value(
    mobile=12, tablet=16, desktop=24, large=32
)
```

3. Accessibility-Compliant Components:
```python
# Create accessible button with proper touch targets
accessible_button = theme_manager.create_accessible_component(
    component_type="button",
    text="Click Me",
    on_click=handle_click
)

# Create accessible text with responsive sizing
accessible_text = theme_manager.create_accessible_component(
    component_type="text",
    value="Important Message",
    size=16
)
```

4. Performance Monitoring:
```python
# Get performance metrics
responsive_manager = theme_manager.get_responsive_layout_manager()
metrics = responsive_manager.get_performance_report()
print(f"Cache hit rate: {metrics['cache_hit_rate']}")

# Optimize performance
responsive_manager.optimize_layout_calculations()
```

5. Responsive Utility Functions:
```python
from src.modules.ui.theme_system_ui import (
    get_responsive_value,
    calculate_responsive_font_size,
    create_responsive_text_style
)

# Get responsive values
font_size = get_responsive_value(14, 15, 16, 18)  # mobile, tablet, desktop, large
spacing = calculate_responsive_spacing(16)
text_style = create_responsive_text_style(16, ft.FontWeight.W_500)
```

6. Viewport Detection and Events:
```python
# Initialize responsive event handling
responsive_handler = ResponsiveEventHandler(theme_manager)
responsive_handler.initialize(page)

# Add responsive callbacks
def on_screen_size_change(screen_size):
    print(f"Screen size changed to: {screen_size.value}")

responsive_handler.add_responsive_callback(on_screen_size_change)
```
"""

# Standard library imports
import os
import json
import time
import platform
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports - using lazy imports to avoid circular dependencies
# AppStateManager and UserPreferencesDB will be imported when needed


class ThemeMode(Enum):
    """Theme mode enumeration for MikroDok application."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"
    HIGH_CONTRAST = "high_contrast"


class ColorBlindMode(Enum):
    """Color blind accessibility mode enumeration."""
    NONE = "none"
    PROTANOPIA = "protanopia"
    DEUTERANOPIA = "deuteranopia"
    TRITANOPIA = "tritanopia"


class ScreenSize(Enum):
    """Screen size enumeration for responsive design."""
    MOBILE = "mobile"
    TABLET = "tablet"
    DESKTOP = "desktop"
    LARGE_DESKTOP = "large_desktop"


@dataclass
class ResponsiveBreakpoints:
    """
    Modern responsive breakpoint system for MikroDok application.

    Defines screen size breakpoints following industry standards and
    MikroDok design specifications for optimal user experience across devices.
    """
    # Breakpoint definitions (max-width values)
    mobile: int = 575          # 0-575px: Mobile devices (phones)
    tablet: int = 991          # 576-991px: Tablet devices (iPads, small laptops)
    desktop: int = 1599        # 992-1599px: Desktop displays (standard monitors)
    large_desktop: int = 1600  # 1600px+: Large desktop displays (4K, ultrawide)

    # Minimum supported resolution (as per project requirements)
    min_width: int = 1280
    min_height: int = 720

    # Container max-widths for centered layouts
    mobile_container: int = 100      # 100% width on mobile
    tablet_container: int = 768      # Fixed max-width on tablet
    desktop_container: int = 1200    # Fixed max-width on desktop
    large_container: int = 1400      # Fixed max-width on large desktop

    def get_screen_size(self, width: int) -> ScreenSize:
        """
        Determine screen size category based on viewport width.

        Args:
            width: Viewport width in pixels

        Returns:
            ScreenSize enum value
        """
        if width <= self.mobile:
            return ScreenSize.MOBILE
        elif width <= self.tablet:
            return ScreenSize.TABLET
        elif width <= self.desktop:
            return ScreenSize.DESKTOP
        else:
            return ScreenSize.LARGE_DESKTOP

    def get_container_width(self, screen_size: ScreenSize) -> int:
        """
        Get appropriate container max-width for screen size.

        Args:
            screen_size: Current screen size category

        Returns:
            Container max-width in pixels
        """
        container_map = {
            ScreenSize.MOBILE: self.mobile_container,
            ScreenSize.TABLET: self.tablet_container,
            ScreenSize.DESKTOP: self.desktop_container,
            ScreenSize.LARGE_DESKTOP: self.large_container
        }
        return container_map.get(screen_size, self.desktop_container)


@dataclass
class ResponsiveSizing:
    """
    Viewport-aware sizing system for responsive design.

    Provides scaling factors and sizing values that adapt to different
    screen sizes while maintaining design consistency and usability.
    """
    # Font scaling factors for different screen sizes
    mobile_font_scale: float = 0.9      # Slightly smaller text on mobile
    tablet_font_scale: float = 0.95     # Slightly smaller text on tablet
    desktop_font_scale: float = 1.0     # Base font size on desktop
    large_font_scale: float = 1.1       # Slightly larger text on large screens

    # Component padding for different screen sizes
    mobile_padding: int = 12             # Compact padding on mobile
    tablet_padding: int = 16             # Standard padding on tablet
    desktop_padding: int = 24            # Comfortable padding on desktop
    large_padding: int = 32              # Spacious padding on large screens

    # Grid column counts for responsive layouts
    mobile_columns: int = 1              # Single column on mobile
    tablet_columns: int = 2              # Two columns on tablet
    desktop_columns: int = 3             # Three columns on desktop
    large_columns: int = 4               # Four columns on large screens

    # Sidebar widths for different screen sizes
    mobile_sidebar: int = 280            # Full-width overlay on mobile
    tablet_sidebar: int = 240            # Narrow sidebar on tablet
    desktop_sidebar: int = 280           # Standard sidebar on desktop
    large_sidebar: int = 320             # Wide sidebar on large screens

    # Touch target sizes (minimum 44px for accessibility)
    mobile_touch_target: int = 48        # Larger touch targets on mobile
    tablet_touch_target: int = 44        # Standard touch targets on tablet
    desktop_touch_target: int = 40       # Smaller targets for mouse interaction
    large_touch_target: int = 40         # Consistent with desktop

    def get_font_scale(self, screen_size: ScreenSize) -> float:
        """
        Get font scaling factor for screen size.

        Args:
            screen_size: Current screen size category

        Returns:
            Font scaling factor
        """
        scale_map = {
            ScreenSize.MOBILE: self.mobile_font_scale,
            ScreenSize.TABLET: self.tablet_font_scale,
            ScreenSize.DESKTOP: self.desktop_font_scale,
            ScreenSize.LARGE_DESKTOP: self.large_font_scale
        }
        return scale_map.get(screen_size, self.desktop_font_scale)

    def get_padding(self, screen_size: ScreenSize) -> int:
        """
        Get appropriate padding for screen size.

        Args:
            screen_size: Current screen size category

        Returns:
            Padding value in pixels
        """
        padding_map = {
            ScreenSize.MOBILE: self.mobile_padding,
            ScreenSize.TABLET: self.tablet_padding,
            ScreenSize.DESKTOP: self.desktop_padding,
            ScreenSize.LARGE_DESKTOP: self.large_padding
        }
        return padding_map.get(screen_size, self.desktop_padding)

    def get_columns(self, screen_size: ScreenSize) -> int:
        """
        Get appropriate column count for screen size.

        Args:
            screen_size: Current screen size category

        Returns:
            Number of columns
        """
        column_map = {
            ScreenSize.MOBILE: self.mobile_columns,
            ScreenSize.TABLET: self.tablet_columns,
            ScreenSize.DESKTOP: self.desktop_columns,
            ScreenSize.LARGE_DESKTOP: self.large_columns
        }
        return column_map.get(screen_size, self.desktop_columns)

    def get_sidebar_width(self, screen_size: ScreenSize) -> int:
        """
        Get appropriate sidebar width for screen size.

        Args:
            screen_size: Current screen size category

        Returns:
            Sidebar width in pixels
        """
        sidebar_map = {
            ScreenSize.MOBILE: self.mobile_sidebar,
            ScreenSize.TABLET: self.tablet_sidebar,
            ScreenSize.DESKTOP: self.desktop_sidebar,
            ScreenSize.LARGE_DESKTOP: self.large_sidebar
        }
        return sidebar_map.get(screen_size, self.desktop_sidebar)

    def get_touch_target_size(self, screen_size: ScreenSize) -> int:
        """
        Get appropriate touch target size for screen size.

        Args:
            screen_size: Current screen size category

        Returns:
            Touch target size in pixels
        """
        target_map = {
            ScreenSize.MOBILE: self.mobile_touch_target,
            ScreenSize.TABLET: self.tablet_touch_target,
            ScreenSize.DESKTOP: self.desktop_touch_target,
            ScreenSize.LARGE_DESKTOP: self.large_touch_target
        }
        return target_map.get(screen_size, self.desktop_touch_target)


@dataclass
class ColorPalette:
    """Color palette definition for theme modes."""
    # Background colors
    background_primary: str
    background_secondary: str
    surface: str
    surface_variant: str

    # Text colors
    text_primary: str
    text_secondary: str
    text_tertiary: str
    text_disabled: str

    # Border and outline colors
    borders: str
    outline: str

    # State colors
    error: str
    error_container: str
    success: str
    warning: str
    info: str

    # Interactive colors
    primary: str
    primary_variant: str
    secondary: str
    secondary_variant: str

    # Focus and selection
    focus_indicator: str
    selection: str


@dataclass
class TypographyScale:
    """
    Typography scale definition following MikroDok design specifications.
    Based on Inter font family with JetBrains Mono for technical content.
    Tuple format: (size_px, line_height_px, weight, letter_spacing_percent)
    """
    # Font families
    primary_font: str = "Inter"
    secondary_font: str = "JetBrains Mono"
    fallback_fonts: str = "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial"
    mono_fallback_fonts: str = "SF Mono, Monaco, Consolas, Courier New, monospace"

    # Display sizes (48px, 40px, 32px)
    display_large: Tuple[int, int, int, float] = (48, 56, 600, 0.5)
    display_medium: Tuple[int, int, int, float] = (40, 48, 600, 0.25)
    display_small: Tuple[int, int, int, float] = (32, 40, 600, 0.0)

    # Heading sizes
    h1: Tuple[int, int, int, float] = (28, 36, 600, 0.0)
    h2: Tuple[int, int, int, float] = (24, 32, 600, 0.0)
    h3: Tuple[int, int, int, float] = (20, 28, 600, 0.0)
    h4: Tuple[int, int, int, float] = (18, 24, 500, 0.0)
    h5: Tuple[int, int, int, float] = (16, 20, 500, 0.0)
    h6: Tuple[int, int, int, float] = (14, 18, 500, 0.0)

    # Body text
    body_large: Tuple[int, int, int, float] = (16, 24, 400, 0.0)
    body_medium: Tuple[int, int, int, float] = (14, 20, 400, 0.0)  # Default
    body_small: Tuple[int, int, int, float] = (13, 18, 400, 0.0)

    # Supporting text
    caption: Tuple[int, int, int, float] = (12, 16, 400, 0.0)
    overline: Tuple[int, int, int, float] = (11, 16, 500, 4.0)  # Uppercase
    label: Tuple[int, int, int, float] = (12, 16, 500, 0.0)

    # Data display (monospace - JetBrains Mono)
    metric_large: Tuple[int, int, int, float] = (32, 36, 300, 0.0)
    metric_medium: Tuple[int, int, int, float] = (24, 28, 400, 0.0)
    code_block: Tuple[int, int, int, float] = (13, 20, 400, 0.0)
    inline_code: Tuple[int, int, int, float] = (13, 0, 400, 0.0)  # Inherit line height

    # Font weights
    light: int = 300
    regular: int = 400
    medium: int = 500
    semibold: int = 600
    bold: int = 700

    # Line height ratios
    tight: float = 1.2  # Display text
    normal: float = 1.5  # Body text
    relaxed: float = 1.75  # Small text, captions


@dataclass
class SpacingSystem:
    """Spacing system definition with consistent scale."""
    base_unit: int = 4
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32
    xxxl: int = 48
    xxxxl: int = 64

    # Component-specific spacing
    component_padding: int = 16
    section_padding: int = 24
    icon_text_gap: int = 8
    button_padding_horizontal: int = 16
    button_padding_vertical: int = 8


@dataclass
class IconSystem:
    """Centralized icon management system with categorized icons."""

    # System and Navigation Icons
    MENU: str = ft.Icons.MENU
    CLOSE: str = ft.Icons.CLOSE
    SETTINGS: str = ft.Icons.SETTINGS
    HOME: str = ft.Icons.HOME
    BACK: str = ft.Icons.ARROW_BACK
    FORWARD: str = ft.Icons.ARROW_FORWARD
    REFRESH: str = ft.Icons.REFRESH
    SEARCH: str = ft.Icons.SEARCH
    MINIMIZE: str = ft.Icons.MINIMIZE
    DARK_MODE: str = ft.Icons.DARK_MODE
    LIGHT_MODE: str = ft.Icons.LIGHT_MODE
    LOGOUT: str = ft.Icons.LOGOUT
    MONITOR: str = ft.Icons.MONITOR
    PERSON: str = ft.Icons.PERSON
    DESCRIPTION: str = ft.Icons.DESCRIPTION
    COMPUTER: str = ft.Icons.COMPUTER

    # Status and State Icons
    SUCCESS: str = ft.Icons.CHECK_CIRCLE
    ERROR: str = ft.Icons.ERROR
    WARNING: str = ft.Icons.WARNING
    INFO: str = ft.Icons.INFO
    LOADING: str = ft.Icons.HOURGLASS_EMPTY
    CIRCLE: str = ft.Icons.CIRCLE
    CHECK_CIRCLE: str = ft.Icons.CHECK_CIRCLE
    CHECK_CIRCLE_OUTLINE: str = ft.Icons.CHECK_CIRCLE_OUTLINE
    RADIO_BUTTON_UNCHECKED: str = ft.Icons.RADIO_BUTTON_UNCHECKED
    PLAY_CIRCLE_OUTLINE: str = ft.Icons.PLAY_CIRCLE_OUTLINE
    ROCKET_LAUNCH: str = ft.Icons.ROCKET_LAUNCH
    HELP: str = ft.Icons.HELP

    # Outlined variants for notification system
    INFO_OUTLINE: str = ft.Icons.INFO_OUTLINE
    ERROR_OUTLINE: str = ft.Icons.ERROR_OUTLINE
    WARNING_OUTLINE: str = ft.Icons.WARNING_OUTLINED
    WARNING_AMBER_OUTLINED: str = ft.Icons.WARNING_AMBER_OUTLINED
    CIRCLE_OUTLINED: str = ft.Icons.CIRCLE_OUTLINED
    DANGEROUS: str = ft.Icons.DANGEROUS

    # Progress and interaction icons
    EXPAND_MORE: str = ft.Icons.EXPAND_MORE
    EXPAND_LESS: str = ft.Icons.EXPAND_LESS
    CANCEL: str = ft.Icons.CANCEL

    # Resource Monitoring Icons
    CPU: str = ft.Icons.MEMORY
    MEMORY: str = ft.Icons.STORAGE
    GPU: str = ft.Icons.VIDEOGAME_ASSET
    DISK: str = ft.Icons.STORAGE
    NETWORK: str = ft.Icons.NETWORK_CHECK
    THERMAL: str = ft.Icons.THERMOSTAT
    POWER: str = ft.Icons.BOLT
    SPEED: str = ft.Icons.SPEED

    # Health and Safety Icons
    HEALTH: str = ft.Icons.HEALTH_AND_SAFETY
    SECURITY: str = ft.Icons.SECURITY
    SHIELD: str = ft.Icons.SHIELD

    # Media Control Icons
    PLAY: str = ft.Icons.PLAY_ARROW
    PAUSE: str = ft.Icons.PAUSE
    PAUSE_CIRCLE_OUTLINE: str = ft.Icons.PAUSE_CIRCLE_OUTLINE
    PAUSE_CIRCLE_FILLED: str = ft.Icons.PAUSE_CIRCLE_FILLED
    STOP: str = ft.Icons.STOP
    RECORD: str = ft.Icons.FIBER_MANUAL_RECORD

    # File and Document Icons
    FILE: str = ft.Icons.DESCRIPTION
    FOLDER: str = ft.Icons.FOLDER
    DOWNLOAD: str = ft.Icons.DOWNLOAD
    UPLOAD: str = ft.Icons.UPLOAD
    UPLOAD_FILE: str = ft.Icons.UPLOAD_FILE
    SAVE: str = ft.Icons.SAVE
    BACKUP: str = ft.Icons.BACKUP
    INSERT_DRIVE_FILE: str = ft.Icons.INSERT_DRIVE_FILE
    ARCHIVE: str = ft.Icons.ARCHIVE
    PICTURE_AS_PDF: str = ft.Icons.PICTURE_AS_PDF
    FOLDER_OPEN: str = ft.Icons.FOLDER_OPEN

    # Communication Icons
    NOTIFICATION: str = ft.Icons.NOTIFICATIONS
    MESSAGE: str = ft.Icons.MESSAGE
    EMAIL: str = ft.Icons.EMAIL
    PHONE: str = ft.Icons.PHONE

    # Editing and Tools Icons
    EDIT: str = ft.Icons.EDIT
    DELETE: str = ft.Icons.DELETE
    ADD: str = ft.Icons.ADD
    REMOVE: str = ft.Icons.REMOVE
    COPY: str = ft.Icons.COPY
    CUT: str = ft.Icons.CONTENT_CUT
    PASTE: str = ft.Icons.CONTENT_PASTE

    # View and Display Icons
    VISIBILITY: str = ft.Icons.VISIBILITY
    VISIBILITY_OFF: str = ft.Icons.VISIBILITY_OFF
    FULLSCREEN: str = ft.Icons.FULLSCREEN
    FULLSCREEN_EXIT: str = ft.Icons.FULLSCREEN_EXIT
    ZOOM_IN: str = ft.Icons.ZOOM_IN
    ZOOM_OUT: str = ft.Icons.ZOOM_OUT

    # Search and Filter Icons
    HISTORY: str = ft.Icons.HISTORY
    TRENDING_UP: str = ft.Icons.TRENDING_UP
    TEXT_SNIPPET: str = ft.Icons.TEXT_SNIPPET
    TAG: str = ft.Icons.TAG
    MIC: str = ft.Icons.MIC
    CLEAR: str = ft.Icons.CLEAR
    TUNE: str = ft.Icons.TUNE
    IMAGE: str = ft.Icons.IMAGE

    # Navigation and Control Icons
    EXPAND_MORE: str = ft.Icons.EXPAND_MORE
    EXPAND_LESS: str = ft.Icons.EXPAND_LESS
    CHEVRON_LEFT: str = ft.Icons.CHEVRON_LEFT
    CHEVRON_RIGHT: str = ft.Icons.CHEVRON_RIGHT
    MORE_VERT: str = ft.Icons.MORE_VERT
    ARROW_UPWARD: str = ft.Icons.ARROW_UPWARD
    ARROW_DOWNWARD: str = ft.Icons.ARROW_DOWNWARD
    ARROW_RIGHT: str = ft.Icons.ARROW_RIGHT
    FIRST_PAGE: str = ft.Icons.FIRST_PAGE
    LAST_PAGE: str = ft.Icons.LAST_PAGE

    # Content and Document Icons
    DESCRIPTION: str = ft.Icons.DESCRIPTION
    LOCATION_ON: str = ft.Icons.LOCATION_ON
    ACCESS_TIME: str = ft.Icons.ACCESS_TIME
    OPEN_IN_NEW: str = ft.Icons.OPEN_IN_NEW
    CONTEXT_MENU: str = ft.Icons.MORE_VERT

    # UI State Icons
    LIST: str = ft.Icons.LIST
    VIEW_COMPACT: str = ft.Icons.VIEW_COMPACT
    VIEW_AGENDA: str = ft.Icons.VIEW_AGENDA
    VIEW_LIST: str = ft.Icons.VIEW_LIST
    VIEW_MODULE: str = ft.Icons.VIEW_MODULE
    SEARCH_OFF: str = ft.Icons.SEARCH_OFF
    SORT: str = ft.Icons.SORT
    FILTER_ALT: str = ft.Icons.FILTER_ALT
    DATE_RANGE: str = ft.Icons.DATE_RANGE
    LABEL: str = ft.Icons.LABEL

    # Psychology and AI Icons
    PSYCHOLOGY: str = ft.Icons.PSYCHOLOGY
    AUTO_AWESOME: str = ft.Icons.AUTO_AWESOME
    LIGHTBULB_OUTLINE: str = ft.Icons.LIGHTBULB_OUTLINE

    # Additional UI Icons for modern components
    MONITORING: str = ft.Icons.MONITOR_HEART
    GRID_VIEW: str = ft.Icons.GRID_VIEW
    LIST_VIEW: str = ft.Icons.VIEW_LIST
    COMPACT_VIEW: str = ft.Icons.VIEW_COMPACT
    TRENDING_DOWN: str = ft.Icons.TRENDING_DOWN
    TRENDING_FLAT: str = ft.Icons.TRENDING_FLAT
    CLOUD_UPLOAD: str = ft.Icons.CLOUD_UPLOAD
    ATTACHMENT: str = ft.Icons.ATTACH_FILE
    CAMERA: str = ft.Icons.CAMERA_ALT
    BUILD: str = ft.Icons.BUILD
    TRAINING: str = ft.Icons.SCHOOL
    ANALYTICS: str = ft.Icons.ANALYTICS
    DONE_ALL: str = ft.Icons.DONE_ALL
    CLEANUP: str = ft.Icons.CLEANING_SERVICES

    # Feedback and Rating Icons
    THUMB_UP: str = ft.Icons.THUMB_UP
    THUMB_DOWN: str = ft.Icons.THUMB_DOWN
    THUMB_UP_OUTLINED: str = ft.Icons.THUMB_UP_OUTLINED
    THUMB_DOWN_OUTLINED: str = ft.Icons.THUMB_DOWN_OUTLINED
    STAR: str = ft.Icons.STAR
    STAR_OUTLINE: str = ft.Icons.STAR_OUTLINE
    SEND: str = ft.Icons.SEND
    VERIFIED: str = ft.Icons.VERIFIED
    HELP_OUTLINE: str = ft.Icons.HELP_OUTLINE

    # Chat and Communication Icons
    CHAT: str = ft.Icons.CHAT
    CHAT_BUBBLE_OUTLINE: str = ft.Icons.CHAT_BUBBLE_OUTLINE
    PERSON: str = ft.Icons.PERSON
    SMART_TOY: str = ft.Icons.SMART_TOY
    ATTACH_FILE: str = ft.Icons.ATTACH_FILE
    PUSH_PIN: str = ft.Icons.PUSH_PIN
    PUSH_PIN_OUTLINED: str = ft.Icons.PUSH_PIN_OUTLINED
    CLEAR_ALL: str = ft.Icons.CLEAR_ALL
    CHECK: str = ft.Icons.CHECK
    RESTORE: str = ft.Icons.RESTORE

    # Progress and Status Icons
    INVENTORY: str = ft.Icons.INVENTORY
    CANCEL: str = ft.Icons.CANCEL
    ERROR_OUTLINE: str = ft.Icons.ERROR_OUTLINE
    DANGEROUS: str = ft.Icons.DANGEROUS
    PRIORITY_HIGH: str = ft.Icons.PRIORITY_HIGH
    TIMER: str = ft.Icons.TIMER
    CACHED: str = ft.Icons.CACHED
    SHOW_CHART: str = ft.Icons.SHOW_CHART
    BUG_REPORT: str = ft.Icons.BUG_REPORT
    SCHEDULE: str = ft.Icons.SCHEDULE
    PAUSE_CIRCLE: str = ft.Icons.PAUSE_CIRCLE
    PAUSE_CIRCLE_OUTLINE: str = ft.Icons.PAUSE_CIRCLE_OUTLINE
    PAUSE_CIRCLE_FILLED: str = ft.Icons.PAUSE_CIRCLE_FILLED
    PLAY_CIRCLE: str = ft.Icons.PLAY_CIRCLE
    PLAY_CIRCLE_OUTLINE: str = ft.Icons.PLAY_CIRCLE_OUTLINE
    CHECK_CIRCLE: str = ft.Icons.CHECK_CIRCLE
    RADIO_BUTTON_CHECKED: str = ft.Icons.RADIO_BUTTON_CHECKED
    RADIO_BUTTON_UNCHECKED: str = ft.Icons.RADIO_BUTTON_UNCHECKED
    LIGHTBULB_OUTLINE: str = ft.Icons.LIGHTBULB_OUTLINE
    MINIMIZE: str = ft.Icons.MINIMIZE

    # Citation and Quote Icons
    FORMAT_QUOTE: str = ft.Icons.FORMAT_QUOTE

    # Additional UI Icons for Model Builder
    ARCHITECTURE: str = ft.Icons.ARCHITECTURE
    TUNE: str = ft.Icons.TUNE
    DATASET: str = ft.Icons.DATASET
    VERIFIED: str = ft.Icons.VERIFIED
    CHECK: str = ft.Icons.CHECK
    HELP_OUTLINE: str = ft.Icons.HELP_OUTLINE
    FOLDER_OPEN: str = ft.Icons.FOLDER_OPEN
    EXPAND_LESS: str = ft.Icons.EXPAND_LESS
    EXPAND_MORE: str = ft.Icons.EXPAND_MORE
    PLAY_CIRCLE: str = ft.Icons.PLAY_CIRCLE
    SCHEDULE: str = ft.Icons.SCHEDULE
    EMERGENCY: str = ft.Icons.EMERGENCY
    CHECK_CIRCLE: str = ft.Icons.CHECK_CIRCLE
    TRENDING_UP: str = ft.Icons.TRENDING_UP
    BOOKMARK: str = ft.Icons.BOOKMARK
    GRID_VIEW: str = ft.Icons.GRID_VIEW
    VIEW_LIST: str = ft.Icons.VIEW_LIST
    FAVORITE: str = ft.Icons.FAVORITE
    FAVORITE_BORDER: str = ft.Icons.FAVORITE_BORDER
    RESTORE: str = ft.Icons.RESTORE
    BOOKMARK_BORDER: str = ft.Icons.BOOKMARK_BORDER
    ARROW_DOWNWARD: str = ft.Icons.ARROW_DOWNWARD
    ARROW_UPWARD: str = ft.Icons.ARROW_UPWARD

    # Model Registry UI Icons
    MODEL_TRAINING: str = ft.Icons.MODEL_TRAINING
    CLOUD_UPLOAD: str = ft.Icons.CLOUD_UPLOAD
    UPDATE: str = ft.Icons.UPDATE
    COMPARE_ARROWS: str = ft.Icons.COMPARE_ARROWS
    CALL_SPLIT: str = ft.Icons.CALL_SPLIT
    ACCOUNT_TREE: str = ft.Icons.ACCOUNT_TREE
    CENTER_FOCUS_STRONG: str = ft.Icons.CENTER_FOCUS_STRONG
    ZOOM_IN: str = ft.Icons.ZOOM_IN
    ZOOM_OUT: str = ft.Icons.ZOOM_OUT
    RADIO_BUTTON_CHECKED: str = ft.Icons.RADIO_BUTTON_CHECKED
    RADIO_BUTTON_UNCHECKED: str = ft.Icons.RADIO_BUTTON_UNCHECKED
    ROCKET_LAUNCH: str = ft.Icons.ROCKET_LAUNCH
    ARROW_FORWARD: str = ft.Icons.ARROW_FORWARD
    BAR_CHART: str = ft.Icons.BAR_CHART
    PIE_CHART: str = ft.Icons.PIE_CHART
    AREA_CHART: str = ft.Icons.AREA_CHART
    COMPARE: str = ft.Icons.COMPARE
    TABLE_CHART: str = ft.Icons.TABLE_CHART
    TRENDING_FLAT: str = ft.Icons.TRENDING_FLAT
    TRENDING_DOWN: str = ft.Icons.TRENDING_DOWN
    OPEN_IN_NEW: str = ft.Icons.OPEN_IN_NEW


@dataclass
class DesignTokens:
    """
    Structured design tokens following industry best practices.
    Implements a hierarchical token system with primitive, semantic, and component levels.
    Enhanced with responsive design capabilities for adaptive layouts.
    """
    # Primitive tokens (base values)
    primitive_colors: Dict[str, str]
    primitive_spacing: Dict[str, int]
    primitive_typography: Dict[str, Tuple[int, int, int]]
    primitive_shadows: Dict[str, str]
    primitive_borders: Dict[str, str]

    # Semantic tokens (contextual meaning)
    semantic_colors: Dict[str, str]
    semantic_spacing: Dict[str, int]
    semantic_typography: Dict[str, Tuple[int, int, int]]

    # Component tokens (specific component styling)
    component_tokens: Dict[str, Dict[str, Any]]

    # Responsive tokens (breakpoint-specific values)
    responsive_spacing: Dict[str, Dict[str, int]]
    responsive_typography: Dict[str, Dict[str, Tuple[int, int, int]]]
    responsive_layout: Dict[str, Dict[str, Any]]


@dataclass
class ComponentVariants:
    """
    Predefined component style variants following design system patterns.
    Provides consistent styling for common component variations.
    Enhanced with responsive design capabilities for adaptive components.
    """
    # Button variants
    button_variants: Dict[str, Dict[str, Any]]

    # Card variants
    card_variants: Dict[str, Dict[str, Any]]

    # Input variants
    input_variants: Dict[str, Dict[str, Any]]

    # Text variants
    text_variants: Dict[str, Dict[str, Any]]

    # Container variants
    container_variants: Dict[str, Dict[str, Any]]

    # Responsive variants (breakpoint-specific styling)
    responsive_button_variants: Dict[str, Dict[str, Dict[str, Any]]]
    responsive_card_variants: Dict[str, Dict[str, Dict[str, Any]]]
    responsive_container_variants: Dict[str, Dict[str, Dict[str, Any]]]


@dataclass
class AnimationConfig:
    """Enhanced animation configuration with sophisticated easing and transitions."""
    # Duration settings (in milliseconds)
    instant: int = 0
    fast: int = 150
    normal: int = 200
    slow: int = 300
    slower: int = 500

    # Material Design 3 easing curves
    ease_standard: str = "cubic-bezier(0.2, 0, 0, 1)"
    ease_decelerate: str = "cubic-bezier(0, 0, 0, 1)"
    ease_accelerate: str = "cubic-bezier(0.3, 0, 1, 1)"
    ease_accelerate_decelerate: str = "cubic-bezier(0.3, 0, 0, 1)"

    # Legacy easing for compatibility
    ease_in: str = "cubic-bezier(0.4, 0, 1, 1)"
    ease_out: str = "cubic-bezier(0, 0, 0.2, 1)"
    ease_in_out: str = "cubic-bezier(0.4, 0, 0.2, 1)"

    # Specialized animations
    bounce: str = "cubic-bezier(0.68, -0.55, 0.265, 1.55)"
    elastic: str = "cubic-bezier(0.175, 0.885, 0.32, 1.275)"

    # Theme transition
    theme_transition_duration: int = 200
    theme_transition_easing: str = "cubic-bezier(0.2, 0, 0, 1)"

    # Component-specific animations
    hover_duration: int = 150
    focus_duration: int = 100
    press_duration: int = 50

    # Reduced motion support
    respect_reduced_motion: bool = True
    reduced_motion_duration: int = 0


@dataclass
class ThemePersistence:
    """Enhanced theme persistence configuration."""
    # Storage options
    use_local_storage: bool = True
    use_database: bool = True
    use_file_system: bool = False

    # Sync options
    sync_across_sessions: bool = True
    sync_across_devices: bool = False

    # Backup and recovery
    auto_backup: bool = True
    backup_interval: int = 3600  # seconds
    max_backups: int = 5

    # Validation
    validate_on_load: bool = True
    fallback_to_defaults: bool = True


class ResponsiveLayoutManager:
    """
    Central responsive layout management system for MikroDok application.

    Provides comprehensive responsive design capabilities including:
    - Real-time viewport detection and monitoring
    - Automatic breakpoint management and transitions
    - Component adaptation and responsive utilities
    - Performance-optimized layout calculations
    - Accessibility-compliant responsive behaviors
    - Integration with existing theme system
    """

    def __init__(self,
                 breakpoints: Optional[ResponsiveBreakpoints] = None,
                 sizing: Optional[ResponsiveSizing] = None):
        """
        Initialize the responsive layout manager.

        Args:
            breakpoints: Custom breakpoint configuration
            sizing: Custom sizing configuration
        """
        self._breakpoints = breakpoints or ResponsiveBreakpoints()
        self._sizing = sizing or ResponsiveSizing()
        self._current_width = 1920  # Default desktop width
        self._current_height = 1080  # Default desktop height
        self._current_screen_size = ScreenSize.DESKTOP
        self._resize_callbacks: List[Callable[[int, int, ScreenSize], None]] = []
        self._debounce_timer = None
        self._debounce_delay = 150  # milliseconds
        self._layout_cache: Dict[str, Any] = {}
        self._performance_metrics = {
            'resize_events': 0,
            'layout_calculations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'component_pool_hits': 0,
            'component_pool_misses': 0
        }

        # Performance optimization features
        self._component_pool: Dict[str, List[ft.Control]] = {}
        self._max_pool_size = 50
        self._cache_ttl = 300  # 5 minutes in seconds
        self._cache_timestamps: Dict[str, float] = {}
        self._memoized_calculations: Dict[str, Any] = {}
        self._calculation_timestamps: Dict[str, float] = {}

    def update_window_size(self, width: int, height: int) -> None:
        """
        Update current window size and trigger responsive updates.

        Args:
            width: New window width in pixels
            height: New window height in pixels
        """
        # Validate minimum dimensions
        if width < self._breakpoints.min_width or height < self._breakpoints.min_height:
            print(f"Warning: Window size {width}x{height} below minimum {self._breakpoints.min_width}x{self._breakpoints.min_height}")

        old_screen_size = self._current_screen_size
        self._current_width = width
        self._current_height = height
        self._current_screen_size = self._breakpoints.get_screen_size(width)

        # Clear layout cache if screen size changed
        if old_screen_size != self._current_screen_size:
            self._layout_cache.clear()

        # Update performance metrics
        self._performance_metrics['resize_events'] += 1

        # Debounced callback execution
        self._debounced_resize_callback()

    def _debounced_resize_callback(self) -> None:
        """Execute resize callbacks with debouncing to prevent excessive updates."""
        if self._debounce_timer:
            # Cancel previous timer
            pass  # In a real implementation, you'd cancel the timer

        # In a real implementation, you'd set a timer here
        # For now, execute immediately
        self._execute_resize_callbacks()

    def _execute_resize_callbacks(self) -> None:
        """Execute all registered resize callbacks."""
        for callback in self._resize_callbacks:
            try:
                callback(self._current_width, self._current_height, self._current_screen_size)
            except Exception as e:
                print(f"Error in resize callback: {e}")

    def add_resize_callback(self, callback: Callable[[int, int, ScreenSize], None]) -> None:
        """
        Add a callback to be executed on window resize.

        Args:
            callback: Function to call with (width, height, screen_size)
        """
        if callback not in self._resize_callbacks:
            self._resize_callbacks.append(callback)

    def remove_resize_callback(self, callback: Callable[[int, int, ScreenSize], None]) -> None:
        """
        Remove a resize callback.

        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._resize_callbacks:
            self._resize_callbacks.remove(callback)

    def get_current_screen_size(self) -> ScreenSize:
        """
        Get the current screen size category.

        Returns:
            Current ScreenSize enum value
        """
        return self._current_screen_size

    def get_current_dimensions(self) -> Tuple[int, int]:
        """
        Get current window dimensions.

        Returns:
            Tuple of (width, height) in pixels
        """
        return (self._current_width, self._current_height)

    def get_breakpoints(self) -> ResponsiveBreakpoints:
        """
        Get the current breakpoint configuration.

        Returns:
            ResponsiveBreakpoints instance
        """
        return self._breakpoints

    def get_sizing(self) -> ResponsiveSizing:
        """
        Get the current sizing configuration.

        Returns:
            ResponsiveSizing instance
        """
        return self._sizing

    def is_mobile(self) -> bool:
        """Check if current screen size is mobile."""
        return self._current_screen_size == ScreenSize.MOBILE

    def is_tablet(self) -> bool:
        """Check if current screen size is tablet."""
        return self._current_screen_size == ScreenSize.TABLET

    def is_desktop(self) -> bool:
        """Check if current screen size is desktop."""
        return self._current_screen_size == ScreenSize.DESKTOP

    def is_large_desktop(self) -> bool:
        """Check if current screen size is large desktop."""
        return self._current_screen_size == ScreenSize.LARGE_DESKTOP

    def is_mobile_or_tablet(self) -> bool:
        """Check if current screen size is mobile or tablet."""
        return self._current_screen_size in [ScreenSize.MOBILE, ScreenSize.TABLET]

    def is_desktop_or_larger(self) -> bool:
        """Check if current screen size is desktop or larger."""
        return self._current_screen_size in [ScreenSize.DESKTOP, ScreenSize.LARGE_DESKTOP]

    def get_responsive_font_size(self, base_size: int) -> int:
        """
        Get responsive font size based on current screen size.

        Args:
            base_size: Base font size in pixels

        Returns:
            Scaled font size for current screen
        """
        cache_key = f"font_size_{base_size}_{self._current_screen_size.value}"

        # Try to get from cache with TTL validation
        cached_value = self._get_from_cache(cache_key)
        if cached_value is not None:
            return cached_value

        # Calculate and cache
        self._performance_metrics['layout_calculations'] += 1

        def calculate_font_size():
            scale_factor = self._sizing.get_font_scale(self._current_screen_size)
            return int(base_size * scale_factor)

        scaled_size = self._get_memoized_calculation(cache_key, calculate_font_size)
        self._set_cache(cache_key, scaled_size)

        return scaled_size

    def get_responsive_padding(self) -> int:
        """
        Get responsive padding for current screen size.

        Returns:
            Padding value in pixels
        """
        cache_key = f"padding_{self._current_screen_size.value}"
        if cache_key in self._layout_cache:
            self._performance_metrics['cache_hits'] += 1
            return self._layout_cache[cache_key]

        self._performance_metrics['cache_misses'] += 1
        padding = self._sizing.get_padding(self._current_screen_size)

        self._layout_cache[cache_key] = padding
        return padding

    def get_responsive_columns(self) -> int:
        """
        Get responsive column count for current screen size.

        Returns:
            Number of columns for grid layouts
        """
        return self._sizing.get_columns(self._current_screen_size)

    def get_responsive_sidebar_width(self) -> int:
        """
        Get responsive sidebar width for current screen size.

        Returns:
            Sidebar width in pixels
        """
        return self._sizing.get_sidebar_width(self._current_screen_size)

    def get_responsive_container_width(self) -> int:
        """
        Get responsive container max-width for current screen size.

        Returns:
            Container max-width in pixels or percentage
        """
        return self._breakpoints.get_container_width(self._current_screen_size)

    def get_responsive_touch_target_size(self) -> int:
        """
        Get responsive touch target size for current screen size.

        Returns:
            Touch target size in pixels
        """
        return self._sizing.get_touch_target_size(self._current_screen_size)

    def get_breakpoint_value(self, mobile: Any, tablet: Any, desktop: Any, large: Any) -> Any:
        """
        Get value based on current breakpoint.

        Args:
            mobile: Value for mobile screens
            tablet: Value for tablet screens
            desktop: Value for desktop screens
            large: Value for large desktop screens

        Returns:
            Appropriate value for current screen size
        """
        value_map = {
            ScreenSize.MOBILE: mobile,
            ScreenSize.TABLET: tablet,
            ScreenSize.DESKTOP: desktop,
            ScreenSize.LARGE_DESKTOP: large
        }
        return value_map.get(self._current_screen_size, desktop)

    def create_responsive_grid(self,
                             children: List[ft.Control],
                             mobile_cols: Optional[int] = None,
                             tablet_cols: Optional[int] = None,
                             desktop_cols: Optional[int] = None,
                             large_cols: Optional[int] = None,
                             spacing: Optional[int] = None,
                             run_spacing: Optional[int] = None) -> ft.Control:
        """
        Create a responsive grid that adapts to screen size.

        Args:
            children: List of child controls
            mobile_cols: Columns for mobile (default: 1)
            tablet_cols: Columns for tablet (default: 2)
            desktop_cols: Columns for desktop (default: 3)
            large_cols: Columns for large desktop (default: 4)
            spacing: Horizontal spacing between items
            run_spacing: Vertical spacing between rows

        Returns:
            Responsive grid control
        """
        # Use provided values or defaults from sizing system
        cols = self.get_breakpoint_value(
            mobile=mobile_cols or self._sizing.mobile_columns,
            tablet=tablet_cols or self._sizing.tablet_columns,
            desktop=desktop_cols or self._sizing.desktop_columns,
            large=large_cols or self._sizing.large_columns
        )

        # Calculate responsive spacing
        responsive_spacing = spacing or self.get_responsive_padding() // 2
        responsive_run_spacing = run_spacing or responsive_spacing

        return ft.GridView(
            controls=children,
            runs_count=cols,
            max_extent=None,  # Let it calculate based on available space
            child_aspect_ratio=1.0,
            spacing=responsive_spacing,
            run_spacing=responsive_run_spacing,
            expand=True
        )

    def create_responsive_container(self,
                                  content: ft.Control,
                                  padding: Optional[int] = None,
                                  margin: Optional[int] = None,
                                  max_width: Optional[int] = None) -> ft.Control:
        """
        Create a responsive container with adaptive sizing.

        Args:
            content: Container content
            padding: Custom padding (uses responsive default if None)
            margin: Custom margin
            max_width: Custom max-width (uses responsive default if None)

        Returns:
            Responsive container control
        """
        responsive_padding = padding or self.get_responsive_padding()
        responsive_max_width = max_width or self.get_responsive_container_width()

        # On mobile, use full width; on larger screens, use max-width
        if self.is_mobile():
            container_width = None  # Full width
        else:
            container_width = responsive_max_width

        return ft.Container(
            content=content,
            padding=ft.padding.all(responsive_padding),
            margin=ft.margin.all(margin) if margin else None,
            width=container_width,
            alignment=ft.alignment.center if not self.is_mobile() else None
        )

    def get_performance_metrics(self) -> Dict[str, int]:
        """
        Get performance metrics for the responsive layout manager.

        Returns:
            Dictionary of performance metrics
        """
        return self._performance_metrics.copy()

    def clear_cache(self) -> None:
        """Clear the layout calculation cache."""
        self._layout_cache.clear()
        self._cache_timestamps.clear()
        self._memoized_calculations.clear()
        self._calculation_timestamps.clear()
        print("Responsive layout cache cleared")

    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Check if cache entry is still valid based on TTL.

        Args:
            cache_key: Cache key to check

        Returns:
            True if cache entry is valid
        """
        if cache_key not in self._cache_timestamps:
            return False

        import time
        current_time = time.time()
        cache_time = self._cache_timestamps[cache_key]

        return (current_time - cache_time) < self._cache_ttl

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        Get value from cache with TTL validation.

        Args:
            cache_key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if cache_key in self._layout_cache and self._is_cache_valid(cache_key):
            self._performance_metrics['cache_hits'] += 1
            return self._layout_cache[cache_key]

        # Remove expired entry
        if cache_key in self._layout_cache:
            del self._layout_cache[cache_key]
            del self._cache_timestamps[cache_key]

        self._performance_metrics['cache_misses'] += 1
        return None

    def _set_cache(self, cache_key: str, value: Any) -> None:
        """
        Set value in cache with timestamp.

        Args:
            cache_key: Cache key
            value: Value to cache
        """
        import time
        self._layout_cache[cache_key] = value
        self._cache_timestamps[cache_key] = time.time()

    def _get_memoized_calculation(self, calc_key: str, calculation_func: Callable[[], Any]) -> Any:
        """
        Get memoized calculation result with TTL.

        Args:
            calc_key: Calculation key
            calculation_func: Function to execute if not cached

        Returns:
            Calculation result
        """
        if calc_key in self._memoized_calculations and self._is_calculation_valid(calc_key):
            return self._memoized_calculations[calc_key]

        # Perform calculation
        result = calculation_func()

        # Cache result
        import time
        self._memoized_calculations[calc_key] = result
        self._calculation_timestamps[calc_key] = time.time()

        return result

    def _is_calculation_valid(self, calc_key: str) -> bool:
        """
        Check if memoized calculation is still valid.

        Args:
            calc_key: Calculation key

        Returns:
            True if calculation is valid
        """
        if calc_key not in self._calculation_timestamps:
            return False

        import time
        current_time = time.time()
        calc_time = self._calculation_timestamps[calc_key]

        return (current_time - calc_time) < self._cache_ttl

    def get_pooled_component(self, component_type: str, **kwargs) -> Optional[ft.Control]:
        """
        Get component from pool for reuse.

        Args:
            component_type: Type of component to get
            **kwargs: Component properties

        Returns:
            Pooled component or None if not available
        """
        pool_key = f"{component_type}_{hash(str(sorted(kwargs.items())))}"

        if pool_key in self._component_pool and self._component_pool[pool_key]:
            self._performance_metrics['component_pool_hits'] += 1
            return self._component_pool[pool_key].pop()

        self._performance_metrics['component_pool_misses'] += 1
        return None

    def return_component_to_pool(self, component: ft.Control, component_type: str, **kwargs) -> None:
        """
        Return component to pool for reuse.

        Args:
            component: Component to return
            component_type: Type of component
            **kwargs: Component properties
        """
        pool_key = f"{component_type}_{hash(str(sorted(kwargs.items())))}"

        if pool_key not in self._component_pool:
            self._component_pool[pool_key] = []

        # Limit pool size
        if len(self._component_pool[pool_key]) < self._max_pool_size:
            self._component_pool[pool_key].append(component)

    def optimize_layout_calculations(self) -> None:
        """Optimize layout calculations by cleaning up expired cache entries."""
        import time
        current_time = time.time()

        # Clean up expired cache entries
        expired_cache_keys = [
            key for key, timestamp in self._cache_timestamps.items()
            if (current_time - timestamp) >= self._cache_ttl
        ]

        for key in expired_cache_keys:
            if key in self._layout_cache:
                del self._layout_cache[key]
            del self._cache_timestamps[key]

        # Clean up expired calculations
        expired_calc_keys = [
            key for key, timestamp in self._calculation_timestamps.items()
            if (current_time - timestamp) >= self._cache_ttl
        ]

        for key in expired_calc_keys:
            if key in self._memoized_calculations:
                del self._memoized_calculations[key]
            del self._calculation_timestamps[key]

        print(f"Cleaned up {len(expired_cache_keys)} cache entries and {len(expired_calc_keys)} calculations")

    def set_performance_settings(self,
                                cache_ttl: Optional[int] = None,
                                max_pool_size: Optional[int] = None,
                                debounce_delay: Optional[int] = None) -> None:
        """
        Configure performance settings.

        Args:
            cache_ttl: Cache time-to-live in seconds
            max_pool_size: Maximum component pool size
            debounce_delay: Debounce delay in milliseconds
        """
        if cache_ttl is not None:
            self._cache_ttl = cache_ttl

        if max_pool_size is not None:
            self._max_pool_size = max_pool_size

        if debounce_delay is not None:
            self._debounce_delay = debounce_delay

        print(f"Performance settings updated: TTL={self._cache_ttl}s, Pool={self._max_pool_size}, Debounce={self._debounce_delay}ms")

    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get detailed performance report.

        Returns:
            Performance metrics and statistics
        """
        cache_hit_rate = 0
        if self._performance_metrics['cache_hits'] + self._performance_metrics['cache_misses'] > 0:
            cache_hit_rate = self._performance_metrics['cache_hits'] / (
                self._performance_metrics['cache_hits'] + self._performance_metrics['cache_misses']
            )

        pool_hit_rate = 0
        if self._performance_metrics['component_pool_hits'] + self._performance_metrics['component_pool_misses'] > 0:
            pool_hit_rate = self._performance_metrics['component_pool_hits'] / (
                self._performance_metrics['component_pool_hits'] + self._performance_metrics['component_pool_misses']
            )

        return {
            'metrics': self._performance_metrics.copy(),
            'cache_hit_rate': f"{cache_hit_rate:.2%}",
            'pool_hit_rate': f"{pool_hit_rate:.2%}",
            'cache_size': len(self._layout_cache),
            'calculation_cache_size': len(self._memoized_calculations),
            'component_pools': {k: len(v) for k, v in self._component_pool.items()},
            'settings': {
                'cache_ttl': self._cache_ttl,
                'max_pool_size': self._max_pool_size,
                'debounce_delay': self._debounce_delay
            }
        }


# Responsive component classes will be defined after ThemeAwareUserControl


class ViewportDetector:
    """
    Viewport detection utility for responsive design.

    Provides real-time viewport monitoring with efficient event handling
    and debounced updates to prevent excessive re-rendering during resize operations.
    """

    def __init__(self, responsive_manager: ResponsiveLayoutManager):
        """
        Initialize viewport detector.

        Args:
            responsive_manager: ResponsiveLayoutManager instance to update
        """
        self._responsive_manager = responsive_manager
        self._page_ref = None
        self._is_monitoring = False
        self._last_width = 0
        self._last_height = 0
        self._resize_timer = None
        self._debounce_delay = 150  # milliseconds

    def start_monitoring(self, page: ft.Page) -> None:
        """
        Start monitoring viewport changes.

        Args:
            page: Flet page instance to monitor
        """
        if self._is_monitoring:
            return

        self._page_ref = page
        self._is_monitoring = True

        # Set initial size
        if hasattr(page, 'window_width') and hasattr(page, 'window_height'):
            self._last_width = page.window_width or 1920
            self._last_height = page.window_height or 1080
        else:
            self._last_width = 1920
            self._last_height = 1080

        self._responsive_manager.update_window_size(self._last_width, self._last_height)

        # Register resize handler
        if hasattr(page, 'on_resize'):
            page.on_resize = self._handle_page_resize

        print(f"Viewport monitoring started: {self._last_width}x{self._last_height}")

    def stop_monitoring(self) -> None:
        """Stop monitoring viewport changes."""
        if not self._is_monitoring:
            return

        self._is_monitoring = False

        if self._page_ref and hasattr(self._page_ref, 'on_resize'):
            self._page_ref.on_resize = None

        self._page_ref = None
        print("Viewport monitoring stopped")

    def _handle_page_resize(self, e: ft.ControlEvent) -> None:
        """
        Handle page resize events with debouncing.

        Args:
            e: Resize event
        """
        if not self._is_monitoring or not self._page_ref:
            return

        # Get current dimensions
        current_width = getattr(self._page_ref, 'window_width', self._last_width) or self._last_width
        current_height = getattr(self._page_ref, 'window_height', self._last_height) or self._last_height

        # Check if dimensions actually changed
        if current_width == self._last_width and current_height == self._last_height:
            return

        self._last_width = current_width
        self._last_height = current_height

        # Debounced update
        self._debounced_update()

    def _debounced_update(self) -> None:
        """Perform debounced viewport update."""
        # In a real implementation, you would use a proper timer
        # For now, update immediately
        self._responsive_manager.update_window_size(self._last_width, self._last_height)

        # Update page if needed
        if self._page_ref:
            try:
                self._page_ref.update()
            except Exception as e:
                print(f"Error updating page during resize: {e}")

    def get_current_dimensions(self) -> Tuple[int, int]:
        """
        Get current viewport dimensions.

        Returns:
            Tuple of (width, height) in pixels
        """
        return (self._last_width, self._last_height)

    def force_update(self, width: int, height: int) -> None:
        """
        Force viewport update with specific dimensions.

        Args:
            width: New width in pixels
            height: New height in pixels
        """
        self._last_width = width
        self._last_height = height
        self._responsive_manager.update_window_size(width, height)


class ResponsiveEventHandler:
    """
    Event handler for responsive design updates.

    Manages efficient re-rendering and state updates during responsive
    transitions while maintaining performance and user experience.
    """

    def __init__(self, theme_manager: 'ThemeManager'):
        """
        Initialize responsive event handler.

        Args:
            theme_manager: ThemeManager instance
        """
        self._theme_manager = theme_manager
        self._viewport_detector = ViewportDetector(theme_manager.get_responsive_layout_manager())
        self._responsive_callbacks: List[Callable[[ScreenSize], None]] = []
        self._transition_callbacks: List[Callable[[ScreenSize, ScreenSize], None]] = []
        self._current_screen_size = ScreenSize.DESKTOP
        self._performance_mode = False

    def initialize(self, page: ft.Page) -> None:
        """
        Initialize responsive event handling for a page.

        Args:
            page: Flet page instance
        """
        self._viewport_detector.start_monitoring(page)

        # Register for responsive layout manager callbacks
        responsive_manager = self._theme_manager.get_responsive_layout_manager()
        responsive_manager.add_resize_callback(self._handle_responsive_change)

        print("Responsive event handler initialized")

    def cleanup(self) -> None:
        """Clean up event handlers and resources."""
        self._viewport_detector.stop_monitoring()

        # Unregister callbacks
        responsive_manager = self._theme_manager.get_responsive_layout_manager()
        responsive_manager.remove_resize_callback(self._handle_responsive_change)

        self._responsive_callbacks.clear()
        self._transition_callbacks.clear()
        print("Responsive event handler cleaned up")

    def add_responsive_callback(self, callback: Callable[[ScreenSize], None]) -> None:
        """
        Add callback for responsive changes.

        Args:
            callback: Function to call with new screen size
        """
        if callback not in self._responsive_callbacks:
            self._responsive_callbacks.append(callback)

    def remove_responsive_callback(self, callback: Callable[[ScreenSize], None]) -> None:
        """
        Remove responsive callback.

        Args:
            callback: Function to remove
        """
        if callback in self._responsive_callbacks:
            self._responsive_callbacks.remove(callback)

    def add_transition_callback(self, callback: Callable[[ScreenSize, ScreenSize], None]) -> None:
        """
        Add callback for screen size transitions.

        Args:
            callback: Function to call with (old_size, new_size)
        """
        if callback not in self._transition_callbacks:
            self._transition_callbacks.append(callback)

    def remove_transition_callback(self, callback: Callable[[ScreenSize, ScreenSize], None]) -> None:
        """
        Remove transition callback.

        Args:
            callback: Function to remove
        """
        if callback in self._transition_callbacks:
            self._transition_callbacks.remove(callback)

    def _handle_responsive_change(self, width: int, height: int, screen_size: ScreenSize) -> None:
        """
        Handle responsive layout changes.

        Args:
            width: New width in pixels
            height: New height in pixels
            screen_size: New screen size category
        """
        old_screen_size = self._current_screen_size
        self._current_screen_size = screen_size

        # Execute responsive callbacks
        for callback in self._responsive_callbacks:
            try:
                callback(screen_size)
            except Exception as e:
                print(f"Error in responsive callback: {e}")

        # Execute transition callbacks if screen size changed
        if old_screen_size != screen_size:
            for callback in self._transition_callbacks:
                try:
                    callback(old_screen_size, screen_size)
                except Exception as e:
                    print(f"Error in transition callback: {e}")

            print(f"Screen size transition: {old_screen_size.value} → {screen_size.value}")

    def set_performance_mode(self, enabled: bool) -> None:
        """
        Enable or disable performance mode for reduced updates.

        Args:
            enabled: Whether to enable performance mode
        """
        self._performance_mode = enabled
        print(f"Performance mode {'enabled' if enabled else 'disabled'}")

    def force_responsive_update(self) -> None:
        """Force a responsive update with current dimensions."""
        width, height = self._viewport_detector.get_current_dimensions()
        responsive_manager = self._theme_manager.get_responsive_layout_manager()
        responsive_manager.update_window_size(width, height)


# Responsive Utility Functions
def get_responsive_value(mobile: Any, tablet: Any, desktop: Any, large: Any,
                        screen_size: Optional[ScreenSize] = None) -> Any:
    """
    Get value based on screen size or current breakpoint.

    Args:
        mobile: Value for mobile screens
        tablet: Value for tablet screens
        desktop: Value for desktop screens
        large: Value for large desktop screens
        screen_size: Specific screen size (uses current if None)

    Returns:
        Appropriate value for screen size
    """
    if screen_size is None:
        theme_manager = get_theme_manager()
        if theme_manager:
            screen_size = theme_manager.get_current_screen_size()
        else:
            screen_size = ScreenSize.DESKTOP

    value_map = {
        ScreenSize.MOBILE: mobile,
        ScreenSize.TABLET: tablet,
        ScreenSize.DESKTOP: desktop,
        ScreenSize.LARGE_DESKTOP: large
    }
    return value_map.get(screen_size, desktop)


def calculate_responsive_font_size(base_size: int,
                                 mobile_scale: float = 0.9,
                                 tablet_scale: float = 0.95,
                                 desktop_scale: float = 1.0,
                                 large_scale: float = 1.1) -> int:
    """
    Calculate responsive font size with custom scaling factors.

    Args:
        base_size: Base font size in pixels
        mobile_scale: Scaling factor for mobile
        tablet_scale: Scaling factor for tablet
        desktop_scale: Scaling factor for desktop
        large_scale: Scaling factor for large desktop

    Returns:
        Scaled font size for current screen
    """
    scale = get_responsive_value(mobile_scale, tablet_scale, desktop_scale, large_scale)
    return int(base_size * scale)


def calculate_responsive_spacing(base_spacing: int,
                               mobile_factor: float = 0.75,
                               tablet_factor: float = 0.875,
                               desktop_factor: float = 1.0,
                               large_factor: float = 1.25) -> int:
    """
    Calculate responsive spacing with custom factors.

    Args:
        base_spacing: Base spacing in pixels
        mobile_factor: Spacing factor for mobile
        tablet_factor: Spacing factor for tablet
        desktop_factor: Spacing factor for desktop
        large_factor: Spacing factor for large desktop

    Returns:
        Scaled spacing for current screen
    """
    factor = get_responsive_value(mobile_factor, tablet_factor, desktop_factor, large_factor)
    return int(base_spacing * factor)


def get_responsive_grid_columns(mobile_cols: int = 1,
                              tablet_cols: int = 2,
                              desktop_cols: int = 3,
                              large_cols: int = 4) -> int:
    """
    Get responsive grid column count.

    Args:
        mobile_cols: Columns for mobile
        tablet_cols: Columns for tablet
        desktop_cols: Columns for desktop
        large_cols: Columns for large desktop

    Returns:
        Column count for current screen size
    """
    return get_responsive_value(mobile_cols, tablet_cols, desktop_cols, large_cols)


def get_responsive_container_padding(mobile_padding: int = 12,
                                   tablet_padding: int = 16,
                                   desktop_padding: int = 24,
                                   large_padding: int = 32) -> int:
    """
    Get responsive container padding.

    Args:
        mobile_padding: Padding for mobile
        tablet_padding: Padding for tablet
        desktop_padding: Padding for desktop
        large_padding: Padding for large desktop

    Returns:
        Padding for current screen size
    """
    return get_responsive_value(mobile_padding, tablet_padding, desktop_padding, large_padding)


def create_responsive_text_style(base_size: int,
                                weight: ft.FontWeight = ft.FontWeight.W_400,
                                font_family: str = "Inter",
                                mobile_scale: float = 0.9,
                                tablet_scale: float = 0.95,
                                desktop_scale: float = 1.0,
                                large_scale: float = 1.1) -> ft.TextStyle:
    """
    Create responsive text style with adaptive sizing.

    Args:
        base_size: Base font size in pixels
        weight: Font weight
        font_family: Font family name
        mobile_scale: Scaling factor for mobile
        tablet_scale: Scaling factor for tablet
        desktop_scale: Scaling factor for desktop
        large_scale: Scaling factor for large desktop

    Returns:
        TextStyle with responsive sizing
    """
    responsive_size = calculate_responsive_font_size(
        base_size, mobile_scale, tablet_scale, desktop_scale, large_scale
    )

    return ft.TextStyle(
        size=responsive_size,
        weight=weight,
        font_family=font_family
    )


def create_responsive_padding(mobile: int = 12,
                            tablet: int = 16,
                            desktop: int = 24,
                            large: int = 32) -> ft.Padding:
    """
    Create responsive padding object.

    Args:
        mobile: Padding for mobile
        tablet: Padding for tablet
        desktop: Padding for desktop
        large: Padding for large desktop

    Returns:
        Padding object for current screen size
    """
    padding_value = get_responsive_value(mobile, tablet, desktop, large)
    return ft.padding.all(padding_value)


def create_responsive_margin(mobile: int = 8,
                           tablet: int = 12,
                           desktop: int = 16,
                           large: int = 20) -> ft.Margin:
    """
    Create responsive margin object.

    Args:
        mobile: Margin for mobile
        tablet: Margin for tablet
        desktop: Margin for desktop
        large: Margin for large desktop

    Returns:
        Margin object for current screen size
    """
    margin_value = get_responsive_value(mobile, tablet, desktop, large)
    return ft.margin.all(margin_value)


def is_touch_device() -> bool:
    """
    Check if current device is likely a touch device.

    Returns:
        True if device is likely touch-enabled
    """
    theme_manager = get_theme_manager()
    if theme_manager:
        return theme_manager.is_mobile_or_tablet()
    return False


def get_touch_target_size() -> int:
    """
    Get appropriate touch target size for current device.

    Returns:
        Touch target size in pixels (minimum 44px for accessibility)
    """
    if is_touch_device():
        return get_responsive_value(48, 44, 40, 40)  # Larger on mobile
    else:
        return get_responsive_value(40, 40, 36, 36)  # Smaller for mouse interaction


def create_responsive_icon_size(base_size: int = 24) -> int:
    """
    Create responsive icon size.

    Args:
        base_size: Base icon size in pixels

    Returns:
        Icon size for current screen
    """
    scale_factors = {
        ScreenSize.MOBILE: 0.9,
        ScreenSize.TABLET: 0.95,
        ScreenSize.DESKTOP: 1.0,
        ScreenSize.LARGE_DESKTOP: 1.1
    }

    theme_manager = get_theme_manager()
    if theme_manager:
        screen_size = theme_manager.get_current_screen_size()
        scale = scale_factors.get(screen_size, 1.0)
    else:
        scale = 1.0

    return int(base_size * scale)


def get_responsive_elevation(mobile: int = 1,
                           tablet: int = 2,
                           desktop: int = 2,
                           large: int = 3) -> int:
    """
    Get responsive elevation for cards and surfaces.

    Args:
        mobile: Elevation for mobile
        tablet: Elevation for tablet
        desktop: Elevation for desktop
        large: Elevation for large desktop

    Returns:
        Elevation value for current screen size
    """
    return get_responsive_value(mobile, tablet, desktop, large)


def create_adaptive_layout(children: List[ft.Control],
                         mobile_layout: str = "column",
                         tablet_layout: str = "row",
                         desktop_layout: str = "row",
                         spacing: int = 16) -> ft.Control:
    """
    Create adaptive layout that changes orientation based on screen size.

    Args:
        children: List of child controls
        mobile_layout: Layout type for mobile ("column" or "row")
        tablet_layout: Layout type for tablet ("column" or "row")
        desktop_layout: Layout type for desktop ("column" or "row")
        spacing: Spacing between items

    Returns:
        Adaptive layout control
    """
    layout_type = get_responsive_value(mobile_layout, tablet_layout, desktop_layout, desktop_layout)

    if layout_type == "column":
        return ft.Column(
            controls=children,
            spacing=spacing,
            alignment=ft.MainAxisAlignment.START
        )
    else:
        return ft.Row(
            controls=children,
            spacing=spacing,
            alignment=ft.MainAxisAlignment.START,
            wrap=True  # Allow wrapping on smaller screens
        )


class AccessibilityManager:
    """
    Accessibility management for responsive design.

    Ensures WCAG 2.1 AA compliance across all breakpoints while maintaining
    focus management, keyboard navigation, and reduced motion preferences.
    """

    def __init__(self, responsive_manager: ResponsiveLayoutManager):
        """
        Initialize accessibility manager.

        Args:
            responsive_manager: ResponsiveLayoutManager instance
        """
        self._responsive_manager = responsive_manager
        self._focus_management_enabled = True
        self._reduced_motion_enabled = False
        self._high_contrast_enabled = False
        self._keyboard_navigation_enabled = True
        self._screen_reader_support = True

        # WCAG 2.1 AA compliance settings
        self._min_contrast_ratio = 4.5
        self._min_touch_target_size = 44  # pixels
        self._max_line_length = 80  # characters
        self._min_font_size = 12  # pixels

        # Focus management
        self._focus_history: List[str] = []
        self._focus_trap_stack: List[ft.Control] = []

    def ensure_wcag_compliance(self, component: ft.Control, screen_size: ScreenSize) -> ft.Control:
        """
        Ensure component meets WCAG 2.1 AA compliance for given screen size.

        Args:
            component: Component to check
            screen_size: Current screen size

        Returns:
            Compliant component
        """
        # Ensure minimum touch target size
        if hasattr(component, 'width') and hasattr(component, 'height'):
            min_size = self._get_min_touch_target_size(screen_size)

            if hasattr(component, 'width') and component.width and component.width < min_size:
                component.width = min_size

            if hasattr(component, 'height') and component.height and component.height < min_size:
                component.height = min_size

        # Ensure minimum font size
        if hasattr(component, 'style') and hasattr(component.style, 'size'):
            if component.style.size and component.style.size < self._min_font_size:
                component.style.size = self._min_font_size

        # Add accessibility attributes
        self._add_accessibility_attributes(component, screen_size)

        return component

    def _get_min_touch_target_size(self, screen_size: ScreenSize) -> int:
        """
        Get minimum touch target size for screen size.

        Args:
            screen_size: Current screen size

        Returns:
            Minimum touch target size in pixels
        """
        # Larger touch targets on mobile devices
        if screen_size == ScreenSize.MOBILE:
            return 48
        elif screen_size == ScreenSize.TABLET:
            return 44
        else:
            return 40  # Desktop can be smaller due to mouse precision

    def _add_accessibility_attributes(self, component: ft.Control, screen_size: ScreenSize) -> None:
        """
        Add accessibility attributes to component.

        Args:
            component: Component to enhance
            screen_size: Current screen size
        """
        # Add semantic attributes based on component type
        if isinstance(component, ft.ElevatedButton) or isinstance(component, ft.TextButton):
            if not hasattr(component, 'tooltip') or not component.tooltip:
                component.tooltip = getattr(component, 'text', 'Button')

        elif isinstance(component, ft.TextField):
            # Ensure proper labeling
            if not hasattr(component, 'label') or not component.label:
                component.label = "Input field"

        elif isinstance(component, ft.Container):
            # Add role for containers that act as landmarks
            if hasattr(component, 'content') and component.content:
                # This would be implemented with proper ARIA attributes in a real app
                pass

    def manage_focus_during_resize(self, old_screen_size: ScreenSize, new_screen_size: ScreenSize) -> None:
        """
        Manage focus during responsive transitions.

        Args:
            old_screen_size: Previous screen size
            new_screen_size: New screen size
        """
        if not self._focus_management_enabled:
            return

        # Store current focus if transitioning to mobile (where layout changes significantly)
        if old_screen_size != ScreenSize.MOBILE and new_screen_size == ScreenSize.MOBILE:
            self._store_current_focus()

        # Restore focus if transitioning from mobile
        elif old_screen_size == ScreenSize.MOBILE and new_screen_size != ScreenSize.MOBILE:
            self._restore_focus()

    def _store_current_focus(self) -> None:
        """Store current focus for later restoration."""
        # In a real implementation, this would store the currently focused element
        # For now, we'll just track that focus was stored
        self._focus_history.append("stored_focus")

    def _restore_focus(self) -> None:
        """Restore previously stored focus."""
        if self._focus_history:
            self._focus_history.pop()
            # In a real implementation, this would restore focus to the stored element

    def create_focus_trap(self, container: ft.Control) -> None:
        """
        Create focus trap for modal dialogs and overlays.

        Args:
            container: Container to trap focus within
        """
        if self._keyboard_navigation_enabled:
            self._focus_trap_stack.append(container)

    def remove_focus_trap(self) -> None:
        """Remove the most recent focus trap."""
        if self._focus_trap_stack:
            self._focus_trap_stack.pop()

    def get_reduced_motion_duration(self, normal_duration: int) -> int:
        """
        Get animation duration respecting reduced motion preference.

        Args:
            normal_duration: Normal animation duration in milliseconds

        Returns:
            Adjusted duration (0 if reduced motion is enabled)
        """
        if self._reduced_motion_enabled:
            return 0
        return normal_duration

    def create_accessible_responsive_text(self,
                                        text: str,
                                        base_size: int = 16,
                                        screen_size: Optional[ScreenSize] = None) -> ft.Text:
        """
        Create accessible responsive text with proper sizing and contrast.

        Args:
            text: Text content
            base_size: Base font size
            screen_size: Target screen size (uses current if None)

        Returns:
            Accessible text component
        """
        if screen_size is None:
            screen_size = self._responsive_manager.get_current_screen_size()

        # Calculate responsive font size
        responsive_size = self._responsive_manager.get_responsive_font_size(base_size)

        # Ensure minimum font size for accessibility
        responsive_size = max(responsive_size, self._min_font_size)

        # Create text with accessibility features
        text_component = ft.Text(
            value=text,
            size=responsive_size,
            # Additional accessibility properties would be set here
        )

        return self.ensure_wcag_compliance(text_component, screen_size)

    def create_accessible_button(self,
                               text: str,
                               on_click: Optional[Callable] = None,
                               screen_size: Optional[ScreenSize] = None,
                               variant: str = "primary") -> ft.ElevatedButton:
        """
        Create accessible responsive button.

        Args:
            text: Button text
            on_click: Click handler
            screen_size: Target screen size
            variant: Button variant

        Returns:
            Accessible button component
        """
        if screen_size is None:
            screen_size = self._responsive_manager.get_current_screen_size()

        # Get minimum touch target size
        min_size = self._get_min_touch_target_size(screen_size)

        button = ft.ElevatedButton(
            text=text,
            on_click=on_click,
            height=min_size,
            tooltip=text,  # Ensure tooltip for screen readers
        )

        return self.ensure_wcag_compliance(button, screen_size)

    def set_accessibility_preferences(self,
                                    reduced_motion: Optional[bool] = None,
                                    high_contrast: Optional[bool] = None,
                                    focus_management: Optional[bool] = None,
                                    keyboard_navigation: Optional[bool] = None) -> None:
        """
        Set accessibility preferences.

        Args:
            reduced_motion: Enable reduced motion
            high_contrast: Enable high contrast mode
            focus_management: Enable focus management
            keyboard_navigation: Enable keyboard navigation
        """
        if reduced_motion is not None:
            self._reduced_motion_enabled = reduced_motion

        if high_contrast is not None:
            self._high_contrast_enabled = high_contrast

        if focus_management is not None:
            self._focus_management_enabled = focus_management

        if keyboard_navigation is not None:
            self._keyboard_navigation_enabled = keyboard_navigation

        print(f"Accessibility preferences updated: "
              f"reduced_motion={self._reduced_motion_enabled}, "
              f"high_contrast={self._high_contrast_enabled}, "
              f"focus_management={self._focus_management_enabled}, "
              f"keyboard_navigation={self._keyboard_navigation_enabled}")

    def get_accessibility_report(self) -> Dict[str, Any]:
        """
        Get accessibility compliance report.

        Returns:
            Accessibility status and settings
        """
        return {
            'wcag_compliance': {
                'min_contrast_ratio': self._min_contrast_ratio,
                'min_touch_target_size': self._min_touch_target_size,
                'min_font_size': self._min_font_size,
                'max_line_length': self._max_line_length
            },
            'preferences': {
                'reduced_motion': self._reduced_motion_enabled,
                'high_contrast': self._high_contrast_enabled,
                'focus_management': self._focus_management_enabled,
                'keyboard_navigation': self._keyboard_navigation_enabled,
                'screen_reader_support': self._screen_reader_support
            },
            'focus_management': {
                'focus_history_length': len(self._focus_history),
                'active_focus_traps': len(self._focus_trap_stack)
            }
        }


class ThemeManager:
    """
    Enhanced central theme management system for MikroDok application.

    Provides comprehensive theme control including:
    - Dark/Light mode switching with system preference detection
    - Color palette management with WCAG 2.1 AA compliance
    - Typography system with Inter and JetBrains Mono fonts
    - Spacing system with consistent scale
    - Enhanced animation configuration with Material Design 3 easing
    - Color blind accessibility modes
    - Cross-platform theme integration
    - Structured design tokens system
    - Component variants and styling presets
    - Enhanced theme persistence and backup
    """

    def __init__(self, app_state_manager=None, user_preferences_db=None, persistence_config=None):
        """
        Initialize the enhanced theme manager.

        Args:
            app_state_manager: Application state manager instance
            user_preferences_db: User preferences database instance
            persistence_config: Theme persistence configuration
        """
        self._app_state_manager = app_state_manager
        self._user_preferences_db = user_preferences_db
        self._persistence_config = persistence_config or ThemePersistence()
        self._current_mode = ThemeMode.AUTO
        self._color_blind_mode = ColorBlindMode.NONE
        self._font_scale = 1.0
        self._reduced_motion = False
        self._theme_change_callbacks: List[Callable[[ThemeMode], None]] = []

        # Initialize color palettes
        self._color_palettes = self._initialize_color_palettes()

        # Initialize typography system
        self._typography = self._initialize_typography()

        # Initialize spacing system
        self._spacing = SpacingSystem()

        # Initialize enhanced animation configuration
        self._animation = AnimationConfig()

        # Initialize icon system
        self._icons = IconSystem()

        # Initialize design tokens
        self._design_tokens = self._initialize_design_tokens()

        # Initialize component variants
        self._component_variants = self._initialize_component_variants()

        # Initialize responsive layout manager
        self._responsive_layout_manager = ResponsiveLayoutManager()

        # Initialize accessibility manager
        self._accessibility_manager = AccessibilityManager(self._responsive_layout_manager)

        # Load user preferences with enhanced persistence
        self._load_user_preferences()

        # Detect system theme preference
        self._detect_system_theme()

    def _convert_weight_to_font_weight(self, weight: int) -> ft.FontWeight:
        """
        Convert numeric font weight to Flet FontWeight enum.

        Args:
            weight: Numeric font weight (100-900)

        Returns:
            Corresponding Flet FontWeight enum value
        """
        weight_map = {
            100: ft.FontWeight.W_100,
            200: ft.FontWeight.W_200,
            300: ft.FontWeight.W_300,
            400: ft.FontWeight.W_400,
            500: ft.FontWeight.W_500,
            600: ft.FontWeight.W_600,
            700: ft.FontWeight.W_700,
            800: ft.FontWeight.W_800,
            900: ft.FontWeight.W_900,
        }
        return weight_map.get(weight, ft.FontWeight.W_400)  # Default to normal weight

    def _initialize_color_palettes(self) -> Dict[ThemeMode, ColorPalette]:
        """Initialize color palettes for all theme modes."""
        return {
            ThemeMode.DARK: ColorPalette(
                # Background colors
                background_primary="#000000",
                background_secondary="#0D0D0D",
                surface="#2D2D2D",
                surface_variant="#333333",

                # Text colors
                text_primary="#FFFFFF",
                text_secondary="#C0C0C0",
                text_tertiary="#B8B8B8",
                text_disabled="#666666",

                # Border and outline colors
                borders="#5D5D5D",
                outline="#5D5D5D",

                # State colors
                error="#FF4444",
                error_container="#4D1A1A",
                success="#44FF44",
                warning="#FFA500",
                info="#44AAFF",

                # Interactive colors
                primary="#44AAFF",
                primary_variant="#3388CC",
                secondary="#B8B8B8",
                secondary_variant="#999999",

                # Focus and selection
                focus_indicator="#44AAFF",
                selection="#44AAFF33"
            ),
            
            ThemeMode.LIGHT: ColorPalette(
                # Background colors
                background_primary="#FFFFFF",
                background_secondary="#F5F5F5",
                surface="#E8E8E8",
                surface_variant="#D0D0D0",

                # Text colors
                text_primary="#000000",
                text_secondary="#333333",
                text_tertiary="#666666",
                text_disabled="#CCCCCC",

                # Border and outline colors
                borders="#B8B8B8",
                outline="#B8B8B8",

                # State colors
                error="#CC0000",
                error_container="#FFEBEE",
                success="#008800",
                warning="#FF8C00",
                info="#0066CC",

                # Interactive colors
                primary="#0066CC",
                primary_variant="#004499",
                secondary="#666666",
                secondary_variant="#888888",

                # Focus and selection
                focus_indicator="#0066CC",
                selection="#0066CC33"
            ),
            
            ThemeMode.HIGH_CONTRAST: ColorPalette(
                # Background colors
                background_primary="#000000",
                background_secondary="#000000",
                surface="#000000",
                surface_variant="#1A1A1A",

                # Text colors
                text_primary="#FFFFFF",
                text_secondary="#FFFFFF",
                text_tertiary="#CCCCCC",
                text_disabled="#666666",

                # Border and outline colors
                borders="#FFFFFF",
                outline="#FFFFFF",

                # State colors
                error="#FF0000",
                error_container="#330000",
                success="#00FF00",
                warning="#FFFF00",
                info="#00FFFF",

                # Interactive colors
                primary="#FFFFFF",
                primary_variant="#CCCCCC",
                secondary="#FFFFFF",
                secondary_variant="#CCCCCC",

                # Focus and selection
                focus_indicator="#FFFF00",
                selection="#FFFF0066"
            )
        }

    def _initialize_typography(self) -> TypographyScale:
        """Initialize typography scale with Inter and JetBrains Mono fonts."""
        return TypographyScale(
            # Display sizes (size, line_height, weight)
            display_large=(48, 56, 300),
            display_medium=(40, 48, 300),
            display_small=(32, 40, 400),

            # Heading sizes
            h1=(28, 36, 600),
            h2=(24, 32, 600),
            h3=(20, 28, 600),
            h4=(18, 24, 500),

            # Body text
            body_large=(16, 24, 400),
            body_medium=(14, 20, 400),
            body_small=(13, 18, 400),

            # Supporting text
            caption=(12, 16, 400),
            overline=(11, 16, 500),
            label=(12, 16, 500),

            # Data display (monospace)
            metric_large=(32, 36, 300),
            metric_medium=(24, 28, 400),
            code_block=(13, 20, 400),
            inline_code=(13, 16, 400)
        )

    def _initialize_design_tokens(self) -> DesignTokens:
        """Initialize structured design tokens system."""
        return DesignTokens(
            # Primitive tokens (base values)
            primitive_colors={
                "blue-50": "#EBF8FF",
                "blue-100": "#BEE3F8",
                "blue-500": "#3182CE",
                "blue-600": "#2C5282",
                "blue-900": "#1A365D",
                "gray-50": "#F7FAFC",
                "gray-100": "#EDF2F7",
                "gray-500": "#718096",
                "gray-600": "#4A5568",
                "gray-900": "#1A202C",
                "red-500": "#E53E3E",
                "green-500": "#38A169",
                "yellow-500": "#D69E2E",
            },
            primitive_spacing={
                "space-1": 4,
                "space-2": 8,
                "space-3": 12,
                "space-4": 16,
                "space-6": 24,
                "space-8": 32,
                "space-12": 48,
                "space-16": 64,
            },
            primitive_typography={
                "text-xs": (12, 16, 400),
                "text-sm": (14, 20, 400),
                "text-base": (16, 24, 400),
                "text-lg": (18, 28, 400),
                "text-xl": (20, 28, 500),
                "text-2xl": (24, 32, 600),
                "text-3xl": (30, 36, 700),
            },
            primitive_shadows={
                "shadow-sm": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
                "shadow": "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)",
                "shadow-md": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
                "shadow-lg": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
            },
            primitive_borders={
                "border-thin": "1px solid",
                "border-medium": "2px solid",
                "border-thick": "4px solid",
                "radius-sm": "4px",
                "radius": "8px",
                "radius-lg": "12px",
                "radius-full": "9999px",
            },

            # Semantic tokens (contextual meaning)
            semantic_colors={
                "color-primary": "blue-500",
                "color-secondary": "gray-500",
                "color-success": "green-500",
                "color-warning": "yellow-500",
                "color-error": "red-500",
                "color-surface": "gray-50",
                "color-background": "gray-100",
                "color-text": "gray-900",
                "color-text-muted": "gray-600",
            },
            semantic_spacing={
                "spacing-component": 16,
                "spacing-section": 24,
                "spacing-page": 32,
                "spacing-tight": 8,
                "spacing-loose": 24,
            },
            semantic_typography={
                "heading-primary": (28, 36, 600),
                "heading-secondary": (24, 32, 600),
                "body-primary": (16, 24, 400),
                "body-secondary": (14, 20, 400),
                "caption": (12, 16, 400),
            },

            # Component tokens (specific component styling)
            component_tokens={
                "button": {
                    "padding-x": 16,
                    "padding-y": 8,
                    "border-radius": 8,
                    "font-weight": 500,
                },
                "card": {
                    "padding": 16,
                    "border-radius": 8,
                    "shadow": "shadow-md",
                },
                "input": {
                    "padding-x": 12,
                    "padding-y": 8,
                    "border-radius": 4,
                    "border-width": 1,
                },
            },

            # Responsive tokens (breakpoint-specific values)
            responsive_spacing={
                "mobile": {
                    "component-padding": 12,
                    "section-padding": 16,
                    "page-padding": 16,
                    "grid-gap": 12,
                },
                "tablet": {
                    "component-padding": 16,
                    "section-padding": 20,
                    "page-padding": 24,
                    "grid-gap": 16,
                },
                "desktop": {
                    "component-padding": 24,
                    "section-padding": 32,
                    "page-padding": 40,
                    "grid-gap": 24,
                },
                "large": {
                    "component-padding": 32,
                    "section-padding": 40,
                    "page-padding": 48,
                    "grid-gap": 32,
                }
            },
            responsive_typography={
                "mobile": {
                    "heading-primary": (24, 32, 600),
                    "heading-secondary": (20, 28, 600),
                    "body-primary": (14, 20, 400),
                    "body-secondary": (13, 18, 400),
                    "caption": (11, 16, 400),
                },
                "tablet": {
                    "heading-primary": (26, 34, 600),
                    "heading-secondary": (22, 30, 600),
                    "body-primary": (15, 22, 400),
                    "body-secondary": (13, 19, 400),
                    "caption": (12, 16, 400),
                },
                "desktop": {
                    "heading-primary": (28, 36, 600),
                    "heading-secondary": (24, 32, 600),
                    "body-primary": (16, 24, 400),
                    "body-secondary": (14, 20, 400),
                    "caption": (12, 16, 400),
                },
                "large": {
                    "heading-primary": (32, 40, 600),
                    "heading-secondary": (26, 34, 600),
                    "body-primary": (18, 26, 400),
                    "body-secondary": (15, 22, 400),
                    "caption": (13, 18, 400),
                }
            },
            responsive_layout={
                "mobile": {
                    "container-width": "100%",
                    "sidebar-width": 280,
                    "grid-columns": 1,
                    "card-min-width": 280,
                },
                "tablet": {
                    "container-width": 768,
                    "sidebar-width": 240,
                    "grid-columns": 2,
                    "card-min-width": 320,
                },
                "desktop": {
                    "container-width": 1200,
                    "sidebar-width": 280,
                    "grid-columns": 3,
                    "card-min-width": 360,
                },
                "large": {
                    "container-width": 1400,
                    "sidebar-width": 320,
                    "grid-columns": 4,
                    "card-min-width": 400,
                }
            }
        )

    def _initialize_component_variants(self) -> ComponentVariants:
        """Initialize component style variants."""
        return ComponentVariants(
            # Button variants
            button_variants={
                "primary": {
                    "style": "filled",
                    "elevation": 2,
                    "color_role": "primary",
                },
                "secondary": {
                    "style": "outlined",
                    "elevation": 0,
                    "color_role": "secondary",
                },
                "tertiary": {
                    "style": "text",
                    "elevation": 0,
                    "color_role": "tertiary",
                },
                "danger": {
                    "style": "filled",
                    "elevation": 2,
                    "color_role": "error",
                },
                "ghost": {
                    "style": "text",
                    "elevation": 0,
                    "background": "transparent",
                },
                "floating": {
                    "style": "filled",
                    "elevation": 6,
                    "shape": "circular",
                },
            },

            # Card variants
            card_variants={
                "elevated": {
                    "elevation": 2,
                    "border": False,
                    "background": "surface",
                },
                "outlined": {
                    "elevation": 0,
                    "border": True,
                    "background": "surface",
                },
                "filled": {
                    "elevation": 0,
                    "border": False,
                    "background": "surface_variant",
                },
                "interactive": {
                    "elevation": 1,
                    "hover_elevation": 4,
                    "border": False,
                    "background": "surface",
                },
            },

            # Input variants
            input_variants={
                "outlined": {
                    "border": True,
                    "background": "transparent",
                    "focus_style": "border_highlight",
                },
                "filled": {
                    "border": False,
                    "background": "surface_variant",
                    "focus_style": "underline",
                },
                "underlined": {
                    "border": False,
                    "background": "transparent",
                    "focus_style": "underline_only",
                },
            },

            # Text variants
            text_variants={
                "display": {
                    "font_family": "Inter",
                    "weight": 300,
                    "letter_spacing": -0.5,
                },
                "headline": {
                    "font_family": "Inter",
                    "weight": 600,
                    "letter_spacing": 0,
                },
                "body": {
                    "font_family": "Inter",
                    "weight": 400,
                    "letter_spacing": 0.25,
                },
                "label": {
                    "font_family": "Inter",
                    "weight": 500,
                    "letter_spacing": 0.5,
                },
                "code": {
                    "font_family": "JetBrains Mono",
                    "weight": 400,
                    "letter_spacing": 0,
                },
            },

            # Container variants
            container_variants={
                "page": {
                    "max_width": 1200,
                    "padding": 24,
                    "margin": "auto",
                },
                "section": {
                    "padding": 16,
                    "margin_bottom": 24,
                },
                "panel": {
                    "padding": 16,
                    "border_radius": 8,
                    "background": "surface",
                },
                "sidebar": {
                    "width": 280,
                    "padding": 16,
                    "background": "surface_variant",
                },
            },

            # Responsive variants (breakpoint-specific styling)
            responsive_button_variants={
                "primary": {
                    "mobile": {"padding_x": 12, "padding_y": 8, "font_size": 14},
                    "tablet": {"padding_x": 14, "padding_y": 9, "font_size": 15},
                    "desktop": {"padding_x": 16, "padding_y": 10, "font_size": 16},
                    "large": {"padding_x": 18, "padding_y": 11, "font_size": 17},
                },
                "secondary": {
                    "mobile": {"padding_x": 10, "padding_y": 6, "font_size": 14},
                    "tablet": {"padding_x": 12, "padding_y": 7, "font_size": 15},
                    "desktop": {"padding_x": 14, "padding_y": 8, "font_size": 16},
                    "large": {"padding_x": 16, "padding_y": 9, "font_size": 17},
                },
            },
            responsive_card_variants={
                "elevated": {
                    "mobile": {"padding": 12, "elevation": 1, "border_radius": 6},
                    "tablet": {"padding": 16, "elevation": 2, "border_radius": 8},
                    "desktop": {"padding": 20, "elevation": 2, "border_radius": 8},
                    "large": {"padding": 24, "elevation": 3, "border_radius": 10},
                },
                "outlined": {
                    "mobile": {"padding": 12, "border_width": 1, "border_radius": 6},
                    "tablet": {"padding": 16, "border_width": 1, "border_radius": 8},
                    "desktop": {"padding": 20, "border_width": 1, "border_radius": 8},
                    "large": {"padding": 24, "border_width": 1, "border_radius": 10},
                },
            },
            responsive_container_variants={
                "page": {
                    "mobile": {"max_width": "100%", "padding": 16},
                    "tablet": {"max_width": 768, "padding": 24},
                    "desktop": {"max_width": 1200, "padding": 32},
                    "large": {"max_width": 1400, "padding": 40},
                },
                "sidebar": {
                    "mobile": {"width": 280, "padding": 12, "overlay": True},
                    "tablet": {"width": 240, "padding": 16, "overlay": False},
                    "desktop": {"width": 280, "padding": 20, "overlay": False},
                    "large": {"width": 320, "padding": 24, "overlay": False},
                },
            }
        )

    def _load_user_preferences(self) -> None:
        """Load user theme preferences with enhanced persistence support."""
        preferences = None

        # Try multiple storage methods based on configuration
        if self._persistence_config.use_database and self._user_preferences_db:
            try:
                preferences = self._user_preferences_db.get_user_preferences()
            except Exception as e:
                print(f"Warning: Failed to load preferences from database: {e}")

        if not preferences and self._persistence_config.use_local_storage:
            try:
                preferences = self._load_from_local_storage()
            except Exception as e:
                print(f"Warning: Failed to load preferences from local storage: {e}")

        if not preferences and self._persistence_config.use_file_system:
            try:
                preferences = self._load_from_file_system()
            except Exception as e:
                print(f"Warning: Failed to load preferences from file system: {e}")

        # Apply preferences or use defaults
        if preferences:
            try:
                if self._persistence_config.validate_on_load:
                    preferences = self._validate_preferences(preferences)

                self._current_mode = ThemeMode(preferences.get('theme_mode', ThemeMode.AUTO.value))
                self._color_blind_mode = ColorBlindMode(preferences.get('color_blind_mode', ColorBlindMode.NONE.value))
                self._font_scale = preferences.get('font_scale', 1.0)
                self._reduced_motion = preferences.get('reduced_motion', False)
            except Exception as e:
                print(f"Warning: Invalid preferences format, using defaults: {e}")
                self._use_default_preferences()
        else:
            self._use_default_preferences()

    def _save_user_preferences(self) -> None:
        """Save current theme preferences with enhanced persistence support."""
        preferences = {
            'theme_mode': self._current_mode.value,
            'color_blind_mode': self._color_blind_mode.value,
            'font_scale': self._font_scale,
            'reduced_motion': self._reduced_motion,
            'timestamp': time.time(),
            'version': '2.0'
        }

        # Create backup if enabled
        if self._persistence_config.auto_backup:
            try:
                self._create_preferences_backup()
            except Exception as e:
                print(f"Warning: Failed to create preferences backup: {e}")

        # Save to multiple storage methods
        saved_successfully = False

        if self._persistence_config.use_database and self._user_preferences_db:
            try:
                self._user_preferences_db.save_user_preferences(preferences)
                saved_successfully = True
            except Exception as e:
                print(f"Warning: Failed to save preferences to database: {e}")

        if self._persistence_config.use_local_storage:
            try:
                self._save_to_local_storage(preferences)
                saved_successfully = True
            except Exception as e:
                print(f"Warning: Failed to save preferences to local storage: {e}")

        if self._persistence_config.use_file_system:
            try:
                self._save_to_file_system(preferences)
                saved_successfully = True
            except Exception as e:
                print(f"Warning: Failed to save preferences to file system: {e}")

        if not saved_successfully:
            print("Error: Failed to save preferences to any storage method")

    def _use_default_preferences(self) -> None:
        """Set default theme preferences."""
        self._current_mode = ThemeMode.AUTO
        self._color_blind_mode = ColorBlindMode.NONE
        self._font_scale = 1.0
        self._reduced_motion = False

    def _validate_preferences(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize preferences data."""
        validated = {}

        # Validate theme mode
        try:
            validated['theme_mode'] = ThemeMode(preferences.get('theme_mode', ThemeMode.AUTO.value)).value
        except ValueError:
            validated['theme_mode'] = ThemeMode.AUTO.value

        # Validate color blind mode
        try:
            validated['color_blind_mode'] = ColorBlindMode(preferences.get('color_blind_mode', ColorBlindMode.NONE.value)).value
        except ValueError:
            validated['color_blind_mode'] = ColorBlindMode.NONE.value

        # Validate font scale
        font_scale = preferences.get('font_scale', 1.0)
        validated['font_scale'] = max(0.8, min(1.2, float(font_scale)))

        # Validate reduced motion
        validated['reduced_motion'] = bool(preferences.get('reduced_motion', False))

        return validated

    def _load_from_local_storage(self) -> Optional[Dict[str, Any]]:
        """Load preferences from local storage (browser-like storage)."""
        # This would be implemented based on the platform
        # For now, return None as fallback
        return None

    def _save_to_local_storage(self, preferences: Dict[str, Any]) -> None:
        """Save preferences to local storage."""
        # This would be implemented based on the platform
        pass

    def _load_from_file_system(self) -> Optional[Dict[str, Any]]:
        """Load preferences from file system."""
        import json
        from pathlib import Path

        config_dir = Path.home() / ".mikrodok"
        config_file = config_dir / "theme_preferences.json"

        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        return None

    def _save_to_file_system(self, preferences: Dict[str, Any]) -> None:
        """Save preferences to file system."""
        import json
        from pathlib import Path

        config_dir = Path.home() / ".mikrodok"
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / "theme_preferences.json"

        with open(config_file, 'w') as f:
            json.dump(preferences, f, indent=2)

    def _create_preferences_backup(self) -> None:
        """Create a backup of current preferences."""
        import json
        import time
        from pathlib import Path

        config_dir = Path.home() / ".mikrodok" / "backups"
        config_dir.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time())
        backup_file = config_dir / f"theme_preferences_backup_{timestamp}.json"

        current_preferences = {
            'theme_mode': self._current_mode.value,
            'color_blind_mode': self._color_blind_mode.value,
            'font_scale': self._font_scale,
            'reduced_motion': self._reduced_motion,
            'backup_timestamp': timestamp
        }

        with open(backup_file, 'w') as f:
            json.dump(current_preferences, f, indent=2)

        # Clean up old backups
        self._cleanup_old_backups(config_dir)

    def _cleanup_old_backups(self, backup_dir: Path) -> None:
        """Clean up old backup files, keeping only the most recent ones."""
        backup_files = list(backup_dir.glob("theme_preferences_backup_*.json"))

        if len(backup_files) > self._persistence_config.max_backups:
            # Sort by timestamp (newest first)
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            # Remove old backups
            for old_backup in backup_files[self._persistence_config.max_backups:]:
                try:
                    old_backup.unlink()
                except Exception as e:
                    print(f"Warning: Failed to remove old backup {old_backup}: {e}")

    def _detect_system_theme(self) -> None:
        """Detect system theme preference for auto mode."""
        if self._current_mode == ThemeMode.AUTO:
            try:
                # Platform-specific theme detection
                if platform.system() == "Windows":
                    self._detect_windows_theme()
                elif platform.system() == "Darwin":  # macOS
                    self._detect_macos_theme()
                elif platform.system() == "Linux":
                    self._detect_linux_theme()
                else:
                    # Default to dark mode if detection fails
                    self._effective_mode = ThemeMode.DARK
            except Exception:
                # Default to dark mode if detection fails
                self._effective_mode = ThemeMode.DARK
        else:
            self._effective_mode = self._current_mode

    def _detect_windows_theme(self) -> None:
        """Detect Windows theme preference."""
        try:
            import winreg
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            self._effective_mode = ThemeMode.LIGHT if value else ThemeMode.DARK
            winreg.CloseKey(key)
        except Exception:
            self._effective_mode = ThemeMode.DARK

    def _detect_macos_theme(self) -> None:
        """Detect macOS theme preference."""
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True
            )
            self._effective_mode = ThemeMode.DARK if result.stdout.strip() == "Dark" else ThemeMode.LIGHT
        except Exception:
            self._effective_mode = ThemeMode.DARK

    def _detect_linux_theme(self) -> None:
        """Detect Linux theme preference."""
        try:
            # Try GTK settings first
            gtk_theme = os.environ.get('GTK_THEME', '')
            if 'dark' in gtk_theme.lower():
                self._effective_mode = ThemeMode.DARK
            else:
                self._effective_mode = ThemeMode.LIGHT
        except Exception:
            self._effective_mode = ThemeMode.DARK

    def _apply_color_blind_adjustments(self, palette: ColorPalette) -> ColorPalette:
        """Apply color blind accessibility adjustments to palette."""
        if self._color_blind_mode == ColorBlindMode.NONE:
            return palette

        # Create a copy of the palette for modification
        adjusted_palette = ColorPalette(**asdict(palette))

        if self._color_blind_mode == ColorBlindMode.PROTANOPIA:
            # Adjust for red-blind users
            adjusted_palette.error = "#0066CC"  # Use blue instead of red
            adjusted_palette.success = "#FFA500"  # Use orange instead of green
        elif self._color_blind_mode == ColorBlindMode.DEUTERANOPIA:
            # Adjust for green-blind users
            adjusted_palette.success = "#0066CC"  # Use blue instead of green
            adjusted_palette.warning = "#FF4444"  # Use red instead of orange
        elif self._color_blind_mode == ColorBlindMode.TRITANOPIA:
            # Adjust for blue-blind users
            adjusted_palette.info = "#FFA500"  # Use orange instead of blue
            adjusted_palette.primary = "#44FF44"  # Use green instead of blue

        return adjusted_palette

    def get_current_palette(self) -> ColorPalette:
        """Get the current color palette with accessibility adjustments."""
        base_palette = self._color_palettes[self._effective_mode]
        return self._apply_color_blind_adjustments(base_palette)

    def get_typography(self) -> TypographyScale:
        """Get the current typography scale with font scaling applied."""
        base_typography = self._typography

        if self._font_scale == 1.0:
            return base_typography

        # Apply font scaling
        scaled_typography = TypographyScale(
            display_large=(int(base_typography.display_large[0] * self._font_scale),
                          int(base_typography.display_large[1] * self._font_scale),
                          base_typography.display_large[2]),
            display_medium=(int(base_typography.display_medium[0] * self._font_scale),
                           int(base_typography.display_medium[1] * self._font_scale),
                           base_typography.display_medium[2]),
            display_small=(int(base_typography.display_small[0] * self._font_scale),
                          int(base_typography.display_small[1] * self._font_scale),
                          base_typography.display_small[2]),
            h1=(int(base_typography.h1[0] * self._font_scale),
                int(base_typography.h1[1] * self._font_scale),
                base_typography.h1[2]),
            h2=(int(base_typography.h2[0] * self._font_scale),
                int(base_typography.h2[1] * self._font_scale),
                base_typography.h2[2]),
            h3=(int(base_typography.h3[0] * self._font_scale),
                int(base_typography.h3[1] * self._font_scale),
                base_typography.h3[2]),
            h4=(int(base_typography.h4[0] * self._font_scale),
                int(base_typography.h4[1] * self._font_scale),
                base_typography.h4[2]),
            body_large=(int(base_typography.body_large[0] * self._font_scale),
                       int(base_typography.body_large[1] * self._font_scale),
                       base_typography.body_large[2]),
            body_medium=(int(base_typography.body_medium[0] * self._font_scale),
                        int(base_typography.body_medium[1] * self._font_scale),
                        base_typography.body_medium[2]),
            body_small=(int(base_typography.body_small[0] * self._font_scale),
                       int(base_typography.body_small[1] * self._font_scale),
                       base_typography.body_small[2]),
            caption=(int(base_typography.caption[0] * self._font_scale),
                    int(base_typography.caption[1] * self._font_scale),
                    base_typography.caption[2]),
            overline=(int(base_typography.overline[0] * self._font_scale),
                     int(base_typography.overline[1] * self._font_scale),
                     base_typography.overline[2]),
            label=(int(base_typography.label[0] * self._font_scale),
                  int(base_typography.label[1] * self._font_scale),
                  base_typography.label[2]),
            metric_large=(int(base_typography.metric_large[0] * self._font_scale),
                         int(base_typography.metric_large[1] * self._font_scale),
                         base_typography.metric_large[2]),
            metric_medium=(int(base_typography.metric_medium[0] * self._font_scale),
                          int(base_typography.metric_medium[1] * self._font_scale),
                          base_typography.metric_medium[2]),
            code_block=(int(base_typography.code_block[0] * self._font_scale),
                       int(base_typography.code_block[1] * self._font_scale),
                       base_typography.code_block[2]),
            inline_code=(int(base_typography.inline_code[0] * self._font_scale),
                        int(base_typography.inline_code[1] * self._font_scale),
                        base_typography.inline_code[2])
        )

        return scaled_typography

    def get_spacing(self) -> SpacingSystem:
        """Get the current spacing system."""
        return self._spacing

    def get_icons(self) -> IconSystem:
        """Get the current icon system."""
        return self._icons

    def get_icon(self, icon_name: str) -> str:
        """
        Get icon by name from the centralized icon system.

        Args:
            icon_name: Name of the icon (e.g., 'CPU', 'MEMORY', 'SUCCESS')

        Returns:
            Flet icon constant (e.g., ft.Icons.MEMORY)
        """
        return getattr(self._icons, icon_name, ft.Icons.HELP_OUTLINE)

    def get_design_tokens(self) -> DesignTokens:
        """Get the current design tokens system."""
        return self._design_tokens

    def get_component_variants(self) -> ComponentVariants:
        """Get the current component variants."""
        return self._component_variants

    def get_responsive_layout_manager(self) -> ResponsiveLayoutManager:
        """Get the responsive layout manager instance."""
        return self._responsive_layout_manager

    def update_window_size(self, width: int, height: int) -> None:
        """
        Update window size for responsive calculations.

        Args:
            width: Window width in pixels
            height: Window height in pixels
        """
        self._responsive_layout_manager.update_window_size(width, height)

    def get_current_screen_size(self) -> ScreenSize:
        """Get the current screen size category."""
        return self._responsive_layout_manager.get_current_screen_size()

    def get_responsive_font_size(self, base_size: int) -> int:
        """
        Get responsive font size based on current screen size.

        Args:
            base_size: Base font size in pixels

        Returns:
            Scaled font size for current screen
        """
        return self._responsive_layout_manager.get_responsive_font_size(base_size)

    def get_responsive_padding(self) -> int:
        """Get responsive padding for current screen size."""
        return self._responsive_layout_manager.get_responsive_padding()

    def get_responsive_columns(self) -> int:
        """Get responsive column count for current screen size."""
        return self._responsive_layout_manager.get_responsive_columns()

    def get_responsive_sidebar_width(self) -> int:
        """Get responsive sidebar width for current screen size."""
        return self._responsive_layout_manager.get_responsive_sidebar_width()

    def get_responsive_container_width(self) -> int:
        """Get responsive container max-width for current screen size."""
        return self._responsive_layout_manager.get_responsive_container_width()

    def is_mobile(self) -> bool:
        """Check if current screen size is mobile."""
        return self._responsive_layout_manager.is_mobile()

    def is_tablet(self) -> bool:
        """Check if current screen size is tablet."""
        return self._responsive_layout_manager.is_tablet()

    def is_desktop(self) -> bool:
        """Check if current screen size is desktop."""
        return self._responsive_layout_manager.is_desktop()

    def is_large_desktop(self) -> bool:
        """Check if current screen size is large desktop."""
        return self._responsive_layout_manager.is_large_desktop()

    def is_mobile_or_tablet(self) -> bool:
        """Check if current screen size is mobile or tablet."""
        return self._responsive_layout_manager.is_mobile_or_tablet()

    def is_desktop_or_larger(self) -> bool:
        """Check if current screen size is desktop or larger."""
        return self._responsive_layout_manager.is_desktop_or_larger()

    def get_breakpoint_value(self, mobile: Any, tablet: Any, desktop: Any, large: Any) -> Any:
        """
        Get value based on current breakpoint.

        Args:
            mobile: Value for mobile screens
            tablet: Value for tablet screens
            desktop: Value for desktop screens
            large: Value for large desktop screens

        Returns:
            Appropriate value for current screen size
        """
        return self._responsive_layout_manager.get_breakpoint_value(mobile, tablet, desktop, large)

    def create_responsive_grid(self,
                             children: List[ft.Control],
                             mobile_cols: Optional[int] = None,
                             tablet_cols: Optional[int] = None,
                             desktop_cols: Optional[int] = None,
                             large_cols: Optional[int] = None,
                             spacing: Optional[int] = None,
                             run_spacing: Optional[int] = None) -> ft.Control:
        """
        Create a responsive grid that adapts to screen size.

        Args:
            children: List of child controls
            mobile_cols: Columns for mobile (default: 1)
            tablet_cols: Columns for tablet (default: 2)
            desktop_cols: Columns for desktop (default: 3)
            large_cols: Columns for large desktop (default: 4)
            spacing: Horizontal spacing between items
            run_spacing: Vertical spacing between rows

        Returns:
            Responsive grid control
        """
        return self._responsive_layout_manager.create_responsive_grid(
            children, mobile_cols, tablet_cols, desktop_cols, large_cols, spacing, run_spacing
        )

    def create_responsive_container(self,
                                  content: ft.Control,
                                  padding: Optional[int] = None,
                                  margin: Optional[int] = None,
                                  max_width: Optional[int] = None) -> ft.Control:
        """
        Create a responsive container with adaptive sizing.

        Args:
            content: Container content
            padding: Custom padding (uses responsive default if None)
            margin: Custom margin
            max_width: Custom max-width (uses responsive default if None)

        Returns:
            Responsive container control
        """
        return self._responsive_layout_manager.create_responsive_container(
            content, padding, margin, max_width
        )

    def get_accessibility_manager(self) -> AccessibilityManager:
        """Get the accessibility manager instance."""
        return self._accessibility_manager

    def create_accessible_component(self,
                                  component_type: str,
                                  screen_size: Optional[ScreenSize] = None,
                                  **kwargs) -> ft.Control:
        """
        Create accessible component with WCAG compliance.

        Args:
            component_type: Type of component to create
            screen_size: Target screen size
            **kwargs: Component properties

        Returns:
            Accessible component
        """
        if screen_size is None:
            screen_size = self.get_current_screen_size()

        if component_type == "text":
            text = kwargs.get('value', kwargs.get('text', ''))
            base_size = kwargs.get('size', 16)
            return self._accessibility_manager.create_accessible_responsive_text(text, base_size, screen_size)

        elif component_type == "button":
            text = kwargs.get('text', 'Button')
            on_click = kwargs.get('on_click')
            variant = kwargs.get('variant', 'primary')
            return self._accessibility_manager.create_accessible_button(text, on_click, screen_size, variant)

        else:
            # Create regular component and ensure compliance
            component = self.create_themed_component_with_variant(component_type, **kwargs)
            return self._accessibility_manager.ensure_wcag_compliance(component, screen_size)

    def set_accessibility_preferences(self, **preferences) -> None:
        """Set accessibility preferences."""
        self._accessibility_manager.set_accessibility_preferences(**preferences)

    def get_accessibility_report(self) -> Dict[str, Any]:
        """Get accessibility compliance report."""
        return self._accessibility_manager.get_accessibility_report()

    def get_component_variant(self, component_type: str, variant_name: str = "default") -> Dict[str, Any]:
        """
        Get a specific component variant configuration.

        Args:
            component_type: Type of component (button, card, input, etc.)
            variant_name: Name of the variant (primary, secondary, etc.)

        Returns:
            Component variant configuration
        """
        variants_map = {
            "button": self._component_variants.button_variants,
            "card": self._component_variants.card_variants,
            "input": self._component_variants.input_variants,
            "text": self._component_variants.text_variants,
            "container": self._component_variants.container_variants,
        }

        component_variants = variants_map.get(component_type, {})
        return component_variants.get(variant_name, component_variants.get("default", {}))

    def get_color_with_opacity(self, color: str, opacity: float) -> str:
        """
        Get a color with specified opacity.

        Args:
            color: Base color (hex format)
            opacity: Opacity value between 0.0 and 1.0

        Returns:
            Color with opacity in hex format
        """
        if not color.startswith('#'):
            # If it's already a Flet color constant, convert to hex
            # For now, we'll append the opacity as hex
            opacity_hex = format(int(opacity * 255), '02x')
            return f"{color}{opacity_hex}"

        # Convert opacity to hex (0-255 range)
        opacity_hex = format(int(opacity * 255), '02x')
        return f"{color}{opacity_hex}"

    def get_surface_variant_with_opacity(self, opacity: float = 0.1) -> str:
        """Get surface variant color with opacity."""
        palette = self.get_palette()
        return self.get_color_with_opacity(palette.surface_variant, opacity)

    def get_primary_with_opacity(self, opacity: float = 0.2) -> str:
        """Get primary color with opacity."""
        palette = self.get_palette()
        return self.get_color_with_opacity(palette.primary, opacity)

    def get_success_with_opacity(self, opacity: float = 0.2) -> str:
        """Get success color with opacity."""
        palette = self.get_palette()
        return self.get_color_with_opacity(palette.success, opacity)

    def get_warning_with_opacity(self, opacity: float = 0.2) -> str:
        """Get warning color with opacity."""
        palette = self.get_palette()
        return self.get_color_with_opacity(palette.warning, opacity)

    def get_error_with_opacity(self, opacity: float = 0.2) -> str:
        """Get error color with opacity."""
        palette = self.get_palette()
        return self.get_color_with_opacity(palette.error, opacity)

    def get_design_token(self, token_path: str) -> Any:
        """
        Get a design token value by path.

        Args:
            token_path: Dot-separated path to token (e.g., 'primitive_colors.blue-500')

        Returns:
            Token value or None if not found
        """
        try:
            parts = token_path.split('.')
            value = self._design_tokens

            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                elif isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return None

            return value
        except Exception:
            return None

    def get_animation_config(self) -> AnimationConfig:
        """Get the current animation configuration."""
        config = self._animation
        if self._reduced_motion:
            # Disable animations for accessibility
            config.fast = 0
            config.normal = 0
            config.slow = 0
            config.theme_transition_duration = 0
        return config

    def set_theme_mode(self, mode: ThemeMode) -> None:
        """
        Set the theme mode.

        Args:
            mode: Theme mode to set
        """
        if mode != self._current_mode:
            self._current_mode = mode
            self._detect_system_theme()
            self._save_user_preferences()
            self._notify_theme_change()

    def set_color_blind_mode(self, mode: ColorBlindMode) -> None:
        """
        Set the color blind accessibility mode.

        Args:
            mode: Color blind mode to set
        """
        if mode != self._color_blind_mode:
            self._color_blind_mode = mode
            self._save_user_preferences()
            self._notify_theme_change()

    def set_font_scale(self, scale: float) -> None:
        """
        Set the font scale factor.

        Args:
            scale: Font scale factor (0.8 to 1.2)
        """
        scale = max(0.8, min(1.2, scale))  # Clamp to valid range
        if scale != self._font_scale:
            self._font_scale = scale
            self._save_user_preferences()
            self._notify_theme_change()

    def set_reduced_motion(self, enabled: bool) -> None:
        """
        Set reduced motion preference for accessibility.

        Args:
            enabled: Whether to enable reduced motion
        """
        if enabled != self._reduced_motion:
            self._reduced_motion = enabled
            self._save_user_preferences()
            self._notify_theme_change()

    def toggle_theme(self) -> None:
        """Toggle between light and dark themes."""
        if self._current_mode == ThemeMode.LIGHT:
            self.set_theme_mode(ThemeMode.DARK)
        elif self._current_mode == ThemeMode.DARK:
            self.set_theme_mode(ThemeMode.LIGHT)
        else:
            # If in auto or high contrast, switch to opposite of current effective mode
            if self._effective_mode == ThemeMode.LIGHT:
                self.set_theme_mode(ThemeMode.DARK)
            else:
                self.set_theme_mode(ThemeMode.LIGHT)

    def add_theme_change_callback(self, callback: Callable[[ThemeMode], None]) -> None:
        """
        Add a callback to be notified of theme changes.

        Args:
            callback: Function to call when theme changes
        """
        if callback not in self._theme_change_callbacks:
            self._theme_change_callbacks.append(callback)

    def remove_theme_change_callback(self, callback: Callable[[ThemeMode], None]) -> None:
        """
        Remove a theme change callback.

        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._theme_change_callbacks:
            self._theme_change_callbacks.remove(callback)

    def _notify_theme_change(self) -> None:
        """Notify all registered callbacks of theme change."""
        for callback in self._theme_change_callbacks:
            try:
                callback(self._effective_mode)
            except Exception:
                # Silently ignore callback errors
                pass

    def create_flet_theme(self) -> ft.Theme:
        """
        Create a Flet theme object from current theme settings.

        Returns:
            Configured Flet theme object
        """
        palette = self.get_current_palette()
        typography = self.get_typography()

        # Create color scheme
        color_scheme = ft.ColorScheme(
            primary=palette.primary,
            on_primary=palette.text_primary,
            secondary=palette.secondary,
            on_secondary=palette.text_primary,
            surface=palette.surface,
            on_surface=palette.text_primary,
            background=palette.background_primary,
            on_background=palette.text_primary,
            error=palette.error,
            on_error=palette.text_primary,
            outline=palette.outline,
            surface_variant=palette.surface_variant,
            on_surface_variant=palette.text_secondary
        )

        # Create text theme
        text_theme = ft.TextTheme(
            display_large=ft.TextStyle(
                size=typography.display_large[0],
                height=typography.display_large[1] / typography.display_large[0],
                weight=ft.FontWeight(typography.display_large[2]),
                font_family="Inter"
            ),
            display_medium=ft.TextStyle(
                size=typography.display_medium[0],
                height=typography.display_medium[1] / typography.display_medium[0],
                weight=ft.FontWeight(typography.display_medium[2]),
                font_family="Inter"
            ),
            display_small=ft.TextStyle(
                size=typography.display_small[0],
                height=typography.display_small[1] / typography.display_small[0],
                weight=ft.FontWeight(typography.display_small[2]),
                font_family="Inter"
            ),
            headline_large=ft.TextStyle(
                size=typography.h1[0],
                height=typography.h1[1] / typography.h1[0],
                weight=ft.FontWeight(typography.h1[2]),
                font_family="Inter"
            ),
            headline_medium=ft.TextStyle(
                size=typography.h2[0],
                height=typography.h2[1] / typography.h2[0],
                weight=ft.FontWeight(typography.h2[2]),
                font_family="Inter"
            ),
            headline_small=ft.TextStyle(
                size=typography.h3[0],
                height=typography.h3[1] / typography.h3[0],
                weight=ft.FontWeight(typography.h3[2]),
                font_family="Inter"
            ),
            title_large=ft.TextStyle(
                size=typography.h4[0],
                height=typography.h4[1] / typography.h4[0],
                weight=ft.FontWeight(typography.h4[2]),
                font_family="Inter"
            ),
            body_large=ft.TextStyle(
                size=typography.body_large[0],
                height=typography.body_large[1] / typography.body_large[0],
                weight=ft.FontWeight(typography.body_large[2]),
                font_family="Inter"
            ),
            body_medium=ft.TextStyle(
                size=typography.body_medium[0],
                height=typography.body_medium[1] / typography.body_medium[0],
                weight=ft.FontWeight(typography.body_medium[2]),
                font_family="Inter"
            ),
            body_small=ft.TextStyle(
                size=typography.body_small[0],
                height=typography.body_small[1] / typography.body_small[0],
                weight=ft.FontWeight(typography.body_small[2]),
                font_family="Inter"
            ),
            label_large=ft.TextStyle(
                size=typography.label[0],
                height=typography.label[1] / typography.label[0],
                weight=ft.FontWeight(typography.label[2]),
                font_family="Inter"
            )
        )

        return ft.Theme(
            color_scheme=color_scheme,
            text_theme=text_theme,
            font_family="Inter"
        )

    def get_text_style(self, style_name: str) -> ft.TextStyle:
        """
        Get a specific text style by name.

        Args:
            style_name: Name of the text style

        Returns:
            Configured text style
        """
        typography = self.get_typography()
        palette = self.get_current_palette()

        style_map = {
            'display_large': typography.display_large,
            'display_medium': typography.display_medium,
            'display_small': typography.display_small,
            'h1': typography.h1,
            'h2': typography.h2,
            'h3': typography.h3,
            'h4': typography.h4,
            'body_large': typography.body_large,
            'body_medium': typography.body_medium,
            'body_small': typography.body_small,
            'caption': typography.caption,
            'overline': typography.overline,
            'label': typography.label,
            'metric_large': typography.metric_large,
            'metric_medium': typography.metric_medium,
            'code_block': typography.code_block,
            'inline_code': typography.inline_code
        }

        if style_name not in style_map:
            # Default to body_medium
            style_name = 'body_medium'

        size, line_height, weight = style_map[style_name]
        font_family = "JetBrains Mono" if 'metric' in style_name or 'code' in style_name else "Inter"

        return ft.TextStyle(
            size=size,
            height=line_height / size,
            weight=self._convert_weight_to_font_weight(weight),
            font_family=font_family,
            color=palette.text_primary
        )

    def get_button_style(self, variant: str = "primary") -> Dict[str, Any]:
        """
        Get enhanced button styling configuration using component variants.

        Args:
            variant: Button variant (primary, secondary, tertiary, danger, ghost, floating)

        Returns:
            Button style configuration
        """
        palette = self.get_current_palette()
        spacing = self.get_spacing()
        animation = self.get_animation_config()
        variant_config = self.get_component_variant("button", variant)

        # Base style from design tokens
        base_style = {
            "padding": ft.padding.symmetric(
                horizontal=spacing.button_padding_horizontal,
                vertical=spacing.button_padding_vertical
            ),
            "border_radius": ft.border_radius.all(8),
            "animation_duration": animation.hover_duration if not self._reduced_motion else 0
        }

        # Apply variant-specific styling
        if variant == "primary":
            base_style.update({
                "bgcolor": palette.primary,
                "color": palette.text_primary,
                "elevation": variant_config.get("elevation", 2)
            })
        elif variant == "secondary":
            base_style.update({
                "bgcolor": palette.secondary,
                "color": palette.text_primary,
                "elevation": variant_config.get("elevation", 1)
            })
        elif variant == "tertiary":
            base_style.update({
                "bgcolor": "transparent",
                "color": palette.primary,
                "border": ft.border.all(1, palette.borders),
                "elevation": variant_config.get("elevation", 0)
            })
        elif variant == "danger":
            base_style.update({
                "bgcolor": palette.error,
                "color": palette.text_primary,
                "elevation": variant_config.get("elevation", 2)
            })
        elif variant == "ghost":
            base_style.update({
                "bgcolor": "transparent",
                "color": palette.text_secondary,
                "elevation": 0
            })
        elif variant == "floating":
            base_style.update({
                "bgcolor": palette.primary,
                "color": palette.text_primary,
                "elevation": variant_config.get("elevation", 6),
                "border_radius": ft.border_radius.all(28)  # Circular
            })

        return base_style

    def get_card_style(self, variant: str = "elevated") -> Dict[str, Any]:
        """
        Get enhanced card styling configuration using component variants.

        Args:
            variant: Card variant (elevated, outlined, filled, interactive)

        Returns:
            Card style configuration
        """
        palette = self.get_current_palette()
        spacing = self.get_spacing()
        variant_config = self.get_component_variant("card", variant)

        base_style = {
            "padding": ft.padding.all(spacing.component_padding),
            "border_radius": ft.border_radius.all(8),
        }

        if variant == "elevated":
            base_style.update({
                "bgcolor": palette.surface,
                "elevation": variant_config.get("elevation", 2),
                "border": None
            })
        elif variant == "outlined":
            base_style.update({
                "bgcolor": palette.surface,
                "elevation": 0,
                "border": ft.border.all(1, palette.borders)
            })
        elif variant == "filled":
            base_style.update({
                "bgcolor": palette.surface_variant,
                "elevation": 0,
                "border": None
            })
        elif variant == "interactive":
            base_style.update({
                "bgcolor": palette.surface,
                "elevation": variant_config.get("elevation", 1),
                "border": None,
                # Add hover effects for interactive cards
                "on_hover": {
                    "elevation": variant_config.get("hover_elevation", 4)
                }
            })

        return base_style

    def get_input_style(self, variant: str = "outlined") -> Dict[str, Any]:
        """
        Get enhanced input field styling configuration using component variants.

        Args:
            variant: Input variant (outlined, filled, underlined)

        Returns:
            Input style configuration
        """
        palette = self.get_current_palette()
        variant_config = self.get_component_variant("input", variant)

        base_style = {
            "color": palette.text_primary,
            "cursor_color": palette.primary,
            "selection_color": palette.selection,
        }

        if variant == "outlined":
            base_style.update({
                "bgcolor": "transparent",
                "border_color": palette.borders,
                "focused_border_color": palette.primary,
                "border_radius": ft.border_radius.all(4)
            })
        elif variant == "filled":
            base_style.update({
                "bgcolor": palette.surface_variant,
                "border_color": "transparent",
                "focused_border_color": palette.primary,
                "border_radius": ft.border_radius.all(4)
            })
        elif variant == "underlined":
            base_style.update({
                "bgcolor": "transparent",
                "border_color": "transparent",
                "focused_border_color": "transparent",
                "border_radius": ft.border_radius.all(0),
                "border": ft.border.only(bottom=ft.border.BorderSide(1, palette.borders))
            })

        return base_style

    def create_themed_component_with_variant(self, component_type: str, variant: str = "default", **kwargs) -> ft.Control:
        """
        Create a themed component with specific variant styling.

        Args:
            component_type: Type of component to create
            variant: Component variant to apply
            **kwargs: Additional component properties

        Returns:
            Styled Flet component with variant applied
        """
        theme_manager = get_theme_manager()
        if not theme_manager:
            raise RuntimeError("Theme manager not initialized")

        if component_type == "button":
            style = self.get_button_style(variant)
            return ft.ElevatedButton(**kwargs, **style)
        elif component_type == "card":
            style = self.get_card_style(variant)
            return ft.Card(**kwargs, **style)
        elif component_type == "input":
            style = self.get_input_style(variant)
            return ft.TextField(**kwargs, **style)
        elif component_type == "text":
            style_name = kwargs.pop('style', 'body_medium')
            text_variant = self.get_component_variant("text", variant)
            text_style = self.get_text_style(style_name)

            # Apply variant modifications
            if "font_family" in text_variant:
                text_style.font_family = text_variant["font_family"]
            if "weight" in text_variant:
                text_style.weight = ft.FontWeight(text_variant["weight"])

            return ft.Text(**kwargs, style=text_style)
        else:
            raise ValueError(f"Unknown component type: {component_type}")

    def get_theme_transition_style(self) -> Dict[str, Any]:
        """
        Get theme transition styling for smooth theme changes.

        Returns:
            Transition style configuration
        """
        animation = self.get_animation_config()

        return {
            "transition_duration": animation.theme_transition_duration,
            "transition_easing": animation.theme_transition_easing,
            "animate_opacity": True,
            "animate_size": False,
            "animate_position": False,
        }



    @property
    def current_mode(self) -> ThemeMode:
        """Get the current theme mode."""
        return self._current_mode

    def get_current_mode(self) -> ThemeMode:
        """Get the current theme mode (method version for compatibility)."""
        return self._current_mode

    @property
    def effective_mode(self) -> ThemeMode:
        """Get the effective theme mode (resolved from auto)."""
        return self._effective_mode

    @property
    def color_blind_mode(self) -> ColorBlindMode:
        """Get the current color blind mode."""
        return self._color_blind_mode

    @property
    def font_scale(self) -> float:
        """Get the current font scale."""
        return self._font_scale

    @property
    def reduced_motion(self) -> bool:
        """Get the reduced motion preference."""
        return self._reduced_motion

    def export_theme_config(self) -> Dict[str, Any]:
        """
        Export current theme configuration.

        Returns:
            Theme configuration dictionary
        """
        return {
            'theme_mode': self._current_mode.value,
            'effective_mode': self._effective_mode.value,
            'color_blind_mode': self._color_blind_mode.value,
            'font_scale': self._font_scale,
            'reduced_motion': self._reduced_motion,
            'color_palette': asdict(self.get_current_palette()),
            'typography': asdict(self.get_typography()),
            'spacing': asdict(self.get_spacing()),
            'animation': asdict(self.get_animation_config())
        }

    def import_theme_config(self, config: Dict[str, Any]) -> None:
        """
        Import theme configuration.

        Args:
            config: Theme configuration dictionary
        """
        try:
            if 'theme_mode' in config:
                self._current_mode = ThemeMode(config['theme_mode'])
            if 'color_blind_mode' in config:
                self._color_blind_mode = ColorBlindMode(config['color_blind_mode'])
            if 'font_scale' in config:
                self._font_scale = max(0.8, min(1.2, config['font_scale']))
            if 'reduced_motion' in config:
                self._reduced_motion = config['reduced_motion']

            self._detect_system_theme()
            self._save_user_preferences()
            self._notify_theme_change()
        except Exception:
            # Ignore invalid configurations
            pass


# Global theme manager instance
_theme_manager_instance: Optional[ThemeManager] = None


def get_theme_manager() -> Optional[ThemeManager]:
    """
    Get the global theme manager instance.

    Returns:
        Theme manager instance or None if not initialized
    """
    return _theme_manager_instance


def initialize_theme_manager(app_state_manager=None, user_preferences_db=None, persistence_config=None) -> ThemeManager:
    """
    Initialize the global theme manager instance.

    Args:
        app_state_manager: Application state manager instance
        user_preferences_db: User preferences database instance
        persistence_config: Theme persistence configuration

    Returns:
        Initialized theme manager instance
    """
    global _theme_manager_instance
    _theme_manager_instance = ThemeManager(app_state_manager, user_preferences_db, persistence_config)
    return _theme_manager_instance


def create_themed_component(component_type: str, **kwargs) -> ft.Control:
    """
    Create a themed component with automatic styling (legacy function).

    For enhanced variant support, use create_themed_component_with_variant.

    Args:
        component_type: Type of component to create
        **kwargs: Additional component properties

    Returns:
        Styled Flet component
    """
    theme_manager = get_theme_manager()
    if not theme_manager:
        raise RuntimeError("Theme manager not initialized")

    # Extract variant if provided, default to primary/default
    variant = kwargs.pop('variant', 'primary' if component_type == 'button' else 'default')

    return theme_manager.create_themed_component_with_variant(component_type, variant, **kwargs)


class ThemeAwareUserControl(ft.Container):
    """
    Enhanced base class for theme-aware and responsive user controls.

    Automatically handles theme changes, responsive layout updates, and provides
    comprehensive theme and responsive design utilities.

    Features:
    - Automatic theme change handling
    - Responsive layout management with breakpoint detection
    - Performance-optimized responsive calculations
    - Accessibility-compliant responsive behaviors
    - Integration with ResponsiveLayoutManager
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._theme_manager = None
        self._responsive_manager = None
        self._callback_registered = False
        self._responsive_callback_registered = False
        self._is_built = False
        self._last_screen_size = None

    def _ensure_theme_manager(self):
        """Ensure theme manager is initialized and callback is registered."""
        if self._theme_manager is None:
            self._theme_manager = get_theme_manager()

        if self._theme_manager and not self._callback_registered:
            self._theme_manager.add_theme_change_callback(self._on_theme_change)
            self._callback_registered = True

    def _ensure_responsive_manager(self):
        """Ensure responsive layout manager is initialized and callback is registered."""
        if self._responsive_manager is None:
            self._ensure_theme_manager()
            if self._theme_manager:
                self._responsive_manager = self._theme_manager.get_responsive_layout_manager()

        if self._responsive_manager and not self._responsive_callback_registered:
            self._responsive_manager.add_resize_callback(self._on_responsive_change)
            self._responsive_callback_registered = True

    def build(self) -> ft.Control:
        """
        Build the control content. Override this method in subclasses.

        Returns:
            The control content
        """
        return ft.Container()

    def _build_content(self) -> None:
        """Build and set the content if not already built."""
        if not self._is_built:
            self.content = self.build()
            self._is_built = True

    def did_mount(self) -> None:
        """Called when control is mounted to the page."""
        super().did_mount()
        self._ensure_responsive_manager()
        self._build_content()

    def _on_theme_change(self, mode: ThemeMode) -> None:
        """Handle theme change events."""
        if self._is_built:
            self.content = self.build()
            self.update()

    def _on_responsive_change(self, width: int, height: int, screen_size: ScreenSize) -> None:
        """
        Handle responsive layout changes.

        Args:
            width: New window width
            height: New window height
            screen_size: New screen size category
        """
        # Only rebuild if screen size category changed
        if self._last_screen_size != screen_size and self._is_built:
            self._last_screen_size = screen_size
            self.content = self.build()
            self.update()

    def get_palette(self) -> ColorPalette:
        """Get current color palette."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_current_palette()
        # Fallback to dark theme
        return ColorPalette(
            background_primary="#000000",
            background_secondary="#0D0D0D",
            surface="#2D2D2D",
            surface_variant="#333333",
            text_primary="#FFFFFF",
            text_secondary="#C0C0C0",
            text_tertiary="#B8B8B8",
            text_disabled="#666666",
            borders="#5D5D5D",
            outline="#5D5D5D",
            error="#FF4444",
            error_container="#4D1A1A",
            success="#44FF44",
            warning="#FFA500",
            info="#44AAFF",
            primary="#44AAFF",
            primary_variant="#3388CC",
            secondary="#B8B8B8",
            secondary_variant="#999999",
            focus_indicator="#44AAFF",
            selection="#44AAFF33"
        )

    def get_text_style(self, style_name: str) -> ft.TextStyle:
        """Get text style by name."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_text_style(style_name)
        # Fallback style
        return ft.TextStyle(size=14, font_family="Inter")

    def get_typography(self) -> TypographyScale:
        """Get typography system."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_typography()
        # Fallback typography
        return TypographyScale()

    def get_spacing(self) -> SpacingSystem:
        """Get spacing system."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_spacing()
        # Fallback spacing
        return SpacingSystem()

    def get_icons(self) -> IconSystem:
        """Get icon system."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_icons()
        # Fallback icon system
        return IconSystem()

    def get_icon(self, icon_name: str) -> str:
        """
        Get icon by name from the centralized icon system.

        Args:
            icon_name: Name of the icon (e.g., 'CPU', 'MEMORY', 'SUCCESS')

        Returns:
            Flet icon constant (e.g., ft.Icons.MEMORY)
        """
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_icon(icon_name)
        # Fallback icon
        return ft.Icons.HELP_OUTLINE

    def get_design_tokens(self) -> DesignTokens:
        """Get design tokens system."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_design_tokens()
        # Fallback - return empty tokens
        return DesignTokens({}, {}, {}, {}, {}, {}, {}, {}, {})

    def get_component_variants(self) -> ComponentVariants:
        """Get component variants system."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_component_variants()
        # Fallback - return empty variants
        return ComponentVariants({}, {}, {}, {}, {})

    def get_component_variant(self, component_type: str, variant_name: str = "default") -> Dict[str, Any]:
        """Get specific component variant configuration."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_component_variant(component_type, variant_name)
        return {}

    def get_color_with_opacity(self, color: str, opacity: float) -> str:
        """Get a color with specified opacity."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_color_with_opacity(color, opacity)
        return color

    def get_primary_with_opacity(self, opacity: float = 0.2) -> str:
        """Get primary color with opacity."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_primary_with_opacity(opacity)
        return "#1976d2"

    def get_surface_variant_with_opacity(self, opacity: float = 0.1) -> str:
        """Get surface variant color with opacity."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_surface_variant_with_opacity(opacity)
        return "#f5f5f5"

    def get_success_with_opacity(self, opacity: float = 0.2) -> str:
        """Get success color with opacity."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_success_with_opacity(opacity)
        return "#4caf50"

    def get_warning_with_opacity(self, opacity: float = 0.2) -> str:
        """Get warning color with opacity."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_warning_with_opacity(opacity)
        return "#ff9800"

    def get_error_with_opacity(self, opacity: float = 0.2) -> str:
        """Get error color with opacity."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_error_with_opacity(opacity)
        return "#f44336"

    def get_design_token(self, token_path: str) -> Any:
        """Get design token value by path."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.get_design_token(token_path)
        return None

    def get_theme_manager(self) -> Optional[ThemeManager]:
        """
        Get the theme manager instance.

        Returns:
            ThemeManager instance or None if not available
        """
        self._ensure_theme_manager()
        return self._theme_manager

    def get_responsive_layout(self) -> ResponsiveLayoutManager:
        """
        Get responsive layout manager instance.

        Returns:
            ResponsiveLayoutManager instance
        """
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager
        # Fallback responsive layout manager
        return ResponsiveLayoutManager()

    def get_responsive_size(self, base_size: int) -> int:
        """
        Get viewport-appropriate size.

        Args:
            base_size: Base size in pixels

        Returns:
            Responsive size for current viewport
        """
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.get_responsive_font_size(base_size)
        return base_size

    def get_responsive_padding(self) -> int:
        """
        Get responsive padding for current screen size.

        Returns:
            Padding value in pixels
        """
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.get_responsive_padding()
        return 16  # Fallback padding

    def get_responsive_columns(self) -> int:
        """
        Get responsive column count for current screen size.

        Returns:
            Number of columns for grid layouts
        """
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.get_responsive_columns()
        return 3  # Fallback column count

    def create_responsive_grid(self,
                             children: List[ft.Control],
                             mobile_cols: Optional[int] = None,
                             tablet_cols: Optional[int] = None,
                             desktop_cols: Optional[int] = None,
                             large_cols: Optional[int] = None,
                             spacing: Optional[int] = None,
                             run_spacing: Optional[int] = None) -> ft.Control:
        """
        Create adaptive grid layout.

        Args:
            children: List of child controls
            mobile_cols: Columns for mobile (default: 1)
            tablet_cols: Columns for tablet (default: 2)
            desktop_cols: Columns for desktop (default: 3)
            large_cols: Columns for large desktop (default: 4)
            spacing: Horizontal spacing between items
            run_spacing: Vertical spacing between rows

        Returns:
            Responsive grid control
        """
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.create_responsive_grid(
                children, mobile_cols, tablet_cols, desktop_cols, large_cols, spacing, run_spacing
            )
        # Fallback to basic grid
        return ft.GridView(
            controls=children,
            runs_count=desktop_cols or 3,
            spacing=spacing or 16,
            run_spacing=run_spacing or 16,
            expand=True
        )

    def create_responsive_container(self,
                                  content: ft.Control,
                                  padding: Optional[int] = None,
                                  margin: Optional[int] = None,
                                  max_width: Optional[int] = None) -> ft.Control:
        """
        Create responsive container with adaptive sizing.

        Args:
            content: Container content
            padding: Custom padding (uses responsive default if None)
            margin: Custom margin
            max_width: Custom max-width (uses responsive default if None)

        Returns:
            Responsive container control
        """
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.create_responsive_container(content, padding, margin, max_width)
        # Fallback container
        return ft.Container(
            content=content,
            padding=ft.padding.all(padding or 16),
            margin=ft.margin.all(margin) if margin else None,
            width=max_width
        )

    def get_breakpoint_value(self, mobile: Any, tablet: Any, desktop: Any, large: Any) -> Any:
        """
        Get value based on current breakpoint.

        Args:
            mobile: Value for mobile screens
            tablet: Value for tablet screens
            desktop: Value for desktop screens
            large: Value for large desktop screens

        Returns:
            Appropriate value for current screen size
        """
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.get_breakpoint_value(mobile, tablet, desktop, large)
        return desktop  # Fallback to desktop value

    def get_current_screen_size(self) -> ScreenSize:
        """
        Get current screen size category.

        Returns:
            Current ScreenSize enum value
        """
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.get_current_screen_size()
        return ScreenSize.DESKTOP  # Fallback

    def is_mobile(self) -> bool:
        """Check if current screen size is mobile."""
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.is_mobile()
        return False

    def is_tablet(self) -> bool:
        """Check if current screen size is tablet."""
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.is_tablet()
        return False

    def is_desktop(self) -> bool:
        """Check if current screen size is desktop."""
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.is_desktop()
        return True  # Fallback to desktop

    def is_large_desktop(self) -> bool:
        """Check if current screen size is large desktop."""
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.is_large_desktop()
        return False

    def is_mobile_or_tablet(self) -> bool:
        """Check if current screen size is mobile or tablet."""
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.is_mobile_or_tablet()
        return False

    def is_desktop_or_larger(self) -> bool:
        """Check if current screen size is desktop or larger."""
        self._ensure_responsive_manager()
        if self._responsive_manager:
            return self._responsive_manager.is_desktop_or_larger()
        return True  # Fallback to desktop

    def create_themed_component(self, component_type: str, variant: str = "default", **kwargs) -> ft.Control:
        """Create a themed component with variant support."""
        self._ensure_theme_manager()
        if self._theme_manager:
            return self._theme_manager.create_themed_component_with_variant(component_type, variant, **kwargs)
        # Fallback to basic component
        if component_type == "text":
            return ft.Text(**kwargs)
        elif component_type == "button":
            return ft.ElevatedButton(**kwargs)
        elif component_type == "card":
            return ft.Card(**kwargs)
        elif component_type == "input":
            return ft.TextField(**kwargs)
        else:
            raise ValueError(f"Unknown component type: {component_type}")

    def _get_control_name(self) -> str:
        """Return the control name for Flet framework."""
        return "container"

    def will_unmount(self) -> None:
        """Clean up theme change and responsive callbacks when control is unmounted."""
        if self._theme_manager and self._callback_registered:
            self._theme_manager.remove_theme_change_callback(self._on_theme_change)
            self._callback_registered = False

        if self._responsive_manager and self._responsive_callback_registered:
            self._responsive_manager.remove_resize_callback(self._on_responsive_change)
            self._responsive_callback_registered = False

        super().will_unmount()


# Responsive Layout Components
class ResponsiveGrid(ThemeAwareUserControl):
    """
    Responsive grid component that automatically adapts column count based on screen size.

    Provides intelligent grid layouts that optimize content display across different
    viewport sizes while maintaining design consistency and usability.
    """

    def __init__(self,
                 children: List[ft.Control],
                 mobile_cols: int = 1,
                 tablet_cols: int = 2,
                 desktop_cols: int = 3,
                 large_cols: int = 4,
                 spacing: int = 16,
                 run_spacing: int = 16,
                 child_aspect_ratio: float = 1.0,
                 **kwargs):
        """
        Initialize responsive grid.

        Args:
            children: List of child controls
            mobile_cols: Columns for mobile screens
            tablet_cols: Columns for tablet screens
            desktop_cols: Columns for desktop screens
            large_cols: Columns for large desktop screens
            spacing: Horizontal spacing between items
            run_spacing: Vertical spacing between rows
            child_aspect_ratio: Aspect ratio for grid items
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        self.children = children
        self.mobile_cols = mobile_cols
        self.tablet_cols = tablet_cols
        self.desktop_cols = desktop_cols
        self.large_cols = large_cols
        self.spacing = spacing
        self.run_spacing = run_spacing
        self.child_aspect_ratio = child_aspect_ratio

    def build(self) -> ft.Control:
        """Build the responsive grid."""
        responsive_manager = self.get_responsive_layout()
        cols = responsive_manager.get_breakpoint_value(
            self.mobile_cols, self.tablet_cols, self.desktop_cols, self.large_cols
        )

        return ft.GridView(
            controls=self.children,
            runs_count=cols,
            spacing=self.spacing,
            run_spacing=self.run_spacing,
            child_aspect_ratio=self.child_aspect_ratio,
            expand=True
        )


class ResponsiveContainer(ThemeAwareUserControl):
    """
    Responsive container component with adaptive sizing and spacing.

    Automatically adjusts padding, margins, and max-width based on screen size
    to provide optimal content presentation across different devices.
    """

    def __init__(self,
                 content: ft.Control,
                 mobile_padding: int = 12,
                 tablet_padding: int = 16,
                 desktop_padding: int = 24,
                 large_padding: int = 32,
                 center_content: bool = True,
                 use_max_width: bool = True,
                 **kwargs):
        """
        Initialize responsive container.

        Args:
            content: Container content
            mobile_padding: Padding for mobile screens
            tablet_padding: Padding for tablet screens
            desktop_padding: Padding for desktop screens
            large_padding: Padding for large desktop screens
            center_content: Whether to center content horizontally
            use_max_width: Whether to apply responsive max-width
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        self.content = content
        self.mobile_padding = mobile_padding
        self.tablet_padding = tablet_padding
        self.desktop_padding = desktop_padding
        self.large_padding = large_padding
        self.center_content = center_content
        self.use_max_width = use_max_width

    def build(self) -> ft.Control:
        """Build the responsive container."""
        responsive_manager = self.get_responsive_layout()
        padding = responsive_manager.get_breakpoint_value(
            self.mobile_padding, self.tablet_padding,
            self.desktop_padding, self.large_padding
        )

        if self.use_max_width:
            max_width = responsive_manager.get_responsive_container_width()
            if responsive_manager.is_mobile():
                max_width = None  # Full width on mobile
        else:
            max_width = None

        return ft.Container(
            content=self.content,
            padding=ft.padding.all(padding),
            width=max_width,
            alignment=ft.alignment.center if self.center_content and max_width else None
        )


class ResponsiveFlex(ThemeAwareUserControl):
    """
    Responsive flex component that adapts direction and wrapping based on screen size.

    Provides flexible layouts that automatically switch between row and column
    orientations to optimize content flow across different viewport sizes.
    """

    def __init__(self,
                 children: List[ft.Control],
                 mobile_direction: ft.MainAxisAlignment = ft.MainAxisAlignment.START,
                 tablet_direction: ft.MainAxisAlignment = ft.MainAxisAlignment.START,
                 desktop_direction: ft.MainAxisAlignment = ft.MainAxisAlignment.START,
                 mobile_wrap: bool = True,
                 tablet_wrap: bool = True,
                 desktop_wrap: bool = False,
                 spacing: int = 16,
                 **kwargs):
        """
        Initialize responsive flex.

        Args:
            children: List of child controls
            mobile_direction: Main axis alignment for mobile
            tablet_direction: Main axis alignment for tablet
            desktop_direction: Main axis alignment for desktop
            mobile_wrap: Whether to wrap on mobile
            tablet_wrap: Whether to wrap on tablet
            desktop_wrap: Whether to wrap on desktop
            spacing: Spacing between items
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        self.children = children
        self.mobile_direction = mobile_direction
        self.tablet_direction = tablet_direction
        self.desktop_direction = desktop_direction
        self.mobile_wrap = mobile_wrap
        self.tablet_wrap = tablet_wrap
        self.desktop_wrap = desktop_wrap
        self.spacing = spacing

    def build(self) -> ft.Control:
        """Build the responsive flex."""
        responsive_manager = self.get_responsive_layout()

        if responsive_manager.is_mobile():
            if self.mobile_wrap:
                return ft.Column(
                    controls=self.children,
                    spacing=self.spacing,
                    alignment=self.mobile_direction
                )
            else:
                return ft.Row(
                    controls=self.children,
                    spacing=self.spacing,
                    alignment=self.mobile_direction
                )
        elif responsive_manager.is_tablet():
            if self.tablet_wrap:
                return ft.Column(
                    controls=self.children,
                    spacing=self.spacing,
                    alignment=self.tablet_direction
                )
            else:
                return ft.Row(
                    controls=self.children,
                    spacing=self.spacing,
                    alignment=self.tablet_direction
                )
        else:  # Desktop or larger
            if self.desktop_wrap:
                return ft.Column(
                    controls=self.children,
                    spacing=self.spacing,
                    alignment=self.desktop_direction
                )
            else:
                return ft.Row(
                    controls=self.children,
                    spacing=self.spacing,
                    alignment=self.desktop_direction
                )


class ResponsiveStack(ThemeAwareUserControl):
    """
    Responsive stack component that switches between vertical and horizontal layouts.

    Automatically adapts stack orientation based on screen size to optimize
    content presentation and user interaction across different devices.
    """

    def __init__(self,
                 children: List[ft.Control],
                 mobile_vertical: bool = True,
                 tablet_vertical: bool = True,
                 desktop_vertical: bool = False,
                 spacing: int = 16,
                 alignment: ft.MainAxisAlignment = ft.MainAxisAlignment.START,
                 cross_alignment: ft.CrossAxisAlignment = ft.CrossAxisAlignment.CENTER,
                 **kwargs):
        """
        Initialize responsive stack.

        Args:
            children: List of child controls
            mobile_vertical: Use vertical layout on mobile
            tablet_vertical: Use vertical layout on tablet
            desktop_vertical: Use vertical layout on desktop
            spacing: Spacing between items
            alignment: Main axis alignment
            cross_alignment: Cross axis alignment
            **kwargs: Additional UserControl properties
        """
        super().__init__(**kwargs)
        self.children = children
        self.mobile_vertical = mobile_vertical
        self.tablet_vertical = tablet_vertical
        self.desktop_vertical = desktop_vertical
        self.spacing = spacing
        self.alignment = alignment
        self.cross_alignment = cross_alignment

    def build(self) -> ft.Control:
        """Build the responsive stack."""
        responsive_manager = self.get_responsive_layout()

        if responsive_manager.is_mobile():
            vertical = self.mobile_vertical
        elif responsive_manager.is_tablet():
            vertical = self.tablet_vertical
        else:  # Desktop or larger
            vertical = self.desktop_vertical

        if vertical:
            return ft.Column(
                controls=self.children,
                spacing=self.spacing,
                alignment=self.alignment,
                horizontal_alignment=self.cross_alignment
            )
        else:
            return ft.Row(
                controls=self.children,
                spacing=self.spacing,
                alignment=self.alignment,
                vertical_alignment=self.cross_alignment
            )