"""
Module: breadcrumb_ui
Description: Hierarchical breadcrumb navigation component for MikroDok application.
            Provides contextual navigation for deep application states with responsive design,
            theme integration, and accessibility features. Implements modern UI/UX patterns
            with elegant breadcrumb trails and navigation functionality.
Phase: 1
Location: /src/modules/ui/navigation_ui/breadcrumb_ui/breadcrumb_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime, timezone
import weakref

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    ColorPalette,
    SpacingSystem,
    TypographyScale,
    IconSystem,
    ResponsiveLayoutManager,
    ScreenSize,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class BreadcrumbItem:
    """Breadcrumb navigation item definition."""
    route_id: str
    title: str
    path: str
    icon: Optional[str] = None
    tooltip: Optional[str] = None
    is_clickable: bool = True
    is_current: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BreadcrumbConfig:
    """Configuration for the breadcrumb component."""
    show_home_icon: bool = True
    show_icons: bool = True
    show_separators: bool = True
    max_items: int = 5
    separator_icon: str = "CHEVRON_RIGHT"
    home_icon: str = "HOME"
    enable_tooltips: bool = True
    enable_overflow: bool = True
    compact_mode: bool = False
    show_current_as_text: bool = True
    enable_keyboard_navigation: bool = True


class BreadcrumbState(Enum):
    """Breadcrumb component states."""
    NORMAL = "normal"
    LOADING = "loading"
    ERROR = "error"
    EMPTY = "empty"


class BreadcrumbUI(ThemeAwareUserControl):
    """
    Hierarchical breadcrumb navigation component with comprehensive functionality.
    
    Features:
    - Responsive breadcrumb trail with overflow handling
    - Clickable navigation items with hover effects
    - Icon support for visual hierarchy
    - Tooltip integration for enhanced UX
    - Keyboard navigation support
    - Mobile-optimized compact display
    - Full theme system integration with responsive design
    - Accessibility-compliant navigation
    - Modern UI/UX with elegant animations and transitions
    - Customizable separators and styling
    - Overflow management for long breadcrumb chains
    """

    def __init__(self,
                 config: Optional[BreadcrumbConfig] = None,
                 on_navigate: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the breadcrumb UI component.

        Args:
            config: Breadcrumb configuration
            on_navigate: Callback for navigation events
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or BreadcrumbConfig()
        
        # Callbacks
        self._on_navigate = on_navigate
        
        # State management
        self._breadcrumbs: List[BreadcrumbItem] = []
        self._state = BreadcrumbState.EMPTY
        self._overflow_items: List[BreadcrumbItem] = []
        self._visible_items: List[BreadcrumbItem] = []
        
        # UI components
        self._breadcrumb_container: Optional[ft.Container] = None
        self._overflow_menu: Optional[ft.PopupMenuButton] = None
        self._home_button: Optional[ft.Control] = None
        
        # Animation and interaction state
        self._hover_states: Dict[str, bool] = {}
        self._focus_index: int = -1
        
        logger.debug("BreadcrumbUI initialized")

    def build(self) -> ft.Control:
        """Build the breadcrumb UI component."""
        try:
            self._ensure_theme_manager()
            palette = self.get_palette()
            spacing = self.get_spacing()
            
            # Create main breadcrumb container
            self._breadcrumb_container = self.create_responsive_container(
                content=self._build_breadcrumb_content(),
                bgcolor=palette.surface_container_lowest,
                border_radius=self.get_breakpoint_value(4, 6, 8, 10),
                padding=self.get_breakpoint_value(8, 10, 12, 14),
                margin=0,
                border=ft.border.all(
                    width=1,
                    color=palette.outline_variant
                )
            )
            
            return self._breadcrumb_container
            
        except Exception as e:
            logger.error(f"Error building breadcrumb UI: {e}")
            return self._build_error_fallback()

    def _build_breadcrumb_content(self) -> ft.Control:
        """Build the main breadcrumb content."""
        if self._state == BreadcrumbState.EMPTY or not self._breadcrumbs:
            return self._build_empty_state()
        
        if self._state == BreadcrumbState.LOADING:
            return self._build_loading_state()
        
        if self._state == BreadcrumbState.ERROR:
            return self._build_error_state()
        
        return self._build_breadcrumb_trail()

    def _build_empty_state(self) -> ft.Control:
        """Build empty state display."""
        palette = self.get_palette()
        typography = self.get_typography()
        
        return ft.Container(
            content=ft.Text(
                "No navigation path",
                style=self.get_text_style("bodySmall"),
                color=palette.text_tertiary,
                italic=True
            ),
            padding=ft.padding.all(8),
            alignment=ft.alignment.center_left
        )

    def _build_loading_state(self) -> ft.Control:
        """Build loading state display."""
        palette = self.get_palette()
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.ProgressRing(
                        width=16,
                        height=16,
                        stroke_width=2,
                        color=palette.primary
                    ),
                    ft.Text(
                        "Loading navigation...",
                        style=self.get_text_style("bodySmall"),
                        color=palette.text_secondary
                    )
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START
            ),
            padding=ft.padding.all(8)
        )

    def _build_error_state(self) -> ft.Control:
        """Build error state display."""
        palette = self.get_palette()
        icons = self.get_icons()
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        name=icons.ERROR,
                        size=16,
                        color=palette.error
                    ),
                    ft.Text(
                        "Navigation error",
                        style=self.get_text_style("bodySmall"),
                        color=palette.error
                    )
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START
            ),
            padding=ft.padding.all(8)
        )

    def _build_error_fallback(self) -> ft.Control:
        """Build error fallback UI."""
        return ft.Container(
            content=ft.Text("Breadcrumb Error"),
            padding=ft.padding.all(8)
        )

    def _build_breadcrumb_trail(self) -> ft.Control:
        """Build the main breadcrumb trail."""
        try:
            # Calculate visible items based on screen size and overflow settings
            self._calculate_visible_items()

            controls = []

            # Add home button if configured
            if self._config.show_home_icon and self._breadcrumbs:
                home_button = self._build_home_button()
                if home_button:
                    controls.append(home_button)
                    if self._visible_items:
                        controls.append(self._build_separator())

            # Add overflow menu if needed
            if self._overflow_items and self._config.enable_overflow:
                overflow_menu = self._build_overflow_menu()
                controls.append(overflow_menu)
                if self._visible_items:
                    controls.append(self._build_separator())

            # Add visible breadcrumb items
            for i, item in enumerate(self._visible_items):
                # Add breadcrumb item
                breadcrumb_control = self._build_breadcrumb_item(item, i)
                controls.append(breadcrumb_control)

                # Add separator (except for last item)
                if i < len(self._visible_items) - 1 and self._config.show_separators:
                    controls.append(self._build_separator())

            # Create scrollable row for breadcrumbs
            breadcrumb_row = ft.Row(
                controls=controls,
                spacing=self.get_breakpoint_value(4, 6, 8, 10),
                scroll=ft.ScrollMode.AUTO,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

            return breadcrumb_row

        except Exception as e:
            logger.error(f"Error building breadcrumb trail: {e}")
            return self._build_error_state()

    def _calculate_visible_items(self):
        """Calculate which items should be visible based on screen size and config."""
        try:
            if not self._breadcrumbs:
                self._visible_items = []
                self._overflow_items = []
                return

            max_items = self._config.max_items

            # Adjust max items based on screen size
            if self.is_mobile():
                max_items = min(max_items, 2)
            elif self.is_tablet():
                max_items = min(max_items, 3)

            if len(self._breadcrumbs) <= max_items:
                # All items fit
                self._visible_items = self._breadcrumbs.copy()
                self._overflow_items = []
            else:
                # Need to handle overflow
                if self._config.enable_overflow:
                    # Show first item, overflow items, and last few items
                    first_item = self._breadcrumbs[0]
                    last_items = self._breadcrumbs[-(max_items-1):]
                    overflow_items = self._breadcrumbs[1:-(max_items-1)]

                    self._visible_items = [first_item] + last_items
                    self._overflow_items = overflow_items
                else:
                    # Just show last max_items
                    self._visible_items = self._breadcrumbs[-max_items:]
                    self._overflow_items = []

            # Mark current item
            if self._visible_items:
                self._visible_items[-1].is_current = True

        except Exception as e:
            logger.error(f"Error calculating visible items: {e}")
            self._visible_items = self._breadcrumbs.copy()
            self._overflow_items = []

    def _build_home_button(self) -> Optional[ft.Control]:
        """Build the home button."""
        try:
            palette = self.get_palette()
            icons = self.get_icons()

            home_icon = getattr(icons, self._config.home_icon, icons.HOME)

            return ft.IconButton(
                icon=home_icon,
                icon_size=self.get_breakpoint_value(16, 18, 20, 22),
                icon_color=palette.text_secondary,
                tooltip="Home" if self._config.enable_tooltips else None,
                on_click=lambda e: self._handle_home_click(),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.TRANSPARENT,
                    overlay_color=palette.surface_variant,
                    padding=ft.padding.all(4),
                    shape=ft.RoundedRectangleBorder(radius=4)
                )
            )

        except Exception as e:
            logger.error(f"Error building home button: {e}")
            return None

    def _build_overflow_menu(self) -> ft.Control:
        """Build the overflow menu for hidden breadcrumb items."""
        try:
            palette = self.get_palette()
            icons = self.get_icons()

            # Create menu items for overflow items
            menu_items = []
            for item in self._overflow_items:
                menu_item = ft.PopupMenuItem(
                    text=item.title,
                    icon=getattr(icons, item.icon) if item.icon else None,
                    on_click=lambda e, route_id=item.route_id: self._handle_navigate(route_id)
                )
                menu_items.append(menu_item)

            return ft.PopupMenuButton(
                icon=icons.MORE_HORIZ,
                icon_size=self.get_breakpoint_value(16, 18, 20, 22),
                icon_color=palette.text_secondary,
                tooltip=f"{len(self._overflow_items)} more items" if self._config.enable_tooltips else None,
                items=menu_items,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.TRANSPARENT,
                    overlay_color=palette.surface_variant,
                    padding=ft.padding.all(4),
                    shape=ft.RoundedRectangleBorder(radius=4)
                )
            )

        except Exception as e:
            logger.error(f"Error building overflow menu: {e}")
            return ft.Container()

    def _build_separator(self) -> ft.Control:
        """Build a breadcrumb separator."""
        try:
            palette = self.get_palette()
            icons = self.get_icons()

            separator_icon = getattr(icons, self._config.separator_icon, icons.CHEVRON_RIGHT)

            return ft.Icon(
                name=separator_icon,
                size=self.get_breakpoint_value(12, 14, 16, 18),
                color=palette.text_tertiary
            )

        except Exception as e:
            logger.error(f"Error building separator: {e}")
            return ft.Container(width=8)

    def _build_breadcrumb_item(self, item: BreadcrumbItem, index: int) -> ft.Control:
        """Build a single breadcrumb item."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            icons = self.get_icons()

            # Determine if this is the current (last) item
            is_current = item.is_current or index == len(self._visible_items) - 1

            # Create item content
            item_controls = []

            # Add icon if configured and available
            if self._config.show_icons and item.icon:
                icon_control = ft.Icon(
                    name=getattr(icons, item.icon, icons.FOLDER),
                    size=self.get_breakpoint_value(14, 16, 18, 20),
                    color=palette.text_secondary if not is_current else palette.primary
                )
                item_controls.append(icon_control)

            # Add text
            text_style = "bodyMedium" if not is_current else "bodyMedium"
            text_color = palette.text_secondary if not is_current else palette.text_primary
            text_weight = ft.FontWeight.NORMAL if not is_current else ft.FontWeight.W_500

            text_control = ft.Text(
                item.title,
                style=self.get_text_style(text_style),
                color=text_color,
                weight=text_weight,
                overflow=ft.TextOverflow.ELLIPSIS,
                max_lines=1
            )
            item_controls.append(text_control)

            # Create item container
            item_content = ft.Row(
                controls=item_controls,
                spacing=self.get_breakpoint_value(4, 6, 8, 8),
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True
            )

            # If current item and configured to show as text only
            if is_current and self._config.show_current_as_text:
                return ft.Container(
                    content=item_content,
                    padding=ft.padding.symmetric(
                        horizontal=self.get_breakpoint_value(4, 6, 8, 10),
                        vertical=self.get_breakpoint_value(2, 3, 4, 5)
                    ),
                    border_radius=ft.border_radius.all(4)
                )

            # If clickable, create button
            if item.is_clickable and not is_current:
                return ft.TextButton(
                    content=item_content,
                    tooltip=item.tooltip or item.title if self._config.enable_tooltips else None,
                    on_click=lambda e, route_id=item.route_id: self._handle_navigate(route_id),
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TRANSPARENT,
                        overlay_color=palette.surface_variant,
                        padding=ft.padding.symmetric(
                            horizontal=self.get_breakpoint_value(4, 6, 8, 10),
                            vertical=self.get_breakpoint_value(2, 3, 4, 5)
                        ),
                        shape=ft.RoundedRectangleBorder(radius=4),
                        animation_duration=150
                    )
                )

            # Non-clickable item
            return ft.Container(
                content=item_content,
                padding=ft.padding.symmetric(
                    horizontal=self.get_breakpoint_value(4, 6, 8, 10),
                    vertical=self.get_breakpoint_value(2, 3, 4, 5)
                ),
                border_radius=ft.border_radius.all(4),
                tooltip=item.tooltip or item.title if self._config.enable_tooltips else None
            )

        except Exception as e:
            logger.error(f"Error building breadcrumb item: {e}")
            return ft.Text(item.title if item else "Error")

    # Public API Methods
    def set_breadcrumbs(self, breadcrumbs: List[BreadcrumbItem]):
        """
        Set the breadcrumb items.

        Args:
            breadcrumbs: List of breadcrumb items to display
        """
        try:
            self._breadcrumbs = breadcrumbs.copy()
            self._state = BreadcrumbState.NORMAL if breadcrumbs else BreadcrumbState.EMPTY

            # Update UI
            if self._breadcrumb_container:
                self._breadcrumb_container.content = self._build_breadcrumb_content()
                self.update()

            logger.debug(f"Set {len(breadcrumbs)} breadcrumb items")

        except Exception as e:
            logger.error(f"Error setting breadcrumbs: {e}")
            self._state = BreadcrumbState.ERROR

    def add_breadcrumb(self, item: BreadcrumbItem):
        """
        Add a breadcrumb item to the end of the trail.

        Args:
            item: Breadcrumb item to add
        """
        try:
            # Mark previous items as not current
            for breadcrumb in self._breadcrumbs:
                breadcrumb.is_current = False

            # Add new item as current
            item.is_current = True
            self._breadcrumbs.append(item)
            self._state = BreadcrumbState.NORMAL

            # Update UI
            if self._breadcrumb_container:
                self._breadcrumb_container.content = self._build_breadcrumb_content()
                self.update()

            logger.debug(f"Added breadcrumb: {item.title}")

        except Exception as e:
            logger.error(f"Error adding breadcrumb: {e}")

    def remove_breadcrumb(self, route_id: str) -> bool:
        """
        Remove a breadcrumb item by route ID.

        Args:
            route_id: Route ID of the item to remove

        Returns:
            True if item was removed, False otherwise
        """
        try:
            original_length = len(self._breadcrumbs)
            self._breadcrumbs = [item for item in self._breadcrumbs if item.route_id != route_id]

            if len(self._breadcrumbs) != original_length:
                # Update current state
                if self._breadcrumbs:
                    self._breadcrumbs[-1].is_current = True
                    self._state = BreadcrumbState.NORMAL
                else:
                    self._state = BreadcrumbState.EMPTY

                # Update UI
                if self._breadcrumb_container:
                    self._breadcrumb_container.content = self._build_breadcrumb_content()
                    self.update()

                logger.debug(f"Removed breadcrumb: {route_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error removing breadcrumb: {e}")
            return False

    def clear_breadcrumbs(self):
        """Clear all breadcrumb items."""
        try:
            self._breadcrumbs.clear()
            self._state = BreadcrumbState.EMPTY

            # Update UI
            if self._breadcrumb_container:
                self._breadcrumb_container.content = self._build_breadcrumb_content()
                self.update()

            logger.debug("Cleared all breadcrumbs")

        except Exception as e:
            logger.error(f"Error clearing breadcrumbs: {e}")

    def set_loading(self, loading: bool):
        """
        Set loading state.

        Args:
            loading: Whether to show loading state
        """
        try:
            self._state = BreadcrumbState.LOADING if loading else (
                BreadcrumbState.NORMAL if self._breadcrumbs else BreadcrumbState.EMPTY
            )

            # Update UI
            if self._breadcrumb_container:
                self._breadcrumb_container.content = self._build_breadcrumb_content()
                self.update()

        except Exception as e:
            logger.error(f"Error setting loading state: {e}")

    # Event Handlers
    def _handle_navigate(self, route_id: str):
        """
        Handle navigation to a breadcrumb item.

        Args:
            route_id: Route ID to navigate to
        """
        try:
            if self._on_navigate:
                self._on_navigate(route_id)

            logger.debug(f"Navigation requested to: {route_id}")

        except Exception as e:
            logger.error(f"Error handling navigation: {e}")

    def _handle_home_click(self):
        """Handle home button click."""
        try:
            # Navigate to home/root route
            if self._on_navigate:
                self._on_navigate("home")

            logger.debug("Home navigation requested")

        except Exception as e:
            logger.error(f"Error handling home click: {e}")

    def _handle_keyboard_navigation(self, e: ft.KeyboardEvent):
        """
        Handle keyboard navigation.

        Args:
            e: Keyboard event
        """
        try:
            if not self._config.enable_keyboard_navigation:
                return

            if e.key == "ArrowLeft":
                self._navigate_focus(-1)
            elif e.key == "ArrowRight":
                self._navigate_focus(1)
            elif e.key == "Enter" or e.key == "Space":
                self._activate_focused_item()
            elif e.key == "Home":
                self._focus_index = 0
                self._update_focus_visual()
            elif e.key == "End":
                self._focus_index = len(self._visible_items) - 1
                self._update_focus_visual()

        except Exception as e:
            logger.error(f"Error handling keyboard navigation: {e}")

    def _navigate_focus(self, direction: int):
        """
        Navigate focus in the specified direction.

        Args:
            direction: -1 for left, 1 for right
        """
        try:
            if not self._visible_items:
                return

            new_index = self._focus_index + direction
            new_index = max(0, min(new_index, len(self._visible_items) - 1))

            if new_index != self._focus_index:
                self._focus_index = new_index
                self._update_focus_visual()

        except Exception as e:
            logger.error(f"Error navigating focus: {e}")

    def _activate_focused_item(self):
        """Activate the currently focused item."""
        try:
            if 0 <= self._focus_index < len(self._visible_items):
                item = self._visible_items[self._focus_index]
                if item.is_clickable and not item.is_current:
                    self._handle_navigate(item.route_id)

        except Exception as e:
            logger.error(f"Error activating focused item: {e}")

    def _update_focus_visual(self):
        """Update visual focus indicators."""
        try:
            # This would typically update visual focus indicators
            # For now, we'll just log the focus change
            if 0 <= self._focus_index < len(self._visible_items):
                item = self._visible_items[self._focus_index]
                logger.debug(f"Focus moved to: {item.title}")

        except Exception as e:
            logger.error(f"Error updating focus visual: {e}")

    # Utility Methods
    def get_breadcrumb_by_route(self, route_id: str) -> Optional[BreadcrumbItem]:
        """
        Get breadcrumb item by route ID.

        Args:
            route_id: Route ID to search for

        Returns:
            Breadcrumb item if found, None otherwise
        """
        try:
            for item in self._breadcrumbs:
                if item.route_id == route_id:
                    return item
            return None

        except Exception as e:
            logger.error(f"Error getting breadcrumb by route: {e}")
            return None

    def get_breadcrumb_path(self) -> List[str]:
        """
        Get the current breadcrumb path as a list of route IDs.

        Returns:
            List of route IDs in breadcrumb order
        """
        try:
            return [item.route_id for item in self._breadcrumbs]

        except Exception as e:
            logger.error(f"Error getting breadcrumb path: {e}")
            return []

    def get_current_breadcrumb(self) -> Optional[BreadcrumbItem]:
        """
        Get the current (last) breadcrumb item.

        Returns:
            Current breadcrumb item if available, None otherwise
        """
        try:
            if self._breadcrumbs:
                return self._breadcrumbs[-1]
            return None

        except Exception as e:
            logger.error(f"Error getting current breadcrumb: {e}")
            return None

    def update_breadcrumb_title(self, route_id: str, new_title: str) -> bool:
        """
        Update the title of a breadcrumb item.

        Args:
            route_id: Route ID of the item to update
            new_title: New title for the item

        Returns:
            True if item was updated, False otherwise
        """
        try:
            for item in self._breadcrumbs:
                if item.route_id == route_id:
                    item.title = new_title

                    # Update UI
                    if self._breadcrumb_container:
                        self._breadcrumb_container.content = self._build_breadcrumb_content()
                        self.update()

                    logger.debug(f"Updated breadcrumb title: {route_id} -> {new_title}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error updating breadcrumb title: {e}")
            return False

    # Properties
    @property
    def breadcrumbs(self) -> List[BreadcrumbItem]:
        """Get current breadcrumb items."""
        return self._breadcrumbs.copy()

    @property
    def state(self) -> BreadcrumbState:
        """Get current component state."""
        return self._state

    @property
    def config(self) -> BreadcrumbConfig:
        """Get component configuration."""
        return self._config

    @config.setter
    def config(self, value: BreadcrumbConfig):
        """Set component configuration."""
        self._config = value

        # Update UI if needed
        if self._breadcrumb_container:
            self._breadcrumb_container.content = self._build_breadcrumb_content()
            self.update()

    @property
    def on_navigate(self) -> Optional[Callable[[str], None]]:
        """Get navigation callback."""
        return self._on_navigate

    @on_navigate.setter
    def on_navigate(self, value: Optional[Callable[[str], None]]):
        """Set navigation callback."""
        self._on_navigate = value

    def will_unmount(self) -> None:
        """Clean up when component is unmounted."""
        try:
            # Clear references
            self._breadcrumbs.clear()
            self._overflow_items.clear()
            self._visible_items.clear()
            self._hover_states.clear()

            # Call parent cleanup
            super().will_unmount()

            logger.debug("BreadcrumbUI unmounted")

        except Exception as e:
            logger.error(f"Error during breadcrumb unmount: {e}")


