"""
Module: app_header_ui
Description: Top navigation bar with logo, primary menu, user profile, and theme toggle for MikroDok application.
            Provides comprehensive application header functionality including responsive design, theme integration,
            navigation management, user controls, and accessibility features. Implements modern UI/UX patterns
            with elegant look-and-feel and full integration with the theme system.
Phase: 1
Location: /src/modules/ui/navigation_ui/app_header_ui/app_header_ui.py
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
class HeaderConfig:
    """Configuration for the app header."""
    show_logo: bool = True
    show_app_name: bool = True
    show_navigation_menu: bool = True
    show_user_controls: bool = True
    show_theme_toggle: bool = True
    show_search_bar: bool = False
    enable_mobile_menu: bool = True
    enable_notifications: bool = True
    max_menu_items: int = 8
    compact_mode: bool = False


@dataclass
class NavigationItem:
    """Navigation menu item definition."""
    id: str
    label: str
    icon: str
    route: str
    tooltip: Optional[str] = None
    badge_count: Optional[int] = None
    is_active: bool = False
    is_enabled: bool = True
    submenu: Optional[List['NavigationItem']] = None


@dataclass
class UserProfile:
    """User profile information for header display."""
    name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    is_authenticated: bool = True


class HeaderState(Enum):
    """Header component states."""
    NORMAL = "normal"
    COMPACT = "compact"
    MOBILE = "mobile"
    LOADING = "loading"
    ERROR = "error"


class AppHeaderUI(ThemeAwareUserControl):
    """
    Application header component with comprehensive navigation and user controls.
    
    Features:
    - Responsive app branding with logo and name
    - Primary navigation menu with active state management
    - User profile section with theme toggle and settings
    - Mobile-optimized hamburger menu and collapsible navigation
    - Search bar integration (optional)
    - Notification indicators and badges
    - Full theme system integration with responsive design
    - Accessibility-compliant navigation and controls
    - Modern UI/UX with elegant animations and transitions
    - Performance-optimized rendering and state management
    """

    def __init__(
        self,
        config: Optional[HeaderConfig] = None,
        navigation_items: Optional[List[NavigationItem]] = None,
        user_profile: Optional[UserProfile] = None,
        on_navigation_change: Optional[Callable[[str], None]] = None,
        on_theme_toggle: Optional[Callable[[], None]] = None,
        on_user_action: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or HeaderConfig()
        self._navigation_items = navigation_items or self._get_default_navigation_items()
        self._user_profile = user_profile or UserProfile(name="User")
        
        # Callbacks
        self._on_navigation_change = on_navigation_change
        self._on_theme_toggle = on_theme_toggle
        self._on_user_action = on_user_action
        
        # State management
        self._current_state = HeaderState.NORMAL
        self._active_navigation_id: Optional[str] = None
        self._mobile_menu_visible = False
        self._user_menu_visible = False
        self._search_focused = False
        self._notification_count = 0
        
        # UI components
        self._logo_container: Optional[ft.Container] = None
        self._navigation_container: Optional[ft.Container] = None
        self._user_controls_container: Optional[ft.Container] = None
        self._mobile_menu_container: Optional[ft.Container] = None
        self._search_bar: Optional[ft.TextField] = None
        
        # Animation controllers
        self._menu_animation_duration = 300
        self._hover_animation_duration = 150
        
        # Initialize component
        self._initialize_component()

    def _initialize_component(self) -> None:
        """Initialize the header component."""
        try:
            # Set initial active navigation if none set
            if not self._active_navigation_id and self._navigation_items:
                for item in self._navigation_items:
                    if item.is_active:
                        self._active_navigation_id = item.id
                        break
                        
            logger.debug("App header component initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing app header component: {e}")
            self._current_state = HeaderState.ERROR

    def _get_default_navigation_items(self) -> List[NavigationItem]:
        """Get default navigation items for the header."""
        return [
            NavigationItem(
                id="dashboard",
                label="Dashboard",
                icon="HOME",
                route="/dashboard",
                tooltip="Main dashboard",
                is_active=True
            ),
            NavigationItem(
                id="documents",
                label="Documents",
                icon="DESCRIPTION",
                route="/documents",
                tooltip="Document management"
            ),
            NavigationItem(
                id="training",
                label="Training",
                icon="SCHOOL",
                route="/training",
                tooltip="Model training"
            ),
            NavigationItem(
                id="chat",
                label="Chat",
                icon="CHAT",
                route="/chat",
                tooltip="AI chat interface"
            ),
            NavigationItem(
                id="monitoring",
                label="Monitor",
                icon="MONITOR",
                route="/monitoring",
                tooltip="System monitoring"
            ),
            NavigationItem(
                id="settings",
                label="Settings",
                icon="SETTINGS",
                route="/settings",
                tooltip="Application settings"
            )
        ]

    def build(self) -> ft.Control:
        """Build the responsive app header."""
        try:
            # Get theme components
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Determine current screen size and adjust layout
            screen_size = self.get_current_screen_size()

            # Build header components
            branding_section = self._build_branding_section()
            navigation_section = self._build_navigation_section()
            user_controls_section = self._build_user_controls_section()
            mobile_menu_toggle = self._build_mobile_menu_toggle()

            # Create main header layout based on screen size
            if screen_size == ScreenSize.MOBILE:
                header_content = ft.Row(
                    controls=[
                        branding_section,
                        ft.Container(expand=True),  # Spacer
                        mobile_menu_toggle,
                        user_controls_section
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.sm
                )
            else:
                header_content = ft.Row(
                    controls=[
                        branding_section,
                        ft.Container(
                            content=navigation_section,
                            expand=True,
                            margin=ft.margin.symmetric(horizontal=spacing.lg)
                        ),
                        user_controls_section
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.md
                )

            # Create mobile menu overlay if needed
            mobile_menu = self._build_mobile_menu() if screen_size == ScreenSize.MOBILE else None

            # Main header container
            header_container = ft.Container(
                content=header_content,
                bgcolor=palette.surface,
                padding=ft.padding.symmetric(
                    horizontal=self.get_breakpoint_value(
                        mobile=spacing.md,
                        tablet=spacing.lg,
                        desktop=spacing.xl,
                        large=spacing.xxl
                    ),
                    vertical=spacing.md
                ),
                border=ft.border.only(
                    bottom=ft.BorderSide(
                        width=1,
                        color=palette.outline_variant
                    )
                ),
                height=self.get_breakpoint_value(
                    mobile=56,
                    tablet=64,
                    desktop=72,
                    large=80
                )
            )

            # Return header with optional mobile menu
            if mobile_menu and self._mobile_menu_visible:
                return ft.Stack(
                    controls=[
                        header_container,
                        mobile_menu
                    ]
                )
            else:
                return header_container

        except Exception as e:
            logger.error(f"Error building app header: {e}")
            return self._build_error_fallback()

    def _build_branding_section(self) -> ft.Control:
        """Build the app branding section with logo and name."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        controls = []

        # App logo
        if self._config.show_logo:
            logo = ft.Icon(
                name=icons.PSYCHOLOGY,  # MikroDok brain icon
                size=self.get_breakpoint_value(
                    mobile=24,
                    tablet=28,
                    desktop=32,
                    large=36
                ),
                color=palette.primary
            )
            controls.append(logo)

        # App name
        if self._config.show_app_name:
            # Show app name on tablet and larger screens
            screen_size = self.get_current_screen_size()
            if screen_size != ScreenSize.MOBILE:
                app_name = ft.Text(
                    "MikroDok",
                    style=self.get_text_style("titleLarge"),
                    color=palette.on_surface,
                    weight=ft.FontWeight.W_600,
                    no_wrap=True
                )
                controls.append(app_name)

        return ft.Row(
            controls=controls,
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _build_navigation_section(self) -> ft.Control:
        """Build the primary navigation menu."""
        if not self._config.show_navigation_menu or not self._navigation_items:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # Create navigation items
        nav_controls = []
        visible_items = self._navigation_items[:self._config.max_menu_items]

        for item in visible_items:
            if not item.is_enabled:
                continue

            # Create navigation button
            nav_button = self._create_navigation_button(item)
            nav_controls.append(nav_button)

        return ft.Row(
            controls=nav_controls,
            spacing=spacing.xs,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _create_navigation_button(self, item: NavigationItem) -> ft.Control:
        """Create a navigation button for a menu item."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        is_active = item.id == self._active_navigation_id

        # Button styling based on active state
        if is_active:
            bg_color = palette.primary_container
            text_color = palette.on_primary_container
            icon_color = palette.primary
        else:
            bg_color = ft.Colors.TRANSPARENT
            text_color = palette.on_surface
            icon_color = palette.on_surface_variant

        # Create button content
        button_content = ft.Row(
            controls=[
                ft.Icon(
                    name=getattr(icons, item.icon, icons.HELP_OUTLINE),
                    size=self.get_breakpoint_value(16, 18, 20, 22),
                    color=icon_color
                ),
                ft.Text(
                    item.label,
                    style=self.get_text_style("labelMedium"),
                    color=text_color,
                    weight=ft.FontWeight.W_500 if is_active else ft.FontWeight.W_400,
                    no_wrap=True
                ) if self.get_current_screen_size() != ScreenSize.MOBILE else None
            ],
            spacing=spacing.xs,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        # Add badge if present
        if item.badge_count and item.badge_count > 0:
            badge = ft.Container(
                content=ft.Text(
                    str(min(item.badge_count, 99)),
                    style=self.get_text_style("labelSmall"),
                    color=palette.on_error,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER
                ),
                bgcolor=palette.error,
                border_radius=ft.border_radius.all(10),
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                margin=ft.margin.only(left=-8, top=-8),
                width=20,
                height=20
            )

            button_content = ft.Stack(
                controls=[button_content, badge]
            )

        # Create navigation button
        nav_button = ft.Container(
            content=button_content,
            bgcolor=bg_color,
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.symmetric(
                horizontal=spacing.sm,
                vertical=spacing.xs
            ),
            ink=True,
            on_click=lambda e, item_id=item.id: self._on_navigation_click(item_id),
            tooltip=item.tooltip,
            animate=ft.animation.Animation(
                duration=self._hover_animation_duration,
                curve=ft.AnimationCurve.EASE_OUT
            )
        )

        return nav_button

    def _build_user_controls_section(self) -> ft.Control:
        """Build the user controls section with theme toggle and profile."""
        if not self._config.show_user_controls:
            return ft.Container()

        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        controls = []

        # Notification button
        if self._config.enable_notifications:
            notification_button = self._create_notification_button()
            controls.append(notification_button)

        # Theme toggle button
        if self._config.show_theme_toggle:
            theme_toggle = self._create_theme_toggle_button()
            controls.append(theme_toggle)

        # User profile button
        user_profile_button = self._create_user_profile_button()
        controls.append(user_profile_button)

        return ft.Row(
            controls=controls,
            spacing=spacing.xs,
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _create_notification_button(self) -> ft.Control:
        """Create notification button with badge."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Notification icon
        notification_icon = ft.Icon(
            name=icons.NOTIFICATIONS,
            size=self.get_breakpoint_value(20, 22, 24, 26),
            color=palette.on_surface_variant
        )

        # Add badge if there are notifications
        if self._notification_count > 0:
            badge = ft.Container(
                content=ft.Text(
                    str(min(self._notification_count, 99)),
                    style=self.get_text_style("labelSmall"),
                    color=palette.on_error,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER
                ),
                bgcolor=palette.error,
                border_radius=ft.border_radius.all(8),
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
                margin=ft.margin.only(left=-6, top=-6),
                width=16,
                height=16
            )

            notification_content = ft.Stack(
                controls=[notification_icon, badge]
            )
        else:
            notification_content = notification_icon

        return ft.IconButton(
            content=notification_content,
            tooltip="Notifications",
            on_click=self._on_notification_click,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.all(8)
            )
        )

    def _create_theme_toggle_button(self) -> ft.Control:
        """Create theme toggle button."""
        palette = self.get_palette()
        icons = self.get_icons()

        # Get current theme mode to determine icon
        theme_manager = self.get_theme_manager()
        is_dark_mode = theme_manager and theme_manager.is_dark_mode()

        return ft.IconButton(
            icon=icons.LIGHT_MODE if is_dark_mode else icons.DARK_MODE,
            icon_size=self.get_breakpoint_value(20, 22, 24, 26),
            icon_color=palette.on_surface_variant,
            tooltip="Toggle theme",
            on_click=self._on_theme_toggle_click,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.all(8)
            )
        )

    def _create_user_profile_button(self) -> ft.Control:
        """Create user profile button."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # User avatar or default icon
        if self._user_profile.avatar_url:
            # TODO: Implement avatar image loading
            avatar_content = ft.Icon(
                name=icons.PERSON,
                size=self.get_breakpoint_value(20, 22, 24, 26),
                color=palette.on_surface_variant
            )
        else:
            avatar_content = ft.Icon(
                name=icons.PERSON,
                size=self.get_breakpoint_value(20, 22, 24, 26),
                color=palette.on_surface_variant
            )

        # Show user name on larger screens
        screen_size = self.get_current_screen_size()
        if screen_size in [ScreenSize.DESKTOP, ScreenSize.LARGE_DESKTOP]:
            user_content = ft.Row(
                controls=[
                    avatar_content,
                    ft.Text(
                        self._user_profile.name,
                        style=self.get_text_style("labelMedium"),
                        color=palette.on_surface,
                        no_wrap=True
                    ),
                    ft.Icon(
                        name=icons.EXPAND_MORE,
                        size=16,
                        color=palette.on_surface_variant
                    )
                ],
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        else:
            user_content = avatar_content

        return ft.Container(
            content=user_content,
            bgcolor=ft.Colors.TRANSPARENT,
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.symmetric(
                horizontal=spacing.xs,
                vertical=spacing.xs
            ),
            ink=True,
            on_click=self._on_user_profile_click,
            tooltip=f"User: {self._user_profile.name}"
        )

    def _build_mobile_menu_toggle(self) -> ft.Control:
        """Build mobile menu toggle button."""
        palette = self.get_palette()
        icons = self.get_icons()

        return ft.IconButton(
            icon=icons.MENU,
            icon_size=self.get_breakpoint_value(24, 26, 28, 30),
            icon_color=palette.on_surface,
            tooltip="Menu",
            on_click=self._on_mobile_menu_toggle,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.all(8)
            )
        )

    def _build_mobile_menu(self) -> ft.Control:
        """Build mobile menu overlay."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Create mobile navigation items
        mobile_nav_items = []
        for item in self._navigation_items:
            if not item.is_enabled:
                continue

            mobile_nav_item = self._create_mobile_navigation_item(item)
            mobile_nav_items.append(mobile_nav_item)

        # Mobile menu content
        menu_content = ft.Column(
            controls=[
                # Header
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                "Navigation",
                                style=self.get_text_style("titleMedium"),
                                color=palette.on_surface,
                                weight=ft.FontWeight.W_600
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color=palette.on_surface,
                                on_click=self._on_mobile_menu_close,
                                tooltip="Close menu"
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    padding=ft.padding.all(spacing.md),
                    border=ft.border.only(
                        bottom=ft.BorderSide(
                            width=1,
                            color=palette.outline_variant
                        )
                    )
                ),
                # Navigation items
                ft.Container(
                    content=ft.Column(
                        controls=mobile_nav_items,
                        spacing=spacing.xs
                    ),
                    padding=ft.padding.all(spacing.md),
                    expand=True
                )
            ],
            spacing=0
        )

        # Mobile menu overlay
        return ft.Container(
            content=menu_content,
            bgcolor=palette.surface,
            border_radius=ft.border_radius.only(
                bottom_left=12,
                bottom_right=12
            ),
            border=ft.border.all(
                width=1,
                color=palette.outline_variant
            ),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=palette.shadow,
                offset=ft.Offset(0, 4)
            ),
            margin=ft.margin.only(
                top=self.get_breakpoint_value(56, 64, 72, 80)
            ),
            height=300,
            animate=ft.animation.Animation(
                duration=self._menu_animation_duration,
                curve=ft.AnimationCurve.EASE_OUT
            )
        )

    def _create_mobile_navigation_item(self, item: NavigationItem) -> ft.Control:
        """Create mobile navigation item."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        is_active = item.id == self._active_navigation_id

        # Item styling
        if is_active:
            bg_color = palette.primary_container
            text_color = palette.on_primary_container
            icon_color = palette.primary
        else:
            bg_color = ft.Colors.TRANSPARENT
            text_color = palette.on_surface
            icon_color = palette.on_surface_variant

        # Item content
        item_content = ft.Row(
            controls=[
                ft.Icon(
                    name=getattr(icons, item.icon, icons.HELP_OUTLINE),
                    size=24,
                    color=icon_color
                ),
                ft.Text(
                    item.label,
                    style=self.get_text_style("bodyLarge"),
                    color=text_color,
                    weight=ft.FontWeight.W_500 if is_active else ft.FontWeight.W_400
                ),
                ft.Container(expand=True),
                # Badge
                ft.Container(
                    content=ft.Text(
                        str(item.badge_count),
                        style=self.get_text_style("labelSmall"),
                        color=palette.on_error,
                        weight=ft.FontWeight.W_600,
                        text_align=ft.TextAlign.CENTER
                    ),
                    bgcolor=palette.error,
                    border_radius=ft.border_radius.all(10),
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    width=20,
                    height=20,
                    visible=item.badge_count and item.badge_count > 0
                )
            ],
            spacing=spacing.md,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        return ft.Container(
            content=item_content,
            bgcolor=bg_color,
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(spacing.md),
            ink=True,
            on_click=lambda e, item_id=item.id: self._on_mobile_navigation_click(item_id),
            animate=ft.animation.Animation(
                duration=self._hover_animation_duration,
                curve=ft.AnimationCurve.EASE_OUT
            )
        )

    # Event Handlers
    def _on_navigation_click(self, item_id: str) -> None:
        """Handle navigation item click."""
        try:
            if item_id != self._active_navigation_id:
                self._active_navigation_id = item_id

                # Update navigation items active state
                for item in self._navigation_items:
                    item.is_active = (item.id == item_id)

                # Trigger callback
                if self._on_navigation_change:
                    self._on_navigation_change(item_id)

                # Update UI
                self.update()

                logger.debug(f"Navigation changed to: {item_id}")

        except Exception as e:
            logger.error(f"Error handling navigation click: {e}")

    def _on_mobile_navigation_click(self, item_id: str) -> None:
        """Handle mobile navigation item click."""
        try:
            # Close mobile menu
            self._mobile_menu_visible = False

            # Handle navigation
            self._on_navigation_click(item_id)

        except Exception as e:
            logger.error(f"Error handling mobile navigation click: {e}")

    def _on_mobile_menu_toggle(self, e) -> None:
        """Handle mobile menu toggle."""
        try:
            self._mobile_menu_visible = not self._mobile_menu_visible
            self.update()

            logger.debug(f"Mobile menu toggled: {self._mobile_menu_visible}")

        except Exception as e:
            logger.error(f"Error toggling mobile menu: {e}")

    def _on_mobile_menu_close(self, e) -> None:
        """Handle mobile menu close."""
        try:
            self._mobile_menu_visible = False
            self.update()

        except Exception as e:
            logger.error(f"Error closing mobile menu: {e}")

    def _on_theme_toggle_click(self, e) -> None:
        """Handle theme toggle click."""
        try:
            # Get theme manager and toggle theme
            theme_manager = self.get_theme_manager()
            if theme_manager:
                theme_manager.toggle_theme()

            # Trigger callback
            if self._on_theme_toggle:
                self._on_theme_toggle()

            logger.debug("Theme toggled")

        except Exception as e:
            logger.error(f"Error toggling theme: {e}")

    def _on_notification_click(self, e) -> None:
        """Handle notification button click."""
        try:
            if self._on_user_action:
                self._on_user_action("notifications")

            logger.debug("Notification button clicked")

        except Exception as e:
            logger.error(f"Error handling notification click: {e}")

    def _on_user_profile_click(self, e) -> None:
        """Handle user profile button click."""
        try:
            self._user_menu_visible = not self._user_menu_visible

            if self._on_user_action:
                self._on_user_action("profile")

            logger.debug("User profile clicked")

        except Exception as e:
            logger.error(f"Error handling user profile click: {e}")

    # Public Methods
    def set_active_navigation(self, item_id: str) -> None:
        """Set the active navigation item."""
        try:
            if item_id != self._active_navigation_id:
                self._active_navigation_id = item_id

                # Update navigation items
                for item in self._navigation_items:
                    item.is_active = (item.id == item_id)

                self.update()

        except Exception as e:
            logger.error(f"Error setting active navigation: {e}")

    def set_notification_count(self, count: int) -> None:
        """Set the notification count."""
        try:
            self._notification_count = max(0, count)
            self.update()

        except Exception as e:
            logger.error(f"Error setting notification count: {e}")

    def update_user_profile(self, profile: UserProfile) -> None:
        """Update user profile information."""
        try:
            self._user_profile = profile
            self.update()

        except Exception as e:
            logger.error(f"Error updating user profile: {e}")

    def set_compact_mode(self, compact: bool) -> None:
        """Set compact mode for the header."""
        try:
            self._config.compact_mode = compact
            self._current_state = HeaderState.COMPACT if compact else HeaderState.NORMAL
            self.update()

        except Exception as e:
            logger.error(f"Error setting compact mode: {e}")

    def _build_error_fallback(self) -> ft.Control:
        """Build error fallback UI."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        name=ft.Icons.ERROR_OUTLINE,
                        size=24,
                        color=palette.error
                    ),
                    ft.Text(
                        "Header Error",
                        style=self.get_text_style("bodyMedium"),
                        color=palette.error
                    )
                ],
                spacing=spacing.sm,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=palette.error_container,
            padding=ft.padding.all(spacing.md),
            border_radius=ft.border_radius.all(8),
            height=56
        )
