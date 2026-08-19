"""
Module: sidebar_menu_ui
Description: Collapsible sidebar navigation component with comprehensive menu system for MikroDok application.
            Provides responsive navigation menu, user profile section, resource monitor mini-view, quick links,
            and seamless integration with theme system. Features mobile-optimized collapsible behavior,
            accessibility compliance, and modern UI/UX with elegant animations and transitions.
Phase: 1
Location: /src/modules/ui/navigation_ui/sidebar_menu_ui/sidebar_menu_ui.py
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


class SidebarState(Enum):
    """Sidebar visibility states."""
    EXPANDED = "expanded"
    COLLAPSED = "collapsed"
    HIDDEN = "hidden"


class NavigationItem(Enum):
    """Navigation menu items."""
    DASHBOARD = "dashboard"
    DOCUMENTS = "documents"
    MODELS = "models"
    TRAINING = "training"
    SETTINGS = "settings"
    HELP = "help"


@dataclass
class SidebarConfig:
    """Configuration for the sidebar menu."""
    expanded_width: int = 280
    collapsed_width: int = 64
    show_user_profile: bool = True
    show_resource_monitor: bool = True
    show_quick_links: bool = True
    enable_auto_collapse: bool = True
    enable_hover_expand: bool = True
    animation_duration: int = 300
    mobile_breakpoint: int = 768
    enable_tooltips: bool = True
    show_badges: bool = True


@dataclass
class UserProfile:
    """User profile information."""
    name: str = "User"
    email: str = ""
    avatar_url: Optional[str] = None
    license_type: str = "Free"
    projects_count: int = 0
    models_count: int = 0
    training_hours: float = 0.0


@dataclass
class ResourceStats:
    """Resource monitoring statistics."""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_usage: float = 0.0
    gpu_memory: float = 0.0
    disk_usage: float = 0.0


@dataclass
class QuickLink:
    """Quick link item."""
    label: str
    icon: str
    route: str
    badge_count: Optional[int] = None
    is_enabled: bool = True


class SidebarMenuUI(ThemeAwareUserControl):
    """
    Collapsible sidebar navigation component with comprehensive menu system.
    
    Features:
    - Responsive collapsible sidebar with smooth animations
    - Primary navigation menu with active state management
    - User profile section with avatar and quick stats
    - Resource monitor mini-view with real-time updates
    - Quick links section for frequently accessed items
    - Mobile-optimized behavior with touch-friendly interactions
    - Full theme system integration with responsive design
    - Accessibility-compliant navigation and controls
    - Modern UI/UX with elegant animations and transitions
    - Performance-optimized rendering and state management
    """

    def __init__(self,
                 config: Optional[SidebarConfig] = None,
                 user_profile: Optional[UserProfile] = None,
                 on_navigation_change: Optional[Callable[[NavigationItem], None]] = None,
                 on_sidebar_toggle: Optional[Callable[[SidebarState], None]] = None,
                 on_quick_link_click: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the SidebarMenuUI component.
        
        Args:
            config: Sidebar configuration settings
            user_profile: User profile information
            on_navigation_change: Callback for navigation item changes
            on_sidebar_toggle: Callback for sidebar state changes
            on_quick_link_click: Callback for quick link clicks
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or SidebarConfig()
        self._user_profile = user_profile or UserProfile()
        
        # Callbacks
        self._on_navigation_change = on_navigation_change
        self._on_sidebar_toggle = on_sidebar_toggle
        self._on_quick_link_click = on_quick_link_click
        
        # State management
        self._current_state = SidebarState.EXPANDED
        self._active_navigation = NavigationItem.DASHBOARD
        self._resource_stats = ResourceStats()
        self._is_mobile = False
        self._hover_timer = None
        
        # UI components
        self._sidebar_container = None
        self._navigation_menu = None
        self._user_profile_section = None
        self._resource_monitor = None
        self._quick_links_section = None
        self._toggle_button = None
        
        # Animation state
        self._is_animating = False
        self._animation_start_time = None
        
        # Quick links data
        self._quick_links = [
            QuickLink("Recent Projects", ft.Icons.HISTORY, "/recent", 3),
            QuickLink("Saved Models", ft.Icons.BOOKMARK, "/saved", 5),
            QuickLink("Training Queue", ft.Icons.QUEUE, "/queue", 2),
            QuickLink("Help Center", ft.Icons.HELP, "/help")
        ]
        
        logger.info("SidebarMenuUI initialized")

    def build(self) -> ft.Control:
        """Build the sidebar menu component."""
        try:
            # Check if mobile
            self._is_mobile = self.get_current_screen_size() == ScreenSize.MOBILE
            
            # Auto-collapse on mobile
            if self._is_mobile and self._config.enable_auto_collapse:
                self._current_state = SidebarState.COLLAPSED
            
            # Build main sidebar container
            self._sidebar_container = self._build_sidebar_container()
            
            return self._sidebar_container
            
        except Exception as e:
            logger.error(f"Error building sidebar menu: {e}")
            return self._build_error_fallback()

    def _build_sidebar_container(self) -> ft.Control:
        """Build the main sidebar container."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        # Calculate current width
        current_width = self._get_current_width()
        
        # Build sidebar content
        content = self._build_sidebar_content()
        
        return ft.Container(
            content=content,
            width=current_width,
            height=None,  # Full height
            bgcolor=palette.surface_container_low,
            border=ft.border.only(
                right=ft.BorderSide(
                    width=1,
                    color=palette.outline_variant
                )
            ),
            padding=ft.padding.all(0),
            animate=ft.animation.Animation(
                duration=self._config.animation_duration,
                curve=ft.AnimationCurve.EASE_OUT
            ) if not self._is_mobile else None,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=palette.shadow,
                offset=ft.Offset(2, 0)
            ) if self._current_state == SidebarState.EXPANDED else None,
            # Accessibility attributes
            data={
                "role": "navigation",
                "aria-label": "Main navigation sidebar",
                "aria-expanded": str(self._current_state == SidebarState.EXPANDED).lower()
            }
        )

    def _build_sidebar_content(self) -> ft.Control:
        """Build the sidebar content."""
        content_sections = []
        
        # Add toggle button
        if not self._is_mobile:
            content_sections.append(self._build_toggle_section())
        
        # Add user profile section
        if self._config.show_user_profile:
            content_sections.append(self._build_user_profile_section())
        
        # Add navigation menu
        content_sections.append(self._build_navigation_menu())
        
        # Add quick links
        if self._config.show_quick_links:
            content_sections.append(self._build_quick_links_section())
        
        # Add resource monitor (at bottom)
        if self._config.show_resource_monitor:
            content_sections.append(self._build_resource_monitor_section())
        
        return ft.Column(
            controls=content_sections,
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO if self._current_state == SidebarState.EXPANDED else ft.ScrollMode.HIDDEN
        )

    def _get_current_width(self) -> int:
        """Get current sidebar width based on state."""
        if self._current_state == SidebarState.EXPANDED:
            return self._config.expanded_width
        elif self._current_state == SidebarState.COLLAPSED:
            return self._config.collapsed_width
        else:  # HIDDEN
            return 0

    def _build_error_fallback(self) -> ft.Control:
        """Build error fallback UI."""
        palette = self.get_palette()

        return ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.ERROR, color=palette.error, size=24),
                ft.Text("Sidebar Error", color=palette.error, size=12)
            ], alignment=ft.MainAxisAlignment.CENTER),
            width=self._config.collapsed_width,
            height=100,
            bgcolor=palette.error_container,
            padding=ft.padding.all(8)
        )

    def _build_toggle_section(self) -> ft.Control:
        """Build the sidebar toggle section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Toggle button
        self._toggle_button = ft.IconButton(
            icon=icons.MENU if self._current_state == SidebarState.COLLAPSED else icons.MENU_OPEN,
            icon_size=self.get_breakpoint_value(20, 22, 24, 26),
            icon_color=palette.on_surface,
            bgcolor=ft.Colors.TRANSPARENT,
            hover_color=palette.surface_container_highest,
            on_click=self._on_toggle_click,
            tooltip="Toggle Sidebar" if self._config.enable_tooltips else None,
            # Accessibility attributes
            data={
                "aria-label": f"{'Expand' if self._current_state == SidebarState.COLLAPSED else 'Collapse'} sidebar navigation",
                "aria-expanded": str(self._current_state == SidebarState.EXPANDED).lower(),
                "role": "button"
            }
        )

        return ft.Container(
            content=ft.Row([
                self._toggle_button,
                ft.Text(
                    "MikroDok",
                    style=self.get_typography().title_medium,
                    color=palette.on_surface,
                    visible=self._current_state == SidebarState.EXPANDED
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.all(spacing.md),
            border=ft.border.only(
                bottom=ft.BorderSide(
                    width=1,
                    color=palette.outline_variant
                )
            )
        )

    def _build_user_profile_section(self) -> ft.Control:
        """Build the user profile section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Avatar
        avatar = ft.CircleAvatar(
            content=ft.Text(
                self._user_profile.name[0].upper() if self._user_profile.name else "U",
                color=palette.on_primary,
                style=typography.title_medium
            ),
            bgcolor=palette.primary,
            radius=self.get_breakpoint_value(16, 18, 20, 22)
        )

        # Profile info (only visible when expanded)
        profile_info = ft.Column([
            ft.Text(
                self._user_profile.name,
                style=typography.body_medium,
                color=palette.on_surface,
                weight=ft.FontWeight.W_500,
                overflow=ft.TextOverflow.ELLIPSIS
            ),
            ft.Text(
                f"{self._user_profile.license_type} License",
                style=typography.body_small,
                color=palette.on_surface_variant,
                overflow=ft.TextOverflow.ELLIPSIS
            )
        ], spacing=spacing.xs, tight=True)

        # Stats row (only visible when expanded)
        stats = ft.Row([
            self._build_stat_item("Projects", str(self._user_profile.projects_count)),
            self._build_stat_item("Models", str(self._user_profile.models_count)),
            self._build_stat_item("Hours", f"{self._user_profile.training_hours:.1f}")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # Main content
        if self._current_state == SidebarState.EXPANDED:
            content = ft.Column([
                ft.Row([avatar, profile_info], spacing=spacing.md, alignment=ft.MainAxisAlignment.START),
                stats
            ], spacing=spacing.sm)
        else:
            content = ft.Row([avatar], alignment=ft.MainAxisAlignment.CENTER)

        return ft.Container(
            content=content,
            padding=ft.padding.all(spacing.md),
            border=ft.border.only(
                bottom=ft.BorderSide(
                    width=1,
                    color=palette.outline_variant
                )
            )
        )

    def _build_stat_item(self, label: str, value: str) -> ft.Control:
        """Build a stat item for the user profile."""
        palette = self.get_palette()
        typography = self.get_typography()
        spacing = self.get_spacing()

        return ft.Column([
            ft.Text(
                value,
                style=typography.label_large,
                color=palette.primary,
                weight=ft.FontWeight.W_600,
                text_align=ft.TextAlign.CENTER
            ),
            ft.Text(
                label,
                style=typography.body_small,
                color=palette.on_surface_variant,
                text_align=ft.TextAlign.CENTER
            )
        ], spacing=spacing.xs, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True)

    def _build_navigation_menu(self) -> ft.Control:
        """Build the main navigation menu."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Navigation items
        nav_items = [
            (NavigationItem.DASHBOARD, "Dashboard", ft.Icons.DASHBOARD, "/dashboard"),
            (NavigationItem.DOCUMENTS, "Documents", ft.Icons.DESCRIPTION, "/documents"),
            (NavigationItem.MODELS, "Models", ft.Icons.PSYCHOLOGY, "/models"),
            (NavigationItem.TRAINING, "Training", ft.Icons.FITNESS_CENTER, "/training"),
            (NavigationItem.SETTINGS, "Settings", ft.Icons.SETTINGS, "/settings")
        ]

        menu_buttons = []
        for nav_item, label, icon, route in nav_items:
            button = self._build_navigation_item(nav_item, label, icon, route)
            menu_buttons.append(button)

        return ft.Container(
            content=ft.Column(
                controls=menu_buttons,
                spacing=spacing.xs,
                tight=True
            ),
            padding=ft.padding.symmetric(
                horizontal=spacing.sm,
                vertical=spacing.md
            )
        )

    def _build_navigation_item(self, nav_item: NavigationItem, label: str, icon: str, route: str) -> ft.Control:
        """Build a single navigation menu item."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        is_active = self._active_navigation == nav_item

        # Icon
        nav_icon = ft.Icon(
            name=icon,
            size=self.get_breakpoint_value(20, 22, 24, 26),
            color=palette.primary if is_active else palette.on_surface_variant
        )

        # Label (only visible when expanded)
        nav_label = ft.Text(
            label,
            style=typography.body_medium,
            color=palette.primary if is_active else palette.on_surface,
            weight=ft.FontWeight.W_500 if is_active else ft.FontWeight.W_400,
            visible=self._current_state == SidebarState.EXPANDED
        )

        # Active indicator
        active_indicator = ft.Container(
            width=4,
            height=self.get_breakpoint_value(24, 28, 32, 36),
            bgcolor=palette.primary,
            border_radius=ft.border_radius.only(
                top_right=2,
                bottom_right=2
            ),
            visible=is_active
        )

        # Button content
        button_content = ft.Row([
            active_indicator,
            ft.Container(width=spacing.sm),
            nav_icon,
            ft.Container(width=spacing.md),
            nav_label
        ], alignment=ft.MainAxisAlignment.START, tight=True)

        return ft.Container(
            content=button_content,
            padding=ft.padding.symmetric(
                horizontal=spacing.sm,
                vertical=spacing.md
            ),
            border_radius=self.get_breakpoint_value(6, 8, 10, 12),
            bgcolor=palette.surface_container_highest if is_active else ft.Colors.TRANSPARENT,
            ink=True,
            on_click=lambda e, item=nav_item, r=route: self._on_navigation_click(item, r),
            tooltip=label if self._config.enable_tooltips and self._current_state == SidebarState.COLLAPSED else None,
            # Accessibility attributes
            data={
                "role": "menuitem",
                "aria-label": f"Navigate to {label}",
                "aria-current": "page" if is_active else "false",
                "tabindex": "0"
            }
        )

    def _build_quick_links_section(self) -> ft.Control:
        """Build the quick links section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Section header
        header = ft.Container(
            content=ft.Text(
                "Quick Links",
                style=typography.label_medium,
                color=palette.on_surface_variant,
                weight=ft.FontWeight.W_500
            ),
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            visible=self._current_state == SidebarState.EXPANDED
        )

        # Quick link items
        link_items = []
        for link in self._quick_links:
            if link.is_enabled:
                item = self._build_quick_link_item(link)
                link_items.append(item)

        return ft.Column([
            header,
            ft.Container(
                content=ft.Column(
                    controls=link_items,
                    spacing=spacing.xs,
                    tight=True
                ),
                padding=ft.padding.symmetric(
                    horizontal=spacing.sm,
                    vertical=spacing.sm
                )
            )
        ], spacing=0, tight=True)

    def _build_quick_link_item(self, link: QuickLink) -> ft.Control:
        """Build a single quick link item."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Icon
        link_icon = ft.Icon(
            name=link.icon,
            size=self.get_breakpoint_value(18, 20, 22, 24),
            color=palette.on_surface_variant
        )

        # Label and badge
        label_content = [
            ft.Text(
                link.label,
                style=typography.body_small,
                color=palette.on_surface,
                visible=self._current_state == SidebarState.EXPANDED
            )
        ]

        # Add badge if present
        if link.badge_count and link.badge_count > 0 and self._config.show_badges:
            badge = ft.Container(
                content=ft.Text(
                    str(link.badge_count),
                    style=typography.label_small,
                    color=palette.on_primary,
                    text_align=ft.TextAlign.CENTER
                ),
                bgcolor=palette.primary,
                border_radius=10,
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                visible=self._current_state == SidebarState.EXPANDED
            )
            label_content.append(badge)

        # Button content
        if self._current_state == SidebarState.EXPANDED:
            button_content = ft.Row([
                link_icon,
                ft.Container(width=spacing.md),
                ft.Row(label_content, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True)
            ], alignment=ft.MainAxisAlignment.START)
        else:
            button_content = ft.Row([link_icon], alignment=ft.MainAxisAlignment.CENTER)

        return ft.Container(
            content=button_content,
            padding=ft.padding.symmetric(
                horizontal=spacing.sm,
                vertical=spacing.sm
            ),
            border_radius=self.get_breakpoint_value(4, 6, 8, 10),
            bgcolor=ft.Colors.TRANSPARENT,
            ink=True,
            on_click=lambda e, route=link.route: self._on_quick_link_click_handler(route),
            tooltip=link.label if self._config.enable_tooltips and self._current_state == SidebarState.COLLAPSED else None
        )

    def _build_resource_monitor_section(self) -> ft.Control:
        """Build the resource monitor section."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Section header
        header = ft.Container(
            content=ft.Text(
                "Resources",
                style=typography.label_medium,
                color=palette.on_surface_variant,
                weight=ft.FontWeight.W_500
            ),
            padding=ft.padding.symmetric(
                horizontal=spacing.md,
                vertical=spacing.sm
            ),
            visible=self._current_state == SidebarState.EXPANDED
        )

        # Resource bars
        resource_bars = []

        # CPU usage
        cpu_bar = self._build_resource_bar(
            "CPU",
            self._resource_stats.cpu_usage,
            ft.Icons.MEMORY,
            palette.info
        )
        resource_bars.append(cpu_bar)

        # Memory usage
        memory_bar = self._build_resource_bar(
            "RAM",
            self._resource_stats.memory_usage,
            ft.Icons.STORAGE,
            palette.warning
        )
        resource_bars.append(memory_bar)

        # GPU usage (if available)
        if self._resource_stats.gpu_usage > 0:
            gpu_bar = self._build_resource_bar(
                "GPU",
                self._resource_stats.gpu_usage,
                ft.Icons.VIDEOGAME_ASSET,
                palette.success
            )
            resource_bars.append(gpu_bar)

        return ft.Column([
            header,
            ft.Container(
                content=ft.Column(
                    controls=resource_bars,
                    spacing=spacing.sm,
                    tight=True
                ),
                padding=ft.padding.all(spacing.md),
                border=ft.border.only(
                    top=ft.BorderSide(
                        width=1,
                        color=palette.outline_variant
                    )
                )
            )
        ], spacing=0, tight=True)

    def _build_resource_bar(self, label: str, usage: float, icon: str, color: str) -> ft.Control:
        """Build a single resource usage bar."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()

        # Clamp usage to 0-100
        usage_percent = max(0, min(100, usage))

        if self._current_state == SidebarState.EXPANDED:
            return ft.Column([
                ft.Row([
                    ft.Icon(icon, size=16, color=palette.on_surface_variant),
                    ft.Text(
                        label,
                        style=typography.body_small,
                        color=palette.on_surface_variant
                    ),
                    ft.Text(
                        f"{usage_percent:.0f}%",
                        style=typography.body_small,
                        color=palette.on_surface,
                        weight=ft.FontWeight.W_500
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.ProgressBar(
                    value=usage_percent / 100,
                    color=color,
                    bgcolor=palette.surface_container_highest,
                    height=4
                )
            ], spacing=spacing.xs, tight=True)
        else:
            # Collapsed view - just icon with color indication
            return ft.Container(
                content=ft.Icon(
                    icon,
                    size=20,
                    color=color if usage_percent > 80 else palette.on_surface_variant
                ),
                padding=ft.padding.all(spacing.xs),
                tooltip=f"{label}: {usage_percent:.0f}%" if self._config.enable_tooltips else None
            )

    # Event Handlers
    def _on_toggle_click(self, e):
        """Handle sidebar toggle button click."""
        try:
            if self._is_animating:
                return

            # Toggle state
            if self._current_state == SidebarState.EXPANDED:
                self.collapse_sidebar()
            else:
                self.expand_sidebar()

        except Exception as ex:
            logger.error(f"Error handling toggle click: {ex}")

    def _on_navigation_click(self, nav_item: NavigationItem, route: str):
        """Handle navigation item click."""
        try:
            # Update active navigation
            self._active_navigation = nav_item

            # Trigger callback
            if self._on_navigation_change:
                self._on_navigation_change(nav_item)

            # Auto-collapse on mobile after navigation
            if self._is_mobile and self._current_state == SidebarState.EXPANDED:
                self.collapse_sidebar()

            # Update UI
            self.update()

            logger.info(f"Navigation changed to: {nav_item.value}")

        except Exception as ex:
            logger.error(f"Error handling navigation click: {ex}")

    def _on_quick_link_click_handler(self, route: str):
        """Handle quick link click."""
        try:
            if self._on_quick_link_click:
                self._on_quick_link_click(route)

            logger.info(f"Quick link clicked: {route}")

        except Exception as ex:
            logger.error(f"Error handling quick link click: {ex}")

    # Public Methods
    def expand_sidebar(self):
        """Expand the sidebar."""
        try:
            if self._current_state == SidebarState.EXPANDED or self._is_animating:
                return

            self._is_animating = True
            self._current_state = SidebarState.EXPANDED

            # Update width
            if self._sidebar_container:
                self._sidebar_container.width = self._config.expanded_width

            # Trigger callback
            if self._on_sidebar_toggle:
                self._on_sidebar_toggle(self._current_state)

            # Update UI
            self.update()

            # Reset animation flag after duration
            asyncio.create_task(self._reset_animation_flag())

            logger.info("Sidebar expanded")

        except Exception as ex:
            logger.error(f"Error expanding sidebar: {ex}")
            self._is_animating = False

    def collapse_sidebar(self):
        """Collapse the sidebar."""
        try:
            if self._current_state == SidebarState.COLLAPSED or self._is_animating:
                return

            self._is_animating = True
            self._current_state = SidebarState.COLLAPSED

            # Update width
            if self._sidebar_container:
                self._sidebar_container.width = self._config.collapsed_width

            # Trigger callback
            if self._on_sidebar_toggle:
                self._on_sidebar_toggle(self._current_state)

            # Update UI
            self.update()

            # Reset animation flag after duration
            asyncio.create_task(self._reset_animation_flag())

            logger.info("Sidebar collapsed")

        except Exception as ex:
            logger.error(f"Error collapsing sidebar: {ex}")
            self._is_animating = False

    def toggle_sidebar(self):
        """Toggle sidebar state."""
        if self._current_state == SidebarState.EXPANDED:
            self.collapse_sidebar()
        else:
            self.expand_sidebar()

    def set_active_navigation(self, nav_item: NavigationItem):
        """Set the active navigation item."""
        try:
            self._active_navigation = nav_item
            self.update()

        except Exception as ex:
            logger.error(f"Error setting active navigation: {ex}")

    def update_resource_stats(self, stats: ResourceStats):
        """Update resource monitoring statistics."""
        try:
            self._resource_stats = stats

            # Update UI if resource monitor is visible
            if self._config.show_resource_monitor:
                self.update()

        except Exception as ex:
            logger.error(f"Error updating resource stats: {ex}")

    def update_user_profile(self, profile: UserProfile):
        """Update user profile information."""
        try:
            self._user_profile = profile

            # Update UI if user profile is visible
            if self._config.show_user_profile:
                self.update()

        except Exception as ex:
            logger.error(f"Error updating user profile: {ex}")

    def update_quick_links(self, links: List[QuickLink]):
        """Update quick links."""
        try:
            self._quick_links = links

            # Update UI if quick links are visible
            if self._config.show_quick_links:
                self.update()

        except Exception as ex:
            logger.error(f"Error updating quick links: {ex}")

    async def _reset_animation_flag(self):
        """Reset animation flag after animation duration."""
        await asyncio.sleep(self._config.animation_duration / 1000)
        self._is_animating = False

    # Properties
    @property
    def current_state(self) -> SidebarState:
        """Get current sidebar state."""
        return self._current_state

    @property
    def active_navigation(self) -> NavigationItem:
        """Get active navigation item."""
        return self._active_navigation

    @property
    def is_expanded(self) -> bool:
        """Check if sidebar is expanded."""
        return self._current_state == SidebarState.EXPANDED

    @property
    def is_collapsed(self) -> bool:
        """Check if sidebar is collapsed."""
        return self._current_state == SidebarState.COLLAPSED

    def on_theme_changed(self):
        """Handle theme change events."""
        try:
            # Rebuild the sidebar with new theme
            self.update()

        except Exception as ex:
            logger.error(f"Error handling theme change: {ex}")

    def on_responsive_change(self, screen_size: ScreenSize):
        """Handle responsive layout changes."""
        try:
            old_is_mobile = self._is_mobile
            self._is_mobile = screen_size == ScreenSize.MOBILE

            # Auto-collapse on mobile
            if self._is_mobile and not old_is_mobile and self._config.enable_auto_collapse:
                self.collapse_sidebar()
            # Auto-expand on desktop
            elif not self._is_mobile and old_is_mobile:
                self.expand_sidebar()

            # Update UI
            self.update()

        except Exception as ex:
            logger.error(f"Error handling responsive change: {ex}")

    def on_keyboard_event(self, e: ft.KeyboardEvent):
        """Handle keyboard navigation events."""
        try:
            # Toggle sidebar with Ctrl+B or Ctrl+Shift+B
            if e.key == "B" and e.ctrl:
                if e.shift:
                    # Force expand
                    self.expand_sidebar()
                else:
                    # Toggle
                    self.toggle_sidebar()
                return True

            # Navigate with arrow keys when sidebar has focus
            if e.key == "ArrowDown":
                self._navigate_next()
                return True
            elif e.key == "ArrowUp":
                self._navigate_previous()
                return True
            elif e.key == "Enter" or e.key == "Space":
                self._activate_current_navigation()
                return True
            elif e.key == "Escape":
                # Collapse sidebar on escape
                if self._current_state == SidebarState.EXPANDED:
                    self.collapse_sidebar()
                return True

            return False

        except Exception as ex:
            logger.error(f"Error handling keyboard event: {ex}")
            return False

    def _navigate_next(self):
        """Navigate to next menu item."""
        try:
            nav_items = list(NavigationItem)
            current_index = nav_items.index(self._active_navigation)
            next_index = (current_index + 1) % len(nav_items)
            self.set_active_navigation(nav_items[next_index])

        except Exception as ex:
            logger.error(f"Error navigating next: {ex}")

    def _navigate_previous(self):
        """Navigate to previous menu item."""
        try:
            nav_items = list(NavigationItem)
            current_index = nav_items.index(self._active_navigation)
            prev_index = (current_index - 1) % len(nav_items)
            self.set_active_navigation(nav_items[prev_index])

        except Exception as ex:
            logger.error(f"Error navigating previous: {ex}")

    def _activate_current_navigation(self):
        """Activate the currently focused navigation item."""
        try:
            # Simulate click on current navigation
            route_map = {
                NavigationItem.DASHBOARD: "/dashboard",
                NavigationItem.DOCUMENTS: "/documents",
                NavigationItem.MODELS: "/models",
                NavigationItem.TRAINING: "/training",
                NavigationItem.SETTINGS: "/settings",
                NavigationItem.HELP: "/help"
            }

            route = route_map.get(self._active_navigation, "/dashboard")
            self._on_navigation_click(self._active_navigation, route)

        except Exception as ex:
            logger.error(f"Error activating navigation: {ex}")

    def focus_sidebar(self):
        """Set focus to the sidebar for keyboard navigation."""
        try:
            if self._sidebar_container:
                self._sidebar_container.focus()

        except Exception as ex:
            logger.error(f"Error focusing sidebar: {ex}")

    def get_accessibility_info(self) -> Dict[str, Any]:
        """Get accessibility information for screen readers."""
        try:
            nav_items = list(NavigationItem)
            current_index = nav_items.index(self._active_navigation)

            return {
                "role": "navigation",
                "label": "Main navigation sidebar",
                "expanded": self._current_state == SidebarState.EXPANDED,
                "current_item": self._active_navigation.value,
                "current_index": current_index + 1,
                "total_items": len(nav_items),
                "keyboard_shortcuts": {
                    "toggle": "Ctrl+B",
                    "expand": "Ctrl+Shift+B",
                    "navigate": "Arrow keys",
                    "activate": "Enter or Space",
                    "collapse": "Escape"
                }
            }

        except Exception as ex:
            logger.error(f"Error getting accessibility info: {ex}")
            return {}

    def announce_state_change(self, message: str):
        """Announce state changes to screen readers."""
        try:
            # This would integrate with a screen reader announcement system
            # For now, we log the message
            logger.info(f"Screen reader announcement: {message}")

        except Exception as ex:
            logger.error(f"Error announcing state change: {ex}")