# Utility Functions for Breadcrumb Integration
def create_breadcrumb_from_route(route_id: str, title: str, path: str,
                                icon: Optional[str] = None,
                                tooltip: Optional[str] = None) -> BreadcrumbItem:
    """
    Create a breadcrumb item from route information.

    Args:
        route_id: Unique route identifier
        title: Display title for the breadcrumb
        path: Route path
        icon: Optional icon name
        tooltip: Optional tooltip text

    Returns:
        Configured BreadcrumbItem
    """
    return BreadcrumbItem(
        route_id=route_id,
        title=title,
        path=path,
        icon=icon,
        tooltip=tooltip or title,
        is_clickable=True,
        is_current=False
    )


def create_breadcrumb_trail_from_navigation(navigation_controller) -> List[BreadcrumbItem]:
    """
    Create breadcrumb trail from navigation controller state.

    Args:
        navigation_controller: Navigation controller instance

    Returns:
        List of breadcrumb items
    """
    try:
        if hasattr(navigation_controller, 'breadcrumbs'):
            # Convert navigation breadcrumbs to UI breadcrumbs
            nav_breadcrumbs = navigation_controller.breadcrumbs
            ui_breadcrumbs = []

            for nav_item in nav_breadcrumbs:
                ui_item = BreadcrumbItem(
                    route_id=nav_item.route_id,
                    title=nav_item.title,
                    path=nav_item.path,
                    is_clickable=nav_item.is_clickable,
                    is_current=False
                )
                ui_breadcrumbs.append(ui_item)

            # Mark last item as current
            if ui_breadcrumbs:
                ui_breadcrumbs[-1].is_current = True

            return ui_breadcrumbs

        return []

    except Exception as e:
        logger.error(f"Error creating breadcrumb trail from navigation: {e}")
        return []


# Enhanced Breadcrumb Component with Accessibility
class AccessibleBreadcrumbUI(BreadcrumbUI):
    """
    Enhanced breadcrumb component with comprehensive accessibility features.

    Additional Features:
    - ARIA landmarks and labels
    - Screen reader announcements
    - Enhanced keyboard navigation
    - Focus management
    - High contrast mode support
    - Reduced motion support
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Accessibility state
        self._aria_label = "Breadcrumb navigation"
        self._announce_changes = True
        self._high_contrast_mode = False
        self._reduced_motion = False

    def build(self) -> ft.Control:
        """Build accessible breadcrumb UI with ARIA support."""
        try:
            self._ensure_theme_manager()
            palette = self.get_palette()

            # Create main container with ARIA attributes
            main_container = self.create_responsive_container(
                content=self._build_accessible_breadcrumb_content(),
                bgcolor=palette.surface_container_lowest,
                border_radius=self.get_breakpoint_value(4, 6, 8, 10),
                padding=self.get_breakpoint_value(8, 10, 12, 14),
                margin=0,
                border=ft.border.all(
                    width=1,
                    color=palette.outline_variant
                )
            )

            # Add keyboard event handling
            main_container.on_key_down = self._handle_keyboard_navigation

            return main_container

        except Exception as e:
            logger.error(f"Error building accessible breadcrumb UI: {e}")
            return self._build_error_fallback()

    def _build_accessible_breadcrumb_content(self) -> ft.Control:
        """Build breadcrumb content with accessibility enhancements."""
        if self._state == BreadcrumbState.EMPTY or not self._breadcrumbs:
            return self._build_accessible_empty_state()

        if self._state == BreadcrumbState.LOADING:
            return self._build_accessible_loading_state()

        if self._state == BreadcrumbState.ERROR:
            return self._build_accessible_error_state()

        return self._build_accessible_breadcrumb_trail()

    def _build_accessible_empty_state(self) -> ft.Control:
        """Build accessible empty state."""
        palette = self.get_palette()

        return ft.Container(
            content=ft.Text(
                "No navigation path available",
                style=self.get_text_style("bodySmall"),
                color=palette.text_tertiary,
                italic=True,
                semantics_label="No breadcrumb navigation available"
            ),
            padding=ft.padding.all(8),
            alignment=ft.alignment.center_left
        )

    def _build_accessible_loading_state(self) -> ft.Control:
        """Build accessible loading state."""
        palette = self.get_palette()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.ProgressRing(
                        width=16,
                        height=16,
                        stroke_width=2,
                        color=palette.primary,
                        semantics_label="Loading navigation"
                    ),
                    ft.Text(
                        "Loading navigation path...",
                        style=self.get_text_style("bodySmall"),
                        color=palette.text_secondary,
                        semantics_label="Loading breadcrumb navigation"
                    )
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START
            ),
            padding=ft.padding.all(8)
        )

    def _build_accessible_error_state(self) -> ft.Control:
        """Build accessible error state."""
        palette = self.get_palette()
        icons = self.get_icons()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        name=icons.ERROR,
                        size=16,
                        color=palette.error,
                        semantics_label="Error"
                    ),
                    ft.Text(
                        "Navigation error occurred",
                        style=self.get_text_style("bodySmall"),
                        color=palette.error,
                        semantics_label="Breadcrumb navigation error"
                    )
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START
            ),
            padding=ft.padding.all(8)
        )

    def _build_accessible_breadcrumb_trail(self) -> ft.Control:
        """Build accessible breadcrumb trail with ARIA support."""
        try:
            # Calculate visible items
            self._calculate_visible_items()

            controls = []

            # Add accessible home button
            if self._config.show_home_icon and self._breadcrumbs:
                home_button = self._build_accessible_home_button()
                if home_button:
                    controls.append(home_button)
                    if self._visible_items:
                        controls.append(self._build_accessible_separator())

            # Add accessible overflow menu
            if self._overflow_items and self._config.enable_overflow:
                overflow_menu = self._build_accessible_overflow_menu()
                controls.append(overflow_menu)
                if self._visible_items:
                    controls.append(self._build_accessible_separator())

            # Add accessible breadcrumb items
            for i, item in enumerate(self._visible_items):
                breadcrumb_control = self._build_accessible_breadcrumb_item(item, i)
                controls.append(breadcrumb_control)

                # Add separator (except for last item)
                if i < len(self._visible_items) - 1 and self._config.show_separators:
                    controls.append(self._build_accessible_separator())

            # Create accessible breadcrumb navigation
            breadcrumb_nav = ft.Row(
                controls=controls,
                spacing=self.get_breakpoint_value(4, 6, 8, 10),
                scroll=ft.ScrollMode.AUTO,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )

            return breadcrumb_nav

        except Exception as e:
            logger.error(f"Error building accessible breadcrumb trail: {e}")
            return self._build_accessible_error_state()

    def _build_accessible_home_button(self) -> Optional[ft.Control]:
        """Build accessible home button with ARIA support."""
        try:
            palette = self.get_palette()
            icons = self.get_icons()

            home_icon = getattr(icons, self._config.home_icon, icons.HOME)

            return ft.IconButton(
                icon=home_icon,
                icon_size=self.get_breakpoint_value(16, 18, 20, 22),
                icon_color=palette.text_secondary,
                tooltip="Navigate to home" if self._config.enable_tooltips else None,
                on_click=lambda e: self._handle_accessible_home_click(),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.TRANSPARENT,
                    overlay_color=palette.surface_variant,
                    padding=ft.padding.all(4),
                    shape=ft.RoundedRectangleBorder(radius=4)
                )
            )

        except Exception as e:
            logger.error(f"Error building accessible home button: {e}")
            return None

    def _build_accessible_separator(self) -> ft.Control:
        """Build accessible separator with ARIA support."""
        try:
            palette = self.get_palette()
            icons = self.get_icons()

            separator_icon = getattr(icons, self._config.separator_icon, icons.CHEVRON_RIGHT)

            return ft.Icon(
                name=separator_icon,
                size=self.get_breakpoint_value(12, 14, 16, 18),
                color=palette.text_tertiary,
                semantics_label="Breadcrumb separator"
            )

        except Exception as e:
            logger.error(f"Error building accessible separator: {e}")
            return ft.Container(width=8)

    def _handle_accessible_home_click(self):
        """Handle accessible home button click with announcements."""
        try:
            if self._announce_changes:
                # Announce navigation to screen readers
                logger.info("Navigating to home")

            self._handle_home_click()

        except Exception as e:
            logger.error(f"Error handling accessible home click: {e}")

    # Accessibility Properties
    @property
    def aria_label(self) -> str:
        """Get ARIA label for the breadcrumb navigation."""
        return self._aria_label

    @aria_label.setter
    def aria_label(self, value: str):
        """Set ARIA label for the breadcrumb navigation."""
        self._aria_label = value

    @property
    def announce_changes(self) -> bool:
        """Get whether to announce navigation changes."""
        return self._announce_changes

    @announce_changes.setter
    def announce_changes(self, value: bool):
        """Set whether to announce navigation changes."""
        self._announce_changes = value
